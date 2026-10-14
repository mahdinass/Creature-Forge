# R3 attempt 1 (protocol `phase2a-r3-protocol-v1`) - aborted, not a result (2026-10-14)

Registered in `7def51f`; contexts and prompts frozen in `196de48`; pilot, evidence pool (theta0 100/180 walking) and screen pool (38/64) completed on the Nebius VM within the ledger (see `results/`). The live batch (`scripts/run_r3.py live --confirm-live`) was started and interrupted after **3 of 30 requests** (M0, N0, M1).

**What happened.** All three requests returned HTTP 200 with `finish_reason=length`, `reasoning_present=true` and `content=null`: the model's hidden reasoning consumed the entire 2,200-token completion limit before any answer was written (prompt tokens 2,746 / 1,059 / 2,718; completion 2,200 each; latency ~16 s; model id as requested; request ids in `results/requests.jsonl`). Under the registered rules each would be an invalid response (four failure slots).

**Why it was stopped.** The failure is about the registered generation settings (default reasoning, 2,200 max tokens), not about the model's physical proposals. Continuing would have spent about 120k of the 130k approved tokens to measure a truncation artifact (all-invalid blocks for both arms, a null result by construction). The protocol requires stopping when an unexpected failure invalidates the experiment.

**Accounting.** 3 requests sent, 13,114 tokens used (estimated cost at an assumed $1 per million tokens: $0.013), no candidates generated or simulated, no screening outcome observed, nothing selected. R3 physics ledger: pilot 96 + evidence pool 180 + screen pool 64 = 340 rollouts of 6,000. Protocol v1 remains immutable; any change of generation settings requires a new protocol id.
