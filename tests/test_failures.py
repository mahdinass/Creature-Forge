import unittest

import numpy as np

from creature_forge.controller import GaitParams
from creature_forge.failures import detect_failures
from creature_forge.morphology import BipedParams
from creature_forge.simulate import Push, run_rollout


def synth(n=400, z=0.77, pitch=0.0, torque=0.0, demand=0.0, slip=0.0, contact=1.0, x_rate=0.0):
    t = np.arange(n) / 200.0
    return {
        "t": t,
        "torso_pos": np.stack([x_rate * t, np.full(n, z), np.full(n, pitch)], 1),
        "torso_pitch": np.full(n, pitch),
        "torso_linvel": np.zeros((n, 2)), "torso_angvel": np.zeros(n),
        "qpos_joints": np.zeros((n, 6)), "qvel_joints": np.zeros((n, 6)),
        "joint_torque": np.full((n, 6), torque), "ctrl_demand": np.full((n, 6), demand),
        "com_pos": np.zeros((n, 3)), "com_vel": np.zeros((n, 3)),
        "foot_contact": np.full((n, 2), contact), "foot_slip_speed": np.full((n, 2), slip),
        "contact_force_total": np.full(n, 100.0),
    }


class FailureDetectorTests(unittest.TestCase):
    def kinds(self, tel, limit=60.0):
        return {e.kind for e in detect_failures(tel, BipedParams(torque_limit=limit))}

    def test_healthy_standing_has_no_events(self):
        self.assertEqual(self.kinds(synth()), set())

    def test_fall_detected_on_low_torso_with_evidence_and_time(self):
        tel = synth()
        tel["torso_pos"][200:, 1] = 0.1
        ev = [e for e in detect_failures(tel, BipedParams()) if e.kind == "fall"]
        self.assertEqual(len(ev), 1)
        self.assertAlmostEqual(ev[0].time, 1.0, places=1)
        self.assertIn("torso_height", ev[0].evidence)

    def test_brief_dip_is_not_a_fall(self):
        tel = synth()
        tel["torso_pos"][100:104, 1] = 0.1  # 20 ms
        self.assertNotIn("fall", self.kinds(tel))

    def test_sustained_saturation_detected(self):
        tel = synth(torque=60.0, demand=120.0)
        self.assertIn("actuator_saturation", self.kinds(tel))

    def test_slip_detected_only_with_stance_contact(self):
        self.assertIn("foot_slip", self.kinds(synth(slip=0.5, contact=1.0)))
        self.assertNotIn("foot_slip", self.kinds(synth(slip=0.5, contact=0.0)))

    def test_same_push_topples_short_foot_but_not_default_foot(self):
        push = Push(time=1.0, force=25.0, duration=0.15)  # measured frontier: 20 N short foot, 40 N default
        for seed in (0, 1, 2):
            short = BipedParams(foot_length=0.08)
            t_short = run_rollout(short, GaitParams(), seed=seed, duration=4, push=push)
            self.assertIn("fall", {e.kind for e in detect_failures(t_short, short)})
            default = BipedParams()
            t_def = run_rollout(default, GaitParams(), seed=seed, duration=4, push=push)
            self.assertNotIn("fall", {e.kind for e in detect_failures(t_def, default)})

if __name__ == "__main__":
    unittest.main()
