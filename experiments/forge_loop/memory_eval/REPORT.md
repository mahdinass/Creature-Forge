# forge-memory-eval-v1 — does engineering memory help? Report

**Result: no evidence of a benefit.** Under the pre-registered test, the AI's selected redesign was verified in 6/12
investigations with memory and 7/12 without (discordant pairs 3 vs 4, exact one-sided McNemar p = 0.773). The model never
cited a memory lesson in any of the 12 memory-on investigations. Engineering memory therefore stays an experimental,
off-by-default feature, and no benefit is claimed for it anywhere.

## Protocol (registered before any run; unchanged)
- `protocol.json` (registered 2026-10-15T18:35:27Z) and the frozen 34-lesson `bank.jsonl` (sha256_lf in the protocol) were
  committed before the first run and are unchanged. The evaluation server ran without `CF_MEMORY`, so no lesson was added
  during the run.
- 6 new creatures (short-legs, long-legs, big-torso, small-feet, heavy-legs, soft-motors) x 2 replicates = 12 pairs. Per
  pair: one fresh push challenge run and two LIVE investigations on it (memory on, memory off), identical arena seeds within
  the pair; memory-first on replicate 1, no-memory-first on replicate 2. Investigation profile `default`, probes on, no loop,
  memory k = 3. Model: `nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory (production configuration).
- Primary outcome: the arena's selected AI arm has verdict `VERIFIED_IMPROVEMENT` (rule `verdict_v1`; a run with no AI arm
  counts as not verified). Primary analysis: exact one-sided McNemar on discordant pairs, alpha 0.05. Power note (stated
  before running): 12 pairs give low power; a null result was the expected outcome unless the effect is large.

## Conduct (including the interruption)
- Run 1: started 18:36 UTC on 2026-10-15; stopped by the operator at a clean pair boundary after 5 complete pairs (owner
  disconnecting). The driver had already created the creature for pair 6 (`mem-soft-motors-1`, `c-2fd9f160`) but no
  investigation existed on it, so nothing was interrupted and nothing is excluded.
- Run 2 (`--resume`): 2026-10-15 21:49-22:29 UTC, in a remote `tmux` session on the VM. It skipped the 5 recorded pairs and
  ran the remaining 7 on fresh creatures. **No pair was rerun; no interim analysis was looked at** (the analysis below was run
  once, after all 12 pairs were recorded).
- Code identity: records carry the slot snapshot commit — 10 records `50f24a7` (run 1), 14 records `6314247` (run 2). The two
  snapshots have **no difference** under `creature_forge/`, `studio/src/`, `protocol.json` or `bank.jsonl`; only the driver
  script's `--resume` bookkeeping changed between them.
- Every investigation finished with status `done`; 0 exclusions; 0 errors. `runs.jsonl` is append-only (its first 5 lines
  are byte-identical to the copy committed at the pause). All 24 records are archived unedited in `results/records/` with
  SHA-256 in `results/records/MANIFEST.json`; the 10 committed at the pause matched the VM copies by hash.
- Caps respected: 49 model requests of 72; $0.109 of $1.00; wall time ~71 min of 2.5 h.

## Primary result
| | memory verified | memory not verified |
|---|---|---|
| **no-memory verified** | 3 (both) | 4 (no-memory only) |
| **no-memory not verified** | 3 (memory only) | 2 (neither) |

Exact one-sided McNemar (H1: memory-only > no-memory-only) on 3 vs 4 discordant pairs: **p = 0.773**. Pre-declared
conclusion: **"no evidence of a benefit from engineering memory."** (`results/summary.json`, produced by
`python scripts/forge_memory_eval.py --analyze --records experiments/forge_loop/memory_eval/results/records`.)

## Secondary (descriptive, pre-declared list; no test)
- AI verified rate: memory 6/12 (Wilson 95% CI 0.25-0.75); no memory 7/12 (0.32-0.81).
- Paired median of the per-pair difference in the AI arm's median critical-force gain (memory minus no memory): -0.16 N.
- **Memory cited in hypotheses: 0 of 12** memory-on investigations. This was not a delivery or schema problem: every
  memory-on prompt carried the 3 retrieved lessons (about 140 `memory[i].*` evidence lines) and the system note asking the
  model to cite `memory.*` paths when relevant, and the reply schema's citation enum included 56-70 memory paths (checked by
  rebuilding the schema from the stored evidence with `forge_ai.build_reply_schema`). No memory reached any memory-off arm.
  The model simply did not ground any hypothesis in a past case.
- Matched-random twins: 0 of 24 verified (memory-on runs: 9 INCONCLUSIVE, 3 NOT_VERIFIED; memory-off runs: 7 INCONCLUSIVE,
  3 WORSE, 2 NOT_VERIFIED).
- Cost (both arms, all 24 investigations): 49 calls, 323,902 tokens, $0.109, 31,274 MuJoCo rollouts.

## Per pair
AI arm verdict and median gain on the held-out seeds (N, critical push force).

| creature | rep | memory | gain | no memory | gain |
|---|---|---|---|---|---|
| short-legs | 1 | VERIFIED | +3.13 | NOT_VERIFIED | +2.50 |
| long-legs | 1 | NOT_VERIFIED | +2.81 | NOT_VERIFIED | +1.88 |
| big-torso | 1 | VERIFIED | +5.00 | VERIFIED | +5.31 |
| small-feet | 1 | NOT_VERIFIED | +2.19 | VERIFIED | +4.38 |
| heavy-legs | 1 | VERIFIED | +9.69 | NOT_VERIFIED | +1.25 |
| soft-motors | 1 | VERIFIED | +3.44 | VERIFIED | +3.44 |
| short-legs | 2 | NOT_VERIFIED | +2.50 | INCONCLUSIVE | 0.00 |
| long-legs | 2 | NOT_VERIFIED | 0.00 | VERIFIED | +6.25 |
| big-torso | 2 | WORSE | -12.81 | VERIFIED | +10.94 |
| small-feet | 2 | NOT_VERIFIED | +1.88 | VERIFIED | +5.00 |
| heavy-legs | 2 | VERIFIED | +10.00 | NOT_VERIFIED | +1.25 |
| soft-motors | 2 | VERIFIED | +3.75 | VERIFIED | +4.38 |

## Interpretation and limits
- The pre-registered test finds no benefit, and the point estimate slightly favours no memory. With 12 pairs this cannot
  rule out a small benefit or a small harm; a large benefit would most likely have shown many more memory-only than
  no-memory-only pairs, and the observed 3 vs 4 does not.
- Because the model never cited a lesson, the evaluation cannot tell whether well-used memory would help; it shows that
  memory offered as optional extra evidence was ignored by this model and prompt. Any further memory work would need a
  different design (for example, retrieved past edits offered as candidate proposals for the arena) and a new registration.
- Limits: one model, one challenge (push), six synthetic creatures, a 34-lesson bank built from earlier records of other
  creatures, and run-to-run model variability (earlier development runs showed different proposals for the same
  evidence; `dev_live_records/README.md`), which adds noise to every pair.
- Not a contradiction of the scoreboard (6/12 AI vs 1/12 twin); that result concerned AI vs matched random edits on a
  different creature set. Here the twins were again never verified (0/24), consistent with it, but this evaluation was not
  designed to test that comparison.
