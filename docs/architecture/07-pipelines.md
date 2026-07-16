# 07 — Domain Pipelines

← [Index](README.md) · [Prev](06-api-security.md) · [Next](08-observability.md)

Covers requirements: **#27 Document · #28 Loan · #29 Budget · #30 Investment · #31 Behavior · #32 Continuous monitoring**

Each pipeline below is specified with Purpose / Stages / Inputs / Outputs / Failure / Recovery.

---

## 1. Financial document processing pipeline

**Purpose:** Turn an uploaded financial document (statement, loan contract, tax form) into **structured, grounded facts** in the Twin + **searchable chunks** in memory.

```
Upload ──▶ [Store raw → object store] ──▶ [Docling: layout+table-aware parse]
       ──▶ [Classify doc type] ──▶ [Chunk (layout-aware)] 
       ──▶ [Embed chunks → Qdrant]                     (RAG / semantic memory)
       ──▶ [LLM Extractor → typed facts/terms]         (schema-constrained)
       ──▶ [Validate + confidence score]
       ──▶ [Normalizer → canonical facts] ──▶ [Twin-Keeper.apply → snapshot]
       ──▶ [Link entities → Neo4j KG]
       ──▶ [Emit DocumentProcessed event]
```

- **Why Docling:** financial docs are **tables + layout**, not prose; naive OCR loses structure. Docling preserves tables/columns so amortization schedules and statement line-items survive.
- **Schema-constrained extraction:** the LLM fills a **typed schema** (e.g., `LoanTerms`), not free text — every field carries a confidence + source span (grounding).
- **Inputs:** file (PDF/image), user_id. **Outputs:** twin facts, extracted terms, searchable chunks, KG links.
- **Failure modes:** unparseable scan; wrong doc type; low-confidence extraction; hallucinated fields.
- **Recovery:** OCR fallback for image-only; human-in-loop confirmation for low-confidence fields (surfaced in UI); fields below confidence threshold are **flagged, not silently trusted**; never write unverified numbers into the Twin as fact.

---

## 2. Loan Contract Intelligence pipeline

**Purpose:** Understand a loan/mortgage contract deeply — terms, hidden costs, risks, and whether a decision (refi, payoff) is wise.

```
[Doc pipeline extracts LoanTerms] (principal, apr, term, fees, prepayment penalty,
                                   rate type, balloon, covenants)
        │
        ▼
[Deterministic calculators] amortization schedule · effective APR · total interest ·
        │                    break-even for refi · prepayment cost
        ▼
[Risk Sentinel + Loan Analyst] read terms + calc results + KG(regulations,products)
        │  detect: hidden fees, rate-reset cliffs, penalty traps, underwater risk
        ▼
[Simulation] rate-path & income scenarios → prob(refi net-positive), tail risk
        │
        ▼
[Consensus → Verify (recompute schedule!) → Compliance(disclosures) → Explain]
        │
        ▼
Decision: "refinance / hold / caution" + amortization charts + counterfactuals + trust
```

- **Numbers are computed deterministically**, then the Verifier **recomputes** them independently — a refinancing break-even that doesn't survive recomputation is a hard fail.
- **KG use:** loan `INSTANCE_OF` product `GOVERNED_BY` regulation → surfaces jurisdiction-specific disclosure/suitability constraints.
- **Failure/Recovery:** missing terms → request the specific missing field from user; ambiguous rate type → conservative worst-case assumption, flagged.

---

## 3. Budget analysis pipeline

**Purpose:** Understand spending, find leaks, and connect budgeting to goals — *intelligently*, not as static category bars.

```
[Transactions] ──▶ [Categorize (rules + LLM for ambiguous)] ──▶ [Aggregate by period/category]
        │
        ▼
[Detect patterns] recurring subscriptions, creep, anomalies, seasonality
        │
        ▼
[Behavioral Coach] map overspend to biases (impulse categories, lifestyle inflation)
        │
        ▼
[Twin projection] "at this rate, goal X slips by N months"
        │
        ▼
[Counterfactuals] "cut Y by 15% → goal X reached 3 months sooner"
        │
        ▼
[Explain + nudges] concrete, ranked, personalized (grounded in this user's history)
```

