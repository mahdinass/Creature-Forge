# Creature Forge V2: P0.5 revision 2.2, a targeted amendment to revision 2.1

**Status**
- **Base documents:** this amends `P0_5_DESIGN_REVIEW_rev2_1.md` (sha256 `27cd709f…`). Revision 2.1 holds everywhere this
  file is silent.
- **P0 verdict:** INSUFFICIENT-DATA, unchanged.
- **Branch:** `feature/experience-learning` pinned at `e3caf81`, untouched.
- **Approvals:** none of A0–A11 is approved or implied.
- **Nothing was executed:** no physics, no spend, no sealed or held-out access, no harness, no commit. G = 46 remains NOT
  COMPUTED and was not restarted.

**Supporting files** (scratchpad):
- `p05_amend22.py`: exact arithmetic, no Monte Carlo.
- `test_p05_amend22.py`: 12 deterministic tests, including the invariance lemmas checked directly on P0's
  `experience_p0.Space` and `knn_rates`.
- `p05_amend22_output.md`: the tables cited as "amend §X".

**Labels:**

| label | meaning |
|---|---|
| **[PROOF]** | A mathematical statement with its proof. |
| **[ASSUMP]** | An assumption, or a number derived from one. |
| **[UNVERIFIED]** | A claim not yet checked by any computation or record. |
| **[HIST]** | Record or source evidence. |

---

## 1. H4 permutation degeneracy (objection 1)

### 1.1 Setting

In one LOBO fold the training set has G−1 bases with m_inst instances each. A control permutes one of two things within
groups:
- outcome rows: S-base (group = base), S-family-free (group = (base, severity bin)), S-generator;
- the cf block: S-cf-conditional (group = base).

### 1.2 Lemmas [PROOF] (each is a unit test on the exact P0 code)

**Lemma 1: π0 and the prior are unchanged.**
- *Statement:* any permutation of training outcome rows leaves the fold prior p̄ = (1/n) Σ_i Y_i unchanged, and so leaves π0
  and the kNN shrinkage target unchanged.
- *Proof:* a sum is invariant under reordering. ∎

**Lemma 2: kNN invariance for outcome permutations.**
- *Setup:* P̂(x) = (Σ_{i∈N} Y_i + p̄) / (k+1), where N = N_k(x) depends on features only (`knn_rates`, stable argsort).
- *Statement:* for a within-group outcome permutation σ, P̂_σ(x) = P̂(x) whenever every group g satisfies N ∩ g ∈ {∅, g}, or
  the rows of N ∩ g are permuted among identical rows.
- *Proof:* σ does not change N, because outcomes do not enter distances. If each group lies wholly inside or wholly outside
  N, then σ(N) = N and Σ_{i∈N} Y_{σ(i)} = Σ_{i∈N} Y_i. The identical-rows case is immediate. ∎
- **Consequence:** a within-base outcome shuffle changes a prediction only if the neighbour set **splits** some base.

**Lemma 3: standardisation is unchanged.**
- *Statement:* the training-fold mean and sd per column (`Space.dist`) are invariant under any permutation of training rows.
  For a block-only permutation σ of the cf block, D_σ(x, i) = D_{obs,morph}(x, i) + D_cf(x, σ(i)).
- *Proof:* column moments are symmetric functions of the rows. The block distances add (equal block weights). ∎

**Lemma 4: cf-conditional invariance.**
- *Statement:* S-cf-conditional changes P̂(x) only if it changes the neighbour **set** N. For m_inst = 2 with group {i, j}, the
  swap gives D′(x, i) = A_i + C_j and D′(x, j) = A_j + C_i. If i and j stay inside (or both stay outside) the top k, P̂ is
  unchanged.
- *Proof:* outcomes are fixed, so P̂ depends on N only through Σ_{i∈N} Y_i. ∎

**Lemma 5: singleton strata give an exact identity.**
- *Statement:* if every stratum has size 1, every within-stratum permutation is the identity. The control then equals the
  real run exactly, and V(π_M) − V(π_ctrl) = 0 for every instance.
