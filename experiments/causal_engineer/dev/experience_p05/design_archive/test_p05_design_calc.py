"""Unit tests of the P0.5 rev. 2 design arithmetic (no data, no simulator).  python -I -m unittest test_p05_design_calc"""
import itertools
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import p05_design_calc as c  # noqa: E402


class Constraints(unittest.TestCase):
    def test_delta_cannot_exceed_q(self):
        for q, d in ((0.10, 0.15), (0.15, -0.2), (0.05, 0.051)):
            with self.assertRaises(ValueError):
                c.check_dq(q, d)
        self.assertAlmostEqual(c.check_dq(0.42, 0.10), 0.42 - 0.01)

    def test_every_valid_pair_has_nonnegative_variance(self):
        for q in np.linspace(0.01, 1.0, 50):
            for d in np.linspace(-q, q, 21):
                self.assertGreaterEqual(c.check_dq(q, d), -1e-12)

    def test_constraint_is_exact_for_d_in_minus1_0_1(self):
        # brute force over distributions (p+, p-) on a grid: |p+ - p-| <= p+ + p- always holds
        for pp, pm in itertools.product(np.linspace(0, 0.5, 11), repeat=2):
            q, d = pp + pm, pp - pm
            if q > 0:
                self.assertLessEqual(abs(d), q + 1e-12)

    def test_marginal_feasibility(self):
        c.check_marginals(0.3, 0.3, 0.42)
        with self.assertRaises(ValueError):
            c.check_marginals(0.3, 0.1, 0.1)          # q < |pa - pb|
        with self.assertRaises(ValueError):
            c.check_marginals(0.1, 0.1, 0.5)          # q > pa + pb

    def test_design_checks(self):
        for bad in ((1, 2, 0.1), (8, 0, 0.1), (8, 2, 1.5)):
            with self.assertRaises(ValueError):
                c.check_design(*bad)
        with self.assertRaises(ValueError):
            c.var_mean_diff(0.1, 0.2, 12, 2, 0.2)
        with self.assertRaises(ValueError):
            c.check_design(12, 2, 0.2, 0.5)           # inflation below 1


class Quantiles(unittest.TestCase):
    def test_t_quantiles_against_tables(self):
        for p, df, ref in ((0.95, 7, 1.894579), (0.95, 11, 1.795885), (0.95, 45, 1.679427), (0.80, 7, 0.896030),
                           (0.80, 11, 0.875539), (0.975, 5, 2.570582)):
            self.assertAlmostEqual(c.t_ppf(p, df), ref, places=4)

    def test_t_tends_to_normal(self):
        self.assertAlmostEqual(c.t_ppf(0.95, 10_000), c.z_ppf(0.95), places=3)


class Precision(unittest.TestCase):
    def test_mde_closed_form_solves_the_power_equation(self):
        for q, G, m, rho, infl in ((0.15, 46, 2, 0.2, 1.0), (0.42, 24, 3, 0.5, 2.0), (0.30, 46, 3, 0.0, 1.5)):
            d = c.mde(q, G, m, rho, infl)
            self.assertIsNotNone(d)
            K = c.crit(0.95, G, "t") + c.crit(0.80, G, "t")
            self.assertAlmostEqual(d, K * math.sqrt(c.var_mean_diff(q, d, G, m, rho, infl)), places=10)

    def test_mde_none_when_beyond_q(self):
        self.assertIsNone(c.mde(0.10, 8, 1, 0.5, 3.0))

    def test_t_wider_than_z(self):
        self.assertGreater(c.halfwidth(0.42, 0, 8, 2, 0.2, method="t"), c.halfwidth(0.42, 0, 8, 2, 0.2, method="z"))

    def test_bases_needed_monotone(self):
        a = c.bases_needed(0.10, 0.30, 2, 0.2)
        b = c.bases_needed(0.10, 0.30, 2, 0.2, infl=2.0)
        self.assertLess(a, b)

    def test_small_designs_can_be_undetectable(self):
        self.assertIsNone(c.mde(0.30, 12, 1, 0.0, 1.5))   # the solution would exceed q


