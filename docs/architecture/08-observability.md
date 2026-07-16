# 08 — Observability, Error Handling & Configuration

← [Index](README.md) · [Prev](07-pipelines.md) · [Next](09-engineering-standards.md)

Covers requirements: **#33 Observability · #34 Logging · #35 Tracing · #36 Metrics · #37 Error handling · #38 Configuration management**

---

## 1. Observability architecture

**Purpose:** Because FIOS makes **money decisions via non-deterministic agents**, observability isn't optional — you must be able to answer "why did the system recommend this?" for *every* decision. Observability and auditability reinforce each other here.

### 1.1 Three pillars + a fourth

```
        ┌──────────────────────────────────────────────────────────────┐
        │                    OpenTelemetry (OTel)                        │
        │   unified instrumentation → traces + metrics + logs           │
        └───────────┬───────────────┬────────────────┬─────────────────┘
                    ▼               ▼                 ▼
              ┌──────────┐    ┌──────────┐      ┌──────────┐
              │ Tracing  │    │ Metrics  │      │ Logging  │
              │ (Jaeger/ │    │(Prometheus│     │ (Loki /  │
              │  Tempo)  │    │ +Grafana)│      │  stdout) │
              └──────────┘    └──────────┘      └──────────┘
                    │               │                 │
                    └───────────────┴─────────────────┘
                                    ▼
                    ┌────────────────────────────────────┐
                    │  4th pillar: AGENT/DECISION AUDIT   │
                    │  (append-only ledger + replay)      │
                    │  the "why" layer, business-grade    │
                    └────────────────────────────────────┘
```

The standard three pillars answer *ops* questions ("is it slow/broken?"). The **audit/replay** pillar answers *product/trust* questions ("why this advice?"). Both share the same `trace_id`/`decision_id` correlation.

---

## 2. Logging

| Aspect | Decision |
|--------|----------|
| Format | **Structured JSON** (one event per line) |
| Correlation | every log carries `trace_id`, `span_id`, `request_id`, `user_id`(hashed), `decision_id` |
| Levels | DEBUG/INFO/WARN/ERROR/CRITICAL; INFO default in prod |
| PII | **scrubbed** — no raw financial values, emails, or document text in logs; reference by id |
| Sensitive LLM I/O | prompts/outputs logged **by reference** to the audit ledger, not to app logs |
| Sinks | stdout (12-factor) → collector (Loki/ELK) |
| Retention | app logs 30d; audit ledger permanent |

**Rule:** logs are for **operators**; the **audit ledger** is for **accountability**. Never conflate them — different retention, different access control, different PII policy.

---

## 3. Tracing

- **OpenTelemetry** auto- + manual-instrumentation across API → orchestrator → agents → tools → datastores → LLM calls.
- A single decision produces **one trace** with spans for: `intake`, `plan`, each `agent.perceive/reason/act`, each `tool_call`, `consensus`, `verify`, `simulate`, `compliance`, `persist`.
- **LLM spans** record provider, model, version, token counts, latency, cost — this is both ops telemetry and audit data.
- **Cross-async propagation:** trace context is carried through Redis Streams messages so background jobs stay in the same trace.

```
trace: decision_7f3...
 ├─ span intake (12ms)
 ├─ span plan → llm(gemini) (1.4s, 900 tok)
 ├─ span dispatch
 │   ├─ span agent.loan → llm(claude) + tool.amortize (2.1s)
 │   ├─ span agent.risk → llm(openai) + tool.run_sim (3.8s)
 │   └─ span agent.compliance → tool.kg_lookup (0.4s)
 ├─ span consensus (0.2s)
 ├─ span verify → tool.recompute (0.9s)
 └─ span persist + audit (30ms)
```

---

## 4. Metrics

### 4.1 Metric taxonomy (RED + USE + domain)

| Category | Metrics |
|----------|---------|
| **RED (per endpoint/agent)** | Rate, Errors, Duration (p50/p95/p99) |
| **USE (resources)** | Utilization, Saturation, Errors for CPU/mem/queue depth/DB pool |
| **LLM/cost** | tokens per decision, cost per decision, provider error/failover rate, cache hit rate |
| **Agent quality** | consensus agreement score dist., verify pass/fail rate, abstain rate, debate rounds used |
| **Domain** | decisions/day, decisions by intent, doc parse success rate, monitor trigger rate, notification open rate |
| **Trust** | trust-score distribution, % contested decisions, % decisions rejected by verifier |
| **Reliability** | queue lag, job retry rate, DLQ size, replay success rate |

- **Alerting SLOs:** e.g., API p95 > 4s (5m), verify-fail-rate spike, LLM cost/user/hr breach, queue lag > threshold, DLQ non-empty.
- **Grafana dashboards:** Ops, LLM-cost, Agent-quality, Business.

---

## 5. Error handling

### 5.1 Taxonomy & strategy

| Error class | Example | Strategy |
|-------------|---------|----------|
| **Validation** | bad DTO | 422 problem+json, no retry |
| **AuthN/Z** | expired token | 401/403, client refresh |
| **Transient dependency** | LLM 429/5xx, DB blip | retry w/ exponential backoff + jitter, circuit breaker |
| **Provider outage** | OpenAI down | router failover to Gemini/Claude |
| **Agent failure** | schema-invalid/timeout | one structured retry → then `abstain` + degrade confidence |
| **Verification failure** | claim fails recompute | do NOT surface; retry/degrade/reject |
| **Business rule** | invariant violated | reject with explanation |
| **Fatal/unknown** | unhandled | 500 problem+json (no internals leaked), alert, trace captured |

### 5.2 Principles

- **Fail safe, not silent (P6):** partial failures **degrade with an explicit lowered trust score and a caveat**, never a silent confident answer.
- **Idempotency:** job-creating endpoints + all queue handlers are idempotent (dedupe keys) → safe retries.
- **Dead-letter queue:** poison messages go to a DLQ with full context for inspection, never lost.
- **Circuit breakers:** per external provider; open breaker → immediate failover/degrade instead of cascading timeouts.
- **Bulkheads:** agent worker pool isolated from API pool → a runaway agent job can't starve interactive requests.
- **User-facing errors** are RFC-7807 with a `trace_id` the user can quote to support — never stack traces.

---

## 6. Configuration management

| Concern | Approach |
|---------|----------|
| Method | **12-factor**: config in environment, code is env-agnostic |
| Layers | defaults (in-repo) → per-env `.env`/compose → runtime env → secret manager (highest) |
| Validation | **typed settings** (Pydantic Settings) validated at boot; app refuses to start on invalid/missing critical config |
| Secrets | never in code/images/logs; injected via secret manager (Vault-ready); local dev uses `.env` (gitignored) |
| Feature flags | config-driven toggles (e.g., enable/disable an agent, debate depth caps, model routing policy) |
| Model routing policy | declarative config: intent→provider preference, budgets, failover order |
| Environments | `local` / `test` / `staging` / `prod` — identical images, different config only |
| Reload | most config at boot; hot-reloadable subset (flags, routing) via config service + cache bust |

**Config as an ADR-worthy surface:** the **LLM routing policy** and **agent enablement/debate caps** are config, not code — so behavior/cost can be tuned (and demoed) without redeploys. This is central to controlling cost and adapting the agent panel per environment.

---

Next: [09 — Engineering Standards →](09-engineering-standards.md)
