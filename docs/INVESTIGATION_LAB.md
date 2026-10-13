# Investigation Lab (Phase 1.5)

The **Investigations** tab in Creature Forge Studio lets you walk through any saved Nemotron investigation:
**Observe → Hypothesize → Intervene → Verify → Compare**. Everything shown is either read from an immutable saved
record or produced by a fresh MuJoCo run. The browser invents nothing and no model is called.

Run it: `python scripts/run_studio.py` (after `npm --prefix studio run build`), open the **Investigations** tab.
Deep link: `/?tab=lab&trial=<id>&step=verify`.

## How claims are separated
| Look | Meaning |
|---|---|
| solid blue outline, "Measured by MuJoCo" | numbers MuJoCo produced (evidence, verifier results, replays) |
| dashed violet outline, "Model-written · unverified" | the hypothesis, mechanism label and prediction; a guess, never a proven cause |
| dotted amber outline, "Self-reported by the model" | the model's confidence; uncalibrated, never used by the verifier |

Failed experiments stay in the history: rejected, invalid and errored records are listed next to accepted ones, with
a plain-language status. An invalid reply is shown verbatim as plain text, labelled untrusted and "never tested".

## Data
* `experiments/demo_trials/`: byte-identical copies of the **four real** live Nemotron investigations of 2026-10-13
  (3 rejected by MuJoCo, 1 invalid response) plus `manifest.json` with SHA-256 per file. Marked `-text` in
  `.gitattributes` so the hashes hold on Windows and Linux. **There is no accepted AI trial; none was fabricated.**
* The 16 cm-foot design in *Compare (Phase 0)* is a human-authored reference, not an AI result; the lab says so.
* Local records in `artifacts/investigations/` (git-ignored) are listed too; a local copy of a bundled id wins.

## API (read-only, `creature_forge/lab.py`)
* `GET /api/lab/trials`: history (unreadable files are listed, not hidden).
* `GET /api/lab/trials/{id}`: display model: sections, provenance labels, verdict, missing pieces, raw reply, integrity.
* `GET /api/lab/trials/{id}/replay?seed=N`: re-simulates original and modified robots with MuJoCo from the parameters
  saved in the record, and reports whether the fresh per-seed statistics match the saved ones.

## Replay is reproducible from saved parameters (requirement 7)
A record stores the baseline body, controller, push, duration, seeds and the candidate body. MuJoCo is deterministic,
so `build_replay` regenerates geometry, poses and telemetry with no model call. Displayed statistics correspond to
the original evaluation: the replay is compared with the saved screening numbers by the cross-platform tolerance
policy (`docs/REPRODUCIBILITY.md`), and the badge says "matches the saved record" or "DIFFERS".
Measured on Windows (`python scripts/verify_demo_trials.py --full`): all 4 records hash-verified; every saved seed of
every arm reproduces with max relative difference 0.0; the full held-out protocol (5 pushes x 10 seeds x 2 designs =
100 simulations) reproduces for both records that have one. Linux differs only at the documented ~1e-14 level.
The held-out numbers shown in the UI are the recorded ones; recomputing them is a script (about 1.5 min per record),
not a button.

## Tests
* Python `tests/test_lab.py` (listing, loading, traversal ids, corrupt/empty/malformed records, views, replay
  consistency, tamper detection, held-out recompute, API, no model calls, no credentials, manifest hashes).
* Frontend `studio/src/lab/labLogic.test.ts` (status wording, step availability, formatting, filters, deep links).
* Real browser `scripts/lab_browser_check.py` -> `studio/e2e/investigation-flow.mjs` (playwright-core + system
  Chrome/Edge): history -> select -> evidence -> hypothesis -> change -> verdict -> load simulation -> synchronized
  two-robot compare, invalid-response path, seed change, error/retry paths, phone width, no page errors.

## Not implemented (by design for this milestone)
* No running of new investigations from the UI (records are written by scripts); no model calls.
* No in-app recomputation of the held-out protocol (script only).
* The replay uses the saved controller and bodies; Studio's free-form editor is unchanged and separate.
* Visual polish is deliberately minimal; a dedicated polish phase is planned.
* The built frontend and demo records are not packaged in the Python wheel (source-checkout feature).

## Bug fixed on the way
Leaving any tab with a viewport threw `removeChild` errors (drei `<Html>` portal under React 19). The push label is now
a plain DOM overlay; physics and poses are unaffected.
