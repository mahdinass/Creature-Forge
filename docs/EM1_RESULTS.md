# EM-1 results — NOT EVALUABLE; NO-GO at decision identifiability

**Verdict: NOT EVALUABLE for H-EM1. Recommendation: NO-GO for further learner or
online implementation with the current evidence.** The G0 physical measurement
audit completed; the required decision-relevant learning target was not
established. This is not a failed statistical test of a fitted learner, and not
proof that physics correction cannot help. No learner, B1/B2/B3 experiment,
prospective cohort or Nemotron comparison was run after the G0 stop.

The positive finding is a legitimate same-intervention prediction discrepancy.
The limiting finding is that B0 already resolves the observed walking-ranking
problem with real plant checks. Learning the discrepancies currently logged
would target predictions whose outcomes B0 already knows, while evidence for
earlier changed repair decisions is missing. The mission explicitly requires
stopping at G0 when identifiable decision-relevant support is insufficient.

## What was executed

Read-only audit of E-1/RL-1/DS-1/R0 reports and relevant engine/twin/hidden-plant,
verification and experience-memory code; scoped Basic Memory retrieval; then a
new development-only measurement auditor, guard tests, exact-input preparation,
bounded real-VM twin evaluations, base-clustered analysis and evidence checks.
E-1 raw outcomes and sealed/reserve loaders were not used. No earlier frozen
protocol/result, release/PR #20/E-2R or submission file was changed.

Two named v5 files supply 356 rows, of which 324 are eligible non-LLM episodes
on **30 independent robot bases and nine development families**. These are
historical training/audit observations, not fresh prospective test robots. The
866 design-index/check entries contain 62 repeated physical designs/prefix
checks. The corrected audit has **804 distinct physical interventions and
11,632 matched robustness-seed responses**, retaining all source indices.

The predictor recomputes the unchanged diagnostic ensemble on the exact saved
design, original robustness seeds, variation preset, 10-second horizon and
walking criterion. Plant observations are existing 8/16-seed walking counts;
individual seed outcomes were not saved and were not invented. This is a
retrospective extension of a frozen diagnostic model, not a claim that the
original pre-decision forecasts were logged on those seeds. Original twin-CMA
training scores and different RL-1 designs were not used as paired residuals.

## Physical prediction and decision findings

All summaries below use the complete set. Base-equal summaries give each of the
30 bases equal weight; repeated seeds/instances are not independent robots.
Intervals use 10,000 base-cluster bootstrap draws, seed 2026102509. They are
descriptive for this purposive development cohort, not confirmatory population
claims.

| Quantity | Result |
|---|---:|
| Observed minus predicted robustness walking fraction | +0.05185 |
| Descriptive 95% base-cluster interval | [+0.01581,+0.08973] |
| Base-equal squared error of predicted aggregate walking fraction | 0.07460 |
| Aggregate Bernoulli Brier score | 0.19537 |
| Episodes with at least two distinct checked designs | 276/324 |
| Actual B0 final walking regret versus best observed candidate | **0 in all 324** |
| Reconstructed twin-only audit ranker walking regret | 0.04598 |
| Audit ranker changes the original submission | 86/324 |
| Changed choices with strictly lower observed walking / tied | 54 / 32 |
| Changed choices without independent FULL outcomes | 86/86 |

The Brier value is calculable from aggregate walking counts and a constant
fraction forecast per intervention. It is not a score for FULL recovery, a
fitted correction, or a claim of calibrated per-seed trajectories. The twin
underforecasts walking by about 5.18 percentage points on average, with large
intervention-level error. A global additive offset would preserve within-case
ordering before clipping; a bias estimate alone does not establish a useful
repair strategy.

**The twin-only audit ranker is not B0 or a learned B1.** B0 also uses actual
robustness/stress evidence and its stopping map. Its measured walking choice
already attains the maximum in every observed set. This does not imply that
B0 is optimal for FULL recovery, untried interventions or a new cohort. Its
adaptive candidate availability is itself a consequence of the original
policy, so a post-policy reranking cannot identify the full earlier policy effect.

