import unittest

import mujoco

from creature_forge.morphology import BipedParams, build_model, build_mjcf


class MorphologyTests(unittest.TestCase):
    def test_default_model_compiles_with_expected_structure(self):
        m = build_model(BipedParams())
        self.assertEqual(m.nu, 6)  # hip + knee + ankle per leg
        self.assertEqual(m.nq, 3 + 6)  # root x,z,pitch + 6 joints

    def test_out_of_bounds_parameter_rejected(self):
        with self.assertRaises(ValueError):
            BipedParams(shank_length=5.0).validate()
        with self.assertRaises(ValueError):
            BipedParams(foot_friction=-0.1).validate()

    def test_parameters_change_physical_model(self):
        heavy = build_model(BipedParams(torso_mass=8.0))
        light = build_model(BipedParams(torso_mass=3.0))
        self.assertGreater(heavy.body_subtreemass[0], light.body_subtreemass[0])
        weak = build_model(BipedParams(torque_limit=10.0))
        self.assertEqual(float(weak.actuator_ctrlrange[0, 1]), 10.0)

    def test_foot_friction_is_the_effective_contact_friction(self):
        # MuJoCo takes the max of the two geoms' friction, so the floor must not mask the foot.
        import mujoco
        for mu in (0.1, 0.5, 1.5):
            m = build_model(BipedParams(foot_friction=mu))
            foot = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "foot_l")
            floor = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "floor")
            self.assertAlmostEqual(max(m.geom_friction[foot][0], m.geom_friction[floor][0]), mu)

    def test_mjcf_is_deterministic(self):
        self.assertEqual(build_mjcf(BipedParams()), build_mjcf(BipedParams()))


if __name__ == "__main__":
    unittest.main()