- **Differentiator:** budget analysis is **goal-linked and behavioral**, not descriptive. It answers "so what?" via counterfactuals over the twin.
- **Failure/Recovery:** sparse transaction data → widen confidence bands, state limitations; miscategorization → user correction feeds procedural memory (learns the user's categories).

---

## 4. Investment pipeline

**Purpose:** Analyze allocation, risk/return fit, and contribution strategy against goals and risk profile.

```
[Assets + holdings + risk_profile + goals] ──▶ [Portfolio metrics: allocation, concentration,
                                                 risk/return, drawdown exposure]
        │
        ▼
[Investment Analyst] fit vs risk tolerance/capacity + goals + horizon
[Risk Sentinel]     concentration, tail risk, liquidity mismatch, correlation traps
        │
        ▼
[Monte Carlo simulation] contribution/return/inflation paths → prob(reach goal),
        │                 worst-case (CVaR), required-contribution distribution
        ▼
[Consensus → Verify → Compliance(suitability, disclaimers) → Explain + counterfactuals]
        │
        ▼
Recommendation: rebalance/contribute/hold + probability bands + "what if markets drop 30%"
```

- **Probabilistic, not point estimates** — output is "70% chance of reaching goal," with the distribution charted.
- **Compliance gate is mandatory** here (suitability + "not licensed advice" disclaimers).
- **Failure/Recovery:** unknown holdings → treat as opaque with conservative risk assumption, flagged; sim timeout → fewer paths + wider CI, disclosed.

---

## 5. Behavior analysis pipeline (Behavioral Finance Intelligence)

**Purpose:** Detect the user's cognitive biases and behavioral patterns, and use them to design **nudges that actually work for this person** — and to *warn* when a decision looks bias-driven.

```
[Signals] transaction timing/emotion proxies · decision acceptance/rejection history ·
          reaction to past advice · goal churn · panic-sell/impulse-buy patterns
        │
        ▼
[Bias detection] loss aversion, recency bias, present bias, overconfidence, herding, anchoring
        │
        ▼
[Update behavior_profile] (JSONB: biases + patterns + confidence)
        │
        ▼
[Feed agents] Behavioral Coach uses it for nudges; Risk Sentinel flags bias-driven decisions
        │
        ▼
[Procedural memory] which nudge framings this user responds to → improves over time
```

- **Two uses:** (1) *coach* — frame advice to land; (2) *guard* — "this looks like a panic decision; here's the counterfactual before you act." Directly serves the vision's "help users avoid poor financial decisions."
- **Ethics guardrail:** nudges must be **transparent and in the user's interest** (surfaced, not covert); logged for audit. No dark patterns — this is enforced as a design rule and reviewed in the Compliance gate.
- **Failure/Recovery:** thin history → low-confidence profile, generic (non-manipulative) framing; wrong inference → user feedback corrects it.

---

## 6. Continuous monitoring pipeline (Continuous Intelligence)

**Purpose:** Make FIOS *always-on* — re-evaluating the user's situation when their state or the world changes, instead of only when asked. Solves "static recommendations."

```
[Triggers]
  • TwinUpdated events (new transaction, balance change, doc ingested)
  • Scheduled sweeps (nightly health check)
  • External signals (rate change, market move) — pluggable feeds
        │
        ▼
[Monitor Worker] load user monitors + relevant twin deltas
        │
        ▼
[Rule Engine] evaluate triggers (thresholds, invariants):
     e.g., emergency fund < 1 month · debt-to-income breach · goal drifting ·
           unusual spend spike · refi window opened
        │
        ├─ nothing fired → record, sleep
        └─ fired → open a Decision job (full agent workflow) at appropriate stakes
        │
        ▼
[Notification] severity-ranked, respects quiet hours & user prefs
     (only surface high-value insights — avoid alert fatigue)
```

- **Event-driven + scheduled hybrid:** react instantly to state changes; sweep periodically for slow drifts.
- **Anti-noise design:** dedupe, severity thresholds, cooldowns per monitor → the system earns trust by not crying wolf.
- **Failure/Recovery:** trigger storm → debounce + coalesce; worker crash → at-least-once redelivery from Redis Streams, idempotent evaluation (dedupe by `(monitor_id, twin_snapshot_id)`); external feed down → degrade to internal triggers only, flagged.

---

## Pipeline summary matrix

| Pipeline | Trigger | Core engines | Key output | Mandatory gate |
|----------|---------|--------------|------------|----------------|
| Document | upload | Docling, LLM extract, Twin | grounded facts + chunks | confidence flag |
| Loan | doc / request | calculators, Sim, KG | refi/hold decision | Verify recompute + Compliance |
| Budget | request / nightly | categorize, Twin, counterfactual | goal-linked nudges | — |
| Investment | request | portfolio metrics, Monte Carlo | prob-of-goal + rebalance | Compliance suitability |
| Behavior | continuous | bias detection | behavior_profile + nudges | ethics guardrail |
| Monitoring | event / schedule | rule engine, orchestrator | proactive alerts + decisions | anti-noise |

---

Next: [08 — Observability →](08-observability.md)
