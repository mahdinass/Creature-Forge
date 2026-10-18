"""SEALED held-out mechanism families of the Hidden-Damage Bench (phase 3).

Never imported by agent-facing code (belief_engine, scientist_has, hdb_policies, hdb_workbench; guarded by tests/test_hdb.py).
Used only by the bench builder after registration. Their primitives are expressible in the generic DSL (hidden_plant), but
they are excluded from experience (dossiers, the learned posterior's training data) and from every prompt or tuning example.

Families (threshold-relative strengths as in hdb_bench.FAMILY_SPECS):
  sensor_latency       T1 twin of feedback_gain_loss: the controller reads a delayed state. Fix: LOWER feedback gains / more
                       damping (raising gains, the twin's fix, destabilises further).
  joint_damping_wear   T3 twin of actuator_weakness: worn joints dissipate energy (velocity dependent).
  leg_asymmetry        one shank shorter (damage); the symmetric toolset may not be able to compensate (honest U stratum).
  compositions         two dev primitives, each at a fraction of its own failure threshold; jointly they fail.
"""
from __future__ import annotations

import math

from .hdb_bench import _strength_dev

HELDOUT_FAMILY_SPECS: dict[str, dict] = {
    "sensor_latency": {"pair": "T1", "split": "heldout", "taxonomy": "sensing", "variants": {
        "": {"make": _strength_dev("sensor_delay", "all", "seconds", lambda s, b: round(s, 6)), "max": 0.15}}},
    "joint_damping_wear": {"pair": "T3", "split": "heldout", "taxonomy": "actuation / wear", "variants": {
        "": {"make": _strength_dev("joint_damping", "all", "factor", lambda s, b: round(math.exp(s), 6)),
             "max": math.log(100.0)}}},
    "leg_asymmetry": {"pair": "S4", "split": "heldout", "taxonomy": "geometry / damage", "variants": {
        "left": {"make": _strength_dev("segment_length", "shank_l", "factor", lambda s, b: round(math.exp(-s), 6)),
                 "max": math.log(1 / 0.5)},
        "right": {"make": _strength_dev("segment_length", "shank_r", "factor", lambda s, b: round(math.exp(-s), 6)),
                  "max": math.log(1 / 0.5)}}},
}

# Compositions: (family A, variant A, family B, variant B). Strength of each component = COMPOSITION_FRACTIONS x its own
# threshold on the base, so neither alone is expected to fail; eligibility (the plant fails) still decides.
COMPOSITIONS = (("payload_offset", "fwd", "actuator_weakness", ""),
                ("low_ground_friction", "", "clock_fault", "fast"),
                ("pitch_sensor_bias", "+", "short_feet", ""),
                ("heavy_torso", "", "feedback_gain_loss", ""))
COMPOSITION_FRACTIONS = (0.6, 0.8)
