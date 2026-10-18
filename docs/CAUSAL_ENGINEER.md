# Creature Forge Causal Engineer — architecture, hypotheses and execution log

Branch `feature/causal-engineer` (from `feature/walk-recovery` @ `f96b9d9`). Owner directive 2026-10-17: build an
autonomous, physics-grounded AI engineering scientist. Nemotron is the reasoning brain; MuJoCo, optimisers and physics
analysis are its instruments; independent verification stays authoritative.

Budgets (verified 2026-10-17):
- **Infra:** $26.77 of the $35 approved cap (conservative ledger). About $2 is reserved for the demo, so about $6 is
  usable: roughly 22 h on the 8-vCPU main VM, or about 3 h on the batch VM.
- **Inference:** $3.67 of $15 (958 requests).
- No new paid services.

## 0. Results summary (2026-10-18)

### What exists
- **Instruments** (`physics_probe`, `physics_digest`, `eng_tools`):
  - physics observations: COM, angular momentum, CoP, capture point, contacts, friction use, saturation, cadence against the
    pendulum frequency, Froude number;
  - healthy-reference ranges;
  - model-designed one- or two-parameter counterfactuals (never clipped);
  - a 20 s stress test;
  - CMA-ES repairs per tool;
  - all under one budget-exact ledger.
- **The Nemotron scientist** (`scientist.py`, v2.3) runs a closed loop:
  - its reply starts with its reading of the newest measurements, then a verdict on every tested hypothesis, then new
    hypotheses, then one action: experiment, test, repair or conclude;
  - predictions are registered before every experiment and scored afterwards;
  - verification is independent and hidden.
- **Experience:**
  - Level A, episodic memory, and Level B, mechanism cards (`experience_bank.py`, `ce_memory.py`), with applicability verdicts
    by the model;
  - Level C, a learned repair-effect predictor (`repair_learner.py`), used as advice and as a `learned` policy.
- **Comparison arms:** non-AI policies on the same tools (exhaustive, learned, random, expert rules) and one-shot ablations.
- **Studio:** the "Causal engineer" page shows recorded investigations (replays, timeline, hypotheses, predictions, memory
  verdicts, independent verification).

### Development evidence (dev robots only; prompts were tuned on them)
- The pilot1 audit found interface and evidence defects, not just model failure (`experiments/causal_engineer/dev/AUDIT_PILOT1.md`).
- v1 to v2.3 turned a non-revising agent (0 status updates) into one that revises, designs experiments and tests robustness.
- On 7 paired dev robots: 0 → 3 FULL recoveries.

### Held-out evaluation (registered; 40 robots on 22 unseen morphologies)
Reports: `experiments/causal_engineer/heldout/REPORT.md` (registered run) and `REPORT_AMEND1.md` (AI arms re-run after the
authentication outage, owner-approved, post-hoc).

| arm | FULL recoveries |
|---|---|
| exhaustive | 23 |
| learned | 18 |
| scientist + memory | 16 |
| scientist (closed loop) | 14 |
| scientist + memory + learned advice | 14 |
| random | 12 |
| one-shot scientist | 8 |
| expert rules | 6 |

- **No registered hypothesis is supported** after Holm correction.
- Closed loop vs one-shot is directionally favourable (10 vs 4 discordant, p = 0.09).
- The fixed exhaustive procedure beats the scientist (2 vs 11).
- Memory and learned advice show no measurable benefit.
- Level C's learned ranking is better on development ranking metrics but not on held-out recoveries (18 vs 23).
- Prediction accuracy (0.37) is below an always-`no_change` baseline.

### What Nemotron contributes, honestly
- On unseen robots it genuinely investigates: it designs experiments, registers predictions, revises and refutes hypotheses,
  and judges whether past experience applies (117 items: 33 applies, 38 does_not_apply, 44 needs_adaptation; 1 case of
  negative transfer).
- Its tool choices are about as good as the systematic procedure's (34/40 vs 38/40 chose a repairing tool). Its recoveries
  are better than random choices or hand-written rules, and worse than the exhaustive procedure.