All 324 original submissions have FULL labels: **153 FULL, 80 partial and 91
not recovered**, from the original 700-plant/2,800-twin-cap episodes (109 FULL
of 211 fresh-dev and 44 of 113 older-dev episodes). This is historical
description, not a new controlled B1–B0 contrast. **480 unsubmitted distinct
designs lack FULL labels.** Missing labels were neither excluded to make a
comparison complete nor assigned failure/success.

For the unlearned audit ranker's 86 changed choices, missing FULL outcomes give
logical finite-cohort gain bounds of **−29 to +57 recoveries**, or **−8.62 to
+17.66 percentage points** under equal-base weighting. These are identification
bounds, not confidence intervals or an estimated correction effect. They
illustrate why the unknown outcomes cannot support either a success claim or a
clean null for H-EM1.

## Mechanism-family descriptives

Family labels are evaluation metadata only. No learner saw injected mechanisms.
The following intervals are unadjusted descriptive summaries; no subgroup claim
is substituted for the G0 decision.

| Family | Bases | Interventions | Mean observed−predicted walking | Descriptive 95% interval |
|---|---:|---:|---:|---|
| actuator weakness | 18 | 43 | +0.00579 | [−0.05845,+0.06829] |
| clock fault | 18 | 56 | +0.05307 | [−0.05093,+0.15914] |
| feedback gain loss | 18 | 47 | +0.01157 | [−0.11343,+0.11806] |
| heavy torso | 18 | 44 | +0.05382 | [approximately 0,+0.12269] |
| low ground friction | 27 | 88 | +0.01439 | [−0.04630,+0.07793] |
| one-side weakness | 18 | 83 | +0.03958 | [−0.02454,+0.09826] |
| payload offset | 30 | 172 | +0.06066 | [+0.01665,+0.11134] |
| pitch sensor bias | 30 | 197 | +0.06726 | [+0.02422,+0.11116] |
| short feet | 25 | 74 | +0.08625 | [+0.02583,+0.15458] |

## Learning, controls, negative transfer and power

| Requested component | Actual status |
|---|---|
| B0 original engine | Historical outputs audited; no new engine run |
| B1 experience-corrected engine | Not implemented/run after G0 NO-GO |
| B2 sham-experience control | Not implemented/run; no attribution test |
| B3 simple numerical correction | Not fitted; nonzero average bias is not a repair gain |
| LOBO/LOFO learner evaluation | Not run; no transferred-prediction claim |
| Chronological/prequential learner updates | Not run; no online-learning claim |
| Applicability, abstention and negative transfer | Not estimable for an unimplemented learner |
| Prospective development gate | Not registered/launched; zero new bases |
| Nemotron contribution | **Untested**, zero calls/tokens charged by EM-1 |

It would be invalid to call an untested contribution ineffective or to claim
that experience caused a gain. Likewise, the raw audit ranker's 54 worse
walking choices are not measured negative transfer from a learned correction.
No applicability threshold was invented after seeing results. Training on FULL
labels to rank tools would reproduce RL-1 rather than the requested physical
prediction-correction mechanism.

Thirty base clusters cannot become 804 or 11,632 independent examples. Planning
sensitivity, not a prospectively registered gate: with one paired binary problem
per independent base, a 10-percentage-point FULL difference at two-sided 5%
and 80% power, discordance 0.2/0.4/0.6
requires approximately **150/307/464 independent bases**. The actual B1–B0
discordance and effect cannot be estimated from the missing alternatives. The
registered audit includes 5/10/15-point sensitivity; finite-sample clustered
simulation would be required before any future paid launch.

The optimistic 150-base, three-arm full-budget envelope is 1,618,200 ten-second
equivalents before a 25% margin. Even extrapolating the earlier R0 public
48-worker throughput gives about 6.31 hours before margin and task overhead,
exceeding the six-hour/$12 task envelope. This is a conservative bound, not a
newly measured EM-1 engine-runtime forecast. No favorable variance/early-stop
assumption was chosen to fit an otherwise unsupported prospective experiment.

## Engineering, shutdown and reproducibility

