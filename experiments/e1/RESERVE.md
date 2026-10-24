# E-1 reserve record (sealed test side)

**Rule (registered, `docs/E1_PROTOCOL.md` §7.2).**
- The 160 instance ids below are **spent** by E-1 for every future confirmatory claim.
- A future registered study, such as Stage 3 A3 > A1, samples from the complement of these ids, with its own seed, and re-checks eligibility.
- Thresholds and eligibility rows from this build are physics only and may be reused. No E-1 arm outcome may inform that sample.

**Build facts.**
- 160 instances on 90 of 99 test bases (at most 2 per base).
- 280 candidates evaluated.
- 66 candidates were evaluated as eligible but not accepted, because a cap or a filled quota blocked them; they are part of the reserve.
- Evidence: `experiments/e1/build/` (`SHA256SUMS`).

| stratum | spent |
|---|---|
| pitch_sensor_bias | 6 |
| payload_offset | 6 |
| low_ground_friction | 6 |
| short_feet | 6 |
| feedback_gain_loss | 6 |
| actuator_weakness | 6 |
| one_side_weakness | 6 |
| clock_fault | 6 |
| heavy_torso | 6 |
| sensor_latency | 18 |
| joint_damping_wear | 18 |
| leg_asymmetry | 18 |
| heldcomp:payload_offset.fwd+actuator_weakness | 13 |
| heldcomp:low_ground_friction+clock_fault.fast | 13 |
| heldcomp:pitch_sensor_bias.++short_feet | 13 |
| heldcomp:heavy_torso+feedback_gain_loss | 13 |

## Spent instance ids

