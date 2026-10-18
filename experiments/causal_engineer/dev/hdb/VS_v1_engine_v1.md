# Vertical slice (dev): engine-only episodes on the Hidden-Damage Bench

Instances: 24; eligible and run: 20; not eligible: 4 (tiny-feet:pitch_sensor_bias:4, top-heavy:pitch_sensor_bias:4, tiny-feet:short_feet:2, tiny-feet:short_feet:3).

| family | n | MAP = injected structure | mean posterior on injected | FULL | PARTIAL | NOT | plant used | twin used |
|---|---|---|---|---|---|---|---|---|
| low_ground_friction | 6 | 5 | 0.83 | 0 | 2 | 4 | 417 | 1730 |
| payload_offset | 6 | 6 | 1.00 | 0 | 1 | 5 | 571 | 1844 |
| pitch_sensor_bias | 4 | 3 | 0.74 | 0 | 1 | 3 | 471 | 1698 |
| short_feet | 4 | 3 | 0.75 | 0 | 1 | 3 | 248 | 1457 |

Total: MAP correct 17/20; FULL 0/20.

Per episode:

- stilts-drawn:pitch_sensor_bias:4: MAP [['sensor_bias', 'pitch']] (1.00); repair [('placement', 3, 7, None)] -> NOT_RECOVERED (0.88)
- stilts-drawn:pitch_sensor_bias:7: MAP [['joint_damping', 'all']] (1.00); repair [('foot_length', 4, 0, 0), ('placement', 2, 0, 0)] -> NOT_RECOVERED (0.00)
- tiny-feet:pitch_sensor_bias:7: MAP [['sensor_bias', 'pitch']] (0.98); repair [('feedback', 8, 0, 14), ('posture', 8, 2, 16)] -> PARTIAL_IMPROVEMENT (1.00)
- top-heavy:pitch_sensor_bias:7: MAP [['sensor_bias', 'pitch']] (1.00); repair [('leg_length', 0, 0, 0), ('torque_limit', 0, 0, 0)] -> NOT_RECOVERED (0.00)
- stilts-drawn:payload_offset:3: MAP [['payload', 'torso']] (1.00); repair [('torso_mass', 1, 0, 0), ('foot_length', 4, 3, 5)] -> NOT_RECOVERED (0.25)
- tiny-feet:payload_offset:3: MAP [['payload', 'torso']] (1.00); repair [('foot_length', 0, 0, 0), ('leg_length', 8, 8, None)] -> PARTIAL_IMPROVEMENT (0.88)
- top-heavy:payload_offset:3: MAP [['payload', 'torso']] (1.00); repair [('foot_friction', 0, 0, 0), ('feedback', 0, 0, 0)] -> NOT_RECOVERED (0.00)
- stilts-drawn:payload_offset:5: MAP [['payload', 'torso']] (1.00); repair [('feedback', 0, 0, 0), ('posture', 0, 0, 0)] -> NOT_RECOVERED (0.00)
- tiny-feet:payload_offset:5: MAP [['payload', 'torso']] (1.00); repair [('feedback', 0, 0, 0), ('torso_mass', 0, 0, 0)] -> NOT_RECOVERED (0.00)
- top-heavy:payload_offset:5: MAP [['payload', 'torso']] (1.00); repair [('foot_friction', 0, 0, 0), ('leg_length', 0, 0, 0)] -> NOT_RECOVERED (0.00)
- stilts-drawn:low_ground_friction:2: MAP [['contact_friction', 'feet']] (1.00); repair [('foot_length', 7, 7, None)] -> NOT_RECOVERED (0.79)
- tiny-feet:low_ground_friction:2: MAP [['contact_friction', 'feet']] (1.00); repair [('feedback', 4, 2, 5), ('foot_friction', 8, 7, None)] -> NOT_RECOVERED (0.92)
- top-heavy:low_ground_friction:2: MAP [['contact_friction', 'feet']] (1.00); repair [('posture', 3, 0, 0), ('timing', 3, 0, 0)] -> PARTIAL_IMPROVEMENT (0.00)
- stilts-drawn:low_ground_friction:4: MAP [['contact_friction', 'feet']] (1.00); repair [('foot_length', 6, 6, 14), ('foot_friction', 6, 2, 10)] -> NOT_RECOVERED (0.75)
- tiny-feet:low_ground_friction:4: MAP [['joint_damping', 'ankles']] (1.00); repair [('leg_length', 4, 0, 0), ('feedback', 3, 0, 6)] -> NOT_RECOVERED (0.33)
- top-heavy:low_ground_friction:4: MAP [['contact_friction', 'feet']] (1.00); repair [('foot_friction', 2, 5, 12), ('timing', 3, 7, None)] -> PARTIAL_IMPROVEMENT (0.79)
- stilts-drawn:short_feet:2: MAP [['segment_length', 'feet']] (1.00); repair [('foot_length', 8, 8, None)] -> PARTIAL_IMPROVEMENT (0.92)
- top-heavy:short_feet:2: MAP [['segment_length', 'feet']] (1.00); repair [('foot_length', 5, 0, 0), ('leg_length', 8, 7, None)] -> NOT_RECOVERED (1.00)
- stilts-drawn:short_feet:3: MAP [['gain_scale', 'balance_feedback']] (1.00); repair [('timing', 3, 0, 0), ('leg_length', 1, 0, 0)] -> NOT_RECOVERED (0.00)
- top-heavy:short_feet:3: MAP [['segment_length', 'feet']] (1.00); repair [('foot_length', 7, 7, None)] -> NOT_RECOVERED (0.75)

