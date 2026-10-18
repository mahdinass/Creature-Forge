# Identifiability study (dev, model-based twin-pair separability + model-free check)

Instances: 138; eligible (plant fails): 104. Results below use eligible instances; the posterior is over the two families of the instance's twin pair (uniform prior, marginal over each family's grid).

## T2

| family | n | MAP correct: obs | obs+conditions | all | mean P(correct) all |
|---|---|---|---|---|---|
| payload_offset | 35 | 35 | 35 | 35 | 1.000 |
| pitch_sensor_bias | 31 | 31 | 31 | 31 | 1.000 |

Model-free leave-one-base-out 1-NN on the plant panel: 65/66 correct.

## T4

| family | n | MAP correct: obs | obs+conditions | all | mean P(correct) all |
|---|---|---|---|---|---|
| low_ground_friction | 24 | 24 | 24 | 24 | 1.000 |
| short_feet | 14 | 14 | 14 | 14 | 1.000 |

Model-free leave-one-base-out 1-NN on the plant panel: 24/38 correct.

## Not eligible (plant still walks; reported, not studied)

- stilts-drawn:pitch_sensor_bias:1: check walking 4/8
- tiny-feet:pitch_sensor_bias:1: check walking 3/8
- tiny-feet:pitch_sensor_bias:0: check walking 6/8
- tiny-feet:pitch_sensor_bias:4: check walking 7/8
- tiny-feet:pitch_sensor_bias:5: check walking 8/8
- tiny-feet:payload_offset:1: check walking 4/8
- tiny-feet:low_ground_friction:0: check walking 3/8
- tiny-feet:short_feet:0: check walking 7/8
- tiny-feet:short_feet:1: check walking 5/8
- tiny-feet:short_feet:2: check walking 6/8
- tiny-feet:short_feet:3: check walking 7/8
- top-heavy:pitch_sensor_bias:5: check walking 6/8
- top-heavy:pitch_sensor_bias:4: check walking 7/8
- top-heavy:low_ground_friction:0: check walking 8/8
- top-heavy:low_ground_friction:1: check walking 8/8
- top-heavy:short_feet:0: check walking 3/8
- walkrec-dev-m1-gen-0000:pitch_sensor_bias:4: check walking 8/8
- walkrec-dev-m1-gen-0000:short_feet:3: check walking 7/8
- walkrec-dev-m1-gen-0000:short_feet:1: check walking 6/8
- walkrec-dev-m1-gen-0001:pitch_sensor_bias:1: check walking 5/8
- walkrec-dev-m1-gen-0001:pitch_sensor_bias:0: check walking 5/8
- walkrec-dev-m1-gen-0001:pitch_sensor_bias:5: check walking 7/8
- walkrec-dev-m1-gen-0001:pitch_sensor_bias:4: check walking 8/8
- walkrec-dev-m1-gen-0002:pitch_sensor_bias:0: check walking 4/8
- walkrec-dev-m1-gen-0002:pitch_sensor_bias:3: check walking 6/8
- walkrec-dev-m1-gen-0002:pitch_sensor_bias:2: check walking 6/8
- walkrec-dev-m1-gen-0002:pitch_sensor_bias:1: check walking 6/8
- walkrec-dev-m1-gen-0002:pitch_sensor_bias:4: check walking 7/8
- walkrec-dev-m1-gen-0002:low_ground_friction:0: check walking 5/8
- walkrec-dev-m1-gen-0002:low_ground_friction:2: check walking 3/8
- walkrec-dev-m1-gen-0002:short_feet:1: check walking 6/8
- walkrec-dev-m1-gen-0002:low_ground_friction:1: check walking 3/8
- walkrec-dev-m1-gen-0002:short_feet:0: check walking 6/8
- walkrec-dev-m1-gen-0002:short_feet:2: check walking 4/8

