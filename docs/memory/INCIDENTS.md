# Creature Forge — incidents and proven fixes

Append one incident per significant recurring failure. Mark everything here as `observed`, `hypothesized`, `verified`, or `superseded`. Never claim a workaround succeeded without a command/log/test demonstrating it.

## Template

### YYYY-MM-DD — Concise incident name
- Status:
- Scope (OS, branch, interpreter, dependency versions):
- Symptom and precise error:
- Root-cause hypothesis:
- What we tried (including failed attempts):
- Validated fix:
- Reproduction / regression test:
- Evidence (git commit, file, log path, command):
- Applicability / exceptions:
- Related memory note or ADR:

## Current incidents

### 2026-10-13 — Foot friction parameter silently had no effect
- Status: fixed (Phase 0).
- Scope: Windows 11, Python 3.11.9, MuJoCo 3.15.0.
- Symptom: sweeping `foot_friction` 0.1..1.0 gave bitwise identical results.
- Root cause (verified): MuJoCo uses the **max** of the two contacting geoms' friction; floor friction was 1.0 and masked the foot.
- Validated fix: floor friction set to 0.05 (= lowest allowed foot friction). Regression test: `tests/test_morphology.py::test_foot_friction_is_the_effective_contact_friction` (watched fail, then pass).
- Related: same session, logged `torso_pos` z was the slide-joint offset (~0), not world height; fixed to use `data.xpos`, test `test_torso_height_is_absolute_world_height`. A "collapse" test had passed only because of that bug.

### 2026-10-13 — Open-loop gait does not walk (limitation, not a fix)
- Status: partly addressed in Phase 2A (see below); the open-loop family still does not walk (0/1000 sampled gaits pass the gates). Sinusoidal hip/knee gaits tried (0.6-1.5 Hz) all fell within 10 s or walked backward; only standing balance is validated for that family.

### 2026-10-13 — "Visual-only" leg offset changed the physics (Phase 0.5)
- Status: reverted; mitigated by a regression test.
- Symptom: moving the left/right legs +-0.07 m apart in y inside the MJCF (to make the legs distinguishable in the viewer) changed the Phase 0 result: baseline (8 cm foot, 25 N push) fall rate dropped from 5/5 to 3/5; 3 tests failed. A torso-box widening also doubled torso mass (density used a hard-coded volume) until fixed, but mass was NOT the cause of the remaining change.
- Cause (not fully isolated): contact outcomes near the tipping boundary are sensitive to small solver/geometry changes. Re-measured frontier with the offset: 8 cm foot fell 0/5 at 15 N, 2/5 at 20 N, 3/5 at 25 N, 5/5 at 30 N.
- Fix: model reverted (morphology.py identical to reviewed commit 5a13a09); the offset is a declared presentation transform (`scene.display_lateral_offset`, applied only by the viewer). Test: `test_model_stays_planar_and_lateral_leg_offset_is_display_only`.
- Implication: the Phase 0 headline "8 cm foot falls 5/5 at 25 N" sits close to the frontier; treat it as a result for this exact model and seed set, not a robust margin.
- Also fixed: spawn height used `1.5 * half_height` instead of the exact lowest foot point, so the creature dropped ~1 cm at t=0 (found by the first viewer-export test; Phase 0 results unchanged after the fix).
- Also fixed: Phase 0 docs commit 5a13a09 contained invalid UTF-8 in PROJECT_STATE.md, DECISIONS.md and INCIDENTS.md (Python wrote cp1252 em dashes on Windows). Repaired here; always pass `encoding='utf-8'`.

## 2026-10-13 — First live investigation: model hypothesis falsified (not a defect)
- Nemotron 3 Nano blamed torso inertia; MuJoCo showed torso_mass 5->3 kg changes nothing (fall rate 1.0->1.0). Phase 0 already showed foot_length is the dominant lever. Kept as a recorded failed trial (`20261013T002054Z-aaad96`), the intended behavior of the verifier. Next: richer evidence in the prompt and repeated trials vs. a baseline proposer before judging the model.
- Also: `reasoning_effort:"none"` returned null content (see PROJECT_STATE).

