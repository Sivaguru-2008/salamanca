# 06 — API & Security Architecture

← [Index](README.md) · [Prev](05-data-architecture.md) · [Next](07-pipelines.md)

Covers requirements: **#19 API architecture · #20 REST endpoints · #21 AuthN · #22 RBAC · #23 Security model · #24 Threat model**

---

## 1. API architecture

### 1.1 Style choice

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| GraphQL | Flexible queries | Overkill for MVP; caching/authz harder; agent jobs aren't query-shaped | ❌ |
| gRPC | Fast, typed | Poor browser story; hackathon friction | ❌ internal-only later |
| **REST + JSON (OpenAPI) + SSE for streaming** | Simple, cacheable, tooling, FastAPI auto-docs; SSE streams long agent jobs | Chattier | ✅ **chosen** |

**Async job model:** long decisions return **202 + job id**, and progress/results stream over **Server-Sent Events (SSE)** (`/decisions/{id}/stream`). SSE over WebSockets because the flow is server→client, unidirectional, reconnect-friendly, and proxy-simple.

### 1.2 Cross-cutting API concerns (middleware order)

```
request →
  [1] TraceContext (OTel trace/span, request id)
  [2] Security headers / CORS
  [3] AuthN (JWT verify → principal)
  [4] Rate limit (Redis token bucket per principal+route)
  [5] Idempotency (Idempotency-Key for POST that create jobs)
  [6] Request validation (Pydantic DTO)
  [7] AuthZ (RBAC policy check on resource+action)
  [8] Handler → service facade
  [9] Error mapping (domain error → RFC-7807 problem+json)
  [10] Response + audit event emit
→ response
```

### 1.3 API design conventions

- **Versioned:** `/api/v1/...`.
- **Errors:** RFC 7807 `application/problem+json` (`type`, `title`, `status`, `detail`, `trace_id`).
- **Pagination:** cursor-based (`?cursor=&limit=`).
- **Idempotency:** required `Idempotency-Key` header on job-creating POSTs.
- **Consistency:** all money as string-decimal in JSON to avoid float loss.

---

## 2. REST endpoint list

| Method | Path | Purpose | AuthZ (min role) |
|--------|------|---------|------------------|
| **Auth** | | | |
| POST | `/api/v1/auth/register` | create account | public |
| POST | `/api/v1/auth/login` | issue access+refresh JWT | public |
| POST | `/api/v1/auth/refresh` | rotate access token | valid refresh |
| POST | `/api/v1/auth/logout` | revoke refresh/session | user |
| POST | `/api/v1/auth/mfa/verify` | verify MFA challenge | user |
| **Users** | | | |
| GET | `/api/v1/users/me` | current profile | owner |
| PATCH | `/api/v1/users/me` | update profile/preferences | owner |
| **Accounts & facts** | | | |
| GET/POST | `/api/v1/accounts` | list/create accounts | owner |
| GET/PATCH/DELETE | `/api/v1/accounts/{id}` | manage account | owner |
| GET/POST | `/api/v1/transactions` | list/add transactions | owner |
| GET/POST | `/api/v1/obligations` | loans/debts | owner |
| GET/POST | `/api/v1/goals` | financial goals | owner |
| GET/POST | `/api/v1/assets` | assets | owner |
| **Documents** | | | |
| POST | `/api/v1/documents` | upload (multipart) → parse job | owner |
| GET | `/api/v1/documents/{id}` | status + extracted terms | owner |
| GET | `/api/v1/documents/{id}/stream` | SSE parse progress | owner |
| **Digital Twin** | | | |
| GET | `/api/v1/twin` | current twin snapshot | owner |
| GET | `/api/v1/twin/snapshots` | snapshot history | owner |
| POST | `/api/v1/twin/project` | deterministic projection | owner |
| **Decisions (core)** | | | |
| POST | `/api/v1/decisions` | start a decision job | owner |
| GET | `/api/v1/decisions` | history | owner |
| GET | `/api/v1/decisions/{id}` | full decision + evidence + trust | owner |
| GET | `/api/v1/decisions/{id}/stream` | SSE live agent progress | owner |
| GET | `/api/v1/decisions/{id}/explanation` | explanation + evidence graph | owner |
| POST | `/api/v1/decisions/{id}/feedback` | user accepts/rejects (feeds procedural memory) | owner |
| **Simulation & counterfactuals** | | | |
| POST | `/api/v1/simulations` | run Monte Carlo | owner |
| GET | `/api/v1/simulations/{id}` | results | owner |
| POST | `/api/v1/counterfactuals` | "what if" delta | owner |
| **Agents & knowledge** | | | |
| GET | `/api/v1/agents` | roster + status | owner |
| GET | `/api/v1/knowledge/query` | KG lookup (safe subset) | owner |
| **Monitoring** | | | |
| GET/POST | `/api/v1/monitors` | list/create monitors | owner |
| PATCH/DELETE | `/api/v1/monitors/{id}` | manage | owner |
| GET | `/api/v1/notifications` | list | owner |
| POST | `/api/v1/notifications/{id}/read` | mark read | owner |
| **Audit & compliance** | | | |
| GET | `/api/v1/audit/decisions/{id}` | audit trail of a decision | owner/auditor |
| POST | `/api/v1/audit/decisions/{id}/replay` | replay a decision | owner/auditor |
| GET | `/api/v1/compliance/checks/{decisionId}` | compliance result | owner/auditor |
| **Ops** | | | |
| GET | `/healthz` `/readyz` | liveness/readiness | public (internal) |
| GET | `/metrics` | Prometheus metrics | internal only |

