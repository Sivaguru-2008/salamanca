# 09 — Engineering Standards, Delivery & Scaling

← [Index](README.md) · [Prev](08-observability.md) · [Next](10-adrs.md)

Covers requirements: **#39 Folder structure · #40 Project structure · #41 Naming · #42 Coding standards · #43 Testing · #44 CI/CD · #45 Deployment · #46 Scaling · #47 Extensibility**

---

## 1 & 2. Folder / Project structure

**Monorepo** (backend + frontend + infra + docs) — one clone, one compose-up, ideal for judges and for shared types.

```
fios/
├─ docker-compose.yml            # full stack: api, workers, pg, redis, qdrant, neo4j, otel
├─ docker-compose.override.yml   # local dev
├─ .github/workflows/            # CI/CD
├─ docs/architecture/            # THIS document
├─ infra/
│  ├─ otel/  grafana/  prometheus/   # observability configs
│  └─ neo4j/seed/                    # world-knowledge seed (regulations, products)
│
├─ backend/
│  ├─ pyproject.toml
│  ├─ alembic/                    # migrations
│  ├─ app/
│  │  ├─ main.py                  # FastAPI app factory + middleware wiring
│  │  ├─ core/                    # config, security, logging, otel, errors, deps
│  │  │  ├─ config.py             # Pydantic Settings
│  │  │  ├─ security.py           # jwt, argon2, rbac
│  │  │  ├─ observability.py
│  │  │  └─ errors.py             # problem+json mapping
│  │  ├─ api/v1/                  # routers (thin controllers) + DTO schemas
│  │  │  ├─ routers/  (auth, users, accounts, documents, twin,
│  │  │  │            decisions, simulations, counterfactuals,
│  │  │  │            agents, knowledge, monitors, audit, compliance)
│  │  │  └─ schemas/              # Pydantic request/response DTOs
│  │  ├─ domain/                  # business logic (framework-agnostic)
│  │  │  ├─ twin/                 # Digital Twin service + projection
│  │  │  ├─ decisions/            # decision aggregate + orchestration facade
│  │  │  ├─ memory/               # 4-tier memory services
│  │  │  ├─ documents/            # doc intelligence
│  │  │  ├─ compliance/           # rule engine
│  │  │  ├─ behavior/             # behavioral finance
│  │  │  └─ calculators/          # deterministic finance math (amortize, portfolio, sim)
│  │  ├─ agents/                  # REASONING plane
│  │  │  ├─ base.py               # BaseAgent contract
│  │  │  ├─ roster/               # planner, loan, investment, risk, behavior,
│  │  │  │                        # compliance, explainer, verifier, twin_keeper
│  │  │  ├─ orchestrator/         # LangGraph StateGraph, nodes, checkpointer
│  │  │  ├─ consensus/            # consensus engine
│  │  │  ├─ protocol/             # ACP envelopes + message types
│  │  │  ├─ llm/                  # LLM router + provider adapters
│  │  │  └─ tools/                # typed tool registry (ADK function tools)
│  │  ├─ infra/                   # adapters (ports & adapters / hexagonal)
│  │  │  ├─ db/                   # SQLAlchemy models, repositories, session
│  │  │  ├─ redis/                # cache + streams
│  │  │  ├─ qdrant/               # vector store adapter
│  │  │  ├─ neo4j/                # KG adapter
│  │  │  ├─ objectstore/          # blob adapter
│  │  │  └─ events/               # event bus (publish/consume)
│  │  └─ workers/                 # background consumers
│  │     ├─ document_worker.py
│  │     ├─ decision_worker.py
│  │     ├─ simulation_worker.py
│  │     └─ monitor_worker.py
│  └─ tests/  (unit/ integration/ e2e/ contract/ fixtures/ golden/)
│
└─ frontend/
   ├─ package.json
   └─ src/
      ├─ app/                     # Next.js app router (routes/pages)
      ├─ components/              # shadcn/ui + domain components
      │  ├─ agent-graph/          # React Flow: live agent panel + replay
      │  ├─ twin/                 # digital twin dashboards
      │  ├─ decisions/            # decision + explanation + evidence graph
      │  └─ simulations/          # probability charts
      ├─ lib/                     # api client, sse client, auth
      ├─ hooks/  stores/  types/  # shared TS types (mirror DTOs)
      └─ styles/
```

