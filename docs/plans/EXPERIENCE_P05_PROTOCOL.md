# P0.5 protocol (consolidated): randomised FULL-verified repair-effect study for experience learning

**Document status**
- **Version:** consolidated 2026-10-23 (A0 documentation-only commit).
- **Approvals:** **no execution gate (A1–A11) is approved.** Settings D1/D2/D3/D5/D7′ are the owner's planning choices,
  not authorisations to run.
- **Branch:** `feature/experience-learning`. Drafted on `e3caf8121da84523c36449e353a84bd05977ea9a`; published in A0 commit `afe33ca68b73da313d720db0939ef382bc1cae91`. This document is the only new
  protocol text; all source documents are preserved verbatim in the archive (§0.2), apart from one sanitised line in one test.
- **P0 result:** **INSUFFICIENT-DATA** (`docs/EXPERIENCE_P0_REPORT.md`). Nothing here is evidence for or against repair
  memory.

**Labels:**

| label | meaning |
|---|---|
| **[RULE]** | A current protocol rule. |
| **[OWNER]** | An owner setting (2026-10-23). |
| **[ASSUMP]** | An assumption, or a number computed from assumptions. |
| **[UNVERIFIED]** | Not yet checked. |
| **[HIST]** | Records or source code. |
| **[BLOCKER]** | Must be resolved before the gate named in §12. |

---

## 0. Sources, precedence and archive

### 0.1 Precedence (later overrides earlier)

| order | document | archive file | sha256 |
|---|---|---|---|
| 1 | revision 1 (superseded) | `P0_5_DESIGN_REVIEW.md` | `aa9bd74bcc16ae326d940335cd832bf6480b78e12a26f4105f01c166d69eb045` |
| 2 | revision 2 (superseded except where revision 2.1 carries it) | `P0_5_DESIGN_REVIEW_rev2.md` | `0c9349b8ffe8845d8c8da2172e637cf4b6c15b64c99edffa4ba574d1ed48010c` |
| 3 | revision 2.1 | `P0_5_DESIGN_REVIEW_rev2_1.md` | `27cd709fe248c7caddc35562a140f8319c7605251b4d059112b25a83f0563c45` |
| 4 | amendment 2.2 | `P0_5_AMENDMENT_rev2_2.md` | `76d136deba1505e7e56a07f3314300ac1f2969eaf2927006f53e026b8e9fdf1f` |
| 5 | erratum 2.2a | `P0_5_ERRATUM_rev2_2a.md` | `5196894366b877fd9796695cc2be9dadb4fbb7d1ff31f4d5ff6300528b31f63b` |
| 6 | owner settings (2026-10-23) and this consolidation | this file | — |

Where this file states a rule, it is the current rule. Where it is silent, the latest archived document applies.

### 0.2 Archive

- **Location:** `experiments/causal_engineer/dev/experience_p05/design_archive/`.
- **Contents:** 33 archived files from the session scratchpad.
  - **32 are byte-identical** to the delivered sources.
  - **1 is sanitised for publication** (B12, resolved): `test_p05_amend22.py` line 11. A local absolute worktree path, which
    contained the user-profile directory, was replaced by a repository-relative default. No other byte changed.
  - `PROVENANCE.tsv` records each file's source sha256 and published sha256. `SHA256SUMS` verifies the published files.
  - **The unredacted copy is not published.**
- **EOL:** Git EOL conversion is disabled for the directory in `.gitattributes`. This affects no tracked file.
- **Status:** these are research materials, not production code. The archived tests are outside `tests/`, so CI does not
  discover them.

### 0.3 A0 calculations (new; read-only arithmetic, nothing executed against physics)

- `experiments/causal_engineer/dev/experience_p05/a0_cost_model/p05_a0_cost_model.py`, plus its output (§9).
- `experiments/causal_engineer/dev/experience_p05/a0_review/p05_sv1_admission_resolution.py`, plus its output: the exact
  binomial operating characteristics of the P05-SV1 admission rule (§5).

### 0.4 Decision status at a glance

