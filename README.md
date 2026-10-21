# Creature Forge

**An AI scientist for physical failures.** Creature Forge investigates why a simulated robot fails. It tests explanations
by experiment in MuJoCo, and it accepts a repair only when an independent verifier confirms it. Built for the
Nebius × NVIDIA Global AI Hackathon 2026, **Physical AI** track (simulation only).

**NVIDIA Nemotron** (on **Nebius Token Factory**) takes scientific decisions inside a deterministic laboratory: which
experiment to run, which hypotheses to write, when to hand a repair to the optimiser. MuJoCo, a Bayesian belief engine,
an optimiser and a pre-registered verifier do the measuring and the judging. Heavy simulation ran on **Nebius AI Cloud**.

> **V1 release candidate.** Release record, tests and reproduction: [`docs/RELEASE_V1.md`](docs/RELEASE_V1.md).

## What the demo shows (two separate results; please do not mix them)
| Studio page | What you see | Who did it | Evidence |
|---|---|---|---|
| **Verified repair** (`?tab=recovery`) | One robot with a hidden slippery-floor fault (faulty: 5/24 starts walk). Two optimizer repairs, replayed side by side. **Frozen** objective: PARTIAL_IMPROVEMENT, 19/24 walk. **DO-1** objective: FULL_RECOVERY, 21/24, and the 20 s confirmation passes. | A deterministic change to the optimizer's objective. **NO_AI: no language model.** | [`docs/DO1_DEMO.md`](docs/DO1_DEMO.md); replays hash-pinned in `experiments/do1/demo/` |
| **Nemotron's experiment** (`?tab=nemotron`) | A recorded LIVE investigation, played back. Both lanes have the same evidence. The engine's experiment (freq ×1.2) leaves its belief 99.8 % on the wrong side. Nemotron's experiment (freq ×0.85) moves it to the right side. The repair is then verified: Nemotron's lane is FULL 23/24, the engine alone PARTIAL 20/24. | **Nemotron 3 Super** chose the experiment. The engine and the optimiser did the rest. | [`docs/NEMOTRON_CONTRIBUTION.md`](docs/NEMOTRON_CONTRIBUTION.md); `experiments/w2/` |

**How strong is each result?**
- **DO-1 was replicated.** In a pre-registered replication on the same robot, with 5 fresh optimizer seeds (W3), DO-1
  recovered in **5/5** and the frozen objective in **0/5** (exact one-sided McNemar p = 0.031).
  - This shows reliability on **one** robot, on its already studied validation seeds, with thin margins (20–21/24 against
    a threshold of 20).
  - In a two-instance cross-family pilot (W4), DO-1 recovered one case. In the other it passed validation but failed the
    20 s confirmation.
  - Full details: [`docs/DO1_REPLICATION_REPORT.md`](docs/DO1_REPLICATION_REPORT.md), with raw records and audit in
    `experiments/do1/w3w4_2026-10-21/`.
- **The Nemotron case is one selected, recorded instance.** A second Nemotron run made the same choice and only partly
  recovered.
  - Across 36 paired instances, Nemotron and the engine alone verified **15 vs 14** (p = 0.50): parity, not superiority.
  - Nemotron's one pre-registered favourable result is the Forge Loop scoreboard: 6/12 verified redesigns vs 1/12 for
    matched random edits (p = 0.031), mostly on push challenges
    ([`experiments/forge_loop/scoreboard/REPORT.md`](experiments/forge_loop/scoreboard/REPORT.md)).
- **R2 is classical optimisation, not Nemotron.** An earlier controller walks on 150/150 untouched seeds vs 91/150.

## Quick start for judges (no API key, no cloud, about 10 minutes)
Prerequisites: Python 3.11 or 3.12, Node 22+, Git, and Chrome or Edge.

```sh
git clone https://github.com/mahdinass/Creature-Forge.git && cd Creature-Forge
python -m venv .venv
.venv/bin/pip install -e ".[studio]"            # Windows: .venv\Scripts\pip install -e ".[studio]"
npm --prefix studio ci && npm --prefix studio run build
.venv/bin/python scripts/run_studio.py          # Windows: .venv\Scripts\python scripts\run_studio.py
```

Then open:
- <http://127.0.0.1:8000/?tab=recovery> (Verified repair);
- <http://127.0.0.1:8000/?tab=nemotron> (Nemotron's experiment);
- or Home, then *Shown in the demo video*.

Both pages play back recorded, hash-pinned files. They make no model call and no simulation, so they need no key.

**Windows, one command:** `powershell -ExecutionPolicy Bypass -File scripts\start_studio.ps1`. It frees port 8000,
rebuilds a stale frontend, checks the API and opens the browser.

**Also in the Studio:**
- **Create → Draw** (sketch a biped);
- **Simulate → Playground / Compare / My creature** (live MuJoCo on your machine);
- **Investigate → AI investigation, AI scientist, Causal engineer, Walking lab, Experiment history** (recorded runs).

