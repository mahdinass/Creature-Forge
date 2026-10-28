# Stage 2 transfer evaluation (agent `stage2-agent-v4-frozen`, 18 unseen transfer bases; development only, no claim)

Generated 2026-10-20 by `scripts/hdb_agent_report.py` and a read-only analysis script over the raw records below. Non-LLM arms
(A1e, A2, A1e on compositions) ran on the batch VM, LLM arms (A3, A4, A4lfo, A4bad) on the main VM (16:01 UTC 19 Oct to
01:37 UTC 20 Oct; 40 parallel sessions with one pool worker each, so LLM-arm wall times reflect CPU contention and are
not comparable with the non-LLM arms). All 124 LLM-arm episodes are valid (no authentication failures).

## Part 1: single mechanisms (36 instances, 9 dev families x 4)

```
# Arms on the Hidden-Damage Bench (dev; development only, no claim)

| arm | n | FULL | PARTIAL | NOT | mean plant used | mean twin used |
|---|---|---|---|---|---|---|
| A1e | 36 | 14 | 13 | 9 | 586 | 2022 |
| A2 | 36 | 12 | 14 | 10 | 597 | 2180 |
| A3 | 36 | 15 | 8 | 13 | 545 | 2420 |
| A4 | 36 | 14 | 13 | 9 | 581 | 2493 |

Paired contrasts on FULL (exact one-sided McNemar, first arm better; development only):

- A1e vs A2: n 36, A1e only 5, A2 only 3, p(A1e>A2) = 0.363, p(A2>A1e) = 0.855
- A1e vs A3: n 36, A1e only 3, A3 only 4, p(A1e>A3) = 0.773, p(A3>A1e) = 0.500
- A1e vs A4: n 36, A1e only 2, A4 only 2, p(A1e>A4) = 0.688, p(A4>A1e) = 0.688
- A2 vs A3: n 36, A2 only 3, A3 only 6, p(A2>A3) = 0.910, p(A3>A2) = 0.254
- A2 vs A4: n 36, A2 only 3, A4 only 5, p(A2>A4) = 0.855, p(A4>A2) = 0.363
- A3 vs A4: n 36, A3 only 3, A4 only 2, p(A3>A4) = 0.500, p(A4>A3) = 0.812


Paired validation walking fraction (one-sided Wilcoxon, first arm better; development only):

- A1e vs A2: n 36, mean diff +0.041, p(A1e>A2) = 0.249, p(A2>A1e) = 0.764
- A1e vs A3: n 36, mean diff +0.072, p(A1e>A3) = 0.326, p(A3>A1e) = 0.687
- A1e vs A4: n 36, mean diff -0.015, p(A1e>A4) = 0.744, p(A4>A1e) = 0.275
- A2 vs A3: n 36, mean diff +0.031, p(A2>A3) = 0.468, p(A3>A2) = 0.548
- A2 vs A4: n 36, mean diff -0.056, p(A2>A4) = 0.951, p(A4>A2) = 0.053
- A3 vs A4: n 36, mean diff -0.087, p(A3>A4) = 0.804, p(A4>A3) = 0.206

# Process metrics (development only)

## A1e (n = 36)

- actions: {'observe': 36, 'delegate_repair': 36, 'experiment': 24}
- actors: {'engine': 96} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 0 of 0)
- conclusions: {'engine_repair': 36}
- Nemotron experiments: 0, of which designed beyond the engine's candidate list: 0; EIG of its choice / best available: median None
- Nemotron hypotheses: 0; entered the top 3: 0; became the leading explanation: 0; had the injected structure (dev post-mortem): 0
- repairs: tools {}, modes {}; plant contradicted the belief's prediction: 0; assimilated checks: 0; dossiers applied: 0
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): 
- MAP structure = injected: 29/36; mean posterior mass on injected 0.80
- inference: $0.000 total ($0.0000/episode), 0 calls, 0 prompt + 0 completion tokens; mean wall 10.5 min

## A2 (n = 36)

- actions: {'observe': 36, 'use_learned': 36, 'delegate_repair': 36, 'experiment': 18}
- actors: {'engine': 126} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 0 of 0)
- conclusions: {'engine_repair': 36}
- Nemotron experiments: 0, of which designed beyond the engine's candidate list: 0; EIG of its choice / best available: median None
- Nemotron hypotheses: 0; entered the top 3: 0; became the leading explanation: 0; had the injected structure (dev post-mortem): 0
- repairs: tools {}, modes {}; plant contradicted the belief's prediction: 0; assimilated checks: 0; dossiers applied: 0
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): 
- MAP structure = injected: 31/36; mean posterior mass on injected 0.85
- inference: $0.000 total ($0.0000/episode), 0 calls, 0 prompt + 0 completion tokens; mean wall 11.1 min

## A3 (n = 36)

- actions: {'experiment': 68, 'observe': 36, 'delegate_repair': 33, 'propose': 32, 'repair': 20, 'screen_tools': 6, 'delegate_diagnosis': 5, 'conclude': 3, 'check': 2}
- actors: {'engine': 36, 'nemotron': 159, 'fallback': 10} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 10 of 169)
- conclusions: {'engine_repair': 33, 'nemotron': 3}
- Nemotron experiments: 67, of which designed beyond the engine's candidate list: 15; EIG of its choice / best available: median 1.0
- Nemotron hypotheses: 44; entered the top 3: 8; became the leading explanation: 5; had the injected structure (dev post-mortem): 2
- repairs: tools {'timing': 1, 'foot_length': 1, 'posture': 6, 'torso_mass': 4, 'placement': 1, 'foot_friction': 4, 'feedback': 2}, modes {'twin': 15, 'plant': 4}; plant contradicted the belief's prediction: 0; assimilated checks: 0; dossiers applied: 0
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): n_walking: 0.335, 25/30, 21/30; time_upright: 0.796, 14/30, 11/30; pitch_mean: 0.024, 17/28, 9/28
- MAP structure = injected: 28/36; mean posterior mass on injected 0.78
- inference: $0.577 total ($0.0160/episode), 217 calls, 853122 prompt + 357245 completion tokens; mean wall 126.0 min

## A4 (n = 36)

- actions: {'experiment': 73, 'observe': 36, 'delegate_repair': 35, 'propose': 34, 'repair': 17, 'delegate_diagnosis': 7, 'screen_tools': 4, 'check': 3, 'conclude': 1, 'apply_dossier': 1}
- actors: {'engine': 36, 'nemotron': 165, 'fallback': 10} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 10 of 175)
- conclusions: {'engine_repair': 35, 'nemotron': 1}
- Nemotron experiments: 73, of which designed beyond the engine's candidate list: 19; EIG of its choice / best available: median 1.0
- Nemotron hypotheses: 58; entered the top 3: 10; became the leading explanation: 6; had the injected structure (dev post-mortem): 4
- repairs: tools {'feedback': 3, 'timing': 1, 'leg_length': 2, 'posture': 1, 'torso_mass': 1, 'foot_friction': 3, 'foot_length': 3, 'placement': 3}, modes {'twin': 12, 'plant': 5}; plant contradicted the belief's prediction: 1; assimilated checks: 0; dossiers applied: 1
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): n_walking: 0.354, 33/38, 24/38; time_upright: 0.839, 24/38, 15/38; pitch_mean: 0.016, 25/37, 12/37
- MAP structure = injected: 29/36; mean posterior mass on injected 0.81
- inference: $0.643 total ($0.0179/episode), 218 calls, 1050259 prompt + 364870 completion tokens; mean wall 119.0 min

```

