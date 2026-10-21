# What Nemotron contributed to Creature Forge (W2a attribution audit)

Date: 2026-10-21. Branch `feature/do1-demo`. Read-only audit of recorded evidence: no physics, no Nebius, no model call.
Machine-readable companions (hash-pinned, served by `/api/nemotron/case`):
- `experiments/w2/studies.json`: one row per study. `tests/test_w2_case.py` checks that every row quotes its source file verbatim.
- `experiments/w2/gen0137_one_side_weakness/`: the three recorded episodes of the demo case (byte-exact lines), `case.json`
  and `cross_instance.json`, rebuilt by `scripts/w2_case_build.py`.

## 1. Summary

- **One pre-registered result favours Nemotron**: the Forge Loop scoreboard (drawn creatures, push and stand). AI-selected
  redesigns verified in 6/12 investigations vs 1/12 for matched random edits (discordant 5 vs 0, exact one-sided McNemar
  p = 0.031). The effect was concentrated in the push challenge. Nothing verified on walking.
- **Every other registered comparison is null or negative for Nemotron.** These are the Phase 1 batch, the Forge memory
  evaluation, the walking-recovery confirmatory S3 and the causal-engineer held-out evaluation.
- **Development studies of the HaS scientist show parity.** On 36 paired Stage 2 instances, Nemotron (A3) and the engine
  alone (A1e) verified 15 vs 14 (discordant 4 vs 3, p = 0.50). On compositions it was 6 vs 8. In DS-1 it was 8 vs 8.
  Its success forecasts were worse than a constant.
- **The strongest effects in the programme are deterministic** and are not Nemotron's:
  - the belief engine vs exhaustive screening, 109 vs 62 of 211;
  - R2's classical optimiser, 150/150 vs 91/150;
  - the DO-1 objective (NO_AI): FULL 21/24 vs PARTIAL 19/24 in the exploratory replicate; in the pre-registered
    replication on the same robot (W3) FULL 5/5 vs 0/5 (exact McNemar p = 0.031), and in a two-instance cross-family
    pilot (W4) one recovery and one partial (`docs/DO1_REPLICATION_REPORT.md`).
- **What Nemotron demonstrably does** is take real scientific decisions inside a deterministic laboratory. It chooses
  experiments, proposes executable hypotheses and decides when to delegate. In one recorded instance (gen-0137
  one_side_weakness, §3) its experiment choice changed the diagnosis from wrong to right on identical evidence, and the
  episode verified. That instance is selected post hoc. It is the only one of 36 with that pattern, and a second Nemotron run
  on it (A4) did not verify.

**DO-1 and Nemotron are separate results.** The DO-1 L4 recovery (`docs/DO1_DEMO.md`) is a deterministic change to the
plant optimiser's objective. Both arms are A1e6 with recorded provenance NO_AI, and no model was called. Nemotron's
contribution is the scientific-decision evidence below. Neither result supports the other.

## 2. Where Nemotron sits in the code

| Layer | File | Role |
|---|---|---|
| Client | `creature_forge/nebius.py` | Token Factory client (`https://api.tokenfactory.nebius.com/v1`). Injectable transport, request/token/timeout limits, no blind retries, key never logged. |
| Model settings | `experiments/forge_loop/model_config.json` | Default `nvidia/nemotron-3-super-120b-a12b`, temperature 0.6, JSON schema. The HaS agent ran with thinking enabled and `max_tokens` 32000 (recorded per call). |
| Ledger | `creature_forge/inference_ledger.py` | Every call is appended with its request id, tokens and cost. The demo case's 8 request ids (A3 and A4) are each found once in `stage2_final/inference_ledger_main_20261020.jsonl` (sha256 `729e37ff…`). |
| HaS scientist | `creature_forge/has_agent.py`, `scientist_has.py` | One tool per turn from a notebook (measurements, posterior, model check, candidate experiments with EIG and per-hypothesis predictions, tool screen, engine recommendation). Replies are validated by schema, whitelist and bounds. An invalid reply falls back to the engine's recommendation, which is recorded as `fallback`. |
| Deterministic instruments | `belief_engine.py`, `hdb_workbench.py`, `hidden_plant.py`, `walk_opt.py`, `recovery.py` | Bayesian inference over simulated hypotheses, EIG, twin and plant CMA-ES, and the independent verification `full_recovery_v1`. |
| Other Nemotron roles | `forge_ai.py` (Forge Loop), `director.py` / `mech_director.py` (walking recovery), `investigator.py` (Phase 1) | Proposals and strategies that MuJoCo and `verdict_v1` or `full_recovery_v1` judge. |

