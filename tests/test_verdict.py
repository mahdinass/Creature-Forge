"""verdict_v1: paired sign test, ties at resolution, minimum effects, guard, INCONCLUSIVE (contracts section 6.3)."""
import math
import unittest

from creature_forge import verdict as vd


class SignTest(unittest.TestCase):
    def test_exact_binomial(self):
        self.assertAlmostEqual(vd.paired_sign_test([1.0] * 8), 1 / 256)
        self.assertAlmostEqual(vd.paired_sign_test([1, 1, 1, 1, 1, -1, -1, -1], 0.0), sum(math.comb(8, k) for k in range(5, 9)) / 256)
        self.assertAlmostEqual(vd.paired_sign_test([-1.0] * 8, alternative="less"), 1 / 256)
        self.assertAlmostEqual(vd.paired_sign_test([-1.0] * 8, alternative="greater"), 1.0)

    def test_ties_are_excluded(self):
        diffs = [2.5, -2.5, 2.5, 0.0, 10.0, 10.0, 10.0]
        self.assertEqual(vd.sign_counts(diffs, 2.5), {"wins": 3, "losses": 0, "ties": 4})
        self.assertAlmostEqual(vd.paired_sign_test(diffs, 2.5), 1 / 8)
        self.assertEqual(vd.paired_sign_test([0.0] * 5, 0.1), 1.0)   # all tied -> no evidence

    def test_bad_alternative(self):
        with self.assertRaises(ValueError):
            vd.paired_sign_test([1.0], 0.0, "two-sided")


