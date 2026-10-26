# H3 preparation validation — 26 October 2026

**Non-physics preparation complete; new physics and spending await fresh explicit approval.** The earlier pause checkpoint is preserved at6c27e116a350898007d7352347b1f8279eb4954a and in `docs/H3_RESUME.md`.

Environment reused: `C:/Users/mbnas/.vscode/Creature-Forge/.venv/Scripts/python.exe`, Python3.11.9, NumPy2.4.6, MuJoCo3.15.0. No installation or new environment. All commands below ran from this H3 worktree in that venv except the stdlib audit, which used global Python.

| Check | Result / scope |
|---|---|
| `python -m unittest tests.test_h3 tests.test_h1 -v` | **32 passed**,9.604s after CI-isolation correction. Real controller objects on synthetic inputs; spawned bridge/routing contracts; actual-background-thread rejection; error/budget/manifests; candidate/seed drift; grouped analysis and orchestration. No physics. |
| `python -m unittest tests.test_frozen_records -v` | Two pass; coverage test fails on **42 inherited E1 omissions**, exactly equal to pin e8d5fa6. All279 covered blobs match. No full-suite-green claim. |
| `frozen_integrity.json` | Independently compares current tracked frozen paths and manifest with e8d5fa6730ecf6d2db67021a9d3d0f08cce03310. Manifest unchanged; no new omissions or modified covered blobs. No regeneration. |
| `python scripts/h3_run.py plan --out experiments/causal_engineer/dev/h3/plan.json` | Generates bodies/seeds/pins only; zero model compilation/physics.48 unique new root draws,18 known historical body hashes excluded,9,696 disjoint evaluation-seed IDs. |
| Plan replay and `check_plan` | Exact regeneration; all106 normalized source pins match. Exact plan SHA256 **c5eea6daddaf90c9ed2cef598dce0b45919e6c9bbcef8226b456b0412e988bdd**. |
| Original saved audit | Preserved, not rerun after resumption. SHA256 **3e6522a6d69ac4ac4d1618679f3e3df5bd494287641feea9a8d50e0f5ce4f7bf**. Recounts existing raw development evidence only. |
| Unrelated user file | `scripts/e2r_analysis.py` remains untracked and unchanged, SHA256224ea1a3ccd203e3746c192711586fbe1330e53275e7d35fb67352ef590874f8. |

H3 test fixtures patch `mj_step`/`mj_forward` to reject physics, including inside synthetic spawned jobs. Synthetic responses are confined to unit tests and never exported as physical findings. No full discovery was run because many existing tests generate trajectories.

`preparation_validation.json` preserves the earlier31-test receipt; `final_nonphysics_validation.json` records the final32-test review. `SHA256SUMS` covers the immutable preparation packet and seven research documents, excluding this mutable publication log. Source hashes explicitly normalize CRLF to LF; plan, records and report export hashes preserve exact bytes. The first unregistered local plan, superseded during failure-journal review with identical scientific gates, remains at ignored `artifacts/h3_plan_prelogging_review_20261026.json`; no H3 physical outcomes preceded either preparation.

**Automatic checkpoint CI exception:** push6c27e11 unintentionally triggered existing full-physics CI; completed runs40362890285 and40362889245 failed, with frontend jobs passing. The inspected first run reported1539 tests, two failures/one error/five skips. Failures were the inherited frozen coverage omission plus two H3 unit-test isolation assumptions in a parent runner with background threads. Those positive tests now model the documented dedicated-worker contract, while real additional-thread rejection and spawned-worker checks remain enforced. Local32-test verification passes; no full-suite rerun or full-green CI claim. See `checkpoint_ci_review.json` and `docs/memory/INCIDENTS.md`. Current publication commits include `[skip ci]` to suppress the existing push/PR physics workflow ([GitHub behavior](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs)). No workflow or release setting changed. Zero `new_physics` in the preparation receipt means zero H3 research-physics calls, not zero simulator steps in unintended repository CI. CI outputs are not used as scientific outcomes; GitHub Actions consumption is not a Nebius invoice claim.

Native trajectory equivalence, real19D physics/verifier behavior, qualification yield, optimization performance, recovery benefit and Cloud throughput remain **untested**. Spawned non-physics contracts are not native physical validation. T1/T2 gates in `docs/H3_EXPERIMENTAL_PROTOCOL.md` are mandatory; the planned pilot is not authorized.

Both VMs are API-confirmed STOPPED at epoch1793045409.7172987, main compute72.369h/batch48.874h unchanged from H1. See `preparation_cloud_status.json` and the older `pause_cloud_status.json`. Ledger124.909USD includes existing disk accrual; it is not a fresh payment-capacity balance. New H3 compute/Token Factory spending is0; no starts, training, new physics or model calls.

