# G0 measurement driver fail-fast recovery

The first bounded twin-only audit was interrupted at 2026-10-25 19:02:24 UTC
after publication stopped at 17/866 records while six workers remained busy.
A bounded replay of the first unpublished job completed in 2.97 seconds and all
866 seed-routing metadata checks passed. The suspected mechanism is executor
shutdown waiting on all queued work after an unpublished exception; the actual
worker error was not logged by the old driver and remains unconfirmed until
explicit failure capture is exercised. Do not infer a scientific result from it.

The native supervisor retained all available evidence, exit code 124, archived
299,017 bytes (SHA-256 `7a3f4657127dc2ece6e0ec867d0b8171cb02cf19ca851da88b6b221b837aab6e`)
and invoked API stop. Both VMs independently confirmed STOPPED at epoch
1792954984. The archive remains on the stopped batch disk for retrieval.

Engineering-only recovery: replace Executor context shutdown with the public
multiprocessing Pool context, record each failing job's id/traceback separately,
and terminate queued workers on the first error. No prediction/physics function,
seed, job, measured target, action space or outcome definition changes. Preserve
the original protocol and partial archive. Uniformly rerun the same 866 jobs in
a fresh v2 output; this is deterministic measurement recovery, not selective
optimization or method selection. Any physical error discovered is retained and
audited; it is never converted into a valid unsuccessful walking outcome.

The original EM-1 campaign clock and limits remain unchanged. A new bounded
45-minute deadline is an engineering allowance inside the original six-hour/$12
authorization, not a new task budget. No correction learner or prospective
evaluation has begun.
