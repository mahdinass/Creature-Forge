# Hidden-Damage Bench (HDB) v2: specification

Status: **FROZEN 2026-10-19 (bench definition; code at commit `251765b`)**, after the multi-class identifiability study
(`experiments/causal_engineer/dev/hdb/IDENTIFIABILITY_v2_multiclass.md`: 282/302 dev instances identified with all
instruments; observation alone 245, + condition tests 270). **The owner confirmed the threshold-relative severity
definition (§3) on 2026-10-19.** The spec is unchanged by the confirmation.
Hashes at the freeze (SHA-256 of the committed blobs at that commit, LF line endings: `git show <commit>:<path> | sha256sum`):
- `creature_forge/hdb_bench.py` sha256 `7bd810cf9b843ef9fa9b84f73f7f03ae55f91878030a2acbd85446845a64af05`
- `creature_forge/hdb_heldout.py` sha256 `3875de597cfbcb8dd71cd4fae8ddc533d8e0cdeb2d23492174fc8cfec79f1077`
- `creature_forge/hidden_plant.py` sha256 `91c26fd93fcb303e877ff5ee15ee62b7543077b2f549aae0875bad9e2773b7c6`
- `creature_forge/hdb_workbench.py` sha256 `ba34b0a5f0aa2c729218a53a80a7525a60f6b474086bc79ee8049a50081d83d0`
At the freeze, this file gets the commit and the SHA-256 of `creature_forge/hdb_bench.py`, `creature_forge/hdb_heldout.py`,
`creature_forge/hidden_plant.py` and `creature_forge/hdb_workbench.py`. Any later change is a dated amendment with a reason;
none may be motivated by an arm's results. Plan of record: `docs/HAS_PLAN_2026-10-18.md`. Log: `docs/HAS_SCIENTIST.md`.

## 1. Bases (nominal designs)
- **Dev:** the 12 earlier dev walkers (`fault_bench` dev split), plus the 36 fresh walkers whose region is on the dev side.
- **Test:** the 99 fresh walkers whose region is on the test side.
- **Provenance:** fresh walkers come from campaign `hdb-v1-walkers` (`scripts/hdb_walkers.py`):
  - S3 generation rule (`hdb-v1-gen`);
  - FIX pipeline at 2,000 rollouts;
  - `full_recovery_v1`.
- **Split:** the dev/test assignment is a hash of the morphology region, fixed before any pipeline ran.
- **Isolation:** test bases are never used in development. The 40 old held-out instances are never reused.

## 2. Mechanism families (fixed before any comparative run)

| Pair | Dev families (`hdb_bench.FAMILY_SPECS`) | Held-out families (`hdb_heldout`, sealed) |
|---|---|---|
| T1 balance instability | feedback_gain_loss (gain_scale balance_feedback) | sensor_latency (sensor_delay all) |
| T2 lean | pitch_sensor_bias (±), payload_offset (fwd/back) | — |
| T3 weakness | actuator_weakness (actuator_strength all) | joint_damping_wear (joint_damping all) |
| T4 slip vs support | low_ground_friction, short_feet | — |
| Singles | one_side_weakness (left/right), clock_fault (fast/slow), heavy_torso | leg_asymmetry (shank l/r) |
| Compositions | — | 4 pairs of dev primitives, each component at 0.6× or 0.8× its own threshold |

## 3. Severity
- Each (base, family variant) has a **failure threshold** s\*: the smallest fault strength at which the gap-free plant walks on
  ≤ 2/8 check seeds. It is found by bisection, 6 steps (`hdb_bench.threshold`).
- Instances use strength = **1.0×, 1.3× and 1.7× s\***, capped at the variant's DSL maximum. A variant with no threshold
  (the design still walks at the strongest allowed fault) has no instances.
- Every plant also carries the instance's hidden **reality gap** (`hdb_bench.reality_gap`):
  - torso mass ±3 %;
  - damping ×0.8–1.25;
  - friction ±5 %;
  - per-joint actuator strength ±5 %.

## 4. Eligibility (physics only)
- Valid: in bounds, no simulation errors.
- The plant (deviation + gap) walks on **≤ 2 of 8 check seeds**.
- No criterion uses any policy's or oracle's result.

## 5. Strata labels (reported, never filters)
- **R/U:** oracle repair = the engine's posterior-robust repair given the exact deviation (MKV condition K2) at the
  evaluation budget. R if FULL.
- **Ambiguity:** from the identifiability study. The injected family is not the multi-class MAP with all instruments on the
  same base family.
- **Family, pair, severity multiple, held-out/dev.**

## 6. Sampling (registered study)
- **Population:** all eligible test instances.
- **Sample:** stratified random, with a fixed seed and quotas per family declared in the protocol.
- **Primary analysis:** includes R, U and ambiguous instances.

## 7. Instruments and budgets (identical for every arm)
- **Plant budget 700 rollout-equivalents:**
  - observe (4);
  - parametric counterfactuals (4);
  - floor test (4);
  - weigh test (1);
  - robustness check (8 or 16);
  - 20 s stress test (8);
  - repair (CMA over tool subspaces, body ratio ×0.25–4, n_train 4 or 8).
- **Twin budget 2,800** (4× plant), policy-visible seed roles only.
- **Verification:** `full_recovery_v1` on the hidden plant (`hdb_bench.verify`), against the nominal design on the same
  plant.

## 8. Seeds
Campaign `hdb-v1`, `creature_gen.walkrec_seed_block`. Roles:

| Role | Namespace | Count | Policy-visible |
|---|---|---|---|
| check | screen | 8 | no |
| train | train | 8 | yes |
| obs | probe | 8 | yes |
| robust | selection | 16 | yes |
| twin | gen | 16 | yes |
| validate | validate | 24 | no |
| confirm | confirm | 24 | no |

Roles are disjoint by construction and asserted per instance.
