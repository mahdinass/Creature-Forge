# H3 executed T1/T2 reproduction — saved evidence only

Decision: NO-GO at qualification, no optimization. Native source c7103d47ba6e63e6cfd5d0b2c2ab161091163969; frozen plan SHA c5eea6daddaf90c9ed2cef598dce0b45919e6c9bbcef8226b456b0412e988bdd. Do not rerun physics or reuse spent unit directories. Read docs/H3_RESULTS.md and H3_EXECUTION_DECISION.md.

Portable stdlib-only replay from Git, without authentication or simulator imports:

```text
python scripts/h3_qualification_audit.py --qualification experiments/causal_engineer/dev/h3/results/qualification.json.gz --plan experiments/causal_engineer/dev/h3/plan.json --sha256 8ac22cedb978ad684375d846ca3dbd8bed29d1c820882bac90d26624ec9dab70 --out <new-output.json>
```

This validates all1,152 seed rows/48 roots against fixed plan seed roles, rederives each entry flag and six-per-side quotas, and reproduces four eligible / NO-GO. The gzip payload is the exact native qualification-result JSON; raw-byte SHA abd895ae2873f5d8f3fbf7040645fbd981bd9eb847a9089cead98c292695f883. `native_gate.json` and `native_finish.json` retain the other direct scientific outputs.

Full native archive audit, if the preserved local archive is accessible (contains private authorization metadata and is deliberately not committed):

```text
python scripts/h3_qualification_audit.py --archive artifacts/h3_ops/native_run.tgz --plan experiments/causal_engineer/dev/h3/plan.json --sha256 7033654550fd5d2bb6fbc37b600cce7b3dc0d44c0df5f3200947b4cf733e1262 --out <new-native-audit.json>
```

This checks61 outer and3/51 closed unit-manifest entries, direct per-root records, native gate/finish and reservation journals. Audit repetition was byte-exact. `independent_native_audit.json` is the saved full-archive audit; `portable_replay.json` the portable science-only audit. Auditor was added post-acquisition to independently replay frozen rules, not fit a new target. Original raw archive and all failed transfer traces remain local/VM evidence.

Registered saved-result analyzer, in the already inspected existing venv, if the full local native extraction is available:

```text
python scripts/h3_analyze.py --plan experiments/causal_engineer/dev/h3/plan.json --campaign artifacts/h3_ops/native_retrieved/h3_pilot_v1 --out <new-analysis.json>
```

Expected: NO-GO, fewer than12 independent qualified lineages. The script refuses overwrite. `registered_analysis.json` preserves the actual output. It performs no simulation/training.

Operational tests: `python -m unittest tests.test_h3_ops -v` (two non-physics tests pass). Earlier32 H3/H1 non-physics tests and frozen-integrity warning remain in the preparation record; no full-suite rerun. Existing root API-stop and independent watchdog were reused; no new credentials or environment. Retrieval-only window changed local ops helper, not frozen science sources.

`resource_audit.json` uses conservative pre-start/first-STOPPED timestamps rather than assuming stop-request time ends billing. Quote, not invoice: approximatelyUSD0.35 /0.165 batch hours; Token Factory0; main0. Both STOPPED in `final_shutdown.json`. No further paid job is scheduled. `SHA256SUMS` covers this result packet; preparation's separate14-file export manifest is preserved, not regenerated.
