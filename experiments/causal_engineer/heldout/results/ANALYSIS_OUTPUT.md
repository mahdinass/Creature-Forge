# Held-out evaluation: analysis output (generated, single run)

Registered instances: 40; result rows outside the registry ignored: 0.

| arm | FULL | PARTIAL | NOT | ERROR | mean walking | rollouts | chose repairing tool | first repair repairs | diag (injected) | diag (repair-consistent) | LLM $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exhaustive | 23 | 7 | 10 | 0 | 0.85 | 689 | 38/40 | 36/40 | 0/0 | 0/0 | 0.00 |
| expert | 6 | 19 | 15 | 0 | 0.61 | 690 | 31/40 | 22/40 | 0/0 | 0/0 | 0.00 |
| learned | 18 | 13 | 9 | 0 | 0.83 | 688 | 37/40 | 33/40 | 0/0 | 0/0 | 0.00 |
| random | 12 | 10 | 18 | 0 | 0.62 | 690 | 28/40 | 17/40 | 0/0 | 0/0 | 0.00 |
| scientist_1shot_think | 2 | 9 | 29 | 0 | 0.26 | 137 | 12/40 | 10/40 | 1/15 | 8/15 | 0.88 |
| scientist_think | 2 | 2 | 36 | 0 | 0.15 | 62 | 7/40 | 6/40 | 0/5 | 2/5 | 2.90 |
| scientist_think_mem | 2 | 2 | 36 | 0 | 0.10 | 69 | 6/40 | 6/40 | 1/3 | 1/3 | 3.04 |
| scientist_think_mem_learned | 2 | 5 | 33 | 0 | 0.15 | 75 | 7/40 | 7/40 | 2/3 | 2/3 | 2.96 |

| test | A | B | A only / B only (or above / below) | p (one-sided) | Holm threshold | null rejected |
|---|---|---|---|---|---|---|
| C1 | scientist_think accuracy | majority-direction baseline | 3 / 4 | 0.7734 | 0.0167 | False |
| C2 | scientist_think | scientist_1shot_think | 2 / 2 | 0.6875 | 0.0083 | False |
| C3 | scientist_think | exhaustive | 0 / 21 | 1.0000 | 0.0500 | False |
| C4 | scientist_think_mem | scientist_think | 1 / 1 | 0.7500 | 0.0125 | False |
| C5a | learned | exhaustive | 1 / 6 | 0.9922 | 0.0250 | False |
| C5b | scientist_think_mem_learned | scientist_think_mem | 2 / 2 | 0.6875 | 0.0100 | False |