| category | items | status |
|---|---|---|
| **Confirmed owner choices** (planning, not execution) | D1 m = 0.10; D2 P-B, 28 confirmatory bases; D3 B = 300, 8 train seeds; D5 3 instances per base, 2 severity bins; D7′ pilot 4 T1-panel + 2 T3 | confirmed 2026-10-23 |
| **Execution gates** | A1–A11 (§12.1) | **all unapproved.** A0 (documentation only) has a conditional GO for preservation and review. |
| **Blockers** | B1–B11 and B13 open; **B12 resolved** (§12.2) | open as listed |
| **Unverified statistical assumptions** | discordance q, base ICC ρ, learning inflation (1 / 2.25 / 2.7), flip rate, p_pass, costs and throughput, bounds-feasibility rate, eligibility of every base (T3 in particular) | [ASSUMP] / [UNVERIFIED] |
| **Missing results** | G = 46 learning inflation: **NOT COMPUTED**. P05-SV0 / P05-SV1: **not run**, and the refit-bootstrap coverage is unknown. Stage 0a/0b, Stage E, pilot: not run. | missing |

---

## 1. Objective and estimands

**Question:** does intervention-informed experience give a **verifiable, decision-relevant repair benefit on unseen robot
bases**? Better prediction of historical policy choices is not the target.

**Four separated stages** [RULE; revision 2.1 §1.1]:
1. **D_obs:** observe on 4 obs seeds; 4 plant rollouts.
2. **D_cat:** the fixed 9-entry `eng_tools.COUNTERFACTUALS` catalogue on the same 4 seeds; 36 plant rollouts.
3. **D_twin** (H2 and exploratory only): the same 40 observations on the nominal twin; 40 twin rollouts.
4. **Repair R_B:** plant-only CMA in the tool's subspace from the nominal design, using **no diagnostic output**, through
   `eng_tools.run_repair` with a plant-aware `cma_fn`.
   - **Verification:** `full_recovery_v1` through `hdb_bench.verify`.

**Estimands** [RULE]:
- **Cell response:** Q_B(x, a) = P(FULL | do(a), R_B), over optimizer seeds.
- **Policy value:** V(π) = E_x[Q_B(x, π(h(x)))], where h(x) is the information π pays for.
- **π0** = P0's `prior`, the training-fold most frequent FULL tool.
- **Primary estimand = P0-exact and unmasked** (revision 2.1 §2):
  - argmax over all 10 tools;
  - a pick outside A(x) scores Y = 0 for every arm, including π0;
  - **P0-masked** (argmax over A(x)) is a declared secondary variant only.
- **Learned policies** are evaluated as a *procedure* estimand by LOBO cross-fitting.
- **Headroom** (Γ, Γ_sel, the variance bound) is reported **descriptively only.** No gate, STOP rule or "no headroom" claim
  depends on it (revision 2.1 §3).

**H1 representation** [RULE]:
- It is exactly P0's `interv` (blocks obs, morph, cf; `experience_p0.ce_dataset`, `Space`, `knn_rates`, `choose_k`,
  `decide`).
- The run verifies the blob hashes at `e3caf81`:

  | file | blob |
  |---|---|
  | `experience_p0.py` | `dcfb1f29…` |
  | `experience_bank.py` | `38aed182…` |
  | `scripts/exp_p0_audit.py` | `dbaa4d34…` |

- The full formula is in revision 2 §6.

---

## 2. Owner settings and their consequences

| setting | value [OWNER] | consequence [RULE / ASSUMP] |
|---|---|---|
| **D1** minimum meaningful effect | **m = 0.10** absolute FULL-recovery probability | It is the margin in the outcome partition (§4). **It is not a detectable effect:** at G = 28 the MDE is about 0.11–0.50 across the assumption grid, and the power to detect 0.10 is about 0.11–0.70 (0.16–0.59 at ρ = 0.3, q ≤ 0.42) (§9.3) [ASSUMP]. "No meaningful gain" at 0.10 is effectively unreachable. |
| **D2** population | **P-B, hdb-v1 only** (T1 + T3 = 34 bases), **28 confirmatory** after the pilot | LOGO is undefined: one generator. Claims are restricted to hdb-v1 development bases. |
| **D7′** pilot | **4 T1-panel + 2 T3 bases**, excluded from all confirmatory fitting and evaluation | Confirmatory: 8 T1-panel + 6 T1-non-panel + 14 T3 = 28. The H2-naive set is 6 T1-non-panel + 14 T3 = **20**. |
| **D3** repair budget | **B = 300**, **8 training seeds** | All 10 tools are budget-feasible at B, B + 36 and B + 40 (minima 104 / 152 / 176 / 200; §9.1). The action set A(x) is fixed at B. Cost-matched cells (B + 36, B + 40) choose from the same A(x). |
| **D5** instances | **3 per base, 2 severity bins** | Instances are **not** independent bases. With 3 instances in 2 bins, every base has a shared stratum (pigeonhole), so S-family-free can meet N3. S-base and S-cf-conditional have 2 derangements per base, giving 2²⁷ joint derangements: a genuine permutation distribution (E2). |

