# Held-out fault benchmark: build specification (fixed 2026-10-17, before the build)

This file is committed before any held-out instance is built. It defines the benchmark only. The evaluation protocol (arms,
hypotheses, analysis) is registered separately, after development and before any policy runs on these instances.

- **Bases:** `fault_bench.load_bases("heldout")`, i.e. the 28 verified 17-D walkers of the S3 confirmatory study across 15
  morphology regions. No held-out base was used in development, in the probe dataset, in memory or in Level C training.
- **Faults and severities:** all 8 faults of `fault_bench.FAULTS` × severity {0.5, 1.0} = 448 candidates.
- **Campaign:** `ce-heldout-v1`. Seeds come from `fault_bench.instance_seeds` (per-role blocks; verification seeds disjoint from
  check/train/obs seeds).
- **Build:**
  - command: `scripts/fault_bench_build.py --split heldout --campaign ce-heldout-v1 --severities 0.5 1.0 --screen-first`;
  - repair budget B = 160, n_train 4, n_check 8;
  - same keep rule as dev: faulty robot walks on ≤ 2/8 check seeds; matching tool restores walking on ≥ 6/8.
- **Screen-first:** the matching tool runs first and the other tools only if it repairs. Kept instances therefore have complete
  repair matrices, identical to a full build.
- **Records:** results are written append-only to `artifacts/ce/heldout_shard*.jsonl` on the VM, then copied with a SHA-256
  manifest into this directory when the evaluation is registered.
- **Who looks at what:** during development nobody inspects held-out instances beyond counts (kept per fault). No policy, prompt
  or memory setting is tuned on them.
