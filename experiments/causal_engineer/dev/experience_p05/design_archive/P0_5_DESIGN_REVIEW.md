# Creature Forge V2: P0.5 experimental-design review (proposal only)

- **Checkpoint:** `CF-V2-P0-2026-10-22`. The auditor's decision is REDESIGN: P0 is conditionally accepted as an
  identifiability audit, and the repair-memory hypothesis is not validated.
- **Based on:** `feature/experience-learning` at `e3caf8121da84523c36449e353a84bd05977ea9a`.
- **Status:** this is a design proposal for owner approval and external audit.
  - Nothing here was executed: no simulation, harness, paid inference, cloud spend, sealed or held-out access, commit or push.
  - This review read only the committed P0 evidence CSVs and the repository source.
  - V1 (`release/v1`, `v1.0.0-rc1` = `3a740a7…`) was not touched.
- **Supporting scripts:** both are read-only and not committed; they live in the session scratchpad.
  - `ds1_comparability_check.py` (sha256 `1a17aa530199bf648e5d0704b446e71eb528992069a673eb4b9879bd0b719c3b`) reproduces §1
    from the committed evidence.
  - `p05_precision.py` (sha256 `72a8812d92d76212cb148f8a3b3e9b2503b40ad23b594ecbde7dc125d31fae1c`) produces the tables in
    §6. It is closed-form arithmetic and reads no data.

**Claim labels, used throughout:**

| label | meaning |
|---|---|
| **[HIST]** | Historical evidence: read from existing records or committed P0 outputs. This includes counts re-derived in this review from those records; they are not independently audited. |
| **[INDEP]** | Independently established result: reconstructed by the external auditor and reproduced here from the committed evidence. |
| **[ASSUMP]** | Assumption: a design-stage value or premise that is not measured. |
| **[FUTURE]** | Proposed future measurement, procedure or design choice. It is not executed and not authorised. |

---

## 1. DS-1 comparability: resolving the nuance

### 1.1 The auditor's counts, checked row by row

| claim | auditor | this review | label |
|---|---|---|---|
| DS-1 `cases_init.json` rows / instances / bases | 947 / 231 / 20 | 947 / 231 / 20 | [INDEP] |
| multi-tool instances | 194 | 194 | [INDEP] |
| same-broad-label candidates (instance × label with ≥ 2 tools) | 70 instances | 70 instances, in 103 groups, on 8 bases | [INDEP] |
| … with differing recorded FULL rates | 21 | 21 | [INDEP] |
| … that overlap a level-P comparison somewhere in the expanded P0 corpus | 27 | 27 | [INDEP] |
| within DS-1 candidate rows: two tools under one broad procedure **and** one engine version | 18 | 18, all `engine_old` at `belief_engine_v4`, on 8 bases | [INDEP] |
| … of those, differing outcomes | 2 | 2: `weak-slippery:payload_offset:1`, `weak-slippery:pitch_sensor_bias:0` | [INDEP] |
| two different tools within one recorded arm | 0 | 0 for every repair-policy arm. Each DS-1 engine-arm file contributes exactly one row per instance. | [INDEP] |
| controlled, independently verifiable tool-effect comparisons | 0 | 0 | [INDEP] |

**There is no disagreement on any count.** The disagreement is with my own earlier wording, which equated
expanded-corpus overlap with candidate comparability. The row- and instance-level account follows.

### 1.2 Where my P0 wording conflated two different things [HIST]

**(a) "27 of the 70 are level P" (handoff §6.1) is an overlap statement, not a property of the DS-1 rows.**
- **18 of the 27** reach two tools inside the DS-1 candidate rows themselves.
  - Those rows come from the three engine-v4 arms `vs4_a1` (A1, provisional stop), `vs4_A1c` (A1c, calibrated stop
    τ = 0.75) and `vs4_A1f` (A1f, spend all).
  - The arms differ in stop rule and in the plant budget actually spent. For example, A1 often stops at 28 plant rollouts
    while A1c and A1f spend 676–700.
- **9 of the 27** reach level P **only through records that are not DS-1 candidate rows:**

  | source of the second tool | instances |
  |---|---|
  | MKV `mkv4.jsonl`, condition K0n (no oracle, different harness) | `top-heavy:low_ground_friction:1`, `top-heavy:pitch_sensor_bias:1`, `top-heavy:pitch_sensor_bias:4`, `top-heavy:short_feet:1`, `walkrec-dev-m1-gen-0000:payload_offset:4`, `walkrec-dev-m1-gen-0000:pitch_sensor_bias:4` |
  | `mkv5.jsonl` K0n plus `vs5_A1c.jsonl` (engine v5) | `walkrec-dev-m1-gen-0000:pitch_sensor_bias:1` |
  | Stage-2 pilot arms A3/A4 (recorded provenance LIVE) plus `vs5_A1c.jsonl` (engine v5) | `walkrec-dev-m1-gen-0002:short_feet:1`, `walkrec-dev-m1-gen-0003:payload_offset:1` |

  For these 9, the DS-1 rows show only one tool within any single engine version. My handoff phrase "two or more tools among
  engine-v4 arms that differ only in stop rule" is therefore **wrong for 9 of the 27**, three of which are at engine v5.

**(b) "21 with differing FULL" is a pooled, label-level statement.**
- **By label:** 13 differ only under `diverse`, 4 only under `engine_old`, and 4 under both.
- **The `diverse` differences:** all 17 come from `stopcal.jsonl`.
  - That file holds re-verified designs produced by *different steps* (twin search, counterfactual probe, plant repair)
    inside engine-v2 episodes.
  - It records no engine version and no per-design budget, and it has up to 4 rows per instance.
  - A literal group-by on the `arm` column (`stopcal`) would report 49 instances with ≥ 2 tools, 17 of them differing,
    "within one arm".
  - That is a grouping artefact. `stopcal` is a re-verification set, not a treatment arm. This is the only place where a
    naive analysis would contradict the auditor's "zero within one recorded arm".
