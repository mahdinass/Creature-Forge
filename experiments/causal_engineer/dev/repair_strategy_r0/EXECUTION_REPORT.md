# R0 execution report — development gate FAILED

All 324 registered units completed on 25 October 2026. The frozen advancement gate **FAILED**: two repeatable rescue bases (required three), two families (required two), net failed-cohort gain zero against the per-base best restricted/DO-1 comparator (required at least three), and three material control regressions (required zero). There were no missing/invalid units or verification errors. This supersedes the execution-blocked status in the historical preparation REPORT.md; the original proposal and registration remain preserved.

## Scientific conclusion

Joint/DO-1 produced 16/36 FULL outcomes on the historically failed cohort, versus 12/36 for both single/DO-1 and sequential/DO-1. The primary base-averaged difference versus sequential was +11.1 percentage points, descriptive 95% cluster bootstrap [−5.6, +27.8], exploratory two-sided sign-flip p=0.40625. There is some repeatable additional repair capability on two selected development bases, but no sufficient robust advantage for advancement under the registered gate. Three controls regressed. This is a negative advancement result, not proof that coordinated repair is physically impossible.

DO-1 did not provide a general improvement: it increased single recovery but reduced sequential and joint recovery overall. Joint/frozen had the largest observed FULL total (32/54); choosing it after seeing results would change the registered decision rule, so it does not rescue the failed gate. No Nemotron calls, experience learning, model training, held-out transfer, hardware testing or causal mechanism discovery were performed. No R1 work or sealed experiment follows from this result.

## Design and implementation

Frozen six-arm factorial: single, standardized sequential and joint search crossed with frozen and byte-exact audited DO-1 objectives. Eighteen distinct development bases comprise 12 historically unsuccessful cases and six repairable controls; three optimizer randomness replicates per arm produce 324 units. Physical seeds are matched across arms/replicates, with distinct four-train/eight-selection/24-validation/24-confirmation roles. Technical replicates are not independent robots; inferential summaries cluster the 12 failed bases.

Reused CMA/SearchSpace, hidden-plant MuJoCo evaluation, physical bounds and unchanged `full_recovery_v1`. Each policy sees opaque id/nominal design and train/selection seeds; hidden plant state and verification outcomes remain with the trusted evaluator. Eight pairs were predeclared before outcomes; sequential and joint use the same pairs. Sequential chains two group searches, whereas joint optimizes the union simultaneously. The standardized plant-only sequential portfolio is not the full adaptive diagnosis/twin/early-stop engine. Body limits remain anchored to the original robot, with relative [0.25,4] limits plus existing absolute bounds; faults/environment are never edited.

Every unit used exactly 3,000 policy rollouts, including four training and eight selection baselines and top-two candidate selection on eight seeds. Optimization/tail allocation uses the remaining 2,972. The independent verifier adds 48 ten-second validation equivalents and, when triggered, 48 confirmation equivalents. No favorable early stopping or selective rerunning of main outcomes occurred. Equal rollout counts address extra-search confounding, but dimensions, portfolio sizes, initialization and candidate counts differ and limit pure action-space attribution. RL-1's historical matrix budget was 300 per tool over ten tools (about 3,000 total), not 300 total; fresh seeds, objectives, stochastic search and selection differ, so the concurrent arms are the appropriate comparators.

## All six conditions

FULL is independently verified full recovery; partial is not counted as FULL. Failed denominator is 36 and control denominator 18 per arm. Each arm has 54 records and zero ERROR.

| Condition | FULL/54 | Failed FULL/36 | Control FULL/18 | Partial | Not recovered | Mean validation walking | Mean worker seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| joint/do1 | 27 | 16 | 11 | 20 | 7 | 0.7901 | 1348.5 |
| joint/frozen | 32 | 17 | 15 | 15 | 7 | 0.8194 | 1443.7 |
| sequential/do1 | 24 | 12 | 12 | 23 | 7 | 0.7847 | 1542.6 |
| sequential/frozen | 28 | 14 | 14 | 18 | 8 | 0.8056 | 1497.5 |
| single/do1 | 26 | 12 | 14 | 19 | 9 | 0.7963 | 1374.2 |
| single/frozen | 20 | 9 | 11 | 24 | 10 | 0.8171 | 1445.3 |

Validation walking is a component, not a replacement for the unchanged improvement, aggregate and confirmation requirements. A high walking fraction can coexist with failure to demonstrate FULL.

