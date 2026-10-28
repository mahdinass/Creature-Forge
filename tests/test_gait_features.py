import json
import math
import unittest

import numpy as np

from creature_forge import creature_walk as cw
from creature_forge import gait_features as gf
from creature_forge.sandbox import SandboxBody

DT = 0.005
MASS = 10.0
LIMIT = 60.0


def synthetic(n=800, v=0.6, accel=0.0, foot_ahead=0.1, fall_at=None, fall_pitch=1.2, body_z=0.5):
    """Hand-made 200 Hz trace. Torso x = v t + accel t^2/2. Touchdowns alternate every 100 samples, first (foot 0) at
    sample 20; each foot is loaded for 120 samples (20 samples of double support), foot x = torso x at its touchdown +
    `foot_ahead`, held until its next touchdown."""
    t = (np.arange(n) + 1) * DT
    x = v * t + 0.5 * accel * t * t
    force = np.zeros((n, 2))
    foot_x = np.zeros((n, 2))
    td = {0: list(range(20, n, 200)), 1: list(range(120, n, 200))}
    for k in (0, 1):
        cur = 0.0
        for i in range(n):
            if i in td[k]:
                cur = x[i] + foot_ahead
            foot_x[i, k] = cur
            if any(s <= i < s + 120 for s in td[k]):
                force[i, k] = 200.0
    pitch = np.zeros(n)
    if fall_at is not None:
        n = fall_at + 30
        pitch[fall_at:] = fall_pitch
    tau = np.zeros((n, 6))
    tau[:, 0] = 0.5 * LIMIT
    tau[:, 4] = -0.25 * LIMIT
    demand = np.zeros((n, 6))
    demand[:10, 1] = LIMIT
    return {"t": t[:n], "x": x[:n], "z": np.full(n, body_z), "pitch": pitch[:n], "q": np.zeros((n, 6)),
            "qd": np.zeros((n, 6)), "tau": tau, "demand": demand, "force": force[:n], "slip": np.zeros((n, 2)),
            "foot_x": foot_x[:n], "foot_z": np.zeros((n, 2)), "body_contact": np.zeros(n),
            "meta": {"seed": 0, "duration": 4.0, "mass": MASS, "weight": MASS * 9.81, "torque_limit": LIMIT,
                     "controller": "synthetic"}}


BODY = SandboxBody()   # legs 0.3 + 0.3, L = 0.6 m