## 2026-10-13 - Phase 1 live batch: weak claim-to-action link and an invalid citation (not defects)
- Control and enriched-1 both proposed torso_mass 5->3, which is harmful (9/10 falls at 15 N where the baseline has 0/10). Enriched-1 cited real margins but the intervention did not follow from them. Enriched-2 cited a nonexistent path and was rejected. Prompts were NOT edited afterwards (pre-registered). Evidence: `experiments/phase1/results/live_summary.json`.
- Disclosure: exploration seeds 100-105 included the 16 cm design (see protocol).

### 2026-10-13 - Forward displacement was a reward-hacking exploit (Phase 2A)
- Status: handled by design; regression test `test_phase2a_feasibility_exploit_fails_walking_classification`.
- Symptom: a phase-lag variant of the open-loop gait moved +4 m in 5 s and survived 3/3 seeds. Telemetry: ~85 touchdowns per foot in 10 s (8.5/s vs 0.82 Hz commanded), 53-79% flight, saturated torque, slip up to 3.5 m/s, 2/5 seeds fell. It is chatter-hopping, not walking.
- Fix: gate-based walking classification (chatter, flight, saturation, slip, valid alternating steps); falls stop crediting displacement.

### 2026-10-13 - Phase 2A UI regressions caught by checks
- A fifth Studio nav tab overflowed the header by 44 px at 390 px width (existing lab browser check caught it); fixed with `nav { flex-wrap: wrap }`.
- A placeholder `peak_torso_vx = 0` in the replay payload showed 0.00 m/s for a walking robot (caught in a screenshot); now measured from the trajectory (tested).

## 2026-10-14 Stale Studio server: Locomotion/Investigations tabs showed "Unexpected token '<'"
- **Cause (verified):** a Studio server started 2026-10-13 01:43 (PIDs 72876/216116) was still bound to :8000 and only had the Phase 0.5 routes (`/api/version`-less OpenAPI listed 5 paths). The SPA catch-all `/{path:path}` answered every unknown `/api/*` GET with `index.html` (HTTP 200, text/html), which `res.json()` could not parse. The `dist` bundle on disk was current; the missing Overview tab was a cached older bundle.
- **Fix:** unknown `/api/*` now returns a JSON 404; `GET /api/version` (commit, start time, build time, routes); `index.html` served `Cache-Control: no-cache`; frontend `j()` turns non-JSON into an actionable message; `scripts/start_studio.ps1` replaces an older Creature Forge Studio (only if its command line contains `run_studio.py`), rebuilds a stale frontend and verifies required routes; `studio/e2e/tabs-smoke.mjs` checks every tab and every API response in a real browser.