**Severity bins [BLOCKER B2]:**
- Amendment 2.2 §1.5 proposed bins {multiple 1.0} vs {1.3, 1.7} (`hdb_bench.MULTS`).
- D5 says "two severity bins" but does not define them. The owner must confirm this mapping.

---

## 3. Population, eligibility and independence

**Tiers** [HIST; revision 2.1 §6; erratum E4]:
- **T1:** 18 hdb-v1 experience bases. 12 of them are in the identifiability panel, which generated the H2 lead.
- **T3:** 16 hdb-v1 transfer bases. Their historical family coverage is sparse.
- **T2 is excluded** under P-B. It holds the 12 causal-engineer proxy bases, where H1 was tested.

**Eligibility** [RULE]:
- **No base is verified eligible** for the homogeneous protocol.
- The zero-rollout E-check and, where needed, Stage E must establish eligibility.
- **T3 eligibility is UNKNOWN and must never be treated as PASS.**
- **Confirmatory G is the number of confirmatory bases that pass eligibility.** It is reported as achieved, never imputed.
- **No confirmatory inference if G < 12.**
- **[BLOCKER B4]:** there is no replacement policy if eligibility leaves fewer than 28 confirmatory bases, or makes a pilot T3
  base ineligible.

**Independence** [RULE]:
- Bases are the independent units (I9). Pilot bases are disjoint from confirmatory bases.
- Stage 0b and pilot instances are disjoint.
- Historical HDB outcomes are never used as memory, features or labels.

**Overlap rules** [RULE; revision 2.1 §6.2]:
- **H2** is confirmatory only on the 20 H2-naive bases. The other 8 confirmatory bases (T1-panel) give exploratory
  replication.
- **B5** (engine-posterior benchmark) is reported on T3 only, because T1 helped build the Stage-2 posterior.
- `cf_only` stays exploratory everywhere.

**Representativeness** [RULE; E4]:
- The pilot is generator-matched and now samples both tiers.
- That does **not** establish equivalent difficulty, feasibility, ERROR or cost rates between pilot bases and confirmatory
  bases.
- Pilot rates are reported as pilot-tier rates.

---

## 4. Hypotheses and outcome classification

**Outcome partition** [RULE; revision 2 §8.1], applied to every contrast with margin **m = 0.10**:

| outcome | condition on the interval [L, U] |
|---|---|
| supported benefit | L > 0 and U ≥ m |
| no meaningful gain | 0 ≤ U < m |
| supported harm | U < 0 |
| inconclusive | L ≤ 0 and U ≥ m |

- An interval that includes 0 is never called a falsification.
- These outcomes are available **only if an admissible inference method exists** (§5). Otherwise every contrast is
  "inference not validated".

**Hypotheses** [RULE; revision 2 §8.2, carried; H4 per amendment 2.2 §1.5 and E2]:

| | primary estimand | level |
|---|---|---|
| **H1** (primary) | V(interv) − V(obs_morph), LOBO, replicate-1 cells | 90 % CI |
| **H0** | equivalence reading of Δ_comb and Δ_int | — |
| **H2** (secondary) | V(obs + morph + residual cf) − V(interv): the same plant information | 95 %, Bonferroni with H3; on the 20 H2-naive bases |
| **H3** (secondary) | V(interv gated at coverage 0.5, fallback π0) − V(random gate at 0.5) | 95 % |
| **H4** (attribution) | three outcomes (below) | — |

**H4 outcomes:**
- **Validated transfer attribution:** permission and leakage tests pass, every required control is valid (N1–N3), and memory
  beats each with "supported benefit".
- **Direct evidence of artefact or leakage:** positive evidence only. A failed permission or leakage test, or a *valid*
  control that reproduces the gain.
