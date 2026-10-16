import unittest

import numpy as np

from creature_forge import creature_walk as cw
from creature_forge import locomotion as loc
from creature_forge import r2
from creature_forge.forge_pool import ForgePool
from creature_forge.morphology import BipedParams
from creature_forge.phasegait_init import LOWER15, UPPER15, controller_from_vector
from creature_forge.sandbox import SandboxBody


class CriteriaTests(unittest.TestCase):
    def test_default_body_gets_exactly_the_frozen_criteria(self):
        self.assertEqual(cw.creature_criteria(SandboxBody()), loc.DEFAULT_CRITERIA)
        self.assertIs(cw.creature_criteria(SandboxBody()), loc.DEFAULT_CRITERIA)
        self.assertEqual(cw.creature_criteria(SandboxBody(thigh_length_r=0.3, shank_length_r=0.3, foot_length_r=0.16)),
                         loc.DEFAULT_CRITERIA)

    def test_length_carrying_gates_scale_with_mean_leg_length_and_nothing_else(self):
        tall = cw.creature_criteria(SandboxBody(thigh_length=0.6, shank_length=0.6))   # 1.2 m legs: twice the reference
        c = loc.DEFAULT_CRITERIA
        self.assertAlmostEqual(tall.min_speed, 2 * c.min_speed)
        self.assertAlmostEqual(tall.min_step_advance, 2 * c.min_step_advance)
        for k in c.as_dict():
            if k not in ("min_speed", "min_step_advance"):
                self.assertEqual(getattr(tall, k), getattr(c, k), k)

    def test_mean_over_both_legs(self):
        b = SandboxBody(thigh_length=0.3, shank_length=0.3, thigh_length_r=0.45, shank_length_r=0.45)  # 0.6 and 0.9
        self.assertAlmostEqual(cw.length_scale(b), 1.25)
        self.assertAlmostEqual(cw.creature_criteria(b).min_speed, 1.25 * loc.DEFAULT_CRITERIA.min_speed)


class WinnerTests(unittest.TestCase):
    def test_r2_winner_is_the_frozen_record_and_in_bounds(self):
        self.assertEqual(len(cw.R2_WINNER), 15)
        u = r2.to_u(cw.R2_WINNER)
        self.assertTrue(np.all(u >= 0) and np.all(u <= 1))
        self.assertTrue(np.all(np.asarray(cw.R2_WINNER) >= LOWER15) and np.all(np.asarray(cw.R2_WINNER) <= UPPER15))


class RolloutTests(unittest.TestCase):
    def assert_same_trace(self, a: dict, b: dict):
        self.assertEqual(set(a), set(b))
        for k in a:
            if k == "meta":
                self.assertEqual(a[k], b[k])
            else:
                self.assertTrue(np.array_equal(a[k], b[k]), f"trace key {k} differs")

    def test_neutral_start_is_bit_identical_to_locomotion_rollout_for_the_default_body(self):
        v = list(cw.R2_WINNER)
        for seed in (101, 102, 103):
            ref = loc.rollout(controller_from_vector(v), BipedParams(), seed, 4.0)
            got = cw.rollout(controller_from_vector(v), SandboxBody(), seed, 4.0, start="neutral")
            self.assert_same_trace(ref, got)

    def test_neutral_start_ignores_the_drawn_pose(self):
        v = list(cw.R2_WINNER)
        leaning = SandboxBody(pose=(0.3, 0.2, -0.4, 0.0, 0.2, -0.4, 0.0))
        self.assert_same_trace(cw.rollout(controller_from_vector(v), SandboxBody(), 7, 2.0),
                               cw.rollout(controller_from_vector(v), leaning, 7, 2.0, start="neutral"))

    def test_drawn_start_begins_in_the_drawn_configuration(self):
        v = list(cw.R2_WINNER)
        b = SandboxBody(pose=(0.3, 0.2, -0.4, 0.0, 0.2, -0.4, 0.0))
        tr = cw.rollout(controller_from_vector(v), b, 7, 1.0, start="drawn")
        self.assertGreater(tr["pitch"][0], 0.2)
        self.assertLess(tr["q"][0][1], -0.2)      # left knee started bent (before the first 5 ms of control)
        self.assertTrue(np.all(np.isfinite(tr["x"])))

    def test_bad_start_and_bad_body_are_refused_with_a_reason(self):
        v = list(cw.R2_WINNER)
        with self.assertRaises(ValueError):
            cw.rollout(controller_from_vector(v), SandboxBody(), 1, 1.0, start="sideways")
        with self.assertRaises(ValueError):
            cw.rollout(controller_from_vector(v), SandboxBody(foot_length=-1.0), 1, 1.0)

    def test_the_r2_winner_walks_the_default_body_under_creature_criteria(self):
        res = cw.eval_vector(list(cw.R2_WINNER), SandboxBody().as_dict(), [100001, 100002], 10.0)
        self.assertTrue(all(p["walking"] for p in res["per_seed"]), res)


