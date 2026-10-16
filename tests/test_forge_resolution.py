"""Push measurement resolution is a spec field: finer bisection costs 2 rollouts per extra step and per direction, and the arena's
tie tolerance follows the spec actually used (investigations measure every arm at 0.625 N)."""
import unittest

from creature_forge import arena, challenges as ch, investigation as inv
from creature_forge.creatures import default_controllers, normalize_body

DEFAULT = normalize_body({"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.16, "foot_friction": 1.0,
                          "torque_limit": 60.0, "leg_density": 1000.0}, "experimental")


class ResolutionTests(unittest.TestCase):
    def test_default_stays_five_steps_and_the_spec_round_trips(self):
        s = ch.default_spec("push", [100701])
        self.assertEqual(s.bisection_steps, 5)
        self.assertEqual(ch.ChallengeSpec.from_dict({**s.to_dict(), "bisection_steps": 7}).bisection_steps, 7)
        for bad in (2, 10, 7.0, True):
            with self.assertRaises(ValueError):
                ch.ChallengeSpec.from_dict({**s.to_dict(), "bisection_steps": bad})

    def test_seven_steps_cost_and_resolution(self):
        spec = ch.ChallengeSpec.from_dict({**ch.default_spec("push", [100702]).to_dict(), "bisection_steps": 7})
        r = ch.run_seed(DEFAULT, default_controllers(), spec, 100702)
        self.assertEqual(r.rollouts, 1 + 2 * (1 + 7))
        self.assertAlmostEqual(r.metrics["force_resolution_N"], 0.625)
        self.assertAlmostEqual(arena.resolution_for("push", spec), 0.625)
        self.assertEqual(inv.ARENA_PUSH_BISECTION_STEPS, 7)


if __name__ == "__main__":
    unittest.main()
