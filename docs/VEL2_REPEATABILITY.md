# VEL-2 independent verification repeatability

26 October 2026. **The frozen Stage A reliability gate failed.** The same exact
15 known development candidates were assessed on their original panel and two
new globally disjoint full-verifier panels. All30 new records completed with
zero simulator errors; no candidate, controller, plant or threshold changed.

Only **9/15 (60%)** bases retained a binary FULL/non-FULL label across all three
panels; six changed. The frozen requirement was >=12/15. A Wilson95% binomial
reference for this selected15-base fraction is **[35.75%,80.18%]**. This is small-N
descriptive uncertainty, not an IID population guarantee. Pairwise FULL agreement
was33/45=73.33%, below85%; the45 pairs are correlated within15 bases.

## Requirement-specific reliability

| Requirement | Agree / observed panel pairs | Agreement |
|---|---:|---:|
| FULL/non-FULL |33/45|73.33%|
| Independent improvement |45/45|100%|
| Validation walking |37/45|82.22%|
| Confirmation walking, both panels executed |29/33|87.88%|
| Confirmation median speed, both executed |33/33|100%|
| Confirmation contact, both executed |31/33|93.94%|

Improvement and validation-walking agreement pass their separate80% gates.
There are seven persistent FULL bases (>=3 required), but only two persistent
non-FULL bases (>=3 required). Completeness/error checks pass. Thus three
readiness checks fail: all-panel FULL agreement, pairwise FULL agreement, and
persistent-failure support. No alternative grouping or stable-only cohort is
substituted for the original gate.

## Every base, without favorable selection

F=FULL_RECOVERY, P=PARTIAL_IMPROVEMENT, N=NOT_RECOVERED. Counts show walking
seeds out of24. A dash means confirmation was not run, not failed.

| Known base suffix | Family | Original / new1 / new2 | Validation walking | Confirmation walking |
|---|---|---|---|---|
|0004|low_ground_friction|N/N/N|15/20/17|—/—/—|
|0011|feedback_gain_loss|F/F/P|20/22/19|21/21/—|
|0013|heavy_torso|F/F/P|21/22/23|21/20/19|
|0024|clock_fault|F/F/F|24/24/24|24/24/24|
|0028|clock_fault|F/F/F|23/24/22|22/21/23|
|0030|pitch_sensor_bias|F/P/F|22/17/21|24/—/21|
|0036|short_feet|F/F/P|22/24/22|23/23/19|
|0037|pitch_sensor_bias|P/F/F|18/23/21|—/20/20|
|0038|low_ground_friction|F/F/F|21/22/20|23/20/23|
|0039|heavy_torso|F/F/F|23/20/24|24/22/23|
|0040|payload_offset|P/P/P|16/19/19|—/—/—|
|0044|feedback_gain_loss|F/F/F|22/24/22|22/22/21|
|0052|clock_fault|F/F/F|24/22/24|24/24/24|
|0054|feedback_gain_loss|F/F/F|23/20/23|23/21/23|
|0064|payload_offset|P/P/F|23/24/23|23/22/24|

All IDs have prefix `hdb-v1-gen-`. Exact candidate identities and source unit
hashes are frozen in stage_a_cases.json. On0004 the paired-improvement verdict
is WORSE on all three panels; its walking threshold crossing does not rescue
FULL. On0040 validation walking fails on all three panels. These are persistent
physical/verifier weaknesses in the measured conditions.

Three discordant bases (0011,0030,0037) cross validation walking requirements;
two (0013,0036) cross the20-second confirmation-walking requirement. On0064,
contact fails in the original and first new confirmation panel (one violating
seed each), then passes in the second new panel. Independent improvement is
VERIFIED_IMPROVEMENT for all three panels on every other base: **14/15**.
No improvement verdict changes and no speed requirement fails.

## What changes, and what remains unidentified

FULL totals are11/15,11/15,10/15 across the three panels. Similar aggregate
recovery fractions therefore conceal substantial case-specific label changes.
In controls,3/6 labels persist and totals are5/4/3; in the historically failed
cohort6/9 persist and totals are6/7/7. Family all-panel agreement is clock3/3,
feedback2/3, heavy1/2, friction2/2, payload1/2, pitch0/2, short_feet0/1. These
tiny strata are descriptive only, not tuned subgroups or family-transfer tests.

The observed discordance is consistent with sensitivity to the seed-sampled
perturbation/condition panel and threshold margins, with design and plant fixed.
This does not establish nondeterministic MuJoCo, a population noise floor or an
irreducible inability to predict risk. Three panels/base cannot estimate a
precise per-candidate failure probability or separate every source of variation.
Per-seed traces retain scores, walking, displacement, speed, contact, steps,
fall information and conditions; no artificial outcome replaces physics.

VEL-1's predominant apparent-success failure was independent improvement
(17/27). This R0 selection has only **one** persistent improvement-failing base.
Consequently its perfect observed improvement agreement is encouraging for
measurement consistency but supplies insufficient failure diversity to validate
an improvement-risk learner. R0's3000-rollout policies, select8 event and enriched
case selection differ from VEL-1's adaptive700-plant robust16 event. The new
walking/contact variability cannot be extrapolated to explain all VEL-1 failures.

The legitimate stopping point is the frozen Stage A failure. Stage B is not
run; no new physical/state-versus-history prediction contrast or warning-action
effect is inferred from these repeatability measurements.
