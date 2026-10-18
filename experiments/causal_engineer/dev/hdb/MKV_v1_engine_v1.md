# Mechanism-Knowledge Value study (dev, NO_AI): same pipeline, different mechanism information

Instances: 9.

| condition | FULL | PARTIAL | NOT | mean walking (validation) |
|---|---|---|---|---|
| K2 | 0/9 | 4 | 5 | 0.53 |
| K1 | 0/9 | 3 | 6 | 0.62 |
| K3 | 1/9 | 4 | 4 | 0.50 |
| K0n | 1/8 | 2 | 5 | 0.48 |
| K4 | 0/6 | 1 | 5 | 0.64 |
| K0 | 0/5 | 2 | 3 | 0.37 |

Paired contrasts on FULL (exact one-sided McNemar; development only, not a registered test):

- K1 vs K3: n 9, K1 only 0, K3 only 1, p = 1.000
- K1 vs K0: n 5, K1 only 0, K0 only 0, p = 1.000
- K1 vs K0n: n 8, K1 only 0, K0n only 1, p = 1.000
- K2 vs K1: n 9, K2 only 0, K1 only 0, p = 1.000
- K4 vs K0: n 5, K4 only 0, K0 only 0, p = 1.000
- K4 vs K3: n 6, K4 only 0, K3 only 1, p = 1.000