---

## 3. Authentication architecture

### 3.1 Choice

**OAuth2 / OIDC-compatible, JWT access tokens + rotating refresh tokens**, MFA-capable.

| Option | Verdict |
|--------|---------|
| Sessions in DB only | ❌ doesn't scale statelessly across workers |
| Long-lived JWT only | ❌ can't revoke |
| **Short JWT access (≈15 min) + rotating refresh (DB-backed, revocable)** | ✅ stateless fast-path + revocation |

### 3.2 Flow

```
login → verify password (argon2id) → [MFA if enabled] →
  issue access JWT (15m, RS256, claims: sub, roles, scopes, tenant)
  issue refresh token (opaque, hashed in `sessions`, 30d, rotating)
→ client stores access in memory, refresh in httpOnly Secure SameSite cookie
→ access expires → /auth/refresh rotates (old refresh invalidated; reuse = breach → revoke all)
```

- **Signing:** RS256 (asymmetric) so workers verify with public key without the signing secret.
- **Token contents:** minimal claims; no PII in JWT.
- **Service-to-service:** internal calls carry a short-lived service JWT (mTLS-ready between containers in later phases).

---

## 4. RBAC

### 4.1 Model — roles × permissions, resource-action based

| Role | Description | Representative permissions |
|------|-------------|----------------------------|
| **owner** | The end user, owns their financial data | `*:own` (read/write own accounts, decisions, docs, monitors) |
| **advisor** | (future) delegated human advisor with user consent | `decision:read`, `twin:read` on granted users |
| **auditor** | Read-only access to audit/compliance/decision trails | `audit:read`, `compliance:read`, `decision:read` |
| **admin** | Platform operator (no financial-data read by default) | `user:manage`, `system:config` — **not** `financial:read` |
| **system** | Internal service principal (workers, agents) | scoped service permissions |

### 4.2 Enforcement (defense in depth)

```
[Layer 1] Route guard: JWT role/scope must satisfy endpoint policy
[Layer 2] Object-level check: principal.user_id == resource.user_id (ownership)
          (advisor/auditor: explicit grant row required)
[Layer 3] Postgres Row-Level Security: policies filter by current tenant
          → even a buggy query can't cross tenants
```

**Principle of least privilege:** `admin` deliberately cannot read financial data — separating operational admin from data access is a key FinTech control (prevents the "god admin" breach class).

---

## 5. Security model

### 5.1 Layered controls

