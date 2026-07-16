# 05 — Data Architecture

← [Index](README.md) · [Prev](04-knowledge-graph-memory.md) · [Next](06-api-security.md)

Covers requirements: **#14 Database architecture · #15 ER diagram · #16 Tables · #17 Indexes · #18 Relationships**

---

## 1. Database architecture

### 1.1 Polyglot persistence — who owns what

| Store | Role | Rationale |
|-------|------|-----------|
| **PostgreSQL 16** | System of record: users, financial facts, twin snapshots, decisions, agent artifacts, audit ledger, episodic + procedural memory | ACID for money & audit; JSONB for flexible agent artifacts |
| **Redis 7** | Working memory, cache, rate limits, event streams (jobs/domain events) | Speed + lightweight bus |
| **Qdrant** | Semantic memory + document/RAG vectors | Purpose-built ANN + payload filtering |
| **Neo4j** | Financial Knowledge Graph | Native multi-hop reasoning |
| **Object store** (S3-compatible / local MinIO for MVP) | Raw uploaded documents | Cheap blob storage; keep binaries out of the DB |

**Rule:** Postgres is the **source of truth**. Qdrant and Neo4j are **derived** and rebuildable. This keeps the trust boundary small and makes disaster recovery tractable.

### 1.2 Postgres design conventions

- **UUID v7 / ULID** primary keys (`id`) — sortable, non-guessable, distributed-friendly.
- **Multi-tenancy:** every user-owned row carries `user_id`; enforced by **Row-Level Security (RLS)** policies as defense-in-depth behind app-layer scoping.
- **Money:** stored as `NUMERIC(18,4)` + explicit `currency` (never floats).
- **Time:** `TIMESTAMPTZ`, UTC; `created_at`/`updated_at` on every table.
- **Soft delete:** `deleted_at` where reversibility matters; **audit ledger is append-only** (no deletes ever).
- **Flexible artifacts:** agent opinions/transcripts/evidence in `JSONB` with GIN indexes.
- **Encryption:** sensitive columns encrypted at the application layer (envelope encryption); DB encrypted at rest.

---

## 2. ER diagram

