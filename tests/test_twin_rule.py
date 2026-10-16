"""matched_random_v2: a matched-random twin never reproduces the AI's own edit (live walk run i-7ef344a03dd2 drew the identical
foot_length x 1.4 under v1, which made the control degenerate)."""
import unittest

from creature_forge import baselines, interventions as iv
from creature_forge.creatures import default_controllers, normalize_body

BODY = normalize_body({"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.05, "foot_friction": 1.0,
                       "torque_limit": 60.0, "leg_density": 1000.0}, "experimental")
VERSION = {"n": 1, "mode": "experimental", "body": BODY, "controllers": default_controllers()}


class TwinRuleTests(unittest.TestCase):
    def test_no_seed_draws_the_ai_edit_itself(self):
        ai = [iv.Edit("foot_length", "scale", 1.4, "both")]
        draws = [baselines.matched_random(VERSION, "walk", ai, baselines.make_rng("i-test", f"P{k}")) for k in range(300)]
        twins = [d for d in draws if d]
        self.assertTrue(twins)
        for d in twins:
            self.assertFalse(d[0].param == "foot_length" and d[0].target == "both" and abs(d[0].value - 1.4) < 1e-9, d)

    def test_version_is_recorded(self):
        self.assertEqual(baselines.MATCHED_RANDOM_VERSION, "matched_random_v2")


if __name__ == "__main__":
    unittest.main()
