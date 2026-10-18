"""Analysis Agent: Performs deep customer health diagnostics, churn prediction, and recommendations."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.graph.schema import GRAPH_SCHEMA_DESCRIPTION
from app.models.schemas import CustomerSummary, HealthAnalysis, ReasoningStep

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """Agent specializing in diagnostic customer analytics, risk modeling, and strategic recommendations."""

    def __init__(
        self,
        openai_client: OpenAI,
        graph_manager: Any,
        model: str = "gpt-4o",
    ) -> None:
        """Initialize the AnalysisAgent.

        Args:
            openai_client: Synchronous OpenAI client.
            graph_manager: Active FalkorDB GraphManager.
            model: OpenAI chat model identifier.
        """
        self.openai_client = openai_client
        self.graph_manager = graph_manager
        self.model = model

    def analyze_customer_health(self, customer_name: str) -> HealthAnalysis:
        """Run deep graph diagnostic on customer health, risks, and trends.

        Args:
            customer_name: Name of the customer account.

        Returns:
            Structured HealthAnalysis model.
        """
        reasoning_path: List[ReasoningStep] = []
        step_idx = 1

        # 1. Fetch Core Health and Account Metrics
        health_cypher = """
        MATCH (c:Customer)
        WHERE toLower(c.name) CONTAINS toLower($customer_name)
        OPTIONAL MATCH (c)-[:HAS_SCORE]->(h:HealthScore)
        RETURN c.id AS id,
               c.name AS name,
               c.industry AS industry,
               c.segment AS segment,
               c.mrr AS mrr,
               c.status AS status,
               coalesce(h.score, c.health_score, 70.0) AS score,
               coalesce(h.trend, 'stable') AS trend,
               coalesce(h.risk_factors, '') AS risk_factors
        LIMIT 1
        """
        health_data: List[Dict[str, Any]] = []
        try:
            res = self.graph_manager.execute_readonly(health_cypher, {"customer_name": customer_name})
            health_data = self.graph_manager.parse_result(res)
            reasoning_path.append(
                ReasoningStep(
                    step=step_idx,
                    description=f"Fetched health score and account profile for '{customer_name}'",
                    cypher_query=health_cypher.strip(),
                    result_summary=f"Found: {health_data[0].get('name') if health_data else 'None'}",
                    nodes_visited=["Customer", "HealthScore"],
                    relationships_followed=["HAS_SCORE"],
                )
            )
        except Exception as exc:
            logger.error("Error fetching health metrics: %s", exc)
        step_idx += 1

        # 2. Fetch Open and Critical Tickets
        ticket_cypher = """
        MATCH (c:Customer)-[:RAISED]->(t:Ticket)
        WHERE toLower(c.name) CONTAINS toLower($customer_name)
          AND t.status <> 'closed' AND t.status <> 'resolved'
        OPTIONAL MATCH (t)-[:ASSIGNED_TO]->(tm:TeamMember)
        RETURN t.id AS ticket_id,
               t.title AS title,
               t.priority AS priority,
               t.status AS status,
               t.category AS category,
               tm.name AS assigned_to
        ORDER BY CASE t.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
        LIMIT 5
        """
        ticket_data: List[Dict[str, Any]] = []
        try:
            res = self.graph_manager.execute_readonly(ticket_cypher, {"customer_name": customer_name})
            ticket_data = self.graph_manager.parse_result(res)
            reasoning_path.append(
                ReasoningStep(
                    step=step_idx,
                    description=f"Queried open/critical tickets for '{customer_name}'",
                    cypher_query=ticket_cypher.strip(),
                    result_summary=f"Retrieved {len(ticket_data)} active tickets",
                    nodes_visited=["Customer", "Ticket", "TeamMember"],
                    relationships_followed=["RAISED", "ASSIGNED_TO"],
                )
            )
        except Exception as exc:
            logger.error("Error fetching tickets: %s", exc)
        step_idx += 1

        # 3. Fetch Recent Interactions and Sentiment
        inter_cypher = """
        MATCH (c:Customer)-[:HAD]->(i:Interaction)
        WHERE toLower(c.name) CONTAINS toLower($customer_name)
        OPTIONAL MATCH (i)-[:CONDUCTED_BY]->(tm:TeamMember)
        RETURN i.date AS date,
               i.type AS type,
               i.sentiment AS sentiment,
               i.sentiment_score AS score,
               i.summary AS summary,
               tm.name AS staff
        ORDER BY i.date DESC
        LIMIT 4
        """
        inter_data: List[Dict[str, Any]] = []
        try:
            res = self.graph_manager.execute_readonly(inter_cypher, {"customer_name": customer_name})
            inter_data = self.graph_manager.parse_result(res)
            reasoning_path.append(
                ReasoningStep(
                    step=step_idx,
                    description=f"Retrieved recent touchpoints and sentiment for '{customer_name}'",
                    cypher_query=inter_cypher.strip(),
                    result_summary=f"Retrieved {len(inter_data)} touchpoint records",
                    nodes_visited=["Customer", "Interaction", "TeamMember"],
                    relationships_followed=["HAD", "CONDUCTED_BY"],
                )
            )
        except Exception as exc:
            logger.error("Error fetching interactions: %s", exc)
        step_idx += 1

        # Synthesize using OpenAI
        base_name = health_data[0].get("name", customer_name) if health_data else customer_name
        current_score = float(health_data[0].get("score", 65.0)) if health_data else 65.0
        trend_val = str(health_data[0].get("trend", "stable")) if health_data else "stable"

        prompt = f"""You are a Customer Success AI Diagnostician. Analyze this customer data from FalkorDB:

