---
name: physics-integrity
description: Use before writing or reviewing any Creature Forge code that runs MuJoCo experiments, compares designs, calls Nemotron, records results or words a verdict (challenges, arena, verdict, investigator, scoreboard, UI result text). Enforces frozen records, matched conditions, seed namespaces, reject-not-clip, provenance and honest wording.
---

# Physics integrity (Creature Forge)

MuJoCo decides; the model proposes; deterministic code judges. Check every item before claiming work is done.

## Frozen evidence
- Never edit `experiments/**` except `experiments/forge_loop/**`. `tests/test_frozen_records.py` must pass.
- Never change defaults, criteria, prompts or protocol builders of the pinned modules listed in
  `docs/FORGE_LOOP_CONTRACTS.md` §0. Add new modules instead.
- R2's 150/150 vs 91/150 is classical optimisation. The recorded Nemotron demo did not beat matched random edits.
  R3 produced no statistical result. Never reword these.

## Matched conditions
- Every compared arm uses the same challenge spec, seeds, controller policy, retune budget and noise seed.
  If one arm gets controller adaptation, all arms of that category get the identical budget. Record it.
- Seeds come from `seed_block` (≥ 100000), roles disjoint (challenge/train/screen/validate/probe). Validation seeds are
  used once and never for selection.
- Screening selects; only validation decides (`verdict_v1`). Model confidence never enters a verdict.

## Model output is untrusted
- Parse → schema → whitelist → bounds → citations resolve to scalars. Reject with a named reason; **never clip**.
- Store full prompt, raw response, request id, usage, latency, cost, settings. Never store or print the API key.
- No blind retries. One repair call only for an unparseable/schema-invalid reply, counted in budgets.
- SCRIPTED_MOCK replies are labelled everywhere and never counted as LIVE.

## Honest results
- Per-seed scores + paired test + minimum effect. One animation is not evidence.
- Report NOT_VERIFIED / WORSE / INCONCLUSIVE and model failures plainly; keep negative results.
- Say "hypothesis" for causal claims; "supported/contradicted by" for tests. No "AI beat random" without the
  pre-declared aggregate test.
- Distinguish ERROR (could not run) from FAIL (ran and failed) from POOR (ran, weak).
