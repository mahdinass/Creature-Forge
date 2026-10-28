# Level C leave-one-base-out evaluation

Data: 165 instances, 12 bases, 10 tools; target = measured repair (walking fraction >= 0.75). Base-clustered bootstrap (1000 reps, seed 20261017) 95% CIs in brackets. Test = an unseen base; standardisation, k, lambda (logistic inner leave-one-base-out CV over [1.0, 3.0, 10.0, 30.0, 100.0]) fitted on training bases only. Instances with no repairing tool (56) are excluded from top-k/MRR but counted in Brier/log-loss. Mean fraction of tools that repair: 0.194.

## Setting `obs` (information cost 4 rollouts (initial observation))

| model | top-1 | top-3 | MRR | Brier | log-loss |
|---|---|---|---|---|---|
| prior | 0.394 [0.284, 0.509] | 0.752 [0.687, 0.806] | 0.606 [0.538, 0.672] | 0.149 [0.129, 0.168] | 0.460 |
| knn | 0.550 [0.432, 0.660] | 0.826 [0.742, 0.915] | 0.702 [0.618, 0.780] | 0.159 [0.134, 0.180] | 0.752 |
| logistic | 0.560 [0.457, 0.670] | 0.826 [0.748, 0.908] | 0.714 [0.653, 0.780] | 0.136 [0.116, 0.155] | 0.417 |
| mlp_ensemble | 0.523 [0.390, 0.638] | 0.807 [0.745, 0.877] | 0.686 [0.620, 0.755] | 0.135 [0.114, 0.155] | 0.415 |
| expert_rules | 0.394 [0.264, 0.512] | 0.688 [0.584, 0.771] | 0.594 [0.505, 0.674] | n/a | n/a |
| random | 0.283 [0.245, 0.314] | 0.582 [0.531, 0.623] | 0.485 [0.450, 0.515] | n/a | n/a |
| logistic_shuffled | 0.465 (range 0.404-0.532) | 0.795 (range 0.743-0.872) | 0.652 (range 0.605-0.688) | 0.160 (range 0.155-0.166) | 0.496 |
| mlp_ensemble_shuffled | 0.416 (range 0.339-0.477) | 0.758 (range 0.743-0.780) | 0.617 (range 0.578-0.646) | 0.149 (range 0.148-0.150) | 0.461 |

Strongest simple baseline by top-1: **knn**.

Paired differences in top-1 (model A - B; base-clustered 95% CI):

| A - B | top-1 diff | top-3 diff | MRR diff |
|---|---|---|---|
| logistic - expert_rules | +0.165 [+0.007, +0.351] | +0.138 [+0.076, +0.212] | +0.120 [+0.026, +0.228] |
| logistic - knn | +0.009 [-0.092, +0.119] | +0.000 [-0.081, +0.103] | +0.012 [-0.034, +0.065] |
| logistic - prior | +0.165 [+0.057, +0.270] | +0.073 [-0.009, +0.171] | +0.108 [+0.056, +0.171] |
| mlp_ensemble - expert_rules | +0.128 [-0.077, +0.333] | +0.119 [+0.063, +0.191] | +0.092 [-0.024, +0.210] |
| mlp_ensemble - knn | -0.028 [-0.168, +0.096] | -0.018 [-0.110, +0.084] | -0.016 [-0.081, +0.046] |
| mlp_ensemble - prior | +0.128 [+0.048, +0.200] | +0.055 [-0.016, +0.139] | +0.080 [+0.039, +0.130] |
| knn - expert_rules | +0.156 [+0.035, +0.310] | +0.138 [+0.026, +0.231] | +0.108 [+0.030, +0.200] |
| knn - prior | +0.156 [+0.032, +0.288] | +0.073 [-0.008, +0.179] | +0.096 [+0.033, +0.161] |

Verdict (generated from the CIs):

- logistic is NOT distinguishable from knn (strongest simple baseline) on top-1 (+0.009, CI [-0.092, +0.119]).
- mlp_ensemble is NOT distinguishable from knn (strongest simple baseline) on top-1 (-0.028, CI [-0.168, +0.096]).
- logistic BEATS expert_rules on top-1 (+0.165, CI [+0.007, +0.351]).
- mlp_ensemble is NOT distinguishable from expert_rules on top-1 (+0.128, CI [-0.077, +0.333]).
- knn BEATS expert_rules on top-1 (+0.156, CI [+0.035, +0.310]).

