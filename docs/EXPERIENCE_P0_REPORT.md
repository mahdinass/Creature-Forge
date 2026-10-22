# Experience-learning P0 report: offline identifiability and decision-signal audit

- **Date:** 2026-10-22.
- **Branch:** `feature/experience-learning`, worktree `cf-experience`, based on `v1.0.0-rc1` (`3a740a7`).
- **Protocol:** `docs/plans/EXPERIENCE_LEARNING_PLAN.md`, revision 2, committed as `85aef4f` **before any Phase-3 model or
  metric**.
- **Code and generated outputs:** `8aa3a16`; generated tables in `experiments/causal_engineer/dev/experience_p0/`.
- **Scope:** development evidence only. No MuJoCo simulation, no Nebius spend, no model calls and no sealed or held-out data
  were used. V1, `release/v1` and the submission materials are untouched.

## Errata (2026-10-22, evidence review before publication; conclusions unchanged)
- **E1.** The single level-S instance was mislabelled "TA-1 L4, PARTIAL in both arms".
  - It is **TA-1 L1**, `hdb-v1-gen-0073:low_ground_friction:2`: control `posture`, treatment `placement`, both
    NOT_RECOVERED (`experiments/ta1/phase1b_2026-10-20/ta1_phase1b.jsonl` lines 1–2).
  - TA-1 L4 has one resolved tool (`leg_length`) in both arms, so it is not a multi-tool instance.
  - The count (1 instance, 0 informative) and every gate are unchanged.
- **E2.** The committed `experience_p0/outcomes.csv` leaves `plant_used` / `twin_used` empty for A0 and MKV records, whose
  ledger is stored at record top level. No gate or analysis used these fields.
  `experience_p0/evidence/p0_outcome_rows.csv` carries them.
- **Tool attribution (clarification, not a change).** A row's tool is `has_cases.final_tool`: the tool of the repair step that
  produced the submitted design. Multi-step designs (e.g. friction, then legs) are attributed to the last step.

## 0. Recommendation

**INSUFFICIENT-DATA** (pre-declared rule, plan §4).

1. **HDB has no FULL-verified support meeting D2.** It does not meet even D1 at any comparability level, so the repair-decision
   applicability target **is not identifiable from the historical records**. No FULL counterfactual labels were invented, and
   no FULL transfer predictor was built.
2. **Only the proxy tier meets D1.** That is the older causal-engineer bench, with a complete 10-tool repair matrix, 12 bases
   and a walking-fraction proxy. There, retrieval from other robots beats the no-memory default (π0), and shuffled memory
   loses most of that gain. But the **pre-declared primary contrast is null**: structured interventional retrieval adds no
   decision value over observation + morphology kNN, at −0.006, 90 % CI [−0.052, 0.034]. Interventional features improve the
   probability scores (log loss) but not the decisions. That is the same split between prediction and decision that DS-1's
   R-head showed.
3. **On HDB, cross-robot retrieval of raw interventional fingerprints identifies the fault family poorly** (top-1 0.33). The
   no-memory model-based posterior, which compares each robot with its own nominal twin, reaches 0.93. Memory in belief space
   only recalibrates that posterior.
4. **The conditions in plan §6 for a randomised campaign are met:**
   - the question is not identifiable from logs;
   - repair heterogeneity is clear (on HDB, tools differ in verified outcome on 39 of 124 policy-comparable instances; on the
     proxy, retrieval beats π0);
   - a minimal campaign fits a small budget.

   §8 proposes a minimal randomised multi-repair development campaign. It is **not executed**, and it needs owner approval
   plus a cap decision (§8.4).

Stop here for independent review.

## 1. What changed from the old P0

Revision 1 asked whether memory predicts "the verified repair tool". In HDB that label is the tool a policy chose and then
verified. A model that predicts it learns P(A_hist | x), which partly imitates the old policy. The revised target is
Q(x, a) = P(FULL | do(A = a), x) and the policy benefit Δ = E[Y(π_M) − Y(π0)], with p₊ and p₋ (plan §1). P0 asks the prior
question: do the records identify that target at all?

