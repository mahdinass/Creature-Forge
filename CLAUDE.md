# Creature Forge — Claude Code entry point

Follow **all** instructions in `AGENTS.md`; those rules also apply to Codex. Detailed project vision is in `docs/PROJECT_SPEC.md`.

At the start of each Claude Code session:

1. Review the automatically produced `SessionStart` preflight (or run `python scripts/context_preflight.py` manually) and read `docs/PROJECT_STATE.md`.
2. Inspect `git status`, the relevant existing source and environment, then check `docs/memory/` for previous decisions or fixes.
3. If `basic-memory-cloud` or another Basic Memory MCP server is connected, search project **creature-forge** for task-specific decisions, setup state and relevant prior failures. Read only relevant notes. Treat notes as pointers, not filesystem truth.
4. For any consequential discovery or fix, update Git-tracked state/decisions and optionally write a cross-tool Basic Memory note. In your final reply identify what you updated.
5. Do not create a virtual environment, reinstall a stack, duplicate a module or rework architecture without checking the present state. If a dependency is missing, prove it with a diagnostic.

Use the full project specification as a roadmap, not as a request to generate the whole application in one pass. First implementation target: Phase 0 / T0 simulation, telemetry, fall detection and a real Nebius-Nemotron connectivity test.

See `docs/MEMORY_SYSTEM.md` for MCP setup and `docs/NEBIUS_SETUP.md` for promotional-credit onboarding. Do not expose API keys in output.
