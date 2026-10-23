# P0.5 A0 cost and precision model (B = 300, 8 train seeds, 3 instances per base; NOT executed; [ASSUMP])

## 1. Units

- Independent confirmatory bases G = 28 (the unit of inference); instances = 84 (3 per base, NOT independent); pilot bases = 6 (excluded from confirmatory analysis).
- Budget-feasible tools at B = 300 / 336 / 340 with 8 train seeds: 10 / 10 / 10 (bounds feasibility per robot is UNKNOWN until the E-check).
- Verification per cell: 62.4 RE (p_pass = 0.3 [ASSUMP], original not cached); cell = B + verification = 362.4 RE; prefix = 80 RE.

## 2. Rollout-equivalents (RE) by stage

RE: one 10 s plant or twin rollout = 1; one 20 s confirmation rollout = 2.

| stage | count | RE |
|---|---|---|
| Stage 0b (local physics, $0 cloud; 182 repair executions + sentinel) | 182 executions | 69,571 |
| Stage E for 16 bases (16 = all T3; 34 = every P-B base) [UNKNOWN which are needed] | 16 bases | 16,640 |
| Stage E for 34 bases (16 = all T3; 34 = every P-B base) [UNKNOWN which are needed] | 34 bases | 35,360 |
| Pilot: 6 bases x 2 instances, full matrix R = 2, phase-2 + selector cells, 3 sentinels | 240 matrix cells | 115,645 |
| Pilot: 6 bases x 3 instances, full matrix R = 2, phase-2 + selector cells, 3 sentinels | 360 matrix cells | 168,767 |
| Campaign: 28 bases x 3 instances, full matrix, 25 % R = 2, 2 cost-matched + selector cells | 1050 matrix + 168 cost-matched + 42 selector cells | 479,130 |

## 3. VM hours and USD per stage (prices and throughput UNVERIFIED; local stages cost $0 cloud)

VM hours = RE / throughput x (1 + idle fraction) + sessions x overhead per session (each stage pays its own session overhead) [ASSUMP].

| stage | old recorded rate ($0.269/VM-h, 31.2k RE/h): VM-hours / USD | pessimistic ($0.60/VM-h, 15.6k RE/h): VM-hours / USD |
|---|---|---|
| Stage 0b (local physics, $0 cloud; 182 repair executions + sentinel) | local, $0 | local, $0 |
| Stage E for 16 bases (16 = all T3; 34 = every P-B base) [UNKNOWN which are needed] | 2.1 VM-h / $0.58 | 6.4 VM-h / $3.86 |
| Stage E for 34 bases (16 = all T3; 34 = every P-B base) [UNKNOWN which are needed] | 2.9 VM-h / $0.77 | 8.1 VM-h / $4.84 |
| Pilot: 6 bases x 2 instances, full matrix R = 2, phase-2 + selector cells, 3 sentinels | 5.9 VM-h / $1.60 | 15.0 VM-h / $9.00 |
| Pilot: 6 bases x 3 instances, full matrix R = 2, phase-2 + selector cells, 3 sentinels | 8.0 VM-h / $2.15 | 19.6 VM-h / $11.76 |
| Campaign: 28 bases x 3 instances, full matrix, 25 % R = 2, 2 cost-matched + selector cells | 19.9 VM-h / $5.36 | 46.5 VM-h / $27.88 |

## 4. Programme totals (Stage E + pilot + campaign; Stage 0b is local) and funding constraints

| scenario | old recorded rate ($0.269/VM-h, 31.2k RE/h): USD | pessimistic ($0.60/VM-h, 15.6k RE/h): USD |
|---|---|---|
| low: Stage E 16 bases + pilot 6 x 2 + campaign | $7.54 | $40.75 |
| high: Stage E 34 bases + pilot 6 x 3 + campaign | $8.28 | $44.48 |

