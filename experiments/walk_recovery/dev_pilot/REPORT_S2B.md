# S2b: director prompt v2 and a model-capacity check (development data)

**Registration.**
- Protocol `protocol_s2b.json` (`walkrec-s2b-director-v2-v1`) was committed in `0799dea` before the run.
- Amendment 1 (`protocol_s2b_amend1.json`, `10d92d7`) changed the cap only. The registered rollout cap (90k) was below the
  design's own need, so 7 exploratory Ultra units were refused before starting (none were interrupted). They ran under
  the amendment, with completed units skipped and none rerun.

**Execution.** 36/36 units, 0 unit errors. Paired with S2: same creatures, seeds and noise seed.

**Records.** `results_s2b/` (SHA-256 `MANIFEST.json`; key scan: 0 hits). `analysis_output.txt` is the analysis over
S2 + S2b together.

## Results (full recoveries of the 12 dev creatures; S2 rows repeated for comparison)
| method | 2,000 | 4,000 | plans with body co-design | budget used | decisions ok | cost / pipeline |
|---|---|---|---|---|---|---|
| ai v1 (S2) | 2 | 1 | 6/62 | 87% | 93/96 | $0.008 |
| **ai v2 (Nemotron-3-Super, thinking off)** | **4** | **5** | 32/64 | 91% | 94/96 | $0.009 |
| ai v2, Nemotron-3-Ultra (reasoning low), exploratory | 5 | — | 1/6 | 50% | 27/48 | $0.14 (18 s / call) |
| fix (S2) | 4 | 8 | 48/48 | 97–99% | — | — |
| rand (S2) | 7 | 5 | ~60% | 98–99% | — | — |
| cma_joint (S2) | 3 | 6 | all | 96–97% | — | — |

H6 (round-1 probes include a census top-2 probe):
- v1: 11/24 (random 8.0)
- v2: 13/24 (random 8.7)
- Ultra: 3/11 (random 5.2)

The order shuffle removed v1's position bias: `opt_timing` was the first probe in 22/24 v1 pipelines and in 15/24 v2
pipelines. v2 often probes `similarity` (15/24), which never helped in M1a.

## Interpretation
- **v2 fixed the measured v1 failure modes.**
  - Body co-design rose from 10% to 50% of plans.
  - Budget use rose to 91%.
  - Full recoveries doubled.
  - At R\* = 2,000, v2 ties the fixed rule (4 vs 4).
  - At 4,000 it is below FIX (5 vs 8), and RAND at 2,000 (7) is higher still. At n = 12, counts vary by ±2–3 from
    optimiser noise alone.
- **Ultra is not better at deciding.** It produced invalid or failed replies in 21/48 decisions, so most of its
  pipelines had no valid plan and spent only half the budget. Its 5/12 came from the probes' short searches plus
  screening, not from its plans.

## Decision for the confirmatory AI arm (deviation from the literal S2b rule, stated openly)
- The S2b rule ("the most dev full recoveries at R\* among v1, v2, v2-Ultra") selects **Ultra (5)** over **v2 (4)**.
- The plan's G2 gate, defined before S2b, requires the AI arm to produce a valid plan in **≥ 80%** of pipelines.
  - **Ultra fails G2:** only 6 valid plans in 12 pipelines.
  - **v2 passes:** 24/24 pipelines produced a valid plan.
- **Recommendation:** use **ai v2 with Nemotron-3-Super** (production configuration) as the confirmatory AI arm. Ultra is
  ineligible under G2, and v2 is also 15× cheaper and 12× faster.
- This reading of the two rules is recorded here before the confirmatory protocol is written. It is flagged to the owner
  for approval with the freeze.
