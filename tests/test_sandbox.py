import hashlib
import json
import math
import unittest

import mujoco
import numpy as np

from creature_forge.controller import GaitParams
from creature_forge.morphology import BOUNDS, BipedParams, build_mjcf
from creature_forge.sandbox import (SANDBOX_BOUNDS, SandboxBody, SandboxError, build_sandbox_payload, explain_outcome,
                                    sandbox_model)
from creature_forge.simulate import Push, run_rollout


class ScientificSpaceIsFrozenTests(unittest.TestCase):
    """Sandbox freedom must never leak into the registered scientific design space."""

    def test_bounds_and_default_models_are_pinned(self):
        self.assertEqual(hashlib.sha256(json.dumps(BOUNDS, sort_keys=True).encode()).hexdigest(),
                         "c7c3f5bcf29e96cfa99eddca8888a8c316ecb09f15a6b9e6b2fd944789f14a5f")
        self.assertEqual(hashlib.sha256(build_mjcf(BipedParams()).encode()).hexdigest(),
                         "f4139ef16517e372d732f14890126dc2b5a5c0a77d57556f69258fd1c1d694ff")
        self.assertEqual(hashlib.sha256(build_mjcf(BipedParams(foot_length=0.08)).encode()).hexdigest(),
                         "6c61c72582997f47426580dcc6958c67e8138f432903d3df7efa49e326248950")

    def test_scientific_validation_still_rejects_what_the_sandbox_allows(self):
        with self.assertRaises(ValueError):
            BipedParams(foot_length=0.03).validate()
        SandboxBody(foot_length=0.03).validate()  # allowed in the sandbox
        self.assertEqual(BipedParams().as_dict().keys(), {"torso_mass", "thigh_length", "shank_length", "foot_length",
                                                         "foot_friction", "torque_limit", "leg_density"})

    def test_sandbox_bounds_are_wider_than_scientific_bounds_everywhere(self):
        for k, (lo, hi) in BOUNDS.items():
            slo, shi = SANDBOX_BOUNDS[k]
            self.assertLessEqual(slo, lo, k)
            self.assertGreaterEqual(shi, hi, k)
            self.assertGreater(slo, 0, k)  # finite and strictly positive


class SandboxValidationTests(unittest.TestCase):
    def test_rejects_non_finite_non_positive_and_out_of_sandbox_values(self):
        for bad in (float("nan"), float("inf"), -1.0, 0.0, 1e6):
            with self.assertRaises(ValueError, msg=str(bad)):
                SandboxBody(torso_mass=bad).validate()
        with self.assertRaises(ValueError):
            SandboxBody(thigh_length_r=float("nan")).validate()

    def test_pose_must_be_inside_joint_ranges(self):
        SandboxBody(pose=(0.2, 0.3, -1.0, 0.1, -0.2, -0.5, -0.1)).validate()
        with self.assertRaises(ValueError):  # knee only flexes in [-2.2, 0]
            SandboxBody(pose=(0, 0, 0.5, 0, 0, 0, 0)).validate()
        with self.assertRaises(ValueError):
            SandboxBody(pose=(0, 0, 0, 0, 0)).validate()  # wrong length


class SandboxModelTests(unittest.TestCase):
    def test_per_leg_lengths_are_real_not_mirrored(self):
        m = sandbox_model(SandboxBody(thigh_length=0.2, thigh_length_r=0.5, shank_length=0.3, shank_length_r=0.25,
                                      foot_length=0.1, foot_length_r=0.3))
        size = lambda name: m.geom_size[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, name)]
        # box foot half-length = foot_length / 2
        self.assertAlmostEqual(size("foot_l")[0], 0.05)
        self.assertAlmostEqual(size("foot_r")[0], 0.15)
        thigh_l = [i for i in range(m.ngeom) if m.geom_bodyid[i] == mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "thigh_l")][0]
        thigh_r = [i for i in range(m.ngeom) if m.geom_bodyid[i] == mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "thigh_r")][0]
        self.assertAlmostEqual(m.geom_size[thigh_l][1], 0.1)
        self.assertAlmostEqual(m.geom_size[thigh_r][1], 0.25)

    def test_compile_failure_is_a_structured_error_not_a_crash(self):
        import creature_forge.sandbox as sb
        orig = sb._mjcf
        sb._mjcf = lambda body: "<mujoco><worldbody><nonsense/></worldbody></mujoco>"
        try:
            with self.assertRaises(SandboxError) as cm:
                sandbox_model(SandboxBody())
            self.assertIn("MuJoCo", str(cm.exception))
        finally:
            sb._mjcf = orig


