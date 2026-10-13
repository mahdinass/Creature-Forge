# Creature Forge — observed current project state

Updated: 2026-10-13. Local environment audit **reported by Claude Code and relayed by project owner**; ChatGPT has not executed these checks on the Windows machine. Facts may change; always rerun the preflight.

## GitHub / implementation

- Repository: `mahdinass/Creature-Forge`, branch `main` (private when last inspected).
- Master design blueprint: `docs/PROJECT_SPEC.md`; planned, not implemented.
- Shared instructions, local memory guide, preflight and guard tests are committed.
- As of Claude's audit at local commit `fade5d8`, no project scaffolding, Python venv, package manifests, frontend or physics simulator were present. This GitHub documentation update is **newer** than that local audit. Pull before working.

## Local toolchain — Claude-reported audit

- Windows local memory: Basic Memory `0.23.2`, local SQLite, `creature-forge` default project at `C:/Users/mbnas/basic-memory/creature-forge`.
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

- Working directory: `C:\\Users\\mbnas\\.vscode\\Creature-Forge`.
- `git status`: clean `main`, tracking `origin/main`; `git pull --ff-only` succeeded and advanced local HEAD from `24a9008` to `488cc05` at time of audit. Later documentation commits still require a new pull.
- `python scripts/context_preflight.py`: successful; current interpreter `C:\\Users\\mbnas\\AppData\\Local\\Programs\\Python\\Python311\\python.exe`, Python `3.11.9`, `VIRTUAL_ENV=False`, no known project venv directories reported; no `pyproject.toml`, `requirements.txt`, `package.json` or lockfile yet. These are observed at audit time, not permanent declarations.
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
