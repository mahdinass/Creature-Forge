# VEL-1 development data and timing audit

26 October 2026. Source authority is immutable development records and the
executed code, with published reports for context. Plan frozen/pushed as
`63df2c1` before fitting; audit/models and 12 guards preserved as `8c65b44`.
No E-1 raw evaluation, reserve, release work or prior scientific record changed.

## Prediction time and legal observations

`scripts/hdb_vs_run.py:run_a1` calls `Episode.diagnose`, then `robust_repair`,
selects the candidate, and only then calls `hdb_bench.verify`. Verification
cannot choose the original submission. The engine record is serialized afterward,
but source code and logs establish which fields already existed before verify.

| Stage | Available information | Use in VEL-1 |
|---|---|---|
| Diagnosis of damaged robot | Initial walking, slip, capture margin, saturation, hypothesis likelihoods, diagnostic probes | Permitted predecision context |
| Candidate optimization | Four-seed plant training counts; eight-seed twin counts when saved for that exact design | Permitted, with explicit missing fields |
| Original robustness/stop decision | Same-design robust8/16, charged stress4 at 20 s when eligible, budget, checked designs, accept flag, sometimes mapped P(FULL) | Permitted, before independent verification |
| Submission | One exact body/controller candidate committed | Prediction point |
| Independent validation | 24 paired original/candidate 10 s seeds, improvement verdict and walking PASS | Targets only, never predictors |
| Conditional confirmation | 24 disjoint20 s seeds; walking, median speed, body contact | Targets only; not-run stays missing |
| Later verified episodes | Past labels from training bases only | Grouped offline experience bank; no claim of recovered real-world chronology |

Historical v5 does not assimilate repair checks into its diagnosis. The auditor
rejects unsupported engine versions or an outcome-updated check experiment.
Original candidate-local log/ledger identity supports robustness and stress
evidence; no final verifier measurement is borrowed as a candidate feature.
Deterministic historical routing checks324 instances for disjoint seed roles,
matching original observation seeds and absence of verifier seeds in decision
experiments. No plant is reconstructed or simulated for this check.

The current verifier requires both independently verified improvement and
walking PASS, then harder confirmation. It already prevents an unverified repair
from being labelled FULL. A confident diagnosis is not P(FULL), and a high
candidate walking count is not a verified success claim.

The baseline is already verification-aware in a limited sense: `eng_tools.py`
documents adding the charged20 s stress check after earlier high-training-walking
repairs failed confirmation; the learned stopping map was then fitted on a
separate development panel. VEL-1 tests additional predictive headroom and
history relevance, rather than claiming to introduce that basic idea.

## Frozen apparent-success event and labels

Primary apparent success is **selected-candidate robust16 ≥15**, taken from the
existing provisional accept rule, frozen before model scores. It does not use
independent validation walking, observed failure rates, a favorable subgroup or
an optimized threshold. The actual historical A1c5 policy used a learned stop
map at tau0.75; this audit's apparent-success event is a measurable physical
condition, not a claim the engine issued a false FULL verdict.

Target is subsequent non-FULL, excluding simulator errors. Requirement labels
are separate and may overlap. A NOT_RECOVERED record alone is not included as
misleading apparent success unless the predecision condition also held.

DI-1 base003 illustrates why timing matters: original robust16=16 and later
NOT_RECOVERED; raw-EIG robust16=14 (outside the frozen apparent-success subset)
and later PARTIAL; random robust16=16 and later FULL. Both original/raw later
walked23/24 in validation. Those validation counts are future outcomes, not
legal apparent-success inputs. The raw path's confirmation failure is retained
in the overall failure inventory rather than changing the subset to include it.

## Cohorts, duplicates and effective sample size

Rows below are distinct instance/candidate/verification-condition identities
after exact deduplication. They are not independent robot counts. Source methods
and budgets differ and were **not pooled for fitting**.

| Development stratum | Saved records before dedup | Distinct labelled candidates | Nominal body groups | Instance IDs | FULL / non-FULL | Apparent events / non-FULL |
|---|---:|---:|---:|---:|---|---|
| Primary fresh v5 A1c5 | 211 eligible | 211 | 18 | 211 | 109 /102 | 115 /27, robust16≥15 |
| Legacy v5 A1c | 113 eligible | 113 | 12 | 113 | 44 /69 | 50 /19, robust16≥15 |
| RL-1 exhaustive tool matrix | 2, 110 | 2, 105 | 18, reused primary | 211, reused primary | 381 /1, 724 | 903 /566, train4=4 |
| R0 coordinated search | 324 | 320 | 18, reused primary | 18, reused primary | 157 /163 | 184 /60, select8≥7 |
| DI-1 saved v1/v2 arm records | 30, including baseline copies | 11 | 5 local perturbed draws | 5 | 7 /4 | 7 /1, robust16≥15 |

