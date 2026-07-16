# 11 — Risk Analysis, Roadmap & Implementation Prompts

← [Index](README.md) · [Prev](10-adrs.md)

Covers requirements: **#48 Hackathon MVP roadmap · #49 Post-hackathon roadmap · #50 Risk analysis · + ~50 ordered implementation prompts**

---

## 1. Risk analysis

Scored **Likelihood (L)** × **Impact (I)** on 1–5; **Score = L×I**. Sorted by score.

| # | Risk | L | I | Score | Category | Mitigation |
|---|------|---|---|-------|----------|------------|
| R1 | **Scope overrun** — 9 agents + 6 pipelines too much for hackathon | 5 | 5 | 25 | Delivery | Strict MVP slice (§2): vertical slice of 3–4 agents + loan pipeline first; feature-flag the rest |
| R2 | **LLM cost blow-up** during demo/testing | 4 | 4 | 16 | Cost | Stakes-proportional panels, caching, per-user budgets, cheap-model routing, mock mode in tests |
| R3 | **Hallucinated financial numbers** reach user | 3 | 5 | 15 | Trust/Safety | Deterministic math + Verifier recompute + evidence grounding (ADR-005/006/018) |
| R4 | **Agent non-determinism** breaks demos | 4 | 3 | 12 | Reliability | Golden transcripts, deterministic gates, degrade-not-fail, replay from cache |
| R5 | **LLM provider outage/rate limit** mid-demo | 3 | 4 | 12 | Availability | Multi-provider router + failover + circuit breakers |
| R6 | **Latency** — deep decision too slow, judges bounce | 3 | 4 | 12 | UX | Async + SSE live progress + fast-path for simple queries |
| R7 | **Integration complexity** — 4 datastores + 3 LLMs | 4 | 3 | 12 | Delivery | Compose-first, adapters behind ports, seed/fixtures, health checks |
| R8 | **Prompt injection** via uploaded docs | 3 | 4 | 12 | Security | Data-not-instructions, delimited prompts, tool allowlists, no side-effecting tools |
| R9 | **Cross-tenant data leak** | 2 | 5 | 10 | Security | RLS + hard namespace filters + isolation tests (mandatory) |
| R10 | **Consensus non-convergence** produces mush | 3 | 3 | 9 | Quality | Bounded debate + "contested" as a valid, honest output |
| R11 | **Regulatory/advice liability** | 2 | 4 | 8 | Legal | Advisory-only (ADR-011), compliance gate, disclaimers |
| R12 | **Data quality** from OCR extraction | 3 | 3 | 9 | Data | Confidence flags, human-confirm on low confidence, never write unverified as fact |
| R13 | **Observability gaps** — can't debug agent runs | 2 | 3 | 6 | Ops | OTel + audit/replay from day one |
| R14 | **Team knowledge silos** (KG/agents/frontend) | 3 | 2 | 6 | Team | Clear module seams, contracts, this SAD as shared source of truth |

**Top-3 focus for the hackathon:** R1 (scope), R2 (cost), R3 (trust) — the MVP roadmap is built to attack these directly.

---

## 2. Hackathon MVP roadmap (the winnable slice)

**Goal:** a *believable, end-to-end, demo-able* vertical slice that shows the differentiators — multi-agent debate, consensus, verification, explainability, digital twin, and replay — on **one killer flow: the Loan/Refinance decision.**

**MVP theme:** *"Upload your loan → watch a panel of AI experts debate, reach consensus, verify the math, and explain — with a trust score and a replay."*

| Phase | Days | Deliverable (demoable) |
|-------|------|------------------------|
| **P0 — Foundation** | 1–2 | Compose stack up (API, PG, Redis, Qdrant, Neo4j), auth, users, health, CI |
| **P1 — Facts & Twin** | 2–3 | Accounts/obligations/goals CRUD → Digital Twin snapshot + projection |
| **P2 — Documents** | 3–4 | Upload loan PDF → Docling parse → extract LoanTerms → into Twin (grounded) |
| **P3 — Agent core** | 4–6 | LangGraph orchestrator + 4 agents (Planner, Loan, Risk, Verifier) + LLM router + deterministic calculators |
| **P4 — Reasoning value** | 6–8 | Consensus engine + Verifier recompute + Explainability + trust score + counterfactual + Monte Carlo (basic) |
| **P5 — Experience** | 7–9 | Next.js UI: twin dashboard, **React Flow live agent panel**, decision + explanation + evidence graph, **replay** |
| **P6 — Polish & demo** | 9–10 | Continuous-monitor demo (1 trigger), compliance disclaimer gate, seed data, scripted demo, observability dashboard |

**MVP cut lines (feature-flagged OFF for MVP):** Investment/Budget/Behavior pipelines (stub 1 agent each if time), full RBAC advisor role, multi-jurisdiction KG (seed one), full consolidation/memory decay.

**MVP definition of done:** a judge can register → upload a real loan PDF → click "Should I refinance?" → watch agents debate live → see a verified, explained recommendation with a trust score and counterfactual → open the audit replay. That single flow proves every core claim.

