# Post-run engineering amendment 3 — threshold serialization audit

All eight v2 attempts and both alternative policy paths on every qualified base
completed before the audit stopped. Native exit1/end1792963823; original archive
`di1_pilot_v2_1792963824025516518.tgz`, SHA256
`09b98c476d5c8a52febc4e3f4d877f0816078488bc4714c1fb6778976e3df5c4`,
14,793,318 bytes,89 manifest entries. Root SA API-stop requested21:30:28UTC.

The legacy `hdb_bench.threshold` returns a list of tuples. Its original JSON
record contains lists instead. Replay compared the Python containers directly,
so matching numerical data failed the audit. Normalize sequence representation
through `science` before comparison, retaining exact numbers and every key.
Regression test explicitly proves that changed walking counts still fail.

Preserve the failed archive and first64 replay jobs. Uniformly repeat generation
verification for ALL eight attempts into a NEW audit directory, compare overlapping
scientific seed results, then analyze the complete unchanged v1/v2 policy records.
Repeat canonical analysis with immutable-output checking. No policy/FULL run,
enrollment, candidate, seed, simulator, budget or advancement threshold changes.
This repairs evidence verification, not an unfavorable physical result.