Nine fresh and 23 legacy ineligible rows are retained in source inventories and
excluded before model fitting. No errors occur in the valid primary labels.
RL-1 has five exact duplicate submissions, R0 four and DI-1 nineteen saved-arm
duplicates/copies. Conflicting same-identity labels fail the audit. Counts do
not include additional technical equivalence repeats as new candidates/bases.

The union is **35 distinct nominal numerical bodies and 329 recorded instance
IDs**, not18+12+18+18+5 independent cohorts. DI-1's five numerical draws descend
from known development parents; this is not35 unrelated morphology lineages or
35 IID evaluation robots. Primary analysis has18 base groups overall and **17
with apparent-success decisions**. Of those17, 14 have an apparent failure and
all 17 have an apparent success. The apparent class balance is 88 FULL /27 non-FULL.
Episode-weighted failure is 23.48%; primary base-equal failure is 24.83%.

Existing stopping calibration has668 measured rows on 12 legacy bases, 79 FULL
and 589 non-FULL, with 593 distinct source/origin index keys. Numerical candidate
identity is not serialized there, so593 is not asserted to be593 distinct
physical repairs. Its features were remeasured retrospectively in a separate
panel, not necessarily observed by the original policy. All12 nominal base IDs
are mapped to the legacy originals; exact original body hashes are disjoint
from the18 primary bodies. Thus the frozen stop map can be a primary reference,
while testing it on its own legacy bases cannot establish new-base calibration.

EM-1's804 paired designs reuse the same30 historical bases and original labels.
Its forecasts were reconstructed after original outcomes and are excluded from
historical decision features. Its480 alternative designs without FULL remain
unlabelled. It contributes **zero new independent bases** to VEL-1.

## What actually fails

Counts overlap; confirmation nonobservation is not a failure label.

| Requirement failed, primary | All211 submissions | Apparent115 |
|---|---:|---:|
| Independent validation improvement | 50 | 17 |
| Independent validation walking | 63 | 6 |
| Longer-confirmation walking | 13 | 5 |
| Longer-confirmation median speed | 0 | 0 |
| Longer-confirmation body contact | 2 | 1 |

There are102 total non-FULL and 27 apparent non-FULL submissions. Independent
confirmation did not run on 88 total submissions, including 22 apparent ones;
the latter already failed a validation requirement. Only five apparent
confirmation-walking failures and one contact failure are insufficient support
for transferable, separately fitted mechanism-specific risk models.

The v5 writer retained compressed verification status, walking fraction, reasons
and rollout counts; **zero primary/legacy records retain complete per-seed
verifier arrays**. The requirement audit follows the exact recovery source logic
and saved reasons, rather than inventing seed responses. R0 retains full verifier
arrays for 320 distinct candidates and DI-1 for 11. RL-1 retains status and validation
walking but omits requirement reasons and confirmation details; its missing
component counts are unknown, not zero. One saved verifier seed panel per exact
candidate does not identify its across-panel failure probability or distinguish
irreducible simulation variation from predictable vulnerability.

## Features and missingness

Sixteen fixed feature columns plus training-fold missing indicators: selected
robust fraction/check size; same-design train/twin/stress walking; posterior
particle MAP weight and normalized entropy; diagnostic count, remaining budget,
checked-design count and accepted flag; initial damaged-plant walking, slip,
capture margin and ankle saturation; same-design twin/plant walking gap.
No gold family, severity, fault, base identity, validation or FULL field is a
model input. Family is an evaluator-only label for blocked sensitivity analysis.

Of211 primary rows, 56 lack selected-candidate train counts, 152 lack saved
same-design twin counts/gap, and 87 lack stress counts. Robustness and initial
observations are complete. The frozen stop-map probability is available for 124
total submissions and 101 apparent ones; it is not imputed for the rest. Its
missingness follows the original eligibility/budgeted stress logic and is
selective. A policy-visible missing flag is allowed, but is not an observed
physical response or a random missing-data assumption.

Binary-seed variance can be derived from a walking fraction; detailed selected
candidate response variance/contact trajectories are generally not retained
preverification. Candidate-specific improvement margins against a robust-seed
damaged baseline are absent from these v5 summaries. Using independent validation
improvement to supply that predictor would leak the target. The initial damaged
plant responses are not the repaired candidate's stability measurements.

## Provenance and preservation

Primary source SHA-256
`3bde2b77676fd3d46592bb9ad50250ecfc8614376d6676b87d59f2a97d2149cb`;
legacy source `e2ee1d53cdf81f2395a065c1b017ffc885b045fb533467b04a661429834ea520`.
RL-1 archive `9b740a946231d7bf98967d28a641de320831e346048a59da5eaff89434c96b2a`
and its inner matrix manifest verified. All324 consumed R0 unit hashes match
the original manifest; all 30 consumed DI-1 saved submissions match their original
manifests. Exact files/rows/design identities, duplicate mappings, observations,
folds and prepared inputs are linked in development `vel1/results/` and the
reproduction commands. Existing raw archives remain unchanged. No missing FULL
outcome, simulator pose or physical verdict was generated or imputed.
