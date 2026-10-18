"""Query Agent: Translates natural language queries into FalkorDB graph operations via GPT-4o."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.agents.tools import get_openai_tools, get_tool_by_name
from app.graph.schema import GRAPH_SCHEMA_DESCRIPTION
from app.models.schemas import AgentResponse, GraphPath, ReasoningStep

logger = logging.getLogger(__name__)


class QueryAgent:
    """Agent responsible for interpreting user inquiries and orchestrating graph queries."""

    def __init__(
        self,
        openai_client: OpenAI,
        graph_manager: Any,
        model: str = "gpt-4o",
    ) -> None:
        """Initialize QueryAgent.

        Args:
            openai_client: Synchronous OpenAI client.
            graph_manager: Active FalkorDB GraphManager.
            model: OpenAI chat model identifier.
        """
        self.openai_client = openai_client
        self.graph_manager = graph_manager
        self.model = model

    def process(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentResponse:
        """Process incoming natural language inquiry and execute necessary graph tools.

        Args:
            user_message: The user's query or instruction.
            conversation_history: Optional list of past conversation message dictionaries.

        Returns:
            AgentResponse containing the final synthesized answer and reasoning steps.
        """
        system_prompt = f"""You are the Query Agent for CustomerGraph AI, an enterprise Customer Success intelligence platform powered by FalkorDB.
Your mission is to accurately navigate the customer graph to answer inquiries about accounts, health scores, open tickets, escalation paths, team assignments, and interactions.

{GRAPH_SCHEMA_DESCRIPTION}

Instructions:
1. Choose appropriate tools to fetch necessary graph data before formulating your final answer.
2. If the user asks for a customer overview, check their 360 view or health score.
3. If the user asks about risk or churn, analyze their churn signals or at-risk status.
4. If a custom query is appropriate and no tool fits, use run_custom_cypher (read-only).
5. Always explain your reasoning clearly and cite the data points retrieved from the graph.
"""

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        if conversation_history:
            for msg in conversation_history:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        tools = get_openai_tools()
        reasoning_steps: List[ReasoningStep] = []
        cypher_queries_used: List[str] = []
        step_counter = 1
        max_turns = 5
        turn = 0
        final_answer = ""

        try:
            while turn < max_turns:
                turn += 1
                logger.info("QueryAgent invoking OpenAI model %s (turn %d)...", self.model, turn)
                
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.0,
                )

                response_message = response.choices[0].message
                tool_calls = response_message.tool_calls

                # If no tool calls requested, we have reached the final response
                if not tool_calls:
                    final_answer = response_message.content or "No response generated."
                    break

                # Append assistant's call proposal to history
                messages.append(response_message)

                # Process each tool call
                for tc in tool_calls:
                    fn_name = tc.function.name
                    raw_args = tc.function.arguments
                    try:
                        args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        args = {}

                    logger.info("Executing tool '%s' with args: %s", fn_name, args)
                    tool_fn = get_tool_by_name(fn_name)

                    if tool_fn is None:
                        err_str = f"Error: Tool '{fn_name}' is not recognized."
                        result_dict = {
                            "result": err_str,
                            "cypher_query": "",
                            "nodes_visited": [],
                            "relationships_followed": [],
                        }
                    else:
                        try:
                            result_dict = tool_fn(self.graph_manager, **args)
                        except Exception as tool_exc:
                            logger.error("Exception during execution of tool '%s': %s", fn_name, tool_exc)
                            result_dict = {
                                "result": f"Execution error in {fn_name}: {tool_exc}",
                                "cypher_query": "",
                                "nodes_visited": [],
                                "relationships_followed": [],
                            }

                    tool_output = str(result_dict.get("result", ""))
                    query_used = result_dict.get("cypher_query", "")
                    nodes_visited = result_dict.get("nodes_visited", [])
                    rels_followed = result_dict.get("relationships_followed", [])

                    if query_used and query_used not in cypher_queries_used:
                        cypher_queries_used.append(query_used)

                    summary_sample = (
                        tool_output[:250] + "..." if len(tool_output) > 250 else tool_output
                    )
                    reasoning_steps.append(
                        ReasoningStep(
                            step=step_counter,
                            description=f"Called {fn_name}({', '.join(f'{k}={v!r}' for k, v in args.items())})",
                            cypher_query=query_used if query_used else None,
                            result_summary=summary_sample if summary_sample else "No content returned.",
                            nodes_visited=nodes_visited,
                            relationships_followed=rels_followed,
                        )
                    )
                    step_counter += 1

                    # Append tool response for next model loop
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": tool_output,
                    })

            if not final_answer:
                # If loop ended on tool output, request final synthesis
                synthesis_response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                )
                final_answer = synthesis_response.choices[0].message.content or "Analysis complete."

        except Exception as exc:
            logger.error("QueryAgent execution error: %s", exc, exc_info=True)
            # Graceful fallback answering
            final_answer = (
                f"I encountered an error executing your query: {exc}.\n\n"
                f"Please ensure FalkorDB and OpenAI credentials are configured."
            )
            reasoning_steps.append(
                ReasoningStep(
                    step=step_counter,
                    description="Execution encountered an unexpected exception.",
                    cypher_query=None,
                    result_summary=str(exc),
                    nodes_visited=[],
                    relationships_followed=[],
                )
            )

        # Assemble graph path structures for reasoning trace visualization
        graph_paths: List[GraphPath] = []
        if reasoning_steps:
            collected_nodes: List[Dict[str, Any]] = []
            collected_edges: List[Dict[str, Any]] = []
            for step in reasoning_steps:
                for nv in step.nodes_visited:
                    collected_nodes.append({"id": nv, "label": nv, "title": f"Node type: {nv}"})
                for rf in step.relationships_followed:
                    collected_edges.append({"label": rf, "type": rf})

            graph_paths.append(
                GraphPath(
                    nodes=collected_nodes,
                    edges=collected_edges,
                    description=f"Reasoning path through {len(reasoning_steps)} operations",
                )
            )

        confidence = 0.95 if reasoning_steps and not final_answer.startswith("I encountered an error") else 0.5

        return AgentResponse(
            answer=final_answer,
            reasoning_trace=reasoning_steps,
            graph_paths=graph_paths,
            cypher_queries_used=cypher_queries_used,
            confidence=confidence,
            sources=["FalkorDB Graph", "OpenAI GPT-4o"],
        )
