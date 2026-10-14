# Devpost submission text (draft for review; English)

**Project name:** Creature Forge
**Tagline:** Machines that learn from falling.
**Track:** Physical AI (simulation-only; no hardware).
**Repository:** *(public GitHub URL, to be added when the repository is made public)* · **Licence:** Apache-2.0 · **Video:** *(YouTube URL)*

## What it does
Creature Forge is a physics-grounded failure-investigation workbench for a simulated two-legged robot. A failure is measured in MuJoCo (the robot falls at start-up), the evidence is captured (per-seed outcomes, step counts, pitch, timing), and **NVIDIA Nemotron** proposes *bounded* edits to the controller's parameters, citing the evidence it used and predicting how many more seeds will walk. MuJoCo then tests every valid proposal on 32 fresh seeds **beside a matched random edit of the same size**, and the user sees synchronized replays and an honest measured verdict. The model's words are never treated as results: anything it writes is labelled as the model's, invalid replies are shown as invalid, and only simulator measurements decide.

Separately, a **classical local optimiser** (no language model) improved the starting controller from walking on 91/150 untouched seeds to 150/150 (non-inferiority and superiority both confirmed; exact McNemar p = 3.5e-18). The Overview page keeps these two results apart.

## Why it is different
Most "AI designs robots" demos show a generated story or a reward curve. Creature Forge asks a narrower question — *can a language model's physical hypothesis be verified?* — and builds the apparatus to answer it honestly: preregistered protocols, hash-chained rollout ledgers, matched random baselines, strict schemas, and explicit provenance (LIVE / RECORDED LIVE / SCRIPTED MOCK). It also reports its own negative results.

## How we built it
- **Physics:** MuJoCo (planar biped, phase-based gait controller with 15 normalised parameters). Failure labels and walking gates are physical (alternating valid steps, upright, no dragging), not distance travelled.
- **NVIDIA Nemotron on Nebius Token Factory:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` is called at runtime through the OpenAI-compatible API by `creature_forge/nebius.py` (hard request/token caps, no retries, key never logged). Context is a measured-evidence JSON; output is a strict JSON proposal schema (citations must resolve to measured values; edits bounded to ±0.15 in normalised units).
- **Nebius AI Cloud:** all heavy experiments (about 15,000 rollouts across R1/R2) ran on a Nebius CPU VM (AMD EPYC Genoa, 8 vCPU / 32 GiB) managed by our controller (`infra/nebius/forge_cloud.py`: CLI via WSL, SSH, deadline watchdog, verified stop/delete).
- **Studio:** React + three.js frontend and FastAPI backend; replays are fresh deterministic MuJoCo rollouts served on demand.
- **Process:** every experiment preregistered (immutable protocol committed before the first rollout), budget ledger, exact statistics (Tango score non-inferiority test, exact McNemar), 300+ automated tests and real-browser checks in CI.

## Challenges
- A first global random search found nothing (the incumbent was 0.78 normalised units from the nearest sample); we reported that null result, diagnosed the objective, and moved to local search, which worked.
- Nemotron 3 Nano is a reasoning model: with the evidence prompt, hidden reasoning consumed the entire completion budget (up to 5,000 tokens) and returned **empty content** at every setting we preregistered, so the systematic comparison of the model against random edits was **not completed**. We stopped under our own rule rather than run an uninformative batch.
- Cross-platform reproducibility (Windows vs Linux floating point, CRLF in registered hashes) had to be handled explicitly.

## Accomplishments we are proud of
- A verifiable propose → simulate → verify loop with real Nemotron calls and matched random baselines, including a recorded run in which random edits did as well as or better than the model's — shown, not hidden.
- A statistically confirmed 150/150 vs 91/150 improvement with a stated exact interval (97.6%–100%), produced by classical optimisation and never attributed to the language model.
- End-to-end honesty tooling: provenance labels, immutable protocols, ledgers, CI that fails on misleading states.

## What we learned
Local search around a working controller is far more effective than global search; random edits are a strong baseline that any "AI proposer" must be compared against; hosted reasoning models need generation settings calibrated before any experiment.

## What's next
Calibrate a shorter evidence prompt (or structured output) and run the preregistered Nemotron-vs-random comparison; extend beyond one morphology; add Windows replication of the final evaluation.

## Built with
Python, MuJoCo, NumPy, FastAPI, React, three.js / React Three Fiber, TypeScript, Vite, **NVIDIA Nemotron**, **Nebius Token Factory**, **Nebius AI Cloud**.

## How Nemotron and Nebius are used (for judges)
1. Runtime inference: AI Investigation tab → *Run live with Nemotron* (needs a key; recordings of real calls are bundled).
2. Cloud execution: R1/R2 experiments on a Nebius CPU VM; ledgers and logs under `experiments/`.

## Testing instructions
See `README.md` ("Try it"): install, build the frontend, run `scripts/run_studio.py`, open the **Overview** and **AI Investigation** tabs. No key is needed for the recordings. `scripts/lab_browser_check.py` runs the real-browser flows.

## Honest limitations
One planar biped; simulation only; the Nemotron demo is a single verified instance, not a statistical claim; R3's systematic comparison was not completed; the 150/150 result is for the registered scenario family on Linux.

## Attribution and independence
Built for the Nebius × NVIDIA Global AI Hackathon. Not endorsed by, or affiliated with, NVIDIA or Nebius beyond participation. Third-party licences: `THIRD_PARTY_NOTICES.md`; model/service terms: `docs/MODEL_AND_SERVICE_TERMS.md`.