Customer Profile:
{json.dumps(health_data, indent=2, default=str)}

Open Tickets:
{json.dumps(ticket_data, indent=2, default=str)}

Recent Interactions:
{json.dumps(inter_data, indent=2, default=str)}

Produce a structured JSON output with the exact keys:
{{
  "current_score": float (0-100),
  "trend": "improving" | "stable" | "declining",
  "risk_factors": list of strings,
  "positive_signals": list of strings,
  "recommended_actions": list of strings
}}
Only return valid JSON without markdown wrapping.
"""
        risk_factors: List[str] = []
        positive_signals: List[str] = []
        recommended_actions: List[str] = []

        try:
            completion = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a customer health data analysis system. Respond only in pure JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            raw_json = completion.choices[0].message.content or "{}"
            raw_json = raw_json.strip()
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
            data = json.loads(raw_json.strip())

            current_score = float(data.get("current_score", current_score))
            trend_val = str(data.get("trend", trend_val))
            risk_factors = list(data.get("risk_factors", []))
            positive_signals = list(data.get("positive_signals", []))
            recommended_actions = list(data.get("recommended_actions", []))

        except Exception as exc:
            logger.warning("LLM synthesis failed in analyze_customer_health: %s", exc)
            # Heuristic fallback
            if ticket_data:
                risk_factors.append(f"{len(ticket_data)} unresolved support tickets pending")
            if current_score < 60:
                risk_factors.append(f"Low overall health score: {current_score}/100")
                trend_val = "declining"
            else:
                positive_signals.append("Account active with consistent engagement")
            recommended_actions.append("Schedule an executive alignment check-in")
            recommended_actions.append("Review open ticket escalation bottlenecks")

        return HealthAnalysis(
            customer_name=base_name,
            current_score=current_score,
            trend=trend_val,
            risk_factors=risk_factors,
            positive_signals=positive_signals,
            recommended_actions=recommended_actions,
            reasoning_path=reasoning_path,
        )

    def predict_churn_risk(self) -> List[CustomerSummary]:
        """Query and evaluate all customers across the graph to predict churn risks.

        Returns:
            List of CustomerSummary objects sorted by risk severity.
        """
        cypher = """
        MATCH (c:Customer)
        OPTIONAL MATCH (c)-[:HAS_SCORE]->(h:HealthScore)
        OPTIONAL MATCH (c)-[:RAISED]->(t:Ticket)
        WHERE t.status <> 'closed' AND t.status <> 'resolved'
        OPTIONAL MATCH (c)-[:HAD]->(i:Interaction)
        WITH c, h, count(DISTINCT t) AS open_tkts, max(i.date) AS last_inter
        RETURN c.id AS id,
               c.name AS name,
               coalesce(c.company, c.name) AS company,
               coalesce(c.industry, 'Technology') AS industry,
               coalesce(c.segment, 'Enterprise') AS tier,
               coalesce(c.mrr, 0.0) AS mrr,
               coalesce(h.score, c.health_score, 75.0) AS health_score,
               coalesce(h.trend, 'stable') AS trend,
               coalesce(c.status, 'healthy') AS status,
               open_tkts AS open_tickets,
               last_inter AS last_interaction
        ORDER BY health_score ASC
        LIMIT 30
        """
        summaries: List[CustomerSummary] = []
        try:
            res = self.graph_manager.execute_readonly(cypher)
            rows = self.graph_manager.parse_result(res)
            for row in rows:
                score = float(row.get("health_score", 70.0))
                open_tkts = int(row.get("open_tickets", 0))

                # Compute risk level based on signals
                if score < 50 or open_tkts >= 3:
                    risk_level = "critical"
                elif score < 65 or open_tkts >= 1:
                    risk_level = "high"
                elif score < 80:
                    risk_level = "medium"
                else:
                    risk_level = "low"

                summaries.append(
                    CustomerSummary(
                        name=row.get("name", "Unknown"),
                        company=row.get("company", ""),
                        industry=row.get("industry", ""),
                        tier=row.get("tier", ""),
                        mrr=float(row.get("mrr", 0.0)),
                        health_score=score,
                        risk_level=risk_level,
                        open_tickets=open_tkts,
                        last_interaction=row.get("last_interaction"),
                    )
                )
        except Exception as exc:
            logger.error("Error predicting churn risk: %s", exc)

        return summaries

    def get_recommended_actions(self, customer_name: str) -> List[str]:
        """Generate targeted customer success action items for a given customer.

        Args:
            customer_name: Target customer account.

        Returns:
            List of prioritized action item strings.
        """
        analysis = self.analyze_customer_health(customer_name)
        if analysis.recommended_actions:
            return analysis.recommended_actions

        return [
            f"Review recent support interactions for {customer_name}",
            "Coordinate with Account Executive on contract renewal status",
            "Perform health score audit on key product workflows",
        ]

    def explain_reasoning(self, analysis_result: Any) -> str:
        """Produce human-readable explanation of why a health rating or churn prediction was reached.

        Args:
            analysis_result: HealthAnalysis instance, CustomerSummary, or dict.

        Returns:
            Formatted Markdown explanation narrative.
        """
        if isinstance(analysis_result, HealthAnalysis):
            lines = [
                f"### Explainable Diagnostic: {analysis_result.customer_name}",
                f"- **Overall Health Score**: `{analysis_result.current_score}/100` ({analysis_result.trend.upper()})",
                "",
                "**Identified Risk Drivers**:",
            ]
            if analysis_result.risk_factors:
                for rf in analysis_result.risk_factors:
                    lines.append(f"  - ⚠️ {rf}")
            else:
                lines.append("  - No critical risk factors identified.")

            lines.append("")
            lines.append("**Positive Retaining Signals**:")
            if analysis_result.positive_signals:
                for ps in analysis_result.positive_signals:
                    lines.append(f"  - ✅ {ps}")
            else:
                lines.append("  - Limited positive signals recorded.")

            lines.append("")
            lines.append("**Recommended Strategic Actions**:")
            for act in analysis_result.recommended_actions:
                lines.append(f"  1. {act}")

            if analysis_result.reasoning_path:
                lines.append("")
                lines.append("**Graph Traversal Sequence**:")
                for step in analysis_result.reasoning_path:
                    lines.append(f"  - **Step {step.step}**: {step.description}")
                    if step.cypher_query:
                        lines.append(f"    - Cypher: `{step.cypher_query}`")

            return "\n".join(lines)

        elif isinstance(analysis_result, CustomerSummary):
            return (
                f"### Customer Summary: {analysis_result.name}\n"
                f"- Tier: {analysis_result.tier} | MRR: ${analysis_result.mrr:,.2f}\n"
                f"- Health Score: {analysis_result.health_score} | Risk Level: {analysis_result.risk_level.upper()}\n"
                f"- Open Tickets: {analysis_result.open_tickets}\n"
                f"- Last Touchpoint: {analysis_result.last_interaction or 'None'}"
            )

        return f"Analysis summary:\n{json.dumps(analysis_result, indent=2, default=str)}"
