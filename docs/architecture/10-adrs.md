# 10 — Architecture Decision Records (ADRs)

← [Index](README.md) · [Prev](09-engineering-standards.md) · [Next](11-roadmap.md)

Each ADR: **Context · Options · Decision · Consequences.** Status: all **Accepted** for v1 unless noted.

---

### ADR-001 — Modular monolith (API) + async agent workers, not microservices
- **Context:** Hackathon timeline; agent workloads are long-running/bursty; API must stay responsive.
- **Options:** (a) microservices, (b) pure monolith, (c) modular monolith + workers.
- **Decision:** (c). Draw module seams along future service boundaries.
- **Consequences:** Fast to build, clean seams, workers scale separately; requires an event bus; can split to services later without rewrite.

### ADR-002 — FastAPI + Python
- **Context:** Heavy LLM/agent I/O; Python-first AI ecosystem (ADK, LangGraph, LlamaIndex).
- **Options:** FastAPI, Flask, Django, Node/Nest.
- **Decision:** FastAPI.
- **Consequences:** Async-native, Pydantic typing enforces boundary contracts, free OpenAPI; team must follow async discipline.

### ADR-003 — LangGraph for orchestration + Google ADK for agents
- **Context:** Need deterministic, inspectable, **replayable** multi-agent coordination.
- **Options:** raw prompt chains, AutoGen, CrewAI, LangGraph, ADK.
- **Decision:** LangGraph (coordination, checkpointed state) + ADK (agent/tool primitives).
- **Consequences:** Explicit stateful graph → replay & audit; more engineering than a prompt chain; two libraries to learn. LangGraph checkpointer is the backbone of Decision Replay.

### ADR-004 — Multi-provider LLM router (OpenAI + Gemini + Claude)
- **Context:** Avoid vendor lock-in; diversity improves consensus; need failover.
- **Options:** single vendor; multi-vendor behind a router.
- **Decision:** Router abstraction with per-task routing + failover + cost budgets.
- **Consequences:** Resilience + better debate; added complexity normalizing providers; config-driven routing.

### ADR-005 — Proposer/Verifier separation with deterministic recompute
- **Context:** LLMs are overconfident; finance demands correctness.
- **Options:** self-check by same agent; LLM judge; independent verifier + deterministic recompute.
- **Decision:** Independent Verifier that **recomputes numbers with deterministic calculators** and stress-tests against the twin.
- **Consequences:** Strong anti-hallucination guarantee; a wrong number can't pass; extra latency/cost per decision (accepted — it's the trust core).

### ADR-006 — Deterministic financial math outside the LLM
- **Context:** LLM arithmetic is unreliable and unauditable.
- **Decision:** All money math in pure, unit-tested Python tools; LLM only selects tools & interprets results.
- **Consequences:** Auditable, testable, correct numbers; LLM can't "freestyle" figures.

### ADR-007 — Polyglot persistence (Postgres SoR + Qdrant + Neo4j + Redis)
- **Context:** Distinct needs: ACID facts, vector recall, graph reasoning, cache/bus.
- **Decision:** Postgres = source of truth; Qdrant/Neo4j = **derived, rebuildable**; Redis = cache/bus.
- **Consequences:** Right tool per job; small trust boundary; must maintain sync jobs; DR is tractable (rebuild derived stores).

### ADR-008 — Event-sourced, hash-chained append-only audit ledger
- **Context:** Requirements: auditability, replay, non-repudiation.
- **Options:** mutable audit table; append-only; append-only + hash chain.
- **Decision:** Append-only + hash chain (tamper-evident); corrections are new events.
- **Consequences:** Full reconstructability + tamper evidence; ledger grows (mitigated by archival); never delete.

### ADR-009 — SSE for streaming long agent jobs
- **Context:** Deep decisions take 20–90s; users want live progress.
- **Options:** poll, WebSocket, SSE.
- **Decision:** SSE (unidirectional server→client, reconnect-friendly, proxy-simple).
- **Consequences:** Simple live progress; not bidirectional (fine — no need).

### ADR-010 — OAuth2/OIDC, short JWT + rotating refresh, RBAC + RLS
- **Context:** Highly sensitive financial data, multi-role.
- **Decision:** Short RS256 JWT access + DB-backed rotating refresh; RBAC + object ownership + Postgres RLS; admin ≠ financial-data access.
- **Consequences:** Stateless fast path + revocability; defense-in-depth tenant isolation; more auth plumbing.

### ADR-011 — Advisory-only, no execution (no trades/transfers)
- **Context:** Regulatory risk; safety; Principle P4.
- **Decision:** FIOS recommends & simulates; never executes financial transactions.
- **Consequences:** Dramatically lower regulatory/safety surface; if execution ever needed, gates already exist to add it behind human confirm + compliance.

### ADR-012 — Stakes-proportional agent panels + bounded debate
- **Context:** Running 9 agents per query is costly and slow.
- **Decision:** Planner sizes the panel and debate depth to the stakes; hard caps on rounds/budget.
- **Consequences:** Controls cost/latency; guarantees rigor where it matters; adds a classification step (biased toward caution when unsure).

### ADR-013 — Docling for document intelligence
- **Context:** Financial docs are table/layout heavy.
- **Options:** Tesseract OCR, cloud OCR, Docling.
- **Decision:** Docling (layout+table-aware, self-hostable → privacy).
- **Consequences:** Preserves structure critical for loan/statement extraction; heavier dependency.

### ADR-014 — LlamaIndex + Qdrant for RAG/semantic memory
- **Decision:** LlamaIndex for ingestion/retrieval over Qdrant.
- **Consequences:** Mature retrieval abstractions + purpose-built ANN with payload filtering for per-user isolation.

### ADR-015 — Monte Carlo simulation with stored seeds
- **Context:** Need probabilistic planning that's reproducible/auditable.
- **Decision:** Monte Carlo in async workers; persist seed + spec → reproducible.
- **Consequences:** Distributions instead of false-precision point estimates; compute cost (async, adaptive path count).

### ADR-016 — Docker Compose for MVP deployment
- **Decision:** Single-command full-stack compose for the hackathon; k8s later.
- **Consequences:** Reproducible for judges; not production-HA (acceptable for MVP; roadmap to k8s).

### ADR-017 — OpenTelemetry + separate audit "why" pillar
- **Decision:** OTel for traces/metrics/logs (ops) + append-only audit/replay for accountability (product/trust), correlated by ids.
- **Consequences:** Both "is it broken?" and "why this advice?" answerable; two retention/access regimes to maintain.

### ADR-018 — Evidence-grounding guard (resolvable evidence ids)
- **Decision:** Every agent claim must cite resolvable evidence ids; unresolved → stripped + confidence penalty; zero evidence → forced abstain.
- **Consequences:** Structurally hard to surface fabricated numbers; slightly more constrained agent outputs (intended).

---

Next: [11 — Roadmap, Risks & Implementation Prompts →](11-roadmap.md)