| Layer | Control |
|-------|---------|
| Transport | TLS everywhere; HSTS; internal mTLS-ready |
| Identity | OAuth2/OIDC, argon2id password hashing, MFA, rotating refresh, breach-detection on refresh reuse |
| Authorization | RBAC + object ownership + Postgres RLS |
| Data at rest | DB encryption; **field-level (envelope) encryption** for sensitive columns; object store encryption |
| Data in transit | TLS; no PII in URLs/logs/JWTs |
| Secrets | Vault-ready secret manager; no secrets in code/images; per-env injection |
| Input | Pydantic validation, size limits, content-type allowlists, file-type sniffing on uploads |
| LLM-specific | Prompt-injection defenses (see 5.2), output schema validation, tool allowlists, PII minimization into prompts |
| Rate/abuse | Per-principal token buckets, upload quotas, cost budgets per user |
| Auditability | Hash-chained append-only audit ledger |
| Isolation | Per-tenant namespacing across Postgres/Qdrant/Neo4j |

### 5.2 LLM & agent-specific security (often ignored — a differentiator)

- **Prompt injection via documents:** an uploaded loan PDF could contain "ignore instructions." Mitigation: documents are treated as **data, never instructions**; extracted content is placed in clearly delimited, role-typed prompt sections; agents run with **tool allowlists**; no tool can perform side-effecting/irreversible financial actions (there are none — P4).
- **Tool abuse:** tools are typed, allowlisted, and rate-limited; no arbitrary code/SQL execution from agent output.
- **Data exfiltration via prompts:** cross-tenant isolation is enforced *below* the LLM (hard filters), so a manipulated prompt cannot retrieve another user's data.
- **Output grounding:** evidence-id resolution (see [02 §2.4](02-agent-architecture.md)) blocks fabricated figures reaching the user.
- **Cost DoS:** per-user token/cost budgets + bounded debate rounds + circuit breakers.

---

## 6. Threat model (STRIDE)

Scope boundary: browser ↔ API ↔ workers ↔ datastores ↔ LLM providers.

| Threat (STRIDE) | Example | Mitigation |
|-----------------|---------|------------|
| **Spoofing** | Stolen token, impersonation | Short JWT, rotating refresh, MFA, refresh-reuse breach detection |
| **Tampering** | Alter a decision/audit record | Append-only hash-chained ledger; RLS; FK integrity; immutable snapshots |
| **Repudiation** | "I never got that advice" | Full audit trail + decision replay + model_meta records |
| **Information disclosure** | Cross-tenant data leak; PII in logs | Tenant namespacing + RLS + log PII scrubbing + no PII in JWT/URLs |
| **Denial of service** | LLM cost bomb, upload flood | Rate limits, cost budgets, upload quotas, bounded agent loops, circuit breakers |
| **Elevation of privilege** | User → admin; agent → arbitrary action | Least-privilege RBAC, admin≠data-access, tool allowlists, no side-effecting tools |
| **Prompt injection** (LLM-era addition) | Malicious doc/notes steer agents | Data-not-instructions framing, delimited prompts, output validation, grounding |
| **Model manipulation** | Adversarial inputs to force bad advice | Verifier gate + deterministic recompute + rule invariants (a wrong number can't pass verification) |

### 6.1 Trust boundaries diagram

```
   ┌─────────────┐   TLS   ┌───────────────┐   internal   ┌──────────────┐
   │  Browser    │────────▶│   API (Edge)  │─────────────▶│   Workers    │
   │ (untrusted) │         │  authN/Z/RLS  │  (svc JWT)   │  (agents)    │
   └─────────────┘         └──────┬────────┘              └──────┬───────┘
        ▲  user data               │ RLS-scoped                   │ tool-allowlisted
        │                          ▼                              ▼
        │                    ┌───────────────────────────────────────────┐
        │                    │ Postgres · Redis · Qdrant · Neo4j · Object │
        │                    └───────────────────────────────────────────┘
        │                                        │ egress (data leaves boundary!)
        │                                        ▼
        │                             ┌──────────────────────┐
        └── advice ◀──────────────────│ LLM providers (3rd)  │  ← minimize PII sent
                                      └──────────────────────┘
```

**Key boundary note:** LLM providers are **outside** the trust boundary. Only **minimized, purpose-limited** context leaves; raw PII is tokenized/redacted before egress where feasible, and this egress is logged for audit.

---

Next: [07 — Domain Pipelines →](07-pipelines.md)
