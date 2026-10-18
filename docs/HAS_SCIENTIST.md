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
