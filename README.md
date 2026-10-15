# Creature Forge

**Machines that learn from falling.** A physics-grounded failure-investigation workbench for a simulated biped, built for the Nebius × NVIDIA Global AI Hackathon 2026 (**Physical AI** track).

A robot fails in MuJoCo → Creature Forge records measured evidence about the failure → **NVIDIA Nemotron** (hosted on **Nebius Token Factory**) proposes bounded physical interventions → MuJoCo tests each proposal beside a **matched random edit** → you see synchronized replays and an honest measured verdict.

> **Two separate results — please do not mix them**
>
> | | What it shows | Who found it |
> |---|---|---|
> | **Classical optimisation (R2)** | A controller that walks on **150/150** untouched seeds vs **91/150** for the starting controller (non-inferiority and superiority both confirmed, exact McNemar p = 3.5e-18). | A classical local optimiser. **No language model.** |
> | **Nemotron investigation demo** | Real Nemotron proposals, verified by MuJoCo next to matched random edits. In the bundled live recording the model's edits improved the controller **and so did random edits of the same size** (25/32 and 30/32 vs the model's 28/32 and 25/32). | Nemotron proposes; MuJoCo decides. **No claim that the model beats random.** |
>
> The systematic Nemotron-vs-random comparison (experiment R3) was **not completed**: no generation setting passed our preregistered calibration (the evidence prompt returned empty replies because hidden reasoning used the whole token budget). It is reported as such in `experiments/phase2a_r3/REPORT_V2.md`.

## Forge Loop (new): Draw, Challenge, AI Redesign, Verify, Evolve

Forge Loop runs a creature you drew through a stand, push or walk challenge in MuJoCo. Nemotron reads the measured failure
evidence and proposes bounded edits. Deterministic code validates each proposal. Each AI proposal is then tested beside a
matched-random twin (a random edit of the same size) on held-out seeds, and `verdict_v1` gives a verdict. You decide whether
to accept a verified version. The model never decides a score, and the loop never accepts a design on its own.

Full guide for judges and developers: [`docs/FORGE_LOOP.md`](docs/FORGE_LOOP.md). Contracts: [`docs/FORGE_LOOP_CONTRACTS.md`](docs/FORGE_LOOP_CONTRACTS.md).

**Headline results (honest, development stage):**

- Most live Nemotron investigations so far ended NOT_VERIFIED or INCONCLUSIVE. The archived records are in
  [`experiments/forge_loop/dev_live_records/`](experiments/forge_loop/dev_live_records/README.md).
- Three records on one balanced creature (push) reached VERIFIED_IMPROVEMENT on 12 held-out seeds each: `i-f9873480e42a`
  (rear foot x1.25, +3.125 N median) and, with diagnostic probes, `i-47bc91e407c2` (+3.125 N) and `i-172b6a48a0ad`
  (+4.375 N). These are worked cases on one creature and one challenge, not statistics.
- A null pilot found that about 15% of random push edits on standing creatures also verify. A single VERIFIED arm is
  therefore not evidence of model skill, and every AI verdict is shown beside its matched-random twin.
- Pre-registered scoreboard (12 fresh drawn creatures, 6 starters x 2): the AI's selected redesign verified in 6/12
  investigations, its own size-matched random twin in 1/12 (discordant 5 vs 0, exact one-sided McNemar p = 0.031). The
  effect is concentrated in the push challenge; on creatures that cannot stand the AI verified once and its twin did
  better. Small study, one zoo; see [`experiments/forge_loop/scoreboard/REPORT.md`](experiments/forge_loop/scoreboard/REPORT.md).
- The R2 result (150/150 vs 91/150) is classical optimisation, not Nemotron. The earlier recorded Nemotron demo did not
  beat matched random edits. R3 produced no statistical result.

**Run it:** locally, `python scripts/run_studio.py` (scripted mock only, no key). Live Nemotron needs `NEBIUS_API_KEY` in
`.env` and `CREATURE_FORGE_ENABLE_LIVE=1`. Commands for the Nebius VM are in the guide.

## Try it (no API key needed)

```sh
# 1. Python 3.11+ (CI uses 3.12) and Node 22+ required
python -m venv .venv && .venv/bin/pip install -e ".[studio]"          # Windows: .venv\Scripts\pip
npm --prefix studio install && npm --prefix studio run build
# 2. Run the Studio
.venv/bin/python scripts/run_studio.py                               # http://127.0.0.1:8000
```

**Windows, one command (recommended):** `powershell -ExecutionPolicy Bypass -File scripts\start_studio.ps1`. It replaces an older Studio left on port 8000, rebuilds a stale frontend, starts the current server, verifies that every API route the UI needs exists, and opens the browser. `GET /api/version` shows which commit is being served.

Open **Home**: the hero is a real MuJoCo replay of the walking controllers. Navigation follows the journey **Create → Simulate → Investigate**:

