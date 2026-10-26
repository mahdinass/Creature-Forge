# H1 reproduction without paid physics

Use Python 3.11+ in this research checkout. Independent audit uses only stdlib;
no MuJoCo, NumPy, model or authoritative verdict import. Full raw originals and
new archives already exist in this shared workspace. Use new output names.

```powershell
python -m unittest discover -s tests -p test_h1.py -v
python -m unittest discover -s tests -p test_h1_reliability.py -v
python -B scripts/h1_independent_stdlib.py --stage-a artifacts/h1_ops/h1_stage_a_v1 --stage-b artifacts/h1_ops/h1_stage_b_v1 --out artifacts/h1_new_independent_replay.json
python scripts/h1_counterfactual.py analyze --out artifacts/h1_ops/h1_stage_a_v1 --analysis-output artifacts/h1_new_a_replay.json
python scripts/h1_reliability.py analyze --stage-a artifacts/h1_ops/h1_stage_a_v1 --out artifacts/h1_ops/h1_stage_b_v1 --analysis-output artifacts/h1_new_b_replay.json
```

Original R0 raw units: `artifacts/r0_ops/r0_run_20261025/` or `--r0-raw PATH`.
Original R0 archive SHA256:
6dcda839b60a401831a46efd760b2702e65e42fda65e8391e87d7018e8520806.
Full Stage0 recovery/replays remain in `artifacts/h1_stage0_20261026/`,
`artifacts/h1_recovered_audit/` and `artifacts/h1_recovered_reconstruction/`.
See `../STAGE0_RECOVERY.md`.

Complete local archives:

- `artifacts/h1_ops/stage_a_native_retrieved.tgz`, SHA256
  6645c26f2249080a300d59df3a12996bffbb44b6bd05d9cdece4f78d200353a4.
- `artifacts/h1_ops/stage_b_native_retrieved.tgz`, SHA256
  af4655df5bb258b4cea1b01e254cb521b8ba94bf328cf0555c759e8b6ecb47cc.

Verify hashes, safely extract to a fresh directory and check every SHA256SUMS
entry before analysis. Partial `stage_a_native.tgz` and `stage_b_native_stream.tgz`
are preserved and must not be treated as complete evidence. Full originals also
remain on the stopped batch disk at `/home/forge/dev/r0-codex/artifacts/`.

Native Python 3.12 repeats are byte-identical. Python 3.11 has disclosed last-bit
differences <=2.22e-16, with identical counts/choices/gates. Independent audit
checks integer calculations and numerical tolerance without physics reruns.

`python -m unittest discover -s tests -p test_frozen_records.py -v` has one
inherited coverage failure: 42 E-1 paths omitted at the baseline. Covered integrity
passes. See `inherited_guard_failure.json`; do not regenerate the sealed manifest.

None of these commands starts a VM, calls a model or simulates physics. Any new
physics requires registration, new output paths, operational checks and authorization.