- The main measured weakness is budget use: it stops after 317–362 of 700 rollouts instead of buying robustness. Its
  numerical predictions are not calibrated, and it largely ignores accurate learned advice (top-1 correct 31/40, followed
  9/40).

### Research opportunities that remain
1. Budget policy: let the AI choose a budget plan with the stress test as the stopping rule, and test whether that closes the
   gap to exhaustive.
2. Calibrated predictions: magnitude predictions with explicit tolerances, plus feedback on calibration.
3. Advice use: test whether presenting Level C advice as a measured hit rate per robot type changes decisions.
4. A larger held-out set (N = 40 detects only large effects).
5. Learning from investigation traces (which experiments were informative), as opposed to repair outcomes.

## 1. Why the previous AI architecture failed (S2–S4a, confirmatory S3)
The AI chose search-space allocations for an optimiser on robots with *unknown, mixed* causes. At the budgets used,
optimiser noise dominated, and a fixed rule that always co-designs the body won (S3: rule 19/48, AI 9/48). The AI's
decisions never had to be *right about a cause* to matter, and they never were checked against one.

## 2. New research design: diagnosis-dependent repair under realistic experiment costs
- **Fault benchmark.**
  - Start from verified walking robots: designs that achieved FULL_RECOVERY in earlier stages, giving many different
    morphologies.
  - Inject a single physical or control fault from a family of mechanisms that produce **similar symptoms**, for example
    several distinct causes of a forward fall.
  - Each fault has a matching repair tool, a low-dimensional subsystem. Repairing the right subsystem restores walking at
    a small budget; repairing the wrong one does not. This is checked per instance with a measured tool-confusion matrix.
  - The model never sees the fault label.
- **Instruments.**
  - Rich physics measurement: COM state, angular momentum, CoP, support margin, capture point, contact forces and
    transitions, slip, friction use, torque saturation, tracking error, swing clearance.
  - Counterfactual experiments: a small matched intervention, measured on the same seeds.
  - Repair: CMA-ES over a chosen subsystem.
  - Verification: `full_recovery_v1`, independent and never shown to any policy.
- **Experiment costs** are charged to one total budget, so the choice of experiments matters. Probing everything is
  possible but costs repair budget.
- **Policies compared over the same instruments:**
  - Nemotron scientist (closed loop; one-shot ablation);
  - a fixed exhaustive-screening procedure;
  - expert telemetry rules (hand-written thresholds);
  - random;
  - blind joint optimisation.
- **Experience.**
  - Level A: episodic memory of full investigations, successes and failures.
  - Level B: mechanism cards, each holding a failure signature, a cause, a repair, conditions and evidence counts, and
    marked as established physics, an empirical heuristic or an unconfirmed hypothesis.
  - Level C: a trained cause and repair-effect predictor from counterfactual outcomes. The target is real counterfactual
    repair effect, not a training-score delta.
  - Evaluation on held-out morphologies, with explicit negative-transfer cases (same symptom, different cause).

## 3. Falsifiable hypotheses (each tested separately; development first, then a registered held-out evaluation)
- **C1 (causal investigation):** Nemotron's final diagnosis matches the injected mechanism more often than chance and
  than the expert telemetry rules. Its experiment predictions are correct more often than chance.
- **C2 (closed-loop adaptation):** with experimental feedback, diagnosis accuracy and repair success exceed one-shot
  reasoning from the initial telemetry.
- **C3 (repair orchestration):** at an equal total budget, Nemotron-directed tool use yields more verified repairs, or the
  same repairs with fewer rollouts, than the fixed screening procedure.
- **C4 (knowledge transfer):** with episodic memory and mechanism cards built on training morphologies, held-out
  diagnosis and repair improve, and negative transfer (applying a remembered repair when the cause differs) stays below
  the rate of a naive "reuse the nearest episode's repair" policy.
- **C5 (trainable learning):** a model trained on counterfactual outcomes predicts the effective repair on held-out
  morphologies better than kNN retrieval and the expert rules, and helps the scientist when given as advice.

