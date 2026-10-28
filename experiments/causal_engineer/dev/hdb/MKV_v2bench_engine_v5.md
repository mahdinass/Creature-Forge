# Mechanism-Knowledge Value study (dev, NO_AI): same pipeline, different mechanism information

Instances: 21.

| condition | FULL | PARTIAL | NOT | mean walking (validation) |
|---|---|---|---|---|
| K2 | 8/21 | 8 | 5 | 0.79 |
| K1 | 5/21 | 7 | 9 | 0.77 |
| K3 | 5/21 | 6 | 10 | 0.73 |
| K0n | 5/21 | 8 | 8 | 0.63 |
| K4 | 4/21 | 6 | 11 | 0.76 |
| K0 | 6/21 | 9 | 6 | 0.73 |

Paired contrasts on FULL (exact one-sided McNemar; development only, not a registered test):

- K1 vs K3: n 21, K1 only 3, K3 only 3, p = 0.656
- K1 vs K0: n 21, K1 only 3, K0 only 4, p = 0.773
- K1 vs K0n: n 21, K1 only 2, K0n only 2, p = 0.688
- K2 vs K1: n 21, K2 only 4, K1 only 1, p = 0.188
- K4 vs K0: n 21, K4 only 2, K0 only 4, p = 0.891
- K4 vs K3: n 21, K4 only 3, K3 only 4, p = 0.773

