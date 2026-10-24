# RL-1: learning which repair to apply, from verified successes and failures (plan, 2026-10-24)

**Status:** the development plan, executing autonomously on dev data under the owner's 2026-10-24 mandate. The future
registered evaluation (E-2, §7) will get its own registration before anything sealed or newly generated is opened.

**Branch:** `research/rl1-repair-learning`, based on `research/e1-engine-heldout`.

## 1. Question and claim

**Can Creature Forge use previous verified repair successes and failures to choose better physical interventions on
unfamiliar problems?**

**Target claim** (only if a registered test supports it): with the same diagnosis engine and identical plant and twin
budgets, a repair memory that learned from verified outcomes on development robots raises verified recovery on new robots
with new damage mechanisms, compared with:
- the same engine without repair memory;
- a simple memory baseline.

## 2. What E-1 and earlier work imply (the design constraints)

1. **Repair, not diagnosis, is the bottleneck on unfamiliar damage.** In E-1:
   - sensor latency was named correctly in 13 of 18 but repaired in 1;
   - joint damping was identified exactly in 16 of 18 but repaired in 3;
   - in 12 cases plant-probe-ranked search (A0) recovered where the engine's twin-ranked repair did not.
2. **A0 and A1 differ mainly in how they rank tools.**
   - A0 ranks by real plant counterfactual probes, then repairs the top 2.
   - A1 ranks by twin simulation under the diagnosed hypothesis, then repairs the top 2 from a twin warm start.
   - Neither learns anything from earlier robots.
3. **Why DS-1's learned repair head (R-head) failed gate G-a:**
   - **missing-not-at-random training data:** only tools that an engine had chosen were ever observed;
   - **population-level priors competing with instance-specific twin evidence:** its picks verified less often than the
     engine's own picks.

   RL-1 must avoid both problems.
4. **Earlier memories (dossiers, learned posterior) improved identification,** which E-1 shows is not binding.

## 3. Data: the dev repair response matrix (`scripts/rl1_matrix.py`; running now)

**Cells.** For each of the 211 fresh-dev instances (9 dev families on 18 fresh dev bases, the instances of
`fresh_A1c5.jsonl`) and **every** tool (10), the matrix records:
- the repair: plant-only CMA in that tool's subspace from the nominal design (300 plant rollouts, 4 train seeds);
- the independent verification: `full_recovery_v1` on validate and confirm seeds, giving the status and the validation
  walking fraction.

**Why every tool:** every tool is tried on every instance, so there is no missing-not-at-random data (fixes item 2.3).

**Per-instance context** comes from the stored A1c5 record of the same instance. Its diagnosis and twin screen are
identical up to the repair stage: G-R reproduced A1 exactly. The context is:
- the engine posterior (leading structures, mass, entropy);
- the twin probe score of every tool, and the short twin-CMA walking count and fitness of the top 5;
- the plant observation features (`belief_engine.FEATURES`) of the faulty robot;
- the plant counterfactual experiments the engine ran;
- the morphology and actuator constraints of the nominal design: segment lengths, foot length, torso mass, torque limit,
  total mass.

**Cost:** about 2,110 cells × 170 core-seconds, roughly 30–60 min on the batch VM, about $2. The VM stops itself when the
matrix is done.

## 4. Method: RL-1 repair memory

### 4.1 Experience record (one per attempted intervention)

| field group | contents |
|---|---|
| context | diagnosis summary (leading structure kinds, mass, entropy, unmodelled fraction); twin evidence for this tool (probe score, rank, twin-CMA walking and fitness when screened); plant observation signature; morphology and actuator constraints |
| intervention | tool, budget, start (nominal or twin warm start) |
| outcome | train walking, verified status, validation walking fraction |
| provenance | instance id, base id, family (**never a model input**), source file and hash |

### 4.2 Model

A per-tool success estimate built from two evidence sources and a learned calibrator:
- **Memory (similarity) evidence.**
  - Distance-weighted Beta–Binomial counts of verified success for tool t among past instances, in a standardised
    physics-feature space: observation signature, diagnosis kinds and morphology.
  - It yields a rate and an **effective support** n_eff.
  - Features are physical, never family labels, so it can generalise to mechanisms with similar physics.
