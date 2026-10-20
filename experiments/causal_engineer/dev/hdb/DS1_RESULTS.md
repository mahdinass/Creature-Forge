# DS-1 results (development only; no claim)

## dev-eval-2: single mechanism

### Diagnostic signal

| arm | n | mean log P(truth) | leading correct | ECE of leading mass | confident wrong | shares a true primitive | mean unmodelled | composite expansions (skipped) |
|---|---|---|---|---|---|---|---|---|
| A1e | 30 | -2.93 | 18 | 0.391 | 9 | 18 | 0.00 | 0 (0) |
| A1e6 | 30 | -2.54 | 19 | 0.266 | 4 | 21 | 0.14 | 8 (0) |
| A3v5 | 30 | -2.84 | 15 | 0.378 | 6 | 21 | 0.14 | 9 (2) |
| A4x | 30 | -2.25 | 18 | 0.290 | 4 | 20 | 0.15 | 9 (1) |

### Repair signal

- A1e: {"n": 30, "full": 9, "categories": {"FULL": 9, "walks, not farther than faulty": 5, "validation walking < 80 %": 14, "20 s confirmation": 2}, "mean_walking": 0.6749999999999999, "plant_used": 604.3666666666667, "twin_used": 1980.0666666666666, "rhead_brier_on_submitted": {"n": 30, "brier": 0.208602353859578}}
- A1e6: {"n": 30, "full": 8, "categories": {"FULL": 8, "walks, not farther than faulty": 6, "validation walking < 80 %": 16}, "mean_walking": 0.7027777777777777, "plant_used": 621.3, "twin_used": 2508.266666666667, "rhead_brier_on_submitted": {"n": 30, "brier": 0.18983941120717962}}
- A3v5: {"n": 30, "full": 8, "categories": {"validation walking < 80 %": 18, "walks, not farther than faulty": 2, "FULL": 8, "20 s confirmation": 2}, "mean_walking": 0.6444444444444444, "plant_used": 540.3333333333334, "twin_used": 2631.9333333333334, "nemotron_p_success": {"n": 30, "mean": 0.5233333333333333, "brier": 0.3289533333333334}, "deviation": {"episodes": 30, "deviated": 9, "full_when_deviated": 2, "full_when_delegated": 6}, "rhead_brier_on_submitted": {"n": 28, "brier": 0.15661094599264017}}
- A4x: {"n": 30, "full": 10, "categories": {"FULL": 10, "validation walking < 80 %": 15, "walks, not farther than faulty": 4, "20 s confirmation": 1}, "mean_walking": 0.7027777777777778, "plant_used": 584.5333333333333, "twin_used": 2573.4666666666667, "nemotron_p_success": {"n": 30, "mean": 0.6145666666666668, "brier": 0.29330883333333335}, "deviation": {"episodes": 30, "deviated": 3, "full_when_deviated": 2, "full_when_delegated": 8}, "rhead_brier_on_submitted": {"n": 30, "brier": 0.17854053781880996}}

### Cross-feedback (intervention outcomes folded into the belief)

- A1e: {"assimilated_checks": 0, "leader_changed": 0, "episodes_with_change": 0, "rescreens": 0, "skipped_for_budget": 0}
- A1e6: {"assimilated_checks": 76, "leader_changed": 0, "episodes_with_change": 0, "rescreens": 0, "skipped_for_budget": 7}
- A3v5: {"assimilated_checks": 33, "leader_changed": 0, "episodes_with_change": 0, "rescreens": 0, "skipped_for_budget": 42}
- A4x: {"assimilated_checks": 51, "leader_changed": 1, "episodes_with_change": 1, "rescreens": 0, "skipped_for_budget": 29}

### Paired contrasts (exact one-sided McNemar on FULL; Wilcoxon on validation walking)

- A1e vs A1e6: n 30; FULL 9 vs 8; discordant 2/1; p(A1e>A1e6) = 0.500, p(A1e6>A1e) = 0.875; walking diff -0.028 (Wilcoxon p(A1e>A1e6) = 0.829)
- A1e vs A3v5: n 30; FULL 9 vs 8; discordant 4/3; p(A1e>A3v5) = 0.500, p(A3v5>A1e) = 0.773; walking diff +0.031 (Wilcoxon p(A1e>A3v5) = 0.363)
- A1e vs A4x: n 30; FULL 9 vs 10; discordant 3/4; p(A1e>A4x) = 0.773, p(A4x>A1e) = 0.500; walking diff -0.028 (Wilcoxon p(A1e>A4x) = 0.776)
- A1e6 vs A3v5: n 30; FULL 8 vs 8; discordant 2/2; p(A1e6>A3v5) = 0.688, p(A3v5>A1e6) = 0.688; walking diff +0.058 (Wilcoxon p(A1e6>A3v5) = 0.110)
- A1e6 vs A4x: n 30; FULL 8 vs 10; discordant 1/3; p(A1e6>A4x) = 0.938, p(A4x>A1e6) = 0.312; walking diff +0.000 (Wilcoxon p(A1e6>A4x) = 0.487)
- A3v5 vs A4x: n 30; FULL 8 vs 10; discordant 1/3; p(A3v5>A4x) = 0.938, p(A4x>A3v5) = 0.312; walking diff -0.058 (Wilcoxon p(A3v5>A4x) = 0.753)

## dev-eval-2: development compositions

### Diagnostic signal

| arm | n | mean log P(truth) | leading correct | ECE of leading mass | confident wrong | shares a true primitive | mean unmodelled | composite expansions (skipped) |
|---|---|---|---|---|---|---|---|---|
| A1e | 6 | -9.21 | 0 | 0.984 | 6 | 3 | 0.00 | 0 (0) |
| A1e6 | 6 | -4.61 | 3 | 0.352 | 0 | 4 | 0.11 | 3 (0) |
| A3v5 | 6 | -4.61 | 3 | 0.451 | 1 | 4 | 0.01 | 4 (1) |
| A4x | 6 | -4.61 | 3 | 0.413 | 1 | 4 | 0.15 | 4 (0) |