## 2. Data availability and comparability

### 2.1 Sources and hashes
- 191 registered files: 133 episode files, 5 controlled-intervention files, 1 stop-calibration file, 2 stop-data files, the
  identifiability panel, the causal-engineer probe set, 18 causal-engineer instance builds, 6 superseded partials and
  24 mirrors.
- Every file's SHA-256 and record count is in `experience_p0/INVENTORY.md` and `inventory.json`.

| key source | records | SHA-256 |
|---|---|---|
| `ce3/ce/probe_dev.jsonl` (proxy tier) | 165 | `25cfd983cc32f63809f9561432ecb9d648d48c13f3c24c21ffd46f747da2e62c` |
| `hdb/.../ident_v2_all.jsonl` (standardised panel) | 340 | `a87d6d3794e5a0536249610e94e126d3cdf64ee162f866f3641aaed304bbbf47` |
| `hdb/.../stopcal.jsonl` (re-verified designs) | 668 | `8d3b01c0802f01f5b27081a8ff70ccb2d5043737b55c29340f7128c13f7becf3` |
| `hdb/.../fresh_A1c5.jsonl` | 220 | `3bde2b77676fd3d46592bb9ad50250ecfc8614376d6676b87d59f2a97d2149cb` |
| `hdb/.../s2T_A1e.jsonl` | 36 | `2014fa80f8f333b1b2f8d4ba561da024516fb49b0334ef7a696acbfa535cdf56` |
| `hdb/.../mkv5.jsonl` | 126 | `fd2dd81c847cb34be4071a8262ddf43b1dfbecf1cefc51b6a00ccafc9af65920` |
| `ds1/eval/eval_A1e6_s0.jsonl` (one of 28 DS-1 eval shards) | 5 | `8b7b8bbf191759dd27dd38a4aca9cd632f5f2ddde3b6a377f7975a716c93bcd1` |
| `experiments/ta1/a1_l4_pilot_2026-10-21/ta1_a1_l4.jsonl` | 2 | `c43601b22ccc1940f00786ec64ebd29735b0bd266ef45dc713bf14cecbb2f4e1` |
| `experiments/do1/w3w4_2026-10-21/do1_l4_rep.jsonl` | 11 | `4f9c7295bd771cf26c8dab2a8a1db433ed2f2460dd6e1b3a3340d90571114714` |
| generated `inventory.json` | — | `73fb8553bf8466554bf1009e202af97aa4e292ccca09f947d4608dd8e6153687` |
| generated `analysis.json` | — | `523fcb5ba6e3e45d4090733c900ad6faaaf33bffe5662bc4e9826f72d08b5206` |

Paths starting `hdb/` and `ds1/` are relative to `Creature-Forge/artifacts/vm`, which is git-ignored. `experiments/` paths
are in this repository.

**Not opened by the audit:**
- `walkers_all.jsonl`, which holds test-split walker designs;
- the causal-engineer held-out shards (`cehb/`, `experiments/causal_engineer/heldout/`);
- ledgers, the noise calibration, and the causal-engineer LLM pilot episodes.

**Disclosure:** while locating the archives, before the audit code existed, a schema-profiling pass parsed `walkers_all.jsonl`
row by row. It counted rows and read only the `instance_id`, `arm`, `bench` and verification-presence fields. No design or
outcome content was used, and the audit code never registers the file (a test enforces this).

**Off-split records:** none. Every registered record lies on one of the 48 declared development bases.

**Provenance checks:**
- The standard pre-intervention observation (X0) is identical across all records of each plant: 476 of 476 plants with two or
  more records.
- The nominal body is identical across all records of each base: 46 of 46.
- No near-duplicate morphologies (z < 0.5).
- On the causal-engineer bench, the faulty body equals the nominal base body exactly for controller-only faults (85/85) and
  differs for body faults (80/80). So the fault is **visible in the body** on that bench.
- **One discrepancy:** the archive copy `hdb/artifacts/hdb/ds1/pilot_A1e.jsonl` has 3 records, while the canonical
  `ds1/pilot_A1e.jsonl` has 2. The extra record is `hdb-v1-gen-0040:short_feet:2`, FULL. The canonical copy was used; this
  cannot change any gate.

