import unittest

import numpy as np

from creature_forge.controller import GaitParams
from creature_forge.morphology import BipedParams
from creature_forge.render_export import (build_run_payload, mj_to_three_pos, mj_to_three_quat)
from creature_forge.simulate import Push


def qrot(q_xyzw, v):
    x, y, z, w = q_xyzw
    u = np.array([x, y, z])
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def qrot_wxyz(q, v):
    return qrot((q[1], q[2], q[3], q[0]), v)


class CoordinateTests(unittest.TestCase):
    def test_position_maps_zup_to_yup_right_handed(self):
        np.testing.assert_allclose(mj_to_three_pos([1, 2, 3]), [1, 3, -2])

    def test_quaternion_conversion_commutes_with_vector_rotation(self):
        rng = np.random.default_rng(0)
        for _ in range(20):
            q = rng.standard_normal(4)
            q /= np.linalg.norm(q)
            v = rng.standard_normal(3)
            lhs = mj_to_three_pos(qrot_wxyz(q, v))
            rhs = qrot(mj_to_three_quat(q), mj_to_three_pos(v))
            np.testing.assert_allclose(lhs, rhs, atol=1e-12)


class PayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = build_run_payload(BipedParams(foot_length=0.08), GaitParams(), seed=0, duration=3.0,
                                  push=Push(1.0, 25.0, 0.15))

    def test_scene_lists_render_geoms_without_floor(self):
        parts = [g["part"] for g in self.p["scene"]["geoms"]]
        self.assertEqual(sorted(parts), sorted(["torso", "thigh_l", "shank_l", "foot_l",
                                                "thigh_r", "shank_r", "foot_r"]))
        self.assertEqual(self.p["scene"]["frame"], "three-y-up")

    def test_frames_match_telemetry_length_and_are_finite(self):
        n = len(self.p["time"])
        self.assertEqual(len(self.p["frames"]["pos"]), n)
        self.assertEqual(len(self.p["frames"]["pos"][0]), 7)
        self.assertTrue(np.all(np.isfinite(np.array(self.p["frames"]["pos"]))))
        for k in ("torso_height", "torso_pitch", "foot_contact"):
            self.assertEqual(len(self.p["series"][k]), n, k)

    def test_limbs_stay_connected_and_feet_rest_on_ground_in_first_frame(self):
        geoms = self.p["scene"]["geoms"]
        idx = {g["part"]: i for i, g in enumerate(geoms)}

        def ends(part, k):
            g = geoms[idx[part]]
            c = np.array(self.p["frames"]["pos"][k][idx[part]])
            q = self.p["frames"]["quat"][k][idx[part]]
            axis = qrot(q, np.array([0, 1.0, 0]))  # three-frame capsule axis is local Y
            h = g["size"][1]
            return c + axis * h, c - axis * h

        for k in (0, len(self.p["time"]) // 2, len(self.p["time"]) - 1):
            for s in "lr":
                t_a, t_b = ends(f"thigh_{s}", k)
                s_a, s_b = ends(f"shank_{s}", k)
                joint_gap = min(np.linalg.norm(t_b - s_a), np.linalg.norm(t_a - s_b),
                                np.linalg.norm(t_a - s_a), np.linalg.norm(t_b - s_b))
                self.assertLess(joint_gap, 1e-4)  # knee: thigh end coincides with shank end (payload rounds to 1e-5 m)
        foot = self.p["frames"]["pos"][0][idx["foot_l"]]
        self.assertAlmostEqual(foot[1] - 0.02, 0.0, delta=0.01)  # box half-height 0.02

    def test_model_stays_planar_and_lateral_leg_offset_is_display_only(self):
        # Offsetting legs inside MuJoCo changed contact outcomes (see INCIDENTS), so the offset must live
        # only in the declared presentation transform.
        import mujoco
        from creature_forge.morphology import build_model
        m = build_model(BipedParams())
        for side in "lr":
            self.assertEqual(m.body(f"thigh_{side}").pos[1], 0.0)
        self.assertEqual(self.p["scene"]["display_lateral_offset"], 0.07)

    def test_events_and_push_metadata_carry_simulation_time(self):
        falls = [e for e in self.p["events"] if e["kind"] == "fall"]
        self.assertEqual(len(falls), 1)
        self.assertEqual(self.p["push"], {"time": 1.0, "force": 25.0, "duration": 0.15})
        self.assertAlmostEqual(self.p["time"][-1], 3.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
