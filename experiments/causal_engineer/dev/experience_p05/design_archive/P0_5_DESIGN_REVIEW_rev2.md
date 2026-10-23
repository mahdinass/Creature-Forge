# Creature Forge V2: P0.5 experimental design, revision 2 (proposal only)

**Status and scope**
- Checkpoint: `CF-V2-P0-2026-10-22`. This revision answers the auditor's REDESIGN verdict on revision 1
  (`P0_5_DESIGN_REVIEW.md`, sha256 `aa9bd74b…`).
- Basis: `feature/experience-learning` at `e3caf8121da84523c36449e353a84bd05977ea9a`.
- **Nothing was executed:** no harness, no experimental data, no MuJoCo (a tripwire blocks the import), no Stage 0, no sealed
  or held-out access, no cloud spend, no commit or push. V1 was not touched.
- **The P0 verdict stands: INSUFFICIENT-DATA.** No historical record is used as confirmatory evidence anywhere in this
  design.

**Deliverables** (all in the session scratchpad, uncommitted):

| file | role |
|---|---|
| `P0_5_DESIGN_REVIEW_rev2.md` | this proposal |
| `p05_design_calc.py` | corrected read-only calculations; replaces `p05_precision.py` |
| `test_p05_design_calc.py` | unit tests of the arithmetic (25 tests) |
| `p05_inflation_run.py` | runs one section-E cell |
| `p05_design_calc_output.md` | the generated tables cited as "calc §X" below |
| `infl2/` | the section-E JSON results for G = 12 and 24, with per-simulation arrays (the G = 46 runs were stopped by memory pressure and are absent) |

The supporting scripts from revision 1 are unchanged:
- `ds1_comparability_check.py`;
- `p05_precision.py`, kept as the audited original and superseded.

**Claim labels:**

| label | meaning |
|---|---|
| **[HIST]** | Historical evidence: existing records, committed P0 outputs, or repository source at `e3caf81` (code constants and function behaviour read from source). |
| **[INDEP]** | Independently established: reconstructed by the auditor and reproduced from committed evidence. |
| **[ASSUMP]** | An assumption, *or a number computed from assumptions* (every output of `p05_design_calc.py`, including the synthetic Monte Carlo). These are never measured properties of Creature Forge. |
| **[FUTURE]** | A proposed future measurement, procedure or design choice. It is not executed and not authorised. |

---

## 0. Decisions at a glance

1. **Headroom.** Three quantities are now kept apart: the true best-tool bound Γ, a finite-replicate selector, and a
   deployable memory policy.
   - Γ is only *partially identified*. With feasible numbers of replicates, its honest interval is wide.
   - **No headroom-based STOP rule remains in the pilot** (§2).
2. **Noise.** Realised adverse outcomes are not harm. Equally effective tools with success probability 0.3 already produce
   42 % discordance and a 21 % "negative-transfer" rate with zero expected harm (§3).
3. **Arithmetic.** |δ| ≤ q is enforced in code, with tests. Intervals use t with G−1 degrees of freedom. The percentile
   cluster bootstrap is demoted because it undercovers at G ≤ 12 (calc §D). Learning-variance inflation is measured on
   the exact P0 learner with synthetic data (calc §E) and carried into the sizing (§4).
4. **Pilot.** External: pilot *bases* are excluded from all confirmatory analysis. Revision 1's blinding claim is withdrawn
   as incoherent. The STOP, REDESIGN, HOLD and EXPAND rules are mechanical (§5).
5. **H1.** The confirmatory representation is exactly P0's `interv`, by code and blob hash (§6). Residual and raw-panel
   codings are secondary or exploratory.
6. **Cost match.** Repair is made **independent of diagnosis**, so every policy's information matches what it is charged
   for. Cost-matched comparators get the unpaid diagnosis as extra repair budget, in phase-2 cells (§7).
7. **Hypotheses.** A single four-outcome partition, with the owner's margin, applies to every contrast. H2 is judged on its
   own estimand. H4 uses absolute contrasts plus deterministic leakage checks (§8).
8. **Bases.** The committed evidence verifies **no** base as eligible under one homogeneous protocol. It supports 46
   candidates in four tiers. With an external pilot and the tiering, a realistic confirmatory G is **12–40**, depending on the tier choice (§9).

---

## 1. Estimands and identification [FUTURE unless labelled]

### 1.1 The four stages, now causally separated

| stage | content | depends on |
|---|---|---|
| D_obs | Observe the faulty plant with the nominal design on n_obs = 4 policy-visible obs seeds: 4 plant rollouts. This is P0's observation ([HIST] `scripts/ce_probe_dataset.py` `N_OBS = 4`). | instance |
| D_cat | The fixed 9-entry catalogue `eng_tools.COUNTERFACTUALS` ([HIST] `creature_forge/eng_tools.py:33–43`), each applied to the nominal design and observed on the same 4 seeds: 36 plant rollouts. An entry that would leave the bounds is *unavailable* and missing, never clipped ([HIST] same file). | instance |
| D_twin (exploratory and H2 only) | The same 40 observations on the **nominal twin** (gap-free simulator, no fault): 40 twin rollouts and 0 plant rollouts. | nominal design |
| Repair R_B(x, a, s) | Plant-only CMA in tool a's subspace, from the nominal design, plant budget B, on the instance's train seeds. The optimizer noise seed s is fresh per (instance, tool, replicate). It is the procedure of P0's decision tier, `eng_tools.run_repair` ([HIST] `eng_tools.py:127–140`, called by `fault_bench.build_instance`), with a plant-aware rollout function supplied through its `cma_fn` hook (to be implemented and verified; A6). **It uses no diagnostic output.** | instance, tool, seed |
| Verification Y | `full_recovery_v1` through `hdb_bench.verify` → `hidden_plant.verify` → `recovery.assess` ([HIST]). Original and candidate on the 24 validation seeds; confirmation on 24 seeds at 20 s only if validation passes. | final design, seeds |

**Why repair no longer uses the diagnosis.**
- In revision 1 the repair warm-started from the shared posterior. That let the panel's information reach every cell,
  including the cell of the policy that was supposed to be "cost-matched without the panel" (auditor objection 6).
- Under R_B, Q(x, a) is a property of the instance and tool alone. The diagnosis can only change *which* tool is chosen.
- **What it costs:** the study measures the *decision* value of diagnosis, not its value for twin-assisted repair. This
  is a deliberate scope restriction (self-critique §14).

### 1.2 Estimands

- **Cell response.** Q_B(x, a) = P(Y = FULL | do(A = a), R_B), with the expectation over the optimizer seed s. The
  validation and confirmation seeds are fixed per instance.
- **Infeasible tools.** A tool for which `run_repair` raises "no room inside the bounds" ([HIST] `fault_bench.py`) has Y = 0
  by definition, exactly as P0's `ce_dataset` codes a missing matrix entry ([HIST] `experience_p0.py:333`).
- **Policy value.** V(π) = E_x[Q_B(x, π(h(x)))], with h(x) the information π is charged for (§7).
- **Fallback π0** = the training-fold most frequent FULL tool. This is exactly P0's `prior` ([HIST]
  `experience_p0.py:146–156`, `decision_eval`). It uses no diagnosis.
- **Learned policies: procedure estimand.**
  - Δ_proc(M, M′) = E[V(π_M trained on G−1 bases) − V(π_M′ trained on G−1 bases)], over training samples and test bases.
  - Leave-one-base-out (LOBO) cross-fitting estimates Δ_proc, not the value of any single fitted policy.