- **The `engine_old` differences:** of the 8 instances with one, 6 differ only because the label pools the engine-v2 arm
  `vs2_a1` with the three v4 arms. Only **2 persist within one engine version**, the auditor's 2.
- **The 2 that persist confound tool with procedure:**
  - `weak-slippery:payload_offset:1`: A1 torso_mass is FULL at 28 plant rollouts; A1c torque_limit is PARTIAL at 700;
    A1f **torso_mass** is PARTIAL at 692. The same tool gives discordant outcomes across stop rules, so the difference
    cannot be attributed to the tool.
  - `weak-slippery:pitch_sensor_bias:0`: feedback is FULL under A1c and A1 (36 and 28 plant rollouts); torque_limit is
    PARTIAL under A1f (spend all, 692). Tool, stop rule and budget all change together.

**(c) Level P across the whole corpus pools more than stop-rule variants.**
- Of the 124 level-P instances, only **21** draw all their tools from stop-rule variants of one engine arm family.
- **103** pool other harnesses or arms within an engine version: LIVE Nemotron arms (A3, A4, A4x, A3v5), A2, MKV K0n, or
  DS-1 stream frozen-vs-updating runs.
  - The stream runs are 6 instances whose two tools come from `r*_frz_*` and `r*_upd_*` files, both labelled `A4x`.
  - So the `arm` field alone does not identify a condition.
- Handoff §10 item 4 ("Level P pools stop-rule variants of one engine version") understates this.
- The P0 verdict is unchanged, because level P was never eligible for a gate.

### 1.3 Proposed wording (to replace handoff §6.1 "Where they land in P0"; not yet edited)

> **Where they land in P0.**
> - Within the DS-1 candidate rows, 18 of the 70 instances (8 bases) have two tools under one broad procedure label
>   (`engine_old`) and one recorded engine version (v4). They come from three arms that differ in stop rule and spent plant
>   budget (A1, A1c, A1f).
>   - Only 2 of the 18 have differing recorded FULL rates.
>   - In both, the tool contrast is confounded with stop rule and budget. In one, the same tool is both FULL and PARTIAL
>     across arms.
>   - No DS-1 repair arm records two different tools for one instance.
>   - So DS-1 contains **zero** controlled tool-effect comparisons.
> - A further 9 of the 70 overlap a P0 level-P comparison only through records outside DS-1: MKV K0n (6 at v4, 1 at v5) and
>   Stage-2 LIVE arms A3/A4 (2 at v5). In total, 27 of the 70 *overlap* expanded-corpus level P. This overlap is not
>   same-arm or same-procedure comparability.
> - The 21 instances with differing FULL break down as follows:
>   - 17 differ within `diverse`, which holds stop-calibration designs from different procedural steps, with no engine
>     version or per-design budget;
>   - 8 differ within `engine_old`, of which 6 differ only through pooling engine v2 with v4;
>   - 9 of the 21 overlap expanded-corpus level P, 2 of them informative there.
> - Level P is descriptive. 103 of its 124 instances pool different harnesses or arms, including LIVE Nemotron arms, within
>   one engine version.

---

## 2. Causal estimands and identification assumptions

### 2.1 Units and stages

**Unit.** An *instance* x is a development base robot, one injected single-mechanism fault (family, severity) and the
initial design.

The study separates four stages:

| stage | what happens | what it may depend on |
|---|---|---|
| 1. **Diagnosis** D(x) | One standardised, **non-adaptive** prefix per instance, run by frozen engine v6 (NO_AI). Steps: the standard observe, the identifiability panel, nominal-twin predictions for every panel experiment, and the engine posterior. A snapshot is taken and hash-checked. | the instance only |
| 2. **Assignment** A | The tool. Under the recommended full-matrix design, every feasible tool. The feasibility screen is deterministic from the nominal design and bounds only. | the assignment seed and the pre-decision feasibility screen only |
| 3. **Repair optimisation** R(x, a, s_opt) | Fixed plant and twin budgets; starts from the stage-1 snapshot; independent optimizer seed; no information from any other cell. | snapshot, tool, optimizer seed |
| 4. **Outcome verification** Y | Unchanged `full_recovery_v1`. The validation and confirmation seed blocks are shared by all cells of an instance (common random numbers) and disjoint from every training, screening or probe seed. They are used once and never for selection. | final design, verification seeds |

All four stages are [FUTURE].

### 2.2 Estimands [FUTURE]

- **Cell response:** Q(x, a) = P(Y = FULL | do(A = a), D(x), budget B, procedure R). The expectation is over the optimizer
  seed; validation seeds are fixed per instance. One cell is one Bernoulli draw from Q.
- **Average tool effect:** τ(a, a′) = E_x[Q(x, a) − Q(x, a′)] over the declared development population.
- **Policy value:** a decision policy π maps legal pre-decision information h(x) ⊂ D(x) to a feasible tool. Its value is
  V(π) = E_x[Q(x, π(h(x)))]. The fallback π0 is engine v6's top-ranked feasible tool from the prefix posterior.
- **Policy contrasts:** Δ(π, π′) = V(π) − V(π′), with p₊ and p₋ the fractions of instances where π succeeds and π′ fails,
  and the reverse.
- **Headroom (value of tool choice):** Γ = E_x[max_a Q(x, a) − Q(x, π0(x))]. This is an upper bound on what *any*
  tool-selection memory can add.
  - The naive maximum over single draws is biased upward.
  - The estimator is replicate-split: choose argmax_a on replicate 1 and evaluate it on replicate 2, on the replicate subset.
- **Cost-aware utility:** U(π) = E_x[Y − λ·(plant rollouts spent on diagnosis attributable to π + repair) / C_ref].
  - λ and C_ref are owner-declared (open question Q3).
  - Twin rollouts count as compute, not plant cost.