class SyntheticTests(unittest.TestCase):
    def test_constant_velocity_alternating_steps(self):
        f = gf.gait_features(synthetic(), BODY)
        L = 0.6
        self.assertAlmostEqual(f["leg_length_m"], L)
        self.assertAlmostEqual(f["pendulum_freq_hz"], math.sqrt(9.81 / L) / (2 * math.pi))
        self.assertAlmostEqual(f["step_freq_hz"], 2.0, places=6)               # one touchdown per 0.5 s
        self.assertAlmostEqual(f["step_length_over_leg"], 0.3 / L, places=6)   # v * 0.5 s
        self.assertAlmostEqual(f["froude"], 0.36 / (9.81 * L), places=6)
        self.assertAlmostEqual(f["speed_trend_mps2"], 0.0, places=6)
        self.assertAlmostEqual(f["touchdown_foot_ahead_over_leg_mean"], 0.1 / L, places=6)
        self.assertAlmostEqual(f["touchdown_foot_ahead_trend"], 0.0, places=6)
        self.assertEqual(f["fall_direction"], 0.0)
        self.assertIsNone(f["fall_time_s"])
        self.assertIsNone(f["support_at_fall"])
        self.assertAlmostEqual(f["double_support_frac"], 0.2, places=1)
        self.assertAlmostEqual(f["flight_frac"], 0.0, places=1)
        self.assertAlmostEqual(f["torque_authority"], LIMIT / (MASS * 9.81 * L))
        self.assertAlmostEqual(f["peak_tau_over_limit_hip"], 0.5)
        self.assertAlmostEqual(f["peak_tau_over_limit_knee"], 0.25)
        self.assertAlmostEqual(f["peak_tau_over_limit_ankle"], 0.0)
        self.assertAlmostEqual(f["saturation_frac"], 10 / 800, places=6)
        self.assertAlmostEqual(f["pitch_mean_rad"], 0.0)
        self.assertAlmostEqual(f["pitch_drift_radps"], 0.0)

    def test_controller_freq_ratio(self):
        vec = list(cw.R2_WINNER)
        f = gf.gait_features(synthetic(), BODY, vec)
        self.assertAlmostEqual(f["controller_freq_hz"], vec[0])
        self.assertAlmostEqual(f["controller_freq_ratio"], vec[0] / f["pendulum_freq_hz"])
        self.assertIsNone(gf.gait_features(synthetic(), BODY)["controller_freq_ratio"])

    def test_accelerating_torso_has_positive_speed_trend(self):
        f = gf.gait_features(synthetic(v=0.0, accel=0.5), BODY)
        self.assertAlmostEqual(f["speed_trend_mps2"], 0.5, delta=0.01)
        self.assertLess(gf.gait_features(synthetic(v=1.0, accel=-0.2), BODY)["speed_trend_mps2"], 0.0)

    def test_forward_fall_with_double_support(self):
        f = gf.gait_features(synthetic(fall_at=530), BODY)
        self.assertEqual(f["fall_direction"], 1.0)
        self.assertAlmostEqual(f["fall_time_s"], 531 * DT, places=9)
        self.assertEqual(f["support_at_fall"], 2.0)
        self.assertAlmostEqual(f["pitch_at_end_rad"], 1.2)

    def test_backward_fall_with_single_support(self):
        f = gf.gait_features(synthetic(fall_at=480, fall_pitch=-1.2), BODY)
        self.assertEqual(f["fall_direction"], -1.0)
        self.assertEqual(f["support_at_fall"], 1.0)

    def test_feet_landing_behind_capture_point_give_negative_margin(self):
        f = gf.gait_features(synthetic(foot_ahead=-0.1), BODY)
        omega = math.sqrt(9.81 / 0.5)
        expect = (-0.1 - 0.6 / omega) / 0.6
        self.assertAlmostEqual(f["capture_margin_over_leg_mean"], expect, places=6)
        self.assertAlmostEqual(f["capture_margin_over_leg_min"], expect, places=6)
        self.assertAlmostEqual(f["capture_margin_over_leg_last"], expect, places=6)
        self.assertLess(f["capture_margin_over_leg_min"], 0.0)
        self.assertGreater(gf.gait_features(synthetic(foot_ahead=0.4), BODY)["capture_margin_over_leg_min"], 0.0)

    def test_fewer_than_two_steps_gives_none(self):
        f = gf.gait_features(synthetic(n=100), BODY)    # one touchdown only
        for k in ("step_freq_hz", "step_length_over_leg", "touchdown_foot_ahead_over_leg_mean",
                  "touchdown_foot_ahead_over_leg_last", "touchdown_foot_ahead_trend", "capture_margin_over_leg_mean",
                  "capture_margin_over_leg_min", "capture_margin_over_leg_last"):
            self.assertIsNone(f[k], k)
        self.assertIsNotNone(f["froude"])

    def test_docs_complete_and_values_finite_or_none(self):
        f = gf.gait_features(synthetic(), BODY, list(cw.R2_WINNER))
        self.assertEqual(set(f), set(gf.FEATURE_DOCS))
        for k, doc in gf.FEATURE_DOCS.items():
            self.assertTrue(doc.strip(), k)
        for tr in (synthetic(), synthetic(n=100), synthetic(fall_at=300), synthetic(n=2)):
            for k, v in gf.gait_features(tr, BODY, list(cw.R2_WINNER)).items():
                self.assertTrue(v is None or (isinstance(v, float) and math.isfinite(v)), (k, v))
        s = gf.summarize([gf.gait_features(synthetic(), BODY), gf.gait_features(synthetic(fall_at=530), BODY),
                          gf.gait_features(synthetic(fall_at=530, fall_pitch=-1.2), BODY)])
        self.assertEqual(s["n_seeds"], 3)
        self.assertAlmostEqual(s["forward_fall_frac"], 1 / 3)
        self.assertNotIn("fall_direction", s)
        self.assertEqual(set(s), set(gf.SUMMARY_DOCS))
        json.dumps(s)


class RealMuJoCoTests(unittest.TestCase):
    """Run on the VM only (MuJoCo)."""

    def test_default_body_with_r2_winner_walks(self):
        f = gf.features_for(SandboxBody(), cw.R2_WINNER, 100003, duration=10.0)
        print("\ndefault body:", json.dumps(f, sort_keys=True))
        self.assertIsNotNone(f["controller_freq_ratio"])
        self.assertEqual(f["fall_direction"], 0.0)
        self.assertGreater(f["step_freq_hz"], 0.0)

    def test_stilts_body_falls_forward(self):
        stilts = SandboxBody(thigh_length=0.55, shank_length=0.55, foot_length=0.07, torso_mass=4.7917)
        f = gf.features_for(stilts, cw.R2_WINNER, 100003, duration=10.0)
        print("\nstilts body:", json.dumps(f, sort_keys=True))
        self.assertEqual(f["fall_direction"], 1.0)
        self.assertIsNotNone(f["fall_time_s"])


if __name__ == "__main__":
    unittest.main()
