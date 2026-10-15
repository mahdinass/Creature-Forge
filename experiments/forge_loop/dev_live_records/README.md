# Forge Loop — development live records (2026-10-15)

The first nine **real** Nemotron investigations of user-drawn creatures, run on the Nebius VM through the Studio API
(`scripts/forge_acceptance.py`, `scripts/forge_run_loop.py`). Kept unedited for provenance (raw prompts, raw responses, request
ids, usage, arms, seeds, per-seed results, verdicts). `INDEX.json` lists each record with its SHA-256.

**These are development runs, not an experiment.** The pipeline was improved between runs, so they must not be pooled into any
statistic. Model: `nvidia/nemotron-3-super-120b-a12b`, thinking off, strict JSON schema (calibration v2). Every run: 1–2 model
calls, ≈ $0.002 each.

| records | protocol at the time |
|---|---|
| i-d62a72f585fb (tiny-feet, stand), i-6a16174a72ae (balanced, push) | first live runs; push measured at 2.5 N steps; no foot geometry in the evidence |
| i-8cd662cb2a51, i-9d734f7a54a5 (loop) | + heel/toe-vs-ankle geometry in the evidence; loop patience 2 |
| i-7dbe0c20b190, i-8b8dfc87d27d (loop) | + push measured at 0.625 N (7 bisection steps) for every arm |
| i-eb2d953f2c8e, i-f9873480e42a, i-50af182da352 (loop) | + the prompt states the deterministic acceptance rule |

Findings (one creature, one challenge, n = 1 per protocol state — anecdotal):
- The model's hypotheses were physically plausible but inconsistent across runs (torque, friction, heel geometry).
- First **VERIFIED_IMPROVEMENT** of a drawn creature: `i-f9873480e42a`, round 2 of a loop, after round 1's friction proposal was
  falsified (0 wins / 8 losses). Hypothesis: "heel is too close to ankle, reducing backward base of support"; edit: rear
  `foot_length ×1.25`; median +3.125 N critical push force, 12 wins / 0 losses / 0 ties on 12 held-out seeds (p = 0.00024).
- In that record the validated baseline was `random:P2` (NOT_VERIFIED), **not** the AI arm's own twin `random:P1`. The arena
  now always validates the selected AI arm's own matched-random twin (commit after these runs), because the A/A null pilot
  showed ~15 % of random push edits verify. No claim of AI superiority is made from these records.
- Round 3 evaluated the proposed (not accepted) body as a hypothetical parent; nothing was accepted automatically.
