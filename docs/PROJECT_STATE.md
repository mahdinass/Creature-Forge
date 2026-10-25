# Creature Forge — observed current project state

> **Current state (2026-10-18): read `docs/RESEARCH_HANDOFF_2026-10-18.md` first.** This file is an append-only log; the
> header and early sections below describe 2026-10-13 and are historical.

Updated: 2026-10-13. Local environment audit **reported by Claude Code and relayed by project owner**; ChatGPT has not executed these checks on the Windows machine. Facts may change; always rerun the preflight.

## GitHub / implementation

- Repository: `mahdinass/Creature-Forge`, branch `main` (private when last inspected).
- Master design blueprint: `docs/PROJECT_SPEC.md`; planned, not implemented.
- Shared instructions, local memory guide, preflight and guard tests are committed.
- As of Claude's audit at local commit `fade5d8`, no project scaffolding, Python venv, package manifests, frontend or physics simulator were present. This GitHub documentation update is **newer** than that local audit. Pull before working.

## Local toolchain — Claude-reported audit

- Windows local memory: Basic Memory `0.23.2`, local SQLite, `creature-forge` default project at `<user home>/basic-memory/creature-forge`.
- Basic Memory operations: **write, read-by-permalink, text search and recent-activity confirmed by Claude**; hybrid/semantic query took ~2 minutes and missed a known note. Use `search_type="text"` until proven otherwise.
- Python reported as system `3.11.9`. The Basic Memory installed tool may use a separate uv-managed interpreter; do not infer the project has Python 3.12. No venv was detected within the scanned repository depth, **not proof no environment exists elsewhere**.
- `uv`, `node`, `npm`, `git`, `basic-memory` were reported on PATH. `conda`, `nvidia-smi` were not; this alone is not a complete GPU availability test.
- `NEBIUS_API_KEY` unset and no `.env`; Nebius runtime inference not tested.
- Claude's separate GitHub plugin MCP reported HTTP 400 Authorization header error; local `git` and our ChatGPT GitHub connection are separate.

## Still unverified

- Cross-tool **Codex → Basic Memory** retrieval: **confirmed 2026-10-13** (text search + read_note). Codex filesystem verification remained blocked by its Windows command runner.
- Local Claude Code SessionStart and venv PreToolUse hooks (must run the committed tests on Windows).
- Semantic index and similarity threshold behavior.
- Nebius credit redemption, model availability, inference, and actual physics simulation.

## Next actions

1. Pull current `main` docs into the clean local repository.
2. **Completed:** Codex retrieved Claude's note via Basic Memory text search + read_note. **Pending:** inspect the local repo in standalone PowerShell because Codex's workspace execution failed before commands could run.
3. Run `python scripts/context_preflight.py` and `python -m unittest discover -s tests -v`; record actual results and resolve Windows-specific hook issues if any.
4. Once cross-agent retrieval is confirmed, begin Phase 0/T0: toolchain + Nebius runtime verification, MuJoCo physical rollout, telemetry and fall detection.

## Maintenance rule

Update with date, exact commands/tests, linked log or commit, scope, unresolved issues and next step. Incomplete facts must be labeled not checked. Source code and tests supersede notes.
## Cross-agent verification: Codex report (2026-10-13)

- **Confirmed by Codex:** Connected to local Basic Memory MCP, ran diagnostics, used text `search_notes`, and successfully `read_note` for Claude Code's previously written note at `creature-forge/environment/environment-and-memory-setup-audit-2026-10-13`. Cross-tool note visibility is therefore verified.
- Basic Memory compatibility `fetch` returned `Unsupported MCP Client`; use `read_note` instead. This did **not** prevent retrieval.
- **Blocked:** Codex could not run *any* local PowerShell command, including file reads and Python environment verification: `Failed to create unified exec process: helper_unknown_error: setup refresh had errors`. No local code or environment changes were reported by Codex.
- **Not established by Codex:** Independent current local Python/venv state, local safety-hook behavior, or repository test execution. Claude's prior observations are not a substitute for these checks.
- **Immediate action:** Run `python scripts/context_preflight.py` and `python -m unittest discover -s tests -v` directly in standalone Windows PowerShell. If these succeed, isolate Codex's command-execution runtime; look at known Windows sandbox-related Codex issues. Do not delete sandboxes or weaken execution security as a first troubleshooting step.

## Windows PowerShell verification — 2026-10-13 (user-provided execution results)

- Working directory: `<repository root>`.
- `git status`: clean `main`, tracking `origin/main`; `git pull --ff-only` succeeded and advanced local HEAD from `24a9008` to `488cc05` at time of audit. Later documentation commits still require a new pull.
- `python scripts/context_preflight.py`: successful; current interpreter `<user home>\\AppData\\Local\\Programs\\Python\\Python311\\python.exe`, Python `3.11.9`, `VIRTUAL_ENV=False`, no known project venv directories reported; no `pyproject.toml`, `requirements.txt`, `package.json` or lockfile yet. These are observed at audit time, not permanent declarations.
- `python -m unittest discover -s tests -v`: **4 tests passed**, including duplicate-venv guard behavior and hook JSON parsing. This verifies the tested Python logic but does not alone prove Claude Code actually invoked its hooks.
- Codex separately attempted `Get-Location` but every sandbox shell command still failed before launch with `helper_unknown_error: setup refresh had errors`. Standalone PowerShell is healthy; Codex sandbox diagnostics/log inspection remains to be done. Do not alter Windows ACLs or disable security without identifying the log's specific cause.


## Codex Windows sandbox root-cause evidence — 2026-10-13

From the local `$HOME\.codex\.sandbox\sandbox*.log` provided by the project owner:

- FATAL: `runtime read/execute validation failed` when the Codex Windows sandbox setup attempts an ACL operation on `%LOCALAPPDATA%\OpenAI\Codex\runtimes\cua_node\3dd31cfff853001c\bin\node_repl.exe`.
- Windows returns `os error 32` (sharing violation: the file is in use). The setup process exits status 1; consequently `Get-Location` / `Get-Content` fail *before* PowerShell starts.
- An earlier file-lock warning for the user profile states `continuing setup` and is not the decisive failure.
- This matches multiple reported openai/codex Windows regressions during October 7–12, 2026, e.g. https://github.com/openai/codex/issues/52000 and https://github.com/openai/codex/issues/51981 . Some reports persist after restart or reinstall. Exact locking process was not identified from these logs; it may be a Codex-owned helper.
- **Safe next actions:** check for an official Codex update, quit all Codex app/CLI/VS Code integrations completely and restart Windows, then test one `Get-Location` with the normal sandbox. If still failing, leave sandbox restrictions intact and proceed with Claude Code while monitoring upstream fix. Do not delete `node_repl.exe`, indiscriminately kill processes, rewrite ACLs, or enable full access as a default remedy.

## Phase 0 / T0 physics foundation — 2026-10-13 (verified by Claude Code in this session)

**Implemented (code, not plans):** `creature_forge/{morphology,controller,simulate,failures,experiment,artifacts}.py`, `scripts/{run_phase0,smoke_test,nebius_check}.py`, `pyproject.toml`, `.venv` (Python 3.11.9, MuJoCo 3.15.0, NumPy 2.4.6; venv is gitignored).

**Evidence:**
- `.venv\Scripts\python -m unittest discover -s tests -v`: 23 tests pass (4 pre-existing guard tests + 19 new, written test-first; red runs observed).
- `.venv\Scripts\python scripts\smoke_test.py`: 6/6 checks, exit 0 (10 s headless rollout, determinism by SHA-256 of telemetry, fall detection, parameter-change effect, artifacts).
- `.venv\Scripts\python scripts
un_phase0.py`: 25 N push; foot_length 0.08 m falls on 5/5 seeds (fall at ~1.85 s, min torso height 0.03 m); changing only foot_length to 0.16 m falls on 0/5 (min height 0.76 m). Artifacts in `artifacts/phase0/` (gitignored): `telemetry.npz` + `manifest.json` per run.
- Telemetry (200 Hz): torso pose/velocity, joint angles/velocities, applied and demanded torque, COM position/velocity, per-foot contact, slip speed, contact force. Detectors: fall, actuator saturation, foot slip (event + evidence; no causal claim).

**Limitations / not done:** only standing balance + push recovery validated; open-loop walking gaits fell or walked backward (see INCIDENTS). Planar model; no hopper; no video/frontend viewer; no failure *causal* attribution yet (saturation/slip detectors were unit-tested on synthetic data and are quiet in the push experiment; torque and friction showed no effect there). Nebius: `NEBIUS_API_KEY` unset, **no API call made, nothing verified**; endpoint URL in `nebius_check.py` is an unverified assumption. Local `git push` not done.

**Next:** Phase 1 - failure autopsy features, hypothesis schema, gait search with a classical baseline, Nemotron once a key exists.

## Phase 0.5 Creature Forge Studio - 2026-10-13 (branch `feature/phase0.5-studio`, based on 5a13a09, not pushed)

**Implemented and verified:** pose export (`creature_forge/render_export.py`), sketch compiler (`creature_forge/sketch.py`), FastAPI backend (`creature_forge/studio/app.py`), React/R3F frontend (`studio/`), launcher `scripts/run_studio.py`, end-to-end check `scripts/studio_e2e_check.py`.
- Run: `.venv\Scripts\python scripts
un_studio.py` then open http://127.0.0.1:8000 (after `npm --prefix studio install && npm --prefix studio run build`). Deep links: `/?tab=compare&t=2.0`.
- Evidence: `.venv\Scripts\python -m unittest discover -s tests` = 41 passed (23 original kept + 18 new); `npm --prefix studio test` = 6 passed; `npm --prefix studio run build` (strict tsc) ok; `scripts/studio_e2e_check.py --browser` = 13/13 checks including headless Edge rendering the fall banner at the MuJoCo-detected 1.85 s. Screenshots inspected manually (Studio fall, Compare, Sketch).
- Features: orbit/pan/zoom viewer, ground grid and lights, contact rings (green; orange when slipping), push arrow only during the applied force, playback (play/pause/restart/0.1-1x/scrub/follow), failure markers on timeline and chart, morphology sliders (bounds from backend schema) with Forge button, side-by-side 8 cm vs 16 cm replay on one shared clock with matched-seed table, constrained sketch editor (hip/knee/ankle vertical, toe horizontal).
- Limitations: replay of recorded rollouts only (no live stepping); each Forge call is a full 5 s server run; the Forge/slider click path is covered by API tests but not by an automated browser interaction test; legs are drawn 7 cm apart as a declared display transform (model is planar); sketch supports only the straight-leg biped template (no bent knees, no arbitrary drawings, fixed torso geometry); frame payload about 0.9 MB per run as JSON; only tested in headless Edge.
- Incident: see INCIDENTS (leg offset changed physics; Phase 0 "5/5 at 25 N" is near the tipping frontier; invalid-UTF-8 docs repaired).

## Nebius connectivity — 2026-10-13 (branch `feature/phase0.5-studio`)
- `NEBIUS_API_KEY` present in the Claude Code process (boolean check only; value never printed). Supersedes the earlier "unset" note.
- ONE real chat completion succeeded (no retries, max_tokens=256): model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, HTTP 200, 1.167 s, prompt 23 / completion 51 / total 74 tokens, request id `fbc1bdb54e82ef63932e036d724b33cb`. A one-word answer used 51 completion tokens, so the model emits hidden reasoning.
- NOT done: reusable client, Physics Investigator, any end-to-end AI experiment. The AI investigator is **not** claimed to work.

