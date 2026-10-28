# Level C leave-one-base-out evaluation

Data: 165 instances, 12 bases, 10 tools; target = measured repair (walking fraction >= 0.75). Base-clustered bootstrap (1000 reps, seed 20261017) 95% CIs in brackets. Test = an unseen base; standardisation, k, lambda (logistic inner leave-one-base-out CV over [1.0, 3.0, 10.0, 30.0, 100.0]) fitted on training bases only. Instances with no repairing tool (56) are excluded from top-k/MRR but counted in Brier/log-loss. Mean fraction of tools that repair: 0.194.

## Setting `obs` (information cost 4 rollouts (initial observation))

| model | top-1 | top-3 | MRR | Brier | log-loss |
|---|---|---|---|---|---|
| prior | 0.394 [0.284, 0.509] | 0.752 [0.687, 0.806] | 0.606 [0.538, 0.672] | 0.149 [0.129, 0.168] | 0.460 |
| knn | 0.560 [0.471, 0.659] | 0.807 [0.718, 0.908] | 0.706 [0.639, 0.783] | 0.153 [0.127, 0.179] | 0.751 |
| logistic | 0.587 [0.516, 0.671] | 0.817 [0.761, 0.890] | 0.727 [0.680, 0.790] | 0.135 [0.115, 0.156] | 0.415 |
| mlp_ensemble | 0.541 [0.418, 0.658] | 0.789 [0.721, 0.856] | 0.691 [0.622, 0.768] | 0.135 [0.114, 0.154] | 0.413 |
| expert_rules | 0.394 [0.264, 0.512] | 0.688 [0.584, 0.771] | 0.594 [0.505, 0.674] | n/a | n/a |
| random | 0.283 [0.245, 0.314] | 0.582 [0.531, 0.623] | 0.485 [0.450, 0.515] | n/a | n/a |
| logistic_shuffled | 0.453 (range 0.330-0.532) | 0.792 (range 0.743-0.835) | 0.642 (range 0.567-0.690) | 0.161 (range 0.156-0.167) | 0.496 |
| mlp_ensemble_shuffled | 0.394 (range 0.358-0.422) | 0.765 (range 0.752-0.780) | 0.607 (range 0.592-0.618) | 0.149 (range 0.148-0.150) | 0.462 |

Strongest simple baseline by top-1: **knn**.

Paired differences in top-1 (model A - B; base-clustered 95% CI):

| A - B | top-1 diff | top-3 diff | MRR diff |
|---|---|---|---|
| logistic - expert_rules | +0.193 [+0.040, +0.358] | +0.128 [+0.031, +0.232] | +0.133 [+0.035, +0.236] |
| logistic - knn | +0.028 [-0.020, +0.086] | +0.009 [-0.074, +0.069] | +0.021 [-0.010, +0.056] |
| logistic - prior | +0.193 [+0.123, +0.263] | +0.064 [+0.009, +0.140] | +0.121 [+0.085, +0.169] |
| mlp_ensemble - expert_rules | +0.147 [-0.043, +0.322] | +0.101 [+0.046, +0.173] | +0.097 [-0.017, +0.203] |
| mlp_ensemble - knn | -0.018 [-0.117, +0.074] | -0.018 [-0.108, +0.064] | -0.015 [-0.065, +0.034] |
| mlp_ensemble - prior | +0.147 [+0.080, +0.204] | +0.037 [-0.025, +0.107] | +0.085 [+0.051, +0.123] |
| knn - expert_rules | +0.165 [+0.017, +0.341] | +0.119 [+0.009, +0.231] | +0.112 [+0.017, +0.222] |
| knn - prior | +0.165 [+0.083, +0.248] | +0.055 [-0.027, +0.165] | +0.100 [+0.056, +0.151] |

Verdict (generated from the CIs):

- logistic is NOT distinguishable from knn (strongest simple baseline) on top-1 (+0.028, CI [-0.020, +0.086]).
- mlp_ensemble is NOT distinguishable from knn (strongest simple baseline) on top-1 (-0.018, CI [-0.117, +0.074]).
- logistic BEATS expert_rules on top-1 (+0.193, CI [+0.040, +0.358]).
- mlp_ensemble is NOT distinguishable from expert_rules on top-1 (+0.147, CI [-0.043, +0.322]).
- knn BEATS expert_rules on top-1 (+0.165, CI [+0.017, +0.341]).