## 3. The demo case: gen-0137 one_side_weakness (Stage 2 transfer, development data)

Sources (byte-exact single lines, pinned in `SOURCES.json`; the full files' SHA-256 values are the ones in
`experiments/causal_engineer/dev/hdb/STAGE2_TRANSFER_agent_v4.md`):

| Arm | Source | Line | Provenance |
|---|---|---|---|
| A3 Nemotron scientist | `stage2_final/s2_transfer_A3.jsonl` (`540b9415…`) | 24 | LIVE, 4 calls, $0.0118 |
| A1e engine alone | `s2T_A1e.jsonl` (`2014fa80…`) | 24 | NO_AI |
| A4 Nemotron + memory + learned posterior | `stage2_final/s2_transfer_A4.jsonl` (`cb34a780…`) | 24 | LIVE, 4 calls |

**Hidden truth** (evaluation only; no arm saw it): right-side actuator weakness (`actuator_strength:right`), severity 4,
1.3× its failure threshold. The robot is base gen-0137, the same base as the DO-1 L4 robot, with a different hidden fault.

### 3.1 Verified chain

1. **Failure.** The nominal design on the damaged plant: walking 0/4 on the obs seeds (upright for all 10 s, mean forward speed 0.06–0.09 m/s).
   It is also 0/8 on the eligibility check. The record is bit-identical in all three arms.
2. **Hypotheses.** After that observation the engine's belief is right side 0.895 and left side 0.105. It is identical in
   all arms. The prior already favoured the truth.
3. **The fork (turn 0).** The notebook offered 7 candidate experiments, parsed from the recorded prompt:
   - **All 7 show EIG 0.34 nats**, equal to the belief entropy, so EIG cannot separate them.
   - The engine's rule ("highest expected information gain per plant rollout") took `cf:freq@x1.2`, at EIG 0.340.
     Its predicted walking is 1/1/0 of 2 under H1/H2/H3: no left/right contrast in walking.
   - **Nemotron chose `cf:freq@x0.85`**, at recorded EIG 0.339. Its predicted walking is 2/0/2: a clear left/right
     contrast. Its words: under right-side weakness "≈4/4", under left-side "≈0/4".
   - Its claim that this is "more informative than the engine's default suggestion" holds for the walking contrast, not
     for the engine's EIG.
4. **Registered prediction.** None. Nemotron returned an empty structured prediction, and the agent recorded
   `prediction_issue: missing ['n_walking', 'pitch_mean', 'time_upright']`. The qualitative expectation in its text is
   checked here informally only.
5. **Deterministic measurements** (MuJoCo, hidden plant, the same 4 seeds):
   - `freq@x0.85`: 3/4 walk; one start fell at 1.73 s. This is consistent with the right-side prediction (2/2 in the
     notebook; Nemotron said ≈4/4), not with the left (0/2).
   - `freq@x1.2`, the engine alone: 2/4 walk.
