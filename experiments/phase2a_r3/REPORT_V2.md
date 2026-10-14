# R3 v2 - generation calibration failed; the statistical experiment was not run (2026-10-14)

Protocol `phase2a-r3-protocol-v2` (registered `fa69e2c`; calibration context frozen `159617b` before any calibration request). v1 (`7def51f`), its three empty-response requests and the aborted-attempt report are preserved unchanged.

## Documentation check (before any new request)
Nebius Token Factory docs: `reasoning_effort` accepts none|minimal|low|medium|high|xhigh|max with no per-model description; `max_completion_tokens` is documented as covering visible plus reasoning tokens; `usage.completion_tokens_details.reasoning_tokens` is nullable; `json_object`/`json_schema` response formats exist but are model dependent; `enable_thinking` and `chat_template_kwargs` are not documented. Accepted parameters were therefore not assumed to be honoured.

## Calibration (non-experimental pilot contexts: theta0 on pilot seeds 9500-9515, 9/16 walking; 4 failing + 2 walking seeds shown; 8 requests, no retries)
| setting | evidence arm (M) | no-evidence arm (N) | pass |
|---|---|---|---|
| A: effort none, 3500 | stop, 611 completion tokens, **null content**, reasoning present | stop, 672 tokens, **null content**, reasoning present | no |
| B: effort low, 3500 | length, 3500 tokens, **null content** | ok, 3,370 tokens, 4/4 schema-valid proposals | no |
| C: effort low, 5000 | length, 5000 tokens, **null content** | length, 5000 tokens, **null content** | no |
| D: effort medium, 5000 | length, 5000 tokens, **null content** | ok, 4,635 tokens, 4/4 schema-valid proposals | no |

The prespecified pass rule needs BOTH arms to return visible content with a valid envelope and >= 2 valid proposals. **No setting passed.** By the registered rule the statistical experiment is not run, no experimental request was sent, and nothing about physics outcomes was used (none exists for R3 candidates).

## Findings (descriptive)
- `reasoning_effort: none` was accepted but did not disable reasoning: the reply ended normally (`stop`) with reasoning present and no visible content (same as the Phase 1 observation).
- `low` and `medium` did not produce a clearly shorter chain: completion tokens were 3,370-5,000 whenever reasoning was present. The API did not report `reasoning_tokens`, so the effort level's effect cannot be verified directly.
- The control prompt (controller table only, ~1.1k prompt tokens) succeeded under B and D (4 valid proposals each), while the evidence prompt (~2.7k prompt tokens with measurements) hit the length limit at 3,500 and 5,000. Prompt length / evidence content, not the schema, is the main correlate, but with n = 1 per cell this is an observation, not a conclusion. Importantly this asymmetry is itself a treatment-arm difference in feasibility.

## Accounting
Requests: 3 (v1) + 8 (calibration) = **11 of 41**; tokens 13,114 + 42,996 = **56,110 of 300,000**; est. cost at an assumed $5/M tokens: $0.28. Physics: ledger 356 of 6,000 rollouts (340 carried over + 16 for the calibration-context batch, which re-ran theta0 on the pilot seeds because the v1 pilot did not store per-seed results). Ledger chain verified. VM stopped.

## Result
R3 produced **no estimate of whether Nemotron-proposed edits beat matched random edits**. The generation blocker is the R3 result under the registered rule. No AI success is claimed; R2's improvement came from a classical optimiser.

## What would be needed for any further statistical test (needs a new protocol id and your approval)
A prompt/setting combination that returns usable replies for both arms, e.g. fewer evidence seeds or terser evidence, one proposal per request, or a structured-output mode, calibrated again beforehand. Remaining combined headroom under the approved caps: 30 requests and 243,890 tokens.