## Nebius client + Physics Investigator (fake-model verified) — 2026-10-13
- **Reasoning test (1 real call, `scripts/nebius_reasoning_test.py`):** `reasoning_effort:"none"`, max_tokens=128 → HTTP 200 (accepted), usage 23+2=25 tokens (vs 74), latency 0.415 s (vs 1.167 s), finish_reason `stop`, but **`content` was null** while a reasoning-type field was non-empty. So "none" is accepted and cheap but did NOT return a usable answer for this simple prompt. Reasoning-control probing stopped per instruction; the client treats null content as a failed trial. Request id `0d8e5f9d94548b8283464e925c4e1d0f`. Scientific equivalence of reasoning modes is untested.
- **Implemented:** `creature_forge/nebius.py` (injectable transport, request/token/per-request/timeout limits, no retries, key excluded from repr/logs), `creature_forge/investigator.py` (evidence → hypothesis → intervention → MuJoCo verification; strict schema; `Trial` record with separate observed/model/measured sections), read-only Studio endpoints `GET /api/investigations[/{id}]`, `scripts/run_investigation.py` (`--estimate` / `--live`), `evaluate_design` alias in `experiment.py`.
- **Evidence:** `.venv\Scripts\python -m unittest discover -s tests` = 63 tests (41 prior + 21 new client/investigator + 1 API); all use fake transports, zero network calls. Fake-model pipeline: accepted case (foot 0.08→0.16: fall rate 1.0→0.0 over 5 matched seeds), verifier-rejected case (torque_limit change), invalid JSON, null content, model error (single call, no retry), budget exceeded (no call), configurable reasoning_effort. Tests were written alongside the code, not strictly red-first.
- **NOT done / not claimed:** no real investigation has run; the AI investigator is **not verified end-to-end**. JSON-schema `response_format` is untested (client supports it; investigator does not use it). Studio frontend does not yet render trials (API only).
- **Estimate for one real investigation:** prompt ≈ 850–1000 tokens (measured 2,545 chars); completion cap 4096 incl. hidden reasoning; expected total ≈ 1.5–4k, hard ceiling ≈ 5k tokens, 1 request.

## First live Physics Investigator trial — 2026-10-13 (trial `20261013T002054Z-aaad96`, mode `live`)
- **Setup:** Phase 0 failure (8 cm foot, 25 N push for 0.15 s, 5 s). Evidence seeds (0,1,2), verification seeds (0-4). Default reasoning (no `reasoning_effort`), `max_tokens=4096`, 1 request, no retries, timeout 90 s. Model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` at `https://api.tokenfactory.nebius.com/v1`. The model was not told the 16 cm answer.
- **Model call (verified):** HTTP 200, finish `stop`, latency 5.687 s, usage 1088 prompt + 1126 completion = 2214 tokens (hidden reasoning present), request id `611976be3910a5c013c64ab3496015f5`. Whole investigation incl. MuJoCo: 16.8 s.
- **Nemotron's hypothesis (untrusted model claim):** "Lowering the torso mass will reduce the fall_rate ... indicating that excess torso inertia drives the fall." Cited `matched_seed_results.fall_rate`; predicted fall_rate decrease; confidence 0.78; intervention `torso_mass` 5.0 -> 3.0 kg.
- **Valid output, passed local validation.** **MuJoCo verdict: REJECTED.** Fall rate 1.0 -> 1.0 (delta 0); mean min torso height 0.0340 -> 0.0329 m; mean max |pitch| 1.608 -> 1.612 rad. Prediction not met, no improvement.
- **Interpretation / limits:** this is ONE trial; it shows the pipeline completes end-to-end on a real model (evidence -> hypothesis -> bounded change -> independent MuJoCo verdict, with the verifier refuting the model), NOT that Nemotron can find a working fix. The hypothesis was weakly grounded (cited only the aggregate fall rate, ignored the fall time/pitch/slip/torque evidence) and was falsified. No comparison against random or heuristic proposers yet, no repeated trials, no other reasoning modes, `response_format` untested, Studio UI does not yet display trials (API only).
- **Config:** shared `.env` loading (`creature_forge/config.py`, python-dotenv, `override=False`); `.env` is git-ignored and untracked (tested); real env vars win; client, connectivity scripts and `run_investigation.py` share it. Fresh-process test with `NEBIUS_*` stripped from the shell loads the key from `.env`. Key not present in the trial JSON or docs (grep-verified, value never displayed).
- **Preflight before the live call:** 71 Python tests + 6 frontend tests passed; estimator offline.
- **Commit map (replaces stale SHA mentions; all local, unpushed):** `5a13a09` Phase 0 physics; `776c400` Studio (Phase 0.5); `f24eb53` Nebius connectivity + URL fix; `7492472` client + investigator (fake-verified); `00cf1c1` `.env` support; `835b012` first-trial docs. SHAs of these four were rewritten on 2026-10-13 to drop AI co-author trailers (old: 24573ba, eb70eb2, fd6d34e, 45758bd; trees identical; unpublished at the time; backup branch `backup/pre-trailer-rewrite`). Earlier text saying "base URL unverified"/"NEBIUS_API_KEY unset" is superseded; `fade5d8`/`24a9008` are historical audit points only.

## Phase 1 - forensics, baselines, pre-registered live batch (2026-10-13, branch `feature/phase0.5-studio`, unpushed)
- **Implemented (offline-tested; full suite passes):** `forensics.py` (pitch/rate, COM and extrapolated-COM margin vs the loaded-contact support interval, CoP, contact transitions, torque demand vs applied vs limit, disturbance response, instability onset/recovery, timeline), support/CoP logging in `simulate.py` (logging only), `evaluation.py` (held-out protocol + tier rule), `proposers.py` (random, heuristic), forensic variant in `investigator.py`, `trial_view.py` + `GET /api/investigations/{id}/view`, scripts `preregister_phase1.py`, `run_phase1_baselines.py`, `run_phase1_live.py` (refuses unless protocol is committed and prompt hashes match).
- **Pre-registration:** `experiments/phase1/protocol.json`, committed in `8bf6c4b` before any request. **Results:** `experiments/phase1/REPORT.md`, `results/baselines.json`, `results/live_summary.json`.
- **Verified results:** random per-proposal success 22/100 (Wilson 0.15-0.31, 5000 held-out sims); heuristic (foot x1.5 = 0.12 m) tier none; 3 live Nemotron requests (12,643 of 18,000 tokens): 2 valid replies both proposed torso_mass 5->3 and failed (worse at 15 N), 1 invalid (nonexistent evidence path). No outperformance claim is possible.
- **Not done:** Studio panel UI; response_format; repeated trials; gait optimizer baseline (walking still unsolved); nothing pushed or merged.

## Hook repair and pre-push secret audit (2026-10-13)
- **Hook fix:** the SessionStart preflight and PreToolUse venv guard used the relative path `scripts/*.py`, which failed once the working directory moved to `studio/`. `.claude/settings.json` now uses `command: "python"` with `args: ["${CLAUDE_PROJECT_DIR}/scripts/<script>.py"]`. The guard stays active. `tests/test_memory_guard.py` now asserts this format.
- **Hook verification:** from the repo root and from `studio/`, an ordinary command is allowed (rc 0) and `python -m venv` / `uv venv` are blocked (rc 2) while `.venv` exists; the preflight runs from both. Checked by running the scripts directly with the placeholder expanded; the live harness picks the new config up on its next session start.
- **Secret audit:** a temporary local scanner read the real `NEBIUS_API_KEY` from `.env` in-process (never shown, logged or passed as an argument) and compared its bytes with every blob in every commit reachable from all refs, including `backup/pre-trailer-rewrite` and the reflog (40 commits, 127 blobs), plus commit messages. **0 matches.** The earlier "matches" were the public Nebius base URL (harmless). `.env` is untracked and git-ignored.
- **Checks:** 99 Python tests, 6 frontend tests, `tsc` + `vite build`, `smoke_test.py` and `studio_e2e_check.py` pass. No Nebius calls were made.

## PR #2 review fixes (2026-10-13)
- **SPA path traversal:** `studio/app.py` catch-all now uses `resolve_static()` (resolve + `relative_to(dist)`; rejects `..`, absolute paths, prefix-sibling dirs, symlink escapes; non-files fall back to `index.html`). `create_app(dist_dir=...)` added for testing. Regression tests: `tests/test_static_serving.py` (harmless fixtures in a temp dir; real `.env` never opened).
- **Hooks, verified in real fresh `claude -p` sessions** (`--include-hook-events`): from the repo root, SessionStart ran and the PreToolUse guard blocked `python -m venv` (exit 2); the earlier direct-script tests were not sufficient. **Finding:** Claude Code reads project settings from the *launch* directory, so a session started inside `studio/` had NO hooks and an unguarded venv creation succeeded (stray `studio/.venv_dup_test` created by the test, removed). Fix: `studio/.claude/settings.json` points to `${CLAUDE_PROJECT_DIR}/../scripts/*`; re-test from `studio/`: guard blocks (exit 2), `git status` allowed. Config tests added.
- **Token budget:** `NebiusClient.chat()` previously reserved only `max_tokens`; prompt tokens counted only after the response. Now it reserves `estimate_prompt_tokens(messages)` (~3 UTF-8 bytes per token + 64; the same heuristic as the pre-registered live runner; a first attempt with 1 token/byte made the 8,000-token forensic tests and the registered 18,000-token live budget infeasible, so it was relaxed) + `max_tokens` before the call, and still adds API-reported usage afterwards. Limit: **completion is hard-capped by `max_tokens`; the prompt side is a conservative estimate, not a guarantee** (server chat-template overhead is invisible to us), so the total budget is not strictly hard on the first oversized call. Tests added for pre-call reservation and post-hoc blocking.
- **PR hygiene:** Claude Code footer removed from PR #2 body.
- **CI (GitHub Actions, first real run on this branch):** the workflow file had a duplicated `studio-frontend` job (invalid since `776c400`); removed in `49dc1fa`. `studio-frontend` now passes. `test-context-guards` (ubuntu, Python 3.12) passes everything except `test_phase1.RegistrationTests.test_registered_prompts_match_rebuilt_prompts_and_budget_is_capped`: the rebuilt *forensic* prompt hash differs on Linux from the Windows-registered one (the legacy prompt hash matches), i.e. the forensic evidence contains platform-dependent floating-point values. **Unresolved, owner decision needed** (options: platform-scope the hash check, or round evidence before hashing, which would require re-registering). Physics and pre-registration untouched.

## Cross-platform reproducibility fix (2026-10-13)
- Resolves the CI failure above. Correction: BOTH Phase 1 prompt hashes differ on Linux (the legacy one was never asserted). Measured: Windows (py3.11.9, numpy 2.4.6, mujoco 3.15.0) reproduces the registered evidence exactly; Linux (py3.12.14, numpy 2.5.4 and 2.4.6, mujoco 3.15.0; identical to each other) differs in 10 unrounded floats, max rel 3.9e-14, no structural/categorical difference. See `docs/REPRODUCIBILITY.md`.
- New: `creature_forge/reproducibility.py` (exact frozen-prompt integrity check; evidence comparison with an explicit tolerance policy; provenance record for future registrations), tests A/B in `tests/test_phase1.py`, dependency pins in `pyproject.toml`, version logging in CI. `protocol.json`, call plan, limits and results are untouched; no Nebius calls.

## Packaging check (2026-10-13)
- Found: `[tool.setuptools] packages = ["creature_forge"]` omitted `creature_forge.studio`, so a built wheel lacked the Studio API (editable installs hid it). Fixed to list both packages. Verified: `uv build --wheel` now contains `creature_forge/studio/{__init__,app}.py`; installed into an isolated target directory (with the `[studio]` extra) and imported from the wheel, not the checkout: `create_app()` works and `GET /api/schema` returns 200.
- Known limitation: the built React frontend (`studio/dist`) is not part of the wheel; Studio serves it only from a source checkout after `npm run build`.

