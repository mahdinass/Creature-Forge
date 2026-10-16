"""The walk-only `retune_controller` probe adapts the controller on TRAIN seeds (never the probe seeds), then measures the
unchanged body with the adapted controller on the probe seeds; adaptation rollouts are counted."""
import unittest

from creature_forge import probes as pb
from creature_forge.creatures import default_controllers, normalize_body

BODY = normalize_body({"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.05, "foot_friction": 1.0,
                       "torque_limit": 60.0, "leg_density": 1000.0}, "experimental")
VERSION = {"n": 1, "mode": "experimental", "body": BODY, "controllers": default_controllers()}
SPEC = {"kind": "walk", "seeds": [1], "duration": 10.0}


class RetuneProbeTests(unittest.TestCase):
    def setUp(self):
        self.adapt_calls, self.jobs = [], []

    def adapt(self, body, init, *, budget, train_seeds, noise_seed, pool):
        self.adapt_calls.append({"budget": budget, "train": list(train_seeds), "noise": noise_seed})
        return {"vector": [0.5] * len(init), "rollouts_used": 51, "improved": True}

    def job(self, j):
        self.jobs.append(j)
        walk = (j["controllers"] or {}).get("walk")
        score = 2.0 if walk and walk.get("vector") == [0.5] * 15 else 1.0
        return {"seed": j["seed"], "outcome": "FAIL", "score": score, "metrics": {}, "rollouts": 1}

    def test_walk_only_and_listed(self):
        self.assertIn("retune_controller", pb.available_probes(VERSION, "walk", SPEC))
        self.assertNotIn("retune_controller", pb.available_probes(VERSION, "push", {**SPEC, "kind": "push"}))

    def test_adapts_on_train_seeds_and_measures_on_probe_seeds(self):
        out = pb.run_probes(VERSION, "walk", SPEC, ["retune_controller"], [11, 12], job_fn=self.job, train_seeds=[21, 22, 23],
                            adapt_fn=self.adapt)
        self.assertEqual(self.adapt_calls, [{"budget": 48, "train": [21, 22, 23], "noise": pb.RETUNE_NOISE_SEED}])
        self.assertEqual({j["seed"] for j in self.jobs}, {11, 12})
        r = out["results"]["retune_controller"]
        self.assertEqual(r["median_delta"], 1.0)
        self.assertEqual(r["adaptation"]["rollouts_used"], 51)
        self.assertEqual(out["rollouts"], 4 + 51)   # 2 arms x 2 seeds + adaptation

    def test_refuses_without_or_overlapping_train_seeds(self):
        for train in (None, [11, 30]):
            with self.assertRaises(ValueError):
                pb.run_probes(VERSION, "walk", SPEC, ["retune_controller"], [11, 12], job_fn=self.job, train_seeds=train,
                              adapt_fn=self.adapt)


if __name__ == "__main__":
    unittest.main()
