import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import unittest

from fastapi.testclient import TestClient

from creature_forge import walking
from creature_forge.studio.app import create_app


class WalkingTests(unittest.TestCase):
    def test_summary_is_read_from_the_committed_records(self):
        s = walking.summary()
        self.assertEqual((s["winner_walking"], s["incumbent_walking"], s["n"]), (150, 91, 150))
        self.assertEqual(s["paired"]["winner_only"], 59)
        self.assertEqual(len(s["seeds"]), 150)
        self.assertTrue(s["featured"])
        self.assertIn("No language model", s["attribution"])

    def test_featured_seeds_are_ones_where_the_starting_controller_fell_and_the_improved_one_walked(self):
        s = walking.summary()
        by = {x["seed"]: x for x in s["seeds"]}
        for seed in s["featured"]:
            self.assertEqual(by[seed]["incumbent"]["label"], "fall")
            self.assertTrue(by[seed]["winner"]["walking"])

    def test_featured_replays_reproduce_the_committed_outcome_on_this_machine(self):
        seed = walking.summary()["featured"][0]
        a, b = walking.replay("incumbent", seed), walking.replay("r2_winner", seed)
        self.assertEqual(a["locomotion"]["label"], "fall")
        self.assertTrue(b["locomotion"]["walking"])
        self.assertEqual(a["committed"]["label"], "fall")

    def test_api_rejects_unknown_controllers_and_non_final_seeds_as_json(self):
        c = TestClient(create_app())
        self.assertEqual(c.get("/api/walking/replay", params={"which": "x", "seed": 8004}).status_code, 422)
        r = c.get("/api/walking/replay", params={"which": "incumbent", "seed": 1})
        self.assertEqual(r.status_code, 422)
        self.assertIn("application/json", r.headers["content-type"])
        self.assertEqual(c.get("/api/walking/summary").json()["n"], 150)


if __name__ == "__main__":
    unittest.main()