- **Headroom quantities:** see §2.

### 1.3 Identification assumptions

| # | assumption | support |
|---|---|---|
| I1 | Consistency and no interference between cells. | Separate processes; a deterministic re-execution check. |
| I2 | Full matrix: every feasible tool is observed. | design |
| I3 | Each policy's action set = the feasible tools, known before any repair. | zero-rollout feasibility screen |
| I4 | Q_B does not depend on the diagnostic path. | R_B uses no diagnostic output; checked by the initial-mean hash per cell |
| I5 | The same verifier and the same seeds for every tool of an instance. | seed-block ids recorded per cell |
| I6 | Simulator and library versions fixed. | environment manifest; sentinel |
| I7 | Transport *within* the development population (LOBO, LOGO). Transport to sealed test bases is **not** tested. | [ASSUMP] |
| I8 | Conclusions hold at one declared budget B. | [ASSUMP] |
| I9 | Base effects are independent across bases. This justifies the external pilot (§5). | [ASSUMP] |

---

## 2. Repair-effect headroom (auditor item 1)

### 2.1 The estimand mismatch in revision 1

Revision 1 defined Γ = E[max_a Q(x, a) − Q(x, π0)] but proposed estimating it with a replicate-split, one-shot selector.
That selector estimates a *different, smaller* quantity. Revision 1 then used its upper confidence bound in a STOP rule as
if it were an upper bound on Γ. That logic is invalid: a selector trained on noisy repetitions can show near-zero value when
Γ is large (calc §F1, scenario S1: Γ = 0.208, selector at R = 1 = 0.053). **The STOP rule is removed.**

### 2.2 Four distinct quantities [FUTURE definitions; inequalities are mathematical]

| quantity | definition | what it is |
|---|---|---|
| Γ (true best-tool bound) | E_x[max_a Q(x, a) − Q(x, π0(x))] | clairvoyant per-instance best tool; an upper bound on any tool-choice policy at budget B |
| Γ_h (feature-attainable bound) | E_x[max_a E(Q(x, a) \| h(x))] − V(π0) | the best any policy using information h can do |
| Γ_sel(R) (finite-replicate selector) | E_x[Q(x, argmax_a Ȳ_R(x, a)) − Q(x, π0)] | value of trying every tool R times on *this* robot and keeping the best; not deployable (it needs the full matrix on the plant) |
| Δ_M (deployable memory policy) | V(π_M) − V(π0), procedure estimand | what memory delivers |

**Orderings.**
- Δ_M ≤ Γ_h ≤ Γ.
- Γ_sel(R) ≤ Γ, increasing in R toward Γ.
- Neither Γ_sel nor Γ_h bounds the other.

### 2.3 Estimators and honest intervals [FUTURE]

- **Lower end, Γ_sel(R).**
  - Select argmax_a Ȳ_R on R replicates of every tool, with ties broken at random.
  - Then run **one fresh confirmation draw** each of the selected tool and of π0's tool: two cells per instance.
  - The mean difference is unbiased for Γ_sel(R).
- **Upper end 1, naive.** max_a Ȳ_R − Ȳ_R(π0) is unbiased for E[max_a Ȳ_R] − V(π0) ≥ Γ (Jensen). It tightens as R grows.
- **Upper end 2, variance component** (new; unit-tested as a valid bound):
  - Γ ≤ (T−1)/√T · √E[V_Q] + E[Q̄ − Q(π0)], where V_Q(x) is the across-tool variance of Q(x, ·) and Q̄ the tool mean.
  - V_Q is *unbiasedly* estimable with R ≥ 2: S² over tools of Ȳ_R minus mean_a s_a² / R.
  - The bound is tight when tools are equal.
- **Reported identification interval for Γ:** [L_sel, min(U_naive, U_var)].
  - Each end is a one-sided bound at 1 − 0.10/3, so the region has joint coverage ≥ 90 % (Bonferroni over three bounds).
  - Bounds use base-cluster t intervals with G−1 degrees of freedom.
- **Δ_M:** the LOBO cross-fitted estimate with a CR1 t interval with G−1 df, plus a refit-bootstrap sensitivity (§4.4).
- **Γ_h:** not estimable without a model; never reported as a number. Δ_M is a lower bound on it.

### 2.4 What is attainable (calc §F, synthetic) [ASSUMP]

| scenario (10 tools) | Γ | selector R = 1 / 2 / 4 | naive R = 1 / 2 / 4 | variance bound |
|---|---|---|---|---|
| S0: all tools equal, p ~ Beta(1.5, 3.5) | 0 | 0 / 0 / 0 | 0.55 / 0.43 / 0.31 | **0** |
| S1: graded, logit sd 0.75 | 0.21 | 0.05 / 0.08 / 0.11 | 0.59 / 0.48 / 0.38 | 0.37 |
| S2: graded, logit sd 1.5 | 0.38 | 0.16 / 0.23 / 0.29 | 0.61 / 0.54 / 0.48 | 0.66 |
| S3: sparse best tool | 0.50 | 0.24 / 0.34 / 0.42 | 0.71 / 0.60 / 0.55 | 0.58 |

**The identification gap does not shrink with more instances; only replicates shrink it, and slowly.** On top of the gap,
sampling adds the following (calc §F2–F3, ρ = 0.2, m = 2):
- **Selector end:** its per-instance sd is about 0.6, so a ±0.10 half-width needs about 120–140 instances.
- **Naive end (R = 2):** ±0.10 needs about 40–50 instances.
- **Variance component:** the sd of V̂ is about 0.06, so ±0.01 on E[V] needs about 100–175 instances.
- **Near V = 0:** the square root amplifies error, so +0.01 in E[V] moves the bound by 0.29.

**Consequence: absence of headroom cannot be established at practical margins with ≤ 40 bases** [ASSUMP]. Revision 1's
"Γ < 0.05 ⇒ stop" was therefore never decidable. Presence of headroom can be established if Γ is large, through
L_sel > 0.

### 2.5 Replicates [FUTURE]

- **Allocation:** a pre-drawn random 25 % of campaign instances, stratified by base, get R = 2 for every tool, plus the two
  selector-confirmation cells. They provide L_sel(2), U_naive(2), U_var and the flip rate.
- **Primary policy analyses use replicate 1 only,** so every instance contributes the same estimand.

---

## 3. Optimizer noise and negative transfer (auditor item 2)

### 3.1 Three distinct quantities

| quantity | definition | identified from |
|---|---|---|
| Realised adverse outcomes p₋ | P(Y(x, π_M) = 0, Y(x, π0) = 1) on single draws | one draw per cell |
| Expected harmful selection | H = E_x[(Q(x, π0) − Q(x, π_M))₊], and P_x(Q(x, π0) − Q(x, π_M) > ε) | **not** point-identified from single draws (nonlinear in Q) |
| Instance-level effect heterogeneity | Var_x(τ), with τ(x) = Q(x, π_M) − Q(x, π0) | identified with two independent replicate pairs: Var_x(τ) = Cov(d^(1), d^(2)) |

### 3.2 Equally effective stochastic tools still produce discordance [ASSUMP, exact]

