# How We Built CustomerGraph AI: Giving AI Agents Real Context with FalkorDB

*A deep dive into building an interconnected Company Brain for Customer Success that reasons across multi-hop graph topologies, predicts churn, and remembers across sessions.*

---

## The Broken Promise of "Context-Aware" AI Agents

We've all seen the demo: an AI agent reads a PDF, summarizes a support ticket, or answers a question about a customer. It feels like magic—until you deploy it in a real enterprise.

In reality, customer success context is notoriously fragmented:
- Support tickets live in **Zendesk**
- Customer calls and QBR notes live in **Gong** or **Google Docs**
- Contract renewals and ARR live in **Salesforce**
- Feature telemetry lives in internal **Postgres** databases
- Team ownership and escalation paths live in people's heads

When an AI agent tries to answer a question like *"Why is Acme Corp at risk of churn, and who needs to intervene?"*, conventional RAG systems fail completely. They perform semantic similarity search over flat text chunks. They miss the fact that a spike in tickets is connected to a specific SAML feature outage, which was escalated to an engineering lead who just left the company, and that this same bug threatens two other $30k MRR accounts.

**Relational SQL databases aren't the answer either.** Querying these relationships requires multi-table JOINs that grow exponentially in complexity and latency with every additional hop.

To give our agents real context, we made a fundamental shift: **We put the company's customer intelligence into FalkorDB.**

---

## Why FalkorDB?

When designing **CustomerGraph AI**, we needed a graph engine that met three non-negotiable requirements:
1. **Sub-millisecond query latency**: AI agents make multiple tool calls in a single reasoning loop. Waiting hundreds of milliseconds for a database round-trip kills the user experience. FalkorDB’s GraphBLAS linear algebraic engine delivers near-instant traversals.
2. **Native openCypher support**: openCypher is declarative, expressive, and intuitive for LLMs to generate. It allowed us to turn graph traversals directly into agent tools.
3. **Graph-native memory**: We didn't want conversation memory stored in flat JSON logs or external vector stores. FalkorDB allowed us to store `:Session` and `:Insight` nodes directly in the graph, making conversation history part of the company's collective intelligence.

---

## The Graph Data Model

We modeled the entire customer success ecosystem as a connected property graph:

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

With 10 core entity types (`Customer`, `Product`, `Feature`, `Ticket`, `Interaction`, `TeamMember`, `HealthScore`, `Decision`, `Session`, `Insight`) and indexed lookups, our agents can traverse from a customer to their products, down to specific features, across open tickets, and up the escalation hierarchy in a single query.

---

## How It Works: Multi-Hop Reasoning in Action

When a user asks:
> *"Why is Acme Corp at risk of churn, and who owns the escalation?"*

The system executes a multi-step graph reasoning pipeline:

### 1. Intent Classification & Tool Calling
The `OrchestratorAgent` analyzes the intent and invokes the `get_customer_360` and `get_escalation_path` tools.

### 2. Cypher Traversal
The agent queries FalkorDB to trace the exact escalation chain:
```cypher
MATCH (c:Customer {name: 'Acme Corp'})-[:RAISED]->(t:Ticket)
WHERE t.status <> 'closed'
OPTIONAL MATCH (t)-[:ASSIGNED_TO]->(primary:TeamMember)
OPTIONAL MATCH (t)-[e:ESCALATED_TO]->(escalated:TeamMember)
RETURN t.title, t.priority, primary.name, escalated.name, e.reason
```

### 3. Blast-Radius Analysis
The agent doesn't stop at Acme Corp. It checks for shared product dependencies across peer accounts:
```cypher
MATCH (c1:Customer {name: 'Acme Corp'})-[r1:USES]-(p:Product)-[r2:USES]-(c2:Customer)
WHERE c1 <> c2
RETURN c2.name, p.name, c2.mrr, c2.status
```
It immediately surfaces that **DataBridge Solutions ($22K MRR)** uses the same product and has also logged timeouts.

### 4. Transparent Reasoning Trace
Instead of returning an unverified text response, CustomerGraph AI returns:
- The natural language diagnosis
- A step-by-step reasoning trace with visited node IDs
- The exact Cypher statements executed
- An interactive visual subgraph rendered in the UI

### 5. Persistent Memory Write-Back
Finally, the agent commits the session takeaway back to FalkorDB:
```cypher
MERGE (s:Session {session_id: $session_id})
SET s.summary = $summary, s.timestamp = $timestamp;

MATCH (c:Customer {name: 'Acme Corp'})
CREATE (i:Insight {summary: 'Critical SAML lockout resolved via credit', confidence: 0.95})
CREATE (i)-[:PERTAINS_TO]->(c);
```
Next time anyone queries Acme Corp, the agent already knows the history.

---

## What We Learned

Building CustomerGraph AI proved that **graphs are the missing piece for AI agents**:
1. **Graphs eliminate hallucinations**: When an agent's context is grounded in verified graph connections, it doesn't need to guess how things relate.
2. **Explainability builds trust**: Enterprise users won't trust an AI agent that can't explain *why*. Showing the graph path and Cypher query provides instant auditability.
3. **Memory should be connected**: Storing conversation memories as nodes in the graph turns every customer interaction into institutional knowledge.

---

## Try It Out

- **GitHub Repository**: [https://github.com/bhavishyapareek7-web/customergraph-ai](https://github.com/bhavishyapareek7-web/customergraph-ai)
- **Built for**: Graph Hacks: Context for AI Agents Hackathon (Track 03: Company Brain)
- **Stack**: FalkorDB, OpenAI GPT-4o, FastAPI, Streamlit
