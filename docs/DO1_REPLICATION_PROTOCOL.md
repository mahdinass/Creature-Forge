# DO-1 replication (W3) and cross-family pilot (W4): pre-registration

- **Registered:** 2026-10-21, before any W3 or W4 episode ran.
- **Branch:** `experiment/do1-replication-w3w4`, from the frozen DO-1 harness `e9d2379`
  (tag `checkpoint/do1-l4-r0-harness-e9d2379`).
- **Code:** `scripts/do1_repair_ablation.py`; runner `do1_ablation_v2`, phases `DO1-L4-rep` and `DO1-X`. This commit
  becomes the `--harness-commit` of both executions.
- **Authorization:** the owner's 2026-10-21 instruction covers exactly these two phases, with an incremental Nebius ceiling of
  $1.50 for both together. No paid model inference.
- **Plan of record:** `~/.claude/plans/pasted-content-id-3fc3-creature-cozy-parasol.md`, sections 5 to 7.

## 1. What is unchanged
- **Frozen code:** the engine, optimizer, verifier `full_recovery_v1`, the DO-1 objective `do1_objective_v2`, and every
  frozen input.
- **Enforcement:** the runner's preflight refuses if anything under `creature_forge/`, `experiments/`,
  `scripts/hdb_agent_run.py` or `scripts/ds1_launch.sh` differs from `ea9e729`. It also refuses if the inputs or the
  stored DS-1 records differ from their frozen hashes, or if the worktree is not clean at the approved commit.
- **Runner changes in this commit:**
  - two new phases;
  - a run role (`sentinel`, `primary`, `exploratory`);
  - the NOT_EXPOSED continuation rule and the stored-prefix gate, both for the new phases only;
  - recording of infrastructure errors;
  - two W4 cases, kept in the runner's own `CASES` so that `ta1.CASES` (TA-1's pre-registered list) is untouched.
- The v1 phases (`DO1-L4-r0`, `DO1-L4`, `DO1-L1`) behave exactly as before.

## 2. W3: `DO1-L4-rep` (replication on ONE development instance)
| Item | Registered value |
|---|---|
| Instance | L4 = `hdb-v1-gen-0137:low_ground_friction:0`. Stored A1e6 record: `eval_A1e6_s3.jsonl` line 4, submitted design 4, hash `66053dae8e` |
| Runs, in order | 1. frozen r0 **sentinel**; 2. frozen r1, do1 r1, frozen r2, do1 r2, …, frozen r5, do1 r5 (11 episodes) |
| Arms | `frozen`: the unchanged A1e6 episode on `EvidenceWorkbench`. `do1`: the same, but on `Do1Workbench` (the plant repair ranks CMA candidates by the DO-1 objective) |
| What varies between replicates | Only the bench noise seed, `1751409197 + 10007·r`. It is used solely by the plant-repair CMA (`+ 7919·k` for the k-th repair), and is identical in both arms of a replicate |
| Noise seeds | r1 1751419204, r2 1751429211, r3 1751439218, r4 1751449225, r5 1751459232. The sentinel r0 uses 1751409197 |
| Fixed | Instance and physical plant, twin-CMA seeds (11 and 0), train, robust, validation and confirmation seeds, stop map v2, tau 0.75, plant budget 700, twin budget 2,800, verifier, objective |
| Pairing | Seed-matched, not trajectory-matched: after the first plant repair the trajectories may diverge |
| Ceiling | `--max-rollouts 39644` = 11 × 3,604 rollout-equivalents (plant 804 + twin 2,800 per episode). The sentinel counts against it |

**Sentinel.** Frozen r0 must reproduce the stored A1e6 record exactly (all 21 checks), as the DO1-L4-r0 pilot did. It is
an environment-reproduction check only and is excluded from every analysis. If it fails, the phase stops before r1.