### 2.2 Outcome hierarchy

| tier | what | rows / instances |
|---|---|---|
| FULL_VERIFIED | `full_recovery_v1` (HDB episodes, harness episodes, stop-calibration re-verifications) | 2,587 rows on 476 plants (hdb_v1 20, hdb_v2 413, hdb_v2_devcomp 43) and 46 bases. 201 MKV rows and 123 stop-calibration rows carry oracle information and are excluded from every comparison. |
| STANDARDIZED_DEV_PROXY | causal-engineer repair matrix: all 10 tools at budget 160, walking on 8 check seeds, "repairs" if ≥ 75 % | 165 instances, 12 bases, 8 fault families; all matrices complete |
| NON_COMPARABLE | in-episode robustness checks (sequential, budget-dependent); HDB v1 vs v2 plants; MKV K1–K4; the stop-data re-measurements (evidence only, labels copied) | not used as outcomes |

### 2.3 Availability matrix (episode corpora)

| corpus | outcomes | pre-intervention observation | diagnostic experiments (order) | tools: selected / alternatives tested | procedure, budget, optimizer config | seeds | outcome / verifier | missing |
|---|---|---|---|---|---|---|---|---|
| Stage 1 (vs2–vs5, fresh A0/A1c5) | 1,120 | X0 observe in 796 engine records; A0 has none | engine v1–v5: median 1 plant experiment (observe); ordered, adaptive | 1 submitted; earlier plant tools appear only as sequential in-episode checks | engine settings; stop rule in 550; A0 different procedure | observe seeds; no optimizer seed | FULL_VERIFIED | commit; per-seed validation; optimizer seeds |
| MKV (v1, v4, v5) | 298 | 251 | as engine | 1 per assigned condition; the tool is a mediator of assigned knowledge | identical pipeline across conditions | — | FULL_VERIFIED; 201 oracle-informed | commit; per-seed validation |
| Stage 2 | 268 | 268 | engine v5, adaptive; Nemotron trace in A3/A4 | 1 submitted | same caps; A2 adds the amortized prior | — | FULL_VERIFIED | commit; per-seed validation |
| DS-1 | 212 | 212 | engine v6: median 5 per episode, adaptive (EIG) | 1 submitted (+ in-episode checks) | v6 settings in 172 | — | FULL_VERIFIED | commit; per-seed validation; optimizer seeds |
| TA-1 | 4 | yes | yes | **assigned tool order** (control vs foot_friction first) | identical, harness-recorded | noise seed recorded | FULL_VERIFIED, per-seed rows | commit |
| DO-1 / W3 / W4 | 17 | yes | yes | assigned **objective**, not tool | identical | recorded | FULL_VERIFIED, per-seed rows | commit |
| Stop calibration | 668 | — | — | many designs per instance from different procedures (initial, counterfactual, twin, repair) | none comparable | — | FULL_VERIFIED re-verification | procedure equality |
| Identifiability panel | — (no repairs) | yes | **standardised, non-adaptive** panel (observe, floor, weigh, catalogue counterfactuals; 23 % of counterfactual cells excluded by design bounds) | — | — | — | — | nominal-twin baseline features |
| Causal-engineer probe set | 165 matrices | yes | **standardised** 9-counterfactual catalogue | **all 10 tools assigned** | budget 160, same train seeds, per-tool noise seed | yes | proxy (check seeds), not the verifier | FULL verification |

### 2.4 Comparable multi-action support

| level (FULL_VERIFIED, HDB) | instances with ≥ 2 tools | bases | informative instances (tool outcomes differ) | informative bases | families on ≥ 2 bases | Kish n_eff (bases) |
|---|---|---|---|---|---|---|
| **S: assigned tool** | **1** (TA-1 L1) [E1] | 1 | **0** | 0 | 0 | 0 |
| P: same engine version, policy-chosen | 124 | 35 | 39 | 22 | 8 | 18.8 |
| — P, engine v4 / v5 / v6 | 39 / 51 / 30 | 12 / 22 / 19 | 9 / 19 / 11 | 6 / 11 / 8 | 2 / 6 / 1 | 4.8 / 9.8 / 6.4 |
| X: cross-procedure | 385 | 46 | 150 | 41 | 12 | 32.4 |
| **Proxy (causal-engineer), assigned** | **165** | 12 | **109** | 12 | 8 | 10.8 |

