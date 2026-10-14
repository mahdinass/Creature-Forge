import unittest

from fastapi.testclient import TestClient

from creature_forge.studio.app import create_app


class LocomotionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(create_app())

    def test_summary_reports_budget_accounting_and_curves(self):
        r = self.c.get("/api/locomotion/summary")
        self.assertEqual(r.status_code, 200, r.text)
        s = r.json()
        for m in ("random_search", "differential_evolution"):
            self.assertEqual(s["methods"][m]["rollouts"], 600)
            self.assertEqual(len(s["methods"][m]["best_so_far"]), 200)
        self.assertEqual(set(s["seed_roles"]), {"train", "diagnostic", "heldout"})
        self.assertIn("random_search", s["controllers"])
        self.assertIn("random_search", s["heldout"]["controllers"])

    def test_replay_is_viewer_compatible_and_carries_the_gate_verdict(self):
        r = self.c.get("/api/locomotion/replay", params={"controller": "random_search", "seed": 3000,
                                                          "duration": 2.0})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        n = len(d["time"])
        self.assertGreater(n, 100)
        self.assertEqual(len(d["frames"]["pos"]), n)
        self.assertEqual(len(d["series"]["foot_contact"]), n)
        self.assertEqual(d["role"], "heldout")
        self.assertIn(d["locomotion"]["label"], {"walking", "fall", "falling_forward", "slow_or_few_steps"})
        self.assertIn("violations", d["locomotion"])
        self.assertGreater(d["metrics"]["peak_torso_vx"], 0.1)  # measured from the trajectory, not a placeholder

    def test_replay_is_deterministic_and_matches_saved_heldout_label(self):
        a = self.c.get("/api/locomotion/replay", params={"controller": "standing", "seed": 3001, "duration": 2.0}).json()
        b = self.c.get("/api/locomotion/replay", params={"controller": "standing", "seed": 3001, "duration": 2.0}).json()
        self.assertEqual(a["series"]["torso_x"], b["series"]["torso_x"])
        self.assertEqual(a["locomotion"]["label"], "stationary")

    def test_replay_rejects_unknown_controller_unregistered_seed_and_bad_duration(self):
        self.assertEqual(self.c.get("/api/locomotion/replay", params={"controller": "nope"}).status_code, 404)
        self.assertEqual(self.c.get("/api/locomotion/replay", params={"controller": "standing", "seed": 5}).status_code, 422)
        self.assertEqual(self.c.get("/api/locomotion/replay", params={"controller": "standing", "seed": 3000,
                                                                       "duration": 999}).status_code, 422)

    def test_summary_is_404_when_results_missing(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            c = TestClient(create_app(locomotion_dir=Path(d)))
            self.assertEqual(c.get("/api/locomotion/summary").status_code, 404)


if __name__ == "__main__":
    unittest.main()