- *Proof:* the only permutation of a single element is the identity. ∎
- **Consequence for revision 2.1:** §7.1 rule (ii) says a control "reproduces the gain" when memory − control is "no
  meaningful gain". With singleton strata that condition holds **mechanically** whenever memory has a real gain. **Revision
  2.1's rule (ii) is therefore unsafe without a validity criterion.** Fixed in §1.4.

**Lemma 6: counting** (amend §P; verified by enumeration).
- A uniform permutation of m items has one fixed point in expectation, so it moves a fraction (m−1)/m of the items.
- The number of derangements is !m = m! Σ_k (−1)^k / k!. So !2 = 1 and !3 = 2.
- Over G−1 groups the number of distinct joint permutations is (per-group count)^(G−1).

| m_inst | scheme | fraction of rows moved | P(base untouched) | distinct joint permutations (G−1 = 27) |
|---|---|---|---|---|
| 1 | any | 0 | 1 | 1: **no control possible** |
| 2 | uniform | 0.50 | 0.50 | 1.3e8 |
| 2 | derangement | 1.00 | 0 | **1: all 20 "permutations" are the same swap** |
| 3 | uniform | 0.67 | 0.17 | 1.0e21 |
| 3 | derangement | 1.00 | 0 | 1.3e8 |

**Lemma 7: strata** (amend §S).
- With m instances of a base in K severity bins:
  - if bins are drawn independently and uniformly, P(all singletons) = Π_{i<m} (K − i) / K;
  - under a **severity-balanced** draw, which is a valid and even recommended instance rule, all strata are singletons
    whenever m ≤ K.
- **Pigeonhole:** m = 3 with K = 2 guarantees at least one shared stratum in every base.

| m_inst | K | fraction of bases S-family-free can alter: uniform bins | severity-balanced (adversarial, valid) |
|---|---|---|---|
| 2 | 2 | 0.50 | **0** |
| 2 | 3 | 0.33 | **0** |
| 3 | 2 | 1.00 | 1.00 |
| 3 | 3 | 0.78 | **0** |

**Identical outcome rows** [PROOF + ASSUMP]:
- With independent draws, P(Y_1 = Y_2) = Π_a [Q_{1a} Q_{2a} + (1 − Q_{1a})(1 − Q_{2a})].
- At a common Q of 0.05, 0.10 and 0.20 this is 0.37, 0.14 and 0.02.
- So low-success regimes make many within-base swaps no-ops even when the permutation is not the identity.

### 1.3 Degeneracy, control by control [PROOF-based]

| control | m_inst = 2 | m_inst = 3 |
|---|---|---|
| S-global | valid: permutes all training rows ((G−1)·m_inst)! choices; the Lemma-2 caveat does not bind, because whole-set shuffles break every pairing | valid |
| **S-base** | Only one derangement per base, so it is a **single deterministic contrast** with no permutation distribution. It alters a prediction only where the neighbour set splits a base (Lemma 2), and only where the base's two rows differ. | A real permutation distribution; same Lemma-2 caveat. |
| **S-family-free** | **Degenerate** (identity) on ≥ 50 % of bases with uniform bins, and on **all** bases under a severity-balanced draw (Lemma 5, 7). | Valid only if K = 2 bins (pigeonhole) or by chance. Degenerate under a balanced draw with K = 3. |
| **S-cf-conditional** | Single swap per base. Changes predictions only if it changes neighbour sets (Lemma 4). | Permutation distribution available. |
| S-generator | valid if the population has more than one generator; **undefined under P-A/P-B (hdb-v1 only)** | same |

### 1.4 Pre-declared non-degeneracy criterion [ASSUMP for the thresholds]

It is computed from training-fold features and training outcome rows only, **before** any control's decision value is
evaluated:
- **N1, input alteration.** Averaged over permutations and folds, ≥ 50 % of training instances must receive a **different
  and non-identical** row (or cf block). Derangement schemes are required, so no instance keeps its own row.
- **N2, permutation diversity.** At least 20 distinct joint permutations must exist and the 20 drawn must be distinct.
  - If not, the control is a **single deterministic contrast**. That is allowed: inference uses the base-cluster CR1 t
    interval on the paired contrast, and no permutation p-value is reported.