Overconfidence (top-1 probability >= 0.7 while that tool does not repair) and uncertainty:

| model | confident picks | confident & wrong | AUROC(low p flags miss) | mean p hit / miss |
|---|---|---|---|---|
| prior | 0 | 0 | 0.366 | 0.318 / 0.324 |
| knn | 52 | 21 | 0.716 | 0.704 / 0.487 |
| logistic | 9 | 5 | 0.684 | 0.505 / 0.401 |
| mlp_ensemble | 3 | 3 | 0.688 | 0.432 / 0.333 |

MLP ensemble spread of the top-1 tool: mean 0.003 for hits vs 0.004 for misses; AUROC(high spread flags a miss) = 0.550 (0.5 = no information).

Reliability (pooled over tools; 5 bins):

- logistic: 0.0-0.2: n=1011, pred 0.08, obs 0.09; 0.2-0.4: n=446, pred 0.30, obs 0.32; 0.4-0.6: n=150, pred 0.47, obs 0.43; 0.6-0.8: n=36, pred 0.66, obs 0.69; 0.8-1.0: n=7, pred 0.84, obs 0.14
- mlp_ensemble: 0.0-0.2: n=988, pred 0.08, obs 0.08; 0.2-0.4: n=492, pred 0.30, obs 0.35; 0.4-0.6: n=154, pred 0.47, obs 0.39; 0.6-0.8: n=16, pred 0.65, obs 0.50
- knn: 0.0-0.2: n=1032, pred 0.05, obs 0.10; 0.2-0.4: n=274, pred 0.29, obs 0.25; 0.4-0.6: n=171, pred 0.48, obs 0.32; 0.6-0.8: n=95, pred 0.69, obs 0.43; 0.8-1.0: n=78, pred 0.91, obs 0.63
- prior: 0.0-0.2: n=705, pred 0.08, obs 0.09; 0.2-0.4: n=945, pred 0.28, obs 0.27

Learning curve (top-1 vs number of training bases; mean over random base subsets):

| bases | prior | knn | logistic (fixed lambda) | mlp_ensemble |
|---|---|---|---|---|
| 3 | 0.360 | 0.444 | 0.475 | 0.483 |
| 6 | 0.341 | 0.505 | 0.558 | 0.503 |
| 9 | 0.361 | 0.552 | 0.571 | 0.569 |
| 11 | 0.394 | 0.560 | 0.578 | 0.541 |

Per-fault top-1 (fault labels used for this breakdown only):

| fault | n (with repair) | prior | knn | logistic | mlp_ensemble | expert_rules | random |
|---|---|---|---|---|---|---|---|
| cadence_fast | 8 (7) | 0.43 | 0.71 | 0.57 | 0.57 | 0.57 | 0.49 |
| feedback_loss | 42 (21) | 0.19 | 0.67 | 0.57 | 0.52 | 0.43 | 0.20 |
| heavy_torso | 10 (10) | 0.50 | 0.50 | 0.70 | 0.50 | 0.60 | 0.36 |
| placement_loss | 20 (20) | 0.75 | 0.75 | 0.70 | 0.85 | 0.15 | 0.16 |
| posture_lean | 15 (15) | 0.47 | 0.67 | 0.80 | 0.67 | 0.67 | 0.51 |
| short_feet | 4 (4) | 0.25 | 0.75 | 0.75 | 0.75 | 0.25 | 0.25 |
| slippery | 35 (21) | 0.24 | 0.19 | 0.24 | 0.24 | 0.29 | 0.26 |
| weak_motors | 31 (11) | 0.27 | 0.45 | 0.64 | 0.36 | 0.36 | 0.20 |

## Setting `obs+cf` (information cost 36 rollouts (observation + 9 counterfactuals))

