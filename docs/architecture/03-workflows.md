# 03 — Core Workflows

← [Index](README.md) · [Prev](02-agent-architecture.md) · [Next](04-knowledge-graph-memory.md)

Covers requirements: **#6 Planner · #7 Consensus · #8 Verification · #9 Digital Twin · #10 Counterfactual · #11 Simulation · #26 Sequence diagrams**

---

## 1. Planner Agent workflow

**Purpose:** Convert a fuzzy user intent into a bounded, assignable plan — deciding *which* agents run, *what* context they need, and *how much* debate is warranted (proportional to stakes).

```
DecisionRequest(intent, params, user)
        │
        ▼
 classify intent  ──▶ {affordability | refinance | invest | budget | risk | doc_review | monitor}
        │
        ▼
 estimate stakes (amount at risk, irreversibility, horizon)
        │
        ├─ low stakes  → single-agent fast path, 0 debate rounds
        ├─ medium      → 2–3 agents, 1 debate round
        └─ high        → full panel, 2 debate rounds, mandatory verify + simulate
        │
        ▼
 select context needs → [twin fields, memory queries, KG topics, documents]
        │
        ▼
 emit PLAN{subtasks[], assignments{agent→subtask}, context_plan, debate_depth, gates}
```

**Contract**
- **Inputs:** intent, params, user profile, quick twin summary.
- **Outputs:** `PLAN` message (subtasks, agent assignments, context plan, debate depth, required gates).
- **Dependencies:** LLM Router, Twin (summary), KG (topic hints).
- **Failure modes:** mis-classification; over/under-planning.
- **Recovery:** default to a safe conservative plan (more agents, more verification) when classification confidence is low — bias toward caution for money.

**Trade-off (ADR-linked):** Stakes-proportional planning avoids running a 9-agent panel for "how much did I spend on coffee?" (cost) while guaranteeing full rigor for "should I take a $300k mortgage?" (safety).

---

## 2. Consensus Engine workflow

**Purpose:** Reconcile multiple, possibly conflicting, agent opinions into a single decision **with a defensible agreement score** — without letting one confident-but-wrong agent dominate.

### 2.1 Why not just "majority vote"?

| Method | Problem |
|--------|---------|
| Naive majority | Ignores expertise & evidence quality; ties; a domain-irrelevant agent gets equal say |
| Single "judge" LLM | Reintroduces black-box; proposer≈judge risk |
| **Weighted, evidence-aware reconciliation + bounded debate** | Accounts for relevance, evidence, calibration; auditable | ✅ |

### 2.2 Algorithm

```
Inputs: opinions[] (post-debate), each with stance, confidence, evidence[], agent relevance weight
Step 1  Filter: drop abstains; strip opinions whose evidence failed grounding
Step 2  Weight each opinion:
         w = relevance(agent,intent) × evidence_quality × calibration(agent history) × confidence
Step 3  Aggregate stance:
         score = Σ w·sign(stance)   (recommend=+1, caution=-0.5, oppose=-1)
Step 4  Agreement = 1 − normalized_dispersion(weighted stances)   // 0..1
Step 5  If agreement < θ_low AND stakes high → trigger extra debate round (up to cap) then re-run
Step 6  If still divergent → escalate: mark decision "contested", surface BOTH sides to user
Step 7  Else → candidate Decision = weighted-dominant stance + merged rationale + union of evidence
Output: CandidateDecision{stance, rationale, evidence[], agreement_score, dissent[]}
```

**Key properties**
- **Dissent is preserved, never hidden** — the UI can show minority positions (explainability + trust).
- **Calibration weighting** uses each agent's historical verify pass-rate (a learning loop; see Memory/procedural).
- **Contested decisions are a valid output** — FIOS says "experts disagree, here's why" rather than faking certainty.