---

## 3. Post-hackathon roadmap

| Horizon | Focus | Items |
|---------|-------|-------|
| **0–1 mo (harden)** | Trust & correctness | Full test pyramid, LLM eval suite, security review, load test, cost dashboards |
| **1–3 mo (breadth)** | All pipelines | Budget, Investment, Behavior pipelines live; full 9-agent roster; consolidation memory; multi-jurisdiction compliance KG |
| **3–6 mo (scale)** | Production | k8s + HPA, managed data stores, read replicas, semantic LLM cache, real bank connectors (Plaid), SOC2 groundwork |
| **6–12 mo (platform)** | Ecosystem | Advisor/B2B mode, plugin agents (tax/insurance/estate), white-label, mobile, personalization from procedural memory, model fine-tuning for routing |
| **12 mo+ (moat)** | Intelligence | Cross-user (privacy-preserving) benchmarking, richer causal/counterfactual engine, autonomous goal-tracking, optional guarded execution (if licensed) |

---

## 4. Prioritized implementation prompts (~50, dependency-ordered)

Each prompt is a self-contained unit of work that builds on the previous ones. Feed them to an engineer or coding agent **in order**. (These are build instructions — the SAD above is the spec they implement.)

### Track A — Foundation & platform
1. **Scaffold the monorepo** per [09 §1](09-engineering-standards.md): `backend/`, `frontend/`, `infra/`, `docs/`, root `docker-compose.yml`, `pyproject.toml`, `.gitignore`, pre-commit (ruff/mypy).
2. **Create `docker-compose.yml`** with services: `api`, `postgres`, `redis`, `qdrant`, `neo4j`, plus healthchecks and named volumes. One `docker compose up` must boot all.
3. **FastAPI app factory** (`app/main.py`) with middleware skeleton (trace id, CORS, error handler) and `/healthz` + `/readyz` (readiness checks each datastore).
4. **Typed settings** (`core/config.py`) with Pydantic Settings; validate at boot; `.env.example`; fail-fast on missing critical config.
5. **Structured JSON logging + OpenTelemetry** bootstrap (`core/observability.py`): trace/span ids on every log; OTel exporter wired in compose.
6. **SQLAlchemy 2.0 async + Alembic** setup: async engine, session dependency, base model with `id (ULID)`, `created_at`, `updated_at`, `deleted_at`; first empty migration.
7. **RFC-7807 error mapping** (`core/errors.py`): domain exception hierarchy → problem+json; wire into middleware.

### Track B — Identity, access, security
8. **User & auth models + migration**: `users`, `sessions`, `roles`, `permissions`, `role_permissions`, `user_roles`.
9. **Password + JWT security** (`core/security.py`): argon2id hashing, RS256 JWT issue/verify, rotating refresh tokens with reuse detection.
10. **Auth routers**: register, login, refresh, logout, MFA-verify stub; DTO schemas.
11. **RBAC + object-ownership dependency** guards; seed default roles (owner/auditor/admin/system).
12. **Postgres Row-Level Security** policies for user-owned tables + isolation integration test (mandatory).
13. **Rate limiting + idempotency** middleware backed by Redis (token bucket per principal+route; Idempotency-Key on job POSTs).

### Track C — Financial facts & Digital Twin
14. **Financial fact models + migrations**: `accounts`, `transactions`, `obligations`, `goals`, `assets`, `cashflow_streams`, `risk_profiles` with indexes from [05 §4](05-data-architecture.md).
15. **CRUD routers + repositories** for accounts/obligations/goals/assets (owner-scoped).
16. **Deterministic finance calculators** (`domain/calculators/`): amortization, effective APR, cashflow projection, portfolio metrics — pure, fully unit-tested.
17. **Digital Twin service + models**: `twin_snapshots`, `twin_facts`; `Twin-Keeper.apply()`, current-snapshot query, invariant validation, `TwinUpdated` event emit.
18. **Twin projection engine** (deterministic roll-forward) + `POST /twin/project` + `GET /twin`.
19. **Event bus over Redis Streams** (`infra/events/`): publish/consume, at-least-once, trace propagation, idempotent handler base; DLQ.

