# Creature Forge — verified current project state

Updated: 2026-10-13 (repository bootstrap; not a local environment audit).

## Observed / confirmed

- Repository: `mahdinass/Creature-Forge`, default branch `main` (private when last inspected).
- Master blueprint: `docs/PROJECT_SPEC.md` (specification, **not** implemented functionality).
- Shared agent instructions: `AGENTS.md`, `CLAUDE.md`.
- External-memory integration: **not yet authenticated or confirmed** on the user's machine; see `docs/MEMORY_SYSTEM.md`.
- Physics simulator, Python environment, frontend, Nebius credentials, GPU availability and deployed services: **not yet verified**. Do not assume installed or absent; inspect the local checkout.

## Next validated milestone

Phase 0 / T0: verify local Python/toolchain and Nebius access; instantiate a physically valid MuJoCo creature; produce a seeded rollout, real telemetry, fall-event detection and a reproducible smoke test.

## How to maintain

Edit after each meaningful milestone. Record **date, exact command, output/test result, git commit/path, unresolved issue and next owner step**. State `not checked` instead of inventing success. This is a concise index of recent truth, not a replacement for Git or test logs.
