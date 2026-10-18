# Hypothesis-as-Simulation (HaS) scientist — specification and execution log (phase 3)

Plan of record (owner-approved 2026-10-18, revision 2): `docs/HAS_PLAN_2026-10-18.md`. This file is the living specification
and log. Branch `feature/has-scientist` (from `feature/causal-engineer` @ `c429329`).

## Diagnosis that motivated the phase (exploratory)
`experiments/causal_engineer/phase3_diagnosis/DIAGNOSIS.md`, produced by `scripts/phase3_diagnosis.py` from frozen held-out
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
