# DI-1 completed engineering pilot and feasibility decision

25 October 2026. **G-DI1: NOT EVALUABLE. Recommendation: NO-GO for an
experience-guided investigation implementation on this evidence.**

Instrumentation and real-MuJoCo counterfactual measurement worked. One of five
eligible bases had a missed FULL recovery opportunity under the original caps,
found by the random-probe control. Raw EIG did not identify that rescue. The
pilot cannot establish prevalence, predecision predictability or transfer with
the required precision. A conservatively planned three-path prospective study
forecasts 43.78 additional VM hours and $92.69 Cloud, beyond the authorized six
hours/$12. No prospective evaluation cohort was generated or run.

This is the mission's insufficient-information/resource stop, not a failed
powered evaluation or a null test of experience learning. The original pilot
registration and all amendments remain intact. See [decision](DI1_DECISION.md),
[protocol](DI1_PROTOCOL.md), [plan](DI1_PLAN.md) and
[instrumentation](DI1_INSTRUMENTATION.md). All numbers below describe the
engineering pilot unless explicitly labelled as a forecast.

## Population and independent units

Eight morphology attempts were frozen before physics in
`experiments/causal_engineer/dev/di1/pilot_config.json`. Each uses an independent
seeded draw from 18 explicit development nominal parents and seven unrounded
body perturbations within ±3%; the parent's controller is retained. These are
new numerical bodies/IDs in a new namespace, in a narrow neighborhood of known
development designs. They do not establish broad morphology or family transfer.
No sealed record was opened to check for collisions. Config SHA-256:
`3258f1df4ff74ca2787a0f9c1d26c3948c5947ac113871aa1518ffee145e9fe4`.

Indices 1, 2 and 6 failed the predeclared nominal walking qualification and were
retained without replacement. Five eligible independent bases (0, 3, 4, 5, 7)
completed every policy. Existing development failure-family generation and
threshold qualification were used; hidden mechanisms and evaluation seeds
remained trusted evaluator metadata. The five bases appear in both pilot
versions. Alternative paths, validation seeds and equivalence repeats do not
increase the independent base count. There are **zero prospective evaluation
bases**; pilot bases are excluded from any later evaluation.

## Policies and comparable evidence

The original v5 engine uses EIG per rollout to choose a diagnostic probe. V1
changed only its first eligible probe choice: maximum raw EIG or a uniform
nonoriginal choice. Only one of five originals reached this hook; the other
four stopped diagnosis. V1 produced 3/5 FULL for each policy, six distinct final
designs and no rescue. This limited hook coverage motivated engineering
amendment 2, committed before any v2 outcomes.

V2 uniformly applied to all five qualified bases, regardless of v1 recovery:
at the first post-start stopping decision, raw EIG and random each take one
legal scored probe, even if the original would stop. Then the original policy
continues. Ranking, probe and subsequent repair costs all consume the original
700 plant / 2,800 twin caps, with at most six diagnostic experiments. Random is
uniform over all scored actions when the original stops (probability 1/M),
otherwise over nonoriginal actions (1/(M−1)). Candidate panels and origin state
were frozen before the selected plant observation. No other path's outcomes
selected a submission. Raw EIG is a physical information heuristic, without
experience training or privileged labels; random is the uninformative control.

Original baseline records were reused byte-exactly in v2 with SHA references.
All five uninstrumented/instrumented originals matched scientific fields,
ledgers and FULL exactly; a v2 default-policy repeat also matched. This is
observational equivalence on these fixtures, not a universal proof for all
possible robots. Existing baseline, simulator and FULL rules were unchanged.

Across both panels there were **11 distinct submitted physical designs**
(body/vector deduplicated within base), 25 comparison path records after
removing the reused baseline, and 31 actual policy/FULL executions including
six equivalence repeats. Optimizer intermediate and rejected candidates are
retained in raw journals; they are not 11 independent robots or additional FULL
labels. V2 probe panels had 3–14 scored candidates. The complete native analysis,
per-path budgets and walking rates are in the [evidence directory](../experiments/causal_engineer/dev/di1/results/).

## FULL results and negative cases

Base suffixes refer to `di1-pilot-20261025-v1-NNN`. FULL/PARTIAL/NONE abbreviate
FULL_RECOVERY/PARTIAL_IMPROVEMENT/NOT_RECOVERED. Gold families in the CSV are
evaluator-only; they were unavailable to policy decisions.

| Base | Original | V1 raw EIG | V1 random | V2 raw EIG | V2 random |
|---|---|---|---|---|---|
| 000 | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NONE |
| 003 | NONE | NONE | NONE | PARTIAL | FULL |
| 004 | FULL | FULL | FULL | FULL | FULL |
| 005 | FULL | FULL | FULL | FULL | FULL |
| 007 | FULL | FULL | FULL | FULL | FULL |
| Total FULL / 5 | 3 | 3 | 3 | 3 | 4 |

The single missed FULL opportunity is base 003. The original stopped; raw EIG
chose `cf:foot_length@x0.7`; random chose `floor_test@x3`, followed by ordinary
diagnosis/repair. The final independent verifier evaluated the resulting repair
on the original damaged plant and evaluation conditions. It did not grant FULL
for walking on the diagnostic high-friction floor.

