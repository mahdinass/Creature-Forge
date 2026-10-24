# P05-SV1 confirm report

**Classification: ADMITTED and confirmed on the independent evaluation set**

- provenance failures: none; self-test: PASS
- completeness ok: True (missing 0, errors 0, conflicts 0, partial lines 0, replay True)

| cell | n_cov | T | bias check | C0 coverage | degenerate redrawn |
|---|---|---|---|---|---|
| A-info | 200 | 2000 | True | 187/200 | 0 |
| A-null | 200 | 2000 | True | 177/200 | 0 |
| A-obs | 200 | 2000 | True | 188/200 | 0 |
| B-info | 100 | 1000 | True | 95/100 | 0 |
| B-null | 100 | 1000 | True | 85/100 | 0 |

Admitted: ['M2']; composite rule (M5) valid: True
Independent evaluation confirms admission: True

SV1 establishes coverage properties only for the synthetic calc section-E generator family and the certified fingerprint; it is necessary, not sufficient, for real-data validity.