class Headroom(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(1)

    def _mc(self, Q, R, n=200_000):
        K = self.rng.binomial(R, Q, size=(n, len(Q)))
        sel = np.argmax(K + self.rng.random(K.shape) * 1e-6, 1)
        return Q[sel].mean(), (K.max(1) / R).mean()

    def test_exact_selector_and_naive_match_monte_carlo(self):
        for Q, R in ((np.array([0.2, 0.5, 0.3]), 1), (np.array([0.1, 0.1, 0.6, 0.4]), 2), (np.array([0.3] * 5), 3)):
            sel_mc, nav_mc = self._mc(Q, R)
            self.assertAlmostEqual(c.selector_value(Q, R), sel_mc, delta=0.004)
            self.assertAlmostEqual(c.naive_max(Q, R), nav_mc, delta=0.004)

    def test_bracket_order(self):
        for _ in range(200):
            Q = self.rng.random(c.TOOLS)
            for R in (1, 2, 3, 4):
                self.assertLessEqual(c.selector_value(Q, R), Q.max() + 1e-12)
                self.assertGreaterEqual(c.naive_max(Q, R), Q.max() - 1e-12)

    def test_bracket_tightens_with_replicates(self):
        Q = np.array([0.2, 0.25, 0.3, 0.6, 0.1, 0.1, 0.2, 0.3, 0.4, 0.5])
        sel = [c.selector_value(Q, R) for R in (1, 2, 4, 8)]
        nav = [c.naive_max(Q, R) for R in (1, 2, 4, 8)]
        self.assertTrue(all(a <= b + 1e-12 for a, b in zip(sel, sel[1:])))
        self.assertTrue(all(a >= b - 1e-12 for a, b in zip(nav, nav[1:])))

    def test_equal_tools_have_zero_true_headroom_but_positive_naive(self):
        Q = np.full(c.TOOLS, 0.3)
        self.assertAlmostEqual(c.selector_value(Q, 1), 0.3, places=12)
        self.assertGreater(c.naive_max(Q, 1) - 0.3, 0.6)


class VarianceBound(unittest.TestCase):
    def test_variance_component_unbiased(self):
        rng = np.random.default_rng(3)
        Q = rng.random((20_000, c.TOOLS))
        for R in (2, 3):
            Y = (rng.random((20_000, c.TOOLS, R)) < Q[:, :, None]).astype(float)
            self.assertAlmostEqual(c.tool_variance_component(Y).mean(), Q.var(1, ddof=1).mean(), delta=0.002)

    def test_variance_bound_is_an_upper_bound(self):
        rng = np.random.default_rng(4)
        for _ in range(300):
            Q = rng.beta(rng.uniform(0.2, 3), rng.uniform(0.2, 3), (50, c.TOOLS))
            pi0 = rng.integers(0, c.TOOLS)
            true = float(np.mean(Q.max(1) - Q[:, pi0]))
            b = c.headroom_var_bound(float(Q.var(1, ddof=1).mean()), float(np.mean(Q.mean(1) - Q[:, pi0])))
            self.assertGreaterEqual(b, true - 1e-12)

    def test_variance_bound_tight_when_tools_equal(self):
        self.assertAlmostEqual(c.headroom_var_bound(0.0, 0.0), 0.0)


class Noise(unittest.TestCase):
    def test_equal_tool_discordance(self):
        r = c.equal_tool_noise(0.3, 10)
        self.assertAlmostEqual(r["q_discordance"], 0.42)
        self.assertAlmostEqual(r["realised_p_minus"], 0.21)
        self.assertAlmostEqual(r["P_informative_K10"], 1 - 0.3 ** 10 - 0.7 ** 10)
        self.assertAlmostEqual(c.equal_tool_noise(0.5)["q_discordance"], 0.5)

    def test_harm_bounds_contain_truth(self):
        rng = np.random.default_rng(2)
        for _ in range(300):
            tau = rng.normal(rng.normal(0, 0.1), abs(rng.normal(0, 0.2)) + 1e-3, 5000)
            lo, hi = c.harm_bounds(float(tau.mean()), float(tau.var()))
            harm = float(np.maximum(-tau, 0).mean())
            self.assertLessEqual(lo, harm + 1e-9)
            self.assertGreaterEqual(hi, harm - 1e-9)


class Cost(unittest.TestCase):
    def test_cost_matched_cells_pay_for_the_skipped_diagnosis(self):
        cs = c.COST_SETS["mid"]
        base = c.design_re(cs, n_inst=10, tools=10, R=1, aug_per_inst=0, n_confirm_cells=0, n_sentinel=0)
        aug = c.design_re(cs, n_inst=10, tools=10, R=1, aug_per_inst=2, n_confirm_cells=0, n_sentinel=0)
        v = c.verify_re(cs["p_pass"], cs["cache_original"])
        self.assertAlmostEqual(aug["total"] - base["total"], 10 * (2 * (cs["B_plant"] + v) + 36 + 40))

    def test_total_is_sum_of_parts(self):
        p = c.design_re(c.COST_SETS["high"], n_inst=12, tools=10, R=2, aug_per_inst=2, n_confirm_cells=24, n_sentinel=3)
        self.assertAlmostEqual(p["total"], sum(v for k, v in p.items() if k != "total"))

    def test_code_derived_constants(self):
        self.assertEqual(c.prefix_re({"twin_prefix": 0}), 40)          # 4 observe + 9 x 4 catalogue (P0 interv)
        self.assertEqual(c.stage_e_re(1, 0), 13 * 7 * 8)
        self.assertAlmostEqual(c.verify_re(1.0, False), 24 + 24 + 48)

    def test_dollars_monotone_in_price_and_overhead(self):
        lo = dict(c.COST_SETS["mid"])
        hi = dict(lo, price_h=lo["price_h"] * 2)
        self.assertGreater(c.dollars(hi, 1e5), c.dollars(lo, 1e5))
        self.assertGreater(c.dollars(dict(lo, sessions=9), 1e5), c.dollars(lo, 1e5))


if __name__ == "__main__":
    unittest.main()
