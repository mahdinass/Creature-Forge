# Devpost submission text (draft for review; English)

**Project name:** Creature Forge
**Tagline:** You draw a robot. Nemotron investigates why it fails. MuJoCo verifies the fix.
**Track:** Physical AI (simulation-only; no hardware).
**Repository:** *(public GitHub URL, only if and when the owner makes the repository public)* · **Licence:** Apache-2.0 · **Video:** *(YouTube URL)*

## Inspiration
Most "AI designs robots" demos show a generated story or a reward curve. We wanted real AI-driven engineering: a model that reads measured physical failures, forms a hypothesis, and then has that hypothesis checked by a simulator that does not take its word for anything.

## What it does
A user draws a robot. NVIDIA Nemotron investigates its physical failures, proposes structural and controller redesigns, and MuJoCo independently verifies whether the changes work. Verified improvements become new creature versions.

The loop is Draw, Challenge, AI Redesign, Verify, Evolve:
1. **Draw** a side-view biped in the Studio and save it as version 1.
2. **Challenge** it (stand, push or walk) in MuJoCo; per-seed failures and replays are recorded.
3. **Investigate with AI.** Nemotron reads a compact evidence pack, may request up to 3 diagnostic probes (counterfactual simulations such as "longer feet" or "stronger motors") that the code reports as CONFIRMED or REFUTED, then proposes up to 3 bounded edits. A deterministic validator accepts or rejects each one with a named reason.
4. **Verify.** The Counterfactual Arena tests the original, each proposal, a size-matched random twin of each proposal and a non-AI heuristic on held-out seeds. A fixed rule (`verdict_v1`) returns VERIFIED, NOT_VERIFIED, WORSE or INCONCLUSIVE.
5. **Evolve.** The user accepts a VERIFIED redesign as version 2 (the server refuses anything else) and re-challenges it.

The model proposes, the physics measures, the rule judges, the user decides. Model confidence never enters a verdict.

## How we built it
- **NVIDIA Nemotron-3-Super-120B on Nebius Token Factory:** strict JSON-schema replies whose enums list every editable parameter and every citable evidence value; thinking disabled; diagnostic probes; hard request, token and dollar caps in a ledger.
- **MuJoCo:** planar biped, challenges, probes, and a deterministic verdict. Replays are fresh deterministic rollouts.
- **Counterfactual Arena:** every AI result is shown beside its matched-random twin.
- **Nebius AI Cloud:** all simulation and testing ran on a Nebius CPU VM, driven by our own start/stop/sync tooling with a spend cap.
- **Studio:** React and React Three Fiber frontend, FastAPI backend.

## Challenges
- Our earlier Nemotron Nano experiment returned empty replies (hidden reasoning used the whole token budget), so that comparison was never completed. We ran a model calibration (30 requests, $0.31) and chose Super with thinking off.
- The first calibration produced 0 of 12 valid replies because of contract defects (ids, citation paths); schema enums fixed them.
- Push measurements were too coarse to see small gains; we refined the resolution to 0.625 N.
- In one run the model proposed a mechanism its own probes had refuted; we added an explicit method rule.
- A matched-random twin once copied the AI's edit; we fixed the twin generator (`matched_random_v2`) and always validate the selected arm's own twin.

## Accomplishments (with limits)
- A real end-to-end live browser test passed 15 of 15 checks: a drawn creature, a real Nemotron call, a VERIFIED redesign (+6.25 N push resistance, 12 wins, 0 losses on 12 held-out seeds) accepted as v2 and re-challenged.
- A pre-registered scoreboard (protocol committed before any run, 12 investigations, no exclusions): the Nemotron-selected redesign was verified in 6 of 12, its matched-random twin in 1 of 12 (discordant pairs 5 vs 0, exact one-sided p = 0.03125). We read this as encouraging evidence **limited to the tested creatures and challenges**, not as a general result. Limits: only 12 investigations; six starter shapes, each repeated twice; 5 of the 6 successes were on the push challenge, where the pipeline was developed; the AI arm picks the best of up to 3 proposals while the twin is a single edit (a post-hoc check against the best baseline also gave 5 vs 0); one more twin-only success would have removed the p-value. Cost: 24 model calls, $0.05.
- Honest negatives: walking investigations verified nothing. The probes confirmed the feet, but gains were small and consistent and stayed below the 0.5 m bar, and the model never chose controller co-design. A separate classical optimiser (no language model) reached 150/150 walking seeds; that result is not Nemotron's. The earlier recorded demo did not beat matched random edits.

## What we learned
Random edits are a strong baseline (about 15% of random push edits verified in our null pilot), so a single VERIFIED proposal says little about model skill; the matched-twin comparison does. Calibrate output format and contracts before judging reasoning.

## What's next
A pre-registered paired evaluation of engineering memory (lessons from other creatures, memory on versus off) is running; its result is pending and not claimed here. Next: walking co-design and more creature families.

## Built with
Python, MuJoCo, NumPy, FastAPI, React, React Three Fiber, TypeScript, Vite, **NVIDIA Nemotron**, **Nebius Token Factory**, **Nebius AI Cloud**.

## How Nemotron and Nebius are used (for judges)
1. Runtime inference: *Investigate with AI* in the "My creature" tab calls Nemotron-3-Super through Token Factory (needs a key; archived real calls are bundled).
2. Cloud execution: all heavy simulation, tests and the scoreboard ran on a Nebius CPU VM.

## Testing instructions
See `docs/submission/SETUP_AND_REPRODUCTION.md`. No key is needed for the scripted mode or the committed records; live mode needs a Nebius key.

## Attribution and independence
Built for the Nebius x NVIDIA Global AI Hackathon. Not endorsed by, or affiliated with, NVIDIA or Nebius beyond participation. Licences: `THIRD_PARTY_NOTICES.md`; model and service terms: `docs/MODEL_AND_SERVICE_TERMS.md`.
