"""No-physics tests of the preregistered W3/W4 analysis (scripts/do1_replication_analysis.py)."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import do1_replication_analysis as an  # noqa: E402


def _rec(arm, r, status, k, role="primary", case="L4", exposed=True, med=0.7, conf=None, gates=("speed",) * 4, last=True):
    reasons = [] if status == an.FULL else [f"candidate aggregate is POOR, not PASS (walking on {k} of 24 seeds)"]
    rec = {"instance_id": {"L4": "hdb-v1-gen-0137:low_ground_friction:0", "B1": "b1", "C1": "c1"}[case], "submitted": 4,
           "wall_s": 300.0, "repair": {"accepted": False},
           "verification": {"summary": {"status": status, "walking_frac": k / 24, "reasons": reasons},
                            "full": {"validation": {"aggregate": "PASS" if k >= 20 else "POOR",
                                                    "verdict": {"status": "VERIFIED_IMPROVEMENT", "wins": 20, "losses": 1,
                                                                "ties": 3, "median_diff": med, "p_one_sided": 1e-5}},
                                     "confirmation": {"run": conf is not None, "passed": conf, "checks": {}}}},
           "harness": {"case": case, "replicate": r, "role": role, "noise_seed": 1751409197 + 10007 * r,
                       "resources": {"plant": {"used": 700}, "twin": {"used": 2500}, "total_rollout_equivalents": 3300.0},
                       "arm_checks": {"valid": exposed, "exposed": None if arm == "frozen" else exposed,
                                      "problems": [] if exposed else ["NOT_EXPOSED: no DO-1 repair completed"]},
                       "rescreen": {"classification": "no re-screen"},
                       "do1": {"arm": arm, "repairs": [] if (arm == "frozen" or not exposed) else [{
                           "tool": "leg_length", "design_index": 4, "selected_log_index": 2 if last else 0,
                           "candidates": [{}, {}, {}],
                           "selected": {"walking_count": 4, "margin": 0.28, "median_diff_m": 0.8,
                                        "per_seed": [{"binding_gate": g} for g in gates]}}]}}}
    return rec


class Statistics(unittest.TestCase):
    def test_clopper_pearson_closed_forms(self):
        lo, hi = an.clopper_pearson(0, 5)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 1 - 0.025 ** (1 / 5), places=6)
        lo, hi = an.clopper_pearson(5, 5)
        self.assertAlmostEqual(lo, 0.025 ** (1 / 5), places=6)
        self.assertEqual(hi, 1.0)
        lo, hi = an.clopper_pearson(1, 5)                               # standard table values
        self.assertAlmostEqual(lo, 0.00505, places=4)
        self.assertAlmostEqual(hi, 0.71641, places=4)

    def test_sign_test(self):
        self.assertAlmostEqual(an.sign_test_one_sided(5, 0), 0.03125)
        self.assertAlmostEqual(an.sign_test_one_sided(4, 0), 0.0625)
        self.assertAlmostEqual(an.sign_test_one_sided(4, 1), 6 / 32)
        self.assertIsNone(an.sign_test_one_sided(0, 0))


class W3(unittest.TestCase):
    def _recs(self):
        recs = [_rec("frozen", 0, an.PARTIAL, 19, role="sentinel")]
        outcomes = {1: ((an.PARTIAL, 19), (an.FULL, 21)), 2: ((an.FULL, 22), (an.FULL, 21)),
                    3: ((an.PARTIAL, 18), (an.PARTIAL, 18)), 4: ((an.FULL, 20), (an.PARTIAL, 19)),
                    5: ((an.PARTIAL, 17), (an.FULL, 23))}
        for r, ((sf, kf), (sd, kd)) in outcomes.items():
            recs += [_rec("frozen", r, sf, kf), _rec("do1", r, sd, kd, conf=True if sd == an.FULL else None)]
        return recs

    def test_itt_tallies(self):
        a = an.w3_analysis(*an.split_lines(self._recs()))
        self.assertEqual(len(a["sentinel"]), 1)
        itt = a["itt"]
        self.assertEqual((itt["n_pairs"], itt["full_frozen"], itt["full_do1"]), (5, 2, 3))
        self.assertEqual((itt["discordant_for_do1"], itt["discordant_against_do1"]), (2, 1))
        self.assertAlmostEqual(itt["mcnemar_one_sided_p"], 0.5)
        self.assertIn("mixed", itt["reading"])
        self.assertEqual(itt["walking_diff"], [2, -1, 0, -1, 6])
        self.assertEqual((itt["walking_sign_for"], itt["walking_sign_against"]), (2, 2))
        self.assertEqual(itt["status_counts"]["do1"][an.FULL], 3)
        self.assertEqual(a["per_protocol"], itt)                       # every do1 episode exposed
        self.assertEqual(a["incomplete_pairs"], [])

    def test_not_exposed_kept_in_itt_and_excluded_in_pp(self):
        recs = self._recs()
        recs[2] = _rec("do1", 1, an.PARTIAL, 19, exposed=False)
        a = an.w3_analysis(*an.split_lines(recs))
        self.assertEqual(a["itt"]["n_pairs"], 5)
        self.assertEqual(a["per_protocol"]["n_pairs"], 4)
        self.assertEqual([x["replicate"] for x in a["per_protocol_excluded"]], [1])

    def test_infrastructure_error_makes_an_incomplete_pair(self):
        recs = self._recs()[:7] + [{"infrastructure_error": True, "case": "L4", "arm": "do1", "replicate": 4, "error": "x"}]
        a = an.w3_analysis(*an.split_lines(recs))
        self.assertEqual(a["itt"]["n_pairs"], 3)
        self.assertEqual([x["replicate"] for x in a["incomplete_pairs"]], [4, 5])
        self.assertEqual(len(a["incomplete_pairs"][0]["infrastructure_error"]), 1)

    def test_readings(self):
        def a(outs):
            recs = []
            for r, (f, d) in enumerate(outs, 1):
                recs += [_rec("frozen", r, f, 19), _rec("do1", r, d, 21)]
            return an.w3_analysis(*an.split_lines(recs))["itt"]["reading"]
        F, P = an.FULL, an.PARTIAL
        self.assertIn("p <= 0.05", a([(P, F)] * 5))
        self.assertIn("suggestive", a([(P, F)] * 4 + [(F, F)]))
        self.assertIn("no discordant pair:", a([(F, F)] * 5))
        self.assertIn("no evidence of improvement", a([(F, P)] + [(P, P)] * 4))

    def test_report_and_json(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "w3.jsonl")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(r) for r in self._recs()) + "\n")
        out = os.path.join(tmp, "s.json")
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(an.main(["--w3", p, "--json", out]), 0)
        self.assertIn("SENTINEL", buf.getvalue())
        self.assertIn("ITT", buf.getvalue())
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["w3"]["itt"]["n_pairs"], 5)


class W4(unittest.TestCase):
    def test_descriptive_per_case(self):
        recs = [_rec("frozen", 0, an.PARTIAL, 17, role="exploratory", case="B1"),
                _rec("do1", 0, an.FULL, 21, role="exploratory", case="B1", conf=True),
                _rec("frozen", 0, an.PARTIAL, 19, role="exploratory", case="C1"),
                _rec("do1", 0, an.PARTIAL, 18, role="exploratory", case="C1")]
        a = an.w4_analysis(*an.split_lines(recs))
        self.assertEqual(a["B1"]["direction"], "do1 better status")
        self.assertEqual(a["C1"]["direction"], "same status; walking -1/24")
        self.assertEqual(a["B1"]["gates"]["walking_k"], (17, 21))
        self.assertTrue(a["B1"]["gates"]["reasons_frozen_only"])


if __name__ == "__main__":
    unittest.main()
