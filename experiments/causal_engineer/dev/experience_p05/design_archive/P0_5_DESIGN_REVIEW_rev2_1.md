# Creature Forge V2: P0.5 experimental design, revision 2.1 (proposal and calculation only)

**Status and scope**
- **Checkpoint:** `CF-V2-P0-2026-10-22`. This revision answers the auditor's review of revision 2
  (`P0_5_DESIGN_REVIEW_rev2.md`, sha256 `0c9349b8…`).
- **Basis:** `feature/experience-learning` at `e3caf8121da84523c36449e353a84bd05977ea9a`. Repository unchanged; nothing
  committed or pushed.
- **Not done:** no harness, no physics or MuJoCo execution, no Stage 0, no sealed or held-out access (the walker file was not
  opened), no cloud or paid inference, no V1 change, no new phase.
  - The G = 46 learning-variance runs were **not restarted**. They remain **NOT COMPUTED**.
- **P0 verdict:** INSUFFICIENT-DATA, unchanged.
- **Scientific goal (unchanged):** does intervention-informed experience give verifiable, decision-relevant repair benefit
  on **unseen robot bases**? Better prediction of historical policy choices is not the target.

**Claim labels:**

| label | meaning |
|---|---|
| **[HIST]** | Records, committed P0 outputs, or repository source at `e3caf81`. |
| **[INDEP]** | Reproduced by the auditor. |
| **[ASSUMP]** | An assumption, *or any number computed from assumptions*: everything printed by the calculation scripts, including synthetic Monte Carlo. Not a property of Creature Forge. |
| **[FUTURE]** | A proposed procedure or measurement. Not authorised. |

**Passing arithmetic tests shows only that the arithmetic is implemented as specified. It does not establish experimental
validity.**

---

## 0. Corrections that change revision-2 conclusions

These are stated first so that no superseded number is reused.

1. **Revision 2's tool feasibility was wrong for its own "low" cost set** [HIST, published code; its repair used the instance's 8 train seeds]. With 8 training seeds, the
   minimum repair budgets are 104, 152, 176 and 200 rollouts, depending on tool dimension. B = 160 permits only 6 tools;
   B + 36 permits 8; B + 40 permits 10.
   - So revision 2's cost-matched cells would have **enlarged the action set**. Fixed in §1.
2. **Revision 2's few-cluster bootstrap undercoverage claim is retracted** [ASSUMP, synthetic]. It reported 0.656 / 0.738
   at G = 8 / 12. That came from a scoring defect: the true value at δ = 0 was a Monte Carlo estimate (≈ ±1e−4) instead of
   exactly 0. On discrete data, intervals often end exactly at 0, so they were scored as misses.
   - Corrected coverage of the percentile cluster bootstrap is **0.86–0.93** (§4.2).
   - t(G−1) CR1 is still the closest to nominal (0.88–0.94) and stays primary.
   - A regression test pins the fix.
3. **Revision 2's ρ labels in section D were nominal, not achieved.** Nominal ρ = 0.30 achieved 0.0963 at q = 0.15 and
   0.1878 at q = 0.42 [INDEP; reproduced analytically in §4.1]. That generator can never reach an ICC ≥ q.
4. **Revision 2's pilot rule R3 is withdrawn.** Its discordance input was not an upper bound on policy disagreement, and it
   merged two capabilities: detecting a large benefit and demonstrating equivalence (§5).
5. **Revision 2's H4 verdict rule is withdrawn.** It treated a non-significant shuffle advantage as evidence of artefact
   (§7).

---

## 1. Feasible tool sets and budgets (auditor item 1)

### 1.1 Minimum repair budgets (published `eng_tools.min_repair_budget`)

The rule is min_repair_budget(t, n_train) = n_train · (1 + 3 · pop(dim_t)), with pop(d) = max(2, 4 + ⌊3 ln d⌋). These are
from `eng_tools.py:118–124` [HIST].

| tool | dim | population | min budget, 4 train seeds | min budget, 8 train seeds |
|---|---|---|---|---|
| foot_friction, foot_length, torque_limit, torso_mass | 1 | 4 | 52 | **104** |
| leg_length, placement | 2 | 6 | 76 | **152** |
| stride, timing | 3 | 7 | 88 | **176** |
| posture | 4 | 8 | 100 | **200** |
| feedback | 5 | 8 | 100 | **200** |

**How these were obtained** [HIST; `p05_min_budget_check.py`]:
- `eng_tools` was imported from the published code. The import loads the MuJoCo module, but every physics entry point
  (`mj_step`, `mj_forward`, model compilation, `MjData`) was trapped to raise an error. The script asserts that none was
  called, and none was.
- The values match the auditor's.
- The lightweight script `p05_design_calc.py` restates the dimensions, and a unit test pins all ten minima.

**Budget-feasible tools by budget** (calc §I) [HIST]:

