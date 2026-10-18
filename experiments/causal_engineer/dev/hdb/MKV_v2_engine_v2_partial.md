# Mechanism-Knowledge Value study (dev, NO_AI): same pipeline, different mechanism information

Instances: 21.

| condition | FULL | PARTIAL | NOT | mean walking (validation) |
|---|---|---|---|---|
| K2 | 7/21 | 4 | 10 | 0.75 |
| K1 | 2/21 | 11 | 8 | 0.72 |
| K3 | 1/21 | 8 | 12 | 0.60 |
| K0n | 3/19 | 8 | 8 | 0.58 |
| K4 | 3/18 | 7 | 8 | 0.68 |
| K0 | 5/18 | 9 | 4 | 0.73 |

Paired contrasts on FULL (exact one-sided McNemar; development only, not a registered test):

- K1 vs K3: n 21, K1 only 2, K3 only 1, p = 0.500
- K1 vs K0: n 18, K1 only 0, K0 only 3, p = 1.000
- K1 vs K0n: n 19, K1 only 1, K0n only 2, p = 0.875
- K2 vs K1: n 21, K2 only 5, K1 only 0, p = 0.031
- K4 vs K0: n 18, K4 only 1, K0 only 3, p = 0.938
- K4 vs K3: n 18, K4 only 2, K3 only 0, p = 0.250

