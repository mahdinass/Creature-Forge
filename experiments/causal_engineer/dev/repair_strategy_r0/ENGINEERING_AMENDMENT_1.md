# R0 engineering amendment 1 — service-account start entry point

Date: 2026-10-25. Parent registration commit: `bb2ecb9`.
The owner confirmed current available Cloud credit of **$33.73** and instructed
resumption under the existing $35 / ten-hour authorization. No R0 unit had been
attempted when this amendment was made.

Code inspection found that the existing `forge_cloud.cmd_start` calls its legacy
`nebius` function directly, while other control-plane operations call `ctl`.
The R0 wrapper routed only `ctl` to the service account. Route both entry points
to the existing `nebius_sa`; create no credentials, IAM or new authentication
system. A focused test checks both bindings. No physics code changes.

The original protocol is preserved byte-for-byte as
`protocol_registered_bb2ecb9.json` and in the preparation archive. The active
`protocol.json` differs only in the `scripts/r0_nebius.py` source hash and an
explicit engineering-amendment annotation. Its parent SHA-256 is
`e9c0a0b1a9f24e173129de569c77c7795ee72a1b5c794efcf39e066dd66ffa26`;
the active SHA-256 is
`333a740174229eda3c5f27eb6b4ced8e45c3311af47dc356dd8f3f0f3e4b83d5`.

All cases, case bytes, seed roles/values, actions, pair library, objectives,
optimizer settings, budgets, verifier, analysis and gate remain unchanged.
The original preparation report/validation observations remain historical.
An execution report will supersede their blocked status when engineering and
the registered campaign have been evaluated. This amendment changes operational
authentication only; it does not tune the study after an outcome.
