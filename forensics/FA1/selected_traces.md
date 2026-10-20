# FA-1 selected trace excerpts (11)

These were selected after the quantitative screening, and each one tests a specific claim in `FA1_REPORT.md`. References are
repo-relative `path#L<line>` (1-based JSONL line). `python -I scripts/fa1_trace.py <path> <line>` reprints each one.
Notation: dx = leading modelled explanation (mass). r8/r16 = plant robustness walking on 8/16 robust seeds. val = validation
walking fraction (24 seeds; PASS needs ≥ 20). disp = median paired forward displacement, candidate − faulty, on robust seeds.

---

### T1 Correct compound diagnosis, failed repair; a wrong diagnosis recovers (G-m, init bases)
- **Records:** v5 `artifacts/vm/hdb/artifacts/hdb/s2DC_exp_A1e.jsonl#L1`; v6 `artifacts/vm/ds1/gm_A1e6.c.jsonl#L1`. Instance
  `hdb-v1-gen-0024:devcomp:pitch_sensor_bias.++heavy_torso:0`.
- **Why selected:** the only G-m case where v6 held the exact injected pair as leader and v5 held a primitive unrelated to the truth.
- **v5:**
  - dx actuator_strength:knees (0.91), p(truth) 0.000.
  - Screen: torque_limit first. Twin 1/8 → plant r16 12, then plant stride r16 15, stress 4/4.
  - **FULL** (val 0.96).
- **v6:**
  - cf:foot_friction@x2 drove the composite expansion (misfit −11.1). dx sensor_bias:pitch+torso_mass:torso (0.78).
  - Screen: torque_limit first (twin 6/8, r8 6), then plant torque_limit r16 12, then plant torso_mass r16 12.
  - **NOT_RECOVERED**: val 19/24 (one seed short) and NOT_VERIFIED.
  - The *correct* structure under-predicted every repaired design: predicted 3, 2, 4 walking vs 6, 7, 6 observed.
- **Interpretation:**
  - A correct diagnosis neither selected a different first tool nor produced a better design.
  - The true structure's twin predicted the repaired designs worse than the alternatives did.
- **Alternative:** the second tool (stride vs torso_mass) and optimizer trajectory differ, so this is one pair, not a tool effect.
- **Cannot establish:** whether stride would have recovered v6's design.

### T2 Same correct diagnosis, same first tool: one validation seed separates FULL from failure
- **Records:** A1e `artifacts/vm/ds1/eval/eval_A1e_s0.jsonl#L4`; A1e6 `artifacts/vm/ds1/eval/eval_A1e6_s0.jsonl#L4`. Instance
  `hdb-v1-gen-0104:clock_fault:3`.
- **Shared by both arms:**
  - dx clock_scale:clock (1.00 / 0.92). CMA screen top = feedback (4/4).
  - Twin warm start feedback at 8/8 in the twin.
- **A1e:**
  - Twin design r8 4. Plant feedback r16 15, stress 4.
  - Second tool foot_length (CMA screen rank 2) r16 15, submitted. **FULL**, val 20/24.
- **A1e6:**
  - Twin design r8 5. Plant feedback r16 12.
  - Second tool leg_length (foot_length fell to CMA rank 5) r16 11. Submitted feedback design. val 19/24 → PARTIAL.
  - Three assimilations: obs 5/5/5 vs leader predicted 5/5/6. TV ≤ 0.008.
- **Interpretation:**
  - With identical diagnosis and first tool, plant CMA reached 15 vs 12 of 16 from different twin starts.
  - The verdict hinged on a single seed at the 80 % threshold.
- **Alternative:** the second-tool choice (foot_length vs leg_length) is the cause. The records cannot separate the two
  explanations.

### T3 Correct diagnosis at 1.00, directly compensating tool invisible, robot walks but is not farther than faulty
- **Record:** `artifacts/vm/ds1/eval/eval_A1e6_s3.jsonl#L1`, `hdb-v1-gen-0073:low_ground_friction:0`. Base foot_friction 1.319.
- **Observations:**
  - floor_test@x3 → contact_friction:feet 0.9997.
  - CMA screen: leg_length, placement, posture, timing all 4/4. foot_friction is **absent**: its probes ×2 and ×3 give
    2.64 and 3.96, outside the guided bound 2.0 (`morphology.BOUNDS`), so `screen_tools` silently drops the tool.
  - Designs: twin leg_length r16 15, stress 4, **disp −2.27 m**, p_full 0.013. Plant leg_length/placement r16 13,
    disp −3.03 m.
  - val 0.96 but verdict_v1 **WORSE**.
  - Assimilations: every hypothesis predicted 6–7/8 and 7/8 was observed. TV = 0.