Measurement source: **`f70549d636b5b2141988a9165574c5f53015a6be`**. The isolated
VM checkout reused `/home/forge/dev/venvs/hdb/bin/python`: Python 3.12.3,
MuJoCo 3.15.0, NumPy 2.5.4; six serial workers and BLAS/OMP threads fixed at one.
No environment, dependency, VM or IAM setup was duplicated. Native supervisor,
existing root SA API self-stop/timer and independent Windows watchdog were reused.

Corrected measurement ran **19:07:45–19:20:24 UTC on 25 October 2026**, exit zero;
summed worker time 1.25575 hours. The native analysis completed and API stop was
requested at 19:20:26. Both VMs independently observed STOPPED; a brief bounded
restart retrieved evidence and repeated analysis, then both were independently
confirmed STOPPED again at **19:27:35 UTC**.

Tests: 12 G0 guard tests passed in the actual Linux environment; 13 local guard
tests passed after the post-run path-formatting fix. All 22 existing R0 regression
tests also passed locally with physical rollouts explicitly mocked. Two real
development fixtures matched the frozen ensemble evaluator (48 engineering twin
rollouts). No physics was run on the laptop.

The first driver encountered duplicate physical-input checkpoint ids and waited
on queued executor work after publication failed. Its interrupted 17-record
archive was preserved, with both VMs API-stopped. Amendments 1/2 add fail-fast
error capture and deduplicate identical physical designs/nested checks. All
804 corrected interventions were uniformly rerun in a fresh output. The 17
overlapping predictions reproduce every scientific field exactly except timing.
No favorable outcome or sample was selectively rerun.

The original Linux analysis repeated byte-exactly before retrieval. Local Python
3.11 replay failed the exact-publication guard: after the path-formatting fix,
all identities, hashes, counts and choices match, with 16 last-bit float
differences, maximum **1.77636e−15**. Python 3.12 changed float summation; the
registered Python 3.12 result remains authoritative and was not overwritten.
No numerical calculation or gate was changed to force equality. See engineering
amendment 3 and the portability receipt. This is an explicit reproduction limit,
not a claim of cross-version byte equality.

Full archive: **1,030,524 bytes**, SHA-256
**`dbfc677101a6430ce7fa829d0a3e22ac07697f24b90fae3b9ad5db6317b14236`**.
All **818 manifest entries** verified locally, plus all 27 in the interrupted
archive (SHA-256 `7a3f4657127dc2ece6e0ec867d0b8171cb02cf19ca851da88b6b221b837aab6e`).
Raw archives remain in ignored `artifacts/em1_ops/` and on the stopped batch disk
at `/home/forge/dev/r0-codex/artifacts/`; this is not an independent object-store
backup claim. Small analysis, intervention CSV, gate, source/input/checksum and
shutdown/validation receipts are in `experiments/causal_engineer/dev/em1/results/`.

The 11,632 complete-audit twin rollouts and 48 equivalence plus eight bounded
debug rollouts are recorded. The interrupted executor did some unpublished work,
so **exact total campaign rollouts are unavailable**; timing/ledger totals
include that work. No new plant rollout or model call occurred.

At the final recorded stop, the conservative ledger rose from $117.737 to
$118.834: **$1.097 additional Cloud estimate**, **0.517 paid batch hours** and
0.582 campaign elapsed hours. Token Factory spending **$0**, model calls zero.
This is within owner-verified $26.51/$47 balances and the $12/$3/six-hour caps.
The ledger is not a provider invoice or a verified final account balance; boot
disks continue ordinary storage charges. Paid research ended on 25 October,
well before the 27 October cutoff.

Reproduce the original numerical analysis using Python 3.12 and measurement
source `f70549d` after extracting the archive into ignored artifacts:

```bash
python -B scripts/em1_g0_analyze.py --root artifacts/em1_g0_v2
```

The current utility adds only portable manifest-key formatting; retain the
registered interpreter for exact immutable-output reuse. `SHA256SUMS` protects
raw files; `results/EVIDENCE_SHA256SUMS` and `EM1_SHA256SUMS` protect published
small evidence/docs. Source protocols and all three engineering annotations
remain available. Final decision and data requirements: `docs/EM1_DECISION.md`.