- **Unresolved:** everything else. An invalid control is always "not identifiable", never replaced after data.

**Permutation rules** [RULE; E2]:
- Groups with ≥ 2 records get uniform derangements. Singletons stay unchanged.
- **N1:** the mean fraction of moved, value-changing records is ≥ 0.50. The denominator is all training records.
- **N3:** ≥ 50 % of bases contain a group of size ≥ 2.
- **Regimes:**
  - single deterministic contrast (D = 1);
  - limited exact set (2 ≤ D < 20);
  - genuine distribution (D ≥ 20).
- **Required controls:** S-global and S-cf-conditional for H1. S-base is required for any instance-level claim.

**Permission tests** [RULE; revision 2.1 §7.3]:
- static projection;
- metamorphic negative and sensitivity tests on the **feature matrix**;
- a detector positive control (a planted leak must be detected without any policy prediction having to change);
- a run-time input-hash check.

---

## 5. Statistical inference

**Rules** [RULE]:
- **Primary interval:** CR1 with t(G−1) on base-level paired differences.
- **Refit bootstrap:** mandatory sensitivity. If it is > 25 % wider, the wider interval is used.
- **No inference at G < 12.**

**Validation before any confirmatory use** [RULE; amendment 2.2 §4.2, renamed by E5]:
- **P05-SV0:** deterministic refit-pipeline tests.
- **P05-SV1:** a synthetic coverage calibration.
- A method is **admissible** only if its estimated coverage is ≥ 0.85 in every P05-SV1 cell at the planned G, with the Wilson
  90 % lower bound ≥ 0.75. The confirmatory interval is the widest admissible one.

**Resolution of the admission rule** (A0 review, exact binomial, `a0_review/p05_sv1_admission_resolution_output.md`)
[ASSUMP: independent cells]:
- **At S = 40 datasets per cell with the two-sided Wilson bound** (z = 1.645, as in the revision-2 tables), the Wilson
  condition binds and requires k ≥ 35 of 40 (0.875).
- **P(admit) across 2 cells:**

  | true coverage | P(admit), 2 cells | with 3 cells |
  |---|---|---|
  | 0.90 (a good method) | **0.63** | 0.50 |
  | 0.85 (borderline) | **0.19** | — |
  | 0.80 (inadequate) | **0.03** | — |

- **With a one-sided bound** (z = 1.282): 0.81, 0.37 and 0.08.
- **Ambiguity:** "Wilson 90 % lower bound" is ambiguous as written; it must be fixed before P05-SV1 (B10).
- **Assessment:** at S = 40 the rule rejects a good method about 37 % of the time, and it cannot separate 0.85 from 0.90 at any
  S ≤ 1,000. It does guard against clearly inadequate methods.
- **Minimum S per cell:**
  - for P(admit | 0.90) ≥ 0.90 and P(admit | 0.80) ≤ 0.05: **S ≈ 87 per cell**;
  - for 0.80 / 0.10: **S ≈ 48**.
- **Recommendation (for the owner and auditor; not adopted):**
  - S ≥ 100 per cell, which costs about 2.5× the S = 40 compute;
  - use the same number of bootstrap refits in P05-SV1 as in the confirmatory analysis. Revision 2 §4.4 specifies B = 200
    confirmatory against B = 40 in the P05-SV1 proposal; a mismatch would validate a different procedure.
- **Until resolved, B10 stays open.**

**[RULE; E1]: if no method is admissible**, every confirmatory contrast is **"inference not validated"**. No benefit,
equivalence or harm claim is made, and every apparent benefit is exploratory. The √2.7 fallback is withdrawn; 2.7 remains only
a planning assumption.

**Established only for synthetic models** [ASSUMP]:
- t(G−1) CR1 covers 0.88–0.94 for *fixed* differences.
- The naive SE for *learned* policies undercovers: variance up to 2.25×, coverage 0.66–0.69 at G = 24.
- The auditor reproduced the G = 24 result.
- **G = 46: NOT COMPUTED. Refit-bootstrap coverage: unknown.**

**Early stopping** [RULE]:
- The protocol has **no group-sequential plan.**
- If a safety STOP ends the pilot or the campaign early, the collected data are reported in full (intention to treat), with the
  achieved G.
- **They are not analysed as if the planned fixed sample had been completed,** and no confirmatory classification is made.
  The results are exploratory.

