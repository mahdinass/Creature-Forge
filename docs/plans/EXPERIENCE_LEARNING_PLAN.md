# Plan: `feature/experience-learning` — can measured interventions tell us when past repair experience applies? (revision 2)

- **Status:** revision 2, 2026-10-22. It **supersedes revision 1** (`8cae193`). Revision 1's P0 ("does memory predict the
  verified repair tool?") is withdrawn. Its engineering controls (§9) are kept.
- **Why it was revised:** the research review "Causal Experience Learning for Creature Forge: forskningsrapport og anbefalt
  studiedesign" (owner-supplied, 2026-10-22).
  - Predicting the historically chosen or historically successful tool mostly learns the old repair **policy**.
  - In the historical records, tool choice, repair procedure and budget are confounded, and most alternative repairs were never
    run.
  - Creature Forge has already shown that better prediction is not better recovery:
    - the R-head beat B1 on log loss but chose worse repairs (G-a failed);
    - engine v6 diagnosed better but repaired no better (8 vs 9).
- **Branch:** `feature/experience-learning`, from `v1.0.0-rc1` (`3a740a7`); worktree `cf-experience`. V1, `release/v1` and the
  submission materials are not touched.
- **Spend:** none. P0 is offline. Every later phase needs its own owner approval, and none auto-advances.

## 1. Research question and estimands

**Central hypothesis.** Experimentally measured intervention and repair outcomes can tell us whether a previous repair strategy
applies to a new robot, and selective reuse can avoid negative transfer.

Notation:
- x is the information legally available at the repair decision point.
- A is the repair tool, with a standardised repair procedure.
- Y = 1 only under the unchanged independent verifier `full_recovery_v1` (FULL_RECOVERY).
- π0 is the frozen no-memory policy; π_M is the memory policy with a frozen store S.

| Object | Definition | Role |
|---|---|---|
| Interventional repair value | Q(x, a) = P(Y = 1 \| do(A = a), x) | What a repair memory must learn. Historical tool frequencies estimate P(A_hist \| x) instead. |
| Policy benefit (primary, eventual) | Δ = E[Y(π_M(x, S)) − Y(π0(x))] | The eventual target: **verified repair-decision benefit** |
| Positive / negative transfer | p₊ = P(Y_M = 1, Y_0 = 0); p₋ = P(Y_M = 0, Y_0 = 1) | p₋ is the negative-transfer rate; net = p₊ − p₋ |
| Applicability | a(x) = P(Δ(x) > 0 \| x, S), or a conservative lower bound on Δ(x) | Not "two cases look alike", and not "they share a mechanism label" |

The eventual target is **verified repair-decision benefit, not historical repair-tool accuracy**. A model can reach 100 %
historical-tool accuracy and still never improve recovery.

## 2. What the records can and cannot identify

| Class | Examples in Creature Forge | What it supports |
|---|---|---|
| **Observed association** | historical tool → FULL; posterior → FULL; Nemotron deviation → FULL; diagnosis correct → FULL | Hypotheses only. Missing not at random, with procedure, budget and policy confounding |
| **Controlled intervention: within-instance measurement** | each experiment the engine ran: observe, counterfactual edit, floor test, weigh test, plant robustness check | The **measured response** is interventional. The **choice** of experiment is adaptive, so the same experiment is not exchangeable across episodes |
| **Controlled intervention: standardised panel** | the identifiability panel (`ident_v2_all`: every instrument on every instance); the causal-engineer probe catalogue (`probe_dev`: 9 fixed counterfactuals on every instance) | Comparable interventional fingerprints across robots (no selection) |
| **Controlled intervention: assigned repair** | causal-engineer repair matrix: all 10 tools, fixed budget 160, same train seeds | Q_proxy(x, a) for a **proxy** outcome on an older, different bench |
| **Controlled intervention: information or policy** | MKV K0n/K1/K2/K3/K4 (same pipeline and compute, assigned belief); TA-1 (forced tool order, 2 instances); DO-1/W3/W4 (objective change) | Effects of the assigned information or policy; the tool is a mediator, not the assigned factor |
| **Not identifiable from the records** | FULL under unchosen tools on HDB; tool effect separated from procedure and budget; the recovery effect of memory; transport of proxy repair effects to FULL | Needs new randomised physics data (§7) |

## 3. Outcome hierarchy
- **FULL_VERIFIED:** `full_recovery_v1` on the instance's validation and confirmation seeds (HDB episode records,
  `stopcal` re-verifications).
- **STANDARDIZED_DEV_PROXY:** the same assigned procedure for every tool, measured on a fixed seed set. It is not the verifier.
  The causal-engineer repair matrix (walking fraction on 8 check seeds) is the one example.
- **NON_COMPARABLE:** in-episode robustness checks (sequential, budget-dependent), different bench versions (HDB v1 vs v2),
  oracle-informed conditions (MKV K1–K4), and outcomes from a different verifier.

**Comparable repair outcomes.** Two outcomes on one instance are comparable at level:
- **S (strict):** same plant (bench version and instance), same verifier, the same repair procedure and budget accounting, no
  oracle information, different tools, with the tool **assigned** (forced, randomised or exhaustive) and not chosen by the
  policy.
