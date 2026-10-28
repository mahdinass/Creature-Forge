# DO-1 replication (W3) and cross-family pilot (W4): results

- **Run:** 2026-10-21 on the main Nebius VM. W3 ran 17:50–18:56 UTC and W4 ran 18:56–19:15 UTC.
- **Code:** pre-registered commit `3b8a8b1e12bccddb2573a21c2717d3c36ae15dd5`, pushed before execution. The protocol is
  `docs/DO1_REPLICATION_PROTOCOL.md`.
- **Evidence:** `experiments/do1/w3w4_2026-10-21/`. It contains the raw JSONL, the manifests, the logs, the VM and local
  SHA-256 lists, and the analysis and audit outputs.
- **Attribution:** DO-1 is a deterministic objective change. It is NO_AI: no language model was called, and nothing here
  is attributable to Nemotron.
- **Review:** these results await independent review. Until then, the Studio demonstration and the submission wording
  are unchanged.

## 1. Summary
- **W3 (L4, 5 fresh paired replicates):**
  - DO-1 reached FULL_RECOVERY in **5 of 5** replicates; the frozen objective reached it in **0 of 5** (PARTIAL_IMPROVEMENT
    19/24 every time).
  - Exact one-sided McNemar on the discordant pairs: 5 for DO-1, 0 against, p = 0.031. This meets the pre-registered
    criterion. It is an instance-specific finding about how reliably DO-1 repairs this one robot under different optimizer
    randomness, at this budget and on these validation seeds. It is not a rate over robots.
- **W4 (two other fault families, one paired episode each, exploratory):**
  - **C1** (`feedback_gain_loss:2`): DO-1 FULL_RECOVERY 20/24 vs frozen PARTIAL 19/24.
  - **B1** (`payload_offset:5`): both PARTIAL_IMPROVEMENT. DO-1 raised validation walking from 17/24 to 20/24 (aggregate
    PASS), but its 20 s confirmation **failed** (62 % walking vs ≥ 80 % required). For B1: "No verified recovery was found
    under the tested intervention, optimizer configuration and computational budget."
  - Two examples cannot establish transfer. DO-1 helped on one family, and on the other improved the validation gate but
    not the confirmation gate.
- **Validity:** every gate passed and nothing was excluded. There were no infrastructure errors and no NOT_EXPOSED
  episodes. Cost: +$0.41 on the infrastructure ledger.

## 2. W3: `DO1-L4-rep` (L4 = `hdb-v1-gen-0137:low_ground_friction:0`)
**Sentinel (frozen r0, reproduction check only, not analysed).** It reproduced the stored A1e6 record exactly (21/21
checks). The submitted design was d4 `66053dae8e`, PARTIAL 19/24 with a median of +1.082 m: identical to the DO1-L4-r0 pilot
and to DS-1.

| r | Noise seed | Frozen: status, walking, median paired displacement | DO-1: status, walking, median, confirmation | Δ walking |
|---|---|---|---|---|
| 1 | 1751419204 | PARTIAL 19/24, VERIFIED +1.081 m | **FULL** 21/24, VERIFIED +0.775 m, passed | +2 |
| 2 | 1751429211 | PARTIAL 19/24, VERIFIED +1.084 m | **FULL** 21/24, VERIFIED +0.814 m, passed | +2 |
| 3 | 1751439218 | PARTIAL 19/24, VERIFIED +1.084 m | **FULL** 20/24, VERIFIED +0.875 m, passed | +1 |
| 4 | 1751449225 | PARTIAL 19/24, VERIFIED +1.085 m | **FULL** 21/24, VERIFIED +0.717 m, passed | +2 |
| 5 | 1751459232 | PARTIAL 19/24, VERIFIED +1.054 m | **FULL** 21/24, VERIFIED +0.728 m, passed | +2 |

**Primary (ITT, 5 pairs).**

| Arm | FULL | Exact 95 % CI |
|---|---|---|
| Frozen | 0/5 | Clopper–Pearson [0.000, 0.522] |
| DO-1 | 5/5 | Clopper–Pearson [0.478, 1.000] |

