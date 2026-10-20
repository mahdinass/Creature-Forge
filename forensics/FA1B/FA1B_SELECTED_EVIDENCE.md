# FA-1B selected evidence (8 traces)

- **Sources.** Record paths are relative to the repository (`ea9e729`); `#Ln` is the 1-based JSONL line.
- **Not duplicated from FA-1.** These traces add correctness details absent from FA-1's T1–T11. Where an instance overlaps an
  FA-1 trace, only the new detail is shown.

---

## E1. Final per-seed validation data are discarded at serialisation (Investigation A2)

- **Source:** `scripts/hdb_agent_run.py:114, 126-127`; `creature_forge/recovery.py:168-174`; any eval record, e.g.
  `artifacts/vm/ds1/eval/eval_A1e6_s1.jsonl#L1` (hdb-v1-gen-0073:low_ground_friction:2).
- **Sequence.**
  1. `recovery.assess` returns `validation.original` and `validation.candidate`: 24 rows each with score, walking,
     `forward_disp_upright` and label.
  2. It also returns `verdict` (wins, losses, ties, `median_diff`, `p_one_sided`) and `confirmation.per_seed`.
  3. `run_one` keeps only `{"status", "walking_frac", "reasons", "rollouts"}`.
- **Fields:** `status NOT_RECOVERED`, `walking_frac 0.958` (23/24), `reasons ["verdict_v1 is WORSE, not VERIFIED_IMPROVEMENT"]`.
- **Search:** 0 occurrences of `median_diff` or `p_one_sided` in any DS-1 file or in `ds1_all.tgz` (stream-scanned, not
  extracted). Logs contain one summary line per instance.
- **Interpretation:** final per-seed distances of the faulty and submitted designs are unrecoverable without re-simulation.
- **Competing interpretation:** none. This is a direct absence.
- **Cannot be established:** whether each WORSE or NOT_VERIFIED verdict came from the sign test, the 0.5 m minimum effect, or
  `MIN_NON_TIED`.

## E2. One instance, four arms: compensating tool absent, robots walk, verdict WORSE (A + B)

- **Source:** `eval_A1e_s1.jsonl#L1`, `eval_A1e6_s1.jsonl#L1`, `eval_A3v5_s1.jsonl#L1`, `eval_A4x_s1.jsonl#L1`;
  instance hdb-v1-gen-0073:low_ground_friction:2.
- **Instance:** strength 0.6235 (mult 1.7, injected friction ×0.536). Base `foot_friction` 1.319.
- **Faulty robot:** eligibility labels `contact_chatter` 8/8.
- **Probe screens (every arm):**
  - the order is placement > posture > leg_length > timing > torso_mass > stride > foot_length > torque_limit > feedback;
  - there is **no `foot_friction` entry**;
  - the `foot_friction@x2` (2.64) and `@x3` (3.96) probes exceed the guided maximum 2.0 (`morphology.py:14`), so both raise and
    are skipped (`belief_engine.py:813-816`).
- **Executable but unused.** The CMA interval for `foot_friction` would be ×0.25–×1.516 (`walk_opt._log_interval`).
- **Feasibility bound.** In `scripts/_friction_feasibility.json`, the threshold trace needs ×1.37–×1.46 to return effective μ to
  the base's walking bracket. That is inside the legal range.
- **Repairs:** placement then posture, in every v6 arm.
  - A1e6: twin placement 8/8; plant check 8/8 then 16/16; robust displacement WORSE, median −2.87 m.
  - Plant placement and posture: 16/16, WORSE −2.80 m.
  - Validation: 23/24 walking, WORSE.
  - A1e (v5, no displacement evidence) accepted early at mapped P 0.77 and was WORSE at 24/24.
- **Interpretation:**
  - the robots walk robustly but travel ≥ 2.8 m less (median) than a chattering, non-walking faulty robot;
  - the tool that restores the physical cause was never offered;
  - v6's stop map saw the displacement problem (P 0.06) and could not repair it.
- **Competing interpretation:** a friction-only repair might also lose on distance, because the faulty robot's displacement
  is not walking-gated. A friction repair could also fail outright, as in E7.
- **Cannot be established:** whether a `foot_friction` repair would verify. That needs simulation.

## E3. Leg-shortening repair: walks by body-relative criteria, never farther than faulty (A3)

- **Source:** `eval_A1e6_s5.jsonl#L2`, hdb-v1-gen-0073:heavy_torso:0.
- **Sequence.**
  1. The probe screen ties 6 tools at 0.542 (saturated).
  2. CMA re-rank: leg_length first.
  3. Twin leg_length: legs 0.8707 → 0.6438 m, twin 8/8, plant 8/8 then 16/16, displacement WORSE −1.73 m.
  4. Plant leg_length: legs 0.5814 m (×0.668), 16/16, WORSE −1.81 m.
  5. Plant placement: 16/16, WORSE.
  6. Validation 23/24, WORSE.