### 2.3 Identification assumptions

| # | assumption | how it is supported or tested |
|---|---|---|
| I1 | **Consistency and no interference:** a cell's outcome depends only on (snapshot, tool, optimizer seed, verification seeds). | Cells are separate processes from a hash-checked snapshot. A determinism sentinel runs at the start, middle and end. [FUTURE] |
| I2 | **Ignorability by design:** full matrix, so every feasible tool is observed. Under a subset design, assignment is by a seeded draw independent of outcomes given D(x). | assignment log with seed and propensity [FUTURE] |
| I3 | **Positivity:** every feasible tool has assignment probability > 0 (= 1 under the full matrix). Infeasible tools are removed from *every* policy's action set. | feasibility log [FUTURE] |
| I4 | **Shared diagnosis:** every cell of an instance starts from an identical diagnostic state. | snapshot hash recorded per cell [FUTURE] |
| I5 | **Measurement invariance:** same verifier, same seeds and same thresholds for every tool. | verifier version and seed-block ids recorded per cell [FUTURE] |
| I6 | **Simulator stability:** same MuJoCo, numpy and Python versions and thread settings throughout. | environment manifest; sentinel [FUTURE] |
| I7 | **Transport:** effects on development bases say something about unseen bases. Only cross-base transport within the development population is tested (LOBO, LOGO). Transport to the sealed test population is **not** tested. | [ASSUMP] |
| I8 | Q is defined at **one declared budget level B**. Tool effects at other budgets are not identified. | [ASSUMP] |

---

## 3. Randomisation and recording specification [FUTURE]

### 3.1 Population and sampling
- **Development bases only.** Eligible: the 48 declared bases, minus any the owner or auditor exclude (open question Q1).
  - 46 have historical verified outcomes [HIST].
  - One transfer base was used by a SCRIPTED_MOCK smoke [HIST]. Whether it may be used is open question Q1.
  - Generator groups among the 46: hdb-v1 34, walkrec-m1 8, hand 4 [HIST].
- **Faults:** the 9 single-mechanism development families. Compositions and held-out families are excluded from the primary
  matrix. The sealed test split is not touched.
- **Instance draw:**
  - per base, m instances, drawn from the physics-eligible pool with a declared `seed_block`;
  - stratified so that each family appears on approximately G·m/9 bases, with distinct families within a base wherever
    possible, and severity balanced in bins;
  - eligibility (physics only) is fixed before any repair run.
- **Historical HDB outcomes** are not used as memory content, features or training labels. They are policy-selected [HIST].

### 3.2 Treatment assignment
- **Recommended: full matrix.** Every feasible tool of the 10 is assigned to every instance [FUTURE]. The 10 tools are
  posture, timing, feedback, stride, placement, foot_length, torso_mass, torque_limit, foot_friction and leg_length
  (`creature_forge/fault_bench.py`) [HIST].
  - Propensity is 1 per feasible tool, so no inverse weighting is needed.
  - Any future policy can be evaluated exactly, and Γ is estimable.
- **Alternative: K-subset** [FUTURE]. π0's tool plus K−1 others drawn uniformly without replacement from the feasible
  remainder.
  - The propensity is (K−1)/(|A(x)|−1) for each non-π0 tool and is logged.
  - Off-policy evaluation needs inverse-propensity or doubly-robust estimators, which inflate variance [ASSUMP: about
    1.5–2.5× for policies that often disagree with π0].
  - Γ is not identifiable.
- **Cost-matched fallback cell** [FUTURE]. One extra cell per instance: π0's tool with the plant budget increased by the
  plant cost of the interventional panel. It makes the diagnostic-cost comparison in H3 a measurement rather than an
  assumption.
- **Order:**
  - cells run in a seeded random permutation across instances and tools, randomly allocated to workers;
  - no cell reads another cell's state;
  - order effects are tested by regressing Y and cost on execution position and worker. They are expected to be null for
    deterministic cells; a non-null result is a defect.
- **Technical replicates:**
  - a pre-drawn random subset of instances, stratified by base, gets every tool repeated with a fresh optimizer seed;
  - replicates are never counted as robots;
  - they estimate the flip rate f = P(Y_rep1 ≠ Y_rep2 | x, a).

### 3.3 Budgets and seeds
- **Budgets:** one declared plant budget and one twin budget per cell, identical across tools (open question Q4). The
  previous P0.5 assumed 300 plant and 600 twin [ASSUMP]. The diagnosis prefix has its own declared budget, the same for
  every instance.
- **Seed namespaces (`seed_block` ≥ 100000, roles disjoint):**

  | role | scope |
  |---|---|
  | instance draw | — |
  | assignment and order | — |
  | prefix | per instance |
  | optimizer | per (instance, tool, replicate) |
  | twin and screen | per (instance, tool, replicate) |
  | validation | per instance, shared across that instance's tools |
  | confirmation | per instance, shared across that instance's tools |

- **Warm start:** none from any other cell, from the memory, or from historical records. Every cell's optimizer starts from
  the snapshot design under the shared posterior, and the initial mean hash is recorded per cell.

### 3.4 Run controls
The runner is fail-closed:
- a `--max-rollouts` ceiling and a separate dollar ceiling, with the VM stopped via the control plane;
- an exposure check (every cell runs its full repair budget or records ERROR);
- intention to treat (ERROR cells are reported and never dropped or re-run silently);
- ERROR, FAIL and POOR kept distinct;
- before any run, a sentinel reproduces one stored A1e6 episode exactly;
- `--harness-commit` must equal HEAD of a clean tree.

---

## 4. Dataset and schema contract [FUTURE]

### 4.1 Column groups
Each column belongs to exactly one group, and feature extraction is allow-listed **by group**, not by token matching. The
P0 token whitelist produced a false positive (`q:clock_fault`) [HIST].

