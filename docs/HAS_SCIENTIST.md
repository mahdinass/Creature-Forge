# Hypothesis-as-Simulation (HaS) scientist — specification and execution log (phase 3)

Plan of record (owner-approved 2026-10-18, revision 2): `docs/HAS_PLAN_2026-10-18.md`. This file is the living specification
and log. Branch `feature/has-scientist` (from `feature/causal-engineer` @ `c429329`).

## Diagnosis that motivated the phase (exploratory)
`experiments/causal_engineer/dev/phase3_diagnosis/DIAGNOSIS.md`, produced by `scripts/phase3_diagnosis.py` from frozen held-out
records. Main points:
- **Weak visible evidence.** The old scientist stopped on statistically weak evidence: a 4/4 stress test led to only 51% FULL.
- **Flat budget curve.** Verification hardly depends on optimiser budget.
- **Injected-mechanism association.** Repairs of the injected mechanism are associated with better verification (0.53 vs 0.29).
  This is an association only; the controlled MKV study tests it.
- **Benchmark leaks.** The old bench lets parameter readout and a fault-inverse catalogue stand in for diagnosis.

## Components (status in the log below)

| Module | Role |
|---|---|
| `creature_forge/hidden_plant.py` | Generic deviation DSL (`PRIMITIVES`); plant = nominal design + hidden deviation + reality gap; rollout and pool jobs; hooks for `Workbench` (`observe`, `plant_cma`) and `recovery.assess` (`seed_job`, `verify`). Bit-identical to the existing paths at zero deviation (`tests/test_hidden_plant.py`) |
| `creature_forge/hdb_bench.py` (planned) | Hidden-Damage Bench: mechanism families as DSL generators, severity grid, physics-only eligibility, seeds, strata labels |
| `creature_forge/hdb_workbench.py` (planned) | Workbench subclass on the plant: condition tests, robustness check, twin ledger |
| `creature_forge/belief_engine.py` (planned) | Particles over DSL structures and parameters; paired-seed twin likelihood; EIG; posterior-robust repair; stopping |
| `creature_forge/scientist_has.py` (planned) | Nemotron roles: proposer, experimenter, engineer, consolidator |

## Deviation DSL (v1, `hidden_plant.PRIMITIVES`)

| Stage | Primitive | Targets | Parameters (range) |
|---|---|---|---|
| body | `segment_length` | thigh/shank/foot per side, feet, legs | factor (0.3–2.0) |
| model | `actuator_strength` | joint groups (all, left, right, hips, knees, ankles, each joint) | factor (0.05–2.0) |
| model | `joint_damping` | joint groups | factor (0.1–100) |
| model | `torso_mass` | torso | factor (0.3–4.0) |
| model | `payload` | torso | mass_kg (0–15), x_m (−0.3–0.3) |
| model | `contact_friction` | feet, foot_l, foot_r | factor (0.02–3.0) |
| vector | `gain_scale` | balance_feedback (balance_gain + pitch_kp), placement (fp_kd + fp_kv) | factor (0–1) |
| controller | `sensor_delay` | pitch, joints, all | seconds (0–0.15) |
| controller | `sensor_bias` | pitch, each joint | rad (−0.4–0.4) |
| controller | `clock_scale` | clock | factor (0.4–2.5) |

Rules:
- Out-of-range values are rejected, never clipped.
- The controller keeps the **design's** geometry, torque limit and weight calibration; the plant does not inform it.
- Recorded `tau` is the delivered joint torque: actuator force × gear.

## Literature checked against full text (2026-10-18; Elicit was unavailable)