- **Faulty robot:** `falling_forward` 8/8. A robot that falls after 1 s with ≥ 1 valid step is still scored its upright forward
  displacement (`hdb_evidence.walk_score`; `hidden_plant.py:617`).
- **Code:** `creature_criteria` scales `min_speed` and `min_step_advance` by the evaluated body's leg length
  (`creature_walk.py:62-71`). A ×0.668 body faces a 33 % lower walking speed bar.
- **Pattern across all 144 submitted designs:** legs ≤ ×0.85 in 12 designs, 0 FULL, 11 displacement-only.
- **Interpretation:**
  - the walking-count-first CMA objective (`walk_opt.py:395`) can satisfy the walking label by shrinking the body's own
    yardstick;
  - the absolute displacement clause then fails.
- **Competing interpretation:** shorter legs may simply be what stabilises a heavy torso, so the displacement loss is the
  physical price of stability rather than a criterion artefact.
- **Cannot be established:** the counterfactual distance of a stabilising repair at nominal leg length.

## E4. The one genuine partial particle update, and a misleading model-check display (C)

- **Source:** `eval_A3v5_s3.jsonl#L1`, hdb-v1-gen-0073:low_ground_friction:0. The twin ledger is in
  `engine.ledger.twin.lines[487..490]`; prompts are in `nemotron.calls[9..15]`.
- **Sequence.**
  1. Turn 7: Nemotron runs `cf:kp@x2`; the twin has 0 remaining after its EIG predictions.
  2. `_register(X6)` updates `contact_friction:feet` at factors 0.75, 0.5 and 0.7095 (ledger 487-489, 4 rollouts each).
  3. Factor 0.3523 is refused (ledger 490: "needs 4, 0 remain"). `_register` breaks without rollback
     (`belief_engine.py:631-636`).
  4. Final record: 3 particles include X6 and 9 do not. The final leader, factor 0.6107, lacks X6.
- **Posterior.** Every seed's term is ≤ −0.105 nats (`loglik`, L207-215), so updated particles are only ever penalised:
  - 0.7095: 0.0042 → 0.0028;
  - 0.75: 0.0005 → 0.0003;
  - leader 0.6107 (stale): 0.9890 → 0.9907.

  All particles share the structure `contact_friction:feet` (the true structure), so the structure posterior stays 1.0.
- **Display.** In calls 9–15 Nemotron's MODEL CHECK shows `X6:cf:kp@x2: fits` and later `X7:cf:kd@x0.5: fits`. The leader
  never scored X6 or X7: `state()` uses `best.seen.get(id) or {}` (`belief_engine.py:791`), and `notebook()` prints "fits" for
  an empty residual (`has_agent.py:592`).
- **Interpretation:** a confirmed inconsistent posterior state with the predicted bias direction, but negligible measured
  impact (same structure, leader unchanged, twin-dependent decisions unavailable).
- **Competing interpretation:** none for the state. For impact, the stale leader might have lost mass to a better-fitting
  magnitude had X6 been scored.
- **Cannot be established:** X6's log-likelihood contribution for the stale particles, because per-seed predictions were never
  computed.

## E5. Count-level replay cannot verify the update arithmetic (D2)

- **Source:** `eval_A4x_s0.jsonl#L5`, hdb-v1-gen-0142:pitch_sensor_bias:3, design 5 (assimilated `X5:check@5`).
- **Observed:** 8/8 walking.
- **Predicted counts:** joint_damping:hips 7, sensor_bias:pitch 7, segment_length:legs 0, joint_damping:all 5.
- **Seed-level exactness.** Observed = n, so each structure's representative particle has |pred − obs| seed mismatches exactly.
  The replay therefore predicts **no** relative shift between hips and pitch.
- **Realised:**
  - sensor_bias:pitch 0.0108 → 0.0948, the *true* structure;
  - joint_damping:hips 0.9792 → 0.8974;
  - a log-odds shift of 2.26 nats.
- **Why.** The hips structure holds ≥ 5 particles (factor 5.6–20) whose individual predictions differ. The event stores only the
  best particle's count (`belief_engine.py:479-483`). Its other particles mismatched more.
- **Aggregate:** in the exact subset (weights ≥ 0.01), realised/expected median 0.89 (IQR 0.54–1.25); 11/25 identical-count
  pairs shift by > 0.1 nats.
- **Interpretation:** the shift is consistent with correct per-particle arithmetic, and it is invisible to FA-1's structure-level
  replay. The replay's Spearman 0.85 is not a numerical verification. This event also carries real information toward the true
  structure that FA-1's count-level spread scored as zero.
- **Cannot be established:** exact per-particle predictions, which are not serialised (`Particle.as_dict` omits `seen`).

## E6. A fallback path verified where every screened arm failed; Nemotron's own design was discarded (B/E)

