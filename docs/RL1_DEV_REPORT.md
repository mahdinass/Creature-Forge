# RL-1 development result: repair learning from verified outcomes (dev only; 2026-10-24)

**Plan:** `docs/RL1_PLAN.md`, committed at `9fbcb38` before the matrix was read; gate G-RL1 was fixed there.

**Result: gate G-RL1 FAILED.** As pre-declared, RL-1 v1 is reported as a null on dev and is **not run online**. E-2 as
planned (RL-1 vs A1 on a fresh cohort) is **not recommended**.

## 1. Data

**The dev repair response matrix** (`scripts/rl1_matrix.py`):
- 211 fresh-dev instances × all 10 tools = **2,110 cells**, with no errors and no refusals;
- each cell is a plant-only CMA repair at 300 rollouts (4 train seeds) from the nominal design, followed by independent
  verification (`full_recovery_v1`);
- archive `experiments/causal_engineer/dev/rl1/rl1_matrix.tgz`, sha256 `9b740a94…` (inner `SHA256SUMS` verified);
- cost about $4.9 on the batch VM, which stopped itself through the API when done.

**Context** for each instance comes from the stored A1c5 record: diagnosis, twin evidence, observation and morphology.

**What the matrix shows:**
- **Per-tool verified success** across instances: leg_length 59, placement 55, torso_mass 55, feedback 52, timing 48,
  posture 38, foot_length 31, stride 22, torque_limit 21, foot_friction 0 (of 211).
- **Some tool verifies on 130 of 211 instances (61.6 %).** For comparison, the stored full-pipeline results are A1c5 109
  and A0 62.
- **81 of 211 (38 %) have no single tool that verifies at this budget.** This capability limit is the largest one (for
  example, low ground friction: 1 of 17).

## 2. Registered-in-plan offline evaluation (`scripts/rl1_offline.py`; nested, so hyper-parameters are chosen on inner folds only)

**Metric:** the matrix success of each policy's ordered top-2 tools.

| policy | LOFO (unfamiliar mechanism) | LOBO (unfamiliar morphology) |
|---|---|---|
| P-eng: the engine's twin ranking (A1, no memory) | **0.521** | 0.521 |
| P-probe: A0's plant-probe ranking | 0.450 | 0.450 |
| P-mem0: simple memory (5 nearest past cases) | 0.450 | 0.436 |
| **P-RL1** (calibrated memory + twin evidence, abstain / commit / hedge) | **0.512** | 0.502 |
| oracle (any tool) | 0.616 | 0.616 |

| contrast (LOFO) | difference | base-cluster bootstrap 90 % |
|---|---|---|
| P-RL1 − P-eng | −0.009 | [−0.029, +0.009] |
| P-mem0 − P-eng | −0.071 | [−0.107, −0.037] |
| P-probe − P-eng | −0.071 | [−0.121, −0.023] |

**Gate G-RL1:**

| criterion | result |
|---|---|
| (1) lower 90 % bound of P-RL1 − P-eng > 0 | **failed** |
| (2) no family worse than −0.15 | passed (worst: short_feet −0.13) |
| (3) P-RL1 ≥ P-mem0 | passed |

**→ FAIL.**

**What RL-1 did:**
- Decision modes under LOFO: commit 125, hedge 24, abstain 62.
- Its probabilities carry real but modest predictive information: Brier 0.1225 vs 0.1404 for per-tool base rates.
- That information does not improve decisions over the engine's instance-specific twin simulation.
- Per family (LOFO, top-2):
  - gains on feedback_gain_loss (+0.06) and one_side_weakness (+0.03);
  - losses on short_feet (−0.13) and pitch_sensor_bias (−0.06);
  - ties elsewhere.

## 3. Exploratory analysis (post hoc, after the gate failed; no claim; `scripts/rl1_explore.py`, `explore_v1.json`)

1. **Headroom is scattered, not systematic.**
   - In 20 instances the engine's top-2 fails while some tool verifies. The first working tool sits at engine rank 2, 3,
     4 or 6 (4–5 cases each), or at rank 5 or 9.
   - Engine top-k success: k = 1: 0.370, k = 2: 0.521, k = 3: 0.540, k = 4: 0.559, k = 10: 0.616.
   - No simple rule (for example, "try a third tool") recovers much of it.
2. **Memory does not help a twin-free engineer either, and it can mislead.**
   - Adding the same memory to A0's plant-probe ranking (LOFO, fixed hyper-parameters, no tuning) *lowers* top-2 success
     from 0.450 to 0.403 (0 wins, 10 losses). Clock fault, for example, falls from 0.50 to 0.27.
   - Repair experience from other mechanism families transferred negatively. Apparent physical similarity misled the
     choice.
3. **Why the twin is hard to beat in dev.**
   - On dev families the engine's hypothesis library contains every mechanism kind, so its twin simulation of each tool
     is instance-specific and well-specified.
   - Population-level experience is weaker evidence than simulating the robot at hand, as DS-1's R-head also found.
   - That was under missing-not-at-random data; this matrix removes that excuse.
   - Leave-one-family-out removes the family from memory, not from the twin's library. So dev cannot reproduce E-1's
     regime, where the diagnosis was right but twin-guided repair still failed.

## 4. What this means for the research question

**"Can Creature Forge use previous failures and successes to select better physical interventions on unfamiliar
problems?"**

On dev, with complete counterfactual data and nested validation, **no**:
- learned repair memory does not improve on the engine's simulate-the-robot-at-hand tool selection;
- added to a twin-free engineer, it hurts.

This is the third independent null for experience in this programme. The first two were DS-1's R-head and the Stage 2
dossiers. The first two were limited by data, but this one is not, which makes it the strongest.

**The binding constraints on dev are:**
1. **capability:** 38 % of instances have no single tool that works within budget;
2. **a scattered residual:** ≈ 10 points of tool-choice headroom.

Neither is the kind of regularity that cross-robot experience captures well.

## 5. Recommendation

- **Do not spend the fresh cohort on RL-1 vs A1.** The expected result is a null.
- **Strongest feasible registered experiment before the deadline: E-2R.** It confirms or refutes E-1's diagnosis
  finding on fully independent problems. This changes E-2's hypothesis, so it needs the owner's decision.
  - **Population:** a fresh hdb-v2 cohort, morphology-independent, crossed with the HF2 mechanisms defined before any
    result, mechanism-independent.
  - **Arms:** A1 vs K0n vs A0, at equal plant budgets.
  - **Primary:** A1 > K0n, the diagnosis ablation. **Secondary:** A1 > A0, tested only if the primary rejects
    (fixed-sequence gatekeeping).
  - **Exploratory:** a Nemotron arm.
  - **Cost:** about $3 for the cohort plus about $9 for the run, within the remaining credit of about $23.
  - **Outcome:** a confirmatory answer to whether investigating the physical cause selects better interventions on
    unfamiliar problems.
- **Experience learning, next (after the deadline): target the capability gap, not the ranking.** Learn from verified
  outcomes which *combinations* of intervention parameters work, a multi-tool repair space. Alternatively, test memory
  where the twin is known to be wrong, using twin-plant disagreement as the trigger. Each needs a new dev design.
