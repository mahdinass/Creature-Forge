# Audit of dev pilot1: why the closed-loop scientist failed (2026-10-17)

**Scope.**
- Data: 13 dev fault-bench instances × 6 policies, budget about 700 rollouts each.
- Model: `nvidia/nemotron-3-super-120b-a12b`, thinking off.
- Records: `artifacts/vm/ce2/ce/pilot1_shard*.jsonl`. Instances: `artifacts/vm/ce/ce/dev_shard*.jsonl`.
- This is development evidence only. No held-out instance was used.
- Method: every scientist trace was read (the user messages the model saw, its raw replies, validator errors, hypothesis and
  experiment ledgers). The tools and the benchmark were checked before the model was blamed.

Headline (from `ce_analysis.py`):

| policy | FULL / PARTIAL / NOT | mean rollouts | chose a repairing tool |
|---|---|---|---|
| exhaustive | 5 / 6 / 2 | 684 | 11/13 |
| scientist | 3 / 2 / 8 | 425 | 4/13 |

Diagnosis matched the injected label in 1/13. Prediction accuracy was 0.38 (n = 71).

## Findings, by cause

### F1. The pipeline ended 5 of 13 investigations before any physics was done (the "unused budget")
- Five episodes ended with `consecutive_invalid` after 4 rollouts. Two steps in a row stayed invalid after the repair call.
- Causes:
  - (a) placeholder status updates with id `"(none)"`;
  - (b) two counterfactuals in one action, which the pilot's code rejected;
  - (c) 9 evidence citations against a cap of 6.
- Across all scientist steps, 29 of 55 first replies were invalid (53%).
- The pilot ran on code from before `3a2187a`, which already allows one or two counterfactuals and drops placeholders. Its
  messages say "requests 5 of 16", where the current cap is 24. (b) and part of (a) are therefore already addressed; (c) and
  the high first-reply error rate are not.
- **This is the main cause of the "40% unused budget".** In the 8 episodes that ran, the budget was spent (680–696 of 700).
- **Consequence:** this is not evidence about physical reasoning; it is an interface defect. Fixed in v2 (§ changes).

### F2. Hypotheses were frozen after step 1 and never revised
- 0 status updates in all 8 completed investigations. No new hypothesis was proposed after step 1 in any episode; every
  episode kept exactly H1 and H2.
- The model kept testing and repairing on behalf of hypotheses whose predictions had just failed.
- Example: `tiny-feet:feedback_loss`.
  - E1 `torque_limit_x1.6` changed **no quantity at all**: saturation was 0, so the torque limit never binds and the
    trajectories were identical. All three H1 predictions were scored INCORRECT.
  - The model then spent 53% of the remaining budget on a `torque_limit` repair for H1.
  - It concluded "insufficient torque authority is not the cause" only in its final explanation.
- **Cause (interface, not only the model):**
  - Status updates were optional and appear late in the schema.
  - The `action` field comes first, and with thinking off and constrained decoding the model commits to an action before it
    writes anything about the evidence.
  - Nothing asked the model to interpret the last result.
- **v2:** the reply starts with a written reading of the newest result, then a verdict for every hypothesis whose predictions
  were scored, then any new hypotheses, and only then the action.

### F3. The evidence lacked a healthy comparison, and signs were misread
- The model sees 58 absolute quantities but no reference for what a healthy walker shows on the same instruments. Example
  (`tiny-feet:feedback_loss`):
  - 4.95 touchdowns/s, step length 0.09 L and swing clearance ≈ 0 indicate shuffling;
  - the robot falls backward (`fall_direction = -1`, pitch_end −0.75 rad, com_vx_end −0.85 m/s).
  - The model never cited cadence or step length, and its H2 speaks of "forward lean ... forward falls".
- In 2 of 13 episodes (both in each scientist arm), a hypothesis described the opposite fall direction to the one observed.
- The system prompt said "Experiments are expensive: every rollout spent on experiments is not available for repair." In
  fact a counterfactual costs 4 rollouts (0.6% of the budget) against 52–100 for the cheapest repair. The completed episodes
  ran only 1–4 of about 8 available counterfactuals before putting up to 100% of the remaining budget into a repair. **This
  sentence was a bias we introduced.**