## Part 2: development compositions (16 instances)

```
# Arms on the Hidden-Damage Bench (dev; development only, no claim)

| arm | n | FULL | PARTIAL | NOT | mean plant used | mean twin used |
|---|---|---|---|---|---|---|
| A1e | 16 | 8 | 6 | 2 | 593 | 2022 |
| A3 | 16 | 6 | 6 | 4 | 594 | 2637 |
| A4 | 16 | 6 | 7 | 3 | 626 | 2586 |

Paired contrasts on FULL (exact one-sided McNemar, first arm better; development only):

- A1e vs A3: n 16, A1e only 2, A3 only 0, p(A1e>A3) = 0.250, p(A3>A1e) = 1.000
- A1e vs A4: n 16, A1e only 3, A4 only 1, p(A1e>A4) = 0.312, p(A4>A1e) = 0.938
- A3 vs A4: n 16, A3 only 1, A4 only 1, p(A3>A4) = 0.750, p(A4>A3) = 0.750


Paired validation walking fraction (one-sided Wilcoxon, first arm better; development only):

- A1e vs A3: n 16, mean diff +0.018, p(A1e>A3) = 0.123, p(A3>A1e) = 0.894
- A1e vs A4: n 16, mean diff -0.010, p(A1e>A4) = 0.447, p(A4>A1e) = 0.588
- A3 vs A4: n 16, mean diff -0.029, p(A3>A4) = 0.733, p(A4>A3) = 0.297

# Process metrics (development only)

## A1e (n = 16)

- actions: {'observe': 16, 'delegate_repair': 16, 'experiment': 10}
- actors: {'engine': 42} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 0 of 0)
- conclusions: {'engine_repair': 16}
- Nemotron experiments: 0, of which designed beyond the engine's candidate list: 0; EIG of its choice / best available: median None
- Nemotron hypotheses: 0; entered the top 3: 0; became the leading explanation: 0; had the injected structure (dev post-mortem): 0
- repairs: tools {}, modes {}; plant contradicted the belief's prediction: 0; assimilated checks: 0; dossiers applied: 0
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): 
- MAP structure = injected: 0/16; mean posterior mass on injected 0.00
- inference: $0.000 total ($0.0000/episode), 0 calls, 0 prompt + 0 completion tokens; mean wall 5.9 min

## A3 (n = 16)

- actions: {'experiment': 52, 'propose': 47, 'observe': 16, 'delegate_repair': 15, 'repair': 8, 'delegate_diagnosis': 7, 'screen_tools': 6, 'conclude': 1}
- actors: {'engine': 16, 'nemotron': 121, 'fallback': 15} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 15 of 136)
- conclusions: {'engine_repair': 15, 'nemotron': 1}
- Nemotron experiments: 52, of which designed beyond the engine's candidate list: 13; EIG of its choice / best available: median 1.0
- Nemotron hypotheses: 72; entered the top 3: 17; became the leading explanation: 7; had the injected structure (dev post-mortem): 0
- repairs: tools {'torque_limit': 1, 'feedback': 2, 'foot_friction': 1, 'torso_mass': 1, 'timing': 2, 'foot_length': 1}, modes {'twin': 6, 'plant': 2}; plant contradicted the belief's prediction: 1; assimilated checks: 0; dossiers applied: 0
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): n_walking: 0.324, 20/26, 19/26; time_upright: 0.832, 13/26, 7/26; pitch_mean: 0.024, 12/21, 8/21
- MAP structure = injected: 0/16; mean posterior mass on injected 0.00
- inference: $0.486 total ($0.0304/episode), 171 calls, 718724 prompt + 300297 completion tokens; mean wall 156.2 min

## A4 (n = 16)

- actions: {'experiment': 46, 'propose': 45, 'observe': 16, 'delegate_repair': 16, 'delegate_diagnosis': 10, 'repair': 5, 'check': 4, 'apply_dossier': 1}
- actors: {'engine': 16, 'nemotron': 114, 'fallback': 13} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 13 of 127)
- conclusions: {'engine_repair': 16}
- Nemotron experiments: 46, of which designed beyond the engine's candidate list: 6; EIG of its choice / best available: median 0.9896551724137931
- Nemotron hypotheses: 64; entered the top 3: 14; became the leading explanation: 7; had the injected structure (dev post-mortem): 1
- repairs: tools {'foot_friction': 1, 'feedback': 2, 'torque_limit': 2}, modes {'plant': 2, 'twin': 3}; plant contradicted the belief's prediction: 1; assimilated checks: 0; dossiers applied: 1
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): n_walking: 0.337, 19/23, 15/23; time_upright: 0.737, 12/23, 9/23; pitch_mean: 0.014, 16/22, 11/22
- MAP structure = injected: 0/16; mean posterior mass on injected 0.00
- inference: $0.504 total ($0.0315/episode), 158 calls, 780544 prompt + 299546 completion tokens; mean wall 163.1 min

```

