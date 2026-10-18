"""Agent tools wrapping FalkorDB openCypher graph operations for CustomerGraph AI."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.graph.queries import (
    AT_RISK_CUSTOMERS_QUERY,
    CHURN_SIGNALS_HEALTH_QUERY,
    CHURN_SIGNALS_TICKETS_QUERY,
    CUSTOMER_360_QUERY,
    CUSTOMER_360_RECENT_INTERACTIONS,
    CUSTOMER_INTERACTIONS_QUERY,
    CUSTOMER_NETWORK_QUERY,
    DECISION_HISTORY_QUERY,
    ESCALATION_PATH_QUERY,
    FEATURE_ADOPTION_QUERY,
    GET_ALL_SESSIONS_QUERY,
    GET_SESSION_BY_ID_QUERY,
    OPEN_TICKETS_ALL_QUERY,
    OPEN_TICKETS_CUSTOMER_QUERY,
    SAVE_INSIGHT_QUERY,
    SAVE_INSIGHT_WITH_CUSTOMER_QUERY,
    SAVE_SESSION_MEMORY_QUERY,
    SEARCH_CUSTOMER_QUERY,
    TEAM_INFLUENCE_QUERY,
)

logger = logging.getLogger(__name__)

# Tool registry: maps tool name to metadata and function
TOOLS: Dict[str, Dict[str, Any]] = {}


def tool(name: str, description: str, parameters: Optional[Dict[str, Any]] = None):
    """Decorator to register a function as an agent tool.

    Args:
        name: Unique tool identifier.
        description: Natural language summary of the tool's capability.
        parameters: JSON schema definition of the tool's arguments.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        TOOLS[name] = {
            "name": name,
            "description": description,
            "function": func,
            "parameters": parameters or {"type": "object", "properties": {}},
        }
        return func
    return decorator


def format_graph_result(result: Any, headers: Optional[List[str]] = None) -> str:
    """Format raw FalkorDB QueryResult or parsed records into a clean string representation.

    Args:
        result: QueryResult instance or list of dictionaries.
        headers: Optional explicit column headers.

    Returns:
        Formatted multi-line text or Markdown representation.
    """
    if result is None:
        return "No records found."

    # If it's already a list of dicts
    if isinstance(result, list):
        if not result:
            return "No records found."
        lines = []
        for i, item in enumerate(result, 1):
            if isinstance(item, dict):
                formatted_item = ", ".join(f"{k}: {v}" for k, v in item.items() if v is not None)
                lines.append(f"{i}. {formatted_item}")
            else:
                lines.append(f"{i}. {item}")
        return "\n".join(lines)

    # Check for FalkorDB QueryResult object
    parsed_rows: List[List[Any]] = getattr(result, "result_set", [])
    if not parsed_rows:
        return "No records found."

    col_names = headers
    if not col_names and hasattr(result, "header") and result.header:
        col_names = [
            h if isinstance(h, str) else getattr(h, "name", str(h))
            for h in result.header
        ]
    if not col_names:
        col_names = [f"Col_{idx + 1}" for idx in range(len(parsed_rows[0]))]

    lines = []
    for idx, row in enumerate(parsed_rows, 1):
        fields = []
        for i, val in enumerate(row):
            label = col_names[i] if i < len(col_names) else f"Field_{i}"
            # Extract properties if val is a Node/Edge
            if hasattr(val, "properties"):
                val_repr = json.dumps(val.properties, default=str)
            else:
                val_repr = str(val)
            fields.append(f"{label}: {val_repr}")
        lines.append(f"{idx}. " + " | ".join(fields))

    return "\n".join(lines)


def _safe_execute(graph_manager: Any, query: str, params: Optional[Dict[str, Any]] = None, readonly: bool = True) -> Any:
    """Safely execute query with fallback to execute_query if execute_readonly is unavailable."""
    params = params or {}
    if readonly and hasattr(graph_manager, "execute_readonly"):
        return graph_manager.execute_readonly(query, params)
    elif hasattr(graph_manager, "execute_query"):
        return graph_manager.execute_query(query, params)
    elif hasattr(graph_manager, "query"):
        return graph_manager.query(query, params)
    raise AttributeError("Graph manager instance lacks query execution methods.")


