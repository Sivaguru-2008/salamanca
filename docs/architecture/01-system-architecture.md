# 01 — System Architecture

← [Index](README.md) · [Prev](00-overview.md) · [Next](02-agent-architecture.md)

Covers requirements: **#1 Overall architecture · #2 High-level diagram · #3 Detailed component diagram · #25 Data flow**

---

## 1. Overall architecture

FIOS is organized into **six planes**. This "planes" framing keeps concerns separable and makes the eventual monolith→services split obvious.

| Plane | Responsibility | Key tech |
|-------|----------------|----------|
| **Experience Plane** | UI, visualization of agents/twin/decisions | Next.js, React Flow, shadcn |
| **Edge / API Plane** | AuthN/Z, rate limiting, request validation, routing | FastAPI, OAuth2/OIDC, Redis |
| **Orchestration Plane** | Agent graphs, planning, consensus, verification | LangGraph, Google ADK |
| **Reasoning Plane** | The agents themselves + LLM router + tools | OpenAI/Gemini/Claude, tool registry |
| **Knowledge & Memory Plane** | Twin, KG, vector memory, RAG, document intelligence | Postgres, Neo4j, Qdrant, LlamaIndex, Docling |
| **Platform Plane** | Persistence, event bus, audit ledger, observability, config | Postgres, Redis Streams, OTel |

**Control flow direction:** Experience → Edge → Orchestration → Reasoning ↔ Knowledge/Memory, with the Platform plane cross-cutting all of them (every plane logs, traces, and emits audit events).

### 1.1 Request archetypes

FIOS serves three fundamentally different request shapes; the architecture handles them distinctly:

| Archetype | Example | Path | SLA |
|-----------|---------|------|-----|
| **Interactive query** | "Can I afford this car?" | Sync fast-path → cached twin + single planner pass | p95 < 4 s |
| **Deep decision** | "Should I refinance my mortgage?" | Async job → full agent panel + consensus + verify + simulate | 20–90 s, streamed |
| **Continuous / ambient** | Nightly re-evaluation, market shift alert | Event/scheduler → monitoring pipeline → agents if triggered | background |

---

## 2. High-level system diagram

```
                                   ┌───────────────────────────────────────────┐
                                   │              EXPERIENCE PLANE               │
                                   │  Next.js · React · Tailwind · shadcn        │
                                   │  React Flow (agent graph, twin, replay)     │
                                   └───────────────────────┬─────────────────────┘
                                                           │ HTTPS / SSE (stream)
                                                           ▼
                                   ┌───────────────────────────────────────────┐
                                   │               EDGE / API PLANE              │
                                   │  FastAPI Gateway                            │
                                   │  • OAuth2/OIDC + JWT   • RBAC               │
                                   │  • Rate limit (Redis) • Validation (Pydantic)│
                                   │  • Idempotency keys   • Request tracing     │
                                   └───────┬───────────────────────────┬─────────┘
                                 sync path │                async enqueue│
                                           ▼                             ▼
                    ┌──────────────────────────────┐        ┌────────────────────────────┐
                    │     ORCHESTRATION PLANE       │        │        EVENT BUS            │
                    │  LangGraph Orchestrator       │◀──────▶│  Redis Streams              │
                    │  • Planner  • Consensus       │        │  (jobs, domain events,      │
                    │  • Verifier • Debate Rounds   │        │   audit events)             │
                    └───────┬───────────────────────┘        └──────────┬──────────────────┘
                            │                                            │
                            ▼                                            ▼
        ┌───────────────────────────────────────┐        ┌────────────────────────────────┐
        │           REASONING PLANE              │        │        WORKER POOL              │
        │  Agent Fabric (Google ADK)             │        │  • Document workers (Docling)  │
        │  ┌──────────┬──────────┬────────────┐  │        │  • Ingestion / sync workers    │
        │  │ Planner  │ LoanAnal │ InvestAnal │  │        │  • Monitoring / scheduler      │
        │  │ RiskSent │ Behavior │ Compliance │  │        │  • Simulation (Monte Carlo)    │
        │  │ Verifier │ Explainer│ Twin-Keeper│  │        └──────────┬──────────────────────┘
        │  └──────────┴──────────┴────────────┘  │                   │
        │  LLM Router → OpenAI · Gemini · Claude │                   │
        │  Tool Registry (typed function tools)  │                   │
        └───────────────┬───────────────────────┘                   │
                        │  reads/writes                              │
                        ▼                                            ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                        KNOWLEDGE & MEMORY PLANE                                   │
   │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐  │
   │  │ Digital Twin  │  │ Knowledge     │  │ Vector Memory │  │ Document Intel     │  │
   │  │ Service       │  │ Graph (Neo4j) │  │ (Qdrant+LI)   │  │ (Docling+LlamaIdx) │  │
   │  └───────────────┘  └───────────────┘  └───────────────┘  └───────────────────┘  │
   └─────────────────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                              PLATFORM PLANE                                       │
   │  PostgreSQL (system of record + audit ledger)  ·  Redis (cache/bus)              │
   │  Object store (raw documents)  ·  OpenTelemetry (traces/metrics/logs)            │
   │  Config/Secrets  ·  Vault-ready secret mgmt                                       │
   └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed component diagram

```
EDGE / API PLANE
┌──────────────────────────────────────────────────────────────────────┐
│ FastAPI App                                                            │
│  ├─ Middleware: TraceID · Auth · RateLimit · Idempotency · ErrorMap    │
│  ├─ Routers:                                                           │
│  │    /auth  /users  /accounts  /documents  /twin  /decisions          │
│  │    /simulations  /counterfactuals  /agents  /knowledge  /monitor    │
│  │    /audit  /compliance  /health                                     │
│  ├─ DTO layer (Pydantic schemas)                                       │
│  └─ Service facade (calls domain services; never touches DB directly)  │
└──────────────────────────────────────────────────────────────────────┘

