# Creature Forge — durable decisions

This is the Git-visible decision index. Add one dated section per consequential choice, with status (`active`, `superseded`, or `proposed`), alternatives, reason and concrete evidence. Prefer succinct entries linking to ADRs/commits instead of copying large discussions.

## 2026-10-13 — Memory architecture

- **Status:** active as repository policy; external MCP not yet connected.
- **Decision:** use `AGENTS.md` + `CLAUDE.md` + verified `PROJECT_STATE.md` for every agent; Git-tracked decisions/incidents for fallback; Basic Memory MCP as an optional semantic/linked cross-tool store.
- **Why:** memory notes must never override filesystem or tests; remote connection cannot be assumed.
- **Evidence:** `docs/MEMORY_SYSTEM.md`, `scripts/context_preflight.py`, `.claude/settings.json`.
- **Revisit if:** cross-tool authentication, retrieval quality or maintenance overhead fails evaluation.

## 2026-10-13 — Physics and AI separation

- **Status:** design decision, not implemented.
- **Decision:** MuJoCo is authoritative for physics; NVIDIA Nemotron through Nebius proposes falsifiable hypotheses and experiments; deterministic verifier adjudicates outcomes.
- **Evidence:** `docs/PROJECT_SPEC.md` sections 4–5 and 9–11.
- **Revisit if:** new backend exhibits better validated physical accuracy and comparable reproducibility.

## 2026-10-13 — Phase 0 creature and environment
- **Status:** active, implemented.
- **Decision:** planar (xz) biped with hip/knee/ankle motors, parameters bounded in `creature_forge/morphology.py` (`BipedParams`, `BOUNDS`), generated MJCF; baseline = joint PD + ankle balance feedback (`controller.py`). Dedicated `.venv` (none existed; verified by preflight and `guard_venv.py` dirs) created with `uv venv --python 3.11`, deps from `pyproject.toml` (`mujoco`, `numpy`). Tests use stdlib `unittest` (no new test dependency).
- **Why:** a biped exposes slip, saturation and tipping failures; planar keeps contact physics inspectable. Hopper deferred.
- **Evidence:** measured push-recovery frontier (3 seeds): default 8 cm foot falls at 20 N, 16 cm foot survives up to 30 N and falls at 40 N, 26 cm foot survives 40 N; torque limit (20 vs 150 N·m) and friction (0.1-0.3) did not change the outcome in that range. Foot length is the dominant lever for this disturbance.
- **Revisit if:** 3D or contact-richer morphologies replace the planar model.

## 2026-10-13 — Nebius base URL not hardcoded as fact
- **Status:** active. `scripts/nebius_check.py` default `https://api.studio.nebius.com/v1` is an **unverified assumption** from memory; confirm against current Nebius docs before the first live call. `NEBIUS_API_KEY` unset at this date, so no inference was attempted.

## 2026-10-13 — Studio architecture (Phase 0.5)
- **Status:** active, implemented on branch `feature/phase0.5-studio`.
- **Decision:** MuJoCo rollouts are recorded server-side (`run_rollout(record_poses=True)`: geom world pose + foot contact points per 200 Hz frame), converted once in Python to three.js Y-up (`render_export.py`: (x,y,z)->(x,z,-y), quaternion conjugated; unit-tested) and replayed by a React + React Three Fiber client (`studio/`). FastAPI (`creature_forge/studio/app.py`) exposes `/api/schema`, `/api/simulate`, `/api/experiments/phase0`, `/api/sketch/*` and contains no physics. One zustand clock drives all viewports (sim time and wall replay time shown separately). Bounds violations return 422 (never clipped). Sketch boundary: `creature_forge/sketch.py` compiles only the straight-leg biped template and rejects everything else with reasons.
- **Alternatives rejected:** frontend physics (violates MuJoCo authority); WASM MuJoCo in the browser (possible later for live interactivity).
- **Revisit if:** live interactive stepping or larger payloads are needed (binary frames / WebSocket).
