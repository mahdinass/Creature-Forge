# EM-1 feasibility — source and identifiability audit

Status: G0 measurement complete. **EM-1 NOT EVALUABLE / NO-GO** for further
implementation with the current repair-decision evidence. All 804 interventions
were retained; results are in `docs/EM1_RESULTS.md`. Plan: `docs/EM1_PLAN.md`.
Branch from R0 `8e7e824`.

## Reconciled prior evidence

- E-1: the primary A1–A0 contrast did not reject its null. Diagnosis ablation met
  the registered secondary family only. Already-published E-1 summaries inform
  the question, but its robot records/outcomes are not training, tuning or method
  selection data for EM-1; no held-out or sealed loader is used.
- RL-1: 2,110 per-tool outcomes on 211 development instances gave complete tool
  support but did not beat the engine ranking. Its per-tool repaired designs are
  not the designs whose twin screen scores were saved. Their difference is not a
  physical prediction residual. LOFO also leaves the held-out family's mechanism
  in the twin hypothesis library; it is not an unknown-physics experiment.
- DS-1: a better-calibrated diagnosis and success prediction did not improve
  verified repair. Its relative cross-feedback could not move a belief when all
  hypotheses predicted the same repair response. In the non-LLM dev-eval report,
  the leader never changed in 88 assimilations. This suggests checking absolute
  response discrepancy rather than relabeling tool success as model correction.
  Saved assimilation counts also choose the best particle within each structure
  after incorporating the check; without the missing cache they are not clean
  prospectively frozen pre-outcome forecasts for an experience learner.
- R0: all 324 units valid, registered advancement gate failed. Some joint repairs
  worked, but no sufficiently robust net/control-protected gain. This neither
  proves no model mismatch nor makes unresolved robots physically irreparable.

## Audited development data

Explicit sources are `fresh_A1c5.jsonl` (SHA-256
`3bde2b77676fd3d46592bb9ad50250ecfc8614376d6676b87d59f2a97d2149cb`)
and `vs5_A1c.jsonl` (SHA-256
`e2ee1d53cdf81f2395a065c1b017ffc885b045fb533467b04a661429834ea520`).
They contain 356 rows: 324 eligible non-LLM v5 episodes and 32 ineligible rows.
There are **30 independent robot bases and nine development families**, not 324
independent robots. The files are read-only existing artifacts; exact row hashes
identify every source observation in the prepared input archive.

The repair logs have 866 checked design-index entries. Deduplication by exact
episode/model/design identity collapses 62 entries: **804 distinct interventions**
and **11,632 aggregate robustness-seed responses**. Repeated indices and nested
8/16-seed checks do not count as independent evidence. There are 48 episodes with
one distinct checked design, 72 with two and 204 with three. Count equality and
nested-prefix compatibility are mandatory. Original inventory/protocol and the
interrupted 17-record run are retained with engineering amendments.

All 324 original submitted designs have an independent FULL result; **480
unsubmitted distinct designs do not**. The learner must never inherit a FULL
label from another design or infer one from walking fraction. The old log saves
walking counts, not individual robustness-seed outcomes, so no artificial
per-seed plant labels are created.

## What can be paired legitimately

`Particle.as_dict()` omits `seen`, and `Episode.record()` omits experiment design
objects from the diagnostic log. Original prediction caches are absent in all
324 v5 records. Twin-CMA walking scores use its training seeds, not the actual
plant robustness seeds. They are not exact paired residuals.

However, the v5 diagnostic posterior is unchanged during repair; retained
particle parameters/log likelihoods and the last diagnostic snapshot reconstruct
its full-precision repair hypothesis set. The auditor recomputes the existing
`Episode.ensemble(k=8)` cyclic hypothesis/nuisance model on the exact saved
candidate, original robust seed namespace, 10-second horizon, variation preset
and walking classifier. This extension of a frozen model to a saved intervention
is a legitimate retrospective physical prediction measurement. It is not evidence
that the original engine logged that forecast before the observation.

Neither the observed walking count nor FULL status/family metadata enters the
predictor. The source instance key is trusted seed-routing metadata, never a
learner feature. Later learner features would require a separate explicit
numeric whitelist. Family labels may stratify evaluation only. Outcome-updated
posteriors and missing/inconsistent ledger entries are rejected.

Two development fixtures matched the frozen ensemble evaluator's walking counts
and mean fitness (48 extra engineering twin rollouts). Twelve new guard tests
pass locally and on the existing VM environment. Physics, engine, verifier and
prior frozen experimental source remain unchanged.

