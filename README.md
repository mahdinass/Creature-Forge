# Creature Forge

**Machines that learn from falling.** An autonomous physics-grounded robot-design research and product project for the Nebius × NVIDIA Global AI Hackathon 2026 (Physical AI track).

**Status:** Project specification and developer-context foundation committed; physics simulation, AI integration and product implementation not yet verified.

## Start here

- [Master project specification](docs/PROJECT_SPEC.md)
- [Verified project state](docs/PROJECT_STATE.md)
- [Shared agent instructions](AGENTS.md) / [Claude Code instructions](CLAUDE.md)
- **[Free local memory setup (Windows) — start here](docs/FREE_MEMORY_QUICKSTART.md)**
- [Full persistent memory architecture and optional cloud integration](docs/MEMORY_SYSTEM.md)
- [Nebius account, credits and model setup](docs/NEBIUS_SETUP.md)

Before starting Claude Code or Codex in this repository, inspect the existing environment and run:

```sh
python scripts/context_preflight.py
```

On Windows, `py -3 scripts/context_preflight.py` may be needed instead. Do **not** blindly create a new virtual environment. Claude Code has an optional repository hook that runs this preflight at session start and checks for duplicate environment creation; confirm project hooks are enabled and tested before relying on them. Codex follows the same convention via `AGENTS.md`.

## Scientific scope

A creator builds a robot, it attempts locomotion under authoritative MuJoCo physics, Failure Autopsy identifies evidence for possible mechanisms, a Nemotron investigator proposes falsifiable physical changes, and controlled counterfactual experiments test whether redesign truly improves stability. See the master spec for evaluation, architecture and extended roadmap.

## Hackathon reminder

Deadline: October 30, 2026, 18:00 Norway time. Public source repository, open-source license, a working project using NVIDIA open-source model(s) on Nebius and an under-three-minute YouTube demo are required for final submission. The repository is private during development and must be made public for judging.

Do not add real keys to git. A working app, dependency pins and deployment instructions will be added as implementation progresses.

## License

Apache License 2.0: see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). Third-party components and services (MuJoCo, NumPy, React Three Fiber, NVIDIA Nemotron via Nebius Token Factory, ...) are inventoried in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) (regenerate with `python scripts/generate_third_party_notices.py`). The repository remains private until the planned public-release review.

## Creature Forge Studio (local)

```
uv pip install --python .venv\Scripts\python.exe -e ".[studio]"
npm --prefix studio install && npm --prefix studio run build
.venv\Scripts\python scripts\run_studio.py        # http://127.0.0.1:8000
.venv\Scripts\python scripts\studio_e2e_check.py --browser
```
