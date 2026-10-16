# Forge Loop model calibration (M0), 2026-10-14

**Purpose.** Engineering calibration: which NVIDIA model on Nebius Token Factory, with which generation settings,
reliably returns a usable, machine-valid engineering reply for a drawn creature's failure evidence. **This is not a
measurement of how good the models' redesigns are**; no proposal here was simulated. That comparison is the
Counterfactual Arena's job.

**Frozen context** (`context.json`, built in MuJoCo on the VM before any request): calibration creature "Stubby"
(5 cm feet, 6 kg torso, default legs/motors), 25 N forward push for 0.15 s at 1.0 s, 5 s runs, seeds 100001–100003
(2 of 3 fall), compact evidence 3.0 KB (forensics of seed 100001), editable parameters per
`docs/FORGE_LOOP_CONTRACTS.md` §5.2. Prompt ≈ 3,726 tokens incl. the reply schema.

**Pass criteria (every request):** HTTP 200 · `finish_reason=stop` · non-empty content · JSON object · schema-valid ·
every edit within the edit rules · every citation resolves to a single value · latency ≤ 120 s.

Script: `scripts/forge_calibrate.py`. Raw requests/responses, request ids, usage and cost: `requests.jsonl` (v1),
`requests_v2.jsonl` (v2). Runs executed on the Nebius VM. No retries.

## v1 — original contract (12 requests: 4 models × 3 settings)

Settings: **A** `reasoning_effort=low` + strict `json_schema`, max 16k · **B** `chat_template_kwargs.enable_thinking=false`
+ strict `json_schema`, max 8k · **C** default reasoning, JSON requested in the prompt only, max 16k.

Result: **12/12 HTTP 200, finish=stop, non-empty content** (the `content=null` failure that stopped R3 did not occur),
but **0/12 valid**. Two systematic contract defects, not model collapse:
1. `proposals[].hypothesis` was filled with the hypothesis *sentence* (ids also came back as "h1"/"P1" variants).
2. Citations used invented or mis-prefixed key paths, or appended values (`"path: 1.21"`).
12 requests, $0.0810.

## v2 — contract fix only (same evidence, models, settings, criteria)

Changes: ids fixed to `"H1".."H3"` and stated in the prompt; the JSON schema enumerates the hypothesis ids, the
editable parameter names and **every citable evidence path** (93 scalar leaves). Prompt otherwise unchanged.

Judging rule: at run time Stage A used a *strict* reading of the prompt ("controller edits use op `set`"); the
production contract (§5.2) allows `scale` or `set` judged on the resulting value. Table below is judged by the
**contract rule** (`python scripts/forge_calibrate.py --report`); under the strict rule nano/B is the only change (fail).
The "failures" column shows the errors recorded at run time.

| stage | model | setting | pass | http | finish | latency s | prompt tok | completion tok | cost $ | failures (as recorded) |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | super | B | PASS | 200 | stop | 4.79 | 3726 | 928 | 0.0020 |  |
| A1 | super | A | fail | 200 | stop | 6.03 | 3733 | 1210 | 0.0022 | P2: balance_gain 80→150 exceeds \|Δu\| ≤ 0.25 |
| A1 | super | C | PASS | 200 | stop | 10.55 | 3726 | 2257 | 0.0031 |  |
| A1 | ultra | B | fail | 200 | stop | 8.05 | 3726 | 1855 | 0.0093 | P1: foot_length ×2.0 (> 1.5) |
| A1 | nano | B | PASS* | 200 | stop | 10.18 | 3726 | 1429 | 0.0006 | (*strict rule: op `scale` on balance_gain) |
| A1 | ultra | A | PASS | 200 | stop | 28.68 | 3726 | 7800 | 0.0271 |  |
| A1 | ultra | C | PASS | 200 | stop | 33.78 | 3726 | 9295 | 0.0316 |  |
| A1 | lightning | B | PASS | 200 | stop | 6.08 | 3726 | 1356 | 0.0005 |  |
| A1 | lightning | A | PASS | 200 | stop | 32.77 | 3726 | 7965 | 0.0021 |  |
| A1 | nano | C | PASS | 200 | stop | 38.82 | 3726 | 6297 | 0.0017 |  |
| A1 | lightning | C | PASS | 200 | stop | 48.0 | 3726 | 13032 | 0.0034 |  |
| A1 | nano | A | fail | 200 | **length** | 96.43 | 3726 | 16000 | 0.0041 | hidden reasoning used the whole budget; empty content |
| B2 | super | B | PASS | 200 | stop | 4.0 | 3726 | 768 | 0.0018 |  |
| B3 | super | B | PASS | 200 | stop | 4.65 | 3726 | 924 | 0.0019 |  |
| B4 | super | B | PASS | 200 | stop | 3.99 | 3726 | 792 | 0.0018 |  |
| B4 | ultra | A | PASS | 200 | stop | 55.92 | 3726 | 13491 | 0.0442 |  |
| B3 | ultra | A | PASS | 200 | stop | 57.22 | 3726 | 13326 | 0.0437 |  |
| B2 | ultra | A | PASS | 200 | stop | 61.27 | 3726 | 14532 | 0.0473 |  |

v2 Stage A: 9/12 pass (contract rule). Stage B (3 more reps of two pre-chosen pairs): super/B 3/3, ultra/A 3/3.
18 requests, $0.2286.

## Decision

- **Production default: `nvidia/nemotron-3-super-120b-a12b`, thinking disabled (`chat_template_kwargs.enable_thinking=false`),
  strict `json_schema` with per-evidence enums, `max_tokens` 8,000, temperature 0.6.** 4/4 valid, 4.0–4.8 s,
  ~770–930 completion tokens, ≈ $0.002 per call.
- **Optional "deep" mode: `nvidia/Nemotron-3-Ultra-550b-a55b`, `reasoning_effort=low`, strict `json_schema`.**
  4/4 valid, but 28–61 s and 7.8k–14.5k completion tokens, i.e. close to the 16k cap that caused R3-style empty replies;
  if used, `max_tokens` must be raised (24k) and the UI must show the wait. ≈ $0.03–0.05 per call.
- Not selected: Nano with reasoning (length failure), prompt-only JSON (works but unconstrained citations depend on
  luck); Lightning passes and is cheap but offers no advantage over Super/B here.
- The id/path/param enum construction is part of the production contract (`forge_ai.build_reply_schema`), and the
  server-side validator still re-checks everything.

**Caveats.** One frozen context, one creature, one challenge; n = 1 per pair in Stage A and n = 4 for the chosen pairs.
"Valid" means machine-checkable and grounded in real evidence paths, not physically correct. Reply quality (diagnosis
diversity, plausibility) was read informally: all valid replies proposed physically sensible edits (foot length,
ankle balance gain, standing posture, leg proportions); Ultra/A produced the most diverse hypotheses.

**Totals (shared Forge inference ledger, VM `~/dev/ledger/inference_ledger.jsonl`):** 30 requests, $0.3096,
274,898 tokens. The R3 41-request/300k-token cap is separate and unchanged.
