import unittest

from creature_forge.morphology import BipedParams
from creature_forge.sketch import SketchError, compile_sketch, default_sketch, normalize_sketch, support_info


class SketchTests(unittest.TestCase):
    def test_default_sketch_round_trips_default_body(self):
        body = compile_sketch(default_sketch(BipedParams()))
        base = BipedParams()
        self.assertAlmostEqual(body.thigh_length, base.thigh_length, places=6)
        self.assertAlmostEqual(body.shank_length, base.shank_length, places=6)
        self.assertAlmostEqual(body.foot_length, base.foot_length, places=6)

    def test_dragging_ankle_changes_shank_length_only(self):
        sk = default_sketch(BipedParams())
        sk["nodes"]["ankle"][1] -= 0.10
        sk["nodes"]["toe"][1] -= 0.10
        body = compile_sketch(sk)
        self.assertAlmostEqual(body.shank_length, 0.40, places=6)
        self.assertAlmostEqual(body.thigh_length, 0.30, places=6)

    def test_unsupported_topology_is_rejected_with_reasons_not_converted(self):
        sk = default_sketch(BipedParams())
        sk["nodes"]["tail"] = [-0.2, 0.0]
        sk["segments"].append(["hip", "tail"])
        with self.assertRaises(SketchError) as cm:
            compile_sketch(sk)
        self.assertTrue(any("unsupported" in e.lower() for e in cm.exception.errors))

    def test_geometry_violations_are_reported(self):
        sk = default_sketch(BipedParams())
        sk["nodes"]["knee"] = [0.0, 0.95]  # knee above hip
        with self.assertRaises(SketchError) as cm:
            compile_sketch(sk)
        self.assertTrue(any("below the hip" in e for e in cm.exception.errors))

    def test_out_of_bounds_length_rejected(self):
        sk = default_sketch(BipedParams())
        sk["nodes"]["ankle"][1] -= 1.0
        with self.assertRaises(SketchError):
            compile_sketch(sk)


class NormalizeTests(unittest.TestCase):
    """Near-valid sketches are projected deterministically onto the supported planar biped; the rest is explained."""

    def sk(self):
        return default_sketch(BipedParams())

    def test_valid_sketch_needs_no_adjustment_and_matches_compile(self):
        r = normalize_sketch(self.sk())
        self.assertTrue(r["ok"])
        self.assertEqual(r["adjustments"], [])
        for k, v in compile_sketch(self.sk()).as_dict().items():
            self.assertAlmostEqual(r["params"][k], v, places=6)

    def test_sideways_knee_within_tolerance_is_straightened_and_reported(self):
        s = self.sk()
        s["nodes"]["knee"][0] += 0.05
        r = normalize_sketch(s)
        self.assertTrue(r["ok"])
        self.assertEqual(r["sketch"]["nodes"]["knee"][0], r["sketch"]["nodes"]["ankle"][0])
        adj = [a for a in r["adjustments"] if a["node"] == "knee"]
        self.assertEqual(len(adj), 1)
        self.assertIn("straight", adj[0]["message"].lower())

    def test_sideways_knee_beyond_tolerance_is_rejected_not_silently_fixed(self):
        s = self.sk()
        s["nodes"]["knee"][0] += 0.30
        r = normalize_sketch(s)
        self.assertFalse(r["ok"])
        self.assertIsNone(r["params"])
        self.assertTrue(any("bent" in e.lower() or "sideways" in e.lower() for e in r["errors"]))

    def test_tilted_foot_within_tolerance_is_levelled(self):
        s = self.sk()
        s["nodes"]["toe"][1] += 0.03
        r = normalize_sketch(s)
        self.assertTrue(r["ok"])
        self.assertEqual(r["sketch"]["nodes"]["toe"][1], r["sketch"]["nodes"]["ankle"][1])

    def test_floating_skeleton_is_lowered_to_stand_on_the_ground(self):
        s = self.sk()
        for n in s["nodes"].values():
            n[1] += 0.2
        r = normalize_sketch(s)
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["sketch"]["nodes"]["ankle"][1], 0.04)
        self.assertEqual(r["params"], BipedParams().as_dict())  # lengths unchanged by a rigid translation
        self.assertTrue(any(a["kind"] == "translate" for a in r["adjustments"]))

    def test_slightly_too_long_segment_is_clamped_to_the_physical_bound_and_reported(self):
        s = self.sk()
        s["nodes"]["hip"][1] += 0.33  # thigh 0.63 > 0.60 bound
        r = normalize_sketch(s)
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["params"]["thigh_length"], 0.60)
        self.assertTrue(any(a["kind"] == "clamp" for a in r["adjustments"]))

    def test_far_out_of_range_segment_is_an_error(self):
        s = self.sk()
        s["nodes"]["hip"][1] += 1.0
        r = normalize_sketch(s)
        self.assertFalse(r["ok"])
        self.assertTrue(any("thigh" in e.lower() for e in r["errors"]))

    def test_unsupported_topology_is_explained_and_never_converted(self):
        s = self.sk()
        s["nodes"]["tail"] = [-0.3, 0.5]
        s["segments"].append(["hip", "tail"])
        r = normalize_sketch(s)
        self.assertFalse(r["ok"])
        self.assertIsNone(r["sketch"])
        self.assertTrue(any("tail" in e and "planar biped" in e for e in r["errors"]))

    def test_extras_are_validated_and_carried_into_params(self):
        r = normalize_sketch(self.sk(), extras={"torso_mass": 8.0, "foot_friction": 1.4})
        self.assertTrue(r["ok"])
        self.assertEqual(r["params"]["torso_mass"], 8.0)
        bad = normalize_sketch(self.sk(), extras={"torso_mass": 80.0})
        self.assertFalse(bad["ok"])
        self.assertTrue(any("torso_mass" in e for e in bad["errors"]))
        unknown = normalize_sketch(self.sk(), extras={"wings": 2})
        self.assertFalse(unknown["ok"])

    def test_normalization_is_deterministic_and_idempotent(self):
        s = self.sk()
        s["nodes"]["knee"][0] += 0.04
        s["nodes"]["toe"][1] -= 0.02
        a = normalize_sketch(s)
        b = normalize_sketch(s)
        self.assertEqual(a, b)
        again = normalize_sketch(a["sketch"])
        self.assertEqual(again["adjustments"], [])
        self.assertEqual(again["params"], a["params"])

    def test_support_info_states_freedoms_and_limits(self):
        info = support_info()
        self.assertIn("thigh_length", info["freedoms"])
        self.assertTrue(info["not_supported"])
        self.assertIn("planar", info["summary"].lower())


if __name__ == "__main__":
    unittest.main()
