"""SEALED held-out mechanism families HF2 for the registered study E-2 (docs/RL1_PLAN.md §6). Defined on 2026-10-24, in the plan
commit, before any RL-1 result existed. Not used in development, not in E-1, not in any prompt or memory. Never imported by
agent-facing code (belief_engine, scientist_has, hdb_policies, hdb_workbench, repair_memory; guarded by tests/test_rl1.py).
Used only by the E-2 bench builder after registration.

Each family uses a (kind, target) primitive of the generic deviation DSL that no dev family and no E-1 family uses. Related,
not equal, to dev mechanisms: memory may transfer, and apparent similarity may mislead.
  knee_weakness        actuator_strength on the knees only           (dev: actuator_weakness = all joints)
  ankle_damping_wear   joint_damping on the ankles only              (E-1 sealed: all joints)
  one_side_slip        contact_friction on one foot                  (dev: low_ground_friction = both feet)
  placement_gain_loss  gain_scale on the foot-placement gains        (dev: feedback_gain_loss = balance feedback)
  thigh_asymmetry      segment_length on one thigh                   (E-1 sealed: one shank)
Strengths are threshold-relative exactly as hdb_bench.FAMILY_SPECS (multiples 1.0 / 1.3 / 1.7 of each variant's own
failure threshold on the base).
"""
from __future__ import annotations

import math

from .hdb_bench import _strength_dev

HF2_FAMILY_SPECS: dict[str, dict] = {
    "knee_weakness": {"pair": "H2a", "split": "heldout2", "taxonomy": "actuation", "variants": {
        "": {"make": _strength_dev("actuator_strength", "knees", "factor", lambda s, b: round(math.exp(-s), 6)),
             "max": math.log(1 / 0.05)}}},
    "ankle_damping_wear": {"pair": "H2b", "split": "heldout2", "taxonomy": "actuation / wear", "variants": {
        "": {"make": _strength_dev("joint_damping", "ankles", "factor", lambda s, b: round(math.exp(s), 6)),
             "max": math.log(100.0)}}},
    "one_side_slip": {"pair": "H2c", "split": "heldout2", "taxonomy": "contact / environment", "variants": {
        "left": {"make": _strength_dev("contact_friction", "foot_l", "factor", lambda s, b: round(math.exp(-s), 6)),
                 "max": math.log(1 / 0.02)},
        "right": {"make": _strength_dev("contact_friction", "foot_r", "factor", lambda s, b: round(math.exp(-s), 6)),
                  "max": math.log(1 / 0.02)}}},
    "placement_gain_loss": {"pair": "H2d", "split": "heldout2", "taxonomy": "control", "variants": {
        "": {"make": _strength_dev("gain_scale", "placement", "factor", lambda s, b: round(math.exp(-s), 6)),
             "max": math.log(1 / 0.02)}}},
    "thigh_asymmetry": {"pair": "H2e", "split": "heldout2", "taxonomy": "geometry / damage", "variants": {
        "left": {"make": _strength_dev("segment_length", "thigh_l", "factor", lambda s, b: round(math.exp(-s), 6)),
                 "max": math.log(2.0)},
        "right": {"make": _strength_dev("segment_length", "thigh_r", "factor", lambda s, b: round(math.exp(-s), 6)),
                  "max": math.log(2.0)}}},
}