- **Twin evidence.** The engine's probe score, twin-CMA walking and rank for tool t.
- **Calibrator.** A logistic stacking model:
  P(success_t) = σ(w · [twin evidence, memory rate, n_eff, mean neighbour distance, feasibility]).
  It is fitted on dev only, by cross-fitting.

### 4.3 Applicability and negative transfer

- **Out of support:** when n_eff is below a threshold or the nearest past cases are far, the memory abstains, and the
  engine's twin ranking is used unchanged.
- **Disagreement → investigate.** When memory and twin disagree strongly on the top tool, and neither is confident, the
  memory does not override. It **hedges**: the second repair slot goes to the other source's top tool instead of the
  engine's second choice.
- **Similar but misleading:** each memory neighbour carries its outcome under every tool, including failures. Similar
  contexts where the "obvious" tool failed lower that tool's estimate. Only the full matrix makes this possible.
- **No hard-coded fixes.** No rule names a family or mechanism. There are no new repair tools: lowering gains, for
  example, is already inside the existing `feedback` tool's range.
  - Capability changes that E-1 might suggest (latency compensation) are explicitly out of scope for RL-1. Mixing them in
    would confound learning with engineering.

### 4.4 Decision rule (fixed on dev offline, frozen before the online test)

- The engine's robust repair is unchanged, except for its `tool_order`.
- RL-1 supplies the order: commit, abstain or hedge, per §4.3.
- The plant and twin budgets and the stop rule are identical to A1.

## 5. Dev evaluation

### 5.1 Offline, on the matrix

**Policies:** each picks an ordered top-2 of tools; its matrix value is "success of either of its 2 tools".

| policy | description |
|---|---|
| P-eng | the engine's own twin ranking (A1) |
| P-probe | A0's plant-probe ranking |
| P-mem0 | **simple memory baseline:** the tool that most often succeeded on the k nearest past instances (raw observation features), ties broken by the engine's order |
| **P-RL1** | §4.2–4.4 |
| oracle | any tool that verified (headroom) |

**Splits:**
- **LOFO** (leave one family out): memory trained on 8 dev families, tested on the 9th, i.e. an unfamiliar mechanism;
- **LOBO** (leave one base out): an unfamiliar morphology;
- both are reported.

**Metrics:**
- the matrix success rate of the chosen top-2;
- verified-status agreement;
- the paired difference against P-eng, with a base-cluster bootstrap 90 % interval;
- the per-family difference (negative-transfer check);
- calibration (Brier score) of P(success_t).

**Gate G-RL1** (fixed now, before the matrix is read). P-RL1 goes online only if, under **LOFO**:
1. P-RL1 − P-eng > 0, with the base-cluster bootstrap 90 % lower bound > 0;
2. no family has P-RL1 − P-eng < −0.15 (no material negative transfer);
3. P-RL1 ≥ P-mem0.

If G-RL1 fails, RL-1 is reported as a null on dev and is not run online. The report then says which part failed.

### 5.2 Online dev test (only if G-RL1 passes)

**Arms,** on the same dev instances, paired, with plant budget 700, twin budget 2,800 and the stop rule all identical:
- **A1:** stored, reproduced exactly per G-R;
- **A1 + P-mem0;**
- **A1 + P-RL1**, with the memory LOFO-trained: an instance's own family is never in its memory.

This measures the real effect through the engine's full repair pipeline. The matrix measured plant-only single-tool
repairs, a proxy.

## 6. How much independence remains in the sealed reserve

**What E-1 exposed.** E-1 exposed verified outcomes on 160 instances across 90 of the 99 test bases, and the aggregate
results per sealed family: sensor latency is nearly unrepairable, damping is identified but not repaired.

**Instance-level generalisation is still testable** on the reserve. New (base, mechanism, severity) combinations are
possible, and RL-1 is trained on dev only. But:
- **Morphology level:** 90 of 99 test bases have published outcomes. Only 9 test bases are untouched, too few for a
  morphology-level claim.