Publication and verified memory/Notion readback are appended after the scientific bundle commit. The provider quote and usable credit must be freshly checked before any later approved paid window. No release merge, sealed data mutation or submission edit is authorized or performed.


## Publication and synchronization verified

Scientific bundle **5c0975e2dcd3dd3be0ed89a5596917273a7e96aa** is pushed on `codex/h3-capability-audit`; remote ref matched. Draft PR23 https://github.com/mahdinass/Creature-Forge/pull/23 targets H1 `codex/h1-bounded-investigation` at a2619c7 and is attached to this chat. No merge. The closeout commit adds metadata only; find it with `git log -1 -- experiments/causal_engineer/dev/h3/publication.json`.

Basic Memory project creature-forge note `research/h3-preparation-complete-unvalidated-stance-residual-pilot-2026-10-26` was written and read back, checksum **f5316102462d1e7d057cbc058b2c4fa821e5a5bd96890c212e1ebb984dd27b45** matches the write and contains the scientific commit and fresh-approval boundary.

Notion page4035d357-b5ad-813e-84d4-de5fd8928f41 readback last edit **2026-10-26T20:23:57.721Z** contains exactly one H3-preparation section, the matching scientific commit and plan hash. Its complete earlier content prefix, including H1 and prior studies, is preserved. A date-tag deprecation was automatically converted without changing the date. This is content synchronization verification, not Notion's native editorial-verification badge.

Final provider receipt `final_cloud_status.json`, epoch **1793046301.875729**: both STOPPED; main72.369h/batch48.874h unchanged. Ledger124.911USD reflects stopped-disk accrual, not usable credit or new H3 compute. No new CI runs for scientific commit5c0975e; only the two disclosed, completed checkpoint runs remain. Publication/closeout use `[skip ci]`. Exact metadata: `publication.json`; staged verification records106 matching source pins and14 matching exported files. The export manifest lists those14 scientific files explicitly; status/publication/staged-check metadata and this mutable log are outside that list. Future execution-unit manifests instead enforce full unit-directory coverage.

All permitted H3 preparation is complete. Next action is fresh explicit experiment approval, then fresh credit/price checks and native T1/qualification T2/throughput gates. Do not start either VM, new physics, training or Token Factory work from a generic resume or H1 authorization. Proposed ceiling USD8 additional Cloud / three paid batch hours / USD0 Token Factory; no paid follow-on scheduled. V1 release, submission and sealed evidence remain untouched.


## Executed T1/T2 closure — 26 October 2026

This supersedes preparation-only pending-approval status above; immutable preparation14-file export stays unchanged. Explicit owner USD8 Cloud / three batch hours / USD0 Token Factory authorization and fresh capacity preceded native execution at c7103d47ba6e63e6cfd5d0b2c2ab161091163969. All106 source pins and plan SHA c5eea6daddaf90c9ed2cef598dce0b45919e6c9bbcef8226b456b0412e988bdd verified natively.

T1 PASS: six zero-gain paired rich traces and six paired verifier rows;24rollouts. T2 NO-GO:48roots/1152rollouts,4eligible(1left/3right) versus6 per side. Total1176rollouts/1560equivalents, no errors. Zero optimization/FULL/model calls. Expected native exit20. Frozen analyzer and separate stdlib archive audit/portable1152-row replay agree; full audit repeated byte-exact.32 preparation H3/H1 non-physics tests and2 operational-cap tests passed; no full-suite rerun or green claim. Earlier unintended checkpoint CI and inherited42 omissions remain disclosed.

Exact native archive SHA7033654550fd5d2bb6fbc37b600cce7b3dc0d44c0df5f3200947b4cf733e1262:61 outer entries,3 gate/51 qualification unit entries verified. Science-only exact native qualification payload gzip SHA8ac22cedb978ad684375d846ca3dbd8bed29d1c820882bac90d26624ec9dab70,1152 seed rows; no authorization/payment data in portable export. Independent auditor added after acquisition only to replay frozen criteria; source provenance and exact commands in results/COMMANDS.md. Original raw archive stays ignored/on stopped VM disk.

Both VMs API STOPPED at1793049383.7590587. Additional batch upper0.164798624h; configured compute plus both existing disks quote USD0.3500432, not invoice/current balance. Includes retrieval-only restart, no physics replay; main compute0, Token Factory0. Operational archive-path/receipt/stop-latency limitations disclosed in INCIDENTS and resource_audit.json. Results: docs/H3_RESULTS.md; current decision docs/H3_EXECUTION_DECISION.md. Stop now: no replacement acquisition, threshold changes or unused-budget experiments. Any new acquisition recipe requires new protocol/approval; residual efficacy remains untested.
