# 🧠 CustomerGraph AI
### FalkorDB-Powered Customer Success Intelligence Agent
*Built for Graph Hacks: Context for AI Agents Hackathon — Track 03: Company Brain*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FalkorDB](https://img.shields.io/badge/FalkorDB-Graph%20Database-red.svg)](https://www.falkordb.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-green.svg)](https://openai.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-teal.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-orange.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What It Does

Customer success data is notoriously fractured. Support tickets live in Zendesk, executive communications and check-ins sit in Gmail or Slack, contract values reside in Salesforce, and feature telemetry is siloed in usage databases. When an enterprise account begins showing early churn warning signs, human customer success managers (CSMs) and standard LLMs face two critical failure modes:

1. **Relational Blindspots**: A spike in billing tickets might actually be caused by an unannounced API change in an integrated product, which also affects three other top-tier accounts. Relational SQL queries require complex, fragile multi-table joins to uncover these hidden connections.
2. **Context Loss & Hallucinations**: Generic RAG systems perform vector similarity searches over isolated text chunks, missing the multi-hop organizational topologies, manager-to-account assignments, escalation ladders, and past executive commitments.

**CustomerGraph AI** acts as the **Company Brain** for Customer Success. Powered by **FalkorDB**'s ultra-low latency graph engine and **OpenAI GPT-4o**, it constructs an interconnected knowledge graph spanning customers, products, features, tickets, team members, interactions, and historical decisions. It delivers:
- **Instant Customer 360° Diagnostics**: Unified visibility across accounts, active contracts, assigned CSMs, product usage, and open issues.
- **Proactive Churn Signal Detection & Impact Analysis**: Graph-traversal queries that correlate unresolved high-priority tickets, negative interaction sentiment, and declining health scores—projecting blast-radius ripple effects across shared products and CSM portfolios.
- **Traceable Multi-Hop Reasoning**: Step-by-step reasoning traces backed by executed Cypher queries, eliminating black-box LLM hallucinations.
- **Long-Term Contextual Memory**: Persisting conversation sessions and key strategic decisions directly back into the graph, evolving the organization's collective intelligence over time.

---

## 🏗️ Architecture

```
+-----------------------------------------------------------------------------------+
|                                  USER INTERFACE                                    |
|   Streamlit Web App (ui/streamlit_app.py)                                          |
|   - 💬 Interactive Chat with Reasoning Trace & Cypher Inspector                    |
|   - 🕸️ Interactive Subgraph Explorer (streamlit-agraph / PyVis)                    |
|   - 📊 Real-Time Account Health & At-Risk Portfolio Dashboard                     |
|   - 🧠 Long-Term Session Memory & Decision Audit Trail                             |
+-----------------------------------------------------------------------------------+
                                          |
                                          | HTTP / REST (httpx)
                                          v
+-----------------------------------------------------------------------------------+
|                               FASTAPI REST BACKEND                                |
|   (app/main.py & app/api/routes.py)                                               |
|   - Endpoints: /api/chat, /api/customers, /api/customers/at-risk, /api/graph/...   |
+-----------------------------------------------------------------------------------+
                                          |
                                          | Orchestration
                                          v
+-----------------------------------------------------------------------------------+
|                             AI AGENT ORCHESTRATION                                |
|   OrchestratorAgent (app/agents/orchestrator.py)                                  |
|   - Intent Classification & Entity Resolution                                     |
|   - Multi-Hop Graph Traversal via Tool Calling (app/agents/tools.py)              |
|   - Synthesis Engine with GPT-4o & Transparent Reasoning Traces                  |
|   - Interactive Subgraph Extraction & Path Construction                           |
+-----------------------------------------------------------------------------------+
                     |                                           |
                     | Graph Context Retrieval                   | Cypher Execution
                     v                                           v
+-----------------------------------------------------------------------------------+
|                        GRAPH LAYER & COMPANY BRAIN                                |
|   FalkorDB Graph Database (Docker container on port 6379)                         |
|   - GraphManager (app/graph/connection.py)                                       |
|   - Schema & Cypher Indexes (app/graph/schema.py)                                 |
|   - Optimized Cypher Queries (app/graph/queries.py)                               |
|   - Long-Term Session & Decision Storage (:Session, :Insight, :Decision)           |
+-----------------------------------------------------------------------------------+
```

---

## 📊 Graph Schema

The CustomerGraph AI knowledge model represents the living fabric of customer relationships.

```
                  [:USES]
(Customer) ---------------------> (Product)
    |                                 ^
    | [:ADOPTED]                      | [:ABOUT_PRODUCT]
    v                                 |
(Feature)                         (Ticket) <--- [:RELATED_TO] ---> (Ticket)
    ^                                 |
    |                                 | [:ASSIGNED_TO]
    |                                 v
(Customer) ---[:MANAGED_BY]---> (TeamMember) <---[:ESCALATED_TO]--- (Ticket)
    |                                 ^
    | [:HAD]                          | [:MADE]
    v                                 |
(Interaction) --[:CONDUCTED_BY]-------+
    |
    +---[:ABOUT]---> (Decision)
    |
(Customer) ---[:HAS_SCORE]---> (HealthScore)
    ^
    | [:ABOUT]
(Session)
```

### Node Types and Properties
1. **`Customer`**: `id`, `name`, `industry`, `segment`, `mrr`, `status`, `created_at`
2. **`Product`**: `id`, `name`, `category`, `tier`, `description`
3. **`Feature`**: `id`, `name`, `product_id`, `description`
4. **`Ticket`**: `id`, `customer_id`, `title`, `status`, `priority`, `category`, `created_at`, `resolved_at`
5. **`Interaction`**: `id`, `customer_id`, `channel`, `type`, `summary`, `sentiment`, `sentiment_score`, `date`
6. **`TeamMember`**: `id`, `name`, `role`, `email`, `department`
7. **`HealthScore`**: `id`, `customer_id`, `score`, `trend`, `risk_factors`, `calculated_at`
8. **`Decision`**: `id`, `customer_id`, `title`, `description`, `category`, `impact`, `date`
9. **`Session`**: `id`, `session_id`, `user_query`, `summary`, `timestamp`
10. **`Insight`**: `id`, `category`, `summary`, `confidence`, `created_at`

### Core Relationships
- `(c:Customer)-[:USES {since, status, license_count}]->(p:Product)`
- `(c:Customer)-[:ADOPTED {adoption_date, usage_level}]->(f:Feature)`
- `(c:Customer)-[:RAISED]->(t:Ticket)`
- `(c:Customer)-[:HAD]->(i:Interaction)`
- `(c:Customer)-[:MANAGED_BY {role, since}]->(tm:TeamMember)`
- `(c:Customer)-[:HAS_SCORE]->(h:HealthScore)`
- `(t:Ticket)-[:ASSIGNED_TO]->(tm:TeamMember)`
- `(t:Ticket)-[:ESCALATED_TO {escalated_at, reason}]->(tm:TeamMember)`
- `(t:Ticket)-[:ABOUT_PRODUCT]->(p:Product)`
- `(t:Ticket)-[:RELATED_TO]->(t:Ticket)`
- `(i:Interaction)-[:CONDUCTED_BY]->(tm:TeamMember)`
- `(tm:TeamMember)-[:MADE]->(d:Decision)-[:ABOUT]->(c:Customer)`
- `(s:Session)-[:ABOUT]->(c:Customer)`
- `(ins:Insight)-[:PERTAINS_TO]->(c:Customer)`
- `(c1:Customer)-[:SIMILAR_TO {reason}]->(c2:Customer)`

---

## 🤖 Agent Capabilities

CustomerGraph AI provides five core intelligence capabilities:

1. **Customer 360° Comprehensive Profile**
   - Retrieves full context across active products, feature adoption depth, assigned account teams, recent interaction summaries, and open support tickets in a single graph traversal.
2. **Predictive Churn Detection & Root-Cause Diagnosis**
   - Correlates unresolved high-severity tickets, declining health trends, and negative sentiment logs to isolate churn drivers before accounts churn.
3. **Ripple Impact & Blast-Radius Assessment**
   - Analyzes second-degree connections (shared products, shared CSMs, identical industries) to calculate the organizational revenue risk if an account leaves.
4. **Escalation Path & Decision Tracing**
   - Follows ticket escalation chains (`[:ESCALATED_TO]`) and traces historical executive decisions (`[:MADE] -> [:ABOUT]`) to explain how situations developed.
5. **Team Influence Mapping**
   - Evaluates portfolio load, total managed MRR, and average customer health across account executives and CSMs to balance risk across teams.
6. **Agent Memory & Context Evolution**
   - Automatically stores session summaries and key findings into `:Session` nodes linked back to the affected customer nodes, enabling contextual recall in future sessions.

---

## 🚀 Quick Start

### 1. Prerequisites
- [Docker](https://www.docker.com/) & Docker Compose
- Python 3.10 or higher
- OpenAI API Key

### 2. Clone & Install
```bash
git clone https://github.com/bhavishyapareek7-web/customergraph-ai.git
cd customergraph-ai

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Start FalkorDB
Launch FalkorDB via Docker Compose:
```bash
docker-compose up -d
```
Verify the container is healthy:
```bash
docker ps
```
FalkorDB will be listening on port `6379`.

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and provide your OpenAI API key:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
OPENAI_API_KEY=sk-proj-yourOpenAIKeyHere
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
LLM_MODEL=gpt-4o
GRAPH_NAME=customer_graph
```

### 5. Seed the Graph Database
Populate FalkorDB with realistic, interconnected customer accounts, tickets, interactions, and team hierarchies:
```bash
python -m app.graph.seed
```
*Alternatively, you can click "Seed Database" directly in the Streamlit UI or POST to `/api/seed`.*

### 6. Start the FastAPI Backend
```bash
python -m app.main
```
The REST API will be available at [http://localhost:8000](http://localhost:8000) and interactive Swagger docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### 7. Launch the Streamlit UI
In a separate terminal (with virtual environment active):
```bash
streamlit run ui/streamlit_app.py
```
Open your browser at [http://localhost:8501](http://localhost:8501).

---

## 💡 Example Queries

Here are benchmark questions showcasing CustomerGraph AI's multi-hop graph reasoning:

| # | User Question | Reasoning Path & FalkorDB Query Action | Expected Agent Response |
|---|---|---|---|
| 1 | *"Who are our highest-risk customers?"* | Executes `GET_AT_RISK_CUSTOMERS`, filters accounts with health score < 50 or multiple unresolved tickets. | Lists Acme Corp (Health: 38) and NovaPay (Health: 45) with specific risk factors (unresolved billing tickets, declining trend). |
| 2 | *"Show me everything about Acme Corp."* | Executes `GET_CUSTOMER_360`, aggregating products (`CustomerOS`), assigned CSM, health scores, open tickets, and recent interaction notes. | Complete 360° dossier detailing $12,500 MRR, active tickets, executive sponsor meetings, and churn risks. |
| 3 | *"Which customers haven't had interactions recently?"* | Inspects `(:Customer)-[:HAD]->(:Interaction)` dates, ordering by oldest interaction timestamp. | Highlights neglected accounts in the portfolio with dates of last contact. |
| 4 | *"If we lose Acme Corp, who else might be affected?"* | Executes `GET_CUSTOMER_IMPACT`, traversing `[:USES]->(Product)<-[:USES]` and `[:MANAGED_BY]->(CSM)`. | Identifies shared product dependencies and team bandwidth risks for peer enterprise clients. |
| 5 | *"Trace the escalation path for the billing dispute ticket."* | Executes `GET_ESCALATION_DETAILS` on ticket `tkt_101`, following `[:ESCALATED_TO]` edges from Support Engineer to VP of Customer Success. | Step-by-step chronology of escalation hops, timestamps, and stated reasons. |
| 6 | *"Which team member has the most influence on retention?"* | Executes `GET_INFLUENCE_MAP`, grouping managed accounts by CSM, summing portfolio MRR and computing average customer health scores. | Ranks CSMs by total portfolio value, customer retention count, and team health averages. |
| 7 | *"What decisions were made regarding Acme Corp's renewal discount?"* | Executes `GET_DECISION_TRACE` for Acme Corp, traversing `(Decision)-[:ABOUT]->(Customer)`. | Context on a 15% renewal discount approved by VP of CS following high-severity outage. |
| 8 | *"What churn signals are appearing across our fintech clients?"* | Traverses `(Customer {industry: 'Fintech'})` down through tickets, negative sentiment logs, and health trends. | Summarizes sector-wide vulnerabilities and recurring integration issues. |

---

## ⚡ Core Cypher Queries Driving the Agent

The agent's intelligence is directly shaped by graph traversals that would require prohibitive multi-table joins or recursive queries in SQL:

### 1. Multi-Hop Customer 360 Diagnostic
Traverses customer, health trends, product licenses, assigned CSMs, and open tickets simultaneously:
```cypher
MATCH (c:Customer)
WHERE toLower(c.name) CONTAINS toLower($customer_name)
OPTIONAL MATCH (c)-[:HAS_SCORE]->(h:HealthScore)
OPTIONAL MATCH (c)-[u:USES]->(p:Product)
OPTIONAL MATCH (c)-[:MANAGED_BY]->(tm:TeamMember)
OPTIONAL MATCH (c)-[:RAISED]->(t:Ticket)
WHERE t.status <> 'closed' AND t.status <> 'resolved'
RETURN c.name, c.mrr, h.score, h.trend,
       collect(DISTINCT p.name) AS products,
       collect(DISTINCT tm.name + ' (' + tm.role + ')') AS team,
       count(DISTINCT t) AS open_tickets_count
```

### 2. Multi-Hop Ticket Escalation Path Tracing
Traces the full escalation chain across support engineers, leads, and executive VPs:
```cypher
MATCH (t:Ticket {id: $ticket_id})
OPTIONAL MATCH (c:Customer)-[:RAISED]->(t)
OPTIONAL MATCH (t)-[:ASSIGNED_TO]->(primary:TeamMember)
OPTIONAL MATCH (t)-[e:ESCALATED_TO]->(escalated:TeamMember)
RETURN t.title, t.priority, c.name AS customer,
       primary.name AS assigned_to,
       escalated.name AS escalated_to,
       e.reason AS escalation_reason, e.escalated_at AS escalated_at
```

### 3. Ripple Impact & Blast-Radius Traversal
Calculates organizational exposure by identifying peer customers sharing identical products and account managers:
```cypher
MATCH (c1:Customer)
WHERE toLower(c1.name) CONTAINS toLower($customer_name)
MATCH (c1)-[r1]-(shared)-[r2]-(c2:Customer)
WHERE c1 <> c2
RETURN c2.name AS connected_customer,
       labels(shared)[0] AS shared_entity_type,
       coalesce(shared.name, shared.title, shared.id) AS shared_entity_name,
       type(r1) + ' <-> ' + type(r2) AS connection_type,
       c2.industry AS industry, c2.status AS status
LIMIT 15
```

### 4. Team Influence & Risk Balancing
Aggregates portfolio health and total MRR managed per team member:
```cypher
MATCH (tm:TeamMember)
OPTIONAL MATCH (c:Customer)-[:MANAGED_BY]->(tm)
OPTIONAL MATCH (t:Ticket)-[:ASSIGNED_TO]->(tm)
OPTIONAL MATCH (i:Interaction)-[:CONDUCTED_BY]->(tm)
RETURN tm.name AS team_member, tm.role AS role,
       count(DISTINCT c) AS customers_managed,
       coalesce(sum(DISTINCT c.mrr), 0.0) AS managed_mrr,
       count(DISTINCT t) AS tickets_handled,
       count(DISTINCT i) AS interactions_conducted
ORDER BY customers_managed DESC, managed_mrr DESC
```

### 5. Persistent Graph Memory (Bi-Directional Learning)
Stores conversation sessions and new insights back into FalkorDB:
```cypher
MERGE (s:Session {session_id: $session_id})
ON CREATE SET s.summary = $summary, s.timestamp = $timestamp, s.user_query = $user_query
ON MATCH SET s.summary = $summary, s.timestamp = $timestamp;

// Associate insight with affected customer
MATCH (c:Customer {name: $customer_name})
CREATE (i:Insight {id: $insight_id, summary: $insight, confidence: $confidence})
CREATE (i)-[:PERTAINS_TO]->(c);
```

---

## 🔍 How It Works

```
                               ┌───────────────────────────┐
                               │   User Prompt / Message   │
                               └─────────────┬─────────────┘
                                             │
                                             v
                               ┌───────────────────────────┐
                               │ Intent Classifier & Entity │
                               │        Resolution         │
                               └─────────────┬─────────────┘
                                             │
                                             v
                               ┌───────────────────────────┐
                               │ Cypher Query Construction │
                               │  & Multi-Hop Traversal    │
                               │        (FalkorDB)         │
                               └─────────────┬─────────────┘
                                             │ Graph Results
                                             v
                               ┌───────────────────────────┐
                               │ Synthesis Engine (GPT-4o) │
                               │  - Reasoning Trace Gen    │
                               │  - Subgraph Extraction    │
                               └─────────────┬─────────────┘
                                             │
                                             v
                               ┌───────────────────────────┐
                               │ Structured AgentResponse  │
                               │ + Subgraph Visualization  │
                               │ + Persisted Graph Memory  │
                               └───────────────────────────┘
```

1. **Query Ingestion**: The user inputs a question via the Streamlit UI or REST API.
2. **Intent Classification & Tool Selection**: The `OrchestratorAgent` determines the analytical intent (e.g., risk evaluation, customer 360, escalation trace, or custom Cypher inquiry) and selects the corresponding graph retrieval tool.
3. **Graph Traversal via FalkorDB**: The agent executes targeted Cypher queries against the FalkorDB graph, traversing multi-hop relationship paths (`(:Customer)-[:RAISED]->(:Ticket)-[:ESCALATED_TO]->(:TeamMember)`).
4. **Transparent Reasoning Trace**: Each step of the graph traversal is recorded into a `ReasoningStep` object, capturing the Cypher statement, visited node IDs, followed relationships, and intermediate findings.
5. **Synthesis & Interactive Subgraph Generation**: GPT-4o formats a comprehensive, actionable response. A targeted subgraph (nodes and edges) is extracted and returned for live rendering in the UI.
6. **Graph-Backed Memory**: The session exchange is committed to the graph as a `:Session` node connected via `[:ABOUT]` to the referenced customer, allowing cross-session recall.

---

## 🕸️ Why FalkorDB?

Many AI agents treat databases as simple key-value lookups or vector stores. Customer success is intrinsically a **relational network**:

- **Real-World Relationships are Non-Linear**: A customer's risk is not just a column in a table; it is an emergent property of open bugs on specific features, recent negative sentiment in executive meetings, and team member workload.
- **Microsecond Graph Traversal**: FalkorDB leverages Redis's in-memory engine and GraphBLAS linear algebraic operations to execute deep multi-hop traversals in sub-millisecond latencies—essential for interactive conversational agents.
- **Natural Knowledge Graph for LLMs**: openCypher provides a declarative, expressive query language that allows LLMs to query complex topologies with precision without writing error-prone SQL joins.
- **Living Memory Fabric**: Rather than keeping session memories in disconnected files, FalkorDB stores interactions, insights, and decisions as interconnected nodes directly within the enterprise knowledge graph.

---

## 📁 Project Structure

```
customergraph-ai/
├── app/
│   ├── __init__.py               # Package marker
│   ├── config.py                 # Pydantic BaseSettings & configuration
│   ├── main.py                   # FastAPI application initialization & CORS
│   ├── api/
│   │   ├── __init__.py           # API package marker
│   │   └── routes.py             # REST API endpoints (/chat, /customers, /seed, etc.)
│   ├── models/
│   │   ├── __init__.py           # Models package marker
│   │   └── schemas.py            # Pydantic request/response schemas & data models
│   ├── graph/
│   │   ├── __init__.py           # Graph package marker
│   │   ├── connection.py         # FalkorDB client connection & GraphManager
│   │   ├── schema.py             # openCypher indexes & LLM schema descriptions
│   │   ├── queries.py            # Reusable Cypher query templates & execution helpers
│   │   └── seed.py               # Comprehensive database seed data & script
│   └── agents/
│       ├── __init__.py           # Agents package marker
│       ├── tools.py              # Agent tool definitions wrapping Cypher operations
│       ├── query_agent.py        # Natural language → Cypher query translation agent
│       ├── analysis_agent.py     # Deep health diagnostics & churn prediction agent
│       ├── memory_agent.py       # Session memory persistence & cross-session recall
│       └── orchestrator.py       # OrchestratorAgent with GPT-4o & multi-hop reasoning
├── ui/
│   └── streamlit_app.py          # Streamlit UI (Chat, Explorer, Dashboard, Memory)
├── tests/
│   ├── __init__.py               # Test package marker
│   └── test_graph.py             # Unit tests for GraphManager & Agent Tools
├── .env.example                  # Environment variable template
├── docker-compose.yml            # FalkorDB Docker configuration
├── requirements.txt              # Production Python dependencies
└── README.md                     # Project documentation & hackathon submission
```

---

## 🛠️ Tech Stack

- **Graph Database**: [FalkorDB](https://www.falkordb.com/) (Ultra-fast, in-memory graph database based on GraphBLAS)
- **Language Models**: [OpenAI GPT-4o](https://platform.openai.com/docs/models/gpt-4o)
- **Backend API**: [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)
- **Data Validation**: [Pydantic v2](https://docs.pydantic.dev/) & Pydantic-Settings
- **Frontend UI**: [Streamlit](https://streamlit.io/), [streamlit-agraph](https://github.com/ChrisDelClea/streamlit-agraph), [PyVis](https://pyvis.readthedocs.io/)
- **HTTP Client**: [HTTPX](https://www.encode.io/httpx/)
- **Containerization**: Docker, Docker Compose
- **Testing**: [Pytest](https://docs.pytest.org/)

---

## 🎯 Hackathon Track Alignment

### Track 03: Company Brain
CustomerGraph AI is purpose-built to fulfill the vision of a unified **Company Brain**:

- **Context Integration**: Synthesizes customer relationship management, support ticketing, feature usage telemetry, organizational hierarchy, and executive decision-making into a unified graph.
- **True Multi-Hop Context**: Answers questions that cannot be solved by single-table lookups or plain text search (e.g. tracing escalation paths from ticket to VP, or blast radius analysis across shared components).
- **Explainable & Verifiable**: Every answer provides an auditable reasoning trace and the exact Cypher queries executed against FalkorDB.
- **Bi-Directional Learning**: The agent doesn't just read company knowledge; it updates the company brain with new sessions and discovered insights.

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.