- **How many instances truly have two or more comparable repair outcomes?**
  - Under the strict definition (same plant, procedure, budget and verifier, tool assigned): **one HDB instance**, with
    identical outcomes (NOT_RECOVERED in both arms) [E1].
  - The 124 level-P instances are policy-chosen, with endogenous remaining budget.
  - The 385 level-X instances mix procedures.
- **Groups:** several rows on one base are never treated as independent robots. Outcomes span 46 bases (Kish n_eff 19.6 by
  outcome rows), in three generator groups: hdb-v1 34, walkrec-m1 8, hand 4.

### 2.5 Adequacy gates (pre-declared D1/D2)

| tier | D1 | D2 |
|---|---|---|
| HDB FULL_VERIFIED level S | no (0 informative) | no |
| HDB FULL_VERIFIED level P | no (policy-chosen never qualifies) | no |
| HDB FULL_VERIFIED level X | no (cross-procedure) | no |
| Causal-engineer proxy | **yes** (12 bases, 109 informative) | no (a proxy never gives a GO) |

## 3. Baselines and evaluation protocol (as declared)

**Comparators on the proxy tier:**
- `prior` (π0: the training-fold most frequent repairing tool);
- `morph` (nominal design);
- `obs_only`;
- `obs_morph` (the `experience_bank` signature: the observation before any intervention);
- `cf_only`;
- `interv` (observation + morphology + responses to the fixed catalogue: structured interventional retrieval);
- leakage probes using the faulty body.

Each block has equal weight, fixed a priori.

**Not evaluable on a decision target:**
- belief-space case attention (`has_cases`) and the amortized posterior exist only on HDB, where no tier meets D1;
- DS-1's offline belief-space case-attention result on level P is cited (§4.4);
- the amortized posterior cannot be re-run offline, because its inputs are differences from nominal-design simulations, so
  only its stored outputs are read.

**Folds:**
- outer: leave-one-base-out (LOBO), leave-one-fault-family-out (LOFO) and leave-one-generator-group-out (LOGO);
- standardisation and π0 fitted on the training fold;
- k from {1, 3, 5, 9, 15, 25} by inner leave-one-base-out log loss.

**Leakage controls:**
- a whitelist rejects id, seed, severity, family, fault, injected-change and outcome tokens (it caught one false positive
  during the run);
- every catalogue response is legal at the decision point, because the catalogue precedes any repair (cost 36 rollouts, on
  top of 4 for the observation).

**Metrics:**
- per-(case, tool) log loss and Brier, with calibration intercept and slope;
- decision value of the top tool on the measured matrix, regret, Δ against π0, and p₊/p₋;
- matched-coverage risk–coverage, with a similarity gate and a predicted-benefit gate;
- base-cluster bootstrap, 2,000 resamples, seed 20261022.

**Controls:**
- 20 shuffled-memory permutations, with k fixed to the real run's;
- hard-negative versus hard-positive neighbours.

## 4. Results

### 4.1 Decision signal on the proxy tier (exploratory: proxy outcome, older bench, 12 bases)

Value is the fraction of instances repaired by the top-1 tool. The oracle best is 0.661, because 109 of 165 instances have
at least one repairing tool.