**Contract**
- **Inputs:** post-debate opinions.
- **Outputs:** `CandidateDecision` + agreement score + dissent set.
- **Dependencies:** agent calibration history (Memory), evidence grounding results.
- **Failure modes:** persistent non-convergence; all agents abstain.
- **Recovery:** bounded extra debate; escalate to "contested"; if all abstain → "insufficient information" with what's missing.

---

## 3. Decision Verification workflow

**Purpose:** An **independent** gate that tries to *break* the candidate decision before the user sees it. Separation of proposer and verifier (Principle P3) is the core anti-hallucination / anti-overconfidence mechanism.

```
CandidateDecision + full context
        │
        ▼
 Verifier Agent (isolated; different model where possible)
        │
        ├─ Recompute: independently redo the numeric claims via deterministic tools
        │             (amortization, cashflow, allocation) → compare to claimed values
        ├─ Rule check: rule_eval against hard constraints (liquidity floor, DTI limits,
        │             emergency-fund invariants, jurisdiction rules)
        ├─ Twin stress: apply decision to twin; run adverse simulation; check survival
        │             (does user go cash-negative in a downturn?)
        └─ Consistency: does rationale actually follow from evidence? contradictions?
        │
        ▼
 VERDICT ∈ {PASS, PASS_WITH_CONDITIONS, FAIL}
        │
        ├─ PASS               → proceed to explain/compliance
        ├─ PASS_WITH_CONDITIONS → attach conditions/caveats, lower trust score
        └─ FAIL               → return to orchestrator:
                                  • retry with feedback (bounded), or
                                  • degrade to safer recommendation, or
                                  • reject → "we can't confidently recommend this"
```

**Why recompute instead of trust?** Numbers are verified by **re-running deterministic calculators**, not by asking an LLM "are you sure?". A claim that fails recomputation is a hard fail. This is the difference between a demo and a trustworthy financial product.

**Contract**
- **Inputs:** candidate decision, twin, rulesets, evidence.
- **Outputs:** `VERDICT` with reasons, corrected values, conditions.
- **Dependencies:** deterministic calculators, rule engine, simulation, twin.
- **Failure modes:** verifier itself errors/timeouts.
- **Recovery:** if verifier unavailable, decision is downgraded to "unverified — advisory only" with maximum caveats and lowered trust (never silently pass as verified).

---

## 4. Digital Twin workflow

**Purpose:** Maintain a canonical, queryable, projectable model of the user's finances that all agents share as ground truth.

### 4.1 Twin state model (conceptual)

```
FinancialTwin
 ├─ Accounts        (cash, savings, brokerage, retirement)
 ├─ Obligations     (loans, mortgages, credit lines, recurring bills)
 ├─ Cashflows       (income streams, expenses by category, cadence)
 ├─ Assets          (property, holdings)
 ├─ Goals           (targets: fund X by date, retire at N)
 ├─ RiskProfile     (tolerance, capacity, constraints)
 ├─ BehaviorProfile (biases, tendencies — from Behavior pipeline)
 └─ Snapshots[]      (immutable point-in-time copies for replay/audit)
```

### 4.2 Update & query flow

```
New fact (from doc parse / connector / manual) 
        │
        ▼
 Normalizer → canonical fact  ──▶  Twin-Keeper.apply()
        │                              │
        │                              ├─ validate against schema + invariants
        │                              ├─ write to Postgres (transactional)
        │                              ├─ new immutable Snapshot (if material change)
        │                              ├─ emit TwinUpdated event → triggers monitoring
        │                              └─ refresh embeddings/KG links (async)
        ▼
 Agents query via query_twin / twin_project (read from current snapshot)
```

### 4.3 Projection engine

- **Deterministic projection:** roll cashflows/obligations forward over a horizon (baseline).
- **Distributional projection:** hand off to Simulation (§6) for uncertainty bands.
- **Scenario twin:** a *copy* of the twin with hypothetical deltas applied — used by counterfactuals/simulation **without mutating** canonical state.

