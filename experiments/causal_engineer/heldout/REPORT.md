# Held-out evaluation ce-heldout-eval-v1: report on the registered run

**Bottom line.** The registered run completed. An authentication outage invalidated the AI arms. The non-AI arms are valid,
and their one pre-registered test (C5a, learned vs exhaustive) is a clear negative result. **No claim about the Nemotron
scientist can be made from this run.**

## What happened
- **Launch:** 2026-10-17 20:12 UTC on the main VM: 40 registered instances (22 unseen bases) × 8 arms = 320 episodes, protocol
  frozen at commit `5ca165c` (`c4c2c87`).
- **Outage:** at 21:02 UTC the owner rotated the Nebius Token Factory API key. The operator (Claude) had recommended the
  rotation an hour earlier, after a separate key-handling incident (`docs/memory/INCIDENTS.md`), without saying it should wait
  until the run ended.
- **Effect:** the last successful model request was at 21:03:50 UTC. Every later request returned `HTTP 401 Couldn't
  authenticate`.
- **Behaviour of the run:**
  - the AI episodes kept running, and each one ended after two failed steps (`consecutive_invalid`), with the bench's unrepaired
    design submitted, as the registered rules prescribe;
  - the non-AI arms make no model calls and were unaffected;
  - all 320 episodes were written and their SHA-256 values verified (`results/heldout_eval.sha256`).

AI episodes with no authentication failure (the ones that ran before the rotation; not a random sample):

| arm | episodes without a 401 | of which FULL_RECOVERY |
|---|---|---|
| `scientist_think` | 6 / 40 | 2 |
| `scientist_1shot_think` | 15 / 40 | 2 |
| `scientist_think_mem` | 4 / 40 | 1 |
| `scientist_think_mem_learned` | 6 / 40 | 1 |

## Registered analysis (run once, `results/ANALYSIS_OUTPUT.md`, `results/analysis.json`)

| arm | FULL | PARTIAL | NOT | mean walking | rollouts used | chose a repairing tool |
|---|---|---|---|---|---|---|
| exhaustive (non-AI) | **23** | 7 | 10 | 0.85 | 689 | 38/40 |
| learned (non-AI, Level C ranking) | **18** | 13 | 9 | 0.83 | 688 | 37/40 |
| random (non-AI) | 12 | 10 | 18 | 0.62 | 690 | 28/40 |
| expert rules (non-AI) | 6 | 19 | 15 | 0.61 | 690 | 31/40 |
| `scientist_1shot_think` | 2* | 9 | 29 | 0.26 | 137 | 12/40 |
| `scientist_think` | 2* | 2 | 36 | 0.15 | 62 | 7/40 |
| `scientist_think_mem` | 2* | 2 | 36 | 0.10 | 69 | 6/40 |
| `scientist_think_mem_learned` | 2* | 5 | 33 | 0.15 | 75 | 7/40 |

\* Dominated by the authentication outage: most of these episodes made no successful model call.

| test | result by the registered rule | interpretable? |
|---|---|---|
| C1 prediction accuracy > majority baseline | 3 above / 4 below, p = 0.77 | no (7 usable episodes, all before the outage) |
| C2 closed loop > one-shot | 2 / 2, p = 0.69 | **no** (outage) |
| C3 scientist > exhaustive | 0 / 21, p = 1.00 | **no** (outage) |
| C4 memory > no memory | 1 / 1, p = 0.75 | **no** (outage) |
| C5a learned ranking > exhaustive ranking | **1 / 6, p = 0.99, not supported** | **yes**: no model calls involved |
| C5b memory + learned advice > memory | 2 / 2, p = 0.69 | **no** (outage) |

No null hypothesis was rejected.

## Valid findings
1. **The strong fixed procedure transfers to unseen robots.**
   - Exhaustive counterfactual screening plus two maximal repairs fully recovered 23 of 40 robots on 22 morphologies never
     used in development (dev pilot3: 9/16).
   - Random tool choice with the same budget recovered 12/40, so the choice of experiments and tools matters.
   - Hand-written telemetry rules recovered only 6/40.
2. **Level C did not translate into better repairs (C5a negative).**
   - Replacing the fixed ranking with the trained repair-effect predictor (dev leave-one-base-out top-1 0.66 vs 0.59) gave
     18 vs 23 FULL recoveries on held-out robots: 1 instance favoured the learned ranking and 6 the fixed one.
   - A better tool *ranking* on development metrics did not produce better verified outcomes on unseen morphologies. This is
     the same pattern as the S2/L2 experience results.
   - The likely causes: two repairs at about 340 rollouts each make the second-ranked tool almost as good as the first, and
     the learned model was trained on 12 dev bases.
3. **Cost.**
   - Real inference spend for the run was $2.36.
   - The ledger also holds $7.42 of worst-case settlements for calls that failed authentication (conservative accounting:
     nothing was billed for them).
   - VM about 3 h on the 8-vCPU machine.

## What is not known from this run
Whether the v2.3 closed-loop scientist, its memory or its learned advice beat the one-shot scientist or the fixed procedure
on unseen robots. The development evidence (pilots 2–5) is in `docs/CAUSAL_ENGINEER.md` and is not a substitute.

## Deviation handling and proposed amendment (needs the owner's decision)
- The registered rule (interrupted episodes count as not recovered) was applied as written above, and the result is
  reported, not hidden.
- Proposed **amendment 1**: re-run ONLY the four AI arms on the same 40 instances with the rotated key, with the same frozen
  code, prompts, memory inputs and Level C model (SHA-256 unchanged), as a separately labelled run.
  - This amendment is proposed AFTER this run's results were seen. The six clean pre-outage episodes per arm and the non-AI
    results are known.
  - The amendment run must therefore be reported as a post-hoc repair of an infrastructure failure, next to (never replacing)
    the registered result.
- Fail-fast added before any re-run: the evaluation runner stops an AI shard at the first authentication error, so an outage
  can never again be silently scored as model failures.
- Inference: about $10 real expected. The ledger cap must rise to cover the conservative phantom charges.

## Lessons
- Never rotate credentials during a live, registered run.
- Pre-run checks should include a live, read-only key check, and runners should fail fast on authentication errors.
- Disclosed in `docs/memory/INCIDENTS.md`.
