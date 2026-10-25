# R0 preparation and execution status

Date: 2026-10-25. Branch: `codex/repair-strategy-r0`, based on research commit
`0828cbd0ea556fb31630e275b444b0197671185e`.

**Outcome B: implementation prepared; paid execution blocked by unavailable
current account-credit verification. No R0 physical outcomes exist.** The owner
authorized execution; another authorization to run is unnecessary. The Nebius
console requires interactive sign-in, and the existing service-account CLI has
not supplied a current account balance. Authentication was requested while safe
implementation continued. Historical balance, the $35 authorization, and the
local spend ledger are not substitutes for current available credit.

## Implementation

The isolated R0 policy reuses the existing CMA, singleton tool spaces, hidden
plant, physical bounds and unchanged independent recovery verifier. It adds
union spaces for eight physically motivated group pairs and compares joint
optimization with singleton and sequential portfolios. The byte-exact audited
DO-1 module is imported from its existing research branch, rather than rewritten.
No production engine behavior or release work was changed.

The trusted evaluator holds the private plant; policy input contains only an
opaque identifier, nominal design and train/selection seeds. Candidates are
checked against absolute limits and the original-relative body bounds.
Each unit accounts for exactly 3,000 measured policy rollouts, including faulty
baselines and candidate selection. Verification follows final submission.

The driver provides deterministic sampling, role-separated fresh seeds,
source/protocol/environment provenance, atomic immutable unit files, validated
resume, deterministic shards, complete-set analysis and base-clustered contrasts.
Invalid or missing records cannot produce a complete study. Errors are retained;
unfavorable completed outcomes are never selectively rerun. The VM supervisor
finalizes evidence and requests the existing service-account API stop on normal,
fatal and deadline exits. It has not yet run on the actual VM.

## Frozen design

The registration contains 12 historically unsuccessful development cases and
six historically repairable controls on 18 distinct bases. Selection balances
families with deterministic hash tie-breaking. All selected families are dev
families. Sampling does not consult R0 outcomes. One separate instance is reserved
for engineering smoke tests; it is excluded from the main study.

Three action conditions cross frozen and DO-1 objectives. Three optimizer
replicates per case/condition give 324 units and 972,000 policy rollouts.
Independent verification adds 15,552 validation rollouts and at most 15,552
10-second-equivalent confirmation rollouts. The full maximum is 1,003,104
10-second equivalents, excluding the engineering smoke tests.

The sequential comparator standardizes existing chained-search capability in a
plant-only portfolio; it is not a replay of the whole diagnosis/twin engine.
Equal actual rollout counts control additional-search budget. Portfolio sizes,
dimensions, overhead and numbers of candidate evaluations differ; this limits a
pure action-space attribution. All contrasts are descriptive development
comparisons, not confirmatory tests of transfer or Nemotron learning.

Primary descriptive contrast: joint/DO-1 minus sequential/DO-1 on the 12 failed
bases. Objective-matched comparisons and objective effects appear regardless of
outcome. Technical replicates are averaged within bases; 10,000 base-cluster
bootstrap samples provide descriptive intervals. Exploratory sign-flip tests
enumerate base-level differences.

Protocol SHA-256:
`e9c0a0b1a9f24e173129de569c77c7795ee72a1b5c794efcf39e066dd66ffa26`.
The protocol pins exact case/input bytes and LF-normalized implementation hashes.
`SHA256SUMS` and the preparation archive preserve the other deliverables.
Earlier unrun preparation drafts were retained locally under
`artifacts/r0_preparation/drafts/`; no scientific change followed an R0 outcome.

## Results for every condition

| Action | Objective | Assigned units | Completed units | Verified recovery |
|---|---|---:|---:|---|
| single | frozen | 54 | 0 | not measured |
| single | DO-1 | 54 | 0 | not measured |
| sequential | frozen | 54 | 0 | not measured |
| sequential | DO-1 | 54 | 0 | not measured |
| joint | frozen | 54 | 0 | not measured |
| joint | DO-1 | 54 | 0 | not measured |

