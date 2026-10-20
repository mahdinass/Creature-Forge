# FA-1B measurement findings (Investigation A)

Source: `feature/has-scientist` @ `ea9e729`. Path-by-path details are in `metric_path_matrix.csv`. Numbers come from
`scripts/fa1b_measure.py` (stdout in `logs/out_measure.txt`). Labels follow the brief: **Directly verified**,
**Interpretation**, **Hypothesis**, **Unknown**.

## Confirmed equivalences (Directly verified, code)

- **Plant.** Plant CMA, plant robustness checks (8/16), displacement evidence and final validation/confirmation all run on the
  same hidden plant object: the injected deviation plus the sealed reality gap.
- **Per-seed conditions.** All four paths generate conditions from the same function, `arena._condition`, on their own seeds:
  - perturbation 0.06 rad;
  - friction factor 1 ± U(0.10);
  - no push in walk rollouts.
- **Friction application.** Friction reaches the plant by two code routes:
  - training and robust checks pass `friction_factor` into `plant_rollout`;
  - validation applies `_body_with_friction` to the job body first.

  Both routes call the same function with the same clip [0.01, 3.0], *before* the plant's `contact_friction` multiplies the
  foot geom. They are numerically equivalent.
- **Walking label.** The label is `compute_metrics` + `classify` with `creature_criteria(evaluated body)` on every path.
  Validation's `outcome == PASS` is exactly `m["walking"]` (`hidden_plant.py:619`).
- **Score.** Validation's `score` equals `hdb_evidence.walk_score`: 0 if the robot fell before 1 s or had no valid step,
  otherwise `max(0, forward_disp_upright)`.
- **Comparator.** The robust-seed displacement evidence and the final verdict use the same `verdict_v1`, the same score rule and
  the same comparator design: design 0 is `inst["robot"]`.
- **Settle window.** Validation uses `settle_s = 0.3` and the policy paths use 0. This changes only the rollout's early stop.
  `compute_metrics` re-detects falls over the whole trace, so `fell`, `walking` and `score` cannot differ; only
  `min_torso_height` can. The difference is inert for every DS-1 criterion.

## Intentional differences (Directly verified; relevance noted)

| difference | where | relevance |
|---|---|---|
| Seed namespaces are disjoint (train / robust / twin / obs vs validate / confirm) | `hdb_bench.py:31-34, 206-211` | Out-of-sample by design |
| `robust8` reuses the first 8 of the 16 robust seeds | `hdb_evidence.py:62` | `robust8` and `robust16` are not independent evidence |
| n = 4 (train), 16 (robust), 24 (validation) | `belief_engine.py:971`, `recovery.py:36` | Selection on small samples leads to shrinkage at validation (below) |
| The CMA objective has no faulty-robot comparison | `walk_opt.py:395`, `locomotion.py:325-341` | Optimisation never targets the displacement clause |
| Twin training uses hypothesis ensembles without the reality gap | `belief_engine.py:856-860` | Twin→plant transfer gap |
| `assimilate_light` uses only the first 8 labels of a 16-seed check | `belief_engine.py:461` (V6 `assimilate_seeds = 8`) | Half of each 16-seed check is never assimilated |
| **Walking gates scale with the *evaluated* body's leg length; the displacement clause is in absolute metres** | `creature_walk.py:62-71` | A leg-shortening repair lowers its own `min_speed` and `min_step_advance` bar (below) |

## What existing records establish about the verification losses

- **A1. Displacement failures are already visible on the robust seeds.** *(Directly verified, records.)* Cross-tabulating the
  submitted designs in the v6 arms:

  | robust-seed displacement status (16 pairs) | final verdict on 24 validation pairs |
  |---|---|
  | WORSE (16 designs) | WORSE 15 |
  | VERIFIED (61 designs) | VERIFIED 59 |
  | NOT_VERIFIED (27 designs) | NOT_VERIFIED 23 |

  The fresh re-measurements in `ds1_stopdata` (678 init-base designs) agree: robust-seed WORSE → FULL 0/32.

  So the displacement-only failures are mostly *not* seed-generalisation failures. The design was already measured as worse than
  the faulty robot on policy-visible seeds, and stop map v2 rated it low. FA-1 called this "the engine knows". It was submitted
  because nothing better was found.
