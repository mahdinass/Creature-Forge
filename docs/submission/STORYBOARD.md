# Demo video storyboard (W5 draft, 2026-10-21; 2:53.5 long, hard limit < 3:00)

**Positioning.** Creature Forge is an AI scientist that investigates why a robot fails. It tests explanations by
simulation and only accepts repairs that an independent verifier confirms. The video keeps two results apart:
- **DO-1**: a deterministic optimiser result. NO_AI.
- **Nemotron's scientific decision**: a recorded LIVE investigation, played back.

**Rules.** Hackathon rules (`docs/PROJECT_SPEC.md` §1.2): under three minutes, and at least one minute of the application
operating. Here 2:47 of the 2:53.5 is the running Studio (only the two text cards are not).
- Every frame comes from `studio/e2e/demo-video-capture.mjs`: the real Studio on the real GPU, playing back hash-pinned
  files.
- No new simulation and no model call happen while filming.
- The edit rules are at the end.

Voice-over: plain English, calm, about 110–130 words per minute. The rough cut writes the same text to `narration.srt` as captions.

| # | Time | Capture chapters | Screen | Voice-over |
|---|---|---|---|---|
| 0 | 0:00.0–0:02.5 | title card | "Creature Forge" / "An AI scientist for physical failures" | — |
| 1 | 0:02.5–0:16.5 | `hook` | Verified repair: three synchronised robots on the illustrative seed. The frozen repair falls at 0.79 s. | "A walking robot with a hidden fault, and two repairs, side by side in MuJoCo. What if an AI could investigate why a robot fails, instead of just trying another design?" (31 words) |
| 2 | 0:16.5–0:52.5 | `do1`, `why` | The three cards: faulty 5/24, frozen 19/24 PARTIAL, DO-1 21/24 FULL with 22/24 confirmation. Attribution flag. Then the "Why … not a full recovery" panel. | "First, how a repair is judged. Every design runs on twenty-four held-out starts the optimiser never saw. The frozen optimiser's repair goes farther on the median, but only nineteen of twenty-four starts walk: a partial improvement. DO-1 changes the optimiser's objective. Twenty-one walk, and a twenty-second confirmation passes. Full recovery, verified. This is purely deterministic optimisation, with no language model, and one replicate on one robot." (66 words) |
| 3 | 0:52.5–1:04.5 | `nemo-intro`, `failure` | "Nemotron's experiment": the RECORDED LIVE playback flag, then the damaged robot (reconstructed replay), 0/4 walking. | "Now the scientist: a recorded live investigation by NVIDIA Nemotron, played back, with no new model call. Same robot, a different hidden fault. It barely moves." (26 words) |
| 4 | 1:04.5–1:26.5 | `hypotheses`, `fork` | Belief 0.895 / 0.105. The candidate table: every EIG 0.34; the engine's row (freq ×1.2, predicts 1/1) and Nemotron's row (freq ×0.85, predicts 2/0). Then Nemotron's verbatim reason and "Registered prediction: none". | "The belief engine has two explanations: a weak right side, or a weak left. All seven experiments look equally informative to it. It picks a faster gait, where both predict the same walking. Nemotron picks a slower gait, where they predict opposite outcomes, without registering a formal prediction." (48 words) |
| 5 | 1:26.5–1:42.5 | `measure`, `measure-fall` | Both experiments replayed side by side on the damaged robot (reconstructed, measurements exact). Per-seed tiles 3/4 vs 2/4. | "MuJoCo runs both experiments on the damaged robot. These are the recorded measurements, replayed exactly. Nemotron's experiment walks on three of four starts; on one, it falls." (27 words) |
| 6 | 1:42.5–1:52.5 | `belief` | Belief bars: right 1.000 in Nemotron's lane; left 0.998 in the engine's. | "Nemotron's lane now points to the right side, which is correct. The engine alone is 99.8 percent sure of the wrong side." (22 words) |
| 7 | 1:52.5–2:06.5 | `repair`, `verify` | The repair log: delegated, twin design 6/8 vs 3/8. Then verification 23/24 FULL vs 20/24 PARTIAL, with the three-way reconstructed replay. | "Nemotron hands the repair to the engine's optimiser. The verifier: Nemotron's lane fully recovers, twenty-three of twenty-four. The engine alone, partly." (21 words) |
| 8 | 2:06.5–2:24.5 | `lab` | The laboratory strip: Nemotron → MuJoCo, belief engine, CMA-ES, memory → independent verifier. | "Nemotron 3 Super, on Nebius Token Factory, decides what to do next. Deterministic instruments do the rest: experiments, Bayesian inference, optimisation and memory. A hidden verifier decides. The simulation ran on Nebius AI Cloud." (34 words) |
| 9 | 2:24.5–2:49.5 | `scope`, `studies` | The A4 replicate (PARTIAL 19/24), the 36-instance strip (15 vs 14), then the study table with the scoreboard and DO-1 rows. | "Is Nemotron better? Not overall. A second run made the same choice and only partly recovered. Across thirty-six robots it is level with the engine. Our one pre-registered win is small: six of twelve redesigns verified, against one in twelve random edits, mostly on push tests. AI proposes; physics decides." (50 words) |
| 10 | 2:49.5–2:53.5 | end card | "Creature Forge · Built for the Nebius × NVIDIA Global AI Hackathon" (text only, no logos) | — |

**Word count:** 325 words of voice-over over 173.5 s of picture (about 112 words per minute). Generated from `video/cutlist.json`, which is the source; edit it there, not here.

**Nothing on screen or in the voice-over may claim:**
- that Nemotron produced the DO-1 recovery;
- that Nemotron beats the engine or random edits in general;
- that the replays are archived original frames. The Nemotron-page replays are reconstructions:
  - the experiment replays reproduce the recorded per-seed measurements exactly;
  - the verification replays match the recorded verdicts, because Stage 2 kept no per-seed verification rows.

## Edit rules (carried over, still binding)
- Keep the RECORDED LIVE / playback flag visible whenever Nemotron's words are on screen.
- **Never show:**
  - terminals, `.env`, tokens or request headers;
  - the Nebius console, account identifiers or balances.

  The capture uses a fresh browser profile and records only the page, so no address bar, bookmarks or desktop appear.
- Use only footage captured from the app: no stock clips, and no music unless its licence is documented (preferred: none).
- Do not display NVIDIA or Nebius logos or marks. Name them in text only.
- **Wording:**
  - Say "built for the Nebius × NVIDIA Global AI Hackathon", never "partner", "sponsored by" or "endorsed by".
  - Never say the model "proves", "beats random" or is "significantly better".
  - Never show the scoreboard without its caveats: small sample, mostly push, nothing verified on walking.
  - Never credit Nemotron with R2's classical 150/150 controller or with DO-1.