All paths used the unchanged paired 24-seed, 10-second validation and conditional
independent 24-seed, 20-second confirmation. Base 003 original validation
walking was 23/24, but it lacked the required verified improvement. Raw EIG also
walked 23/24 in validation and improved its physical response, yet confirmation
walking was 18/24 (75%), below the 80% threshold: PARTIAL. Random validation
walking was 21/24, confirmation walking 23/24, confirmation median upright speed
0.1783 against required 0.1150, and the body-contact gate passed: FULL. A higher
validation walking fraction therefore did not imply better independent FULL.
Full per-seed displacement, falls, steps, contact/stability, improvement verdicts
and confirmation-not-run reasons remain in raw records; no missing responses
were imputed.

This identifies a feasible **allocation path** with a better verified result
on one base. It does not isolate the causal contribution of the floor probe
from subsequent posterior/search/budget changes. It also does not show a
deployable best-of-panel improvement: collecting multiple paths and verifying
them is additional research cost, unavailable as free policy information.

Base 000 is a negative case: the random path reduced validation walking from
14/24 to 6/24 and changed PARTIAL to NONE. Neither alternative lost an original
FULL on the three original FULL bases. These statements concern different
outcome levels; zero binary FULL losses does not mean no physical degradation.

## Predecision signals, uncertainty and learnability

V2 raw EIG changed all five first decisions; the original selected a probe only
on base 004. Recorded permitted signals include physical start/probe responses,
posterior weights/entropy, twin particle predictions, scored candidate sets,
action costs, remaining budget and existing search/repair state. After-observation
assimilation forecasts remain temporally labelled and are not called prospective
forecasts. Missing original forecasts remain missing.

| Base | Original first choice | V2 raw choice | V2 random choice | Posterior entropy | Scored actions |
|---|---|---|---|---:|---:|
| 000 | STOP | foot length ×1.5 | floor ×3 | 0.3411 | 12 |
| 003 | STOP | foot length ×0.7 | floor ×3 | 0.9589 | 3 |
| 004 | weigh | foot length ×1.5 | floor ×3 | 1.9581 | 12 |
| 005 | STOP | pitch reference −0.1 rad | foot length ×0.7 | 0.2280 | 14 |
| 007 | STOP | torso mass ×0.7 | balance gain ×0.5 | 0.0469 | 12 |

Raw EIG versus original FULL difference was 0 percentage points; raw versus
random was −20 points, descriptive base bootstrap 95% [−60, 0]. The original
comparison's [0, 0] bootstrap is degenerate with five tied binary pairs and is
not evidence of zero population variance. Opportunity frequency was 1/5 (20%),
with a binomial reference 95% interval [0.5%, 71.6%]. Raw FULL negative transfer
was 0/5; the corresponding reference upper 95% bound is 52.2%, far above the
planned 10% tolerance.

The fixed family strata, qualification exclusions and five local morphology
draws do not establish IID population sampling. These binomial intervals are
precision/planning references, not confirmatory population confidence claims;
bootstrap resamples whole bases, never seeds or policy repeats. One rescue
cannot establish multiple-base transfer or a predecision predictor. No physical
signal has demonstrated predictive value beyond random here. In particular,
floor probing also worsened base 000. No entropy threshold, successful family
subgroup or always-floor policy was fitted after outcomes. No history-based
applicability or history-ignore mechanism, learner or Nemotron adaptation was
implemented/tested. The result supplies a measured question, not evidence that
an experience-learning mechanism works or cannot work.

## Powered-study feasibility and final gate

The protocol's planning target remains a 10-point useful equal-cap FULL gain;
opportunities ≥15%, lower 95% >5%, at least five independent rescue bases;
predictive policy ≥10 points above random with positive 95% interval; negative
transfer target ≤5%, upper 95% ≤10%. An engineering pilot cannot PASS/FAIL it.

The registered helper uses paired binary contrast power with two-sided 5%
rejection thresholds and conservative pilot discordance uncertainty. It targets
90% power for each original and random contrast, giving at least 80% joint by
the union bound under that working model. Upper 97.5% discordance references
are 0.5218 and 0.7164; the resulting planning counts are 562 and 768 bases.
Use **768 independent evaluation bases** for the resource forecast. Other gate
conditions may need more information, and these are not validated population
parameters or a universal minimum sample size.

Sensitivity (planning N at 90% per-contrast power; >800 exceeds the search cap):

| Useful FULL difference | Discordance .2 | .4 | .6 |
|---|---:|---:|---:|
| 5 points | >800 | >800 | >800 |
| 10 points | 215 | 433 | 645 |
| 15 points | 90 | 193 | 288 |

The useful effect was not increased to make the study fit. Maximum unknown
discordance requires >800 at the 10-point effect. Pilot variance is not set to
zero because one comparison had five ties.

