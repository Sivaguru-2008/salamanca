# 02 — Agent Architecture

← [Index](README.md) · [Prev](01-system-architecture.md) · [Next](03-workflows.md)

Covers requirements: **#4 Agent architecture · #5 Agent communication protocol**

---

## 1. Design rationale — why a fabric, not a single "super-prompt"

| Option | Description | Pros | Cons | Verdict |
|--------|-------------|------|------|---------|
| Single mega-agent | One LLM call with a giant system prompt | Simple | No specialization, no debate, no verification separation, unexplainable, hits context limits | ❌ |
| Pipeline of prompts | Fixed chain | Deterministic order | No collaboration/consensus, brittle | ❌ |
| **Multi-agent fabric on a state graph** | Specialist agents coordinated by LangGraph, tooling via ADK | Specialization, parallelism, debate, consensus, verifiable, replayable | More engineering, cost | ✅ **chosen** |

**Why LangGraph + Google ADK together?**
- **LangGraph** provides an explicit, checkpointed **StateGraph** — nodes/edges with typed state. This is what makes **Decision Replay** and deterministic orchestration possible (Principle P5).
- **Google ADK** provides structured agent primitives, tool declarations, and multi-agent patterns; agents are authored with ADK and *orchestrated* by LangGraph.
- Separation: **ADK = "what an agent is,"** **LangGraph = "how agents are coordinated."**

---

## 2. Agent architecture

### 2.1 The BaseAgent contract

Every agent implements a four-phase lifecycle. This uniformity is what lets the orchestrator treat agents polymorphically and what guarantees explainability (P1).

```
                 ┌────────────────────────────────────────────┐
                 │                 BaseAgent                    │
                 │                                              │
  context ─────▶ │  perceive(context) → Perception             │
                 │     (pull twin facts, memory, KG, docs)      │
                 │                                              │
                 │  reason(Perception) → Reasoning              │
                 │     (LLM via router + tools, chain-of-       │
                 │      thought kept internal, structured out)  │
                 │                                              │
                 │  act(Reasoning) → Opinion                    │ ─────▶ Opinion
                 │     (typed claim + recommendation)           │
                 │                                              │
                 │  explain(Opinion) → Explanation              │ ─────▶ Evidence
                 │     (evidence, drivers, assumptions, conf.)  │
                 └────────────────────────────────────────────┘
```

**Opinion schema (conceptual, not code):**

| Field | Meaning |
|-------|---------|
| `agent_id`, `agent_role` | who |
| `claim` | the position (e.g., "Refinancing is net-positive") |
| `stance` | one of {recommend, caution, oppose, abstain} |
| `rationale` | structured reasoning summary |
| `evidence[]` | facts referenced (twin fields, KG nodes, doc spans, sim results) with source ids |
| `assumptions[]` | explicit assumptions made |
| `confidence` | 0–1 self-assessed |
| `dissent_notes` | disagreements with peers (populated in debate) |

### 2.2 Agent roster

| Agent | Purpose | Key tools | Primary model bias* |
|-------|---------|-----------|---------------------|
| **Planner** | Decompose the request into subtasks; assign agents; set debate depth | `query_twin`, `kg_lookup`, `memory_recall` | Reasoning-strong (Claude/Gemini) |
| **Loan Analyst** | Analyze loans, refinancing, amortization, contract terms | `amortize`, `contract_extract`, `run_sim` | Reasoning + math |
| **Investment Analyst** | Portfolio, allocation, risk/return, contributions | `portfolio_metrics`, `run_sim`, `kg_lookup` | Reasoning + math |
| **Risk Sentinel** | Detect hidden risks, tail events, liquidity/solvency stress | `stress_test`, `run_sim`, `twin_project` | Adversarial reasoning |
| **Behavioral Coach** | Detect biases, emotional/behavioral patterns, nudge design | `behavior_profile`, `memory_recall` | Language-nuance model |
| **Compliance Officer** | Regulatory constraints, disclosures, suitability | `regulation_lookup(KG)`, `rule_eval` | Precise / low-temp |
| **Explainer** | Turn the consensus decision into human explanation + evidence graph | `evidence_assemble` | Language-nuance model |
| **Verifier** | Independently stress-test the candidate decision | `recompute`, `rule_eval`, `stress_test` | Adversarial + precise |
| **Twin-Keeper** | Maintain/refresh twin from new facts; answer twin queries | `twin_update`, `twin_query` | Deterministic/tools-heavy |

*Model bias = default routing preference; the LLM Router can override by availability/cost.

### 2.3 Agent component contract (applies to each specialist)

- **Purpose:** Provide an expert, independent opinion within its domain.
- **Responsibilities:** Perceive relevant context; reason; produce a typed `Opinion` with evidence and confidence; participate in debate.
- **Inputs:** `DecisionState` context slice, peer opinions (in debate rounds).
- **Outputs:** `Opinion` + `Explanation`.
- **Dependencies:** LLM Router, Tool Registry, Twin/KG/Memory/Sim services.
- **Failure modes:** LLM timeout/refusal; schema-invalid output; hallucinated evidence (citing non-existent facts); tool error.
- **Recovery:** Output Validator rejects → one structured retry with error feedback; hallucination check cross-references evidence ids against real store — unverifiable evidence is stripped and confidence downgraded; on persistent failure the agent returns `abstain` (never a fabricated answer), and the orchestrator proceeds with remaining agents at reduced trust.