**Layering rule (dependency direction):** `api → domain/agents → infra`. The `domain` and `agents` layers never import framework/DB code directly — they depend on **ports (interfaces)**; `infra` provides adapters. This hexagonal seam is what lets modules become services later without rewrites (extensibility, #47).

---

## 3. Naming conventions

| Thing | Convention | Example |
|-------|------------|---------|
| Python modules/packages | `snake_case` | `decision_worker.py` |
| Python classes | `PascalCase` | `LoanAnalystAgent` |
| Python functions/vars | `snake_case` | `run_projection()` |
| Constants | `UPPER_SNAKE` | `MAX_DEBATE_ROUNDS` |
| DB tables/columns | `snake_case`, plural tables | `agent_opinions` |
| API routes | `kebab/lowercase`, plural nouns | `/api/v1/decisions` |
| JSON fields | `snake_case` | `trust_score` |
| Env vars | `UPPER_SNAKE`, prefixed | `FIOS_DB_URL`, `FIOS_LLM_OPENAI_KEY` |
| React components/files | `PascalCase.tsx` | `AgentGraph.tsx` |
| TS types/interfaces | `PascalCase` | `DecisionDTO` |
| Agents | `<Role>Agent` | `RiskSentinelAgent` |
| Tools | `verb_noun` | `run_sim`, `query_twin` |
| Events | `Noun.PastTense` | `TwinUpdated`, `DecisionCompleted` |
| Git branches | `type/short-desc` | `feat/consensus-engine` |
| Commits | Conventional Commits | `feat(agents): add verifier` |

---

## 4. Coding standards

| Area | Standard |
|------|----------|
| Python | 3.12; **type hints everywhere**; `ruff` (lint+format), `mypy --strict` on domain/agents |
| Boundaries | **Pydantic** models at every I/O boundary (API, agents, tools) — no untyped dicts crossing seams (Principle P2) |
| Async | async/await for all I/O (DB, HTTP, LLM); no blocking calls in request path |
| Errors | typed domain exceptions → mapped to problem+json; never `except: pass` |
| Money | `Decimal`/`NUMERIC` only; never `float` for currency |
| Purity | financial math in pure, unit-tested functions; LLMs never do arithmetic that matters |
| Secrets | via config only; lint rule blocks hardcoded secrets |
| Docstrings | every public service/agent documents Purpose/In/Out/Failure |
| Frontend | TypeScript strict; ESLint + Prettier; shared DTO types generated from OpenAPI |
| Reviews | PR required; CI green; no direct pushes to `main` |
| Commits | Conventional Commits → drives changelog/semver |

---

## 5. Testing strategy

**Core challenge:** how do you test a **non-deterministic** system deterministically? Answer: test the **deterministic contract around** the LLM, and pin the LLM behind fakes/goldens.

```
        ▲  fewer, slower, higher-confidence
        │   E2E  ── full stack via compose: upload doc → decision → explanation
        │   Contract ── API DTOs & agent I/O schemas (provider/consumer)
        │   Integration ── real Postgres/Redis/Qdrant/Neo4j (testcontainers)
        │   Component ── orchestrator graph with MOCKED agents (deterministic)
        │   Unit ── calculators, consensus math, rule engine, validators (pure, fast)
        ▼  many, fast
```

| Layer | What / how |
|-------|-----------|
| **Unit** | Pure finance math, consensus weighting, trust scoring, rule engine, output validators, hash-chain — fully deterministic, high coverage |
| **Agent-mocked component** | Run the LangGraph orchestrator with **stubbed agents** returning fixed opinions → assert consensus/verify/gate logic deterministically |
| **Golden transcripts** | Record real agent runs once; replay stored LLM outputs to test orchestration & regressions without live LLM calls (also powers Decision Replay) |
| **LLM eval suite** | Separate, non-blocking-in-PR **quality evals**: scenario prompts scored for correctness/grounding/refusal; tracked over time (nightly) |
| **Integration** | Real datastores via testcontainers; repositories, migrations, RLS policies |
| **Contract** | OpenAPI schema tests; agent Opinion/ACP schema validation |
| **E2E** | Docker Compose smoke: register → upload → decision → replay |
| **Security tests** | authz/RLS tenant-isolation tests, prompt-injection corpus, rate-limit tests |
| **Load** | k6 against API + queue depth under concurrent decisions |

**Non-negotiables:** tenant isolation, verifier recompute logic, and hash-chained audit integrity have **mandatory tests** — these are the trust core.

---

## 6. CI/CD strategy (GitHub Actions)

```
PR opened ──▶ [lint+format (ruff/eslint)] ─┐
             [type check (mypy/tsc)]        ├─ fail fast, parallel
             [unit tests]                   │
             [build images]                 ┘
          ──▶ [integration+contract tests (testcontainers)]
          ──▶ [security scan (deps: pip-audit/npm audit; SAST: bandit; secret scan)]
          ──▶ [E2E smoke on ephemeral compose]
          ──▶ ✅ required checks → mergeable

merge to main ──▶ [build+tag images] ─▶ [push to registry] ─▶ [deploy staging]
              ──▶ [migrations (alembic) gated] ─▶ [staging E2E] ─▶ [manual approve] ─▶ [prod]

nightly ──▶ [LLM quality eval suite] ─▶ [cost/regression report]
```

| Stage | Tooling |
|-------|---------|
| Lint/format/type | ruff, mypy, eslint, tsc |
| Tests | pytest, testcontainers, k6, playwright (frontend E2E) |
| Security | pip-audit, npm audit, bandit, gitleaks/secret-scan, Trivy (image scan) |
| Build | Docker buildx, layer caching, SBOM generation |
| Deploy | compose (MVP) → later Helm/k8s; DB migrations gated & reversible |
| Quality | nightly LLM evals, cost dashboards |

**Principles:** required green checks to merge; **migrations are versioned & reversible**; images are immutable and promoted (build once, deploy many); secrets never in CI logs.

---

## 7. Deployment strategy

| Phase | Target | Rationale |
|-------|--------|-----------|
| **Hackathon MVP** | **Docker Compose** (single host) | One command (`docker compose up`) reproduces the entire stack for judges; fastest path |
| **Post-hackathon** | Kubernetes (Helm) or managed containers | HPA autoscaling, rolling deploys, self-healing |
| **Data** | Managed Postgres + managed Redis + Qdrant/Neo4j (managed or operator) | offload ops |

- **Health:** `/healthz` (liveness), `/readyz` (readiness — checks DB/Redis/Qdrant/Neo4j).
- **Zero-downtime (later):** rolling update; stateless API/workers make this safe; migrations forward-compatible (expand/contract pattern).
- **Rollback:** immutable image tags → redeploy previous; DB migrations reversible.
- **Config per env** via env/secret injection (never rebuild to change env).

---

## 8. Scaling strategy

FIOS scales along **three independent axes** because the workloads differ:

| Axis | Bottleneck | Scaling approach |
|------|-----------|------------------|
| **API (interactive)** | request concurrency | stateless → horizontal replicas behind LB; Redis for shared state |
| **Agent/decision workers** | LLM latency + CPU | separate worker pool, scale by **queue depth**; bulkhead from API |
| **Simulation workers** | CPU-bound Monte Carlo | dedicated pool; parallel paths; autoscale on job backlog |
| **Datastores** | reads/writes | Postgres read replicas + PgBouncer pooling; Redis cluster; Qdrant/Neo4j sharding/replication later |

**Cost is a first-class scaling concern (it's an LLM system):**
- LLM response **caching** (semantic cache for repeated analyses).
- **Stakes-proportional** agent panels (don't run 9 agents for trivial queries).
- Per-user **cost budgets** + provider routing to cheapest capable model per task.
- Batch/async deep work; keep interactive path lean.

**Statelessness rule:** API and workers hold **no durable state** → any instance handles any request; all state in Postgres/Redis/Qdrant/Neo4j. This is what makes horizontal scaling trivial.

---

## 9. Future extensibility

The architecture is deliberately built so these extensions are **additive, not invasive**:

| Extension | Why it's easy |
|-----------|---------------|
| **New specialist agent** (tax, insurance, estate) | Implement `BaseAgent`, register in roster + tool registry; Planner picks it up. No orchestrator changes. |
| **New LLM provider** | Add an adapter behind the LLM Router; config routing. |
| **Monolith → microservices** | Module seams already match service boundaries (twin, documents, agents, compliance); ports/adapters + event bus already in place → lift a module into its own deployable. |
| **Real bank connectors** (Plaid, etc.) | New ingestion adapter → Normalizer → Twin; rest unchanged. |
| **New document type** | Add a schema + extractor; pipeline is generic. |
| **New regulation/jurisdiction** | Seed KG nodes + rules; versioned; no code change for compliance reasoning. |
| **New decision type** | Planner intent + relevant tools; orchestrator is intent-agnostic. |
| **Multi-language / white-label** | Frontend i18n; API already DTO-typed. |
| **Advisor/B2B mode** | RBAC roles (advisor) + grant model already modeled. |
| **Execution (if ever licensed)** | Add a guarded, human-confirmed action tool behind Compliance + Verify — the gates already exist. |

---

Next: [10 — Architecture Decision Records →](10-adrs.md)
