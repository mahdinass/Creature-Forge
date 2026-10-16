# Forge Loop

Status as of 2026-10-15, branch `feature/forge-loop`. Implemented and tested on the Nebius VM. Live Nemotron calls have
run on development records. A small pre-registered scoreboard found AI-selected edits verified more often than matched random edits (6/12 vs 1/12, p = 0.031), mostly on the push challenge. Contracts: `docs/FORGE_LOOP_CONTRACTS.md`.

## What it is

Forge Loop is the part of Creature Forge that takes a creature you drew and runs it through a repeatable cycle:
Draw, Challenge, AI Redesign, Verify, Evolve. You draw a side-view biped. MuJoCo runs it through a stand, push or walk
challenge and records how it fails. An AI model (NVIDIA Nemotron on Nebius Token Factory) reads that evidence and
proposes bounded physical edits. Deterministic code checks each proposal against the edit rules. MuJoCo then tests each
proposal, and each one is compared with a matched random edit of the same size. A fixed rule (`verdict_v1`) decides
whether a proposal is verified on held-out seeds. You decide whether to accept a verified version. The model proposes,
the physics measures, and the rule judges.

## The loop step by step

| Step | You do | The system does |
|---|---|---|
| 1. Draw | Draw a creature in the Studio (Create, Draw) or use a starter shape. Click "Use this creature". | Interprets the strokes into a body. Stores version 1 with its drawing. |
| 2. Challenge | Pick stand, push or walk and run it. | Runs one MuJoCo job per seed. Shows a PASS, POOR, FAIL or ERROR outcome, per-seed scores and a replay. |
| 3. AI Redesign | Start an investigation (live or scripted). | Builds a compact evidence pack. Asks the model for hypotheses and up to 3 proposals. Validates each proposal and records accepted or rejected with reasons. Optionally runs diagnostic probes first. |
| 4. Verify | Read the arena results. | Runs the original, the AI arms, a matched-random twin of each AI arm and a heuristic arm. Screens on one set of seeds, validates on another. Gives each arm a verdict. |
| 5. Evolve | Accept a VERIFIED arm, or revert to an earlier version. | Stores an accepted arm as a new version with its lineage. Refuses any arm that is not VERIFIED. A bounded loop can repeat steps 2 to 4, but never accepts. |

## Who decides what

| Part | Decides | Does not decide |
|---|---|---|
| Nemotron (model) | Hypotheses, edit proposals, predictions, probe requests | Scores, verdicts, what is accepted |
| Deterministic validator (`forge_ai.py`, `interventions.py`) | Whether each proposal is accepted or rejected, with a named reason | Physics. It never clips a value into range. |
| MuJoCo (`challenges.py`, `arena.py`) | Every score, metric, replay and probe result | Whether a design is good enough |
| `verdict_v1` (`verdict.py`) | VERIFIED_IMPROVEMENT, NOT_VERIFIED, WORSE or INCONCLUSIVE | Acceptance |
| You | Accept or revert | Nothing is accepted automatically |

Model confidence is recorded but is never an input to any verdict.

## Challenges

Each challenge runs on a fixed list of seeds. Each seed gives one outcome and one score.

| Challenge | Duration | Score | PASS | POOR | FAIL |
|---|---|---|---|---|---|
| stand | 8 s | Survival time (s) | Stands for the full duration with a clean posture | Survives, but pitch after settling exceeds 0.5 rad or height drops below 0.7 of the start | Falls |
| push | 5 s | Lower of the forward and backward critical push force (N) | Score at least the target (default 10 N) | Score at least 60% of the target | Below that |
| walk | 10 s | Forward distance (m) while upright and gait-valid | Gait label "walking" | Upright at the end, but not walking | Falls |

- Push uses bisection over 0 to 80 N. The default resolution is 2.5 N (5 steps). Investigations use 0.625 N (7 steps).
- Failure checks ignore the first 0.3 s (the settle window), because drawings can lean at the start.
- Aggregate outcome for a challenge: PASS if at least 80% of seeds pass, FAIL if at least 50% fail, otherwise POOR.
- ERROR means a seed could not run. It is reported with its message and is never counted as FAIL.
- The pilot found that the backward push is the weak direction for every standing body tested. The default body therefore
  scores about 10 N on push. The contract's 25 N default was not reachable and the target was lowered to 10 N.

Seeds come from hashed blocks at or above 100,000. Roles (challenge, train, screen, validate, probe) never overlap.

## The AI investigator

