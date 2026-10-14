# R2 — local robustness optimisation around the frozen Phase 2A walker

> **Update 2026-10-14:** approved with corrections and executed. The binding protocol is `experiments/phase2a_r2/protocol.json` (commit `463c603`); the corrections (Tango non-inferiority with a hierarchy, frozen training-seed rule, exact 49-point grid, explicit reference accounting, pilot seeds 7300-7315) supersede the text below where they differ. Results: `experiments/phase2a_r2/REPORT.md`. This file is kept as the original proposal.

Status: design for review. Nothing here is committed as a protocol; after approval it becomes `experiments/phase2a_r2/protocol.json`, committed **before** any optimisation, with the same guard machinery as R1 (committed-file check, hash-chained ledger, session-based wall guard, futility gate). Basis: `docs/R1_SEARCH_ANALYSIS.md` (post-hoc).

## 1. Question and what it can and cannot show
**Question.** Starting from the frozen Phase 2A controller θ0 (`best_random_search.json`, sha256 `8ba7d5ee…`), does a *local* search in normalized parameter space, trained for robustness across initial conditions, produce a controller that walks (all gates) on a larger fraction of fresh seeds than θ0?

**Separating two claims.** R2 is deliberately a *refinement* experiment. It reports two separate conclusions, with different tests:
- **Preservation** (did not break the gait): non-inferiority — the winner's final walking rate is not lower than θ0's by more than 5 pp (exact one-sided test on the discordant pairs, α = 0.05), and zero new body-dragging seeds.
- **Improvement**: superiority — exact two-sided McNemar on paired final seeds (α = 0.05) with positive difference. Only this is the confirmatory improvement claim.
- **Discovery of a gait from scratch is out of scope.** R1 showed that a 149-point uniform search finds none (nearest sample 0.78 normalized-L2 from θ0). Nothing in R2 can be described as global discovery.

## 2. Frozen elements (unchanged from R1/Phase 2A)
Morphology, walking gates (`DEFAULT_CRITERIA`), 10 s episodes, initial-state distribution N(0, 0.03 rad) from the episode seed, controller family (`PhaseGaitInitController`, 15 parameters, bounds from `INIT_BOUNDS`), θ0 = incumbent. No FSM, no RL.

## 3. Parameterisation
u ∈ [0,1]^15 = (θ − lower)/(upper − lower). θ0 in u: freq .76, duty .24, hip_amp .02, knee_amp .66, knee_shift .41, stance_knee .89, hip_bias .86, kp .53, kd .38, balance_gain .71, pitch_kp .71, pitch_ref .68, sync_gain .84, ramp_s .17, start_lean 0.00. Perturbations are added in u and **reflected** at the bounds (start_lean = 0 sits on its lower bound, hip_amp at .02).