Overconfidence (top-1 probability >= 0.7 while that tool does not repair) and uncertainty:

| model | confident picks | confident & wrong | AUROC(low p flags miss) | mean p hit / miss |
|---|---|---|---|---|
| prior | 0 | 0 | 0.366 | 0.318 / 0.324 |
| knn | 54 | 20 | 0.696 | 0.689 / 0.524 |
| logistic | 6 | 2 | 0.675 | 0.489 / 0.390 |
| mlp_ensemble | 2 | 2 | 0.691 | 0.442 / 0.336 |

MLP ensemble spread of the top-1 tool: mean 0.003 for hits vs 0.003 for misses; AUROC(high spread flags a miss) = 0.500 (0.5 = no information).

Reliability (pooled over tools; 5 bins):

- logistic: 0.0-0.2: n=1016, pred 0.08, obs 0.09; 0.2-0.4: n=449, pred 0.29, obs 0.32; 0.4-0.6: n=158, pred 0.48, obs 0.44; 0.6-0.8: n=27, pred 0.68, obs 0.59
- mlp_ensemble: 0.0-0.2: n=987, pred 0.08, obs 0.08; 0.2-0.4: n=502, pred 0.30, obs 0.34; 0.4-0.6: n=146, pred 0.47, obs 0.41; 0.6-0.8: n=15, pred 0.65, obs 0.47
- knn: 0.0-0.2: n=1006, pred 0.04, obs 0.12; 0.2-0.4: n=272, pred 0.30, obs 0.19; 0.4-0.6: n=200, pred 0.48, obs 0.32; 0.6-0.8: n=92, pred 0.66, obs 0.41; 0.8-1.0: n=80, pred 0.89, obs 0.60
- prior: 0.0-0.2: n=705, pred 0.08, obs 0.09; 0.2-0.4: n=945, pred 0.28, obs 0.27

Learning curve (top-1 vs number of training bases; mean over random base subsets):

| bases | prior | knn | logistic (fixed lambda) | mlp_ensemble |
|---|---|---|---|---|
| 3 | 0.360 | 0.470 | 0.459 | 0.475 |
| 6 | 0.341 | 0.483 | 0.547 | 0.516 |
| 9 | 0.361 | 0.528 | 0.567 | 0.561 |
| 11 | 0.394 | 0.550 | 0.560 | 0.523 |

Per-fault top-1 (fault labels used for this breakdown only):

| fault | n (with repair) | prior | knn | logistic | mlp_ensemble | expert_rules | random |
|---|---|---|---|---|---|---|---|
| cadence_fast | 8 (7) | 0.43 | 0.43 | 0.57 | 0.29 | 0.57 | 0.49 |
| feedback_loss | 42 (21) | 0.19 | 0.52 | 0.52 | 0.62 | 0.43 | 0.20 |
| heavy_torso | 10 (10) | 0.50 | 0.50 | 0.70 | 0.50 | 0.60 | 0.36 |
| placement_loss | 20 (20) | 0.75 | 0.75 | 0.75 | 0.85 | 0.15 | 0.16 |
| posture_lean | 15 (15) | 0.47 | 0.60 | 0.73 | 0.53 | 0.67 | 0.51 |
| short_feet | 4 (4) | 0.25 | 0.75 | 0.75 | 0.75 | 0.25 | 0.25 |
| slippery | 35 (21) | 0.24 | 0.43 | 0.24 | 0.29 | 0.29 | 0.26 |
| weak_motors | 31 (11) | 0.27 | 0.45 | 0.45 | 0.27 | 0.36 | 0.20 |

## Setting `obs+cf` (information cost 36 rollouts (observation + 9 counterfactuals))

