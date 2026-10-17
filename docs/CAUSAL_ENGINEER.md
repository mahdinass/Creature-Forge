# Creature Forge Causal Engineer — architecture, hypotheses and execution log

Branch `feature/causal-engineer` (from `feature/walk-recovery` @ `f96b9d9`). Owner directive 2026-10-17: build an
autonomous, physics-grounded AI engineering scientist. Nemotron is the reasoning brain; MuJoCo, optimisers and physics
analysis are its instruments; independent verification stays authoritative.

Budgets (verified 2026-10-17):
- **Infra:** $26.77 of the $35 approved cap (conservative ledger). About $2 is reserved for the demo, so about $6 is
  usable: roughly 22 h on the 8-vCPU main VM, or about 3 h on the batch VM.
- **Inference:** $3.67 of $15 (958 requests).
- No new paid services.

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
  `scientist_think_mem`, `exhaustive`, `expert`. Results pending.
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