## Registered base-clustered contrasts

Three technical outcomes are averaged within each of 12 failed bases. Intervals use the frozen 10,000 cluster bootstrap draws/seed 2026102507. All seven comparisons appear; probabilities are exploratory exact two-sided base sign flips, without a confirmatory significance claim. The positive descriptive bootstrap interval for joint/frozen versus single/frozen does not override its exploratory p=0.125 or the advancement gate.

| Left minus right | Mean difference (percentage points) | Descriptive 95% interval | Exploratory p | Bases |
|---|---:|---|---:|---:|
| joint/do1 - joint/frozen | -2.78 | [-16.67, +13.89] | 1.00000 | 12 |
| joint/do1 - sequential/do1 | +11.11 | [-5.56, +27.78] | 0.40625 | 12 |
| joint/do1 - single/do1 | +11.11 | [-8.33, +27.78] | 0.40625 | 12 |
| joint/frozen - sequential/frozen | +8.33 | [-11.11, +27.78] | 0.59375 | 12 |
| joint/frozen - single/frozen | +22.22 | [+2.78, +44.44] | 0.12500 | 12 |
| sequential/do1 - sequential/frozen | -5.56 | [-19.44, +8.33] | 0.68750 | 12 |
| single/do1 - single/frozen | +8.33 | [-13.89, +33.33] | 0.68750 | 12 |

## Repeatability, controls and unresolved cases

Entries are FULL counts out of three optimizer replicates. SF=single/frozen, SD=single/DO-1, QF=sequential/frozen, QD=sequential/DO-1, JF=joint/frozen, JD=joint/DO-1. Family labels below are post-run reporting metadata, never policy inputs.

| Instance | Cohort | SF | SD | QF | QD | JF | JD |
|---|---|---:|---:|---:|---:|---:|---:|
| hdb-v1-gen-0008:one_side_weakness:4 | failed | 0 | 0 | 0 | 0 | 0 | 0 |
| hdb-v1-gen-0024:clock_fault:1 | failed | 0 | 0 | 1 | 1 | 3 | 2 |
| hdb-v1-gen-0038:low_ground_friction:1 | failed | 0 | 0 | 1 | 1 | 0 | 0 |
| hdb-v1-gen-0034:short_feet:1 | failed | 0 | 0 | 0 | 0 | 0 | 0 |
| hdb-v1-gen-0037:pitch_sensor_bias:4 | failed | 1 | 0 | 0 | 1 | 2 | 1 |
| hdb-v1-gen-0011:feedback_gain_loss:1 | failed | 2 | 0 | 2 | 1 | 2 | 1 |
| hdb-v1-gen-0064:payload_offset:1 | failed | 1 | 3 | 3 | 2 | 2 | 1 |
| hdb-v1-gen-0039:heavy_torso:1 | failed | 0 | 3 | 2 | 3 | 3 | 3 |
| hdb-v1-gen-0004:low_ground_friction:1 | failed | 0 | 0 | 0 | 0 | 0 | 0 |
| hdb-v1-gen-0028:clock_fault:1 | failed | 3 | 3 | 2 | 1 | 3 | 3 |
| hdb-v1-gen-0062:pitch_sensor_bias:1 | failed | 0 | 1 | 0 | 0 | 0 | 2 |
| hdb-v1-gen-0044:feedback_gain_loss:1 | failed | 2 | 2 | 3 | 2 | 2 | 3 |
| hdb-v1-gen-0040:payload_offset:1 | control | 2 | 1 | 3 | 2 | 2 | 1 |
| hdb-v1-gen-0013:heavy_torso:1 | control | 3 | 3 | 3 | 2 | 3 | 3 |
| hdb-v1-gen-0052:clock_fault:1 | control | 3 | 3 | 3 | 3 | 3 | 3 |
| hdb-v1-gen-0036:short_feet:1 | control | 0 | 2 | 0 | 1 | 3 | 0 |
| hdb-v1-gen-0030:pitch_sensor_bias:4 | control | 0 | 3 | 2 | 2 | 3 | 1 |
| hdb-v1-gen-0054:feedback_gain_loss:1 | control | 3 | 2 | 3 | 2 | 1 | 3 |