| LOBO | value | π0 | Δ | p₊ | p₋ | log loss | calib. slope |
|---|---|---|---|---|---|---|---|
| prior (π0) | 0.261 | 0.261 | 0 | 0 | 0 | 0.460 | 0.80 |
| morph | 0.248 | 0.261 | −0.012 | 0.061 | 0.073 | 0.491 | 0.40 |
| obs_only | 0.345 | 0.261 | +0.085 | 0.139 | 0.055 | 0.423 | 0.73 |
| **obs_morph** | **0.333** | 0.261 | +0.073 | 0.158 | 0.085 | 0.441 | 0.69 |
| cf_only | 0.382 | 0.261 | +0.121 | 0.164 | 0.042 | 0.407 | 0.68 |
| **interv** | **0.327** | 0.261 | +0.067 | 0.121 | 0.055 | 0.406 | 0.82 |
| faulty body + obs + cf (leak probe) | 0.388 | 0.261 | +0.127 | 0.170 | 0.042 | 0.407 | 0.87 |

| base-cluster bootstrap | estimate | 90 % CI |
|---|---|---|
| **primary: interv − obs_morph, decision value, LOBO** | **−0.006** | **[−0.052, +0.034]** |
| interv − obs_morph, LOFO / LOGO | +0.024 / −0.049 | [−0.011, +0.064] / [−0.104, +0.007] |
| interv Δ vs π0, LOBO / LOFO / LOGO | +0.067 / +0.055 / +0.036 | [+0.024, +0.110] / [−0.006, +0.119] / [−0.024, +0.092] |
| obs_morph Δ vs π0, LOBO / LOFO / LOGO | +0.073 / +0.030 / +0.085 | [+0.006, +0.146] / [−0.019, +0.086] / [+0.014, +0.153] |
| interv − obs_morph, log loss (lower is better), LOBO / LOFO / LOGO | −0.035 / −0.029 / −0.049 | all CIs exclude 0 |

- **Pre-declared primary contrast: not supported.**
  - The CI includes 0, and the sign flips under LOFO.
  - The shuffle criterion holds: shuffled memory retains only 13 % (interv) and 18 % (obs_morph) of the advantage over π0.
  - So retrieval carries case-specific information, but the interventional catalogue does not improve the *decision* beyond
    the observation.
- **Prediction is not decision.** The interventional features improve log loss and calibration in every scheme while the
  decision value does not move.
- **Exploratory, not pre-declared (hypotheses only):**
  - `cf_only` and `obs_only` do better than the blocks that include morphology in every scheme. With 12 bases, the nominal
    morphology mostly adds base-specific noise.
  - The equal-block weighting fixed a priori may therefore have hidden a counterfactual-only signal (LOBO Δ +0.121). That
    needs fresh data to test; it was not tuned here.
- **Leakage:** the leaky faulty-body variant is the best LOBO method (0.388). The earlier Level C numbers
  (`LEVEL_C_LOBO.md`, top-1 0.59–0.66, faulty-body features) are partly inflated by a fault that is visible on that bench,
  and they are not transportable to hidden damage.
- **Generalisation:** gains over π0 shrink under fault-family holdout. For interv, Δ is +0.055 with a CI including 0. Most
  instances stay unrepaired: regret is 0.33 against an oracle of 0.66.
- **Prior registered evidence on the same bench:** the Level C ranking learned from these proxy matrices then lost to
  exhaustive search on *verified* FULL in the registered held-out run (18 vs 23 of 40; discordant 1 vs 6). Proxy decision
  gains have already failed to transport to FULL once.

### 4.2 Abstention: matched-coverage risk–coverage (LOBO)

| method / gate | coverage 0.3 | 0.5 | 0.7 | 1.0 |
|---|---|---|---|---|
| obs_morph / similarity | 0.248 / 0.042 | 0.261 / 0.067 | 0.291 / 0.073 | 0.333 / 0.085 |
| obs_morph / predicted benefit | 0.285 / 0.024 | **0.333 / 0.042** | 0.327 / 0.085 | 0.333 / 0.085 |
| interv / similarity | 0.261 / 0.030 | 0.267 / 0.042 | 0.303 / 0.042 | 0.327 / 0.054 |
| interv / predicted benefit | 0.303 / 0.018 | **0.333 / 0.042** | 0.327 / 0.054 | 0.327 / 0.054 |

Each cell is the decision value, then the negative-transfer rate p₋ over all cases.