| funding item | USD | status |
|---|---|---|
| existing infrastructure spending cap remaining | 6.595 | [HIST] $96 cap minus $89.405 ledger; binding until the owner decides A10 |
| Nebius AI Cloud VM credit | 40.04 | owner-reported 2026-10-23, unverified; a balance, NOT an authorisation |
| Nebius Token Factory credit | 47.00 | owner-reported, unverified; separate pool, not usable for VMs; P0.5 needs none |

## 5. Statistical precision at G = 28 (t-based, one-sided 0.05, power 0.80) versus D1 = 0.10

| m_inst | q | rho | infl | MDE | M_nmg (no meaningful gain shown at M) | power to detect delta = 0.10 |
|---|---|---|---|---|---|---|
| 2 | 0.15 | 0.1 | 1.0 | 0.131 | 0.139 | 0.58 |
| 2 | 0.15 | 0.1 | 2.25 | n/a | 0.208 | 0.33 |
| 2 | 0.15 | 0.1 | 2.7 | n/a | 0.228 | 0.30 |
| 2 | 0.15 | 0.3 | 1.0 | 0.141 | 0.151 | 0.52 |
| 2 | 0.15 | 0.3 | 2.25 | n/a | 0.226 | 0.30 |
| 2 | 0.15 | 0.3 | 2.7 | n/a | 0.248 | 0.27 |
| 2 | 0.3 | 0.1 | 1.0 | 0.185 | 0.196 | 0.35 |
| 2 | 0.3 | 0.1 | 2.25 | 0.259 | 0.295 | 0.21 |
| 2 | 0.3 | 0.1 | 2.7 | 0.278 | 0.323 | 0.19 |
| 2 | 0.3 | 0.3 | 1.0 | 0.199 | 0.214 | 0.32 |
| 2 | 0.3 | 0.3 | 2.25 | 0.276 | 0.320 | 0.19 |
| 2 | 0.3 | 0.3 | 2.7 | 0.295 | 0.351 | 0.17 |
| 2 | 0.42 | 0.1 | 1.0 | 0.219 | 0.232 | 0.28 |
| 2 | 0.42 | 0.1 | 2.25 | 0.307 | 0.349 | 0.17 |
| 2 | 0.42 | 0.1 | 2.7 | 0.329 | 0.382 | 0.16 |
| 2 | 0.42 | 0.3 | 1.0 | 0.235 | 0.253 | 0.25 |
| 2 | 0.42 | 0.3 | 2.25 | 0.327 | 0.379 | 0.16 |
| 2 | 0.42 | 0.3 | 2.7 | 0.350 | 0.415 | 0.14 |
| 2 | 0.5 | 0.1 | 1.0 | 0.239 | 0.254 | 0.25 |
| 2 | 0.5 | 0.1 | 2.25 | 0.335 | 0.380 | 0.16 |
| 2 | 0.5 | 0.1 | 2.7 | 0.359 | 0.417 | 0.14 |
| 2 | 0.5 | 0.3 | 1.0 | 0.257 | 0.276 | 0.23 |
| 2 | 0.5 | 0.3 | 2.25 | 0.357 | 0.413 | 0.15 |
| 2 | 0.5 | 0.3 | 2.7 | 0.381 | 0.453 | 0.13 |
| 2 | 0.6 | 0.1 | 1.0 | 0.261 | 0.278 | 0.22 |
| 2 | 0.6 | 0.1 | 2.25 | 0.367 | 0.417 | 0.14 |
| 2 | 0.6 | 0.1 | 2.7 | 0.393 | 0.456 | 0.13 |
| 2 | 0.6 | 0.3 | 1.0 | 0.281 | 0.302 | 0.20 |
| 2 | 0.6 | 0.3 | 2.25 | 0.391 | 0.453 | 0.13 |
| 2 | 0.6 | 0.3 | 2.7 | 0.418 | 0.496 | 0.12 |
| 2 | 1.0 | 0.1 | 1.0 | 0.338 | 0.359 | 0.17 |
| 2 | 1.0 | 0.1 | 2.25 | 0.474 | 0.538 | 0.12 |
| 2 | 1.0 | 0.1 | 2.7 | 0.508 | 0.589 | 0.11 |
| 2 | 1.0 | 0.3 | 1.0 | 0.363 | 0.390 | 0.15 |
| 2 | 1.0 | 0.3 | 2.25 | 0.505 | 0.585 | 0.11 |
| 2 | 1.0 | 0.3 | 2.7 | 0.539 | 0.641 | 0.10 |
| 3 | 0.15 | 0.1 | 1.0 | 0.113 | 0.118 | 0.70 |
| 3 | 0.15 | 0.1 | 2.25 | n/a | 0.178 | 0.42 |
| 3 | 0.15 | 0.1 | 2.7 | n/a | 0.195 | 0.37 |
| 3 | 0.15 | 0.3 | 1.0 | 0.129 | 0.137 | 0.59 |
| 3 | 0.15 | 0.3 | 2.25 | n/a | 0.205 | 0.34 |
| 3 | 0.15 | 0.3 | 2.7 | n/a | 0.225 | 0.30 |
| 3 | 0.3 | 0.1 | 1.0 | 0.160 | 0.167 | 0.44 |
| 3 | 0.3 | 0.1 | 2.25 | 0.228 | 0.251 | 0.26 |
| 3 | 0.3 | 0.1 | 2.7 | 0.246 | 0.275 | 0.23 |
| 3 | 0.3 | 0.3 | 1.0 | 0.182 | 0.193 | 0.36 |
| 3 | 0.3 | 0.3 | 2.25 | 0.256 | 0.290 | 0.21 |
| 3 | 0.3 | 0.3 | 2.7 | 0.275 | 0.318 | 0.19 |
| 3 | 0.42 | 0.1 | 1.0 | 0.190 | 0.198 | 0.35 |
| 3 | 0.42 | 0.1 | 2.25 | 0.270 | 0.297 | 0.21 |
| 3 | 0.42 | 0.1 | 2.7 | 0.291 | 0.326 | 0.19 |
| 3 | 0.42 | 0.3 | 1.0 | 0.216 | 0.229 | 0.29 |
| 3 | 0.42 | 0.3 | 2.25 | 0.303 | 0.343 | 0.18 |
| 3 | 0.42 | 0.3 | 2.7 | 0.325 | 0.376 | 0.16 |
| 3 | 0.5 | 0.1 | 1.0 | 0.207 | 0.216 | 0.31 |
| 3 | 0.5 | 0.1 | 2.25 | 0.295 | 0.324 | 0.19 |
| 3 | 0.5 | 0.1 | 2.7 | 0.317 | 0.355 | 0.17 |
| 3 | 0.5 | 0.3 | 1.0 | 0.235 | 0.250 | 0.25 |
| 3 | 0.5 | 0.3 | 2.25 | 0.331 | 0.375 | 0.16 |
| 3 | 0.5 | 0.3 | 2.7 | 0.355 | 0.410 | 0.15 |
| 3 | 0.6 | 0.1 | 1.0 | 0.227 | 0.237 | 0.27 |
| 3 | 0.6 | 0.1 | 2.25 | 0.323 | 0.355 | 0.17 |
| 3 | 0.6 | 0.1 | 2.7 | 0.348 | 0.389 | 0.15 |
| 3 | 0.6 | 0.3 | 1.0 | 0.258 | 0.274 | 0.23 |
| 3 | 0.6 | 0.3 | 2.25 | 0.363 | 0.410 | 0.15 |
| 3 | 0.6 | 0.3 | 2.7 | 0.389 | 0.449 | 0.13 |
| 3 | 1.0 | 0.1 | 1.0 | 0.292 | 0.306 | 0.20 |
| 3 | 1.0 | 0.1 | 2.25 | 0.417 | 0.459 | 0.13 |
| 3 | 1.0 | 0.1 | 2.7 | 0.449 | 0.502 | 0.12 |
| 3 | 1.0 | 0.3 | 1.0 | 0.333 | 0.353 | 0.17 |
| 3 | 1.0 | 0.3 | 2.25 | 0.468 | 0.530 | 0.12 |
| 3 | 1.0 | 0.3 | 2.7 | 0.502 | 0.580 | 0.11 |
