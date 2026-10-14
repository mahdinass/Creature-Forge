import math
import unittest

import numpy as np

from creature_forge import r2_stats as s
from creature_forge.r1_stats import exact_mcnemar


def numeric_restricted_q(b, c, n, theta0):
    """Independent check: root of the derivative of the restricted log-likelihood (strictly decreasing in q), by
    bisection on the log-likelihood terms themselves; no use of the closed-form quadratic."""
    m = n - b - c
    lo, hi = max(0.0, theta0) + 1e-15, (1 + theta0) / 2 - 1e-15

    def dll(q):
        return (b / q if b else 0.0) + (c / (q - theta0) if c else 0.0) - (2 * m / (1 - 2 * q + theta0) if m else 0.0)

    if dll(lo) <= 0:
        return lo
    if dll(hi) >= 0:
        return hi
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if dll(mid) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


class RestrictedMleTests(unittest.TestCase):
    TABLES = [(10, 5, 150), (3, 12, 150), (20, 4, 150), (0, 7, 150), (7, 0, 150), (1, 1, 64), (15, 15, 100), (30, 2, 150)]

    def test_closed_form_matches_independent_numeric_maximiser(self):
        for b, c, n in self.TABLES:
            for th0 in (-0.05, -0.02, 0.0, 0.03):
                if (b == 0 and th0 > 0) or (c == 0 and th0 < 0 and False):
                    continue
                try:
                    q = s.restricted_q(b, c, n, th0)
                except ValueError:
                    continue
                self.assertAlmostEqual(q, numeric_restricted_q(b, c, n, th0), places=9, msg=(b, c, n, th0))

    def test_theta0_zero_reduces_to_mcnemar(self):
        for b, c, n in self.TABLES:
            if b + c == 0:
                continue
            self.assertAlmostEqual(s.tango_z(b, c, n, 0.0), (b - c) / math.sqrt(b + c), places=10)

    def test_reference_values(self):
        """Frozen reference values. Each Z was reproduced by the independent derivative-bisection maximiser above
        (agreement ~1e-16) and the interval ends satisfy Z(end) = +-1.959964. They are computed values, not literature values."""
        self.assertAlmostEqual(s.tango_z(10, 5, 150, -0.05), 2.872387724660142, places=9)
        self.assertAlmostEqual(s.tango_z(5, 12, 150, -0.05), 0.1219064092114025, places=9)
        th, lo, hi = s.tango_ci(10, 5, 150)
        self.assertAlmostEqual(th, 5 / 150)
        self.assertAlmostEqual(lo, -0.019255632960393936, places=9)
        self.assertAlmostEqual(hi, 0.0903491830141431, places=9)
        self.assertAlmostEqual(s.tango_z(10, 5, 150, lo), s.Z975, places=8)     # bounds invert the test
        self.assertAlmostEqual(s.tango_z(10, 5, 150, hi), -s.Z975, places=8)
        _, lo2, hi2 = s.tango_ci(0, 0, 150)
        self.assertAlmostEqual(lo2, -0.02497024436810414, places=9)
        self.assertAlmostEqual(hi2, 0.02497024436810414, places=9)
        self.assertAlmostEqual(s.tango_ci(27, 10, 150)[1], 0.03550866710234375, places=9)

    def test_ci_contains_estimate_and_is_monotone_in_data(self):
        for b, c, n in self.TABLES:
            th, lo, hi = s.tango_ci(b, c, n)
            self.assertLessEqual(lo, th + 1e-12)
            self.assertGreaterEqual(hi, th - 1e-12)
        lows = [s.tango_ci(b, 5, 150)[1] for b in range(0, 30)]
        self.assertTrue(all(x <= y + 1e-12 for x, y in zip(lows, lows[1:])))

    def test_size_at_the_margin_by_exact_enumeration(self):
        """Exact rejection probability of the one-sided alpha=0.025 test on the null boundary theta = -0.05, n = 150,
        over a grid of discordance levels. The score test is asymptotic: its size is checked, not assumed."""
        n, delta = 150, 0.05
        worst = 0.0
        table = {(b, c): s.tango_z(b, c, n, -delta) > s.Z975 for b in range(0, n + 1) for c in range(0, n + 1 - b)}
        lg = [math.lgamma(i + 1) for i in range(n + 2)]
        for q in (0.005, 0.01, 0.02, 0.04, 0.08, 0.15, 0.25, 0.4):
            p10, p01 = q, q + delta
            p00 = 1 - p10 - p01
            if p00 <= 0:
                continue
            size = 0.0
            for (b, c), rej in table.items():
                if not rej:
                    continue
                m = n - b - c
                logp = lg[n] - lg[b] - lg[c] - lg[m] + b * math.log(p10) + c * math.log(p01) + m * math.log(p00)
                size += math.exp(logp)
            worst = max(worst, size)
        self.assertLess(worst, 0.040, worst)             # reported in docs; asymptotic score tests can slightly exceed nominal
        print(f"\n[r2_stats] max exact size at theta=-0.05, n=150, nominal one-sided 0.025: {worst:.4f}")


class DecisionTests(unittest.TestCase):
    def test_noninferiority_rule(self):
        r = s.noninferiority(10, 5, 150)
        self.assertTrue(r["non_inferior"])
        self.assertGreater(r["tango_ci"][0], -0.05)
        bad = s.noninferiority(2, 17, 150)               # winner clearly worse
        self.assertFalse(bad["non_inferior"])
        self.assertLess(bad["tango_ci"][0], -0.05)

    def test_hierarchy_stops_when_noninferiority_fails(self):
        d = s.hierarchical_decision(2, 17, 150)
        self.assertFalse(d["claims"]["preservation_confirmed"])
        self.assertFalse(d["step2_superiority"]["tested"])
        self.assertFalse(d["claims"]["improvement_confirmed"])

    def test_hierarchy_superiority_requires_positive_difference_and_exact_p(self):
        d = s.hierarchical_decision(30, 5, 150)
        self.assertTrue(d["claims"]["preservation_confirmed"] and d["claims"]["improvement_confirmed"])
        self.assertAlmostEqual(d["step2_superiority"]["mcnemar_exact_two_sided_p"], exact_mcnemar(30, 5))
        d2 = s.hierarchical_decision(12, 8, 150)         # non-inferior but not significantly better
        self.assertTrue(d2["claims"]["preservation_confirmed"])
        self.assertFalse(d2["claims"]["improvement_confirmed"])
        d3 = s.hierarchical_decision(0, 0, 150)          # identical outcomes
        self.assertTrue(d3["claims"]["preservation_confirmed"])
        self.assertFalse(d3["claims"]["improvement_confirmed"])


if __name__ == "__main__":
    unittest.main()