| group | may enter decision features? | contents |
|---|---|---|
| `DECISION_LEGAL` | yes | nominal design vector; standard observation; panel responses (raw); nominal-twin predictions and residuals (measured − predicted) per panel experiment; engine v6 posterior and its tool ranking (flagged `imitation_risk`); prefix rollout counts |
| `TRUTH` | **never** | fault family, severity, injected parameters, faulty body/MJCF, instance-id tokens, base id, generator group (the last two are used only for folds and strata) |
| `ASSIGNMENT` | never | tool, feasibility and reason, propensity, assignment seed, order index, worker id, replicate index, cost-matched flag |
| `OUTCOME` | never for the same instance; for training-fold instances only through the declared memory | status, FULL, verdict, per-seed validation and confirmation rows, final design hash, repair trace, rollouts used, walking-proxy outcome (recorded separately and labelled PROXY) |
| `PROVENANCE` | never | source commit, harness version, simulator/numpy/Python versions, CPU and thread settings, snapshot hash, seed-block ids, start/end timestamps, VM id, ledger rows |

### 4.2 Record types (JSONL; one schema version; append-only)

1. **`prefix`** (one per instance):
   - opaque `cell_group_id` (a salted hash; the instance id is held in `TRUTH`);
   - `DECISION_LEGAL` block, `TRUTH` block, snapshot hash, prefix seeds, prefix plant/twin rollouts, provenance.
