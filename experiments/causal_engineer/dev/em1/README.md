# EM-1 completed G0 evidence

**EM-1 NOT EVALUABLE; NO-GO for further implementation with current decision
evidence.** This is not a failed test of a fitted learner. Read
`docs/EM1_RESULTS.md`, `docs/EM1_FEASIBILITY.md` and `docs/EM1_DECISION.md`.

The complete physical audit covers 804 exact interventions, 324 historical
episodes, 30 independent bases and nine development families. Observed minus
predicted robustness walking is +5.18 percentage points (descriptive cluster95
[1.58,8.97]), but B0 already chooses an observed walking maximizer in every
candidate set. FULL for 480 alternatives is missing. No learner, sham/control
comparison, Nemotron call or fresh prospective cohort followed the G0 stop.

Measurement/analysis source `f70549d636b5b2141988a9165574c5f53015a6be`, original
protocol `protocol_g0.json`; older inventories/protocols and all engineering
annotations are retained. Current analysis utility adds a post-run path-index
formatting fix only. Original Python 3.12 reproduces the numerical analysis
exactly; Python 3.11 has documented last-bit float-summation differences, so
its failed exact comparison is explicitly recorded, not overwritten.

Full raw archive `em1_g0_v2_1792956024417354279.tgz`: 1,030,524 bytes, SHA-256
`dbfc677101a6430ce7fa829d0a3e22ac07697f24b90fae3b9ad5db6317b14236`.
It is retained locally in ignored `artifacts/em1_ops/` and on the stopped batch
disk under `/home/forge/dev/r0-codex/artifacts/`. The interrupted partial archive
is retained beside it. Large generated raw files are not committed.

`results/` contains the small original analysis, paired intervention CSV,
identification bounds, decision and verification/shutdown receipts. Its
`EVIDENCE_SHA256SUMS` uses names relative to that directory. `EM1_SHA256SUMS`
uses paths relative to the **repository root** and covers the four reports,
registration/engineering documents and result manifest. Protocol source hashes
normalize source LF only; scientific raw record hashes use exact bytes.

Both VMs were independently STOPPED after retrieval. Conservative Cloud estimate
$1.097 and paid batch time 0.517 hours, Token Factory $0; these are not invoice
or final-credit values. No additional paid stage is scheduled.