- **N3, stratum coverage** (stratified controls). At least 50 % of training bases must contain a stratum of size ≥ 2.
- **Reported, not a validity criterion: prediction-alteration rate,** the share of (query, permutation) pairs whose P̂
  changes.
  - If the inputs are altered (N1 holds) but predictions are invariant, that is a **substantive finding**: the policy's
    decisions do not depend on the within-group pairing, so its value is not instance-level within that group. It is not a
    defect of the control.

### 1.5 Handling invalid controls, and attribution conclusions

- **A control that fails N1 or N3 is INVALID.**
  - It is reported as "not identifiable in this design".
  - It counts toward neither "validated" nor "artefact".
  - It is **never replaced after data** by a coarser stratification, another grouping, or a weaker control.
- **Pre-data remedies, which must be declared before the pilot:**
  - choose m_inst = 3, and K = 2 severity bins ({1.0} vs {1.3, 1.7} multiples), so S-family-free satisfies N3 by
    pigeonhole;
  - otherwise drop S-family-free before data and declare severity attribution unidentifiable.

**Attribution outcomes,** replacing revision 2.1 §7.1:

| outcome | condition |
|---|---|
| **Validated transfer attribution** | Leakage and permission tests pass; **every required control** (S-global, S-cf-conditional for H1; S-base for any *instance-level* claim) is valid; and memory beats each with "supported benefit". |
| **Direct evidence of artefact / leakage** | A permission or leakage test fails, **or** a **valid** control reproduces the gain: the control's advantage over π0 is a supported benefit **and** memory − control is "no meaningful gain". For S-base this reads "the gain is base-level similarity, not instance-level diagnosis". |
| **Unresolved attribution** | Any required control invalid, or any contrast inconclusive. A non-significant shuffle advantage is always "unresolved". |

**Design consequence** [PROOF + ASSUMP]:
- With m_inst = 2, S-base and S-cf-conditional are valid only as single swaps.
- An instance-level claim then rests on **one deterministic contrast per control**.
- If the owner requires permutation-distribution evidence for instance-level attribution, m_inst = 3 is needed (D5).

---

## 2. Pilot representativeness (objection 2)

### 2.1 Correction to revision 2.1 [HIST]

The generator composition of the options (amend §R) is:

| option | population | generator shares |
|---|---|---|
| P-A | 18 | hdb-v1 100 % |
| P-B | 34 | **hdb-v1 100 %** |
| P-C | 46 | hdb-v1 74 % / walkrec-m1 17 % / hand 9 % |

- Revision 2.1 §6.3 said hdb-v1 is "about 75 % of the population weight" under P-B. **That is wrong.** P-B is entirely
  hdb-v1; the 75 % figure applies only to P-C.
- Consequently, under P-B a T2 pilot has **total-variation distance 1** from the population: it shares no generator with it.
- Also, **LOGO is undefined under P-A and P-B.** Claims there are restricted to the hdb-v1 generator.

### 2.2 Options compared (amend §R)

The precision columns are MDE and M_nmg at q = 0.30, ρ = 0.3, inflation 2.25 [ASSUMP].

| option and pilot | TV (pilot vs population) | confirmatory bases lost | G | MDE, 2 / 3 per base | M_nmg, 2 / 3 per base | hypothesis overlap in the confirmatory set |
|---|---|---|---|---|---|---|
| P-A, pilot 6 T3 | 0.00 | 0 | 18 | undetectable / undetectable | 0.41 / 0.37 | 12 T1-panel bases (H2 lead) |
| P-B, pilot 6 T2 | **1.00** | 0 | 34 | 0.256 / 0.236 | 0.289 / 0.262 | 12 T1-panel bases (H2 lead) |
| **P-B, pilot 6 of the 12 T1-panel bases** | **0.00** | **6** | **28** | 0.276 / 0.256 | 0.320 / 0.290 | 6 remaining T1-panel bases |
| P-C, stratified pilot 4 / 1 / 1 | 0.08 | 6 | 40 | 0.239 / 0.220 | 0.266 / 0.241 | 12 T2 (H1 tested, `cf_only` lead) + 12 T1-panel |