- **Mechanism level:** the 4 sealed families are no longer unfamiliar *to the designer*. E-1's results informed this
  plan: repair is the bottleneck. A claim about "unfamiliar mechanisms" made on them would be contaminated at the design
  level, even though no model is trained on them.

**Recommendation:** the confirmatory test needs a **fresh, independently generated cohort**:
- **morphology:** new walkers from a new generation campaign (`hdb-v2-gen` / `hdb-v2-walkers`, same S3 generation rule,
  new seed) that nobody has seen;
- **mechanisms:** new held-out families **defined here, now, before any RL-1 result exists**, from (kind, target) pairs
  that no dev family, no E-1 family and no prompt has used.

| family (HF2) | primitive | variants | strength → parameter | max |
|---|---|---|---|---|
| knee_weakness | actuator_strength, knees | – | factor = e^(−s) | ln(1/0.05) |
| ankle_damping_wear | joint_damping, ankles | – | factor = e^(s) | ln(100) |
| one_side_slip | contact_friction, foot_l / foot_r | left, right | factor = e^(−s) | ln(1/0.02) |
| placement_gain_loss | gain_scale, placement | – | factor = e^(−s) | ln(1/0.02) |
| thigh_asymmetry | segment_length, thigh_l / thigh_r | left, right | factor = e^(−s) | ln(2) |

- **Severity:** the HDB v2 rule (multiples 1.0 / 1.3 / 1.7 of each variant's own threshold on the base).
- **Eligibility:** the HDB v2 rule; the reality gap is the frozen generator.
- **Related, not equal:** these are related to dev mechanisms (for example, knee weakness relates to whole-body actuator
  weakness, and one-side slip to symmetric low friction). That is the regime where memory can help, and where apparent
  similarity can mislead.
- **Secondary stratum:** the E-1 sealed reserve can be added as an instance-level stratum, labelled as such.

## 7. Registered evaluation E-2 (before the deadline if the dev gates pass)

- **Population:** about 120 instances.
  - Fresh hdb-v2 bases. The cohort is generated after E-2's registration; about 110 bodies give about 55 walkers.
  - Strata: HF2 families (about two thirds) and dev families on the new bases (about one third).
- **Arms:** A1 (engine, no repair memory) / A1 + P-mem0 / A1 + RL-1. The memory is trained on **all** dev matrix data and
  frozen at registration. Plant 700 and twin 2,800 are identical across arms.
- **Primary:** FULL(A1 + RL-1) > FULL(A1), exact one-sided McNemar, α = 0.05.
- **Secondary:** FULL(A1 + RL-1) > FULL(A1 + P-mem0), with a **fixed-sequence gate**: tested only if the primary rejects.
  This avoids the E-1 multiplicity ambiguity.
- **Nemotron (in scope, exploratory):** an A3 arm in which Nemotron sees the RL-1 evidence (memory rate, support, twin
  evidence) and chooses the tool order, run on a declared subset on the main VM. It is reported descriptively, not in the
  confirmatory family.
- **Power (honest):**
  - With about 120 instances and the E-1-like discordance rate (about 25 %), roughly 30 discordant pairs.
  - About 80 % power needs a true split of about 75:25.
  - A null is likely unless RL-1 is strong. The dev gates exist to avoid spending the cohort on a weak method.

## 8. Budget and timeline

| step | when | Cloud cost |
|---|---|---|
| dev matrix | 24 Oct (running) | ≈ $2 |
| offline development, G-RL1 | 25 Oct | $0 (local) |
| online dev test, 3 arms, about 108 instances | 25–26 Oct | ≈ $3 |
| E-2 registration; cohort generation (about 110 bodies) | 26 Oct | ≈ $3 |
| E-2 build and run | 27 Oct | ≈ $8 |
| report and submission update | 28 Oct | $0 |

- **Total:** ≈ $16 of about $28 remaining credit.
- **Inference (Nemotron arm):** ≤ $3 of Token Factory.