- **A2. Mechanism behind the 20 displacement-only arm-episodes (7 instances).** *(Directly verified, records + code;
  interpretation flagged.)*
  - **Leg shortening.** 11/20 submitted designs have legs shortened to ×0.67–0.76, in 4 instances (heavy_torso:0,
    heavy_torso:2, low_ground_friction 0073:0, comp 0137).
    - Across all 144 submitted designs, legs ≤ ×0.85 occur 12 times: **0 FULL**, 11 displacement-only, 1 walking failure.
    - Legs ≥ ×1.15 occur 17 times: 8 FULL.
    - *Interpretation:* shortened legs make the body-relative walking label easier to reach, which the CMA's walking-count-first
      objective rewards, while absolute displacement falls.
  - **Faulty comparator.** In the same episodes the faulty robot does not walk. Its eligibility labels are `contact_chatter`
    (low friction) or `falling_forward` (heavy torso). Under `walk_score`, a non-walking robot that keeps ≥ 1 valid step and does
    not fall within 1 s is still credited its upright forward displacement.
  - **Size of the gap.** Robust-seed median paired differences are −0.9 to −2.8 m.
  - *Interpretation:* "walks but travels less far than a moving, non-walking faulty robot" is directly observed on robust seeds.
    Whether that is a genuine repair failure or a property of the pre-declared criterion is a definitional question, not a
    measurement error.
- **A3. Near-threshold walking failures (38 arm-episodes, 15 instances, validation 17–19/24).** *(Directly verified, records.)*
  - 25/37 of these designs already had a robust16 of 9–14 and were submitted after the budget was spent.
  - If the validation walking rate equalled robust16/16, the expected count would be 18.9/24; the observed mean is 18.1. The
    lower-tail binomial probability is < 0.05 in 13/37.
  - Shrinkage across all submitted designs: robust16 15–16 → validation rate 0.967 → 0.901; robust16 12–14 → 0.837 → 0.797.
  - *Interpretation:* the robust → validation drop is modest and consistent with selection on noisy 16-seed estimates. It is not
    evidence of a condition mismatch, which the code excludes. The large drop is earlier: train 4/4 → robust16 ≥ 15 only in
    52/138 plant steps (FA-1).

## Missing records (Directly verified)

- **Serialisation boundary.** `scripts/hdb_agent_run.py:126-127` keeps only `status`, `walking_frac`, `reasons` and `rollouts`
  from `recovery.assess`. That discards:
  - `validation.original` and `validation.candidate` (24 per-seed rows: score, walking, `forward_disp_upright`, label);
  - the verdict's wins, losses, ties, `median_diff` and p-values;
  - the per-seed confirmation rows.
- **Search coverage.** None of these survive in:
  - `artifacts/vm/ds1/eval`;
  - `artifacts/vm/hdb/artifacts/hdb/ds1` (stream);
  - the logs, which hold one summary line per instance;
  - `ds1_all.tgz` (stream-scanned: 0 `median_diff` or `p_one_sided` fields).
- **Robust-seed scores.** Per-seed robust *scores* (`EvidenceWorkbench.scores`, `_baseline`) are not serialised either. Only the
  status and median of the displacement evidence survive.
- **Recoverability.**
  - From existing records: final verdict status, validation walking count (from `walking_frac`), robust-seed displacement
    status/median, robust walking counts, faulty-robot eligibility labels (8 check seeds) and submitted bodies.
  - Requires new simulation: faulty versus candidate per-seed validation distances and win/loss counts, and therefore whether
    any NOT_VERIFIED case failed on the sign test or on the 0.5 m minimum effect.