- **Interpretation:**
  - The faulty robot travels ~2–3 m farther than the repaired robot.
  - The engine's displacement evidence knew the design would fail (p 0.013), but neither the screen nor the CMA objective
    targets displacement.
- **Counter-evidence (T3b):** `artifacts/vm/hdb/artifacts/hdb/ds1/stream/r1_upd_hdb-v1-gen-0038_low_ground_friction_0.jsonl#L1`.
  - Base friction 0.635, so foot_friction was screened and ranked first (4/4).
  - Twin 8/8 → plant r8 5 → plant CMA r16 7 → val 13/24, NOT_RECOVERED.
  - The compensating tool, when available, did not recover that instance.
- **Cannot establish:** whether foot_friction would recover 0073 (unobserved).

### T4 Informative repair outcome overwhelmed by prior concentration, and not decision-reachable
- **Record:** `artifacts/vm/ds1/eval/eval_A1e6_s0.jsonl` (`hdb-v1-gen-0142:pitch_sensor_bias:3`; see `feedback_events.csv`).
- **Event 0 (twin design):**
  - obs 8/8. Predicted: jd:hips 8, sensor_bias:pitch (truth) 8, jd:all 5, segment_length:legs 0.
  - Leader jd:hips 0.81 (wrong). TV 0.168.
- **Event 1 (plant design):**
  - obs 8/8. Predicted: jd:hips **5**, truth **8**.
  - Leader jd:hips 0.98. Log-odds gap 4.55 nats > the 8-seed ceiling 3.41, so no leader change was possible.
  - The event followed plant optimisation, which has no code path to a re-screen.
- **Interpretation:** the feedback was discriminating and pointed to the truth. The update worked (mass moved), but the prior gap
  and the decision flow made it inert. FULL: no.
- **Cannot establish:** whether a re-screen under sensor_bias would have helped.

### T5 Identical predictions: a successful repair carries no information
- **Records:** `artifacts/vm/ds1/eval/eval_A1e6_s1.jsonl#L2` and `artifacts/vm/ds1/eval/eval_A3v5_s1.jsonl#L2`
  (`hdb-v1-gen-0096:feedback_gain_loss:0`).
- **Event:**
  - Before: aw:left+gain_scale 0.48, unmodelled 0.30, actuator_strength:left 0.22.
  - Every structure, the truth (gain_scale:balance_feedback) included, predicted 8/8. Observed 8/8. TV 0.00015.
- **Interpretation:** a repair that works under every hypothesis cannot discriminate between them. This instance is FULL in all 4 arms.

### T6 Compound pair never constructible; open-world reserve takes all mass (G-m)
- **Record:** `artifacts/vm/ds1/gm_A1e6.c.jsonl` (`walkrec-dev-m1-gen-0006:devcomp:short_feet+clock_fault.fast:0`; row in
  `compound_cases.csv`).
- **Observations:**
  - Only one of the two true primitives survived the 12-particle generic screen.
  - Misfit flagged twice (−12.6, −12.1), so 2 expansions ran, but no enumerated pair contained both truths.
  - Unmodelled reserve 1.00 at the end; v5 also missed.
- **Pattern:** this holds for all 5 G-m cases where the reserve led. In all 5, the true pair was not enumerable.
- **Interpretation:** a candidate-generation failure, not a likelihood failure.

### T7 Nemotron degrades a consequential decision: diagnosis past the engine's stop, twin exhausted, faulty design submitted
- **Record:** `artifacts/vm/ds1/eval/eval_A3v5_s0.jsonl#L2`, `hdb-v1-gen-0073:heavy_torso:2` (truth torso_mass).
- **Sequence:**
  - 10 plant experiments; the engine's own rule would have stopped after 2–3 (twin guard).
  - Twin used 548 → 2,798 / 2,800.
  - The last 2 experiments (cf:torque_limit@x2, cf:foot_length@x1.5) changed nothing: the twin was exhausted during the
    belief update, so plant rollouts were spent with no inference.
  - Turn 13 `conclude design 0` (the unmodified faulty design), P(success) 0.78, with 659 plant rollouts unused.
