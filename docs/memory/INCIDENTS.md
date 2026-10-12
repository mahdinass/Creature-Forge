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
- Status: open. Sinusoidal hip/knee gaits tried (0.6-1.5 Hz) all fell within 10 s or walked backward; only standing balance is validated. Phase 1 should search/optimise a gait with a fair classical baseline.

### 2026-10-13 — "Visual-only" leg offset changed the physics (Phase 0.5)
- Status: reverted; mitigated by a regression test.
- Symptom: moving the left/right legs +-0.07 m apart in y inside the MJCF (to make the legs distinguishable in the viewer) changed the Phase 0 result: baseline (8 cm foot, 25 N push) fall rate dropped from 5/5 to 3/5; 3 tests failed. A torso-box widening also doubled torso mass (density used a hard-coded volume) until fixed, but mass was NOT the cause of the remaining change.
- Cause (not fully isolated): contact outcomes near the tipping boundary are sensitive to small solver/geometry changes. Re-measured frontier with the offset: 8 cm foot fell 0/5 at 15 N, 2/5 at 20 N, 3/5 at 25 N, 5/5 at 30 N.
- Fix: model reverted (morphology.py identical to reviewed commit 5a13a09); the offset is a declared presentation transform (`scene.display_lateral_offset`, applied only by the viewer). Test: `test_model_stays_planar_and_lateral_leg_offset_is_display_only`.
- Implication: the Phase 0 headline "8 cm foot falls 5/5 at 25 N" sits close to the frontier; treat it as a result for this exact model and seed set, not a robust margin.
- Also fixed: spawn height used `1.5 * half_height` instead of the exact lowest foot point, so the creature dropped ~1 cm at t=0 (found by the first viewer-export test; Phase 0 results unchanged after the fix).
- Also fixed: Phase 0 docs commit 5a13a09 contained invalid UTF-8 in PROJECT_STATE.md, DECISIONS.md and INCIDENTS.md (Python wrote cp1252 em dashes on Windows). Repaired here; always pass `encoding='utf-8'`.