### Track D — Documents & knowledge
20. **Object store adapter** (MinIO/local) + `documents`/`document_chunks`/`extracted_terms` models & migration.
21. **Document upload endpoint** (multipart) → store raw → enqueue parse job; SSE status endpoint.
22. **Docling parse worker**: layout/table-aware parse → classify → layout-aware chunk.
23. **Qdrant adapter + embedding** (via LLM router): embed chunks, per-user namespaced payload; LlamaIndex retrieval wrapper.
24. **Schema-constrained LLM extractor**: fill typed `LoanTerms`/statement schema with per-field confidence + source span; low-confidence flagging.
25. **Normalizer → Twin**: map extracted facts to canonical facts → `Twin-Keeper.apply` (never write unverified as fact).
26. **Neo4j adapter + KG schema**: nodes/relationships from [04 §1.2](04-knowledge-graph-memory.md); constraints/indexes; seed world knowledge (products, one jurisdiction's regulations).
27. **KG sync + `kg_lookup`/`regulation_lookup` tools**: link per-user entities; Cypher traversals; versioned world-knowledge seed.

### Track E — Memory
28. **Memory models + services**: `memory_episodes`, `memory_procedural`; working memory (Redis), episodic writer.
29. **Semantic memory + `memory_recall` tool**: Qdrant similarity (namespaced) + episodic + procedural → ranked, token-budgeted `MemoryBundle`.
30. **Memory writer + consolidation job**: append episodes, embed salient artifacts, update procedural calibration; periodic summarize/prune.

### Track F — LLM & agent fabric
31. **LLM Router** (`agents/llm/`): provider adapters (OpenAI/Gemini/Claude), policy-based selection, failover, circuit breaker, token/cost telemetry, **mock provider** for tests.
32. **Typed Tool Registry** (`agents/tools/`): register `query_twin`, `twin_project`, `run_sim`, `kg_lookup`, `regulation_lookup`, `rule_eval`, `contract_extract`, calculators; schema-validated args; allowlist.
33. **BaseAgent contract** (`agents/base.py`): perceive→reason→act→explain; typed `Opinion`/`Explanation`; **Output Validator** with evidence-id grounding + forced-abstain rule.
34. **ACP protocol** (`agents/protocol/`): envelope + message types (`PLAN/OPINION/CRITIQUE/REVISION/VOTE/VERDICT/TOOL_*`) as validated schemas; persist to `agent_messages`.
35. **Planner Agent**: intent classification, stakes estimation, panel/debate sizing → `PLAN`.
36. **Loan Analyst Agent** (uses calculators + KG + contract terms).
37. **Risk Sentinel Agent** (stress-test + simulation + adversarial reasoning).
38. **Verifier Agent** (isolated; **recompute numbers deterministically**, rule check, twin stress) → `VERDICT`.
39. **(Optional MVP+) Investment, Behavioral, Compliance, Explainer agents** — implement Explainer + Compliance now; stub Investment/Behavior behind flags.

### Track G — Orchestration & reasoning value
40. **LangGraph Decision Orchestrator** (`agents/orchestrator/`): `DecisionState`, node graph (intake→plan→gather→dispatch→debate→consensus→verify→simulate→explain→compliance→persist), Postgres checkpointer.
41. **Consensus Engine** (`agents/consensus/`): weighted, evidence-aware reconciliation + agreement score + dissent preservation + "contested" output; unit-tested with mocked opinions.
42. **Simulation worker** (Monte Carlo): `simulation_runs` model, seed persistence, adaptive path count, percentile/CVaR outputs; `run_sim` tool + `POST /simulations`.
43. **Counterfactual service**: clone scenario twin, re-run projection/sim, structured `outcome_diff`; `POST /counterfactuals`.
44. **Explainability service + evidence graph**: assemble human explanation + link claims to evidence/KG nodes; `GET /decisions/{id}/explanation`.
45. **Trust/Confidence scorer**: compose from agreement × evidence quality × verification × data freshness; attach to decision.
46. **Compliance Engine + gate**: `rule_eval` over KG rules, jurisdiction context, disclaimers; `compliance_checks` table; mandatory gate in orchestrator.
47. **Decision endpoints + SSE**: `POST /decisions`, `GET /decisions/{id}`, `GET /decisions/{id}/stream` (live agent progress), feedback endpoint → procedural memory.

### Track H — Audit, monitoring, frontend, delivery
48. **Hash-chained audit ledger + Decision Replay**: `audit_events` (append-only, `prev_hash`/`hash`), emit on every stage; `POST /audit/decisions/{id}/replay` re-executes graph in replay mode from cached model outputs.
49. **Continuous monitoring**: `monitors`/`notifications` models, rule-engine triggers, monitor worker (event + scheduled), anti-noise (dedupe/cooldown/severity), notification endpoints.
50. **Frontend (Next.js)**: auth flow, Twin dashboard, **React Flow live agent panel + replay animation**, decision + explanation + evidence graph + trust score, simulation probability charts, document upload — wired to API/SSE with generated DTO types.
51. **CI/CD + test suite + seed/demo**: GitHub Actions (lint/type/test/security/build/E2E), test pyramid incl. tenant-isolation + verifier + audit-integrity tests, golden transcripts, seed data, scripted demo, Grafana dashboards.

*(51 prompts — the roster of specialist agents in prompt 39 can be expanded 1:1 into more prompts post-hackathon.)*

---

## 5. Closing note

This blueprint is deliberately **trust-first**: the differentiators that win a hackathon *and* survive contact with real money — **debate, consensus, independent verification with deterministic recompute, evidence grounding, explainability, and full audit/replay** — are load-bearing in the architecture, not bolted on. Build the **Loan/Refinance vertical slice** end-to-end first ([§2](#2-hackathon-mvp-roadmap-the-winnable-slice)); every other pipeline and agent is an additive extension of the same spine.

← [Back to Index](README.md)
