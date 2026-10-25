# DI-1 reproducibility and evidence locations

Final decision: NOT EVALUABLE / NO-GO. These commands audit existing evidence;
they do not authorize new physics, a VM start or a prospective evaluation.

Physics v1 source: `1e0f610`; v2: `2f6031f`; normalized uniform replay and
canonical analysis: `2a4f7d4`. See `source_provenance.json` for full Git IDs and
SHA-256 of committed source bytes. Original registrations remain under the
parent `di1/` directory; protocol SHA-256 is
`30046abf92e2cf393400edeca6d4b7f5e258f131a00d59279e85f177b77619ad`.

Raw TGZs listed in `archives_verified.json` are retained at:

- Windows research checkout: `artifacts/di1_ops/` (ignored).
- Persistent stopped batch disk: `/home/forge/dev/r0-codex/artifacts/`.

Do not put large journals/archives or credentials in Git. All three outer hashes,
sizes and exact manifest membership/hashes were checked locally. Committed
`v1_SHA256SUMS`, `v2_SHA256SUMS`, `postaudit_SHA256SUMS` cover their extracted
archive roots, excluding the manifest itself and operational temporary files per
the existing `r0_integrity.hashes` convention. `archives_verified.json` records
200 verified file entries; it is not a count of independent experiments.
`SHA256SUMS` in this results directory uses repository-relative paths, covering
the small committed results and five DI1 reports; it excludes itself and the
mutable PROJECT_STATE/memory sync records. Source snapshot hashes are separate
to avoid platform line-ending changes.

Canonical native environment: existing `/home/forge/dev/venvs/hdb/bin/python`,
Python 3.12.3, MuJoCo 3.15.0, NumPy 2.5.4; see `environment.json`. No new venv.
The original interpreter matters for exact floating-point replay. Local 3.11
can verify hashes/export and run guards; no 3.11 exact numerical analysis claim.

From the isolated Linux checkout at the indicated source commit, with the raw
archives safely extracted into their original roots, the completed canonical
commands were equivalent to:

```sh
PY=/home/forge/dev/venvs/hdb/bin/python
$PY -m unittest discover -s tests -p test_di1.py -v
$PY scripts/di1_analyze.py --root artifacts/di1_pilot_v1 --out artifacts/di1_postaudit_v1/v1_analysis.json
$PY scripts/di1_analyze.py --root artifacts/di1_pilot_v2 --stop-amendment --out artifacts/di1_postaudit_v1/analysis.json
$PY scripts/di1_analyze.py --root artifacts/di1_pilot_v2 --stop-amendment --out artifacts/di1_postaudit_v1/analysis.json
```

The repeated command verifies exact immutable output, rather than overwriting
it. Saved stdout repeats were byte-identical. Uniform physical generation replay
was already completed for all eight attempts into a new directory, 384 jobs,
with 64 exact overlapping failed-audit jobs; proof JSONs and the post-audit
archive retain the launcher/source and actual invocation. It is not required
for read-only reuse and must not be triggered implicitly.

Local read-only re-export and feasibility (PowerShell, repository root; each
command is one line):

```powershell
python scripts/di1_export_evidence.py --v1 artifacts/di1_ops/extracted/di1_pilot_v1 --v2 artifacts/di1_ops/extracted/di1_pilot_v2 --audit artifacts/di1_ops/extracted/di1_postaudit_v1 --ops artifacts/di1_ops --out experiments/causal_engineer/dev/di1/results
python scripts/di1_feasibility.py --analysis artifacts/di1_ops/extracted/di1_postaudit_v1/analysis.json --root artifacts/di1_ops/extracted/di1_pilot_v2 --campaign artifacts/di1_ops/campaign.json --status artifacts/di1_ops/final_control_plane.json --out experiments/causal_engineer/dev/di1/results/feasibility.json
```

Both refuse changed existing output. Campaign/status source files remain in
ignored operations evidence; the nonsecret campaign and final API receipt are
also committed here. These are local
conservative billing records, not current account balance or provider invoice.
The final gate is a documented feasibility/precision decision, not a hidden
rerun of the pilot analysis's immutable PENDING_FEASIBILITY label. Preserve that
label as historical stage provenance.

Audit qualifications: whole-base descriptives, no learner fitted, no outcomes
imputed, no post-hoc subgroup selected, no prospective evaluation or sealed data.
The final reports explain the limits of fixed-family strata, five eligible
bases, reference binomial intervals and planning power assumptions.