- A **predicted-benefit gate** halves negative transfer (0.085 → 0.042 for obs_morph) at 50 % coverage, with no loss of value.
  A **similarity-only gate** gives lower decision value at every coverage below 1.0. Its negative-transfer rate is not
  uniformly worse: for interv at 0.7 it is 0.042 against 0.054.
- At matched coverage, interventional retrieval is not better than observational retrieval.

**Hard negatives** (105 queries; the observationally nearest case whose best tool fails on the query, against the nearest
whose best tool succeeds):

| representation | pairs separated | 90 % CI |
|---|---|---|
| interv | 0.51 | [0.45, 0.59] |
| obs_morph | 0.47 | [0.41, 0.53] |
| difference | +0.048 | [+0.018, +0.081] |

Both are at about chance (0.5): neither representation tells a misleading near neighbour from a helpful one. The small
difference is not a usable gate.

### 4.3 HDB diagnostic precondition (fault-family prediction; not a decision result)

The data are 302 eligible identifiability instances on 24 bases (Kish n_eff 23.3), with 9 families.

| LOBO | log loss | top-1 | ECE | selective accuracy at 50 % coverage |
|---|---|---|---|---|
| prior | 2.150 | 0.14 | 0.03 | 0.09 |
| obs_morph kNN | 2.181 | 0.29 | 0.04 | 0.34 |
| obs + conditions + morph kNN | 2.102 | 0.32 | 0.08 | 0.43 |
| interv kNN (full panel) | 1.986 | 0.33 | 0.06 | 0.42 |
| belief-space kNN (stored posterior) | 0.365 | 0.93 | 0.03 | 0.99 |
| **model posterior, all instruments (no memory)** | 0.560 | **0.93** | 0.06 | 0.99 |
| model posterior, observe only (no memory) | 0.655 | 0.81 | 0.08 | 0.95 |

- **Interventional fingerprints:** they add information over observation in cross-robot retrieval, at +0.19 mean log p(truth),
  90 % CI [0.08, 0.33]. But they stay far below the no-memory model posterior: interv − posterior is −1.43 [−1.79, −0.99].
  LOGO is similar.
- **Within twin pairs** (sanity check): raw-panel 1-NN separates T2 in 62/100 and T4 in 36/43.
- **Interpretation (hypothesis):**
  - the raw responses are not differenced against each robot's own nominal twin;
  - the model posterior does exactly that comparison;
  - so interventional evidence becomes transportable across robots mainly as **predicted-versus-measured residuals against the
    robot's own nominal twin**;
  - the records do not store those residuals in a standardised form.
- **Belief-space retrieval:** it only recalibrates the posterior (log loss 0.56 → 0.37). It adds no new diagnostic
  information. Shuffled labels push interv kNN to log loss 2.39.
- **Stored amortized-posterior outputs** (A2, 36 transfer instances): top-1 0.31 and mean log p(truth) −1.93, against the
  engine's −1.09 on the same records. The `s2_transfer_A4` records store no amortized output. These are stored outputs and
  were not re-run.

### 4.4 Cited, not re-run (HDB level P, missing not at random)

DS-1 offline (`experiments/causal_engineer/dev/hdb/ds1/offline_report.json`, sha256 `61c9bfd65ce32f10…`) reports expected FULL
of each chooser's pick on the comparable support of 194 instances:

| chooser | expected FULL |
|---|---|
| engine | 89.3 |
| R-head | 85.7 |
| B1 | 83.9 |
| belief-space case attention | 74.4 |
| random | 70.6 |

Case attention is far below the engine's own choices and close to random. As the protocol said, these outcomes are policy-
selected and procedure-confounded.

## 5. Evidence leakage and procedure confounding

