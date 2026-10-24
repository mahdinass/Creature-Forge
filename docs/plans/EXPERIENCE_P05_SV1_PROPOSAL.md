# Creature Forge V2: P05-SV1 proposal, the statistical validation of the experience-learning inference procedure

**Document:** CF-V2-P05-SV1-PLAN, draft 2 (2026-10-23). It is planning only.

**Draft 2 resolves the owner's six review items:**

| # | item | where |
|---|---|---|
| 1 | Complete SV1 proposal saved in the repository; SV0 proposal archived | N1 deliverables (§10) |
| 2 | Estimand audit (θ_G, θ(D), θ_new), truth precision, pilot blinding | §2A |
| 3 | Budget recheck, real parallel strategy, CPU quota, benchmark before projection | §9 (rewritten) |
| 4 | Admission, selection and independent evaluation separated | §6A |
| 5 | "Not validated" versus evidence of invalidity | §6B |
| 6 | D-1 to D-7 reconciled against the frozen protocol | §11 (rewritten) |
- Nothing has been executed. No VM has been started, nothing installed, nothing committed.
- The SV0 proposal of record (revision 4b, completed) is archived verbatim in
  `experiments/causal_engineer/dev/experience_p05/sv0/PROPOSAL_SV0_rev4b.md`.

## 0. Context

**What SV0 established** (attempt 2, PASS; attempt 1 FAIL preserved):
- In the fingerprint below, on synthetic fixtures, the P0 learner, the refit wrapper (`sv0_lib.replicate`), the H4 calculator
  and the interval helpers compute what the protocol specifies.
- They do so deterministically.

**What SV1 must answer:**
- Do the candidate intervals have valid **coverage** when the policy being evaluated is *learned* by the P0 procedure?
- That procedure involves an argmax, data-driven k from inner CV, nearest-neighbour sets, and duplicated bases under resampling.
- This is statistical validity, a separate question from SV0's implementation correctness.

**Why it matters:**
- Protocol §5 / E1: if no method is admissible, every P0.5 confirmatory contrast is "inference not validated".
- Prior synthetic evidence (calc §E, G = 24) found that the naive SE undercovers learned policies, with coverage 0.66–0.69.
- Refit-bootstrap coverage is unknown.
- **A negative SV1 is a legitimate, decision-relevant result.**

## 1. SV0 closure check (done, read-only)

| item | finding |
|---|---|
| SV0-4 "missing row" | **A summary formatting gap, not a missing result.** The canonical JSON has SV0-4 PASS 30/30 in both attempts: 12 items under 4a (order-preserving) and 18 under 4b (non-monotone), plus 18 4c diagnostics. |
| Nine stages | **Attempt 2:** SV0-0 to SV0-8 all PASS: 50, 23, 12, 104, 30, 36, 34, 10, 10 items. **Attempt 1:** identical, except SV0-5 at 26/27, so FAIL. |
| Code hashes | `sv0_lib` `7ca9658d…`, `sv0_reference` `ec34f409…`, `sv0_run` `03e7a2f0…` (attempt 2) and `0708b7e8…` (attempt 1, kept in `sv0/attempt1/`). |
| Fingerprint | venv `/home/forge/venvs/creature-forge`; Python 3.12.3; numpy 2.5.4 (config `2ab35740…`); `Linux-6.11.0-1016-nvidia-x86_64-with-glibc2.39`; AMD EPYC-Genoa (flags `2635ea8b…`); manifest `af2cf766…` (29 dists); pip freeze `def4117c…`; HEAD `afe33ca`. |
| Results | Attempt 2 `sv0_results.json` `861372bd…`, byte-identical across both runs. Attempt 1 `d73e46f6…`. Both `SHA256SUMS` re-verify 9/9 now. |
| **Gap** | No single evidence manifest ties these together; they are spread over `out/SHA256SUMS`, `sv0_env.json` and `attempt1/PROVENANCE.txt`. **N1 writes `sv0/MANIFEST.md`.** |
| Uncommitted | Modified: `docs/EXPERIENCE_P05_HANDOFF.md` and `docs/plans/EXPERIENCE_P05_PROTOCOL.md` (C1–C3). Untracked: `experiments/causal_engineer/dev/experience_p05/sv0/` (3 code files, `attempt1/`, `out/`). The two `launcher/launcher.log` files are **git-ignored** (`*.log`), so a future commit must force-add them, as was done for `infl2/*.log`. VM copies remain in `~/sv0` and `~/sv0_attempt1`. HEAD is still `afe33ca`. |

## 2. Estimands and ground truth (synthetic, known Q)

Each synthetic dataset D has G bases × m = 3 instances, drawn from calc §E `_synth` with the scenario's fixed parameters. The
true repair probabilities Q are known.

| symbol | definition | role |
|---|---|---|
| θ̂(D) | the LOBO estimate: mean over the G·m rows of v(interv) − v(obs_morph), using the realised Y. This is the P0 confirmatory statistic | what the intervals are centred on |
| θ(D) | **conditional value**: the same LOBO picks, evaluated with the true Q, i.e. mean of Q[pick_interv] − Q[pick_obs_morph] | secondary truth (reported) |
| **θ_G** | **procedure estimand** = E_D[θ(D)]: the expected value of the LOBO procedure at sample size G. H1 targets this ("procedure estimand, LOBO") | **primary truth for admission** |
| θ_new(D) | **deployment value**: the policy trained on all G bases (k by inner LOBO on all G, exact P0 primitives) applied to 3,000 fresh instances (1,000 new bases) from the same population, scored with the true Q | secondary truth (reported) |

- **Estimating θ_G:** from T = 2,000 independent *truth* datasets per cell, disjoint from the coverage datasets, using exact Q (no
  Bernoulli noise). The MC SE is reported; I expect it to be about 0.001.
- **Sensitivity:** coverage is recomputed with θ_G ± 2 MC-SE, to show that truth uncertainty does not drive any verdict.
- **Why θ̂ is unbiased for θ_G:** E[θ̂ − θ(D) | X, Q] = 0 by the tower argument of §2A item 4. It is **not** true that
  E[θ̂ | picks] = θ(D), because other bases' picks depend on Y_b. This is checked empirically as "bias of θ̂".
- **Challenge 1 (estimand):** CV-type intervals target θ_G, not θ_new (Bates, Hastie and Tibshirani).
  - H1 wording must therefore stay "procedure value at G".
  - SV1 reports coverage of θ(D) and θ_new as well, so that any gap between "the procedure works on average" and "the
    deployed policy works" is visible rather than assumed away.

## 2A. Estimand audit (review item 2)

**1. What each interval actually estimates** (corrected in review).

There are two exact decompositions:
- Var(θ̂) = Var(θ(D)) + Var(θ̂ − θ(D)) + 2·Cov(θ(D), θ̂ − θ(D));
- Var(θ̂) = Var(E[θ̂ | X, Q]) + E[Var(θ̂ | X, Q)].

The two kinds of randomness are **entangled**. The picks depend on the training Y, and each base's outcome noise enters both
its own term and the other bases' picks. So the covariance is not zero in general, and no term is "pure learning" or "pure
outcome" variance. (Draft 2's Var_D(θ(D)) + E_D[Var(θ̂ | D)] was wrong: conditioning on D, which includes Y, makes θ̂
deterministic.)
- CR1 treats the per-base totals of d as independent and fixed-policy. It ignores refit variance **and** the cross-base
  dependence that runs through training.
- The refit bootstrap and half-sampling try to capture both. Whether any of them does is exactly what SV1 measures.
- Coverage of **θ_G** therefore tests the right thing for H1, which says "procedure estimand".
- θ(D) is *not* the H1 target. Covering θ(D) is a conditional property: a CR1 interval can cover θ(D) and still miss θ_G, or
  the reverse.
- θ_new is a different estimand: the deployed G-trained policy evaluated on new bases. It is relevant to any claim about
  "new robots" and is **outside H1**.

**2. Primary coverage indicator.** For dataset s and method j:
1{L_js ≤ θ̂_G^truth ≤ U_js}, with closed intervals and a 1e-12 tolerance.
- θ_G^truth is computed **once per cell, before any coverage dataset is scored**, from T = 2,000 truth datasets on a separate
  seed stream.
- Secondary indicators use θ(D_s) and θ_new(D_s) per dataset. These need no Monte Carlo truth: they are exact given Q, apart
  from the 3,000 new instances used for θ_new, whose MC SE is about 0.008 and is reported per dataset.

**3. Truth precision rule (fixed in advance).**
- MC SE(θ_G) = sd(θ(D))/√T. With sd ≈ 0.03–0.05 [ASSUMP], this is ≈ 0.0007–0.0011.
- The effect on coverage is ≲ 2·φ(1.645)·SE/sd(θ̂) ≈ 0.005, which is small next to the coverage MC SE of 0.021.
- **Rule:** coverage is also computed at θ_G ± 2 MC-SE. Any admission outcome that flips inside that band is labelled
  **truth-sensitive**, and it is not admitted as validated.
- T is fixed and is not adapted after seeing data.

**4. Unbiasedness of θ̂ for θ_G: the precise argument** (corrected in review).