### Repair signal

- A1e: {"n": 6, "full": 1, "categories": {"20 s confirmation": 1, "validation walking < 80 %": 4, "FULL": 1}, "mean_walking": 0.6736111111111112, "plant_used": 696.8333333333334, "twin_used": 2026.0, "rhead_brier_on_submitted": {"n": 6, "brier": 0.36018907443225623}}
- A1e6: {"n": 6, "full": 1, "categories": {"validation walking < 80 %": 4, "FULL": 1, "walks, not farther than faulty": 1}, "mean_walking": 0.7569444444444443, "plant_used": 583.6666666666666, "twin_used": 2575.0, "rhead_brier_on_submitted": {"n": 6, "brier": 0.16494696384505117}}
- A3v5: {"n": 6, "full": 2, "categories": {"FULL": 2, "validation walking < 80 %": 3, "walks, not farther than faulty": 1}, "mean_walking": 0.7638888888888888, "plant_used": 567.0, "twin_used": 2689.3333333333335, "nemotron_p_success": {"n": 6, "mean": 0.575, "brier": 0.28291666666666665}, "deviation": {"episodes": 6, "deviated": 1, "full_when_deviated": 1, "full_when_delegated": 1}, "rhead_brier_on_submitted": {"n": 6, "brier": 0.14695176019590342}}
- A4x: {"n": 6, "full": 1, "categories": {"validation walking < 80 %": 4, "FULL": 1, "walks, not farther than faulty": 1}, "mean_walking": 0.7777777777777777, "plant_used": 582.3333333333334, "twin_used": 2615.0, "nemotron_p_success": {"n": 6, "mean": 0.575, "brier": 0.29875}, "deviation": {"episodes": 6, "deviated": 0, "full_when_deviated": 0, "full_when_delegated": 1}, "rhead_brier_on_submitted": {"n": 6, "brier": 0.27718256699355504}}

### Cross-feedback (intervention outcomes folded into the belief)

- A1e: {"assimilated_checks": 0, "leader_changed": 0, "episodes_with_change": 0, "rescreens": 0, "skipped_for_budget": 0}
- A1e6: {"assimilated_checks": 12, "leader_changed": 0, "episodes_with_change": 0, "rescreens": 0, "skipped_for_budget": 4}
- A3v5: {"assimilated_checks": 3, "leader_changed": 0, "episodes_with_change": 0, "rescreens": 0, "skipped_for_budget": 8}
- A4x: {"assimilated_checks": 8, "leader_changed": 0, "episodes_with_change": 0, "rescreens": 0, "skipped_for_budget": 8}

### Paired contrasts (exact one-sided McNemar on FULL; Wilcoxon on validation walking)

- A1e vs A1e6: n 6; FULL 1 vs 1; discordant 0/0; p(A1e>A1e6) = 1.000, p(A1e6>A1e) = 1.000; walking diff -0.083 (Wilcoxon p(A1e>A1e6) = 0.828)
- A1e vs A3v5: n 6; FULL 1 vs 2; discordant 0/1; p(A1e>A3v5) = 1.000, p(A3v5>A1e) = 0.500; walking diff -0.090 (Wilcoxon p(A1e>A3v5) = 0.979)
- A1e vs A4x: n 6; FULL 1 vs 1; discordant 0/0; p(A1e>A4x) = 1.000, p(A4x>A1e) = 1.000; walking diff -0.104 (Wilcoxon p(A1e>A4x) = 0.932)
- A1e6 vs A3v5: n 6; FULL 1 vs 2; discordant 0/1; p(A1e6>A3v5) = 1.000, p(A3v5>A1e6) = 0.500; walking diff -0.007 (Wilcoxon p(A1e6>A3v5) = 0.658)
- A1e6 vs A4x: n 6; FULL 1 vs 1; discordant 0/0; p(A1e6>A4x) = 1.000, p(A4x>A1e6) = 1.000; walking diff -0.021 (Wilcoxon p(A1e6>A4x) = 0.977)
- A3v5 vs A4x: n 6; FULL 2 vs 1; discordant 1/0; p(A3v5>A4x) = 0.500, p(A4x>A3v5) = 1.000; walking diff -0.014 (Wilcoxon p(A3v5>A4x) = 0.644)

## Learning stream (A4x updating vs frozen experience; same instances, same order)

| round | n | FULL updating | FULL frozen | mean log P(truth) upd / frz | Nemotron P(success) Brier upd / frz | repair model Brier on this round (store before round) upd / init |
|---|---|---|---|---|---|---|
| 0 | 5 | 1 | 1 | -2.10 / -2.61 | 0.348 / 0.229 | 0.290 / 0.290 |
| 1 | 5 | 2 | 2 | -3.62 / -1.86 | 0.187 / 0.213 | 0.231 / 0.231 |
| 2 | 5 | 1 | 1 | -2.15 / -1.92 | 0.430 / 0.451 | 0.264 / 0.267 |
| 3 | 5 | 3 | 3 | -1.89 / -1.86 | 0.149 / 0.251 | 0.369 / 0.393 |

Paired over the whole stream:
- A4x-frozen vs A4x-updating: n 20; FULL 7 vs 7; discordant 2/2; p(A4x-frozen>A4x-updating) = 0.688, p(A4x-updating>A4x-frozen) = 0.688; walking diff +0.037 (Wilcoxon p(A4x-frozen>A4x-updating) = 0.206)