## Part 3: memory probes (A4lfo: 8 instances of the 2 families excluded from memory; A4bad: 12 instances with a corrupted dossier)

```
# Arms on the Hidden-Damage Bench (dev; development only, no claim)

| arm | n | FULL | PARTIAL | NOT | mean plant used | mean twin used |
|---|---|---|---|---|---|---|
| A4bad | 12 | 5 | 4 | 3 | 591 | 2344 |
| A4lfo | 8 | 4 | 3 | 1 | 524 | 2450 |

Paired contrasts on FULL (exact one-sided McNemar, first arm better; development only):

- A4bad vs A4lfo: n 0, A4bad only 0, A4lfo only 0, p(A4bad>A4lfo) = 1.000, p(A4lfo>A4bad) = 1.000


Paired validation walking fraction (one-sided Wilcoxon, first arm better; development only):


# Process metrics (development only)

## A4bad (n = 12)

- actions: {'experiment': 32, 'propose': 17, 'observe': 12, 'delegate_repair': 10, 'delegate_diagnosis': 7, 'screen_tools': 4, 'repair': 3, 'conclude': 2, 'check': 1}
- actors: {'engine': 12, 'nemotron': 73, 'fallback': 3} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 3 of 76)
- conclusions: {'engine_repair': 10, 'nemotron': 2}
- Nemotron experiments: 32, of which designed beyond the engine's candidate list: 7; EIG of its choice / best available: median 1.0
- Nemotron hypotheses: 24; entered the top 3: 7; became the leading explanation: 4; had the injected structure (dev post-mortem): 0
- repairs: tools {'torque_limit': 1, 'posture': 1, 'feedback': 1}, modes {'plant': 1, 'twin': 2}; plant contradicted the belief's prediction: 0; assimilated checks: 0; dossiers applied: 0
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): n_walking: 0.450, 11/13, 9/13; time_upright: 1.344, 5/13, 2/13; pitch_mean: 0.025, 6/12, 4/12
- MAP structure = injected: 10/12; mean posterior mass on injected 0.83
- inference: $0.301 total ($0.0250/episode), 95 calls, 467895 prompt + 177963 completion tokens; mean wall 159.7 min

## A4lfo (n = 8)

- actions: {'experiment': 10, 'observe': 8, 'propose': 8, 'delegate_repair': 7, 'delegate_diagnosis': 5, 'repair': 3, 'screen_tools': 1, 'conclude': 1}
- actors: {'engine': 8, 'nemotron': 32, 'fallback': 3} (fallback = invalid/failed model reply replaced by the engine's recommendation; model role calls not ok: 3 of 35)
- conclusions: {'engine_repair': 7, 'nemotron': 1}
- Nemotron experiments: 10, of which designed beyond the engine's candidate list: 2; EIG of its choice / best available: median 1.0
- Nemotron hypotheses: 15; entered the top 3: 11; became the leading explanation: 5; had the injected structure (dev post-mortem): 3
- repairs: tools {'leg_length': 1, 'posture': 2}, modes {'twin': 3}; plant contradicted the belief's prediction: 0; assimilated checks: 0; dossiers applied: 0
- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): n_walking: 0.206, 7/8, 6/8; time_upright: 0.635, 7/8, 6/8; pitch_mean: 0.014, 5/8, 2/8
- MAP structure = injected: 7/8; mean posterior mass on injected 0.87
- inference: $0.130 total ($0.0163/episode), 44 calls, 206534 prompt + 75908 completion tokens; mean wall 133.9 min


## Corrupted-dossier probe (A4bad, n = 12; the probe dossier claims low friction for every failure)

- probe dossier ranked first on some turn: 6/12; applied as hypotheses: 0/12; its repair adopted (tool order, trial repair or start edits): 0/12
- outcomes: {'NOT_RECOVERED': 3, 'FULL_RECOVERY': 5, 'PARTIAL_IMPROVEMENT': 4}
```