## Integration into main (2026-10-13) - actual merged state
- **Phase 0:** PR #3 (`review/phase0-physics-93bcc43`, one commit `5a13a09`, verified as main + that commit only) merged with a merge commit: `82097b7`.
- **Phase 0.5 + Phase 1:** PR #2 (`feature/phase0.5-studio`, 14 commits, all authored by Mahdi, 0 AI co-author trailers) retargeted to `main` and merged with a merge commit (no squash): `da9b4d8a42a3f3d98d5f1a12bd77894040920453`. Individual commits, including the pre-registration (`8bf6c4b`) and experiment records, are preserved on `main`; `experiments/phase1/*` was not altered.
- **CI before merge:** `test-context-guards` and `studio-frontend` passed on the final PR head `1a61429` (push and pull_request runs). 115 Python tests, 6 frontend tests.
- **Local backup branches kept** (`backup/pre-trailer-rewrite`, and the feature/review branches were not deleted). No Nebius requests were made during integration.
- **Remaining limitations:** the Phase 1 live runner refuses on any platform whose rebuilt prompts do not hash to the registered values (e.g. Linux) by design; the built React frontend is not packaged in the wheel; Nemotron has not been shown to outperform baselines (see `experiments/phase1/REPORT.md`); walking/gait optimisation unsolved; Phase 2 not started.

## Phase 1.5 - Investigation Lab (2026-10-13, branch `feature/phase1.5-investigation-lab`, from main `d55f363`)
- **Implemented:** Investigations tab (history incl. accepted/rejected/invalid, filters, 5-step detail view Observe -> Hypothesize -> Intervene -> Verify -> Compare, provenance styling, synchronized two-robot MuJoCo replay on the existing viewport/timeline, consistency badge, graceful empty/missing/corrupt/error states, deep links). Backend `creature_forge/lab.py` + `/api/lab/*`. Bundled real demo records + manifest. Details, API and limits: `docs/INVESTIGATION_LAB.md`.
- **Replay reproducibility (requirement 7):** `python scripts/verify_demo_trials.py --full` on Windows: 4/4 hash-verified; every saved seed/arm reproduces (max rel 0.0); full 100-simulation held-out protocol reproduces for both records that have one. No model inference anywhere.
- **Tests:** 135 Python (115 + 20 new), 6 + 11 frontend, production build, `smoke_test.py`, `studio_e2e_check.py --browser`, and the real-browser lab flow (`scripts/lab_browser_check.py`: select experiment -> inspect evidence -> load simulation -> compare outcomes, invalid/error/phone-width paths) all pass locally; CI wiring added (frontend job runs the browser flow).
- **Fixed:** pre-existing `removeChild` page error when a viewport unmounts (drei `<Html>`); playwright-core added as a dev dependency (no browser download; uses system Chrome/Edge).
- **Not done / limits:** no UI to launch new investigations, no accepted AI trial exists to display, in-app held-out recompute is script-only, minimal visual polish (a dedicated phase is planned), demo records and the built frontend are not in the Python wheel. No locomotion optimisation or AI-architecture work started.
- **Review correction (2026-10-13):** the Verify step previously titled the screening table "same seeds as the evidence". Recorded Phase 1 trials used evidence seeds 0-2 and screening seeds 0-4. The lab now reads both sets from the saved record (`view.seeds`, from `config.evidence_seeds`/`verify_seeds` or the scenario/outcome metadata) and words the label from them (`screeningText`): "Screening: seeds 0-4 ... evidence came from seeds 0-2; screening re-uses all of them and adds seeds 3, 4"; "the same seeds" appears only when the sets are identical. Tests: backend seed-role test, 5 frontend wording tests, browser assertion.

## Phase 1.5 merged into main (2026-10-13) - actual state
- PR #5 (Investigation Lab, 2 commits `ebf473d`, `04e927c`, both authored by Mahdi, 0 AI co-author trailers) merged with a merge commit (no squash): `1066ee789395f549af8475bd72bc395bb3870736`. Branch was 0 commits behind main at merge.
- CI: `test-context-guards` and `studio-frontend` (which now also runs the real-browser lab flow) passed on the PR head and on the resulting `main` push run. Local: 136 Python, 22 frontend, build, smoke, Studio E2E, lab browser flow.
- Historical investigation records, physics and Phase 1 pre-registration untouched; no Nebius calls. Phase 2 not started.
- Remaining limits (unchanged): no UI to launch investigations; no accepted AI trial exists; held-out recompute is script-only; minimal visual polish; demo records and built frontend not in the wheel.