## 4. Execution log
- 2026-10-17: branch created; spend verified; S3 complete (see `docs/WALK_RECOVERY.md`).
- 2026-10-17: subagent routing verified (sonnet -> claude-sonnet-5-5, haiku -> claude-haiku-5-5). Healthy-base audit: 17-D verified walkers from S2/S2b (19 dev creatures) and S3 (28 creatures, held-out family for this benchmark); 15-D walkers from S4a (19 dev creatures).
- 2026-10-17: fault bench built on dev bases.
  - Severity 1.0: 41 of 192 candidates kept.
  - Mild severities 0.0/0.25: 27 of 144 kept (feedback_loss 10, posture_lean 8, cadence_fast 3, short_feet 2,
    weak_motors 2, slippery 2).
  - Files: `artifacts/vm/ce/ce/dev_*.jsonl`.
- 2026-10-17: **dev pilot1** (development only, not a claim): 13 instances × 6 policies, budget about 700 rollouts each.
  Results in `artifacts/vm/ce2/ce/pilot1_*` (`ce_analysis.py`).

  | policy | FULL / PARTIAL / NOT | rollouts | chose a repairing tool |
  |---|---|---|---|
  | exhaustive | 5 / 6 / 2 | — | 11/13 |
  | expert | 4 / 5 / 4 | — | — |
  | blind | 3 / 5 / 5 | — | — |
  | random | 3 / 7 / 3 | — | — |
  | scientist (closed loop) | 3 / 2 / 8 | 425 of about 690 | 4/13 |
  | scientist_1shot | 2 / 7 / 4 | — | 8/13 |

  - The closed-loop scientist was the weakest arm. It left about 40% of its budget unspent and its mean walking
    fraction was 0.27.
  - Its diagnosis matched the injected fault in only 1/13; prediction accuracy was 0.38 (n = 71) against a 1/3 chance
    level. Inference cost was $0.20.
  - The next development step is to find why it concludes or under-spends, and why its first repairs miss, before
    building experience levels. No evaluation instances were touched.
- 2026-10-17: **pilot1 audit** (`experiments/causal_engineer/dev/AUDIT_PILOT1.md`). Main causes:
  - interface defects ended 5/13 runs, which accounts for the unused budget;
  - hypotheses were never revised (0 status updates);
  - no healthy reference, and fall-direction signs were misread;
  - our prompt said "experiments are expensive";
  - the counterfactual catalogue was one-directional;
  - diagnosis is often non-identifiable (7/13 robots are repaired by 3–7 tools).
  The evidence itself is mostly sufficient: systematic counterfactuals rank a repairing tool first in 9/13.
- 2026-10-17: **scientist v2** (`causal_scientist_v2`):
  - reasoning-first reply: `result_reading`, required verdicts on scored hypotheses, new hypotheses, then the action;
  - parametric one- or two-parameter experiments;
  - KEY FACTS with signs in words, plus a healthy-reference range from 12 dev base robots (`physics_digest.py`);
  - neutral cost wording.
- 2026-10-17: **pilot2** (the same 13 dev instances, v2): see the table below.

  | arm | FULL / PARTIAL / NOT | chose a repairing tool | first repair repairs | diagnosis match | LLM $ |
  |---|---|---|---|---|---|
  | v2, thinking off | 3 / 4 / 6 | 4/13 | 3/13 | 1/13 | 0.48 |
  | v2, thinking on (`scientist_think`) | 4 / 6 / 3 | 9/13 | 7/13 | 5/13 | 1.05 |

  - Process change against v1: 96–99 status updates, 54–60 new hypotheses after step 1, 32–51 refutations (v1: 0 / 0 / 0).
  - Remaining problems:
    - under-spending: the thinking arm used 260 of 700 rollouts, with repair shares of 0.1–0.2;
    - prediction accuracy 0.29, below the always-`no_change` baseline of about 0.56, because most measured changes are
      within tolerance;
    - 0/3 feedback faults recovered.
  - Interpretation: development evidence only, on the same 13 instances as pilot1, so possibly tuned to them.
