# P0.5 rev. 2.2 amendment: exact arithmetic (NOT measured Creature Forge properties)

## P. Within-group permutation controls (exact)

| m_inst | scheme | perms per base | expected fraction of rows moved | P(base untouched) | distinct joint perms (G-1 = 27) | P(some of 20 draws coincide) |
|---|---|---|---|---|---|---|
| 1 | uniform | 1 | 0.000 | 1.000 | 1 | 1 |
| 1 | derangement | 0 | 0.000 | 1.000 | 1 | 1 |
| 2 | uniform | 2 | 0.500 | 0.500 | 1.34e+08 | 1.42e-06 |
| 2 | derangement | 1 | 1.000 | 0.000 | 1 | 1 |
| 3 | uniform | 6 | 0.667 | 0.167 | 1.02e+21 | 0 |
| 3 | derangement | 2 | 1.000 | 0.000 | 1.34e+08 | 1.42e-06 |

## S. (base, severity-bin) strata: fraction of bases where S-family-free can move anything

| m_inst | K bins | uniform independent bins | severity-balanced draw (adversarial, valid) |
|---|---|---|---|
| 2 | 2 | 0.500 | 0.000 |
| 2 | 3 | 0.333 | 0.000 |
| 3 | 2 | 1.000 | 1.000 |
| 3 | 3 | 0.778 | 0.000 |

## R. Population options: generator composition, pilot representativeness and confirmatory bases

TV = total-variation distance between pilot and population generator shares (0 = identical, 1 = disjoint).

| option | population (by generator) | pilot | confirmatory bases lost | confirmatory G | TV(pilot, population) | MDE q=.30 rho=.3 infl=2.25, 2 / 3 per base | M_nmg same |
|---|---|---|---|---|---|---|---|
| P-A | {'hdb-v1': 18} | 6 T3 bases (hdb-v1) | 0 | 18 | 0.00 | n/a / n/a | 0.406 / 0.368 |
| P-B / T2 pilot | {'hdb-v1': 34} | 6 T2 bases (2 hand + 4 walkrec) | 0 | 34 | 1.00 | 0.256 / 0.236 | 0.289 / 0.262 |
| P-B / T1-panel pilot (recommended default) | {'hdb-v1': 34} | 6 of the 12 T1-panel bases (hdb-v1) | 6 | 28 | 0.00 | 0.276 / 0.256 | 0.320 / 0.290 |
| P-C / stratified pilot | {'hdb-v1': 34, 'walkrec-m1': 8, 'hand': 4} | 4 hdb-v1 + 1 walkrec + 1 hand from the population | 6 | 40 | 0.08 | 0.239 / 0.220 | 0.266 / 0.241 |

## Z. Stage 0b sequential physics validation (NOT executed): rollout-equivalents per step

### cost set low (B = 160, n_train = 4)

| step | new repair executions | step RE | cumulative RE |
|---|---|---|---|
| 1 sentinel reproduction (one stored A1e6 episode) | 0 | 3,134 | 3,134 |
| 2 one instance x 2 tools (dims 1 and 5) x 1 seed x arms {D, 0, D'} | 6 | 1,227 | 4,361 |
| 3 instrumentation neutrality: step-2 arm 0 rerun without hooks | 2 | 382 | 4,744 |
| 4 same instance, remaining 8 tools x 1 seed x 3 arms | 24 | 4,589 | 9,332 |
| 5 three instances x 10 tools x 2 seeds x 3 arms, minus steps 2-4 | 150 | 28,840 | 38,172 |

### cost set mid (B = 300, n_train = 8)

| step | new repair executions | step RE | cumulative RE |
|---|---|---|---|
| 1 sentinel reproduction (one stored A1e6 episode) | 0 | 3,134 | 3,134 |
| 2 one instance x 2 tools (dims 1 and 5) x 1 seed x arms {D, 0, D'} | 6 | 2,334 | 5,468 |
| 3 instrumentation neutrality: step-2 arm 0 rerun without hooks | 2 | 725 | 6,193 |
| 4 same instance, remaining 8 tools x 1 seed x 3 arms | 24 | 8,698 | 14,891 |
| 5 three instances x 10 tools x 2 seeds x 3 arms, minus steps 2-4 | 150 | 54,680 | 69,571 |

### cost set high (B = 700, n_train = 8)

| step | new repair executions | step RE | cumulative RE |
|---|---|---|---|
| 1 sentinel reproduction (one stored A1e6 episode) | 0 | 3,134 | 3,134 |
| 2 one instance x 2 tools (dims 1 and 5) x 1 seed x arms {D, 0, D'} | 6 | 4,792 | 7,926 |
| 3 instrumentation neutrality: step-2 arm 0 rerun without hooks | 2 | 1,544 | 9,470 |
| 4 same instance, remaining 8 tools x 1 seed x 3 arms | 24 | 18,528 | 27,998 |
| 5 three instances x 10 tools x 2 seeds x 3 arms, minus steps 2-4 | 150 | 116,120 | 144,118 |

