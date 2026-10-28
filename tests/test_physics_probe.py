"""Tests for creature_forge.physics_probe: bit-identical dynamics, documentation coverage, physical sanity of the measurements."""
import json
import math
import unittest

import numpy as np

from creature_forge import creature_walk as cw
from creature_forge import physics_probe as pp
from creature_forge.forge_pool import ForgePool
from creature_forge.phasegait_init import controller_from_vector
from creature_forge.sandbox import SandboxBody

R2 = list(cw.R2_WINNER)
DEFAULT = SandboxBody()
STILTS = SandboxBody(thigh_length=0.55, shank_length=0.55, foot_length=0.07, torso_mass=4.7917)
SEED = 100003
SAME_KEYS = ("t", "x", "z", "pitch", "q", "qd", "tau", "demand", "force", "slip", "foot_x", "foot_z", "body_contact")


def vec17(kd, kv):
    return R2 + [kd, kv]


def finite_or_none(d):
    for k, v in d.items():
        if isinstance(v, dict):
            finite_or_none(v)
        elif v is not None and not isinstance(v, (bool, str)):
            assert math.isfinite(v), (k, v)


def cp_inside_fraction(tr):
    com, vel = tr["com"], tr["com_vel"]
    xcp = com[:, 0] + vel[:, 0] / np.sqrt(9.81 / com[:, 2])
    ok = np.isfinite(tr["sup_min"])
    return float(np.mean(((tr["sup_min"] <= xcp) & (xcp <= tr["sup_max"]))[ok])), int(ok.sum())


class BitIdentity(unittest.TestCase):
    def check(self, body, vector, duration=6.0, seed=SEED):
        ref = cw.rollout(controller_from_vector(vector, body=body), body, seed, duration)
        rich = pp.rich_rollout(body, vector, seed, duration=duration)
        self.assertGreater(len(ref["t"]), 100)
        for k in SAME_KEYS:
            self.assertTrue(np.array_equal(ref[k], rich[k]), f"{k} differs")
        return rich

    def test_default_body(self):
        self.check(DEFAULT, R2)

    def test_stilts_body(self):
        rich = self.check(STILTS, R2, duration=10.0)
        self.assertLess(len(rich["t"]), 2000)   # fell: identical early stop

    def test_17d_foot_placement(self):
        self.check(DEFAULT, vec17(0.5, 0.5))
        self.check(STILTS, vec17(0.5, 0.5))

    def test_other_seed(self):
        self.check(DEFAULT, R2, seed=100019)


class Docs(unittest.TestCase):
    def test_every_key_documented_and_finite(self):
        tr = pp.rich_rollout(STILTS, R2, SEED, duration=10.0)
        s = pp.summarize(tr, STILTS)
        finite_or_none(s)
        for k in s:
            self.assertIn(k, pp.PROBE_DOCS, k)
        for k in s["pre_fall"]:
            self.assertIn("pre_fall." + k, pp.PROBE_DOCS, k)
        for k, v in pp.PROBE_DOCS.items():
            self.assertTrue(isinstance(v, str) and v.endswith("."), k)
        for need in ("fall_time", "fall_direction", "time_upright", "slip_fraction", "max_friction_utilisation", "step_freq_hz",
                     "step_length_over_L", "double_support_fraction", "flight_fraction", "swing_peak_clearance_min_over_L",
                     "saturation_frac_hip", "saturation_frac_knee", "saturation_frac_ankle", "tracking_error_hip",
                     "capture_margin_over_L_mean", "com_vx_slope", "angmom_norm_end", "pitch_rate_mean"):
            self.assertIn(need, pp.PROBE_DOCS)

    def test_no_fall_has_no_prefall(self):
        s = pp.summarize(pp.rich_rollout(DEFAULT, R2, SEED, duration=6.0), DEFAULT)
        self.assertEqual(s["fall_direction"], 0.0)
        self.assertIsNone(s["fall_time"])
        self.assertIsNone(s["pre_fall"])
        finite_or_none(s)


