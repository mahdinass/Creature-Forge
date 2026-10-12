import unittest

from creature_forge.morphology import BipedParams
from creature_forge.sketch import SketchError, compile_sketch, default_sketch


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


if __name__ == "__main__":
    unittest.main()