If Q(x, a) = Q(x, b) = p and the optimizer draws are independent:
- discordance q = P(Y_a ≠ Y_b) = 2p(1−p);
- realised p₋ = p(1−p);
- expected harm H = 0;
- the probability that K equal tools look "informative" (some succeed and some fail) is 1 − p^K − (1−p)^K.

| p | q | realised p₋ | expected harm | P(informative), K = 4 | K = 10 |
|---|---|---|---|---|---|
| 0.1 | 0.18 | 0.09 | 0 | 0.34 | 0.65 |
| 0.2 | 0.32 | 0.16 | 0 | 0.59 | 0.89 |
| 0.3 | **0.42** | **0.21** | 0 | 0.75 | 0.97 |
| 0.5 | **0.50** | 0.25 | 0 | 0.88 | 1.00 |

**Implications:**
- The auditor's q = 0.42 and 0.50 are exactly what pure noise produces at p = 0.3 and 0.5.
- The historical proxy matrix [HIST: 109 of 165 instances "informative" at K = 10, single draws with a deterministic
  per-tool noise seed `fault_bench._tool_noise_seed`] cannot by itself show within-instance tool heterogeneity.
- A beta-binomial spread of instance difficulty reproduces such counts with equal tools [ASSUMP].

### 3.3 Safeguards so random success is not read as transferable knowledge [FUTURE]

1. **Harm is reported as a bracket, not as p₋:**
   - max(0, −E τ) ≤ H ≤ (√(Var τ + (E τ)²) − E τ) / 2 (unit-tested);
   - Var τ comes from the replicate covariance, with its own CI;
   - p₋ is still reported, but labelled "realised, includes optimizer noise".
2. **Transfer is credited only out of base**, through LOBO. Instance-level claims ("memory hurt robot x") are not made: with
   R ≤ 2, Q̂(x, a) ∈ {0, ½, 1}.
3. **Memory labels are single draws,** for both memory and baselines. The shuffled-memory control (H4) keeps the noise
   structure and breaks only the feature-to-outcome link.
4. **The informative-instance count is retired as a gate.** It is replaced by the variance component E[V_Q] with a CI
   (§2.3).
5. **Noise is measured, not assumed:**
   - flip rate f = P(Y_rep1 ≠ Y_rep2 | x, a) per tool;
   - E[Q(1−Q)] from the replicate cells.

---

## 4. Corrected precision and power (auditor item 3)

### 4.1 Constraints, now enforced in code

For d ∈ {−1, 0, 1}, with q = P(d ≠ 0) and δ = E[d]:
- **Pair constraint:** |δ| ≤ q (`check_dq`). Var(d) = q − δ² follows.
- **Marginals constraint:** for paired binary outcomes with marginals p_a and p_b, |p_a − p_b| ≤ q ≤ min(p_a + p_b,
  2 − p_a − p_b) (`check_marginals`).
- **Design checks:** G ≥ 2, m ≥ 1, ρ ∈ [0, 1], inflation ≥ 1 (`check_design`).
- **MDE:** solved in closed form, δ = K √(q / (n_eff + K²)). The function returns *undetectable* when the solution would
  exceed q.
- **Tests:** a brute-force check that |δ| ≤ q for every distribution on {−1, 0, 1}, and rejection of revision 1's impossible
  cells.
  - Revision 1 §6.2 C quoted δ = 0.15 at q = 0.10.
  - Its MDE table quoted 0.104 at q = 0.10.
  - Both are impossible.

### 4.2 Normal approximation versus few-cluster intervals [ASSUMP]

**Coverage of nominal 90 % intervals** (synthetic, 2,000 replications, m = 2; calc §D):

| G | q | ρ | z, CR0 | **t(G−1), CR1** | percentile cluster bootstrap |
|---|---|---|---|---|---|
| 8 | 0.15 | 0.3 | 0.844 | 0.857 | 0.656 |
| 8 | 0.42 | 0.3 | 0.862 | 0.900 | 0.820 |
| 12 | 0.15 | 0.3 | 0.865 | 0.883 | 0.738 |
| 12 | 0.42 | 0.3 | 0.851 | 0.892 | 0.846 |
| 24 | 0.15 | 0.3 | 0.867 | 0.895 | 0.840 |
| 46 | 0.42 | 0.3 | 0.885 | 0.896 | 0.888 |

**Pre-declared consequences** [FUTURE]:
- The primary interval is **CR1 with t at G−1 degrees of freedom**.
- The percentile base-cluster bootstrap, which P0 used, is a sensitivity analysis only.
- **No confirmatory inference with G < 12.** At G = 8 even t intervals undercover, and 8.8 % of datasets have SE = 0 at
  q = 0.15.
- Every precision number in calc §C is printed twice: z | t. The t value is the one used.

### 4.3 Cross-fitted policy learning (calc §E, exact P0 learner, synthetic data) [ASSUMP]

**Method:**
- `creature_forge.experience_p0` was run unchanged on synthetic data: LOBO outer folds, inner LOBO k choice over
  {1, 3, 5, 9, 15, 25}, Laplace kNN and argmax decision.
- Three scenarios: null; observation sufficient; interventions add information.
- The variance of the interv − obs_morph estimate across synthetic datasets is compared with the mean squared *naive* CR1
  SE, which treats the cross-fitted policies as fixed.

| G | scenario | sims | procedure estimand | variance inflation (naive → true) | P(naive SE = 0) | naive t90 coverage, all / SE > 0 |
|---|---|---|---|---|---|---|
| 12 | null | 200 | −0.001 | 1.18 | 0.73 | 0.26 / 0.94 |
| 12 | observation sufficient | 200 | −0.001 | 1.38 | 0.35 | 0.58 / 0.89 |
| 12 | interventions add information | 200 | +0.018 | 1.31 | 0.36 | 0.58 / 0.91 |
| 24 | null | 80 | −0.000 | 1.08 | 0.10 | 0.78 / 0.86 |
| 24 | observation sufficient | 80 | +0.004 | 1.11 | 0.03 | 0.89 / 0.91 |
| 24 | interventions add information | 80 | +0.069 | **2.25** | 0.04 | **0.66 / 0.69** |
| 46 | all three | — | **not computed** | — | — | — |

- The MC relative sd of each inflation ratio is about 0.10 at G = 12 and 0.16 at G = 24.
- The G = 46 runs (30 simulations each) were stopped by Claude Code's memory-pressure guard before finishing. They were not
  restarted. To reproduce: `p05_inflation_run.py <worktree> 46 <0|1|2> 30 infl2/G46_s<i>.json`.

**Interpretation** [ASSUMP]: the naive interval is unreliable in two distinct ways.
- **Degeneracy.** When neither representation carries usable information, the two policies often pick identical tools on
  every instance. The naive SE is then 0 and the "interval" is the point 0. This happened in 73 % of datasets at G = 12
  under the null.
- **Undercoverage when there is signal.** When interventions do carry information, the true sampling variance is up to
  **2.25×** the naive estimate (G = 24), and nominal 90 % intervals cover about 0.66–0.69.

**Consequences:**
- Sizing (§4.5) uses inflation ∈ {1, 2, 3}, with 2.7 (the upper 90 % Monte Carlo bound of 2.25) as the conservative value
  in R3.
- The refit bootstrap (§4.4) is mandatory, not optional.
- A zero naive SE is reported as "degenerate: the policies agree everywhere". It is never a zero-width CI.
- The estimates come from one synthetic generative model, so the factors are illustrative, not properties of Creature Forge.

