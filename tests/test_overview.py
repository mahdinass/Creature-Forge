import json
import unittest
from pathlib import Path

from creature_forge import overview

ROOT = Path(__file__).resolve().parents[1]


class OverviewTests(unittest.TestCase):
    def test_classical_numbers_come_from_the_committed_r2_records(self):
        c = overview.classical_r2()
        f = json.loads((ROOT / "experiments/phase2a_r2/results/final.json").read_text(encoding="utf-8"))
        self.assertEqual((c["winner_walking"], c["incumbent_walking"], c["n"]), (150, 91, 150))
        self.assertEqual(c["paired"]["winner_only"], f["paired_table"]["new_only"])
        self.assertTrue(c["non_inferior"] and c["superior"])
        self.assertIn("No language model", c["attribution"])
        self.assertLess(c["winner_exact_ci"][0], 1.0)                         # an exact lower bound, not "100%"

    def test_nemotron_section_is_honest_about_random_edits_and_the_unfinished_comparison(self):
        n = overview.nemotron_demo()
        recorded = [r for r in n["recorded_runs"] if r["kind"] == "RECORDED_LIVE"]
        self.assertEqual(len(recorded), 2)
        self.assertTrue(any(r["valid_proposals"] == 0 for r in recorded))     # the rejected live run is not hidden
        run2 = next(r for r in recorded if r["valid_proposals"] == 2)
        self.assertTrue(any(p["random_walking"] >= p["model_walking"] for p in run2["proposals"]))   # random did as well or better: stated, not hidden
        self.assertEqual(n["systematic_comparison"]["status"], "not completed")
        self.assertIsNone(n["systematic_comparison"]["chosen_setting"])
        self.assertIn("does NOT show", n["claim"])
        self.assertTrue(all(r["kind"] != "LIVE" for r in n["recorded_runs"]))
        self.assertLessEqual(n["usage"]["requests"], n["usage"]["requests_cap"])

    def test_limits_keep_the_two_lines_of_evidence_apart(self):
        o = overview.overview()
        text = " ".join(o["limits"])
        self.assertIn("classical optimisation, not from the language model", text)
        self.assertIn("not completed", text)
        self.assertEqual(len(o["pipeline"]), 5)


if __name__ == "__main__":
    unittest.main()
