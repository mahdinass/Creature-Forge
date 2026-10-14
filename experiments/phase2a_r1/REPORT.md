# R1 robustness experiment - result: NULL (futility gate STOP), 2026-10-14

Protocol `phase2a-r1-protocol-v1` (commit `f33d429`, unchanged). Executed on a Nebius `cpu-d3` 8 vCPU / 32 GiB VM (Ubuntu 24.04, Python 3.12.3, MuJoCo 3.15.0, NumPy 2.5.4), 4 workers, stages run exactly as `scripts/run_r1.py` defines them. Records: `results/` (ledger, pilot, histories, validations, gate), `logs/` (stage logs, pip freeze, environment check).

## Pilot
32 rollouts, 0 errors, 2.1 s wall (15.0 rollouts/s), peak worker RSS 65 MB, 30.7 GB free before / 30.6 GB after, recommended workers 4, projected remaining wall 517 s. All four checks passed.

## Replicate 1 (arms A, B, C)
Training: 3 x 150 candidates x 8 seeds = 3,600 rollouts, 0 errors. Across the 447 non-incumbent candidates, **none passed every walking gate on any of the 8 training seeds** (best survival without falling 6/8 in A and B, 7/8 in C). The frozen incumbent walked 4/8 on the training seeds.

Validation (16 seeds 4100-4115): incumbent **11/16** walking (11/16 not falling). Eligible validated candidates (A 4, B 5, C 5, incumbent excluded): **0/16 walking for every one**. Best survival counts: A 14/16, B 11/16, C 16/16 (standing/lingering without gate-valid walking).

## Futility gate
Required: some arm's best eligible candidate walks on >= 2 more of the 16 validation seeds than the incumbent. Observed gain: A -11, B -11, C -11 seeds (-68.75 pp). **Rule says STOP**: replicate 2, selection and the final evaluation (seeds 6000-6029) were not run and are untouched. No hypothesis test applies (the gate is a stopping heuristic, not a significance test); no superiority claim is possible.

## Interpretation (limits)
Uniform random search in 13/15-D bounds with 150 candidates per run never produced a walking controller, so under this budget the incumbent (found by Phase 2A's search) is not beaten; the robustness-oriented objective (A vs B) and the initiation parameters (C) did not change that. This does not show that robustness training, a longer search or a different optimiser cannot help; it shows the registered design did not. Comparisons between arms are exploratory. Linux floats differ from Windows by ~1e-15 relative (see docs/REPRODUCIBILITY.md); the incumbent's 11/16 validation count was produced on Linux.

## Resources and budget
Ledger: **3,872 of 8,500 rollouts** (32 pilot + 3,600 training + 240 validation: 224 candidate + 16 incumbent), hash chain verified locally. Active wall time (sessions): 81 s of the 5,400 s limit. 4 workers, minimum free memory 30.5 GB, 0 job errors.

## Deviations (engineering only, disclosed)
Before the pilot (commit after `f33d429`): the cumulative wall-time guard now sums whole-script sessions (`session_begin/session_end` ledger events) in addition to batch durations, counts crashed sessions up to their last ledger entry and the live elapsed time of the running session; a test asserting bit-exact Windows floats was replaced by the documented tolerance (discrete outcomes still exact). `protocol.json`, seeds, objective, gates, futility rule and arms are unchanged.

---
## Addendum 2026-10-14 (review; the result above is unchanged)
Post-hoc offline analysis (`docs/R1_SEARCH_ANALYSIS.md`, `scripts/analyze_r1_search.py`, no new rollouts) shows: (1) the "447 candidates" above are **149 distinct 13-D points** evaluated by three arms (common random numbers), so the run was one 149-point random search; (2) the nearest sample was 0.78 normalized-L2 from the incumbent; (3) the registered worst-2 objective ranked the walking incumbent 140th of 150, so arms B and C selected non-walking survivors; (4) 30 final seeds would have given only ≈ 23% power to detect a +15 pp improvement. None of this alters the registered gate decision or any recorded file.
