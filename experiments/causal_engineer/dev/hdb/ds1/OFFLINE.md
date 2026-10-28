# DS-1 offline stage (development; init experience bases only)

Engine-v5 records on init bases: 219 single-mechanism, 12 development compositions.

## 1. Temperature

- T = 6.0 (grid (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0), chosen on all init singles; LOBO mean log P(truth) -1.884 vs -2.392 at T = 1)
- confident-but-wrong (>= 0.95 on a wrong structure): 56 at T = 1 -> 7 at T = 6.0, of 219

## 2. Structural misfit threshold

- threshold = 5th percentile of the leader's log-likelihood per diagnostic seed on 146 correctly diagnosed init singles: -6.532
- flag rate: all init singles 0.1282051282051282; init development compositions 0.4 (n = 10)

## 3. R-head data

- 947 verified (situation, tool, outcome) rows on 231 init instances: {'engine_final': 231, 'engine_old': 304, 'a0': 219, 'diverse': 193}; FULL rate 0.34. Excluded: 259 oracle-informed MKV designs.
- Selection bias: outcomes exist only for tools some procedure chose (missing not at random); engine-final tools had the full pipeline, other rows other budgets. Procedure is a covariate, and decisions are compared only among tools whose outcome is known on the same instance.

## 4. Leave-one-base-out probability quality

| model | log loss | Brier | ECE |
|---|---|---|---|
| b0 | 0.6539 | 0.2302 | 0.000 |
| b1 | 0.6089 | 0.2105 | 0.025 |
| b2 | 0.6395 | 0.2256 | 0.057 |
| full | 0.5679 | 0.1914 | 0.030 |
| case_attention | 0.6117 | 0.2133 | 0.024 |

Reliability of the R-head (mean predicted, observed, n per bin): [(0.11, 0.148, 332), (0.295, 0.297, 232), (0.493, 0.461, 219), (0.683, 0.658, 146), (0.819, 0.556, 18)]

## 5. Decision quality on comparable support

Instances with the engine's own final tool outcome known and >= 1 other known tool: 194. Expected FULL of each chooser's pick among the known tools (mean of that tool's known outcomes on the instance):

- engine: 89.3
- full: 85.7
- b1: 83.9
- case_attention: 74.4
- random: 70.6
- R-head minus engine: base-bootstrap 90 % CI [-9.3, 1.9]
- Caveat: the engine's choice is scored by its own full-pipeline outcome; alternatives by outcomes from other procedures (older engines, A0, diverse repairs), which this comparison cannot equalise.

## 6. Gate G-a

**NOT PASSED** (R-head LOBO log loss < B1 AND comparable-support FULL >= engine).

## 7. Initial case store

- 947 verified repair cases, 535 investigation summaries (dossier support), 29 earlier scientist decisions (Stage-2 pilots on init bases, agent v1-v4).
