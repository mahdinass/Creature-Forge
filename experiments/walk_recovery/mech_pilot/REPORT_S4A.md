# S4a: can Nemotron invent control laws that make failing robots walk, and does closing the loop help? (development data)

**Registration.**
- Protocol `protocol_s4a.json` (`walkrec-s4a-mech-pilot-v1`) was committed in `854e698` before any unit.
- The analysis script `scripts/walk_s4_analysis.py` was committed in `7a6bc08` before the results were complete.
- Design: `docs/WALK_RECOVERY_ITERATION3.md`.

**Execution.**
- One execution on the batch VM (slot `s4`, snapshot `4ba1fb9`).
- 144/144 units, 0 unit errors, accounting exact in every unit.
- 24 NEW development creatures (`walkrec-dev2-gen`, 44 draws, all recorded).

**Records.** `results/` (SHA-256 manifest; key scan 0 hits).

**Inference.** 206 calls, $0.52. **Infra:** $17.65 of $35 cumulative.

## Setup
- Every arm starts from the 15-D controller (no foot placement) and gets the same total budget of 3,000 rollouts. All
  investigation, mechanism probes with their diagnostics, plans and screening are charged.
- Final selection uses selection v2 (verdict-aware screening) for every arm.
- Assessment is `full_recovery_v1`, unchanged.

## Results (full recoveries of 24)
| arm | FULL | PARTIAL | NOT | mean validation walking | final plans with body co-design | final plans with mechanisms |
|---|---|---|---|---|---|---|
| **fix15** (no new structure; fixed rule over body / posture / timing) | **11** | 11 | 2 | 0.78 | 24/24 | 0 |
| expert (human swing-foot-placement law in the DSL; reference) | 9 | 12 | 3 | 0.75 | 24/24 | 23 |
| randmech (random DSL mechanisms + fixed rule) | 6 | 16 | 2 | 0.69 | 24/24 | 24 |
| generic (blind linear feedback structure + fixed rule) | 5 | 12 | 7 | 0.54 | — | — |
| ai_1shot (Nemotron invents mechanisms, one round) | 5 | 13 | 6 | 0.55 | 11/24 | 19 |
| **ai_iter** (Nemotron, closed loop, up to 4 rounds with physical feedback) | **4** | 12 | 8 | 0.49 | 14/24 | 18 |

**G4 = FAIL.** ai_iter (4) is far below the best non-AI structure arm, fix15 (11), against the required ≥ 14. Per the
pre-declared rule, mechanism invention does not enter S3, and S4b (the library) is not run.

## What the closed loop did (capability 1: within-investigation adaptation)
- **The loop works mechanically.**
  - ai_iter used 3.0 rounds on average and stopped by its own decision in 23/24 pipelines; it was never forced to continue.
  - It revised 6 mechanisms after measured feedback, and 2/6 revisions improved on the version they replaced.
  - It made 134/145 valid decisions.
- **It did not help.** Iterative vs one-shot, paired: 3 creatures recovered only by the iterative arm, 4 only by the
  one-shot arm. There is no evidence that feedback within an investigation improved the outcome at this budget.
- Nearly every mechanism probe "improved" on the start (82/84), because extra gains plus a short search always add some
  flexibility. That flag was therefore weak evidence for the director to act on.

## What Nemotron invented
- **Mostly redundant structure.** Of 48 mechanisms in ai_iter:
  - 25 were ankle-torque laws on stance (mainly on pitch, pitch rate or phase), which largely duplicate the controller's
    existing ankle-balance and pitch feedback;
  - 13 were hip-torque laws.
- **Almost never the law that mattered in M1.** It proposed the swing-hip-on-d/v (foot-placement-like) structure once in
  48. It favoured stance-phase torque corrections.
- **Stated plainly:** the model did not rediscover foot placement from the diagnostics. Its physical priors pointed at
  balance torques.
- 6/48 mechanisms had all fitted gains near zero. The optimiser found no use for them, and the model saw this.

## Why the AI arms lost (mechanistic, from the records)
1. **The same bias as in S2: body co-design is under-used.** Only 11–14 of 24 AI final plans changed the body, against 24/24
   for every non-AI arm. Throughout this project, body co-design has been the most reliable lever (M1, S2 census, here).
2. **Extra structure dilutes the search.** Every arm that added mechanisms to the final search did worse than fix15:
   expert 9, random 6, generic 5. With 3,000 rollouts, more dimensions cost more than they buy. This holds even for the
   human-designed foot-placement law, which in M1 helped *controller-only* search (ctrl15 1/12 → ctrl17 5/12). Once the body
   is co-designed, the advantage disappears in this panel.
3. **It is not the investigation cost.** The share of budget spent on investigation was similar across arms: 0.21–0.25 for
   fix15 and both AI arms.

## Consequences
- The pre-declared S3 design stands: ai_v2 vs FIX at 2,000 rollouts, family 17, with the shared selection v2 fix approved
  in iteration 3. Mechanism invention and the library are reported as development negatives.
- Capability 2 (library) was not tested: G4 failed, and no AI-invented mechanism was verified as beneficial.
- Capability 3 (trainable learning across experiences) was not pursued. The mechanism-probe outcomes carry almost no
  signal: nearly all "improve" on the start. A learned critic would need a target with variance, such as a mechanism's
  effect on the *final* recovery, which needs many more creatures than the deadline allows.
- Across three AI designs, the evidence is consistent:
  - v1 direction, v2 direction, and v3 mechanism invention, one-shot and closed-loop.
  - A simple engineering rule ("always co-design the body; search posture and timing") beats Nemotron's decisions.
  - Nemotron's physical priors favour controller-centric fixes (timing in S2 v1, stance balance torques here) over
    changing the body.
  - The verified finding for the project is the classical one: with foot placement or body co-design and a strong
    optimiser, most genuinely failing robots can be made to walk.
