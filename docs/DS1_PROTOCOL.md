# DS-1 development protocol (pre-declared 2026-10-20, before any DS-1 code, cross-validation or run)

Owner approval: 2026-10-20 (DS-1 within the remaining Stage-2 authorization: at most +$10 infra and +$4.60 inference, no
cap change; displacement-aware evidence and stopping; non-LLM runs on the batch VM, with no key there and a control-plane
STOPPED check after each batch; trainable BiCAM after 29 Oct only). Plan: `docs/DUAL_SIGNAL_PLAN.md`, revised here
according to the owner's three design issues.

Development evidence only. The sealed test split, the held-out families and Stage 3 are untouched. Frozen modules stay
byte-identical:
- HDB v2 (`hdb_bench`, `hdb_heldout`, `hidden_plant`, `hdb_workbench`);
- `verdict_v1`, `full_recovery_v1`, pinned modules.
New behaviour lives in new modules or behind flags whose default reproduces engine v5 and agent v4 exactly.

## 0. Correction to the plan
- "Fix 1: one retry for invalid replies" was already implemented: `scientist_has._ask_role` makes one repair call.
- The 53 invalid Stage-2 turns failed *after* that call, almost all for semantic reasons:
  - counterfactual levels outside this design's bounds (e.g. balance_gain ×2 beyond the controller bound);
  - hidden-deviation names used as design parameters.
  The error text never listed the valid levels.
- **Fix 1 is therefore: informative constraint feedback**, within the same single repair call:
  - the notebook lists the valid counterfactual levels per parameter for this design;
  - errors name the valid levels, and explain deviation-vs-design-parameter confusion.

## 1. Engine v6 (identical for every v6 arm; the v5 path is preserved bit-identically by flag)
1. **Tempered likelihood:** weights ∝ exp(loglik / T).
   - T is chosen by leave-one-base-out on init-base engine records, recomputed from stored particle log-likelihoods.
   - Criterion: mean log P(true structure). The true structure is used only to *score* T; it is never an agent-visible
     feature.
2. **Structural misfit and composite hypotheses:**
   - **Statistic:** the leading particle's log-likelihood per observed seed on the *diagnostic* experiments (observe,
     counterfactual, floor). Plant checks of repaired designs are excluded: a repair failing is not evidence of an
     unmodelled cause.
   - **Threshold:** the 5th percentile of that statistic on init-base single-mechanism engine records whose leading
     explanation was correct.
   - **When flagged:**
     - the engine enumerates pairs of the leading distinct single-primitive structures (top 4 → at most 6 pairs);
     - each pair starts at its components' fitted parameters, its magnitudes are fitted (`fit_structures`, 1 round), and
       it is weighed by the same likelihood.
   - **Hard budget:** composite work may use at most min(500, twin remaining − 1,750) twin rollouts. 1,750 are reserved
     for repair. If less is available, nothing is enumerated and the event is recorded.
   - **Open-world reserve:** an "unmodelled" pseudo-hypothesis whose per-seed log-likelihood equals the threshold:
     - it takes posterior mass when every explanation fits worse than it;
     - it counts against the diagnosis-confidence stopping rule;
     - it is never used to design repairs.
3. **Cross-feedback from interventions:**
   - Every plant robustness check of a repaired design is assimilated automatically: each alive particle's twin predicts
     walking for that design on the same 8 robust seeds, and the walking-only likelihood reweights the hypotheses
     (`assimilate_check`, without refinement, to bound cost).
   - **Relative update:** an outcome that every competing mechanism predicted equally (e.g. all predicted success, and the
     repair failed) changes no relative weight. Only differential predictions move the belief.
   - **Re-screen:** if the leading structure changes, the engine re-screens tools under the new belief before its plant
     optimisation, when the twin budget allows.
   - **Recorded:** every assimilation logs the before and after posterior and each structure's predicted walking.
4. **Displacement-aware evidence and stopping:**
   - **Instrument** (new subclass `hdb_evidence.EvidenceWorkbench`; frozen workbench untouched):
     - robustness checks also return per-seed forward displacement while upright (walk-score proxy, zero if fallen
       before 1 s or no valid step);
     - a one-time charged baseline check of the faulty design on the same robust seeds (16 plant rollouts).
   - **Evidence:** paired candidate − faulty differences on the robust seeds:
     - wins / losses / ties (tie tolerance 0.05 m);
     - median difference;
     - a proxy pass flag mirroring `verdict_v1`'s rule (one-sided sign test p < 0.05 and median ≥ 0.5 m) on *robust*
       seeds.
   - Validation and confirmation seeds are never used.
   - **Stop map v2:** logistic P(FULL | robust16, stress4, displacement evidence), fitted on experience-base designs
     re-measured on the plant. It is compared with map v1 by leave-one-base-out Brier and AUROC. τ = 0.75 is kept. The
     final submission picks the checked design with the highest mapped P(FULL).
   - **Decision rule:** if map v2 does not beat v1 in base-grouped Brier, v6 keeps map v1, and displacement evidence is
     only displayed.