### 2.3 Recommended default (owner choice preserved): P-B with 6 T1-panel bases as the external pilot

**Rationale:**
1. **The pilot is representative:** same generator (TV = 0), so the cost, feasibility and ERROR rates it measures apply to the
   campaign.
2. **The confirmatory population excludes all 12 T2 bases,** on which H1 was already tested (proxy, null) and the `cf_only`
   lead was generated.
3. **The pilot consumes H2-overlap bases preferentially.** The H2-naive set (6 T1 non-panel + 16 T3 = 22) stays intact. H1
   is evaluated on 28 bases, none of them T2.
4. **One generator** keeps the estimand homogeneous. LOBO is the only transport test, which is honest about scope.

**Cost of the choice** [ASSUMP]:
- **6 confirmatory bases lost** (34 → 28, −17.6 %).
- At q = 0.30, the MDE rises by about +0.02 (0.256 → 0.276) and M_nmg by about +0.03.
- No cross-generator transport can be studied.
- **B5 (engine posterior):** T1 bases were Stage-2 experience bases, so B5 comparisons are reported on the 16 T3 bases only.

**Stage 0 compatibility:** Stage 0 instances are drawn from the 6 pilot bases, so they too stay outside the confirmatory
set.

**Alternatives remain the owner's choice (D2):**
- **P-C** gives the best precision and generator diversity, but has the T2 overlap; its claims must be worded "including
  the P0 proxy bases".
- **P-B with a T2 pilot** keeps G = 34, but its pilot is unrepresentative (TV = 1).

---

## 3. Stage 0 scope (objection 3)

### 3.1 Stage 0a: static, no physics (zero rollouts; part of A6 test acceptance)

1. Allow-list projection test; metamorphic permission tests and the detector positive control (revision 2.1 §7.3) on
   synthetic records.
2. A static schema test that the R_B request has no field able to carry diagnostic output. An AST scan for global-RNG use
   inside R_B.
3. A seed-namespace disjointness test; verification that the optimizer-seed rule is replicate-specific.
4. Budget-feasibility table equals `eng_tools.min_repair_budget` (tool-dimension import with physics trapped, as in
   `p05_min_budget_check.py`).
5. A bounds-feasibility screen on nominal designs from development records.
   - [UNVERIFIED] that it needs no model compilation; if it does, it moves to Stage 0b.
6. P0 blob-hash check; determinism of the feature builder (the same records give a bit-identical feature matrix).
7. The H4 non-degeneracy calculator (§1.4) on a synthetic design table.
8. Cost-formula and analysis-script unit tests.

**Stop condition:** any failure blocks A7. There is no partial pass.

### 3.2 Stage 0b: sequential physics validation (local MuJoCo, $0 cloud; requires A7; NOT executed)

| step | content | new repair executions | stop if |
|---|---|---|---|
| 1 | sentinel: reproduce one stored A1e6 episode | 0 (one episode) | not bit-identical |
| 2 | 1 instance × 2 tools (dimension 1 and dimension 5) × 1 seed × arms {D, ∅, D′} | 6 | any trace difference; any ERROR |
| 3 | instrumentation neutrality: step-2 arm ∅ rerun without hooks | 2 | final design or verification differs |
| 4 | the same instance, the remaining 8 tools × 3 arms | 24 | any trace difference; measured RE per execution > 3× the formula |
| 5 | 3 instances × 10 tools × 2 seeds × 3 arms, minus steps 2–4 | 150 | any trace difference |

**Cumulative rollout-equivalents** (amend §Z) [ASSUMP]:

| cost set | after step 4 | after step 5 |
|---|---|---|
| low (B = 160, 4 seeds) | 9.3 k | **38 k** |
| mid (B = 300, 8 seeds) | 14.9 k | **70 k** |
| high (B = 700, 8 seeds) | 28 k | **144 k** |