class Sanity(unittest.TestCase):
    def test_standing_com_height_matches_analytic(self):
        b = DEFAULT
        t, s_, f = b.thigh_length, b.shank_length, b.foot_length
        rho, mt = b.leg_density, b.torso_mass
        zt = (t + s_ + 0.16) + 0.002           # torso frame height after the rollout's placement (feet 2 mm above floor)
        hip = zt - 0.12

        def capsule(r, length):
            return rho * (math.pi * r * r * length + 4.0 / 3.0 * math.pi * r ** 3)
        # the torso box is 0.12 x 0.12 x 0.3 m but its density is torso_mass / (0.2*0.12*0.3): its true mass is 0.6 x torso_mass
        parts = [(mt * (0.12 * 0.12 * 0.3) / (0.2 * 0.12 * 0.3), zt + 0.03)]
        for _ in range(2):
            parts += [(capsule(0.04, t), hip - t / 2), (capsule(0.035, s_), hip - t - s_ / 2),
                      (rho * f * 0.08 * 0.04, hip - t - s_ - 0.02)]
        expected = sum(m * z for m, z in parts) / sum(m for m, _ in parts)
        tr = pp.rich_rollout(b, R2, SEED, duration=0.1, perturb=0.0)
        got = float(tr["com"][0, 2])
        print(f"\nstanding COM z: measured {got:.4f} m, analytic {expected:.4f} m")
        self.assertAlmostEqual(got, expected, delta=0.01)
        self.assertAlmostEqual(sum(m for m, _ in parts), tr["meta"]["mass"], delta=1e-6 * tr["meta"]["mass"] + 1e-9)

    def test_default_walker(self):
        tr = pp.rich_rollout(DEFAULT, R2, SEED, duration=10.0)
        s = pp.summarize(tr, DEFAULT)
        frac, n = cp_inside_fraction(tr)
        print("\ndefault walker:", json.dumps({k: v for k, v in s.items() if k != "pre_fall"}, sort_keys=True))
        print(f"capture point inside support interval: {frac:.3f} of {n} supported samples")
        self.assertEqual(s["fall_direction"], 0.0)
        self.assertGreater(s["com_vx_mean"], 0.1)
        # NOT "mostly inside": at 0.5 m/s a walker's capture point lies beyond the stance foot (that is why it steps); what the
        # instrument must show is that it is far less beyond the toe than for the falling stilts (next test)
        self.assertLess(s["cp_ahead_of_front_edge_over_L_mean"], 0.25)
        self.assertGreater(s["capture_margin_over_L_mean"], -0.3)

    def test_stilts_forward_instability(self):
        tr = pp.rich_rollout(STILTS, R2, SEED, duration=10.0)
        s = pp.summarize(tr, STILTS)
        print("\nstilts:", json.dumps(s, sort_keys=True))
        self.assertEqual(s["fall_direction"], 1.0)
        pf = s["pre_fall"]
        self.assertGreater(pf["pitch"], 0.0)
        self.assertGreater(pf["com_ahead_of_cop_over_L"], 0.0)
        self.assertGreater(pf["cp_ahead_of_front_edge_over_L"], 0.0)
        self.assertLess(pf["capture_margin_over_L"], 0.0)
        d = pp.summarize(pp.rich_rollout(DEFAULT, R2, SEED, duration=10.0), DEFAULT)
        self.assertLess(pf["capture_margin_over_L"], d["capture_margin_over_L_mean"] - 0.2)
        self.assertGreater(s["capture_margin_over_L_slope"] * -1, 0.0)    # margin deteriorates towards the fall

    def test_ground_force_sign_and_impulse(self):
        """Ground tangential force summed over both feet must equal m * d(v_com)/dt on average (only the ground pushes sideways)."""
        tr = pp.rich_rollout(DEFAULT, R2, SEED, duration=10.0)
        m = tr["meta"]["mass"]
        mean_f = float(tr["ft_x"].sum(1).mean())
        vx = tr["com_vel"][:, 0]
        expected = m * (vx[-1] - vx[0]) / (tr["t"][-1] - tr["t"][0])
        print(f"\nmean ground x-force {mean_f:.3f} N vs m*dv/dt {expected:.3f} N (m={m:.2f} kg)")
        self.assertAlmostEqual(mean_f, expected, delta=max(0.25 * abs(expected), 1.0))

    def test_low_friction_raises_utilisation(self):
        hi = pp.summarize(pp.rich_rollout(DEFAULT, R2, SEED, duration=10.0), DEFAULT)
        low_body = SandboxBody(foot_friction=0.05)
        lo = pp.summarize(pp.rich_rollout(low_body, R2, SEED, duration=10.0), low_body)
        print(f"\nfriction utilisation: mu=1.0 max {hi['max_friction_utilisation']} p95 {hi['friction_utilisation_p95']} "
              f"slip {hi['slip_fraction']}; mu=0.05 max {lo['max_friction_utilisation']} p95 {lo['friction_utilisation_p95']} "
              f"slip {lo['slip_fraction']}")
        self.assertGreater(lo["friction_utilisation_p95"], 2.0 * hi["friction_utilisation_p95"])
        self.assertGreater(lo["max_friction_utilisation"], 0.9)
        tr = pp.rich_rollout(DEFAULT, R2, SEED, duration=3.0, friction_factor=0.05)
        self.assertAlmostEqual(tr["meta"]["foot_friction"], 0.05)

    def test_low_torque_raises_ankle_saturation(self):
        ref = pp.summarize(pp.rich_rollout(DEFAULT, R2, SEED, duration=10.0), DEFAULT)
        weak = SandboxBody(torque_limit=8.0)
        w = pp.summarize(pp.rich_rollout(weak, R2, SEED, duration=10.0), weak)
        print(f"\nankle saturation: limit 60 {ref['saturation_frac_ankle']}, limit 8 {w['saturation_frac_ankle']}; "
              f"hip {ref['saturation_frac_hip']} -> {w['saturation_frac_hip']}")
        self.assertGreater(w["saturation_frac_ankle"], ref["saturation_frac_ankle"] + 0.1)


