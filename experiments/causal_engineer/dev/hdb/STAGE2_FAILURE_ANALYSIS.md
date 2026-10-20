# Stage 2 failure analysis (development only; exploratory, post hoc)

Generated 2026-10-20 by `scripts/stage2_failure_analysis.py` (read-only). Sections 1–8 read the Stage-2 transfer records of all arms.
Sections 9–10 read experience-base records only. No sealed data were touched. These results motivate the next development
iteration. Because they were derived from transfer records, the Stage-2 transfer instances can no longer serve as an untouched
evaluation set (see `docs/DUAL_SIGNAL_PLAN.md`).

```
## 1. Why non-FULL episodes failed (verification reasons)
- single A1e: FULL: 14; validation walking < 80 %: 13; walks, but verdict_v1 not VERIFIED (displacement vs faulty): 7; 20 s confirmation failed: 2
- single A3: FULL: 15; validation walking < 80 %: 14; walks, but verdict_v1 not VERIFIED (displacement vs faulty): 6; 20 s confirmation failed: 1
- single A4: FULL: 14; validation walking < 80 %: 14; walks, but verdict_v1 not VERIFIED (displacement vs faulty): 7; 20 s confirmation failed: 1
- comp A1e: FULL: 8; validation walking < 80 %: 6; walks, but verdict_v1 not VERIFIED (displacement vs faulty): 2
- comp A3: validation walking < 80 %: 8; FULL: 6; walks, but verdict_v1 not VERIFIED (displacement vs faulty): 2
- comp A4: validation walking < 80 %: 9; FULL: 6; 20 s confirmation failed: 1
- pooled non-FULL (all arms, n = 128): validation walking < 80 %: 89; walks, but verdict_v1 not VERIFIED (displacement vs faulty): 32; 20 s confirmation failed: 7

## 2. Does a correct diagnosis convert into recovery?
- single (all arms pooled): FULL | MAP correct 55/134 (41 %); FULL | MAP wrong 9/30 (30 %)
- comp (all arms pooled): FULL | MAP correct 0/0; FULL | MAP wrong 20/48 (42 %)
  - MAP shares >= 1 injected primitive: FULL 8/22 (36 %); shares none: FULL 12/26 (46 %)
  - single, MAP mass in [0, 0.5): MAP correct 0/0
  - single, MAP mass in [0.5, 0.9): MAP correct 0/4 (0 %)
  - single, MAP mass in [0.9, 0.99): MAP correct 27/34 (79 %)
  - single, MAP mass in [0.99, 1.01): MAP correct 107/126 (85 %)
  - comp: MAP mass >= 0.99 in 39/48 (81 %), correct in 0

## 3. Experiment selection: information gained per experiment (structure-level posterior)
- comp chosen by eig: n 1, entropy drop median +0.674 nats, log-mass gain on truth median +0.00, share moving the truth up 0/1, down 0/1
- comp chosen by engine: n 10, entropy drop median +0.004 nats, log-mass gain on truth median +0.00, share moving the truth up 0/10, down 0/10
- comp chosen by nemotron: n 98, entropy drop median +0.000 nats, log-mass gain on truth median +0.00, share moving the truth up 0/98, down 0/98
- comp chosen by nemotron-designed: n 17, entropy drop median +0.000 nats, log-mass gain on truth median +0.00, share moving the truth up 0/17, down 0/17
- comp chosen by nemotron-listed: n 81, entropy drop median +0.000 nats, log-mass gain on truth median +0.00, share moving the truth up 0/81, down 0/81
- single chosen by eig: n 3, entropy drop median +0.836 nats, log-mass gain on truth median +0.38, share moving the truth up 2/3, down 0/3
- single chosen by engine: n 42, entropy drop median +0.459 nats, log-mass gain on truth median +0.42, share moving the truth up 32/42, down 10/42
- single chosen by fallback: n 1, entropy drop median +0.676 nats, log-mass gain on truth median +0.00, share moving the truth up 0/1, down 0/1
- single chosen by nemotron: n 182, entropy drop median +0.000 nats, log-mass gain on truth median +0.00, share moving the truth up 59/182, down 20/182
- single chosen by nemotron-designed: n 37, entropy drop median +0.000 nats, log-mass gain on truth median +0.00, share moving the truth up 4/37, down 2/37
- single chosen by nemotron-listed: n 145, entropy drop median +0.002 nats, log-mass gain on truth median +0.00, share moving the truth up 55/145, down 18/145
- single A1e: mean mass on truth after observation only 0.71 -> end 0.80
- single A3: mean mass on truth after observation only 0.71 -> end 0.78
- comp A1e: mean mass on truth after observation only 0.00 -> end 0.00
- comp A3: mean mass on truth after observation only 0.00 -> end 0.00

## 4. Where the plant and twin budgets go (mean per episode)
- single A1e: plant diagnosis 6, repair 528, robustness 44, stress 9; twin 2022 of 2800; twin budget exhausted in 0/36
- single A3: plant diagnosis 11, repair 480, robustness 45, stress 8; twin 2420 of 2800; twin budget exhausted in 3/36
- single A4: plant diagnosis 11, repair 512, robustness 48, stress 9; twin 2493 of 2800; twin budget exhausted in 4/36
- comp A1e: plant diagnosis 6, repair 538, robustness 42, stress 8; twin 2022 of 2800; twin budget exhausted in 0/16
- comp A3: plant diagnosis 16, repair 530, robustness 40, stress 8; twin 2637 of 2800; twin budget exhausted in 4/16

## 5. Repair: tool screen, tool choice, twin-to-plant transfer, stopping
- tool screen: top score shared (within 1 %) by >= 3 tools in 48/199 (24 %) of screens; median number tied at the top 1
- CMA re-ranking: every top-5 tool reached the same twin walking count in 57/206 (28 %)
- single: non-FULL episodes 100; on instances no arm recovered: 67; on recoverable instances: submitted a tool that worked in another arm 14, tried it but submitted another 4, never tried it 15
- comp: non-FULL episodes 28; on instances no arm recovered: 21; on recoverable instances: submitted a tool that worked in another arm 2, tried it but submitted another 2, never tried it 3
- twin-optimised designs walking >= 7/8 in the twin: plant robust16 <= 12/16 (the plant contradicts the twin) in 2/85 (2 %); MAP was correct in 0/2 of those (contradictions occurred only under a wrong diagnosis)
- contradictions fed back into the belief (assimilate): 0 in every arm (assimilate was never called by Nemotron; the engine never does it)
- accepted by the calibrated stop: 47, mean mapped P(FULL) 0.77, verified 31/47 (66 %); not accepted (budget/turns ran out): 165, verified 53/165 (32 %)
- accepted designs that walked but failed on displacement (verdict_v1): 14 (the stop rule never sees forward displacement)

## 6. Memory retrieval vs what the engine did anyway (A4, single)
- instances with a non-retired dossier for the true mechanism: 23 (no dossier or no repair: 13)
- the submitted tool was already one of the dossier's recommended tools in 8; FULL 3/8. Different tool: 15; FULL 6/15
  - D1 [['actuator_strength', 'all']] [active] tools ['placement', 'posture', 'feedback']: precision 0.4, recommended repair FULL [0, 0], other repairs [3, 5]
  - D2 [['actuator_strength', 'right']] [retired] tools ['torso_mass', 'posture', 'torque_limit']: precision 0.086, recommended repair FULL [19, 24], other repairs [23, 34]
  - D3 [['clock_scale', 'clock']] [active] tools ['feedback', 'timing']: precision 0.929, recommended repair FULL [7, 10], other repairs [2, 4]
  - D4 [['gain_scale', 'balance_feedback']] [active] tools ['timing', 'torso_mass', 'foot_length']: precision 0.778, recommended repair FULL [3, 4], other repairs [2, 5]
  - D5 [['payload', 'torso']] [active] tools ['leg_length', 'torso_mass', 'timing']: precision 0.809, recommended repair FULL [17, 22], other repairs [14, 25]
  - D6 [['segment_length', 'feet']] [contested] tools ['foot_length', 'leg_length']: precision 0.25, recommended repair FULL [6, 14], other repairs [16, 30]
  - D7 [['sensor_bias', 'pitch']] [contested] tools ['feedback', 'torque_limit', 'timing']: precision 0.444, recommended repair FULL [3, 22], other repairs [10, 32]
- dossier content is a mechanism -> tool list; it carries no conditions under which a tool fails, no magnitudes or start edits learned from outcomes, and no link from a failed repair back to the hypothesis

## 7. Paired diagnosis, evidence of the submitted design, procedure noise, families
A. single, paired A1e vs A3: entropy after observation 0.35; end of diagnosis A1e 0.05, A3 0.05 nats
   truth mass end: A1e 0.80 A3 0.78; A3 higher on 5, lower on 4, equal 27
   experiments per episode A1e 0.7, A3 1.9; diagnostic plant rollouts A1e 6.0, A3 10.9
   entropy already < 0.1 nats after observation in 20/36 (EIG can only be small afterwards)
B. submitted design evidence by verification category (all arms, single + comp):
   FULL: n 84; robust16 median 15.0, >= 15 in 67/78; stress4 = 4 in 64; p_full median 0.47; final step plant 54, twin 24
   walks, but verdict_v1 not VERIFIED (displacement vs faulty): n 32; robust16 median 16, >= 15 in 22/31; stress4 = 4 in 19; p_full median 0.77; final step plant 16, twin 15
   validation walking < 80 %: n 89; robust16 median 12.0, >= 15 in 15/76; stress4 = 4 in 8; p_full median 0.40; final step plant 72, twin 4
   20 s confirmation failed: n 7; robust16 median 13, >= 15 in 0/7; stress4 = 4 in 0; p_full median 0.20; final step plant 3, twin 4
C. A1e vs A2 discordant 8/36; among instances where both submitted the SAME tool: discordant 4/26
   A1e vs A3: discordant 7/36; same final tool on 17, of which discordant 2
   A1e vs A4: discordant 4/36; same final tool on 21, of which discordant 1
   A3 vs A4: discordant 5/36; same final tool on 14, of which discordant 1
D. single, FULL by family across all arms: {'low_ground_friction': '2/16', 'feedback_gain_loss': '4/16', 'clock_fault': '7/19', 'payload_offset': '7/19', 'pitch_sensor_bias': '8/20', 'one_side_weakness': '8/19', 'short_feet': '7/16', 'actuator_weakness': '10/20', 'heavy_torso': '11/19'}

## 8. Recoverability ceiling and twin search
single: instances 36; recovered by at least one arm 21
comp: instances 16; recovered by at least one arm 9
twin search outcome x FULL: {('no twin step', False): 24, ('no twin step', True): 11, ('twin < 7/8', False): 33, ('twin < 7/8', True): 9, ('twin >= 7/8', False): 71, ('twin >= 7/8', True): 64}

## 9. Experience corpus (experience bases only): verified tool outcomes and offline repair-prior checks
experience instances with >= 1 verified tool outcome: 340; (instance, tool) cells: 880; A0 cells parsed 324
instances with >= 2 tools verified: 290; mean tools per instance 2.59; instances where some tool gave FULL: 188
instances where tools disagree (some FULL, some not): 109/290  <- tool choice matters here
  actuator_weakness: foot_length 3/4, posture 3/4, torso_mass 4/6, placement 4/7, timing 3/9
  clock_fault: feedback 4/4, timing 9/13, posture 5/9, placement 4/9, torso_mass 0/4
  devcomp:low_ground_friction+feedback_gain_loss: 
  devcomp:one_side_weakness.left+clock_fault.fast: 
  devcomp:payload_offset.fwd+short_feet: 
  devcomp:pitch_sensor_bias.++actuator_weakness: 
  devcomp:pitch_sensor_bias.++clock_fault.fast: 
  devcomp:pitch_sensor_bias.++heavy_torso: 
  devcomp:short_feet+clock_fault.fast: 
  feedback_gain_loss: timing 4/7, torso_mass 5/9, placement 4/8, posture 0/7
  heavy_torso: leg_length 3/3, placement 4/8, torso_mass 3/7, timing 2/5, posture 2/7
  low_ground_friction: foot_length 2/6, feedback 1/7, timing 2/16, posture 0/14, foot_friction 0/18, torque_limit 0/9, torso_mass 0/6, placement 0/10, leg_length 0/7, pitch_ref@-0.1R 0/3, stride 0/4
  one_side_weakness: torque_limit 3/4, posture 3/5, foot_length 4/7, leg_length 3/6, torso_mass 5/12, timing 4/11, placement 5/15
  payload_offset: torso_mass 15/21, leg_length 11/16, placement 14/22, posture 18/33, timing 19/41, foot_length@x1.5 2/5, fp_kd@+0.2R 1/3, foot_length 7/22, torque_limit 6/22, feedback 4/17, pitch_ref@-0.1R 1/10, pitch_ref@+0.1R 0/7, foot_friction 0/3
  pitch_sensor_bias: feedback 12/19, posture 12/31, leg_length 9/24, timing 16/45, torque_limit 5/16, stride 2/10, foot_friction 1/6, torso_mass 3/23, placement 2/20, foot_length 1/17, pitch_ref@-0.1R 0/9, pitch_ref@+0.1R 0/7
  short_feet: leg_length 6/7, feedback 4/8, foot_length 10/21, torque_limit 2/7, posture 2/11, placement 1/6, timing 2/14, torso_mass 0/6, pitch_ref@-0.1R 0/3

Offline (LOBO, true family as the condition = upper bound; within tools whose outcome is known), n = 290 instances:
{'engine': 141, 'learned': 120, 'best_known': 161, 'random_known': 106.6}
lambda 0.0: n 253 {'combined': 114, 'engine_top_known': 114, 'best_known': 145}
lambda 0.5: n 253 {'combined': 114, 'engine_top_known': 114, 'best_known': 145}
lambda 1.0: n 253 {'combined': 117, 'engine_top_known': 114, 'best_known': 145}
lambda 2.0: n 253 {'combined': 124, 'engine_top_known': 114, 'best_known': 145}
lambda 4.0: n 253 {'combined': 123, 'engine_top_known': 114, 'best_known': 145}

## 10. Likelihood tempering (experience bases only; offline from stored particle log-likelihoods)
n single 211 n comp 16
T  1: single mean log P(truth) -2.50, MAP mass >= .95 in 194 (correct 136), confident-wrong 58; comp: mass on structures sharing an injected primitive 0.44, MAP mass >= .95 in 14/16
T  2: single mean log P(truth) -2.22, MAP mass >= .95 in 135 (correct 104), confident-wrong 31; comp: mass on structures sharing an injected primitive 0.45, MAP mass >= .95 in 11/16
T  4: single mean log P(truth) -2.04, MAP mass >= .95 in 80 (correct 69), confident-wrong 11; comp: mass on structures sharing an injected primitive 0.44, MAP mass >= .95 in 9/16
T  8: single mean log P(truth) -2.05, MAP mass >= .95 in 35 (correct 31), confident-wrong 4; comp: mass on structures sharing an injected primitive 0.40, MAP mass >= .95 in 2/16
T 16: single mean log P(truth) -2.17, MAP mass >= .95 in 6 (correct 6), confident-wrong 0; comp: mass on structures sharing an injected primitive 0.35, MAP mass >= .95 in 1/16
T 32: single mean log P(truth) -2.30, MAP mass >= .95 in 0 (correct 0), confident-wrong 0; comp: mass on structures sharing an injected primitive 0.31, MAP mass >= .95 in 1/16
```