| B | train seeds | feasible at B | at B + 36 | at B + 40 |
|---|---|---|---|---|
| 160 | 8 | **6** | 8 | 10 |
| 160 | 4 (P0's fault-bench repair: `fault_bench.DEFAULT_TRAIN = 4`, budget 160) | 10 | 10 | 10 |
| ≥ 200 | 8 | 10 | 10 | 10 |

### 1.2 Design rule: the action set must not depend on the repair budget [FUTURE]

Two kinds of feasibility exist:
- **Budget feasibility** (`RepairRefused`) is deterministic from the tool's dimension and n_train.
- **Bounds feasibility** ("no room inside the bounds") depends on the robot's nominal design.

**The rule:**
- **The primary design must make all ten tools budget-feasible at the base budget B**:
  - either B = 160 with n_train = 4, exactly P0's repair protocol (low cost set);
  - or n_train = 8 with B ≥ 200 (mid and high sets: B = 300 and 700).
  - The script refuses a cost set that violates this (`check_all_tools_feasible`).
- **The action set is fixed at the base budget:** A(x) = the tools that are budget- and bounds-feasible at B.
  - Cost-matched comparators (C1 at B + 36, C2 at B + 40) choose from the **same A(x)**. Their extra budget buys more
    optimizer generations, never access to new tools.
  - Under the rule above, B + 36 and B + 40 unlock nothing, so the constraint is automatically met. The constraint itself is
    still stated, so it is binding if the owner picks another B.
- **If the owner nevertheless chooses B = 160 with 8 train seeds:**
  - the matrix has 6 tools;
  - the cost-matched comparators stay restricted to those 6;
  - any "budget-unlocked" comparator choosing among 8 or 10 tools is a separately labelled **exploratory** benchmark that
    mixes budget and action-set effects. It never enters H1–H4.

**Cost effect:** none. Costs are counted in total rollouts B, so the calc §H tables are unchanged from revision 2; only their
n_train labels were added.

---

## 2. Exact P0 learner and infeasible actions (auditor item 2)

### 2.1 Primary estimand: P0-exact and unmasked [FUTURE]

- **What P0 does:** `decide` (`experience_p0.py:141–143` [HIST]) takes argmax_a P̂(a | x) over **all ten tools**, with no
  feasibility mask. A tool with no measured outcome is coded Y = 0 (`ce_dataset`, line 333).
- **The confirmatory H1 algorithm is that procedure, unchanged.**
- **Primary estimand:** V_unmasked(π) = E_x[Y(x, π(x))], where Y(x, a) = 0 for every a ∉ A(x). **An infeasible pick is scored
  as a failure.** This applies equally to π0 (P0's `prior`, also unmasked) and to both arms of the H1 contrast.

**Why this is the primary:**
1. It is the pre-declared algorithm. Changing it after P0 would be an undeclared modification of the confirmatory method.
2. It is a fair contrast. Both H1 arms face the same rule. The kNN rates learn infeasibility from neighbours whose Y = 0, so
   a representation that encodes feasibility-relevant morphology is rewarded. That reward is a legitimate part of decision
   value.
3. Its deployment meaning is conservative: choosing an action that cannot be executed yields no recovery.

**Consequence:**
- Under the §1.2 rule, only bounds infeasibility remains. Its frequency is unknown before the E-check [ASSUMP].
- If it is common, the unmasked estimand mixes "choosing infeasible tools" with "choosing ineffective tools". The masked
  variant (§2.2) separates the two.

### 2.2 Declared secondary variant: P0-masked [FUTURE]

- **Rule:** the same features, P̂ and tie-break, but argmax over A(x) only. π0-masked is the highest-prior feasible tool.
- **Status:** reported as a separately named variant, never substituted for the primary.
- **Feasibility knowledge:** the difference V_masked − V_unmasked, reported per method, is the value of knowing
  feasibility. It is never credited to memory.

---

## 3. Headroom: estimands and simultaneous confidence region (auditor item 6)

The definitions are kept from revision 2 §2: Γ (true best-tool bound), Γ_h, Γ_sel(R), and Δ_M (deployable). So are the
orderings Δ_M ≤ Γ_h ≤ Γ and Γ_sel(R) ≤ Γ.

### 3.1 Three bounds and their components [FUTURE]

All four per-instance estimates are averaged first **within base**; inference treats bases as the independent units (I9).

| bound | per-instance estimate | range (for the finite-sample method) |
|---|---|---|
| L_sel: lower bound on Γ_sel(R) ≤ Γ | Y_fresh(selected tool) − Y_fresh(π0 tool) | [−1, 1] |
| U_naive: upper bound on E[max_a Ȳ_R] − V(π0) ≥ Γ | max_a Ȳ_R − Ȳ_R(π0) | [−1, 1] |
| U_var = (T−1)/√T · √(UCB[E V]) + UCB[E gap] ≥ Γ: component E V | V̂ = S²_a(Ȳ_R) − mean_a s²_a / R (unbiased for the across-tool variance of Q) | [−1/(4(R−1)), T/(4(T−1))] = [−0.25, 0.278] for T = 10, R = 2 |
| U_var: component E gap | Ȳ_R averaged over tools − Ȳ_R(π0) | [−1, 1] |

- The range of V̂ is unit-tested and is attained at both ends.
- **Validity of U_var:** max_a Q − Q̄ ≤ (T−1)√(V/T) holds for every instance (deviations from the mean sum to zero). Then
  E√V ≤ √(E V) by Jensen. Both steps are unit-tested.

### 3.2 How simultaneous coverage is guaranteed [FUTURE]

**Bonferroni split of α = 0.10:**
- L_sel at α/3;
- U_naive at α/3;
- U_var's two components at α/6 each.
- All bounds then hold jointly with probability ≥ 0.90. The reported region is [L_sel, min(U_naive, U_var)].

**Negative estimates and the boundary at zero:**
- V̂ can be negative.
- E V ≥ 0 holds by definition, so replacing a negative upper bound UCB[E V] by 0 can only enlarge the coverage event.
- √ is monotone, so √(max(UCB, 0)) is a valid bound with no delta-method linearisation at the boundary.
- If UCB[E V] = 0, the U_var bound reduces to UCB[E gap].

**Two methods:**
- **Guaranteed:** `method = "hoeffding"`. Each one-sided bound is mean ± range · √(ln(1/α′) / (2G)). It is valid in finite
  samples for independent bases with bounded base means. **Only this version carries the advertised ≥ 90 % simultaneous
  coverage.**
- **Approximate:** `method = "t"`, a t interval with G−1 degrees of freedom on base means. It is reported alongside and
  labelled approximate.

**Tests:** a deterministic test with fixed seed checks that the Hoeffding region covers the true Γ in ≥ 90 % of 200
synthetic campaigns (G = 34). This is a sanity check, not a proof.

### 3.3 What it delivers (calc §M; one synthetic dataset per row, R = 2, m_inst = 2) [ASSUMP]

| scenario | true Γ | G | t: [L, upper] | Hoeffding (guaranteed): [L, upper] |
|---|---|---|---|---|
| S0: all tools equal | 0 | 34 | [−0.11, 0.52] | [−0.40, 0.93] |
| S1: graded, logit sd 0.75 | 0.23 | 34 | [+0.08, 0.53] | [−0.23, 0.89] |
| S2: graded, logit sd 1.5 | 0.40 | 34 | [+0.19, 0.58] | [−0.12, 0.93] |
| S3: sparse best tool | 0.48 | 34 | [+0.23, 0.62] | [−0.11, 0.99] |
| any scenario | — | 12 | upper ≥ 0.59 | upper ≥ 1.2 |

**Conclusions:**
- **Guaranteed coverage is uninformative at feasible sizes.** The Hoeffding upper bound is ≥ 0.89, and its lower bound
  never exceeds 0.
- **The approximate t version** can show that headroom exists (L > 0) when it is large. It cannot show that headroom is
  small: the upper bound is ≥ 0.52 even when Γ = 0.
- **Consequences:**
  - headroom is reported descriptively, with both methods;
  - **no gate, STOP rule or claim of "no headroom" depends on it.**

---

## 4. Statistical calibration (auditor item 3)

### 4.1 Achieved versus requested ICC (calc §J) [ASSUMP; exact]

**The generator:**
- Each base has an effect δ_b = clip(δ + u_b, −q, q), with u_b ~ N(0, σ²).
- Each pair outcome is d ∈ {+1, −1, 0} with P(±1 | b) = (q ± δ_b) / 2.
- Hence P(d ≠ 0 | b) = q for every base. So Var(d) = q − μ², with μ = E δ_b.

**The ICC is exact, not simulated:**
- ICC = Var(δ_b) / (q − μ²). The clipped-normal mean and variance come from closed-form truncated-normal moments.
- They are unit-tested against deterministic quadrature to 1e−6.

**Achieved values of revision 2's nominal ρ = 0.30:**

| q | 0.15 | 0.30 | 0.42 | 0.50 |
|---|---|---|---|---|
| achieved ICC | **0.0963** | 0.1548 | **0.1878** | 0.2050 |

**Supremum:**
- A variable confined to [−q, q] with mean μ has variance ≤ q² − μ², and (q² − μ²) / (q − μ²) ≤ q.
- So **this generator cannot reach ICC ≥ q.** A target of 0.30 is unattainable at q ≤ 0.30, and the code raises.

**Calibration:**
- `calibrate_sigma` inverts the exact ICC, which is increasing in σ, by bisection.
- The round trip is tested to 1e−9; the unattainable case is tested to raise.
- **Example:** σ = 0.2296 achieves 0.10 at q = 0.15.

**The precision formulas (calc §C, §L)** use ρ directly as the ICC of d. They are unaffected by the generator and need no
relabelling. The generator matters only for the coverage simulation.

### 4.2 Few-cluster coverage, corrected (calc §D; 2,000 replications, m_inst = 2, δ = 0) [ASSUMP]

**Labelling of the two tables in calc §D:**
- **D1** re-labels revision 2's runs by their achieved ICC (same seeds), with the scoring fix applied.
- **D2** re-runs with the calibrated generator at achieved ICC 0.10, and at 0.30 where attainable.

| G | q | achieved ICC | z, CR0 | **t(G−1), CR1** | percentile cluster bootstrap |
|---|---|---|---|---|---|
| 8 | 0.15 | 0.10 | 0.923 | 0.937 | 0.923 |
| 8 | 0.42 | 0.10 / 0.30 | 0.856 / 0.851 | 0.893 / 0.892 | 0.871 / 0.872 |
| 12 | 0.15 | 0.10 | 0.889 | 0.908 | 0.895 |
| 12 | 0.42 | 0.10 / 0.30 | 0.838 / 0.841 | 0.894 / 0.891 | 0.872 / 0.877 |
| 24 | 0.42 | 0.10 / 0.30 | 0.875 / 0.877 | 0.901 / 0.903 | 0.901 / 0.899 |
| 46 | 0.42 | 0.10 / 0.30 | 0.884 / 0.878 | 0.896 / 0.892 | 0.898 / 0.894 |

**Readings:**
- At q = 0.15 and G ≤ 12, 2.5–8 % of datasets have every d = 0, so SE = 0 and coverage is trivially met. Those cases are
  reported separately (column "P(SE = 0)").
- **Decision, kept from revision 2:**
  - CR1 t(G−1) is the primary interval;
  - the percentile bootstrap is a sensitivity analysis (mild undercoverage of 0.87–0.88 at G ≤ 12, q = 0.42);
  - **no confirmatory inference at G < 12.**
- **The rationale has changed:** the bootstrap is no longer called "badly undercovering".

### 4.3 Cross-fitted learning variance (calc §E; unchanged from revision 2) [ASSUMP]

| G | scenario | inflation | naive t90 coverage (SE > 0 datasets) |
|---|---|---|---|
| 12 | null / observation sufficient / interventions add information | 1.18 / 1.38 / 1.31 | 0.94 / 0.89 / 0.91 |
| 24 | null / observation sufficient / interventions add information | 1.08 / 1.11 / **2.25** | 0.86 / 0.91 / **0.69** |
| 46 | all | **NOT COMPUTED** | — |

- The auditor reproduced the G = 24 intervention row (+0.0686, 2.25, 0.662) [INDEP].
- The G = 46 runs were stopped by Claude Code's memory-pressure guard and **were not restarted**, per instruction.
- **Planning inflation values:** {1, 2.25, 2.7}. 2.7 is the upper 90 % Monte Carlo bound of 2.25.
- **Refit bootstrap:** mandatory, as in revision 2 §4.4. If the refit interval is > 25 % wider, the wider interval is used
  for classification.
- **A naive SE of 0** is reported as "degenerate: the policies agree", never as a zero-width CI.

### 4.4 Discordance between policies (auditor item 4, first part)

Revision 2's "pooled discordance of random tool pairs" does **not** upper-bound the disagreement between two policies that
select particular tools. It is withdrawn.

**A defensible bound** [mathematical; unit-tested on arbitrary random policy pairs]:
- For any two tool-choice policies with values v_a and v_b, q = P(Y_a ≠ Y_b) ≤ min(1, v_a + v_b, 2 − v_a − v_b).
- Each value lies in [E min_a Q, E max_a Q], so q ≤ q_UB = min(1, 2 E max_a Q, 2 − 2 E min_a Q).
- E max_a Q ≤ E max_a Ȳ_R and E min_a Q ≥ E min_a Ȳ_R. Both right-hand sides are unbiasedly estimable from the replicate
  cells; their confidence bounds give q_UB.

**Its size** (calc §K): q_UB = 0.60 (S0, all tools equal), 0.98 (S1) and 1.00 (S2, S3) [ASSUMP]. It is valid but loose:
two equal tools at the same mean produce q = 0.27–0.43.

**Labelled sensitivity range for planning:** q ∈ {0.15, 0.30, 0.42, 0.50} [ASSUMP]. 0.42 and 0.50 are the pure-noise
values at p = 0.3 and 0.5. The range is reported next to the q_UB worst case and is never presented as a bound.

---

## 5. Benefit detection versus equivalence, and the revised pilot rules (auditor item 4)

### 5.1 Two separate capabilities (calc §L; t-based) [ASSUMP]

- **(a) Detecting a large benefit:** the MDE, one-sided α = 0.05, power 0.80.
- **(b) Showing no meaningful gain at margin M** if the true effect is 0:
  - M_nmg = (t_{0.95} + t_{0.80}) · SE, so that P(U < M) = 0.80;
  - M_tost: the two-sided equivalence version (L > −M and U < M).

| G × m_inst | q | ρ | inflation | MDE | M_nmg | no meaningful gain shown at M = 0.05 / 0.10 / 0.15 |
|---|---|---|---|---|---|---|
| 18 × 2 | 0.15 | 0.3 | 1 | undetectable | 0.192 | no / no / no |
| 28 × 2 | 0.30 | 0.3 | 2.25 | 0.276 | 0.320 | no / no / no |
| 34 × 2 | 0.15 | 0.3 | 1 | 0.129 | 0.136 | no / no / **yes** |
| 34 × 2 | 0.42 | 0.3 | 2.25 | 0.303 | 0.342 | no / no / no |
| 40 × 3 | 0.15 | 0.1 | 1 | 0.095 | 0.098 | no / **yes** / yes |
| 40 × 3 | 0.30 | 0.1 | 2.7 | 0.211 | 0.228 | no / no / no |
| 34 × 2 | q_UB = 0.60 | 0.3 | 2.7 | 0.388 | 0.448 | no / no / no |
| 40 × 3 | q_UB = 1.00 | 0.3 | 2.7 | 0.434 | 0.481 | no / no / no |

**Implications for the owner's margin** (D1; not chosen here):

| margin | demonstrable? |
|---|---|
| **M = 0.05** | Not demonstrable in any configuration up to G = 40 × 3 instances. |
| **M = 0.10** | Demonstrable only in the single most favourable configuration (q = 0.15, ρ = 0.1, no learning inflation, 40 × 3). |
| **M = 0.15** | Only with low discordance (q = 0.15; q = 0.30 at one point) and essentially no learning inflation: 13 configurations with G ≥ 22. With inflation ≥ 2.25, only one configuration qualifies (40 × 3, q = 0.15, ρ = 0.1). H1 compares *learned* policies, so realistic inflation makes M = 0.15 demonstrable only in that best case. |

**Large benefits:** detectable with 80 % power only when they are about 0.21–0.33 or larger, under realistic inflation
(G = 28–40). At the q_UB worst case (q = 0.6–1.0, inflation 2.7), about 0.34–0.54.

**Therefore:** the campaign can answer "is there a large, verifiable benefit?". It **cannot** answer "is there no meaningful
benefit?" at any margin ≤ 0.15, unless discordance and learning inflation both turn out low. This is declared before data
collection.

### 5.2 Pilot outcome rules (revision 2.1) [FUTURE]

The rules are mechanical, with code hash-pinned before the pilot. Checks run in this order, and the first triggered
category wins.

| category | trigger |
|---|---|
| **STOP** | S1–S7 as in revision 2 §5.3: sentinel, determinism, ERROR rates, unresolved infrastructure ERROR, leakage detector, ledger vs billing, cost per cell vs Stage 0. **Plus S8: the diagnosis-independence test (§8) fails.** |
| **REDESIGN** | R1: median bounds-feasible tools < 5, or < 3 in any generator group. R2: floor or ceiling in the pooled FULL rate (90 % bound < 0.05 or > 0.95). **R3′:** for the owner's pre-declared δ_large, the projected MDE at the pilot's q_UB (90 % bounds), ρ = 0.3 and inflation 2.7 exceeds δ_large **and** the projected MDE at q = 0.42 also exceeds δ_large. |
| **HOLD** (owner judgement) | **H-a:** R3′ fails at q_UB but passes at q = 0.42. The worst-case bound and the planning value disagree, so the owner decides explicitly. **H-b:** the projected cost (90 % upper bound + 25 % reserve) exceeds the approved cap (A10). |
| **EXPAND** (request A11) | None of the above. |

- **Equivalence capability (b) is not a gate.** It is reported as a declared limitation.
- If the owner states that showing equivalence at margin M is *required*, and §5.1 says it is unreachable for the planned
  design, the campaign should not be requested. That is an owner decision before the pilot, not a pilot rule.
- **No headroom rule and no informative-rate rule exist** (§3.3).

---

## 6. Populations, eligibility and independence (auditor item 7)

### 6.1 Tiers, kept from revision 2 §9 [HIST]

The walker file was not inspected, and `hdb_bench.load_bases` was not called.

| tier | bases | eligibility evidence in committed records | role in hypothesis generation |
|---|---|---|---|
| **T1** | 18 hdb-v1 experience bases | hdb_v2 FULL-verified outcomes in ≥ 8 of 9 families. 12 of them (0004, 0008, 0011, 0013, 0024, 0028, 0030, 0034, 0036, 0037, 0038, 0039) are in the identifiability panel. | Those 12 helped generate the **H2 residual lead** (P0 §4.3, diagnostic). None was in P0's decision analysis. All were used for engine development and for Stage-2 dossiers and the learned posterior. |
| **T3** | 16 hdb-v1 transfer bases | hdb_v2 outcomes in only 1–7 families. `0070:pitch_sensor_bias:1` excluded. | None. Used only for historical transfer *evaluation*. |
| **T2** | 12 old-dev bases (4 hand + 8 walkrec-m1) | hdb_v2 outcomes in 3–6 families; panel-eligible instances in 5–9 families; 142 of 160 ineligible-plant records. | **Strong overlap:** these are exactly the 12 causal-engineer proxy bases. P0's pre-declared H1 contrast was *tested* there (null, proxy outcome); the exploratory `cf_only` lead was generated there; they are also in the identifiability panel (H2 lead). |
| T4 | 2 (0101, 0117) | no verified outcome | none |

**None of these bases is verified eligible** for one homogeneous FULL-verifier protocol. The zero-rollout E-check (revision
2 §9.2) and, where needed, Stage E must establish it [FUTURE].

### 6.2 Effect of the overlap on confirmatory claims [FUTURE]

**H1 (pre-declared before P0's analysis) is not data-selected on any base.** But re-testing it on T2 means:
- the same robots on which the proxy contrast was null;
- a confirmatory claim on a population that contains them is not independent of P0's exploratory result;
- such a claim must be worded "on a population including the P0 proxy bases".

**H2 (residual coding) was suggested by the identifiability panel on T1-panel ∪ T2:**
- confirmatory H2 is restricted to **H2-naive bases**: the 6 T1 bases outside the panel (0040, 0044, 0052, 0054, 0062,
  0064), plus T3, plus T4 if eligible;
- on the other bases it is reported as exploratory replication.

**The exploratory `cf_only` lead** stays exploratory on every population.

**Engine-posterior benchmark B5:** T1 and T2 contributed to the Stage-2 learned posterior and dossiers. B5 is therefore
in-sample on T1/T2, and its comparisons are reported only on T3 or labelled in-sample.

### 6.3 Population options, kept separate [FUTURE]

| option | confirmatory population | H1-naive bases | H2-naive bases | pilot pool, disjoint and compatible |
|---|---|---|---|---|
| **P-A: T1** | 18 | 18 | 6 | **6 of T3** (same generator, hdb-v1); T1 intact, G = 18 |
| **P-B: T1 + T3** | 34 | 34 | 22 | **6 of T2** (2 hand + 4 walkrec). T1 + T3 intact, G = 34. Alternative: 6 of the 12 T1-panel bases, giving G = 28, which keeps a hdb-v1 pilot. |
| **P-C: T1 + T3 + T2** | 46 | 34 (T2 flagged) | 22 | 6 drawn stratified 4 / 1 / 1 from the population, giving G = 40. Sensitivity without T2 is pre-declared. |

**Compatibility rules for the pilot:**
- Pilot bases are always **outside** the confirmatory population (base-level external pilot, revision 2 §5.1).
- Under P-B with a T2 pilot, the pilot exercises **no hdb-v1 base**, although hdb-v1 is about 75 % of the population weight.
  Generator-specific cost and feasibility differences are then covered only by:
  - the zero-rollout E-check (feasibility for every population base);
  - the HOLD rule's 90 % cost bound plus 25 % reserve.
  - This is a declared representativeness gap.
- Under P-A with a T3 pilot, the pilot shares the population's generator. T3 is then unavailable for confirmation.
- **No new bases are generated.**

**Precision by option (calc §L, m_inst = 2, ρ = 0.3):**
- P-A (G = 18): the MDE is about 0.24–0.29 without learning inflation. With inflation 2.25, it is 0.39 at q = 0.42 and undetectable
  at q ≤ 0.30. It is close to the G ≥ 12 inference floor.
- P-B and P-C are the only options in which effects of about 0.20–0.30 are detectable under realistic inflation.

---

## 7. H4 attribution: three outcomes (auditor item 5)

### 7.1 Outcomes [FUTURE]

| outcome | condition |
|---|---|
| **Validated transfer attribution** | All permission and leakage tests pass (§7.3), **and** the memory policy's advantage over **every** structure-preserving shuffle control (§7.2) is a "supported benefit" (L > 0 and U ≥ m, revision 2 §8.1). |
| **Direct evidence of artefact or leakage** | *Positive* evidence only. **(i)** A permission or leakage test fails: a forbidden field reaches the feature matrix. **(ii)** A structure-preserving control **reproduces the gain**: that control's own advantage over π0 is a "supported benefit", and the memory-minus-control contrast is "supported no meaningful gain" (U < m). The gain is then explained by the structure the control preserves. **(iii)** The warm-start or diagnosis-independence checks fail. |
| **Unresolved attribution** | Everything else. In particular: a memory-minus-shuffle contrast that is inconclusive (L ≤ 0 < m ≤ U), or a shuffle control whose own value is inconclusive. **A non-significant shuffle advantage is "unresolved", never "artefact".** |

Unless attribution is validated, H1–H3 results are reported as "decision value present, attribution unresolved". They are
not presented as transfer of intervention knowledge.

### 7.2 Structure-preserving shuffle controls

All are applied within each LOBO training fold, with k fixed to the real run's per-fold value and 20 permutations.

| control | what is permuted | what it preserves | a gain that survives it indicates |
|---|---|---|---|
| S-global (P0's) | whole 10-tool outcome rows across training instances | marginal tool rates | — (baseline control) |
| **S-base** | outcome rows **within each training base** | each base's tool-success profile | the gain comes from base-level similarity, not instance-level diagnosis |
| **S-family-free** | outcome rows within (base, severity bin) strata | base profile and severity structure | severity-driven, not mechanism-driven, transfer |
| **S-cf-conditional** | the **cf block** across training instances within base, keeping obs, morph and outcomes | the obs/morph → outcome link | the interventional block adds nothing beyond obs/morph (the H1 contrast's attribution) |
| S-generator | outcome rows within generator group | group-level profiles | generator-level similarity |

**Notes:**
- Outcome rows are permuted **as whole vectors**, so the tool-correlation structure and the noise structure are preserved.
- The family label is used only to *define* strata; it never enters features.

### 7.3 Robust feature-permission tests (not dependent on a trained policy)

1. **Static construction:**
   - the feature builder receives only a projection of each record onto its allowed column groups (`legal_obs`, `legal_cat`,
     `legal_twin`);
   - a test asserts that the projection's keys are a subset of the allow-list for every record type.
2. **Metamorphic negative test (the feature matrix, not predictions):**
   - for each forbidden field (`TRUTH`, `OUTCOME`, `ASSIGNMENT`, `PROVENANCE`), replace it with random values of the same
     type in a copy of the records;
   - the **feature matrix must be bit-identical**.
3. **Metamorphic sensitivity test:**
   - perturb each permitted field;
   - the feature matrix must change in exactly the columns derived from it.
   - This shows the detector can see changes.
4. **Positive control for the detector:**
   - in a test copy of the builder, deliberately route a forbidden field (e.g. `TRUTH.family`, or a function of the true
     outcome) into a legal-group column;
   - the negative test (2) must then **fail**: the feature matrix differs when the forbidden field is perturbed.
   - This validates the detector **without requiring any trained policy's prediction to change**. It replaces revision 2's
     "the positive-control leak must change predictions".
5. **Run-time check:** the per-record hash of the feature builder's input equals the hash of the allowed projection.

---

## 8. Diagnosis-independence test, defined without executing physics (auditor item 8) [FUTURE]

**Claim to verify:** conditional on the same instance x, tool a, repair budget B, train seeds and optimizer seed s, running
or omitting the diagnostic prefix (D_obs, D_cat, D_twin) cannot change **any** part of the repair execution R_B.

**Test design** (it runs only after A6/A7 authorise physics):
1. **Isolation by construction:**
   - R_B runs in a fresh worker process whose only inputs are a serialised, allow-listed request: policy view of x, tool,
     B, train seeds, s, and plant reference;
   - the request schema has no field that can carry diagnostic output (static test);
   - worker pools are not reused between diagnosis and repair (`maxtasksperchild = 1` or equivalent).
2. **Two arms per test case:**
   - **arm D:** the full prefix for x is executed earlier in the same session and pool, then R_B;
   - **arm ∅:** no prefix at all, then R_B.
   - **Hidden-state variant arm D′:** the prefix of a *different* instance is run first, so leaks of global state are not
     masked by instance identity.
3. **Complete execution trace,** compared bit-for-bit between arms:
   - the ordered list of every candidate evaluated (vector and body hash);
   - per-generation CMA state: mean, step size, covariance-matrix hash, evolution paths, RNG state hash before and after
     sampling;
   - every rollout's (seed, candidate hash, score, walking flag, error);
   - rollout counts; the final design hash;
   - the complete `full_recovery_v1` per-seed rows and status.
   - The initial-mean hash alone is explicitly insufficient.
4. **Instrumentation neutrality:**
   - the trace hooks wrap `cma_fn` and the rollout function;
   - a separate run without hooks must give a bit-identical final design and verification. This shows the hooks do not
     perturb execution.
5. **Hidden-state audit (static plus run time):**
   - no use of the global `numpy.random` or `random` state inside R_B (an AST scan, plus a run-time sentinel that raises if
     the global RNG is touched);
   - observation and model caches are cleared or keyed only by repair inputs; a test runs arm ∅ with warm and with cold
     caches.
6. **Coverage:**
   - Stage 0: all 10 tools × 3 instances (one per generator group) × 2 optimizer seeds × arms {D, ∅, D′};
   - pilot and campaign: a random 2 % of cells re-executed as arm ∅.
7. **Verdict:** any trace difference is STOP S8. No tolerance is allowed: execution is deterministic.

---

## 9. Cost and statistical sensitivity (updated)

### 9.1 Costs [ASSUMP; prices unverified]

- **Formulas:** unchanged from revision 2 §7.4 (verification, prefix, cells, cost-matched cells at B + 36 / B + 40,
  selector confirmation, sentinels, Stage E, VM hours = RE / throughput · (1 + idle) + sessions · overhead).
- **New in 2.1:**
  - each cost set states n_train and is checked to keep all 10 tools budget-feasible: low = B 160 / 4 train seeds; mid =
    300 / 8; high = 700 / 8;
  - Stage 0 additionally runs the §8 independence matrix: 10 tools × 3 instances × 2 seeds × 3 arms = 180 repair executions.
    That is about 180 · C_cell(B) RE, locally, at $0 cloud cost.
- **Numbers:** the totals in calc §H are identical to revision 2 (verified by diff).

| design | low | mid | high |
|---|---|---|---|
| Stage 0 (local) | 7.9 k RE | 12.0 k RE | 21.8 k RE |
| §8 independence matrix (local), plus | 180 · 191 ≈ 34 k RE | 180 · 362 ≈ 65 k RE | 180 · 772 ≈ 139 k RE |
| Pilot (6 × 2, R = 2) | $0.55 | $1.60 | $15.13 |
| Campaign 28 × 2 | $1.26 | $3.74 | $37.61 |
| Campaign 36 × 2 | $1.56 | $4.67 | $47.36 |
| Campaign 36 × 3 | $2.25 | $6.75 | $69.30 |

- **C_cell** here is B + verification per cell: 160 + 31.2 (low, original validation cached), 300 + 62.4 (mid), 700 + 72 (high).
- **Remaining cap:** $6.595 [HIST, owner to confirm]. The pilot fits only under the low and mid sets.

### 9.2 Statistical sensitivity (calc §C, §D, §E, §K, §L, §M)

**Grid:**
- q ∈ {0.10, 0.15, 0.25, 0.30, 0.42, 0.50}, plus q_UB ∈ {0.6, 0.8, 1.0};
- G ∈ {8, 12, 18, 22, 24, 28, 34, 40, 46}; m_inst ∈ {1, 2, 3};
- ρ (achieved) ∈ {0, 0.1, 0.2, 0.3, 0.5}; inflation ∈ {1, 2, 2.25, 2.7, 3}.

**Labelling:** every table is labelled normal approximation or t, and every one is [ASSUMP].

---

## 10. Objection-to-resolution table (revision 2 → 2.1)

| # | auditor objection | resolution | where |
|---|---|---|---|
| 1 | Minimum repair budgets: B = 160 permits 6 tools; B + 36 permits 8; B + 40 permits 10 | Enumerated from the published code with physics trapped (matches the auditor). Design rule: all tools budget-feasible at B; the action set is fixed at B; cost-matched cells cannot add tools; cost sets carry n_train and are checked. | §1; calc §I; `p05_min_budget_check.py`; tests |
| 2 | Unmasked P0 `decide` vs "feasible tools only" | Primary = P0-exact, unmasked; infeasible picks score 0 for all arms, including π0. Masked = declared secondary variant. | §2 |
| 3 | Clipped generator: nominal ρ ≠ achieved | Exact achieved-ICC formula (0.0963 / 0.1878 reproduced); supremum ICC < q; calibration by bisection; tests against quadrature. Coverage relabelled (D1) and rerun calibrated (D2). Separately, a scoring defect was found and fixed, and the bootstrap-undercoverage claim retracted. | §0.2–0.3, §4.1–4.2; calc §J, §D |
| 4a | Random-pair discordance is not a bound | Replaced by q ≤ min(1, 2 E max Q, 2 − 2 E min Q), estimable, unit-tested on arbitrary policies; plus a labelled sensitivity range. | §4.4; calc §K |
| 4b | R3 conflated benefit and equivalence | Two capabilities computed separately; implications for M = 0.05 / 0.10 / 0.15 without choosing M; R3′ on benefit only; equivalence is a declared limitation; HOLD when bound and planning value disagree. | §5; calc §L |
| 5 | H4 treated a non-significant shuffle as artefact | Three outcomes; artefact needs positive evidence; structure-preserving shuffles (base, stratum, cf-conditional, generator); permission tests on the feature matrix; positive control validates the detector, not predictions. | §7 |
| 6 | Headroom CI components and simultaneous coverage | Bonferroni α/3, α/3, α/6, α/6; truncation of negative UCB[E V] at 0 justified; monotone √ (no delta method); finite-sample Hoeffding version is the only guaranteed one; t is approximate; deterministic coverage test. | §3; calc §M |
| 7 | Populations T1, T3, T2 separately; overlap; pilot compatibility | Separate tier table; H1/H2/B5 overlap consequences; options P-A/P-B/P-C with matching pilot pools and the representativeness gap stated; no walker file; no new bases. | §6 |
| 8 | Diagnosis independence beyond the initial mean | Full-trace, bit-identical, three-arm test with instrumentation-neutrality and hidden-state audits; STOP S8. | §8 |
| 9 | Deliverables | This file; code and tests; tables; checklist; self-critique. G = 46 NOT COMPUTED. | §9–§13 |

---

## 11. Approval checklist A0–A11 (revision 2.1; no gate is approved)

- [ ] **A0.** Documentation-only commit of the accepted DS-1 corrections C1–C8 and of the revision-2 retractions (§0).
- [ ] **A1.** Estimands, including P0-exact unmasked primary (§2), diagnosis-independent repair, and headroom quantities
  reported descriptively only (§3).
- [ ] **A2.** Population option P-A, P-B or P-C, with its pilot pool (§6); the E-check (zero rollouts); generator-group
  handling.
- [ ] **A3.** Budget and action-set rule (§1.2): B and n_train, with all tools budget-feasible; cost-matched comparators
  restricted to A(x).
- [ ] **A4.** Hypotheses H0–H3 with the four-outcome partition; H4 three-outcome attribution with shuffle controls and
  permission tests (§7); the owner's margin m and large-effect threshold δ_large declared before the pilot.
- [ ] **A5.** Statistical plan: CR1 t(G−1) primary; mandatory refit bootstrap; no inference at G < 12; Hoeffding vs t
  reporting of headroom.
- [ ] **A6.** Harness and test implementation, including the §8 trace instrumentation and §7.3 permission tests. No runs.
- [ ] **A7.** Stage 0 (local MuJoCo, $0 cloud), including the §8 independence matrix.
- [ ] **A8.** Stage E, only for bases the E-check cannot verify.
- [ ] **A9.** External pilot with rollout and dollar ceilings inside the remaining cap; rules from §5.2.
- [ ] **A10.** Budget cap decision: separate, after measured pilot costs.
- [ ] **A11.** Campaign and confirmatory analysis at a frozen commit; the runner named.

---

## 12. Owner decisions, ranked by effect on feasibility

| rank | decision |
|---|---|
| D1 | **The minimum meaningful margin M, and whether equivalence must be shown.** If equivalence at M ≤ 0.15 is required, §5.1 says the campaign cannot deliver it under realistic inflation. If only large-benefit detection is required, δ_large must be ≥ about 0.20–0.30. |
| D2 | **Population option** P-A / P-B / P-C (§6.3). It sets G = 18 / 34 / 40 and the claim wording (T2 overlap). |
| D3 | **B and n_train** (§1.2): P0-exact 160 / 4 (cheapest; the same repair protocol as P0's matrix) or 8 seeds with B ≥ 200. |
| D4 | **Cap and confirmation of the real balance.** |
| D5 | **Instances per base and replicate fraction.** |
| D6 | **Verification-seed namespace** (reuse vs fresh). |
| D7 | **Pilot pool** under P-B: T2 (no hdb-v1 representation) or T1-panel (G drops to 28). |
| D8 | **Confirmation-stage and original-validation caching.** |
| D9 | **Whether the masked variant (§2.2)** is promoted to co-primary before data. It is not recommended. |
| D10 | **Who runs the confirmatory analysis.** |

---

## 13. Self-critique: what remains unresolved

**Identification**
1. Whether HDB tools differ at all within an instance at budget B. No record identifies it, and the headroom region is
   uninformative at guaranteed coverage (§3.3).
2. The bounds-feasibility frequency is unknown. If it is high, the unmasked primary mixes feasibility and effectiveness.
3. Attribution: even with validated shuffle controls, "intervention knowledge" is credited only relative to the controls
   listed. Unlisted structure could still explain a gain.
4. Diagnosis independence is defined but unproven until §8 runs.

**Transport**

5. Nothing is said about the sealed test population.
6. LOGO has only two usable generator groups.
7. Under P-B with a T2 pilot, the pilot does not exercise hdb-v1 at all.
8. H1 on P-C includes the P0 proxy bases, so it is not independent of P0.

**Power and inference**

9. q, ρ, inflation, flip rate and costs are assumed ranges. The synthetic generators are arbitrary; the cluster generator
   cannot represent ICC ≥ q.
10. The G = 46 inflation is NOT COMPUTED. The refit bootstrap's own few-cluster coverage is unverified.
11. The q bound is valid but loose (0.6–1.0). Planning relies on a labelled sensitivity range.
12. Equivalence at M ≤ 0.15 is effectively unreachable; small true benefits (< about 0.2) will usually end "inconclusive".

**External validity**

13. R_B (plant-only, diagnosis-independent repair; 4 train seeds if B = 160) differs from the engines' twin-assisted repair.
    Tool effects and the decision value of diagnosis may differ in deployment.
14. One budget level. Conclusions do not extend to other B.
15. P0's equal-weight kNN representation is kept for exactness. A null H1 says nothing about other learners.

**Process**

16. Two defects in revision 2 were found only on re-examination: the coverage scoring, and tool feasibility. Further defects
    of this kind are possible. Independent re-implementation of the critical calculations is advisable before A11.
17. **Passing the 40 arithmetic unit tests establishes only that the formulas are implemented as written.** It does not
    establish that the design is valid, or that any assumption holds for Creature Forge.

*End of revision 2.1. No implementation, Stage 0, simulation, cloud spend, campaign or confirmatory evaluation has been
started. Awaiting independent review and explicit owner authorisation.*
