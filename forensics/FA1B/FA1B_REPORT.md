# FA-1B: Implementation and metric correctness audit (read-only)

**Date:** 2026-10-20
**Implementation:** `feature/has-scientist` @ `ea9e7291e8b7`
**Forensic base:** FA-1 @ `16f174d98ea6`
**Mode:** static source reading plus offline processing of stored development records. No simulation, no paid call, no
cloud, no sealed or held-out data, no repository change.

**Evidence labels:** **[V]** directly verified · **[R]** reported (FA-1, not regenerated) · **[I]** interpretation ·
**[H]** hypothesis · **[U]** unknown.

---

## 1. Executive findings

1. **The verification paths measure the same physics. The losses are not a condition mismatch.** **[V]**
   - Plant CMA, robustness checks, robust-seed displacement evidence and final validation/confirmation all share the plant,
     the per-seed condition generator, the friction semantics, the walking criteria and the score rule (`metric_path_matrix.csv`).
   - Robust-seed displacement status already predicts the final verdict: WORSE→WORSE 15/16 and VERIFIED→VERIFIED 59/61.
   - Displacement-only failures were therefore *measured as failing before submission* and submitted because nothing better
     was found.
   - Final per-seed validation data were discarded at serialisation and cannot be recovered without simulation.
2. **A new, concrete displacement-failure mechanism.** **[V]** for the facts, **[I]** for the mechanism.
   - Walking gates scale with the *evaluated* body's leg length, while the displacement clause is absolute.
   - 12 submitted designs shortened their legs to ≤ ×0.85 (5 instances). **None verified**; 11 of the 12 are displacement-only
     failures.
   - The walking-count-first CMA objective can satisfy "walking" by shrinking the body's own yardstick.
3. **Tool-screen exclusion is real, prevalent and never compensated in engine arms. Its recovery impact is unknown.** **[V]**
   - `foot_friction` is absent from 87/138 complete screens (23/36 instances, 10 bases). `torque_limit` is absent from 47
     (12 instances).
   - In every absent case the tool remained *executable* (non-empty CMA interval) but was never optimised through any path in
     dev-eval-2.
   - All 20 single low-friction arm-episodes are affected.
   - A pure-arithmetic bound says the legal friction range can reach the base controller's walking regime in 3–4 of those 5
     instances **[I]**. A stream case shows that reaching it is not sufficient.
4. **The twin-exhaustion partial update is a reachable, confirmed defect with negligible measured impact. A related display
   defect misinforms Nemotron.** **[V]**
   - 4/144 episodes are affected, all A3v5.
   - Exactly one partial update occurred (3 particles updated, the stale leader kept its advantage, same structure).
   - In three episodes, registration scored 0 particles; those plant experiments were silently discarded by inference.
   - In all four, the unscored experiments were shown to Nemotron as **"fits"**: 7 experiments, 26 prompt instances.
5. **FA-1 overstated two of its central claims.** **[V]**
   - **"Correct diagnosis does not help"** is a between-instance (Simpson-type) artefact. Holding the instance fixed,
     correct-diagnosis episodes did better in 3 and worse in 0 of 10 informative instances.
   - **"Feedback arithmetic is correct"** is not supported by the replay. It cannot verify the update (identical-count pairs
     shift by up to 2.26 nats because of within-structure heterogeneity).
   - The deterministic reachability count falls from 67 to **40**/183. Nemotron could act on 7, and 0 are demonstrated to have
     changed an action.

## 2. Source verification

- **Repository:** at start and end, `git rev-parse HEAD = ea9e729…`, branch `feature/has-scientist`, `git status --porcelain`
  empty. No checkout, reset or write.
- **FA-1:** read from the original local directory and the forensic worktree (HEAD `16f174d`, clean). The four FA-1 CSVs used
  are byte-identical to `git show 16f174d:forensics/FA1/…`. Neither location was modified.
- **Records** (checksums in `FA1B_MANIFEST.json`):
  - 144 dev-eval-2 records (`artifacts/vm/ds1/eval/*.jsonl`, 36 per arm);
  - 40 stream records;
  - `thresholds_dev.json`;
  - `ds1_stopdata*.jsonl` (678 init-base designs);
  - `ds1_all.tgz`, *listed and stream-scanned only*, never extracted to disk.
- **Context:** the Notion page was read as context; Basic Memory returned no FA-1 notes.
- **Resource use:** no MuJoCo, no network inference, no package installs. Python 3.11.9 standard library plus numpy, run with
  `-I`. No script imports `creature_forge`.

## 3. Measurement audit (Investigation A)

### Confirmed equivalences [V]

- Every path calls `arena._condition` (perturbation 0.06; friction ±10 %) on its own seeds.
- Friction reaches the plant through two code routes:
  - training and checks pass `friction_factor` into `plant_rollout`;
  - validation pre-applies `_body_with_friction`.

  Both use the same function and clip, before the plant multiplies the foot geom.
