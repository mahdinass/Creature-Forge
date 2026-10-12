# Creature Forge â€” incidents and proven fixes

Append one incident per significant recurring failure. Mark everything here as `observed`, `hypothesized`, `verified`, or `superseded`. Never claim a workaround succeeded without a command/log/test demonstrating it.

## Template

### YYYY-MM-DD â€” Concise incident name
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