# -----------------------------------------------------------------------------
# 1. search_customer
# -----------------------------------------------------------------------------
@tool(
    name="search_customer",
    description="Search for a customer by company name or partial string. Returns basic info, MRR, status, and health score.",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Full or partial name of the customer company to search for",
            }
        },
        "required": ["name"],
    },
)
def search_customer(graph_manager: Any, name: str) -> Dict[str, Any]:
    """Search for a customer by name."""
    query = SEARCH_CUSTOMER_QUERY
    params = {"name": name}
    try:
        raw_res = _safe_execute(graph_manager, query, params, readonly=True)
        records = graph_manager.parse_result(raw_res) if hasattr(graph_manager, "parse_result") else raw_res
        text_result = format_graph_result(records)
        return {
            "result": text_result,
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer", "HealthScore"],
            "relationships_followed": ["HAS_SCORE"],
        }
    except Exception as exc:
        logger.error("Error in search_customer: %s", exc)
        return {
            "result": f"Error searching customer: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 2. get_customer_360
# -----------------------------------------------------------------------------
@tool(
    name="get_customer_360",
    description="Get a comprehensive 360-degree view of a customer including products used, tickets, health score, account team, and recent interactions.",
    parameters={
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "The exact or partial name of the customer to inspect",
            }
        },
        "required": ["customer_name"],
    },
)
def get_customer_360(graph_manager: Any, customer_name: str) -> Dict[str, Any]:
    """Retrieve full 360-degree profile for a customer."""
    params = {"customer_name": customer_name}
    try:
        # Profile query
        res_profile = _safe_execute(graph_manager, CUSTOMER_360_QUERY, params, readonly=True)
        profile_data = graph_manager.parse_result(res_profile) if hasattr(graph_manager, "parse_result") else res_profile
        
        # Interactions query
        res_inter = _safe_execute(graph_manager, CUSTOMER_360_RECENT_INTERACTIONS, params, readonly=True)
        inter_data = graph_manager.parse_result(res_inter) if hasattr(graph_manager, "parse_result") else res_inter

        profile_text = format_graph_result(profile_data)
        inter_text = format_graph_result(inter_data)

        combined_result = (
            f"=== Customer Profile & Health ===\n{profile_text}\n\n"
            f"=== Recent Touchpoints ===\n{inter_text}"
        )
        return {
            "result": combined_result,
            "cypher_query": CUSTOMER_360_QUERY.strip(),
            "nodes_visited": ["Customer", "HealthScore", "Product", "TeamMember", "Ticket", "Interaction"],
            "relationships_followed": ["HAS_SCORE", "USES", "MANAGED_BY", "RAISED", "HAD"],
        }
    except Exception as exc:
        logger.error("Error in get_customer_360: %s", exc)
        return {
            "result": f"Error retrieving customer 360 view: {exc}",
            "cypher_query": CUSTOMER_360_QUERY.strip(),
            "nodes_visited": ["Customer"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 3. get_at_risk_customers
# -----------------------------------------------------------------------------
@tool(
    name="get_at_risk_customers",
    description="Retrieve all customers considered at-risk due to low health score (<65), declining trends, or active critical issues.",
    parameters={"type": "object", "properties": {}},
)
def get_at_risk_customers(graph_manager: Any) -> Dict[str, Any]:
    """List all at-risk customers."""
    query = AT_RISK_CUSTOMERS_QUERY
    try:
        res = _safe_execute(graph_manager, query, readonly=True)
        records = graph_manager.parse_result(res) if hasattr(graph_manager, "parse_result") else res
        text_result = format_graph_result(records)
        return {
            "result": text_result,
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer", "HealthScore", "Ticket", "TeamMember"],
            "relationships_followed": ["HAS_SCORE", "RAISED", "MANAGED_BY"],
        }
    except Exception as exc:
        logger.error("Error in get_at_risk_customers: %s", exc)
        return {
            "result": f"Error fetching at-risk customers: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 4. analyze_churn_signals
# -----------------------------------------------------------------------------
@tool(
    name="analyze_churn_signals",
    description="Analyze churn signals, open complaints, health trends, and unresolved tickets for a specific customer.",
    parameters={
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Name of the customer to analyze for churn risk",
            }
        },
        "required": ["customer_name"],
    },
)
def analyze_churn_signals(graph_manager: Any, customer_name: str) -> Dict[str, Any]:
    """Analyze churn indicators for a given customer."""
    params = {"customer_name": customer_name}
    try:
        health_res = _safe_execute(graph_manager, CHURN_SIGNALS_HEALTH_QUERY, params, readonly=True)
        health_data = graph_manager.parse_result(health_res) if hasattr(graph_manager, "parse_result") else health_res

        tkt_res = _safe_execute(graph_manager, CHURN_SIGNALS_TICKETS_QUERY, params, readonly=True)
        tkt_data = graph_manager.parse_result(tkt_res) if hasattr(graph_manager, "parse_result") else tkt_res

        summary = (
            f"=== Health Indicators ===\n{format_graph_result(health_data)}\n\n"
            f"=== Open & Critical Issues ===\n{format_graph_result(tkt_data)}"
        )
        return {
            "result": summary,
            "cypher_query": CHURN_SIGNALS_HEALTH_QUERY.strip() + " ; " + CHURN_SIGNALS_TICKETS_QUERY.strip(),
            "nodes_visited": ["Customer", "HealthScore", "Ticket"],
            "relationships_followed": ["HAS_SCORE", "RAISED"],
        }
    except Exception as exc:
        logger.error("Error in analyze_churn_signals: %s", exc)
        return {
            "result": f"Error analyzing churn signals: {exc}",
            "cypher_query": CHURN_SIGNALS_HEALTH_QUERY.strip(),
            "nodes_visited": ["Customer"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 5. get_customer_interactions
# -----------------------------------------------------------------------------
@tool(
    name="get_customer_interactions",
    description="Retrieve recent interactions, call summaries, and meeting touchpoints for a customer.",
    parameters={
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Name of the customer whose touchpoints to retrieve",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of interactions to return (default: 10)",
            },
        },
        "required": ["customer_name"],
    },
)
def get_customer_interactions(graph_manager: Any, customer_name: str, limit: int = 10) -> Dict[str, Any]:
    """Fetch customer interactions history."""
    query = CUSTOMER_INTERACTIONS_QUERY
    params = {"customer_name": customer_name, "limit": limit}
    try:
        raw = _safe_execute(graph_manager, query, params, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer", "Interaction", "TeamMember"],
            "relationships_followed": ["HAD", "CONDUCTED_BY"],
        }
    except Exception as exc:
        logger.error("Error in get_customer_interactions: %s", exc)
        return {
            "result": f"Error retrieving interactions: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 6. get_open_tickets
# -----------------------------------------------------------------------------
@tool(
    name="get_open_tickets",
    description="Retrieve active open support tickets. Can optionally filter by customer name.",
    parameters={
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Optional customer name to filter tickets for",
            }
        },
    },
)
def get_open_tickets(graph_manager: Any, customer_name: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve open tickets, optionally filtered by customer."""
    if customer_name:
        query = OPEN_TICKETS_CUSTOMER_QUERY
        params = {"customer_name": customer_name}
    else:
        query = OPEN_TICKETS_ALL_QUERY
        params = {}
    try:
        raw = _safe_execute(graph_manager, query, params, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer", "Ticket", "TeamMember"],
            "relationships_followed": ["RAISED", "ASSIGNED_TO"],
        }
    except Exception as exc:
        logger.error("Error in get_open_tickets: %s", exc)
        return {
            "result": f"Error retrieving open tickets: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Ticket"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 7. get_escalation_path
# -----------------------------------------------------------------------------
@tool(
    name="get_escalation_path",
    description="Trace the escalation chain and responsible team members for a given ticket ID.",
    parameters={
        "type": "object",
        "properties": {
            "ticket_id": {
                "type": "string",
                "description": "The ticket identifier, e.g., 'tkt_101'",
            }
        },
        "required": ["ticket_id"],
    },
)
def get_escalation_path(graph_manager: Any, ticket_id: str) -> Dict[str, Any]:
    """Trace escalation path for a ticket."""
    query = ESCALATION_PATH_QUERY
    params = {"ticket_id": ticket_id}
    try:
        raw = _safe_execute(graph_manager, query, params, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["Ticket", "Customer", "TeamMember"],
            "relationships_followed": ["RAISED", "ASSIGNED_TO", "ESCALATED_TO"],
        }
    except Exception as exc:
        logger.error("Error in get_escalation_path: %s", exc)
        return {
            "result": f"Error retrieving escalation path: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Ticket"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 8. get_team_influence
# -----------------------------------------------------------------------------
@tool(
    name="get_team_influence",
    description="Analyze CS and Support team members by the number of accounts managed, MRR impact, and touchpoints.",
    parameters={"type": "object", "properties": {}},
)
def get_team_influence(graph_manager: Any) -> Dict[str, Any]:
    """Identify key team members and their account distribution."""
    query = TEAM_INFLUENCE_QUERY
    try:
        raw = _safe_execute(graph_manager, query, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["TeamMember", "Customer", "Ticket", "Interaction"],
            "relationships_followed": ["MANAGED_BY", "ASSIGNED_TO", "CONDUCTED_BY"],
        }
    except Exception as exc:
        logger.error("Error in get_team_influence: %s", exc)
        return {
            "result": f"Error fetching team influence: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["TeamMember"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 9. get_decision_history
# -----------------------------------------------------------------------------
@tool(
    name="get_decision_history",
    description="Retrieve strategic, commercial, and operational decisions recorded for a customer.",
    parameters={
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Name of the customer whose decision history to retrieve",
            }
        },
        "required": ["customer_name"],
    },
)
def get_decision_history(graph_manager: Any, customer_name: str) -> Dict[str, Any]:
    """Retrieve decision log for a customer."""
    query = DECISION_HISTORY_QUERY
    params = {"customer_name": customer_name}
    try:
        raw = _safe_execute(graph_manager, query, params, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["Decision", "Customer", "TeamMember"],
            "relationships_followed": ["ABOUT", "MADE"],
        }
    except Exception as exc:
        logger.error("Error in get_decision_history: %s", exc)
        return {
            "result": f"Error retrieving decision history: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Decision"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 10. get_customer_network
# -----------------------------------------------------------------------------
@tool(
    name="get_customer_network",
    description="Find connected customers through shared products, account managers, industry, or similarity relationships.",
    parameters={
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Name of the customer to analyze connectivity for",
            }
        },
        "required": ["customer_name"],
    },
)
def get_customer_network(graph_manager: Any, customer_name: str) -> Dict[str, Any]:
    """Find customer network and graph associations."""
    query = CUSTOMER_NETWORK_QUERY
    params = {"customer_name": customer_name}
    try:
        raw = _safe_execute(graph_manager, query, params, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer"],
            "relationships_followed": ["USES", "MANAGED_BY", "SIMILAR_TO"],
        }
    except Exception as exc:
        logger.error("Error in get_customer_network: %s", exc)
        return {
            "result": f"Error exploring customer network: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 11. get_feature_adoption
# -----------------------------------------------------------------------------
@tool(
    name="get_feature_adoption",
    description="Examine feature adoption levels and product subscription status for a customer.",
    parameters={
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Name of the customer to inspect feature adoption for",
            }
        },
        "required": ["customer_name"],
    },
)
def get_feature_adoption(graph_manager: Any, customer_name: str) -> Dict[str, Any]:
    """Inspect customer feature adoption and product licenses."""
    query = FEATURE_ADOPTION_QUERY
    params = {"customer_name": customer_name}
    try:
        raw = _safe_execute(graph_manager, query, params, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer", "Feature", "Product"],
            "relationships_followed": ["ADOPTED", "USES"],
        }
    except Exception as exc:
        logger.error("Error in get_feature_adoption: %s", exc)
        return {
            "result": f"Error inspecting feature adoption: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Customer"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 12. run_custom_cypher
# -----------------------------------------------------------------------------
@tool(
    name="run_custom_cypher",
    description="Run a custom read-only openCypher query directly against FalkorDB. Strictly disallows write or mutate commands.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Valid read-only openCypher query (e.g. MATCH ... RETURN ...)",
            }
        },
        "required": ["query"],
    },
)
def run_custom_cypher(graph_manager: Any, query: str) -> Dict[str, Any]:
    """Execute arbitrary read-only Cypher query."""
    forbidden_keywords = ["CREATE", "DELETE", "SET", "REMOVE", "DROP", "MERGE", "DETACH"]
    query_upper = query.upper()
    for word in forbidden_keywords:
        # Check whole word match
        if f" {word} " in f" {query_upper} ":
            return {
                "result": f"Execution rejected: Mutation keyword '{word}' is not allowed in read-only queries.",
                "cypher_query": query,
                "nodes_visited": [],
                "relationships_followed": [],
            }

    try:
        raw = _safe_execute(graph_manager, query, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["Dynamic"],
            "relationships_followed": ["Dynamic"],
        }
    except Exception as exc:
        logger.error("Error executing custom Cypher: %s", exc)
        return {
            "result": f"Cypher Execution Error: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": [],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 13. save_session_memory
# -----------------------------------------------------------------------------
@tool(
    name="save_session_memory",
    description="Save conversational memory and session takeaways into the graph database.",
    parameters={
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Unique session identifier",
            },
            "summary": {
                "type": "string",
                "description": "Concise summary of findings and conversation decisions",
            },
        },
        "required": ["session_id", "summary"],
    },
)
def save_session_memory(graph_manager: Any, session_id: str, summary: str) -> Dict[str, Any]:
    """Save session summary to FalkorDB Session node."""
    query = SAVE_SESSION_MEMORY_QUERY
    params = {
        "session_id": session_id,
        "summary": summary,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        raw = _safe_execute(graph_manager, query, params, readonly=False)
        return {
            "result": f"Successfully stored memory for session '{session_id}'.",
            "cypher_query": query.strip(),
            "nodes_visited": ["Session"],
            "relationships_followed": [],
        }
    except Exception as exc:
        logger.error("Error saving session memory: %s", exc)
        return {
            "result": f"Error saving session memory: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Session"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 14. get_session_history
# -----------------------------------------------------------------------------
@tool(
    name="get_session_history",
    description="Retrieve past session memories and summaries stored in the graph.",
    parameters={
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Optional specific session ID to retrieve",
            }
        },
    },
)
def get_session_history(graph_manager: Any, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve session memory from FalkorDB."""
    if session_id:
        query = GET_SESSION_BY_ID_QUERY
        params = {"session_id": session_id}
    else:
        query = GET_ALL_SESSIONS_QUERY
        params = {}
    try:
        raw = _safe_execute(graph_manager, query, params, readonly=True)
        records = graph_manager.parse_result(raw) if hasattr(graph_manager, "parse_result") else raw
        return {
            "result": format_graph_result(records),
            "cypher_query": query.strip(),
            "nodes_visited": ["Session"],
            "relationships_followed": [],
        }
    except Exception as exc:
        logger.error("Error retrieving session history: %s", exc)
        return {
            "result": f"Error retrieving session history: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Session"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# 15. save_insight
# -----------------------------------------------------------------------------
@tool(
    name="save_insight",
    description="Save an actionable AI-generated insight or risk notice into the graph, optionally linking to a customer.",
    parameters={
        "type": "object",
        "properties": {
            "insight": {
                "type": "string",
                "description": "The insight narrative to record",
            },
            "related_customer": {
                "type": "string",
                "description": "Optional customer name to associate with this insight",
            },
        },
        "required": ["insight"],
    },
)
def save_insight(graph_manager: Any, insight: str, related_customer: Optional[str] = None) -> Dict[str, Any]:
    """Save an insight node to FalkorDB, optionally linked to a customer."""
    insight_id = f"ins_{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat()

    if related_customer:
        query = SAVE_INSIGHT_WITH_CUSTOMER_QUERY
        params = {
            "insight_id": insight_id,
            "insight": insight,
            "category": "agent_insight",
            "confidence": 0.9,
            "created_at": created_at,
            "related_customer": related_customer,
        }
        rel = ["PERTAINS_TO"]
        nodes = ["Insight", "Customer"]
    else:
        query = SAVE_INSIGHT_QUERY
        params = {
            "insight_id": insight_id,
            "insight": insight,
            "category": "general_insight",
            "confidence": 0.9,
            "created_at": created_at,
        }
        rel = []
        nodes = ["Insight"]

    try:
        raw = _safe_execute(graph_manager, query, params, readonly=False)
        return {
            "result": f"Insight stored successfully with ID '{insight_id}'.",
            "cypher_query": query.strip(),
            "nodes_visited": nodes,
            "relationships_followed": rel,
        }
    except Exception as exc:
        logger.error("Error saving insight: %s", exc)
        return {
            "result": f"Error saving insight: {exc}",
            "cypher_query": query.strip(),
            "nodes_visited": ["Insight"],
            "relationships_followed": [],
        }


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def get_tools_description() -> str:
    """Return a formatted string describing all available tools for LLM prompts."""
    lines = ["Available Graph Tools:"]
    for name, item in TOOLS.items():
        desc = item["description"]
        params = item.get("parameters", {}).get("properties", {})
        param_list = [f"{p_name}: {p_meta.get('type', 'any')}" for p_name, p_meta in params.items()]
        params_str = f"({', '.join(param_list)})" if param_list else "()"
        lines.append(f"- {name}{params_str}: {desc}")
    return "\n".join(lines)


def get_tool_by_name(name: str) -> Optional[Callable[..., Any]]:
    """Return tool function by name.

    Args:
        name: The registered tool name.

    Returns:
        The callable tool function or None if not registered.
    """
    tool_info = TOOLS.get(name)
    if tool_info:
        return tool_info["function"]
    return None


def get_openai_tools() -> List[Dict[str, Any]]:
    """Return tools list formatted as OpenAI function specifications."""
    openai_tools = []
    for name, info in TOOLS.items():
        openai_tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": info["description"],
                "parameters": info.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return openai_tools