**Contract**
- **Inputs:** normalized facts, scenario deltas, projection horizon.
- **Outputs:** current snapshot, projections, scenario twins, `TwinUpdated` events.
- **Dependencies:** Postgres, Simulation, event bus, Normalizer.
- **Failure modes:** conflicting/stale facts; invariant violation; snapshot bloat.
- **Recovery:** conflict resolution (latest-authoritative-source wins, flagged); reject invariant-violating writes; snapshot compaction; full rebuild from event log + source docs.

---

## 5. Counterfactual workflow

**Purpose:** Answer "**what would change if…**" — the reasoning users actually want, and a differentiator vs. static tools.

```
Base decision/state  +  Δ (delta: e.g., "rate −0.5%", "income −20%", "buy now vs wait 1yr")
        │
        ▼
 build ScenarioTwin = clone(Twin).apply(Δ)     // never mutates canonical twin
        │
        ▼
 re-run the relevant projection/simulation on ScenarioTwin
        │
        ▼
 diff(base_outcome, scenario_outcome) → structured delta:
     • net worth Δ over horizon
     • cashflow Δ
     • risk Δ (e.g., probability of shortfall)
     • which goals move / break
        │
        ▼
 Explainer frames it: "If X, then Y changes by Z because …"
```

**Design choices**
- Counterfactuals operate on **cloned scenario twins** → safe, parallelizable, comparable.
- The **diff is structured**, not prose — so the UI can chart it and the Verifier can check it.
- Counterfactuals feed both the Explainability output and the Risk Sentinel's analysis.

**Contract**
- **Inputs:** base outcome, delta spec.
- **Outputs:** structured outcome diff + narrative.
- **Dependencies:** Twin (clone), Simulation, Explainer.
- **Failure modes:** ill-defined delta; combinatorial explosion of scenarios.
- **Recovery:** validate/normalize deltas; cap number of scenarios per request; prioritize by relevance from Planner.

---

## 6. Simulation workflow (probabilistic planning)

**Purpose:** Replace point-estimate advice with **distributions** — "80% chance you keep a 3-month buffer" beats "you'll be fine."

### 6.1 Why Monte Carlo?

| Method | Pros | Cons | Verdict |
|--------|------|------|---------|
| Single deterministic projection | Simple, fast | Ignores uncertainty; false precision | ❌ alone |
| Closed-form analytic | Exact for simple models | Real finances aren't closed-form | ❌ |
| **Monte Carlo simulation** | Handles uncertainty, correlations, fat tails; intuitive percentiles | Compute cost | ✅ (async worker) |

### 6.2 Flow

```
ScenarioSpec {horizon, variables (income, returns, inflation, expenses),
              distributions, correlations, num_paths}
        │
        ▼
 Simulation Worker (async, parallelizable):
   for path in N:
        sample stochastic variables → roll twin forward → record outcomes
        │
        ▼
 Aggregate → percentiles (p5..p95), probability-of-goal, prob-of-shortfall,
             worst-case (CVaR), distribution charts
        │
        ▼
 Persist SimulationRun (id, spec, seed, results)  // seed stored → reproducible
        │
        ▼
 Feed agents (Risk Sentinel, Loan/Investment), Verifier (stress), UI (charts)
```

