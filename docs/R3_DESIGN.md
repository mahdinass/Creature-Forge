# R3 — Nemotron-guided physical investigation (corrected design, 2026-10-14)

Binding text: `experiments/phase2a_r3/protocol.json` (built by `creature_forge.r3.build_protocol`, committed before any rollout or model request). Code: `creature_forge/r3.py`, `scripts/run_r3.py`, `scripts/preregister_r3.py`; tests: `tests/test_r3.py` (25). Approved limits: **30 live requests, 130,000 combined tokens, 6,000 physics rollouts, ≤ $2 additional estimated spend, no extension, no retries, no GPU.**

## 1. Question
Do Nemotron-proposed, MuJoCo-grounded, bounded edits to the frozen Phase 2A incumbent θ0 raise its walking success more often than **matched random edits**? Secondary (exploratory): measured evidence vs none; a rule-based heuristic. MuJoCo alone decides; text is never a result. R2's classical optimiser success is not attributable to the model and is not part of this experiment.

**Honest prior.** R2 showed random local perturbations of θ0 already improve it often, so the matched-random baseline is strong and a null or negative result for the model is plausible; it will be reported as such.

## 2. Corrections applied (review of 2026-10-14)
1. **Identical control context.** Arms M and N receive the same system prompt and a byte-identical controller block (value, lower, upper, u, meaning for all 15 parameters) and episode description. The only difference is the measured MuJoCo evidence (`summary`, `failing_seeds`, `walking_seeds`). Both arms are held to the same output schema (≥ 2 distinct citations resolving inside *their* context). Test: `ControlIdentityTests`.
2. **Clustering.** The primary comparison is a paired **request-block** exact sign-flip test over the 15 blocks (statistic Σ d_c, d_c = successes(M) − successes(RM) in block c; null distribution enumerated exactly; two-sided α = 0.05; claim only if p < 0.05 and mean d_c > 0). Proposals within a request are never treated as independent. Verified against brute-force enumeration.
3. **All four slots.** Each request asks for exactly 4 proposals; the endpoint counts all 4 allocated slots per request, with invalid/empty/missing slots as failures. Every one of the 60 slots per model arm has a matched-random counterpart whose parameter/sign stream (`default_rng(SeedSequence([rng_base, 11|12, block, slot]))`) is fixed before any request; for a valid slot the counterpart takes the model's edit count and |Δu| list, for an invalid or empty slot the fallback (2 edits, |Δu| = 0.10 and 0.05). The valid-slot-only comparison is exploratory.
4. **Prespecified contexts and no feedback.** θ0 is run once on 180 evidence-pool seeds (9100-9279). Context c shows the failing seeds with ascending rank 4c…4c+3 and the walking seeds with rank 2c…2c+1 (STOP if the pool has < 60 failing or < 30 walking). `contexts.json` (15 contexts, both prompts per block, SHA-256 of every prompt) is committed before any request. `candidates.json` (every model-derived and random candidate vector with provenance) is committed before any candidate is simulated. Screening outcomes never alter prompts, comparators or selection.
5. **Realised magnitudes.** For every edit both the requested Δu and the Δu realised after reflection at the bounds are stored; `matching_audit` reports mean requested vs realised magnitude and the reflected fraction per arm (e.g. `start_lean` at its lower bound flips a negative step).
6. **Provenance.** Per request: prompt SHA-256, redacted call metadata (model id reported by the API, tokens, latency, request id), raw reply as received, per-slot validation result and reason, status (`ok / invalid_response / model_error / budget_exceeded`). No repair, selection by hand or re-request.
7. **Feasibility under the caps.** Planned maximum 5,268 rollouts ≤ 6,000 (pilot 96, pools 244, ≤ 244 candidates × 16 screening, θ0 + 15 validations × 64); the 30 frozen prompts have a token ceiling below 130,000 (checked at the freeze; STOP otherwise); an end-to-end test runs scripted model + fake physics over the real frozen prompts and asserts every cap.
8. **Seeds.** Evidence pool 9100-9279, screen pool 9300-9363, validation 9400-9463, pilot 9500-9515. Disjoint from all Phase 2A, R1 and R2 seeds, including the R2 final seeds 8000-8149 (untouched). Seeds 9000-9001 were used by infrastructure compatibility checks (`check_env.py`) and are excluded and disclosed; no R3 seed has been used before registration.

## 3. Arms
| arm | proposer | context |
|---|---|---|
| **M** | Nemotron | controller table + episode + measured evidence of 6 θ0 seeds (4 failing, 2 walking) |
| **N** | Nemotron | controller table + episode only |
| **RM / RN** | matched random | counterparts of every M / N slot |
| **H** | rule-based heuristic (descriptive) | fires if ≥ half of the pool's failing seeds have ≤ 1 valid step; edits from the pre-R2 diagnosis; written knowing R2's outcome, i.e. a knowledgeable baseline |

Model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, temperature 0.7, max 2,200 completion tokens, default reasoning, requests interleaved M0, N0, M1, N1, …

## 4. Evaluation
Candidate = θ0 in normalised space + edits, reflected at the bounds. **Screening:** 16 seeds chosen from a 64-seed pool (first 8 walking + first 8 failing for θ0, so θ0 walks 8/16 by construction), common random numbers; **improved** = ≥ 2 more walking seeds than θ0. **Validation:** top-3 per arm by screening gain (ties by earlier block, slot) plus θ0 once on 64 fresh seeds; validated improvement = ≥ 5 more walking seeds; descriptive. Exploratory: M vs N (paired sign-flip), N vs RN, prediction hit rate vs confidence, H outcomes.

## 5. Completeness and stopping
The confirmatory test is run only if all 30 requests were sent with no transport/HTTP error or budget refusal; otherwise the experiment is reported as incomplete. Any hard limit stops the run. A malformed reply is a model outcome (failure slots), a transport error is not.

## 6. Spend
Inference ≤ 130k tokens; the model's token price could not be verified, so the bound assumes a deliberately high $5 per million tokens (≤ $0.65). VM ≤ 1 h ≈ $0.27. Upper bound ≈ $0.92 < $2. Actual token usage and the price-bracketed estimate are recorded in `live_summary.json`.

## 7. Demo mode (exploratory, labelled)
Separate from R3: an interactive Investigation Lab flow (observed failure → live Nemotron hypothesis → bounded intervention → MuJoCo verification → replay → measured verdict). Scripted replies are never shown as live; no classical-optimiser result is attributed to the model.

## 8. Not claimed
That Nemotron understands the physics, that its stated mechanisms are causal, or that it beats an optimiser (R2's arm T needed no model).
