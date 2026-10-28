"""Statistics of the registered held-out analysis (exact McNemar, Holm, Wilcoxon) and the selection rule."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ce_heldout_analysis as ha  # noqa: E402
import ce_heldout_select as hs  # noqa: E402


class Stats(unittest.TestCase):
    def test_mcnemar_exact(self):
        a = {"i1": "FULL_RECOVERY", "i2": "FULL_RECOVERY", "i3": "FULL_RECOVERY", "i4": "NOT_RECOVERED"}
        b = {"i1": "FULL_RECOVERY", "i2": "NOT_RECOVERED", "i3": "NOT_RECOVERED", "i4": "FULL_RECOVERY"}
        t = ha.mcnemar(a, b, ["i1", "i2", "i3", "i4"])
        self.assertEqual((t["a_only"], t["b_only"]), (2, 1))
        self.assertAlmostEqual(t["p_one_sided"], 4 / 8)            # P(X >= 2 | n = 3)
        self.assertEqual(ha.mcnemar(a, a, list(a))["p_one_sided"], 1.0)
        self.assertAlmostEqual(ha.binom_upper(7, 8), 9 / 256)

    def test_holm(self):
        h = ha.holm({"x": 0.01, "y": 0.04, "z": 0.03})
        self.assertTrue(h["x"]["reject_null"])                    # 0.01 <= 0.05/3
        self.assertFalse(h["z"]["reject_null"])                   # 0.03 > 0.05/2: stops here
        self.assertFalse(h["y"]["reject_null"])

    def test_wilcoxon_symmetric_and_shifted(self):
        self.assertEqual(ha.wilcoxon([1, 2], [1, 2])["n"], 0)
        w = ha.wilcoxon([1.0] * 12, [0.0] * 12)
        self.assertLess(w["p_two_sided"], 0.01)


class Selection(unittest.TestCase):
    def test_caps_and_determinism(self):
        pool = [{"instance_id": f"b{b}:f{f}:{s}", "base_id": f"b{b}", "fault": f"f{f}", "kept": True}
                for b in range(14) for f in range(8) for s in (0.5, 1.0)]
        ids, cap = hs.select(pool, 40)
        self.assertEqual(len(ids), 40)
        self.assertEqual(cap, 3)
        self.assertEqual(ids, hs.select(list(reversed(pool)), 40)[0])
        sel = [r for r in pool if r["instance_id"] in set(ids)]
        from collections import Counter
        self.assertLessEqual(max(Counter(r["fault"] for r in sel).values()), 6)
        self.assertLessEqual(max(Counter(r["base_id"] for r in sel).values()), 3)
        small = pool[:5]
        self.assertEqual(len(hs.select(small, 40)[0]), 5)


if __name__ == "__main__":
    unittest.main()