## 2026-10-14 Freehand: hand wobble made a straight leg a "forward knee"
- Found by the first browser run of the starter sketches (not by the synthetic unit strokes): a hand-like wobble gave knee angles of +0.0003 rad, outside the joint range [-2.2, 0], so a straight leg was refused. Fix: `KNEE_TOL = 0.1 rad` clamp, reported as a note (guided mode reports it as a snap). Regression test with a wobbly stroke added.
## 2026-10-14 Two-simulation layouts overflowed after a window shrink
- R3F canvases keep their pixel width until the resize observer fires, and `1fr` grid tracks have `min-content` minimums, so a wide-to-narrow resize left the page 100+ px too wide. Fix: `minmax(0, 1fr)` tracks and `min-width: 0` on grid children; the existing responsive browser check (which resizes) caught it.
## 2026-10-14 Windows text-mode stdin sent CRLF scripts to the VM
- `forge_dev.py` piped bash scripts to `ssh ... bash -s` with `text=True`; Windows translated `\n` to `\r\n` and bash failed with `set: pipefail\r: invalid option`. Fix: send bytes (`remote_bash`). Also the Windows console (cp1252) crashed printing vitest's check marks; stdout/stderr are reconfigured to UTF-8 with replacement.
## 2026-10-14 FastAPI 0.143 `include_router` entries have no `.path`
- Mounting the forge router broke `/api/version` (`'_IncludedRouter' object has no attribute 'path'`), which the browser smoke flow calls. Caught by the new wiring test before any browser run. Fix: `_route_paths()` descends into `original_router`.
## 2026-10-14 Nemotron calibration v1: valid transport, invalid contract
- All 12 requests returned content (the R3 null-content mode did not recur with a 3.7k-token prompt), but 0/12 were machine-valid: proposals named hypotheses by sentence and cited invented paths. Fixed by enumerating ids, params and citable paths in the strict JSON schema (v2: 9/12, then 6/6). Lesson: constrain identifiers by construction instead of instructions.
## 2026-10-15 Deadman powered the guest off, but the instance stayed RUNNING
- The VM's 6 h deadman (`poweroff` inside the guest) fired overnight; SSH timed out, yet `forge_cloud.py status` reported `RUNNING` 3.75 h after the deadline. The Windows watchdog (which stops via the API) had last run at 00:27 (PC asleep). An API `stop` reached STOPPED immediately. Billing of a guest-powered-off but RUNNING instance is unverified, so it is assumed to bill.
- Fixes: the spend ledger now charges every run until an explicit API stop (conservative total $2.63 of $10 at 07:05); the orchestrator stops the VM through the API at the end of every work block instead of relying on the deadman. Option for the owner: let the watchdog task wake the PC.
## 2026-10-16 M1a partial results deleted by a slot sync (operator error)
- The first M1a run wrote `experiments/walk_recovery/oracle/results/m1a.jsonl` (untracked) inside slot `wr-main`; it then crashed on tiny-feet (`walk_opt.encode` rejected a base body exactly on the guided bound foot 0.06 because of the 1e-9 interval margin). Syncing the fix ran `git clean -fd` in the slot and deleted the 6 completed units (stilts x4, tiny-feet x2), exactly the hazard RESUME_CHECKPOINT warned about.
- Impact: ~8.4k rollouts re-spent; no result was selected or altered. Units are deterministic (fixed seeds, fixed noise stream), so the rerun from scratch reproduces them; the stilts statuses/gains printed before the loss are compared with the rerun as a determinism check.
- Fixes: encode tolerance covers the margin (regression test `BaseOnBoundTests`); oracle outputs now go to git-ignored `artifacts/walk_recovery/` on the VM (survives sync), pulled with `forge_dev.py pull` before they are copied into `experiments/` for commit.
## 2026-10-17 S2: the ai_nogait ablation shared the ai arm's ledger investigation id (confounded arm)
- `scripts/walk_s2_pilot.py` derived the AI investigation id from (creature, budget, noise seed) only, so `ai_nogait@2000` used the same id as `ai@2000`, which ran first in each shard. The per-investigation cap (8 requests) was therefore shared: 12 of ai_nogait's calls were refused BEFORE sending (`BudgetExceeded: ... request cap 8 reached`; no cost), leaving those pipelines with missing decisions.
- Consequence: the S2 `ai_nogait` numbers (2/12 recovered, H6 2/12 top-2 hits) are confounded and are NOT evidence about gait features. `ai` (both budgets) was unaffected: it ran first and has its own ids per budget. Disclosed in `experiments/walk_recovery/dev_pilot/REPORT_S2.md`.
- Fix: every method other than `ai` now derives its id with the method name (S2 `ai` ids unchanged). The information ablation must be re-run if it is to be used.
## 2026-10-17 S3 nearly reached the batch VM's deadman deadline
- The S3 confirmatory run was launched with a 4 h VM deadline that included the time spent on smokes and the amendment; the local background waiter that would have flagged it was stopped by Claude Code (Windows host low on memory). A one-off check found 0.11 h left with 28 units running; `forge_cloud.py extend --hours 2` (cap-guarded) fixed it before the guest powered off. No unit was interrupted.
- Lesson: set the deadline at launch for the projected run time + margin (not the default), and do not rely on a local waiter process for safety-relevant extensions.
## 2026-10-17 API key written into dev result files on the VM (trailing CR, redaction miss)
- What happened:
  - The causal-engineer pilot2 launch sourced `~/dev/.env` in bash (`set -a; . ~/dev/.env`). That file has CRLF line endings, so `NEBIUS_API_KEY` carried a trailing CR.
  - Every request failed locally (`ValueError: Invalid header value b'Bearer <key>\r'`); no request reached the provider and nothing was spent.
  - The error text contained the key. `redact_secret` and the record guards compare the exact key (with the CR) and missed the escaped form, so the key was written into 4 git-ignored result files on the VM (`~/dev/ce3/artifacts/ce/pilot2_shard*.jsonl`).
  - The key was also echoed once into the operator's local session transcript while diagnosing.
