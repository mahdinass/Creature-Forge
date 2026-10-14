# R3 attempt 1: aborted; options for a v2 protocol (2026-10-14)

Evidence: `experiments/phase2a_r3/ATTEMPT1_ABORTED.md`, `results/requests.jsonl` (3 records), `results/live_summary.json`. Protocol v1 (`7def51f`) stays immutable.

## Finding
`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` with default reasoning and `max_tokens = 2200` returned `finish_reason=length`, hidden reasoning present, **null content** on 3 of 3 requests (both arms). This reproduces the Phase 1 note that the model "emits hidden reasoning" and that `reasoning_effort: none` once returned null content. With four structured proposals per request, reasoning does not fit in 2,200 completion tokens; the per-request budget implied by the approved caps (130k tokens / 30 requests ≈ 4.3k including a 1-3k prompt) leaves little room to raise it.

## Why this needed a stop and not a note
Under the registered rules these are four-failure blocks. All 30 would have measured a truncation artifact in both arms (M and N both 0), i.e. an uninformative null by construction, using ~120k of the 130k tokens.

## Options (all need a new protocol id; v1 and its 3 requests are disclosed and counted)
| option | change | token/request implication | risk |
|---|---|---|---|
| **A (recommended)** | Pre-specified calibration on 4 non-experimental pilot contexts (pilot seeds 9500-9515): ≤ 8 requests trying `reasoning_effort` ∈ {low, medium} × `max_tokens` ∈ {2200, 3500}; rule: take the cheapest setting with ≥ 3 of 4 parseable replies; then run the full 30-request v2 batch with it | +8 requests, ≤ +45k tokens → total ≤ 41 requests / ≤ 175k tokens (est. ≤ $0.9 at an assumed $5/M) | needs your approval of the larger caps; the parameter may not exist for this model |
| B | Keep 30/130k: 2 proposals per request, `max_tokens` 3,000, default reasoning | slots per request 2 (30 slots per arm) | weaker power; reasoning may still not fit |
| C | Keep everything, continue v1 as registered | ~120k tokens | uninformative; not recommended |
| D | Drop the live statistical comparison; use Nemotron only in the interactive Lab demo (1 proposal per call, generous `max_tokens`) with the offline matched-random/heuristic baselines and no claims | small | no confirmatory evidence about the model |

## Recommendation
Option A. It preserves the registered science (corrected contexts, request-block test, four slots, frozen comparators; only generation settings change), stays far under the $2 cap, and the calibration rule is fixed before the first calibration request. If no calibrated setting yields parseable replies, report that finding as the R3 result and fall back to D for the demo.

## What carries over unchanged to v2
Contexts and prompts (`196de48`), evidence/screen pools, pilot, seeds, comparator streams, analysis, completeness rules, ledger. Only `model.max_tokens_per_request`, `reasoning_effort`, the request/token caps and the calibration procedure change.