- `outcome == PASS` equals `m["walking"]`, and validation's `score` equals `hdb_evidence.walk_score`.
- The displacement evidence uses the same `verdict_v1`, score rule and comparator design (design 0 = `inst["robot"]`).
- **Settle window.** Validation uses `settle_s = 0.3`, policy paths 0. This affects only the early stop: `compute_metrics`
  detects falls over the whole trace (`locomotion.py:207`), so `fell`, `walking` and `score` cannot differ. It is inert.

### Intentional differences with scientific relevance [V]

- Disjoint seed namespaces; n = 4 / 16 / 24.
- `robust8` is a subset of `robust16`.
- The CMA objective has no paired-displacement term.
- Assimilation uses only 8 of the 16 robust labels.
- Walking gates are body-relative (`creature_walk.py:62-71`).

### What the records establish

- **Displacement-only failures** (20 arm-episodes, 7 instances).
  - Robust-seed median paired differences are −0.9 to −2.8 m against a faulty robot that does not walk (eligibility labels
    `contact_chatter` or `falling_forward`) but is credited its upright forward displacement.
  - 11/20 have shortened legs.
  - On robust seeds the observation is direct: "walks, travels less far than a moving non-walking robot". Whether that is a
    repair failure or a property of the pre-declared criterion is definitional. **[I]**
- **Near-threshold failures** (38 arm-episodes, 15 instances).
  - 25/37 already had robust16 9–14 and were submitted after the budget was spent.
  - Under p = robust16/16 the expected validation count is 18.9/24; the observed mean is 18.1.
  - The top-band shrinkage (0.967 → 0.901) fits selection on noisy 16-seed estimates. **[I]**
  - The large attrition is earlier: train 4/4 → robust16 ≥ 15 in only 52/138 plant steps. **[R]**
- **Missing [V].** `scripts/hdb_agent_run.py:126-127` keeps only status, walking fraction, reasons and rollouts. Per-seed
  original/candidate rows, verdict statistics and confirmation rows (`recovery.py:168-174`) survive nowhere. Per-seed robust
  scores are not serialised either.

## 4. Tool-screening audit (Investigation B)

### Mechanism [V]

1. `screen_tools` applies fixed probes through `apply_changes`, which raises if **any** guided-bounds field of the result is
   out of range (`fault_bench.py:123-151`).
2. The `except Exception: continue` (`belief_engine.py:813-816`) drops the probe. A tool whose probes all fail never enters
   `out`.
3. Engine repair uses only `ranking` (`robust_repair` L885): CMA re-ranks the top 5 and optimises `tools[:2]`.
4. The fallback `list(TOOL_PROBES)` fires only when `ranking` is empty.
5. Nemotron can bypass the screen with `repair(tool=…)` or `delegate_repair(tool_order=…)` → `prefer` (L886-888).
6. A second, latent defect: when a `twin_walk` is refused mid-screen, `screen_tools` returns the **partial, unsorted** list with
   no `tool_screen` event (L821-822). In DS-1 the list was empty every time this happened, so 4 A3v5 episodes fell through to
   the fixed fallback order (posture, timing first). A partial non-empty list was not observed.

### Failure mechanisms, dev-eval-2 (`tool_availability.csv`)

| tool | probe-invalid (all probes) | still CMA-executable | optimised via another path | Nemotron requested | present but never CMA-screened (probe rank > 5) |
|---|---|---|---|---|---|
| foot_friction | 87/138 (23 inst., 10 bases) | 87 (ceiling ×1.37–×1.89) | 0 | 0 | 38 |
| torque_limit | 47/138 (12 inst., 5 bases) | 47 (×1.09–×1.66) | 0 | 0 | 57 |
| foot_length | 8/138 (2 inst., 1 base) | 8 | 0 | 0 | 73 |

- When `foot_friction` *was* present (51), it was never ranked in the top 2 and was optimised once.
- With a `contact_friction:feet` leading diagnosis it was absent in 15/16 screens. FULL outcomes among absent episodes are
  reported, not attributed.

### Physical feasibility [I]

- **Bound.** Effective μ = design friction × injected factor (floor 0.05; MuJoCo max-combination). From the stored threshold
  bisection traces (`_friction_feasibility.json`), the multiplier needed to reach the base's ≥ 5/8 walking bracket falls within
  the legal ceiling for:
  - 0073:0 (×1.06 vs ×1.52);
  - 0073:2 (×1.37 vs ×1.52);
  - 0126:0 (×1.13 vs ×1.37).

  It falls just outside for 0137:0 (×1.84 vs ×1.78). It is far outside for 0096:2 (the base never reached 5/8 in its trace;
  ≥ ×4.4 is needed even for 3/8).
