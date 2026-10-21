# Devpost submission text (V1, for the owner's final review; English)

**Paste fields:**
- **Project name:** Creature Forge
- **Tagline:** An AI scientist for physical failures. Nemotron chooses the experiments; physics decides.
- **Track:** Physical AI (simulation only; no hardware).
- **Repository:** *(GitHub URL, only once the owner makes the repository public or grants judge access)*
- **Licence:** Apache-2.0
- **Video:** *(YouTube URL, after the owner's upload)*

## Inspiration
When a robot fails, trying another design is easy. Finding out *why* it failed is hard. We wanted an AI that does science
on physical failures:
- it forms explanations;
- it chooses experiments that tell them apart;
- it repairs the robot;
- it accepts a repair only when an independent check says so.

A simulator that does not take the model's word for anything does the checking.

## What it does
Creature Forge is a laboratory for simulated two-legged robots with hidden faults: a slippery floor, a weak side, a
payload, lost feedback gain.
- **MuJoCo** is the instrument; every measurement and replay comes from it.
- **A Bayesian belief engine** keeps the competing explanations and their weights.
- **An optimiser** searches for repairs.
- **A pre-registered verifier** judges every repair on 24 held-out starts plus a 20-second endurance run. It returns
  FULL_RECOVERY, PARTIAL_IMPROVEMENT or NOT_RECOVERED.
- **NVIDIA Nemotron 3 Super**, through Nebius Token Factory, sits inside this laboratory as the scientist. It reads a
  notebook of measurements, writes executable hypotheses, chooses the next experiment, and decides when to hand the repair
  to the optimiser.

The video shows two recorded results from the Studio. They are kept separate on purpose:
1. **Verified repair (no AI).** A robot on a slippery floor.
   - The standard optimiser's repair walks farther, but only on 19 of 24 starts: a partial improvement.
   - Our DO-1 objective, a deterministic change to what the optimiser rewards, walks on 21 of 24 and passes the endurance
     run: a full recovery.
   - We then pre-registered a replication with five fresh optimizer seeds on the same robot. DO-1 recovered in 5 of 5; the
     standard objective in 0 of 5 (exact McNemar p = 0.031).
2. **Nemotron's experiment (recorded live run).** The same robot body has a different hidden fault, a weak side.
   - The belief engine's experiments all look equally informative to it. It picks a faster gait, and its belief ends
     99.8 % on the wrong side.
   - Nemotron picks a slower gait, where the explanations predict opposite outcomes, and its belief moves to the correct
     side.
   - Verification: Nemotron's lane fully recovers (23/24); the engine alone recovers partly (20/24).

## How we built it
- **NVIDIA Nemotron 3 Super on Nebius Token Factory:**
  - one validated tool call per turn, with a strict JSON schema, a whitelist and bounds;
  - an invalid reply is never repaired, and the code falls back to the engine's recommendation, which is recorded;
  - every call's request id, tokens and cost are written to a ledger with hard caps.
- **Deterministic laboratory:** MuJoCo plant and twin simulations, a Bayesian belief engine with expected-information-gain
  experiment ranking, CMA-ES repair, and a pre-registered verifier.
- **Nebius AI Cloud:** every heavy experiment ran on CPU VMs driven by our own start, stop, sync and watchdog tooling,
  with a spend cap and stops through the API.
- **Studio:** a React + three.js frontend and a FastAPI backend.
  - The two demo pages play back hash-pinned files that were exported from the exact recorded simulations.
  - The export is fail-closed: every row was reproduced exactly on Linux before export.
- **Scientific hygiene:**
  - pre-registered protocols committed before any run;
  - frozen record manifests and SHA-256 hashes;
  - reproduction gates;
  - intention-to-treat reporting, with nothing dropped.

## Challenges
- **Our first Nemotron calibration failed.** An earlier Nano setup returned empty replies, because hidden reasoning used
  the whole token budget. We recalibrated and moved to Super.
- **The optimiser's objective was the real bottleneck.** It kept proposing repairs that walked far but not reliably.
  Changing what it rewards (DO-1) fixed this instance, and the fix replicated.
- **Exact replay was hard.** Windows does not reproduce the Linux physics bit for bit. So demo exports run on the recorded
  Linux environment and are checked row by row; the Studio only plays them back.

## Accomplishments, with their limits
- **DO-1 replicated (NO_AI):** 5/5 vs 0/5 on one robot under fresh optimizer randomness.
  - It is reliable on that robot, but the margins are thin: 20–21 of 24 against a threshold of 20.
  - On two other fault families, an exploratory pilot gave one recovery. In the other case DO-1 passed validation but
    failed the endurance run.
- **Nemotron took a decision that mattered:** on identical evidence, its experiment choice turned a wrong diagnosis into a
  right one, and the episode verified.
  - This is one recorded instance, chosen afterwards. A second run made the same choice and only partly recovered.
  - Across 36 paired instances Nemotron and the engine alone are level (15 vs 14).
- **Nemotron's pre-registered win** is in our Forge Loop redesign scoreboard: AI-selected redesigns verified in 6 of 12
  investigations vs 1 of 12 for size-matched random edits (p = 0.031), mostly on push challenges.
- **Negative results are reported, not dropped.** Walking redesigns by the AI never verified, and several registered
  comparisons were null.

## What we learned
- A good scientist-agent does not need to out-compute the engine. It has to choose the right question when the numbers
  cannot tell options apart.
- Random edits are a strong baseline, so a single VERIFIED result says little until it stands next to its matched-random
  twin.

## What's next
Learning from past experiments: keeping hypotheses, failed experiments and repair outcomes, and testing, with a
memory-on vs memory-off design that prevents leakage, when a lesson from one robot really applies to another. Our first
attempt, retrieved text lessons in Forge Loop, showed no benefit (p = 0.773). So the next design stores measured causal
evidence, not prose.

## Built with
Python, MuJoCo, NumPy, FastAPI, React, three.js / React Three Fiber, TypeScript, Vite, **NVIDIA Nemotron 3 Super**,
**Nebius Token Factory**, **Nebius AI Cloud**.

## How Nemotron and Nebius are used (for judges)
1. **Runtime inference:** the HaS scientist calls Nemotron 3 Super through Token Factory.
   - The *Nemotron's experiment* and *AI scientist* pages play back recorded real calls. Request ids are in the
     records.
   - In the Studio, *My creature → Investigate with AI* makes live calls when a key is configured.
2. **Cloud execution:** all heavy simulation (the scientist studies and the DO-1 replication) ran on Nebius CPU VMs.

## Testing instructions
See the README *Quick start for judges*: Python 3.11+, Node 22+, then `pip install -e ".[studio]"`,
`npm --prefix studio ci`, `npm --prefix studio run build` and `python scripts/run_studio.py`. Then open `?tab=recovery`
and `?tab=nemotron`.
- No key is needed: both demo pages are recorded playback.
- Live mode needs a Nebius key; see `docs/submission/SETUP_AND_REPRODUCTION.md`.

## Attribution and independence
- Built for the Nebius × NVIDIA Global AI Hackathon. Not endorsed by, or affiliated with, NVIDIA or Nebius beyond
  participation.
- Licences are in `THIRD_PARTY_NOTICES.md`; model and service terms in `docs/MODEL_AND_SERVICE_TERMS.md`.
- Code was written with an AI coding assistant; those commits carry a `Co-Authored-By` disclosure.