```
┌──────────────┐        ┌───────────────┐         ┌────────────────┐
│    users     │1      *│   accounts    │1       *│  transactions  │
│──────────────│────────│───────────────│─────────│────────────────│
│ id (PK)      │        │ id (PK)       │         │ id (PK)        │
│ email        │        │ user_id (FK)  │         │ account_id(FK) │
│ role         │        │ type          │         │ amount         │
│ status       │        │ institution   │         │ category       │
└──────┬───────┘        │ balance       │         │ occurred_at    │
       │                └───────┬───────┘         └────────────────┘
       │1                        │
       │                         │
       │*        ┌───────────────┴────┐   ┌────────────────┐   ┌────────────────┐
       ├────────▶│   obligations      │   │     goals      │   │     assets     │
       │         │────────────────────│   │────────────────│   │────────────────│
       │         │ id (PK)            │   │ id (PK)        │   │ id (PK)        │
       │         │ user_id (FK)       │   │ user_id (FK)   │   │ user_id (FK)   │
       │         │ product_ref        │   │ target_amount  │   │ kind, value    │
       │         │ principal, apr     │   │ target_date    │   └────────────────┘
       │         │ term, schedule     │   │ priority       │
       │         └────────────────────┘   └────────────────┘
       │
       │1     *┌────────────────────┐        ┌─────────────────────┐
       ├──────▶│  twin_snapshots    │1      *│  twin_facts         │
       │       │────────────────────│────────│─────────────────────│
       │       │ id (PK)            │        │ id (PK)             │
       │       │ user_id (FK)       │        │ snapshot_id (FK)    │
       │       │ state (JSONB)      │        │ kind, key, value    │
       │       │ created_at         │        │ source_ref, conf    │
       │       └─────────┬──────────┘        └─────────────────────┘
       │                 │ referenced by
       │1     *          ▼
       ├──────▶┌────────────────────┐1      *┌─────────────────────┐
       │       │    decisions       │────────│   agent_opinions    │
       │       │────────────────────│        │─────────────────────│
       │       │ id (PK)            │        │ id (PK)             │
       │       │ user_id (FK)       │        │ decision_id (FK)    │
       │       │ intent, status     │        │ agent_role          │
       │       │ recommendation JSONB│       │ stance, confidence  │
       │       │ trust_score        │        │ opinion (JSONB)     │
       │       │ agreement_score    │        │ evidence (JSONB)    │
       │       │ verdict            │        │ round               │
       │       │ twin_snapshot_id FK│        └─────────────────────┘
       │       │ kg_version         │
       │       └───┬────────┬───────┘
       │           │1       │1
       │           │*       │*
       │  ┌────────▼───┐ ┌──▼──────────────┐   ┌─────────────────────┐
       │  │ evidence   │ │ simulation_runs │   │  counterfactuals     │
       │  │────────────│ │─────────────────│   │──────────────────────│
       │  │ id (PK)    │ │ id (PK)         │   │ id (PK)              │
       │  │ decision_id│ │ decision_id(FK) │   │ decision_id (FK)     │
       │  │ ref_type   │ │ spec (JSONB)    │   │ delta (JSONB)        │
       │  │ ref_id     │ │ seed            │   │ outcome_diff (JSONB) │
       │  │ payload    │ │ results (JSONB) │   └──────────────────────┘
       │  └────────────┘ └─────────────────┘
       │
       │1     *┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
       ├──────▶│    documents       │1 *│  document_chunks   │   │  audit_events      │
       │       │────────────────────│───│────────────────────│   │────────────────────│
       │       │ id (PK)            │   │ id (PK)            │   │ id (PK)            │
       │       │ user_id (FK)       │   │ document_id (FK)  │   │ user_id (FK)       │
       │       │ type, uri          │   │ span, text        │   │ decision_id (FK?)  │
       │       │ status, parsed     │   │ vector_id (Qdrant)│   │ event_type         │
       │       └────────────────────┘   │ extracted (JSONB) │   │ payload (JSONB)    │
       │                                 └────────────────────┘   │ prev_hash, hash    │
       │                                                          │ created_at         │
       │1     *┌────────────────────┐   ┌────────────────────┐   └────────────────────┘
       ├──────▶│ memory_episodes    │   │ memory_procedural  │
       │       │────────────────────│   │────────────────────│
       │       │ id (PK)            │   │ id (PK)            │
       │       │ user_id (FK)       │   │ user_id (FK?)      │
       │       │ event_type         │   │ scope (agent/user)│
       │       │ payload (JSONB)    │   │ policy (JSONB)     │
       │       │ occurred_at        │   │ updated_at         │
       │       └────────────────────┘   └────────────────────┘
       │
       │1     *┌────────────────────┐   ┌────────────────────┐
       ├──────▶│  monitors          │   │  notifications     │
       │       │────────────────────│   │────────────────────│
       │       │ id (PK)            │   │ id (PK)            │
       │       │ user_id (FK)       │   │ user_id (FK)       │
       │       │ trigger (JSONB)    │   │ severity, channel  │
       │       │ enabled, last_run  │   │ payload, read_at   │
       │       └────────────────────┘   └────────────────────┘
       │
       │*     1┌────────────────────┐
       └──────▶│  roles / rbac       │  (roles, permissions, role_permissions, user_roles)
               └────────────────────┘
```

---

## 3. Database tables

Core tables (representative — not exhaustive; types shown for Postgres).

### 3.1 Identity & access

| Table | Key columns | Notes |
|-------|-------------|-------|
| `users` | `id`, `email`(unique), `password_hash`, `status`, `mfa_enabled`, `created_at` | root identity |
| `roles` | `id`, `name` (owner/advisor/auditor/admin/system) | RBAC |
| `permissions` | `id`, `resource`, `action` | e.g., `decision:read` |
| `role_permissions` | `role_id`, `permission_id` | M:N |
| `user_roles` | `user_id`, `role_id`, `scope` | user↔role (optionally scoped) |
| `sessions` | `id`, `user_id`, `refresh_token_hash`, `expires_at`, `revoked_at` | refresh-token store |
| `api_keys` | `id`, `user_id`, `hash`, `scopes`, `expires_at` | programmatic access |