**Why a stored-prefix gate for r ≥ 1 is valid.** This is a no-physics fact, tested in
`W4Selection.test_l4_prehook_trace_has_no_plant_repair`.
- The noise seed enters only `run_repair` (the plant CMA).
- Both twin CMAs use fixed seeds (11 and 0).
- The weigh-test noise is keyed on the robot id.
- The stored L4 trace reaches the engineer hook before its first plant repair.

So every replicate's pre-hook segment must equal the stored record's. Both arms are checked, as are equal pre-hook
fingerprints within each pair.

**Hypothesis.** DO-1 reaches FULL_RECOVERY on more L4 replicates than the frozen objective, under matched optimizer
randomness.

**Primary outcome.** FULL_RECOVERY per episode, under the unchanged `full_recovery_v1`. This needs:
- validation walking aggregate PASS (≥ 20/24);
- a VERIFIED_IMPROVEMENT paired displacement verdict;
- a passed independent 20 s confirmation.

**Primary analysis** (intention to treat, the 5 pairs r1–r5):
- FULL count per arm, k/5, with exact Clopper–Pearson 95 % intervals;
- the exact one-sided McNemar (sign) test on discordant pairs, alpha 0.05;
  - 5/0 gives p = 0.031;
  - 4/0 gives 0.0625: suggestive, inconclusive;
  - mixed or fewer discordant pairs: descriptive only.

**Secondary** (descriptive):
- PARTIAL_IMPROVEMENT and NOT_RECOVERED counts;
- the paired validation walking difference k/24 per replicate, with an exact one-sided sign test (ties dropped);
- verdict and median paired displacement per episode;
- confirmation runs and checks;
- plant and twin rollouts, and stop-map acceptance;
- the binding walking gates of DO-1's selected candidates, and whether each selected candidate was the last one evaluated;
- the per-protocol analysis, which excludes pairs whose do1 episode was NOT_EXPOSED. It is always shown next to ITT, with
  the count and reason for each exclusion.

**Analysis code.** `scripts/do1_replication_analysis.py`, committed now, before execution, with tests in
`tests/test_do1_replication_analysis.py`.

**The r0 pilot.** `experiments/do1/l4_r0/` on `feature/do1-demo` is shown alongside as an exploratory reference. It is
never pooled and never counted as confirmatory.

**Generalization limits.**
- These are technical replicates of optimizer randomness on one physical instance, evaluated on the same, already studied
  L4 validation seeds.
- They estimate how reliably DO-1 repairs *this* robot under different optimizer randomness.
- They say nothing about unseen robots, fault families or validation conditions.

## 3. W4: `DO1-X` (exploratory cross-family pilot)
**Pre-declared eligibility rule.** It was fixed in the plan of record before any DO-1 run on these instances, and is
re-evaluated over all 30 stored A1e6 records in `W4Selection.test_rule_selects_b1_and_c1`. An instance is eligible if:
- its base is in the Stage-2 transfer split, and it is not excluded from it;
- its family is not `low_ground_friction`, and its base is not gen-0137;
- its stored status is PARTIAL_IMPROVEMENT, with walking only as the failure reason (17–19/24);
- its stored trace contains at least one plant repair.

**Selection.** One body/mass case (taxonomy "mass properties" or "geometry") and one controller case ("control" or
"control timing"). In each class the highest stored walking count wins, and ties go to the lowest base id. Counting
"sensing" as a controller class changes nothing, which the test checks.

| Case | Instance | Stored record | Stored A1e6 |
|---|---|---|---|
| B1 (body/mass) | `hdb-v1-gen-0142:payload_offset:5` | `eval_A1e6_s3.jsonl` line 5, design 2, `73146bcf6e` | PARTIAL 17/24 |
| C1 (controller) | `hdb-v1-gen-0070:feedback_gain_loss:2` | `eval_A1e6_s5.jsonl` line 1, design 4, `9823aeddda` | PARTIAL 19/24 (tied with `clock_fault:3`@0104, broken by base id) |

