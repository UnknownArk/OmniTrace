# OmniTrace

**Autonomous hybrid analytics engine bridging structured SQL telemetry with unstructured document RAG.**

---

### The Problem: The Dual-Modality Gap

Operational datasets in media streaming, fintech, and enterprise operations are fundamentally split into two disjoint silos:

1. **Structured Telemetry (SQL)** captures quantitative realities—viewership drop-offs, latency spikes, transaction failure rates, and completion percentages. It answers *what happened* and *when*, but contains no narrative context.
2. **Unstructured Evidence (Documents/Transcripts)** captures human narrative—scene dialogue, screenplay notes, incident postmortems, and customer dispute transcripts. It answers *why it happened*, but cannot compute mathematical aggregations, filter numeric thresholds, or join tabular entities.

Traditional AI implementations fail on hybrid questions:
- **Pure RAG** cannot compute aggregations (`AVG`, `MAX`, `WHERE drop_off > 30%`).
- **Text-to-SQL** cannot reason over unstructured dialogue or narrative pacing.

**OmniTrace** implements a cyclic **ReAct** (Reason $\rightarrow$ Act $\rightarrow$ Observe $\rightarrow$ Reflect) state machine that routes queries across both modalities, self-heals execution errors, and synthesizes evidence-backed root-cause diagnoses.

---

### Architecture

```
                                 [ User Query ]
                                        │
                                        ▼
                     ┌──────────────────────────────────────┐
                     │       ReAct Agent Orchestrator       │◄─────────────────┐
                     │ (Reason ──► Act ──► Observe ──► Ref) │                  │
                     └──────────┬────────────────┬──────────┘                  │
                                │                │                             │
                ┌───────────────┘                └───────────────┐             │
                ▼                                                ▼             │
  ┌───────────────────────────┐                    ┌───────────────────────────┐
  │   Safe SQL Telemetry DB   │                    │   Windowed Script RAG     │
  │ ───────────────────────── │                    │ ───────────────────────── │
  │ • SQLite Read-Only (ro)   │                    │ • Temporal window (+/-60s)│
  │ • AST Keyword Guardrail   │                    │ • Scene dialogue chunks   │
  │ • Automatic LIMIT inject  │                    │ • Missing boundary checks │
  └─────────────┬─────────────┘                    └─────────────┬─────────────┘
                │                                                │
                │ (On SQLite Syntax/Schema Error)                │
                ▼                                                │
  ┌───────────────────────────┐                                  │
  │    Self-Healing Engine    │──────────────────────────────────┘
  │ • Catch OperationalError  │
  │ • Schema reflection hint  │
  │ • Circuit breaker (max 3) │
  └───────────────────────────┘
                │
                └───────────────────────┬────────────────────────┘
                                        │
                                        ▼
                         [ Synthesized Root Cause ]
                         (Cites Metrics & Dialogue)
```

---

### Engineering Decisions & Defensive Design

#### 1. Deterministic SQL Guardrails (Zero Trust)
Prompt-only guardrails (*"please only write SELECT queries"*) are brittle and vulnerable to hallucinations or prompt injection. OmniTrace enforces safety at the system boundary:
- Database connection initialized with `sqlite3.connect("file:...?mode=ro", uri=True)`.
- AST and token parser validates that queries strictly start with `SELECT` or `WITH`.
- Reject-list blocks destructive tokens (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `PRAGMA`).
- Queries without an explicit `LIMIT` automatically receive `LIMIT 100` to prevent memory exhaustion.

#### 2. Windowed Temporal Retrieval (Absorbing Clock Drift)
In media production and streaming pipelines, client player playhead timestamps rarely match post-production screenplay timecodes exactly due to player buffering, intro recaps, or editing trims.
- Standard retrieval fails on exact timestamp queries (`timestamp == 790`).
- OmniTrace implements a sliding window:
  $$\text{Interval} = [\max(0, T - W), T + W] \quad \text{where } W = 60\text{s}$$
  This captures both the lead-up context and the immediate narrative consequence.

#### 3. Autonomous Self-Healing & Circuit Breaker
When an LLM generates a query targeting an invalid column or missing table:
- The runtime intercepts the `sqlite3.OperationalError`.
- Formats a structured diagnostic observation containing the failed query and schema hint.
- The agent inspects valid schemas via `inspect_schema`, revises the SQL, and re-executes.
- Execution is governed by a **Circuit Breaker** (maximum 3 retry budget) to prevent runaway token spend.