### 3.2 Financial state (system of record)

| Table | Key columns |
|-------|-------------|
| `accounts` | `id`, `user_id`, `type`, `institution`, `balance NUMERIC`, `currency`, `is_active` |
| `transactions` | `id`, `account_id`, `amount`, `currency`, `category`, `merchant`, `occurred_at` |
| `obligations` | `id`, `user_id`, `product_ref`, `principal`, `apr`, `term_months`, `schedule JSONB`, `origination_date` |
| `goals` | `id`, `user_id`, `name`, `target_amount`, `target_date`, `priority`, `status` |
| `assets` | `id`, `user_id`, `kind`, `value NUMERIC`, `as_of` |
| `cashflow_streams` | `id`, `user_id`, `direction`, `amount`, `cadence`, `category` |
| `risk_profiles` | `id`, `user_id`, `tolerance`, `capacity`, `constraints JSONB` |

### 3.3 Digital Twin

| Table | Key columns |
|-------|-------------|
| `twin_snapshots` | `id`, `user_id`, `state JSONB`, `reason`, `created_at` |
| `twin_facts` | `id`, `snapshot_id`, `kind`, `key`, `value JSONB`, `source_ref`, `confidence`, `as_of` |

### 3.4 Decisions & reasoning artifacts

| Table | Key columns |
|-------|-------------|
| `decisions` | `id`, `user_id`, `intent`, `params JSONB`, `status`, `recommendation JSONB`, `trust_score`, `agreement_score`, `verdict`, `twin_snapshot_id`, `kg_version`, `created_at` |
| `agent_opinions` | `id`, `decision_id`, `agent_role`, `round`, `stance`, `confidence`, `opinion JSONB`, `evidence JSONB`, `model_meta JSONB` |
| `agent_messages` | `id`, `decision_id`, `msg_type`, `sender`, `round`, `payload JSONB`, `refs JSONB`, `ts` (the ACP log → replay) |
| `evidence` | `id`, `decision_id`, `ref_type`, `ref_id`, `payload JSONB` |
| `simulation_runs` | `id`, `decision_id?`, `user_id`, `spec JSONB`, `seed`, `results JSONB`, `created_at` |
| `counterfactuals` | `id`, `decision_id`, `delta JSONB`, `outcome_diff JSONB` |
| `decision_checkpoints` | `id`, `decision_id`, `node`, `state JSONB`, `ts` (LangGraph checkpoints → replay) |

### 3.5 Documents

| Table | Key columns |
|-------|-------------|
| `documents` | `id`, `user_id`, `type`, `uri`, `status`, `parsed_at`, `meta JSONB` |
| `document_chunks` | `id`, `document_id`, `ordinal`, `span JSONB`, `text`, `vector_id`, `extracted JSONB` |
| `extracted_terms` | `id`, `document_id`, `term_type`, `value JSONB`, `confidence` (e.g., loan terms) |

### 3.6 Memory

| Table | Key columns |
|-------|-------------|
| `memory_episodes` | `id`, `user_id`, `event_type`, `payload JSONB`, `salience`, `occurred_at` |
| `memory_procedural` | `id`, `scope`, `owner_id`, `policy JSONB`, `updated_at` (agent calibration, user heuristics) |
| *(semantic memory lives in Qdrant; `document_chunks.vector_id`/`memory_episodes` link out)* | | |

### 3.7 Compliance, audit, monitoring, behavior

| Table | Key columns |
|-------|-------------|
| `audit_events` | `id`, `user_id`, `decision_id?`, `actor`, `event_type`, `payload JSONB`, `prev_hash`, `hash`, `created_at` — **append-only, hash-chained** |
| `compliance_checks` | `id`, `decision_id`, `jurisdiction`, `ruleset_version`, `result`, `violations JSONB` |
| `monitors` | `id`, `user_id`, `trigger JSONB`, `enabled`, `last_run_at`, `last_result JSONB` |
| `notifications` | `id`, `user_id`, `severity`, `channel`, `payload JSONB`, `read_at`, `created_at` |
| `behavior_profiles` | `id`, `user_id`, `biases JSONB`, `patterns JSONB`, `updated_at` |