class AdaptationTests(unittest.TestCase):
    SEEDS = (100101, 100102)
    KW = dict(train_seeds=SEEDS, noise_seed=4242, duration=3.0)

    @classmethod
    def setUpClass(cls):
        cls.body = SandboxBody()
        cls.a32 = cw.adapt_controller(cls.body, list(cw.R2_WINNER), budget=32, **cls.KW)
        cls.a16 = cw.adapt_controller(cls.body, list(cw.R2_WINNER), budget=16, **cls.KW)

    def test_record_and_exact_budget_accounting(self):
        a = self.a32
        for k in ("vector", "init_vector", "budget", "rollouts_used", "train_seeds", "noise_seed", "history", "best_score"):
            self.assertIn(k, a)
        self.assertEqual(a["generations"], 2)
        self.assertEqual(a["es_rollouts"], 2 * 8 * len(self.SEEDS))
        self.assertLessEqual(a["es_rollouts"], a["budget"])
        self.assertEqual(a["init_eval_rollouts"], len(self.SEEDS))
        self.assertEqual(a["rollouts_used"], a["es_rollouts"] + a["init_eval_rollouts"])
        self.assertEqual(len(a["history"]), 2)
        self.assertEqual([len(h["candidates"]) for h in a["history"]], [8, 8])
        self.assertEqual(a["init_vector"], list(cw.R2_WINNER))
        self.assertEqual(a["train_seeds"], list(self.SEEDS))
        self.assertTrue(np.all(np.asarray(a["vector"]) >= LOWER15) and np.all(np.asarray(a["vector"]) <= UPPER15))

    def test_budget_below_one_generation_runs_no_search(self):
        a = cw.adapt_controller(self.body, list(cw.R2_WINNER), budget=15, **self.KW)
        self.assertEqual(a["generations"], 0)
        self.assertEqual(a["es_rollouts"], 0)
        self.assertEqual(a["vector"], list(cw.R2_WINNER))
        self.assertFalse(a["improved"])

    def test_known_init_score_skips_the_parent_evaluation(self):
        a = cw.adapt_controller(self.body, list(cw.R2_WINNER), budget=16, init_score=tuple(self.a16["init_score"]), **self.KW)
        self.assertEqual(a["init_eval_rollouts"], 0)
        self.assertEqual(a["rollouts_used"], 16)
        self.assertEqual(a["history"][0]["candidates"], self.a16["history"][0]["candidates"])
        self.assertEqual(a["history"][0]["parent_vector"], self.a16["history"][0]["parent_vector"])
        self.assertEqual(a["vector"], self.a16["vector"])

    def test_same_noise_seed_gives_identical_stream_and_nested_budgets(self):
        n2 = cw.adaptation_noise(4242, 2)
        self.assertTrue(np.array_equal(n2[:1], cw.adaptation_noise(4242, 1)))
        self.assertFalse(np.array_equal(n2, cw.adaptation_noise(4243, 2)))
        # a smaller budget is exactly the prefix of a larger one
        self.assertEqual(self.a16["history"][0], self.a32["history"][0])
        self.assertEqual(self.a16["history"][0]["parent_vector"], self.a16["vector"])

    def test_pool_and_inline_agree_and_progress_counts_rollouts(self):
        seen = []
        with ForgePool(2) as pool:
            a = cw.adapt_controller(self.body, list(cw.R2_WINNER), budget=32, pool=pool,
                                    progress=lambda d, t: seen.append((d, t)), **self.KW)
        self.assertEqual(a["vector"], self.a32["vector"])
        self.assertEqual(a["history"], self.a32["history"])
        self.assertEqual(seen[-1], (a["rollouts_used"], a["rollouts_used"]))
        self.assertEqual([d for d, _ in seen], sorted(d for d, _ in seen))

    def test_invalid_inputs_are_refused_not_clipped(self):
        bad = list(cw.R2_WINNER)
        bad[0] = float(UPPER15[0]) + 1.0
        with self.assertRaises(ValueError):
            cw.adapt_controller(self.body, bad, budget=16, **self.KW)
        with self.assertRaises(ValueError):
            cw.adapt_controller(self.body, list(cw.R2_WINNER)[:13], budget=16, **self.KW)
        with self.assertRaises(ValueError):
            cw.adapt_controller(self.body, list(cw.R2_WINNER), budget=16, train_seeds=[], noise_seed=1)
        with self.assertRaises(ValueError):
            cw.adapt_controller(self.body, list(cw.R2_WINNER), budget=-1, **self.KW)

    def test_a_broken_body_is_counted_as_errors_not_raised(self):
        # an unbuildable body: every candidate errors, rollouts are still counted, nothing escapes
        bad = SandboxBody().as_dict()
        bad["foot_length"] = -1.0
        a = cw.adapt_controller(bad, list(cw.R2_WINNER), budget=16, init_score=(0, 0, -10.0), **self.KW)
        self.assertEqual(a["rollouts_used"], 16)
        self.assertTrue(all(c["error"] for c in a["history"][0]["candidates"]))
        self.assertEqual(a["vector"], list(cw.R2_WINNER))


if __name__ == "__main__":
    unittest.main()