- Containment:
  - The 4 files (0 successful calls, no results) were deleted.
  - A grep of the VM logs, ledger and other slots found no other copy. Nothing was committed or pushed.
- Fix:
  - `config.nebius_api_key()` strips whitespace.
  - `nebius.redact_secret` also removes stripped and escaped forms and any `Bearer <token>`.
  - A new fail-closed `nebius.contains_secret` (which also checks JSON-escaped forms) is used by the director, mech_director and scientist record guards.
  - Regression tests in `tests/test_nebius_client.py`.
  - Launch rule: never `source` the .env in a shell; the Python `load_env` (dotenv) reads it.
- Owner action recommended: rotate the Nebius Token Factory key, since it appeared in a local transcript.
## 2026-10-17/18 Registered held-out run: AI arms invalidated by a key rotation during the run
- Timeline:
  - The registered evaluation (`experiments/causal_engineer/heldout/`) was launched at 20:12 UTC.
  - At about 20:45 UTC the operator recommended rotating the Token Factory key (see the previous incident) without saying to
    wait until the run ended.
  - The owner rotated it at 21:02 UTC. Every model request after 21:03:50 UTC returned HTTP 401.
- Effect:
  - AI episodes ended as `consecutive_invalid` with the unrepaired robot submitted; only 4–15 of 40 per AI arm ran before
    the outage.
  - Non-AI arms were unaffected.
  - 231 failed calls were settled in the ledger at worst case ($7.42 recorded, nothing billed).
- Handling:
  - The registered analysis was run once and reported as is (`REPORT.md`), with the AI tests marked uninterpretable.
  - The new key was installed on the VM (verified read-only).
  - A re-run of the AI arms is proposed as amendment 1 and needs the owner's decision.
- Lessons:
  - no credential changes during live runs;
  - pre-run live key check;
  - runners must fail fast on authentication errors.
## 2026-10-18 GitHub Actions refuses to start runs (account billing) - infrastructure blocker
- Push run 39088125876 (`feature/causal-engineer` @ `192c000`): both jobs failed in 1-2 s without starting.
  - The annotation said "The job was not started because recent account payments have failed or your spending limit needs
    to be increased."
  - No test ran, so this is not a code failure.
