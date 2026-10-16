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
