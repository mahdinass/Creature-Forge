# R0 engineering amendment 2 — asynchronous lifecycle requests

Date: 2026-10-25. Parent execution-preparation commit: `37355a6`.

The first engineering start request was accepted by the service-account API,
but the CLI's default wait failed with PermissionDenied on a separate
`computeoperation` resource. The instance read API confirmed RUNNING. SSH through
the previous host address timed out. No experiment or physics test ran. A direct
existing-SA `stop --async` was accepted, and both instances were verified STOPPED.
Its short interval was conservatively recorded from campaign initialization
through verified stop; the original campaign clock/budget was not reset.

Use `--async` for start/stop requests, then the existing helper's instance-state
polling (which this scoped SA can perform). Keep read calls unchanged. The test
checks start and stop receive `--async` and get does not. This needs no IAM,
credentials, firewall or scientific change. The root VM self-stop already uses
this asynchronous form.

The previous active protocol is preserved as
`protocol_after_engineering_amendment_1.json`. Only the operational wrapper's
source hash and the amendment annotation change. Parent protocol SHA-256:
`333a740174229eda3c5f27eb6b4ced8e45c3311af47dc356dd8f3f0f3e4b83d5`.
Active protocol SHA-256:
`c1aab65c08616cb992e5065fb02d0efcf23bca64d355f3b3af597229e275bea7`.

No R0 outcome has been observed. Cases, seeds, search/selection, objectives,
physical budgets, verifier, analysis and advancement thresholds remain frozen.
