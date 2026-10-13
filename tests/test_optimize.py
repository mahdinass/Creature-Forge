import json
import unittest

import numpy as np

from creature_forge.locomotion import evaluate_controller
from creature_forge.optimize import (Executor, OptimizerConfig, _eval_job, candidate_export, controller_from_export,
                                     differential_evolution, jsonable, random_search)
from creature_forge.phasegait import LOWER, UPPER, PhaseGaitParams

CFG = OptimizerConfig(rollout_budget=36, duration=1.5, train_seeds=(1000, 1001), batch_size=6, de_pop=6)  # 18 candidates


class OptimizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with Executor(1) as ex:
            cls.rs, cls.rs_sum = random_search(CFG, ex)
            cls.de, cls.de_sum = differential_evolution(CFG, ex)

    def test_matched_budgets_count_every_rollout(self):
        for hist, summ in ((self.rs, self.rs_sum), (self.de, self.de_sum)):
            self.assertEqual(len(hist), 18)
            self.assertEqual(summ["rollouts"], 36)
            self.assertEqual(hist[-1]["rollouts_after"], 36)
            self.assertEqual([r["rollouts_before"] for r in hist], list(range(0, 36, 2)))

    def test_all_candidates_are_inside_bounds_and_recorded_with_provenance(self):
        for r in self.rs + self.de:
            v = np.array(r["vector"])
            self.assertTrue(np.all(v >= LOWER) and np.all(v <= UPPER))
            self.assertEqual(r["seeds"], [1000, 1001])
            self.assertIn("fitness_components", r)
            self.assertEqual(len(r["per_seed"]), 2)
        self.assertIn("git_commit", self.de_sum["provenance"])
        self.assertEqual(self.de_sum["hyperparameters"]["polish"], False)
        self.assertEqual(self.de_sum["config"]["rng_seed"], 0)

    def test_methods_share_the_initial_population(self):
        self.assertEqual([r["vector"] for r in self.rs[:6]], [r["vector"] for r in self.de[:6]])
        self.assertEqual([r["vector"] for r in self.rs[6:]] != [r["vector"] for r in self.de[6:]], True)

    def test_history_is_json_serialisable_and_keeps_failed_candidates(self):
        json.dumps(self.de, allow_nan=False)
        self.assertTrue(any(not r["feasible"] for r in self.de))

    def test_runs_are_reproducible(self):
        with Executor(1) as ex:
            again, _ = random_search(CFG, ex)
        self.assertEqual([r["fitness"] for r in again], [r["fitness"] for r in self.rs])

    def test_worker_count_does_not_change_results(self):
        small = OptimizerConfig(rollout_budget=12, duration=1.0, train_seeds=(1000, 1001), batch_size=6)
        with Executor(1) as e1:
            a, _ = random_search(small, e1)
        with Executor(2) as e2:
            b, _ = random_search(small, e2)
        self.assertEqual([r["fitness"] for r in a], [r["fitness"] for r in b])
        self.assertEqual([r["vector"] for r in a], [r["vector"] for r in b])


class FailureAndExportTests(unittest.TestCase):
    def test_worker_exception_is_returned_as_error_not_lost(self):
        out = _eval_job({"vector": [1e9] * len(LOWER), "body": OptimizerConfig().body, "seeds": [0],
                         "duration": 0.5})
        self.assertFalse(out["ok"])
        self.assertIn("ValueError", out["error"])

    def test_jsonable_maps_nonfinite_to_null(self):
        self.assertEqual(jsonable({"a": float("inf"), "b": np.float64("nan"), "c": np.bool_(True)}),
                         {"a": None, "b": None, "c": True})

    def test_export_round_trip_replays_identically(self):
        rec = {"params": PhaseGaitParams(freq=0.9).as_dict(), "seeds": [1000], "fitness": 0.0, "label": "fall",
               "feasible": False}
        d = candidate_export(rec, OptimizerConfig().body, {"run": "test"})
        ctrl, body = controller_from_export(json.loads(json.dumps(d)))
        a = evaluate_controller(ctrl, body, (7,), 1.5)
        b = evaluate_controller(*controller_from_export(d), (7,), 1.5)
        self.assertEqual(a["per_seed"][0]["forward_disp_upright"], b["per_seed"][0]["forward_disp_upright"])
        with self.assertRaises(ValueError):
            controller_from_export({"controller": "other"})


if __name__ == "__main__":
    unittest.main()