class SandboxSimulationTests(unittest.TestCase):
    def test_default_sandbox_body_with_neutral_pose_matches_the_scientific_rollout(self):
        sci = run_rollout(BipedParams(), GaitParams(), seed=1, duration=0.6)
        sbx = run_rollout(SandboxBody(), GaitParams(), seed=1, duration=0.6)
        np.testing.assert_allclose(sbx["torso_pos"], sci["torso_pos"], atol=1e-9)

    def test_a_deliberately_bad_creature_reaches_mujoco_and_falls(self):
        bad = SandboxBody(foot_length=0.025, torso_mass=40.0, torque_limit=6.0, thigh_length=0.9, shank_length=0.25, foot_friction=0.05)
        tel = run_rollout(bad, GaitParams(), seed=0, duration=3.0, push=Push(0.5, 25.0, 0.15))
        z = tel["torso_pos"][:, 1]
        self.assertLess(z.min(), 0.5 * z[0])  # it really collapsed in the physics engine
        p = build_sandbox_payload(bad, GaitParams(), seed=0, duration=3.0, push=Push(0.5, 25.0, 0.15))
        self.assertTrue(p["metrics"]["fell"])
        self.assertTrue(p["sandbox"])
        self.assertTrue(any("fell" in r["text"].lower() or "fall" in r["text"].lower() for r in p["explanation"]["reasons"]))
        self.assertTrue(all(r["measured"] for r in p["explanation"]["reasons"]))  # every reason cites a measurement

    def test_initial_pose_is_applied_and_lowest_point_rests_on_the_floor(self):
        b = SandboxBody(pose=(0.0, 0.5, -1.2, 0.4, -0.3, -0.6, 0.2))
        tel = run_rollout(b, GaitParams(), seed=0, duration=0.05, perturb=0.0)
        np.testing.assert_allclose(tel["qpos_joints"][0], b.pose[1:], atol=0.05)
        m = sandbox_model(b)
        d = mujoco.MjData(m)
        d.qpos[2] = b.pose[0]
        d.qpos[3:9] = b.pose[1:]
        mujoco.mj_forward(m, d)
        self.assertTrue(math.isfinite(float(d.qpos.sum())))

    def test_same_body_gives_identical_telemetry(self):
        b = SandboxBody(foot_length=0.04, torso_mass=20.0)
        a = run_rollout(b, GaitParams(), seed=3, duration=1.0)
        c = run_rollout(b, GaitParams(), seed=3, duration=1.0)
        np.testing.assert_array_equal(a["torso_pos"], c["torso_pos"])

    def test_explanation_for_a_stable_design_does_not_invent_a_failure(self):
        p = build_sandbox_payload(SandboxBody(foot_length=0.16), GaitParams(), seed=0, duration=2.0)
        self.assertFalse(p["metrics"]["fell"])
        self.assertEqual(p["explanation"]["verdict"], "stayed_upright")

    def test_explain_outcome_cites_measurements(self):
        b = SandboxBody(foot_length=0.025, torque_limit=6.0, torso_mass=30.0)
        tel = run_rollout(b, GaitParams(), seed=0, duration=2.5, push=Push(0.5, 25.0, 0.15))
        ex = explain_outcome(tel, b, [])
        self.assertIn("verdict", ex)
        self.assertTrue(ex["reasons"])


if __name__ == "__main__":
    unittest.main()
