"""Comprehensive unit and integration tests for CustomerGraph AI."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.agents.tools import TOOLS, get_openai_tools, get_tool_by_name
from app.graph.schema import GRAPH_SCHEMA_DESCRIPTION, SCHEMA_QUERIES
from app.graph.queries import (
    AT_RISK_CUSTOMERS_QUERY,
    CUSTOMER_360_QUERY,
    SEARCH_CUSTOMER_QUERY,
)
from app.models.schemas import (
    AgentResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CustomerSummary,
    HealthAnalysis,
    MessageRole,
    ReasoningStep,
)


class TestSchemas(unittest.TestCase):
    """Test Pydantic schemas and serialization."""

    def test_chat_message(self):
        msg = ChatMessage(role=MessageRole.USER, content="Hello")
        self.assertEqual(msg.role, MessageRole.USER)
        self.assertEqual(msg.content, "Hello")
        self.assertIsNotNone(msg.timestamp)

    def test_reasoning_step(self):
        step = ReasoningStep(
            step=1,
            description="Queried customers",
            cypher_query="MATCH (c:Customer) RETURN c",
            nodes_visited=["Customer"],
            relationships_followed=[],
        )
        self.assertEqual(step.step, 1)
        self.assertEqual(step.nodes_visited, ["Customer"])

    def test_agent_response(self):
        resp = AgentResponse(
            answer="Acme Corp is at risk.",
            confidence=0.95,
            sources=["FalkorDB"],
        )
        self.assertEqual(resp.answer, "Acme Corp is at risk.")
        self.assertEqual(resp.confidence, 0.95)

    def test_health_analysis(self):
        ha = HealthAnalysis(
            customer_name="Acme Corp",
            current_score=42.0,
            trend="declining",
            risk_factors=["Billing dispute", "Critical SAML bug"],
            positive_signals=["Long-term contract"],
            recommended_actions=["Issue billing credit"],
        )
        self.assertEqual(ha.customer_name, "Acme Corp")
        self.assertEqual(len(ha.risk_factors), 2)
        self.assertEqual(ha.trend, "declining")

    def test_customer_summary(self):
        cs = CustomerSummary(
            name="Acme Corp",
            industry="SaaS",
            mrr=15000.0,
            health_score=42.0,
            risk_level="critical",
        )
        self.assertEqual(cs.name, "Acme Corp")
        self.assertEqual(cs.risk_level, "critical")


class TestTools(unittest.TestCase):
    """Test tool registry and definitions."""

    def test_all_expected_tools_registered(self):
        expected_tools = [
            "search_customer",
            "get_customer_360",
            "get_at_risk_customers",
            "analyze_churn_signals",
            "get_customer_interactions",
            "get_open_tickets",
            "get_escalation_path",
            "get_team_influence",
            "get_decision_history",
            "get_customer_network",
            "get_feature_adoption",
            "run_custom_cypher",
            "save_session_memory",
            "get_session_history",
            "save_insight",
        ]
        for name in expected_tools:
            self.assertIn(name, TOOLS, f"Tool '{name}' should be registered")

    def test_get_tool_by_name(self):
        fn = get_tool_by_name("search_customer")
        self.assertIsNotNone(fn)
        self.assertTrue(callable(fn))

        none_fn = get_tool_by_name("nonexistent_tool")
        self.assertIsNone(none_fn)

    def test_get_openai_tools(self):
        tools = get_openai_tools()
        self.assertGreaterEqual(len(tools), 15)
        for t in tools:
            self.assertEqual(t["type"], "function")
            self.assertIn("name", t["function"])
            self.assertIn("description", t["function"])
            self.assertIn("parameters", t["function"])

    def test_search_customer_tool_execution(self):
        mock_gm = MagicMock()
        mock_gm.execute_readonly.return_value = None
        mock_gm.parse_result.return_value = [
            {"id": "cust_acme", "name": "Acme Corp", "health_score": 42}
        ]

        fn = get_tool_by_name("search_customer")
        result = fn(mock_gm, name="Acme")
        self.assertIn("result", result)
        self.assertIn("cypher_query", result)
        self.assertIn("nodes_visited", result)

    def test_run_custom_cypher_blocks_mutation(self):
        mock_gm = MagicMock()
        fn = get_tool_by_name("run_custom_cypher")

        # CREATE should be blocked
        result = fn(mock_gm, query="CREATE (n:BadNode)")
        self.assertIn("not allowed", result["result"])

        # DELETE should be blocked
        result = fn(mock_gm, query="MATCH (n) DELETE n")
        self.assertIn("not allowed", result["result"])


class TestGraphSchema(unittest.TestCase):
    """Test schema definitions and index queries."""

    def test_schema_description_not_empty(self):
        self.assertGreater(len(GRAPH_SCHEMA_DESCRIPTION), 200)
        self.assertIn("Customer", GRAPH_SCHEMA_DESCRIPTION)
        self.assertIn("Product", GRAPH_SCHEMA_DESCRIPTION)
        self.assertIn("Ticket", GRAPH_SCHEMA_DESCRIPTION)

    def test_schema_queries_count(self):
        self.assertGreaterEqual(len(SCHEMA_QUERIES), 8)
        for q in SCHEMA_QUERIES:
            self.assertTrue(q.startswith("CREATE INDEX"))


class TestCypherQueries(unittest.TestCase):
    """Test Cypher query templates."""

    def test_queries_have_parameters(self):
        self.assertIn("$name", SEARCH_CUSTOMER_QUERY)
        self.assertIn("$customer_name", CUSTOMER_360_QUERY)

    def test_queries_syntax(self):
        self.assertTrue(AT_RISK_CUSTOMERS_QUERY.strip().startswith("MATCH"))


if __name__ == "__main__":
    unittest.main()