- **Counterexample (E7).** On stream 0038 the tool was ranked first and raised friction ×2.6 / ×1.5, above the bound. It still
  walked 5/8 and 7/16, then 13/24 at validation.
- **Nemotron re-introduction (E8).** Once, an excluded tool (`torque_limit`, stream 0064) was re-introduced by Nemotron. It
  reached 16/16 robust but WORSE displacement.

### Root cause

**Screening coverage, not executability.** Fixed multiplicative probes are tested against absolute guided bounds, so the screen
reports a tool family as *unavailable* exactly when the base sits in the upper part of its range. The CMA search for the same
family remains legal (factor up to max/base). The defect removes access; whether access would recover the instances is
**[U]**.

## 5. Posterior-consistency audit (Investigation C)

### Source [V]

- `_register` appends E and calls `_update_particle` per particle in dict order. That function recomputes the full likelihood
  from the per-experiment cache and charges one twin call per uncached experiment. A refusal breaks the loop with no rollback.
- Every per-seed term is ≤ log 0.9, so a stale particle is never penalised for E: the bias always favours it by
  ≥ 0.105·n/T nats.
- **Reachability:**
  - `assimilate_light` pre-checks `particles × n` (L464-467) and is safe unless stale particles already exist;
  - the v6 `diagnosis_done` guard (L743) protects engine-only arms;
  - the defect is reachable only through Nemotron-driven experiments after twin exhaustion.

### Events (`partial_update_cases.csv`) [V]

- **Scope.** All 8 `update` exhaustion events are in 4 A3v5 episodes, 2 per episode. They were reconstructed exactly from the
  twin ledger (`pid|exp` tags).

| episode | experiment | updated at registration | final particles with / without E | classification |
|---|---|---|---|---|
| 0073:low_ground_friction:0 | X6 cf:kp@x2 | 3 | 3 / 9 (leader lacks E) | **confirmed inconsistency** persisting to the final record; leader 0.989 → 0.991, same structure |
| 0073:heavy_torso:2 | X9 (+X10) | 0 | 0 / 12 | consistent; experiments discarded by inference |
| 0104:short_feet:2 | X5 | 0 | 0 / 12 | consistent; discarded |
| 0142:pitch_sensor_bias:5 | X6 (+X7) | 0 | 0 / 12 | consistent; discarded |

### Contamination [V] / [I]

- **Not affected:**
  - confidence threshold (forced stop by the v6 guard);
  - EIG (twin unavailable);
  - tool selection (the screen was also unavailable; in the 0073 episode the repair used the fallback order).
- **Affected:**
  - **Displayed posterior and model check.** Unscored experiments were shown as "fits" (`belief_engine.py:791` →
    `has_agent.py:592`): 26 prompt instances, 7 experiments.
  - **Pruning** ran on mixed evidence once.
  - **Identification metrics** at final scoring are taken from these posteriors.
  - Nemotron proposals refused for budget are not reported to it: `propose()` drops them from feedback.

## 6. Feedback-reachability audit (Investigation D)

**Classification of the 183 assimilations (`feedback_reachability.csv`) [V]:**

| context | n | deterministic re-screen possible | later Nemotron decision |
|---|---|---|---|
| `robust_repair` twin warm-start check | 69 | 40 (requires no `prefer`, not accepted at L950, twin ≥ 250 at L952) | 0 |
| `robust_repair` plant steps | 107 | 0 (submission uses mapped P, not belief) | 0 |
| Nemotron `repair` (twin 5, plant 2) | 7 | 0 | 7, all shown in a later prompt |

- **FA-1's 67** included 21 events with twin < 250 and 10 accepted designs; neither can reach L952.
- **Only 7 events are Nemotron-reachable.** Every A3v5/A4x assimilation inside `delegate_repair` ends the session.
- **Separating the three problems:**
  - **Information availability.** Count-level disagreement exists in 120/183 events. Count level *understates* it: in E5 the
    true structure gained 0.011 → 0.095 on an event the replay scored zero. [V]
  - **Bayesian influence.** 30 events changed beliefs (TV8 ≥ 0.05 or leader change); 1 leader change. [V]
  - **Action influence.** 0 re-screens. Of the 7 Nemotron-visible events, the next actions were conclude 3, propose 2,
    screen_tools 1, delegate_repair 1; 1 next turn cites the update in its text. No action change is demonstrated. [V]
- **Groups** (exclusive; precedence 4 > 3 > 2 > 1):
  1. no count-level information: 60;
  2. informative counts, limited effect: 88;
  3. belief changed without any path: 24, plus 4 re-screen-possible but not triggered (no leader change);
  4. might influence Nemotron: 7;
  5. demonstrated changed action: 0.