2. **`cell`** (one per instance × tool × replicate):
   - `cell_id`, `cell_group_id`, `ASSIGNMENT` block, budgets allocated and used, optimizer seed;
   - initial-mean hash (it must equal the snapshot's);
   - repair trace (per generation: best score, candidates, plant/twin rollouts), final design;
   - `OUTCOME` block with **per-seed** verification rows (seed, walking, distance, falls, stage), status, ERROR detail,
     wall seconds, provenance.
3. **`ledger`**: per VM session, from control-plane start/stop timestamps and the billing export. Arithmetic estimates are
   not accepted as cost records.
4. **`manifest`**: the sha256 of every record file, the analysis script and the frozen config, written before analysis.

**Fail-closed validation before analysis:**
- every assigned cell is present;
- every cell's snapshot hash equals its prefix's;
- validation seed blocks are identical within an instance;
- no `TRUTH` or `OUTCOME` column is reachable from the feature builder (a test injects a canary column into each forbidden
  group).

---

## 5. Controls and leakage threat model [FUTURE unless marked]

| threat | vector | control | test |
|---|---|---|---|
| Fault identity in ids | instance id encodes family and severity (`base:family:k`) [HIST] | opaque ids; `TRUTH` group | canary column must not change any prediction |
| Fault-injected morphology | the faulty body differs from the nominal; on the causal-engineer bench it leaked the fault (80/80 body faults) [HIST] | features from the nominal design only | feature-input design hash = nominal design hash |
| Post-decision observations | repair trace, repair-phase plant rollouts, verification rows | `OUTCOME` group; same-instance use forbidden | static check plus canary |
| Outcome-derived features | per-base success rates, best-tool labels, standardisation or k fitted on the full data | everything fitted inside the training fold, with nested inner LOBO | fold audit log |
| Base similarity and fingerprinting | the nominal morphology acted as base identity on the proxy tier [HIST] | LOBO primary; near-duplicate bases merged into one group | H4: leave-one-instance-out (LOIO) vs LOBO gap |
| Generator-family similarity | three generator groups [HIST] | LOGO secondary (hand has only 4 bases) | reported, not gated |
| Historical policy imitation | the engine ranking in features; historical HDB labels | historical labels are never used; engine-ranking ablation | H4 imitation control |
| Optimizer warm start | memory or other cells seeding the optimizer | prohibited; initial-mean hash per cell | hash check |
| Optimizer stochasticity read as tool effect | single draw per cell; in DS-1 the same tool was FULL and PARTIAL across arms [HIST] | technical replicates; noise-corrected estimands | flip rate f; replicate-split Γ |
| Diagnostic-policy effect | adaptive experiments differ per episode [HIST] | standardised non-adaptive prefix shared by all cells | snapshot hash |
| Seed reuse | validation seeds used in screening | disjoint namespaces | seed-overlap assertion |
| Analyst degrees of freedom | choosing metrics or representations after seeing data | hash-pinned analysis script and config before data; a single confirmatory run; everything reported | manifest |
| Pilot peeking | tool-effect estimates in the pilot steering the design | the pilot reports nuisance parameters only (§6.3) | the pilot report schema contains no tool-specific or policy-contrast fields |
| Sealed or test data | globbing archive directories ([HIST] incident, 2026-10-22) | the harness reads only the declared development manifest; path allow-list | test: any path outside the manifest raises an error |
| Proxy substituted for FULL | the proxy-learned ranking lost on FULL (18 vs 23 of 40) [HIST] | FULL_VERIFIED is the only primary outcome; proxy recorded and labelled separately | proxy–FULL agreement reported as a secondary measurement |

---

## 6. Pilot and sample-size decision

### 6.1 Critique of the previous P0.5 numbers

**12 instances on 12 bases × 4 tools, plus 6 replicates (pilot):**
- With m = 1 per base, the pilot **cannot separate base from instance variance**.
- 6 replicate cells give a flip-rate interval roughly [0, 0.4] [ASSUMP: Wilson interval].
- The 4-tool subset cannot estimate the headroom Γ.
- The "informative rate ≥ 25 %" gate is not robust to noise. If every tool had the same Q = 0.3, optimizer noise alone would
  make 75 % of 4-tool instances "informative" (§6.2 D) [ASSUMP: independent draws]. So the D2 count of informative
  instances can be met with zero true tool effect.

**120 instances on ≥ 40 bases × 4 tools (campaign):** sized from HDB level P's 31 % informative rate [HIST]. That rate is
policy-selected and not noise-corrected, so it is not a valid basis for sizing.
- At m = 3, q = 0.15 and ρ = 0.2, a learned-policy contrast has a minimum detectable effect of about 0.13 *before* the
  inverse-weighting penalty of the 4-tool subset.

**Dollar figures:** every one ($0.65 and $6–15) is an extrapolation from W3/DS-1 throughput with an assumed 1,000
rollout-equivalents per cell [ASSUMP]. **They are unverified.**

### 6.2 Precision and power (from `p05_precision.py`)

**Model** [ASSUMP]:
- paired per-instance difference d ∈ {−1, 0, 1} between two policies;
- discordance q = P(d ≠ 0), so Var(d) = q − δ²;
- base design effect 1 + (m−1)ρ;
- learning-variance inflation 1.0–1.5 for policies cross-fitted inside LOBO;
- G bases × m instances per base.

**Sensitivity anchors:**
- q = 0.15 is the historical discordance between `interv` and `obs_morph` on the causal-engineer proxy (LOBO) [HIST]
  (0.18–0.24 for either against π0);
- q is varied over 0.10–0.25 [ASSUMP];
- ρ over 0–0.5 [ASSUMP], because no historical estimate exists.

**A. 90 % CI half-width for δ = 0, inflation 1.5 (selected cells):**

| q | ρ | 12×2 | 24×2 | 36×2 | 46×2 | 46×3 |
|---|---|---|---|---|---|---|
| 0.10 | 0.2 | 0.142 | 0.101 | 0.082 | 0.073 | 0.064 |
| 0.15 | 0.2 | 0.174 | 0.123 | 0.101 | 0.089 | 0.079 |
| 0.15 | 0.5 | 0.195 | 0.138 | 0.113 | 0.100 | 0.094 |
| 0.25 | 0.2 | 0.225 | 0.159 | 0.130 | 0.115 | 0.101 |

**B. Minimum detectable effect** (one-sided α = 0.05, power 0.80, inflation 1.5):

| q | ρ | 36×2 | 46×2 | 46×3 |
|---|---|---|---|---|
| 0.10 | 0.2 | 0.116 | 0.104 | 0.093 |
| 0.15 | 0.2 | 0.142 | 0.127 | 0.114 |
| 0.15 | 0.5 | 0.156 | 0.140 | 0.133 |
| 0.25 | 0.2 | 0.183 | 0.164 | 0.147 |

**C. Independent bases needed to detect δ** (power 0.80, inflation 1.5, m = 2, ρ = 0.2):

| δ | q = 0.10 | q = 0.15 | q = 0.25 |
|---|---|---|---|
| 0.15 | 20 | 32 | 57 |
| 0.10 | 51 | 78 | 134 |
| 0.05 | 218 | 329 | 551 |

**D. Spurious "informative" rate from optimizer noise alone** (all K tools share the same Q = p):

| p | K = 2 | K = 4 | K = 10 |
|---|---|---|---|
| 0.1 | 0.18 | 0.34 | 0.65 |
| 0.3 | 0.42 | 0.75 | 0.97 |

**Consequences (each rests on the stated assumptions):**
1. **The binding constraint is independent bases, not rows.** With ≤ 46–48 development bases, the bench can detect only
   policy effects of about **0.10–0.15** decision value. An effect of 0.05 needs hundreds of bases. Increasing m beyond 3
   helps little once ρ ≥ 0.2.
2. A null result can only be read as "no effect ≥ the MDE", or as equivalence within the margin when the CI permits it.
   - **Historical reference:** the proxy-tier interventional contrast was −0.006 [HIST]. A true effect of that size is
     undetectable here.
3. **More bases** require an owner and auditor decision: generating fresh development bases with the frozen generator under
   a new, disjoint id range (open question Q1). This changes the split definition. It is not proposed as a default.

### 6.3 Minimum pilot (P0.5a) [FUTURE]

**Design:**
- 8 bases × 2 instances, with distinct families within a base, stratified across generator groups;
- full matrix of feasible tools: ≤ 160 cells;
- replicates: all tools on 4 instances (≤ 40 replicate cells, 4 bases);
- 16 cost-matched π0 cells;
- 3 sentinel re-runs.

**What it measures, and only this** (nuisance parameters):

| quantity | why |
|---|---|
| plant, twin and wall cost per cell, by tool; billed VM cost | cost validation |
| exposure and ERROR rate; determinism | runner validity |
| flip rate f (40 pairs: if f = 0.15, the 90 % CI is about [0.08, 0.27] [ASSUMP]) | optimizer stochasticity |
| noise-corrected between-tool variance: Var_a(Y) within instance minus the replicate component | is there any tool effect at all |
| replicate-split headroom Γ, reported only as an interval | is tool choice worth learning |
| crude ICC ρ from 8 bases × 2 (its interval will be wide [ASSUMP]; the campaign is sized from its upper bound) | base heterogeneity |
| feasibility rate per tool | action-set definition |

**Blinding:** the pilot report has no tool-specific success rates and no policy contrasts. The auditor may hold them. If the
protocol is unchanged after the pilot, pilot instances join the confirmatory data (an internal pilot). If it changes, they
stay exploratory.

**Why this is the smallest useful pilot:**
- m = 2 is the minimum for any base-versus-instance split;
- the full matrix is the minimum for Γ and for the noise-corrected tool variance;
- 40 replicate pairs is the smallest count giving a flip-rate interval narrower than about ±0.1 around plausible values
  [ASSUMP].
- A 12 × 2 pilot (≤ 240 + 60 + 24 cells) is the better option if Stage 0 shows the cost fits.

**Useful even if nothing disagrees:**
- If Γ's upper 90 % bound is < 0.05 and the noise-corrected tool variance is about 0, that is itself a finding [FUTURE]:
  under this bench, tool set and budget, the repair-tool choice is not the bottleneck, and no tool-selection memory can
  help.
- Cost, noise and feasibility parameters, and the validated runner, remain reusable for other decision points (experiment
  selection, budget or stop decisions; open question Q8).

### 6.4 Pre-declared pilot outcomes [FUTURE]

| outcome | condition (any one triggers it) |
|---|---|
| **STOP** (report, no campaign) | sentinel not bit-identical; > 5 % ERROR cells; any determinism failure; a leakage canary fails; measured cost per cell > 3× the Stage-0 measurement; replicate-split Γ upper 90 % bound < 0.05 |
| **REDESIGN** (new proposal) | f ≥ half the observed between-tool discordance, so tool effects are swamped by optimizer noise (would need more replicates or a larger budget); feasibility < 5 tools on median; the bases needed for half-width ≤ 0.10 at the pilot's upper-bound ρ exceed the eligible bases (see Q1); projected campaign cost exceeds the approved cap |
| **EXPAND** (request campaign approval) | none of the above, and the projected campaign gives a 90 % half-width ≤ 0.10 on the primary contrast within the approved cap |

### 6.5 Campaign (P0.5b), sized after the pilot [FUTURE]

- **Size:** G·m = (z_α + z_β)² · (q̂ − δ²) · (1 + (m−1)ρ̂_upper) · 1.5 / δ², with δ = the owner's smallest effect of
  interest (Q2) and q̂ and ρ̂ from the pilot.
- **Provisional envelope:** all eligible development bases × 2 instances, full matrix (about 92 instances, about 920 cells),
  plus 10 % replicates and the cost-matched cells.
- **Precision:** this gives a 90 % half-width of about 0.09 and an MDE of about 0.13 at q = 0.15 and ρ = 0.2 [ASSUMP].

### 6.6 Cost validation and sensitivity

**Validation sequence:**
1. **Stage 0** [FUTURE; needs separate authorisation of local MuJoCo runs; no cloud spend]: the sentinel plus one development
   instance × all tools, run locally. It measures rollouts per cell and wall-seconds per rollout, by tool.
2. **Pilot costs** [FUTURE] come from control-plane timestamps and the provider billing export, reconciled with the ledger
   (they must agree within 10 %, otherwise STOP).
3. **Campaign projection** [FUTURE] = (measured per-cell cost distribution by tool × planned cells) at its 90 % upper bound,
   plus a 25 % reserve.

**Pilot design (16 prefixes, 216 cells) in USD**, assuming 1,600 rollout-eq per prefix [ASSUMP]:

| rollout-eq per cell [ASSUMP] | $0.009 / 1k | $0.02 / 1k | $0.05 / 1k |
|---|---|---|---|
| 600 | 1.40 | 3.10 | 7.76 |
| 1,000 | 2.17 | 4.83 | 12.08 |
| 2,000 | 4.12 | 9.15 | 22.88 |
| 4,000 | 8.01 | 17.79 | 44.48 |

**Campaign 46 × 2 full matrix in USD:**

| rollout-eq per cell [ASSUMP] | $0.009 / 1k | $0.02 / 1k |
|---|---|---|
| 600 | 7.29 | 16.19 |
| 1,000 | 11.26 | 25.02 |
| 2,000 | 21.20 | 47.10 |

**Rate basis:** $0.009 / 1k is the W3 main-VM throughput rate [HIST, measured for a different workload]; the other rates are
[ASSUMP].

**Budget position** [HIST, owner to confirm]:
- the infrastructure ledger was $89.405 against the $96 cap, leaving **$6.595**;
- the real cloud credit was last estimated at about $16 on 2026-10-20.
- The pilot fits the remaining cap only under the cheaper assumptions. It needs a hard dollar stop below the remaining cap.

### 6.7 Budget-cap decision (separate approval) [FUTURE]

**Do not raise the cap with the pilot approval.** If the campaign projection from §6.6 step 3 exceeds the remaining cap, the
owner receives a separate cap request. It states the measured per-cell cost, the projected total at its 90 % upper bound,
the reserve, the confirmed real credit balance and the precision bought.

---

## 7. Pre-registered competing hypotheses [FUTURE]

**Common to every hypothesis:**
- **Outcome:** FULL_VERIFIED.
- **Folds:** outer LOBO (primary), with LOGO and LOFO (leave one fault family out) as secondaries; standardisation, k and
  hyperparameters chosen by inner LOBO.
- **Learners:** each representation gets the **same** learner families and the same tuning grid: kNN retrieval with
  k ∈ {1, 3, 5, 9, 15, 25}, and per-tool L2-logistic models.
- **Uncertainty:**
  - primary: base-cluster bootstrap of per-instance LOBO differences (2,000 resamples, fixed seed);
  - sensitivity: a cluster-robust t interval with G−1 degrees of freedom, and a 200-resample refit bootstrap that reruns
    the whole pipeline;
  - the narrowest of these is never selected after the fact.
- **No representation is pre-selected from the proxy results:**
  - The H1 representation is the one P0 declared before its own analysis.
  - H2's residual representation and the proxy's `cf_only` signal are exploratory leads [HIST], so H2 is secondary.
- **Margin:** m = the owner's smallest effect of practical interest (Q2). Suggested m = 0.10, because §6.2 shows smaller
  margins are not resolvable.

| | hypothesis | primary estimand | strong control | falsification condition | uncertainty |
|---|---|---|---|---|---|
| **H0** | Observational features already contain all practically useful transfer information. | Δ_comb = V(π_comb) − V(π_obs). π_comb uses observation + raw responses + residuals + nominal design; π_obs uses observation + nominal design; same learner and tuning budget. | an obs-only model with the same capacity and tuning budget as π_comb, plus the engine-posterior baseline (B5) | **Falsified** if the one-sided 95 % lower bound of Δ_comb > 0 and the point estimate ≥ m. **Supported** (practical equivalence) if the 90 % CI ⊂ (−m, m). Otherwise inconclusive. | cluster bootstrap; TOST through the 90 % CI |
| **H1** | Intervention-response features add conditional decision value beyond observational similarity. | Δ_int = V(π_obs+raw) − V(π_obs): the P0-declared `interv` representation, raw panel responses added to observation + nominal design | the same learner on observation plus a **cost-matched observational extra** (π0 with the panel's plant cost reallocated to repair: the cost-matched cell), and shuffled-memory π_obs+raw | **Falsified** if the 90 % CI upper bound ≤ 0, or the CI ⊂ (−m, m) (no practical value). **Supported** if the one-sided 95 % lower bound > 0. **Primary confirmatory test, α = 0.05.** | cluster bootstrap; LOGO and LOFO reported as robustness, not as rescue |
| **H2** | Nominal-twin-relative responses transfer better than raw cross-robot responses. | Δ_res = V(π_obs+res) − V(π_obs+raw), under **LOGO** (cross-generator transport); LOBO secondary | the same panel, learner and tuning, differing only in the response coding; plus the no-memory engine posterior (which already uses the twin comparison) | **Falsified** if the 90 % CI upper bound ≤ 0, or if V(π_obs+res) ≤ V(B5) with CI (memory adds nothing over the in-instance model) | cluster bootstrap; Holm-adjusted with H3 |
| **H3** | Uncertainty-aware abstention improves verified decision utility after diagnostic and repair costs. | Δ_U = U(π_M ⊕ π0 at coverage 0.5) − U(random gate at coverage 0.5), with fallback π0 and λ from Q3. π_M is the pre-declared H1 policy; the gate is its predicted benefit, with thresholds fitted on the training fold. | a random gate at matched coverage; a similarity gate; the cost-matched π0 cell; the full risk–coverage curve at 0.3 / 0.5 / 0.7 | **Falsified** if the 90 % CI of Δ_U includes or lies below 0, or if p₋ is not lower than under the random gate | cluster bootstrap; λ sensitivity ×0.5 / ×2 reported, not chosen |
| **H4** | Apparent memory gains are explained by optimizer warm starts, source or base similarity, feature leakage or historical-policy imitation. | the fraction of the memory gain explained by each control: R_c = (V(π_c) − V(π0)) / (V(π_M) − V(π0)) | (i) shuffled memory, 20 permutations within fold with k fixed; (ii) a base-fingerprint check, LOIO − LOBO gap; (iii) imitation: the engine ranking alone vs π_M with the engine-ranking features removed; (iv) leakage canaries; (v) warm start: excluded by design, since memory never touches the optimizer in P0.5; testable only prospectively (P2) against a generic warm start (the training-fold mean solution per tool) | **H4 supported** (gain is an artefact) if any R_c ≥ 0.5 with a CI excluding 0.25, or a canary changes predictions. **H4 falsified** if shuffled R ≤ 0.25 *and* the gain over every control has a one-sided 95 % lower bound > 0 under LOBO. | permutation distribution; cluster bootstrap |

**Rules for claims:**
- H4's controls are validity gates: if H4 is supported, no H1–H3 claim is made.
- Every hypothesis result is reported whether or not it is significant.
- Proxy-outcome replications are labelled PROXY and never enter a decision.

---

## 8. Benchmark comparisons [FUTURE]

**Common rules:**
- Every method is evaluated on the same FULL_VERIFIED matrix with the same folds.
- Diagnostic cost is charged in U by what each method's features require: observation only, or observation + panel.
- Abstention variants are compared with the same fallback π0 at matched coverage.

| id | method | features | role |
|---|---|---|---|
| B0 | π0: engine v6 top tool from the prefix posterior | posterior (prefix) | no-memory fallback |
| B0a | prior: training-fold best-on-average tool | none | no-memory |
| B0b | uniform random feasible tool (exact expectation from the matrix) | none | floor |
| B1 | observational retrieval / model | observation + nominal design | H0, H1 comparator |
| B2 | interventional retrieval (raw responses) | B1 + raw panel | H1 |
| B3 | residual retrieval | B1 + nominal-twin residuals | H2 |
| B4 | combined observation/intervention model | B1 + raw + residuals | H0 |
| B5 | belief-model diagnostic baseline: engine posterior + learned tool head (no case memory) | posterior | strong model-based baseline for H0/H2 |
| B6 | shuffled-memory versions of B1–B4 | as the original, with outcome labels permuted within fold | H4 |
| B7 | generic warm start (training-fold mean solution per tool) | — | specified for P2 only; not in P0.5 |
| B8 | cost-matched π0 (extra plant budget equal to the panel cost) | posterior | matched diagnostic cost (H1, H3) |
| B9 | replicate-split oracle | outcomes | headroom Γ (upper bound, never a method) |
| G1–G3 | predicted-benefit, similarity and random gates over B2 (and over B1, B3) | — | H3 at matched coverage |

**Outcome tiers:**
- Every reported metric carries its tier. FULL_VERIFIED is primary.
- The walking-proxy result per cell is recorded and reported only as proxy–FULL agreement.
- Historical proxy-tier numbers [HIST] are cited as exploratory and never pooled.

---

## 9. Falsification and stopping rules (summary) [FUTURE]

1. **Stage 0 and the pilot:** §6.4 STOP / REDESIGN / EXPAND, applied mechanically.
2. **Headroom gate before any memory analysis:** if the campaign's replicate-split Γ has a 90 % upper bound < m, report "no
   tool-choice headroom". Hypotheses H1–H3 are then reported as untestable at this effect size, not as failed.
3. **Validity gate:** if any leakage canary fails or H4 is supported, no memory claim is made.
4. **Primary:** H1 at α = 0.05, one-sided. Secondaries H2 and H3 are Holm-adjusted. H0 is read from the same CI by
   equivalence.
5. **No rescue:** no change of folds, learners, margins, λ or representations after unblinding. Additional analyses are
   labelled exploratory.
6. **Spend:** the hard rollout and dollar ceilings stop the run, and the partial data are reported as intention to treat.

---

## 10. Approval checklist (each a separate decision)

- [ ] **A0.** Accept the DS-1 corrections (§1.3, §12) for later edits to the report and handoff (one commit on the V2
  branch, when authorised).
- [ ] **A1.** Approve the estimands, the four-stage separation and the identification assumptions (§2).
- [ ] **A2.** Choose full matrix or K-subset (§3.2); approve the cost-matched π0 cell.
- [ ] **A3.** Fix the eligible base list, families, budget level B and the prefix definition (Q1, Q4, Q5).
- [ ] **A4.** Approve the schema contract and the leakage controls (§4, §5).
- [ ] **A5.** Approve hypotheses H0–H4, margin m, λ and multiplicity (§7; Q2, Q3).
- [ ] **A6.** Authorise *implementation* of the harness and its tests (no simulation runs). Separate approval.
- [ ] **A7.** Authorise Stage 0: local MuJoCo, no cloud spend. Separate approval.
- [ ] **A8.** Authorise the pilot, with an explicit dollar and rollout ceiling inside the existing cap. Separate approval.
- [ ] **A9.** Budget cap: increase or not (§6.7). Separate approval after the pilot.
- [ ] **A10.** Authorise the campaign, sized by §6.5 from the pilot. Separate approval.
- [ ] **A11.** Approve the confirmatory analysis run at a frozen, hash-pinned commit, and who runs it (Q9).

None of A0–A11 is requested as granted by this document.

## 11. Open questions for the owner or auditor

| # | question |
|---|---|
| Q1 | **Bases.** Which of the 48 development bases are eligible? This includes the transfer base used by the SCRIPTED_MOCK smoke, and the 2 with no historical outcome. May fresh development bases be generated by the frozen generator under a disjoint id range to exceed about 46? This changes the split and is not a default. |
| Q2 | **Smallest effect of interest m.** §6.2 suggests that m < 0.10 cannot be resolved on this bench. |
| Q3 | **Cost weight λ and C_ref.** Are only plant rollouts costed? |
| Q4 | **Repair budget per cell** (plant and twin). Is one budget level enough, given that tool effects are budget-specific (I8)? |
| Q5 | **Prefix definition.** Which identifiability-panel experiments, and at what plant cost? Is the engine's adaptive diagnosis excluded from π0, as proposed? |
| Q6 | **Pilot type.** A blinded internal pilot (instances reused) or an external one (pilot bases consumed)? |
| Q7 | **Confirmation stage.** Is the `full_recovery_v1` confirmation stage run for every cell (cost), or only for validation-PASS cells, as the verifier defines? |
| Q8 | If headroom Γ ≈ 0, should memory research move to other decision points (experiment selection, budget allocation, stopping)? |
| Q9 | **Analysis.** Does the auditor run the confirmatory analysis from the hash-pinned script, or verify it? |
| Q10 | **Credit balance.** Confirmation of the real cloud credit and of which VM (main or batch) runs the work; cross-VM determinism must be shown if both are used. |
| Q11 | **Walker-file exposure.** Should the schema-level exposure of 250 rows (2026-10-22 incident) be logged formally against the sealed split before any sealed-test use? |

## 12. Proposed corrections to the current P0 report and handoff (not edited)

| # | location | correction |
|---|---|---|
| C1 | Handoff §6.1, "Where they land in P0" | Replace it with the §1.3 wording: 18 / 2 / 0 within DS-1 candidate rows; 27 as an *expanded-corpus overlap* (9 via MKV K0n or Stage-2 LIVE arms, 3 of them at v5); zero controlled comparisons. |
| C2 | Handoff §6.1, the 21 differing | Add the decomposition: 13 `diverse` only, 4 `engine_old` only, 4 both. Of the 8 `engine_old`, 6 differ only by pooling v2 with v4. The `stopcal` "one arm" grouping is an artefact of a re-verification file. |
| C3 | Handoff §6.1, the 194 multi-tool instances | "31 are level P" → "31 overlap an expanded-corpus level-P comparison". |
| C4 | Report §2.4 row label and handoff §10 item 4 | Level P is "same engine version, pooled across arms and harnesses, including LIVE Nemotron, A2, MKV K0n and stream frozen/updating; 21 of 124 instances are stop-rule variants of one engine arm only". The `arm` field alone does not identify a condition. |
| C5 | Report §8 (P0.5 proposal) | Mark it superseded by this review. The 12 × 4 / 120 × 4 sizes and all dollar figures are unverified extrapolations. The D2 informative-instance count is not robust to noise, so a noise-corrected between-tool variance and the headroom Γ should replace it. |
| C6 | Report §0 recommendation | Add the checkpoint outcome: "Auditor decision `CF-V2-P0-2026-10-22`: REDESIGN; P0 conditionally accepted as an identifiability audit; repair-memory hypothesis not validated." |
| C7 | Report §2.4, the text under the table | Add: "In DS-1, the same tool was FULL under one stop rule and PARTIAL under another for one instance (`weak-slippery:payload_offset:1`, torso_mass). Within-tool procedural and optimizer variation is of the same order as the between-tool differences recorded." |
| C8 | Handoff §10 | Add a new uncertainty: optimizer stochasticity was never measured, so recorded "informative" instances may be noise-generated (§6.2 D). |

---
*End of proposal. No pilot, harness, research-phase change or paid resource has been started. Awaiting owner approval and
external scientific audit.*