No physical worker was started, and no experimental unit was attempted. There
are no R0 success rates, confidence intervals, effect estimates or unresolved
physical failure diagnoses to report. The synthetic fixtures used to test
analysis are engineering fixtures and are not experimental observations.

**Advancement gate: NOT EVALUATED.** It requires at least three failed-cohort
bases rescued reproducibly (joint/DO-1 >=2/3; both restricted/DO-1 <=1/3), spanning
at least two families; net joint FULL gain >=3 against the per-base better
restricted comparator; no material control regression; and all 324 records
complete without verification ERROR. Missing data do not imply gate failure.

## Validation and its limits

- 69 Windows tests passed using the existing main-checkout Python 3.11.9
  environment, MuJoCo 3.15.0 and NumPy 2.4.6. The selected existing suites cover
  search spaces/CMA, recovery status logic, HDB structure/engine and hidden-plant
  DSL. A guard forbade physical rollouts during this local validation.
- The 19 R0 tests cover singleton equivalence, union dimensions, anchored bounds,
  exact budgets in all six conditions, determinism, leakage rejection, verifier
  handoff, invalid records, seed separation, sampling, validated resume, unique
  shards, provenance, resource caps, archive bytes and complete aggregation.
- The synthetic 324-record analysis fixture checks base clustering, the rescue
  gate and rejection of a control regression. It supplies no physical evidence.
- Three Linux supervisor tests passed under existing WSL Python using fake sudo,
  worker and stop commands: normal finish, shard failure/process cleanup, and an
  early argument error. Bash syntax also passed. No cloud API was invoked by
  these tests. Real VM-side API self-stop remains untested in this campaign.
- Actual hidden-plant/DO-1 rollouts, development physical regression tests,
  serial-versus-pooled physical equivalence, throughput, reusable VM environment
  and full-study fit remain launch gates. They cannot be claimed as passing.
- The old research base's known 42-path global frozen-manifest issue was not
  repaired. R0 has separate evidence checksums; release rc2 and PR #20 remain
  outside scope.

Logs and infrastructure observations are in `validation/`. Basic Memory tools
were unavailable after retrying tool discovery; tracked project memory was
used. No remote memory synchronization is claimed.

## Infrastructure, cost and shutdown

At control-plane epoch 1792889886 (2026-10-25 00:58:06 UTC), the service-account
API returned **STOPPED** for both the 8-vCPU main instance and 64-vCPU/256-GiB
batch instance. No start, extension or stop mutation was needed during this
campaign. The existing Windows watchdog was Ready and allowed on battery.

The existing batch quote is $2.112 compute/hour plus $0.00486 disk/hour, or about
$2.1169/hour. This agrees with the current official CPU/RAM price schedule:
https://docs.nebius.com/compute/resources/pricing . The local conservative
lifetime ledger read $107.262; it is an estimate across existing infrastructure,
not current available credit or a reconciled provider invoice.

R0 paid VM runtime and new compute spend are zero. No resources were provisioned.
Pre-existing disks remain and continue storage charges while instances are
stopped. Their charges and account credit cannot be reconciled to an actual
invoice without console access. No $35 spend or historical credit is assumed.

The planned schedule is eight shards of six serial workers on the batch VM,
with one BLAS/OMP thread each. Throughput is unmeasured. Even though ten hours
at the batch quote is approximately $21.17, this does not establish that the
study fits ten hours or the current balance. Launch requires measured fit with
25% margin, the separate $35 ceiling, available-credit ceiling, and ten-hour
campaign ceiling. No sample reduction is authorized as a workaround.

## Next scientific step

Obtain a verified current Cloud credit amount through the existing signed-in
console or owner confirmation. Then perform the bounded engineering start,
verify the existing VM environment and autonomous API self-stop end to end,
benchmark the excluded smoke case, check serial/pooled scientific equivalence,
and calculate full-study fit. Only after all gates pass should the unchanged
324-unit registration run. Operational commands are in `README.md`.

No conclusion about coordinated repair capability, objective benefit, control
regression, or transferable strategy learning is supported yet. R1 planning
based on a passed R0 gate is premature. The next step is completion of R0, not
another memory or learning mechanism.