- **`fa1_f2b.py` assumptions:**
  - The 3.41-nat ceiling is a valid upper bound per 8-seed check at T = 6: per-particle mismatch differences ≤ 8, and ratios of
    sums are bounded by the component ratios. [V]
  - Its other assumptions do not hold exactly: the reserve inherits the *post-update* best particle; counts lose seed identity;
    one particle stands for each structure; weights are 4-decimal and top-4/8 truncated.
  - On the subset where count mismatch equals seed mismatch (weights ≥ 0.01), realised/expected is 0.89 (IQR 0.54–1.25).
  - Spearman 0.85 shows ordering, not numerical correctness.

## 7. Statistical corrections (`claim_audit.md`)

- **Variance shares.** eta² 0.72 / 0.002 are reproduced descriptive shares. Chance-corrected omega² is 0.63 (instances) and
  −0.02 (arms); the expectation under no effect is 0.245 / 0.021. They describe concordance, not causation or futility.
- **Pooled Wilson intervals** labelled "clustered by instance" are ordinary Wilson. With ICC 0.62 and design effect 2.86 they
  widen to 0.13–0.45 vs 0.17–0.57.
- **McNemar values** are reproduced. Every contrast rests on 3–5 discordant instances.
- **Claim re-categorisation:**
  - diagnosis-irrelevance → OVER;
  - replay arithmetic → OVER;
  - "instance determines" → OVER if read causally (shared pipeline properties such as `foot_friction` exclusion and leg
    shortening are instance-keyed);
  - memory-suppresses-overrides → WEAK;
  - compound likelihood → WEAK (5 distinct cases);
  - stopping minor → PCM/SDA.

## 8. Updated causal bottleneck map

| rank | mechanism | status | confidence | contradicting / limiting evidence |
|---|---|---|---|---|
| 1 | Repair objective blind to the displacement clause, amplified by body-relative walking gates (leg shortening) | mechanism [V]; share of losses [I] | high (existence); moderate (share: ≥ 11 of 104 failures) | 9/20 displacement failures had no leg change; the faulty comparator's distance is not walking-gated |
| 2 | Tool-access loss from probe-vs-bound screening, plus shallow use (top-5 CMA, top-2 optimised) | defect [V]; impact [U] | high / low | E7 (available, ranked first, failed); E8 (re-introduced, failed) |
| 3 | Small-sample search: train 4 → robust16 over-fit; designs submitted at robust16 9–14 after budget exhaustion | [R]/[V] | moderate | Robust → validation shrinkage is small; physical infeasibility not excluded |
| 4 | LLM budget governance → twin exhaustion → lost screen/warm start, discarded experiments, misleading display | [V] procedure; outcome [U] | moderate | E6: the fallback path verified where screened arms failed |
| 5 | Feedback → action pathway | [V] | high (that it is narrow) | Informative evidence exists (E5) |
| 6 | Posterior partial update | [V] once | high (rare, negligible here) | — |
| 7 | Diagnosis accuracy | association [V]; causal [U] | low | Within-instance 3/0 in favour of correct diagnosis |

## 9. Remaining uncertainty (not answerable from existing records)

1. Faulty vs candidate per-seed validation distances, and therefore sign-test vs minimum-effect failure.
2. Whether `foot_friction`/`torque_limit` access recovers the affected instances, or whether they are physically infeasible.
3. Whether a displacement-aware objective (or nominal-length constraint) converts the leg-shortening walkers into
   verifications.
4. LLM run-to-run variance per instance.
5. Exact per-particle predictions behind any assimilation.

## 10. Decision recommendation

**Choose option 2: a small, owner-approved, controlled non-LLM development experiment.** It has the greatest expected
information value. Questions 1–3 above are now *precise*, and each can be discriminated with existing code paths, without
algorithm changes:

- **(a) Re-verification.** Re-verify the stored submitted designs of the 20 displacement-only and ~10 near-threshold episodes on
  their original validation seeds, writing the full `recovery.assess` output.
  - This is deterministic: the statuses must reproduce exactly, which is itself a reproducibility test.
  - Cost is about 1.5k rollouts.
  - It settles question 1 at negligible cost.
- **(b) Forced tool order.** Use the existing `robust_repair(tool_order=…)` on the 5 low-friction singles and the 5
  leg-shortening instances: `foot_friction` / `torque_limit` first versus the engine order, equal budgets, A1e6 settings,
  ≥ 2 noise seeds. This separates tool access from physical infeasibility.

**Why not the other options:**

- **Option 1** (more offline forensics) has little left to extract: the per-seed data are gone.
- **Option 3** (Deep Research) is premature until (b) shows whether access or objective is the limit.
- **Option 4** (correctness repair) is needed later. The screening and partial-update/"fits" defects, and full verification
  serialisation, should be repaired and approved separately *before* any LLM evaluation. They are not the highest information
  per unit cost now.
- **Precondition:** any approved run must serialise the full verification output. That is a new experiment script, not a
  benchmark change.
