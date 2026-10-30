# Devpost submission text (final candidate, 2026-10-27; English; for the owner's review)

Every number below is traceable to a file named in the README table *What was demonstrated* or in
`docs/RESEARCH_STATUS.md`. Paste the sections into the matching Devpost fields.

> **Current status (2026-10-30).** The owner reports that the project was submitted on 2026-10-29:
> <https://devpost.com/software/creature-forge>. This file is the text prepared before submission, kept as a record; the
> Devpost page is authoritative and may differ. Only the repository and video fields below were updated afterwards.

## Form fields
| Field | Value |
|---|---|
| Project name | Creature Forge |
| Tagline (max ~200 characters) | An AI lab for robot failures: NVIDIA Nemotron proposes the diagnosis and the fix, and MuJoCo physics decides whether the fix is real. |
| Track | **Physical AI** (simulation only; no hardware) |
| Repository | `https://github.com/mahdinass/Creature-Forge` |
| Demo URL | Not required for Physical AI. Optional: the repository README quick start |
| Video | `https://youtu.be/hPY-_cK5Oow` |
| Built with | python, mujoco, numpy, fastapi, react, three.js, react-three-fiber, typescript, vite, nvidia-nemotron, nebius-token-factory, nebius-ai-cloud |
| New or existing project | New: the repository's first commit is 2026-10-13, inside the submission period (which began 2026-08-26) |

## Inspiration
When a robot falls over, trying another design is easy; finding out *why* it fell is hard. Large language models are good
at producing plausible physical explanations, but plausible is not the same as true. In our very first live trial the
model blamed torso inertia and proposed a lighter torso. It sounded right. MuJoCo showed the robot still fell on every
seed. We wanted to build an AI collaborator for physical engineering whose every suggestion is treated as a hypothesis
and tested by physics before anyone believes it.

## What it does
Creature Forge is a simulation laboratory for two-legged robots, with a browser Studio.
- **Draw a robot** in the Studio, or start from a damaged one.
- **Challenge it in MuJoCo**: standing, push recovery or walking, on fixed seeds. The failure is measured, not described.
- **Investigate with AI.** NVIDIA Nemotron 3 Super, called live through Nebius Token Factory, reads an evidence pack of
  measurements. It writes hypotheses that must cite real evidence, may request up to three diagnostic experiments with
  stated expectations, and proposes bounded physical edits.
- **Verify.** Deterministic code rejects invalid or out-of-bounds proposals (never clipping them). MuJoCo tests the rest on
  seeds the model never saw, beside a random edit of the same size. A fixed rule, not the model, decides
  VERIFIED_IMPROVEMENT, NOT_VERIFIED, INCONCLUSIVE or WORSE.
- **Evolve.** Only a verified change can be accepted as the robot's next version.

Two recorded pages show the deeper research systems:
- **Nemotron's experiment**: a "Hypothesis-as-Simulation" scientist investigates a robot with a hidden fault. From the same
  evidence, Nemotron and our deterministic engine choose different experiments; Nemotron's choice moved the belief to the
  correct fault and its repair fully recovered the robot (23/24), while the engine's partly did (20/24).
- **Verified repair** (no AI): two optimiser repairs of a robot on a slippery floor, judged by a strict full-recovery
  verifier, to show what "verified" means.

## How we built it
- **Nemotron on Nebius Token Factory.** `nvidia/nemotron-3-super-120b-a12b` with thinking off and strict JSON-schema guided
  decoding, chosen by a 30-request calibration against Nano and Ultra. Hypothesis ids, editable parameters and every
  citable evidence path are enumerated in the schema, so identifiers are valid by construction.
- **Guard rails.** One client (`creature_forge/nebius.py`) enforces request, token and dollar caps with no blind retries
  and never logs the key. Every call's request id, tokens and cost go to an inference ledger.
- **Physics and judgement.** MuJoCo 3.15 with role-separated, hashed seeds; an arena of AI, matched-random and heuristic
  arms; fixed verdict rules (`verdict_v1`, `full_recovery_v1`); a Bayesian belief engine and CMA-ES optimiser for the
  scientist studies.
- **Nebius AI Cloud.** All heavy MuJoCo batch studies ran on Nebius Compute VMs (8 and 64 vCPUs), driven by our own
  start, stop, sync and watchdog tooling with a spend cap, deadlines and service-account API stops.
- **Studio.** FastAPI backend and a React + three.js frontend with synchronized multi-robot replays. Recorded pages play
  back hash-pinned files that were reproduced row by row from the experimental records before export.
- **Scientific hygiene.** Pre-registered protocols pushed before data, frozen record manifests, reproduction gates,
  matched baselines and intention-to-treat reporting. About 1,600 Python tests, frontend tests and real-browser checks
  run in CI.