### 4.4 Refit-bootstrap sensitivity (justification) [FUTURE]

**Why it is needed:** the naive interval treats the out-of-fold picks as fixed. It ignores that a different set of training
bases yields different policies.

**Procedure:**
- Resample bases with replacement (B = 200, fixed seed).
- Duplicated bases keep **one group label**, so LOBO holds them out together and no base can neighbour its own copy.
- Re-run the entire pipeline: standardisation, inner k choice, kNN, decision.
- Take the percentile interval of the estimates.

**Use:**
- It is reported next to the primary interval, never instead of it.
- **Rule:** if the refit interval is wider than the primary by more than 25 %, the result is reported as
  "learning-variance-limited", and the four-outcome classification (§8.1) uses the **wider** interval.

**Why this is justified:** calc §E shows the naive SE can be materially too small when information is present. The refit
bootstrap is the only interval here that includes refitting variance. Its own few-cluster coverage is unknown; a synthetic
check at G = 12 is proposed as an offline pre-registration computation before A11 (it was not run here, because it costs
about 200× section E).

### 4.5 Sizing table (calc §C2, t-based, power 0.80, one-sided α 0.05) [ASSUMP]

Minimum detectable effect, rows of q × ρ × learning inflation (infl):

| q | ρ | infl | 24×2 | 28×2 | 34×2 | 40×2 | 40×3 |
|---|---|---|---|---|---|---|---|
| 0.15 | 0.2 | 1 | 0.146 | 0.136 | 0.124 | 0.115 | 0.102 |
| 0.15 | 0.2 | 2 | undetectable | undetectable | undetectable | undetectable | 0.140 |
| 0.30 | 0.2 | 2 | 0.273 | 0.256 | 0.236 | 0.220 | 0.198 |
| 0.42 | 0.2 | 2 | 0.323 | 0.303 | 0.280 | 0.261 | 0.234 |

"Undetectable" means the closed-form solution would exceed q: no admissible effect reaches 80 % power.

**Bases needed** at m = 2 (calc §C3):
- δ = 0.10, q = 0.15, ρ = 0.2: **54** (infl = 1) to **106** (infl = 2);
- δ = 0.15, same q and ρ: 23–44;
- **δ = 0.05 needs 147–1,860 bases. It is out of reach.**

**Conclusion** [ASSUMP]:
- With ≤ 40 confirmatory bases, only learned-policy effects of roughly **0.10–0.30** decision value are reliably
  detectable. The low end (≈ 0.10–0.14) is reached only with low discordance (q ≈ 0.15), little learning inflation and
  m_inst = 3.
- The plausible size from the proxy history [HIST: −0.006] is far below that.
- The confirmatory study is therefore mainly an **estimation** study:
  - a benefit verdict is reachable only for large effects;
  - an equivalence verdict needs half-width < m (§8.1).

---

## 5. Protecting confirmatory inference: external pilot (auditor item 4)

### 5.1 Choice: an external pilot, excluded at base level [FUTURE]

- Revision 1's "blinded internal pilot" was incoherent: its continuation rules required tool-effect quantities (headroom,
  between-tool variance), so it could not be blind.
- A valid internal pilot would need either a blinded nuisance-only re-estimation (Kieser–Friede type), which cannot use
  tool-effect quantities, or a pre-specified adaptive combination test. With G ≤ 40 clusters, a combination test would cost
  power that this study cannot spare.

**Therefore:**
- Pilot instances **and their bases** are excluded from every confirmatory analysis, training fold and memory bank.
- Base-level exclusion matters. Shared bases would carry base random effects from pilot into campaign, so a
  pilot-dependent decision could select on those effects. Under I9, disjoint bases make the confirmatory data independent of
  the pilot data given the design. Any design choice made from the pilot then cannot bias confirmatory inference.
- **No blinding is claimed.** All pilot results are reported to the auditor in full and labelled exploratory.
- **Price:** 6 bases. A confirmatory maximum G of 40 instead of 46.

### 5.2 Pilot design [FUTURE]

- **Bases:** 6, drawn with a declared seed from the eligible pool, stratified 4 hdb-v1, 1 walkrec-m1, 1 hand, so that each
  generator group's failure modes are exercised (open question D7).
- **Instances:** 2 per base, distinct families.
- **Cells:**
  - the full feasible matrix with R = 2 for every cell: ≤ 240 cells;
  - two phase-2 cost-matched cells per instance (§7.3);
  - two selector-confirmation cells per instance;
  - 3 sentinels;
  - deterministic re-execution of a random 5 % of cells.

### 5.3 Pilot outcome rules (mechanical; code hash-pinned before the pilot) [FUTURE]

Checks are evaluated in this order. The first triggered category wins.

| category | trigger |
|---|---|
| **STOP** (report; no campaign) | S1: sentinel not bit-identical. S2: any re-executed cell not bit-identical. S3: non-infrastructure ERROR in > 5 % of cells. S4: any infrastructure ERROR that deterministic re-execution with identical seeds does not resolve. S5: a leakage canary changes any prediction, or the positive-control leak is not detected. S6: ledger and billing disagree by > 10 %. S7: measured rollout-equivalents per cell > 3× the Stage-0 measurement. |
| **REDESIGN** (new proposal) | R1: median feasible tools per instance < 5, or < 3 in any generator group. R2: pooled matrix FULL rate with a 90 % upper bound < 0.05, or a lower bound > 0.95 (floor or ceiling at budget B). R3: projected confirmatory 90 % half-width for the H1 contrast > owner margin m. |
| **HOLD** (separate cap decision A10) | The projected campaign cost (90 % upper bound of measured per-cell cost × planned cells, + 25 % reserve) exceeds the approved cap. |
| **EXPAND** (request campaign approval A11) | None of the above. |

**R3 inputs, fixed in advance:**
- G_conf is the confirmatory base count from §9.
- m_inst ∈ {2, 3} is chosen by cost.
- ρ = 0.3 [ASSUMP]: the pilot cannot estimate it usefully.
- Inflation = 2.7: the upper 90 % Monte Carlo bound of the largest calc §E ratio (2.25, G = 24, "interventions add information"). It is to be replaced by the G = 46 value if that is computed before the pilot.
- q̂ = the pooled discordance between random pairs of distinct feasible tools on the same instance. This is an upper-range
  proxy for discordance between two policies, with a 90 % upper bound.
- t intervals with G_conf − 1 degrees of freedom.

**Deliberately absent:** any headroom or "informative rate" rule (§2.4, §3.2).

---

## 6. The exact P0 intervention representation for H1 (auditor item 5)

**Source.** Blob hashes at `e3caf81` [HIST]:

| file | blob |
|---|---|
| `creature_forge/experience_p0.py` | `dcfb1f29cc14ea05bb4bb80eb9d18240a81b3360` |
| `creature_forge/experience_bank.py` | `38aed182696d5d46cf992e7bd4e9d138e6a6a0f4` |
| `scripts/exp_p0_audit.py` | `dbaa4d34cb83bfc6fdfd0b456aaf3be72753ec98` |

The confirmatory run must import these unchanged, and verify the hashes.

**Notation.** For instance x with nominal body b(x), observation O₀ (median over the 4 obs seeds, from `hidden_plant.observe`,
the same output shape as `physics_probe.observe` [HIST `hidden_plant.py:444`]) and catalogue responses O_c for
c ∈ C = `eng_tools.COUNTERFACTUALS`:

- **morph block**, 7 columns: m(x) = `experience_audit.morphology`(b(x)) over `MORPH_KEYS` = (L, foot_to_leg, torso_mass,
  leg_density, foot_friction, tau_proxy, leg_asym) ([HIST] `experience_audit.py:164–178`). It is computed from the
  **nominal** design.
- **obs block**, 14 columns: o_k(x) = s⁰_k for k ∈ `CE_OBS_KEYS` (= `OBS_KEYS`), where s⁰ = `compute_signature`(O₀.median,
  {}) ([HIST] `experience_bank.py:32–35, 75–`; `experience_p0.py:278, 321–323`).
- **cf block**, 9 × 8 = 72 columns: for each c and k ∈ `CE_CF_KEYS` = (time_upright, fall_direction, pitch_end,
  com_vx_end, step_length_over_L, slip_fraction, capture_margin_over_L_end):
  - Δ_{c,k}(x) = s^c_k − s⁰_k, with s^c = `compute_signature`(O_c.median, {});
  - plus Δ_{c,walk}(x) = (n_walking(O_c) − n_walking(O₀)) / 4 ([HIST] `experience_p0.py:279–280, 324–330`);
  - an unavailable c gives NaN.
- **Standardisation:** z_j = (x_j − μ_j) / σ_j, with μ and σ the training-fold nanmean and nanstd. σ ≤ 1e−9 is set to 1;
  NaN maps to 0 ([HIST] `Space.dist`, `experience_p0.py:38–53`). Column scaling such as the /4 is therefore immaterial.
- **Distance:** D(x, x′) = Σ_{B ∈ use} mean_{j ∈ B} (z_j(x) − z_j(x′))². Equal block weights are fixed a priori.
- **Rates:** P̂(a | x) = (Σ_{i ∈ kNN(x)} Y_{i,a} + p̄_a) / (k + 1), with p̄ the training-fold tool means ([HIST]
  `knn_rates`, lines 56–60).
- **k:** chosen from {1, 3, 5, 9, 15, 25} by inner leave-one-base-out log loss ([HIST] `choose_k`, lines 95–111).
- **Decision:** argmax_a P̂(a | x) + 10⁻⁹ p̄_a ([HIST] `decide`, lines 141–143).
- **Methods:** `interv` uses = (obs, morph, cf); `obs_morph` uses = (obs, morph) ([HIST] `scripts/exp_p0_audit.py:25–26`
  `CE_METHODS`).
- **Confirmatory H1 contrast:** V(interv) − V(obs_morph), LOBO, replicate-1 cells.

**Execution path.** HDB rows are written in the probe-row schema `{base_id, instance_id, robot.body, observation{median,
n_walking}, counterfactuals{c: {observation}}, repair_matrix}`, with repair_matrix[a] = 1.0 if FULL else 0.0. They then pass
through `ce_dataset` unchanged, so `CE_REPAIRS = 0.75` maps FULL to 1.

**What differs from P0, and is declared:**
1. The label is FULL_VERIFIED, not the walking proxy.
2. The fault is hidden in the plant, not visible in the body.
3. The bench is HDB, not the fault bench.
4. The repair plant budget is B, not 160 (unless the owner sets B = 160, D3).

The transformation itself is identical.

**Secondary and exploratory representations,** each a separately identified hypothesis, never confirmatory for H1:
- **H2, secondary:** residual coding. Δᴿ_{c,k} = Δ_{c,k}(plant) − Δ_{c,k}(nominal twin), from D_twin. It uses the **same**
  plant information as `interv`, plus twin compute only.
- **Exploratory:** a raw-response coding (catalogue medians without subtracting the observation); the `cf_only` block
  ([HIST]: an exploratory proxy lead); identifiability-panel instruments (floor test, weigh). Each is labelled exploratory
  with no claim.

---

## 7. Cost-matched comparisons and information sets (auditor item 6)

### 7.1 Who pays for what

| policy | information it may use | plant rollouts charged before repair |
|---|---|---|
| π0 (P0 `prior`) | none (training-fold frequencies) | 0 |
| obs_morph | D_obs + nominal design | 4 |
| interv (H1) | D_obs + D_cat + nominal design | 40 |
| residual (H2) | D_obs + D_cat + D_twin + nominal design | 40 (+ 40 twin) |
| engine-posterior baseline (B5, optional) | the engine's own diagnostic experiments | as the engine spends them, logged |

**In deployment:**
- A policy that does not use the catalogue **skips** it and keeps those 36 plant rollouts.
- In this study, the prefix runs everything once per instance, for measurement only. Because R_B uses no diagnostic output
  (§1.1), running the prefix gives a no-panel policy no hidden advantage.
- Each policy's features are restricted to its row of the table. This is enforced by column-group allow-lists (§10).

### 7.2 Matched-total-cost comparators [FUTURE]

The plant rollouts a policy did not spend on diagnosis are given back to it as extra repair budget:
- **C1:** obs_morph's cross-fitted pick, repaired at B + 36. Its total equals interv's: 4 + 36 + B.
- **C2:** π0's pick, repaired at B + 40. Its total also equals 40 + B.

### 7.3 How phase-2 cells work [FUTURE]

- The picks are determined only after the matrix exists: LOBO fits on other bases, then predicts with the instance's own
  legal features.
- Phase 2 runs one fresh cell per instance for C1 and one for C2, with new optimizer seeds and the instance's shared
  verification seeds.
- These cells estimate Q_{B+36} and Q_{B+40} at the chosen tool only. They are separate estimands, not matrix entries.

**Cost-matched benchmark contrasts:**
- V(interv; B) − V(obs_morph-pick; B + 36);
- V(interv; B) − V(π0-pick; B + 40).

Both are reported with the §8.1 partition. Matched totals mean λ is not needed for these comparisons.

### 7.4 Cost formulas (deliverable 4)

All in rollout-equivalents (RE). A plant or twin rollout at 10 s = 1 RE; a 20-s confirmation rollout = 2 RE.

| symbol | meaning | value |
|---|---|---|
| V_cell | verification per verified design | (24 if the original is not cached, else 0) + 24 + p_pass · 24 · 2. Code-derived structure [HIST `recovery.assess`]; p_pass [ASSUMP] |
| C_prefix | diagnosis per instance | 4 + 9 · 4 + n_twin [HIST structure; n_twin 0 or 40 per H2 choice] |
| C_cell(B) | one repair cell | B + V_cell |
| matrix | the full matrix | N_inst · T · R̄ · C_cell(B) + N_inst · 24 · [original cached] |
| cost-matched | phase-2 cells | N_inst · [C_cell(B + 36) + C_cell(B + 40)] |
| selector-confirmation | headroom cells | N_rep_inst · 2 · C_cell(B) |
| sentinel | determinism checks | n_sent · 3,134 [HIST: one A1e6 episode, 615 plant + 2,519 twin] |
| Stage E | physics-only eligibility, one-time per base without a verified threshold file | n_E · (13 · 7 · 8 + 39 · 8) = n_E · 1,040 [HIST structure: 13 variants, 1 + 6 bisection evaluations, 8 check seeds, 39 candidate instances per base] |
| VM hours | — | RE / throughput · (1 + idle) + sessions · overhead_h |
| dollars | — | VM hours · price_h |

**Assumption sets** [ASSUMP; every price unverified until billed]:

