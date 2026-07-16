# 04 — Knowledge Graph & Memory Architecture

← [Index](README.md) · [Prev](03-workflows.md) · [Next](05-data-architecture.md)

Covers requirements: **#12 Knowledge Graph architecture · #13 Memory architecture**

---

## 1. Financial Knowledge Graph (Neo4j)

### 1.1 Purpose & why a graph

Financial reasoning is inherently **relational**: a loan *is governed by* a regulation; a product *is suitable for* a risk profile; an expense *belongs to* a category *that competes with* a goal. Answering "what regulations apply to refinancing this FHA loan in my state?" is a **multi-hop traversal**.

| Option | Multi-hop reasoning | Flexibility | Verdict |
|--------|--------------------|-------------|---------|
| Relational (recursive CTEs) | Painful, slow past 2–3 hops | Rigid schema | ❌ for deep reasoning |
| Document DB | No native relationships | Flexible | ❌ |
| **Neo4j property graph** | Native, fast traversals; Cypher | Schema-flexible | ✅ **chosen** |

**Scope decision:** The KG holds **shared/world knowledge** (products, regulations, concepts, relationships) *and* **per-user financial entity graphs** (their accounts/obligations/goals and how they relate), in separate namespaces. Per-user *raw facts* live in Postgres (system of record); the KG holds the *relationships and semantic links* for reasoning.

### 1.2 Node & relationship model

```
NODES
 (:User)                      per-user root
 (:Account) (:Obligation) (:Goal) (:Asset) (:CashflowStream)   per-user entities
 (:Product {type})           world: loan/mortgage/investment products
 (:Regulation {jurisdiction})world: rules, disclosures
 (:Concept)                   world: financial concepts (DTI, LTV, diversification)
 (:Institution)              world: lenders, brokers
 (:RiskFactor)               world: risk categories
 (:Decision)                 link to a past decision (for grounding)

RELATIONSHIPS
 (User)-[:OWNS]->(Account)
 (User)-[:HAS_OBLIGATION]->(Obligation)
 (User)-[:PURSUES]->(Goal)
 (Obligation)-[:INSTANCE_OF]->(Product)
 (Product)-[:GOVERNED_BY]->(Regulation)
 (Product)-[:SUITABLE_FOR]->(RiskProfile)
 (Regulation)-[:APPLIES_IN]->(Jurisdiction)
 (Concept)-[:AFFECTS]->(Concept)          e.g., LTV -[:AFFECTS]-> InterestRate
 (Obligation)-[:COMPETES_WITH]->(Goal)     debt vs savings tension
 (Decision)-[:REFERENCED]->(Product|Regulation|Concept)   evidence grounding
```

### 1.3 How agents use it

- **Compliance Officer:** `regulation_lookup` = Cypher traversal `Product→GOVERNED_BY→Regulation→APPLIES_IN→{jurisdiction}`.
- **Loan/Investment Analysts:** find comparable products, understand governing constraints.
- **Explainer:** builds the **evidence graph** by linking a decision's claims to KG nodes → this is literally what gets visualized in React Flow.
- **Risk Sentinel:** traverse `COMPETES_WITH` / `AFFECTS` chains to find second-order risks.

### 1.4 Contract

- **Purpose:** Relational substrate for regulatory/product/concept reasoning + evidence grounding.
- **Inputs:** entity upserts (from twin updates & doc extraction), curated world knowledge (seeded).
- **Outputs:** subgraphs, paths, rule sets.
- **Dependencies:** Neo4j; sync jobs from Postgres.
- **Failure modes:** graph drift from system of record; stale world knowledge; slow deep queries.
- **Recovery:** KG is **derived** → rebuildable from Postgres + seed data; query depth caps + indexes; versioned world-knowledge seeds.

### 1.5 World-knowledge seeding & versioning

World knowledge (regulations, product taxonomies) is **versioned** (`kg_version`) so a decision records *which knowledge version* it used → reproducible compliance reasoning even as laws change.

---

## 2. Memory architecture

### 2.1 Purpose — solving "no long-term memory"