**Notes:**
- Wall time is unknown, because the local throughput has not been measured [UNVERIFIED].
- The arm-∅ executions of step 5 form a full R = 2 matrix for 3 instances. They double as the Stage-0 cost and feasibility
  measurement.
- **Stopping logic:** the steps are ordered so that the cheapest checks most likely to fail come first. A failure stops the
  sequence, and the fix plus re-review restart it from step 1. **Diagnosis independence (S8) counts as cleared only after
  step 5 passes in full.** No early success is allowed, because it is a structural property that has to be shown across tool
  kinds, seeds and instances.
- **Optional reduction (owner):** run arm D′ with one seed only in step 5. It saves 30 executions and weakens hidden-state
  coverage.

---

## 4. Inference validity (objection 4)

### 4.1 What the existing synthetic calculations establish [ASSUMP; synthetic]

| result | establishes | does not establish |
|---|---|---|
| calc §D (revision 2.1, corrected) | For **fixed** paired differences under one generator (ternary d, constant per-base discordance, clipped-normal base effect, ICC < q, δ = 0, equal clusters of 2): CR1 t(G−1) covers 0.88–0.94 at G = 8–46, and the bootstrap 0.86–0.93. | Heavy-tailed or heterogeneous base effects; unequal cluster sizes; δ ≠ 0; ICC ≥ q; **learned policies**. |
| calc §E | For the exact P0 learner under one synthetic generative model at G = 12 and 24: the naive SE ignores refitting variance (up to 2.25×; coverage 0.69 when information is present). Degenerate SE = 0 cases are common at small G. | Any property at G = 46 (NOT COMPUTED); **coverage of the refit bootstrap**; behaviour at G = 28. |

**Unknown** [UNVERIFIED]:
1. Whether the base-level refit bootstrap is consistent for this non-smooth procedure. It involves argmax decisions, k
   chosen by inner CV, and duplicated bases changing neighbour composition. Bootstrap failure for non-smooth functionals is
   a known risk.
2. Whether the LOBO procedure estimand's variance is estimable with about 28 bases.
3. Whether any of the candidate intervals has adequate coverage here.