#### 4. Epistemic Integrity on Asymmetric Data
Real data is frequently out of sync:
- **Telemetry exists, transcript missing**: The agent reports confirmed metrics and explicitly flags that dialogue records are absent (e.g. silent scene or missing log) without hallucinating text.
- **Transcript exists, telemetry missing**: The agent extracts dialogue notes and explicitly states that viewership analytics are pending ingestion or unreleased.

---

### Live Execution Walkthrough

**Query**:
> *"Which episode in Bhaichara had the highest audience drop-off rate, and what was happening in the script during that scene?"*

**Trace Summary**:
1. `inspect_schema()` $\rightarrow$ Discovers `shows`, `episodes`, `retention_dropoffs`, `regional_performance`.
2. `execute_sql(query="SELECT ... FROM retention_dropoffs ORDER BY drop_off_pct DESC LIMIT 1;")` $\rightarrow$ Isolates **Episode 103 ("The Ambush")** with an abnormal **38.4% drop-off at 00:13:10 (790s)**.
3. `search_transcripts(episode_id=103, timestamp_seconds=790, window_seconds=60)` $\rightarrow$ Retrieves Scene 4 in the Abandoned Warehouse basement:
   > *"Virender: The GPS beacon was planted under Jaideep's seat... [Audio cuts to jarring high-pitched static for 15 seconds. Unresolved narrative jump. Scene cuts abruptly into an unannounced black-and-white flashback without subtitle translations.]"*
4. **Synthesis**:
   > *"The 38.4% mobile drop-off at 00:13:10 corresponds directly to a technical/editing defect: a 15-second burst of high-pitched audio static followed by an untranslated, unannounced flashback. This broke viewer immersion (logged as 'Abrupt Scene Exit'), followed by a secondary 12.1% SmartTV exit 60 seconds later. Recommended action: Remaster audio and add transition cues to Scene 4."*

---

### Evaluation Suite (`evals/`)

OmniTrace includes an automated test and evaluation harness:

```bash
# Run deterministic offline unit tests (0.5s execution)
pytest evals/test_unit_guardrails.py -v

# Run the golden benchmark evaluation suite
python evals/runner.py
```

#### Test Coverage:
- **SQL Security & AST**: Rejection of destructive queries, chained statements, and validation of CTE queries.
- **Schema Discovery**: Table discovery and column type inspection.
- **RAG Temporal Windows**: Range retrieval verification and missing-entity handling.
- **Agent Routing Precision**: Asserting correct tool call sequences across hybrid and single-modality questions.
- **G-Eval Semantic Faithfulness**: Using Chain-of-Thought LLM judgment (`evals/geval_judge.py`) to score answer fidelity and penalize hallucinations.

---

### Repository Structure

```text
OmniTrace/
├── omni_trace/                 # Core engine package
│   ├── agent.py                # ReAct loop orchestrator & multi-provider dispatcher
│   ├── config.py               # Central configuration & safeguard limits
│   ├── models.py               # Pydantic schemas for traces, steps, and tool payloads
│   ├── safety/
│   │   └── sql_guard.py        # AST validation, keyword blocking, LIMIT injection
│   └── tools/
│       ├── base.py             # Tool contract interface
│       ├── inspector_tool.py   # Read-only schema introspection tool
│       ├── sql_tool.py         # Read-only SQL executor with error feedback
│       └── rag_tool.py         # Transcript retriever with sliding temporal window
├── data/
│   ├── seed_data.py            # Reproducible telemetry DB & transcript generator
│   └── sample_transcripts/     # Seeded scene transcripts
├── evals/
│   ├── benchmark_dataset.json  # Golden test queries, expected tools, and facts
│   ├── geval_judge.py          # Native G-Eval judge (Chain-of-Thought semantic scoring)
│   ├── runner.py               # Benchmark runner & metric aggregator
│   ├── test_unit_guardrails.py # Deterministic offline Pytest suite
│   ├── test_routing.py         # Tool routing precision tests
│   └── test_self_healing.py    # Error recovery & guardrail tests
├── cli.py                      # Interactive terminal CLI with step-by-step trace views
├── pyproject.toml              # Build system & package configuration
├── requirements.txt            # Minimal runtime dependencies
└── LICENSE                     # MIT License
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

# 3. Seed demo telemetry & scripts
python data/seed_data.py

# 4. Configure environment (.env)
# OMNITRACE_PROVIDER=groq
# GROQ_API_KEY=your_key_here

# 5. Launch interactive CLI
python cli.py
```

---

### License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