## Part 4: paired probe contrasts, per-family table, discordant instances, memory use, compositions

```
# Probe pairings (same instances)
A4lfo vs A4: n 8, FULL 4 vs 3, discordant 1/0, walking diff +0.016
A4lfo vs A3: n 8, FULL 4 vs 4, discordant 0/0, walking diff -0.005
A4lfo vs A1e: n 8, FULL 4 vs 3, discordant 1/0, walking diff +0.026
A4lfo vs A2: n 8, FULL 4 vs 4, discordant 1/1, walking diff -0.005
A4bad vs A4: n 12, FULL 5 vs 6, discordant 2/3, walking diff -0.049
A4bad vs A3: n 12, FULL 5 vs 7, discordant 1/3, walking diff +0.014
A4bad vs A1e: n 12, FULL 5 vs 6, discordant 1/2, walking diff -0.007
A4bad vs A2: n 12, FULL 5 vs 5, discordant 2/2, walking diff +0.094

# Per family FULL (single, n=4 each; A1e/A2/A3/A4)
actuator_weakness A1e 2/4 A2 2/4 A3 2/4 A4 2/4 MAP=inj A1e/A3/A4 4 3 4
clock_fault A1e 1/4 A2 1/4 A3 2/4 A4 2/4 MAP=inj A1e/A3/A4 4 4 4
feedback_gain_loss A1e 1/4 A2 1/4 A3 1/4 A4 1/4 MAP=inj A1e/A3/A4 2 2 2
heavy_torso A1e 2/4 A2 2/4 A3 3/4 A4 3/4 MAP=inj A1e/A3/A4 3 3 2
low_ground_friction A1e 1/4 A2 0/4 A3 0/4 A4 1/4 MAP=inj A1e/A3/A4 4 3 4
one_side_weakness A1e 2/4 A2 1/4 A3 3/4 A4 1/4 MAP=inj A1e/A3/A4 3 4 4
payload_offset A1e 2/4 A2 1/4 A3 1/4 A4 1/4 MAP=inj A1e/A3/A4 2 3 3
pitch_sensor_bias A1e 1/4 A2 2/4 A3 2/4 A4 1/4 MAP=inj A1e/A3/A4 4 3 4
short_feet A1e 2/4 A2 2/4 A3 1/4 A4 2/4 MAP=inj A1e/A3/A4 3 3 2

# Discordant single instances A1e vs A3 / A4
A3 WIN  hdb-v1-gen-0137:clock_fault:4 fam=clock_fault mapA1e=True mapA3=True acts=['experiment', 'repair', 'screen_tools', 'delegate_repair'] order=[['timing', 'posture', 'feedback']] start=[None]
A3 WIN  hdb-v1-gen-0170:heavy_torso:1 fam=heavy_torso mapA1e=True mapA3=True acts=['experiment', 'experiment', 'experiment', 'repair', 'delegate_repair'] order=[None] start=['']
A3 LOSS hdb-v1-gen-0142:low_ground_friction:1 fam=low_ground_friction mapA1e=True mapA3=True acts=['experiment', 'experiment', 'repair', 'propose', 'screen_tools', 'experiment', 'experiment', 'propose', 'propose', 'propose', 'repair', 'delegate_diagnosis', 'delegate_repair'] order=[None] start=['']
A3 WIN  hdb-v1-gen-0137:one_side_weakness:4 fam=one_side_weakness mapA1e=False mapA3=True acts=['experiment', 'screen_tools', 'propose', 'delegate_repair'] order=[None] start=[None]
A3 LOSS hdb-v1-gen-0096:payload_offset:4 fam=payload_offset mapA1e=True mapA3=True acts=['experiment', 'repair', 'repair', 'experiment', 'repair', 'repair', 'delegate_repair'] order=[None] start=['']
A3 WIN  hdb-v1-gen-0099:pitch_sensor_bias:1 fam=pitch_sensor_bias mapA1e=True mapA3=True acts=['propose', 'experiment', 'propose', 'experiment', 'propose', 'propose', 'delegate_repair'] order=[None] start=['']
A3 LOSS hdb-v1-gen-0143:short_feet:1 fam=short_feet mapA1e=False mapA3=True acts=['experiment', 'experiment', 'delegate_repair'] order=[None] start=['']
A4 WIN  hdb-v1-gen-0137:clock_fault:4 fam=clock_fault mapA1e=True mapA4=True acts=['experiment', 'repair', 'delegate_repair'] order=[None] start=[None]
A4 WIN  hdb-v1-gen-0170:heavy_torso:1 fam=heavy_torso mapA1e=True mapA4=True acts=['experiment', 'experiment', 'repair', 'delegate_repair'] order=[None] start=[None]
A4 LOSS hdb-v1-gen-0104:one_side_weakness:1 fam=one_side_weakness mapA1e=True mapA4=True acts=['experiment', 'experiment', 'delegate_repair'] order=[None] start=['']
A4 LOSS hdb-v1-gen-0096:payload_offset:4 fam=payload_offset mapA1e=True mapA4=True acts=['experiment', 'delegate_repair'] order=[None] start=['']

# Nemotron customisation of the final repair (delegate_repair by nemotron)
A3 customised 6 FULL 3 | plain 27 FULL 11
A4 customised 5 FULL 2 | plain 29 FULL 12
A3c customised 1 FULL 0 | plain 14 FULL 6
A4c customised 2 FULL 0 | plain 14 FULL 6

# Memory (A4 single): dossier shown first, applied, uses
A4 first-shown {'D1': 9, 'D7': 9, 'D3': 7, 'D5': 6, 'D6': 5} apply_dossier 1 episodes whose Nemotron text cites a dossier 4 uses 1
A4lfo first-shown {'D1': 3, 'D3': 1, 'D4': 3, 'D2': 1} apply_dossier 0 episodes whose Nemotron text cites a dossier 0 uses 0
A4bad first-shown {'D3': 3, 'D90': 4, 'D1': 1, 'D5': 2, 'D7': 2} apply_dossier 0 episodes whose Nemotron text cites a dossier 0 uses 0

# Composition per-pair FULL A1e/A3/A4 and whether a Nemotron hypothesis became MAP
0170 DC ... nemMAP [0, 0]
0167 DC FFF nemMAP [1, 1]
0222 DC ... nemMAP [0, 0]
0103 DC ... nemMAP [1, 0]
0136 DC ... nemMAP [1, 0]
0099 DC ... nemMAP [2, 0]
0137 DC FFF nemMAP [0, 0]
0167 DC FFF nemMAP [1, 0]
0170 DC ... nemMAP [1, 0]
0099 DC ..F nemMAP [0, 0]
0143 DC F.. nemMAP [0, 0]
0108 DC FF. nemMAP [0, 2]
0105 DC ... nemMAP [0, 1]
0126 DC FFF nemMAP [0, 2]
0108 DC F.. nemMAP [0, 0]
0142 DC FFF nemMAP [0, 1]

# Compositions: MAP shares at least one injected primitive; confident (>= 0.95) wrong posteriors
A1e shares >= 1 primitive 7 / 16 | confident and wrong 12 / 16
A3 shares >= 1 primitive 9 / 16 | confident and wrong 15 / 16
A4 shares >= 1 primitive 6 / 16 | confident and wrong 16 / 16
```

