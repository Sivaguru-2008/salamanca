# 00 — Overview, Principles & Tech-Stack Rationale

← [Index](README.md)

---

## 1. Executive summary

FIOS is a platform that treats a user's finances as a **living, continuously-updated system of record** (the *Digital Twin*) over which a **multi-agent reasoning fabric** operates. The platform's differentiators are not features — they are **guarantees**:

1. **Every recommendation is explainable.** No black-box "you should refinance." Instead: the drivers, the numbers, the counterfactual, and the confidence.
2. **The system remembers.** A long-term financial memory means advice is grounded in the user's history, prior decisions, and stated goals — not a stateless prompt.
3. **Decisions are debated and verified.** Multiple agents produce independent opinions; a consensus engine reconciles them; a separate verifier tries to break the decision before it reaches the user.
4. **Everything is auditable and replayable.** Any recommendation can be reconstructed: which agents, which inputs, which model versions, which twin snapshot.

## 2. Problem framing — the 15 market gaps

| # | Gap | FIOS mechanism |
|---|-----|----------------|
| 1 | No explainable advice | Explainability Service + evidence graph attached to every decision |
| 2 | No long-term memory | 4-tier Memory subsystem (working / episodic / semantic / procedural) on Postgres + Qdrant + Neo4j |
| 3 | No digital twin | Financial Digital Twin service — canonical state + projection engine |
| 4 | Static recommendations | Continuous Monitoring pipeline re-evaluates on state/market change (event-driven) |
| 5 | No multi-agent collaboration | Agent fabric on LangGraph + Google ADK with a defined ACP |
| 6 | No consensus engine | Consensus Engine (weighted, evidence-aware voting + debate rounds) |
| 7 | No counterfactual reasoning | Counterfactual Service ("what would change if X") over the twin |
| 8 | No probabilistic planning | Monte-Carlo Simulation service with distributional outputs |
| 9 | No decision verification | Verifier Agent + rule engine + twin stress-test gate |
| 10 | No auditability | Append-only Audit Ledger + Decision Replay |
| 11 | No behavioral intelligence | Behavioral Finance engine (bias detection, nudges) |
| 12 | No financial knowledge graph | Neo4j Financial Knowledge Graph (entities, products, regulations, relationships) |
| 13 | No regulatory reasoning | Compliance Engine over a rules KG + jurisdiction context |
| 14 | No trust score | Trust/Confidence scoring composed from agreement, evidence, verification |
| 15 | No continuous intelligence | Event bus + scheduler drive always-on re-evaluation |

## 3. Design principles

| Principle | Statement | Consequence in the design |
|-----------|-----------|---------------------------|
| **P1 — Explainability is a first-class output** | A decision without an explanation is a bug. | Every agent must emit structured evidence; no "naked" recommendations. |
| **P2 — Determinism at the boundary** | LLMs are non-deterministic; the *contract* around them must not be. | Typed schemas (Pydantic) at every agent boundary; validation gates. |
| **P3 — Separation of proposer and verifier** | Whoever proposes must not be the sole judge. | Verifier Agent is architecturally isolated from proposing agents. |
| **P4 — Human money = human confirm** | Irreversible/financial actions require explicit user confirmation. | FIOS *recommends and simulates*; it never executes trades or transfers. |
| **P5 — Everything is an event** | State changes, agent steps, and decisions are events. | Event-sourced audit ledger; replay is a first-class capability. |
| **P6 — Fail safe, not silent** | A degraded answer is better than a wrong confident one. | Graceful degradation + explicit confidence downgrade on partial failure. |
| **P7 — Privacy by construction** | Financial data is maximally sensitive. | Field-level encryption, PII tokenization, tenant isolation, least privilege. |
| **P8 — Model-agnostic reasoning** | No single LLM vendor lock-in. | Router abstraction over OpenAI / Gemini / Claude behind one interface. |

## 4. Quality attributes (the "-ilities") and how they are met

| Attribute | Target | Architectural means |
|-----------|--------|---------------------|
| Explainability | 100% of decisions carry evidence | Evidence graph + Explainability Service |
| Auditability | 100% reconstructable | Event-sourced Audit Ledger + snapshotting |
| Reliability | No lost decision; at-least-once processing | Durable queues (Redis Streams), idempotent handlers |
| Availability | MVP: single-region; target 99.9% | Stateless API, health checks, graceful degradation |
| Latency | Interactive query p95 < 4 s; deep analysis async | Sync fast-path + async agent orchestration |
| Scalability | Horizontal on API + workers | Stateless services, queue-based workers, read replicas |
| Security | Zero-trust between services; encrypted at rest/in transit | OAuth2/OIDC, mTLS-ready, RBAC, field encryption |
| Observability | Every request traceable end-to-end | OpenTelemetry traces, structured logs, metrics |
| Testability | Deterministic tests around non-deterministic core | Agent mocking, golden transcripts, contract tests |
| Maintainability | Clear module boundaries | Hexagonal-ish layering, domain packages |