| Paper | What the full text shows | Consequence here |
|---|---|---|
| Piriyakulkij et al. 2024 (arXiv 2402.06025, NeurIPS) | LLM-proposed rules tracked as weighted particles. The LLM revises only low-likelihood particles; experiments are chosen by information gain. Zendo ablation: InfoGain 6.55, random experiments 5.84, LLM-only experiments 4.72. The authors note the LLM experiment proposer "does not clearly beat random proposals" | A3hx (Nemotron chooses experiments) may well be *worse* than engine EIG; the arm measures it. The proposer is given residuals of poorly fitting hypotheses |
| BED-LLM (arXiv 2508.21184, ICLR 2026) | In-context belief updating is unreliable (GPT-4o "regularly sample[s] hypotheses incompatible with past observations"). Hypotheses are filtered against the whole history by an explicit likelihood. EIG uses a Rao-Blackwellised estimator. Candidates are generated conditioned on the hypothesis pool to split it | Beliefs live in the engine, never in the prompt. Nemotron's experiment candidates may be conditioned on the current pool |
| ModelSMC (arXiv 2602.18266) | Executable simulator programs as particles; LLM revision; weights from a TabPFN-surrogate marginal likelihood. Mixed results: single-particle beats it on SIR, it wins on Hodgkin-Huxley. Expensive | Expect mixed gains from LLM proposals; measure, don't assume |
| Experience-following (Xiong et al., arXiv 2505.16067) | Agents copy similar memories; errors propagate. Add-all memory hurts (e.g. CIC-IoT 71.5 → 59.9). Strict selection helps (85.4). Later outcomes are free quality labels for deletion | Dossiers only from verified dev investigations; outcome-based pruning; a corrupted-dossier probe |

## Execution log
- **2026-10-18 — plan approved; Stage 1 started.**
  - Infra cap `SPEND_CAP_USD` 38 → 72: ledger $33.29 + envelope $35 + accrual. Real Cloud credit is $66.
  - Inference unchanged ($40 cap; ≤ $5 Stage-1 smoke). Real Token Factory credit is $52.
- **2026-10-18 — M0.**
  - Diagnosis script and outputs committed; approved plan copied to `docs/HAS_PLAN_2026-10-18.md`.
  - Elicit was unavailable: every API call returned `api_access_denied`. The literature was reviewed from web and primary pages.
- **2026-10-18 — `hidden_plant.py` and its tests (11 pass, local).**
  - Bit-identity with `physics_probe.rich_rollout`, `creature_walk.rollout` (settle 0 and 0.3), `challenges.seed_job`,
    `cw.eval_job` and `physics_probe.observe`.
  - Every primitive kind has a measured effect.
  - `full_recovery_v1` runs unchanged on the plant through `recovery.assess(job_fn=...)`.
  - Found while testing: MuJoCo `actuator_force` is pre-gear, so the plant trace records delivered torque (exact at gear 1).
- **2026-10-18 — vertical-slice code.**
  - New modules: `hdb_bench.py` (dev families T2/T4), `hdb_workbench.py`, `belief_engine.py`, `hdb_policies.py` (A0) and
    `scientist_has.py` (Nemotron roles).
  - Scripts: `hdb_vs_run.py` (arms A1/A3h/A3hx/A3), `hdb_identifiability.py`, `hdb_mkv.py`, `hdb_stop_calibration.py`,
    `hdb_walkers.py`, `hdb_report.py`.
  - Tests: `test_hdb`, `test_hidden_plant`, `test_scientist_has` (27 pass).
- **Local smoke (1 episode, reduced library, small repair budgets).**
  - Hidden friction loss was identified from one observation (posterior 1.0 on the true structure, 128 twin rollouts).
  - The twin-optimised design walked on the twin, but only 4–5/8 on the plant, and verification failed (11/24).
  - Lesson: designing against the single MAP hypothesis overfits the twin, just as the old scientist overfit 4 training seeds.
  - Fix: posterior-robust repair across an ensemble. Each of 8 twin seeds runs one of the leading hypotheses combined with a
    draw from a generic tolerance prior. The prior is declared a priori and is wider than, and independent of, the bench's
    sealed reality gap.
- **Design refinement proposed for registration (owner to confirm): C-MKV primary K1 vs K3** (correct vs symptom-twin
  structure, identical pipeline and compute). K1 vs K0 (model-free A0) is confounded by the twin machinery itself, so it
  becomes a secondary contrast.
- **2026-10-18 — first batch-VM block (Stage 1).** Ran: VS A1 (24 episodes, full generic library), the identifiability
  study (6 dev bases × 23 severities) and MKV dev (3 bases, mid severity).
