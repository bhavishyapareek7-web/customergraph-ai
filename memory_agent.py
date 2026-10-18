"""Memory Agent: Manages persistent session memory and insights in FalkorDB."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.graph.queries import (
    GET_ALL_SESSIONS_QUERY,
    GET_SESSION_BY_ID_QUERY,
    SAVE_INSIGHT_QUERY,
    SAVE_INSIGHT_WITH_CUSTOMER_QUERY,
    SAVE_SESSION_MEMORY_QUERY,
)

logger = logging.getLogger(__name__)


class MemoryAgent:
    """Agent responsible for persisting and retrieving conversational memory in FalkorDB.

    All memory is stored as graph nodes and edges:
    - Session nodes capture conversation summaries with timestamps
    - Insight nodes capture learned knowledge, optionally linked to Customers
    """

    def __init__(self, graph_manager: Any) -> None:
        """Initialize the MemoryAgent.

        Args:
            graph_manager: Active FalkorDB GraphManager instance.
        """
        self.graph_manager = graph_manager

    def generate_session_id(self) -> str:
        """Generate a unique session identifier.

        Returns:
            A unique session ID string.
        """
        return f"sess_{uuid.uuid4().hex[:12]}"

    def save_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        summary: str,
    ) -> bool:
        """Save a conversation session to the graph.

        Creates or updates a Session node with the conversation summary,
        timestamp, and a serialized snapshot of the message history.

        Args:
            session_id: Unique session identifier.
            messages: List of message dicts with 'role' and 'content' keys.
            summary: Concise summary of the conversation.

        Returns:
            True if saved successfully, False otherwise.
        """
        timestamp = datetime.utcnow().isoformat()

        # Save core session node
        params = {
            "session_id": session_id,
            "summary": summary,
            "timestamp": timestamp,
        }
        try:
            self.graph_manager.execute_query(SAVE_SESSION_MEMORY_QUERY, params)
            logger.info("Saved session memory: %s", session_id)

            # Store message count and last user query as extra properties
            user_messages = [m for m in messages if m.get("role") == "user"]
            if user_messages:
                last_query = user_messages[-1].get("content", "")[:500]
                update_query = """
                MATCH (s:Session {session_id: $session_id})
                SET s.user_query = $user_query,
                    s.message_count = $message_count
                RETURN s.session_id AS session_id
                """
                self.graph_manager.execute_query(update_query, {
                    "session_id": session_id,
                    "user_query": last_query,
                    "message_count": len(messages),
                })

            return True
        except Exception as exc:
            logger.error("Failed to save conversation for session %s: %s", session_id, exc)
            return False

    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve the conversation record for a specific session.

        Args:
            session_id: The session identifier to look up.

        Returns:
            List of session record dictionaries.
        """
        try:
            result = self.graph_manager.execute_readonly(
                GET_SESSION_BY_ID_QUERY, {"session_id": session_id}
            )
            return self.graph_manager.parse_result(result)
        except Exception as exc:
            logger.error("Failed to retrieve session %s: %s", session_id, exc)
            return []

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Retrieve all past conversation sessions.

        Returns:
            List of session record dictionaries, ordered by most recent.
        """
        try:
            result = self.graph_manager.execute_readonly(GET_ALL_SESSIONS_QUERY)
            return self.graph_manager.parse_result(result)
        except Exception as exc:
            logger.error("Failed to retrieve all sessions: %s", exc)
            return []

    def save_insight(
        self,
        insight: str,
        related_entities: Optional[List[str]] = None,
        category: str = "agent_insight",
        confidence: float = 0.85,
    ) -> Optional[str]:
        """Save a learned insight to the graph, optionally linked to customer entities.

        Args:
            insight: The insight text to persist.
            related_entities: Optional list of customer names to link.
            category: Insight category label.
            confidence: Confidence score (0.0 to 1.0).

        Returns:
            The created insight ID, or None if save failed.
        """
        insight_id = f"ins_{uuid.uuid4().hex[:8]}"
        created_at = datetime.utcnow().isoformat()

        try:
            if related_entities:
                # Link insight to each related customer
                for entity_name in related_entities:
                    params = {
                        "insight_id": insight_id,
                        "insight": insight,
                        "category": category,
                        "confidence": confidence,
                        "created_at": created_at,
                        "related_customer": entity_name,
                    }
                    self.graph_manager.execute_query(
                        SAVE_INSIGHT_WITH_CUSTOMER_QUERY, params
                    )
                    # Only create node once — subsequent links just need relationships
                    # Update insight_id to avoid duplicate nodes
                    insight_id = f"ins_{uuid.uuid4().hex[:8]}"
            else:
                params = {
                    "insight_id": insight_id,
                    "insight": insight,
                    "category": category,
                    "confidence": confidence,
                    "created_at": created_at,
                }
                self.graph_manager.execute_query(SAVE_INSIGHT_QUERY, params)

            logger.info("Saved insight: %s", insight_id)
            return insight_id
        except Exception as exc:
            logger.error("Failed to save insight: %s", exc)
            return None

    def get_relevant_context(
        self,
        query: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Retrieve relevant past context for the current query.

        Searches past sessions and insights to build context that
        helps the agent provide continuity across conversations.

        Args:
            query: The current user query to find context for.
            session_id: Optional current session ID to check for prior turns.

        Returns:
            Formatted string with relevant context from past sessions.
        """
        context_parts: List[str] = []

        # 1. Get current session history if we have a session_id
        if session_id:
            current_session = self.get_conversation_history(session_id)
            if current_session:
                for rec in current_session:
                    summary = rec.get("summary", "")
                    user_q = rec.get("user_query", "")
                    if summary:
                        context_parts.append(
                            f"[Current Session] Previous query: '{user_q}' → {summary}"
                        )

        # 2. Search past sessions for related context
        try:
            search_query = """
            MATCH (s:Session)
            WHERE s.summary IS NOT NULL
            RETURN s.session_id AS session_id,
                   s.summary AS summary,
                   s.user_query AS user_query,
                   s.timestamp AS timestamp
            ORDER BY s.timestamp DESC
            LIMIT 5
            """
            result = self.graph_manager.execute_readonly(search_query)
            past_sessions = self.graph_manager.parse_result(result)
            for sess in past_sessions:
                sid = sess.get("session_id", "")
                if sid != session_id:  # Don't duplicate current session
                    summary = sess.get("summary", "")
                    user_q = sess.get("user_query", "")
                    ts = sess.get("timestamp", "")
                    if summary:
                        context_parts.append(
                            f"[Past Session {ts}] Query: '{user_q}' → {summary}"
                        )
        except Exception as exc:
            logger.warning("Could not retrieve past sessions for context: %s", exc)

        # 3. Check for relevant insights
        try:
            insight_query = """
            MATCH (i:Insight)
            RETURN i.summary AS insight,
                   i.category AS category,
                   i.created_at AS created_at
            ORDER BY i.created_at DESC
            LIMIT 3
            """
            result = self.graph_manager.execute_readonly(insight_query)
            insights = self.graph_manager.parse_result(result)
            for ins in insights:
                insight_text = ins.get("insight", "")
                if insight_text:
                    context_parts.append(f"[Stored Insight] {insight_text}")
        except Exception as exc:
            logger.warning("Could not retrieve insights for context: %s", exc)

        if not context_parts:
            return "No prior conversation context available. This is a fresh session."

        return "=== Prior Context ===\n" + "\n".join(context_parts)