**Setting:**
- D = (X, Q, Y), and row i belongs to base b(i).
- The outcome noise is ε_{i,a} = Y_{i,a} − Q_{i,a}.
- For policy p, the LOBO pick π_i^p is a measurable function of (X, Y_{−b(i)}). The fold that predicts base b uses only the
  other bases' rows (standardisation, inner CV, kNN), plus b's own features.
- **The generator.** In calc §E `_synth`, Y = 1{U < Q} with independent uniforms, so given (X, Q) every Y_{i,a} is independent
  Bernoulli(Q_{i,a}). In particular, Y_{b} ⟂ Y_{−b} | (X, Q), and E[Y_{i,a} | X, Q] = Q_{i,a}: no outcome dependence on
  latent variables beyond Q.

**The argument:**
1. θ̂ − θ(D) = (1/n) Σ_i (ε_{i,π_i^int} − ε_{i,π_i^obs}).
2. For each term, E[ε_{i,π_i^p} | X, Q, Y_{−b(i)}] = Σ_a 1{π_i^p = a} · E[ε_{i,a} | X, Q, Y_{−b(i)}] = 0.
3. By the tower property, **E[θ̂ − θ(D) | X, Q] = 0**, hence E[θ̂] = E[θ(D)] = θ_G.
4. This is exact in finite samples, for any G. It needs only LOBO exclusion of b's outcomes and conditional independence of
   outcomes across bases given (X, Q).

**What does *not* hold:**
- E[θ̂ | all picks] = θ(D) fails. Base b is training data for every other fold, so the full collection of picks depends on
  Y_b, and conditioning on it makes ε_b not mean-zero.
- Hence θ̂ − θ(D) *need not be* independent of θ(D). The terms of different bases are dependent, and coverage of θ(D) is only a
  conditional, secondary property.
- The argument also fails if the real generator had cross-base outcome dependence given (X, Q). That is an [ASSUMP] of the
  synthetic model, not something SV1 tests.

**Check:**
- The empirical bias, mean(θ̂ − θ(D)) over the admission-sample (`cov`) and truth datasets of a cell (the evaluation
  datasets are not pooled), must be within 3 MC-SE of 0.
- A larger value means an implementation anomaly (INVALID-HARNESS). That is valid because the expectation is exactly 0 by
  the argument above.

**5. Fixed-tool positive control C0.** The truth is θ_fix = E[Q₀ − Q₁], estimated from the same truth datasets. No learning is
involved, so CR1 should be near nominal (calc §D: 0.88–0.94).

**6. Pilot blinding.**
- The pilot aggregator **does not compute** coverage or width for M1–M6.
- It reports only engineering quantities: timings, scaling, failures, degenerate rates and fast-path bit-identity.
- It also reports C0 as a harness check, and bias(θ̂ − θ(D)).
- So no pilot number can steer methods, cells or rules. Pilot and confirmatory seeds are disjoint.

## 3. Methods evaluated (pre-registered before the pilot)