| input | low | mid | high | notes |
|---|---|---|---|---|
| B | 160 | 300 | 700 | |
| p_pass | 0.15 | 0.3 | 0.5 | |
| throughput (RE/h) | 46,800 | 31,200 | 15,600 | mid is the W3 rate [HIST, measured for a different workload] |
| price ($/h) | 0.269 | 0.269 | 0.60 | $0.269 is the ledger-recorded main-VM rate [HIST, not billing-verified] |
| overhead (h/session) | 0.25 | 0.5 | 1.0 | |
| sessions | 2 | 3 | 5 | |
| idle fraction | 10 % | 20 % | 35 % | |
| original validation | cached | not cached | not cached | |

**Results** (calc §H):

| design | low | mid | high |
|---|---|---|---|
| Stage 0 (local, $0 cloud) | 7.9 k RE, 0.7 h local | 12.0 k RE, 2.0 h | 21.8 k RE, 6.9 h |
| **Pilot** (6 × 2, R = 2, full matrix, phase 2, sentinels) | 66 k RE, **$0.55** | 116 k RE, **$1.60** | 234 k RE, **$15.13** |
| Campaign 28 × 2 (25 % R = 2) | 178 k, $1.26 | 323 k, $3.74 | 667 k, $37.61 |
| Campaign 36 × 2 | 226 k, $1.56 | 412 k, $4.67 | 854 k, $47.36 |
| Campaign 36 × 3 | 334 k, $2.25 | 613 k, $6.75 | 1.28 M, $69.30 |
| Stage E, 18 bases / 48 bases | 18.7 k / 49.9 k RE | $0.60 / $0.92 (mid) | $3.97 / $5.59 (high) |

**Against the cap:**
- The remaining cap is **$6.595** ($96 − $89.405) [HIST, owner to confirm].
- The pilot fits under the low and mid sets, but not the high set. Its hard dollar stop must sit below the remaining cap.
- The campaign fits only under low or mid assumptions; the high set needs the separate cap decision (A10).

---

## 8. Hypotheses and acceptance rules (auditor item 7)

### 8.1 One outcome partition for every contrast [FUTURE]

**Inputs:**
- The estimate, its interval [L, U] (90 % two-sided for primary contrasts; 95 % for the Bonferroni-adjusted secondaries H2
  and H3), the one-sided p-value against 0 and the one-sided p-value against m. All are reported.
- **m** is the owner's minimum meaningful effect (D1).
- The interval is the primary CR1 t interval, replaced by the refit-bootstrap interval when §4.4's rule applies.

| outcome | condition |
|---|---|
| **Supported benefit** | L > 0 and U ≥ m. Additionally flagged "meaningful benefit established" if L ≥ m. |
| **Supported practical equivalence / no meaningful gain** | 0 ≤ U < m. Flagged "equivalence" if additionally L > −m. A statistically positive result with U < m falls here, explicitly labelled. |
| **Supported harm** | U < 0. Flagged "meaningful harm" if U < −m. |
| **Inconclusive** | L ≤ 0 and U ≥ m. **An interval that includes 0 is never called a falsification.** |

The four outcomes partition all (L, U). If the planned half-width exceeds m, "no meaningful gain" is effectively
unreachable, and that is said before data collection.

### 8.2 The hypotheses [FUTURE]

| | primary estimand | strong control | uncertainty | notes |
|---|---|---|---|---|
| **H1** (primary) | V(interv) − V(obs_morph), procedure estimand, LOBO, replicate 1 | the same learner, grid and folds; shuffled-memory interv (H4a); cost-matched benchmark C1 reported alongside | CR1 t(G−1) at 90 %; refit-bootstrap sensitivity | §8.1 outcomes, plus the point estimate relative to m |
| **H0** | Δ_comb = V(obs + morph + cf + residual) − V(obs_morph), the same learner family | as H1 | as H1 | H0 is the *equivalence* reading: "supported no meaningful gain" for Δ_comb **and** Δ_int. Any "supported benefit" contradicts H0. |
| **H2** (secondary) | V(obs + morph + residual cf) − V(interv): the same plant information, different coding; LOGO across generator groups with ≥ 8 bases, LOBO reported | its own estimand only | CR1 t at 95 % (Bonferroni with H3) | The engine-posterior baseline B5 is a separate **deployment benchmark** with different information. It never decides H2. |
| **H3** (secondary) | V(interv gated at coverage 0.5, fallback π0) − V(interv with a random gate at coverage 0.5) | random gate at matched coverage (diagnostic cost identical, so it cancels); similarity gate; benchmark against C2 (π0 at B + 40, the same total cost) | CR1 t at 95 % | Gate = P̂(pick) − P̂(π0), threshold fitted on the training fold. Realised p₋ is also reported, labelled as including noise. |
| **H4** (validity) | absolute contrasts (§8.3) | — | — | Deterministic checks pass or fail, and contrasts use the §8.1 partition. |

### 8.3 H4: absolute contrasts and leakage checks [FUTURE]

The ratio-to-memory-gain criterion is withdrawn.

| check | estimand or test | reading |
|---|---|---|
| H4a: shuffled memory | Δ_shuf = V(π_M) − mean over 20 permutations of V(π_M^shuf), k fixed per fold to the real run's | §8.1 partition. Memory is credited only if Δ_shuf is "supported benefit". |
| H4b: base fingerprinting | Δ_fp = V_LOIO(π_M) − V_LOBO(π_M) (LOIO = leave one instance out) | Reported. A "supported benefit" means memory exploits same-base similarity; LOBO is already the primary, so this explains the gap but cannot inflate H1. |
| H4c: historical-policy imitation | by design: no historical labels and no engine-ranking features in H1 | static test that no feature column comes from a historical record or an engine output |
| H4d: warm start | by design: every cell starts from the nominal design | per-cell initial-mean hash = nominal-design hash; any mismatch is a STOP |
| H4e: leakage canaries | a random column in each forbidden group must leave predictions **bit-identical**; a positive control (true family inserted, in a copy of the pipeline) must change them | failure of either is a STOP |
| H4f: id and morphology leak | opaque ids; the feature builder's input design hash = the nominal design hash | failure is a STOP |

**Verdict:**
- **"H4 supported (artefact)"** if H4a is not "supported benefit", or any of c–f fails.
- **"H4 rejected"** if H4a is "supported benefit" and all of c–f pass.
- No H1–H3 memory claim is made unless H4 is rejected.

---

## 9. Feasible bases and tool coverage (auditor item 8)

### 9.1 What the committed evidence establishes

- **Declared:** 48 development bases (`stage2_split.json`): hdb-v1 36, walkrec-m1 8, hand 4 [HIST].
- **Not verified:** none of them is shown eligible for a single homogeneous FULL-verifier protocol (hdb_v2 single-mechanism
  instances, threshold-relative severities, `full_recovery_v1`, one seed scheme). The threshold and instance-pool files that
  would show it are **not** in P0's hash-pinned provenance [HIST].
- **Not used:** `hdb_bench.load_bases` reads the walker file that also holds sealed test designs [HIST
  `hdb_bench.py:277–304`]. It was not called, and must not be called to answer this question.