- **Create → Draw:** draw a side-view biped freehand (mouse, touch or pen; undo, redo, erase, zoom, pan). Deterministic stroke interpretation shows the torso, joints and feet it found, a live MuJoCo preview, and what it assumed. **Guided constraints ON** (default) snaps gently and keeps the creature inside the verified design range; **OFF (experimental)** uses your strokes exactly as drawn and runs bad-but-buildable creatures through MuJoCo so they can fall. Drawings the model cannot represent are refused with the exact reason, with an optional consent-gated approximation. *Refine* keeps the older joint-handle editor.
- **Simulate → Playground / Compare designs:** push a creature and read, in plain words, why it fell.
- **Investigate → AI investigation / Walking lab / Experiment history:** the recorded Nemotron investigation (failure → evidence → proposal → verification → verdict, with synchronized before/after simulations), the tuned walking robot next to the starting one, and an archive of earlier experiments sorted by outcome.

Old `?tab=` links (`overview`, `studio`, `compare`, `lab`, `locomotion`, `demo`, `sketch`) keep working.

## Where NVIDIA Nemotron and Nebius are used

| Component | How |
|---|---|
| **NVIDIA Nemotron** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Runtime calls from `creature_forge/demo.py` (and the R3 tooling) through **Nebius Token Factory**'s OpenAI-compatible API (`creature_forge/nebius.py`: no retries, hard request/token caps, key never logged). It receives measured evidence and proposes bounded parameter edits under a strict JSON schema; invalid output is shown as invalid, never repaired. |
| **Nebius AI Cloud** | All heavy MuJoCo experiments (R1 and R2, about 15,000 rollouts) ran on a Nebius CPU VM (`cpu-d3`, 8 vCPU / 32 GiB, Ubuntu) controlled by `infra/nebius/forge_cloud.py` (CLI in WSL, SSH, deadline watchdog, stop/delete safeguards). No GPU was needed. |
| **MuJoCo** | Authoritative physics for every measurement and replay. |

Live mode (optional): set `NEBIUS_API_KEY` (environment or a git-ignored `.env`, see `.env.example`) and `CREATURE_FORGE_ENABLE_LIVE=1`, then use *Run live with Nemotron* in the AI Investigation tab (one model call, then ~1–4 minutes of MuJoCo verification). Live calls draw on a shared budget (41 requests / 300,000 tokens; 13 used).

## Reproduce the evidence

```sh
.venv/bin/python -m unittest discover -s tests -v                    # 300+ tests (physics, statistics, guards, demo, overview)
npm --prefix studio test                                              # frontend unit tests
.venv/bin/python scripts/smoke_test.py                                # MuJoCo rollout, determinism, fall detection
.venv/bin/python scripts/lab_browser_check.py                         # real-browser flows (needs Chrome/Edge)
.venv/bin/python scripts/verify_demo_trials.py --full                 # recorded Phase 1 trials reproduce bit-for-bit
```

Every experiment is **preregistered** (an immutable `protocol.json` committed before the first rollout), runs under a hash-chained rollout ledger, and reports null and failed outcomes: `experiments/phase1`, `phase2a`, `phase2a_r1` (null), `phase2a_r2` (confirmed), `phase2a_r3` (aborted/not completed). Re-running R2 end to end on a cloud VM is documented in [`docs/NEBIUS_CLOUD_R1.md`](docs/NEBIUS_CLOUD_R1.md) and [`docs/submission/SETUP_AND_REPRODUCTION.md`](docs/submission/SETUP_AND_REPRODUCTION.md).

## Honest limits

One planar biped, one controller family, simulation only. The 150/150 result is for the registered scenario family (fresh initial poses), not general robustness. The Nemotron demo is a verifiable loop, not a statistical claim. Replays are fresh simulations of stored controller parameters. See [`docs/INVESTIGATION_DEMO.md`](docs/INVESTIGATION_DEMO.md).

## Repository map

`creature_forge/` physics, controllers, statistics, Nebius client, demo · `studio/` React + three.js frontend · `experiments/` preregistered protocols, ledgers, results, reports · `infra/nebius/` cloud VM controller · `docs/` specification, state, decisions, reproducibility, submission package · `tests/`, `scripts/`.

## License

Apache License 2.0: [`LICENSE`](LICENSE), [`NOTICE`](NOTICE); third-party inventory in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). NVIDIA Nemotron is used only as a hosted service under its own license (NVIDIA Nemotron Open Model License); no weights are distributed. Model and service terms: [`docs/MODEL_AND_SERVICE_TERMS.md`](docs/MODEL_AND_SERVICE_TERMS.md). Creature Forge is an independent hackathon project: it is not endorsed by, or affiliated with, NVIDIA or Nebius beyond participation in the hackathon.

## For contributors and coding agents

Read [`AGENTS.md`](AGENTS.md) / [`CLAUDE.md`](CLAUDE.md), `docs/PROJECT_STATE.md`, and run `python scripts/context_preflight.py` first. The full specification is [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md); the free local memory setup is [`docs/FREE_MEMORY_QUICKSTART.md`](docs/FREE_MEMORY_QUICKSTART.md).
