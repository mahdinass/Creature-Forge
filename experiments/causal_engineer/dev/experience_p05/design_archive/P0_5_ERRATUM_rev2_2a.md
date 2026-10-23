# Creature Forge V2: P0.5 revision 2.2, erratum 2.2a (protocol corrections only)

**Status**
- **Applies to:** `P0_5_AMENDMENT_rev2_2.md` (sha256 `76d136de…`) and, through it, `P0_5_DESIGN_REVIEW_rev2_1.md` (sha256
  `27cd709f…`). Everything not named here is unchanged.
- **Unchanged context:** the P0 verdict is INSUFFICIENT-DATA; the branch is pinned at `e3caf81`; no A0–A11 approval is
  implied; G = 46 is NOT COMPUTED.
- **Nothing was executed** for this erratum: no calculation, simulation or code change.

**Labels:**

| label | meaning |
|---|---|
| **[RULE]** | A protocol rule, replacing the cited text. |
| **[PROOF]** | A mathematical statement. |
| **[ASSUMP]** | An assumption. |
| **[UNVERIFIED]** | A claim not yet checked. |

---

## E1. No confirmatory claim without a validated inference method (replaces 2.2 §4.2, "Pre-declared use", third bullet)

**Withdrawn:** "supported benefit may be declared only if the naive interval inflated by √2.7 excludes 0".
- 2.7 is the upper Monte Carlo bound of one synthetic variance ratio (calc §E, G = 24, one generative model).
- **It is not a proven upper bound on the sampling variance** of the LOBO procedure.

**[RULE]**
- **If no inference method is admissible under P05-SV1 (E5),** every confirmatory contrast is classified **"inference not
  validated"**.
- **No confirmatory outcome can then be declared:** neither "supported benefit", "no meaningful gain" nor "supported harm".
- **Point estimates and any intervals** are still reported. Every apparent benefit is labelled **exploratory**.
- **If some methods are admissible,** 2.2 §4.2's rule applies, and only among admissible methods: the confirmatory interval
  is the widest one. Revision 2.1 §4.3's refit rule is likewise applied only among admissible methods.

**Inflation 2.7 remains only as a planning assumption** in the pilot's precision projection (revision 2.1 §5.2, R3′). It is
labelled [ASSUMP] there and is never used to construct an inferential interval.

---

## E2. N1 with singleton groups; contrast versus distribution (replaces 2.2 §1.4, N1–N2)

**[RULE]: permutation draw.**
- Each group containing **≥ 2 records** is permuted by a uniformly drawn **derangement** of that group, so no record keeps its
  own row (or cf block).
- **Singleton groups are left unchanged.** That is unavoidable, not an error.

**[RULE]: N1, moved-record fraction.**
- For each fold and each draw, F = (number of training records whose assigned row or cf block comes from another record **and
  differs in value** from their own) / (number of **all** training records in the fold).
- The denominator **includes** singleton records, records in groups whose rows are identical, and records that received an
  identical row.
- **N1 holds** if the mean of F over folds and draws is ≥ 0.50.

**[PROOF]: worked cases.**
- With strata made of one pair plus one singleton (m_inst = 3, K = 2, where one bin is shared by exactly two instances),
  F ≤ 2/3.
- If every non-singleton group is a pair of identical rows, F = 0.

**[RULE]: N2 replaced by three explicitly named regimes.**
- **The count:** D = Π over groups with |g| ≥ 2 of !|g|, the number of distinct joint derangements per fold.

| regime | condition | what is reported | p-value |
|---|---|---|---|
| **Single deterministic contrast** | D = 1 (every non-singleton group is a pair) | exactly one control policy; the paired contrast memory − control, with an interval only from an admissible method (E1) | none; the words "permutation" and "20 permutations" are not used |
| **Limited exact set** | 2 ≤ D < 20 | all D joint derangements enumerated, labelled "exact set, D = …" | resolution no finer than 1/D |
| **Genuine permutation distribution** | D ≥ 20 | 20 distinct joint derangements drawn without replacement | from the reference distribution |

**[RULE]:**
- **N3** (≥ 50 % of training bases contain a group of size ≥ 2) is unchanged.
- **A control that fails N1 or N3 is INVALID** (2.2 §1.5). Its regime is not considered.

---

## E3. Stage 0b instances under the P-B / T1-panel default (replaces 2.2 §3.2, step 5 "3 instances")

