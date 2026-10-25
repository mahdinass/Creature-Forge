# R0 engineering amendment 3 — excluded-case reporting metadata

Date: 2026-10-25. Parent source commit: `6219317`.

## Observed defect and preserved evidence

The first excluded-case serial smoke completed optimization and verification,
then failed constructing its record with `KeyError: 'cohort'`. The frozen smoke
case lacks this reporting field; main cases already contain `failed` or
`control`. No valid smoke checkpoint was written, and no main unit was attempted.
The selected design and verifier result were not serialized before the exception
and cannot be recovered from the stopped process. Their outcomes are unknown;
no success or failure is inferred. The completed solve used 2,000 policy rollouts;
verification used between 48 and 96 rollout equivalents, with its exact count
unavailable. These costs remain included in the conservative runtime ledger.

The supervisor archived the available logs/error, then the existing root SA
requested API stop at 12:35:25 UTC. An independent API read confirmed both VMs
STOPPED. The failed engineering archive is preserved as
`engineering/invalid_v1.tgz`, SHA-256:
`212a534187009f011b8bda80213d1de0e52bd7e162ca379ba6a18d9875abaa42`.
It includes the passing 82-test regression run, fixed-fixture throughput probe,
physical DO-1 equivalence and the smoke error. It is not a valid R0 outcome set.

## Minimal fix

Assign `cohort: engineering` in memory only when loading the excluded smoke
blob. Its case bytes, seeds, nominal design and plant remain unchanged. The
label is never supplied to policy. Validate required case metadata before any
optimization or physics so an incomplete record cannot incur this loss again.
Two focused regression tests cover byte preservation and failure before physics.
The record/analysis/resume tests pass after the fix.

Only `scripts/r0_experiment.py` changes relative to amendment 2: reporting-only
smoke metadata and pre-physics metadata checking. The previous active protocol
is preserved as `protocol_after_engineering_amendment_2.json`.
Parent SHA-256: `c1aab65c08616cb992e5065fb02d0efcf23bca64d355f3b3af597229e275bea7`.
Active SHA-256: `b481dc8977d56a9878526cfafce259e05e4c55bd551f1983661040bb482139bb`.
All scientific choices, input bytes, optimizer behavior, physical budgets,
verifier, analysis and advancement thresholds remain unchanged.

## Explicit recovery procedure

1. Preserve the failed v1 archive/logs and charge its compute; never overwrite it.
2. Freeze the amended source before retrying. No main outcome has been observed.
3. Rerun all six excluded-case conditions uniformly under serial and pooled
   scheduling in fresh `r0_engineering_v2` directories. No validated successful
   checkpoint is rerun; v1 produced none. Retain every v2 result regardless of
   recovery status. Main data remain untouched.
4. Rerun the affected regression tests and exact scientific-output comparison.
   The fixed-fixture CPU probe may be reused with its original source provenance:
   no physics/search implementation changed.
5. Recheck full-study fit and all resource limits before launching the unchanged
   324-unit main registration. Do not tune on smoke recovery outcomes.