---

## 6. Leakage and schema

The rules of revision 2 §4–5 and §10 and revision 2.1 §7.3 apply unchanged:
- column groups;
- information-set allow-lists (`legal_obs`, `legal_cat`, `legal_twin`);
- opaque ids;
- nominal-design-only morphology;
- no historical labels;
- no warm start (per-cell initial-mean hash);
- fold-internal fitting;
- a hash-pinned analysis script;
- **never call `hdb_bench.load_bases`**, because it reads the sealed-adjacent walker file.

---

## 7. Stage 0 and diagnosis independence

**Stage 0a: static, 0 rollouts** [RULE; amendment 2.2 §3.1]. This is A6's acceptance test:
- permission tests;
- R_B request schema and the global-RNG AST scan;
- seed namespaces;
- budget-feasibility table;
- the bounds-feasibility screen. [UNVERIFIED] whether it needs model compilation. **[BLOCKER B9]**: if it does, it moves to
  Stage 0b.

**Stage 0b: local physics, sequential** [RULE; amendment 2.2 §3.2, E3]:

| step | content |
|---|---|
| 1 | sentinel |
| 2 | 1 instance × 2 tools × 3 arms |
| 3 | instrumentation neutrality |
| 4 | the remaining 8 tools |
| 5 | 3 instances × 10 tools × 2 seeds × 3 arms |

- **Stopping:** any trace difference is STOP S8, and the sequence restarts from step 1 after the fix and a review.
- **Instances, reconciling E3 with D7′:** three instances on three distinct **pilot** bases that pass the E-check, from three
  taxonomy groups (mass or geometry; sensing or control; actuation), disjoint from pilot instances.
  - E3's wording "six T1-panel pilot bases" predates D7′. The pilot is now 4 T1-panel + 2 T3, so the draw is from those 6
    bases.
  - [Interpretation pending auditor confirmation; BLOCKER B13.]
- **Scope:** S8 clearance applies **only to the hdb-v1 generator, the tested families, the ten tools, both seeds and the
  harness commit used.**
- **Cost:** about 70 k RE locally (§9).

---

## 8. Pilot (external) and campaign rules

**Pilot design** [RULE; revision 2 §5; revision 2.1 §5.2]: full feasible matrix, R = 2, phase-2 cost-matched cells, selector
confirmation, 3 sentinels.
- **[BLOCKER B3]:** instances per pilot base. Revision 2.1 said 2; D5 sets 3 for the campaign; the pilot is unspecified.

**Outcome categories** (first triggered wins):