## 2. Repair learning: the R-head (`creature_forge/repair_learning.py`)
- **Rows:**
  - verified repair outcomes on init bases;
  - one row per verified design with its tool: engine final designs, A0 submissions, and stop-calibration "diverse"
    designs.
- **Agent-visible features only:**
  - the engine's structure posterior aggregated by deviation kind (10 kinds), its entropy and leading mass, re-tempered at
    T;
  - the engine's own tool-screen evidence for that tool (probe-score rank; ensemble twin-CMA walking and rank, or a
    missing flag);
  - the procedure that produced the row (engine final / A0 / diverse), set to "engine final" at decision time.
  - Injected mechanisms and families are never features.
- **Model:** L2-logistic with tool one-hot + kind-weight × tool interactions + tool-screen evidence + procedure. λ = 1.0
  is fixed a priori; sensitivity is reported only.
- **Baselines:**
  - B0 constant;
  - B1 engine-evidence-only logistic (the same tool-screen and procedure features, no situation × tool terms);
  - B2 tool-only rates.
- **Selection bias, documented with the results:**
  - outcomes exist only for tools that some procedure chose;
  - engine final tools got the full pipeline (twin warm start + plant CMA), while diverse rows used other budgets.
  - Rows are therefore missing not at random, and tool efficacy is confounded with procedure. That is why procedure is a
    covariate, and why the decision evaluation compares choices only among tools whose outcomes are known on the same
    instance.
- **Validation:** leave-one-base-out over the init bases.
  - Probability quality: log loss, Brier, ECE, reliability bins.
  - **Decision quality on comparable support:** instances with the engine's final tool's outcome known and at least one
    other tool's outcome known. Compare FULL for: the R-head's choice among the known tools, B1's choice, and the engine's
    actual choice. The base-bootstrap 90 % CI of R-head − engine is reported.
  - **Optional offline baseline:** similarity-softmax case attention (kernel over situation features, temperature by
    inner LOBO), with the same metrics.
- **Gate G-a (pre-declared):** the R-head enters arms A1x and A4x only if both hold:
  - its LOBO log loss < B1's;
  - its comparable-support FULL count ≥ the engine's.
  - Otherwise A1x is not run, A4x shows case evidence without R-head ordering, and repair learning is reported as null.

## 3. Shared causal experience store (`creature_forge/has_cases.py`)
- **Contents:** one case per repair attempt, with links to its investigation. Each case holds:
  - the situation (posterior summary, observation features);
  - diagnostic evidence (experiments, predictions, model check);
  - action (tool, mode, start edits);
  - visible evidence;
  - verified outcome.
- **Two separately scored signals:**
  - **Diagnostic:** log P(truth class), ECE, confident-wrong rate, prediction scores. Dossier diagnostic status uses
    precision and recall only.
  - **Repair:** FULL, P(FULL) Brier, lift over the engine default. Dossier repair status uses repair lift only.
- **Use:** Nemotron sees the R-head's P(FULL) per tool, the similar past cases (case attention) and its own track record
  (deviations from the engine default and how they verified; Brier of its registered P(success)).

## 4. Arms (identical instruments, plant budget 700, twin cap 2,800, same seeds)

| Arm | Engine | Learned repair ranking | Nemotron | Experience shown |
|---|---|---|---|---|
| A1e | v5 (historical reference) | – | – | – |
| A1e6 | v6 | – | – | – |
| A1x | v6 | R-head orders the engine's tools | – | – |
| A3v5 | v6 | – | yes (agent v5: constraint feedback, registered P(success)) | – |
| A4x | v6 | R-head is the default order of delegate_repair | yes | case evidence, R-head, dual-scored dossiers, track record |

- A1e6 vs A1x differ **only** by the R-head. A3v5 vs A1e6 and A4x vs A1x differ **only** by Nemotron.
- If A4x's Nemotron always delegates, A4x reproduces A1x (equivalence test, like A1e = A1c5).

