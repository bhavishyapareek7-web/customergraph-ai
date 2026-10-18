# 🏆 FalkorDB Hackathon Submission Guide: CustomerGraph AI

This document provides all required submission artifacts, copy-paste text, and demonstration scripts for submitting **CustomerGraph AI** to the **Graph Hacks: Context for AI Agents Hackathon**.

---

## 📋 Submission Checklist & Information

### 1. The Track You Are Entering
* **Primary Track**: **Track 03: Company Brain**
* **Secondary/Multi-Track Coverage**:
  * **Track 01: Agents That Act on Connected Data** (Multi-hop reasoning, blast-radius queries, explainable reasoning traces with visited nodes and edges).
  * **Track 02: Agent Memory and Coordination** (Persistent `:Session` and `:Insight` graph nodes enabling cross-session recall and state persistence in FalkorDB).

### 2. Project Title & Tagline
* **Title**: `CustomerGraph AI`
* **Tagline**: `A living Company Brain for Customer Success powered by FalkorDB graph traversals and OpenAI GPT-4o.`
* **Short Description**:
  > Most AI agents treat customer context as flat relational tables or disconnected document chunks. CustomerGraph AI transforms enterprise customer data—accounts, product licenses, feature adoption, support tickets, executive interactions, team assignments, and strategic decisions—into an interconnected FalkorDB knowledge graph. When querying accounts or evaluating churn risk, the agent executes multi-hop graph traversals, predicts retention risks with explainable reasoning traces, and writes conversational insights back into the graph as persistent memory.

---

### 3. Public Source-Code Repository
* **Repository Link**: `https://github.com/bhavishyapareek7-web/customergraph-ai`
* **License**: MIT License (included in repository)

#### Steps to Publish to GitHub:
```bash
# Initialize git if not already initialized
git init

# Add remote
git remote add origin https://github.com/bhavishyapareek7-web/customergraph-ai.git

# Stage all files (.env is protected by .gitignore)
git add .

# Commit and push
git commit -m "Initial commit: CustomerGraph AI with FalkorDB and Streamlit"
git branch -M main
git push -u origin main
```

---

### 4. Graph Data Model & Schema

The living graph schema connects operational data with internal staff and decisions:

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
    |                                 |
(Interaction) --[:CONDUCTED_BY]-------+
    |
    +---[:ABOUT]---> (Decision)
    |
(Customer) ---[:HAS_SCORE]---> (HealthScore)
    ^
    | [:ABOUT]
(Session)
```

#### Node Labels:
1. `Customer` (name, industry, segment, MRR, status, created_at)
2. `Product` (name, category, tier, description)
3. `Feature` (name, product_id, description)
4. `Ticket` (title, status, priority, category, created_at, resolved_at)
5. `Interaction` (channel, type, summary, sentiment, sentiment_score, date)
6. `TeamMember` (name, role, email, department)
7. `HealthScore` (score, trend, risk_factors, calculated_at)
8. `Decision` (title, description, category, impact, date)
9. `Session` (session_id, user_query, summary, timestamp)
10. `Insight` (category, summary, confidence, created_at)

---

### 5. Key Cypher Queries & Graph Traversals

FalkorDB is the core engine driving every decision:

#### A. Customer 360 Diagnostic
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

#### B. Ripple Impact & Blast-Radius Traversal
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

#### C. Ticket Escalation Chain
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

#### D. Persistent Memory & Insight Write-Back
```cypher
MERGE (s:Session {session_id: $session_id})
ON CREATE SET s.summary = $summary, s.timestamp = $timestamp, s.user_query = $user_query
ON MATCH SET s.summary = $summary, s.timestamp = $timestamp;

MATCH (c:Customer {name: $customer_name})
CREATE (i:Insight {id: $insight_id, summary: $insight, confidence: $confidence})
CREATE (i)-[:PERTAINS_TO]->(c);
```

---

### 6. Local Setup Instructions

#### Prerequisites:
* Python 3.10+
* Docker & Docker Compose (or FalkorDB Cloud account)
* OpenAI API Key

#### Steps:
```bash
# 1. Clone the repository
git clone https://github.com/bhavishyapareek7-web/customergraph-ai.git
cd customergraph-ai

# 2. Configure environment
cp .env.example .env
# Edit .env and paste your OPENAI_API_KEY=sk-proj-...

# 3. Start FalkorDB
docker-compose up -d

# 4. Install dependencies
py -3.11 -m pip install -r requirements.txt

# 5. Seed the graph with sample enterprise customer data
py -3.11 -m app.graph.seed

# 6. Run automated tests (14/14 tests)
py -3.11 -m unittest discover -s tests -p "test_*.py" -v

# 7. Start FastAPI Backend (Terminal 1)
py -3.11 -m app.main

# 8. Start Streamlit UI (Terminal 2)
py -3.11 -m streamlit run ui/streamlit_app.py
```

---

### 7. Demo Video Script (2–3 Minutes Walkthrough)

Record a screen capture (using Loom, OBS Studio, or Windows Game Bar `Win + G`) following this script:

| Time | Screen / Action | Spoken Narration |
|---|---|---|
| **0:00 – 0:30** | Show **README.md** architecture and schema diagram | *"Hello! This is CustomerGraph AI, built for the FalkorDB Graph Hacks Hackathon in Track 03: Company Brain. Customer success data is usually scattered across Zendesk, Salesforce, and email, leading to context loss and churn blindspots. We built a unified Company Brain where customers, products, tickets, interactions, and team members form a living FalkorDB graph."* |
| **0:30 – 1:15** | Open **Streamlit UI** (`http://localhost:8501`), click **Dashboard** tab | *"Here in our Streamlit dashboard, we see real-time account health across the portfolio. Let's look at Acme Corp—it shows critical risk with health score 42 and multiple open tickets. Clicking 'Deep Analysis' triggers our FalkorDB multi-hop diagnostic, correlating open tickets with negative interaction sentiment."* |
| **1:15 – 2:00** | Switch to **Chat** tab, ask: *"Who are our highest-risk customers and why?"* | *"Now let's ask our AI agent. Behind the scenes, the agent generates and executes Cypher queries against FalkorDB. Notice the Reasoning Trace expander: it shows each graph traversal step, the visited nodes, and the exact Cypher query used. No hallucinations—everything is grounded in graph data."* |
| **2:00 – 2:30** | Switch to **Graph Explorer** tab | *"In the Graph Explorer, we can interactively visualize the reasoning subgraph, seeing the connection between Acme Corp, the CustomerOS product, open tickets, and the assigned CSM Sarah Chen."* |
| **2:30 – 3:00** | Switch to **Memory** tab, show past sessions | *"Finally, in the Memory tab, CustomerGraph AI remembers previous conversations across sessions by persisting them directly as Session and Insight nodes in FalkorDB. Thank you!"* |
