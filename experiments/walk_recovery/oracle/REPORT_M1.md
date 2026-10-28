# M1: controller recoverability on the 12-creature development panel — G1 report (development data)

**Registration.**
- Protocol `protocol_m1.json` (`walkrec-oracle-m1-v1`, sha256 `252f0038…`) was committed in `7df398f`/`66a228f` before any
  M1 run.
- The analysis script `scripts/walk_m1_analysis.py` was committed in `c5635fb` before the results were complete.

**Execution.**
- One execution, on the temporary 64-vCPU batch VM (slot `m1`, snapshot `b6825a0` = `66a228f` with a clean tree), in
  12 shards with one creature each.
- 108/108 units completed, every shard exited 0, nothing was rerun.
- Rollouts: 734,700 of the 850,000 cap. Infra about $5.50 for this stage; $10.51 cumulative of the $20 cap.

**Records.** `results/m1/` (`shard*.jsonl`, `panel.json`, `summary.json`, `analysis_output.txt`, SHA-256 `MANIFEST.json`).

This is development data. It decides gate G1 and the design of the next stage, and it is never confirmatory evidence.

## Panel
- 4 named development creatures: stilts-drawn, tiny-feet (guided version), top-heavy (guided version) and weak-slippery.
- 8 generated guided bodies (`walkrec-dev-m1-gen-*`, 13 draws, all recorded in `panel.json`).
- Leg lengths range from 0.45 to 1.10 m, with torque authority 0.12–2.3.
- Every creature walks on **0/24** validation seeds with the transferred R2 controller (`c0_r2`: 12/12 NOT_RECOVERED).

## Criteria
`full_recovery_v1`, unchanged. FULL_RECOVERY requires all of:
- ≥ 80% walking on 24 held-out seeds under perturbation/friction variation;
- `verdict_v1` VERIFIED against the original;
- a 20 s confirmation on 24 further seeds.

## Main table
Final checkpoint (8k; H7 at 4k). Each cell shows status and validation walking fraction, replicate 1 / replicate 2.
(`analysis_output.txt` has the exact table.)

| creature | ctrl15 | ctrl17 (foot placement) | joint17 | joint15 |
|---|---|---|---|---|
| stilts-drawn | PART .71 / NOT .50 | NOT .00 / PART .67 | **FULL 1.00** / PART .83 | **FULL .83** |
| tiny-feet | PART .46 / NOT .38 | NOT .42 / PART .50 | PART .62 / PART .62 | PART .71 |
| gen-0006 | NOT .79 / NOT .62 | NOT .58 / PART .83 | PART .83 / NOT .96 | NOT .88 |
| gen-0007 | PART .58 / PART .50 | PART .79 / **FULL .88** | **FULL 1.00** / PART .75 | **FULL .96** |
| top-heavy | PART .62 / PART .58 | PART .58 / **FULL .96** | PART .54 / PART .75 | PART .75 |
| weak-slippery | PART .75 / PART .54 | PART .46 / PART .67 | PART .92 / **FULL .96** | PART .58 |
| gen-0000 | PART .79 / NOT .50 | PART .83 / **FULL .92** | PART .88 / **FULL .96** | PART .79 |
| gen-0001 | PART .75 / PART .67 | PART .92 / PART .79 | PART .83 / PART .79 | PART .79 |
| gen-0002 | **FULL .92 / FULL .92** | **FULL .92** / PART .96 | **FULL 1.00 / FULL .96** | **FULL .92** |
| gen-0003 | NOT .00 / PART .33 | NOT .00 / NOT .42 | **FULL 1.00 / FULL .96** | **FULL 1.00** |
| gen-0004 | PART .71 / PART .67 | **FULL .96** / PART .83 | NOT .54 / PART .75 | PART .71 |
| gen-0005 | PART .50 / NOT .29 | PART .71 / NOT .46 | PART .67 / PART .58 | PART .58 |

Creatures fully recovered at the final checkpoint (any replicate):

| condition | recovered |
|---|---|
| ctrl15 | **1/12** |
| ctrl17 | **5/12** |
| joint17 | **6/12** |
| joint15 | **4/12** (1 replicate) |
| union of conditions | 8/12 |
| any condition, any checkpoint | 10/12 |
| H7 (3 nominal seeds) | 0/12 |

## G1 decision (pre-declared rule)
The best single condition, **joint17, fully recovers 6/12 = 50%** of the development creatures at 8k.

**G1 = PROCEED**: the representation (with foot placement) can make most failing bodies walk. Two qualifications:
- The result sits exactly on the 50% line.
- Recovery is stochastic: replicate agreement is only 2/2 on 2 of the 6 creatures.

The architecture now routes per plan §B. Body+controller co-design with the foot-placement controller is the strongest
family, so the AI's room is choosing **what to change and where to spend a fixed budget**, at a budget where blind
search succeeds only part of the time.

## Findings
1. **Foot-placement feedback (H3) is the largest single gain.** ctrl17 recovered 5/12 against ctrl15's 1/12 (paired by
   creature: better on 5, worse on 1). joint17 recovered 6/12 against joint15's 4/12 (better on 3, worse on 0).
   - The 15-D controller family lacks a balance mechanism that many bodies need.
   - This supports the diagnosis from the stilts gait features (forward runaway, foot landing behind the capture point).
2. **Co-design helps (H4).** joint15 beat ctrl15 on 3 creatures and was worse on 0. Some creatures (gen-0003, stilts)
   recover only when the body changes too.
3. **Search is noisy at this budget.** Replicates of the same condition often disagree (FULL vs PARTIAL). A single
   optimisation run is weak evidence, which matters for the confirmatory design.
4. **Overfitting to the training seeds is real.**
   - More budget does not help monotonically: joint17 had 10 FULL replicate-runs at 4k but 8 at 8k.
   - The median train-minus-validation walking-fraction gap is +0.21 (max +0.75).
   - **Implication:** select the final candidate on separate screening seeds (now built into `walk_pipelines`) rather
     than by training score.
5. **The old adaptation protocol generalises worse (H7).** Training on 3 nominal seeds was worse at 4k than 8 varied
   seeds on 9 of 12 creatures, and recovered none.
6. **Not recovered within 8k by any final-checkpoint condition**, under either representation: tiny-feet, gen-0001,
   gen-0005, gen-0006.
   - Their walking fractions reached 0.62–0.96, so they are close to the threshold, not hopeless.
   - Nothing here shows they cannot be recovered.
7. **Dynamic-similarity transfer** (M1a) never helped.

## Consequences for M2 (to be decided before the dev pilot, recorded in DECISIONS)
- All methods use the 17-D foot-placement family and may co-design the body (4 parameters, edit-rule box).
- Final selection uses held-out screening seeds.
- The primary budget R\* is chosen on the method pilot with the pre-declared rule: the smallest budget where the best
  non-AI method fully recovers 25–60% of dev creatures. M1 suggests R\* is around 2–4k for joint17-like search.
- Diagnosis ground truth for H6 is still to be produced: which subspace probes lead to recovery, per creature.
- Recovery variance means the confirmatory study should use paired seeds and noise streams across methods, and a panel
  large enough for a McNemar test on binary recovery. The plan's N = 36 is kept.
