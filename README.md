# OmniTrace

**Autonomous SRE incident triage and telemetry intelligence engine built with LangGraph, PGVector, and Self-RAG.**

---

### The Problem: Siloed Operational Telemetry

During production microservice outages, operational intelligence is fundamentally split into two disjoint systems:

1. **Structured Telemetry (SQL):** Status codes (HTTP 504, 500), p99 latency spikes, error rates, and connection pool saturation live in relational databases. They tell you *what broke* and *when*, but cannot explain system context or remediation procedures.
2. **Unstructured Runbooks (Vector Search):** SRE architectural runbooks, postmortems, and mitigation procedures live in technical documentation. They tell you *how to fix it*, but cannot compute aggregate error rates or filter telemetry spikes.

Standard AI pipelines fail here:
- **Pure RAG** cannot compute aggregations (`AVG`, `MAX`, `WHERE latency > 4000ms`).
- **Text-to-SQL** cannot interpret narrative incident runbooks.
- **Linear chains** hallucinate root causes under noisy, ambiguous logs without self-correction.

**OmniTrace** is an autonomous finite state machine built with **LangGraph** that unifies structured SQL telemetry with hybrid PGVector runbook retrieval, validates hypotheses using a **Self-RAG Groundedness Critic**, and enforces **Human-in-the-Loop (HITL)** approval before remediation.

---

### Architecture

```
                                [ Alert / Incident Trigger ]
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │       Router Node             │
                             │ (Service Parsing & Plan)      │
                             └───────┬───────────────┬───────┘
                                     │               │
                     ┌───────────────┘               └───────────────┐
                     ▼                                               ▼
       ┌───────────────────────────┐                   ┌───────────────────────────┐
       │   PGVector Hybrid Store   │                   │  AST-Guarded SQL Analytics│
       │ ───────────────────────── │                   │ ───────────────────────── │
       │ • HNSW Vector Index (m=16)│                   │ • Read-Only Connection(ro)│
       │ • Service Metadata Filter │                   │ • DDL/DML Keyword Blocking│
       │ • Sub-15ms similarity     │                   │ • Auto LIMIT Injection    │
       └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                     │                                               │
                     └───────────────────────┬───────────────────────┘
                                             ▼
                             ┌───────────────────────────────┐
                             │        Synthesis Node         │
                             │ (Diagnosis & Action Proposal) │
                             └───────────────┬───────────────┘
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │   Self-RAG Critic Node        │◄──────────────┐
                             │ (Groundedness Score Check)    │               │
                             └───────────────┬───────────────┘               │
                                             │                               │
                       ┌─────────────────────┴─────────────────────┐         │
        Score < 0.75   │                             Score >= 0.75 │         │
     (Retry count < 3) │                                           │         │
                       ▼                                           ▼         │
        ┌─────────────────────────────┐             ┌─────────────────────┐  │
        │      Refine Query Node      │             │ Sensitive Action?   │  │
        │ (Broadens search context)   │             └──────┬────────┬─────┘  │
        └──────────────┬──────────────┘                    │        │        │
                       │ (Cycle)                           │ Yes    │ No     │
                       └───────────────────────────────────┘        │        │
                                                           ▼        │        │
                                            ┌─────────────────────┐ │        │
                                            │ Human Approval Gate │ │        │
                                            │ (interrupt_before)  │ │        │
                                            └──────────────┬──────┘ │        │
                                                           │        │        │
                                                           └────┬───┘        │
                                                                ▼            │
                                                 ┌────────────────────────┐  │
                                                 │ Final SRE Triage Report│──┘
                                                 └────────────────────────┘
```

---

### Engineering Decisions & System Mechanics

#### 1. LangGraph State Machine & Cyclical Refinement
Instead of fragile linear while-loops, OmniTrace runs on a strongly typed `AgentState` (`TypedDict` with `add_messages` reducer). When initial telemetry is noisy, conditional edges route the graph from `critic` $\rightarrow$ `refine_query` $\rightarrow$ `retriever` in a cyclical loop. An explicit `retry_count` state variable acts as a circuit breaker, routing to fallback escalation if confidence remains below 0.75 after 3 attempts.