## 5. Learning curve without leakage
- **Init bases:** 20 of the 30 experience bases. Stream bases: the other 10, fixed by a hash rule before any run.
  - Within each group, sort by sha256("ds1-stream:" + base_id) and take the first 4 old dev and 6 fresh dev bases.
  - Stream bases: walkrec-dev-m1-gen-0001, stilts-drawn, tiny-feet, walkrec-dev-m1-gen-0005, hdb-v1-gen-0038,
    hdb-v1-gen-0028, hdb-v1-gen-0036, hdb-v1-gen-0004, hdb-v1-gen-0013, hdb-v1-gen-0064.
- **What is fitted on init bases only:** the case store, R-head, temperature, misfit threshold, stop map v2 and dossier
  support. Every record from stream bases is excluded.
- **Stream:**
  - 30 new instances on the stream bases, never run in any earlier record (instance ids are checked against all records);
  - ordered by a fixed seed;
  - run in 6 chronological rounds of 5.
- **Paired arms, the same episodes in the same order:**
  - A4x-updating: after each round, its outcomes are appended, and the R-head, dossier support and track record are
    refreshed;
  - A4x-frozen: the init memory throughout;
  - non-LLM pair: A1x-updating vs A1x-frozen.
- **Measures over rounds:** repair-decision quality (FULL; R-head Brier on the new outcomes; Nemotron P(success) Brier)
  and diagnostic quality (log P(truth class)). The updating − frozen difference is the learning effect. n = 30 cannot
  confirm small effects; the curves are reported as they are.

## 6. Development evaluation (dev-eval-2)
- **Instances:** new instances on the 18 transfer bases, sampled with seed 20261020 before any run. All 52 Stage-2
  transfer instances are excluded.
  - 48 single-mechanism instances (9 families);
  - 12 development compositions.
  - Fewer if the budget gate (§7) requires it. The reduction is applied to every arm equally.
- **Memory:** M_final, the init memory plus the updating stream's outcomes, frozen for every arm that uses memory or the
  R-head.
- **Limitation:** the Stage-2 failure analysis read aggregate records on these bases.

## 7. Stages and gates (each stage reports before the next)
1. **Code + tests:**
   - v5 bit-identity of A1e;
   - the frozen-module hashes;
   - unit tests of temperature, misfit, assimilation (relative update), displacement evidence, R-head, case store, agent
     v5 validation.
2. **Offline:**
   - T fit;
   - misfit threshold;
   - stop-map v2 data and fit (batch VM, about 35k plant rollouts);
   - R-head LOBO → **G-a**.
3. **Pilot (experience init bases only, about 8 episodes per new arm):**
   - **G-b:** reply validity ≥ 95 %;
   - **G-m:** composite work never pushes twin remaining below the repair reserve, and on development compositions the
     leading explanation shares at least one injected primitive no less often than v5;
   - the A4x = A1x equivalence check with a scripted always-delegate scientist.
4. **Stream (§5)**, then **dev-eval-2 (§6)**, only if the projected spend stays within the remaining DS-1 allowance:
   - infra ledger ≤ $93.30 (= $83.30 + $10);
   - real billed inference since 2026-10-20 ≤ $4.60.
5. **Report:** both signals separately, the attribution contrasts of §4, the learning curves, costs, and the revised
   Stage-3 request.
6. **G-c (Stage-3 eligibility of A4x):** Nemotron registered P(success) on ≥ 80 % of repair decisions; deviated from the
   default in ≥ 15 % of episodes; A4x not worse than A1x by more than 2 discordant pairs.

## Amendment 1 (2026-10-20 03:05 UTC, before any pilot, stream or dev-eval-2 outcome)
- **Reason:** wall time, not results. Nemotron episodes cost about 0.62 vCPU-hours each, and the owner keeps LLM runs on the
  8-vCPU main VM. At the declared sizes the LLM work would need about 13 h of main-VM compute; the owner wants a finished
  milestone by the morning.
- **Changes** (applied equally to every arm and declared before any outcome):
  - pilot: 3 episodes per LLM arm, 4 for A1e6;
  - learning stream: 20 instances in 4 rounds of 5 (16 single + 4 compositions);
  - dev-eval-2: 30 single + 6 compositions per arm.
- **Gate G-a (§2) failed offline** (`experiments/causal_engineer/dev/hdb/ds1/OFFLINE.md`). As declared:
  - A1x is not run, and the R-head never orders tools;
  - A4x shows the repair-outcome model only as calibrated evidence, next to the similar cases and its track record;
  - the non-LLM updating-vs-frozen stream pair is dropped (its learned component failed the gate);
  - the A4x stream measures whether Nemotron's decisions improve with accumulating experience.
- **Equivalence check:** A4x with no scientist (`--no-scientist`) must reproduce A1e6 exactly. This shows the experience
  store does not change the instruments.
