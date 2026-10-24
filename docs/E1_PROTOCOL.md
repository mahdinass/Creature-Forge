# E-1 protocol: physics-grounded investigation vs equally plant-budgeted exhaustive repair on sealed held-out damage

**Status: DRAFT, not registered.** Registration means:
1. this file and `experiments/e1/protocol.json` are final;
2. the code hashes in §9 are filled in;
3. the commit is pushed;
4. **then**, and only then, the sealed test side is opened by `scripts/e1_build.py`.

Nothing in this study has touched the sealed side yet.

**Context:** `docs/ROADMAP_REASSESSMENT_2026-10-24.md` §4. **Bench:** `docs/HDB_SPEC.md` (HDB v2, frozen 2026-10-19).
**Dev evidence motivating it:**
- fresh dev robots: A1c5 109 vs A0 62 of 211, paired 61 vs 14;
- `experiments/causal_engineer/dev/hdb/ARMS_fresh_dev_9families.md`.

These are development data: the engine, the stop map and the dev families were developed on them.

## 1. Question

On walking robots with **hidden** damage, does the physics-grounded investigation engine reach independently verified full
recovery more often than a generic exhaustive repair search with the same plant (real-experiment) budget? The test covers:
- damage drawn from mechanisms **never used in development** (sensor latency, joint damping wear, leg asymmetry, compositions);
- unseen dev-family instances on **unseen morphologies**.

## 2. Arms

All arms are paired on the same instances, with identical instruments and seeds:
- plant budget 700 rollout-equivalents;
- twin budget 2,800;
- the instance's train / obs / robust / twin seeds;
- noise seed = first 4 bytes of the instance id.