- Impact: there is no CI signal on any branch or PR (including PR #18) until the owner fixes GitHub billing.
- Not done: no workaround, and no workflow change on this branch. PR #18 already reduces Actions usage once merged.


## 2026-10-25 — R0 atomic checkpoint portability (resolved before physical execution)

- **Symptom:** the first Windows engineering test of a POSIX-style atomic hard-link checkpoint failed under the workspace filesystem permissions. No physical R0 record existed.
- **Fix:** `scripts/r0_experiment.py:write_new` uses same-directory fsynced temporary files, Windows atomic rename that refuses overwrite, and POSIX exclusive hard-link publication. An already-existing checkpoint must match exact bytes; malformed or disagreeing evidence is rejected. No existing scientific record was overwritten.
- **Validation:** immutable checkpoint/invalid JSON and resume tests in `tests/test_r0.py`; 69 selected local tests passed. An unrelated real-cloud launch remains blocked by unverified current account credit.
- **Lesson:** exercise the target OS publication primitive before generating outcomes; preserve exclusive creation and exact-byte comparison rather than weakening evidence immutability.


## 2026-10-25 — Scoped SA lifecycle operation polling (R0 engineering)

- First authorized engineering start was accepted, but the CLI default operation-resource wait returned PermissionDenied. Instance get confirmed RUNNING; stale-host SSH timed out. No R0 physical unit ran.
- Immediately used existing SA `stop --async` and instance polling; both VMs verified STOPPED. Conservatively charged the initial interval without resetting the campaign clock.
- Fix is R0-scoped: append `--async` to lifecycle start/stop only, keep get synchronous and poll instance state. No IAM/auth changes. Focused ops tests pass. Original and amended protocols are preserved; all scientific choices remain unchanged. Evidence: `ENGINEERING_AMENDMENT_2.md` under the R0 registration directory, `scripts/r0_nebius.py`, `tests/test_r0.py`.


## 2026-10-25 — R0 excluded smoke missing reporting cohort (resolved before main)

- After first real smoke solve/verification, record construction failed on absent `cohort` in the frozen excluded-case blob. No valid checkpoint or main record existed; the unserialized design/verifier result is unavailable and is not inferred.
- Guard archived logs and API-stopped the VM; both instances independently confirmed STOPPED. Invalid archive SHA-256 `212a534187009f011b8bda80213d1de0e52bd7e162ca379ba6a18d9875abaa42`, preserved in the R0 registration `engineering/invalid_v1.tgz`.
- Fix: trusted loader adds a reporting-only engineering cohort in memory, preserving exact case/seed bytes; required metadata is checked before physics. Focused record tests pass. No optimizer, physics, verifier, budget or threshold changed.
- Recovery is explicit in `ENGINEERING_AMENDMENT_3.md`: preserve v1, uniformly rerun all six serial/pooled excluded smoke conditions in fresh v2 output, then reevaluate launch gates. No selective favorable rerun. Original campaign clock/credit bounds remain in force.

## 2026-10-25 — R0 autonomous completion and evidence retrieval verified

- Native supervisor completed all 324 units, frozen analysis and audit with exit zero at 16:50:02 UTC, archived evidence, and invoked the existing root SA API stop at 16:50:07. Both VMs independently observed STOPPED at 17:03:23. No main worker/verification errors occurred.
- Raw archive remains on persistent batch disk. A bounded 15-minute restart retrieved its exact 16,568,688 bytes and reran analysis/audit without new physics; then API stop and independent get confirmed both STOPPED at 17:10:46. Archive SHA-256 and all 337 checksums verified; repeated analysis and native/local audits matched.
- Preserve the distinction between actual API stop and local ledger observation: root shutdown does not automatically append the laptop ledger event, so paid time was conservatively charged until the first later API observation. Final $10.349 additional/4.877 hours are local conservative estimates, not provider invoice or final-credit evidence. Never reset campaign time/credit on restart.
- Evidence and scientific negative gate: R0 `results/verification_receipt.json`, `final_control_plane.json`, `final_selfstop_log.txt` and `EXECUTION_REPORT.md`. No permission/IAM expansion or shutdown workaround was needed.

## 2026-10-25 — EM-1 duplicate design indices and cross-version replay

- First audit published17 records then waited with workers busy: distinct pipeline indices referenced identical physical inputs/checkpoint ids, with differing timing fields. Immutable publication rejected a duplicate and Executor shutdown waited for queued work. Native interruption archivedpartial299,017bytes SHA`7a3f4657127dc2ece6e0ec867d0b8171cb02cf19ca851da88b6b221b837aab6e`; API stop independently verified. Exact unpublished work count unavailable; paid ledger includes it.
- Recovery preserved original inputs/protocols, added public Pool fail-fast/error capture and exact design deduplication with equal/prefix count consistency. 866 logged checks became804 distinct interventions within30 independent bases. All804 uniformly rerun; all17 overlapping physical predictions equal except timing. Physics, hypothesis construction, seeds, target and verification remained unchanged. See EM-1 engineering amendments1/2.
- Original Linux/Python3.12 analysis repeated byte-exactly. Windows/Python3.11 immutable re-analysis refused path-index and last-bit numeric differences; original evidence stayed untouched. Post-run path formatting fixed/tested; no numerical method changed. All hashes/counts/choices match,16float differences max1.77636e-15 documented. Python3.12 changed float summation; retain original interpreter for exact reuse (amendment3).
- Full archive1,030,524bytes SHA`dbfc677101a6430ce7fa829d0a3e22ac07697f24b90fae3b9ad5db6317b14236`,818manifest files verified. Both VMs STOPPED after retrieval; conservative additional$1.097/0.517paid batch hours, TF$0. Audit G0 stopped scientifically at NOT EVALUABLE/NO-GO; no learner/prospective run was attempted to force a positive result.

## 2026-10-25 — DI-1 legacy threshold serialization and autonomous stop

- V2's complete eight-attempt/five-qualified-base policy worklist finished, then generation replay failed on legacy threshold list-of-tuples versus JSON list-of-lists. Numeric values were identical; exit1/end1792963823 and failed64replayjobs were preserved. Amendment3/source `2a4f7d4` normalizes sequence representation while keeping exact numeric/key comparison; regression test still rejects changed walking counts. No policy/FULL outcome was rerun or selected for recovery.
- All8attempts uniformly replayed into a new audit directory:384jobs,0physics errors, exact saved qualification/threshold results. All64earlier overlap jobs matched exact scientific fields except timing. Native v1 reanalysis and v2 exact immutable repeat passed, with8guards. Original failed archive09b98c476d5c8a52febc4e3f4d877f0816078488bc4714c1fb6778976e3df5c4 remains unchanged; successful post-audit archive7525cb7305aaa0d5089da81f20195f12e83e61a867b960cd15bd110361b5a940. Three archives/200manifest entries verified.
- A laptop tool action hit automatic approval review's usage limit and did not execute. After the user restored usage, control-plane inspection confirmed native SA stop had already succeeded; v2 stop request21:30:28UTC. Existing detached supervisor/root deadline did not depend on the chat continuing. The laptop ledger conservatively charges until observed STOPPED rather than backdating to an unobserved state. Bounded restart completed retrieval/uniform audit; final bothVMsSTOPPED22:36:47UTC, conservativeCloud$4.124/1.943paidbatchhours. The usage rejection was resolved; no authentication/IAM expansion or outstanding approval blocker.
- Pilot gate is NOT EVALUABLE/NO-GO on precision/resource grounds, independently of the repaired engineering error. Source/protocol, equal caps, methods, failed outcomes and original FULL thresholds remain preserved. See `docs/DI1_RESULTS.md`, development `di1/PILOT_AMENDMENT_3.md`, native analyses and final API receipt.


## 2026-10-26 - VEL-2 native launcher ownership and accounting

First systemd-run omitted --uid=forge and ran the research script asroot. Git rejected ownership, exit128 before tests/physics; native finisher preserved504-byte archive efdd4a835947efeacf4b88d94a46dae81737cf3dde32ada02ab8a606fa5657d7 and API-stopped. Corrected launcher to --uid=forge --gid=forge --setenv=HOME=/home/forge; same frozene04d3ec source/candidates/seeds/gate,30/30 measurements completed. No scientific reruns/discarded outcomes. Preserve failurejournal/archive invel2/results/operations. Future native launch must name checkout owner; do not bypass Git ownership protection. One read-only inspection hit PowerShell CRLF stdin; LF-normalized Python bytes corrected transport.

Post-pool multiprocessing semaphore cleanup warnings remain in rawdriverlog; low-levelcause unestablished. Independent replay/arrayaudit finds0ERROR/missing seeds and nativeexit0; do not claim warning-free runtime or rerun science to hidewarnings. Control-plane states helper does not close local spend intervals. After retained API STOPPED proof, appended finalstop at proofepoch1792974130 (no interveningstart), preventing fictitious continuingcompute. Earlier interval leftconservative throughnextstart. Final ledgerincrement$0.339 notinvoice. BothVMs reconfirmedSTOPPED.
