import unittest

from fastapi.testclient import TestClient

from creature_forge.studio.app import create_app


class StudioApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(create_app())

    def test_schema_exposes_bounds_defaults_and_phase0_preset(self):
        r = self.c.get("/api/schema").json()
        self.assertEqual(r["body"]["bounds"]["foot_length"], [0.06, 0.30])
        self.assertEqual(r["body"]["defaults"]["foot_length"], 0.16)
        self.assertEqual(r["preset"]["push"]["force"], 25.0)

    def test_simulate_returns_real_fall_for_short_foot(self):
        r = self.c.post("/api/simulate", json={"body": {"foot_length": 0.08}, "seed": 0, "duration": 3.0,
                                              "push": {"time": 1.0, "force": 25.0, "duration": 0.15}})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["metrics"]["fell"])
        self.assertEqual(d["body"]["foot_length"], 0.08)

    def test_out_of_bounds_parameter_is_422_not_clipped(self):
        r = self.c.post("/api/simulate", json={"body": {"foot_length": 5.0}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("foot_length", r.text)

    def test_unknown_parameter_rejected(self):
        self.assertEqual(self.c.post("/api/simulate", json={"body": {"wings": 2}}).status_code, 422)

    def test_phase0_comparison_uses_matched_seed_and_push(self):
        d = self.c.get("/api/experiments/phase0").json()
        self.assertEqual(d["baseline"]["push"], d["candidate"]["push"])
        self.assertEqual(d["baseline"]["seed"], d["candidate"]["seed"])
        self.assertEqual(d["baseline"]["body"]["foot_length"], 0.08)
        self.assertEqual(d["candidate"]["body"]["foot_length"], 0.16)
        self.assertTrue(d["baseline"]["metrics"]["fell"])
        self.assertFalse(d["candidate"]["metrics"]["fell"])
        self.assertEqual(d["matched_seed_summary"]["baseline"]["fall_rate"], 1.0)
        self.assertEqual(d["matched_seed_summary"]["candidate"]["fall_rate"], 0.0)

    def test_sketch_compile_ok_and_unsupported(self):
        sk = self.c.get("/api/sketch/default").json()
        ok = self.c.post("/api/sketch/compile", json=sk).json()
        self.assertTrue(ok["ok"])
        self.assertAlmostEqual(ok["params"]["thigh_length"], 0.30, places=6)
        sk["nodes"]["tail"] = [-0.2, 0.0]
        bad = self.c.post("/api/sketch/compile", json=sk).json()
        self.assertFalse(bad["ok"])
        self.assertNotIn("params", bad)


if __name__ == "__main__":
    unittest.main()
