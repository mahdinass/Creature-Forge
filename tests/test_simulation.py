import unittest

import numpy as np

from creature_forge.controller import GaitParams
from creature_forge.morphology import BipedParams
from creature_forge.simulate import run_rollout

TELEMETRY_KEYS = {
    "t", "torso_pos", "torso_pitch", "torso_linvel", "torso_angvel", "qpos_joints",
    "qvel_joints", "joint_torque", "ctrl_demand", "com_pos", "com_vel", "foot_contact",
    "foot_slip_speed", "contact_force_total",
}


class SimulationTests(unittest.TestCase):
    def test_telemetry_contract_and_finite(self):
        tel = run_rollout(BipedParams(), GaitParams(), seed=0, duration=1.0)
        self.assertTrue(TELEMETRY_KEYS <= set(tel))
        n = len(tel["t"])
        self.assertGreater(n, 100)
        for k in TELEMETRY_KEYS:
            self.assertEqual(len(tel[k]), n, k)
            self.assertTrue(np.all(np.isfinite(tel[k])), k)
        self.assertEqual(tel["joint_torque"].shape[1], 6)

    def test_same_seed_is_bitwise_deterministic(self):
        a = run_rollout(BipedParams(), GaitParams(), seed=7, duration=1.0)
        b = run_rollout(BipedParams(), GaitParams(), seed=7, duration=1.0)
        for k in TELEMETRY_KEYS:
            np.testing.assert_array_equal(a[k], b[k], err_msg=k)

    def test_different_seed_changes_initial_perturbation(self):
        a = run_rollout(BipedParams(), GaitParams(), seed=1, duration=0.5)
        b = run_rollout(BipedParams(), GaitParams(), seed=2, duration=0.5)
        self.assertFalse(np.array_equal(a["torso_pitch"], b["torso_pitch"]))

    def test_torso_height_is_absolute_world_height(self):
        tel = run_rollout(BipedParams(), GaitParams(), seed=0, duration=0.2)
        self.assertGreater(tel["torso_pos"][0, 1], 0.5)  # standing torso origin ~0.8 m above floor

    def test_push_disturbance_is_applied(self):
        from creature_forge.simulate import Push
        base = run_rollout(BipedParams(), GaitParams(), seed=0, duration=1.0)
        pushed = run_rollout(BipedParams(), GaitParams(), seed=0, duration=1.0,
                             push=Push(time=0.3, force=60.0, duration=0.1))
        i = int(0.35 * 200)
        self.assertLess(abs(base["torso_linvel"][i, 0]), 0.05)
        self.assertGreater(pushed["torso_linvel"][i, 0], 0.15)

    def test_gravity_pulls_body_to_ground_physically(self):
        # Bent knees need ~10 N*m of holding torque; with a 2 N*m limit the body must collapse.
        tel = run_rollout(BipedParams(torque_limit=2.0), GaitParams(stand_knee=-0.6), seed=0, duration=3.0)
        self.assertLess(tel["torso_pos"][-1, 1], 0.7 * tel["torso_pos"][0, 1])


if __name__ == "__main__":
    unittest.main()