The registered repeatable rescues were `0024:clock_fault:1` (JD=2, SD=0, QD=1) and `0062:pitch_sensor_bias:1` (JD=2, SD=1, QD=0). Three controls met the material-regression definition: `0040:payload_offset:1` (JD=1, best restricted=2), `0036:short_feet:1` (JD=0, best restricted=2), and `0030:pitch_sensor_bias:4` (JD=1, best restricted=3). Favorable failed-cohort changes were offset elsewhere, producing net gain zero under the conservative per-base maximum comparator. That comparator uses hindsight and is not a deployable policy.

Three cases had zero FULL in all 18 assigned units: `0004:low_ground_friction:1`, `0008:one_side_weakness:4`, and `0034:short_feet:1`. These are unresolved within this representation/optimizer/budget, not proven irreparable. Severity/family findings remain descriptive; no favorable subgroup claim is substituted for the failed gate.

## Engineering validation and amendments

The existing remote `/home/forge/dev/venvs/hdb/bin/python` was reused: Python 3.12.3, MuJoCo 3.15.0, NumPy 2.5.4 on Linux x86_64. No new VM, IAM, environment or dependency installation was required. The batch had 64 vCPU/256 GiB; eight deterministic shards each used six independent serial physics workers (48 total), with BLAS/OMP threads fixed at one.

The final pre-main real-VM regression run passed **84 tests, zero failures/errors/skips** (`test_r0`, `test_walk_opt`, `test_hidden_plant`, `test_recovery`, `test_hdb.Bench`, `test_hdb.Engine`), in 6.9 seconds. Six excluded engineering units were run serially and six pooled; every scientific field matched exactly except root wall time. Public-fixture DO-1 physics matched the existing hidden-plant job. The 6-versus-48 worker public probe also produced exactly equal physics; measured 48-worker throughput was 71.2429 rollouts/s. Earlier preparation passed 69 local tests and three command-fake supervisor tests; those fakes were not claimed as actual shutdown proof.

Three pre-main engineering amendments preserve their original registrations: (1) bind legacy cloud-start entry point to the existing SA, (2) use async lifecycle mutation and instance-state polling because the SA cannot read operation resources, and (3) add an engineering-only reporting cohort in memory to the frozen excluded smoke case, checking metadata before physics. No scientific case bytes, seeds, optimizer, verifier, budget, analysis or gate changed. Original and intermediate protocols remain committed.

The first excluded smoke finished solve/verification but failed record construction on missing cohort; no valid checkpoint or main unit existed. Its selected design/verifier outcome was not serialized and is unknown. Its logs are preserved in `engineering/invalid_v1.tgz` (SHA-256 `212a534187009f011b8bda80213d1de0e52bd7e162ca379ba6a18d9875abaa42`). Uniform recovery reran all six serial and pooled smoke conditions in a fresh v2 directory. The v2 smoke FULL results were excluded from main analysis and did not select methods. The first failed smoke consumed 2,000 policy rollouts and 48–96 unrecorded verification equivalents; exact verification cost is unavailable. This uncertainty is outside main data and covered by campaign wall-time/spend accounting.

## Runtime, budget and shutdown

Before main outcomes the measured launch gate passed: 2,326.161 summed serial smoke seconds, contention factor 1.53177, public-probe main upper forecast 3.9111 hours; including 25% margin and finalization yielded 5.0389 hours, within a six-hour main deadline and original ten-hour campaign bound. Six-hour main cost cap was $12.7014, within owner-verified $33.73 Cloud credit and $35 additional authorization. Smoke extrapolation alone was faster; the more conservative forecast governed launch.

Main began 2026-10-25 13:43:16 UTC and all shards, analysis and audit finished at 16:50:02 UTC (3.1128 hours). Supervisor exit code was zero; the existing root SA API-stop log records the request at 16:50:07 UTC. Shutdown was first independently observed through the control plane at 17:03:23 UTC. A 15-minute bounded restart retrieved artifacts and repeated analysis/audit without new rollouts; it was stopped immediately after retrieval. The existing VM-side five-minute timer and laptop watchdog were checked before launch; real API self-stop was proven before main, and both VMs were independently verified STOPPED after retrieval. Boot disks continue ordinary storage charges.

Main used **972,000 policy rollouts + 24,672 verification equivalents = 996,672 ten-second rollout equivalents**, with 190 confirmation-triggered units. Summed unit worker time was 129.7788 hours (parallel worker time, not billed VM hours). Selection errors=0, recorded refusals=0, verification seed errors=0; no worker exception files.

