# Phase 1 report - 2026-10-13 (exploratory; NOT a claim that Nemotron beats or loses to any baseline)

Setup: 8 cm foot, 25 N push for 0.15 s at t=1 s, 5 s rollouts. Registered in `protocol.json` (commit `8bf6c4b`) before any request.
Judge: 10 held-out seeds (200-209) x pushes 15/20/25/30/35 N = 50 MuJoCo rollouts per design. Baseline falls 0/10 at 15 N and 10/10 at >=20 N.
Success = primary (25 N) fall rate <= 0.2 AND never worse than baseline at any push AND primary survival time not worse.

## Baselines (no model calls)
| method | proposals | held-out sims | result |
|---|---|---|---|
| random (uniform parameter + value in bounds, seed 1000) | 100 | 5000 | 22 success / 6 partial / 72 none; per-proposal success 0.22, Wilson 95% [0.15, 0.31]; analytic best-of-k estimates: k=3 0.53, k=5 0.71, k=10 0.92. 19/22 foot_length proposals succeeded (0.135-0.252 m); 3 leg_density proposals (2167-2476 kg/m3) also succeeded; 0 successes for the other 5 parameters |
| heuristic (mechanism screen -> foot_length x1.5 = 0.12 m) | 1 | 50 | tier none: falls 0/10 at 15 N, 0/10 at 20 N, 9/10 at 25 N, 10/10 at 30-35 N. Prior knowledge is disclosed in `proposers.py`; the factor was fixed before evaluation |
| reference: foot_length 0.16 (known Phase 0 answer, not a proposer) | 1 | 50 | success |

## Nemotron (3 requests, 12,643 of 18,000 tokens, no retries, default reasoning, 4096 max completion)
| id | prompt | tokens (prompt+completion) | latency | outcome |
|---|---|---|---|---|
| control `20261013T010249Z-ca2db8` | original compact evidence, T=0 | 1088+2080 | 14.0 s | torso_mass 5->3, cited `body.torso_mass`, `matched_seed_results.fall_rate`; prediction (fall rate down) NOT met; tier none; WORSE at 15 N (9/10 fall vs 0/10) |
| enriched-1 `20261013T010325Z-9d9310` | forensic evidence, T=0 | 3002+1414 | 8.5 s | mechanism tipping_support_margin; cited `support.com_margin_before_push_m` and `support.min_xcom_margin_after_push_m` (real measured values); still proposed torso_mass 5->3; prediction NOT met; tier none; worse at 15 N (9/10) |
| enriched-2 `20261013T010405Z-9a3be8` | same prompt, T=0.7 | 3002+2057 | 40.4 s | invalid_model_output: cited nonexistent path `forensics.detailed.xcom_margin_before_push_m`; nothing simulated |

Request ids: 0a302030165be13a6800a72b8c9afb4b, 5bdcd341847994f60aca7315eac28f26, cc9517d785544f8ac1c200047086bc31.
Simulator evaluations per valid Nemotron trial: 100 held-out (baseline is re-evaluated per trial) + 10 screening, plus 3 evidence rollouts (+3 for forensic).

## What this does and does not show
- Forensic evidence made the model cite real measured margins (enforced by validation), but it chose the same ineffective lever (torso mass) in 2 of 2 valid replies, and 1 reply was invalid. The stated mechanism (support margin) did not lead to the chosen parameter; the claim-to-intervention link is weak. Prediction matched measurement 0 of 2.
- Lowering torso mass is not neutral: the robot falls at 15 N where the baseline is stable. The multi-push regression rule caught this; a fall-rate-at-25-N-only check would have called it a tie.
- 3 requests (2 valid), no success. A random proposer succeeds about 22% of the time per proposal, so a few failures say nothing about the relative ranking. The sample is far too small to claim anything about Nemotron vs random vs heuristic.
- The heuristic failure (0.12 m) shows the frontier: "longer foot" is necessary but the magnitude matters.
- Caveats: one scenario and one model; planar sim; the 8 cm baseline sits near the tipping frontier (see INCIDENTS); the 16 cm design also falls at 35 N; held-out seeds only vary a small initial perturbation; the random best-of-k figures are pooled-rate estimates.
- Not done: no prompt iteration (deliberate), no response_format test, no Studio panel UI (data model and `/api/investigations/{id}/view` only).