- **Model:** `nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory. Reasoning is off. The reply uses a strict JSON
  schema. Temperature 0.6, max 8,000 tokens. Chosen by a calibration run (30 requests, $0.31). A deeper option,
  `nvidia/Nemotron-3-Ultra-550b-a55b`, is documented but is not the default. Settings are in `experiments/forge_loop/model_config.json`.
- **Evidence pack:** about 6 KB or less. It holds the body and derived values, the challenge spec, the outcome counts,
  up to 6 seeds (worst, median, best), a physics summary, up to 5 earlier rounds, and the bounds of each editable parameter.
  A citation must resolve to a single number. A list or a dict is rejected.
- **Reply:** 1 to 3 hypotheses, each with cited evidence and competing explanations. 1 to 3 proposals, each with
  edits, a category, a predicted change, a confidence and a verification plan.
- **Edit rules:** at most 4 edits. Each parameter is on a whitelist. Morphology and actuation changes must be a ratio
  between 0.5 and 1.5. Control changes must move by at most 0.25. The result must stay inside the mode's bounds.
  Every rejection names the parameter and the rule it broke.
- **Diagnostic probes (M6):** before proposing, the model may request up to 3 probes from a fixed catalogue of 8
  (seven counterfactual changes plus a no-push baseline). Examples are foot length x1.5, torque x1.5, friction x2 and neutral start. Each probe runs on its own
  probe seeds. Its expected direction is checked by code, and the probe is reported CONFIRMED or REFUTED. The model
  then proposes, citing the measured probe results.
- **Repair:** if the reply cannot be parsed or fails the schema, one repair call is made with the validator's error list.
  There are no other retries.
- **Ledger caps:** 1,500 requests and $15.00 in total, and 4 requests and 80,000 tokens per investigation. A call is refused
  before it is sent if its worst-case cost would exceed a cap.
- **Live gate:** real calls need `CREATURE_FORGE_ENABLE_LIVE=1` and `NEBIUS_API_KEY`. Without them only the scripted
  mock runs.

## Counterfactual Arena and verdict

| Arm | What it is |
|---|---|
| `original` | The creature as drawn or as the current version |
| `ai:Pn` | Nemotron proposal `Pn`, after validation |
| `random:Pn` | Matched-random twin of `Pn`: the same number of edits, the same kind and size, a random sign. Seeded from the investigation and proposal IDs. |
| `heuristic` | A fixed rule table (for example, a fall on push raises foot length by 30%). Labelled non-AI everywhere. |

**Protocol.** Every arm is screened on the screen seeds. Screening only selects. The arena then picks the best AI arm and
the best baseline by median screening score. Validation runs on separate seeds and decides. The original is always
validated. The selected AI arm is always validated beside its own twin. If a walk proposal asks for controller retuning,
every arm gets the same retune budget and noise seed.

**`verdict_v1`.** A one-sided exact sign test on paired scores (candidate minus original, same seed).

| Setting | Value (frozen in code) |
|---|---|
| Test threshold (alpha) | 0.05 |
| Non-tied pairs needed | 6 (pairs within one score step are ties) |
| Minimum effect, push | 3 N and 10% of the original median (both) |
| Minimum effect, stand | 0.5 s |
| Minimum effect, walk | 0.5 m |

| Status | Meaning |
|---|---|
| VERIFIED_IMPROVEMENT | Candidate is better on held-out validation seeds, with a median gain of at least the minimum effect |
| NOT_VERIFIED | Enough pairs, but neither direction reaches the threshold with the minimum effect |
| WORSE | The mirrored test reaches the threshold in the other direction |
| INCONCLUSIVE | Fewer than 6 non-tied pairs, or a seed could not be scored |

**Why every AI verdict is shown beside its twin.** The null pilot ran the same comparisons with the original against itself.
It found 0 false alarms in 48 comparisons from seed noise. Random edits are a different matter. On standing creatures,
about 15% of random push edits were VERIFIED (4 of 26), and 35% were WORSE. So one VERIFIED arm does not show that the model
has skill. It shows only that the change helped on held-out seeds. The skill question is answered by the pre-registered
comparison of AI arms against their twins, which is the scoreboard.

## Evolve

- **Versions:** each creature keeps numbered versions (`n = 1, 2, ...`), each with its parent, a content hash, its origin
  (`user` or `ai_accepted`) and, for a change, the edits, category, rationale, source (`nemotron`, `random_baseline` or
  `heuristic`), investigation ID, arm ID and verdict.
- **Accept:** `POST /api/forge/creatures/{cid}/accept` creates a new version. It is refused with a 409 unless the arm's
  verdict is VERIFIED_IMPROVEMENT. The store enforces the same rule.
- **Revert:** setting the current version to an earlier `n` is allowed. Nothing is deleted.
- **Bounded loop:** up to 3 rounds, 3,000 rollouts, 8 model calls and 600 s of wall time. It stops early after two rounds
  without improvement. From round 2 on, the proposed body of the best verified AI arm is used as a hypothetical parent,
  and the record says so. Such an arm can be accepted only after that parent exists as a version. **The loop never accepts.**

## Provenance labels

| Label | Meaning |
|---|---|
| LIVE | The reply came from the real Nemotron endpoint. Recorded with request ID, usage and cost. |
| SCRIPTED_MOCK | The reply came from a fixture. It is labelled in the record and the UI, is never promoted to LIVE and is never used in a scoreboard. |
| Archived records | Unedited live records in `experiments/forge_loop/dev_live_records/`, each with a SHA-256 in `INDEX.json`. They are development runs, not an experiment. |

Arms carry their own source label (`nemotron`, `random_baseline`, `heuristic`, or `scripted_mock`).

## Running it

**Local (no API key needed):**

```sh
python scripts/run_studio.py          # then open http://127.0.0.1:8000 and use the "My creature" tab
```

Only the scripted mock runs unless live mode is enabled. To enable live mode locally, put `NEBIUS_API_KEY` in a git-ignored
`.env` and set `CREATURE_FORGE_ENABLE_LIVE=1`.

**On the Nebius VM (live):**

```sh
python infra/nebius/forge_cloud.py start                      # start the VM
python infra/nebius/forge_dev.py serve --slot integ --live    # run the Studio on the VM
python infra/nebius/forge_dev.py tunnel                       # then open http://127.0.0.1:8765
python infra/nebius/forge_cloud.py stop                       # stop the VM when finished
```

The VM bills while it runs. Stop it when you are done.

**Scripts:**

```sh
python scripts/forge_acceptance.py --base http://127.0.0.1:8000 --starter balanced --kind push --mode scripted
python scripts/forge_run_loop.py --cid <cid> --n <version> --run-id <run_id> --mode live
```

`forge_acceptance.py` runs draw, challenge, investigate, verdict and accept-if-verified over HTTP. It writes a report under
`artifacts/forge/acceptance/`. `forge_run_loop.py` runs a bounded loop and prints each round. Neither script accepts a
design that is not verified.

## Honest status and limitations

**Implemented:** challenges (stand, push, walk); evidence pack and strict reply schema; edit validation; probes; the matched-random
twin, heuristic and arena; `verdict_v1`; the investigation record; the bounded loop; versions, accept and revert; the
ledger caps; the scripted mock; the VM workflow.

**Results so far:**

- Calibration (2026-10-14): 4 of 4 valid replies for the chosen setting. This measured the output format. It did not measure redesign quality.
- Development records (2026-10-15): most investigations ended NOT_VERIFIED or INCONCLUSIVE. Three records on one balanced
  creature (push) reached VERIFIED_IMPROVEMENT on 12 held-out seeds each: `i-f9873480e42a` (before probes), and
  `i-47bc91e407c2` and `i-172b6a48a0ad` (with probes, rounds 1 and 3 of one loop). Those are worked cases on one creature and one
  challenge. They are not statistics, and they are not a claim that the model is better than random edits.
- Pre-registered scoreboard (`experiments/forge_loop/scoreboard/REPORT.md`): 6 starter and challenge cells, 2 replicates each.
  AI arm verified 6/12, its matched-random twin 1/12, discordant 5 vs 0, exact one-sided McNemar p = 0.031. Five of the six AI
  verifications were push; on creatures that cannot stand the AI verified once and its twin did better. Small study, one zoo,
  and the push cells share a creature family with development; read the report's limits before quoting it.

**Limitations:**

- One planar biped in simulation. One controller family. One platform for the zoo pilot (Linux VM).
- Few seeds per cell. The verdict is a consistency filter on held-out seeds, not a sampling-uncertainty estimate.
- Stand and push scores are nearly deterministic across seeds, so small differences can be ties.
- Walking adaptation helps only creatures that cannot walk at first. On creatures that already walk it overfits the training seeds.
- Live development records were produced while the pipeline was changing. They must not be pooled into one statistic.
- The Nemotron calibration used one frozen context (one creature, one challenge).

## File map

| Area | File |
|---|---|
| Contracts | `docs/FORGE_LOOP_CONTRACTS.md` |
| Challenges and walking | `creature_forge/challenges.py`, `creature_forge/creature_walk.py`, `creature_forge/forge_pool.py` |
| Evidence and edits | `creature_forge/evidence.py`, `creature_forge/interventions.py` |
| Model side | `creature_forge/forge_ai.py`, `creature_forge/inference_ledger.py` |
| Probes | `creature_forge/probes.py` |
| Arena and verdict | `creature_forge/arena.py`, `creature_forge/baselines.py`, `creature_forge/verdict.py` |
| Investigation and loop | `creature_forge/investigation.py`, `creature_forge/jobs.py` |
| Creatures and versions | `creature_forge/creatures.py` |
| HTTP API | `creature_forge/studio/forge_api.py` (`/api/forge/*`) |
| Scripts | `scripts/forge_acceptance.py`, `scripts/forge_run_loop.py`, `scripts/forge_calibrate.py`, `scripts/forge_null_pilot.py`, `scripts/forge_zoo_pilot.py`, `scripts/forge_scoreboard.py` |
| VM | `infra/nebius/forge_cloud.py`, `infra/nebius/forge_dev.py` |
| Records | `experiments/forge_loop/` (calibration, pilot, null_pilot, dev_live_records, scoreboard, `model_config.json`) |
| Physics rules | `.claude/skills/physics-integrity/SKILL.md` |
