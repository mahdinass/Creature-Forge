# Creature Forge — instructions for all coding agents

Read this file before changing code. Claude Code additionally reads `CLAUDE.md`. The complete product blueprint is in `docs/PROJECT_SPEC.md`; use the relevant sections, not all ~104 KB of it for every small task.

## Non-negotiable workflow

1. Run `python scripts/context_preflight.py` (or `py -3 scripts/context_preflight.py` on Windows where `python` is unavailable). Read `docs/PROJECT_STATE.md`, `git status`, and the relevant existing implementation before planning. Do not infer environment state from chat or memory.
2. Search the codebase and `docs/memory/` for the task's dependencies, decisions, known issues and past fixes. If Basic Memory MCP is connected, use `search_notes` scoped to **creature-forge**, **starting with `search_type: "text"`** for reliable exact/topic keyword lookups; then `read_note` for useful hits. As of 2026-10-13, local hybrid/semantic lookup was slow and returned no matching note while text lookup worked. Treat semantic search as optional until separately validated. Search actual project code and Git docs too. Do not dump every note into context. If MCP is not connected, continue using Git-tracked notes and report the missing connection; never pretend you checked it.
3. Form a short plan with files affected and acceptance tests. Reuse what already exists. No duplicate venvs, project scaffolds, services, schemas, APIs or tooling unless there is a documented reason.
4. Implement the smallest complete vertical slice, test it with real evidence, and report commands/results. Never replace MuJoCo outputs with invented poses or AI-written verdicts.
5. After a consequential change, update `docs/PROJECT_STATE.md` and appropriate `docs/memory/DECISIONS.md` / `docs/memory/INCIDENTS.md`. If Basic Memory is connected, also write or update a concise linked note in its **creature-forge** project, with the code commit/path as evidence. Do not claim remote memory is synced unless verified.
6. Before ending: record changes, validation, unresolved issues and the next step. Keep `main` runnable. Use separate branches or worktrees for parallel Claude/Codex edits.

## Authority order

- Current filesystem, executable tests, git history and runtime API/model catalog establish operational facts.
- `docs/PROJECT_SPEC.md` defines the planned vision and scientific constraints (it is **not** proof of implemented features).
- `docs/PROJECT_STATE.md` tracks observed implementation status with timestamps/commits.
- `docs/memory/` and Basic Memory are searchable hypotheses/decisions/learnings; verify against current files before acting.
- Chat summaries and earlier agent replies are the lowest-confidence source for current environment state.

## Environment integrity — critical example

Before installing dependencies or creating a virtual environment, inspect `sys.executable`, `VIRTUAL_ENV`, `.venv/`, `venv/`, `env/`, `backend/.venv/`, `pyproject.toml`, requirements/lockfiles and existing setup docs. If an environment exists, determine whether it is usable; activate/reuse or repair it instead of creating a second environment. Never delete or overwrite an environment automatically.

Never commit `.env`, credentials, virtual environments, secret keys, private tokens, generated large artifacts or user data.

## Science and hackathon essentials

MuJoCo is authoritative physics; Nemotron on Nebius proposes hypotheses and bounded interventions; deterministic experiment verifier accepts or rejects improvements. Record seeds, telemetry, predictions and failed trials. Compare with fair baselines. Avoid ungrounded causal claims. Preserve the project's Physical AI track and submission obligations from the specification.

## Context economy

Prefer reading a few focused files and Basic Memory search hits, rather than repeatedly re-reading the full spec. If a retrieved note conflicts with source code, explain and correct the note. Maintain concise memory records with dates, exact paths and evidence. See `docs/MEMORY_SYSTEM.md`.