### 2.4 Hallucination / grounding guard (why this matters for a finance product)

Every `evidence` item must reference a **real, resolvable id** (twin field id, KG node id, document span id, simulation run id). The **Output Validator** resolves each id:
- unresolved evidence → stripped + logged + confidence penalty;
- claim with **zero** resolvable evidence → agent forced to `abstain`.

This makes "made-up numbers" structurally hard to surface to the user.

---

## 3. Agent Communication Protocol (ACP)

### 3.1 Why a protocol at all?

Free-form agent chatter is unreplayable, unauditable, and expensive. FIOS defines a **typed, message-based protocol** so that every inter-agent exchange is a persisted, schema-valid event (supports replay, audit, and observability).

### 3.2 Transport & pattern

- **Intra-decision (same job):** agents do **not** call each other directly. They communicate **through the orchestrator's blackboard** (`DecisionState`). This *mediated* pattern avoids N×N coupling and keeps a single source of truth.
- **Cross-job / async (e.g., monitoring triggers a decision):** **Redis Streams** events.

```
        ┌──────────────────────── Blackboard (DecisionState) ───────────────────────┐
        │  context · opinions[] · debate_rounds[] · consensus · verification · …     │
        └───────▲───────────▲───────────▲───────────▲───────────▲───────────────────┘
                │           │           │           │           │
            Planner     LoanAnal    RiskSent    Compliance    Verifier
         (write plan) (write op.) (write op.) (write op.)  (write verdict)
                          ▲  read peers' opinions during debate  ▲
```

### 3.3 Message envelope (ACP)

Every ACP message shares an envelope:

| Field | Purpose |
|-------|---------|
| `msg_id` | unique id (ULID) |
| `decision_id` | correlation to the decision job |
| `trace_id` | OTel trace correlation |
| `sender` | agent role / orchestrator |
| `type` | `PLAN` `OPINION` `CRITIQUE` `REVISION` `VOTE` `VERDICT` `TOOL_CALL` `TOOL_RESULT` `ERROR` |
| `round` | debate round index |
| `payload` | type-specific, schema-validated |
| `refs[]` | evidence/source ids |
| `ts` | timestamp |
| `model_meta` | provider, model, version, tokens (for audit/cost) |

### 3.4 Message types & semantics

| Type | Sender → Recipient | Meaning |
|------|--------------------|---------|
| `PLAN` | Planner → Orchestrator | Subtask breakdown + agent assignments + debate depth |
| `OPINION` | Specialist → Blackboard | Initial typed opinion |
| `CRITIQUE` | Specialist → Blackboard | Structured disagreement with a peer opinion (targets `msg_id`) |
| `REVISION` | Specialist → Blackboard | Updated opinion after seeing critiques |
| `VOTE` | Specialist → Consensus | Weighted stance for reconciliation |
| `VERDICT` | Verifier → Orchestrator | pass / fail / conditions |
| `TOOL_CALL` / `TOOL_RESULT` | Agent ↔ Tool Registry | Typed tool invocation + result |
| `ERROR` | any → Orchestrator | Structured failure (drives recovery) |

### 3.5 Protocol guarantees

- **Schema-validated:** malformed messages are rejected before entering state.
- **Ordered per decision:** the orchestrator sequences rounds.
- **Idempotent replay:** every message is persisted; replaying the log reproduces the decision (deterministic given cached model outputs — see Replay in [03](03-workflows.md)).
- **At-least-once (async):** cross-job events are acked; handlers are idempotent.
- **Backpressure:** bounded debate rounds and per-agent time budgets prevent runaway loops/cost.

### 3.6 Tool invocation contract

Tools are **typed functions** in a registry; agents may only call declared tools with schema-valid args. This is the ADK "function tool" pattern.

| Tool | Input | Output | Backing service |
|------|-------|--------|-----------------|
| `query_twin` | field/query | facts | Twin Svc |
| `twin_project` | horizon, params | projection | Twin Svc |
| `run_sim` | scenario spec | distribution | Simulation |
| `counterfactual` | base + delta | delta outcome | Counterfactual Svc |
| `kg_lookup` | entity/relationship query | subgraph | Neo4j |
| `memory_recall` | query | ranked memories | Memory Svc |
| `regulation_lookup` | jurisdiction+topic | rules | Compliance KG |
| `rule_eval` | facts + ruleset | pass/violations | Rule engine |
| `contract_extract` | doc id | terms | Doc Intel |
| `amortize` / `portfolio_metrics` / `stress_test` | numeric params | numeric results | Deterministic calculators |

**Design note:** numeric/financial computations run in **deterministic tools**, never "in the LLM's head." The LLM decides *which* tool and *interprets* results; the math is auditable Python. This is a core trust decision.

---

Next: [03 — Core Workflows →](03-workflows.md)