6. **Bayesian update** (the same engine, on each arm's own data):
   - A3: right side 1.000, final MAP right with mass 0.99999.
   - A1e: **left side 0.998**, final MAP left, mass on the truth 0.002. The engine alone became confidently wrong from its
     own top-EIG experiment.
7. **Nemotron's later decisions.**
   - Turn 1, `screen_tools`; the engine recommended `delegate_repair`.
   - Turn 2, `propose` 4 hypotheses: joint damping right, pitch sensor bias, foot friction and left-side weakness. All
     ended at weight 0.000; three were pruned, and left-side weakness was ranked 2 with a log-likelihood gap of −11.5.
     Its reason cited a "systematic" double-support residual of −1.1 noise units, which the notebook's own rule
     (|r| > 2 is unexplained) treats as explained.
   - Turn 3, `delegate_repair`, as the engine recommended. Its `tool`/`mode` fields are not arguments of
     `delegate_repair` and were not used.
8. **Repair (the engine's optimiser).** Each arm optimises a simulator ("twin") design against its own belief, then
   plant CMA on two tools:

   | Step | A3 (belief: right) | A1e (belief: left) |
   |---|---|---|
   | Twin design, leg length, checked on the real robot | **6/8** | 3/8 |
   | Plant CMA, leg length (400 trials) | 11/16 | 12/16 |
   | Plant CMA, second tool (264 trials) | posture 5/16 | placement 11/16 |
   | Submitted (best check) | design 2, twin leg length (`7d577c6688`) | design 3, plant leg length (`4a74f1bbe1`) |

9. **Independent verification** (`full_recovery_v1`, 24 hidden validation starts plus a 20 s confirmation):
   - **A3: FULL_RECOVERY, 23/24**, confirmation passed.
   - **A1e: PARTIAL_IMPROVEMENT, 20/24.** Confirmation failed: "walking on 79% of seeds at 20 s, needs >= 80%".
10. **Costs.**
    - A3: plant 696/700, twin 2,798/2,800, 4 calls, 14,757 prompt and 8,193 completion tokens, $0.0118.
    - A1e: plant 680/700, twin 2,134/2,800, no calls. (A3 used 664 more twin rollouts: equal budgets, not equal use.)

### 3.2 What this shows, and what it does not

- **Shown (one instance).** On identical evidence and an identical belief, Nemotron chose a different experiment, among
  candidates that EIG ranked as tied. It chose by a physically legible criterion: the predicted walking outcome separates
  the two sides. Under that experiment the engine's own Bayesian update reached the truth. Under the engine's choice the
  same update reached the wrong side with 0.998 confidence. The twin design built against the correct belief transferred
  to the damaged robot (6/8 vs 3/8), and that design verified.
- **Not shown.**
  - That Nemotron is a better experimenter in general. Across the 36 instances, its first experiment differed from the
    engine's in 22. Its final diagnosis was correct in 28 vs the engine's 29. Diagnosis discordance was 3 vs 4.
  - That Nemotron repaired the robot. The repair was the engine's delegated procedure.
  - That a correct diagnosis suffices. **A4** made the same choice, measured bit-identical results and reached the same
    correct belief. Its delegated repair produced a different twin design (`86776eb382`, also 6/8 on the real robot), and
    it verified only PARTIAL, at 19/24.
  - Any registered forecast skill. No prediction was registered here. Across A3 singles, 90 % interval coverage was
    25/30 for walking count, 14/30 for time upright and 17/28 for pitch (`docs/STAGE2_REPORT.md` §3.2).
- **Selection.** The case was picked after the fact because it is instructive. It is the only one of 36 where Nemotron's
  diagnosis was right, the engine's was wrong, and only Nemotron's arm verified (`cross_instance.json`,
  `map_and_full_both_favour_A3`).
  - The engine alone verified 3 instances Nemotron did not: gen-0096 payload_offset:4, gen-0142 low_ground_friction:1 and
    gen-0143 short_feet:1.
  - It had the right diagnosis where Nemotron's was wrong in 4: gen-0073 low_ground_friction:1, gen-0073 short_feet:1,
    gen-0142 pitch_sensor_bias:1 and gen-0143 actuator_weakness:1.
  - The Stage 2 transfer instances were later read for failure analysis, so they are no longer an untouched evaluation
    set.

### 3.3 Deterministic attribution without new physics

The plan of record proposed `hdb_replay.replay()` (generic + Nemotron hypotheses vs generic only) as the attribution
replay. It is not needed for this case, and as written it would not attribute it:
- **The hypothesis contribution is already zero in the record.** All four of Nemotron's hypotheses ended at weight 0.000.
- **`hdb_replay.nemotron_proposals` would see no proposals.** It reads log entries with role `propose`. The agent-v4
  records log every call under role `agent`.
- **The experiment-choice counterfactual is recorded directly.** A1e is the engine-alone continuation from the
  bit-identical state; the observation and the belief after it are identical. A4 is a second, independent LIVE run of
  Nemotron's branch, and its X1 features and belief are bit-identical to A3's.

A replay would need twin rollouts, which are physics. It is not run, and is not proposed unless the owner wants the
hypothesis contrast across all 36 instances.

## 4. Attribution table (all studies, date order)

The rows come from `experiments/w2/studies.json`; each has a source file and a verbatim quote checked by the tests.

| Date | Study | Registration · n | Outcome | Credited to |
|---|---|---|---|---|
| 10-13 | Physics Investigator live batch | pre-registered · 3 requests | 2 valid replies, both torso_mass 5→3, failed; 1 invalid | none |
| 10-14 | R2 local robustness | pre-registered · 150 seeds | 150/150 vs 91/150 | classical optimiser (NO_AI) |
| 10-14 | AI Investigation demo live-002 | single instance · 32 seeds | 28/32 and 25/32 vs frozen 19/32; random 25/32 and 30/32 | inconclusive |
| 10-15 | **Forge Loop scoreboard v1** | **pre-registered · 12 pairs** | **6/12 vs 1/12, p = 0.031 (push)** | **Nemotron** |
| 10-15 | Forge Loop walking investigations | development | nothing verified | none |
| 10-16 | Forge memory evaluation | pre-registered · 12 pairs | 6/12 vs 7/12, p = 0.773 | none |
| 10-17 | Walking recovery S2/S2b | development · 12 | director 2/12, 4/12 vs FIX 4, RAND 7 | none |
| 10-17 | Walking recovery S4a (control laws) | development · 24 | 4/24, 5/24 vs fix15 11/24 | none |
| 10-17 | Walking recovery S3 confirmatory | pre-registered · 48 | FIX 19, director 9; AI > FIX p = 0.996 | fixed strategy (NO_AI) |
| 10-18 | Causal engineer held-out | pre-registered · 40 | exhaustive 23, scientist 14, sci+memory 16 | exhaustive screening (NO_AI) |
| 10-19 | HaS Stage 1 engine vs exhaustive | development · 211 | 109 vs 62 (paired 61 vs 14) | belief engine (NO_AI) |
| 10-20 | HaS Stage 2 singles, A3 vs A1e | development · 36 | 15 vs 14, discordant 4/3, p = 0.50 | parity |
| 10-20 | HaS Stage 2 gen-0137 one_side_weakness | post hoc case · 1 | A3 FULL 23/24 vs A1e PARTIAL 20/24; A4 PARTIAL 19/24 | Nemotron's experiment choice changed the diagnosis; the repair was the engine's |
| 10-20 | HaS Stage 2 compositions | development · 16 | 6 vs 8 (discordant 0/2) | none |
| 10-20 | HaS Stage 2 A4 (memory + learned) | development · 36 | 14 vs 14 (2/2); memory applied once | none |
| 10-20 | DS-1 A3v5 vs A1e6 | development · 30 + 6 | 8 vs 8 and 2 vs 1; P(success) worse than constant | none |
| 10-20 | DS-1 experience / stream | development · 36; 20 | 10 vs 8 (p = 0.31), deviated 3/36; stream 7 vs 7 | none established |
| 10-20 | TA-1 / RV-1 tool access | staged · 1 per phase | 1B both NOT_RECOVERED; A1 L4 both PARTIAL 19/24 | none (NO_AI) |
| 10-21 | **DO-1 L4 recovery** | exploratory, audited · 1 pair | DO-1 FULL 21/24 vs frozen PARTIAL 19/24 | **DO-1 objective (NO_AI)** |

**Favourable:** the Forge Loop scoreboard (registered), and the gen-0137 case (one instance).
**Mixed:** the AI Investigation demo, Stage 2 singles, DS-1 experience, and the gen-0137 A4 replicate.
**Negative:** the Phase 1 batch, Forge walking, Forge memory, walking recovery S2/S4a/S3, the causal-engineer held-out
evaluation, Stage 2 compositions and A4, and DS-1 A3v5.

## 5. Demonstration integrity (W2b)

- **New Studio tab `?tab=nemotron` ("Nemotron's experiment").** It shows failure → hypotheses → Nemotron's experiment →
  measurements → belief → repair → verification for A3 and A1e side by side, then the A4 replicate, the 36-instance
  strip and the study table.
  - Every number is read from the pinned case files. The page recounts the counts from the rows and fails loudly on any
    disagreement.
  - It is labelled RECORDED LIVE playback, and the page makes no model call.
- **Scientist tab relabelled.** Its replays (`/api/scientist/.../replay`) simulate the recorded designs on the nominal
  robot, because the HaS damage lives in the hidden plant.
  - Viewports now read "NOMINAL DESIGN — no hidden damage" and "SUBMITTED DESIGN — on the nominal robot, no hidden
    damage".
  - A banner and the API note state this.
- **Causal tab unchanged.** Its faults are part of the replayed body and vector (`fault_bench.inject`), so "INITIAL DESIGN
  (the faulty robot)" is accurate there.
- **Damaged-plant replays: exported and verified (2026-10-21, owner-authorized VM run).**
  `scripts/w2_damaged_plant_export.py` ran on the main VM at `c8816c6`.
  - **Environment:** Linux x86_64, Python 3.12.3, numpy 2.5.4, MuJoCo 3.15.0, the recorded one. 2 workers, 1:32 wall
    time, 210 MB peak.
  - **Attempt 1 failed closed in the instance check, before any experiment rollout.** The exporter compared all 8 of
    the instance's obs seeds, but the bench observes on the first `n_obs` = 4. The fix is in the exporter; nothing in the
    gate was loosened. Its logs are in `experiments/w2/export_run_2026-10-21/attempt1/`.
  - **Gates passed:**

    | Gate | What was checked | Result |
    |---|---|---|
    | Instance rebuild | eligibility labels 0/8, nominal design, strength, obs seeds | equal to the record |
    | Experiments X0, X1 (Nemotron, `freq@x0.85`), X1 (engine, `freq@x1.2`) | every per-seed feature, on the production path and on the traced frame path | **exact** |
    | Verification of both submitted designs | status, walking fraction and reasons | equal to the record: A3 FULL_RECOVERY 23/24; A1e PARTIAL_IMPROVEMENT 20/24, "confirmation: walking on 79% of seeds at 20 s" |
    | Frames | forward-kinematics error of the pre-step state | 0.0 m (tolerance 1e-9 m) |

  - **Limitation.** Stage 2 kept no per-seed verification rows. The 72 validation replays (faulty robot, A3 design,
    A1e design × 24 starts) are therefore reconstructed simulations. They match the record at the level it allows, and
    each trace matches this run's own production row. They are not archived original frames, and the page and the video
    say so. The 12 experiment replays reproduce the recorded per-seed measurements exactly.
  - **Output.**
    - `experiments/w2/gen0137_one_side_weakness/plant_replays/`: 84 payloads, 9.2 MB. `SHA256SUMS` is `7c05c8de…`,
      pinned in `creature_forge/studio/nemotron_api.py`; every served file is checked against it.
    - Run logs, the run script and the archive hashes are in `experiments/w2/export_run_2026-10-21/`.
  - **Cost and shutdown.** Infra ledger $88.939 → $88.971 (+$0.032). Both VMs were confirmed STOPPED through the control
    plane.
  - **The page.** Stages 1, 4 and 7 have a "watch" button. One viewer is mounted at a time, because the playback clock is
    shared.
    - Stage 1 shows the damaged robot.
    - Stage 4 shows both experiments side by side, on all 4 starts, including the start where Nemotron's own
      experiment fell.
    - Stage 7 shows the faulty robot and both submitted designs, on any of the 24 hidden starts. It opens on a
      pre-declared illustrative seed: the first where A3's design walks and A1e's does not.
    - Captions are the recorded outcomes.

## 6. Reproduce

```
python scripts/w2_case_build.py --check [--full-root <...>/artifacts/vm/hdb/artifacts/hdb]
python -m unittest tests.test_w2_case tests.test_w2_damaged_plant_export
npm --prefix studio run build && BASE_URL=http://127.0.0.1:8000 node studio/e2e/nemotron-flow.mjs
python scripts/w2_damaged_plant_export.py          # dry run only
```