| id | interval (90 %) | status |
|---|---|---|
| **M1** | CR1 t(G−1): θ̂ ± t·SE. The SE uses the calc §E formula, `sv0_lib.cr1_se` | frozen primary candidate |
| **M2** | refit **percentile** bootstrap: B base resamples via the SV0-validated `sv0_lib.replicate`, which refits everything (standardisation, inner-CV k, kNN, argmax); then [q05, q95] via `percentile_ci` | frozen candidate |
| **M3** | refit **basic** bootstrap: [2θ̂ − q95, 2θ̂ − q05], from the same replicates at zero extra cost | **new candidate** (escalation D-6) |
| **M4** | half-sampling: 40 distinct balanced splits (`sv0_lib.half_splits`). θ̂_A and θ̂_B are each LOBO within a half of G/2 bases. V̂ = (1/(4·40)) Σ(θ̂_A − θ̂_B)², and the interval is θ̂ ± t(G/2 − 1)·√V̂. The scale is conservative, because the halves have more learning variance | frozen candidate; this definition is fixed here |
| **M5** | the **protocol composite** (§5): M1, replaced by M2 when width(M2) > 1.25·width(M1) | evaluated because this is the rule actually used confirmatorily |
| M6 | "widest admissible", chosen per dataset after admission | reported |
| C0 | **harness positive control**: M1 on a fixed (non-learned) contrast v(tool 0) − v(tool 1), whose truth comes from the truth MC | gate: coverage must lie in [0.85, 0.95] |
| C1 | naive iid SE (ignores clustering) | diagnostic baseline |
| C2 | non-refit cluster bootstrap of the fixed d (as in P0's `cluster_bootstrap`) | diagnostic: isolates the refit variance |

- **Excluded:** the nested-CV interval (amendment §4.1, "optional"). It would mean nested CV inside LOBO inside inner CV, so it
  costs too much, and its theory for argmax value with data-driven k is not established. This is recorded as a limitation.
- **Bootstrap structure:**
  - **Draws:** i.i.d. base draws, laid out canonically, with copies sharing one LOBO label.
  - **Complete refit:** all of this was validated in SV0-3.
  - **Degenerate replicates (U10):** a replicate with G\* ≤ 2 is recorded and redrawn from the same stream. Its probability is
    about 3e-8 at G = 12 and negligible at G = 28. A cell with > 1 % degenerate replicates is flagged.
  - **Bias:** the bootstrap bias mean(θ̂\*) − θ̂ is reported. Each replicate has only about 0.63·G distinct bases.
- **Challenge 2 (bootstrap):** the percentile bootstrap may be biased toward the value at smaller G. M3 (basic) mirrors that bias.
  Reporting both separates "wrong centre" from "wrong spread".

## 4. Cells, sample sizes and Monte Carlo precision

**These are the recommended values.** The frozen-only values are S = 40, B = 40 and 2 scenarios (§11). Every owner-open value
is a `PENDING` config field. The B cells are reduced to S = 100 and T = 1,000, because they are diagnostic (§9).

| cell | G | scenario (calc §E) | role | S (coverage datasets) | T (truth) |
|---|---|---|---|---|---|
| A-null | 28 | null | **admission** | 200 | 2,000 |
| A-info | 28 | interventions add information | **admission** | 200 | 2,000 |
| A-obs | 28 | observation sufficient (θ likely < 0: the harm side) | **admission** (D-3) | 200 | 2,000 |
| B-null | 12 | null | diagnostic (inference boundary) | 200 | 2,000 |
| B-info | 12 | interventions add information | diagnostic | 200 | 2,000 |

- **Fixed design:** m = 3 per base (D5) and B = 200 refits (D-1), matching revision 2 §4.4's confirmatory B and closing B10.
- **G = 46 is excluded** (amendment §4.2).
- **MC precision at S = 200:** the coverage SE is about 0.021 at 0.90.
- **Operating characteristics of the frozen admission rule** (point estimate ≥ 0.85, Wilson two-sided z = 1.645 lower bound
  ≥ 0.75; normal approximation now, and SV1-0 recomputes them exactly with the A0 exact-binomial code):
  - at k/S = 0.85 the Wilson bound is 0.80, so the point estimate is the binding condition;
  - P(admit | true 0.90, 3 cells) ≈ **0.98**;
  - P(admit | 0.85) ≈ **0.16**;
  - P(admit | 0.80) ≈ 1e-4.

  At S = 40 these were 0.63, 0.19 and 0.03. B10's sidedness ambiguity becomes immaterial at S = 200, and z = 1.645 is fixed.

## 5. Metrics (per cell × method; every rate carries a Wilson interval, every mean an MC SE)

- **Coverage of θ_G (primary):** also reported against θ(D) and θ_new, and the per-dataset deployment value.
- **One-sided miss rates, lower and upper separately:** "supported benefit" depends on the lower bound, so asymmetry matters.
- **Width:** mean and median, and width relative to the true sd(θ̂).
- **θ̂ quality:** bias (mean θ̂ − θ_G), sd(θ̂), RMSE.
- **SE calibration:** mean SE² / Var(θ̂). This links back to calc §E's inflation of 2.25.
- **Degenerate and failure rates:** CR1 with SE = 0 (common at small G), zero-width bootstrap intervals, degenerate
  replicates, crashes and timeouts.
- **Decision rates under the §4 partition with m = 0.10:** P(supported benefit), P(no meaningful gain), P(supported harm),
  P(inconclusive). In the null cell, P(supported benefit) is the false-claim rate.
- **Discreteness:** θ̂ lies on the 1/84 lattice. Intervals are closed, with a 1e-12 tolerance, as in calc §D.

## 6. Pre-registered acceptance criteria and their interpretation

1. **Harness validity (gate, not admission):**
   - C0 coverage in every cell lies in [0.85, 0.95];
   - SV1-0 passes (§8).

   If either fails, SV1 is **INVALID-HARNESS**: stop, preserve the evidence, investigate. No method verdict is drawn.
2. **Admission of a method** (frozen protocol rule, decisions applied):
   - coverage of θ_G ≥ 0.85 in **every** admission cell (A-null, A-info, A-obs);
   - Wilson lower bound (two-sided 90 %) ≥ 0.75;
   - **plus (D-4, recommended):** lower-tail miss ≤ 0.10 in every admission cell.
3. **Confirmatory interval:** the widest admissible method, per protocol. M5's own coverage must also meet rule 2, or the
   composite rule is declared invalid and M1 alone is never used.
4. **If no method is admissible:** apply E1 verbatim. Every P0.5 confirmatory contrast is "inference not validated", and the
   SV1 report states which failure mode applied:
   - bias of θ̂,
   - SE too small,
   - wrong bootstrap centre, or
   - discreteness.
5. **What SV1 validates:** an admission certifies coverage **only for this synthetic generator family and this fingerprint**.
   It is necessary, not sufficient, for real-data validity.
6. **G = 12 cells** inform the "no inference at G < 12" rule and may only *add* caution. They never relax anything.

**Anti-tuning safeguards:**
- methods, B, S, T, cells, truths, metrics and rules are frozen in the SV1 protocol **before the pilot**;
- the pilot and the confirmatory run use disjoint seed streams;
- pilot coverage numbers are reported but cannot change methods, rules or cells; the pilot may change only engineering
  parameters (shards, timeouts);
- the confirmatory run happens once, and its results are final;
- any code fix after the confirmatory run starts invalidates it. A new run then needs new seeds and a new approval, and the
  failed run is kept.

## 6A. Admission, selection and independent evaluation (review item 4)

The frozen rule ("admit if coverage ≥ 0.85 …, use the widest admissible") estimates coverage on the same datasets that decide
admission. A method admitted because its estimate cleared 0.85 has an upward-biased estimate (the winner's curse). Three
stages, on disjoint seed streams:

| stage | data | output | allowed use |
|---|---|---|---|
| **1. Admission** | S_adm datasets per admission cell (frozen protocol rule) | the admitted set 𝒜 | the decision only. Its coverage numbers are labelled "admission estimates (selection-biased upward for admitted methods)" |
| **2. Selection** | none (pre-declared rule) | the confirmatory procedure = M6 "widest admissible within 𝒜", or M5 if it is in 𝒜, per frozen §5 | — |
| **3. Independent evaluation** | **S_eval fresh datasets per admission cell** (proposed deviation D-8) | coverage, one-sided miss, width and decision rates of the *selected* procedure and of each admitted method | the only coverage figures quoted as estimates of validity |

- **If evaluation contradicts admission** (the evaluation Wilson upper bound for the selected procedure < 0.85): report
  **"admission not confirmed"**. That is final; there is no re-selection.
- **Frozen fallback:** without D-8, the protocol's rule is executed exactly, and the report flags every admitted coverage as
  selection-biased.

## 6B. "Not validated" versus "evidence of invalidity" (review item 5)

Per method and per cell, with the Wilson two-sided 90 % interval [ℓ, u] on coverage, at a nominal level of 0.90:

| verdict | condition |
|---|---|
| **validated** (admission cell) | the frozen admission rule holds; with D-4, the lower-tail rule also holds |
| **not validated** | the admission rule fails **and** u ≥ 0.90: undercoverage is not demonstrated; the method may be adequate but the evidence is insufficient |
| **evidence of undercoverage** | u < 0.90 |
| **evidence of material undercoverage** | u < 0.85 |
| **conservative** | ℓ > 0.90 (also reported, since an over-wide interval costs power) |

- **For the procedure:** failing admission yields E1 "inference not validated". The SV1 report must say whether this reflects
  demonstrated undercoverage or only insufficient evidence, and must never call the method "invalid" in the second case.
- The same two-level language applies to one-sided miss rates. "Evidence of excess lower-tail miss" requires the Wilson lower
  bound > 0.05.

## 7. Seeds and reproducibility

- **Seeds:** `numpy.random.SeedSequence([SV1_ROOT = 2026102390, phase, cell, purpose, s])`, with phase pilot or confirm and
  purpose data, truth, boot, half or new.
  - This is disjoint from SV0 (2026102370 plus offsets up to 31) and from calc §E.
  - Results do not depend on the shard index.
- **Records:** one per dataset (θ̂, θ(D), θ_new, all intervals, diagnostics, sha256 of X/Y/base), written as `.ndjson`, because
  the guard refuses `*.jsonl` by design.
- **Determinism checks:**
  - aggregation is byte-identical when run twice;
  - a **replay** recomputes 2 % of datasets, chosen at random but pre-declared by seed, in a fresh process; the records must
    be byte-identical;
  - shard invariance is checked in SV1-0.
- **Environment:** the identical SV0 fingerprint is required (SV0 §4 item 4), via the same SV0-0-style preflight. Any mismatch
  means rerun SV0 first.

## 8. Implementation (new files only; P0 and the SV0 files are untouched and pinned by hash)

All new files go in `experiments/causal_engineer/dev/experience_p05/sv1/`.

| file | content |
|---|---|
| `sv1_lib.py` | dataset generation (reusing `p05_design_calc._synth`, `SCENARIOS`, `t_ppf`); the truths (θ(D), θ_new via P0 `Space.dist`, `choose_k` and `knn_rates` on all G bases); M1–M5 and C0–C2; aggregation and admission. It **reuses** `sv0_lib.replicate`, `cr1_se`, `percentile_ci`, `half_splits` and `wilson_lower` |
| `sv1_fast.py` | optional cached predict: `Space.dist` is computed once per inner fold instead of once per k, and every other step uses the exact P0 functions in P0's order. **Used only if SV1-0 shows bit-identity** with `p0.predict` on ≥ 20 datasets, including replicates and relabellings. Otherwise the P0 path is used |
| `sv1_run.py` | shard worker. It copies the SV0 audit-hook guard pattern, with writes allowed only under `sv1/out/<phase>/` and no in-process multiprocessing. Parallelism comes from separate processes. Records are resumable: completed datasets are skipped |
| `sv1_aggregate.py` | completeness check, metrics, admission, `sv1_results.json`, a one-page report, `SHA256SUMS` |
| `sv1_selftest.py` | **SV1-0, implementation gates (no statistics):** (a) the fast path is bit-identical to P0; (b) toy coverage: a normal mean with known σ covers exactly 0.90 in closed form; (c) the truths: interv vs interv gives θ(D) = θ_new = 0 exactly, and the fixed-tool truth matches a direct computation; (d) shard invariance on 4 datasets with B = 5; (e) the exact-binomial admission operating characteristics |

- **Launcher:** 8 shard processes, each in its own `systemd-run` scope (MemoryMax 1 GiB, CPUQuota 100 %, `env -i`, 1 BLAS
  thread), all inside tmux. Then aggregate, replay and cmp.
- **Sessions:** each session is ≤ 3 h with a verified 3.25 h deadline, and work resumes across sessions. This means no
  unattended overnight VM. The laptop must be on AC and awake for each session.

## 9. Compute, RAM, parallelism and cost (review item 3; rewritten)

**Measured basis** (SV0 on the VM, one core under `CPUQuota=100%`):
- one two-policy P0 fit takes about **1.7 s at G = 28** and about **0.3 s at G = 12**. The SV0-3 and SV0-4 per-check times
  reconcile with these to within 1 %;
- G = 14 is estimated at about 0.40 s, scaling with the 6·G·(G − 1) inner-fold distance calls. This is **[ASSUMP]**.

**Per-dataset cost, one core:**
- **G = 28:** 1 + 200 refits = 342 s, plus 80 half-fits = 32 s, plus deployment ≈ 2 s, about **378 s**.
- **G = 12:** about **66 s**.

**CPU-hours, P0 path, with the recommended decisions (S_adm 200, S_eval 100, B 200):**

| component | count | CPU-h |
|---|---|---|
| A cells, admission | 3 × 200 × 378 s | 63.0 |
| A cells, independent evaluation (D-8) | 3 × 100 × 378 s | 31.5 |
| B cells (diagnostic) | 2 × 100 × 66 s (S = 100; diagnostic only) | 3.7 |
| truth | A: 3 × 2,000 × ≈ 3.7 s; B: 2 × 1,000 × ≈ 0.8 s | 6.6 |
| replay (2 %) and overhead (≈ 5 %) | — | ≈ 7 |
| **total** | | **≈ 112 CPU-h** |

Under the frozen-only option (S = 40, B = 40, no evaluation set) the total is about 6 CPU-h.

**Parallel strategy on the main VM:**
- **Hardware:** 8 vCPU = **4 physical cores × 2 SMT threads**, AMD EPYC-Genoa (c1 `lscpu`).
- **Workers:** independent single-threaded processes (no multiprocessing inside the SV0-style guard). Each runs in its own
  `systemd-run --scope` with `CPUQuota=100%`, `MemoryMax=1G` and BLAS threads = 1.
- **Sharding:** by dataset index, which is shard-invariant by construction.
- **Concurrency:** 8 scopes × 100 % = 800 % ≤ the 8 vCPU.
- **Parent quota (not yet verified):** whether a parent cgroup quota limits this was not checked in c1. N3 stage 0 reads
  `/sys/fs/cgroup/cpu.max` and `/sys/fs/cgroup/system.slice/cpu.max`, and requires `max`.
- **Effective parallelism p is unknown.** For these small-array numpy workloads, SMT typically adds 0–40 % per core, so
  p ∈ [4, ~5.6]. **No projection assumes more until it is measured.**

**Benchmark before any projection:**
- **N1 (local):** measures the fast-path speed-up ratio f on the laptop. The ratio is transferable, but not the absolute times.
- **N3 stage 0 (VM, about 10 min):** runs the same fixed workload with 1, 2, 4, 6 and 8 concurrent workers. It measures
  throughput, then sets the shard count to the best measured throughput.
- The confirmatory cost is projected only from these measurements.

**Memory:**
- SV0 measured VmHWM at 80 MB.
- An SV1 worker holds one dataset, its 200 θ̂\* scalars and its records, so ≤ 150 MB is expected, capped at 1 GiB per scope.
- 8 workers need ≲ 1.2 GB of 32 GB. Memory is not a constraint.

**Runtime and cost** (wall = CPU-h / p; $0.269/h; plus ≈ 15 min overhead per session):

| scenario | CPU-h | p = 4 (no SMT gain) | p = 5.6 | cost range |
|---|---|---|---|---|
| pilot (S = 6 per A cell, 4 per B cell, T = 200, B = 200) | ≈ 2.5 | ≈ 40 min | ≈ 30 min | **≈ $0.20–0.30** (cap $0.75) |
| confirmatory, P0 path | ≈ 112 | 28 h | 20 h | **$5.4–7.6: exceeds the $6.09 headroom** |
| confirmatory, fast path f = 2 | ≈ 56 | 14 h | 10 h | $2.7–3.8 |
| confirmatory, fast path f = 3 | ≈ 37 | 9.3 h | 6.7 h | $1.8–2.5 |
| confirmatory, no D-8 evaluation set (P0 path) | ≈ 80 | 20 h | 14 h | $3.8–5.4 |

**Implications:**
- The recommended design fits the cap only with a fast path of f ≳ 2, or with a cap raise.
- Sessions are ≤ 3 h, with a verified 3.25 h deadline, AC power and an attended laptop. Work resumes across sessions. That
  means 3–10 sessions.
- The batch VM has the same cost per CPU-hour, so it saves wall time, not money. It is not proposed.
- **Ledger:** $89.911 against the $96 cap. The stopped disks accrue ≈ $0.24/day. The SV0 allowance does not carry over.

## 10. Execution sequence (each step needs its own go)

- **N1 (local, $0; authorised by the owner, 2026-10-23):**
  - archive this file's Appendix verbatim as `sv0/PROPOSAL_SV0_rev4b.md`;
  - write `sv0/MANIFEST.md` (code hashes, fingerprint, results, attempt-1 FAIL);
  - write the complete **`docs/plans/EXPERIENCE_P05_SV1_PROPOSAL.md`**;
  - implement `sv1/` with the 5 files plus `sv1_config.json`. Every owner decision is a config field set to `"PENDING"`, and
    `sv1_run.py` refuses to run a confirmatory phase while any field is pending;
  - run the **local** self-tests and a tiny smoke run (S = 2, B = 5), plus the fast-path benchmark (f);
  - no VM.
- **N2:** independent code review, then freeze the protocol and code hashes.
- **N3 (pilot, VM, ≤ $0.75):** SV1-0 self-tests, then the pilot.
  - Outputs: timings, the fast-path speed-up, degenerate and failure rates, and a confirmatory cost projection.
  - Pre-declared go/no-go: no crashes; SV1-0 PASS; C0 within [0.80, 1.00] (loose at S = 10); projected confirmatory cost
    within the authority granted.
- **N4 (confirmatory, VM, cost set from the N3 projection):** run once, aggregate, replay, then report.

## 11. Reconciliation against the frozen protocol (review item 6; rewritten)

Sources:
- protocol §4/§5;
- amendment 2.2 §4.2 (the V1 grid, as renamed by E5);
- erratum E1;
- revision 2 §4.4;
- protocol B10 and SV0 U10.

| item | status | value used | note |
|---|---|---|---|
| CR1 t(G−1) primary; refit-bootstrap sensitivity, with the > 25 % wider rule; no inference at G < 12 | **settled (frozen)** | as frozen | M1, M2 and M5 implement these |
| Admission: coverage ≥ 0.85 in every cell at the planned G, Wilson 90 % lower ≥ 0.75; widest admissible; E1 if none | **settled (frozen)** | as frozen | G = 12 cells are not "at the planned G", so they are diagnostic. That is a reading of the frozen text, not a change |
| Frozen grid: G ∈ {12, 28} × {null, interventions add information}; methods CR1, refit bootstrap, half-sampling; nested CV "optional" | **settled (frozen)** | as frozen | excluding nested CV is allowed by "optional" (an implementation choice) |
| Primary truth θ_G (procedure estimand), D-5 | **settled** (H1: "procedure estimand, LOBO") | θ_G | reporting θ(D) and θ_new is a reporting addition |
| **B (D-1)** | **open by protocol (B10)**. The frozen texts conflict: SV1 B = 40 (amendment §4.2) versus confirmatory B = 200 (revision 2 §4.4) | config `PENDING` | **owner decision.** Recommendation: 200, so that SV1 validates the confirmatory procedure |
| **S (D-2)** | **open by protocol (B10)**. Frozen S = 40, which B10 calls inadequate | config `PENDING` | **owner decision.** Recommendation: S_adm = 200 |
| Wilson sidedness | **open by protocol (B10)** | config `PENDING` | **owner decision.** Recommendation: two-sided z = 1.645 (the revision-2 tables). It is immaterial at S = 200 and decisive at S = 40 |
| Degenerate replicates (U10) | open by protocol; negligible impact (≈ 3e-8 at G = 12) | redraw and count | implementation decision; reported per cell |
| Half-sampling definition | frozen by name only | §3 M4 | **pre-registration specification**: needs auditor sign-off, not a new science decision |
| M5 composite and M6 widest-admissible evaluated | consistent with the frozen rule | reported | reporting addition |
| Truth T, seed streams, pilot blinding, sessions, sharding, fast path (bit-identity gated) | implementation | §2A, §7, §9 | my decisions; reviewable |
| §6B verdict language ("not validated" versus evidence of undercoverage) | reporting definition | §6B | changes no rule |
| **D-3: add the obs-sufficient admission cell** | **new scientific deviation** | config `PENDING` (default: frozen 2 scenarios) | owner decision. It makes admission stricter by adding the harm side |
| **D-4: lower-tail miss ≤ 0.10** | **new scientific deviation** | config `PENDING` (default: not applied) | owner decision. It adds a criterion |
| **D-6: add M3 (basic bootstrap) as a candidate** | **new scientific deviation** | config `PENDING` (default: not a candidate; still reported as a diagnostic) | owner decision. It enlarges the widest-admissible pool |
| **D-8: independent evaluation set, S_eval = 100 per A cell** | **new scientific deviation** (§6A) | config `PENDING` (default: none, with the selection-bias flag) | owner decision. Cost +31.5 CPU-h |
| **D-7: spending** | **owner authority** | none granted | pilot ≤ $0.75 to be requested at N3; confirmatory amount after the N3 benchmark ($1.8–7.6, see §9) |

**Execution consequence:** the code implements both the frozen-only configuration and the recommended one. The confirmatory
phase cannot start until every `PENDING` field is decided.

**Recommended next action:**
1. Execute N1 now (authorised; local; $0).
2. Then the owner decides B, S, the Wilson sidedness and D-3, D-4, D-6 and D-8.
3. Then the auditor reviews the code and the M4 specification.
4. Then N3 (benchmark and pilot) with ≤ $0.75.

## 12. N1 implementation status (2026-10-23, local only; no VM, no paid compute, nothing committed)

**Files** in `experiments/causal_engineer/dev/experience_p05/sv1/`. P0 and the SV0 files are untouched.

| file | sha256 | role |
|---|---|---|
| `sv1_guard.py` | `2594028cbc635a005900cfccc5ce5ee6463af6fb995f7e6b7e4b8fc692628a15` | audit-hook guard (the SV0 pattern) |
| `sv1_fast.py` | `f9f5842cc49c071f3f194b464116e681c29daf1640f5c15262ad56fffce79ca8` | cached-distance fast path (bit-identity gated) |
| `sv1_lib.py` | `88037d5ec0cf0695ca51d011d663c6d72f5ddea8e3ba2818c634957978904c39` | data, truths, intervals, coverage and admission arithmetic |
| `sv1_run.py` | `bd5508696b3925fa3875b8246681bb64a3e3285b99e1ef39b53627fc4ef0f7dc` | shard worker, VM preflight, benchmark mode |
| `sv1_aggregate.py` | `d319442785d45b9ece8df7c7ef52d463be2ab1fd549b4a7cc7447565591365d2` | blinded pilot report; confirm-phase admission, selection, evaluation |
| `sv1_selftest.py` | `a5bb8d29579592ae414d8b76d989125fadc9582ef7ef9e16b691fe5c6825cbfb` | SV1-0 implementation gates |
| `sv1_config.json` | `e61053969fc683a717899a7c6b3d611fe858b3cb2354522b05b1af7d69222620` | every owner decision `PENDING`; `fast_path` `PENDING_SELFTEST` |

**Implementation choices made in N1:**
- **Guard module.** The guard is a separate module, `sv1_guard.py`, and SV1 has 6 code files rather than the planned 5.
- **Broader read rule than SV0.** Reads are allowed anywhere in the repository and the interpreter trees, except the refused
  locations: `artifacts/`, `*.jsonl`, `.env`, `~/dev` and `~/creature-forge`. Provenance is enforced by the hash preflight,
  not the read list.
- **Record format.** Records are `.ndjson`, because the guard refuses `*.jsonl`.

**Local test evidence** (Windows, numpy 2.4.6, `-I -B` under the guard). This is *not* the certified VM fingerprint; SV1-0 is
re-run there in N3.
- **`sv1_selftest.py`: PASS 71/71.**
  - (a) The fast path is bit-identical to `p0.predict`, `p0.choose_k` and `sv0_lib.replicate`: 9 datasets at G = 12 and 28,
    including relabelled and resampled cases.
  - (b) The coverage-indicator arithmetic is correct on a closed-form grid.
  - (c) Identical policies give θ(D) = θ_new = 0 exactly.
  - (d) Records are order- and shard-invariant, and the fast-path records equal the P0-path records.
  - (e) The exact admission operating characteristics reproduce A0's published table: 0.630 / 0.187 / 0.026 and
    0.811 / 0.368 / 0.082.
  - (f)–(i) Wilson identities, the §4 partition, the M4 variance and the §6B verdicts pass.
  - (k) 7 constructed admission and selection cases pass: admit, coverage reject, lower-tail reject, D-4 off,
    truth-sensitive reject, widest selection.
  - (j) Every guard probe is refused, and the module provenance is clean.
- **Exact operating characteristics at S = 200, 3 cells, z = 1.645:** P(admit) = **0.972** at true coverage 0.90, **0.165**
  at 0.85 and **0.0001** at 0.80.
- **Fast-path speed-up at G = 28** (local CPU time): **f = 3.58–3.67×**. This is [ASSUMP] transferable to the VM; it is
  re-measured in N3.
- **Smoke run** (S = 2, B = 3, R = 2, 50 → 30 new bases, 2 shards):
  - 25 records;
  - a resume adds nothing;
  - 1 shard and 2 shards give byte-identical records;
  - pilot aggregation is deterministic and blinded;
  - the harness gate correctly returns INVALID-HARNESS on S = 2;
  - confirm refuses `--local-test`, and a non-local run refuses without `--pre`.

**Revised cost** (§9 table, using the local f = 3.6, still [ASSUMP] until N3):
- the recommended confirmatory design needs ≈ 112 / 3.6 ≈ **31 CPU-h**;
- that is ≈ 5.6–7.8 h of wall time at p = 5.6–4;
- **≈ $1.5–2.1 compute**, plus about 4 session overheads ≈ $0.3, for **≈ $1.8–2.4** in total;
- the P0-path fallback stays at $5.4–7.6.

## 13. Owner decision record: FROZEN 2026-10-23, before any pilot execution

| item | decision | type (§11) |
|---|---|---|
| B (bootstrap refits) | **200** | B10, open by protocol: resolved |
| S_adm (datasets per admission cell) | **200** | B10: resolved |
| Wilson bound | **two-sided, z = 1.645** | B10: resolved |
| D-3 | **include A-obs** as an admission cell, so the admission cells are A-null, A-info and A-obs | new deviation: adopted |
| D-4 | **lower-tail miss ≤ 0.10** in every admission cell | new deviation: adopted |
| D-6 | **M3 (basic bootstrap) is a candidate** | new deviation: adopted |
| D-8 | **independent evaluation set, S_eval = 100** per admission cell | new deviation: adopted |
| spending | N3 only, **≤ $0.75**; confirmatory authorised separately | owner authority |

- These values are written into `sv1/sv1_config.json`, together with its `decision_record`.
- After this point, none of B, S, T, the cells, the thresholds, the truths, the methods or the rules may change on the
  basis of pilot or confirmatory data.
- The fast path is enabled (`engineering.fast_path = true`), but `sv1_run.py` refuses it in a non-local run unless the same
  session's `sv1_selftest` PASSes, with every (a) bit-identity item passing, in the certified fingerprint.

**Review corrections recorded before the code review (2026-10-23):**
- §2A item 1 (the variance decomposition) and item 4 (the unbiasedness argument) are restated precisely. Unbiasedness holds
  given (X, Q), by the tower property. It does not hold given all picks.
- The bias check and every criterion are unchanged.

## 14. Independent code review and corrections (2026-10-23, before any VM execution)

**The review.** A fresh-context reviewer read the code, read-only, and ran spot checks.
- **Verdict on the first build: FAIL** (fixable). The statistical core was correct: estimands, intervals, seeds, bootstrap,
  M4, C0–C2, coverage and miss definitions, Wilson, the §4 partition and the fast path.
- **The unbiasedness argument (§2A item 4)** was confirmed mathematically correct.
  - It holds because P0 never uses Y_b in b's fold, and `_synth` gives Y conditionally independent given (X, Q).
  - A leakage probe confirmed this: re-randomising Y_b left b's picks unchanged.
  - The empirical bias was consistent with 0 (z = 0.12–1.37).
  - corr(θ(D), θ̂ − θ(D)) was 0.11–0.18, confirming the two "need not be independent".

**Corrections** (implementation and reporting only; no frozen criterion changed):

| # | finding | correction |
|---|---|---|
| R1 | no completeness or per-record parameter check; a shard failure was silent | `sv1_lib.work_units` is shared by the runner and the aggregator. The aggregator requires the record keys to equal the expected set exactly and every record to carry the frozen phase, G, B, R_half, m and fast flag. Per-unit exceptions go to `errors_*.ndjson`. Any gap means INCOMPLETE |
| R2 | the §6 item 3 / §6A M5 clause was not implemented | M5's admission is computed as `composite_rule_valid`, and M5 is evaluated on the evaluation set. **Operational reading (aligned with frozen E1):** the confirmatory interval is M6, the widest admissible interval among the candidates. If M5 fails admission, the composite rule is reported as invalid and is not used. Draft 2's phrase "M1 alone is never used" is withdrawn, because it conflicted with E1's "widest admissible". *Flagged for the owner and auditor* |
| R3 | the aggregator had no provenance; SV1-0 was not gated | Outside `--local-test` the aggregator requires `--pre`. It checks the code and config sha256 against `expected.json` and requires this `--out`'s self-test PASS with the approved hashes and fingerprint. Hashes are embedded in `sv1_results.json`, and a one-page `sv1_report.md` is written |
| R4 | a local smoke run could overwrite the real confirm result | `--local-test` writes `*_SMOKE.json` / `*_SMOKE.md` only |
| R5 | the C0 gate covered admission cells only, while §6 item 1 says every cell | implemented **as written: every cell** (see the escalation below) |
| R6 | the D-4 lower-tail rule was not checked for truth-sensitivity | the lower-tail miss is computed at θ_G ± 2 MC-SE, and any flip of the coverage or lower-tail outcome is truth-sensitive |
| R7 | the fast-path gate did not bind to this session's hashes and fingerprint; (a) used 9 datasets | the self-test writes its code sha256 values and fingerprint, and the runner and aggregator require them to equal `expected.json`. (a) now uses **20 datasets** |
| R8 | the preflight dropped the 40-hex HEAD and `rev-parse` checks; `p05_design_calc.py` was unpinned | the detached 40-hex HEAD and the launcher `rev-parse` (`pre/head.txt`) are restored, and `design_archive/p05_design_calc.py` (sha256 `18a6a163…`, matches `SHA256SUMS`) is added to the hashed code set |
| R9 | `--out` was not pinned | outside `--local-test`, `--out` must be `sv1/out` of this checkout |
| R10 | §5 and §6B reporting items were missing | added: a `conservative` flag (Wilson lower > 0.90); `evidence_excess_lower_tail` (lower-miss Wilson lower > 0.05); a flag for more than 1 % degenerate replicates; zero-width counts; bootstrap bias; §6B verdicts on the evaluation set |
| R11 | a partial or unterminated line crashed resume and aggregation | it is skipped in resume, and counted in aggregation, which makes the run NOT complete |
| — | §7 replay was not implemented | `sv1_run.py --replay K` recomputes K units chosen by a fixed seed in a fresh process. The aggregator requires byte equality |
| — | §8 said "otherwise the P0 path is used" | the code **refuses** instead, which fails closed. The text is aligned |
| — | §12 hash table was stale | superseded by the table below |

**Pilot go/no-go correction** (engineering rule, corrected before execution). §10's "C0 within [0.80, 1.00]" at pilot sizes
S = 6 / 4 would pass all 5 cells with probability only 0.299 even when the true C0 coverage is 0.90 (exact binomial). It would
be a false stop. **The pilot is therefore gated only on engineering items:** provenance, the SV1-0 PASS, completeness, errors,
conflicts, the replay, and the bias check. C0 is reported, not gated.

**ESCALATION (scientific; owner decision before the confirmatory run, not needed for N3).** The §6 item 1 harness gate, as
written ("C0 coverage in [0.85, 0.95] in every cell"), has these exact false INVALID-HARNESS rates with a *correct* harness
(admission cells S = 200, diagnostic cells S = 100):

| true C0 coverage | 0.88 | 0.90 | 0.92 | 0.94 |
|---|---|---|---|---|
| P(false INVALID-HARNESS) | 0.437 | 0.157 | 0.272 | 0.765 |

calc §D puts fixed-contrast CR1 coverage at 0.88–0.94. So this gate is likely to void a correct confirmatory run. It is
pre-registered, so it is unchanged here. **Recommended replacement, to decide before the confirmatory run:** INVALID-HARNESS
only on *evidence* of a harness error, for example a pooled C0 Wilson interval entirely outside [0.85, 0.95].

**Hashes after the corrections** (supersede §12):

| file | sha256 |
|---|---|
| `sv1_guard.py` | `572c14f0d6d8b6f2cc918a4c3d3b6d1698559bda24a9618bbe53ade1b25c3c18` |
| `sv1_fast.py` | `f9f5842cc49c071f3f194b464116e681c29daf1640f5c15262ad56fffce79ca8` (unchanged) |
| `sv1_lib.py` | `3037eabbcd967386e49e98495c98209fd07ad1ab059257e70c822db09b3980d3` |
| `sv1_run.py` | `d1d80faa7a39490dc3300736c3ffc5ed1d30d80218d4e7a5d2878caf6211157e` |
| `sv1_aggregate.py` | `d5e09f710d6e94dfa0c4abe6162e9f09c06a394f81ab66e3c88eff9b31870a71` |
| `sv1_selftest.py` | `25d6c75aa6af325b48b75aed1ef76e8df9b2f56a85235069e45934a35314f1b7` |
| `sv1_config.json` (frozen decisions) | `06a717fbfcfd8b7edde84ef873fcaa243ceb57fb809323bdab85049eae54d4ec` |

**Local re-test** (Windows, numpy 2.4.6):
- **self-test: PASS 112/112.** (a) is bit-identical on 20 datasets, with f = 3.70×. The new (l) unit checks: confirm has
  9,100 units and the pilot 1,026. There is a new (k) case for truth-sensitivity of the lower tail.
- **smoke run with `--replay 4`:** PILOT OK, the replay matches, and completeness is OK.
- **negative tests:** a removed record gives `n_missing` 1 and NOT OK; a wrong B gives `n_wrong` 1 and NOT OK; a truncated line
  gives `partial_lines` 1.

### 14a. Verification pass (same reviewer), then the minor fixes: review closed

**Verification verdict: PASS WITH MINOR ISSUES.** R1–R11 were confirmed, no new defect was found, and nothing blocks N3.
The four minor items were fixed before N3:

| # | finding | fix |
|---|---|---|
| m1 | a killed worker's fragment or a logged error voided the run permanently, and resume appended onto the fragment | resume first terminates an unterminated records file with "\n", so the fragment is kept as evidence. **Recovery policy (engineering):** fragments and logged errors stay reported, but do not void the run when every expected unit is present exactly once with the frozen parameters and the replay passes |
| m2 | the replay was optional | for a non-local confirm, `replay.ndjson` is mandatory with n ≥ ⌈0.02 · n_expected⌉, which is 182 of 9,100 |
| m3 | the `--out` pin was incomplete | `--local-test` refuses the real `sv1/out` (the check runs before any directory is created). The aggregator also requires every `preflight_*.json` of the phase to be non-local with no failures |
| m4 | n_new_bases was unchecked | records carry `n_new`, and `record_problems` checks it against the frozen 1,000 |

**Local re-test:**
- self-test: 112/112;
- smoke run plus replay: OK;
- recovery (a truncated last record, then resume): OK, with `partial_lines` 1 and `n_missing` 0;
- negative tests: a missing unit and a wrong `n_new` both give NOT OK;
- the `--local-test` refusal on `sv1/out`: confirmed, with no directory created.

**N3 code set (frozen for N3):**

| file | sha256 |
|---|---|
| `sv1/sv1_guard.py` | `572c14f0d6d8b6f2cc918a4c3d3b6d1698559bda24a9618bbe53ade1b25c3c18` |
| `sv1/sv1_fast.py` | `f9f5842cc49c071f3f194b464116e681c29daf1640f5c15262ad56fffce79ca8` |
| `sv1/sv1_lib.py` | `11bd1ac777a620d2945a8680378641c14a19b04b1001c1a714148684d38671a7` |
| `sv1/sv1_run.py` | `f2dd7fbb9035a2c0ba58dc4c27864c2b505f3aee5b99fd145353fcdcc9ec3276` |
| `sv1/sv1_aggregate.py` | `6bddc0c0b799d477af3b98d9f4b1b0df938da9b4fc4a84c868e08785f124192d` |
| `sv1/sv1_selftest.py` | `25d6c75aa6af325b48b75aed1ef76e8df9b2f56a85235069e45934a35314f1b7` |
| `sv1/sv1_config.json` | `06a717fbfcfd8b7edde84ef873fcaa243ceb57fb809323bdab85049eae54d4ec` |
| `sv0/sv0_lib.py` | `7ca9658df2fe3c22495b45a63f6f73c2e85316dbc7d06104632bbf354de8cde2` |
| `sv0/sv0_run.py` | `03e7a2f02ff8b03ddfbd383c60007ab22bdcc15721aedd1c6406588d198ee6a0` |
| `design_archive/p05_design_calc.py` | `18a6a163aa8233e6b2171094358e179d740124f5e6f0c028f0e4f74620d42ed4` |

## 15. N3 results (2026-10-23 21:55–22:03 UTC, Nebius main VM; spend $0.048)

**Preflight:**
- on AC power; the watchdog was OK; authentication was OK;
- both VMs STOPPED before the session;
- ledger baseline $89.938;
- deadline 1.25 h, verified locally and on the VM.

**Session:**
- **Setup:** a fresh bundle clone at `afe33ca` (`--no-checkout`, `autocrlf=false`). Every transferred hash was verified, the
  pip freeze matched `def4117c…`, and the status showed exactly the 9 allowed files.
- **CPU quota:** `system.slice` and `user.slice` have `cpu.max = max`, so no parent quota applies.
- **Every gate passed:**
  - the preflighted P0-path benchmark, covering hashes, fingerprint, the 40-hex HEAD and `rev-parse`, the P0 pins, the pip
    freeze and the status allow-list;
  - **SV1-0 on the VM: PASS 112/112** in the certified fingerprint (numpy 2.5.4). Fast-path bit-identity holds on 20 datasets,
    with a speed-up of **3.48×** at G = 28;
  - the blinded pilot: 8 shards, all rc 0, in 5.5 min;
  - a 10-unit cross-process replay: 0 mismatches;
  - aggregation: **PILOT OK (engineering)**, with completeness 1,026/1,026, no missing, extra, wrong-parameter or errored units,
    no partial lines, and 9/9 preflights non-local and clean;
  - empty stderr.
- **Blinding:** no M1–M6 coverage or width was computed.

**Pilot harness checks:**

| cell | bias(θ̂ − θ(D)) | C0 | degenerate replicates | CR1 SE = 0 |
|---|---|---|---|---|
| A-info | +0.0009 ± 0.0030 | 6/6 | 0 | 0 |
| A-null | −0.0030 ± 0.0025 | 6/6 | 0 | 0 |
| A-obs | −0.0005 ± 0.0024 | 4/6 | 0 | 0 |
| B-info | −0.0010 ± 0.0032 | 4/4 | 0 | 0 |
| B-null | −0.0011 ± 0.0028 | 4/4 | 0 | 0 |

- All bias values are within 3 MC-SE.
- C0 is reported, not gated, at pilot sizes.

**Pilot truths** (T = 200, pilot seeds; generator properties, not method performance):

| cell | θ_G | sd(θ(D)) |
|---|---|---|
| A-info | +0.105 | 0.043 |
| A-null | +0.001 | 0.010 |
| A-obs | +0.007 | 0.024 |
| B-info | +0.033 | 0.048 |
| B-null | −0.001 | 0.012 |

The confirmatory run recomputes its truths on its own seeds, with T = 2,000 / 1,000.

**Measured throughput** (fast path, 30 G = 28 fits per process):

| processes | throughput (fits/s) |
|---|---|
| 1 | 2.28 |
| 2 | 4.53 |
| 4 | 8.92 |
| 6 | 8.86 |
| 8 | 8.93 |

- **Effective parallelism is 3.91:** the 4 physical cores give it, and SMT adds nothing.
- The P0 path takes 1.547 s per two-policy G = 28 fit.
- Per-process CPU time doubles at 8 processes, from SMT sharing, so the pilot's unit CPU times are converted to single-core
  work: A coverage unit 43.3 s; A truth 0.46 s; B coverage 6.3 s; B truth 0.08 s.
- That work model predicts a pilot wall time of 291 s against 327 s observed (×1.13 for imbalance and overhead).
- Bootstrap replicates hold only about 0.63·G distinct bases, so each refit is about 2.5× cheaper than a full fit. That is
  why the units are far cheaper than §9's estimate.

**Revised confirmatory budget** (9,100 units plus a 2 % replay; measured, not assumed):
- 12.2 core-hours;
- **3.1–3.5 h** of compute wall time at p = 3.91;
- **2 sessions** of ≤ 3 h, at about 4.0 VM-hours;
- **≈ $1.0–1.1**.
- **Recommended authorisation: ≤ $1.50**, a 35–50 % margin. Headroom under the $96 cap is $6.01.
- **Fallback:** if the fast path were unusable in the confirmatory fingerprint, the cost would be ×3.5 ≈ $3.6.

## 16. Pre-confirmatory resolutions (2026-10-24; local only, no VM, no confirmatory data)

### 16.1 Cost reconciliation (corrects the wording of the N3 summary)

"12.2" is **single-core CPU-hours, not VM wall time.** The chain, from the N3 measurements:

| quantity | value | basis |
|---|---|---|
| billing rate | **$0.2689 / VM-hour** ($0.264 compute + $0.0049 disk) | `forge_cloud.py` quoted rates |
| work units | 9,100, plus a **182-unit** replay (2 %, rounded up) | `work_units`, aggregator m2 |
| single-core work per unit | A coverage or evaluation 43.3 s; A truth 0.46 s; B coverage 6.27 s; B truth 0.076 s | N3 unit CPU / 2.03 SMT inflation (bench: 26.64 vs 13.13 s per process at 8 vs 1 processes) |
| **total CPU-hours** | **12.2** (11.99 work + 0.24 replay) | |
| parallel throughput | **3.91 cores' worth** (fits/s at 4 or 8 processes / 1 process) | N3 benchmark |
| compute wall time | 12.2 / 3.91 x imbalance: **3.3 h expected** (x 1.05), **3.5 h conservative** (x 1.13, as in the pilot) | |
| overhead per session | 2.7 min measured in N3 (629 s billed for 7.8 min of work); budgeted 0.10 h expected, 0.25 h conservative | ledger |
| attended sessions | **2** (each <= 3 h; laptop on AC) | |
| **VM wall time** | **3.6 h expected** (3.28 compute + 2 × 0.10 sessions + 0.12 for the VM self-test, aggregation and retrieval); **4.2 h conservative** (3.53 + 2 × 0.25 + 0.17) | |
| **cost** | **$0.96 expected, $1.13 conservative** (ledger including idle-disk accrual: $1.04 / $1.21) | |

**Deadline-bounded worst case:**
- session 1 has a deadline of 2.75 h and session 2 a deadline of 1.50 h, each with up to 0.25 h of watchdog lag;
- that gives 4.75 h, or $1.28, plus about $0.08 of idle disks, for **<= $1.36**;
- so the deadlines alone keep spend below **$1.50 even if every operator stop failed**.

**Contingency session.** In the conservative case, 4.2 VM-hours nearly fill the two deadlines (4.25 h). If work remains, a
third short session (deadline ≤ 0.75 h) resumes it. The $1.35 ledger stop rule still bounds the total. If the cap is reached
before completion, the run is INCOMPLETE, not a result.

**The $1.50 hard cap is sufficient,** with >= $0.29 of margin over the conservative estimate. Stop rule: stop at a ledger delta
of $1.35. If the fast path were refused, the cost would be x3.5, so the run would stop at the cap without completing; that would
be reported as INCOMPLETE, not as a result.

### 16.2 Amendment A-SV1-1: the C0 harness gate (pre-registered before any confirmatory coverage was observed)

- **Observations before the amendment:** no confirmatory run exists. The pilot's C0 counts at S = 6 / 4 were seen (6/6, 6/6,
  4/6, 4/4, 4/4) and were reported, not gated. The amendment is derived from binomial theory only and does not depend on them.
- **Replaced:** section 6 item 1, "C0 coverage in [0.85, 0.95] in every cell", a point-estimate band. With a correct harness
  its exact false-rejection rate is: 0.947 at c = 0.85, 0.437 at 0.88, 0.157 at 0.90, 0.272 at 0.92, 0.765 at 0.94 and 0.948
  at 0.95.
- **New rule:** INVALID-HARNESS if, **in any of the 5 cells or in all cells pooled**, with k of n covered:
  - **P_0.85(X <= k) < 0.01**, i.e. the one-sided Clopper-Pearson upper bound is below 0.85; or
  - **P_0.95(X >= k) < 0.01**, i.e. the one-sided CP lower bound is above 0.95.
- **Thresholds:**

  | n | reject if k <= | or k >= |
  |---|---|---|
  | 200 | 157 | 197 |
  | 100 | 75 | 100 |
  | pooled 800 | 655 | 775 |
- **Family-wise false rejection with a correct harness.** The per-test probabilities are exact binomial; the cells are
  independent.

  | true C0 coverage | 0.85 | 0.88 | 0.90 | 0.92 | 0.94 | 0.95 |
  |---|---|---|---|---|---|---|
  | union bound | 0.047 | 0.0008 | 0.0001 | 0.0007 | 0.0098 | 0.045 |
  | exact joint (the reviewer's DP recomputation) | 0.043 | 0.0008 | 0.0001 | 0.0007 | 0.0097 | 0.042 |

  It is <= 0.05 everywhere in the band, and <= 0.01 across calc section D's 0.88-0.94.
- **Diagnostics preserved:**
  - The per-cell test keeps scenario-specific failures visible. One cell at 157/200 rejects even when the pooled test passes
    (self-test (m)).
  - The pooled test catches a moderate defect common to every cell. All cells at 0.80 pass individually, but pooled rejects.
  - The power of any-of-5 is 0.77 at c = 0.80 and 1.00 at 0.75 with the per-cell tests alone. The pooled test alone has power
    0.92 at 0.80 and 0.48 at 0.82.
  - Per-cell Wilson intervals and the old band check are still reported (`point_in_band`).
- **Other harness gates (unchanged, for context):** the bias check (|mean(theta_hat - theta_cond)| <= 3 MC-SE per cell) adds
  about 1.3 % family-wise false rejection across 5 cells.
- **Status: requires owner approval before the confirmatory run.** It is recorded in `sv1_config.json` as
  `amendments.A-SV1-1.owner_approval`, currently PENDING. The confirm phase must not start until this is recorded.
- **Not changed:** every method-admission criterion (coverage >= 0.85, Wilson lower >= 0.75, lower tail <= 0.10, truth
  sensitivity), B, S, T, the cells, the methods and the decisions.

### 16.3 The M5 / E1 interpretation (no scientific deviation needed)

**Frozen clauses, verbatim:**
- **Protocol section 5, Rules:** "**Primary interval:** CR1 with t(G−1) on base-level paired differences." "**Refit
  bootstrap:** mandatory sensitivity. If it is > 25 % wider, the wider interval is used."
- **Protocol section 5, Validation:** "A method is **admissible** only if its estimated coverage is ≥ 0.85 in every P05-SV1
  cell at the planned G, with the Wilson 90 % lower bound ≥ 0.75. The confirmatory interval is the widest admissible one."
- **Amendment 2.2 section 4.2:** "The confirmatory interval is the **widest admissible** one."
- **Revision 2.1 section 4.3:** "**Refit bootstrap:** mandatory, as in revision 2 §4.4. If the refit interval is > 25 % wider,
  the wider interval is used for classification."
- **Erratum 2.2a E1** (the latest frozen correction; it states it applies to amendment 2.2 and, through it, to revision 2.1):
  "**If some methods are admissible,** 2.2 §4.2's rule applies, and only among admissible methods: the confirmatory interval
  is the widest one. Revision 2.1 §4.3's refit rule is likewise applied only among admissible methods."

**Precedence.** E1 governs. It is the newest frozen text, it explicitly scopes both earlier rules, and protocol section 5
consolidates it. Two operative requirements follow:
1. the confirmatory interval is the **widest admissible** interval;
2. the CR1 -> refit switch applies **only among admissible methods**.

**They never conflict in a way that matters:**
- When CR1 and the refit bootstrap are both admissible, the refit rule selects one of them, and the widest-admissible interval
  is at least as wide. So applying rule 1 always satisfies rule 2's protective intent: it is never narrower.
- "Never narrower" is a statement about **width only**. M6 need not contain M5's interval, because M3 or M4 may be centred
  elsewhere. E1 asks only for "the widest one", so this is compliant.
- When either is inadmissible, rule 2 does not apply (E1).
- "Primary interval: CR1" therefore governs only if CR1 is admissible; it is always reported.

**Implementation check** (`sv1_aggregate.py`):
- The candidates are the frozen M1, M2 and M4, plus M3 under D-6.
- Admission uses the frozen rule.
- The selected procedure is **M6**: per dataset, the widest interval among the admitted candidates (`widest`).
- M5 (the CR1/refit composite) is **not** a candidate. Its coverage is reported as `composite_rule_valid` for information only,
  and is evaluated on the evaluation set.
- If nothing is admitted, the result is E1 "inference not validated". **This matches the frozen requirements.**
- The only correction is to my own draft text: section 6 item 3's phrase "or the composite rule is declared invalid and M1
  alone is never used" (SV1 draft 2, not a frozen protocol text) is withdrawn because it is inconsistent with E1. This is a
  clarification, not a scientific deviation.

### 16.4 Final configuration and implementation status

- **Decisions:** identical to the frozen set (section 13):
  - B 200;
  - S_adm 200;
  - two-sided z 1.645;
  - admission cells A-null, A-info, A-obs;
  - lower tail <= 0.10;
  - M3 is a candidate;
  - S_eval 100.
- **Unchanged fixed values:** admission >= 0.85 and Wilson lower >= 0.75; frozen candidates M1, M2, M4; R_half 40; n_new 1,000;
  T 2,000 / 1,000; S_diagnostic 100.
- **Added:** `fixed.c0_gate` = {band [0.85, 0.95], alpha 0.01 per side, each cell plus pooled} and `amendments.A-SV1-1`.
- **Changes since N3:**
  - `sv1_lib.py`: lines appended only (the exact binomial gate), none removed;
  - `sv1_aggregate.py`: the gate lines, plus the pilot C0 diagnostic;
  - `sv1_selftest.py`: new tests (m);
  - `sv1_config.json`: the new keys;
  - `sv1_run.py`, `sv1_fast.py` and `sv1_guard.py`: unchanged.
- **Local tests:** self-test **118/118** (6 new C0-gate items); the smoke pilot is OK; the confirm-mode smoke exercises the gate
  path.
- **Confirmatory code set:**

| file | sha256 |
|---|---|
| `sv1/sv1_guard.py` | `572c14f0d6d8b6f2cc918a4c3d3b6d1698559bda24a9618bbe53ade1b25c3c18` (= N3) |
| `sv1/sv1_fast.py` | `f9f5842cc49c071f3f194b464116e681c29daf1640f5c15262ad56fffce79ca8` (= N3) |
| `sv1/sv1_run.py` | `f2dd7fbb9035a2c0ba58dc4c27864c2b505f3aee5b99fd145353fcdcc9ec3276` (= N3) |
| `sv1/sv1_lib.py` | `8f16e4c76fd9121e9a0365f9163592de3a06fc7918f9836e98b0ca87ef34340d` |
| `sv1/sv1_aggregate.py` | `f8f744f592229c99baabcf3e20c24cf6354c607240aa4c8d4d116dd669cbb078` |
| `sv1/sv1_selftest.py` | `04fef70d7d32fe1c7df26751d4d82b60768e30625dce43cdb07a2e995ce923a1` |
| `sv1/sv1_config.json` | `67752c9a2d43ff7726b374a9e6f78fd7fbb1564f3f4d0236d78d8d2919de7c1e` |
| `sv0/sv0_lib.py`, `sv0/sv0_run.py`, `design_archive/p05_design_calc.py` | `7ca9658d…`, `03e7a2f0…`, `18a6a163…` (unchanged) |

## 17. Confirmatory freeze (2026-10-24, before any confirmatory execution)

**Owner approvals (recorded in `sv1_config.json`: `amendments.A-SV1-1.owner_approval`, `confirmatory_authorization`):**
1. Amendment A-SV1-1, the C0 harness gate.
2. The M5/E1 interpretation: E1 governs, the confirmatory interval is the widest admissible candidate (M6), and M5 is
   reported separately.
3. The full SV1 confirmatory experiment, with ≤ $1.50 of additional Nebius spend within the $96 project cap. The stop rule
   triggers at a ledger delta of $1.35. If the cap cannot accommodate completion, the run stops and is classified INCOMPLETE;
   there is no budget extension and no fallback to the P0 path.

**Frozen code and config (sha256):**

| file | sha256 |
|---|---|
| sv1_guard | `572c14f0d6d8b6f2cc918a4c3d3b6d1698559bda24a9618bbe53ade1b25c3c18` |
| sv1_fast | `f9f5842cc49c071f3f194b464116e681c29daf1640f5c15262ad56fffce79ca8` |
| sv1_lib | `8f16e4c76fd9121e9a0365f9163592de3a06fc7918f9836e98b0ca87ef34340d` |
| sv1_run | `f2dd7fbb9035a2c0ba58dc4c27864c2b505f3aee5b99fd145353fcdcc9ec3276` |
| sv1_aggregate | `f8f744f592229c99baabcf3e20c24cf6354c607240aa4c8d4d116dd669cbb078` |
| sv1_selftest | `04fef70d7d32fe1c7df26751d4d82b60768e30625dce43cdb07a2e995ce923a1` |
| **sv1_config** | **`dd1b052679e1099ee546280150217b8ce53d462c97cac70b92f21d3f80448c44`** |
| sv0_lib | `7ca9658d…` |
| sv0_run | `03e7a2f0…` |
| p05_design_calc | `18a6a163…` |

**Frozen protocol text:** this file up to and including §16, sha256 `0a56dc5b0a80252fd504d21ae0c1ce774a71d1e8068edb40abc70e75c1376362`,
before this §17 was appended.

**Environment:** the SV0-certified fingerprint:
- HEAD `afe33ca68b73da313d720db0939ef382bc1cae91`;
- venv `/home/forge/venvs/creature-forge`;
- Python 3.12.3, numpy 2.5.4;
- manifest `af2cf766…`;
- pip freeze `def4117c…`.

**Execution plan** (engineering; set before any confirmatory output is seen):
- **Shards:** 4. The measured parallelism is 3.91, and SMT adds nothing, so there is no oversubscription.
- **Session 1:** deadline 2.9 h; the workers stop themselves at 2.4 h.
- **Session 2:** deadline ≤ 1.5 h. It resumes through the validated recovery mechanism, then runs the replay (182 units) and
  the aggregation.
- **No interim statistics:** between sessions only record counts are examined. The aggregator, which computes statistics,
  runs once, after all 9,100 units and the replay are complete.

## 18. Confirmatory results (run 2026-10-23 23:08 – 2026-10-24 02:52 UTC; first read after completion)

**Integrity:**
- **Classification: ADMITTED, and confirmed on the independent evaluation set.**
- 9,100 / 9,100 units: 0 missing, 0 wrong-parameter, 0 errored, 0 partial;
- replay 182 / 182 with 0 mismatches;
- 5 / 5 preflights clean;
- SV1-0 118 / 118 on the VM;
- provenance clean; stderr empty;
- the C0 gate (A-SV1-1) passed: per cell 177/200, 187/200, 188/200, 85/100 and 95/100; pooled 732/800;
- the bias of θ̂ − θ(D) is within 3 MC-SE in every cell.

**Evidence:**

| file | sha256 |
|---|---|
| `confirm_evidence/sv1_n4_s1.tgz` | `0ebf2daa…` |
| `confirm_evidence/sv1_n4_s2.tgz` | `0f9aee31…` |
| `sv1_results.json` | `bab836ec…` |

**Truths** (T = 2,000 for the A cells, 1,000 for the B cells):

| cell | θ_G | θ_new,G |
|---|---|---|
| A-null | −0.0001 | |
| A-info | +0.1079 (MC SE 0.0011) | +0.110 |
| A-obs | +0.0045 | |
| B-null | +0.0003 | |
| B-info | +0.0353 | +0.042 |

**Admission** (S = 200 per admission cell; θ_G coverage, with the lower-tail miss in brackets):

| method | A-null | A-info | A-obs | admitted |
|---|---|---|---|---|
| M1 CR1 t | 0.860 (0.080) | **0.750** (0.090) | 0.875 (0.050) | no: evidence of material undercoverage in A-info |
| **M2 refit percentile bootstrap** | **1.000** (0.000) | **0.995** (0.000) | **1.000** (0.000) | **yes** |
| M3 refit basic bootstrap | 0.800 (0.125) | 0.670 (0.180) | 0.805 (0.105) | no: material undercoverage in all cells |
| M4 half-sampling | 0.835 (0.095) | 0.785 (0.085) | 0.910 (0.045) | no |
| M5 composite (reported only) | 0.985 | 0.940 | 0.975 | `composite_rule_valid` = true |

- **Confirmatory interval (E1):** M6 = the widest admissible = **M2**.
- **Independent evaluation** (S_eval = 100 per cell): M6 = M2 covered **0.97 / 1.00 / 1.00** (A-info / A-null / A-obs), with
  Wilson lower bounds of 0.93 / 0.97 / 0.97 and a **lower-tail miss of 0 in every cell**. Admission is confirmed.
- **The evaluation "verdict" field** reads "not validated" for every method. That is because the §6B mapping is called there
  with admitted = False. Here it means only "no evidence of undercoverage", since every Wilson upper bound is ≥ 0.90. It is a
  label artefact, not a failure, and it was not changed after the results were seen.

**Widths and decisions:**
- **Widths:** the mean M2 width is 0.175 / 0.237 / 0.191, about 1.5× CR1. Width / sd(θ̂) is 3.4–5.0, against 3.29 for an exact
  90 % interval. M2 is conservative: its coverage is ≈ 0.97–1.00 against a nominal 0.90.
- **Decision rates on the evaluation set:**

  | cell | supported benefit | inconclusive | no meaningful gain | supported harm |
  |---|---|---|---|---|
  | A-info (θ_G = 0.108, just above m = 0.10) | 0.05 | 0.93 | 0.02 | — |
  | A-null | 0.00 | 0.22 | 0.78 | — |
  | A-obs | 0.00 | 0.48 | 0.52 | 0.00 |

**Mechanism diagnostics (admission sample):**
- **CR1 SE calibration:** mean SE² / Var(θ̂) = 0.48 in A-info. This is the refit variance the naive SE omits (cf. calc §E,
  2.25×). It is 0.97–1.07 in A-null and A-obs.
- **Bootstrap bias:** mean(θ̂\*) − θ̂ = −0.023 in A-info. Replicates contain about 0.63·G distinct bases, so they learn less.
  The basic bootstrap therefore shifts in the wrong direction, while the percentile bootstrap covers through extra width.
- **G = 12 diagnostic cells:** CR1 covers 0.67 / 0.69. The refit bootstrap covers 0.99 / 1.00.

**Operations:**
- 2 sessions: about 2.4 h of workers in session 1, then 65 min of workers plus 11 min of replay and aggregation in session 2;
  3.7 h of VM time for the experiment.
- **Spend:** the ledger delta is $2.969 against the $1.50 authorisation, because of the post-completion stop failure (see
  `docs/memory/INCIDENTS.md`, 2026-10-24). Project headroom is $3.03.
