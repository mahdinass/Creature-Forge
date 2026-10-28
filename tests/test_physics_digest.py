"""Tests of the physics digest and the parametric counterfactual grammar (scientist v2, pilot1 audit F3/F4). No MuJoCo."""
import math
import unittest

from creature_forge import eng_tools as et
from creature_forge import fault_bench as fb
from creature_forge import physics_digest as pd

from tests.test_fault_bench import BODY, VEC

OBS = {"median": {"leg_length_m": 0.6, "step_freq_hz": 3.0, "com_vx_mean": 0.3, "com_vx_end": -0.4, "pitch_end": -0.5,
                  "saturation_frac_hip": 0.0, "saturation_frac_knee": 0.0, "saturation_frac_ankle": 0.0, "slip_fraction": 0.0,
                  "step_length_over_L": 0.09},
       "per_seed": [{"fell": True, "walking": False, "fall_direction": -1.0, "fall_time": 1.2, "label": "falling_backward"},
                    {"fell": True, "walking": False, "fall_direction": 1.0, "fall_time": 2.0, "label": "falling_forward"},
                    {"fell": False, "walking": True, "fall_direction": 0.0, "fall_time": None, "label": "walking"}],
       "n_fell": 2, "n_walking": 1}
REF = {"source": "test", "n_robots": 3, "quantities": {"step_length_over_L": {"p10": 0.15, "median": 0.18, "p90": 0.23, "n": 3},
                                                       "froude_number": {"p10": 0.01, "median": 0.02, "p90": 0.04, "n": 3}}}


class Derived(unittest.TestCase):
    def test_physics(self):
        v = [1.5] + [0.0] * 16
        d = pd.derived(OBS, None, v)
        self.assertAlmostEqual(d["pendulum_freq_hz"], math.sqrt(9.81 / 0.6) / (2 * math.pi))
        self.assertAlmostEqual(d["commanded_touchdowns_hz"], 3.0)
        self.assertAlmostEqual(d["cadence_measured_over_commanded"], 1.0)
        self.assertAlmostEqual(d["froude_number"], 0.09 / (9.81 * 0.6))
        self.assertEqual(d["max_saturation_frac"], 0.0)

    def test_leg_length_from_body(self):
        self.assertAlmostEqual(pd.leg_length({"median": {}}, {"thigh_length": 0.3, "shank_length": 0.3}), 0.6)

    def test_reference_stats(self):
        st = pd.reference_stats({"x": [1, 2, 3, 4, 5, None]})["x"]
        self.assertEqual((st["median"], st["n"]), (3, 5))
        self.assertAlmostEqual(st["p10"], 1.4)


class KeyFacts(unittest.TestCase):
    def test_signs_in_words_and_reference(self):
        txt = "\n".join(pd.key_facts(OBS, None, [1.5] + [0.0] * 16, ref=REF))
        self.assertIn("FORWARD, i.e. nose down / torso ahead, on 1; BACKWARD on 1", txt)
        self.assertIn("leaning BACKWARD", txt)
        self.assertIn("moving BACKWARD", txt)
        self.assertIn("torque saturation: none measured", txt)
        self.assertIn("step_length_over_L = 0.09 | healthy [0.15, 0.23] (median 0.18) -> BELOW", txt)

    def test_no_cause_words(self):
        txt = "\n".join(pd.key_facts(OBS, None, [1.5] + [0.0] * 16, ref=REF)).lower()
        for w in list(fb.FAULTS) + list(fb.TOOLS) + ["cause", "because", "repair", "diagnos"]:
            self.assertNotIn(w.lower(), txt, w)


class Parametric(unittest.TestCase):
    def test_levels_and_values(self):
        self.assertEqual(et.parametric_change("torso_mass", "x0.7"), {"param": "torso_mass", "op": "scale", "value": 0.7})
        c = et.parametric_change("pitch_ref", "-0.1R")
        self.assertEqual((c["op"], round(c["value"], 6)), ("add", -0.03))       # pitch_ref range [-0.05, 0.25]
        with self.assertRaises(ValueError):
            et.parametric_change("pitch_ref", "x2")
        self.assertEqual(et.parse_counterfactual("foot_length_x1.3"), et.COUNTERFACTUALS["foot_length_x1.3"])   # catalogue still works

    def test_workbench_accepts_parametric_and_refuses_out_of_bounds(self):
        from tests.test_scientist import make_bench
        b = make_bench()
        ok = b.counterfactual("foot_length@x1.5")
        self.assertTrue(ok["ok"])
        self.assertAlmostEqual(b.designs[ok["design_index"]]["body"]["foot_length"], BODY["foot_length"] * 1.5)
        used = b.ledger()["used"]
        bad = b.counterfactual("foot_length@x2&torso_mass@x0.5")     # 0.32 m > 0.30 m guided bound: refused, free, not clipped
        self.assertFalse(bad["ok"])
        self.assertEqual(b.ledger()["used"], used)
        self.assertFalse(b.counterfactual("bogus@x2")["ok"])
        self.assertEqual(VEC, list(b.designs[0]["vector"]))


if __name__ == "__main__":
    unittest.main()