ORCHESTRATION PLANE
┌──────────────────────────────────────────────────────────────────────┐
│ Decision Orchestrator (LangGraph StateGraph)                           │
│  nodes: intake → plan → gather_context → dispatch_agents →             │
│         debate(round n) → consensus → verify → simulate/counterfactual │
│         → explain → compliance_gate → persist → stream_result          │
│  edges: conditional (retry, escalate, degrade)                         │
│  state: DecisionState (typed, checkpointed for replay)                 │
│  ├─ Planner Controller                                                  │
│  ├─ Consensus Engine                                                    │
│  ├─ Verification Gate                                                   │
│  └─ Checkpointer (Postgres) → enables Decision Replay                   │
└──────────────────────────────────────────────────────────────────────┘

REASONING PLANE
┌──────────────────────────────────────────────────────────────────────┐
│ Agent Fabric                                                           │
│  ├─ BaseAgent (contract: perceive→reason→act→explain)                  │
│  ├─ Specialist agents (see 02-agent-architecture)                      │
│  ├─ LLM Router (provider selection, fallback, cost/latency policy)     │
│  ├─ Tool Registry (typed tools: query_twin, run_sim, kg_lookup, …)     │
│  ├─ Prompt Assembler (system + memory + evidence + guardrails)         │
│  └─ Output Validator (schema + safety + hallucination checks)          │
└──────────────────────────────────────────────────────────────────────┘

KNOWLEDGE & MEMORY PLANE
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐ ┌──────────────────┐
│ Digital Twin Svc  │ │ Knowledge Graph   │ │ Memory Svc        │ │ Document Intel   │
│ • State model     │ │ • Entity/product  │ │ • Working (Redis) │ │ • Docling parse  │
│ • Projection eng. │ │ • Regulation KG   │ │ • Episodic (PG)   │ │ • Chunk+embed    │
│ • Snapshotting    │ │ • Reasoning/paths │ │ • Semantic(Qdrant)│ │ • Extract→Twin   │
│ • Scenario apply  │ │ • Cypher queries  │ │ • Procedural      │ │ • Loan/statement │
└───────────────────┘ └───────────────────┘ └───────────────────┘ └──────────────────┘

CROSS-CUTTING SERVICES
┌──────────────────────────────────────────────────────────────────────┐
│ Explainability Svc · Trust/Confidence Scorer · Compliance Engine       │
│ Audit Ledger (append-only) · Notification Svc · Config Svc             │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.1 Component contracts (Purpose / Resp / In / Out / Deps / Failure / Recovery)

**Decision Orchestrator**
- **Purpose:** Own the lifecycle of a decision from intake to explained, verified result.
- **Responsibilities:** Sequence agent stages; hold typed `DecisionState`; checkpoint for replay; enforce gates (consensus, verify, compliance).
- **Inputs:** Decision request (intent, params, user context, twin snapshot ref).
- **Outputs:** `Decision` record (recommendation + evidence + trust score + counterfactual + audit id).
- **Dependencies:** Agent Fabric, Twin, Memory, KG, Simulation, Consensus, Verifier, Compliance, Audit Ledger.
- **Failure modes:** Agent timeout; LLM provider outage; partial context; non-convergent consensus.
- **Recovery:** Per-node retry with backoff; provider failover via router; degrade to fewer agents with lowered confidence; resume from last checkpoint; if verify fails, return "insufficient confidence" instead of a risky answer.