- **Source:** `eval_A3v5_c.jsonl#L1`, hdb-v1-gen-0070:devcomp:low_ground_friction+feedback_gain_loss:0. Other arms:
  `eval_A1e_c.jsonl#L1`, `eval_A1e6_c.jsonl#L1`, `eval_A4x_c.jsonl` (none FULL).
- **Sequence.**
  1. Nemotron runs experiments, including X5 `cf:fp_kd@+0.2R` → 4/4 walking (from 0/4).
  2. It makes a direct plant `placement` repair: design 5, robust 12/16, displacement +0.95 m.
  3. Its twin exhausts (`twin_budget_exhausted` in `add_particles`).
  4. Its `delegate_repair` carries `"design": 0` (an optional schema field, `has_agent.py:777`), so `select(0)`
     (`has_agent.py:419-420`).
  5. The twin warm start is refused; `screen_tools` returns at its first refused `twin_walk` (`belief_engine.py:821-822`), so
     there is no `tool_screen` event, `tool_screen_cma` ranking `[]`, and `tool_screen_unavailable` → fixed `TOOL_PROBES` order.
  6. Plant posture CMA on design 0 (budget 145) gives design 7: `fp_kd = fp_kv = 0` as in design 0; only `vector[5]` changed,
     −0.0046 → −0.0475. Robust 12/16, displacement NOT_VERIFIED. **Validation 22/24 → FULL.**
- **Prevalence:**
  - 45/67 dev-eval Nemotron `delegate_repair` actions carry `design: 0`;
  - 3 dev-eval (+1 stream) did so while a checked non-zero design existed (`scripts/fa1b_design0.py`);
  - 2 of those 3 ended FULL anyway.
- **Interpretation:**
  - the knock-on of Nemotron's budget use replaced the screened tool order with a fixed one, and the fixed order succeeded on
    this instance;
  - Nemotron's own placement design played no part in the FULL design.
- **Competing interpretation:** posture on the original design was always viable and the screened arms' tools (torso_mass,
  feedback, leg_length) were poor choices. This is a single instance, with robust evidence that understated the final outcome
  (12/16 → 22/24).
- **Cannot be established:** whether `design: 0` was intended by the model or is habitual field filling (it also appears on
  actions that ignore it).

## E7. Low friction with the friction tool available and ranked first: still fails (B3 counterexample)

- **Source:** `artifacts/vm/hdb/artifacts/hdb/ds1/stream/r1_frz_hdb-v1-gen-0038_low_ground_friction_0.jsonl#L1` (and `r1_upd_…`
  identical up to design indices).
- **Instance:** base friction 0.635, so the probes are valid (×2 → 1.27). Injected factor 0.141.
- **Sequence.**
  1. The screen ranks foot_friction 1st by probe and by CMA.
  2. Twin warm start foot_friction: friction 1.642 (×2.59), twin 8/8, plant 5/8.
  3. Plant foot_friction CMA *lowers* friction to 0.979 (×1.54): train 4/4, robust 7/16.
  4. Timing: 8/16.
  5. Submitted design 2: validation 13/24, INCONCLUSIVE displacement.
- **Feasibility bound:** ×1.13 to reach the base's walking bracket; both designs exceed it.
- **Interpretation:**
  - restoring friction above the base controller's threshold level was not sufficient here;
  - the arithmetic bound is a necessary-condition screen only;
  - this instance also shows train-seed over-fitting (4/4 → 7/16).
- **Competing interpretation:** the chosen magnitudes were not the right ones, and a longer search might succeed.
- **Cannot be established:** whether any friction magnitude verifies.

## E8. Nemotron re-introduces a screen-excluded tool (B3)

- **Source:** `…/ds1/stream/r0_upd_hdb-v1-gen-0064_one_side_weakness_3.jsonl#L1`, versus `r0_frz_…` on the same instance.
- **Instance:** base `torque_limit` 146.95, so the ×2 and ×3 probes exceed 200 and `torque_limit` is absent from the screen. The
  CMA ceiling is ×1.36.
- **Sequence (update arm).**
  1. `delegate_repair` with `tool_order [torso_mass, torque_limit, posture]` produces `preferred_tools` (`prefer` bypasses the
     screen, `belief_engine.py:886-888`).
  2. Twin torso_mass: 16/16 robust, WORSE −0.94 m.
  3. Plant torso_mass, then plant **torque_limit**: 16/16 robust, WORSE −0.88 m.
  4. Validation 22/24 walking, WORSE.
- **Frozen arm:** the engine-ranked timing gives PARTIAL, 19/24.
- **Interpretation:** the only observed path by which an excluded tool reached optimisation is Nemotron's `tool_order` or
  `repair` action. It happened once in 40 stream and 72 dev-eval LLM-arm episodes, and it did not verify.
- **Cannot be established:** whether torque_limit alone (first, with the full budget) would verify.
