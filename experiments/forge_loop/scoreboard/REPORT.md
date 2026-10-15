# Forge Loop scoreboard v1 — report (2026-10-15)

**Question (pre-registered):** do Nemotron-selected redesigns of drawn creatures pass the verification rule more often than
size-matched random edits?

**Protocol:** `protocol.json`, committed in `e12dd0e` **before any run**. 12 investigations = 6 starter/challenge cells × 2
replicates; each a fresh creature drawn from a Studio starter, a fresh 8-seed challenge run, one live investigation
(Nemotron-3-Super-120B on Nebius Token Factory, `model_config.json` default profile, diagnostic probes on, single round).
The arena validates the selected AI arm and its **own matched-random twin** on the same 12–16 held-out seeds; `verdict_v1`
decides. No reruns. Raw run log `results/runs.jsonl`; unedited investigation records `results/records/` (SHA-256 in
`MANIFEST.json`); analysis `results/summary.json` (`python scripts/forge_scoreboard.py --analyze`).

All 12 investigations completed with status `done`; none excluded. (The client SSH session reset after the last run; all
12 runs and records had already been written on the VM.)

## Primary analysis (as registered)

|                     | twin VERIFIED | twin not verified |
|---------------------|:-------------:|:-----------------:|
| **AI VERIFIED**     | 1             | **5**             |
| **AI not verified** | **0**         | 6                 |

Exact one-sided McNemar on discordant pairs (5 vs 0): **p = 0.031** (the smallest p attainable with 5 discordant pairs).
Registered conclusion: **AI-selected edits verified more often than matched random edits on this zoo.**

## Secondary (registered)

| outcome | result | Wilson 95 % CI |
|---|---|---|
| AI arm verified, per attempted investigation | 6 / 12 | 0.25 – 0.75 |
| matched twin verified | 1 / 12 | 0.01 – 0.35 |
| heuristic verified | 0 / 12 (no applicable rule in 4) | 0.00 – 0.24 |
| probe expectations confirmed | 8 of 28 evaluated | — |
| cost | 24 model calls, 146,901 tokens, **$0.050**, 8,870 MuJoCo rollouts, 21.5 min | — |

Per investigation (median paired difference vs the original on held-out seeds; push in N, stand in s):

| starter | challenge | rep | AI verdict (median diff) | twin verdict (median diff) |
|---|---|---|---|---|
| balanced | push | 1 | VERIFIED (+3.13) | NOT_VERIFIED (−1.88) |
| bird-knees | push | 1 | VERIFIED (+3.75) | INCONCLUSIVE (0.0) |
| weak-slippery | push | 1 | VERIFIED (+3.44) | NOT_VERIFIED (−1.88) |
| tiny-feet | stand | 1 | NOT_VERIFIED (+0.37) | INCONCLUSIVE (−0.03) |
| top-heavy | stand | 1 | NOT_VERIFIED (+0.10) | NOT_VERIFIED (−0.09) |
| stilts | stand | 1 | NOT_VERIFIED (+0.25) | INCONCLUSIVE (+0.02) |
| balanced | push | 2 | VERIFIED (+4.38) | INCONCLUSIVE (−0.63) |
| bird-knees | push | 2 | INCONCLUSIVE (−0.31) | WORSE (−11.88) |
| weak-slippery | push | 2 | VERIFIED (+4.38) | NOT_VERIFIED (+2.5) |
| tiny-feet | stand | 2 | NOT_VERIFIED (+0.11) | NOT_VERIFIED (−0.05) |
| top-heavy | stand | 2 | NOT_VERIFIED (+0.18) | NOT_VERIFIED (+0.13) |
| stilts | stand | 2 | VERIFIED (+0.71) | VERIFIED (+3.17) |

## Post-hoc check (NOT pre-registered; reported for transparency)

Screening picks the best of up to 3 AI proposals, while the registered comparator is the single twin of the selected
proposal, so the AI arm could enjoy a selection advantage. Six of the twelve investigations had only one AI proposal. The
arena also validated the **best baseline** (best of all random twins + heuristic by the same screening rule): it verified
in 1 / 12, and the discordant pattern against the AI arm is again 5 vs 0.

## Interpretation and limits

- The effect is concentrated in the **push** challenge (5 of 6 AI verifications). On the falling creatures' **stand**
  challenge the AI verified once, and there its random twin verified with a larger effect. We do not claim the AI helps
  creatures that cannot stand.
- Small study: 12 investigations, one zoo of six starters, two replicates, one model and protocol, one physics
  model. p = 0.031 is the minimum attainable with five discordant pairs; one more twin-only pair would make it not
  significant. Verification is "verified on held-out seeds" under `verdict_v1`, not proof of a causal mechanism.
- The pipeline was developed on the balanced creature's push challenge before registration (see `../dev_live_records/`),
  so the push cells are not independent of development choices (heel geometry in the evidence, 0.625 N resolution,
  acceptance rule in the prompt, probes). The other five starters were not used in development.
- Not compared: classical optimisers given the same rollout budget (R2-style search), other models, or human designers.