A stateless LLM re-meets the user every prompt. FIOS gives agents a **4-tier memory** modeled on cognitive memory systems, each with a fit-for-purpose store.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            MEMORY SUBSYSTEM                               │
│                                                                          │
│  WORKING MEMORY        EPISODIC MEMORY       SEMANTIC MEMORY   PROCEDURAL │
│  (Redis, TTL)          (Postgres)            (Qdrant + LI)     (Postgres) │
│  ─ current job state   ─ events: decisions,  ─ embeddings of   ─ learned  │
│  ─ blackboard cache      conversations,        docs, notes,      policies:│
│  ─ per-request scratch   life events, goals    facts             agent    │
│                          (time-ordered log)  ─ semantic recall   calibr., │
│                                                                  heuristics│
└─────────────────────────────────────────────────────────────────────────┘
         ▲                    ▲                      ▲                ▲
         │                    │                      │                │
      fast, ephemeral   durable timeline      similarity recall   improves
                                                                   over time
```

### 2.2 The four tiers

| Tier | Analogy | Store | Holds | Lifetime |
|------|---------|-------|-------|----------|
| **Working** | short-term | Redis | active decision state, scratch | seconds–minutes (TTL) |
| **Episodic** | autobiographical | Postgres (append-only events) | "what happened": decisions made, advice given, user reactions, life events, goal changes | permanent (audit-linked) |
| **Semantic** | knowledge | Qdrant + LlamaIndex | vectorized facts, docs, notes for similarity recall | permanent, re-embeddable |
| **Procedural** | skills/habits | Postgres | learned agent calibrations, user-specific heuristics, effective nudge patterns | evolving |

### 2.3 Recall flow (how an agent "remembers")

```
Agent needs context for intent X
        │
        ▼
 memory_recall(query, user, k):
   1. Semantic search Qdrant (vector) filtered by user namespace → top-k passages
   2. Episodic query Postgres (structured: recent decisions on topic X, goal changes)
   3. Procedural fetch: this user's relevant learned heuristics + agent calibration
        │
        ▼
 rerank + dedupe + budget to token limit → MemoryBundle
        │
        ▼
 Prompt Assembler injects MemoryBundle into the agent prompt (as grounded evidence)
```

### 2.4 Write / consolidation flow

```
Decision finalized / conversation ends / doc ingested
        │
        ▼
 Memory Writer:
   • append Episodic event (durable, audit-linked)
   • embed salient artifacts → Qdrant (Semantic)
   • update Procedural (e.g., agent verify pass-rate → calibration weights;
     which nudge the user acted on → behavioral procedural memory)
        │
        ▼
 (periodic) Consolidation job:
   • summarize old episodes into higher-level semantic notes (compression)
   • decay/prune low-salience vectors
```

### 2.5 Why this composition (trade-offs)

| Alt considered | Why rejected |
|----------------|--------------|
| "Just stuff history into the prompt" | Blows context window, no relevance ranking, no durability, unauditable |
| Single vector store for everything | Loses time-ordering (episodic) and structured queries; no ACID for the timeline |
| Fine-tuning per user | Expensive, slow, privacy nightmare, not real-time |
| **4-tier polyglot memory** | Each need met by the right store; durable + recallable + evolving | ✅ |

### 2.6 Memory contract

- **Purpose:** Give agents durable, relevant, evolving context grounded in the user's real history.
- **Inputs:** decisions, conversations, docs, life/goal events, agent outcomes.
- **Outputs:** `MemoryBundle` (ranked, budgeted, grounded).
- **Dependencies:** Redis, Postgres, Qdrant, LlamaIndex, embedding model (via router).
- **Failure modes:** vector store down; irrelevant recall (noise); privacy leakage across users; unbounded growth.
- **Recovery:** semantic tier degrades gracefully to episodic-only recall; strict per-user namespace isolation (hard filter, never cross-tenant); consolidation/pruning caps growth; rebuild vectors from Postgres source of truth.

### 2.7 Privacy & isolation (critical for finance)

- Every vector and memory row is **namespaced by `user_id`**; recall queries **hard-filter** on it — cross-tenant recall is structurally impossible, not just discouraged.
- Salient PII in semantic memory is **tokenized/referenced**, not stored raw where avoidable.
- Memory honors deletion: a user data-deletion request purges Postgres rows, Qdrant vectors, and Neo4j per-user nodes (episodic audit events are retained per policy but PII-redacted).

---

Next: [05 — Data Architecture →](05-data-architecture.md)