| model | top-1 | top-3 | MRR | Brier | log-loss |
|---|---|---|---|---|---|
| prior | 0.394 [0.284, 0.509] | 0.752 [0.687, 0.806] | 0.606 [0.538, 0.672] | 0.149 [0.129, 0.168] | 0.460 |
| knn | 0.624 [0.538, 0.727] | 0.807 [0.708, 0.909] | 0.739 [0.671, 0.817] | 0.131 [0.110, 0.150] | 0.642 |
| logistic | 0.697 [0.624, 0.791] | 0.853 [0.796, 0.920] | 0.792 [0.734, 0.861] | 0.116 [0.099, 0.132] | 0.366 |
| mlp_ensemble | 0.651 [0.568, 0.750] | 0.862 [0.786, 0.937] | 0.771 [0.707, 0.843] | 0.116 [0.099, 0.133] | 0.367 |
| expert_rules | 0.394 [0.264, 0.512] | 0.688 [0.584, 0.771] | 0.594 [0.505, 0.674] | n/a | n/a |
| cf_heuristic | 0.587 [0.495, 0.694] | 0.826 [0.745, 0.912] | 0.726 [0.656, 0.804] | n/a | n/a |
| random | 0.283 [0.245, 0.314] | 0.582 [0.531, 0.623] | 0.485 [0.450, 0.515] | n/a | n/a |
| logistic_shuffled | 0.465 (range 0.413-0.523) | 0.789 (range 0.761-0.826) | 0.649 (range 0.618-0.676) | 0.167 (range 0.165-0.170) | 0.525 |
| mlp_ensemble_shuffled | 0.428 (range 0.394-0.477) | 0.823 (range 0.789-0.844) | 0.634 (range 0.625-0.651) | 0.151 (range 0.150-0.152) | 0.467 |

Strongest simple baseline by top-1: **knn**.

Paired differences in top-1 (model A - B; base-clustered 95% CI):

| A - B | top-1 diff | top-3 diff | MRR diff |
|---|---|---|---|
| logistic - cf_heuristic | +0.110 [+0.053, +0.167] | +0.028 [-0.025, +0.088] | +0.066 [+0.026, +0.110] |
| logistic - expert_rules | +0.303 [+0.150, +0.474] | +0.165 [+0.097, +0.247] | +0.198 [+0.097, +0.308] |
| logistic - knn | +0.073 [-0.009, +0.167] | +0.046 [-0.030, +0.120] | +0.053 [+0.004, +0.108] |
| logistic - prior | +0.303 [+0.190, +0.443] | +0.101 [+0.018, +0.188] | +0.186 [+0.106, +0.286] |
| mlp_ensemble - cf_heuristic | +0.064 [-0.009, +0.139] | +0.037 [-0.028, +0.102] | +0.044 [-0.004, +0.098] |
| mlp_ensemble - expert_rules | +0.257 [+0.107, +0.439] | +0.174 [+0.121, +0.245] | +0.176 [+0.080, +0.285] |
| mlp_ensemble - knn | +0.028 [-0.056, +0.116] | +0.055 [-0.040, +0.147] | +0.032 [-0.018, +0.086] |
| mlp_ensemble - prior | +0.257 [+0.156, +0.375] | +0.110 [+0.034, +0.198] | +0.165 [+0.096, +0.251] |
| knn - cf_heuristic | +0.037 [-0.069, +0.136] | -0.018 [-0.081, +0.057] | +0.013 [-0.053, +0.078] |
| knn - expert_rules | +0.229 [+0.122, +0.344] | +0.119 [+0.000, +0.240] | +0.145 [+0.064, +0.228] |
| knn - prior | +0.229 [+0.119, +0.391] | +0.055 [-0.081, +0.181] | +0.133 [+0.055, +0.230] |

Verdict (generated from the CIs):

- logistic is NOT distinguishable from knn (strongest simple baseline) on top-1 (+0.073, CI [-0.009, +0.167]).
- mlp_ensemble is NOT distinguishable from knn (strongest simple baseline) on top-1 (+0.028, CI [-0.056, +0.116]).
- logistic BEATS cf_heuristic on top-1 (+0.110, CI [+0.053, +0.167]).
- mlp_ensemble is NOT distinguishable from cf_heuristic on top-1 (+0.064, CI [-0.009, +0.139]).
- knn is NOT distinguishable from cf_heuristic on top-1 (+0.037, CI [-0.069, +0.136]).
- logistic BEATS expert_rules on top-1 (+0.303, CI [+0.150, +0.474]).
- mlp_ensemble BEATS expert_rules on top-1 (+0.257, CI [+0.107, +0.439]).
- knn BEATS expert_rules on top-1 (+0.229, CI [+0.122, +0.344]).

Overconfidence (top-1 probability >= 0.7 while that tool does not repair) and uncertainty:

