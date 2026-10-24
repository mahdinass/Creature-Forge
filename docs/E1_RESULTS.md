# E-1 results: physics-grounded investigation vs exhaustive repair on sealed held-out damage

**Study:** registered 2026-10-24 (`docs/E1_PROTOCOL.md`, registration commit `494ed9b`). Run on the batch VM from
13:53 to 17:18 UTC on 2026-10-24.

**Evidence:**
- `experiments/e1/final/e1_final.tgz`, sha256 `8ebaceb4dcaa22129e5706d7b46dff1a0f78fff1893d73cfa39084ba58d7cf73`. It holds
  the build, all arm records, the registered analysis and G-R2.
- Inner manifest `analysis/SHA256SUMS`: 7 of 7 entries verified after the pull.
- The registered analysis output is `analysis/e1_results.json` (sha256 `f474021f…`).
- Post-hoc descriptives (§5) are in `experiments/e1/final/E1_DESCRIPTIVE.json`, from `scripts/e1_descriptive.py`.

## 1. Verdicts (registered analysis, unchanged)

| hypothesis | contrast | FULL | discordant | exact one-sided p | base-clustered sign-flip p | verdict |
|---|---|---|---|---|---|---|
| **H-E1 (primary)** | A1 engine > A0 exhaustive | 56 vs 46 of 160 | 22 vs 12 | **0.061** | 0.056 | **not rejected at α = 0.05** |
| H-E2 (secondary, Holm) | A1 engine > K0n engine without diagnosis | 56 vs 42 | 26 vs 12 | **0.0168** (Holm(2)-adjusted 0.034) | 0.022 | meets the **registered secondary** criterion; **not a study-wide confirmatory claim** (see §1.1) |
| H-E3 (secondary, Holm) | K0n > A0 | 42 vs 46 | 17 vs 21 | 0.79 | 0.78 | not rejected |

**Completeness and ITT.** 160 of 160 records per arm; nothing missing, no errored episode, no re-run. The registered
recovery procedure was never needed.

**In words:**
1. On 160 robots with hidden damage, all on morphologies never used in development and two thirds from mechanisms never
   used in development, the engine recovered more robots than exhaustive search at the same plant budget. The difference
   (+6.3 points) is not statistically significant at the registered level.
   - Per the registered wording, this is **no evidence that the engine beats exhaustive search on sealed held-out damage**.
   - It is not a falsification: the point estimate favours the engine, and p = 0.061.
2. **The diagnosis ablation is the strongest signal, with a qualification.** It is the only contrast that meets a registered
   criterion. That criterion is the secondary-family Holm correction, not a study-wide correction (§1.1).
   - With the same repair machinery and the same plant and twin budgets, switching diagnosis off costs 14 recoveries
     (56 → 42; discordant 26 vs 12).
   - Without diagnosis, the twin-robust repair is no better than model-free exhaustive search (42 vs 46).