Without a key, every AI action runs as a clearly labelled **SCRIPTED MOCK** and is never presented as a model.

## Live Nemotron (optional; needs a Nebius Token Factory key; costs money)
Put `NEBIUS_API_KEY=<key>` and `CREATURE_FORGE_ENABLE_LIVE=1` in a git-ignored `.env` (see `.env.example`) and restart
the Studio. Live calls are then allowed in three places:
- **My creature → Investigate with AI:** `nvidia/nemotron-3-super-120b-a12b`, settings in
  `experiments/forge_loop/model_config.json`. About 1–2 calls and fractions of a cent per investigation, plus MuJoCo
  verification.
- **My creature → Recover walking (AI director):** the same model.
- **AI investigation → Run live:** the original Nano demo path, `creature_forge/demo.py`.

Every call goes through `creature_forge/nebius.py`, which has request, token and dollar caps, no blind retries, and never
logs the key. Each call is recorded in an inference ledger. Replies are validated against a schema, a whitelist and bounds,
and are never clipped or repaired. The **Nemotron's experiment** and **AI scientist** pages show recorded runs of the HaS
scientist (`scripts/hdb_agent_run.py`), which we ran on a Nebius VM; the Studio does not start those runs.

## Where NVIDIA and Nebius are used
| Component | Role |
|---|---|
| NVIDIA Nemotron 3 Super (Token Factory) | Experiment choice, executable hypotheses and delegation in the HaS scientist; redesign proposals and diagnostic probes in Forge Loop. |
| NVIDIA Nemotron 3 Nano (Token Factory) | The original AI-investigation demo (recorded) and the R3 calibration. |
| Nebius AI Cloud | All heavy MuJoCo experiments (DS-1, W3/W4, R1/R2, scoreboard) on CPU VMs controlled by `infra/nebius/` (spend cap, deadline watchdog, API stop). |
| MuJoCo | Every measurement, verdict and replay. |

## Reproduce
```sh
.venv/bin/python -m unittest discover -s tests          # about 1,600 tests (some skip without git-ignored raw records)
npm --prefix studio test && npm --prefix studio run build
.venv/bin/python scripts/smoke_test.py                  # MuJoCo rollout, determinism, fall detection
.venv/bin/python scripts/lab_browser_check.py           # real-browser flows incl. both demo-video pages (needs Chrome/Edge)
.venv/bin/python scripts/do1_replication_analysis.py \
  --w3 experiments/do1/w3w4_2026-10-21/do1_l4_rep.jsonl --w4 experiments/do1/w3w4_2026-10-21/do1_x.jsonl
```
- The last command recomputes the W3/W4 statistics from the raw records, with no physics.
- Re-running physics experiments needs Linux and the recorded environment. Windows reproduces labels and verdicts but not
  every row bit-for-bit.
- Everything else is covered in [`docs/submission/SETUP_AND_REPRODUCTION.md`](docs/submission/SETUP_AND_REPRODUCTION.md).

## Honest limits
- **Scope:** simulation only, with one planar biped family.
- **DO-1:** reliable on one robot under different optimizer randomness. W4 has only two examples.
- **Nemotron:** the recorded case is one instance, chosen afterwards. The broad comparison shows parity with the engine
  alone.
- **Replays:** they are exact playbacks of stored records. Large raw archives are kept out of Git and documented in
  [`docs/NONGIT_ASSETS_2026-10-21.md`](docs/NONGIT_ASSETS_2026-10-21.md).

## Repository map
- `creature_forge/`: physics, controllers, belief engine, optimiser, verifier, Nebius client, Studio API.
- `studio/`: React and three.js frontend, with `studio/e2e/` real-browser flows.
- `experiments/`: pre-registered protocols, raw records, reports and `FROZEN_MANIFEST.json`.
- `scripts/`: runners, analyses, exporters.
- `infra/nebius/`: cloud VM control.
- `docs/`: specification, state, reports, `submission/` (Devpost text, storyboard, video production, checklist).

## License
- Apache License 2.0: [`LICENSE`](LICENSE), [`NOTICE`](NOTICE). Third-party inventory:
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- NVIDIA Nemotron is used only as a hosted service under its own licence; no weights are distributed. Terms:
  [`docs/MODEL_AND_SERVICE_TERMS.md`](docs/MODEL_AND_SERVICE_TERMS.md).
- This is an independent hackathon project, not endorsed by NVIDIA or Nebius.
- Commits made with an AI coding assistant carry a `Co-Authored-By` disclosure.

## For contributors and coding agents
Read [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) and `docs/PROJECT_STATE.md`, and run
`python scripts/context_preflight.py` first. The V1 release is frozen; develop on new branches (see
[`docs/RELEASE_V1.md`](docs/RELEASE_V1.md)).