class Verdict(unittest.TestCase):
    def test_verified_push(self):
        orig = [10.0] * 8
        cand = [20.0] * 8
        v = vd.verdict("push", orig, cand, resolution=2.5)
        self.assertEqual(v["status"], "VERIFIED_IMPROVEMENT")
        self.assertEqual(v["rule"], "verdict_v1")
        self.assertEqual((v["n"], v["wins"], v["losses"], v["ties"]), (8, 8, 0, 0))
        self.assertAlmostEqual(v["p_one_sided"], 1 / 256)
        self.assertEqual(v["median_diff"], 10.0)
        self.assertEqual(v["min_effect"]["required"], 3.0)      # abs 3 N beats 10 % of 10 N
        self.assertTrue(v["reasons"])

    def test_push_relative_effect_binds(self):
        # original median 50 N: 10 % = 5 N > abs 3 N. A +4 N gain wins every pair but is below the relative bound.
        v = vd.verdict("push", [50.0] * 8, [54.0] * 8, resolution=2.5)
        self.assertEqual(v["min_effect"]["required"], 5.0)
        self.assertEqual(v["status"], "NOT_VERIFIED")
        self.assertIn("minimum effect", " ".join(v["reasons"]))

    def test_zero_original_median_push_uses_abs_only(self):
        v = vd.verdict("push", [0.0] * 8, [5.0] * 8, resolution=2.5)
        self.assertEqual(v["min_effect"]["required"], 3.0)
        self.assertEqual(v["status"], "VERIFIED_IMPROVEMENT")

    def test_stand_and_walk_min_effects(self):
        self.assertEqual(vd.verdict("stand", [2.0] * 8, [2.4] * 8)["status"], "NOT_VERIFIED")          # +0.4 s < 0.5 s
        self.assertEqual(vd.verdict("stand", [2.0] * 8, [3.2] * 8)["status"], "VERIFIED_IMPROVEMENT")
        self.assertEqual(vd.verdict("walk", [1.0] * 8, [1.4] * 8)["status"], "NOT_VERIFIED")           # +0.4 m < 0.5 m
        self.assertEqual(vd.verdict("walk", [1.0] * 8, [1.6] * 8)["status"], "VERIFIED_IMPROVEMENT")

    def test_worse(self):
        v = vd.verdict("push", [20.0] * 8, [10.0] * 8, resolution=2.5)
        self.assertEqual(v["status"], "WORSE")
        self.assertAlmostEqual(v["p_worse"], 1 / 256)
        self.assertEqual(v["losses"], 8)

    def test_significant_but_tiny_loss_is_not_worse(self):
        v = vd.verdict("push", [20.0] * 8, [16.0] * 8, resolution=2.5)       # -4 N: beyond -3 abs but rel 2 N -> required 3 => WORSE
        self.assertEqual(v["status"], "WORSE")
        v2 = vd.verdict("stand", [5.0] * 8, [4.6] * 8)                        # -0.4 s: significant sign test, below 0.5 s
        self.assertEqual(v2["status"], "NOT_VERIFIED")

    def test_ties_at_resolution_give_inconclusive(self):
        # every pair differs by exactly one bisection step -> all ties -> never VERIFIED
        v = vd.verdict("push", [10.0] * 8, [12.5] * 8, resolution=2.5)
        self.assertEqual((v["wins"], v["losses"], v["ties"]), (0, 0, 8))
        self.assertEqual(v["status"], "INCONCLUSIVE")
        v2 = vd.verdict("push", [10.0] * 8, [10.0] * 8, resolution=2.5)
        self.assertEqual(v2["status"], "INCONCLUSIVE")
        self.assertEqual(v2["p_one_sided"], 1.0)

    def test_inconclusive_below_six_non_tied(self):
        orig = [10.0] * 8
        cand = [30.0] * 5 + [10.0] * 3                       # 5 wins, 3 ties: p = 1/32 but only 5 non-tied pairs
        v = vd.verdict("push", orig, cand, resolution=2.5)
        self.assertEqual(v["status"], "INCONCLUSIVE")
        self.assertEqual(v["non_tied"], 5)
        v6 = vd.verdict("push", orig, [30.0] * 6 + [10.0] * 2, resolution=2.5)
        self.assertEqual(v6["status"], "VERIFIED_IMPROVEMENT")   # 6 wins: p = 1/64

    def test_not_significant(self):
        v = vd.verdict("push", [10.0] * 8, [20.0, 20.0, 20.0, 20.0, 0.0, 0.0, 0.0, 0.0], resolution=2.5)
        self.assertEqual(v["status"], "NOT_VERIFIED")

    def test_guard_failure_blocks_verification(self):
        v = vd.verdict("push", [10.0] * 8, [20.0] * 8, resolution=2.5, guard={"passed": False, "reason": "lost PASS seeds"})
        self.assertEqual(v["status"], "NOT_VERIFIED")
        self.assertIn("guard failed", " ".join(v["reasons"]))
        ok = vd.verdict("push", [10.0] * 8, [20.0] * 8, resolution=2.5, guard={"passed": True})
        self.assertEqual(ok["status"], "VERIFIED_IMPROVEMENT")

    def test_errors_are_inconclusive_not_dropped(self):
        v = vd.verdict("stand", [2.0, None, 2.0], [5.0, 5.0, 5.0])
        self.assertEqual(v["status"], "INCONCLUSIVE")
        self.assertEqual(v["errors"], [1])

    def test_pass_rate_wilson(self):
        v = vd.verdict("push", [10.0] * 8, [20.0] * 8, resolution=2.5, original_pass=[True] * 2 + [False] * 6,
                       candidate_pass=[True] * 8)
        pr = v["pass_rate"]
        self.assertEqual(pr["original"]["k"], 2)
        self.assertEqual(pr["candidate"]["k"], 8)
        self.assertLess(pr["original"]["ci95"][0], 0.25)
        self.assertGreater(pr["candidate"]["ci95"][0], 0.6)

    def test_validation(self):
        with self.assertRaises(ValueError):
            vd.verdict("push", [1.0], [1.0, 2.0])
        with self.assertRaises(ValueError):
            vd.verdict("fly", [1.0], [1.0])
        with self.assertRaises(ValueError):
            vd.verdict("stand", [float("nan")], [1.0])

    def test_deterministic(self):
        a = vd.verdict("push", [10, 12.5, 10, 15, 10, 10, 7.5, 10], [20, 22.5, 25, 20, 10, 12.5, 15, 20], resolution=2.5)
        b = vd.verdict("push", [10, 12.5, 10, 15, 10, 10, 7.5, 10], [20, 22.5, 25, 20, 10, 12.5, 15, 20], resolution=2.5)
        self.assertEqual(a, b)

    def test_thresholds_versioned(self):
        self.assertEqual(vd.VERDICT_RULE_VERSION, "verdict_v1")
        self.assertEqual(vd.MIN_EFFECT["push"], {"abs": 3.0, "rel": 0.10})


if __name__ == "__main__":
    unittest.main()
