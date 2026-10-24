# P05-SV0 run report (CF-V2-P05-SV0 revision 4)

**Classification: PASS**

| check | status |
|---|---|
| SV0-0 provenance and environment preflight | PASS |
| SV0-1 hand-computed reference fixtures on the exact P0 functions | PASS |
| SV0-2 independent pure-Python reference vs the exact P0 pipeline | PASS |
| SV0-3 refit wrapper: identity, duplicates, edge cases | PASS |
| SV0-4 label relabelling | PASS |
| SV0-5 H4 non-degeneracy calculator (amendment 2.2 Lemmas 1-7, erratum E2) | PASS |
| SV0-6 generator and archived regression | PASS |
| SV0-7 interval constructors (fixtures; no coverage) | PASS |
| SV0-8 guards and process determinism | PASS |

## Items not passing (verbatim)

- none

## SV0-4c row-block reorder (diagnostic, not gated)

- 4c B0 order 0 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B0 order 0 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B0 order 1 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B0 order 1 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B0 order 2 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B0 order 2 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B1 order 0 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B1 order 0 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B1 order 1 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B1 order 1 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B1 order 2 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B1 order 2 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B2 order 0 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B2 order 0 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B2 order 1 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B2 order 1 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B2 order 2 interv: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}
- 4c B2 order 2 obs_morph: {"k_agreement": 1.0, "max_abs_dP": 0.0, "pick_agreement": 1.0}

Cross-process determinism (SV0-8) is verified outside the process with `cmp` of the two runs' sv0_results.json.

SV0 verifies implementation correctness and determinism on synthetic fixtures only; it establishes no coverage, inference validity or transfer.
