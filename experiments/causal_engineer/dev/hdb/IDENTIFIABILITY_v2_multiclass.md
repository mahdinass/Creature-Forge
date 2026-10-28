# Identifiability study (dev, model-based twin-pair separability + model-free check)

Instances: 313; eligible (plant fails): 302. Results below use eligible instances; the posterior is over the two families of the instance's twin pair (uniform prior, marginal over each family's grid).

## Multi-class (every dev family is a rival)

| injected / MAP (all instruments) | actuator_weakness | clock_fault | feedback_gain_loss | heavy_torso | low_ground_friction | one_side_weakness | payload_offset | pitch_sensor_bias | short_feet | correct: obs | obs+conditions | all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| actuator_weakness (n=24) | 21 | 0 | 0 | 2 | 0 | 1 | 0 | 0 | 0 | 21 | 21 | 21 |
| clock_fault (n=36) | 0 | 35 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 36 | 36 | 35 |
| feedback_gain_loss (n=28) | 0 | 0 | 25 | 0 | 1 | 0 | 0 | 0 | 2 | 23 | 25 | 25 |
| heavy_torso (n=21) | 4 | 0 | 0 | 17 | 0 | 0 | 0 | 0 | 0 | 11 | 19 | 17 |
| low_ground_friction (n=21) | 0 | 0 | 0 | 0 | 19 | 0 | 0 | 0 | 2 | 21 | 21 | 19 |
| one_side_weakness (n=50) | 3 | 0 | 0 | 1 | 0 | 45 | 0 | 0 | 1 | 32 | 36 | 45 |
| payload_offset (n=49) | 0 | 0 | 0 | 0 | 0 | 0 | 49 | 0 | 0 | 41 | 47 | 49 |
| pitch_sensor_bias (n=51) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 51 | 0 | 45 | 49 | 51 |
| short_feet (n=22) | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 20 | 15 | 16 | 20 |

## Not eligible (plant still walks; reported, not studied)

- tiny-feet:clock_fault:4: check walking 3/8
- hdb-v1-gen-0028:payload_offset:4: check walking 5/8
- walkrec-dev-m1-gen-0000:low_ground_friction:1: check walking 4/8
- hdb-v1-gen-0038:short_feet:1: check walking 3/8
- walkrec-dev-m1-gen-0000:low_ground_friction:1: check walking 4/8
- walkrec-dev-m1-gen-0002:payload_offset:4: check walking 4/8
- hdb-v1-gen-0004:pitch_sensor_bias:1: check walking 5/8
- hdb-v1-gen-0028:payload_offset:4: check walking 5/8
- walkrec-dev-m1-gen-0004:clock_fault:4: check walking 3/8
- hdb-v1-gen-0037:short_feet:1: check walking 6/8
- walkrec-dev-m1-gen-0000:low_ground_friction:1: check walking 4/8