- 2026-10-17: **v2.1**:
  - the prompt states that unused rollouts have no value and that a repair's budget sets its number of CMA-ES generations;
  - the message shows the within-tolerance base rate;
  - limits raised to 12 predictions and 16 citations;
  - ×0.33 and ×3 experiment levels added.
- 2026-10-17: **Level A/B memory** (`experience_bank.py`, `ce_memory.py`):
  - one "probe" episode per training instance (initial observation, fixed-catalogue counterfactual responses, measured
    repair matrix; `scripts/ce_probe_dataset.py`, 165 instances, 5,600 rollouts), plus earlier investigations;
  - mechanism cards are rebuilt per robot;
  - development runs exclude the robot's own base.
- 2026-10-17: **Level C** (`repair_learner.py`, numpy only). Target: the measured repair matrix (walking ≥ 6/8 check seeds);
  12-fold leave-one-base-out; base-clustered bootstrap CIs (`experiments/causal_engineer/dev/LEVEL_C_LOBO.md`).

  | features | logistic | MLP ensemble | kNN | CF heuristic (exhaustive) | expert rules | prior |
  |---|---|---|---|---|---|---|
  | observation only | 0.59 | 0.54 | 0.56 | – | 0.39 | 0.39 |
  | observation + counterfactuals | 0.66 | 0.67 | 0.63 | 0.59 | 0.39 | 0.39 |

  (top-1 hit rate)
  - Learned beats the hand-made ranking: logistic minus CF heuristic +0.07 [0.02, 0.14].
  - Learned does NOT beat kNN retrieval: +0.03 [−0.06, 0.12]. Counterfactual information adds about 0.08 top-1.
  - The MLP ensemble spread carries no uncertainty signal (AUROC 0.55), so it is not used as uncertainty.
  - Shuffled-target controls sit near the prior.
  - Fix during this work: the fault-bench `features` field describes the creature before its S2 recovery, so it was replaced
    by the faulty robot's own body features everywhere (memory and Level C). The v0 results are kept as `*_v0_stale_features*`.
  - Runtime model: `level_c_logistic.json`. New `learned` policy: the exhaustive procedure with this ranking. New advice item for
    the scientist (observation-only model, labelled with its held-out accuracy).
- 2026-10-17: **held-out benchmark build** (`experiments/causal_engineer/heldout/BUILD_SPEC.md`, frozen before the build):
  28 S3 bases × 8 faults × {0.5, 1.0}, screen-first, on the batch VM.
- 2026-10-17: **pilot3** (a fresh dev subset of 16 instances, not in pilot1/2): `scientist_think`, `scientist_1shot_think`,
  `scientist_think_mem`, `exhaustive`, `expert`.

  | arm | FULL / PARTIAL / NOT | rollouts | chose a repairing tool |
  |---|---|---|---|
  | exhaustive | 9 / 5 / 2 | 687 | 14/16 |
  | `scientist_1shot_think` | 3 / 9 / 4 | 393 | 14/16 |
  | `scientist_think` | 2 / 8 / 6 | 298 | 13/16 |
  | `scientist_think_mem` | 2 / 9 / 5 | 300 | 13/16 |
  | expert | 2 / 9 / 5 | 690 | 11/16 |

  - Diagnosis:
    - Decision quality is close to exhaustive's, but the scientist concluded once its 4 training seeds walked and left
      more than half of the budget unused. Its designs then failed the 20 s confirmation.
    - Exhaustive spends everything on two 330-rollout optimisations, often with tools that do not match the fault.
  - Memory: the scientist judged retrieved items in both directions.
    - Episodes: 5 applies, 7 does_not_apply, 15 needs_adaptation, 3 test_first.
    - Cards: 6 applies, 6 does_not_apply, 1 needs_adaptation, 2 test_first.
  - Defect: pilot3's memory bank used the stale stored features, which affected 4 of 18 retrieval dimensions; fixed afterwards.
