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

- Cross-tool **Codex → Basic Memory** retrieval from a new session.
- Local Claude Code SessionStart and venv PreToolUse hooks (must run the committed tests on Windows).
- Semantic index and similarity threshold behavior.
- Nebius credit redemption, model availability, inference, and actual physics simulation.

## Next actions

1. Pull current `main` docs into the clean local repository.
2. In a fresh Codex session, retrieve the exact Claude-written Basic Memory note using **text search** scoped to `creature-forge` and read it. Confirm the same fact against the local repo. Don't install anything.
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