3. If this holds up, it reverses the dev-based expectation recorded in the MKV studies ("structure knowledge adds little; the
   ensemble-robust pipeline compensates"). On unseen damage, the advantage comes from investigating the cause, not from the
   extra simulation compute.

### 1.1 Multiplicity and sidedness (correction added 2026-10-25, after an owner review; frozen data and analysis unchanged)

**What the registration fixed.** Registration commit `494ed9b` (`docs/E1_PROTOCOL.md` §3 and `protocol.json`
`hypotheses`) fixed:
- **H-E1:** one primary test, exact **one-sided** McNemar, α = 0.05;
- **H-E2 and H-E3:** a **separate secondary family**, Holm over **two**, α = 0.05.

It specified **no gatekeeping** between the primary and the secondary family.

**Exact values** (independently recomputed; equal to `e1_results.json`):

| test | discordant | one-sided p | two-sided p |
|---|---|---|---|
| H-E1 | 22 vs 12 | 0.060725 | 0.121449 |
| H-E2 | 26 vs 12 | 0.016776 | 0.033552 |
| H-E3 | 17 vs 21 | 0.791154 | 0.627103 |

**Under the registered rule:**
- H-E2's Holm(2)-adjusted p is 0.0336 ≤ 0.05, so the registered secondary criterion is met.
- H-E3 (0.791) is not.

**Why this is not a confirmatory claim.** No rule linked the secondaries to the primary, so the family-wise error over all
three registered tests is **not** controlled at 0.05. The primary family and the secondary family each spend α = 0.05.
- Under a Holm correction over all three tests, the adjusted p values are 0.0503, 0.121 and 0.791. That correction was not
  registered and is used here only as a sensitivity reading. Nothing is rejected under it.
- H-E2 is therefore reported as **supportive evidence that met the registered secondary criterion but is not significant
  at the study-wide level**. It is not reported as a confirmed effect.
- The family has not been changed after seeing the results. Both readings are reported.
- An earlier version of this report and of the session summary said H-E2 was "rejected (Holm)" and "significant" without
  this qualification. That wording is withdrawn.

## 2. Three-arm comparison: effect sizes and uncertainty (descriptive intervals; post hoc)

| arm | FULL | rate (Wilson 95 %) | PARTIAL | NOT | mean validation walking fraction | mean plant used | mean twin used |
|---|---|---|---|---|---|---|---|
| A0 exhaustive | 46 | 0.288 (0.223–0.362) | 42 | 72 | 0.577 | 690 | 0 |
| A1 engine | 56 | 0.350 (0.280–0.427) | 43 | 61 | 0.651 | 620 | 2,012 |
| K0n engine, no diagnosis | 42 | 0.263 (0.200–0.336) | 53 | 65 | 0.594 | 653 | 1,532 |

| contrast | risk difference | 95 % Newcombe (paired) | 95 % cluster bootstrap (90 bases) | conditional OR (exact 95 %) | walking-fraction difference (better / worse / tied) |
|---|---|---|---|---|---|
| A1 − A0 | +0.063 | −0.008 to +0.133 | −0.006 to +0.131 | 1.83 (0.87–4.06) | +0.073 (72 / 37 / 51) |
| A1 − K0n | +0.088 | +0.013 to +0.161 | +0.012 to +0.164 | 2.17 (1.06–4.71) | +0.057 (76 / 40 / 44) |
| K0n − A0 | −0.025 | −0.100 to +0.050 | −0.103 to +0.053 | 0.81 (0.40–1.61) | +0.016 (59 / 61 / 40) |

**Reading the intervals:**
- The A1 − A0 interval straddles 0 by a hair. A true effect anywhere from none to about +13 points is compatible with the
  data.
- The continuous outcome (validation walking fraction) favours A1 over A0 in 72 vs 37 instances. This is descriptive, not
  a registered test.

**Compute.** A1 used about 70 fewer plant rollouts than A0 on average. It also used about 2,000 twin (simulation)
rollouts, and about 3.7× A0's wall time (302 s vs 82 s per episode on the batch VM).

**Shrinkage from development.**
- Fresh dev bases: A1c5 109 vs A0 62 of 211, i.e. 52 % vs 29 %, +22 points, discordant 61:14.
- Sealed test side: 35 % vs 29 %, +6 points.
- Even the **dev families on unseen test bases** shrank: 26 vs 23 of 54.
- So much of the development effect did not transfer to the other side of the morphology split. The dev advantage was
  partly tuning to the dev bases.

## 3. Strata (descriptive)

| group | n | A0 | A1 | K0n | A1-only vs A0 | A0-only vs A1 |
|---|---|---|---|---|---|---|
| dev families on unseen bases | 54 | 23 | 26 | 17 | 9 | 6 |
| sealed single mechanisms | 54 | 7 | 9 | 9 | 3 | 1 |
| sealed compositions | 52 | 16 | 21 | 16 | 10 | 5 |

Per stratum (FULL A0 / A1 / K0n; n):
- **Sealed singles:**
  - sensor_latency: 0 / 1 / 3 (18);
  - joint_damping_wear: 4 / 3 / 3 (18);
  - leg_asymmetry: 3 / 5 / 3 (18).
- **Sealed compositions:**
  - payload+actuator: 5 / 9 / 8 (13);
  - friction+clock: 0 / 2 / 1 (13);
  - pitch bias+short feet: 5 / 4 / 2 (13);
  - heavy torso+feedback: 6 / 6 / 5 (13).
- **Dev families on unseen bases** (n = 6 each): A1 is ahead on heavy_torso 5 vs 3 and one_side_weakness 3 vs 1, and
  behind on payload_offset 2 vs 5.
- Per-stratum counts are too small for inference.

## 4. Failure cases, negative transfer and what limits recovery

1. **Diagnosis is right but the repair fails: the main failure mode on unseen mechanisms.**
   - **Sensor latency:** the engine named a sensor delay in 13 of 18 instances (exact target in 6), yet recovered 1 of 18.
     Without diagnosis it recovered 3, and exhaustive search recovered none.
   - **Joint damping wear:** the exact structure was identified in 16 of 18, but only 3 were recovered.
   - The repair toolset (CMA over controller and body subspaces) cannot compensate these mechanisms within budget.
   - The sealed-family design note says sensor latency needs **lower** gains, the opposite of its dev twin, feedback-gain
     loss. That is exactly where knowledge from development points the wrong way.
2. **Negative transfer (A0 recovered, A1 did not): 12 instances.** These are the cases where the engine's reasoning was a
   liability, not just insufficient.
   - **The diagnosis was wrong in 5:**
     - payload offset ×1.3 and short feet ×1.7, both read as pitch-sensor bias;
     - feedback-gain loss, read as ankle damping;
     - two compositions, read as placement gain and as knee actuator strength.
   - **It was correct, or correct on one component, in 7:**
     - payload offset ×1.0 twice;
     - clock fault;
     - joint damping wear;
     - payload+actuator (payload named);
     - pitch bias+short feet twice (pitch bias named).

     In these cases the diagnosis-directed repair still did worse than exhaustive search.
   - So the losses come from two sources. A wrong diagnosis locks the repair onto the wrong subspace. A correct but
     incomplete or "right but not repairable this way" diagnosis narrows the search too early. The exhaustive procedure,
     which tries every tool, is immune to both.
3. **Compositions** are where diagnosis pays most (A1-only 10 vs A0-only 5). This is despite the engine's single-structure
   MAP never matching both components. A partial explanation is still useful for the repair.
4. **Hard ceiling.**
   - No arm recovered 84 of the 160 instances; the union of all arms recovered 76 (47.5 %).
   - Low friction and the friction+clock composition stay almost unsolved (≤ 2 of 19 in every arm), as on dev.
   - Search failure at this budget is not physical impossibility.
5. **Calibration of the dev stop map** on the test side was not registered and is not assessed here.

## 5. Does experience learning deliver a measurable improvement?

**Not demonstrated, and E-1 does not test it directly.** E-1 has no arm that learns from earlier episodes. The engine's
dev-calibrated settings and its stop map are development artefacts, not online learning. Every direct test of experience
in the programme is null:
- memory evaluation, 16 Oct;
- causal-engineer memory: 16 vs 14;
- Stage 2: memory used once in 36 episodes; learned posterior 12 vs 14;
- DS-1: experience 10 vs 8, p = 0.31; updating vs frozen 7 vs 7;
- P0: INSUFFICIENT-DATA.

**What E-1 adds to that question:**
1. **Development "experience" transferred only partly.** The engine's dev advantage (+22 points) fell to +6 points on unseen
   morphologies and mechanisms.
2. **Experience priors were aimed at the wrong bottleneck.** All earlier experience mechanisms improve *identification*.
   E-1 shows identification is largely solved on unseen mechanisms (sensor delay and damping are named correctly), while
   *repair given the diagnosis* is the binding constraint. That explains why experience has never measurably helped:
   identification was not the bottleneck.
3. **The evidence suggests a different target for learning from experience,** where it can matter: which repair works for
   a given diagnosed mechanism, learned from verified outcomes. Negative transfer, as in the dev-twin trap for sensor
   latency, has to be detected the same way.

## 6. Limitations

- **One generator family** (hdb-v1 walkers). The twin uses the same simulator and damage DSL as the plant; only the reality
  gap is hidden.
- **The primary test missed α = 0.05.** The exact one-sided McNemar is slightly conservative (discrete). The registered
  verdict stands as "not rejected".
- **Base clustering.** 160 instances sit on 90 bases (at most 2 per base). The base-clustered sensitivity analyses agree
  with the instance-level tests.
- **Strata sizes** are small; every per-stratum statement in this report is descriptive.
- **Everything in §2–§5 beyond the registered table is post hoc** (`scripts/e1_descriptive.py`, written after the results).
  This includes intervals, odds ratios, walking-fraction differences, strata, diagnosis accuracy and the failure analysis.
- **Simulation only.** There is no real-robot validation.
- **No LLM arm.** Nothing here is credited to Nemotron.

## 7. Deviations and operational notes (transparency)

- **Methodology:** no deviation. Code, settings, seeds, sample and analysis are exactly as registered. The tree hash on
  the VM equals registration commit `494ed9b`.
- **Gates:**
  - G-R (main VM) PASS;
  - G-R2 (batch VM) PASS;
  - G-O PASS (live test: VM self-stop through the API → STOPPED in 47 s);
  - G-T PASS;
  - G-B PASS (all 160 quotas met; 280 candidates evaluated, physics only);
  - G-C PASS (160 of 160 per arm).
- **Operations:**
  - The local progress poller was terminated by Claude Code because the laptop was low on memory. The run was unaffected.
  - A VM-side finisher was added during the run (operational only). It ran the registered analysis after `ARMS_DONE` and
    then brought the VM deadline forward, so the VM stopped itself through the API at 17:20:55 UTC.
  - While checking progress I saw a few per-episode status lines in shard logs. Nothing was changed as a result.
- **Ledger.** The batch stop is booked conservatively at the first watchdog STOPPED observation (17:27:34 UTC). The actual
  API stop was requested at 17:20:55 UTC (`experiments/e1/final/selfstop.log`).

## 8. Cost and VM states

**Cost:**

| item | infra ledger (conservative) |
|---|---|
| before today's work (morning) | $92.977 |
| G-R on the main VM | +$0.42 |
| G-O test, G-R2, build, three arms, finisher, pull (batch VM) | +$8.43 |
| **after E-1** | **$101.823** (cap $120) |

- Today's total is **$8.85**, well below the $18–23 projection: the batch VM ran about 4 h, not 7–9 h.
- Estimated remaining Cloud credit is ≈ $37.49 − $8.85 ≈ **$28.6**; please confirm in the console.
- Token Factory: $0 used.
- **VM states:** both VMs STOPPED, verified on the control plane at the end of the session (§9).
- The boot disks keep accruing about $0.23 a day for both.

## 9. Recommendation for the next milestone

1. **Submission (deadline 30 Oct) can now claim, honestly:**
   - The primary result is inconclusive: the engine recovered 56 of 160 robots against 46 for exhaustive search, with
     p = 0.061 one-sided.
   - In a registered ablation, switching the diagnosis off lowered recoveries from 56 to 42. This met the pre-specified
     secondary criterion (Holm over two secondaries, adjusted p = 0.034), but the study-wide correction is borderline
     (0.050). It is supportive evidence, not a confirmed effect.

   See `docs/submission/` (rc2) for the exact wording.
   - **Proposed:** a `v1.0.0-rc2` PR with one README/Devpost paragraph and one narration line. The owner reviews the wording.
2. **Next research milestone: diagnosis-conditioned repair, learned from verified outcomes.** This is the target where
   experience can matter.
   - Build a mechanism → repair-strategy memory from verified dev episodes: direction, subspace and the tools that worked
     or failed per diagnosed structure, with negative examples.
   - Add the missing repair capabilities that E-1 exposed: latency compensation or gain reduction, and damping
     compensation.
   - Test on fresh dev instances first (no claim). Then register a confirmatory study on the sealed reserve, which still
     holds the complement of the 160 spent ids, together with the Nemotron A3 arm.
   - The primary should be "memory-conditioned repair > the same engine without memory", compute-matched.
3. **Do not run the P0.5 campaign** in its current form (SV1 power analysis).