- **P (policy-comparable):** same plant, same verifier, same engine version and budget caps, but the tool was **chosen** by
  different policies (e.g. A1e6, A3v5, A4x). The repair budget left is endogenous.
- **X (cross-procedure):** anything else (A0 vs engine, different engine versions, diverse/stop-calibration designs).

Several rows on one robot base are one independent group, never several robots.

## 4. P0 (revised): offline identifiability and decision-signal audit
P0 replaces revision 1's P0. It runs no MuJoCo, makes no paid model calls, opens no sealed data and uses no Nebius spend.

**Phase 2: inventory.** A provenance- and hash-checked inventory of the development archives (DS-1, Stage 2, Stage 1/MKV/
identifiability, and the causal-engineer dev probe set). It covers:
- independent bases, morphology and generator groups, and fault families;
- pre-intervention observations, and the diagnostic experiments in their actual temporal order;
- measured outcomes, the tools selected and the alternatives actually tested;
- procedure, budget, engine/optimizer configuration and seeds;
- outcome and verifier definitions, and missing or non-comparable fields.

Excluded are any record on a base outside the 48 declared development bases (`stage2_split.json`), the test-split walker file
and the causal-engineer held-out shards.

**Pre-declared adequacy criteria (decision target).**
- **Timing:** written after a preliminary *feasibility count* of HDB support, made while locating the archives and reported in
  the P0 report, but **before any Phase-3 predictive model was fitted or any Phase-3 metric was computed**.
- **D1: decision-signal test (exploratory).** A tier qualifies only if it has:
  - complete or randomised multi-action outcomes (level S), with no outcome missing because of the policy's choice;
  - ≥ 10 independent bases;
  - ≥ 30 instances on which the comparable tools' outcomes differ (only those carry decision information).
- **D2: a FULL-verified GO.** A GO for building a FULL-targeted transfer model needs a FULL_VERIFIED tier with:
  - level-S support on ≥ 20 independent bases;
  - ≥ 40 informative instances;
  - ≥ 3 fault families, each present on ≥ 2 bases.
- **Level P never qualifies** for fitting a decision predictor, because it is missing not at random and procedure-confounded.
  It is reported descriptively, as discordance rates for planning.
- **Proxy-tier limit:** a proxy-tier result can at most justify "run a randomised FULL-verified campaign". It never justifies a
  GO for a FULL transfer model.

**Phase 3 protocol** (run only on tiers that meet D1; descriptive elsewhere).
- **Comparators:**
  - frequency prior (π0 = the training-fold best tool);
  - morphology-only kNN on the *nominal* design;
  - observation + morphology kNN, the `experience_bank` signature: the pre-intervention observation only;
  - structured interventional retrieval: observation + standardised counterfactual responses;
  - a learned logistic ranking (Level C) where it exists.
  - **Not evaluable on the decision target:** belief-space case attention (`has_cases`) and the amortized posterior
    (`amortized_posterior`) exist only on HDB, where no tier meets D1. They are assessed on the HDB diagnostic precondition,
    as far as stored outputs allow (below).
- **Grouping and fitting:**
  - outer leave-one-base-out;
  - separate leave-one-fault-family-out and leave-one-generator-group-out holdouts where supported;
  - k and standardisation fitted inside the training fold, with k chosen by inner leave-one-base-out;
  - near-duplicate morphologies grouped and reported.
- **Leakage:**
  - instance/base ids, fault truth, severity, the injected design changes, outcomes, validation seeds and future experiments
    never enter a feature;
  - an interventional feature is legal only if its experiment has occurred by the decision point (standardised panels are run
    before the decision by design, and their rollout cost is reported);
  - a whitelist test enforces this.
- **Metrics:**
  - per (instance, tool) repair probability: log loss, Brier, calibration intercept and slope, reliability;
  - decision value of the top-1 tool on the measured matrix, regret, and Δ against π0;
  - negative-transfer rate, i.e. the memory pick fails where π0's succeeds;
  - risk–coverage of an abstention gate at matched coverage. Gates:
    - similarity distance;
    - predicted decision benefit, from the method's own estimates;
  - base-cluster bootstrap CIs (2,000 resamples, seed 20261022).
- **Controls:**
  - shuffled memory: 20 pre-registered permutations of the signature→outcome link in the training store;
  - hard-negative memory: the observationally nearest training case whose top tool fails on the query, against the nearest
    case whose top tool succeeds. The gate should separate them (AUROC);
  - a leakage probe using the faulty-body features of the older bench.
- **Primary P0 contrast (D1 tiers):** decision value of structured interventional retrieval minus observation + morphology kNN,
  leave-one-base-out. "Interventional decision signal present" requires all three:
  - the 90 % base-bootstrap CI excludes 0;
  - shuffled memory loses at least half of the interventional method's advantage over π0;
  - the sign is unchanged under leave-one-fault-family-out.