- **v1 results (dev, engine v1, fixed severity grid).**
  - Diagnosis 17/20 correct, FULL 0/20.
  - The posterior is overconfident: all 3 misses carry mass 1.00.
  - Some 88–100 %-walking designs failed `verdict_v1`. The frozen walk verdict compares forward displacement with the faulty
    robot, which can travel far before it falls. Others narrowly failed the 20 s confirmation.
  - MKV v1: even K2 (exact deviation) 0/9 FULL. The v1 grid sits far beyond the failure threshold (see below), so the
    population measured nothing.
- **Identifiability (v1 grid, 88 eligible dev instances).**
  - Model-based twin-pair posterior: correct family 88/88, already from the first observation.
  - Model-free 1-NN on the same plant panel: T2 51/57, T4 21/31.
  - Simulation makes the twins separable, and the generic single-primitive library covers every single-primitive family.
    Nemotron's hypothesis contribution can therefore come only from search efficiency, magnitudes outside the coarse grid,
    and multi-primitive compositions.
- **Bench v2 (pre-freeze revision, physics only).** Severities are 1.0/1.3/1.7 × each base's failure threshold, found by
  bisection on the gap-free plant. The thresholds are small: payloads of 1–15 % of body mass, foot friction ×0.2–0.6.
- **Engine v2 repair:** twin warm start → warm-started plant optimisation with the remaining budget → selection by
  robustness evidence.
- **VS v2, A1 (dev, 12 old dev bases, 1.0× and 1.3× threshold, 113 eligible).**
  - FULL 37/113: payload 20/41, sensor bias 12/40, short feet 4/15, friction 1/17.
  - Identification only 51/113. Friction is 17/17, but small payloads and biases lie outside the coarse generic magnitudes.
- **MKV v2 (dev, 21 instances at 1.3×; development only).** FULL: K2 7/21, A0 (K0) 5/18, K4 3/18, K0n 3/19, K1 2/21,
  K3 1/21. K2 > K1 one-sided p = 0.031.
  - Exact quantitative knowledge helps. Structure alone does not, because the engine then misestimates the magnitude
    (same defect as above).
- **Engine v3 (dev fix before freeze, applies to every arm).** Generic magnitudes on a 4-level log grid from small to large
  (122 hypotheses); two-step parameter refinement.
- **Fresh walkers.** Panel of 250 failing bodies, split by region hash before any pipeline (dev 67, test 183). Pipelines
  running.
- **Correction (2026-10-18).**
  - Since M0 (`777ef0d`), the phase-3 dev records were committed outside the living directories. That broke
    `tests/test_frozen_records.py`, which requires every tracked file under `experiments/` outside `…/dev/`, `forge_loop/`
    and `demo_records/` to be frozen.
  - They now live in `experiments/causal_engineer/dev/phase3_diagnosis/` and `experiments/causal_engineer/dev/hdb/`.
  - The guard passes again. Lesson: run the frozen-record guard before every commit that adds files under `experiments/`.
- **Gate G-VS (target 21 Oct): met on 18 Oct.**
  - End-to-end episodes are deterministic: two runs of the same episode give byte-identical records, wall time excluded.
  - Plant and twin ledgers are exact; the workbench asserts it on every ledger read.
  - The posterior concentrates on the injected class in most dev episodes: T2/T4 v1 grid 17/20. On the v2 threshold
    severities, identification fell to 51/113 with engine v2; engines v3/v4 address that and are being measured.
  - Bit-identity tests pass. Full Python regression on the main VM: 1,370 tests OK (5 skipped).
- **Live smoke (Stage 1, ≤ $5 allowed).**
  - 3 A3 episodes, all roles valid, $0.013 in total (about $0.004 per episode, far below the $0.25 planning estimate).
  - The engine identified the injected structure in 3/3, but 0/3 recovered.
  - Two of the episodes accepted on 15/16 robust seeds with 650+ plant rollouts unused and then failed verification by one
    seed. This is the stopping problem the dev calibration addresses: `accept_fn` interface; A1f = spend all.
