# VEL-1 feasibility analysis plan

26 October 2026. Branch `codex/verification-experience-vel1-feasibility` from
DI-1 completion `4908493`. Feasibility only: stored development evidence,
lightweight audit/statistical utilities, no production learner, deployment,
sealed outcomes, release changes or automatic next experiment. No inference
calls. No paid measurement is currently needed; any later strictly necessary
Cloud measurement requires fresh credit verification and the $5 ceiling.

## Information boundary and target (frozen before fitting)

Prediction time is the original engine's final candidate submission, before
`hidden_plant.verify`. Training optimization, robustness checks and any charged
stress check are allowed; validation and confirmation fields are never features.
After verification, that outcome may be history for a different training base.
The main target is failure of independent `full_recovery_v1` for a submitted
candidate. Errors remain missing/inconclusive, not negative recovery labels.

Primary apparent success is the existing provisional accept criterion:
**at least 15/16 walking on a final selected candidate's 16-seed robustness
check** (`belief_engine.provisional_accept`). No threshold is chosen by learner
scores. Report all submissions and this prespecified subset. Secondary source
strata retain their own observation definitions: R0 at least7/8 on selection;
RL-1 at least4/4 plant training walking; legacy stop calibration is a separate
retrospective measurement panel. These are not interchangeable confidence events.

Failure requirements are audited separately: validation improvement verdict,
validation walking PASS, confirmation walking, speed and body contact; multiple
reasons may overlap. Confirmation not run is structurally missing, not a passed
or failed longer trial. Never define apparent success from 23/24 validation.

## Explicit development populations

- Primary: `fresh_A1c5.jsonl`, the existing v5 development cohort (18 nominal
  bases; 211 eligible episodes in prior reports). It is disjoint in nominal
  base identity from the 12-base `stopcal.jsonl` fit of the original stopping
  map, subject to physical-design hash verification. Existing map evaluation
  on its own legacy training bases is not out-of-sample evidence.
- Secondary: `vs5_A1c.jsonl` (same v5 policy, legacy bases), the RL-1 dev matrix,
  frozen R0 units, DI-1 pilot v1/v2 (same five bases, deduplicate repeats),
  historical stopping-calibration panel and EM-1 paired audit inventory.
  Audit separately; do not pool strategies, budgets, candidate sampling or
  retroactively measured features as if one new prospective population.
- EM-1 reuses these historical submissions; its reconstructed twin predictions
  were made after the original outcomes, so are not historical decision features.
  It supplies an inventory/missing-label check, not extra independent robots.
- Primary paths are explicitly named and development-only. Read published E-1
  report for context only; no E-1 raw/sealed/reserve loader.

Track exact file/row hashes, physical nominal/candidate hashes, base IDs,
damage instances, selected versus alternative labels, repeats, seed roles and
policy/verifier versions. Collapse exact duplicate primary physical observation
identities or fail on conflicts; never randomly split episodes of one base.
Report distinct numerical morphology separately from reused parent lineage.

## Predictors fixed before outcomes are scored

Allow only the selected design's logged robustness fraction/check size,
same-design train4 fraction, same-design twin8 fraction, charged stress4 fraction,
pre-repair posterior MAP mass/normalized entropy, diagnostic experiment count,
remaining plant fraction, number of checked designs, accepted stopping flag,
and mean initial damaged-plant walking/slip/capture-margin/ankle-saturation.
Use robust/twin disagreement only when both refer to that same candidate.
Counts/fractions must use verified denominators; no invented values or repaired
candidate contact metrics from the verifier. Missing fields remain explicit.
Gold family, severity, instance/base IDs, fault parameters, policy success,
FULL/validation/confirmation and retrospectively reconstructed EM-1 forecasts
are prohibited predictors. Family is only an evaluator grouping label.

Primary fitting uses all valid primary submissions; scores are reported both
overall and on the apparent-success subset. Features are fixed in advance;
no feature selection or hyperparameter search on evaluation folds.

## Frozen lightweight comparisons

- Constant: base-equal failure prevalence from outer training bases only,
  Jeffreys smoothing. Never an all-data prevalence.
- V0: uncalibrated failure1−robust fraction, and the existing Beta-tail walking
  reliability heuristic. These are not claimed to be P(FULL). Also report the
  original frozen calibrated stop-map probability where actually logged for
  this selected design; its complete-case coverage is explicit.