## Raw records (git-ignored; `artifacts/vm/hdb/artifacts/hdb/`, also on the main VM boot disk), SHA-256

```
729e37ffb0e6e594f0a374a40c4e0194b59d9b79dbb50b78c60b8d7a2e0f4d9a  inference_ledger_main_20261020.jsonl
540b9415921b205a80ad62fe6ae9565f5c6d6027bae63e2fb1dee8dca374ea98  s2_transfer_A3.jsonl
cb34a780d76f9325718e53f3d8345672ab642aa005a334cd96bf614dec7ec77a  s2_transfer_A4.jsonl
d0f4d9a528f51e89b080ae3331f51e3e8ea2e201841c51d5eab005be925087fd  s2_transfer_A4bad.jsonl
6de56287d0eec10a4ecae2731c6659f4b7ada6422f39194fac40e3b822a8849a  s2_transfer_A4lfo.jsonl
75cb303c6d54d6c4915d6af8e85e4a7682a590f50075e124a6e7dc2e88b1dda7  s2_transfer_devcomp_A3.jsonl
7c3f9c18ee225278022975614ee472c54ca1358f00c2b7d1c7ab9f31c4ac2dc8  s2_transfer_devcomp_A4.jsonl
9a0522953fd209cfbe9531956362d9e5b7c8dab521fec3ebb434559402a0f7c8  amortized_v1.json
00f737a0ca66b07861c176eb0b9a6be22111d535f84e3cfd13d724a95a8a22ed  memory_v5.json
aa57faeb1be8b89c573d92acde40c0df8943ba589408d94316b7279fa3711a6d  memory_v5_corrupt.json
dcc6219c8b04bdd251ef561791e3409e8d2bca88d7f6fe006cb1c9279a29f55f  memory_v5_lfo.json
2014fa80f8f333b1b2f8d4ba561da024516fb49b0334ef7a696acbfa535cdf56 *s2T_A1e.jsonl
84f5fd06975ce490ea57aec298b1792c2ff11ad0d6cdc009c1c9beac9f334ea0 *s2T_A2.jsonl
51200c3db225153441406856fafeacfcfb41ccf62c4932bcd1473a00705c475d *s2TDC_A1e.jsonl
```

## Part 5: retrieval relevance and the one-side instance (checked 2026-10-20)

- A4 single: 27/36 instances have a memory-v5 dossier with exactly their injected structure (D2, right-side weakness, is
  retired). The matching dossier was ranked first on turn 0 in 15/27, and on some turn in 17/27.
- `hdb-v1-gen-0137:one_side_weakness:4` (injected right-side actuator weakness): A1e MAP left-side weakness (0.998),
  NOT FULL. A3 MAP right-side weakness (1.0), FULL after Nemotron chose the `cf:freq@x0.85` experiment.