| tier | bases | committed evidence [HIST] | status for P0.5 |
|---|---|---|---|
| T1 | 18 hdb-v1 *experience* bases (0004 … 0064) | hdb_v2 FULL-verified outcomes in ≥ 8 of 9 families; 12 of them also have eligible identifiability-panel instances | strongest candidates |
| T2 | 12 old-dev bases: 4 hand (stilts-drawn, tiny-feet, top-heavy, weak-slippery) + 8 walkrec-dev-m1-gen-0000 … 0007 | hdb_v2 outcomes in 3–6 families; panel-eligible instances in 5–9 families; 142 of the 160 ineligible-plant *records* concern these bases (records repeat across arms; most come from the early grid-severity runs). **These are the 12 causal-engineer proxy bases that generated the H1/H2 leads** (P0 §4.1). | candidates, **double-dipping risk** at base level |
| T3 | 16 hdb-v1 *transfer* bases | hdb_v2 outcomes in 1–7 families only (Stage-2 and DS-1 transfer use); `hdb-v1-gen-0070:pitch_sensor_bias:1` excluded (SCRIPTED_MOCK smoke) | candidates; family eligibility largely unknown |
| T4 | 2: hdb-v1-gen-0101, -0117 | no verified outcome in any registered file | unknown |

**Confirmatory G under the options (6 pilot bases removed):**

| option | bases | confirmatory G |
|---|---|---|
| T1 only | 18 | 12–18 |
| T1 + T3 | 34 | ≈ 28–34 |
| T1 + T2 + T3 | 46 | ≈ 34–40 |
| plus T4, if eligible | +2 | — |

The choice is the owner's (D2). **Generating new bases is not proposed;** it is a later, separate owner decision.

### 9.2 Making eligibility verifiable [FUTURE]

**E-check (zero rollouts):**
- Locate the historical hdb_v2 threshold and instance files for these bases by hash.
- Verify that the instance construction from them reproduces the instance ids and seeds in the outcome records.
- Run the feasibility screen per tool on the nominal designs, taken from development records, not from the walker file.

**Stage E (rollouts, separately authorised):** recompute thresholds and eligibility for the bases the E-check cannot verify.
Cost: about 1,040 RE per base (§7.4).

### 9.3 Generator-group imbalance [FUTURE]

- **Population estimand:** equal weight per eligible base. hdb-v1 makes up about 75 % of that weight; this is stated with
  every result.
- **By group:** estimates are reported per generator group.
- **LOGO:** only for groups with ≥ 8 bases (hdb-v1 vs walkrec-m1). The hand group is descriptive.
- **Sampling:** the pilot and the instance draws are stratified by group.

### 9.4 Feasible tool subsets [FUTURE]

- **Definition:** feasibility is decided by `run_repair`'s own refusal ("no room inside the bounds") before any rollout.
- **Policies:** each policy's action set is the instance's feasible set.
- **Coding:** an infeasible pick has Y = 0, as in P0.
- **Reporting:** the feasible-set size by tool and group. R1 (§5.3) redesigns if it is too small.

### 9.5 Seed allocation [FUTURE]

- **Instance seeds:** `hdb_bench.instance_seeds(base, family, severity)`, campaign "hdb-v1", for check, train, obs, validate
  and confirm [HIST scheme].
- **Optimizer noise seed** per (instance, tool, replicate): sha256("p05:{iid}:{tool}:{rep}") mod 2³¹.
  - It is never `fault_bench._tool_noise_seed`, which is replicate-free.
  - It is independent across tools: their search spaces differ, so shared optimizer seeds would not act as common random
    numbers.
- **Validation and confirmation seeds** are shared by all cells of an instance (common random numbers) and are never used in
  any selection.
- **Historical reuse:** these seeds were used to verify *historical* designs on the same instance keys [HIST]. Whether to
  move verification to a fresh namespace, keeping the plant and reality gap identical, is owner decision D6.

### 9.6 Correlated failures [FUTURE]

| source | treatment |
|---|---|
| Common validation seeds (intended) | positively correlates tools within an instance; the paired analysis accounts for it |
| Base-level fragility (one base errors in every tool) | ERROR counts reported by base; a base with > 50 % non-infrastructure ERROR cells is reported, and kept under intention to treat (ERROR = not FULL) |
| VM or infrastructure faults clustered in time | randomised execution order spreads them; deterministic re-execution with identical seeds is allowed **only** for infrastructure ERRORs and must be bit-identical elsewhere |
| Tool-specific numerical failure | reported per tool; counted as failure for that tool |

---

## 10. Schema and leakage contract (carried from revision 1 §4–5, with these changes) [FUTURE]

1. **Column groups** stay as in revision 1: `DECISION_LEGAL`, `TRUTH`, `ASSIGNMENT`, `OUTCOME`, `PROVENANCE`.
   `DECISION_LEGAL` is now split by information set (§7.1): `legal_obs`, `legal_cat`, `legal_twin`.
2. **Engine posterior and ranking columns** are not part of H0–H4 features. They exist only for benchmark B5.
3. **New record fields:**
   - cell: `repair_procedure = "R_B"`, `initial_mean_hash`, `noise_seed_rule`, `phase` (1 = matrix, 2 = cost-matched,
     3 = selector-confirmation), `budget_extra`;
   - instance: `verification_seed_namespace`.
4. **The analysis script** includes the P0 module blob-hash check (§6) and the H4e canary tests.

## 11. Benchmarks (summary) [FUTURE]

| id | benchmark |
|---|---|
| B0 | π0 (prior) |
| B0b | uniform random feasible tool, exact expectation from the matrix |
| B1 | obs_morph |
| B2 | interv |
| B3 | residual |
| B4 | combined |
| B5 | engine-posterior baseline (optional; different information; deployment benchmark only) |
| B6 | shuffled versions of B1–B4 |
| B7 | generic warm start (specified for P2 only) |
| C1, C2 | cost-matched comparators (§7.2) |
| Γ bracket | §2 |
| G1–G3 | predicted-benefit, similarity and random gates |

**Outcome tiers:**
- FULL_VERIFIED is the only primary tier.
- The walking proxy is recorded per cell and reported only as proxy–FULL agreement.
- Historical proxy numbers are never pooled.

---

## 12. Change log (auditor objection → revision)

