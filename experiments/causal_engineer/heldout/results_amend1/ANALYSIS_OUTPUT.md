# Held-out evaluation: analysis output (generated, single run)

Registered instances: 40; result rows outside the registry ignored: 0.

| arm | FULL | PARTIAL | NOT | ERROR | mean walking | rollouts | chose repairing tool | first repair repairs | diag (injected) | diag (repair-consistent) | LLM $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exhaustive | 23 | 7 | 10 | 0 | 0.85 | 689 | 38/40 | 36/40 | 0/0 | 0/0 | 0.00 |
| expert | 6 | 19 | 15 | 0 | 0.61 | 690 | 31/40 | 22/40 | 0/0 | 0/0 | 0.00 |
| learned | 18 | 13 | 9 | 0 | 0.83 | 688 | 37/40 | 33/40 | 0/0 | 0/0 | 0.00 |
| random | 12 | 10 | 18 | 0 | 0.62 | 690 | 28/40 | 17/40 | 0/0 | 0/0 | 0.00 |
| scientist_1shot_think | 8 | 17 | 15 | 0 | 0.60 | 381 | 30/40 | 21/40 | 9/40 | 22/40 | 0.29 |
| scientist_think | 14 | 12 | 14 | 0 | 0.69 | 317 | 34/40 | 23/40 | 11/34 | 19/34 | 3.70 |
| scientist_think_mem | 16 | 14 | 10 | 0 | 0.74 | 359 | 35/40 | 29/40 | 9/27 | 16/27 | 4.23 |
| scientist_think_mem_learned | 14 | 16 | 10 | 0 | 0.75 | 362 | 34/40 | 26/40 | 11/33 | 20/33 | 4.17 |

| test | A | B | A only / B only (or above / below) | p (one-sided) | Holm threshold | null rejected |
|---|---|---|---|---|---|---|
| C1 | scientist_think accuracy | majority-direction baseline | 14 / 23 | 0.9506 | 0.0167 | False |
| C2 | scientist_think | scientist_1shot_think | 10 / 4 | 0.0898 | 0.0083 | False |
| C3 | scientist_think | exhaustive | 2 / 11 | 0.9983 | 0.0500 | False |
| C4 | scientist_think_mem | scientist_think | 6 / 4 | 0.3770 | 0.0100 | False |
| C5a | learned | exhaustive | 1 / 6 | 0.9922 | 0.0250 | False |
| C5b | scientist_think_mem_learned | scientist_think_mem | 5 / 7 | 0.8062 | 0.0125 | False |