| category | trigger |
|---|---|
| STOP | S1–S8 |
| REDESIGN | R1 feasibility; R2 floor or ceiling; **R3′** (the MDE at the q_UB worst case and at q = 0.42, with inflation 2.7 and ρ = 0.3, exceeds the owner's large-effect threshold δ_large) |
| HOLD | the q bound and the planning value disagree, or the projected cost exceeds the cap (A10) |
| EXPAND | none of the above |

- **[BLOCKER B1]:** δ_large is not declared. D1 = 0.10 is the *margin* m, not δ_large.

**Campaign monitoring** [RULE; E4]:
- tier-wise S3 (ERROR) and S7 (cost per cell) safety monitoring on T1 and T3 separately;
- non-adaptive: it can stop the campaign but never modifies the design;
- an early stop follows §5's early-stopping rule.

---

## 9. Fresh cost and precision model (B = 300, 8 seeds, 3 instances per base) [ASSUMP; not executed]

Source: `a0_cost_model/p05_a0_cost_model_output.md`.

### 9.1 Units

| quantity | value |
|---|---|
| independent confirmatory bases | 28 |
| instances (not independent) | 84 |
| pilot bases | 6 |
| budget-feasible tools at 300 / 336 / 340 | 10 / 10 / 10 |
| cell | 300 + 62.4 verification = 362.4 RE (p_pass = 0.3 [ASSUMP]) |
| prefix | 80 RE |

Bounds feasibility per robot is UNKNOWN.

### 9.2 Rollouts and dollars

Prices and throughput are **unverified**:
- "recorded" is the historical ledger rate ($0.269/h) and the W3 throughput (31.2 k RE/h);
- "pessimistic" is $0.60/h and 15.6 k RE/h.

| stage | RE | recorded rate | pessimistic |
|---|---|---|---|
| Stage 0b (local) | 69.6 k | $0 cloud | $0 cloud |
| Stage E, 16 bases (all T3) / 34 bases (all of P-B) | 16.6 k / 35.4 k | $0.58 / $0.77 | $3.86 / $4.84 |
| Pilot, 6 × 2 instances / 6 × 3 instances | 115.6 k / 168.8 k | $1.60 / $2.15 | $9.00 / $11.76 |
| Campaign, 28 × 3 (1,050 matrix + 168 cost-matched + 42 selector cells) | 479.1 k | $5.36 | $27.88 |

**Programme totals** (Stage E + pilot + campaign; Stage 0b is local; each stage pays its own session overhead) [ASSUMP]:

| price set | low (Stage E 16 + pilot 6 × 2 + campaign) | high (Stage E 34 + pilot 6 × 3 + campaign) |
|---|---|---|
| old recorded rate | **$7.54** | **$8.28** |
| pessimistic | **$40.75** | **$44.48** |

**Funding constraints:**

| item | USD | status |
|---|---|---|
| existing infrastructure spending cap, remaining | **6.595** | [HIST] $96 − $89.405. **Binding until the owner decides A10.** |
| Nebius AI Cloud VM credit | **40.04** | owner-reported 2026-10-23, unverified; **not an authorisation** |
| Nebius Token Factory credit | **47.00** | owner-reported, unverified; a separate pool, not usable for VMs; P0.5 needs none (no LLM component) |

- **At the old rate,** the full sequence exceeds the existing cap. The campaign needs the separate A10 decision.
- **At pessimistic rates,** the full sequence would exceed even the reported VM credit.

### 9.3 Precision at G = 28 (t-based)

| instances per base | q | ρ | inflation | MDE | M_nmg | power at δ = 0.10 |
|---|---|---|---|---|---|---|
| 3 | 0.15 | 0.3 | 1 | 0.129 | 0.137 | 0.59 |
| 3 | 0.15 | 0.3 | 2.25 | undetectable | 0.205 | 0.34 |
| 3 | 0.30 | 0.3 | 2.25 | 0.256 | 0.290 | 0.21 |
| 3 | 0.42 | 0.3 | 2.25 | 0.303 | 0.343 | 0.18 |

- **Full grid** (q ∈ {0.15, 0.30, 0.42, 0.50, 0.60, 1.0}, ρ ∈ {0.1, 0.3}, inflation ∈ {1, 2.25, 2.7}): power at δ = 0.10 is
  0.11–0.70 with 3 instances per base, and 0.10–0.58 with 2.
- **With about 28 independent bases, a 10-point benefit is likely below reliable detection.**
- Moving from 2 to 3 instances per base changes the MDE only modestly, because bases, not instances, are the binding unit.

---

## 10. Superseded rules (not to be used)

| superseded rule | source | replaced by |
|---|---|---|
| Predicting the historical tool as P0 | plan revision 1 | P0 revision 2 audit |
| Revision 1 pilot 12 × 4 and campaign 120 × 4, and all revision-1 dollar figures | revision 1 §6 | §8, §9 |
| Headroom-based STOP (Γ_sel upper bound < 0.05) | revision 1 | headroom descriptive only (revision 2.1 §3) |
| "Blinded internal pilot" | revision 1 | external pilot, base-level exclusion (revision 2 §5) |
| Repair warm-started from the diagnostic posterior | revision 1 | diagnosis-independent R_B (revision 2 §1.1) |
| Impossible \|δ\| > q table cells | revision 1 §6.2 | enforced constraints (revision 2 §4.1) |
| B = 160 with 8 seeds (only 6 tools feasible) | revision 2 low set | §2 D3 rule |
| Bootstrap "undercovers 0.66–0.74" | revision 2 §4.2 | retracted (revision 2.1 §0.2): a scoring artefact |
| Nominal ρ labels in coverage tables | revision 2 | achieved ICC (revision 2.1 §4.1) |
| Random-pair discordance as a bound; R3 merging benefit and equivalence | revision 2 §5.3 | q_UB bound, R3′ (revision 2.1 §4.4, §5) |
| H4 ratio criterion; "non-significant shuffle ⇒ artefact" | revision 2 §8.3 / 2.1 §7.1 | three-outcome attribution (amendment 2.2 §1.5) |
| "P-B is about 75 % hdb-v1" | revision 2.1 §6.3 | 100 % hdb-v1 (amendment 2.2 §2.1) |
| √2.7-inflated naive interval fallback | amendment 2.2 §4.2 | "inference not validated" (E1) |
| Stage 0b instances "one per generator" / "six T1-panel pilot bases" | revision 2.1 / E3 | §7, with D7′ |
| V0 / V1 / V2 names | amendment 2.2 | P05-SV0 / SV1 / SV2 (E5) |

---

## 11. Retained scientific limitations

1. With about 28 independent bases, a 10-percentage-point benefit is likely below reliable detection capability.
2. No validated inference method means no confirmatory benefit claim.
3. Stage 0 diagnosis-independence results apply only to the tested families and harness versions.
4. An early safety STOP cannot be analysed as if the originally planned fixed sample were completed.
5. T3 eligibility UNKNOWN must not be treated as PASS.
6. No evidence yet establishes decision-relevant memory transfer.
7. Further limitations:
   - absence of headroom and equivalence at M ≤ 0.15 are not demonstrable;
   - there is no cross-generator transport and no sealed-population transport;
   - R_B differs from the engines' twin-assisted repair;
   - conclusions hold at one budget level;
   - with 3 instances per base, instance-level attribution still depends on neighbour sets splitting bases (amendment 2.2
     Lemma 2).

---

## 12. Approvals and blockers

### 12.1 Approval dependencies (none approved; supersedes the erratum 2.2a table)

| item | scope | depends on | open blockers |
|---|---|---|---|
| **A0** | commit these documents and the archive (no code that executes experiments) | owner review of this file; conditional GO 2026-10-23 for preservation and review | none (B12 resolved) |
| A1 | estimands (§1) | A0 | — |
| A2 | population P-B, D7′ pilot draw (seeded), E-check | D2 / D7′ [set] | B4 |
| A3 | budget and action-set rule | D3 [set] | — |
| A4 | hypotheses, partition, H4 rules | A1, D5 [set] | B2 |
| A5 | statistical plan + **P05-SV0/SV1 run (offline compute)** | A4 | B10 |
| A6 | harness implementation; Stage 0a acceptance | A1–A5 | B8, B9 |
| A7 | Stage 0b (local physics) | A6, Stage 0a passed, A2 drawn | B13 |
| A8 | Stage E | A2, A7 | B4 |
| A9 | pilot | A7 with S8 cleared (hdb-v1), A8, A2 | B1, B3, B5, B6 |
| A10 | infrastructure cap decision | measured A9 costs | B11 |
| A11 | campaign + confirmatory analysis | A9 EXPAND, A10, A5 admissible interval | B7 |

### 12.2 Blocking questions (owner or auditor; nothing is invented here)

| id | question |
|---|---|
| **B1** | Large-effect threshold δ_large for R3′. |
| **B2** | Severity-bin definition ({1.0} vs {1.3, 1.7} proposed). |
| **B3** | Instances per pilot base: 2 (revision 2.1) or 3 (consistent with D5). |
| **B4** | Policy when eligibility leaves fewer than 28 confirmatory bases, or makes a pilot base ineligible. |
| **B5** | Verification-seed namespace (D6). |
| **B6** | Confirmation stage per cell, and caching of the original validation (D8). |
| **B7** | Who runs the confirmatory analysis (D10). |
| **B8** | Plant-aware `cma_fn` for R_B: implementation and verification. |
| **B9** | Whether the bounds-feasibility screen needs model compilation. |
| **B10** | P05-SV0/SV1 compute caps (`docs/EXPERIENCE_P05_HANDOFF.md` §8); the datasets per cell (S = 40 has inadequate resolution, §5); a single Wilson-bound definition; and matching the refit count B between P05-SV1 and the confirmatory analysis. |
| **B11** | Cap and top-up decision: the full sequence exceeds $6.595 at recorded rates. |
| **B12** | **RESOLVED 2026-10-23.** The local path in `design_archive/test_p05_amend22.py` line 11 was sanitised. The source and published hashes are in `design_archive/PROVENANCE.tsv`, and the unredacted copy is not published. |
| **B13** | Auditor confirmation of the §7 reconciliation of E3 with D7′. |
