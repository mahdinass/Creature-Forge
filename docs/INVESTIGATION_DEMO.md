# AI Investigation demo (2026-10-14)

Studio tab **AI Investigation** (`/?tab=demo`): **observed MuJoCo failure → Nemotron proposal → bounded edit → MuJoCo verification → synchronized replay → measured verdict.** Code: `creature_forge/demo.py`, API `/api/demo/*` (`creature_forge/studio/app.py`), UI `studio/src/demo/`, CLI `scripts/run_demo.py`, tests `tests/test_demo.py`, `studio/src/demo/demoLogic.test.ts`, browser flow `studio/e2e/demo-flow.mjs`.

## What each step is
1. **Observed failure**: the frozen Phase 2A incumbent is run on seed 9101 (a failing seed) and 9100 (a walking seed); the measurements are the model's only evidence.
2. **What the model saw**: the exact context JSON (controller table with bounds and normalised values, episode description, the measured seeds) and prompt hash, temperature and generation settings.
3. **Model proposal**: the reply exactly as received; each schema-valid proposal (claim, citations resolved to the measured values they point at, bounded edit with requested and realised step, predicted gain, self-reported confidence), or the reason it was rejected.
4. **Verification**: every valid proposal, plus a **matched random edit** of the same size, is run on 32 fresh seeds (9600–9631) beside the frozen controller. Rule: improved = ≥ 2 more walking seeds.
5. **Replay and verdict**: two synchronized MuJoCo replays (frozen vs edited, any seed) with the height chart and metrics, and the measured verdict.

## Provenance is explicit on every screen
- **LIVE**: a real Nebius call made during this run (green).
- **RECORDED LIVE**: a hash-verified stored copy of an earlier real call (blue); nothing is re-sent.
- **SCRIPTED MOCK — not a model**: text written by the repository (orange, striped); it can never be stored as live, recorded, or counted against the live budget (tests).
Model text is drawn in dashed "model" blocks; MuJoCo measurements in solid "measured" blocks. An unusable reply is shown as such and **nothing is simulated or substituted**.

## Bundled records (`experiments/phase2a_r3/demo_records/`, SHA-256 manifest)
| record | kind | what it shows |
|---|---|---|
| `live-001-invalid-citations` | RECORDED LIVE | Nemotron returned a valid envelope with 2 proposals, but both cited paths that point at lists (`failing_seeds.fell`); the strict contract rejected both; nothing was simulated. 6,280 tokens. |
| `live-002-two-valid-proposals` | RECORDED LIVE | After a path-format note was added to the **demo** prompt (not the registered R3 prompts): 2 valid proposals, both verified. Frozen controller 19/32 walking; proposal 1 (`balance_gain` + `kp`) 28/32, proposal 2 (`knee_shift` + `pitch_ref`) 25/32; their **matched random edits reached 25/32 and 30/32**. Both predictions were met, and random edits did as well or better. 8,374 tokens. |
| `scripted-mock-example` | SCRIPTED MOCK | Scripted text through the same pipeline and real physics, for UI testing and to show the label. |

**Reading it honestly:** the model's edits improved the frozen controller on these 32 seeds, and so did random edits of the same size; this single instance cannot show that the model's choices were better. The registered statistical comparison (R3) was not run (no generation setting passed calibration; `experiments/phase2a_r3/REPORT_V2.md`). R2's controller that walks 150/150 seeds came from a classical optimiser and is not attributed to Nemotron.

## Running it
- Browse recordings and run the scripted mock: `python scripts/run_studio.py`, open `http://127.0.0.1:8000/?tab=demo` (build the frontend first: `npm --prefix studio install && npm --prefix studio run build`).
- Live: set `NEBIUS_API_KEY` (env or `.env`) and `CREATURE_FORGE_ENABLE_LIVE=1`, tick the confirmation box, press *Run live with Nemotron* (≈ 1–4 min: one model call of 30–90 s, then 160 MuJoCo rollouts). CLI: `python scripts/run_demo.py live --confirm-live`; then `python scripts/run_demo.py record <run_id> --name <name>` promotes a **real live** run to a committed recording (mocks are refused).
- Generation settings: `reasoning_effort=low`, `max_tokens=8000`, temperature 0.7, 2 proposals per call. At `low`, the model used 4.6–6.7k completion tokens per call; the API does not report reasoning tokens, so the effect of the effort setting is unverified.

## Budget
Live calls are appended to `experiments/phase2a_r3/results_v2/demo_requests.jsonl` and count toward the same combined Nebius caps as R3 (41 requests / 300,000 tokens): after the two live runs, **13 requests / 70,764 tokens** are used in total. The server also caps live calls per process (10) and refuses live mode unless the flag is set and the box is ticked.

## Known limits
- One planar biped, one frozen controller, one failing seed per run; 32 verification seeds; a single verdict per run is not a statistical claim.
- Citations are validated to exist and resolve to values; whether the claimed mechanism is physically right is not checked and not claimed.
- A live run takes minutes on a laptop; the hosted/judging demo is meant to use the recordings (no server-side compute needed except replays, which are fresh rollouts).
