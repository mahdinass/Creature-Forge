import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from creature_forge.artifacts import save_run, telemetry_hash
from creature_forge.controller import GaitParams
from creature_forge.experiment import compare_designs
from creature_forge.morphology import BipedParams
from creature_forge.simulate import Push, run_rollout
from creature_forge.failures import detect_failures


class ArtifactTests(unittest.TestCase):
    def test_saved_run_is_reproducible_and_self_describing(self):
        body, gait = BipedParams(), GaitParams()
        tel = run_rollout(body, gait, seed=3, duration=1.0)
        with tempfile.TemporaryDirectory() as d:
            path = save_run(Path(d), "r1", body, gait, seed=3, duration=1.0, push=None,
                            telemetry=tel, events=detect_failures(tel, body))
            man = json.loads((path / "manifest.json").read_text())
            self.assertEqual(man["seed"], 3)
            self.assertEqual(man["body"]["foot_length"], body.foot_length)
            self.assertIn("mujoco_version", man)
            self.assertEqual(man["telemetry_sha256"], telemetry_hash(tel))
            with np.load(path / "telemetry.npz") as loaded:
                np.testing.assert_array_equal(loaded["torso_pitch"], tel["torso_pitch"])
            again = run_rollout(body, gait, seed=3, duration=1.0)
            self.assertEqual(telemetry_hash(again), man["telemetry_sha256"])


class CompareTests(unittest.TestCase):
    def test_changing_foot_length_changes_outcome_under_matched_seeds(self):
        push = Push(time=1.0, force=25.0, duration=0.15)
        res = compare_designs(BipedParams(foot_length=0.08), BipedParams(foot_length=0.16),
                              GaitParams(), seeds=(0, 1, 2), duration=4.0, push=push)
        self.assertEqual(res["baseline"]["fall_rate"], 1.0)
        self.assertEqual(res["candidate"]["fall_rate"], 0.0)
        self.assertEqual(res["seeds"], [0, 1, 2])
        self.assertGreater(res["candidate"]["mean_min_torso_height"],
                           res["baseline"]["mean_min_torso_height"])


if __name__ == "__main__":
    unittest.main()
