"""Deterministic unit tests of the rev. 2.1 additions (no data, no simulator).  python -I test_p05_design_calc_rev21.py"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import p05_design_calc as c  # noqa: E402


class Budgets(unittest.TestCase):
    def test_minima_match_published_enumeration(self):
        # values printed by p05_min_budget_check.py from eng_tools at e3caf81 (physics trapped)
        ref8 = {"posture": 200, "timing": 176, "feedback": 200, "stride": 176, "placement": 152, "foot_length": 104,
                "torso_mass": 104, "torque_limit": 104, "foot_friction": 104, "leg_length": 152}
        for t, v in ref8.items():
            self.assertEqual(c.min_repair_budget(t, 8), v)
            self.assertEqual(c.min_repair_budget(t, 4), v // 2)
        self.assertEqual(sorted(set(ref8.values())), [104, 152, 176, 200])

    def test_feasible_counts(self):
        self.assertEqual(len(c.budget_feasible(160, 8)), 6)
        self.assertEqual(len(c.budget_feasible(196, 8)), 8)
        self.assertEqual(len(c.budget_feasible(200, 8)), 10)
        self.assertEqual(len(c.budget_feasible(160, 4)), 10)

    def test_cost_sets_never_budget_restrict(self):
        for cs in c.COST_SETS.values():
            c.check_all_tools_feasible(cs)
            for extra in (0, 36, 40):
                self.assertEqual(len(c.budget_feasible(cs["B_plant"] + extra, cs["n_train"])), 10)
        with self.assertRaises(ValueError):
            c.check_all_tools_feasible({"B_plant": 160, "n_train": 8})


class AchievedICC(unittest.TestCase):
    def _quad_moments(self, mu, sigma, lo, hi, n=400_001):
        x = np.linspace(mu - 12 * sigma, mu + 12 * sigma, n)
        w = np.exp(-0.5 * ((x - mu) / sigma) ** 2)
        w /= np.trapezoid(w, x)
        y = np.clip(x, lo, hi)
        m1 = np.trapezoid(w * y, x)
        return m1, np.trapezoid(w * y * y, x) - m1 * m1

    def test_clipped_moments_match_quadrature(self):
        for mu, sigma, q in ((0.0, 0.2121, 0.15), (0.05, 0.3, 0.42), (-0.1, 1.0, 0.3), (0.2, 0.05, 0.5)):
            m, v = c.clipped_normal_moments(mu, sigma, -q, q)
            mq, vq = self._quad_moments(mu, sigma, -q, q)
            self.assertAlmostEqual(m, mq, places=6)
            self.assertAlmostEqual(v, vq, places=6)

    def test_auditor_values_for_rev2_nominal_rho(self):
        self.assertAlmostEqual(c.achieved_icc(0.15, 0.0, c.rev2_nominal_sigma(0.15, 0.0, 0.30)), 0.096, delta=0.001)
        self.assertAlmostEqual(c.achieved_icc(0.42, 0.0, c.rev2_nominal_sigma(0.42, 0.0, 0.30)), 0.188, delta=0.001)

    def test_calibration_round_trip(self):
        for q, d, r in ((0.15, 0.0, 0.10), (0.42, 0.0, 0.30), (0.42, 0.05, 0.10), (0.50, 0.0, 0.30)):
            self.assertAlmostEqual(c.achieved_icc(q, d, c.calibrate_sigma(q, d, r)), r, places=9)
        self.assertEqual(c.calibrate_sigma(0.3, 0.0, 0.0), 0.0)

    def test_unattainable_targets_raise(self):
        with self.assertRaises(ValueError):
            c.calibrate_sigma(0.15, 0.0, 0.30)

    def test_icc_increasing_and_below_supremum(self):
        for q in (0.15, 0.42):
            vals = [c.achieved_icc(q, 0.0, s) for s in (0.01, 0.1, 0.3, 1.0, 10.0, 1e3)]
            self.assertTrue(all(a < b for a, b in zip(vals, vals[1:])))
            self.assertLess(vals[-1], c.icc_supremum(q))
            self.assertGreater(vals[-1], 0.99 * q)


class CoverageScoring(unittest.TestCase):
    def test_truth_exact_at_zero_and_insensitive_to_sigma(self):
        # rev. 2 defect: an inexact truth at delta = 0 turned lattice-point intervals into misses (bootstrap 0.656 vs 0.92)
        a = c.coverage_sim(8, 2, 0.15, 0.0, None, reps=800, n_boot=299, sigma=c.rev2_nominal_sigma(0.15, 0.0, 0.3))
        b = c.coverage_sim(8, 2, 0.15, 0.0, None, reps=800, n_boot=299, sigma=0.2296)
        self.assertEqual(a["truth"], 0.0)
        self.assertLess(abs(a["cov_boot_pct"] - b["cov_boot_pct"]), 0.03)


class Discordance(unittest.TestCase):
    def test_bound_holds_for_arbitrary_policies(self):
        rng = np.random.default_rng(5)
        for _ in range(400):
            Q = rng.beta(rng.uniform(0.2, 3), rng.uniform(0.2, 3), (60, c.TOOLS))
            a, b = rng.integers(0, c.TOOLS, 60), rng.integers(0, c.TOOLS, 60)
            Qa, Qb = Q[np.arange(60), a], Q[np.arange(60), b]
            q = float(np.mean((a != b) * (Qa + Qb - 2 * Qa * Qb)))      # same tool = same cell = same draw
            self.assertLessEqual(q, c.discordance_upper(Qa.mean(), Qb.mean()) + 1e-12)
            self.assertLessEqual(q, c.discordance_upper_any_policies(Q.max(1).mean(), Q.min(1).mean()) + 1e-12)


class Capability(unittest.TestCase):
    def test_equivalence_margin_formula(self):
        q, G, m, rho, infl = 0.30, 34, 2, 0.3, 2.25
        se = math.sqrt(c.var_mean_diff(q, 0.0, G, m, rho, infl))
        self.assertAlmostEqual(c.equivalence_margin_demonstrable(q, G, m, rho, infl),
                               (c.t_ppf(0.95, G - 1) + c.t_ppf(0.80, G - 1)) * se, places=12)
        self.assertGreater(c.equivalence_margin_demonstrable(q, G, m, rho, infl, two_sided=True),
                           c.equivalence_margin_demonstrable(q, G, m, rho, infl))

    def test_margin_shrinks_with_bases(self):
        v = [c.equivalence_margin_demonstrable(0.42, G, 2, 0.3, 1.0) for G in (12, 18, 28, 40)]
        self.assertTrue(all(a > b for a, b in zip(v, v[1:])))


class HeadroomBounds(unittest.TestCase):
    def test_vhat_range_contains_all_values(self):
        lo, hi = c.vhat_range(c.TOOLS, 2)
        rng = np.random.default_rng(6)
        Y = (rng.random((50_000, c.TOOLS, 2)) < rng.random((50_000, c.TOOLS, 1))).astype(float)
        extremes = np.stack([np.tile([[1.0, 0.0]], (c.TOOLS, 1)), np.tile([[1.0, 1.0]] * 5 + [[0.0, 0.0]] * 5, (1, 1))])
        v = np.concatenate([c.tool_variance_component(Y), c.tool_variance_component(extremes)])
        self.assertGreaterEqual(v.min(), lo - 1e-12)
        self.assertLessEqual(v.max(), hi + 1e-12)
        self.assertAlmostEqual(v.min(), lo)
        self.assertAlmostEqual(v.max(), hi)

    def test_negative_variance_bound_truncated(self):
        G = 20
        h = c.headroom_interval(np.zeros(G), np.zeros(G), np.full(G, -0.2), np.zeros(G), method="t")
        self.assertEqual(h["UCB_EV"], 0.0)
        self.assertAlmostEqual(h["U_var"], c.ucb(np.zeros(G), 0.10 / 6, "t", c.GAP_RANGE))

    def test_hoeffding_joint_coverage_deterministic(self):
        rng = np.random.default_rng(7)
        G, hits, n = 34, 0, 200
        for _ in range(n):
            Q = c.headroom_instances(rng, "S2 graded, logit sd 1.5", 2 * G)
            base = np.repeat(np.arange(G), 2)
            true = float(np.mean(Q.max(1) - Q[:, 0]))
            h = c.headroom_interval(*c.simulate_headroom_estimates(rng, Q, base), method="hoeffding")
            hits += h["L_sel"] <= true <= h["upper"]
        self.assertGreaterEqual(hits / n, 0.90)


if __name__ == "__main__":
    unittest.main()
