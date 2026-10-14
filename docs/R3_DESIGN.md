# R3 — Nemotron-guided physical investigation (DESIGN; not registered, no live model calls made)

Status 2026-10-14. Machinery built and tested offline (`creature_forge/r3.py`, `scripts/run_r3.py`, `tests/test_r3.py`, 14 tests, scripted transport only). A live batch needs your approval of this document's request cap and cost estimate, then a committed `experiments/phase2a_r3/protocol.json` (same registration discipline as R1/R2).

## 1. Question
Do Nemotron-proposed, MuJoCo-grounded, bounded edits to a frozen controller raise its walking success more often than (a) edits of identical size chosen at random, (b) a rule-based heuristic, and (c) the same model without any measurements? "Improvement" is decided only by MuJoCo; text is never a result.

**Honest prior.** R2 showed that random local perturbations of θ0 already improve it often (arm S: 10-100% of candidates preserved walking depending on step size; at sigma 0.02-0.05 roughly 45-75% improved on the training seeds). The matched-random baseline is therefore strong, and a null or negative result for the model is a plausible outcome. It will be reported as such. No AI success is assumed anywhere in this plan.

## 2. Setup (reused, not rebuilt)
- Base controller: the frozen Phase 2A incumbent θ0 (61% walking on R2's final seeds), 15 normalised parameters, same gates, morphology and noise as R2 (`creature_forge.r2` jobs, ledger, Executor). The R2 winner is not the base (it already walks on 150/150, so there is no headroom to measure).
- Model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` through the existing `NebiusClient` (key from the environment/.env only, no retries, request/token/time limits, redacted call records). No GPU, no new Nebius resource.
- Seeds (new, disjoint from every consumed range): evidence 9000-9015 (θ0 once, 16 rollouts), screening 9100-9115 (θ0 + every candidate, common random numbers), validation 9200-9263 (θ0 once + top-3 of each arm).

## 3. Arms
| arm | proposer | evidence shown | slots |
|---|---|---|---|
| **M** | Nemotron | observed MuJoCo evidence of θ0 on the 16 evidence seeds: per-seed outcome label, fall time/pitch, valid/backward steps, touchdowns, speeds, pitch, support fractions, initial perturbation, plus the parameter table with bounds and `u` | 15 requests × 4 proposals = 60 |
| **N** | Nemotron, ablation | the parameter table only (no measurements) | 60 |
| **R** | matched random | none | one per VALID M proposal: same number of edits and same multiset of \|Δu\|, random distinct parameters and signs; a second matched set for N's valid proposals |
| **H** | rule-based heuristic | the same evidence | up to 4 fixed edits; abstains unless ≥ half of the failing evidence seeds have ≤ 1 valid step |

Heuristic rule (`r3.HEURISTIC_RULE`): from the pre-R2 diagnosis (start-up failures with backward lean): lean forward at start, lengthen the ramp, raise the pitch reference. It was written knowing R2's outcome, i.e. it is a knowledgeable baseline, not a blind one; stated in every report.

## 4. Proposal contract (enforced by `r3.parse_proposal`, no repair, no retries)
Per request the model returns `{"proposals": [≤4 items]}`; each item has exactly `claim` (10-400 chars), `cited_evidence` (≥ 2 distinct dotted paths, each resolving to a single value in the observed evidence; `[]` in arm N), `edits` (1-4, distinct known parameters, nonzero `delta_u`, |Δu| ≤ 0.15), `prediction` (`walking_seeds_screen`, `increase`, integer `min_gain_seeds` 1-8) and `confidence` ∈ [0,1]. An invalid envelope invalidates the request; an invalid item invalidates only that slot. Invalid and empty slots stay in the denominator (intention-to-treat) and are reported.

## 5. Evaluation, endpoints and statistics (to be frozen in the protocol)
- Candidate vector = θ0 in normalised space + edits, reflected at the bounds; evaluated on the 16 screening seeds. **Improved** = at least 2 more walking seeds than θ0 (θ0 evaluated once on the same seeds).
- **Primary (confirmatory, one test):** among valid M proposals, improved rate vs their matched-random partners: exact two-sided McNemar on the discordant pairs, α = 0.05; claim "model edits improve more often than matched random edits" only if p < 0.05 and the difference is positive. 
- Secondary (exploratory): M vs N (Fisher exact, unpaired), each arm's improved rate with Wilson 95% CI, intention-to-treat rates, H outcomes (descriptive), prediction hit rate (`min_gain_seeds` met) and calibration against `confidence`.
- **Validated improvement:** the top-3 improved proposals per arm (ranked by screening gain, ties by earlier slot) are run on the 64 validation seeds; success = at least 5 more walking seeds than θ0 on the same seeds (the R2 gate size). Reported per arm, no multiplicity claim.
- Power is limited (~48 valid pairs): the design detects only large differences; confidence intervals are reported rather than "no effect" claims.

## 6. Budget
- Model: 30 requests (15 per model arm), `max_tokens` 2048 each, ceiling **≈ 121k tokens** (`run_r3.py estimate`: M 76.7k, N 44.6k). Token prices for this model could not be verified from public docs; at an assumed $0.25 / $1 / $5 per million tokens the ceiling is $0.03 / $0.12 / $0.61. Hard stop at 30 requests and 130k tokens; no retries, no top-up.
- Physics (VM, no GPU): about 200 candidates × 16 + 15 validations × 64 + 96 θ0 = ≈ 4,300 rollouts, cap 6,000, ≈ 8 min, < $0.15.
- Total new spend well under $1. Requires your approval before the first live request.

## 7. Provenance and anti-fabrication rules
Every request is stored: prompt SHA-256, redacted call metadata (tokens, latency, request id), raw reply (untrusted), validated and invalid proposals with reasons. Status vocabulary: `ok / invalid_response / model_error / budget_exceeded`; a proposal is "improved/validated" only through its recorded MuJoCo outcome. Lab records keep observed / model / measured sections apart (existing `Trial` convention); dry-run replies are scripted text and can never be saved as results. No model reply is edited, repaired, selected by hand or re-requested after seeing the physics.

## 8. Demo mode (exploratory, clearly labelled)
After the registered batch, an interactive loop for the video: evidence → Nemotron proposal(s) → MuJoCo verification → replay of θ0 vs edited controller on a failing seed, with the verdict. It uses the same schema and bookkeeping, may show feedback rounds (the model sees measured outcomes), is labelled "live" vs "replay", and makes no statistical claim.

## 9. Not claimed
No claim that Nemotron understands the physics, that its explanations are causal, or that it outperforms an optimiser (R2's arm T found controllers walking 150/150 without any model). The product claim is narrower: a verifiable propose → simulate → verify loop in which the model's contribution is measured against matched baselines.