## 5. Architectural style

FIOS is a **modular monolith at the API tier + asynchronous agent workers**, event-driven internally, with **polyglot persistence**.

**Why not full microservices for the hackathon?**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Microservices from day 1 | Independent scaling, team autonomy | Heavy ops, network overhead, slow to build under hackathon time | ❌ premature |
| Pure monolith | Fast to build, simple | Agent workloads are long-running & bursty; blocks API | ❌ mixes concerns |
| **Modular monolith (API) + async workers (agents)** | Fast to ship, clean module seams, workers scale independently, easy to later split | Requires a message bus | ✅ **chosen** |

The module seams are drawn along future service boundaries (agents, twin, documents, knowledge, compliance), so the monolith can be **carved into services later without rewrites** (see [Extensibility](09-engineering-standards.md)).

## 6. Tech-stack rationale (ADR summaries)

Full ADRs in [10-adrs.md](10-adrs.md); summaries here.

| Layer | Choice | Chosen because | Alternatives rejected |
|-------|--------|----------------|-----------------------|
| API framework | **FastAPI** | Async-native (critical for fanning out to agents + LLM I/O), Pydantic typing enforces P2, OpenAPI for free | Flask (sync), Django (heavy), Node/Nest (Python-native AI ecosystem wins) |
| Language | **Python 3.12** | AI/agent ecosystem (ADK, LangGraph, LlamaIndex) is Python-first | — |
| Relational DB | **PostgreSQL 16** | ACID for money, JSONB for flexible agent artifacts, `pgvector` optional, mature | MySQL (weaker JSON/ext), Mongo (no ACID for ledgers) |
| Cache / bus | **Redis 7 (+ Streams)** | Cache, rate-limit, and durable-ish event streams in one dependency | Kafka (ops-heavy for MVP), RabbitMQ (extra infra) |
| Vector DB | **Qdrant** | Purpose-built ANN, payload filtering, self-hostable via Docker | pgvector (fine for MVP, but weaker filtering at scale), Pinecone (hosted lock-in) |
| Graph DB | **Neo4j** | Native graph for KG traversals & regulatory relationship reasoning | Postgres recursive CTEs (painful for deep graph), Neptune (AWS lock-in) |
| Agent orchestration | **LangGraph + Google ADK** | LangGraph gives explicit, inspectable **stateful graphs** (needed for replay); ADK adds structured multi-agent tooling | Raw prompt chains (no state/replay), AutoGen (less deterministic control) |
| RAG | **LlamaIndex** | Mature ingestion + retrieval abstractions over Qdrant | LangChain-only (heavier), hand-rolled (reinvention) |
| Document AI / OCR | **Docling** | High-quality layout-aware parsing of financial PDFs/tables | Tesseract (raw OCR, no layout), cloud OCR (privacy + cost) |
| LLM providers | **OpenAI + Gemini + Claude** behind a router | Diversity → better consensus + failover; each has strengths | Single vendor (lock-in, single point of failure) |
| Frontend | **Next.js + React + Tailwind + shadcn/ui** | SSR + great DX, shadcn for fast enterprise UI | CRA (dead), plain React (routing/SSR burden) |
| Graph/flow UI | **React Flow** | Visualize agent graphs, twin, KG, decision replay interactively | D3 hand-rolled (slow to build) |
| ORM / migrations | **SQLAlchemy 2.0 + Alembic** | Async ORM + versioned schema migrations | Raw SQL (no migration story), Tortoise (smaller ecosystem) |
| Packaging / deploy | **Docker + Docker Compose** | One-command reproducible stack for judges | Bare metal (not reproducible), k8s (overkill for hackathon) |
| CI/CD | **GitHub Actions** | Native to the repo, free minutes, matrix builds | Jenkins (ops burden) |

## 7. Non-goals (explicitly out of scope)

- FIOS does **not execute** trades, transfers, or payments. It is an **advisory + simulation** system (Principle P4). This is also a regulatory safety choice.
- FIOS is **not** a licensed financial advisor; outputs carry disclaimers and a Compliance gate.
- No real banking credentials are stored; aggregation is via read-only connectors / user-uploaded documents in the MVP.

---

Next: [01 — System Architecture →](01-system-architecture.md)