| arm | what it is | code |
|---|---|---|
| **A0** | generic exhaustive repair: the strongest model-free procedure on the bench | `hdb_vs_run.run_a0` → `hdb_policies.generic_exhaustive` |
| **A1** | belief engine v5: competing executable hypotheses, paired-seed twin likelihood, EIG experiment choice, posterior-robust twin + plant repair, calibrated stopping (dev stop map v1, τ = 0.75). This is the fresh-dev **A1c5** configuration | `hdb_vs_run.run_one(arm="A1")` |
| **K0n** | the same engine and repair pipeline with **no diagnosis**: nominal hypothesis only, no experiments, same twin and plant repair budgets and the same stop rule | `scripts/e1_run.run_k0n` (MKV K0n plus A1's stop rule) |

**Notes on the arms:**
- Every arm is NO_AI (deterministic). Nothing here is credited to Nemotron.
- Policies see only `hdb_bench.policy_view`: the nominal design and policy-visible seeds. They never see the plant, family,
  severity, check results, strata labels or verification seeds.
- **Compute disclosure:**
  - A1 and K0n use the twin budget, which is simulation on the nominal design under hypotheses; A0 does not.
  - Plant budgets are matched, following the spec, §12 G3 ("match physics experiment budget; report compute separately").
  - K0n is the compute-matched control for A1, with equal plant and equal twin budget.
  - Both plant and twin use are reported per arm.

## 3. Hypotheses and analysis (fixed; `scripts/e1_analysis.py`)

**Outcome.** `FULL_RECOVERY` under `full_recovery_v1` on the hidden plant, from validate and confirm seeds that no arm sees
(`hdb_bench.verify`).

**Primary test.**
- **H-E1:** FULL(A1) > FULL(A0).
- Test: exact one-sided McNemar on discordant pairs, α = 0.05.

**Secondary tests** (Holm over 2, α = 0.05):
- **H-E2:** FULL(A1) > FULL(K0n). Does investigating the cause add value beyond the twin-robust repair machinery?
- **H-E3:** FULL(K0n) > FULL(A0). Does the twin-robust repair alone beat model-free search?

**Sensitivity (pre-declared, not a gate).** A base-clustered sign-flip permutation test for each contrast (200,000 flips,
seed 2026102402). Instances on the same base are not independent.

**ITT.**
- Every sampled instance counts.
- An arm episode that is missing, crashes or ends without a verification counts as not FULL for that arm, and is listed.
- A worker-death or infrastructure failure may be re-run once with identical inputs, and the re-run is logged.
- No other re-run, no exclusion and no change after the first outcome is seen.

**Descriptive** (no inference):
- per stratum, held-out vs dev-family, severity multiple;
- validation walking fraction;
- plant and twin use;
- A1 diagnosis: the MAP structure vs the injected one.

**Wording rules.**
- A null on H-E1 is reported as "no evidence that the engine beats exhaustive search on sealed held-out damage". It is not
  called a falsification.
- A positive H-E1 with a null H-E2 is reported as "the twin-robust repair, not the diagnosis, carries the advantage".
- Search failure at a finite budget is never called physical impossibility.

## 4. Population and sampling (physics only; `creature_forge/hdb_testbench.py`, `scripts/e1_build.py`)

**Bases.** The 99 hdb-v1 test-side walkers (`hdb_bench.load_bases("test")`). They have never been used in development.

**Strata and quotas** (n_total = 160; `experiments/e1/protocol.json`):

| strata | quota each | total |
|---|---|---|
| 9 dev families on unseen bases | 6 | 54 |
| sensor_latency, joint_damping_wear, leg_asymmetry (sealed) | 18 | 54 |
| 4 sealed compositions (each component at 0.6× or 0.8× its own threshold) | 13 | 52 |

**Candidates.**
- For single strata: every (base, variant, multiple ∈ {1.0, 1.3, 1.7}).
- For composition strata: every (base, fraction).
- Strength: each variant's own failure threshold s* on that base (bisection, 6 steps, gap-free plant, check seeds of the
  variant's own key), times the multiple. This is the frozen HDB v2 rule, extended unchanged to the sealed specs.

**Order.**
- Within a stratum, candidates are ordered by sha256(`2026102401:stratum:base:severity`).
- Strata take turns in strict round robin, in the protocol's key order.

**Acceptance.** A candidate is accepted iff all of these hold:
- it is constructible (its thresholds exist, and the multiple is within the variant's maximum);
- it is **eligible**: the plant (deviation + hidden reality gap) walks on ≤ 2 of 8 check seeds, with no error;
- its base has fewer than 2 accepted instances overall and none in this stratum.

The sampler never reads any arm, oracle or verification result. Physics may be computed speculatively for candidates that a
cap later skips, but the accepted set depends only on the fixed order and on deterministic physics (tested:
`tests/test_e1.py`).

**Reserve.** Every unsampled eligible instance stays sealed for a later registered study, such as Stage 3 A3 > A1.

## 5. Gates (in order; each failure stops the study and is reported)

| gate | check | when |
|---|---|---|
| **G-R reproduction** | At the registration commit, A0 and A1 rerun on 4 stored fresh-dev instances (dev data only) must exactly reproduce the stored records: eligibility rows, verification status, walking fraction, every design created, and plant and twin use. K0n smoke on the same 4 must complete | before registration |
| **G-T tests** | `tests/test_e1.py` and the existing HDB tests pass on the VM | before registration |
| **G-B build** | `e1_build.py` completes; quotas are met, or shortfalls are recorded (no top-up from other strata); `summary.json` and `SHA256SUMS` are written and pulled | after registration, before any arm |
| **G-C completeness** | every arm has exactly one record per instance (ITT rules above) | before analysis |

## 6. Compute and cost

**G-R result (2026-10-24, main VM, slot `hdb` = commit `d63f901` tree): PASS.** A0 4/4 and A1 4/4 reproduce the stored
fresh-dev records exactly (eligibility rows, status, walking fraction, all designs, plant and twin use); K0n completed 4/4.
Evidence: `experiments/e1/gate/` (`gate_G_R.json` sha256 `38a917ae…`, `SHA256SUMS`). Cost $0.42.

Wall per episode on the gate (concurrent on the 8-vCPU VM): A0 ≈ 196 s (2 workers), A1 ≈ 443 s (3 workers), K0n ≈ 476 s
(2 workers); 12 episodes in ≈ 1.5 h of VM time.

**Projection (160 instances × 3 arms = 480 episodes):** about 60 h on the main VM (too slow for the deadline), or about
7–9 h on the batch VM (64 vCPU, $2.30/h), about **$17–21**. The build (thresholds and eligibility, about 30–60 k rollouts) adds
about $1–2. **Total ≈ $18–23** of the $37.49 Cloud credit. The infra cap (`SPEND_CAP_USD`) must be raised to about $120; that is
an internal guard within the real credit and is recorded with its reason. Budget authority: the owner's 2026-10-24
development mandate.

## 7. Execution

- **VM:** the batch VM (64 vCPU) for the build and the arm runs. Arms are sharded (`--shard k/n`) with ≤ 7 workers each
  (the `ForgePool` cap).
- **Each session** runs within one CLI-token window, with the auth-horizon guard on and the watchdog running. Stop through
  the API and confirm STOPPED.
- **Outputs:** `artifacts/e1/` on the VM, pulled with `SHA256SUMS`. Records are committed under `experiments/e1/results/`
  with `-text`.

## 8. What E-1 cannot show

- That Nemotron adds value: there are no LLM arms.
- That experience improves decisions: that is the roadmap's §5 line.
- Real-robot performance.
- Effects outside the hdb-v1 generator family. All bases come from one walker generator; the damage DSL and the simulator
  are shared with the twin, and only the reality gap is withheld.

## 9. Registration record (to be filled at registration)

- Commit: `<sha>`.
- `protocol.json` sha256: `<…>`.
- Code sha256:
  - `hdb_testbench.py`, `e1_build.py`, `e1_run.py`, `e1_analysis.py`, `hdb_vs_run.py`;
  - `belief_engine.py`, `hdb_workbench.py`, `hdb_policies.py`, `hdb_bench.py`, `hdb_heldout.py`, `hidden_plant.py`;
  - stop map `8cf94726…`.
- Environment: VM venv `~/dev/venvs/hdb` (mujoco 3.15.0, numpy 2.5.4); G-R report sha256.