## Decision support and three bottlenecks

1. **Model mismatch:** a same-design/same-seed response discrepancy is directly
   measurable after the twin-only audit. Base-clustered bias/intervals and family
   descriptives will quantify it. The aggregate Bernoulli Brier score can be
   calculated exactly from a walking count; this does not recover missing
   individual trajectories or measure the FULL endpoint.
2. **Search failure:** these candidate sets were generated adaptively by B0's
   diagnosis, twin search and subsequent plant optimization. An alternative tool
   that B0 never explored has no same-procedure counterfactual. A new residual
   ranker over the post-policy candidate set is not the original engine and
   cannot establish what its earlier changed decisions would have produced.
3. **Repair capability:** absence of FULL among observed candidates is bounded
   search evidence, not a physical impossibility claim. R0's three all-arm failed
   cases are a relevant warning, not causal training labels for model mismatch.

The audit compares both a reconstructed twin-only ranking and the actual
engine's final robust-walking choice with the best **observed** candidate. The
former is explicitly an audit ranker, not B0; B0 can already use real robustness
checks and a calibrated stopping map. Improved prediction/ranking must not be
mistaken for incremental information or verified recovery improvement.

Completed audit: base-equal observed minus predicted robustness walking is
0.05185, descriptive 95% cluster interval [0.01581,0.08973]. Prediction mismatch
is real in this selected cohort. However, the original engine's walking regret
against its best **observed** design is zero in all 324 episodes. A raw twin-only
audit ranker changes 86 submissions, with lower measured walking in 54 and ties
in 32. FULL is unknown for all 86 changed choices. Thus neither generic bias
correction nor this post-policy candidate panel identifies a useful earlier
repair decision. The data are sufficient to describe a physical discrepancy,
but not to validate the proposed experience-dependent recovery mechanism.

An additive average correction preserves candidate ordering before clipping;
nonzero bias alone does not show a repair benefit. Rich targets such as speed,
displacement, contact and long-horizon stability would require matched plant
measurements not retained in these robustness logs. Walking alone also fails
to distinguish the unchanged verifier's improvement and confirmation criteria.

## Precision and prospective feasibility

Thirty base clusters bound historical precision regardless of 11,632 repeated
seed responses. Report base-equal summaries and descriptive 10,000-draw cluster
bootstrap intervals. Do not use in-sample fitted residuals as transfer evidence.
Family strata and fixed candidate availability are descriptive.

Before any prospective launch, select a scientifically useful minimum effect,
estimate discordance from an independent comparable development pilot, and run
finite-sample base-clustered paired power simulations. The audit includes planning
sensitivity for 5/10/15 percentage-point effects and discordance assumptions
0.2/0.4/0.6; these are not tuned empirical effect estimates or a registered
prospective gate. Multiple mechanisms on one base do not multiply sample size.
Account for B0/B1/B2 and B3, physical checks, full verification, all model calls,
method selection, 25% runtime margin and already incurred task cost. No reduced
or underpowered prospective study will be presented as success.

For illustration only, with one paired binary problem per independent base,
a 10-point FULL difference at two-sided 5% and 80% power needs approximately
150/307/464 independent bases for discordance
0.2/0.4/0.6. Discordance of B1 versus B0 is not estimable here because no B1
policy has been run and alternative FULL results are missing. Even the optimistic
150-base, three-arm full-cap allocation (3,596 rollout equivalents per episode)
is 1,618,200 equivalents: about 6.31 hours at the earlier public R0 48-worker
probe throughput of 71.24/s, before 25% margin or already incurred task time.
This is a conservative planning envelope, not a measured EM-1 runtime forecast
or a proof that no early-stopping design could fit. No powered prospective run
was justified or launched; selecting favorable discordance/early-stop assumptions
would not resolve identifiability. Four mandatory-control arms cost still more.

## Research context

Learning a simulator's limitations from solution descriptors and measured
simulation-to-physical discrepancies is established work, rather than a novelty
claim for EM-1. The [transferability approach](https://arxiv.org/abs/1307.1870)
motivates evaluating the disparity on identical solutions; its quadruped result
does not establish transfer between Creature Forge's damaged robot bodies.
The [reset-free damage recovery study](https://www.sciencedirect.com/science/article/pii/S0921889017302440)
uses trial-and-error and precomputed behavior alternatives; it does not license
learning from mismatched interventions or assuming FULL gains from calibration.
The relevant EM-1 distinction is a deployed, decision-time prediction correction
with matched-information controls and independent recovery verification.