#### 2. Single-Store PGVector Architecture
OmniTrace provides a production PostgreSQL 16 schema (`scripts/init_db.sql`) with PGVector:
- **HNSW Indexing:** `USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)` provides sub-15ms approximate nearest-neighbor search instead of exhaustive $O(N)$ flat scans.
- **Relational + Semantic Fusion:** Filters service metadata (`service_name`) and calculates vector cosine distance (`<=>`) in a single execution plan, eliminating the overhead of managing a separate vector database.
- **Embedded Dual-Adapter:** For local development and testing, an embedded vector store runs immediately without requiring a running PostgreSQL daemon.

#### 3. Self-RAG Hallucination Defense (Critic Node)
The Critic node evaluates diagnostic hypotheses across three groundedness checks:
- Does the hypothesis strictly cite verified telemetry numbers (status codes, peak latency)?
- Does the remediation action derive directly from retrieved runbook content?
- Are service entities consistent across logs and runbooks?

#### 4. Human-in-the-Loop (HITL) Execution Breakpoints
Autonomous agents should never execute destructive infrastructure changes unassisted. OmniTrace compiles the graph with `interrupt_before=["human_approval_gate"]`. When a remediation command contains sensitive operations (`kubectl`, `restart`, `rollback`, `circuit breaker`), execution pauses, serializes state to the checkpointer, and requires explicit operator sign-off before proceeding.

---

### Evaluation Suite (`evals/`)

The evaluation suite validates the **RAG Triad** and state machine cycles deterministically:

```bash
# Run complete test suite (15 passed in under 1 second)
pytest evals/test_rag_triad.py evals/test_graph_cycles.py evals/test_unit_guardrails.py -v
```

- **Context Relevance:** Validates that hybrid retrieval isolates correct service runbooks based on incident symptoms.
- **Groundedness:** Evaluates that $100\%$ of diagnostic claims cite real error codes and peak latencies from telemetry.
- **Answer Relevance:** Verifies that recommended actions contain actionable remediation scripts.
- **Cyclical Graph Safety:** Verifies that ambiguous queries trigger the refinement loop and enforce the 3-attempt circuit breaker without infinite recursion.
- **AST Guardrails:** Offline testing proving `DROP`, `UPDATE`, `DELETE`, and stacked queries are blocked.

---

### Repository Structure

```text
OmniTrace/
├── omni_trace/
│   ├── graph/                      # LangGraph State Machine
│   │   ├── state.py                # Typed AgentState with add_messages
│   │   ├── workflow.py             # StateGraph definition & HITL interrupt
│   │   ├── edges.py                # Conditional routing logic
│   │   └── nodes/                  # Discrete functional nodes
│   │       ├── router.py           # Service extraction & execution plan
│   │       ├── retriever.py        # PGVector hybrid runbook retrieval
│   │       ├── sql_analytics.py    # AST-guarded SQL telemetry analytics
│   │       ├── synthesis.py        # Diagnostic hypothesis formulation
│   │       ├── critic.py           # Self-RAG Groundedness Critic
│   │       ├── refine.py           # Cyclical query refinement
│   │       ├── human_approval.py   # HITL approval gate
│   │       └── report.py           # Final triage report & fallback
│   ├── database/
│   │   └── vector_store.py         # PGVector store + local test fallback
│   ├── safety/
│   │   └── sql_guard.py            # AST validation & read-only enforcement
│   └── config.py                   # Central settings & LangSmith tracing flags
├── scripts/
│   └── init_db.sql                 # Production PostgreSQL + PGVector (HNSW) schema
├── data/
│   ├── seed_incident_data.py       # SRE telemetry DB and runbook generator
│   └── sample_runbooks/            # Seeded incident runbooks
├── evals/
│   ├── test_rag_triad.py           # RAG Triad test suite
│   ├── test_graph_cycles.py        # Cyclical graph & circuit breaker tests
│   └── test_unit_guardrails.py     # Deterministic SQL guardrail tests
├── cli.py                          # Interactive terminal interface with HITL support
├── pyproject.toml                  # Build system & package configuration
├── requirements.txt                # Runtime dependencies
└── LICENSE                         # MIT License
```

---

### Quick Start

```bash
# 1. Clone & create virtual environment
git clone https://github.com/UnknownArk/OmniTrace.git
cd OmniTrace
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Seed demo SRE telemetry & runbooks
python data/seed_incident_data.py

# 4. Launch interactive CLI
python cli.py

# 5. Run evaluation tests
pytest evals/ -v
```

---

### License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