**LLM Router**
- **Purpose:** Single abstraction over multiple LLM vendors.
- **Responsibilities:** Select provider by policy (task type, cost, latency, availability); normalize request/response; enforce token/cost budgets; retry & failover.
- **Inputs:** Prompt bundle + policy hints.
- **Outputs:** Normalized completion + usage/telemetry.
- **Dependencies:** OpenAI, Gemini, Claude SDKs; secrets; rate-limiter.
- **Failure modes:** Provider 429/5xx; timeout; content filter; quota exhaustion.
- **Recovery:** Ordered failover list; circuit breaker per provider; cached deterministic fallbacks for non-critical calls; explicit degrade signal to orchestrator.

**Digital Twin Service**
- **Purpose:** Maintain the canonical, queryable model of the user's financial state and project it forward.
- **Responsibilities:** Ingest normalized facts; maintain current state + snapshots; run projections; apply hypothetical scenarios without mutating canonical state.
- **Inputs:** Normalized financial facts (accounts, cashflows, obligations, goals), scenario deltas.
- **Outputs:** Twin snapshot, projections (deterministic + distributional), scenario twins.
- **Dependencies:** Postgres, Simulation service, event bus.
- **Failure modes:** Stale/incomplete data; projection divergence; snapshot bloat.
- **Recovery:** Confidence flags on stale data; bounded projection horizons; snapshot compaction; rebuild from event log.

(Agent-level and pipeline-level contracts are in [02](02-agent-architecture.md) and [07](07-pipelines.md).)

---

## 4. Data flow

### 4.1 Canonical end-to-end data flow (deep decision)

```
User asks "Should I refinance?"
   │
   ▼
[API] validate + authN/Z + idempotency key → create Decision(job) → enqueue → return job id + SSE stream
   │
   ▼
[Orchestrator] load context:
   • Twin snapshot (current financial state)
   • Memory recall (past refinance discussions, goals, risk tolerance)
   • KG lookup (loan products, rate environment, regulations for jurisdiction)
   • Relevant documents (existing mortgage contract via Doc Intel)
   │
   ▼
[Planner] decompose → subtasks → assign to specialist agents
   │
   ▼
[Agents in parallel] LoanAnalyst, InvestmentAnalyst, RiskSentinel, BehavioralCoach, Compliance
   each: perceive(context) → reason(LLM+tools) → produce Opinion{claim, rationale, evidence, confidence}
   │
   ▼
[Debate] agents see each other's opinions → optional N rounds of critique/revision
   │
   ▼
[Consensus Engine] weighted reconciliation → candidate Decision + agreement score
   │
   ▼
[Simulation] Monte Carlo over twin: refinance vs stay → distributions of net worth, cashflow
[Counterfactual] "what changes if rate drops 0.5%? if you stay 3 yrs?"
   │
   ▼
[Verifier] independent stress test: recompute claims, check against twin & rules, hunt for failure modes
   │  fail → back to orchestrator (retry/degrade/reject)
   ▼
[Explainability] assemble human explanation + evidence graph
[Trust Scorer] compose confidence (agreement × evidence × verification × data freshness)
   │
   ▼
[Compliance Gate] jurisdiction rules + disclaimers → pass/annotate
   │
   ▼
[Persist] Decision + evidence + audit events (append-only) + twin snapshot ref
   │
   ▼
[Stream] result to UI (recommendation, explanation, trust score, counterfactuals, replay link)
```

### 4.2 Data classification & where it lives

| Data class | Examples | Store | Protection |
|------------|----------|-------|------------|
| Identity | user, roles | Postgres | Hashed secrets, RBAC |
| Financial facts (PII) | balances, transactions, obligations | Postgres (encrypted fields) | Field-level encryption, tenant isolation |
| Raw documents | uploaded PDFs | Object store | Encrypted at rest, signed URLs |
| Derived embeddings | doc/memory vectors | Qdrant | Namespaced per user |
| Knowledge | products, regulations, relationships | Neo4j | Read-mostly, versioned |
| Agent artifacts | opinions, transcripts, evidence | Postgres (JSONB) | Audit-linked |
| Audit events | append-only ledger | Postgres (immutable) | Hash-chained, no deletes |
| Ephemeral | working memory, cache | Redis | TTL, no durable PII |

### 4.3 Consistency model

- **Money/system-of-record:** strong consistency (Postgres, transactional).
- **Twin projections & agent artifacts:** derived; recomputable; eventually consistent with facts.
- **Vector/graph memory:** eventually consistent, rebuilt from the system of record if lost.
- **Audit ledger:** append-only, strongly consistent, never mutated (corrections are new events).

---

Next: [02 — Agent Architecture →](02-agent-architecture.md)
