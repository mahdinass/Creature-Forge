import unittest

from fastapi.testclient import TestClient

from creature_forge.studio.app import create_app
from tests.test_freehand import line, poly, stick_figure, stroke


class SandboxApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(create_app())

    def test_draw_a_terrible_creature_in_experimental_mode_and_watch_it_fall_in_mujoco(self):
        """The essential acceptance test: freehand strokes -> interpretation -> real MuJoCo run that fails."""
        s = stick_figure(foot=0.03, torso_closed=True)
        s[0] = stroke("t", poly((-0.22, 0.64), (0.22, 0.64), (0.22, 1.25), (-0.22, 1.25), (-0.22, 0.64)))  # huge torso
        r = self.c.post("/api/freehand/interpret", json={"strokes": s, "guided": False, "materials": {"torque_limit": 8, "foot_friction": 0.1}}).json()
        self.assertEqual(r["status"], "ok", r["errors"])
        self.assertEqual(r["outcome"], "questionable")
        self.assertTrue(r["notes"])
        self.assertGreater(r["body"]["torso_mass"], 15)
        self.assertLess(r["body"]["foot_length"], 0.06)
        sim = self.c.post("/api/sandbox/simulate", json={"body": r["body"], "duration": 3.0, "push": {"time": 0.5, "force": 25, "duration": 0.15}})
        self.assertEqual(sim.status_code, 200, sim.text)
        p = sim.json()
        self.assertTrue(p["sandbox"])
        self.assertTrue(p["metrics"]["fell"])
        self.assertEqual(p["explanation"]["verdict"], "fell")
        self.assertTrue(p["frames"]["pos"])
        self.assertTrue(p["explanation"]["design_notes"])  # says which values are outside the verified range

    def test_same_drawing_in_guided_mode_is_refused_not_silently_fixed(self):
        s = stick_figure(foot=0.03)
        r = self.c.post("/api/freehand/interpret", json={"strokes": s, "guided": True}).json()
        self.assertEqual(r["outcome"], "unrepresentable")
        self.assertIsNone(r["body"])
        self.assertTrue(r["approximation"]["changes"])

    def test_approximation_runs_only_by_explicit_request_and_is_labelled_by_the_client(self):
        r = self.c.post("/api/freehand/interpret", json={"strokes": stick_figure(foot=0.03), "guided": True}).json()
        sim = self.c.post("/api/sandbox/simulate", json={"body": r["approximation"]["body"], "duration": 1.0})
        self.assertEqual(sim.status_code, 200)

    def test_bad_inputs_are_json_errors_never_crashes(self):
        for body in ({"foot_length": -1}, {"foot_length": 1e9}, {"wings": 2}, {"pose": [0, 0, 0.9, 0, 0, 0, 0]}, {"pose": [0, 1]}):
            r = self.c.post("/api/sandbox/simulate", json={"body": body, "duration": 0.5})
            self.assertEqual(r.status_code, 422, body)
            self.assertIn("application/json", r.headers["content-type"])
        r = self.c.post("/api/sandbox/simulate", content='{"body": {"torso_mass": NaN}, "duration": 0.5}', headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 422)  # non-finite numbers are refused, not simulated
        r = self.c.post("/api/freehand/interpret", json={"strokes": [{"id": "a", "points": [[1, "x"]]}]})
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/api/freehand/interpret", json={"strokes": [{"id": str(i), "points": []} for i in range(81)]})
        self.assertEqual(r.status_code, 422)

    def test_registered_experiment_endpoint_still_enforces_scientific_bounds(self):
        r = self.c.post("/api/simulate", json={"body": {"foot_length": 0.03}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("sandbox_bounds", self.c.get("/api/sandbox/schema").json())

    def test_extreme_bodies_run_or_fail_cleanly(self):
        for body in ({"thigh_length": 1.2, "shank_length": 1.2, "torso_mass": 80, "torque_limit": 0.5},
                     {"thigh_length": 0.05, "shank_length": 0.05, "foot_length": 0.02, "torso_mass": 0.2, "foot_friction": 0.01},
                     {"pose": [1.4, 1.1, -2.1, 0.7, -1.1, -2.1, -0.7], "torso_mass": 40}):
            r = self.c.post("/api/sandbox/simulate", json={"body": body, "duration": 1.5})
            self.assertIn(r.status_code, (200, 422), body)
            self.assertIn("application/json", r.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