**Runs.** B1 r0 frozen, B1 r0 do1, C1 r0 frozen, C1 r0 do1: 4 episodes. Ceiling `--max-rollouts 14416` (4 × 3,604).
Under the DS-1 seed rule, every instance's r0 bench noise seed is 1751409197, because it comes from the first 4 bytes of
the id, "hdb-". This is disclosed and is not a defect.

**Gates.**
- frozen r0 reproduces the stored record exactly;
- do1 r0 matches the stored pre-hook prefix;
- equal pre-hook fingerprints;
- the hook is called once;
- verification is complete;
- DO-1 exposure is recorded.

**Analysis.** Descriptive per instance and arm:
- status;
- validation k/24;
- verdict and median paired displacement;
- confirmation;
- plant and twin use;
- which recovery gates changed (walking aggregate, displacement verdict, confirmation).

There is no hypothesis test, no pooling with L4, and no family-level or population-level claim. Cases were chosen on the
baseline's partial failure, so regression to the mean is possible.

**Independence from W3.** The cases are fixed now. W3 outcomes cannot change them. W4 does not run if W3 stops on a
validity defect (see §4), because the same environment gates would be at stake.

## 4. Stopping rules and failure handling (both phases)
- **No outcome-based stopping.** No extra replicates, and no re-runs after seeing results. An extension needs new owner
  approval and a new phase name.
- **Validity defects pause the phase fail-closed:**
  - sentinel or reproduction mismatch;
  - stored-prefix mismatch;
  - unequal pair fingerprints;
  - incomplete verification;
  - hook calls ≠ 1;
  - an inconsistent DO-1 selection or baseline;
  - an infrastructure error (an exception inside an episode is written to the output as its own line before the pause).

  Completed pairs are reported, together with the defect. A paused study is reported as incomplete, never as a smaller
  study. Nothing is re-run or replaced without owner approval.
- **NOT_EXPOSED** (no DO-1 plant repair completed) is a property of the policy. The episode is verified, kept and counted
  in ITT, and the phase continues.
- **Hard limits:**
  - the rollout cap (checked before each episode);
  - `--max-wall-s` (W3 7,200 s, W4 3,600 s; checked before each episode);
  - the VM deadline.

  Unrun episodes are reported as not run, with the reason.
- **Order and dependency:** W3 runs first. W4 starts only if W3 exits 0. Otherwise both stop and the state is reported.

## 5. Execution and controls
- **VM:** the main Nebius VM (8 vCPU), using `--workers 6` and the `run_do1_l4_r0.sh` pattern.
  - The approved commit is pushed to the VM's bare repository and checked out clean at the exact commit; HEAD must equal
    `--harness-commit`.
  - Stored records and artifacts are hash-checked by the preflight.
- **Expected runtime:** about 6 min per episode, so W3 takes about 70 min and W4 about 25 min.
- **Cost:** about $0.30/h, which gives an expected ≈ $0.6 including boot and collection. The ceiling is $1.50
  incremental: the infra ledger must stay ≤ $90.50 (start ledger $88.995).
- **Deadline:** the VM deadline is set to at most 3.5 h, with the Windows watchdog active.
- **End of session:**
  - SHA-256 on the VM and locally;
  - raw JSONL, manifests and logs copied to `creature_forge_runs/`;
  - **stop through the API** and confirm both VMs are STOPPED;
  - the ledger difference and exact rollout counts are recorded.
- **Results:** they go to `experiments/do1/w3_l4_rep/` and `experiments/do1/w4_x/` after execution, as byte-exact
  publication copies. The pre-registration commit itself adds nothing under `experiments/`, because the preflight forbids
  it.

## 6. Reporting wording
- **Null:** "No verified recovery was found under the tested intervention, optimizer configuration and computational
  budget."
- **Attribution:** DO-1 is a deterministic objective change, NO_AI. It is never attributed to Nemotron.
- **Scope:** a FULL rate on L4 is an instance-specific reliability estimate over optimizer randomness. W4 is two
  examples, not a benchmark.
- **Review:** results go to the owner for independent review before any Studio or submission wording changes.
