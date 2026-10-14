# R2 local robustness optimisation - result (2026-10-14)

Protocol `phase2a-r2-protocol-v1`, registered in commit `463c603` before any rollout (machinery `e2b0e5d`). Executed on the Nebius CPU VM (`cpu-d3` 8 vCPU / 32 GiB, Ubuntu 24.04, Python 3.12.3, MuJoCo 3.15.0, NumPy 2.5.4), 4 workers, every stage as `scripts/run_r2.py` defines it. Frozen files were committed before the dependent stage: `training_set.json` (`9c1a26f`, before any candidate optimisation) and `selection.json` (`f4820f8`, before the final evaluation). Records: `results/`, stage logs `logs/`. Descriptive extras: `results/analysis.json` (`scripts/analyze_r2.py`).

## Confirmatory result (winner vs frozen incumbent θ0, 150 untouched final seeds 8000-8149)
Winner = arm T replicate 1, candidate 101 (selected by the registered rule among 24 eligible validated candidates (25 validated, 1 failed the preservation check), 10 of which tied at 64/64 validation seeds (9 from arm T, 1 from S); ties broken by non-falling count, mean fitness, arm order).

| | walking (every gate) | exact 95% CI | median upright speed | body-dragging seeds |
|---|---|---|---|---|
| winner T1#101 | **150 / 150** | [0.976, 1.000] | 0.51 m/s | 0 |
| incumbent θ0 | 91 / 150 (60.7%) | [0.524, 0.685] | 0.46 m/s | 0 |

Paired table: both 91, winner only **59**, incumbent only **0**, neither 0.

Registered hierarchical procedure (fixed sequence, each step at full level):
1. **Non-inferiority** (margin 5 pp, Tango score test for the paired risk difference): θ̂ = +0.393, Tango 95% interval [+0.319, +0.473], score statistic at the margin Z = 8.37 (one-sided p = 3.0e-17). **Non-inferior.**
2. **Superiority** (exact two-sided McNemar): p = 3.5e-18, winner-only successes 59 > incumbent-only 0. **Superior.**

Engineering criterion (reported separately; ≥ 135/150, median speed ≥ 0.25 m/s, no body-dragging): **met by the winner** (150/150), not by θ0. The exact interval's lower bound (97.6%) is what the data support about the true success rate on this seed distribution, not "100%".

## Pre-final stages (all counted in the ledger)
- Pilot (96 rollouts, seeds 7300-7315 disjoint from every other role): passed all checks; 8.9 rollouts/s, 65 MB/worker, 30.7 GB free, recommended 4 workers.
- Screen of θ0 on 7000-7063: 41/64 walking, 43/64 not falling; 41 walking and 23 failing seeds so no registered STOP. Training seeds: walking class 7000, 7001, 7004, 7005, 7006, 7007, 7010, 7012; failing class 7002, 7003, 7008, 7009, 7011, 7014, 7015, 7017. θ0 on them: 8/16 walking (derived from the screen, 0 new rollouts).
- Replicate 1 (training on those 16 seeds → validation on 7100-7163; θ0 = 43/64): best validated walking counts S1 60, **T1 64**, I1 63. **Futility gate: PROCEED** (gain +17/+21/+20 seeds ≥ the required 5). Replicate 2: S2 64, T2 64.
- Selection: T1#101 (frozen in `f4820f8`).

## Exploratory observations (not confirmatory, no multiplicity control)
- Arms on equal footing: training candidates reaching 16/16: T1 46 and T2 26 of 120 each, I1 20 of 48, S 1 and 0 of 120. The initiation-only arm I alone (2 parameters, 48 candidates) reached 63/64 on validation; T and S changed up to 15 or 2-8 coordinates. The winner itself moved only slightly in the initiation parameters (ramp_s 0.37 s, start_lean 0.018 rad) but substantially elsewhere (normalised changes: knee_amp +0.19, knee_shift −0.18, kp −0.22, balance_gain +0.17, pitch_ref −0.16, stance_knee +0.09, hip_bias +0.14); normalised L2 distance from θ0 0.47. **We do not know which parameters carry the improvement**; no causal claim.
- Basin around θ0 (arm S, training seeds, "feasible" = walks on ≥ W(θ0)−1 = 7 of 16 seeds; 20 candidates per cell): σ_u 0.02: 95% (k=2), 100% (k=4), 85% (k=8); σ 0.05: 95%, 65%, 65%; σ 0.10: 55%, 45%, 35%; σ 0.25: 45%, 30%, 10%. The viable region is large for small steps and shrinks smoothly with scale and the number of coordinates changed; contrast R1, where no uniform sample within 0.78 normalised units walked at all.
- Where θ0 fails: 59 final-seed failures, 55 of them plain falls with ≤ 1 valid step (startup failures), 2 chatter, 2 slow/few steps; the same pattern as the Phase 2A / R1 diagnoses.
- Post-hoc diagnostic seeds 7200-7231 (n = 32, never used for selection): standard noise winner 31/32 vs θ0 23/32; stress noise (σ = 0.05, not the evaluated distribution) winner 32/32 vs θ0 20/32. The winner is therefore not flawless: one standard diagnostic seed failed.

## Resources and budget
Ledger **10,700 of 12,000** rollouts (96 pilot, 64 screen, 3,840 + 3,840 + 768 training, 1,664 validation, 300 final, 128 diagnostic; exactly the planned numbers), hash chain verified. Active wall time 1,003 s of the 3,600 s limit; 4 workers; peak worker RSS 65 MB; minimum free memory ≈ 30.5 GB; 0 job errors; no retries. Reference evaluations of θ0 were executed once each (screen, validation, final, diagnostic, stress) as registered.

## Limits and what is not claimed
- One planar morphology, one initial-condition distribution (N(0, 0.03 rad)), 10 s episodes, one set of gates; no claim about other morphologies, terrains, pushes, longer horizons or hardware.
- The winner was selected among many equally good candidates; T1#101 is representative, not special. Local search around a working controller refines it; it does not discover gaits from scratch (R1).
- Seeds only change the initial perturbation, so "150/150" is 150 draws of the same simulated scenario family.
- All evidence was generated on Linux; Windows reproduction of the winner's final evaluation was **not** run because this machine has less than the registered 4 GB free-memory floor. Cross-platform float noise of ~1e-15 relative was documented earlier; behaviour near the gate thresholds on Windows is unverified.
- The gain concerns the registered success definition (every walking gate), not human-judged gait quality. A video/replay inspection of the winner has not been done.
- Arm comparisons (S vs I vs T) are exploratory; only the winner-vs-θ0 hierarchy is confirmatory.
- The same winner could be compared with a stronger baseline (e.g. a longer R1-style global search was not beaten or tested here).

## Deviations
None from the registered protocol. Infrastructure: bootstrap accepts an untracked VM file only if it is byte-identical to the incoming committed frozen file (used for `training_set.json`, `selection.json`).