| # | objection | resolution | where |
|---|---|---|---|
| 1a | Γ estimand vs replicate-split estimator mismatch | four quantities defined and ordered; separate estimators | §2.2–2.3 |
| 1b | honest intervals | identification region [L_sel, min(U_naive, U_var)] with Bonferroni t bounds; new variance-component upper bound (unit-tested) | §2.3, calc §F, tests |
| 1c | STOP treated a lower-bound selector as an upper bound | rule removed; no headroom rule in the pilot; explained why futility is not decidable at feasible sizes | §2.1, §2.4, §5.3 |
| 1d | instances, bases and repeats needed | calc §F2–F3; replicates 25 % at R = 2; gap only closes with R | §2.4–2.5 |
| 2a | separate realised p₋, expected harm, heterogeneity | three definitions; harm bracket from the replicate covariance | §3.1, §3.3 |
| 2b | analytic discordance from equal stochastic tools | exact formulas and table (q = 0.42 / 0.50 at p = 0.3 / 0.5) | §3.2, calc §G |
| 2c | noise mistaken for knowledge | six safeguards; informative-count gate retired | §3.3 |
| 3a | impossible \|δ\| > q combinations | `check_dq`, `check_marginals`, closed-form MDE returning "undetectable"; tests | §4.1 |
| 3b | q to 0.50; G = 8 … 46 plus proposed variants | grid q ∈ {0.10, 0.15, 0.25, 0.30, 0.42, 0.50}, G ∈ {8, 12, 24, 28, 34, 40, 46}, m ∈ {1, 2, 3} | calc §C |
| 3c | normal approximation vs few-cluster CIs | z and t printed side by side; coverage simulation; t(G−1) CR1 primary; no inference at G < 12 | §4.2, calc §D |
| 3d | cross-fitting uncertainty; refit sensitivity | exact-P0-learner synthetic inflation; refit-bootstrap rule | §4.3–4.4, calc §E |
| 3e | approximate power presented as measured | every calculated number labelled [ASSUMP] | throughout |
| 4 | pilot adaptation vs confirmatory reuse; blinding | external pilot, excluded at base level; blinding claim withdrawn; mechanical rules | §5 |
| 5 | preserve the exact P0 `interv` | formula, code lines and blob hashes; execution through `ce_dataset` unchanged; raw and residual codings secondary or exploratory | §6 |
| 6a | the π0 cell received panel information | diagnosis-independent repair R_B; information-set table | §1.1, §7.1 |
| 6b | genuinely matched total cost | phase-2 cells C1 (B + 36) and C2 (B + 40) | §7.2–7.3 |
| 6c | cost script components | augmented budget, sentinels, Stage E, Stage 0, overhead, idle, sessions, caching; prices unverified | §7.4, calc §H |
| 7a | H1: statistical evidence plus owner margin | point, CI, p vs 0 and vs m; §8.1 partition | §8.1–8.2 |
| 7b | CI including 0 called a falsification | now "inconclusive" | §8.1 |
| 7c | H2 judged against a different-information model | H2 = residual vs interv on the same plant information; B5 is a benchmark only | §8.2 |
| 7d | H4 ratio criterion | absolute contrasts plus deterministic checks | §8.3 |
| 7e | four outcomes per hypothesis | one partition for all | §8.1 |
| 8a | 46 historical bases assumed eligible | tiered; none verified; E-check and Stage E | §9.1–9.2 |
| 8b | generator imbalance, tool subsets, seeds, correlated failures | §9.3–9.6 | §9 |
| 8c | no new bases by default | stated | §9.1 |

---

## 13. Approval checklist, revised (each item a separate decision; none is requested as granted)

- [ ] **A0.** Apply the accepted DS-1 corrections C1–C8 (revision 1 §12) as a documentation-only commit on the V2 branch.
- [ ] **A1.** The estimands (§1–2), including diagnosis-independent repair R_B and the three headroom quantities.
- [ ] **A2.** The base protocol: tier choice (D2), the E-check (zero rollouts) and generator-group handling (§9).
- [ ] **A3.** The confirmatory H1 representation, exactly P0's (§6), and hypotheses H0–H4 with the §8.1 partition, margin m
  and multiplicity.
- [ ] **A4.** The schema, information-set allow-lists, canaries and positive-control leak test (§10, §8.3).
- [ ] **A5.** The statistical plan: CR1 t(G−1) primary; the refit-bootstrap rule; no confirmatory inference at G < 12;
  replicate allocation (§2.5, §4).
- [ ] **A6.** Implement the harness and tests, including the plant-aware `cma_fn` for R_B and phase-2 scheduling. No runs.
- [ ] **A7.** Stage 0: local MuJoCo, $0 cloud. Sentinel, one instance's full matrix with R = 2, phase-2 cells.
- [ ] **A8.** Stage E, only for bases the E-check cannot verify. Count and rollout ceiling stated.
- [ ] **A9.** External pilot (§5) with explicit rollout and dollar ceilings inside the remaining cap.
- [ ] **A10.** Budget cap decision: separate, and only after measured pilot costs.
- [ ] **A11.** Campaign plus confirmatory analysis at a frozen, hash-pinned commit, with the runner named (D10).

## 14. Remaining owner decisions, ranked by effect on feasibility

| rank | decision | why it matters |
|---|---|---|
| D1 | Minimum meaningful effect m | With G ≤ 40, only about 0.10–0.30 is detectable (§4.5). A smaller m makes "benefit" and "no meaningful gain" both near-unreachable. |
| D2 | Confirmatory base set | T1 only (G ≈ 12–18, nearly uninformative); + T3 (≈ 28–34); + T2 (≈ 34–40, with double-dipping risk). Whether new bases may ever be generated is a later, separate decision. |
| D3 | Repair budget B, and acceptance of diagnosis-independent repair | Cost scales about ×2–4 between B = 160 and 700. R_B sets external validity (§14). |
| D4 | Budget cap and confirmation of the real credit balance | Pilot $0.55–15 and campaign $1.3–69 across the assumption sets. |
| D5 | Instances per base m_inst and the replicate fraction | precision vs cost; the headroom bracket |
| D6 | Verification-seed namespace: reuse historical instance seeds, or fresh ones with the same plant | used-once principle vs comparability |
| D7 | Pilot composition (4/1/1 by group) and base consumption | Uses 1 of the 4 hand bases. |
| D8 | Confirmation stage per cell; caching of original validation | about 20–35 % of verification RE |
| D9 | Include the engine-posterior benchmark B5 | implementation risk only; it never decides H0–H4 |
| D10 | Who runs the confirmatory analysis | auditor-run vs auditor-verified |
| D11 | λ | needed only for comparisons that are not cost-matched; all primary ones now are |

## 15. Scientific self-critique: what cannot be established before new FULL-verifier data

1. **Whether HDB tools differ at all, within instance, at budget B.** No historical record identifies it. The proxy matrix
   used single draws with replicate-free seeds, and the HDB records are policy-selected.
2. **The magnitudes of q, ρ, E[V_Q], the flip rate and costs.** Every sizing number rests on assumed ranges. The synthetic
   scenarios (calc §E–F) are arbitrary generative models, and the inflation factors they give are model-dependent. Section E
   is missing its G = 46 cells.
3. **Headroom absence.** Even the full campaign cannot show Γ < 0.1 unless tools are nearly identical (§2.4). A null H1 will
   remain compatible with real but unlearnable headroom.
4. **Eligibility and feasibility of any base.** The committed evidence verifies none.
5. **External validity of R_B.** Plant-only, diagnosis-independent repair is cleaner causally but differs from the engines'
   twin-assisted repair. Tool effects and the decision value of diagnosis may differ in deployment.
6. **Transport.** Nothing here says anything about the sealed test population. LOGO with two usable generator groups is
   weak evidence of cross-generator transport.
7. **Few clusters.** With G ≈ 28–40, t intervals are adequate in synthetic checks (calc §D). The refit bootstrap's own
   coverage is unverified, and real base heterogeneity may be heavier-tailed than the simulation.
8. **The representation is not optimised.** P0's equal block weights and kNN are kept for exactness. A null H1 is a
   statement about this representation and learner, not about interventional information in general.
9. **Double dipping.** If T2 bases are included, the hypotheses were partly generated on them, although on a different
   bench and outcome.
10. **The P0 verdict stays INSUFFICIENT-DATA.** Nothing in this proposal is evidence for or against repair memory. It only
    specifies how new FULL_VERIFIED data could answer the question, and at what effect sizes it could not.

*End of revision 2. No implementation, Stage 0, simulation, cloud spend, campaign or confirmatory evaluation has been
started. Awaiting independent review and explicit owner authorisation.*
