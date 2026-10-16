# L2: does learned engineering experience improve decisions on unfamiliar creatures? Gate G3 (development data)

**Registration.**
- Protocol `protocol_l2.json` (`walkrec-exp-l2-v1`) was committed in `8c57b36` before any run.
- The analysis script `scripts/walk_l2_analysis.py` was committed in `9cb5fbe` before the evaluation finished. A field-path
  correction in `d663206` changed no logic.

**Execution.**
- One execution on the batch VM.
- Training panel: 40 creatures from 17 regions, 174 draws.
- Test panel: 12 creatures in the held-out regions `L2-f0-*` (long legs with short feet), 110 draws.
- Collection: 40 joint-17 CMA runs at 4k rollouts, every candidate logged, successes and failures alike.
- Evaluation: 120 units, paired seeds per test creature, 1,000-rollout search from each warm start.

**Records.** `results/` (SHA-256 `MANIFEST.json`; the merged collection file's hash is recorded there).

## What was learned and how it was used
- **Model.** A 5-member numpy MLP ensemble (surrogate), trained on 40 creatures × about 650 evaluated candidates.
  - Input: 6 dimensionless morphology features plus a 21-D design (17 controller u-values and 4 body log-ratios).
  - Output: P(walk) on the training seeds.
- **Decision.** For an unfamiliar creature, rank a pool of past top solutions by mean − std on its morphology, take the
  best feasible one as the optimiser's start, and report an applicability ratio.
- **Baselines.**
  - `knn`: the best solution of the nearest training creature.
  - `mean_best`: the design-space medoid of the training creatures' best solutions.
  - `r2`: the transferred controller, no experience.

## Results (12 held-out-region creatures)
| warm start | N | full recoveries after 1k search | mean walking fraction: warm start alone | after search |
|---|---|---|---|---|
| r2 (no experience) | 0 | 2 | 0.00 | 0.39 |
| knn | 10 / 20 / 40 | 4 / 2 / 1 | 0.31 / 0.00 / 0.14 | 0.61 / 0.38 / 0.37 |
| mean_best | 10 / 20 / 40 | 2 / 2 / 3 | 0.41 / 0.41 / 0.45 | 0.60 / 0.60 / 0.73 |
| **learned** | 10 / 20 / 40 | **2 / 2 / 2** | 0.42 / 0.19 / 0.28 | 0.61 / 0.58 / 0.68 |

**G3 = FAIL** (pre-declared rule):
- learned@40 beat knn@40 (2 > 1) but did not beat mean_best@40 (3).
- It did not beat r2 (2).
- It did not improve from N = 10 to N = 40 (2 → 2).

Experience learning is therefore **not** added to the confirmatory study. It is reported as an exploratory, mostly
negative result.

## What this does show
1. **Reusing past solutions helps an unfamiliar creature.** Every experience-based start lifts the mean validation walking
   fraction after a short search from 0.39 (R2) to 0.6–0.73. The decision alone, with zero search, already walks on
   0.3–0.45 of seeds, against 0.00 for R2. But at n = 12 this does not turn into reliably more *full* recoveries.
2. **The learned surrogate adds nothing measurable beyond a simple reusable medoid of past solutions**, and its learning
   curve is flat. Its applicability score did not separate successes from failures: full recoveries were 3/18 in the
   low-uncertainty half and 3/18 in the high half.
3. **Nearest-neighbour retrieval got worse with more experience** (4 → 2 → 1). More training creatures give closer, but
   not better, neighbours for an out-of-region body. This is a concrete instance of "knowing when experience does not
   apply" failing.
4. **Limits.**
   - 12 test creatures and one held-out family.
   - A 1k evaluation budget.
   - One noise seed.
   - Optimiser variance alone moves counts by ±2.

## Staged next step (not pursued before the deadline)
A learned component would need a target with more headroom than the warm start:
- for example, a policy over the director's decisions (which subsystem to fund), trained across many creatures from
  probe outcomes;
- with far more training creatures (hundreds) and a larger held-out test set.

That is beyond this deadline. The finding to carry forward is the cheap one: past solutions transfer partially, and a
reusable medoid captures most of it.
