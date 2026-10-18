"""Streamlit UI for CustomerGraph AI — FalkorDB-powered Customer Success Agent."""

import json
import streamlit as st
import httpx

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CustomerGraph AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main .block-container { padding-top: 1rem; }
    .user-bubble {
        background: #E3F2FD;
        padding: 12px 16px;
        border-radius: 12px 12px 4px 12px;
        margin: 8px 0;
        max-width: 85%;
        margin-left: auto;
        color: #1565C0;
    }
    .assistant-bubble {
        background: #F3E5F5;
        padding: 12px 16px;
        border-radius: 12px 12px 12px 4px;
        margin: 8px 0;
        max-width: 85%;
        color: #4A148C;
    }
    .reasoning-step {
        background: #FFF3E0;
        border-left: 3px solid #FF9800;
        padding: 8px 12px;
        margin: 4px 0;
        font-size: 0.85em;
        border-radius: 0 8px 8px 0;
    }
    .metric-card {
        background: #FAFAFA;
        border: 1px solid #E0E0E0;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .risk-critical { color: #D32F2F; font-weight: bold; }
    .risk-high { color: #F57C00; font-weight: bold; }
    .risk-medium { color: #FBC02D; font-weight: bold; }
    .risk-low { color: #388E3C; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "api_url" not in st.session_state:
    st.session_state.api_url = "http://localhost:8000"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "last_graph_data" not in st.session_state:
    st.session_state.last_graph_data = None
if "last_reasoning" not in st.session_state:
    st.session_state.last_reasoning = None
if "last_cypher" not in st.session_state:
    st.session_state.last_cypher = []


def api_call(method: str, endpoint: str, **kwargs) -> dict | list | None:
    """Make an API call to the FastAPI backend."""
    url = f"{st.session_state.api_url}{endpoint}"
    try:
        with httpx.Client(timeout=120.0) as client:
            if method == "GET":
                resp = client.get(url)
            elif method == "POST":
                resp = client.post(url, json=kwargs.get("json", {}))
            else:
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        st.error("⚠️ Cannot connect to backend. Make sure the FastAPI server is running at " + st.session_state.api_url)
        return None
    except httpx.HTTPStatusError as e:
        st.error(f"API Error: {e.response.status_code} — {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🧠 CustomerGraph AI")
    st.markdown("*FalkorDB-Powered Customer Success Intelligence*")
    st.divider()

    # API URL config
    api_url = st.text_input("Backend URL", value=st.session_state.api_url, key="api_url_input")
    if api_url != st.session_state.api_url:
        st.session_state.api_url = api_url

    st.divider()

    # Quick Actions
    st.markdown("### ⚡ Quick Actions")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🌱 Seed DB", use_container_width=True):
            with st.spinner("Seeding database..."):
                result = api_call("POST", "/api/seed")
                if result:
                    st.success("✅ Database seeded!")

    with col2:
        if st.button("🔄 New Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = None
            st.session_state.last_graph_data = None
            st.session_state.last_reasoning = None
            st.session_state.last_cypher = []
            st.rerun()

    st.divider()

    # Health Check
    st.markdown("### 🏥 System Status")
    health = api_call("GET", "/api/health")
    if health:
        status = health.get("status", "unknown")
        falkordb = health.get("falkordb", "unknown")
        if status == "healthy":
            st.success(f"System: {status} | FalkorDB: {falkordb}")
        else:
            st.warning(f"System: {status} | FalkorDB: {falkordb}")
    else:
        st.error("Backend offline")

    st.divider()

    # Example Questions
    st.markdown("### 💡 Try Asking")
    examples = [
        "Who are our highest-risk customers?",
        "Show me everything about Acme Corp",
        "Analyze health of DataBridge Solutions",
        "Which customers haven't had interactions recently?",
        "If we lose Acme Corp, who else might be affected?",
        "Trace the escalation for the billing dispute",
        "Which team member has the most influence?",
        "What decisions have been made about GreenLeaf?",
    ]
    for ex in examples:
        if st.button(f"💬 {ex}", key=f"ex_{hash(ex)}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": ex})
            with st.spinner("Thinking..."):
                resp = api_call("POST", "/api/chat", json={
                    "message": ex,
                    "session_id": st.session_state.session_id,
                })
                if resp:
                    st.session_state.session_id = resp.get("session_id")
                    agent_resp = resp.get("response", {})
                    answer = agent_resp.get("answer", "No response.")
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    st.session_state.last_reasoning = agent_resp.get("reasoning_trace", [])
                    st.session_state.last_cypher = agent_resp.get("cypher_queries_used", [])
                    st.session_state.last_graph_data = resp.get("graph_data")
            st.rerun()

    st.divider()
    st.markdown("### 📊 Graph Schema")
    with st.expander("View Schema"):
        schema_data = api_call("GET", "/api/graph/schema")
        if schema_data:
            st.code(schema_data.get("schema", "No schema available"), language="text")


# ---------------------------------------------------------------------------
# Main Area — Tabs
# ---------------------------------------------------------------------------
tab_chat, tab_graph, tab_dashboard, tab_memory = st.tabs([
    "💬 Chat", "🕸️ Graph Explorer", "📊 Dashboard", "🧠 Memory"
])

# ========== TAB 1: Chat ==========
with tab_chat:
    st.markdown("## 💬 Chat with CustomerGraph AI")

    # Display message history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="user-bubble">🧑 {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="assistant-bubble">🤖 {msg["content"]}</div>', unsafe_allow_html=True)

    # Reasoning trace
    if st.session_state.last_reasoning:
        with st.expander("🔍 Reasoning Trace", expanded=False):
            for step in st.session_state.last_reasoning:
                st.markdown(f"""
                <div class="reasoning-step">
                    <strong>Step {step.get('step', '?')}:</strong> {step.get('description', '')}
                    <br><small>Nodes: {', '.join(step.get('nodes_visited', []))} | 
                    Relationships: {', '.join(step.get('relationships_followed', []))}</small>
                </div>
                """, unsafe_allow_html=True)
                if step.get("cypher_query"):
                    st.code(step["cypher_query"], language="cypher")

    # Cypher queries used
    if st.session_state.last_cypher:
        with st.expander("📝 Cypher Queries Used", expanded=False):
            for q in st.session_state.last_cypher:
                st.code(q, language="cypher")

    # Chat input
    user_input = st.chat_input("Ask about your customers, risks, or graph data...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner("🧠 Querying the graph and reasoning..."):
            resp = api_call("POST", "/api/chat", json={
                "message": user_input,
                "session_id": st.session_state.session_id,
            })

        if resp:
            st.session_state.session_id = resp.get("session_id")
            agent_resp = resp.get("response", {})
            answer = agent_resp.get("answer", "No response generated.")
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.session_state.last_reasoning = agent_resp.get("reasoning_trace", [])
            st.session_state.last_cypher = agent_resp.get("cypher_queries_used", [])
            st.session_state.last_graph_data = resp.get("graph_data")

        st.rerun()


# ========== TAB 2: Graph Explorer ==========
with tab_graph:
    st.markdown("## 🕸️ Graph Explorer")
    st.markdown("Visualize the knowledge graph subgraph from the last query.")

    graph_data = st.session_state.last_graph_data
    if graph_data and graph_data.get("nodes"):
        try:
            from streamlit_agraph import agraph, Node, Edge, Config

            nodes = [
                Node(
                    id=n["id"],
                    label=n.get("label", n["id"]),
                    title=n.get("title", ""),
                    color=n.get("color", "#757575"),
                    size=n.get("size", 25),
                )
                for n in graph_data["nodes"]
            ]
            edges = [
                Edge(
                    source=e["source"],
                    target=e["target"],
                    label=e.get("label", ""),
                )
                for e in graph_data.get("edges", [])
            ]
            config = Config(
                width=800,
                height=500,
                directed=True,
                physics=True,
                hierarchical=False,
            )
            agraph(nodes=nodes, edges=edges, config=config)
        except ImportError:
            st.warning("Install `streamlit-agraph` for interactive graph visualization: `pip install streamlit-agraph`")
            st.json(graph_data)
    else:
        st.info("No graph data yet. Ask a question in the Chat tab to visualize the reasoning path.")

    # Custom Cypher query
    st.divider()
    st.markdown("### 🔧 Run Custom Cypher Query")
    custom_query = st.text_area(
        "Enter a read-only Cypher query:",
        value="MATCH (c:Customer)-[:HAS_SCORE]->(h:HealthScore)\nRETURN c.name, h.score, h.trend\nORDER BY h.score ASC",
        height=100,
    )
    if st.button("▶️ Execute Query"):
        with st.spinner("Executing..."):
            result = api_call("POST", "/api/graph/query", json={"query": custom_query})
            if result:
                st.markdown(f"**{result.get('count', 0)} rows returned**")
                st.json(result.get("rows", []))


# ========== TAB 3: Dashboard ==========
with tab_dashboard:
    st.markdown("## 📊 Customer Health Dashboard")

    # Fetch customers
    customers = api_call("GET", "/api/customers")
    if customers:
        # Metrics row
        total = len(customers)
        at_risk_count = sum(1 for c in customers if c.get("health_score", 100) < 65)
        healthy_count = sum(1 for c in customers if c.get("health_score", 0) >= 80)
        total_mrr = sum(c.get("mrr", 0) for c in customers)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Customers", total)
        col2.metric("🟢 Healthy", healthy_count)
        col3.metric("🔴 At Risk", at_risk_count)
        col4.metric("💰 Total MRR", f"${total_mrr:,.0f}")

        st.divider()

        # Customer table
        st.markdown("### Customer Overview")
        for c in sorted(customers, key=lambda x: x.get("health_score", 100)):
            score = c.get("health_score", 0)
            if score < 50:
                risk_class = "risk-critical"
                risk_emoji = "🔴"
            elif score < 65:
                risk_class = "risk-high"
                risk_emoji = "🟠"
            elif score < 80:
                risk_class = "risk-medium"
                risk_emoji = "🟡"
            else:
                risk_class = "risk-low"
                risk_emoji = "🟢"

            with st.expander(
                f"{risk_emoji} **{c.get('name', 'Unknown')}** — "
                f"Health: {score}/100 | MRR: ${c.get('mrr', 0):,.0f} | "
                f"Open Tickets: {c.get('open_tickets', 0)}",
                expanded=False,
            ):
                col_a, col_b, col_c = st.columns(3)
                col_a.write(f"**Industry:** {c.get('industry', 'N/A')}")
                col_b.write(f"**Segment:** {c.get('segment', 'N/A')}")
                col_c.write(f"**Status:** {c.get('status', 'N/A')}")

                if st.button(f"🔍 Deep Analysis", key=f"analyze_{c.get('id', '')}"):
                    with st.spinner(f"Analyzing {c.get('name')}..."):
                        health = api_call("GET", f"/api/customers/{c.get('name', '')}/health")
                        if health:
                            st.markdown(f"**Score:** {health.get('current_score', 'N/A')}/100 ({health.get('trend', 'N/A')})")
                            st.markdown("**Risk Factors:**")
                            for rf in health.get("risk_factors", []):
                                st.markdown(f"  - ⚠️ {rf}")
                            st.markdown("**Positive Signals:**")
                            for ps in health.get("positive_signals", []):
                                st.markdown(f"  - ✅ {ps}")
                            st.markdown("**Recommended Actions:**")
                            for act in health.get("recommended_actions", []):
                                st.markdown(f"  - 📋 {act}")
    else:
        st.info("No customer data available. Click '🌱 Seed DB' in the sidebar to load sample data.")


# ========== TAB 4: Memory ==========
with tab_memory:
    st.markdown("## 🧠 Conversation Memory")
    st.markdown("Past sessions are stored as nodes in FalkorDB, enabling cross-session recall.")

    sessions = api_call("GET", "/api/sessions")
    if sessions:
        st.markdown(f"**{len(sessions)} past sessions found**")
        for sess in sessions:
            sid = sess.get("session_id", "unknown")
            summary = sess.get("summary", "No summary")
            user_q = sess.get("user_query", "")
            ts = sess.get("timestamp", "")

            with st.expander(f"📝 {ts} — Session `{sid[:16]}...`", expanded=False):
                if user_q:
                    st.markdown(f"**User Query:** {user_q}")
                st.markdown(f"**Summary:** {summary}")
                if st.button(f"Load Session", key=f"load_{sid}"):
                    st.session_state.session_id = sid
                    st.success(f"Loaded session {sid[:16]}...")
    else:
        st.info("No past sessions. Start chatting to build conversation memory!")

    st.divider()
    st.markdown("### 📊 Memory Graph")
    st.markdown("Session and Insight nodes in FalkorDB form a persistent memory layer.")
    st.code("""
    // How memory is stored in FalkorDB:
    (s:Session {session_id, summary, timestamp, user_query})
    (i:Insight {summary, category, confidence, created_at})
    (i)-[:PERTAINS_TO]->(c:Customer)
    """, language="cypher")