---

## 4. Indexes

Indexing strategy = **cover the hot access paths, keep writes cheap, support tenant isolation**.

| Table | Index | Type | Why |
|-------|-------|------|-----|
| `users` | `UNIQUE(email)` | btree | login lookup |
| all user-owned | `(user_id)` | btree | tenant scoping (every query filters user_id) |
| `transactions` | `(account_id, occurred_at DESC)` | btree | statement/history queries |
| `transactions` | `(user_id, category, occurred_at)` | btree | budget analysis |
| `obligations` | `(user_id, product_ref)` | btree | loan lookups |
| `decisions` | `(user_id, created_at DESC)` | btree | decision history feed |
| `decisions` | `(status)` partial `WHERE status='running'` | btree partial | worker pickup of active jobs |
| `agent_opinions` | `(decision_id, round)` | btree | assemble a decision |
| `agent_messages` | `(decision_id, ts)` | btree | ordered ACP replay |
| `agent_opinions` | `evidence` | GIN (JSONB) | evidence lookups |
| `decisions` | `recommendation` | GIN (JSONB) | search inside recommendations |
| `twin_snapshots` | `(user_id, created_at DESC)` | btree | latest snapshot |
| `twin_facts` | `(snapshot_id, kind)` | btree | fact retrieval |
| `documents` | `(user_id, status)` | btree | pipeline status |
| `document_chunks` | `(document_id, ordinal)` | btree | reassemble doc |
| `memory_episodes` | `(user_id, occurred_at DESC)` | btree | episodic recall |
| `memory_episodes` | `(user_id, event_type)` | btree | topic recall |
| `audit_events` | `(user_id, created_at)` | btree | audit browsing |
| `audit_events` | `(decision_id)` | btree | reconstruct a decision |
| `audit_events` | `UNIQUE(hash)` | btree | tamper-evidence integrity |
| `monitors` | `(enabled, last_run_at)` | btree partial | scheduler scan |
| `notifications` | `(user_id, read_at)` | btree partial `WHERE read_at IS NULL` | unread badge |

**Qdrant (vector) indexing:** HNSW per collection; payload indexes on `user_id`, `doc_type`, `topic` for hard-filtered ANN.

**Neo4j indexing:** composite index on `(:User{id})`, label indexes on `Product`, `Regulation`, `Concept`; uniqueness constraint on business keys.

---

## 5. Relationships (cardinalities & integrity)

| Parent | Child | Cardinality | On delete | Notes |
|--------|-------|-------------|-----------|-------|
| users | accounts | 1:N | cascade (soft) | tenant root |
| accounts | transactions | 1:N | cascade | |
| users | obligations / goals / assets / cashflow_streams | 1:N | cascade | financial state |
| users | twin_snapshots | 1:N | restrict | snapshots retained for audit |
| twin_snapshots | twin_facts | 1:N | cascade | facts belong to a snapshot |
| users | decisions | 1:N | restrict | decisions retained |
| decisions | agent_opinions / agent_messages / evidence / counterfactuals / compliance_checks | 1:N | cascade-with-audit | reasoning artifacts |
| decisions | simulation_runs | 1:N | set null | sims can also be standalone |
| decisions | twin_snapshots | N:1 | restrict | decision pins the snapshot it reasoned over |
| users | documents | 1:N | cascade | |
| documents | document_chunks / extracted_terms | 1:N | cascade | |
| users | memory_episodes / behavior_profiles / monitors / notifications | 1:N | cascade | |
| users | audit_events | 1:N | **restrict (never delete)** | append-only ledger |
| roles ↔ permissions | role_permissions | M:N | cascade | RBAC |
| users ↔ roles | user_roles | M:N | cascade | RBAC |

**Referential-integrity philosophy:** FKs enforced in Postgres for the system of record; derived stores (Qdrant/Neo4j) reference Postgres ids **loosely** (eventual consistency, reconciled by sync jobs), so a vector store outage never corrupts the source of truth.

---

Next: [06 — API & Security →](06-api-security.md)