**Candidate intervals for the V1 protocol** [UNVERIFIED; to be checked, not assumed]:
- half-sampling (subsampling bases without replacement);
- the nested-cross-validation interval for CV estimates of Bates, Hastie and Tibshirani ("Cross-validation: what does it
  estimate and how well does it do it?"). The reference details are to be verified before use.

### 4.2 Offline-only validation protocol (no physics, no spend; needs its own approval as part of A5; NOT launched)

- **V0, deterministic, seconds.** Unit tests of the refit pipeline:
  - an identity resample reproduces the original fit bit for bit;
  - duplicated bases share one LOBO group;
  - relabelling bases gives the same result;
  - the H4 calculator matches §1.2.
- **V1, calibration at the planned G.**
  - Grid: G ∈ {12, 28}; scenarios {null, interventions add information} from calc §E; S = 40 synthetic datasets per cell.
  - Methods: naive CR1 t; base refit bootstrap (B = 40); half-sampling (40 splits); optionally nested CV.
  - **Compute estimate** [ASSUMP: one G = 28 LOBO run takes about 15 s, from the section-E timings]: about 13 CPU-hours at
    G = 28 and about 1 hour at G = 12.
  - **Resource rule:** at most 4 worker processes with a memory log. The G = 46 cells were lost to memory pressure with 9
    processes. **G = 46 is excluded unless separately approved.**
  - **Monte Carlo precision:** coverage SE ≈ 0.047 at S = 40, so V1 detects only gross failures (coverage below about 0.80).
- **V2, optional.** Heavier-tailed base effects (t₃) and unequal base sizes, S = 40.

**Pre-declared use of the results:**
- A method is **admissible** only if its estimated coverage is ≥ 0.85 in every V1 cell at the planned G, with the Wilson 90 %
  lower bound ≥ 0.75.
- The confirmatory interval is the **widest admissible** one.
- If **no method is admissible,** the confirmatory analysis is limited:
  - "supported benefit" may be declared only if the naive interval inflated by √2.7 excludes 0;
  - every other outcome is "inconclusive (inference not validated)".
- These rules are fixed before V1 runs.

---

## 5. Objection-to-change table

| # | objection | change | where |
|---|---|---|---|
| 1 | H4 controls may not alter their inputs at m_inst = 2 or 3; adversarial singleton strata | Lemmas 1–7 with proofs and tests on the P0 code; exact counts; N1–N3 validity criterion; invalid ⇒ "not identifiable", never substituted after data; revision 2.1 rule (ii) shown unsafe without validity; attribution table revised; m_inst = 3 / K = 2 remedy declared pre-data | §1; amend §P, §S; tests |
| 2 | Pilot representativeness vs generators and overlap | Corrected the P-B composition (100 % hdb-v1); TV distances; bases lost per option; default P-B with a T1-panel pilot (G = 28, 6 lost); alternatives kept | §2; amend §R |
| 3 | Stage 0 scope | Stage 0a static (0 rollouts) separated from Stage 0b's five sequential steps, with stop rules and cumulative RE (38 / 70 / 144 k) | §3; amend §Z |
| 4 | Inference validity with refitting | What §D/§E establish vs what is unknown; V0–V2 offline protocol with compute and memory limits; pre-declared admissibility and fallback | §4 |

## 6. Approval dependencies (A0–A11; none approved)

| item | depends on | added in revision 2.2 |
|---|---|---|
| A0 (documentation commit) | — | includes the revision-2.1 P-B composition correction |
| A1 (estimands) | — | — |
| A2 (population and pilot) | D2 | default P-B / T1-panel pilot proposed |
| A3 (budget and action set) | D3 | — |
| A4 (hypotheses and H4) | A1, **D5 (m_inst, K bins)** | N1–N3 criterion; attribution table §1.5 |
| A5 (statistical plan) | A4, **V0 + V1 results** | V0–V2 protocol needs approval to run (offline compute) |
| A6 (harness implementation) | A1–A5 | **Stage 0a is its acceptance test** |
| A7 (Stage 0b, local physics) | A6 with Stage 0a passed | sequential steps 1–5 |
| A8 (Stage E) | A2, A7 | — |
| A9 (pilot) | A7 (S8 cleared), A8, A2 | — |
| A10 (cap) | measured A9 costs | — |
| A11 (campaign) | A9 EXPAND, A10, A5 admissible interval | — |

## 7. Final self-critique: claims that remain unidentifiable

**Unidentifiable by design** [PROOF or design fact]:
1. **Instance-level vs base-level attribution at m_inst = 2.** S-base is a single deterministic swap, and it can alter
   predictions only where neighbour sets split bases (Lemma 2). If decisions are invariant, only base-level value can be
   claimed.
2. **Severity attribution** whenever severity-balanced draws make strata singletons (m ≤ K), and always at m_inst = 2 under
   balance (Lemma 5, 7).
3. **Cross-generator transport** under P-A or P-B: one generator.

**Unidentifiable with this study** [ASSUMP-conditional]:

4. **Transport** to the sealed test population, under any option.
5. **Absence of headroom** at guaranteed coverage (revision 2.1 §3.3).
6. **Equivalence** at M ≤ 0.15 under realistic learning inflation. Benefits below about 0.2 are not detectable with useful
   power.
7. **Tool effects** at budgets other than B, and the transfer of R_B effects to the engines' twin-assisted repair.

**Not yet identified but identifiable in principle** [UNVERIFIED]:

8. **Validity of the refit-based interval:** pending V1, and even then only under synthetic generators.
9. **Diagnosis independence:** pending Stage 0b step 5.
10. **Bounds-feasibility rates, costs and noise levels:** pending Stage 0b and the pilot.

**Process**

11. The N1–N3 thresholds and the V1 admissibility thresholds are judgement calls fixed before data, not derived.
12. Passing the 12 amendment tests and the 40 revision-2.1 tests shows that the arithmetic and lemmas are implemented
    correctly. **It does not show that the design will identify a decision-relevant repair benefit on unseen bases.**

*End of amendment 2.2. Stopped here.*
