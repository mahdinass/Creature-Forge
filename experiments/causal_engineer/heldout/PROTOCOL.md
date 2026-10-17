# Causal engineer: registered held-out evaluation (ce-heldout-eval-v1)

**Status: REGISTERED (2026-10-17).** Binding together with `protocol.json` (code commit, input hashes, instance list), frozen in
`experiments/FROZEN_MANIFEST.json` before any policy ran on a held-out instance. One run, one analysis, no
reruns. Interrupted episodes are recorded as ERROR and counted as not recovered.

## Instances
- **Pool:** the kept instances of the held-out benchmark (`BUILD_SPEC.md`: 28 S3 bases never used in development, 8 faults,
  severity 0.5 / 1.0).
- **Sample:** N = 40.
  - Order the pool by SHA-256(`"ce-heldout-eval-v1:" + instance_id`), then take instances in that order, at most 6 per fault and
    3 per base robot, until 40 are taken.
  - If fewer than 40 qualify, the cap per base rises to 4, then 5; if the pool is still short, all kept instances are used.
  - The rule is applied by `scripts/ce_heldout_select.py` and the resulting list is committed in `protocol.json`.

## Arms
All arms use the same `eng_tools` workbench, total budget 700 rollouts, n_train 4, n_obs 4, the same instruments and the same
independent verification (`fault_bench.verify`, full_recovery_v1, hidden validate and confirm seeds).

| arm | what decides | experience |
|---|---|---|
| `scientist_think` | Nemotron, closed loop (experiments with registered predictions, revisions, repairs) | none |
| `scientist_1shot_think` | Nemotron, one call from the initial observation, no feedback | none |
| `scientist_think_mem` | as `scientist_think` | Level A/B memory from TRAINING robots only |
| `scientist_think_mem_learned` | as `scientist_think_mem` | plus Level C advice (observation-only model) |
| `exhaustive` | fixed procedure: every catalogue counterfactual, fixed ranking table, top-2 repairs | none |
| `learned` | the `exhaustive` procedure with the trained Level C ranking (observation + counterfactual responses) | Level C |
| `expert` | hand-written telemetry rules, top-2 repairs | none |
| `random` | two random counterfactuals, two random tools | none |

- **Model:** `nvidia/nemotron-3-super-120b-a12b` with thinking enabled (`chat_template_kwargs.enable_thinking = true`),
  max_tokens 32,000, timeout 600 s, temperature 0.6.
- **Scientist:** `causal_scientist_v2`, revision v2.3 (includes the 20 s stress-test instrument), MAX_STEPS 12, MAX_REQUESTS 24,
  one repair call per invalid reply as implemented (`REPAIR_CALLS_PER_STEP`).
- **Memory bank:** the dev probe dataset (165 instances, 12 dev bases) plus dev investigation episodes (pilot1–5, git-ignored
  files pinned by SHA-256 in `protocol.json`). No held-out robot is in any bank.
- **Level C model:** `experiments/causal_engineer/dev/level_c_logistic.json`, trained on the 165 dev instances. Its SHA-256 is
  pinned in `protocol.json`.

## Hypotheses (primary outcome: FULL_RECOVERY per instance)
One-sided exact McNemar tests on paired instances. Holm–Bonferroni across the six tests of the family, at α = 0.05.

| id | capability | test |
|---|---|---|
| C1 | causal investigation | `scientist_think` prediction accuracy > the per-episode majority-direction baseline (exact sign test over episodes with ≥ 5 scored predictions). *This test uses accuracy, not recovery.* |
| C2 | closed-loop adaptation | `scientist_think` > `scientist_1shot_think` |
| C3 | repair orchestration | `scientist_think` > `exhaustive` |
| C4 | knowledge transfer | `scientist_think_mem` > `scientist_think` |
| C5a | trainable learning (non-AI) | `learned` > `exhaustive` |
| C5b | trainable learning (AI) | `scientist_think_mem_learned` > `scientist_think_mem` |

## Secondary and descriptive measures (no claims beyond the stated tests)
- PARTIAL / NOT counts; mean validation walking fraction (paired Wilcoxon signed-rank, two-sided).
- **Decision quality** from the held-out repair matrices, never shown to any policy: share of episodes whose repairs include a
  tool that repairs the instance; first repair repairs.
- **Diagnosis:**
  - injected-label match;
  - repair-consistent match (the diagnosed mechanism maps to a repairing tool);
  - stratified into *specific* (≤ 2 repairing tools) and *over-determined* (≥ 3) instances.
- **Investigation process:** registered predictions, accuracy against the majority baseline, status updates, refutations, new
  hypotheses after step 1, experiments per episode, rollouts used.
- **Memory:**
  - assessment verdicts per item kind;
  - negative transfer: episodes where a memory item was assessed `applies`, its best tool was repaired first, that repair did
    not repair the instance, and another tool would have;
  - the opposite case (memory followed and correct).
- **Level C advice:** whether the advised top-1 tool repairs; how often the scientist follows it.
- Inference cost, tokens, latency and wall time per arm.
- Per-fault tables.

## Execution
- **Where:** the main VM. Results are appended to `artifacts/ce/heldout_eval_shard*.jsonl`, then copied with SHA-256 into
  `experiments/causal_engineer/heldout/results/`.
- **Inference:** inside the $30 ledger cap.
- **Interruptions:** an interrupted shard is resumed with `--resume` (append-only; completed episodes are never rerun). If the
  cap stops the run, the missing episodes are reported as missing, not imputed.

## Analysis
Run `scripts/ce_heldout_analysis.py` once on the complete result files. The report states every test result, including null
results, and the limitations: N = 40 detects only large differences; the bases are S3 creatures and the faults are synthetic
injections.
