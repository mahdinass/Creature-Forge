"""Every validated AI arm is validated together with its own matched-random twin on the same held-out seeds (like-for-like
control), even when another baseline ranks higher in screening."""
import unittest

from creature_forge import arena
from creature_forge.creatures import default_controllers, normalize_body

BODY = normalize_body({"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.05, "foot_friction": 1.0,
                       "torque_limit": 60.0, "leg_density": 1000.0}, "experimental")
VERSION = {"n": 1, "mode": "experimental", "body": BODY, "controllers": default_controllers()}


class TwinValidationTests(unittest.TestCase):
    def test_selected_ai_arm_is_validated_with_its_matched_twin(self):
        arms = [
            {"arm_id": "ai:P1", "source": "nemotron", "proposal_id": "P1",
             "edits": [{"param": "foot_length", "op": "scale", "value": 1.5, "target": "both"}]},
            {"arm_id": "random:P1", "source": "random_baseline", "proposal_id": "P1",
             "edits": [{"param": "leg_density", "op": "scale", "value": 0.8, "target": "both"}]},
            {"arm_id": "heuristic", "source": "heuristic", "proposal_id": None,
             "edits": [{"param": "foot_length", "op": "scale", "value": 1.3, "target": "both"}]},
        ]
        cfg = arena.ArenaConfig(screen_seeds=(100801, 100802), validate_seeds=(100811, 100812, 100813))
        rec = arena.run_arena(VERSION, "stand", arms, cfg, spec_overrides={"duration": 3.0})
        sel = rec["selection"]
        self.assertEqual(sel["ai"], "ai:P1")
        self.assertEqual(sel["matched_twin"], "random:P1")
        self.assertIn("random:P1", sel["validated"])
        self.assertIn("random:P1", rec["verdicts"])
        self.assertIn("ai:P1", rec["verdicts"])


if __name__ == "__main__":
    unittest.main()
