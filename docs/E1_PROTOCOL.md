# E-1 protocol: physics-grounded investigation vs equally plant-budgeted exhaustive repair on sealed held-out damage

**Status: REGISTERED 2026-10-24** (owner approval 2026-10-24: 160 sealed test instances, batch-VM spend of about $18–23,
infra cap $120). The registration record is in §9. Everything below is frozen. The sealed test side is opened only by
`scripts/e1_build.py`, run after the registration commit was pushed.

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
| **G-R2 execution VM** | G-R repeated on the batch VM (the execution machine) at the registration commit: A0 and A1 exact on the same 4 stored dev instances | before any arm runs (may run alongside the physics-only build) |
| **G-O operations** | VM-side API self-stop installed and tested end to end (STOPPED on the control plane); Windows watchdog on the service-account path; deadline inside the SA key lifetime | before the build |
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

### 7.1 Registered recovery procedure

| failure | action |
|---|---|
| a worker or process dies; one arm shard fails | re-run the same shard with `--resume`. Inputs are identical; completed instance records are kept, and a partial episode is recomputed from scratch |
| the VM stops, crashes or reaches its deadline mid-run | restart the VM, re-sync the registered commit (identical tree), resume every shard with `--resume` |
| the build is interrupted | re-run `e1_build.py` on the same out-dir; it resumes, reusing evaluated candidates and thresholds |
| a gate fails | stop, preserve the evidence and report. No fix-and-continue without a dated amendment, and no amendment after any arm outcome is seen |

Never allowed: any change of code, settings, seeds, sample or analysis after an arm outcome has been seen. Every deviation
from this protocol is reported in the results.

### 7.2 Reserve for the future Nemotron evaluation

- The 160 sampled instance ids are listed in `instances.jsonl` and are spent for every future confirmatory claim.
- A later registered study (e.g. Stage 3, A3 > A1) samples from the **complement**:
  - test-side candidates not in `instances.jsonl`;
  - its own sampling seed;
  - eligibility re-checked.
- Thresholds and eligibility rows computed by this build are physics only and may be reused. Nothing from E-1's arm outcomes
  may inform that sample.
- `experiments/e1/RESERVE.md` records this rule and the spent ids.

## 8. What E-1 cannot show

- That Nemotron adds value: there are no LLM arms.
- That experience improves decisions: that is the roadmap's §5 line.
- Real-robot performance.
- Effects outside the hdb-v1 generator family. All bases come from one walker generator; the damage DSL and the simulator
  are shared with the twin, and only the reality gap is withheld.

## 9. Registration record

- **Registration commit:** the commit that contains this text, on branch `research/e1-engine-heldout`, pushed before the
  build.
- **`experiments/e1/protocol.json`** sha256 `a32107980635a8de6266e2121752ee9f2719acdc30505be4c49f3038470d3c81`.
- **Frozen code** (sha256 of the committed blobs). Science code is unchanged since G-R commit `d63f901`. The four HDB modules
  equal the `docs/HDB_SPEC.md` freeze hashes.

| file | sha256 |
|---|---|
| `creature_forge/hdb_testbench.py` | `aad2165848cfeaa7758e44ba10d54312e5834635ca5bf3fd0b57e8e022e761e8` |
| `scripts/e1_build.py` | `6b7ded0fe07e44435d17c533d996e572ce721555cd02c3df96297f433d50e1c1` |
| `scripts/e1_run.py` | `fd0e3a0f4501a1b63bb279d05df33a69f32a3a898ff6494875d759779d395c83` |
| `scripts/e1_analysis.py` | `178900c3a6c93cad857f24348bfb79fbc087211c4e7c504b6cd63e133fac60a0` |
| `scripts/hdb_vs_run.py` | `79234ffcaf8d6aa3d89ef2403f857cf1d1c2d2c016754cf72c6ed8d20fe01917` |
| `creature_forge/belief_engine.py` | `12e20cfeaa3f7dfaef1c7ad79f92b9df4cc929cfd2d92c6572ef98d44e66e915` |
| `creature_forge/hdb_workbench.py` | `ba34b0a5f0aa2c729218a53a80a7525a60f6b474086bc79ee8049a50081d83d0` |
| `creature_forge/hdb_policies.py` | `d50ea77030f65ded482fb4f985c168062e7fdf64130f7e96ba5f8e81d8b6805e` |
| `creature_forge/hdb_bench.py` | `7bd810cf9b843ef9fa9b84f73f7f03ae55f91878030a2acbd85446845a64af05` |
| `creature_forge/hdb_heldout.py` | `3875de597cfbcb8dd71cd4fae8ddc533d8e0cdeb2d23492174fc8cfec79f1077` |
| `creature_forge/hidden_plant.py` | `91c26fd93fcb303e877ff5ee15ee62b7543077b2f549aae0875bad9e2773b7c6` |
| `creature_forge/forge_pool.py` | `bc8145fd18c0c4d5574587bcfc0ca9fd1620c6e7c63691312826689a00347f43` |
| stop map `experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json` | `8cf94726378daa10b3ef88db36f30887a056b9cda89d4a724651ba5898723595` |

- **Environment:**
  - venv `~/dev/venvs/hdb` (Python 3.12.3, mujoco 3.15.0, numpy 2.5.4) on the main VM (G-R) and on the batch VM (G-R2,
    execution);
  - walkers `CF_HDB_WALKERS=artifacts/hdb/walkers_all.jsonl`.
- **Gate evidence:** G-R `experiments/e1/gate/gate_G_R.json` (sha256 `38a917ae…`). G-O was run 2026-10-24 on the batch VM:
  VM-side deadline set in the past → API self-stop → STOPPED in 47 s.