**[RULE]: selection.** Draw three instances under a declared seed, after the A2 pilot-base draw. Each must be:
- on three **distinct** bases among the six T1-panel pilot bases (all hdb-v1);
- physics-eligible under the E-check;
- single-mechanism, from three different taxonomy groups so that body, control and actuation paths are exercised:
  - one **mass or geometry** fault (`payload_offset`, `short_feet` or `heavy_torso`);
  - one **sensing or control** fault (`pitch_sensor_bias`, `feedback_gain_loss` or `clock_fault`);
  - one **actuation** fault (`actuator_weakness` or `one_side_weakness`);
- at any severity multiple;
- **disjoint from the pilot's own instances.** Stage 0b data are never pooled into pilot statistics.

**[RULE]: scope of the result.**
- Passing Stage 0b clears S8 (diagnosis independence) and determinism **only for**:
  - the hdb-v1 generator;
  - the tested families, the ten tools and both optimizer seeds;
  - the harness commit used.
- **If the owner chooses P-C,** step 5 instead uses one instance per generator group (hdb-v1, walkrec-m1, hand) from the
  stratified pilot. Any generator not tested in Stage 0b is out of the cleared scope.
- Rollout requirements are unchanged (2.2 amend §Z: 38 k / 70 k / 144 k RE cumulative).

---

## E4. "Representative pilot" qualified (amends 2.2 §2.3, rationale 1)

**[RULE]: replacement wording.**
- A T1-panel pilot is **generator-matched** (TV = 0 on generator).
- Generator matching **does not establish** equivalent difficulty, bounds feasibility, ERROR rates, cost per cell or FULL
  rates between the T1 pilot bases and the confirmatory T1 + T3 bases.

**Known differences** [HIST / UNVERIFIED]:
- T1 bases were Stage-2 experience bases, with historical verified outcomes in ≥ 8 of 9 families.
- T3 bases have outcomes in only 1–7 families. Their threshold and eligibility status is unverified.

**Consequences:**
- Pilot rates are reported as **T1-panel rates**. No claim is made that the pilot measured T3 behaviour.
- **T3 is covered only by:**
  - the zero-rollout E-check, which gives feasibility for every population base;
  - the HOLD rule's 90 % cost bound plus 25 % reserve;
  - pre-declared **in-campaign safety monitoring by tier**: the same S3 ERROR and S7 cost-per-cell STOP thresholds,
    applied separately to T1 and T3 cells. This is non-adaptive: it can stop the campaign but never modifies the design or
    the analysis.
- **Owner option D7′:** a pilot of 4 T1-panel + 2 T3 bases.
  - Confirmatory G stays 28 (6 bases lost either way).
  - T3 is then sampled in the pilot.
  - The H2-naive set drops from 22 to 20 bases.

---

## E5. Renaming (applies to 2.2 §4.2, §6, §7)

- **[RULE]:** the synthetic statistical-validation steps V0, V1 and V2 are renamed **P05-SV0, P05-SV1, P05-SV2** (P0.5
  statistical validation).
- **"V1" in this protocol family refers only to Creature Forge's frozen release V1** (`v1.0.0-rc1`). The protocol never
  modifies it.
- The content and compute estimates of the three steps are unchanged.
- **P05-SV1 has not been run.**

---

## Updated approval dependencies (supersedes 2.2 §6; none approved)

| item | depends on | changed by 2.2a |
|---|---|---|
| A0 | — | the documentation commit also records E1–E5 |
| A1 | — | — |
| A2 | D2, D7 / D7′ | E4: pilot composition option D7′ |
| A3 | D3 | — |
| A4 | A1, D5 | E2: derangement rule, N1 denominator, three regimes |
| A5 | A4, **P05-SV0 + P05-SV1 results** | E1: no admissible method ⇒ "inference not validated"; E5: renaming |
| A6 | A1–A5 | Stage 0a remains its acceptance test |
| A7 (Stage 0b) | A6 with Stage 0a passed, **A2 drawn** (pilot bases are needed for the E3 instance draw) | E3: instance rule and scope limit |
| A8 | A2, A7 | — |
| A9 (pilot) | A7 with S8 cleared **for every generator in the chosen population**, A8, A2 | E3 scope, E4 wording |
| A10 | measured A9 costs | — |
| A11 (campaign) | A9 EXPAND, A10, A5 | E1: confirmatory classification only if an admissible method exists; E4: tier-wise safety monitoring |

*End of erratum 2.2a. Stopped here.*