## 4. Seeds (all new, disjoint from every consumed range)
Consumed and excluded: Phase 2A 1000-3019, R1 train 4000s, R1 validation 4100s, R1 diagnostic 5000s, R1 final 6000s (never evaluated, but reserved by R1's protocol; not reused so no one can ask whether R2 touched them).

| role | seeds | n | use |
|---|---|---|---|
| screen | 7000-7063 | 64 | θ0 only, once: sort into walking / non-walking |
| train | first 8 θ0-walking + first 8 θ0-failing seeds of the screen | 16 | optimisation (robustness-aware: half are seeds where θ0 fails) |
| validation | 7100-7163 | 64 | choose among each run's top-5 and the overall winner; futility gate |
| diagnostic | 7200-7231 | 32 | post-hoc analysis (incl. 2× larger initial perturbation, as stress) — never used for selection |
| final | 8000-8149 | 150 | winner vs θ0 once, after `selection.json` is committed |

The train rule is deterministic given the screen output and is recorded before optimisation starts. Screening uses θ0 outcomes only; final and validation seeds are never inspected during optimisation. Why 150 final seeds: with 30 seeds exact McNemar has ≈ 23% power at +15 pp (R1 under-powered); with 150: 96% (+15 pp: 20% fixed / 5% broken), 74% (+10 pp: 15%/5%), 64% (+7 pp). Compute is not the constraint (≈ 15 rollouts/s on the VM).

## 5. Training criterion (replaces R1's worst-2 mean)
Lexicographic, evaluated on the 16 training seeds with common random numbers across all candidates:
1. `W` = number of training seeds passing **every** walking gate (higher is better; a discrete success count that cannot reward falling slowly);
2. then number of seeds not falling;
3. then mean per-seed fitness (the existing `fitness_components`).

**Preservation constraint in training:** a candidate is *feasible* only if it walks on at least `W(θ0) − 1` training seeds (allows one lost seed, so improvement elsewhere is not forbidden by noise); infeasible candidates rank below all feasible ones. (R1's finding: the continuous worst-k fitness ranked θ0 140/150.)

## 6. Arms (equal structure, separate random streams, CRN on seeds)
| arm | what varies | method |
|---|---|---|
| **S** subset perturbation | k ∈ {2, 4, 8} randomly chosen coordinates of the 13 gait parameters, σ_u ∈ {0.02, 0.05, 0.10, 0.25} (cycled; 0.25 is the "nearly global" control) | non-adaptive Gaussian perturbations of θ0; 2 independent replicates × 120 candidates |
| **I** initiation-only | only (ramp_s, start_lean), the 2-parameter extension | full 7×7 grid over the bounds + θ0 neighbours; 1 run, 49 candidates |
| **T** trust-region ES | all 15 coordinates | (1+λ)-ES, λ = 8, σ_u0 = 0.05, 1/5-success step-size rule, σ_u ∈ [0.005, 0.2], parent replaced only by a feasible candidate that beats it lexicographically; 2 replicates × 15 generations (120 candidates) |

Sep-CMA-ES is **not** proposed: with 16 seeds per evaluation and ≈ 120 evaluations the covariance adaptation has too little information to be justified over the 1/5 rule; it can be a later R3 comparison.

**Basin map (free by-product).** From arm S, report P(feasible | σ_u, k) with Wilson intervals — how large the viable region around θ0 is, which is the quantitative answer to "preserving vs discovering".

## 7. Validation, gate, selection, final
- Validation: top-5 candidates per run by the training criterion (θ0 validated once on the same 64 seeds). Primary validation measure: number of the 64 seeds passing every walking gate.
- **Futility gate** (after replicate 1 of S and T and the I run): proceed only if some arm's best eligible candidate walks on **≥ 5 more of the 64 validation seeds than θ0 (≥ 7.8 pp)** and loses none of the preservation criteria (no new body-dragging; non-falling count ≥ θ0's). Otherwise stop and report a null result. Pragmatic heuristic, not a significance test.
- Selection (one overall winner after both replicates, committed before the final): eligible = validated, not θ0; rank by (1) validation walking count, (2) non-falling count, (3) mean fitness; ties by arm order S < I < T, replicate, index. Origin of the candidate (hand, optimiser, LLM) plays no role.
- Final: winner vs θ0 on 8000-8149, identical conditions. Reporting as R1: paired 2×2, discordant counts, exact McNemar p, Newcombe interval on the paired difference, Wilson and exact intervals, conditional odds ratio. **Engineering criterion** (reported, separate from superiority): ≥ 135/150 walking seeds (90%), median upright speed ≥ 0.25 m/s, 0 body-dragging seeds; 135/150 does not establish a true rate ≥ 90% (exact interval reported).

## 8. Budget (hard caps; counted in a hash-chained ledger exactly as R1)
| stage | rollouts |
|---|---|
| pilot (≤ 5 candidates × 16 seeds + θ0 × 16, plus resource probes) | cap **100** |
| screen θ0 on 64 seeds | 64 |
| training: S 2×120×16 = 3,840; T 2×120×16 = 3,840 (+ θ0 reference 16 per run); I 49×16 = 784 | ≈ 8,500 |
| validation: top-5 × 5 runs (S1, S2, T1, T2, I) × 64 + θ0 × 64 | ≈ 1,664 |
| final: 2 × 150 | 300 |
| **planned total** | **≈ 10,700** |
| **hard cap** | **12,000**, no automatic extension, no silent retry |

Resources: 4 workers, ≥ 4 GB free memory floor, 60-minute cumulative active-time limit (R1 used 81 s for 3,872 rollouts; ≈ 12-15 min expected), VM run only; the existing `forge_cloud.py` workflow, now with deadline sync and session-based wall accounting. Estimated VM cost < $0.20. The local machine runs nothing heavy.

## 9. Modest pilot (after the protocol is committed; it cannot tune the protocol)
The pilot only measures throughput, memory and *code correctness* (perturbation reflection at bounds, CRN, ledger, seed screening) on ≤ 100 rollouts, using seeds from the diagnostic range so no training/validation/final seed is touched; its results cannot change arms, scales, criteria or thresholds. Protocol is committed first, pilot second.

## 10. Risks and honest limits
- Local search around one controller on one planar morphology can only refine; a null result would mean this controller sits at a local optimum for this objective and seed budget.
- 16 training seeds with θ0 failing on ≈ 5-8 of them gives a noisy but unbiased signal; the validation (64) and final (150) seeds carry the inference.
- Winner's curse is controlled by validation + untouched final; arm comparisons remain exploratory; the final test is the only confirmatory one.
- Linux floats differ from Windows by ~1e-15 relative; all R2 evidence is generated on the VM and the provenance recorded.

## 11. Nemotron: from text hypotheses to a measurable physics loop (needs approval; nothing run)
Evidence so far (honest): Phase 1 — 3 live requests, 2 valid replies both proposed `torso_mass 5→3` and failed verification; random per-proposal success 22/100. No accepted AI improvement exists. The first goal is therefore a **fair, measurable comparison**, not a claim of AI success.

**Loop (reuses `nebius.py`, `investigator.py`, `forensics.py`, the Lab).** (1) MuJoCo rollouts of the current best controller produce forensic evidence on the training seeds where it fails (startup timeline: pitch, COM-vs-support margin, first-step timing, contact sequence, torque demand, label). (2) Nemotron receives that evidence plus the parameter table with bounds and returns strict JSON: up to 4 bounded edits (named parameters, normalized deltas ≤ 0.15, one predicted measurable effect each, e.g. "walking seeds among the failing 8 increases"). (3) The deterministic verifier evaluates every edit on the same training seeds, then validation seeds for the best ones, and records observed vs predicted. (4) The verdict is written to the Lab record (provenance: observed / model / measured). Feedback rounds ≤ 3.

**Arm N inside R2** (added to §6 only if approved before registration): LLM-proposed edits of the same size and parameter subsets as arm S, **equal number of evaluated candidates**. Comparison with S (random edits) and T (optimiser) is exploratory on validation counts; the confirmatory test is unchanged and origin-blind. Controls built in: (a) random edits with the same k and σ (arm S), (b) a heuristic proposer from the Phase 2A ablations, (c) Nemotron without the evidence block (prior only) to test whether the evidence matters. Measured outcomes: fraction of proposals that keep walking and fraction that improve the training count, best validation gain over θ0, prediction accuracy (predicted direction vs measured). Registered metrics only; a result of "no better than random" is reported as such.

**Budget:** ≈ 8 rounds × ≈ 3k tokens × 3 conditions ≈ 75k tokens per replicate, well inside the existing client's token and request limits and negligible against the credit balance; requires your approval for the live requests. No GPU, no new Nebius instance.

**Hackathon path (tell me the deadline date to schedule):** 1) approve R2 → I register and run the pilot (≈ 1 h); 2) R2 run + analysis (≈ 1 h compute-wall, plus review); 3) approve Nemotron arm → adapter from forensics to normalized-delta schema, offline fake-model tests, one registered live batch (≈ 0.5-1 day); 4) Lab view of R2/Nemotron trials with replay (the viewer, replay and provenance panels already exist); 5) demo script and write-up that states exactly which claims the data support (improvement vs θ0 on untouched seeds, proposer comparison, null results included).

## 12. Decisions requested
1. Approve R2 as proposed (arms S, I, T; 150 final seeds; cap 12,000 rollouts; 60-min limit), or change scales/budget.
2. Include arm N (Nemotron) in R2 registration, or keep R2 LLM-free and run the Nemotron comparison as its own registered R3?
   *Recommendation:* LLM-free R2 first (it is the clean baseline and needs no key), then R3 with the baselines and θ-best from R2.
3. Hackathon deadline date.
