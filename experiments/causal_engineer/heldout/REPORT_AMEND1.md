# Held-out evaluation, amendment 1: AI arms re-run (post-hoc, owner-approved)

**Scope.**
- Instances: 40 registered instances on 22 base robots never used in development; 7 fault types, severity 0.5 / 1.0.
- What ran: the four AI arms, re-run with the rotated key, with the same frozen inputs as `protocol.json` (`AMENDMENT_1.md`).
- Non-AI arms: the registered results, unchanged.
- One analysis run (`results_amend1/ANALYSIS_OUTPUT.md`, `analysis.json`).
- No authentication error occurred; all 160 episodes completed with checksums.
- **Post-hoc labelling:** this run was decided after the registered run's results were known. It repairs an infrastructure
  failure and is reported next to the registered result in `REPORT.md`, which it does not replace.

## Outcomes (FULL_RECOVERY = full_recovery_v1: ≥ 80% of 24 hidden 10 s seeds walking, verified improvement, 20 s confirmation)

| arm | decides | FULL | PARTIAL | NOT | mean walking | rollouts used | chose a repairing tool | first repair repairs | LLM $ |
|---|---|---|---|---|---|---|---|---|---|
| exhaustive | fixed procedure | **23** | 7 | 10 | 0.85 | 689 | 38/40 | 36/40 | 0 |
| learned | Level C ranking | 18 | 13 | 9 | 0.83 | 688 | 37/40 | 33/40 | 0 |
| `scientist_think_mem` | Nemotron, closed loop, memory | **16** | 14 | 10 | 0.74 | 359 | 35/40 | 29/40 | 4.23 |
| `scientist_think` | Nemotron, closed loop | 14 | 12 | 14 | 0.69 | 317 | 34/40 | 23/40 | 3.70 |
| `scientist_think_mem_learned` | Nemotron + memory + Level C advice | 14 | 16 | 10 | 0.75 | 362 | 34/40 | 26/40 | 4.17 |
| random | random choices | 12 | 10 | 18 | 0.62 | 690 | 28/40 | 17/40 | 0 |
| `scientist_1shot_think` | Nemotron, one call, no feedback | 8 | 17 | 15 | 0.60 | 381 | 30/40 | 21/40 | 0.29 |
| expert | hand-written rules | 6 | 19 | 15 | 0.61 | 690 | 31/40 | 22/40 | 0 |

## Registered hypotheses (one-sided exact McNemar on FULL; Holm over six; α = 0.05)

| test | result | p | supported |
|---|---|---|---|
| C1 prediction accuracy > majority-direction baseline | 14 episodes above / 23 below | 0.95 | **no** |
| C2 closed loop > one-shot | 14 vs 8 FULL; 10 / 4 discordant | 0.090 | **no** (directionally favourable, not significant) |
| C3 closed loop > exhaustive | 14 vs 23 FULL; 2 / 11 discordant | 0.998 | **no**: the fixed procedure is better (walking fraction 0.69 vs 0.85, Wilcoxon p = 0.001, two-sided, secondary) |
| C4 memory > no memory | 16 vs 14 FULL; 6 / 4 | 0.38 | **no** |
| C5a learned ranking > exhaustive ranking (registered run) | 18 vs 23; 1 / 6 | 0.99 | **no** |
| C5b memory + learned advice > memory | 14 vs 16; 5 / 7 | 0.81 | **no** |

**No hypothesis is supported.**

## Secondary and descriptive findings (no claims beyond the tests above)

- **Iteration helps descriptively.**
  - The closed-loop scientist recovered 14 against the one-shot scientist's 8 (10 vs 4 discordant).
  - It chose a repairing tool in 34/40 against 30/40.
  - Feedback is therefore probably useful, but N = 40 cannot establish it after correction.
- **Nemotron directing the tools ranks between random and the strong fixed procedure.** Recovery: exhaustive 23, scientist
  14–16, random 12, expert rules 6.
- **Decision quality is not the gap. Budget use is.**
  - The scientist arms choose a repairing tool about as often as the fixed procedure (34–35/40 vs 38/40).
  - They spend only 317–362 of 700 rollouts, against 689. This is the failure mode found in development and only partly
    fixed by v2.2/v2.3.
- **Diagnosis:**
  - Injected-label match: 11/34 for the closed loop, 9/40 for the one-shot.
  - Repair-consistent (the diagnosed mechanism maps to a tool that repairs the robot): 19/34 vs 22/40.
  - On *specific* instances (≤ 2 repairing tools): closed loop 7/12, one-shot 4/14.
- **Predictions:**
  - Closed-loop prediction accuracy is 438/1178 = 0.37, against a chance level of 0.33 for three directions.
  - It is below the per-episode majority baseline in 23 of 37 episodes. Most measured changes stay within tolerance, and the
    model predicts changes.
  - Status updates: 369 in the closed-loop arm. The process of revising hypotheses runs; its predictions are not well
    calibrated.
- **Memory (applicability judgements on unseen robots):**
  - Verdicts on 117 retrieved items: applies 33, does_not_apply 38, needs_adaptation 44, test_first 2.
  - Negative transfer (an "applies" item's best tool repaired first and failed while another tool would have worked): 1
    episode. Memory followed and correct: 3.
  - Memory neither clearly helped nor clearly hurt.
- **Level C advice:**
  - Its top-1 tool repairs the robot in 31/40 instances.
  - The scientist marked the advice "applies" 36 times but used its top tool as the first repair only 9 times (8 of those
    repaired).
  - The advice was accurate and mostly not acted on.
  - A strategy that simply follows it is the `learned` arm, which recovered 18; that is not better than the fixed ranking.

## Cost
- Inference, real: $12.39 (1,978 requests) for the amendment; $2.36 for the registered run.
- VM: about 5 h on the 8-vCPU machine across both runs.

## What Nemotron contributes (held-out evidence)
- It runs a genuine experiment–revise–repair loop on unseen robots:
  - 369 hypothesis status updates and many refutations;
  - experiments it designed itself;
  - its own applicability judgements on retrieved experience.
- With the same tools and budget, its decisions recover more robots than random choices or hand-written rules.
- They recover fewer than a systematic screen-everything procedure, chiefly because it stops early instead of spending its
  budget on robustness.
- Experience (memory) and learned advice did not measurably improve it.
- These are the results of one registered evaluation of 40 robots; the confidence intervals are wide.