| model | confident picks | confident & wrong | AUROC(low p flags miss) | mean p hit / miss |
|---|---|---|---|---|
| prior | 0 | 0 | 0.366 | 0.318 / 0.324 |
| knn | 45 | 9 | 0.765 | 0.728 / 0.455 |
| logistic | 41 | 8 | 0.770 | 0.612 / 0.385 |
| mlp_ensemble | 30 | 5 | 0.748 | 0.556 / 0.346 |

MLP ensemble spread of the top-1 tool: mean 0.006 for hits vs 0.007 for misses; AUROC(high spread flags a miss) = 0.508 (0.5 = no information).

Reliability (pooled over tools; 5 bins):

- logistic: 0.0-0.2: n=1087, pred 0.07, obs 0.09; 0.2-0.4: n=298, pred 0.28, obs 0.22; 0.4-0.6: n=134, pred 0.48, obs 0.52; 0.6-0.8: n=78, pred 0.69, obs 0.65; 0.8-1.0: n=53, pred 0.86, obs 0.75
- mlp_ensemble: 0.0-0.2: n=1077, pred 0.07, obs 0.08; 0.2-0.4: n=331, pred 0.29, obs 0.28; 0.4-0.6: n=125, pred 0.49, obs 0.49; 0.6-0.8: n=81, pred 0.70, obs 0.70; 0.8-1.0: n=36, pred 0.87, obs 0.72
- knn: 0.0-0.2: n=1094, pred 0.03, obs 0.08; 0.2-0.4: n=218, pred 0.29, obs 0.28; 0.4-0.6: n=146, pred 0.48, obs 0.36; 0.6-0.8: n=110, pred 0.65, obs 0.48; 0.8-1.0: n=82, pred 0.92, obs 0.74
- prior: 0.0-0.2: n=705, pred 0.08, obs 0.09; 0.2-0.4: n=945, pred 0.28, obs 0.27

Learning curve (top-1 vs number of training bases; mean over random base subsets):

| bases | prior | knn | logistic (fixed lambda) | mlp_ensemble |
|---|---|---|---|---|
| 3 | 0.360 | 0.532 | 0.560 | 0.543 |
| 6 | 0.341 | 0.580 | 0.617 | 0.611 |
| 9 | 0.361 | 0.629 | 0.661 | 0.642 |
| 11 | 0.394 | 0.624 | 0.661 | 0.651 |

Per-fault top-1 (fault labels used for this breakdown only):

| fault | n (with repair) | prior | knn | logistic | mlp_ensemble | expert_rules | cf_heuristic | random |
|---|---|---|---|---|---|---|---|---|
| cadence_fast | 8 (7) | 0.43 | 0.43 | 0.57 | 0.57 | 0.57 | 0.57 | 0.49 |
| feedback_loss | 42 (21) | 0.19 | 0.67 | 0.81 | 0.76 | 0.43 | 0.62 | 0.20 |
| heavy_torso | 10 (10) | 0.50 | 0.50 | 0.70 | 0.50 | 0.60 | 0.60 | 0.36 |
| placement_loss | 20 (20) | 0.75 | 0.85 | 0.90 | 0.90 | 0.15 | 0.90 | 0.16 |
| posture_lean | 15 (15) | 0.47 | 0.73 | 0.87 | 0.87 | 0.67 | 0.87 | 0.51 |
| short_feet | 4 (4) | 0.25 | 0.75 | 0.75 | 1.00 | 0.25 | 0.50 | 0.25 |
| slippery | 35 (21) | 0.24 | 0.52 | 0.38 | 0.24 | 0.29 | 0.24 | 0.26 |
| weak_motors | 31 (11) | 0.27 | 0.36 | 0.55 | 0.55 | 0.36 | 0.27 | 0.20 |

## Notes

- Shuffled controls permute the training targets within the training fold (3 repeats, logistic with fixed lambda 10); they keep the per-tool base rates, so their natural chance level is the `prior` row (not `random`); any lift above prior would indicate a leak.
- The MLP ensemble members differ only by initialisation and agree closely, so their spread is tiny and carries no signal; the predicted probability itself is the usable confidence (AUROC column).
- Bases are strongly unequal in size (5 to 20 instances) and instances within a base share a body, so the effective sample size is the number of bases (12); CIs are wide.
- The cf_heuristic ranks only tools with an available counterfactual (stride has none) and puts the rest after them.