- **Outcome:** NOT_RECOVERED, val 0.00.

### T8 Nemotron improves the same decision on the same instance: physically reasoned direct repair
- **Record:** `artifacts/vm/ds1/eval/eval_A4x_s0.jsonl#L2`, same instance as T7.
- **Sequence:**
  - weigh_test (engine top EIG).
  - `repair` twin mode, tool torso_mass, start_edits torso_mass@x0.7. Twin 7/8, r8 8, r16 16, stress 3/4, disp +1.28 m, p_full 0.87.
  - `conclude`. **FULL**, val 0.96, plant 53 / 700.
- **Engine comparators:** A1e6 `eval_A1e6_s0.jsonl#L2` and A1e `eval_A1e_s0.jsonl#L2`.
  - Both CMA screens are tied at 4/4 across 5 tools; torso_mass was 4th.
  - Both chose leg_length (then placement/timing). r16 16/16 but disp −0.45 to −0.88 m, so WORSE/NOT_VERIFIED.
- **Interpretation:**
  - Nemotron chose a tool that the saturated screen could not distinguish, and the choice was physically correct.
  - Together with T7, this shows that the same LLM on the same instance can produce the best and the worst decision. Aggregate
    FULL hides both.
- **Alternative:** luck in a tie. One instance, no replication.

### T9 Experience changes a consequential decision: the track record suppresses overrides
- **Record:** `artifacts/vm/ds1/eval/eval_A4x_c.jsonl#L1` (and ~10 similar A4x repair decisions).
- **Notebook shown:** "when you overrode the engine's default repair, 1/10 verified; when you delegated it, 23/39 verified."
- **Nemotron's reason:** "delegating to the engine's default repair yields a far higher verification rate (23/39 ≈ 59%) than
  overriding it (1/10 ≈ 10%)." It then delegated.
- **Outcome-level evidence:** A4x deviated in 3/36 vs A3v5 10/36 (paired discordant 2 vs 9, exact p = 0.065).
- **Interpretation:**
  - The memory is connected to action. Its main effect is to make Nemotron delegate.
  - The statistic it relies on is selection-confounded: earlier agent versions, different instances, delegated base rate 59 %
    vs ~30 % in dev-eval.

### T10 Contradicting case: wrong diagnosis, no twin warm start, fixed fallback order, yet the only FULL among 4 arms
- **Record:** `artifacts/vm/ds1/eval/eval_A3v5_c.jsonl#L1`, `hdb-v1-gen-0070:devcomp:low_ground_friction+feedback_gain_loss:0`.
- **Sequence:**
  - dx payload:torso (0.91), p(truth) 0.000.
  - Nemotron ran 6 experiments and one direct plant placement repair (r16 12, disp +0.95 m). The twin was then exhausted.
  - `tool_screen_unavailable` → fixed order, posture first. Plant posture r16 12 → **FULL** (val 0.92).
  - A1e, A1e6 and A4x (all with screens, all with wrong diagnoses) failed.
- **Interpretation:** this contradicts any account in which diagnosis quality or the twin screen drives repair success.
  Outcomes near the threshold are trajectory-sensitive.

### T11 Identical memory, different procedure (LLM run-to-run variation, stream round 0)
- **Records:** `artifacts/vm/hdb/artifacts/hdb/ds1/stream/r0_upd_hdb-v1-gen-0064_one_side_weakness_3.jsonl#L1` and
  `.../r0_frz_hdb-v1-gen-0064_one_side_weakness_3.jsonl#L1`.
- **Shared:** the first-turn CASE EVIDENCE text is byte-identical.
- **upd arm:** experiments balance_gain, hip_bias, freq, foot_length, then `tool_order [torso_mass, torque_limit, posture]`.
  r16 16/16 but disp −0.94 m → WORSE.
- **frz arm:** different experiments, then a plain delegate. Engine timing (5-way tie at 4/4) → val 19/24, PARTIAL.
- **Interpretation:** with no memory difference, the tool sequences differ (3 of 5 round-0 pairs do). Later-round differences
  (9/15) are no larger.