**Reproducibility:** every run stores its **seed + spec**, so results are reproducible and auditable (a random simulation you can't reproduce is not auditable).

**Contract**
- **Inputs:** ScenarioSpec.
- **Outputs:** `SimulationRun` (percentiles, probabilities, tail metrics, seed).
- **Dependencies:** Twin (scenario clone), compute workers.
- **Failure modes:** long runtime; degenerate distributions; worker crash.
- **Recovery:** path-count adaptive to deadline (fewer paths → wider CI, flagged); checkpoint partial results; retry idempotently by seed.

---

## 7. Sequence diagrams

### 7.1 Deep decision (end-to-end)

```
User    API      Orchestrator   Planner   Agents(panel)   Consensus   Simulation   Verifier   Compliance   DB/Audit
 │  ask  │           │             │           │              │            │           │           │           │
 ├──────▶│           │             │           │              │            │           │           │           │
 │       ├─enqueue──▶│             │           │              │            │           │           │           │
 │◀─jobid┤ (SSE)     │             │           │              │            │           │           │           │
 │       │           ├─load ctx (twin/mem/KG/docs)            │            │           │           │           │
 │       │           ├───plan─────▶│           │              │            │           │           │           │
 │       │           │◀──PLAN──────┤           │              │            │           │           │           │
 │       │           ├─dispatch──────────────▶ │(parallel)    │            │           │           │           │
 │       │           │             │  perceive/reason/act     │            │           │           │           │
 │       │           │◀────────OPINIONS─────────┤             │            │           │           │           │
 │       │           ├─debate round(s) (CRITIQUE/REVISION)────┤            │           │           │           │
 │       │           ├──────────────────────────────────────▶│            │           │           │           │
 │       │           │◀─────────────CandidateDecision─────────┤            │           │           │           │
 │       │           ├─run sim / counterfactual─────────────────────────▶ │           │           │           │
 │       │           │◀──────────────distributions──────────────────────  ┤           │           │           │
 │       │           ├─verify────────────────────────────────────────────────────────▶│          │           │
 │       │           │◀─────────────VERDICT (pass/fail/cond)──────────────────────────  ┤          │           │
 │       │           ├─compliance gate───────────────────────────────────────────────────────────▶│          │
 │       │           │◀──────────────────pass/annotate────────────────────────────────────────────┤          │
 │       │           ├─persist decision+evidence+audit events──────────────────────────────────────────────▶ │
 │◀──stream result (recommendation, explanation, trust, counterfactuals, replay link)──────────────────────── │
```

### 7.2 Document → Twin (see also [07 §1](07-pipelines.md))

```
User    API     DocWorker(Docling)   Extractor(LLM)   Normalizer   Twin-Keeper   Qdrant/Neo4j   DB
 │upload │            │                    │              │             │             │          │
 ├──────▶├─store raw─▶│                    │              │             │             │          │
 │◀jobid ┤            ├─parse layout/tables│              │             │             │          │
 │       │            ├───────chunks──────▶│              │             │             │          │
 │       │            │              extract terms/facts  │             │             │          │
 │       │            │                    ├──facts──────▶│             │             │          │
 │       │            │                    │      normalize+validate    │             │          │
 │       │            │                    │              ├──apply─────▶│             │          │
 │       │            │                    │              │       write+snapshot──────────────▶ │
 │       │            ├─embed chunks──────────────────────────────────▶│(vectors)    │          │
 │       │            ├─link entities─────────────────────────────────▶│(graph)      │          │
 │◀──done (twin updated, doc searchable)───────────────────────────────────────────── ┤          │
```

### 7.3 Continuous monitoring trigger

```
Scheduler/Event   MonitorWorker   RuleEngine   Orchestrator   Notification
   │ tick/market Δ │                  │              │              │
   ├──────────────▶│ load twin deltas │              │              │
   │               ├─evaluate triggers▶│             │              │
   │               │◀─fired? ──────────┤              │              │
   │               ├─if fired: open decision job─────▶│             │
   │               │                  (full workflow) │             │
   │               │◀───────result─────────────────── ┤             │
   │               ├─notify user (respecting quiet hours/severity)──▶│
```

### 7.4 Decision Replay

```
User picks a past decision → API /audit/decisions/{id}/replay
        │
        ▼
 load Audit event log + checkpoints + cached model outputs + twin snapshot ref
        │
        ▼
 Orchestrator re-executes the StateGraph in REPLAY mode:
   • uses stored model outputs (no new LLM calls) → deterministic reproduction
   • UI (React Flow) animates each node/message in order
        │
        ▼
 shows exactly which agents said what, which evidence, which verdict → full transparency
```

---

Next: [04 — Knowledge Graph & Memory →](04-knowledge-graph-memory.md)