## Phase 2A - learning locomotion (2026-10-13, branch `feature/phase2a-locomotion`, from main `9ac6f72`)
- **Outcome (honest):** partial. A hybrid phase-based, contact-aware controller reached gate-validated walking (~0.5 m/s, 0.30 m steps) but not robustly: frozen random-search controller walked on **14/20 held-out seeds (70%)**; the pre-registered walking criterion (>= 90%) was **not** met. Frozen DE controller 2/20. Standing and both open-loop gaits: 0/20. Details, tables, failed attempts, limitations: `docs/PHASE2A_LOCOMOTION.md`.
- **Implemented:** `contact.py` (debounced force-based contact estimator), `phasegait.py` (PhaseGait controller + open-loop/lag adapters; Phase 0 controller untouched), `locomotion.py` (lean rollout, gates, labels, fitness), `optimize.py` (random search, bounded DE, spawn-safe pool, exact rollout accounting), `phase2a.py` (protocol, seed roles, committed-file guard), `locomotion_view.py` + `/api/locomotion/{summary,replay}`, Studio "Locomotion" tab, scripts `diagnose_locomotion.py`, `preregister_phase2a.py`, `run_phase2a.py`, `eval_phase2a_heldout.py`, `ablate_phase2a.py`, browser flow `studio/e2e/locomotion-flow.mjs`.
- **Protocol:** `experiments/phase2a/protocol.json` committed (`2f3df1c`) before optimisation; held-out run only after `selection.json` was committed. Budget 600 rollouts per method (200 candidates x 3 seeds), single run each. Phase 0/1/1.5 records untouched; no Nebius calls.
- **Key findings:** existing open-loop family never walks (0/1000 sampled gaits across both families); a forward-moving phase-lag candidate was a chatter-hop exploit (kept as regression test); stance pitch feedback and ankle balance are essential (ablation); contact-informed phase sync is not shown to help; failures on inspected seeds are startup falls backward.
- **Not done / limits:** one planar morphology, one optimiser run per method (RS vs DE comparison anecdotal), 3 training seeds gave a seed-fragile winner, gait thresholds not sensitivity-tested, backward drift of open-loop gaits not root-caused. No larger campaign or Phase 2B started; next step needs review (robustness-aware training, startup strategy; FSM not yet justified).
- **Review follow-up (2026-10-14, PR #7):** CI failure fixed - the Locomotion tables had ~349 px of unbreakable content and overflowed the page at <= 360 px (18 px with the Linux CI font); they now scroll inside `.table-scroll`. `Locomotion.tsx` now clears the replay when the controller or seed changes and discards responses from superseded requests. Browser regression assertions added (checked to fail on the old code); both CI jobs pass. Post-hoc diagnosis of the six held-out failures (`docs/PHASE2A_FAILURE_DIAGNOSIS.md`, `experiments/phase2a/results/failure_diagnosis.json`): all six never established forward stepping (0-1 valid steps, backward drift, single-support backward fall; one at 7.07 s after ~6 s of marching in place); no torque saturation; no early-window variable cleanly separates them from walking seeds; no causal mechanism claimed. 30 rollout executions (10 distinct, deterministic) were run against a review cap of 20 - disclosed in the artifact. Held-out seeds 3000-3019 are consumed. **Proposed R1 robustness experiment (8 train seeds, lower-tail objective, optional 2-parameter gait-initiation extension, fresh seeds 4000-6029, cap 8,500 rollouts) is awaiting approval; not run.** Phase 2A numbers unchanged (14/20, DE 2/20, 90% threshold).

## Nebius CPU VM for R1 (2026-10-14, branch `feature/phase2a-r1-robustness`)
- VM `creature-forge-r1-cpu` (eu-west1, cpu-d3 8vcpu-32gb, 50 GiB disk, $0.269/h) created, bootstrapped and checked; currently **STOPPED** (disk bills ~$0.12/day). Details, commands, safeguards and findings: `docs/NEBIUS_CLOUD_R1.md`. Controller: `infra/nebius/forge_cloud.py`.
- Compatibility/reproducibility on the VM passed (Windows-reference match, max rel 5.5e-15); 207/208 tests pass, the exception being a bit-exact cross-platform test (known libm noise). **R1 not started, pilot not run, ledger empty**; protocol untouched.
- Finding: R1's registered file hashes cover CRLF Windows bytes; Linux needs `core.autocrlf=true` (handled in bootstrap).
- Credit balance and the public-IP price are not verified via the CLI.

## R1 executed - NULL result (2026-10-14)
- Pilot passed (15 rollouts/s, 65 MB/worker); replicate 1 of A/B/C trained and validated; **futility gate: STOP** (no candidate walked on any validation seed; incumbent 11/16). Replicate 2, selection and final evaluation not run; final seeds untouched. Ledger 3,872/8,500 rollouts, 81 s active wall, 0 errors. Full report: `experiments/phase2a_r1/REPORT.md`. VM is STOPPED (disk ~$0.12/day); delete with `forge_cloud.py delete --yes` when no longer needed.
- Engineering changes before the pilot: session-based wall accounting; tolerance-based cross-platform test; verified VM deadline sync on `start`.

## R1 finalization and R2 proposal (2026-10-14)
- Verified: ledger chain (working copy and committed blob), 3,872 rollouts recomputed from histories, gate STOP, protocol/Phase 1/Phase 2A files byte-identical to `f33d429`, no `final.json`/`selection.json`. Local checks run sequentially: 210 Python tests, 27 frontend tests, production build, `smoke_test.py`, `studio_e2e_check.py --browser`, `lab_browser_check.py` (includes the locomotion flow) all pass. VM STOPPED, not deleted.
- Offline analysis (no rollouts): `docs/R1_SEARCH_ANALYSIS.md`. Key points: 149 distinct sampled points not 447; none near the incumbent; the worst-2 objective ranked the incumbent 140/150; 30 final seeds were under-powered.
- R2 (local robustness around the frozen walker) is a **proposal only**: `docs/R2_DESIGN_PROPOSAL.md`; not registered, not run. Nemotron integration plan in its section 11; no live requests made.
- Basic Memory note: `creature-forge/implementation/r1-robustness-experiment-null-result-and-lessons-2026-10-14`.

## R2 executed (2026-10-14, branch `feature/phase2a-r2-local-robustness`)
- PR #8 (R1) merged into main with a merge commit (`b3ac549`). R2 protocol registered in `463c603` before any rollout; training set frozen `9c1a26f`; selection frozen `f4820f8`.
- Result: futility gate PROCEED; winner T1#101 walks 150/150 untouched final seeds vs frozen incumbent 91/150 (paired 59 vs 0). Registered hierarchy: non-inferiority (Tango score, margin 5 pp) confirmed, superiority (exact McNemar p = 3.5e-18) confirmed; engineering criterion (>= 135/150) met by the winner. Ledger 10,700 / 12,000 rollouts, 1,003 s active of 3,600 s. Report `experiments/phase2a_r2/REPORT.md`; limits: one planar morphology/distribution, Linux-only evidence (Windows replication blocked by the 4 GB free-memory floor), no causal claim about which parameters matter.
- VM STOPPED (not deleted). R3 (Nemotron physical investigations): `docs/R3_DESIGN.md` (design, offline machinery `creature_forge/r3.py`, 14 tests, no live calls) and dated plan `docs/MILESTONE_PLAN.md`.

## R3 attempt 1 aborted (2026-10-14, branch `feature/r3-nemotron-investigation`)
- PR #9 (R2 + R3 prep) merged into main (`0c7ee3e`). R3 protocol v1 corrected per review and registered (`7def51f`); contexts/prompts frozen (`196de48`); pilot, evidence pool (theta0 100/180) and screen pool (38/64) done on the VM (R3 ledger 340 / 6,000 rollouts).
- Live batch stopped after 3 of 30 requests: every reply was empty with `finish_reason=length` (hidden reasoning used all 2,200 completion tokens). 13,114 tokens used. Not a result. See `experiments/phase2a_r3/ATTEMPT1_ABORTED.md`, `docs/R3_ATTEMPT1_AND_V2_OPTIONS.md`. Awaiting a decision on a v2 protocol (generation settings / caps). VM STOPPED.

## R3 v2 outcome (2026-10-14): generation calibration failed, statistical experiment not run
- Protocol v2 registered `fa69e2c`; calibration context frozen `159617b`; 8 calibration requests under settings A-D (none/low/low/medium; 3,500/3,500/5,000/5,000): no setting passed (evidence arm returns null content at every setting; `none` also null; the control arm passed under B and D). By the registered rule no experimental request was sent. Report: `experiments/phase2a_r3/REPORT_V2.md`.
- Usage: 11 of 41 requests, 56,110 of 300,000 tokens (v1 3 + calibration 8); R3 physics ledger 356 of 6,000 rollouts (chain verified); VM STOPPED. Docs check: `reasoning_effort` accepted but not shown to shorten reasoning; `reasoning_tokens` not reported.
- No estimate exists of Nemotron-proposed vs matched-random edits. R2's improvement is classical-optimiser work and is not attributed to Nemotron.
- Next: authentic Investigation Lab demo with a short single-failure prompt (remaining combined headroom 30 requests / 243,890 tokens), clearly separating live, recorded-live and scripted results.

## AI Investigation demo (2026-10-14, branch `feature/investigation-demo`, stacked on the R3 branch)
- Studio tab **AI Investigation** with explicit provenance (LIVE / RECORDED LIVE / SCRIPTED MOCK), backend `creature_forge/demo.py`, `/api/demo/*`, CLI `scripts/run_demo.py`, docs `docs/INVESTIGATION_DEMO.md`.
- Two real Nemotron calls were made and stored as hash-verified recordings: run 1 (valid envelope, citations rejected, nothing simulated) and run 2 (two valid proposals, both improved 19/32 -> 28/32 and 25/32, but matched random edits reached 25/32 and 30/32). A labelled scripted-mock example is also bundled. Shared Nebius budget now 13 of 41 requests, 70,764 of 300,000 tokens.
- Checks: 12 backend demo tests, 13 new frontend tests (35 total), browser flow `demo-flow.mjs` (recorded run, verification table, synchronized replay, rejected-reply run, mock label, 360 px layout) inside `lab_browser_check.py`: 82 PASS, 0 FAIL.
- Not claimed: no statistical evidence about the model (R3 not run); R2's improvement is classical optimisation.

## Merges, CI fixes and submission package (2026-10-14, branch `feature/submission-polish`)
- PRs #9-#12 merged into `main` with merge commits (R3 v1/v2 protocols, raw requests, reports and ledgers preserved; R3 v3 cancelled by the owner). CI green on `main` (`19cd597`); integrated checks pass: 301 Python tests, 36 frontend tests, build, smoke, Studio E2E, real-browser flows, demo-trial reproduction.
- CI fixes: (1) PR #11: `test_combined_request_cap_is_enforced_including_v1` depended on repository usage records (CI saw 11 prior requests, so 30 were left, not 38); replaced by isolated tests for the request guard alone and the token guard alone (production checks unchanged). (2) PR #12: the UI requested demo replays by the id stored inside a bundled record while the API serves it by file name; a git-ignored local copy hid the 404 locally. Fixed by serving/using one id (`id` = file stem), with API-level tests, a frontend test, and a browser flow that now reports API errors within seconds instead of a 240 s timeout.
- New: Studio **Overview** landing tab (reads numbers from the committed records; separates the classical 150/150 vs 91/150 result from the Nemotron demo; states that the systematic comparison was not completed), judge-facing README, `docs/submission/` (storyboard, capture plan, Devpost text, Nebius/NVIDIA feedback, setup and reproduction, Nebius clarification request draft, checklist).
- Local backup refs with old trailers removed after verifying no unique work; zero trailers on any ref.

## Studio repair and UX pass (2026-10-14, branch `feature/studio-ux-repair`, from main `3dad8ca`)
- **Broken tabs, root cause (verified):** a Studio server started 2026-10-13 01:43 still held :8000 with only the Phase 0.5 routes; the SPA catch-all returned `index.html` (HTTP 200) for the newer `/api/*` calls, hence `Unexpected token '<'`. Not a data or port-mix-up (port 3000 is another project). Fixes: JSON 404 for unknown `/api/*`, `/api/version`, no-cache `index.html`, clear client error, `scripts/start_studio.ps1`, `studio/e2e/tabs-smoke.mjs` (every tab and every API response in a real browser). Details: `docs/memory/INCIDENTS.md`.
- **AI Investigation:** guided story view (`studio/src/demo/Story.tsx`), Overview call-to-action, parameter-change visual (`paramDiffs` in `demoLogic.ts`), auto-loaded synchronized replay; stepper kept as "Step-by-step details". No new records, no model calls, R1/R2/R3 evidence untouched.
- **Sketch:** `creature_forge/sketch.py` `normalize_sketch` / `support_info`, `POST /api/sketch/normalize`, `GET /api/sketch/support`; editor rewritten around direct manipulation (drag hip/knee/ankle/toe, torso-mass handle, magnetic snapping, ghost of the raw drawing, per-adjustment explanations, refusals with reasons, material sliders, compiled-MuJoCo preview). Race fixed: releasing before the debounced server answer no longer commits a stale result.
- **Checks (Windows):** 319 Python tests, 54 frontend tests, `tsc` + production build, `smoke_test.py`, `studio_e2e_check.py --browser`, `lab_browser_check.py` (all browser flows incl. new tabs-smoke and sketch-flow, 0 FAIL), `verify_demo_trials.py` (all reproduce). No Nebius calls were made.
- **Limits:** sketch remains a planar straight-leg biped; the preview shows the compiled model at t = 0 (a 0.5 s run), not a walk; story replay is one seed; only tested in headless Edge; CI wiring of the new flows is through `lab_browser_check.py` (already in CI).

## Creative redesign (2026-10-14, branch `feature/creative-redesign`, stacked on `feature/studio-ux-repair`)
- **Product:** new design system (`studio/src/theme.css`: graphite stage, journey colours Create ember / Simulate tide / Investigate violet, Bricolage Grotesque + Instrument Sans bundled locally), journey navigation, Home with a real MuJoCo hero (committed R2 controllers, replays re-run locally), freehand **Draw** (stroke canvas, roles, undo/redo/erase/zoom/pan/pinch, interpretation overlay, guided constraints ON/OFF, consent-gated approximation, 3D preview, hand-off to a real MuJoCo run with a plain-language failure account), **Refine** (previous handle editor), cinematic **AI investigation** (five-step rail, synchronized pair, animated parameter inspector, outcome bars, provenance pill; old stepper under Advanced), **Walking lab** (`/api/walking/*`, committed R2 records, clickable seed dots), grouped **Experiment history**. Plan and rationale: `docs/UX_REDESIGN.md`.
- **Backend:** `sandbox.py`, `freehand.py`, `walking.py`; endpoints `/api/sandbox/{schema,simulate}`, `/api/freehand/interpret`, `/api/walking/{summary,replay}`. Registered experiment space frozen and pinned by test.
- **Checks (Windows):** 361 Python tests, 67 frontend tests, strict `tsc`, production build, `smoke_test.py`, `studio_e2e_check.py --browser`, `verify_demo_trials.py`, and `lab_browser_check.py` (tabs, history, walking lab, AI investigation, Home, handle editor, freehand) with 0 FAIL, at 1920 px and 390/360/320 px. Screenshots: `artifacts/screenshots-redesign/` (git-ignored).
- **Acceptance:** `tests/test_sandbox_api.py` and `studio/e2e/freehand-flow.mjs` draw a terrible creature (3 cm feet, huge torso / weak motors), run it in MuJoCo with Guided constraints OFF and watch it fall; the same drawing with Guided ON is refused with the exact reason and a consent-gated approximation.
- **Not done / limits:** torso shape is fixed (mass follows drawn area); two legs only; planar; knee bends backward only; arms/tails/heads refused; no investigation on a drawn creature (recorded investigation is a different robot); freehand tested with mouse events (touch/pen use the same pointer-event path, not device-tested); only headless Edge; the stroke interpreter assumes one creature facing left or right.

## Forge Loop M0 (2026-10-14, branch `feature/forge-loop`, plan approved by the owner)
- **Goal:** Draw -> Challenge -> AI Redesign -> Verify -> Evolve on the user's own drawn creature. Contracts: `docs/FORGE_LOOP_CONTRACTS.md`. Internal deadline 2026-10-29.
- **Merged:** PR #14 (`42e4680`) and PR #15 (`e3cbe2b`) into main with merge commits, after a full regression on the Nebius VM (361 Python, vitest + build, all browser flows, smoke, demo-trial reproduction) and green CI (one CI-only race in `freehand-flow.mjs` fixed in `9bc30d2`).
- **Infra (verified):** VM `creature-forge-r1-cpu` started 2026-10-14 (new IP recorded by `forge_cloud.py`), Node 22.23.3 + Chrome 155 installed via `infra/nebius/remote/dev_bootstrap.sh` (official tarball/deb, SHA-checked Node). `infra/nebius/forge_dev.py` = sync/exec/test/serve/tunnel/pull. Spend ledger + $10 cap in `forge_cloud.py` (`spend`).
- **Implemented and tested on the VM:** `creatures.py` (versions, lineage, accept only with VERIFIED verdict, revert), `jobs.py` (background jobs, persisted events, restart -> failed), `studio/forge_api.py` mounted at `/api/forge/*`; `tests/test_frozen_records.py`. Full suite 420 tests OK (+ wiring tests).
- **Calibration (real Nebius calls, 30 requests, $0.31):** Super-120B thinking-off + strict per-evidence JSON schema selected; see `experiments/forge_loop/calibration/REPORT.md`. No redesign was simulated; this is not a quality claim.
- **In progress:** challenges/walk adaptation/pool (S1), evidence/interventions/forge_ai/ledger (S2), frontend workspace (S5). Not started: arena/verdict/baselines (S3), investigation orchestration, evolve UI.

## Forge Loop M1/M2 core (2026-10-15, `feature/forge-loop` @ eec425f)
- **Implemented, VM-tested (664 Python tests OK):** `challenges.py` (stand/push/walk, settle window, critical-force bisection, FAIL/POOR/PASS/ERROR), `creature_walk.py` (sandbox walking, body-scaled gates, (1+8)-ES adaptation), `forge_pool.py`; `evidence.py`, `interventions.py`, `forge_ai.py`, `inference_ledger.py`, `nebius.py` `extra_body`; cross-module test `tests/test_forge_integration.py` (real MuJoCo challenge -> evidence -> schema -> validator -> edited body runs).
- **Zoo pilot (4,080 rollouts):** default/balanced/bird-knees stand and walk; tiny-feet/top-heavy/stilts/doomed fall without a push; push critical force default 32.5 N forward vs 10 N backward (weak direction everywhere) -> default target 10 N; stand/push near-deterministic across seeds (spread ~one 2.5 N bisection step); walk adaptation helps only tiny-feet (0 -> 3-4/8 at K=48) and overfits elsewhere. `experiments/forge_loop/pilot/README.md`.
- **Fixed:** freehand refused the Top-heavy and Stilts starters ("feet point in opposite directions"); feet are now matched to legs jointly (`tests/test_freehand_starters.py`).
- **In progress:** arena/baselines/verdict + A/A null pilot (S3), investigation orchestration + API (S6), frontend workspace (S5).

## Forge Loop end to end, live (2026-10-15, `feature/forge-loop` @ 7d45008)
- **Integrated and VM-tested (777 Python tests OK; frontend 117 vitest + build; 214 browser checks):** arena (original, AI arms, matched-random twins, heuristic; screening then held-out validation; the selected AI arm is always validated with its own twin), `verdict_v1` (frozen after an A/A null pilot: 0 false alarms in 48 A/A comparisons; ~15 % of random push edits verify, so AI verdicts are always shown beside their twin's), investigation orchestration + bounded loop (patience 2, never auto-accepts), accept/revert API, `scripts/forge_acceptance.py` (draw -> challenge -> investigate -> verdict -> accept-if-verified over real HTTP).
- **Live runs (Nemotron-3-Super via Nebius):** 9 investigations of drawn creatures, archived unedited in `experiments/forge_loop/dev_live_records/` with protocol-state notes. Mostly honest negatives (NOT_VERIFIED / INCONCLUSIVE). First VERIFIED redesign: `i-f9873480e42a` (balanced creature, push; rear foot x1.25 after a falsified friction proposal; +3.125 N, 12/0/0 on 12 held-out seeds). Anecdotal; no superiority claim.
- **Protocol fixes driven by live evidence:** foot heel/toe geometry in the evidence (from the compiled model); push measured at 0.625 N in investigations; the prompt states the acceptance rule; twin validation.
- **Budgets at 08:20:** Forge inference ledger 40 requests, $0.33 (cap $15 / 1,500); infra $2.95 of $10 (conservative, incl. the overnight deadman incident).
- **In progress:** frontend investigation views wired to real records (S5 phase 2); diagnostic probes / active experimentation (S7, M6).

## Diagnostic probes live + pre-registered scoreboard (2026-10-15, `feature/forge-loop`, Draft PR #16)
- **Probes (M6) live:** the model plans up to 3 counterfactual experiments, MuJoCo runs them, expectations are checked deterministically, step B states CONFIRMED/REFUTED. First live probe run ignored its own refuted probes; after the step-B fix, a 3-round loop verified rear-foot redesigns twice beside inconclusive twins (`experiments/forge_loop/dev_live_records/`).
- **Frontend (M5) done:** investigation workspace on real records (probes, twin beside AI, three-way replay, accept-if-verified, lineage, loop/probe controls); 137 vitest, 237 browser checks.
- **Scoreboard v1 (registered `e12dd0e` before running):** 12 live investigations on fresh starter creatures; AI verified 6/12, matched twin 1/12, discordant 5 vs 0, exact one-sided McNemar p = 0.031; heuristic 0/12; $0.05, 24 calls, 8,870 rollouts. Effect concentrated in push. Post-hoc best-of-k baseline check also 5 vs 0. Report: `experiments/forge_loop/scoreboard/REPORT.md`.
- **Remaining:** walk-challenge investigations not yet tried live; engineering memory (post-MVP); submission video/screens; owner decisions on PR #16 and repo visibility.

## Session paused (2026-10-15) — see `docs/RESUME_CHECKPOINT.md`
- `feature/forge-loop` @ d60b155, CI green, Draft PR #16 not merged; repo private; VM STOPPED (infra $3.86 / $10; inference 86 requests, $0.42 / $15).
- Live walking investigations done and archived (nothing verified; model never chose controller co-design).
- Unfinished, preserved as UNVERIFIED branches: `wip/s9-security-hardening-UNVERIFIED` (20224db), `wip/s8-engineering-memory-UNVERIFIED` (54aec28).
- Next: finish/verify S9 -> live end-to-end UI test -> ask owner to merge PR #16 -> memory (pre-registered eval) -> submission assets.

## 2026-10-15 evening — integration complete, memory evaluation running; see `docs/RESUME_CHECKPOINT.md`
- Integrated and verified on the VM: engineering memory (`d3cda1f`) and all security-review fixes (`269ec90`); 894 Python tests, frontend, 237 browser checks; CI green; frozen records 105/105; secret scan 0 hits.
- Owner merge conditions for PR #16 met (CI green; live end-to-end UI test 15/15 with a verified redesign accepted as v2 in the browser, `i-140b1435cb84`; security fixes) — merge still awaits the owner's explicit approval.
- Live walking investigations done (nothing verified). Submission docs updated; repo private.
- Memory evaluation `forge-memory-eval-v1` registered before running (frozen 34-lesson bank) and in progress; resume/analysis procedure and "do not repeat" list in the checkpoint; copy-paste prompt in `docs/RESUME_PROMPT.md`.

## 2026-10-16 - memory evaluation complete: no evidence of a benefit
- `forge-memory-eval-v1` finished: 12/12 pairs (5 before the pause, 7 via `--resume` in remote tmux; no reruns, 0 exclusions,
  all 24 investigations `done`; investigation code identical across both runs). Pre-registered result: AI verified 6/12 with
  memory vs 7/12 without, discordant 3 vs 4, exact one-sided McNemar p = 0.773 -> **no evidence of a benefit**. The model
  cited a memory lesson in 0/12 memory-on investigations although lessons were delivered and citable. Twins 0/24 verified.
  Report: `experiments/forge_loop/memory_eval/REPORT.md`. Memory stays off by default; no benefit claimed.
- Budgets after the evaluation: inference 140 requests, $0.54 of $15; infra ledger in `forge_cloud.py spend`.
- Submission docs: capture plan rewritten for the Forge Loop, feedback updated for Nemotron-3-Super, `webgl-constants`
  confirmed MIT (`4a43440`).

## 2026-10-16 - Walking-recovery research started (branch `feature/walk-recovery` from `main` e58dbdf)
- Plan approved by the owner (rev. 2): `~/.claude/plans/pasted-content-id-4675-creature-merry-corbato.md` (local) — G1 recoverability gate first; Nemotron-as-director later; equal-total-compute comparisons; `full_recovery_v1`; staged spend.
- New modules (VM-tested): `walk_opt.py` (budget-exact numpy CMA-ES, IPOP, subspaces, similarity init, 17-D support), `creature_gen.py` (walkrec seed namespace >= 10M, regions, generator, failing-panel rule, dev bodies), `recovery.py` (`full_recovery_v1`), `gait_features.py` (cadence, capture margin, foot placement, fall direction), `phasegait_fp.py` (optional SIMBICON-style foot placement; zero gains bit-identical to the 15-D controller). Scripts `walk_profile.py`, `walk_oracle.py`, `walk_oracle_report.py`.
- S0 profile: 8-vCPU VM = 4 physical cores; ~11 walking / ~37 falling rollouts/s; 65 MB/worker.
- M1a (registered `563f41c`, results `2274e80`, development data): 4/4 dev creatures fail; similarity transfer never helps; 4k-rollout CMA reaches walking 0.38-1.00, 1 FULL_RECOVERY (weak-slippery, joint); budget-limited; overfitting signs. `experiments/walk_recovery/oracle/REPORT_M1A.md`.
- Incident: a slot sync deleted partial M1a results; re-run deterministically (INCIDENTS 2026-10-16). Outputs now go to git-ignored `artifacts/`.
- Spend: infra $5.00 of $10 (VM STOPPED); inference unchanged ($0.55). Next: S1 (full M1, 12-creature dev panel) awaits owner approval.

## 2026-10-17 - Walking-recovery development stages complete (all development data; reports under experiments/walk_recovery/)
- M1 (G1 PROCEED): foot-placement controller + body co-design make 6/12 failing dev creatures walk (full_recovery_v1).
- S2/S2b: Nemotron director v1 2/12, v2 4/12 at 2k vs FIX 4, RAND 7, CMA-joint 3 (noise-dominated; AI under-uses body co-design; Ultra fails G2).
- L2 (G3 FAIL): learned surrogate warm starts no better than a reused medoid of past solutions.
- Iteration 3 / S4a (G4 FAIL): closed-loop control-law invention (mechanism DSL, director v3) 4/24 (iterative), 5/24 (one-shot) vs fix15 11/24; the loop works (self-stops, revisions) but does not help; invented laws mostly redundant stance torques.
- New product feature: Studio "Recover walking" (backend + frontend, accept only FULL_RECOVERY).
- Spend: infra $17.65 of $35 (owner-approved); inference ~$3.3 of $15. VMs stopped.
- Next: owner decision on the S3 confirmatory freeze (`experiments/walk_recovery/confirmatory/protocol.json`, DRAFT).

## 2026-10-17 - S3 confirmatory complete (walking recovery)
- FIX 19/48, CMA-joint 11, RAND 11, Nemotron director 9, CMA-ctrl 8 (equal total budget 2,000; full_recovery_v1). Primary AI > FIX not supported (p = 0.996). Report `experiments/walk_recovery/confirmatory/REPORT.md`; summary `docs/WALK_RECOVERY.md`.
- Regression on the branch: 1178 Python tests, frontend + build, 314 browser checks PASS (main VM, 2026-10-17).
- Spend: infra ~$26 of $35; inference ~$3.7 of $15. Both VMs STOPPED; the batch VM can be deleted (owner).
- Next: owner decides the demo/submission framing; demo take of "Recover walking" on the stilts robot; Devpost/storyboard update; PR for review (no merge without the owner).

## 2026-10-17 evening - Causal engineer (branch `feature/causal-engineer`), development in progress
- Owner directive: the autonomous physics-grounded AI engineering scientist; log in `docs/CAUSAL_ENGINEER.md` §4.
- Done:
  - pilot1 audit, scientist v2 / v2.1, physics digest with a healthy reference;
  - parametric experiments;
  - Level A/B memory (`experience_bank.py`, `ce_memory.py`) and the probe dataset (165 dev instances);
  - `ce_eval` arms: thinking, one-shot thinking and memory.
- Pilot2 (dev): the thinking scientist chose a repairing tool in 9/13 (v1: 4/13) and recovered 4 FULL.
- Pilot3 (fresh dev subset) is running on the main VM. Level C (repair learner) is being built.
- Security incident (see `docs/memory/INCIDENTS.md`): fixed. The owner should rotate the Token Factory key.
- Budgets:
  - inference caps raised by the owner to $30 / 4,000 requests (ledger about $5);
  - infra cap $35 (ledger about $29.5); the real account balance is about $11.
- PR #18 (CI fix) is open for review. PR #17 is untouched.

## 2026-10-17 22:45 Oslo - Registered held-out evaluation RUNNING (causal engineer)
- Protocol: `experiments/causal_engineer/heldout/PROTOCOL.md` + `protocol.json`, frozen at code commit `5ca165c` (protocol
  commit `c4c2c87`, pushed).
- Scope: 40 instances on 22 unseen bases × 8 arms = 320 episodes.
- Location: main VM, slot `ceh`, 16 tmux sessions `heval_0..15`. Results in `~/dev/ceh/artifacts/ce/heldout_eval_shard*.jsonl`.
- When all shards exit, tmux `hwatch` writes `heldout_eval.sha256`, backs up the ledger to
  `~/dev/ledger/backup/inference_ledger_after_heldout.jsonl` and powers the VM off after 15 min. The VM deadline (10 h) is the
  backstop.
- ETA: about 6 h, CPU-bound.
- If interrupted:
  - restart the same `ce_eval.py` command per shard with `--resume`; the command is in this file's git history and in
    `docs/CAUSAL_ENGINEER.md`; episodes are append-only, never rerun;
  - then run `scripts/ce_heldout_analysis.py` ONCE.
- Next:
  - pull results;
  - run the single analysis;
  - write REPORT.md;
  - update `docs/CAUSAL_ENGINEER.md` (results, what Nemotron contributes, limitations);
  - refresh the Studio demo records.
- Batch VM: STOPPED. Infra ledger about $31.3 of $38; inference about $10.7 of $30 before the run (about $12 expected).

## 2026-10-18 morning - Held-out run finished; AI arms invalidated by key rotation; owner decision pending
- Results, single analysis and REPORT are in `experiments/causal_engineer/heldout/` (frozen). Non-AI arms are valid:
  exhaustive 23/40, learned 18/40 (C5a not supported), random 12/40, expert 6/40.
- AI arms: the key was rotated at 21:02 UTC, about 50 minutes into the run, and every later call returned HTTP 401.
- The new key is on the VM (verified read-only). The main VM is STOPPED and the batch VM STOPPED.
- Inference: real spend $12.37; the ledger shows $20.50, including $7.42 worst-case settlements for failed calls.
- Decision needed: amendment 1 (re-run the 4 AI arms, about $10 real); this requires raising the ledger cap to about $40.

## 2026-10-18 - Causal engineer: held-out evaluation complete (registered run + amendment 1)
- Summary: `docs/CAUSAL_ENGINEER.md` §0. Reports: `experiments/causal_engineer/heldout/REPORT.md` and `REPORT_AMEND1.md` (frozen).
- Held-out FULL recoveries of 40:
  - exhaustive 23, learned 18, scientist+memory 16, scientist 14, scientist+memory+advice 14, random 12, one-shot 8,
    expert 6.
  - No registered hypothesis is supported. Closed loop vs one-shot gives p = 0.09.
- Spend:
  - inference: real $24.75; the ledger shows $32.88 against a $40 cap, including $7.42 of worst-case settlements for calls
    that failed authentication;
  - infra: ledger $33.2 against a $38 cap.
  - Both VMs are STOPPED; the boot disks keep billing about $0.12/day each.
- Open for the owner: PR #18 (CI fix) review/merge; whether to delete the batch VM; demo framing for the submission.

## 2026-10-18 - Research handoff written (no experiments, no cloud cost)
- Handoff for the next session: `docs/RESEARCH_HANDOFF_2026-10-18.md`. It covers state, research history, architecture,
  experience levels, negative findings, infrastructure, budgets, repository operations, priorities, reproducibility, rules,
  and a table resolving outdated statements.
- Verified read-only:
  - both VMs STOPPED;
  - infra ledger $33.28 of $38;
  - inference ledger $32.88 of $40 (real spend $23.6–25.5; $7.42 is unbilled 401 settlements);
  - PR #17 Draft and PR #18 open, both unmerged; repo private.
- New issue: GitHub Actions did not start the run for `192c000` ("recent account payments have failed or your spending
  limit needs to be increased"). The owner must fix billing.

## 2026-10-18 - Causal-engineer artifacts archived; branch pushed (no experiments, no cloud cost)
- What was archived: 66 git-ignored files, 118.7 MB:
  - memory inputs and Level C training data;
  - raw dev traces from pilots 1–5;
  - fault-bench candidates;
  - ledgers.

  All 27 inputs pinned in `protocol.json` are included. Archive SHA-256
  `b81ea8be8d8e40a32a33e02992e66ef0832650abc0423fd7ab292ceb53c20611`.
- Locations:
  - `C:\Users\mbnas\CreatureForge-archive\2026-10-18\`;
  - a draft (unpublished, untagged) release `archive-ce-artifacts-2026-10-18` of the private repo.

  Procedure: `docs/ARTIFACT_ARCHIVE_2026-10-18.md`; checksums: `docs/archive/ce_artifacts_2026-10-18.SHA256SUMS`.
- Verification: both copies were extracted into fresh directories, and all 66 files match their SHA-256.
- Secret scan, 0 hits in each case:
  - the archive inputs;
  - the extracted copies;
  - all 1,461 blobs and 619 commits in the Git object database, including unreachable objects. The only pattern hits are
    the known placeholders (`.env.example` empty value, test fakes).
- **Infrastructure blocker:** GitHub Actions does not start runs ("recent account payments have failed or your spending
  limit needs to be increased"), first seen on `192c000`. CI results for this branch are unavailable until the owner fixes
  GitHub billing. This is not a code failure.

## 2026-10-18 - Phase 3 (HaS scientist) approved; Stage 1 started (branch `feature/has-scientist`)
- **Plan:** `docs/HAS_PLAN_2026-10-18.md`; spec and log: `docs/HAS_SCIENTIST.md`; diagnosis of the frozen held-out records:
  `experiments/causal_engineer/phase3_diagnosis/` (exploratory).
- **Done:** `creature_forge/hidden_plant.py` (deviation DSL, hidden plant, hooks for Workbench and `full_recovery_v1`) with
  `tests/test_hidden_plant.py`: 11 pass locally, bit-identical at zero deviation.
- **Spend:** infra cap raised to $72 for Stage 1 (ledger $33.29); inference cap unchanged at $40 (ledger $32.88). VMs stopped.
- **Next:** vertical slice by 21 Oct (bench families T2/T4, workbench on the plant, belief engine, mock proposer).
- **Deadline:** internal deadline 29 Oct.

## 2026-10-18 - Phase 3 correction: dev records moved into the living dev directory
- The M0 diagnosis outputs were moved to `experiments/causal_engineer/dev/phase3_diagnosis/`; phase-3 dev reports live in
  `experiments/causal_engineer/dev/hdb/`.
- Committing them outside the living directories had broken `tests/test_frozen_records.py` since `777ef0d`; it passes again.

## 2026-10-19 - Phase 3 Stage 1 (non-LLM development) complete; Stage 2 awaits owner approval
- **Bench:** Hidden-Damage Bench v2 frozen (`docs/HDB_SPEC.md`). The threshold-relative severity definition awaits owner
  confirmation.
- **Bases:** 135 fresh verified walkers (36 dev, 99 test-sealed).
- **Identifiability (multi-class, dev):** 282/302 identified with all instruments; observation alone 245.
- **Engine:** v5 (`belief_engine.py`); dev-fitted stopping map in
  `experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json`.
- **Dev results, no claims:**
  - 12 old dev bases: A1c5 44/113 vs A0 28/113.
  - Fresh dev bases, 9 families: A1c5 109/211 vs A0 62/211 (paired 61 vs 14).
  - MKV: exact deviation knowledge helps; structure alone adds little.
  - Calibration: the naive Beta reading is worse than a constant forecast.
- **Live Nemotron smoke:** 3 A3 episodes, $0.013.
- **Spend:** infra ledger about $60 of the $72 cap; inference ledger +$0.013. VMs stopped.
- **Next:** owner decisions (C-MKV primary, severity definition, Stage 2 approval), then LLM development (A3h/A3hx/A3),
  then registration on the test split.

## 2026-10-19 - Ops incident: batch VM ran past its deadline (corrects "VMs stopped" above)
- **What happened:** the session's API stop of `creature-forge-batch` was killed (local out-of-memory) before it ran. The Nebius
  CLI login then expired, so the Windows watchdog's `instance get` failed from 01:47 to 08:47 UTC and it could not stop
  the VM. The deadline was 03:56 UTC.
- **Observed state:**
  - 08:57 and 09:12 UTC: the watchdog saw STOPPING.
  - 09:19 UTC: the control plane reported STARTING, then RUNNING. The cause is not known; it was not started by any script
    in this repository.
- **Stopped:** an API stop at 09:20 UTC (`forge_cloud.py stop`). STOPPED was confirmed twice. The main VM was STOPPED
  throughout.
- **Spend (quoted-rate estimate, not a provider statement):**
  - The conservative ledger is $75.47, over the $72 cap, so `start` now refuses.
  - Stage-1 increment: $42.18 against the $35 envelope.
  - Charged past the deadline: 5.39 h × $2.112/h ≈ $11.39 (worst case; billing during guest-off/STOPPING is not known).
- **Billing:** the Nebius CLI has no balance query (`billing` only has `pricing-policy`). The owner checks the console.
- **Lesson:** an expired CLI login silently disables the watchdog. Before leaving a VM on a deadline, confirm the CLI
  auth is valid, and stop through the API instead of relying on the deadline.
- **Artifacts:** all Stage-1 dev artifacts are present locally (`artifacts/vm/hdb/`, 71 MB; fresh_A0/A1c5 220 rows each).
  The dev reports are committed.

## 2026-10-19 - Phase 3 Stage 2 (owner-authorized: +$20 infra, +$10 inference) in progress
- **Caps:** infra `SPEND_CAP_USD` $96 (ledger $75.48 + $20 + $0.50); inference USD cap $43.40 (ledger $32.90 + $10 + $0.50).
  Requests stay at 8,000 (4,733 used).
- **Nebius auth guard:** unattended CLI calls use `--no-browser --auth-timeout 30s`. An auth failure writes
  `infra/nebius/AUTH_BLOCKED` and stops every further attempt until the owner runs `forge_cloud.py login`.
- **Owner decisions recorded:**
  - severity definition confirmed;
  - C-MKV registered form: primary K2 vs K0n, secondary K1 vs K3 and K2 vs K1, plus a paired Wilcoxon on walking
    (`scripts/hdb_report.py`).
- **Built:**
  - `has_agent.py` (Nemotron-directed scientist; full delegation reproduces A1c5 exactly: identical plant/twin ledgers
    and verification on 3/3 checked instances);
  - `has_memory.py` (dossiers, deterministic support, Nemotron consolidator);
  - `amortized_posterior.py`;
  - `scripts/hdb_agent_run.py`, `hdb_memory_build.py`, `hdb_amortized.py`, `hdb_agent_report.py`, `has_export_records.py`;
  - Studio "AI scientist" tab + `/api/scientist`.
- **Dev protocol (fixed before pilots):** tune on the experience bases, evaluate once on the 18 unseen transfer bases
  (`experiments/causal_engineer/dev/hdb/stage2_split.json`). Details in `docs/HAS_SCIENTIST.md`.

## 2026-10-20 - Phase 3 Stage 2 complete; Stage 3 awaits owner approval
- Transfer evaluation done (124/124 LLM-arm episodes valid). Nemotron scientist at parity with the engine on single
  mechanisms (FULL 15 vs 14 of 36; discordant 4 vs 3), slightly behind on compositions (6 vs 8 of 16). Memory was barely
  used. Details: `docs/STAGE2_REPORT.md`, `experiments/causal_engineer/dev/hdb/STAGE2_TRANSFER_agent_v4.md`.
- Costs: Stage 2 infra $7.82 of $20 (ledger $83.30 / cap $96); inference $3.75 billed of $10 (ledger $46.02 / cap $52.78).
- Both VMs STOPPED (control plane, 01:38 UTC 20 Oct). Raw records are in `artifacts/vm/hdb/artifacts/hdb/stage2_final/`
  (git-ignored, SHA-256 in the record file) and on the main VM boot disk.
- Next: owner decision on Stage 3 (proposed envelopes $65 infra / $15 inference; Cloud top-up of about $55).

## 2026-10-20 - Stage 2b proposal (dual-signal learning); Stage 3 deferred by the owner
- Owner: no Stage 3 yet. The two pre-registration fixes are approved within the remaining Stage-2 allowance (infra
  ≈ $12.18, inference ≈ $6.25 left).
- Failure analysis and the DS-1 plan are in `docs/DUAL_SIGNAL_PLAN.md`. They await owner approval before any run. No VM is
  running.

## DS-1 dual-signal iteration — complete 2026-10-20 (report `docs/DS1_REPORT.md`)
- **Gates:** G-a FAILED (R-head; no A1x, R-head never orders tools); G-b pass; equivalence pass; G-m FAILED (composite
  mechanism, amendment 2); **G-c FAILED** (A4x deviated from the engine default in 3/36 episodes < 15 %), so A4x is not
  Stage-3 eligible.
- **Engine v6 vs v5 (non-LLM, 30 + 6):** diagnosis better calibrated (confidently wrong 4 vs 9 and 0 vs 6); repair
  unchanged (FULL 8 vs 9, 1 vs 1). Stop map v2 beats v1 (LOBO Brier 0.099 vs 0.166).
- **Nemotron (A3v5 vs A1e6):** FULL 8 vs 8 and 2 vs 1; diagnosis slightly worse; registered P(success) worse than a
  constant base-rate forecast.
- **Experience (A4x, M_final):** FULL 10 vs 8 (A3v5) and 10 vs 8 (A1e6), discordant 3 vs 1 each (p = 0.31); Nemotron
  mostly delegated. **Learning stream:** updating vs frozen 7 vs 7 of 20.
- **Cross-feedback:** inert (1 leader change in 183 dev-eval assimilations); repair checks barely discriminate hypotheses.
- **Recommendation:** no registered Nemotron evaluation (Stage 3) now; optional non-LLM registered study of engine-v6
  diagnostic calibration needs its own registration and owner approval. Next development step: informative interventions
  (report §12).
- **Costs:** infra ledger $88.43 at 14:05 UTC (DS-1 limit $93.30); inference $2.44 / 1,441 requests since 2026-10-20
  (limit $4.60). No cap changed.
- **Data:** `artifacts/vm/hdb/artifacts/hdb/ds1_all.tgz` (VM archive), `artifacts/vm/ds1/eval/` (72 + 72 episodes), tables
  `experiments/causal_engineer/dev/hdb/DS1_RESULTS.md`.
- **Ops:** in-VM `poweroff` does not keep the main VM stopped: after the finalisation poweroff (13:42 UTC) and a manual one
  (14:08 UTC) the platform showed it RUNNING again within ~3 min. After the owner's re-login it was stopped via the API at
  14:15 UTC; **both VMs verified STOPPED via the control plane** (infra ledger $88.47). Future finalisation must stop via
  the API, not rely on poweroff or the in-VM deadman.
  The batch VM's pre-existing `~/dev/.env` key line (2026-10-16) is untouched; removal is the owner's decision.

## 2026-10-24 - SV1 closed; auth-horizon guard; roadmap reassessment; E-1 prepared (not registered)
- **Experience P05 (branch `feature/experience-learning`, pushed @ `cea00b5`).**
  - SV0 and SV1 code, evidence and reports are committed. SV1 is ADMITTED: only the refit percentile bootstrap M2 was
    admitted, and CR1 undercovers.
  - `sv1/SV1_FINAL_REVIEW.md` covers the conclusions, the power consequence (θ_G 0.108 → "supported benefit" 5 %), and the
    evaluation `verdict` label clarification; the frozen output is unchanged.
  - Recommendation: no P0.5 campaign before the deadline.
- **Ops (branch `infra/auth-horizon-guard` @ `d8e3727`, pushed).**
  - Root cause of the 2026-10-19 and 2026-10-24 overruns: the CLI federation token is a fixed ~12 h token with no refresh.
  - `start` now shortens and `extend` refuses any deadline beyond the token expiry minus 45 min. The watchdog stops running
    VMs 30 min before expiry, and `status` and the watchdog log the remaining auth time.
  - The watchdog task now also runs on battery.
  - Remaining gap: a sleeping or off laptop. The fix needs a VM-side API stop with a service account, which is owner IAM
    approval.
- **Budget (owner, 2026-10-24).** Cloud $37.49, Token Factory $47.00. Development use is authorised; the $1.50 SV1 limit
  is not the ongoing budget. Ledger $92.98 / cap 96 at 13:15 local.
- **Roadmap.** `docs/ROADMAP_REASSESSMENT_2026-10-24.md`. Experience → better decisions remains undemonstrated. The strongest
  effect (A1c5 109 vs A0 62 of 211 fresh dev) was never confirmed on the sealed test side.
- **E-1 (branch `research/e1-engine-heldout`).** Protocol draft `docs/E1_PROTOCOL.md`; code: `hdb_testbench.py`,
  `e1_build.py`, `e1_run.py`, `e1_analysis.py`, `e1_repro_gate.py`; 14 tests.
  - The G-R reproduction gate is running on the main VM (slot `hdb`, `artifacts/e1/gate`).
  - The sealed side is not opened. Registration and the build need the owner's go, because they spend sealed held-out data.

## 2026-10-24 evening - E-1 complete (registered; `docs/E1_RESULTS.md`)
- **Registration:** `494ed9b`, pushed before the sealed side was opened. Gates G-R, G-R2, G-O, G-T, G-B and G-C all PASS.
- **Sample:** 160 sealed test instances on 90 bases; the reserve is in `experiments/e1/RESERVE.md`.
- **Results:** A1 engine 56, A0 exhaustive 46, K0n (engine without diagnosis) 42.
  - **H-E1 (A1 > A0): 22 vs 12, p = 0.061, not rejected.**
  - **H-E2 (A1 > K0n): 26 vs 12, p = 0.017, rejected (Holm).**
  - H-E3 (K0n > A0): null.
  - Diagnosis carries the advantage on unseen damage; the twin machinery alone does not. The dev effect (+22 pts) shrank
    to +6 pts.
  - On sealed singles the diagnosis is right but the repair fails: sensor latency 1/18, damping 3/18.
- **Ops:** service account `cf-vm-stopper` (instance-scoped editor). VM API self-stop installed on the batch VM and
  tested. A VM-side finisher ran the analysis and stopped the VM through the API.
- **Spend:** today +$8.85, ledger $101.82, cap 120. Both VMs STOPPED (control plane).
- **Next:** rc2 wording (owner); diagnosis-conditioned repair memory (dev first, then registered on the reserve with A3).
- **Correction (2026-10-25, owner review):** H-E2 meets only the registered secondary criterion (Holm over 2, adjusted
  p 0.034). The protocol had no gatekeeping, so it is not a study-wide confirmatory result: Holm over all 3 tests gives an
  adjusted p of 0.0503. Report it as supportive evidence (`docs/E1_RESULTS.md` §1.1). The earlier "rejected (Holm)" wording
  is withdrawn.

## 2026-10-24 night - RL-1 repair learning: dev gate G-RL1 FAILED (`docs/RL1_DEV_REPORT.md`)
- **Dev response matrix:** 211 instances × 10 tools, 2,110 cells, verified. Some tool works on 61.6 %; 38 % are
  unrepairable by any single tool at 300 rollouts.
- **LOFO top-2 matrix success:** engine twin ranking 0.521, RL-1 0.512 (−0.009, 90 % [−0.029, 0.009]), simple memory
  0.450, probe ranking 0.450.
- **Gate:** failed, so RL-1 is not run online. Exploratory: memory added to a twin-free engineer hurts (0.450 → 0.403).
- **Recommendation:** no E-2 RL-1 vs A1. The proposed E-2R (diagnosis-ablation replication on a fresh cohort + HF2) needs
  the owner's decision.
- **Spend:** ledger $107.19. Both VMs STOPPED.


## 2026-10-25 — Isolated R0 preparation; execution blocked on current credit

- Branch `codex/repair-strategy-r0`, from research `0828cbd`; no release, PR #20, E-2R, test or reserve changes. Owner authorized development execution up to $35 additional infrastructure and ten campaign hours, subject to actual available credit.
- Implemented bounded single/sequential/joint search crossed with frozen/byte-exact DO-1 objectives, exact 3,000-rollout accounting, sanitized policy input, original-relative bounds and unchanged recovery verification. Frozen dev registration: 18 distinct bases, three technical replicates, 324 units. Details: `docs/R0_REPAIRABILITY_PROTOCOL.md`; source/inputs/seeds: `experiments/causal_engineer/dev/repair_strategy_r0/protocol.json`.
- Added atomic validated checkpoints/resume, provenance, deterministic shards, base-clustered analysis, evidence archive/audit and existing-SA lifecycle/VM supervisor. Validation: 69 selected local tests (zero physical rollouts) and three Linux command-fake supervisor tests passed. Actual VM physics/equivalence/throughput/self-stop gates remain pending.
- Genuine blocker: console requires sign-in; current available Cloud credit cannot be verified through the exposed SA tooling. Requested authentication immediately and continued safe preparation. No paid start occurred: 0/324 units, R0 gate NOT EVALUATED, zero R0 compute runtime/spend. Existing disks continue charges.
- Both VMs independently verified STOPPED through SA control-plane API at epoch 1792889886; watchdog Ready and battery allowed. Conservative lifetime ledger $107.262 is not account credit or an invoice. No remote Basic Memory tools exposed; tracked memory used, no sync claimed.
- Report, validation evidence, limitations and next step: `experiments/causal_engineer/dev/repair_strategy_r0/REPORT.md` and `README.md`. Next: verify actual current credit, perform bounded remote engineering/self-stop/equivalence/throughput gates, then run the unchanged registration only if it fits with margin. No R1 capability conclusion exists.


## 2026-10-25 — R0 resumption authorized, credit verified by owner

- Owner confirmed current available Cloud credit $33.73 and instructed autonomous resumption from `bb2ecb9`, with the existing $35/ten-hour limits and no R1 or sealed work. Both VMs rechecked STOPPED; watchdog Ready.
- Before any paid start or R0 outcome, found the existing cloud helper start path calls legacy `nebius` directly. Engineering amendment 1 binds that entry point as well as `ctl` to the existing SA helper. The original registration is preserved; only the operational source hash/annotation change, with all scientific choices/case bytes unchanged. See `experiments/causal_engineer/dev/repair_strategy_r0/ENGINEERING_AMENDMENT_1.md`.
- Next: bounded engineering start, inspect existing remote environment and timer, prove real VM-side SA API stop, then physical regression/equivalence/throughput gates. Basic Memory tools are now exposed; scoped text searches found no R0/self-stop note.

## 2026-10-25 — R0 complete, development advancement gate FAILED

- Supersedes the earlier credit-blocked/preparation status. Owner verified $33.73 available credit; all 324 frozen units ran under source `d29cdce6dbca4df9a410beed4ed8acaa47b0e1a5` and protocol SHA-256 `b481dc8977d56a9878526cfafce259e05e4c55bd551f1983661040bb482139bb`. No release/PR #20/E-2R, sealed-data or R1 changes.
- FULL totals out of 54: single/frozen 20, single/DO-1 26, sequential/frozen 28, sequential/DO-1 24, joint/frozen 32, joint/DO-1 27. Failed-cohort FULL out of 36: 9, 12, 14, 12, 17, 16 respectively. Three optimizer replicates are technical; primary clustering uses 12 failed bases.
- Gate FAILED: two repeatable rescues across two families, net failed-cohort gain zero against per-base best restricted/DO-1, three material control regressions, zero errors. Primary joint/DO-1 minus sequential/DO-1 = +11.1 percentage points, descriptive cluster interval [-5.6,+27.8], exploratory p=0.40625. No general DO-1 benefit, transfer or Nemotron-learning claim.
- Engineering: existing VM/environment reused, 84 real-VM regression tests passed; six serial/six pooled excluded smoke records matched exactly except wall time. Three documented operational/metadata amendments preserved scientific choices. Invalid first smoke logs retained; no valid main unit was rerun selectively.
- Main: 13:43:16–16:50:02 UTC, exit zero; 972,000 policy rollouts plus 24,672 verification equivalents. Frozen analysis repeated exactly; local/native audits agreed, all 324 valid and 337 manifest files verified. Raw archive 16,568,688 bytes, SHA-256 `6dcda839b60a401831a46efd760b2702e65e42fda65e8391e87d7018e8520806`, retained locally under ignored `artifacts/r0_ops/` and on persistent stopped batch disk. Small analysis/manifests/receipts are committed in the R0 `results/` directory.
- Root SA API stop requested at 16:50:07 UTC; independent watchdog retained. Brief 15-minute bounded restart retrieved evidence and repeated analysis without physics. Both VMs independently verified STOPPED at 17:10:46 UTC. Conservative additional ledger $10.349, paid batch estimate 4.877 hours, campaign elapsed 5.066 hours; within $35/ten-hour/current-credit bounds. Not an invoice or final available balance; disks continue storage charges.
- Report: `experiments/causal_engineer/dev/repair_strategy_r0/EXECUTION_REPORT.md`. Next scientific question: search allocation/selection mismatch versus repair-representation limits, especially the three regressions and three all-arm failures. Any new study requires prospective registration and owner authorization; no R1 or sealed work initiated. Remote documentation sync is recorded separately after verified readback.
- Results commit `2adff9e6e0eb8dbe73f2acbe4aa828f4996efc4e` pushed and remote ref verified. Completed-result section appended once to Notion proposal `4035d357-b5ad-813e-84d4-de5fd8928f41`, with historical proposal/preparation intact; fetch verified the failed gate and commit. Basic Memory note `creature-forge/research/r0-completed-development-study-frozen-advancement-gate-failed-2026-10-25` created in project `6df7569e-45bd-4cd8-8b84-0fec7c11c9c6` and read back successfully. This sync is verified, unlike the earlier preparation snapshot.

## 2026-10-25 — EM-1 G0 audit authorized, no learning claim

- New branch `codex/experience-model-correction-em1` in the existing isolated Codex worktree, from `8e7e824`; owner authorizes evidence audit through the furthest defensible development gate, $12 Cloud/$3 Token Factory/six VM hours, paid stop by 27 October 12:00 Oslo. Current owner-verified balances: $26.51 Cloud/$47.00 Token Factory. No release, sealed or prior frozen evidence changes.
- Read-only audit identified 324 eligible v5 episodes, 30 independent bases, nine dev families, 866 saved checked designs and 12,592 aggregate robustness-seed observations. Original cached twin predictions are not serialized; training screen scores and different RL-1 designs cannot form paired residuals. 542 checked alternatives lack independent FULL labels.
- `scripts/em1_audit.py` reconstructs only the unchanged pre-repair diagnostic model for exact saved designs/seeds; outcomes/evaluation metadata are excluded from predictor inputs. This is a measurement auditor, not a correction learner. Eight identity/chronology/ledger/limit tests passed; temp-file tests use the writable workspace after sandbox temp rename was denied. No physics runs locally.
- Next: bounded existing-VM twin-only measurement, base-clustered discrepancy/ranking/precision audit, then G0 decision before learner implementation. `docs/EM1_PLAN.md` specifies scope and ordered gates. Both VMs checked STOPPED before start; existing independent watchdog/SA API-stop are reused.

## 2026-10-25 — EM-1 G0 complete: NOT EVALUABLE / NO-GO for learner advancement

- Completed all 804 distinct saved interventions from 866 design-index entries (62 duplicates/prefix checks collapsed), 324 historical episodes, 30 independent bases and nine dev families. 11,632 exact-design/robust-seed twin responses; zero new plant rollouts or model calls. Measurement source `f70549d`, raw archive SHA-256 `dbfc677101a6430ce7fa829d0a3e22ac07697f24b90fae3b9ad5db6317b14236` (1,030,524 bytes), all 818 manifest entries verified. Old inventory/partial run preserved; scientific fields reproduced on all 17 overlapping partial predictions except timing.
- Prediction discrepancy exists: base-equal observed−predicted robustness walking +0.05185, descriptive95 [0.01581,0.08973]. But actual B0 final walking regret against its best observed candidate is zero in every episode. The raw twin-only audit ranker changes 86 submissions (54 lower walking, 32 tied); all 86 changed FULL outcomes and 480 total alternative FULL labels are unknown. Historical original submissions: 153/324 FULL. No causal recovery gain can be inferred.
- G0 identifies physical mismatch but not an actionable, transferable repair-decision target. **EM-1 NOT EVALUABLE; NO-GO for further learner/online implementation on this evidence.** This is not a null test of H-EM1. B1/B2/B3, LOBO/LOFO/prequential learning, applicability/negative-transfer and Nemotron contribution remain untested; no fresh prospective or sealed experiment launched. The mission's G0 stop was followed instead of fitting another tool-success ranker.
- Validation: 12 guard tests on Linux before measurement, 13 local after portable hash-index fix, 22 existing R0 regressions passed. Two real-VM fixtures matched the frozen ensemble evaluator. Original Python3.12 analysis repeated exactly; local Python3.11 exact replay failed on path keys/last-bit summation. Path formatting fixed without numerical changes; 16 remaining floating differences max1.77636e-15 are disclosed, all hashes/counts/choices exact. Original numerical analysis remains authoritative.
- Native full audit 19:07:45–19:20:24 UTC, exit0, root SA API-stop request19:20:26. Evidence retrieval/reanalysis restart stopped; both VMs independently STOPPED at19:27:35 UTC. Conservative additional Cloud $1.097, paid batch0.517h, elapsed0.582h; Token Factory$0, within verified26.51/47 credit and12/3/six-hour caps. Ledger is not invoice/final credit; interrupted first executor did some unpublished rollouts, so exact aggregate campaign rollout count is unavailable while paid time/spend includes them.
- Four reports: `docs/EM1_PLAN.md`, `EM1_FEASIBILITY.md`, `EM1_RESULTS.md`, `EM1_DECISION.md`. Small evidence in `experiments/causal_engineer/dev/em1/results/`; raw/partial archives in ignored `artifacts/em1_ops/` and persistent stopped batch disk. Next scientific requirement: prospectively log pre-check forecasts for controlled, identical interventions and rich plant responses/FULL support, then a separately frozen powered design. No further paid work scheduled; no release, PR #20/E-2R or previous frozen evidence changes.
- Results commit `536c32d2e361d3402b4a109925f006f8ebfc3340` pushed on `codex/experience-model-correction-em1` and remote ref verified. Notion proposal `4035d357-b5ad-813e-84d4-de5fd8928f41` has one appended EM-1 NOT EVALUABLE/NO-GO section, fetched and verified with R0 history intact. Basic Memory note `creature-forge/research/em-1-g0-audit-physics-mismatch-measured-repair-benefit-not-identifiable-no-go-2026-10-25` read back successfully in the creature-forge project; sync verified.

## 2026-10-25 — DI-1 instrumentation and bounded engineering pilot

- Owner authorizes a development-only decision-time opportunity study; current owner-confirmed balances $23.28 Cloud/$47 Token Factory, task ceilings additional$12/$2/six paid VM hours and stop by27 October12:00 Oslo. New `codex/decision-investigation-di1` branch from EM-1 final `e242b5a` in the existing separate research worktree.
- Pilot registered/pushed `c301887`, LF-byte provenance amendment `1e0f610`, before new physics. Eight frozen new morphology attempts from explicit development nominal parents, ±3% independent body perturbations, no replacements. First diagnostic-probe fork: original EIG/cost, raw EIG and uniformly sampled nonoriginal probe; each continuation caps700plant/2800twin with unchanged FULL verifier. Pilot is engineering-only and excluded from future evaluation.
- Observation-only durable hash-chained trace retains calls, exact candidates, rejections, seeds, cached forecasts, posterior/state, optimizer populations and outcomes. Existing baseline/physics/verifier source unchanged. Five native guards passed; seven local guards with exact-power/policy tests. All five eligible pilot bases have exact uninstrumented/instrumented scientific, ledger and FULL equivalence proofs; full fixed pilot still running at21:00UTC. First base has no eligible extra-probe decision, so its paths coincide; do not count repeated paths as independent evidence.
- Reused existing batch/environment/SA API-stop; both VMs API-checked STOPPED before start. Detached native pilot supervisor archives and requests API stop on all exits, root timer active, independent Windows watchdog Ready. Campaign first start1792960767.462, initial conservative ledger118.846USD; native deadline1792966235. Existing main VM remains STOPPED. Independent trace/cost/power and uniform qualification-replay helpers are committed `f9066ab`; final feasibility and prospective launch decision remain pending.

## 2026-10-25 — DI-1 complete: NOT EVALUABLE / NO-GO

- Supersedes the running-pilot status above. Eight frozen new development morphology attempts, five nominally qualified independent bases, no replacements. New numerical bodies in a narrow neighborhood of18 known development parents; no broad morphology/family transfer claim. Zero prospective evaluation bases; pilot excluded from future evaluation.
- V1 reached a probe decision on only one base: original/raw EIG/random each3/5 FULL, no rescue. Engineering amendment2 (`2f6031f`, before v2 outcomes) uniformly tested stop-or-probe on all five eligible bases, keeping700plant/2800twin caps: original3/5, raw3/5, random4/5. Base003 random `floor_test@x3` plus ordinary repair independently reached FULL on original conditions; raw reached PARTIAL. One actionable allocation path, not an isolated causal floor-probe effect or transferable predictive signal. Random also worsened base000 from PARTIAL to NONE. Both versions retained; same bases counted once.
- Eleven distinct final physical designs,25 comparison records excluding reused baseline,31 actual policy/FULL executions including equivalence repeats. Policy ledger16,454plant/58,254twin equivalents; independent verification2,448equivalents. Raw versus original FULL0pp, versus random−20pp, descriptive whole-base bootstrap95[−60,0]. Opportunity1/5; binomial reference95[0.5%,71.6%], raw FULL-loss upper95 52.2%. Fixed family strata/exclusions make these planning references, not confirmatory population intervals. No learner/Nemotron adaptation or history-ignore mechanism tested.
- Gate NOT EVALUABLE; NO-GO for experience-guided investigation implementation. Conservative paired-power planning for10pp useful gain requires768 evaluation bases for the two contrasts; measured full-cap three-path forecast43.7845additionalVMhours/$92.6874 with25% margin/qualification exceeds authorized6h/$12. Other gate conditions can need more information; forecast is for this design, not a universal minimum. No underpowered main, final evaluation registration, sealed work or R1 launched. Thresholds unchanged.
- Five original/instrumented exact science/ledger/FULL proofs and one v2 default repeat passed. Post-run tuple/list normalization fix `2a4f7d4` preserved failed audit/64jobs; uniform replay all8 attempts384jobs matched, overlap64 exact except timing, no policy/FULL rerun. Eight native/local guards, independent temporal/hash/cost checks, native v1/v2 analysis exact repeats, zero policy-trace physics errors. Original Python3.12 numerical analysis authoritative; no3.11 exact replay claim.
- Three raw archives11,447,641/14,793,318/74,714bytes and all200manifest entries verified; hashes/receipts/small native analyses/CSV under `experiments/causal_engineer/dev/di1/results/`. Raw traces retained locally ignored `artifacts/di1_ops/` and stopped persistent batch disk. Reports `docs/DI1_RESULTS.md` and `DI1_DECISION.md`, plus original plan/instrumentation/protocol and amendments. No prior frozen evidence/release/PR#20/E-2R/submission changes.
- Existing native SA API-stop/deadline and independent watchdog retained through session usage interruption; native v2 stop requested21:30:28UTC. Bounded retrieval/uniform audit restart ended; both VMs independently API-confirmed STOPPED at2026-10-25 22:36:47UTC (23:36:47Oslo), epoch1792967807.6748226. Conservative additionalCloud$4.124/1.943paidbatchhours (delayed-observation upper estimate, not invoice/currentbalance); actualTF$0, no modelcalls. No further paid work scheduled. Next research requires separate registration/authorization for predecision misfit/stopping signals and a defensibly powered efficient design on disjoint broader bases. Remote documentation sync is recorded after verified readback.
- **Completion and sync verified:** results commit `2c4c40966a7c5fce574fafed922c34a9fe5f88f6` pushed on `codex/decision-investigation-di1`; remote ref matched. All 32 report/small-evidence checksums matched working and staged bytes, three registered source snapshots verified and reporting-helper Git bytes matched its source hash. Notion proposal `4035d357-b5ad-813e-84d4-de5fd8928f41` fetched after append: exactly one DI-1 completed NOT EVALUABLE/NO-GO section, matching commit, R0/EM-1 history preserved, last edit `2026-10-25T22:52:20.862Z`. Basic Memory project `6df7569e-45bd-4cd8-8b84-0fec7c11c9c6`, note `creature-forge/research/di-1-opportunity-pilot-not-evaluable-no-go-2026-10-25`, read back with matching gate/commit and checksum `934311ab70080fa5731e983fee4aa812536ef7e79ce025b465d9b38b3efdea35`. Git/raw evidence remains authoritative; no pending execution or approval blocker.