| model | top-1 | top-3 | MRR | Brier | log-loss |
|---|---|---|---|---|---|
| prior | 0.394 [0.284, 0.509] | 0.752 [0.687, 0.806] | 0.606 [0.538, 0.672] | 0.149 [0.129, 0.168] | 0.460 |
| knn | 0.633 [0.569, 0.713] | 0.807 [0.729, 0.890] | 0.747 [0.693, 0.813] | 0.130 [0.108, 0.150] | 0.641 |
| logistic | 0.661 [0.575, 0.764] | 0.862 [0.814, 0.924] | 0.779 [0.719, 0.850] | 0.116 [0.099, 0.133] | 0.365 |
| mlp_ensemble | 0.670 [0.579, 0.776] | 0.872 [0.807, 0.938] | 0.784 [0.721, 0.856] | 0.116 [0.099, 0.133] | 0.365 |
| expert_rules | 0.394 [0.264, 0.512] | 0.688 [0.584, 0.771] | 0.594 [0.505, 0.674] | n/a | n/a |
| cf_heuristic | 0.587 [0.495, 0.694] | 0.826 [0.745, 0.912] | 0.726 [0.656, 0.804] | n/a | n/a |
| random | 0.283 [0.245, 0.314] | 0.582 [0.531, 0.623] | 0.485 [0.450, 0.515] | n/a | n/a |
| logistic_shuffled | 0.446 (range 0.385-0.541) | 0.798 (range 0.789-0.807) | 0.637 (range 0.597-0.687) | 0.167 (range 0.166-0.169) | 0.521 |
| mlp_ensemble_shuffled | 0.440 (range 0.404-0.495) | 0.804 (range 0.771-0.835) | 0.635 (range 0.619-0.663) | 0.151 (range 0.149-0.153) | 0.466 |

Strongest simple baseline by top-1: **knn**.

Paired differences in top-1 (model A - B; base-clustered 95% CI):

| A - B | top-1 diff | top-3 diff | MRR diff |
|---|---|---|---|
| logistic - cf_heuristic | +0.073 [+0.017, +0.135] | +0.037 [-0.017, +0.099] | +0.053 [+0.015, +0.096] |
| logistic - expert_rules | +0.266 [+0.098, +0.456] | +0.174 [+0.099, +0.264] | +0.184 [+0.076, +0.302] |
| logistic - knn | +0.028 [-0.055, +0.124] | +0.055 [+0.000, +0.110] | +0.032 [-0.017, +0.087] |
| logistic - prior | +0.266 [+0.164, +0.396] | +0.110 [+0.026, +0.200] | +0.173 [+0.099, +0.261] |
| mlp_ensemble - cf_heuristic | +0.083 [+0.017, +0.152] | +0.046 [-0.017, +0.105] | +0.058 [+0.011, +0.109] |
| mlp_ensemble - expert_rules | +0.275 [+0.115, +0.462] | +0.183 [+0.125, +0.253] | +0.190 [+0.091, +0.299] |
| mlp_ensemble - knn | +0.037 [-0.051, +0.131] | +0.064 [-0.011, +0.132] | +0.037 [-0.015, +0.092] |
| mlp_ensemble - prior | +0.275 [+0.171, +0.400] | +0.119 [+0.044, +0.208] | +0.178 [+0.109, +0.262] |
| knn - cf_heuristic | +0.046 [-0.058, +0.136] | -0.018 [-0.083, +0.056] | +0.021 [-0.048, +0.089] |
| knn - expert_rules | +0.239 [+0.128, +0.360] | +0.119 [+0.015, +0.235] | +0.153 [+0.068, +0.239] |
| knn - prior | +0.239 [+0.135, +0.387] | +0.055 [-0.065, +0.171] | +0.141 [+0.071, +0.233] |

Verdict (generated from the CIs):

- logistic is NOT distinguishable from knn (strongest simple baseline) on top-1 (+0.028, CI [-0.055, +0.124]).
- mlp_ensemble is NOT distinguishable from knn (strongest simple baseline) on top-1 (+0.037, CI [-0.051, +0.131]).
- logistic BEATS cf_heuristic on top-1 (+0.073, CI [+0.017, +0.135]).
- mlp_ensemble BEATS cf_heuristic on top-1 (+0.083, CI [+0.017, +0.152]).
- knn is NOT distinguishable from cf_heuristic on top-1 (+0.046, CI [-0.058, +0.136]).
- logistic BEATS expert_rules on top-1 (+0.266, CI [+0.098, +0.456]).
- mlp_ensemble BEATS expert_rules on top-1 (+0.275, CI [+0.115, +0.462]).
- knn BEATS expert_rules on top-1 (+0.239, CI [+0.128, +0.360]).

Overconfidence (top-1 probability >= 0.7 while that tool does not repair) and uncertainty:

| model | confident picks | confident & wrong | AUROC(low p flags miss) | mean p hit / miss |
|---|---|---|---|---|
| prior | 0 | 0 | 0.366 | 0.318 / 0.324 |
| knn | 51 | 11 | 0.784 | 0.737 / 0.444 |
| logistic | 42 | 8 | 0.797 | 0.636 / 0.383 |
| mlp_ensemble | 32 | 5 | 0.770 | 0.566 / 0.339 |

MLP ensemble spread of the top-1 tool: mean 0.007 for hits vs 0.007 for misses; AUROC(high spread flags a miss) = 0.440 (0.5 = no information).

Reliability (pooled over tools; 5 bins):

- logistic: 0.0-0.2: n=1102, pred 0.07, obs 0.08; 0.2-0.4: n=285, pred 0.29, obs 0.25; 0.4-0.6: n=129, pred 0.48, obs 0.50; 0.6-0.8: n=84, pred 0.70, obs 0.64; 0.8-1.0: n=50, pred 0.87, obs 0.80
- mlp_ensemble: 0.0-0.2: n=1076, pred 0.07, obs 0.08; 0.2-0.4: n=318, pred 0.28, obs 0.28; 0.4-0.6: n=134, pred 0.48, obs 0.45; 0.6-0.8: n=83, pred 0.70, obs 0.70; 0.8-1.0: n=39, pred 0.87, obs 0.74
- knn: 0.0-0.2: n=1092, pred 0.03, obs 0.08; 0.2-0.4: n=213, pred 0.29, obs 0.26; 0.4-0.6: n=156, pred 0.48, obs 0.37; 0.6-0.8: n=99, pred 0.65, obs 0.52; 0.8-1.0: n=90, pred 0.90, obs 0.70
- prior: 0.0-0.2: n=705, pred 0.08, obs 0.09; 0.2-0.4: n=945, pred 0.28, obs 0.27

Learning curve (top-1 vs number of training bases; mean over random base subsets):

| bases | prior | knn | logistic (fixed lambda) | mlp_ensemble |
|---|---|---|---|---|
| 3 | 0.360 | 0.525 | 0.554 | 0.527 |
| 6 | 0.341 | 0.587 | 0.611 | 0.618 |
| 9 | 0.361 | 0.626 | 0.646 | 0.635 |
| 11 | 0.394 | 0.633 | 0.651 | 0.670 |

Per-fault top-1 (fault labels used for this breakdown only):

| fault | n (with repair) | prior | knn | logistic | mlp_ensemble | expert_rules | cf_heuristic | random |
|---|---|---|---|---|---|---|---|---|
| cadence_fast | 8 (7) | 0.43 | 0.71 | 0.57 | 0.57 | 0.57 | 0.57 | 0.49 |
| feedback_loss | 42 (21) | 0.19 | 0.67 | 0.76 | 0.76 | 0.43 | 0.62 | 0.20 |
| heavy_torso | 10 (10) | 0.50 | 0.50 | 0.70 | 0.60 | 0.60 | 0.60 | 0.36 |
| placement_loss | 20 (20) | 0.75 | 0.85 | 0.90 | 0.90 | 0.15 | 0.90 | 0.16 |
| posture_lean | 15 (15) | 0.47 | 0.73 | 0.87 | 0.87 | 0.67 | 0.87 | 0.51 |
| short_feet | 4 (4) | 0.25 | 0.75 | 1.00 | 1.00 | 0.25 | 0.50 | 0.25 |
| slippery | 35 (21) | 0.24 | 0.48 | 0.19 | 0.24 | 0.29 | 0.24 | 0.26 |
| weak_motors | 31 (11) | 0.27 | 0.36 | 0.55 | 0.64 | 0.36 | 0.27 | 0.20 |

## Notes

- Shuffled controls permute the training targets within the training fold (3 repeats, logistic with fixed lambda 10); they keep the per-tool base rates, so their natural chance level is the `prior` row (not `random`); any lift above prior would indicate a leak.
- The MLP ensemble members differ only by initialisation and agree closely, so their spread is tiny and carries no signal; the predicted probability itself is the usable confidence (AUROC column).
- Bases are strongly unequal in size (5 to 20 instances) and instances within a base share a body, so the effective sample size is the number of bases (12); CIs are wide.
- The cf_heuristic ranks only tools with an available counterfactual (stride has none) and puts the rest after them.