| threat | where | status |
|---|---|---|
| Ids, seeds, truth or outcomes in features | all analyses | enforced by `assert_whitelisted` (tested); LOBO prevents same-base retrieval; no near-duplicate morphologies |
| Fault visible in the "morphology" | causal-engineer bench | confirmed (80/80 body faults change the body); a leakage probe shows it raises decision value; nominal morphology used in the declared methods |
| Base fingerprinting via morphology | proxy tier (12 bases) | morphology is one vector per base; adding it hurts retrieval, consistent with acting as base identity rather than signal |
| Policy selection (missing not at random) | HDB levels P/X | decisive: the tool is chosen from the belief and remaining budget; no positivity for unchosen tools; no predictor fitted |
| Procedure and budget confounding | HDB levels P/X, stop calibration | A0 vs engine, engine v1–v6, stop rules, twin/counterfactual/repair designs; second plant tools start from a different budget (e.g. 388 vs 236 plant rollouts within one episode) |
| Adaptive experiment selection | HDB v6 (median 5 experiments, EIG), Nemotron arms | only the first observe is standardised (always first; identical across 476 plants); later experiments are not exchangeable across episodes |
| Oracle information | MKV K1–K4, 123 stop-calibration rows | excluded from every comparison; MKV is a controlled *information* intervention with the tool as mediator |
| Proxy ≠ verifier | causal-engineer bench | check seeds are also the eligibility seeds; budget 160 vs 700; proxy-learned ranking already lost on FULL in a registered run |
| Missing provenance fields | all historical HDB records | no source commit in any record; no per-seed validation (FA-1B defect); no optimizer seeds outside the harness, so technical stochasticity cannot be separated from instance effects |

## 6. Is the decision-relevant applicability target identifiable?

- **On HDB with FULL verification: no.**
  - Δ(x) needs FULL outcomes of the memory policy's and π0's actions on the same plant, under the same procedure.
  - The records contain one such instance, and it carries no outcome difference.
  - The 39 informative level-P instances compare *policies*, not tools, under endogenous budgets.
  - Any applicability label built from them would be a counterfactual invention.
- **On the proxy tier: Δ_proxy(x) is identified** for policies that pick among the 10 assigned tools. The protocol's
  interventional-signal test there is null.
- **Transport of proxy effects to FULL:** not identified, and contradicted once by the registered causal-engineer held-out
  result.

## 7. Negative findings (kept as findings)

1. There is no FULL-verified assigned-tool support on HDB beyond TA-1's single informative-free instance.
2. The pre-declared interventional decision contrast on the proxy tier is null.
3. Interventional features improve proper scores without improving decisions.
4. Hard-negative memory is not detectable by either representation (about chance).
5. Raw interventional fingerprints do not transport fault identity across robots. The in-instance nominal-twin model does.
6. The amortized posterior's stored outputs are weaker than the engine posterior.
7. Belief-space case attention chose worse than the engine on level P (cited).

## 8. Proposal (not executed): a minimal randomised multi-repair development campaign (P0.5)

### 8.1 Objective
Create level-S, FULL_VERIFIED support that meets D2. Then re-run this P0 decision analysis, unchanged and at a frozen commit,
on Q(x, a) for FULL. This identifies tool effects and their heterogeneity across robots and fault families. It does **not**
test whether a memory policy improves recovery prospectively; that is P2.

### 8.2 Design and experimental controls
1. **Population:**
   - development bases only (the 48 declared; ≥ 40 used);
   - the 9 single-mechanism dev families, stratified by family × severity multiple;
   - physics-only eligibility, fixed before any run;
   - compositions excluded from the primary matrix;
   - the sealed test split and the held-out families untouched.
2. **Common pre-intervention state:**
   - one diagnosis prefix per instance by frozen engine v6 (NO_AI): the standard observe, then the standardised, non-adaptive
     identifiability panel;
   - every experiment's predicted-vs-measured residual against the robot's own nominal twin is recorded (the representation
     §4.3 indicates);
   - the engine state is snapshotted, and every repair cell starts from the identical snapshot.
3. **Assigned tools:**
   - K = 4 per instance: the engine's top tool, so π0's outcome is always measured, plus 3 drawn uniformly without
     replacement from the remaining tools that pass a pre-declared feasibility screen (room inside the bounds);
   - the assignment comes from a fixed `seed_block` namespace, and propensities are logged;
   - execution order is randomised;
   - no information flows between cells, and there is no warm start from other cells (generic-warm-start control by design).