Measured maximum six-worker path wall time was 0.1185277 seconds per charged
equivalent. Eight paths fit 48 CPUs. Forecast three paths/base at their full
700+2800+96 independent-verification equivalent cap, qualification up to 72
equivalents/attempt, 3,137 projected attempts using a conservative qualification
acceptance reference, and 25% runtime margin. Result: **43.7845 hours / $92.6874
additional Cloud**. Remaining authorized time after already spent time and a
finalization reserve was 3.4843 hours. This fails even the full six-hour/$12
ceilings. The model is intentionally conservative for this three-path design;
it does not prove every more efficient future design costs this much. No
defensible powered alternative was established from these five bases within
the present authorization. Stage 3 final evaluation registration and stage 4
execution were therefore not entered. `results/gate.json` records NOT EVALUABLE
and NO-GO, distinct from the immutable pilot analysis's PENDING_FEASIBILITY
stage label.

## Engineering, reproducibility and preservation

Pilot registration `c301887` and Linux byte-manifest amendment `1e0f610` preceded
v1 physics. Uniform stop-decision amendment `2f6031f` preceded v2 outcomes.
Post-run audit fix `2a4f7d4` normalizes legacy threshold tuples and JSON lists
without changing numeric comparisons. All v2 policy outcomes had completed
before this serialization-only audit failure. The failed archive and first 64
replay jobs remain preserved. A new uniform replay of all eight attempts matched
384 jobs with zero physical errors; all 64 overlapping failed-audit jobs matched
exact scientific fields except timing. No policy or FULL outcome was rerun to
repair the audit.

Eight guards passed locally and in the native VM. Independent analysis verifies
hash chains, complete before/after jobs, source provenance, selected candidate
membership, state/panel agreement, sampling probabilities, disjoint seed roles,
physical-cost/ledger equality and unchanged caps. All policy traces have zero
physics errors. Original v1 analysis repeated exactly, and v2 canonical analysis
and stdout repeated exactly in Linux/Python 3.12.3, MuJoCo 3.15.0, NumPy 2.5.4.
No Windows/Python 3.11 exact numerical replay is claimed. Eight-attempt
qualification replay and five baseline equality proofs are in committed evidence.

| Raw archive | Bytes | Verified manifest entries | SHA-256 |
|---|---:|---:|---|
| di1_pilot_v1_1792962569869520185.tgz | 11,447,641 | 86 | 9a8339f1ceab5c9c23f3ebfd89381c0623cbebe2276e17b79759a0e2dee9f2b8 |
| di1_pilot_v2_1792963824025516518.tgz | 14,793,318 | 89 | 09b98c476d5c8a52febc4e3f4d877f0816078488bc4714c1fb6778976e3df5c4 |
| di1_postaudit_v1_1792967688007145654.tgz | 74,714 | 25 | 7525cb7305aaa0d5089da81f20195f12e83e61a867b960cd15bd110361b5a940 |

All **200 manifest entries** and outer archive hashes verified. These are file
checks, not 200 experimental units. Raw archives/traces remain locally under
ignored `artifacts/di1_ops/` and on the persistent stopped batch disk at
`/home/forge/dev/r0-codex/artifacts/`. Small native analyses, CSV, integrity and
generation proofs, source hashes, manifests, receipts, gate and reproduction
commands are committed in `experiments/causal_engineer/dev/di1/results/`.

## Resources and shutdown

Ledger-derived policy costs across all 31 actual executions: 16,454 plant
equivalents, 58,254 twin equivalents, 2,448 independent verification equivalents.
Qualification and replay are additional research-only costs (384 successful
uniform replay jobs plus 64 retained earlier replay jobs). Policy caps are equal;
actual usage differs, as shown in `comparison.csv`. No extra panel outcomes
were free inputs to any policy. No model calls: actual Token Factory spend $0.

Owner-confirmed starting credit was $23.28 Cloud / $47 Token Factory. The
conservative additional Cloud ledger estimate is **$4.124**, with **1.943 paid
batch hours** including setup, interrupted session, retrieval and audit. This is
a start-to-observed-API-stop upper estimate, not an invoice or current-credit
measurement. In particular, native v2 stop was requested at 21:30:28 UTC, but
the laptop's later STOPPED observation conservatively charged the gap. The
original campaign clock and ledger were never reset. Rates/ledger are in the
control-plane receipt; [Nebius pricing](https://docs.nebius.com/compute/resources/pricing)
is the provider reference. Stopped disks retain ordinary storage charges.

The detached native supervisor archived and requested existing SA API stop on
all exits; root deadline protection and the independent Windows watchdog were
retained. Native v1 stop request was 21:09:33 UTC. After v2's audit exit and stop,
a bounded restart retrieved evidence and completed uniform verification, without
policy/FULL reruns. Both main `computeinstance-e01g6rhpgcpnf1bfbr` and batch
`computeinstance-e01efb17k9jbzct0m0` were independently verified **STOPPED** through
the control-plane API at **2026-10-25 22:36:47 UTC (23:36:47 Oslo)**. The
`final_control_plane.json` receipt contains epoch 1792967807.6748226 and both
states. No further paid stage is scheduled. Release, sealed cohorts, prior
frozen studies, PR #20/E-2R and submission work were not changed.
