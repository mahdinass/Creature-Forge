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

## 2026-10-13 — Nebius endpoint and model verified (supersedes "base URL not hardcoded")
- **Status:** active. Base URL `https://api.tokenfactory.nebius.com/v1` (stated in Nebius quickstart docs and owner-verified catalog; old `api.studio.nebius.com` guess was wrong/obsolete). OpenAI-compatible `POST /chat/completions`, Bearer auth.
- **Evidence:** one live call, `scripts/nebius_connectivity_test.py`: HTTP 200, model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, 1.17 s, usage 23 prompt + 51 completion tokens for a one-word reply (reasoning tokens are billed and count toward `max_tokens`; budget for it), finish_reason `stop`. Redacted record in `artifacts/nebius/` (gitignored). Structured-output/JSON-schema support: **not yet verified**.

## 2026-10-13 — Physics Investigator trust boundary
- **Status:** active, implemented (fake-model verified; no live investigation yet).
- **Decision:** model output is limited to {claim, cited evidence paths, prediction(metric,direction), confidence, ONE body-parameter intervention}. All fields validated locally (exact keys, finite numbers, `BOUNDS`, existing evidence paths, non-noop); out-of-range is rejected, never clipped. Verdict = deterministic matched-seed MuJoCo comparison (`accepted` = prediction held AND fall rate decreased, or equal with ≥0.02 m mean-min-height gain); model confidence is never used. Every outcome (accepted, rejected, invalid, error, budget) is saved as a `Trial` JSON in `artifacts/investigations/`. Max one model request per investigation; client has no retries. Gait parameters are out of scope for interventions in v1.
- **Reasoning:** `reasoning_effort` is a per-call setting, recorded in each trial. "none" is accepted by Nebius for Nemotron 3 Nano but returned null content on a trivial prompt (2026-10-13) — do not assume it is usable or scientifically equivalent.

## 2026-10-13 - Phase 1 evaluation protocol and trust rules
- **Status:** active, implemented. Candidates from ANY proposer are judged only by `evaluation.py`: held-out seeds 200-209, pushes 15-35 N, tier rule fixed before live calls (`experiments/phase1/protocol.json`). A better secondary metric alone never counts; a push level where the candidate is worse blocks success.
- **Forensic-variant validation:** a mechanism label and >=2 distinct scalar citations under `forensics.` (not definitions) are required. Labels are recorded, never used by the verifier.
- **Baselines:** random is uninformed (seeded uniform parameter and value); heuristic prior knowledge is disclosed in `proposers.py`. Compare per-proposal success and budgets, not one model call against best-of-many.
- **History rewrite:** AI co-author trailers removed from two unpublished commits (filter-branch, trees identical, identity preserved, backup branch kept). New commits omit those trailers at the owner's request.

## 2026-10-13 - Cross-platform reproducibility policy
- **Status:** active. Phase 1 prompt hashes differ on Linux because MuJoCo float low-order bits differ (max rel 3.9e-14; no categorical or structural difference; independent of NumPy 2.4.6 vs 2.5.4).
- **Decision:** keep `protocol.json` untouched; test A re-hashes the stored frozen prompts exactly on every platform; test B regenerates evidence and compares it to the registered reference with exact categorical/structural matching and rtol 1e-9 / atol 1e-12 for floats. No platform-scoped skip, no rounding to match hashes. The `run_phase1_live.py` safeguard is unchanged. Pin `mujoco==3.15.0`, `numpy>=2.4.6,<2.6`. Details: `docs/REPRODUCIBILITY.md`.

## 2026-10-13 - Investigation Lab (Phase 1.5) design rules
- **Status:** active, implemented on `feature/phase1.5-investigation-lab`.
- **Decisions:** (1) Studio shows saved trials read-only; MuJoCo stays authoritative and the frontend computes nothing. (2) Real demo data = byte-identical copies of the 4 actual 2026-10-13 live trials in `experiments/demo_trials/` (hash manifest, `-text` attribute); no accepted trial exists and none is fabricated; the manual 16 cm foot is labelled a human reference. (3) Origin is encoded visually and in text: solid = MuJoCo-measured, dashed = model-written, dotted = self-reported confidence. (4) Replay re-runs MuJoCo from saved parameters and reports whether fresh per-seed numbers match the saved record (tolerance policy of `docs/REPRODUCIBILITY.md`); held-out recompute is a script. (5) The lab never imports the Nebius client.
- **Fix found on the way:** drei `<Html>` push label caused `removeChild` page errors on viewport unmount (pre-existing); replaced by a DOM overlay.

## 2026-10-13 - Phase 2A locomotion design rules
- **Status:** active, on `feature/phase2a-locomotion`.
- **Decisions:** (1) Forward displacement never counts as walking: hard physical gates (upright, valid alternating forward steps, chatter, flight, slip, body contact, saturation) plus a separate continuous fitness so failing candidates stay rankable. (2) Controller = compact phase clock with duty factor, debounced force-based contact estimator (shared online/offline), guarded phase sync, stance-gated torso-pitch and ankle feedback; the Phase 0 controllers are unchanged. (3) Random search and bounded DE (no polishing) at an identical 600-rollout budget, shared initial population, worker-count-independent results. (4) Pre-registration: protocol committed before optimisation; held-out seeds touched once after the selection was committed (script-enforced). (5) Reported honestly as partial (70% held-out walking vs 90% required).
- **Not decided / open:** FSM vs phase controller (no evidence yet for an FSM); larger budgets (need review).

## 2026-10-14 - Run R1 on a Nebius CPU VM (eu-west1)
- **Decision:** CPU-only `cpu-d3` 8vcpu-32gb in eu-west1 (quota 0 in eu-north1/us-central1); Nebius CLI via WSL Ubuntu; dedicated SSH key; code shipped as git bundle (no GitHub token on VM); deadman timer + Windows watchdog task for cost control; `core.autocrlf=true` on the VM to reproduce registered hash bytes. See `docs/NEBIUS_CLOUD_R1.md`.
