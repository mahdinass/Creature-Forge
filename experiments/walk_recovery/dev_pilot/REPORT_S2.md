# S2 method dev pilot: who should make the engineering decisions? (development data)

**Registration.**
- Protocol `protocol_s2.json` (`walkrec-s2-dev-pilot-v1`) was committed in `da421f2` before the run.
- The analysis script `scripts/walk_s2_analysis.py` was committed in `a799d1f` before the results were complete.

**Execution.**
- One execution on the temporary batch VM (slot `s2`, snapshot `08e7dc1` = `da421f2` with a clean tree).
- 144/144 units, 0 unit errors, every shard exited 0, nothing rerun.

**Records.** `results/` (12 shard files, summary, `analysis_output.txt`, SHA-256 `MANIFEST.json`).

**Key scan.** The real `NEBIUS_API_KEY` value occurs in 0 files under `experiments/walk_recovery/`.

**Inference.**
- 165 live Nemotron requests: `ai` 116 calls, $0.19; `ai_nogait` 49 calls, $0.05.
- A smoke run before S2 made 4 more calls; it is not a result.

This is development data. It fixes R\* and the comparator by pre-declared rules, and it is never confirmatory evidence.

## Setup
- The 12 M1 development creatures, with fresh seeds.
- Every method gets the same **total** rollout budget: probes, plans, discarded plans, screening and rounds are all
  charged. The ledger equals the sum of its lines and stays ≤ budget in 144/144 units.
- Each method returns one candidate, assessed with `full_recovery_v1`. Family 17 (foot-placement controller).

## Results (full recoveries out of 12)
| method | 2,000 rollouts | 4,000 rollouts |
|---|---|---|
| cma_ctrl (blind, controller only) | 3 | 3 |
| cma_joint (blind, controller + 4 body params) | 3 | 6 |
| fix (fixed rule: probe placement / body / posture, then search the union of the best two plus body) | 4 | **8** |
| rand (same pipeline, random decisions) | **7** | 5 |
| **ai (Nemotron director, full evidence)** | **2** | **1** |
| ai_nogait (Nemotron without gait features) | 2 | — |

## Pre-declared decisions
- **R\* = 2,000.** The best non-AI method (fix) recovers 4/12 = 33%, inside the 25–60% band.
- **Primary comparator = FIX** (4 vs cma_joint's 3 at R\*).
- **G2 = PASS.** Accounting is exact in every unit, and the AI produced a valid plan in 24/24 pipelines, 12/12 without
  gait features.

## The AI director underperformed every comparator. Why (measured from its recorded decisions)
1. **It almost never co-designs the body.** 56 of its 62 plans changed no body parameter, and it requested `opt_body`
   once in 24 pipelines.
   - The census ranks `opt_body` as the single best probe for 9/12 creatures, and M1 found joint search strongest.
   - FIX added the 4 body parameters in every plan; RAND did so in about 60% of plans.
2. **A strong prior on gait timing.** Its first probe set contained `opt_timing` in 22/24 pipelines, yet timing is a
   census top-2 probe for only 2/12 creatures. Its hypotheses are physically plausible (cadence and leg length), but
   the measurements did not support them as often as it assumed.
3. **It leaves budget unused.** It spent 86–88% of the budget, against 96–99% for every other method. It splits
   0.5/0.5 per round and never spends the remainder in the last round.
4. **Narrow plans.** Its plans cover 1–2 control subspaces.
5. **Diagnosis (H6), descriptive and small n.** With full evidence its round-1 probes included a census top-2 probe in
   11/24 pipelines, against 8.0 expected by random choice. Without gait features it managed 2/12, against 4.0 expected.
   So the gait features carry some diagnostic signal the model uses, but its choices are dominated by priors.

## Other observations
- **Random decisions are surprisingly strong** (7/12 at 2k, 5/12 at 4k).
- Same-method numbers move by ±2–3 between budgets (rand 7 → 5, fix 4 → 8). At this panel size, optimiser
  stochasticity is a large part of every count.
- The decisive factor appears to be including body co-design plus some restricted control subspace, more than which
  subspace is chosen.
- `weak-slippery` reaches PARTIAL with 0% walking at 2k for every method (score gains without gait), and recovers only
  at 4k with body changes.

## Consequence (next step, logged as development tuning)
These are failure modes of the AI's decision policy. They are not representation or optimiser limits. The director is
revised once, on development data:
- state that budget left after the last round is wasted;
- present body co-design as a first-class subsystem equal to the control subspaces;
- show reference values (the default body's features) so unusual proportions are visible;
- no instruction about which subsystem usually works.

The revised director is re-piloted on the same dev creatures and seeds (paired with the numbers above). The FIX rule was
also designed with development knowledge (M1), so both are dev-tuned; the confirmatory study on fresh creatures decides.
Model capacity (Nemotron Ultra, or Super with reasoning on) is checked on the H6 probe-choice benchmark (model calls only).