- 2026-10-17: **v2.2**: the prompt states the exact full_recovery_v1 criteria (pilot4).
- 2026-10-17: **v2.3**: a 20 s **stress-test** instrument (current best design on the visible obs seeds, 2 × n_obs rollouts,
  predicted walking count registered first, once per design), plus "N rollouts would stay unused" at decision time (pilot5).

  Paired results on the same 7 dev instances (FULL recoveries):

  | v2.1 | v2.2 | v2.3 | exhaustive |
  |---|---|---|---|
  | 0 | 1 | 3 | 5 |

  - The stress test was used in 6 of 7 episodes and changed decisions; for example, a prediction of 2 against a measured 4
    led it to conclude, and a measured 0 led it to repair further.
  - Development only; tuned on these instances.
- 2026-10-17: thinking arms raised to max_tokens 32,000 (three pilot5 steps were lost to `finish_reason=length`).
- 2026-10-17: **held-out evaluation registered** (`experiments/causal_engineer/heldout/PROTOCOL.md` + `protocol.json`): 40
  instances on 22 unseen bases, 8 arms, hypotheses C1–C5b with Holm correction.
- 2026-10-17: **security incident** (logged in `docs/memory/INCIDENTS.md`):
  - a CRLF `.env` sourced by bash put the API key into four dev result files on the VM; the files were deleted;
  - redaction and the record guards are fixed;
  - the owner should rotate the key.

## 5. Scientist loop specification (`creature_forge/scientist.py`, to be implemented on top of physics_probe + eng_tools)
Per faulty robot, one total budget (development default 700 rollouts). One Nemotron call per step, at most about 14 calls;
the model may conclude at any step.
- **State given to the model:**
  - Robot features against the reference body.
  - The initial `observe` summary, including the pre-fall block.
  - The hypothesis ledger (each hypothesis: mechanism text, causal chain, cited evidence paths, testable predictions,
    status open / supported / refuted / unresolved).
  - The experiment ledger (action, the model's pre-registered predictions, the measured outcome, deterministic
    prediction scoring).
  - Repairs tried with their training results; the remaining budget.
  - Memory items, only in the memory arms.
- **Actions** (exactly one per step):
  - `counterfactual(change)` with a prediction per open hypothesis: the sign of change of named quantities, chosen from
    a fixed quantity list such as walking_count, pre_fall.capture_margin, slip_frac or saturation_frac.ankle.
  - `observe_more`.
  - `repair(tool, budget_share)`, citing the hypothesis it acts on.
  - `conclude(diagnosis_category, explanation, final_design)`.
- **Diagnosis categories:** a neutral engineering taxonomy of failure mechanisms. It covers the 8 benchmark mechanisms
  plus decoys (insufficient joint stiffness, leg-length mismatch, gait-initiation failure) and "unresolved". The model
  is never told which categories are used by the benchmark.
- **Prediction scoring is deterministic:** observed sign versus predicted sign, with a noise tolerance. Hypotheses are
  updated by the model, and the record keeps whether the model's updates follow the evidence.
- **Baselines over the same Workbench:**
  - EXHAUSTIVE: every counterfactual, then repair the top-2 tools by counterfactual effect.
  - EXPERT_RULES: hand-written telemetry thresholds mapped to tools, then repair; written on dev data, disclosed.
  - RANDOM: random counterfactuals and tools.
  - BLIND: CMA over the union of all tools with the whole budget.
  - SCIENTIST_1SHOT: one call from the initial observation, then repair; tests C2.
- **Metrics:**
  - Verified repair (`full_recovery_v1` against the faulty robot).
  - Diagnosis accuracy against the injected mechanism (hidden).
  - Prediction accuracy.
  - Rollouts used and the number of experiments.
  - LLM calls, cost and wall time.
- 2026-10-17: physics_probe.py integrated (bit-identical dynamics; COM, angular momentum, CoP, support interval, capture point, friction use, saturation, tracking-error proxy, swing clearance; sanity values in the commit report). Finding: a healthy walker's capture point lies ahead of its support interval during normal stepping, so the useful instability signals are trends and pre-fall deltas against the walker's own baseline. Model quirk noted (not changed): torso box true mass = 0.6 x torso_mass.

