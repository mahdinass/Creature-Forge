# VEL-2 results — verification reliability

26 October2026. **NO-GO for the tested stable single-panel FULL-label
prerequisite; Stage B was not entered.** H-VEL2's experience-relevance and action
claims remain untested/insufficient evidence. This is a fixed measurement-readiness
decision, not a statistical rejection of all experience learning.

## Registered measurements

Fifteen known R0 development lineages, one frozen apparent-success candidate
per base, original verifier panel plus two new independent disjoint panels.
No new lineages, policy optimization, learner or paid model call. Candidate
selection, seeds, code and gate were committed/pushed as
`e04d3ecc1d6ee56e593eac8aaab0ddf7648f060c` before outcomes.

All30 new assessments completed:21 FULL,7 PARTIAL,2 NOT_RECOVERED,0 simulator
errors. These are repeated assessments of15 candidates, not30 independent
robots. Exactly2,016 new per-seed physical response rows and2,592 ten-second
equivalents were retained, below the2,880 cap. Native physics wall time
182.138 seconds, six workers,64-vCPU existing batch VM; no GPU or new environment.
Environment: Python3.12.3, NumPy2.5.4, MuJoCo3.15.0, BLAS threads1.

| Frozen readiness condition | Observed | Result |
|---|---|---|
|30 complete error-free new panels|30; no simulator errors|Met|
|>=12/15 all-three FULL-label agreements|9/15|Failed|
|>=85% pairwise FULL agreement|33/45=73.33%|Failed|
|>=80% independent-improvement agreement|45/45=100%|Met|
|>=80% validation-walking agreement|37/45=82.22%|Met|
|>=3 persistent FULL bases|7|Met|
|>=3 persistent non-FULL bases|2|Failed|

Three-panel stable-label fraction60%, Wilson95% binomial reference
[35.75%,80.18%]. Selection is historical/enriched and N=15; this reference does
not validate IID population sampling. Pairwise counts are correlated and are
not substituted for independent-base N. Aggregate FULL11/15,11/15,10/15 masks
six case-specific flips. Full per-base table and cause audit:
[VEL2_REPEATABILITY.md](VEL2_REPEATABILITY.md).

Three flips involve validation walking, two confirmation walking, one contact.
Improvement never changes; one base is always WORSE and14 always pass
VERIFIED_IMPROVEMENT. No speed failure occurs. Confirmation executes on12/15
candidates in each panel; missing checks stay missing. Conditional pairwise
walking/speed/contact agreement is29/33,33/33,31/33. No denominator of45 is
invented for unexecuted confirmation checks.

This supports panel-sensitive walking/contact labels on several known cases,
alongside persistent weaknesses. It does not show that VEL-1's predominant
improvement-failure target is unstable: this different R0 sample has only one
improvement-failing base. There is insufficient diversity to establish its
predictability or experience benefit. No stable-only subgroup was selected to
rescue Stage B, and no method/threshold changed after outcomes.

## Prediction and decision relevance

VEL-2 fits/evaluates no V0/V1/V2/V3 model: Stage B's gate failed. Therefore new
Brier, log loss, calibration, AUROC, risk coverage, warning precision/recall and
sham-history increments are **not measured**, rather than zeros or negative
results. Historical VEL-1 V1/V2/sham Brier.1769/.1772/.1757 remains unchanged and
is not a prospective VEL-2 result. Additional predictive value from rich paired
predecision improvement measurements remains a scientifically plausible,
untested question.

No extra diagnostic, alternative repair, abstention policy or budget reallocation
was randomized/evaluated here. No better investigation or FULL gain is identified.
The evaluator still determines FULL. Recognizing panel sensitivity may motivate
explicit probability targets and warning semantics, but does not supply a
causal recovery effect or a deployable classifier. No Nemotron contribution,
online learning or unfamiliar-mechanism transfer is claimed.

## Budget and Stage B feasibility boundary

Owner verified available Cloud credit$21.34; authorized additional cap$6,
Token Factory$0. Stage A's initial45-minute deadline plus21-minute operational
reserve and$0.30 fixed reserve forecast <$2.63. Real physics took3.04 minutes.
A pre-physics ownership error caused one diagnostic restart; both windows
are included in the conservative ledger cost.