- Discordant pairs: 5 for DO-1, 0 against. Exact one-sided McNemar p = 0.03125.
- Per protocol: identical, because no pair was excluded and every DO-1 episode was exposed.

**Secondary.**
- **Walking difference:** +2, +2, +1, +2, +2 per 24 seeds. Sign test 5+/0−, one-sided p = 0.031, median +2.
- **Every frozen failure has the same single reason:** the walking aggregate is POOR (19/24 < 20/24). Its displacement is
  always VERIFIED_IMPROVEMENT.
- **DO-1 trade-off:** DO-1 gave up median displacement (+0.72 to +0.88 m, vs +1.05 to +1.09 m frozen) for walking
  robustness. It stayed VERIFIED in every replicate, and all five 20 s confirmations passed. This is the same direction as
  the r0 pilot.
- **Resources per episode:**
  - plant: frozen 692 or 700, DO-1 428;
  - twin: frozen 2,514, DO-1 2,418.
  - DO-1's stop map accepted after its first repair every time, while the frozen stop map never accepted.
  - Total W3: 34,354 of 39,644 rollout-equivalents.
- **Optimizer behaviour:**
  - All 11 submitted designs differ. The frozen arm submitted d5 (posture repair) in r1, r3 and r5, and d4 in r2 and r4.
  - Each DO-1 repair evaluated 91 candidates. Its selected candidate was #63, #69, #87, #52 and #75 in r1–r5: never the last
    one (in the r0 pilot it was #90, the last).
  - Selected train-seed margins were 0.24–0.28, and the binding gates were speed and touchdown.

**Comparison with the DO1-L4-r0 pilot.** Exploratory reference only; not pooled.
- Pilot: frozen PARTIAL 19/24, +1.082 m; DO-1 FULL 21/24, +0.710 m.
- The five fresh replicates repeat this pattern: DO-1 20–21/24 with +0.72 to +0.88 m, frozen 19/24 with about +1.08 m.

## 3. W4: `DO1-X` (exploratory, descriptive only)
Both frozen r0 episodes reproduced their stored A1e6 records exactly (21/21). Both DO-1 episodes matched the stored
pre-hook prefix, with equal pair fingerprints, and both were exposed.

| Case | Frozen | DO-1 | Gates that changed |
|---|---|---|---|
| B1 `hdb-v1-gen-0142:payload_offset:5` (body/mass) | PARTIAL 17/24 (POOR), VERIFIED +2.764 m; plant 692 | PARTIAL 20/24 (PASS), VERIFIED +2.541 m; confirmation **failed**: walking on 62 % of seeds at 20 s (needs ≥ 80 %); plant 696 | validation walking aggregate POOR → PASS; confirmation not run → failed |
| C1 `hdb-v1-gen-0070:feedback_gain_loss:2` (controller) | PARTIAL 19/24 (POOR), VERIFIED +2.171 m; plant 457, stop map accepted | **FULL** 20/24 (PASS), VERIFIED +2.189 m, confirmation passed; plant 445, stop map accepted | walking aggregate POOR → PASS; confirmation passed |

Total W4: 12,538 of 14,416 rollout-equivalents.

**Reading.**
- On C1, DO-1's change of the objective turned a walking-gate failure into a verified full recovery.
- On B1, the same change cleared the 24-seed validation gate but not the independent 20 s confirmation.
- Both DO-1 FULL or PASS outcomes sit at the 20/24 threshold.
- The cases were selected for the baseline's partial failure, so regression to the mean is possible. These are single
  episodes on single instances, with no test and no family-level claim.

## 4. Audit (no physics; `audit_output.txt`)
- **Provenance:** both manifests record `git_commit` = the approved `3b8a8b1`, `git_dirty` false, runner
  `do1_ablation_v2`, objective `do1_objective_v2`, Python 3.12.3, numpy 2.5.4, MuJoCo 3.15.0. The VM checkout log shows a
  clean HEAD.
- **Inputs:** the preflight hash-checked every input against the frozen references. That covers v6 settings, stop map,
  split, eval instances, thresholds, walkers, and the stored records s3 and s5. The preflight result was ok for both
  phases.
- **Gates, all passed:**
  - 3/3 reproductions exact;
  - 12/12 stored-prefix matches (W3 r ≥ 1 in both arms, and both W4 DO-1 episodes);
  - 7/7 equal pair fingerprints;
  - 15/15 single hook calls;
  - 15/15 complete verification records;
  - every DO-1 episode exposed (one 4-rollout train baseline and a completed repair), with selected = logged = registered
    design.
- **Pre-hook fingerprints differ between replicates.** They include the bench noise seed, while the stored-prefix content
  matched. That is the expected pattern.
- **Seeds:** all 11 W3 episodes used the same 24 validation seeds, and confirmations ran on 24 seeds.
- **Integrity:** the files' SHA-256 equal the VM's (`vm_sha256.txt`); the archive is
  `42f2ca0f2c513ac3721b73180ee573081a1e0203778be32c7c6fb76ac5a500f1`. The raw JSONL SHA-256 are:
  - `do1_l4_rep.jsonl` `4f9c7295bd771cf26c8dab2a8a1db433ed2f2460dd6e1b3a3340d90571114714`;
  - `do1_x.jsonl` `f484ac6b19ce0f54c8071e4566b42770920734e6553f21c691fb9e936899bc9d`.
- **Complete accounting:** 15 of 15 assigned episodes ran and none was dropped. There were no infrastructure errors and no
  NOT_EXPOSED episodes.

## 5. Limitations
- **W3 is replication on ONE development instance.**
  - The five pairs are technical replicates of plant-CMA randomness. Everything else is fixed: the robot, the fault, the
    physical seeds and the 24 already-studied validation seeds.
  - The p-value speaks only to optimizer randomness. It says nothing about unseen robots, fault families or validation
    conditions.
- **The margins are thin.**
  - DO-1's FULL outcomes are 20–21/24 against a threshold of 20, and the frozen arm sits at 19.
  - The effect is one or two more walking seeds out of 24, which is decisive here only because it crosses the
    pre-declared gate.
- **Trade-off:** DO-1 consistently gives up 0.21–0.37 m of median displacement per replicate, while staying verified.
- **W4 is two examples.** One recovered; one improved validation but failed confirmation. This is not a transfer or
  benchmark result.
- **Platform:** exact replay requires the Linux VM environment. Windows does not reproduce these rows bitwise (W1a
  finding).
- **Review:** the results are not yet independently reviewed.

## 6. Cost and compute
| Item | Value |
|---|---|
| Infra ledger | $88.999 before start → $89.405 after the API stop: **+$0.406** (main VM 1.48 h; ceiling $1.50) |
| VMs | Both STOPPED via the control plane at 19:17 UTC (main `computeinstance-e01g6rhpgcpnf1bfbr`, batch `computeinstance-e01efb17k9jbzct0m0`) |
| Inference | None (NO_AI) |
| W3 | 11 episodes, 34,354 rollout-equivalents (cap 39,644), 66 min |
| W4 | 4 episodes, 12,538 rollout-equivalents (cap 14,416), 19 min |

## 7. Reproduction
- **Re-analysis (no physics, any OS):**
  `python scripts/do1_replication_analysis.py --w3 experiments/do1/w3w4_2026-10-21/do1_l4_rep.jsonl --w4 experiments/do1/w3w4_2026-10-21/do1_x.jsonl`
  It must equal `analysis_output.txt`.
- **Re-execution (Linux, Python 3.12.3, numpy 2.5.4, MuJoCo 3.15.0):**
  1. Check out `3b8a8b1` clean. Later commits on this branch add `experiments/` files, and the preflight correctly refuses
     them.
  2. Provide the DS-1 artifacts (thresholds and walkers) and the stored records `eval_A1e6_s3.jsonl` and `_s5.jsonl`, with
     the hashes in `ta1_tool_access.REFERENCE`.
  3. Run `bash scripts/run_do1_w3w4.sh 3b8a8b1e12bccddb2573a21c2717d3c36ae15dd5 <out dir>`.

  Every episode is deterministic given its seeds, and the sentinel checks the environment first.