- **Fresh-walker campaign (`hdb-v1-walkers`) complete.**
  - 250 genuinely failing guided bodies (S3 generation rule, unchanged). Each went through the FIX pipeline at 2,000
    rollouts, then `full_recovery_v1`.
  - 135 verified walkers became HDB bases: 36 dev-side, 99 test-side. The region-hash split was fixed before any pipeline
    ran. The other 115 creatures (PARTIAL 89, NOT 26) are reported, never used.
  - Test-side bases are never used in development.
- **Engine additions:**
  - `calibrated_accept` (isotonic robust16 → P(FULL), dev-fitted);
  - runner arms A0 and A1f;
  - `hdb_replay.py`: deterministic replay attribution on recorded plant data.
- **Spend at 16:50 UTC:** infra ledger $40.45 of the $72 cap, i.e. about $7.2 of the $35 Stage-1 envelope. Inference
  $0.013 for the live smoke.
- **Engine v2 → v4 on the same 49 dev instances (interim).**
  - Structure correct 23 → 42.
  - Confident-but-wrong posteriors 20 → 5.
  - Mean posterior on the injected structure 0.47 → 0.85.
  - FULL 11 → 12. Diagnosis is no longer the bottleneck; repair and stopping are.
- **Why verification fails (VS v2, 76 non-FULL):**
  - 50: validation walking below 80 %;
  - 18: robust walking but `verdict_v1` not VERIFIED (forward displacement vs the faulty robot);
  - 7: 20 s confirmation failed.
  - The calibration builder now also records forward displacement for the candidate and the faulty design on the robust
    seeds.