Initial ledger122.985, final123.324: **$0.339 additional estimated Cloud**.
Batch compute counter48.055->48.215h (+0.160h); main72.369h unchanged. The first
interval is conservatively charged through the next local start; the last
interval closes at retained API STOPPED observation00:22:10UTC. This includes
delayed observation/storage and is not a provider invoice or current balance.
No new account balance is inferred. Actual Token Factory spend/calls **$0/0**.

The earlier VEL-1 30-base sketch was230,376 equivalents,1.185h/$2.509 with25%
margin at the measured DI-1 maximum six-worker path rate0.118528s/equivalent
and eight concurrent paths. It does not establish healthy-base creation yield
for genuinely new lineages. Reusing the established broad failing-body generator
and2,000-rollout healthy-walker optimization, an illustrative123-attempt upper
allocation adds123x2,096 equivalents; the sum488,184 projects2.511h/$5.316
before operational overhead. Adding$0.50 overhead and Stage A's$0.339 exceeds
$6. This is a sensitivity scenario, **not a validated minimal cost, frozen
Stage B registration or evidence all possible designs are unaffordable**.
A cheaper direct healthy-draw qualification scheme would need its own frozen
attempt stream and measured yield. No additional qualifying outcomes were
collected. The actual reason Stage B stops is its failed reliability prerequisite;
available credit and a cheaper forecast cannot override it. No30-base design
was silently shrunk or represented as evaluated.

## Engineering, shutdown and validation

The first systemd launch used root; Git's ownership check failed before tests
or physics. Native finisher exit128 archived the failure and issued API stop.
Both VMs were verified STOPPED before restart. Launching identical frozen source
as the existing forge user resolved the failure. The failed archive SHA256 is
`efdd4a835947efeacf4b88d94a46dae81737cf3dde32ada02ab8a606fa5657d7` (504 bytes).
There were no partial scientific checkpoints to discard or rerun.

Successful native supervisor exit0, finish00:21:10UTC; automatic archive/API-stop
finisher executed. The archive was retrieved through an existing bounded
read-only SSH connection as soon as its checksum was available. No paid
retrieval restart was needed. Both VMs API STOPPED at00:22:10UTC, reconfirmed
00:23:56UTC /01:23:56Europe/Oslo. Native root timer/API stop and independent
Windows watchdog were retained; guest poweroff was never treated as billingstop.
The Windows watchdog was Ready before launch. No later paid work is scheduled.

Python multiprocessing emitted post-pool semaphore cleanup warnings. They are
preserved, not hidden or recast as physical errors. Root cause is unresolved;
all30 records/2,016 rows were present, no ERROR seed, native exit0. Independent
audit replays every verdict and confirmation computation from saved arrays.
These checks support the reported evidence; they do not claim a warning-free
runtime or a second full-physics replay.

Validation completed:

- Eight leakage/identity/group/seed/error/cost/verifier guards passed locally
  and on the real VM.
-107 frozen source hashes matched on VM before physics and locally afterward.
- Independent audit verified all30 panels, replayed sign-test/confirmation
  calculations without new physics, and independently reproduced the gate.
-43 native manifest entries verified; original and repeated native analysis
  were byte-identical. A new local stdlib analysis also matched native bytes.
- Full native archive228,957 bytes, SHA256
  `aac3a50a713da2615a9798743ae63fe49a71ce02eb7d195c61f9033eaa9f5d20`.
  Retained on stopped batch disk and ignored local artifacts. Small portable
  full response evidence and operational receipts are committed under
  `experiments/causal_engineer/dev/vel2/results/` (~1.4MB).

## Reproduction without paid physics

From the research checkout using its existing Python/MuJoCo environment:

```powershell
python -m unittest discover -s tests -p test_vel2.py -v
python scripts/vel2_repeatability.py analyze --out experiments/causal_engineer/dev/vel2/results/native --analysis-output artifacts/vel2_analysis_reproduction.json
python scripts/vel2_audit.py --root experiments/causal_engineer/dev/vel2/results/native --out artifacts/vel2_independent_reproduction.json
```

Use `experiments/causal_engineer/dev/vel2/EVIDENCE_SHA256SUMS` to check all small
report/source/input/output evidence bytes. `vel2_closeout.py` exports original
local raw/operational evidence; it never generates physics. A future fresh
physics rerun would need a new output directory, the pinned Linux source/env,
new explicit operational authorization and shutdown guard; do not overwrite
this completed study or call it a new independent-lineage experiment.