class Observe(unittest.TestCase):
    def test_observe_inline_and_pool(self):
        seeds = [100003, 100019]
        a = pp.observe(DEFAULT, R2, seeds, duration=4.0)
        self.assertEqual(a["rollouts"], 2)
        self.assertEqual(len(a["per_seed"]), 2)
        self.assertEqual(a["errors"], [])
        finite_or_none(a["median"])
        self.assertEqual(a["n_fell"], sum(p["fell"] for p in a["per_seed"]))
        pool = ForgePool(max_workers=2)
        try:
            b = pp.observe(DEFAULT, R2, seeds, duration=4.0, pool=pool)
        finally:
            pool.close()
        self.assertEqual(json.dumps(a["per_seed"], sort_keys=True), json.dumps(b["per_seed"], sort_keys=True))
        self.assertEqual(a["median"], b["median"])

    def test_observe_labels_match_frozen_metric(self):
        from creature_forge import locomotion as loc
        o = pp.observe(STILTS, R2, [SEED], duration=10.0, variation=None)
        tr = cw.rollout(controller_from_vector(R2), STILTS, SEED, 10.0)
        m = loc.compute_metrics(tr, cw.creature_criteria(STILTS))
        self.assertEqual(o["per_seed"][0]["label"], m["label"])
        self.assertEqual(o["n_walking"], int(m["walking"]))
        self.assertEqual(o["n_fell"], int(m["fell"]))
        self.assertIsNotNone(o["pre_fall_median"])

    def test_observe_error_is_reported(self):
        o = pp.observe(DEFAULT, [0.0] * 3, [SEED], duration=1.0)
        self.assertEqual(len(o["errors"]), 1)
        self.assertEqual(o["per_seed"], [])


if __name__ == "__main__":
    unittest.main()