- **Stopping calibration (dev; partial, 566 designs, 65 FULL).**
  - The naive Beta reading of robust16 has Brier 0.105, *worse* than a constant forecast (0.102); ECE 0.11.
  - Logistic leave-one-base-out: robust16 alone 0.070; robust16 + 20 s stress test 0.067 (ECE 0.03, AUROC 0.92); all
    visible evidence 0.064.
  - Empirical FULL rates: robust16 = 15 → 10/30; 16 → 24/33; 16 with stress 4/4 → 19/23.
  - So the provisional 15/16 rule (and the old scientist's 4/4 stress test) accepted designs that fail about two times in
    three.
  - Engine: candidates reaching ≥ 14/16 get the 8-rollout stress test; acceptance uses the mapped P(FULL) ≥ τ (dev choice
    τ = 0.75). The map and τ are frozen at registration and never refitted on test.
- **MKV v4 (dev, 21 instances at 1.3×).**
  - FULL: K2 6, K1 4, K0n 4, K4 4, K3 2, A0 (K0) 6.
  - Mean validation walking: K2 0.76 > K1 0.71 > K3 0.65 > K0n 0.59. A graded dose-response to mechanism information, but
    with small FULL counts.
  - With the exact deviation, the failures came from the repair search: crude tool screen (probe edits smaller than the
    needed fix, e.g. posture compensation of a sensor bias), weak twin optimisation of the chosen tool, and 15/16
    acceptances.
  - Engine v5: the top-5 tools are re-ranked by short ensemble twin CMA.
- **Dev arm comparison (12 old dev bases; development only; the engine was tuned on these instances, so no claim).**
  - A1 (engine v4, provisional stop) vs A0 (generic exhaustive), paired on 101 instances: A1-only 17, A0-only 7,
    one-sided p = 0.032. FULL: A1 39/113, A0 23/101.
  - Plant rollouts: A1 472, A0 690 on average.
  - The first time in the project any procedure beats exhaustive screening, even in development. Only the registered test
    on fresh robots can confirm it.
- **Stopping rules barely change outcomes.**
  - Paired: A1-provisional vs A1c (calibrated, τ = 0.75) 1/1 discordant; A1 vs A1f (spend all) 1/1; A1c vs A1f 0/0.
  - The calibrated and spend-all rules use 650–690 plant rollouts against 472.
  - This replicates the diagnosis: more optimiser budget does not buy verification. The calibrated map's value is an honest
    P(pass) and compute, not recoveries. Repair quality is the lever (engine v5).
- **A1c calibration check (dev, 113 episodes, τ = 0.75).** Accepted 23; mean mapped P(FULL) 0.77; 16/23 = 0.70 verified.
  Close calibration, slightly optimistic and in-sample (the map was fitted on dev designs of these instances). Not
  accepted: 22/90 verified. Total FULL 38/113 (A1-provisional 39).
- **Complete dev arm comparison (113 instances; correction: the earlier A0 count of 101 came from a partial pull).**
  - FULL: A0 28, A1 39, A1c 38, A1f 36.
  - A1 vs A0, paired: 19 vs 8, one-sided p = 0.026 (development; the engine was tuned on these instances).
  - The stopping variants are within 1–4 discordant pairs of each other.
  - Record: `experiments/causal_engineer/dev/hdb/ARMS_dev_engine_v4.md`.
- **Engine v5 + calibrated stopping (A1c5), dev, 113 instances.**
  - FULL 44 (39 %), against A0 28 (25 %): paired 24 vs 8, one-sided p = 0.004.
  - vs A1c on v4: 8 vs 2, p = 0.055 (the twin-CMA tool screen).
  - Twin use 1,968 of 2,800 on average; plant use 596.
  - Development only (engine and stopping map were tuned on these instances). Record:
    `experiments/causal_engineer/dev/hdb/ARMS_dev_engine_v4_v5.md`.
- **MKV, engine v5 (dev, 21 instances at 1.3×, provisional stopping).**
  - FULL: K2 8, A0 (K0) 6, K1 5, K3 5, K0n 5, K4 4.
  - Mean validation walking: K2 0.79, K1 0.77, K4 0.76, K3 0.73, A0 0.73, K0n 0.63.
  - K1 vs K3: 3 vs 3 discordant. K2 vs K1: 4 vs 1, p = 0.19.
  - Interpretation (dev): the ensemble-robust pipeline tolerates a wrong *structure* (twin optimisation and plant
    optimisation compensate), while exact *quantitative* knowledge helps more.
  - The planned C-MKV primary on binary FULL (K1 vs K3) looks underpowered and close to null at N = 160. The owner decides
    the registered form; proposal in the status report.
- **Operations.** `ForgePool` caps workers at 7 (`MAX_WORKERS`). Parallelism comes from sharding, and the
  identifiability script gained `--shard`. Infra ledger $52.43 at 22:30 UTC (Stage 1 spent about $19 of $35).
- **Multi-class identifiability (dev, 302 eligible instances, all 9 dev families as rivals, 1.3× threshold).**
  - Injected family is the MAP: observation only 245, + condition tests 270, all instruments 282 (93 %).
  - The 20 remaining confusions (actuator weakness / heavy torso / one-side weakness; balance-gain loss / short feet)
    form the ambiguous stratum.
  - Experiments carry information, so experiment choice matters (grounds for arm A3hx).
- **HDB v2 frozen** (`docs/HDB_SPEC.md`, module hashes recorded). The severity definition awaits the owner's confirmation.
- **Fresh dev robots, all 9 dev families (18 fresh dev bases, 1.3× threshold, 211 eligible).**
  - FULL: A1c5 (engine v5 + calibrated stopping) 109 (52 %), A0 62 (29 %). Paired 61 vs 14, one-sided p < 1e-6.
  - The engine matches or beats A0 in every family. Low friction stays unsolved (2 vs 1 of 17).
  - Plant use 586 vs 690; twin use 2,023.
  - Development evidence on morphologies not used for tuning. The engine, map and families are dev, and only the
    registered test (99 sealed bases + held-out families) can confirm it. Record:
    `experiments/causal_engineer/dev/hdb/ARMS_fresh_dev_9families.md`.
- **2026-10-19 — owner decisions on Stage 1; Stage 2 authorized.**
  - Severity definition (1.0×, 1.3×, 1.7× of each robot's failure threshold) **confirmed**. HDB v2 stays frozen as specified.
  - **C-MKV registered form (fixed now, before any sealed evaluation; the change was motivated by development results):**
    - primary: K2 (exact deviation) vs K0n (same inference/repair pipeline, nominal model only), exact one-sided McNemar
      on FULL;
    - secondary: K1 vs K3, and K2 vs K1;
    - secondary engineering outcome for each contrast: paired validation walking fraction, one-sided Wilcoxon
      signed-rank;
    - analysis code: `scripts/hdb_report.py` `MKV_CONTRASTS` and `wilcoxon_one_sided`.
    - Dev MKV v5 under this analysis: K2 vs K0n FULL 4 vs 1 (p = 0.19), walking +0.17 (Wilcoxon p = 0.003).
    - Oracle mechanism knowledge (K1/K2) is a property of the pipeline, **never a capability demonstrated by Nemotron**.
  - **Stage 2 envelopes (incremental): infra $20, inference $10.** Stage 3 and the registered evaluation are not authorized.
  - **Reconciliation of Stage 1.**
    - Infra ledger: $33.29 → $75.48 (+$42.19 against the $35 envelope).
    - The overrun comes from the batch VM running 5.39 h past its deadline (≈ $11.39 at the quoted rate) after an expired
      CLI login disabled the watchdog. Without it, Stage 1 would have cost ≈ $30.8.
    - Real credit is not queryable through the CLI. Estimate: $66 − $42.19 ≈ $23.8 left (conservative, because the ledger
      charges every hour up to the API stop). That covers the $20 Stage-2 envelope, but not the $5 demo reserve, so the
      owner's console balance is needed before Stage 3.
  - **Cloud safety.** Unattended Nebius CLI calls now run with `--no-browser --auth-timeout 30s`. The first auth failure
    writes `infra/nebius/AUTH_BLOCKED`, and every later unattended call refuses without contacting Nebius until the owner
    runs `forge_cloud.py login`.

## Stage 2 (authorized 2026-10-19): the autonomous scientist

### Architecture (`creature_forge/has_agent.py`)
- **Roles.** Nemotron directs the investigation. MuJoCo (plant and twin), the Bayesian belief engine, EIG estimates, CMA-ES
  and the dev-calibrated verification map are its instruments.
- **Each turn.** Nemotron reads a lab notebook and calls ONE tool. The notebook holds:
  - the measurements;
  - the engine's posterior over executable explanations;
  - a model check (UNEXPLAINED residuals);
  - candidate experiments with their EIG and each leading explanation's prediction;
  - the tool screen;
  - designs with plant evidence and P(pass);
  - memory dossiers with live applicability checks;
  - the engine's own recommendation.
- **Tools:**
  - experiment (engine candidates or Nemotron-designed counterfactuals / floor tests, with a registered prediction);
  - propose (executable hypotheses, may accompany any action);
  - delegate_diagnosis, screen_tools;
  - repair (twin or plant mode, tool, physically reasoned start edits, design against belief or leading explanation);
  - check;
  - assimilate (fold a repaired design's plant check into the belief: a failed repair is evidence about the mechanism);
  - apply_dossier, use_learned;
  - delegate_repair, conclude.
- **Delegation is exact.** The engine's recommendations are exactly arm A1c5's steps, so an agent that always delegates
  reproduces A1c5 (checked: `A1e`). Invalid or failed replies fall back to the recommendation (recorded).
- **Engine changes (behaviour-preserving for A1c5).**
  - `diagnose` is split into `start / rank_experiments / experiment_step / diagnosis_done`.
  - `assimilate_check`: walking-only likelihood of a robustness check on the robust seeds.

### Experience (`creature_forge/has_memory.py`) and the learned posterior (`creature_forge/amortized_posterior.py`)
- **Dossiers** are executable and checkable:
  - mechanism template (DSL structure + parameter ranges);
  - signature and fails_when predicates on measurements, or on the engine's belief in the dossier's own mechanism;
  - recommended repair and principle text.
- **Support statistics** are computed by code only, on dev records: signature precision/recall, verified outcome of the
  recommended repair vs other repairs, magnitude coverage.
- **Revision.**
  - Deterministic rules mark a dossier contested / retired.
  - Nemotron (consolidator) writes and revises dossiers from a deterministic evidence digest (contrasts between mechanisms,
    post-mortem magnitudes, outcomes by repair tool).
  - The memory is frozen during evaluation.
- **Learned posterior:**
  - Softmax structure classifier, per-class ridge magnitudes, and a Mahalanobis out-of-distribution flag.
  - Trained on simulated deviations of the dev structures (held-out primitives excluded), on experience bases only.
  - Inputs are differences from the nominal twin on the same seeds.
  - Its suggestions are hypotheses the data must confirm.

### Development protocol for Stage 2 (fixed 2026-10-19, before any agent pilot)
- **Split** (`experiments/causal_engineer/dev/hdb/stage2_split.json`):
  - **experience** = the 30 dev bases already used in Stage 1;
  - **transfer** = the other 18 fresh dev bases, never used.
  - Dossiers, the learned posterior and all prompt or agent tuning use experience bases only.
- **Pilots** (≤ 3 iterations) run on experience-base instances. Traces are inspected and the agent is improved.
- **Then one transfer evaluation**, never tuned on afterwards:
  - transfer bases, 9 dev families, 1.3×;
  - 4 eligible instances per family (seeded shuffle 20261019) = 36;
  - arms A1e (engine), A2 (engine + learned), A3 (Nemotron agent), A4 (agent + dossiers + learned);
  - paired FULL and walking, plant/twin/token costs, and the process metrics of `scripts/hdb_agent_report.py`.
- **Unfamiliar mechanisms.** A leave-family-out memory (two dev families excluded from consolidation) is evaluated on
  those families' transfer instances. This measures applicability checks and negative transfer. The sealed held-out
  families stay sealed.
- **Status of these results.** All are development evidence. The registered primary (A3 vs A1) is tested only in Stage 3
  on the sealed test split, and Stage 3 needs owner approval.

### Stage-2 log
- **2026-10-19 — first consolidations (live, $0.19 in total):**
  1. One dossier was written. Its mechanism range pointed the wrong way (it encoded the repair, actuator strength > 1, not
     the deviation). Its signature had 9 % precision, and the code retired it.
  2. With a contrast digest: the reasoning drafted 10 dossiers, but the schema-constrained answer was empty. Fixed with
     one call per mechanism.
  3. A leading boolean in the schema was emitted as `false` before the reasoning concluded. Fixed by putting the decision
     field last.
  4. Result: 6 dossiers with deterministic support, e.g. "sensor bias pitch" precision 0.92 / recall 0.33.
  - **Finding (dev):** observation medians barely separate the mechanisms. The largest contrast is fall direction, at
    0.67 of the spread; the engine's model-based inference identifies them. Dossiers can therefore condition on the
    engine's belief ("once the mechanism is identified, apply the learned repair principle").
- **2026-10-19 — the agent loop with full delegation reproduces A1c5 exactly.** On 4/4 experience-base instances,
  A1e (`hdb_agent_run.py --arm A1e`) has the same verification, plant ledger, twin ledger and every design vector as the
  Stage-1 A1c5 record. Any A3 vs A1e difference therefore comes from Nemotron's non-delegated decisions.
- **2026-10-19 — learned amortised posterior v1** (3,628 simulated failures on the 30 experience bases; 5-fold
  leave-bases-out CV over 10 dev structures, chance 0.10):
  - observation only: top-1 0.37, top-3 0.67 (log loss 1.78 vs chance 2.30);
  - plus floor test and weigh test: top-1 0.50, top-3 0.81 (log loss 1.39).
  - Real signal, but weaker than the engine's model-based identification (identifiability study: 245/302 from
    observation alone). Its use is as a proposal source, not as the inference.
- **2026-10-19 — memory v5** (live consolidation, $0.14): 7 executable dossiers.
  - Code-computed support: payload (precision 0.81; recommended repair verified 17/22 vs 14/25 for others), clock
    (0.93; 7/10 vs 2/4), balance-feedback gain (0.78; 3/4 vs 2/5), actuator strength all (0.40).
  - The code marked the sensor-bias dossier contested (its recommended repair verified 3/22 vs 10/32 for others) and
    short feet contested, and retired right-side weakness (precision 0.09).
- **2026-10-19 — live pilot 1 (agent v1, A3, 9 experience-base instances, one per dev family; $0.10 = $0.011 per
  episode, about 5 calls each).**
  - **Outcomes:** FULL 5/9; correct leading explanation 6/9.
  - **Paired with engine-only (A1c5) on the 7 instances that have it:** A3 3/7 vs engine 5/7. Losses on heavy torso and
    low friction; no wins.
  - **Diagnosed causes (from traces; no instance-specific tuning):**
    1. Nemotron's own plant-mode repairs used small budgets (120–124 rollouts, n_train 8). They barely optimise, and
       they drain the budget the engine's repair later needs.
    2. It misread tools: it believed delegate_diagnosis costs no plant rollouts, and it misread a weigh test without the
       design's mass.
    3. A third of its turns failed validation, mostly because the optional `prediction` field was dropped under
       constrained decoding. The fallback then executed the engine's terminal recommendation, which ended the
       investigation.
    4. Its physical repair insight could not be passed to the engine's repair procedure.
  - **Positive signs:**
    - On average its experiment choices matched the engine's best EIG (median ratio 1.0).
    - It noticed physically meaningful anomalies, e.g. a too-high step frequency pointing to a timing fault.
    - Its 90 % prediction intervals covered 9/10 (walking), 6/10 (upright time) and 8/10 (pitch).
  - **Hypothesis contribution:** its 9 proposed hypotheses never entered the top 3. The engine's generic library already
    covered the dev mechanisms.
  - **Changes:**
    - v2: delegate_repair takes the scientist's tool order and start edits (engine numerics unchanged); accurate tool
      costs and minimum budgets in the prompt; no terminal fallback; the design's own mass is shown beside weigh tests.
    - v3: required experiment/prediction/hypotheses fields; a missing prediction is recorded instead of voiding the
      action.
    - Engine: proposed hypotheses get a per-structure magnitude fit (the A1c5 path is unchanged).
- **2026-10-19 — live pilot 2 (agent v3, the same 9 experience instances).**
  - **Outcomes:** FULL 5/8 finished; paired engine-only 6/8. One loss (one-side weakness: Nemotron delegated after one
    low-EIG experiment, and the engine's repair was accepted at P(pass) 0.77 but failed verification). No fallbacks.
    $0.004–0.03 per episode.
  - **Pattern:** Nemotron picks experiments (mostly but not always the top-EIG one), sometimes runs a twin repair with
    its own tool choice, then delegates the repair. On single-mechanism dev failures it is about at engine parity.
  - **Engine limitation exposed (feedback-gain case):** after an experiment order different from the engine's, the
    posterior settled with full confidence on a wrong structure, because the true structure had been pruned after the
    first observation. Nemotron did not propose it again: both explanations fitted the data within noise.
- **2026-10-19 — development compositions** (`creature_forge/hdb_devcomp.py`: two dev mechanisms at 0.8× their own
  thresholds; sealed pairs excluded by code).
  - Engine-only A1e on the first 7 experience-base instances: FULL 3/7, posterior on the true two-cause structure 0 in
    7/7. The generic library cannot express two causes; this is the structural opening for Nemotron's compositional
    hypotheses (pilot 3).
- **Inference ledgers.** The batch VM's ledger (1,076 entries, Oct 14–17) is fully contained in the main VM's ledger.
  The main ledger is the master. Any LLM run on the batch VM uses a ledger handover: copy main → batch, no LLM calls on
  main meanwhile, copy back.
- **2026-10-19 — transfer-evaluation addendum (declared before any LLM run on transfer bases).**
  - Added: 16 development-composition instances on the transfer bases (`--devcomp --which transfer --sample --sample-seed
    20261019 --limit 16`), arms A1e, A3, A4.
  - Reason: pilots showed the engine cannot represent two-cause failures. The protocol must also measure the capability
    where the engine is structurally limited, not only where it is already strong.
  - The single-family part (36 instances) is unchanged.