- **HDB diagnostic precondition (prognostic, not a decision claim).** On the standardised identifiability panel: fault-family
  prediction, by leave-one-base-out and leave-one-generator-out. Methods:
  - frequency prior;
  - morphology kNN;
  - observe-only kNN;
  - observe + conditions kNN;
  - full-panel kNN;
  - belief-space kNN on the stored model-based posterior;
  - the stored model-based twin posterior itself (the no-memory instrument baseline).

  A diagnostic gain is never reported as a recovery or decision gain.
- **No physics claim.** Offline predictions never support a claim of recovery improvement.

**Phase 4 decision rules.**
- **GO** (to a FULL-targeted selective-transfer harness): D2 holds, and the interventional decision signal is present on a
  FULL_VERIFIED tier.
- **NO-GO / redesign:** an adequate tier shows no interventional decision signal beyond observation kNN, or the signal is
  explained by shuffled memory, base or procedure identity, or leakage.
- **INSUFFICIENT-DATA:** no FULL_VERIFIED tier meets D2. Then no FULL counterfactual labels are invented and no FULL transfer
  predictor is built. The report proposes, and does not run, a minimal randomised multi-repair campaign (§7).

## 5. Report contents
The P0 report contains:
- the complete availability and comparability matrix;
- independent groups and effective sample sizes;
- source SHA-256 hashes;
- baselines and protocol;
- results with uncertainty, including negative findings;
- an evidence-leakage and procedure-confounding assessment;
- identifiability of the applicability target;
- GO / NO-GO / INSUFFICIENT-DATA.

Then **stop for independent review.**

## 6. When future randomised multi-repair simulations are justified
A development campaign (P0.5) is justified only if all hold:
1. P0 finds no FULL_VERIFIED tier meeting D2. The question is then not identifiable from logs, so new data are the only route.
2. There is at least one of:
   - an interventional decision signal on a proxy tier meeting D1;
   - a clear repair-heterogeneity signal (tools differ in outcome within instances on level-P support).

   Without either, the hypothesis has no support worth buying data for.
3. The campaign can deliver level-S FULL_VERIFIED support meeting D2 within an approved budget.
4. The design measures the costs the review identifies: optimizer stochasticity (technical replicates are not robots),
   heterogeneity across bases, and transport across fault families.

## 7. Phases (each needs separate owner approval; none auto-advances)
| Phase | What | Physics / model | Cost |
|---|---|---|---|
| **P0 audit (this revision)** | §4–5 | none | $0, local |
| P0.5 randomised repair-effect campaign | Standardised multi-tool FULL-verified matrices on development bases (design in the P0 report) | MuJoCo, no paid model calls | proposed in the P0 report |
| P1 harness | M0 / MK / MS / MSG / MS-shuffled / warm-start control behind a fail-closed runner; M-prior and M-repair ablated separately | none (tests, dry runs) | local |
| P2 prospective development pilot | new dev robots and faults; MSG vs MS (negative transfer) and vs MK | MuJoCo | to be estimated |
| P3 decision-aware diagnosis | only if P2 shows transfer signal: repair-regret-driven vs mechanism-EIG experiment selection | MuJoCo | to be estimated |
| P4 sealed confirmatory study | fresh sealed robot/fault families, M0 vs frozen MSG; preregistered | MuJoCo | to be estimated |
| P5 Nemotron extension | only after a positive deterministic study | paid inference | to be estimated |

**Revised later-phase arms** (from the review; not authorised):
- M0: no memory;
- MK: plain similarity retrieval;
- MS: structured interventional memory, ungated;
- MSG: MS with an applicability gate;
- MS-shuffled;
- a generic warm-start control (the same initialisation effect without the relevant case).

M-prior, M-repair and the gate are ablated separately in development before one configuration is frozen. Statistics are
paired by instance, with all discordant pairs reported and family-clustered inference. Power is fixed from a pilot discordance
estimate, not assumed.

## 8. Files (P0)
- `creature_forge/experience_audit.py`: source registry, hashing, record normalisation, comparability, support counting,
  morphology and generator groups, the feature whitelist, decision-point legality. Pure Python + numpy; no simulation.
- `creature_forge/experience_p0.py`: grouped/nested kNN estimators, proper scores, calibration, decision value,
  risk–coverage, shuffled and hard-negative controls, cluster bootstrap.
- `scripts/exp_p0_audit.py`: `inventory` and `analyse`. It writes to `experiments/causal_engineer/dev/experience_p0/`, a
  living development directory.
- `tests/test_experience_audit.py`: whitelist and leakage, grouping, comparability rules, decision-point legality, the sealed
  exclusion, and a MuJoCo tripwire.
- `docs/EXPERIENCE_P0_REPORT.md`: the decision report.

## 9. Engineering controls kept from revision 1 (for P1 and later)
- Frozen, hash-pinned store before any evaluation; the runner refuses a different hash.
- Feature whitelist: no ids, seeds, severity, injected structure or verifier fields.
- Disjoint bases; the sealed split released only by the owner; the 18 transfer bases are spent.
- Shuffled placebo and oracle as a labelled upper bound only.
- Intention to treat: abstentions (NOT_EXPOSED) kept and reported.
- Thresholds and weights fixed on development data only.
- Identical instances, seeds and budgets across arms; every rollout counted.