## 6. Experience system specification (Levels A–C)
- **Supervision principle.** Experience comes from outcomes the system measured itself:
  - its investigations (hypotheses, predictions, experiment results, repairs, verification);
  - the repair matrices of training instances, i.e. which tools verifiably fixed which robots.
  Injected fault labels are used only for scoring diagnosis accuracy, never as training input to memory or the learner.
- **Level A — episodic memory** (`experience_bank.py`).
  - One record per finished investigation on a training instance: robot features, the observation signature (a
    standardised vector of selected physics keys), the hypothesis and experiment ledgers, repairs and outcomes, and
    verification.
  - Retrieval is kNN over the signature plus features. Each item returns its id, a short text and a distance.
- **Level B — mechanism cards.**
  - Clusters of training signatures, each with: the signature condition (feature ranges), per-tool verified repair
    rates, counter-examples where a tool failed, and support counts.
  - Nemotron writes the human-readable principle of each card. Its status is computed deterministically: `empirical
    heuristic` (≥ 3 supporting instances and > 70% repair rate), `hypothesis` (otherwise), or `established physics` only
    when the card restates a textbook relation (marked as such, with no discovery claim).
  - At use time the scientist must state for every retrieved card or episode: APPLIES, ADAPT, TEST-FIRST or REJECT.
- **Level C — learned repair-effect predictor.**
  - P(tool repairs | signature, features) for every tool, trained on the training instances' repair matrices.
  - Baselines: kNN matrix retrieval, expert rules, the global tool prior.
  - Evaluation on held-out bases (other morphologies) by top-k hit rate, and at the policy level as advice to the
    scientist and as a stand-alone "predict then repair" policy, at equal budget.
- **Negative transfer.** A memory-assisted decision that applies a remembered repair which then fails, where a
  different tool would have worked. It is counted per arm.

### Held-out run command (main VM, slot `ceh`, shard i of 16; add `--resume` to continue an interrupted shard)
```
cd ~/dev/ceh && CREATURE_FORGE_ENABLE_LIVE=1 CF_INFERENCE_LEDGER=$HOME/dev/ledger/inference_ledger.jsonl ~/dev/venvs/ceh/bin/python \
  scripts/ce_eval.py --instances <experiments/causal_engineer/heldout/instances/heldout_shard*.jsonl, comma-separated> \
  --instance-ids <protocol.json instance_ids> \
  --policies scientist_think,scientist_1shot_think,scientist_think_mem,scientist_think_mem_learned,exhaustive,learned,expert,random \
  --memory-probe artifacts/mem/probe_dev.jsonl --memory-episodes <artifacts/mem/pilot*_shard*.jsonl, comma-separated> \
  --learned-model experiments/causal_engineer/dev/level_c_logistic.json --budget 700 --workers 1 --shard i/16 \
  --out artifacts/ce/heldout_eval_shard$i.jsonl
```
The memory inputs in `artifacts/mem/` must match the SHA-256 values in `protocol.json`; this was verified before launch.

## Held-out evaluation, registered run (2026-10-17/18): see `experiments/causal_engineer/heldout/REPORT.md`
- **Valid (non-AI arms):** exhaustive 23/40, learned (Level C ranking) 18/40, random 12/40, expert 6/40 FULL recoveries on 40
  instances over 22 unseen morphologies. C5a (learned > exhaustive) is not supported: 1 vs 6 discordant, p = 0.99. Level C's
  better dev ranking did not become better verified repairs on unseen robots.
- **Invalid (AI arms):** the API key was rotated 50 minutes into the run, on the operator's advice. Every later model call
  returned HTTP 401, so C1–C4 and C5b measure the outage and are uninterpretable; they are reported as registered.
- **Pending the owner's decision:** amendment 1, re-running only the four AI arms with the new key and the same frozen inputs
  (post-hoc, labelled as such). The runner now checks the key before starting and fails fast on authentication errors.
