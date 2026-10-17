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
