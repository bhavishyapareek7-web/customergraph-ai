"""Orchestrator Agent: Coordinates all sub-agents and manages the conversational loop."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.config import Settings, get_settings
from app.graph.connection import GraphManager
from app.graph.schema import GRAPH_SCHEMA_DESCRIPTION
from app.models.schemas import (
    AgentResponse,
    ChatResponse,
    GraphPath,
    ReasoningStep,
)
from app.agents.query_agent import QueryAgent
from app.agents.analysis_agent import AnalysisAgent
from app.agents.memory_agent import MemoryAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Central coordinator that routes user requests to specialized sub-agents.

    Responsibilities:
    1. Classify user intent (query, analysis, memory, general)
    2. Build relevant context from past sessions
    3. Route to the appropriate agent(s)
    4. Collect reasoning traces from all agents
    5. Save the conversation to memory
    6. Return ChatResponse with graph visualization data
    """

    def __init__(self, config: Optional[Settings] = None) -> None:
        """Initialize the OrchestratorAgent and all sub-agents.

        Args:
            config: Application settings. If None, loads from environment.
        """
        self.config = config or get_settings()

        # Initialize graph manager
        self.graph_manager = GraphManager(
            host=self.config.FALKORDB_HOST,
            port=self.config.FALKORDB_PORT,
            graph_name=self.config.GRAPH_NAME,
        )
        try:
            self.graph_manager.connect()
        except Exception as exc:
            logger.warning("FalkorDB not immediately reachable at startup (%s). Will retry on first query.", exc)

        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=self.config.OPENAI_API_KEY)

        # Initialize sub-agents
        self.query_agent = QueryAgent(
            openai_client=self.openai_client,
            graph_manager=self.graph_manager,
            model=self.config.LLM_MODEL,
        )
        self.analysis_agent = AnalysisAgent(
            openai_client=self.openai_client,
            graph_manager=self.graph_manager,
            model=self.config.LLM_MODEL,
        )
        self.memory_agent = MemoryAgent(graph_manager=self.graph_manager)

        # Conversation history per session
        self._session_histories: Dict[str, List[Dict[str, str]]] = {}

        logger.info("OrchestratorAgent initialized successfully.")

    def chat(self, message: str, session_id: Optional[str] = None) -> ChatResponse:
        """Process a user chat message through the agent pipeline.

        Args:
            message: The user's natural language message.
            session_id: Optional session ID for continuity. Auto-generated if None.

        Returns:
            ChatResponse containing the answer, reasoning trace, and graph data.
        """
        # Generate or reuse session ID
        if not session_id:
            session_id = self.memory_agent.generate_session_id()

        # Initialize session history if new
        if session_id not in self._session_histories:
            self._session_histories[session_id] = []

        # 1. Classify intent
        intent = self._classify_intent(message)
        logger.info("Classified intent as '%s' for message: %s", intent, message[:100])

        # 2. Build context from memory
        context = self._build_context(session_id)

        # 3. Add context to conversation history
        history = self._session_histories[session_id].copy()
        if context and not context.startswith("No prior"):
            history.insert(0, {"role": "system", "content": context})

        # 4. Route to appropriate agent
        agent_response: Optional[AgentResponse] = None

        if intent == "analysis":
            agent_response = self._handle_analysis(message, history)
        elif intent == "memory":
            agent_response = self._handle_memory_query(message, session_id)
        else:
            # Default: query agent handles general and query intents
            agent_response = self.query_agent.process(message, history)

        if agent_response is None:
            agent_response = AgentResponse(
                answer="I wasn't able to process your request. Please try rephrasing.",
                reasoning_trace=[],
                graph_paths=[],
                cypher_queries_used=[],
                confidence=0.0,
                sources=[],
            )

        # 5. Update session history
        self._session_histories[session_id].append(
            {"role": "user", "content": message}
        )
        self._session_histories[session_id].append(
            {"role": "assistant", "content": agent_response.answer}
        )

        # 6. Save to memory
        summary = f"User asked: '{message[:200]}' → Agent responded with {len(agent_response.reasoning_trace)} reasoning steps."
        self.memory_agent.save_conversation(
            session_id=session_id,
            messages=self._session_histories[session_id],
            summary=summary,
        )

        # 7. Build graph visualization data
        graph_data = self._build_graph_visualization(agent_response)

        return ChatResponse(
            response=agent_response,
            session_id=session_id,
            graph_data=graph_data,
        )

    def _classify_intent(self, message: str) -> str:
        """Classify the user's message into an intent category.

        Uses keyword heuristics first, falls back to LLM for ambiguous cases.

        Args:
            message: The user's message.

        Returns:
            One of: 'query', 'analysis', 'memory', 'general'
        """
        message_lower = message.lower()

        # Analysis keywords
        analysis_keywords = [
            "analyze", "analysis", "health", "churn", "risk", "predict",
            "diagnose", "diagnostic", "recommend", "action", "why",
            "explain", "trend", "signal", "factor",
        ]
        if any(kw in message_lower for kw in analysis_keywords):
            return "analysis"

        # Memory keywords
        memory_keywords = [
            "remember", "last time", "previous session", "history",
            "past conversation", "what did we", "earlier", "before",
            "session", "recall",
        ]
        if any(kw in message_lower for kw in memory_keywords):
            return "memory"

        # Default to query
        return "query"

    def _build_context(self, session_id: str) -> str:
        """Build context string from memory for the current session.

        Args:
            session_id: Current session identifier.

        Returns:
            Context string from past sessions and insights.
        """
        try:
            return self.memory_agent.get_relevant_context(
                query="", session_id=session_id
            )
        except Exception as exc:
            logger.warning("Failed to build context: %s", exc)
            return ""

    def _handle_analysis(
        self,
        message: str,
        history: List[Dict[str, str]],
    ) -> AgentResponse:
        """Handle analysis-type requests using both analysis and query agents.

        Args:
            message: The user's analysis request.
            history: Conversation history.

        Returns:
            Merged AgentResponse from analysis and query agents.
        """
        message_lower = message.lower()

        # Check if asking about a specific customer
        customer_name = self._extract_customer_name(message)

        if customer_name:
            # Deep health analysis for specific customer
            health = self.analysis_agent.analyze_customer_health(customer_name)
            explanation = self.analysis_agent.explain_reasoning(health)

            return AgentResponse(
                answer=explanation,
                reasoning_trace=health.reasoning_path,
                graph_paths=[],
                cypher_queries_used=[
                    step.cypher_query
                    for step in health.reasoning_path
                    if step.cypher_query
                ],
                confidence=0.9,
                sources=["FalkorDB Graph", "OpenAI GPT-4o", "Analysis Agent"],
            )
        else:
            # Portfolio-wide churn prediction
            if any(kw in message_lower for kw in ["all", "portfolio", "churn", "risk", "at-risk", "at risk"]):
                summaries = self.analysis_agent.predict_churn_risk()
                if summaries:
                    lines = ["## Customer Portfolio Risk Assessment\n"]
                    for s in summaries:
                        risk_emoji = {
                            "critical": "🔴", "high": "🟠",
                            "medium": "🟡", "low": "🟢",
                        }.get(s.risk_level, "⚪")
                        lines.append(
                            f"{risk_emoji} **{s.name}** | Health: {s.health_score:.0f}/100 | "
                            f"MRR: ${s.mrr:,.0f} | Risk: {s.risk_level.upper()} | "
                            f"Open Tickets: {s.open_tickets}"
                        )
                    return AgentResponse(
                        answer="\n".join(lines),
                        reasoning_trace=[
                            ReasoningStep(
                                step=1,
                                description="Queried all customers with health scores and open tickets",
                                cypher_query="MATCH (c:Customer) OPTIONAL MATCH (c)-[:HAS_SCORE]->(h:HealthScore) ...",
                                result_summary=f"Found {len(summaries)} customers",
                                nodes_visited=["Customer", "HealthScore", "Ticket"],
                                relationships_followed=["HAS_SCORE", "RAISED"],
                            )
                        ],
                        graph_paths=[],
                        cypher_queries_used=["Portfolio churn analysis query"],
                        confidence=0.85,
                        sources=["FalkorDB Graph", "Analysis Agent"],
                    )

            # Fallback to query agent for general analysis
            return self.query_agent.process(message, history)

    def _handle_memory_query(
        self,
        message: str,
        session_id: str,
    ) -> AgentResponse:
        """Handle memory-related queries.

        Args:
            message: The user's memory query.
            session_id: Current session ID.

        Returns:
            AgentResponse with memory context.
        """
        sessions = self.memory_agent.get_all_sessions()

        if not sessions:
            return AgentResponse(
                answer="No past conversation sessions found. This appears to be our first interaction!",
                reasoning_trace=[
                    ReasoningStep(
                        step=1,
                        description="Queried Session nodes in FalkorDB",
                        cypher_query="MATCH (s:Session) RETURN s ORDER BY s.timestamp DESC",
                        result_summary="No sessions found",
                        nodes_visited=["Session"],
                        relationships_followed=[],
                    )
                ],
                graph_paths=[],
                cypher_queries_used=["MATCH (s:Session) ..."],
                confidence=0.9,
                sources=["FalkorDB Graph", "Memory Agent"],
            )

        lines = ["## Past Conversation Sessions\n"]
        for sess in sessions:
            sid = sess.get("session_id", "unknown")
            summary = sess.get("summary", "No summary")
            user_q = sess.get("user_query", "")
            ts = sess.get("timestamp", "")
            lines.append(f"- **{ts}** (Session: `{sid}`)")
            if user_q:
                lines.append(f"  - Query: *{user_q}*")
            lines.append(f"  - Summary: {summary}")

        return AgentResponse(
            answer="\n".join(lines),
            reasoning_trace=[
                ReasoningStep(
                    step=1,
                    description="Retrieved all past session nodes from FalkorDB",
                    cypher_query="MATCH (s:Session) RETURN s ORDER BY s.timestamp DESC LIMIT 15",
                    result_summary=f"Found {len(sessions)} past sessions",
                    nodes_visited=["Session"],
                    relationships_followed=[],
                )
            ],
            graph_paths=[],
            cypher_queries_used=["MATCH (s:Session) ..."],
            confidence=0.95,
            sources=["FalkorDB Graph", "Memory Agent"],
        )

    def _extract_customer_name(self, message: str) -> Optional[str]:
        """Extract a customer name from the user's message using known customers.

        Args:
            message: The user's message.

        Returns:
            Matched customer name or None.
        """
        known_customers = [
            "Acme Corp", "TechFlow Inc", "DataBridge Solutions",
            "CloudNine Startup", "SecureVault Ltd", "GreenLeaf Organics",
            "QuantumLabs", "MetroLogistics", "PixelPerfect Design", "NovaPharma",
        ]
        message_lower = message.lower()
        for name in known_customers:
            if name.lower() in message_lower:
                return name
            # Also check partial matches (first word)
            first_word = name.split()[0].lower()
            if first_word in message_lower and len(first_word) > 3:
                return name
        return None

    def _build_graph_visualization(
        self,
        agent_response: AgentResponse,
    ) -> Optional[Dict[str, Any]]:
        """Build graph visualization data from the agent's reasoning trace.

        Extracts nodes and edges from the reasoning steps to render
        in streamlit-agraph.

        Args:
            agent_response: The agent's response with reasoning trace.

        Returns:
            Dict with 'nodes' and 'edges' lists for visualization, or None.
        """
        if not agent_response.reasoning_trace:
            return None

        node_colors = {
            "Customer": "#4285F4",      # Google Blue
            "Product": "#34A853",       # Green
            "Ticket": "#EA4335",        # Red
            "Interaction": "#FBBC05",   # Yellow
            "TeamMember": "#9C27B0",    # Purple
            "HealthScore": "#FF6D00",   # Orange
            "Decision": "#00BCD4",      # Cyan
            "Feature": "#8BC34A",       # Light Green
            "Session": "#607D8B",       # Blue Grey
            "Insight": "#E91E63",       # Pink
            "Dynamic": "#757575",       # Grey
        }

        nodes_seen = set()
        nodes_list: List[Dict[str, Any]] = []
        edges_list: List[Dict[str, Any]] = []

        for step in agent_response.reasoning_trace:
            for nv in step.nodes_visited:
                if nv not in nodes_seen:
                    nodes_seen.add(nv)
                    nodes_list.append({
                        "id": nv,
                        "label": nv,
                        "title": f"Node type: {nv}",
                        "color": node_colors.get(nv, "#757575"),
                        "size": 30,
                    })

            for i, rf in enumerate(step.relationships_followed):
                # Create edge between consecutive node types if available
                visited = step.nodes_visited
                if len(visited) >= 2:
                    edges_list.append({
                        "source": visited[0] if i == 0 else visited[min(i, len(visited) - 1)],
                        "target": visited[min(i + 1, len(visited) - 1)],
                        "label": rf,
                    })

        if not nodes_list:
            return None

        return {"nodes": nodes_list, "edges": edges_list}

    def get_graph_visualization(
        self, cypher_queries: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Execute Cypher queries and extract visualization data.

        Args:
            cypher_queries: List of Cypher query strings to execute.

        Returns:
            Dict with 'nodes' and 'edges' for rendering.
        """
        nodes_list: List[Dict[str, Any]] = []
        edges_list: List[Dict[str, Any]] = []
        nodes_seen: set = set()

        node_colors = {
            "Customer": "#4285F4",
            "Product": "#34A853",
            "Ticket": "#EA4335",
            "Interaction": "#FBBC05",
            "TeamMember": "#9C27B0",
            "HealthScore": "#FF6D00",
            "Decision": "#00BCD4",
            "Feature": "#8BC34A",
            "Session": "#607D8B",
            "Insight": "#E91E63",
        }

        for query in cypher_queries:
            try:
                result = self.graph_manager.execute_readonly(query)
                rows = getattr(result, "result_set", [])
                for row in rows:
                    for val in row:
                        if hasattr(val, "labels") and hasattr(val, "properties"):
                            labels = val.labels if isinstance(val.labels, list) else [val.labels]
                            label = labels[0] if labels else "Unknown"
                            props = val.properties if hasattr(val, "properties") else {}
                            node_id = props.get("id", props.get("name", str(id(val))))
                            if node_id not in nodes_seen:
                                nodes_seen.add(node_id)
                                nodes_list.append({
                                    "id": node_id,
                                    "label": props.get("name", props.get("title", node_id)),
                                    "title": json.dumps(props, default=str),
                                    "color": node_colors.get(label, "#757575"),
                                    "size": 25,
                                })
            except Exception as exc:
                logger.warning("Could not execute visualization query: %s", exc)

        if not nodes_list:
            return None

        return {"nodes": nodes_list, "edges": edges_list}