4. **Identical procedure per cell:**
   - fixed twin budget (warm-start CMA under the shared posterior) and fixed plant CMA budget;
   - the frozen repair objective (DO-1's objective only as a separately declared factor, never mixed);
   - an independent optimizer seed per cell.
5. **Optimizer stochasticity:** 10 % of cells are repeated with a fresh optimizer seed. These are technical replicates, not
   robots; they give the within-cell outcome variance.
6. **Verification:**
   - the unchanged `full_recovery_v1`;
   - validation and confirmation seeds used once per cell and never for selection;
   - per-seed validation rows and the source commit stored in every record (fixing the gaps in §5).
7. **Fail-closed runner:**
   - `--max-rollouts` ceiling;
   - an exposure check (every cell completes its repair);
   - intention to treat (ERROR cells reported, never dropped);
   - a sentinel that reproduces one stored A1e6 episode exactly before the campaign;
   - VM stopped via the control plane.
8. **Pre-registration before execution:**
   - the D2 recheck;
   - the decision analysis of this report on the FULL tier, with the primary contrast as declared;
   - the nominal-twin-residual representation as the interventional block;
   - the counterfactual-only variant (§4.1) as a declared secondary;
   - grouping by base, family and generator.

### 8.3 Size and staging
- **P0.5a pilot:**
  - 12 instances on 12 bases × 4 tools, plus 6 replicate cells;
  - measures cell cost, the informative rate and the replicate agreement.
  - **Gate:**
    - the sentinel reproduces exactly;
    - every cell is exposed;
    - informative rate ≥ 25 %;
    - measured cost per cell within 1.5× of the estimate.
- **P0.5b:**
  - 120 instances on ≥ 40 bases × 4 tools (480 cells), plus 48 replicate cells;
  - with HDB level P's informative rate (31 % at 2–3 tools) as a floor, 4 assigned tools should give about 40–60 informative
    instances, which is the D2 range. The pilot replaces this assumption.

### 8.4 Expected compute (estimate from recorded runs; no spend authorised)

**Basis:**
- an A1e6 episode uses about 615 plant and 2,519 twin rollouts;
- the W3 throughput was 34,354 rollout-equivalents in 66 min on the 8-vCPU main VM at $0.269/h, which is about $0.009 per
  1,000.

**Assumed sizes:**
- one cell ≈ 600 twin + 300 plant + 96 verification ≈ 1,000 rollout-equivalents;
- one prefix ≈ 60 plant + ≤ 1,500 twin ≈ 1,600.

| stage | rollout-equivalents | main-VM hours | infra cost | inference |
|---|---|---|---|---|
| P0.5a pilot | ≈ 73 k | ≈ 2.4 | ≈ $0.65 | $0 |
| P0.5b campaign | ≈ 720 k (192 k prefixes + 528 k cells) | ≈ 23 (≈ 12 h wall on main + batch) | ≈ $6–7 on the main VM alone; ≈ $10–15 if the batch VM (≈ $2.1/h in Stage 1) carries half | $0 |

**Budget check:**
- the infra ledger was $89.405 after W3/W4, against the $96 cap;
- the pilot fits, but the full campaign does not fit under the current cap with a reserve;
- the real Cloud credit was last estimated at about $16 on 2026-10-20 and must be confirmed by the owner;
- P0.5b therefore needs an explicit owner decision on cap and top-up.

**Each stage needs separate approval.** Nothing here is authorised by this report.

## 9. Reproduce

```
..\Creature-Forge\.venv\Scripts\python.exe scripts\exp_p0_audit.py inventory --vm-root ..\Creature-Forge\artifacts\vm
..\Creature-Forge\.venv\Scripts\python.exe scripts\exp_p0_audit.py analyse   --vm-root ..\Creature-Forge\artifacts\vm
..\Creature-Forge\.venv\Scripts\python.exe -m unittest tests.test_experience_audit
```
- Runtime: about 15 s and about 2 min respectively, locally.
- The test class `RecordedGates` recomputes the gate outcome from the local records. It is skipped where they are absent
  (CI).