## Challenges we ran into
- **Hidden reasoning ate the answer.** An early Nemotron Nano setup returned HTTP 200 with empty content because reasoning
  consumed the token budget. We calibrated reasoning controls per model and moved to Super with thinking off.
- **Our own schema was the first failure.** With identifiers left to the prompt, 0 of 12 replies were machine-valid;
  enumerating them in the JSON schema brought the chosen setup to 6 of 6.
- **Random edits are a strong baseline.** A single verified AI edit says little until it stands next to its matched random
  twin, so every validation includes one.
- **Exact replay across platforms.** Windows does not reproduce Linux physics bit for bit, so demo exports are produced on
  the recorded Linux environment and checked row by row.
- **Cloud operations.** A guest power-off does not keep a Nebius VM stopped, and the CLI login is a fixed ~12 h token. We
  moved to API stops with a narrowly scoped service account.

## Accomplishments that we're proud of
- **A working, honest loop.** Live runs go from a drawn robot to a physics-verified, accepted redesign. In one recorded
  live run a robot fell short of a 15 N push target on 8 of 8 seeds; Nemotron proposed longer feet (× 1.35), which
  verified 12 wins to 0 on held-out seeds while the matched random edit was inconclusive, and the new version passed 8 of
  8. Every live attempt is listed, including the two walking attempts that did not verify.
- **A pre-registered result for the AI:** Nemotron-selected redesigns verified in 6 of 12 investigations versus 1 of 12
  for size-matched random edits (p = 0.031), mostly on push challenges.
- **Strong non-AI engineering, attributed as such:** a fixed procedure fully recovered walking in 19 of 48 fresh robots in
  a confirmatory study.
- **A registered held-out test on 160 robots with unseen damage** (no AI). The diagnosis engine recovered 56 versus 46 for
  exhaustive search, an inconclusive primary (p = 0.061); removing diagnosis dropped it to 42, supportive evidence that
  diagnosis carries the advantage.
- **Negative results are published, not dropped.**

## What we learned
- On identical evidence, a model can choose a better *question* than an engine whose information estimates are tied. That
  is where Nemotron helped. It did not out-decide the engine on average (parity, 15 versus 14 of 36), and as a
  walking-recovery director it did worse than a fixed rule (9 versus 19 of 48).
- Held-out tests are humbling: a +22-point development advantage became +6 points on unseen robots.
- Before a system can learn from verified outcomes, the outcomes must be repeatable. Single-panel success labels flipped
  between independent seed panels on a sizeable share of cases.

## What's next
- **Learning from experience**, which we have **not** demonstrated: every direct test so far was null, failed its gate or
  was not evaluable. The next step is repeatable, margin-based verification targets, then a matched test of experience
  against the same engine without memory.
- Richer bodies and 3-D robots, and running the batch studies as Nebius Serverless Jobs.
- Applications: a verification layer for AI-assisted design of legged robots, mechanisms and controllers, where every
  suggestion arrives with physical evidence before it reaches hardware.

## How we used NVIDIA and Nebius (for judges)
1. **Runtime inference (Token Factory).** The Studio's *My creature → Investigate with AI* calls Nemotron 3 Super live
   when a key is configured; each call is logged with its request id. The recorded *Nemotron's experiment* and *AI
   scientist* pages play back real Token Factory calls made by our batch scientist, with request ids shown. About 5,600
   requests appear in our local ledger copies up to 2026-10-20. Ultra was used in calibration and Nano in the first
   prototype.
2. **Compute (AI Cloud).** Batch MuJoCo studies ran on Nebius Compute VMs. We did not use Serverless Jobs, Serverless
   Endpoints or DevPods.
3. **What Token Factory accelerated.** Strict JSON-schema guided decoding made structured, citable proposals practical, and
   low latency (about 3 to 5 s per Forge Loop call in our records) kept an interactive investigation to a few minutes,
   most of it physics.

## Testing instructions
No key or cloud is needed. Clone the repository, then follow `docs/submission/JUDGE_TESTING.md` (Python 3.11+, Node 22+;
about 10 minutes). Open `?tab=nemotron` and `?tab=recovery` for the recorded results, and *Create → Draw → My creature*
for the live MuJoCo loop. Without a key the AI step is a clearly labelled scripted mock; with your own Nebius Token
Factory key (`NEBIUS_API_KEY` and `CREATURE_FORGE_ENABLE_LIVE=1` in `.env`) it calls Nemotron live, at fractions of a cent
per call.

## Attribution and independence
Independent hackathon project; not endorsed by NVIDIA or Nebius. Apache-2.0. Third-party licences are in
`THIRD_PARTY_NOTICES.md`, model and service terms in `docs/MODEL_AND_SERVICE_TERMS.md`. Code was written with an AI
coding assistant; those commits carry a `Co-Authored-By` disclosure.