- **v2:**
  - A KEY FACTS block of computed physics, with signs spelled out in words: fall direction, time, commanded vs measured
    cadence, cadence relative to the pendulum frequency √(g/L), Froude number, step length / L, saturation, slip, clearance.
  - A HEALTHY REFERENCE column: a fixed healthy walker observed once on the same instruments; laboratory knowledge, not
    information about this robot.
  - Neutral, exact cost statements.
  These are measurements and calculations. None of them names a cause.

### F4. The experiment catalogue limited what could be tested
- Nine fixed changes, each in one direction only:
  - `pitch_ref_-0.08` only, so a backward-falling robot cannot test leaning more forward;
  - placement gains set to 0.5, so it cannot test "more placement feedback";
  - no stride, duty, knee or damping probes.
- `placement_gains_0.5` *sets* the gains. For a placement-loss robot this counterfactual is itself the repair (4/4 walking in
  the exhaustive runs).
- **v2:** parametric counterfactuals. The model chooses one or two parameters and a signed level from a bounded grid
  (values outside the bounds are refused, never clipped). Two-parameter counterfactuals allow interaction tests. The old
  catalogue stays for the non-AI policies, so the exhaustive baseline is unchanged.

### F5. The benchmark often does not identify a single cause (scoring issue)
- Repair matrices:
  - 7 of 13 pilot instances are repaired by 3–7 different tools; for example, `heavy_torso` on stilts is repaired by
    feedback, leg length, placement, posture, timing and torso mass.
  - For such robots any stabilising change works, so "diagnosis = injected label" is ill-posed.
  - Only the cadence and feedback faults were specific: exactly one repairing tool.
- **Evaluation change (development metric; the held-out analysis will be registered):**
  - diagnosis is also scored as *repair-consistent*, i.e. the diagnosed mechanism maps to a tool that repairs the robot;
  - instances are stratified into *specific* (≤ 2 repairing tools) and *over-determined* (≥ 3);
  - injected-label match stays reported.
- **Identifiability check:** with systematic counterfactuals (the exhaustive policy) the first-ranked change belonged to a
  repairing tool in 9/13 instances. The available evidence is therefore usually sufficient. The scientist's failure lies in
  which experiments it chose and how it read them, as well as in F1.
- Feedback faults are weakly identifiable: `feedback_gains_x2` never restored walking, and it ranked 2nd–4th by upright time.

### F6. Mechanism-to-repair links
- When the scientist did form a correct supported idea, it chose a consistent repair. On `stilts:heavy_torso`, E2
  `pitch_ref_-0.08` raised walking from 0 to 3 of 4, then it chose a posture repair and reached 0.62 validation walking.
- Wrong repairs came from F2 (refuted hypotheses not dropped) and F3 (misreadings), not from a broken mechanism-to-tool
  vocabulary.
- 1 of 15 repairs cited a hypothesis whose scored predictions had all failed.

### F7. Prediction scoring
- Most incorrect predictions were "increase/decrease" where the observed change was within tolerance (no_change). The
  scoring is sound but strict.
- Several predictions named `pre_fall.*` quantities that become undefined when the intervention prevents a fall, so they
  were unscored.
- **v2:** the docs say this explicitly. No scoring rule changes.

## What was not the problem
- **API errors:** none; 0 model failures.
- **Budget accounting:** the ledger totals match.
- **Counterfactual matching:** same observation seeds, deterministic. A null counterfactual reproduced the baseline exactly
  (E1 above, all deltas 0.0).
- **Verification:** independent and unchanged.

## Planned changes (scientist v2, `causal_scientist_v2`; v1 is kept in git at `4d286e5` with its records)
1. Reasoning-first reply order:
   - `result_reading`, a required text;
   - then `status_updates`, required for every hypothesis that was scored in the newest experiments (keeping it `open` is
     allowed);
   - then `new_hypotheses`;
   - then `action`.
2. The KEY FACTS digest and the healthy-reference column (F3).
3. Neutral cost statements (F3).
4. Parametric, bidirectional, one- or two-parameter counterfactuals (F4).
5. Interface fixes:
   - citation cap 6 → 12;
   - per-hypothesis prediction record shown in the ledger;
   - a clearer first-step instruction.
6. Evaluation:
   - repair-consistent diagnosis;
   - specific vs over-determined strata;
   - first-reply validity rate;
   - status-update and new-hypothesis counts as process metrics.

Hard rules unchanged:
- the model never sees the fault, severity, repair matrix or verification seeds;
- no rule makes a decision for the model;
- verification is independent.
