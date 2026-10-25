# VEL-1 evidence and reproduction

Verdict: INSUFFICIENT EVIDENCE. This directory contains stored-data feasibility
analysis, not a production learner or permission for another experiment.

Plan frozen/pushed `63df2c1`; fitted-model/audit source `8c65b44`. Full commit IDs
and Git-blob SHA-256 appear in `source_provenance.json`. Later report/export
helpers do not change the models, predictions, targets, thresholds or features.
The explicitly post-fit context-prevalence diagnostic strengthens the trivial
reference and is not a selected alternative learner.

Primary development input sources:

- `fresh_A1c5.jsonl`, SHA256 `3bde2b77676fd3d46592bb9ad50250ecfc8614376d6676b87d59f2a97d2149cb`.
- `vs5_A1c.jsonl`, SHA256 `e2ee1d53cdf81f2395a065c1b017ffc885b045fb533467b04a661429834ea520`.
- Legacy `stopcal.jsonl` is separately inventoried; its nominal base groups do
  not overlap primary. The old stop map is a separate reference, not refitted
  using held-out primary outcomes.

Machine-local original inputs were found at
`C:/Users/mbnas/.vscode/Creature-Forge/artifacts/vm/hdb/artifacts/hdb/`.
Additional explicitly named development sources: tracked
`experiments/causal_engineer/dev/rl1/rl1_matrix.tgz`, ignored
`artifacts/r0_ops/r0_run_20261025/units/`,
`artifacts/di1_ops/extracted/di1_pilot_v1/` and `di1_pilot_v2/`,
`artifacts/em1_ops/em1_g0_v2/jobs.json`. Exact source file/row/body/candidate
hashes are in `audit.json` and prepared rows. All original raw studies remain
unchanged. No sealed loader is used. RL-1/R0/DI-1 are separately audited, not
pooled to inflate the primary cohort.

Existing local environment: Python3.11.9/NumPy2.4.6 at
`C:/Users/mbnas/.vscode/Creature-Forge/.venv/Scripts/python.exe`. No installation,
new virtual environment or simulator call. Main analysis sets BLAS/OpenMP/MKL
threads to1 before importing NumPy. Exact replay is verified in this environment;
other interpreter/library versions may differ in last-bit arithmetic.

PowerShell, repository root (each command is one line):

```powershell
& 'C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe' -m unittest discover -s tests -p test_vel1.py -v
& 'C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe' scripts/vel1_audit.py --records 'C:\Users\mbnas\.vscode\Creature-Forge\artifacts\vm\hdb\artifacts\hdb' --r0 artifacts/r0_ops/r0_run_20261025 --di1 artifacts/di1_ops/extracted --em1-jobs artifacts/em1_ops/em1_g0_v2/jobs.json --out artifacts/vel1/audit_v2
& 'C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe' scripts/vel1_analyze.py --rows artifacts/vel1/audit_v2/fresh_v5_rows.json --out artifacts/vel1/analysis_v1 --family
& 'C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe' scripts/vel1_analyze.py --rows artifacts/vel1/audit_v2/fresh_v5_rows.json --out artifacts/vel1/analysis_experience --family --experience
& 'C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe' scripts/vel1_analyze.py --rows artifacts/vel1/audit_v2/fresh_v5_rows.json --out artifacts/vel1/analysis_experience --family --experience
& 'C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe' scripts/vel1_report.py --audit artifacts/vel1/audit_v2 --analysis artifacts/vel1/analysis_experience --r0 artifacts/r0_ops/r0_run_20261025 --di1 artifacts/di1_ops/extracted --out artifacts/vel1/report_closeout
& 'C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe' scripts/vel1_export.py --root artifacts/vel1 --out experiments/causal_engineer/dev/vel1/results
```

Existing-output publication refuses changed JSON/CSV/receipt bytes. The repeated
analysis is an equality check, not an overwrite. `analysis_stdout.json` and
`analysis_repeat_stdout.json` match byte-exactly; the recorded full repeat took
28.57s and generated no physics. Preliminary V0/V1 results are unchanged when
experience is added. Earlier audit/report development outputs remain locally
under ignored `artifacts/vel1/`; they were not new physical trials.

The primary grouped analysis can also be reproduced without the large historical
archives from committed prepared `fresh_v5_rows.json`, with a NEW output path:

```powershell
& 'C:\Users\mbnas\.vscode\Creature-Forge\.venv\Scripts\python.exe' scripts/vel1_analyze.py --rows experiments/causal_engineer/dev/vel1/results/fresh_v5_rows.json --out artifacts/vel1/reproduce_from_prepared --family --experience
```

`SHA256SUMS` uses repository-relative paths and covers the four reports and
compact evidence, excluding itself. It omits mutable PROJECT_STATE/memory sync
records; source code bytes are separately pinned in `source_provenance.json`.
After commit, verify the same hashes against Git blobs as well as working files.
Never regenerate masks/labels from the verifier as predictor features.

All groups and family labels are evaluator metadata, not numeric model features.
No actual historical episode chronology is inferred from file order. Current
verification already governs FULL claims; risk/coverage is not improved recovery.
The study's final disposition is `decision.json`, with scientific limits in the
four reports. Proposed next measurements and cost scenarios have not been run.

Initial/final control-plane receipts both show STOPPED; compute ledger hours are
unchanged. `resources.json` distinguishes zero new compute/inference from the
small existing-storage ledger change. No credentials are stored here, no credit
balance is inferred, and no paid work remains scheduled.