At 2026-10-25 17:10:46 UTC, both API states were STOPPED. Conservative ledger increased from $107.371 to $117.720: **$10.349 additional**, including engineering, main, retrieval and disk estimates; batch compute ledger increased from 40.718 to 45.595 hours (**4.877 hours**), with main compute unchanged. Campaign wall elapsed was 5.066 hours, below ten. Root auto-stop is charged conservatively until the first later API observation. These are local estimates, not provider invoice totals; final actual account balance is not exposed by the SA, and no final balance is fabricated. The estimate is safely within the authorized/verified-credit envelope.

## Reproducibility and evidence

Source commit `d29cdce6dbca4df9a410beed4ed8acaa47b0e1a5` on `codex/repair-strategy-r0`; protocol SHA-256 `b481dc8977d56a9878526cfafce259e05e4c55bd551f1983661040bb482139bb`. The original bb2ecb9 protocol SHA-256 is `e9c0a0b1a9f24e173129de569c77c7795ee72a1b5c794efcf39e066dd66ffa26`. DO-1 SHA-256 remains `7391890cb9491b73000a1b034e78399d0f6d93b789ca043728b5f2132ed669af`.

Canonical main archive: `r0_run_20261025_1792947002738841029.tgz`, **16,568,688 bytes**, SHA-256 **`6dcda839b60a401831a46efd760b2702e65e42fda65e8391e87d7018e8520806`**. Preserved both on the stopped batch disk at `/home/forge/dev/r0-codex/artifacts/` and locally in ignored `artifacts/r0_ops/`. The full raw archive is intentionally not added to Git. It retains all 324 immutable records, submitted designs, optimizer histories/scores, budgets, seeds, per-seed validation/confirmation, provenance and shard logs. No generated physics evidence is invented or replaced.

All **337 manifest entries** verified locally against exact bytes and archive SHA matched the VM receipt. The frozen analysis was rerun in the original VM environment and exactly matched the registered output. Native post-run and local audits matched for all 324 records, provenance and hashes. The 27 engineering manifest entries also verified. `results/` commits the small analysis, unit CSV/hash index, execution provenance, manifests, audits, gate, regression/equivalence/timing and shutdown receipts. `results/EVIDENCE_SHA256SUMS` protects every committed result artifact; `operations_archive_receipt.json` identifies a separate local curated operations/smoke archive. This is local/persistent-disk preservation, not a claim of independent remote object-store backup.

Reproduce validation (no physics) from this branch after extracting the archive into ignored artifacts:

```powershell
python scripts/r0_integrity.py audit --root artifacts/r0_ops/r0_run_20261025 --study experiments/causal_engineer/dev/repair_strategy_r0
```

The original Linux analysis command was:

```bash
/home/forge/dev/venvs/hdb/bin/python -B scripts/r0_experiment.py analyze --study experiments/causal_engineer/dev/repair_strategy_r0 --out artifacts/r0_run_20261025
```

Use Linux for byte-identical analysis reuse: record-hash path spelling follows the host separator, while the scientific statistics are portable. Do not overwrite original immutable outputs with Windows-derived formatting. The dedicated SHA manifest/audit normalizes paths without changing record bytes.

## Limitations and next scientific step

This small, selected development cohort cannot establish population-wide superiority, transfer to new bodies/mechanisms, real-world repair or a Nemotron contribution. Three technical optimizer replicates only weakly characterize optimization variability. Fixed portfolio allocation can miss useful coordinated solutions; simultaneous larger spaces receive fewer evaluations per dimension. Success on some bases also occurs in restricted arms, so historical failure is not evidence of a uniquely joint capability. Control regressions and mixed objective effects oppose a generic optimizer-improvement claim. No inference tokens were purchased or used for the study.

The next scientific question is whether search allocation/initialization and train/selection-versus-verification objective mismatch explain the two rescues and three regressions, and whether the unresolved bases require a different legitimate repair representation. The preserved candidate scores and per-seed validation traces provide evidence for a separately authorized development investigation; optimization failure alone cannot distinguish representation failure from search failure. Any changed optimizer, objective, budget, action library or gate requires a new prospectively frozen study and fresh evaluation boundaries. **Do not advance to R1 or open sealed data without separate owner authorization.** Claude's release/PR #20/E-2R work and the inherited global manifest remain untouched.