- V1a: ridge-logistic calibration of robustness fraction/check size only.
- V1: ridge-logistic combination of the permitted physical/state features.
  Reuse the existing stopping-calibration Newton solver; fixed ridge1,
  training-fold median imputation and missing indicators, training-fold scaling,
  base-equal sample weighting. Numerical safeguards do not change the method.
- V2 (conditional feasibility analysis if V1 suggests predictive signal): V1
  plus a shrunken nearest-experience residual correction. Build the training
  memory from inner leave-one-base-out V1 residuals, one representative residual
  per training base chosen by observable feature distance to the query; use
  five nearest training bases, shrink by k/(k+5). No held-out-base labels,
  including other episodes, can enter memory or normalization.
- V3: same residual mechanism with the residual-to-physical-experience pairing
  shuffled between training base blocks, 20 fixed seeds. Preserve class/risk
  information and base grouping; report control variability, not a favorable
  single shuffle. This is a history-relevance control, not Nemotron training.

V1 itself learns from historical labels; V2 tests a particular additional local
experience mechanism, not learning versus no learning. Training history is
strictly outside the held-out base. Historical file order is not a verified
real-world chronology; claim grouped offline feasibility only.

## Evaluation, uncertainty and actionability

Leave-one-physical-base-out primary predictions; verify no physical nominal
aliases cross the boundary. Mechanism-family-out sensitivity also excludes
each test base from the training set (dual block), so other mechanisms on the
same robot cannot leak. No hyperparameter/feature tuning on these results.
Report base-equal Brier/log loss, five fixed calibration bins, discrimination
where both classes exist, fixed warning threshold0.5 precision/recall/false
alarms, and risk/coverage at risk thresholds0.1/0.25/0.5 and descriptive rank
coverage50/80/90/100%. No threshold is selected for a favorable result.

Paired uncertainty resamples whole bases (5,000 fixed bootstrap draws), including
all episodes within a base with base-equal weighting. Intervals describe this
historical panel with overlapping training folds, not a confirmatory powered
population test. Report per-base differences, effective base counts and number
of bases containing failures/successes. No seed-level pseudo-replication.

A practical predictive screen is at least0.01 absolute Brier improvement over
both constant and simple robustness calibration with a positive descriptive95%
paired-base interval. An experience screen is at least0.005 further improvement
over V1 and positive paired-base evidence over shuffled control. These are
feasibility screens, not optimized scientific thresholds or a deployed guarantee.
At least10 independent base groups with each outcome represented are needed for
a credible transfer discussion; sparse target support yields insufficient
evidence. Family results and false-alarm costs can override an optimistic mean.

GO requires a credible out-of-base predictive target, usable observations,
support beyond trivial rules, and a defensible route to evaluating relevant
experience and a useful action. A classifier alone never proves improved FULL.
If simple calibrated signals already capture the useful signal and richer/history
methods do not improve, report that rather than rescue the hypothesis. Distinguish
NO-GO (evidence of little practical headroom) from INSUFFICIENT EVIDENCE (target,
experience, causal action or independent precision unavailable).

Assess abstention/uncertainty separately from recovery. Current verification
already controls whether a repair can be called FULL. Alternative submission or
extra investigation requires comparable counterfactual FULL outcomes and charged
interactions; missing labels are not imputed. One fixed verifier outcome per
candidate cannot separate irreducible randomness from predictable vulnerability.

## Deliverables and acceptance

`scripts/vel1_audit.py`, `vel1_analyze.py`, focused leakage/identity/metrics tests;
this plan plus `VEL1_DATA_AUDIT.md`, `VEL1_FEASIBILITY_RESULTS.md`,
`VEL1_DECISION.md`; compact reproducible evidence under development/vel1.
Primary-source literature review including ReAP2026, monitoring, calibration,
selective prediction and uncertainty/planning. Existing theory/methods are not
novel because they use Nemotron or a twin. Recommend a full protocol only if
GO is justified; otherwise specify the smallest meaningful missing-data study.

Acceptance: deterministic re-extraction/analysis, exact source/data checksums,
explicit before-verifier whitelist, duplicate/seed/conflict guards, group-leak
tests, correct metrics/cluster weighting and failure-requirement labels, all
negative results, current API VM states, no paid start or model calls. Commit
and push isolated results; update state/memory, Notion and Basic Memory and
verify readback. No continuation beyond final feasibility without owner approval.