- `hdb-v1-gen-0177:pitch_sensor_bias:5`
- `hdb-v1-gen-0243:pitch_sensor_bias:2`
- `hdb-v1-gen-0094:pitch_sensor_bias:2`
- `hdb-v1-gen-0050:pitch_sensor_bias:4`
- `hdb-v1-gen-0045:pitch_sensor_bias:4`
- `hdb-v1-gen-0158:pitch_sensor_bias:0`
- `hdb-v1-gen-0189:payload_offset:4`
- `hdb-v1-gen-0223:payload_offset:0`
- `hdb-v1-gen-0145:payload_offset:0`
- `hdb-v1-gen-0185:payload_offset:3`
- `hdb-v1-gen-0169:payload_offset:5`
- `hdb-v1-gen-0172:payload_offset:1`
- `hdb-v1-gen-0084:low_ground_friction:2`
- `hdb-v1-gen-0116:low_ground_friction:2`
- `hdb-v1-gen-0141:low_ground_friction:0`
- `hdb-v1-gen-0129:low_ground_friction:0`
- `hdb-v1-gen-0140:low_ground_friction:1`
- `hdb-v1-gen-0227:low_ground_friction:2`
- `hdb-v1-gen-0046:short_feet:1`
- `hdb-v1-gen-0049:short_feet:2`
- `hdb-v1-gen-0211:short_feet:2`
- `hdb-v1-gen-0223:short_feet:1`
- `hdb-v1-gen-0149:short_feet:1`
- `hdb-v1-gen-0179:short_feet:2`
- `hdb-v1-gen-0182:feedback_gain_loss:1`
- `hdb-v1-gen-0246:feedback_gain_loss:0`
- `hdb-v1-gen-0211:feedback_gain_loss:0`
- `hdb-v1-gen-0139:feedback_gain_loss:0`
- `hdb-v1-gen-0240:feedback_gain_loss:2`
- `hdb-v1-gen-0097:feedback_gain_loss:1`
- `hdb-v1-gen-0243:actuator_weakness:1`
- `hdb-v1-gen-0106:actuator_weakness:0`
- `hdb-v1-gen-0112:actuator_weakness:2`
- `hdb-v1-gen-0001:actuator_weakness:2`
- `hdb-v1-gen-0075:actuator_weakness:1`
- `hdb-v1-gen-0007:actuator_weakness:1`
- `hdb-v1-gen-0016:one_side_weakness:0`
- `hdb-v1-gen-0159:one_side_weakness:0`
- `hdb-v1-gen-0121:one_side_weakness:1`
- `hdb-v1-gen-0046:one_side_weakness:0`
- `hdb-v1-gen-0084:one_side_weakness:5`
- `hdb-v1-gen-0145:one_side_weakness:3`
- `hdb-v1-gen-0194:clock_fault:1`
- `hdb-v1-gen-0079:clock_fault:4`
- `hdb-v1-gen-0224:clock_fault:3`
- `hdb-v1-gen-0176:clock_fault:0`
- `hdb-v1-gen-0141:clock_fault:0`
- `hdb-v1-gen-0192:clock_fault:1`
- `hdb-v1-gen-0169:heavy_torso:0`
- `hdb-v1-gen-0185:heavy_torso:2`
- `hdb-v1-gen-0176:heavy_torso:2`
- `hdb-v1-gen-0109:heavy_torso:0`
- `hdb-v1-gen-0177:heavy_torso:0`
- `hdb-v1-gen-0085:heavy_torso:0`
- `hdb-v1-gen-0083:sensor_latency:0`
- `hdb-v1-gen-0205:sensor_latency:0`
- `hdb-v1-gen-0245:sensor_latency:1`
- `hdb-v1-gen-0229:sensor_latency:2`
- `hdb-v1-gen-0050:sensor_latency:0`
- `hdb-v1-gen-0116:sensor_latency:0`
- `hdb-v1-gen-0092:sensor_latency:2`
- `hdb-v1-gen-0175:sensor_latency:0`
- `hdb-v1-gen-0248:sensor_latency:1`
- `hdb-v1-gen-0049:sensor_latency:1`
- `hdb-v1-gen-0210:sensor_latency:0`
- `hdb-v1-gen-0218:sensor_latency:1`
- `hdb-v1-gen-0195:sensor_latency:2`
- `hdb-v1-gen-0001:sensor_latency:0`
- `hdb-v1-gen-0235:sensor_latency:0`
- `hdb-v1-gen-0158:sensor_latency:2`
- `hdb-v1-gen-0075:sensor_latency:1`
- `hdb-v1-gen-0201:sensor_latency:1`
- `hdb-v1-gen-0095:joint_damping_wear:1`
- `hdb-v1-gen-0029:joint_damping_wear:1`
- `hdb-v1-gen-0020:joint_damping_wear:1`
- `hdb-v1-gen-0069:joint_damping_wear:0`
- `hdb-v1-gen-0238:joint_damping_wear:0`
- `hdb-v1-gen-0065:joint_damping_wear:1`
- `hdb-v1-gen-0129:joint_damping_wear:1`
- `hdb-v1-gen-0114:joint_damping_wear:1`
- `hdb-v1-gen-0000:joint_damping_wear:1`
- `hdb-v1-gen-0149:joint_damping_wear:0`
- `hdb-v1-gen-0179:joint_damping_wear:0`
- `hdb-v1-gen-0080:joint_damping_wear:0`
- `hdb-v1-gen-0161:joint_damping_wear:2`
- `hdb-v1-gen-0226:joint_damping_wear:1`
- `hdb-v1-gen-0140:joint_damping_wear:1`
- `hdb-v1-gen-0085:joint_damping_wear:1`
- `hdb-v1-gen-0021:joint_damping_wear:1`
- `hdb-v1-gen-0173:joint_damping_wear:2`
- `hdb-v1-gen-0130:leg_asymmetry:1`
- `hdb-v1-gen-0189:leg_asymmetry:3`
- `hdb-v1-gen-0229:leg_asymmetry:0`
- `hdb-v1-gen-0079:leg_asymmetry:3`
- `hdb-v1-gen-0184:leg_asymmetry:0`
- `hdb-v1-gen-0112:leg_asymmetry:4`
- `hdb-v1-gen-0119:leg_asymmetry:5`
- `hdb-v1-gen-0032:leg_asymmetry:2`
- `hdb-v1-gen-0063:leg_asymmetry:4`
- `hdb-v1-gen-0197:leg_asymmetry:1`
- `hdb-v1-gen-0071:leg_asymmetry:4`
- `hdb-v1-gen-0092:leg_asymmetry:0`
- `hdb-v1-gen-0061:leg_asymmetry:2`
- `hdb-v1-gen-0159:leg_asymmetry:0`
- `hdb-v1-gen-0151:leg_asymmetry:3`
- `hdb-v1-gen-0216:leg_asymmetry:0`
- `hdb-v1-gen-0240:leg_asymmetry:2`
- `hdb-v1-gen-0220:leg_asymmetry:4`
- `hdb-v1-gen-0016:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0144:heldcomp:payload_offset.fwd+actuator_weakness:0`
- `hdb-v1-gen-0029:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0195:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0114:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0026:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0109:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0205:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0066:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0231:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0121:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0194:heldcomp:payload_offset.fwd+actuator_weakness:0`
- `hdb-v1-gen-0095:heldcomp:payload_offset.fwd+actuator_weakness:1`
- `hdb-v1-gen-0080:heldcomp:low_ground_friction+clock_fault.fast:0`
- `hdb-v1-gen-0237:heldcomp:low_ground_friction+clock_fault.fast:1`
- `hdb-v1-gen-0210:heldcomp:low_ground_friction+clock_fault.fast:0`
- `hdb-v1-gen-0175:heldcomp:low_ground_friction+clock_fault.fast:0`
- `hdb-v1-gen-0184:heldcomp:low_ground_friction+clock_fault.fast:1`
- `hdb-v1-gen-0186:heldcomp:low_ground_friction+clock_fault.fast:0`
- `hdb-v1-gen-0111:heldcomp:low_ground_friction+clock_fault.fast:1`
- `hdb-v1-gen-0058:heldcomp:low_ground_friction+clock_fault.fast:0`
- `hdb-v1-gen-0057:heldcomp:low_ground_friction+clock_fault.fast:1`
- `hdb-v1-gen-0144:heldcomp:low_ground_friction+clock_fault.fast:0`
- `hdb-v1-gen-0130:heldcomp:low_ground_friction+clock_fault.fast:0`
- `hdb-v1-gen-0245:heldcomp:low_ground_friction+clock_fault.fast:0`
- `hdb-v1-gen-0083:heldcomp:low_ground_friction+clock_fault.fast:1`
- `hdb-v1-gen-0235:heldcomp:pitch_sensor_bias.++short_feet:1`
- `hdb-v1-gen-0045:heldcomp:pitch_sensor_bias.++short_feet:1`
- `hdb-v1-gen-0231:heldcomp:pitch_sensor_bias.++short_feet:1`
- `hdb-v1-gen-0007:heldcomp:pitch_sensor_bias.++short_feet:1`
- `hdb-v1-gen-0066:heldcomp:pitch_sensor_bias.++short_feet:1`
- `hdb-v1-gen-0069:heldcomp:pitch_sensor_bias.++short_feet:0`
- `hdb-v1-gen-0206:heldcomp:pitch_sensor_bias.++short_feet:0`
- `hdb-v1-gen-0246:heldcomp:pitch_sensor_bias.++short_feet:1`
- `hdb-v1-gen-0226:heldcomp:pitch_sensor_bias.++short_feet:0`
- `hdb-v1-gen-0173:heldcomp:pitch_sensor_bias.++short_feet:0`
- `hdb-v1-gen-0061:heldcomp:pitch_sensor_bias.++short_feet:0`
- `hdb-v1-gen-0237:heldcomp:pitch_sensor_bias.++short_feet:1`
- `hdb-v1-gen-0224:heldcomp:pitch_sensor_bias.++short_feet:0`
- `hdb-v1-gen-0111:heldcomp:heavy_torso+feedback_gain_loss:1`
- `hdb-v1-gen-0186:heldcomp:heavy_torso+feedback_gain_loss:0`
- `hdb-v1-gen-0182:heldcomp:heavy_torso+feedback_gain_loss:0`
- `hdb-v1-gen-0197:heldcomp:heavy_torso+feedback_gain_loss:1`
- `hdb-v1-gen-0065:heldcomp:heavy_torso+feedback_gain_loss:1`
- `hdb-v1-gen-0218:heldcomp:heavy_torso+feedback_gain_loss:0`
- `hdb-v1-gen-0188:heldcomp:heavy_torso+feedback_gain_loss:1`
- `hdb-v1-gen-0026:heldcomp:heavy_torso+feedback_gain_loss:1`
- `hdb-v1-gen-0020:heldcomp:heavy_torso+feedback_gain_loss:0`
- `hdb-v1-gen-0192:heldcomp:heavy_torso+feedback_gain_loss:0`
- `hdb-v1-gen-0097:heldcomp:heavy_torso+feedback_gain_loss:1`
- `hdb-v1-gen-0220:heldcomp:heavy_torso+feedback_gain_loss:0`
- `hdb-v1-gen-0238:heldcomp:heavy_torso+feedback_gain_loss:1`
