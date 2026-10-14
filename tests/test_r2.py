import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from creature_forge import r1, r2
from creature_forge.optimize import Executor


def fake_seed(seed, walking, fell, fit=-0.4, drag=False):
    return {"seed": seed, "label": "walking" if walking else "fall", "walking": walking, "fell": fell, "fall_time": None if not fell else 1.0,
            "speed_upright": 0.4 if walking else -0.2, "forward_disp_upright": 1.0, "valid_steps": 20 if walking else 0,
            "violations": (["body_dragging"] if drag else []), "fitness": {"total": fit}}


def fake_job(job):
    """Deterministic stand-in for physics: walks on a seed iff the vector is close to theta0 in u-space (closer -> more seeds)."""
    d = float(np.linalg.norm(r2.to_u(job["vector"]) - r2.to_u(r2.incumbent_theta())))
    per = []
    for k, s in enumerate(job["seeds"]):
        walk = d < 0.12 + 0.03 * (k % 4)
        per.append(fake_seed(s, walk, not walk and d > 0.5, 5.0 if walk else -0.4 - d))
    return {"ok": True, "result": {"per_seed": per, "median_speed": 0.1, "labels": [m["label"] for m in per]}, "wall_s": 0.0, "peak_rss_mb": 50.0}


class SeedTests(unittest.TestCase):
    def test_all_seed_sets_disjoint_from_each_other_and_from_consumed(self):
        r2.check_disjoint()
        allseeds = [*r2.SCREEN_SEEDS, *r2.VALIDATION_SEEDS, *r2.DIAGNOSTIC_SEEDS, *r2.PILOT_SEEDS, *r2.FINAL_SEEDS]
        self.assertEqual(len(allseeds), len(set(allseeds)))
        for name, seeds in r2.consumed_seed_sets().items():
            self.assertFalse(set(seeds) & set(allseeds), name)
        self.assertEqual((len(r2.SCREEN_SEEDS), len(r2.VALIDATION_SEEDS), len(r2.DIAGNOSTIC_SEEDS), len(r2.FINAL_SEEDS)), (64, 64, 32, 150))

    def test_training_selection_is_deterministic_and_class_balanced(self):
        screen = [fake_seed(7000 + i, walking=(i % 3 != 0), fell=False) for i in range(64)]
        sel = r2.select_training_seeds(screen[::-1])               # input order must not matter
        self.assertFalse(sel["stop"])
        walking = [s for s in range(7000, 7064) if (s - 7000) % 3 != 0][:8]
        failing = [s for s in range(7000, 7064) if (s - 7000) % 3 == 0][:8]
        self.assertEqual(sel["train_seeds"], sorted(walking + failing))
        self.assertEqual(r2.select_training_seeds(screen)["train_seeds"], sel["train_seeds"])

    def test_insufficient_class_is_a_registered_stop_not_an_improvisation(self):
        few_fail = [fake_seed(7000 + i, walking=(i >= 5), fell=False) for i in range(64)]
        sel = r2.select_training_seeds(few_fail)
        self.assertTrue(sel["stop"])
        self.assertEqual(sel["train_seeds"], [])
        self.assertIn("STOP", sel["reason"])
        few_walk = [fake_seed(7000 + i, walking=(i < 3), fell=False) for i in range(64)]
        self.assertTrue(r2.select_training_seeds(few_walk)["stop"])

    def test_train_seeds_refuses_when_stop_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "training_set.json"
            p.write_text(json.dumps({"stop": True, "reason": "x"}))
            with mock.patch.object(r2, "TRAINING_SET", p):
                with self.assertRaises(SystemExit):
                    r2.train_seeds()


class CandidateTests(unittest.TestCase):
    def test_reflection_keeps_values_inside_and_folds_overshoot(self):
        u = np.array([-0.1, 0.0, 0.3, 1.0, 1.2, -1.1, 2.3])
        r = r2.reflect(u)
        self.assertTrue(((r >= 0) & (r <= 1)).all())
        np.testing.assert_allclose(r, [0.1, 0.0, 0.3, 1.0, 0.8, 0.9, 0.3], atol=1e-12)

    def test_arm_s_is_reproducible_in_bounds_and_follows_the_specified_assignment(self):
        a, b = r2.s_candidates(1), r2.s_candidates(1)
        self.assertEqual([c["vector"] for c in a], [c["vector"] for c in b])
        self.assertNotEqual(a[0]["vector"], r2.s_candidates(2)[0]["vector"])
        theta0 = r2.incumbent_theta()
        self.assertEqual(len(a), 120)
        for i, c in enumerate(a):
            v = np.asarray(c["vector"])
            self.assertTrue(((v >= r2.LOWER15 - 1e-12) & (v <= r2.UPPER15 + 1e-12)).all(), i)
            self.assertEqual(c["sigma"], r2.S_SCALES[i % 4])
            self.assertEqual(c["k"], r2.S_KS[(i % 12) // 4])
            self.assertEqual(len(c["coords"]), c["k"])
            self.assertTrue(all(0 <= j < 13 for j in c["coords"]))
            self.assertEqual(v[13], theta0[13])                      # initiation coordinates untouched
            self.assertEqual(v[14], theta0[14])
            changed = {j for j in range(15) if v[j] != theta0[j]}
            self.assertTrue(changed <= set(c["coords"]), (i, changed, c["coords"]))

    def test_arm_i_grid_is_exactly_49_with_one_reference_equal_to_theta0(self):
        g = r2.i_candidates()
        self.assertEqual(len(g), 49)
        self.assertEqual([c["index"] for c in g], list(range(49)))
        refs = [c for c in g if c["reference"]]
        self.assertEqual([c["index"] for c in refs], [7])
        np.testing.assert_array_equal(refs[0]["vector"], r2.incumbent_theta())
        self.assertEqual({c["ramp_s"] for c in g}, set(r2.RAMP_GRID))
        self.assertEqual({c["start_lean"] for c in g}, set(r2.LEAN_GRID))
        theta0 = r2.incumbent_theta()
        for c in g:
            np.testing.assert_array_equal(np.asarray(c["vector"])[:13], theta0[:13])
            self.assertEqual((c["vector"][13], c["vector"][14]), (c["ramp_s"], c["start_lean"]))
        self.assertEqual(g[24]["ramp_s"], 1.1)
        self.assertEqual(g[24]["start_lean"], 0.075)

    def test_manifest_hash_is_stable(self):
        self.assertEqual(r2.candidate_manifest_sha256(), r2.candidate_manifest_sha256())


class SelectionLogicTests(unittest.TestCase):
    def rec(self, arm="S", rep=1, idx=0, walk=0, surv=0, mean=0.0, drag=False):
        per = [fake_seed(i, i < walk, i >= surv, drag=drag and i == 0) for i in range(64)]
        return {"arm": arm, "replicate": rep, "index": idx, "walking_count": walk, "survival_count": surv, "objective": {"mean": mean},
                "error": None, "per_seed": per, "vector": [0.0] * 15, "training_score": [0, 0, 0.0]}

    def test_feasibility_and_ranking_prefer_walking_count_then_survival_then_fitness(self):
        h = [self.rec(idx=0, walk=5, surv=9, mean=1), self.rec(idx=1, walk=6, surv=6, mean=0), self.rec(idx=2, walk=2, surv=16, mean=9),
             self.rec(idx=3, walk=5, surv=12, mean=0)]
        order = r2.rank_training(h, w0=6)
        self.assertEqual(order[:3], [1, 3, 0])                    # idx 2 (2 < 6-1) is infeasible: last despite the best fitness
        self.assertEqual(order[-1], 2)
        self.assertFalse(r2.is_feasible(h[2], 6))
        self.assertTrue(r2.is_feasible(h[0], 6))

    def test_reference_entries_are_never_ranked(self):
        h = [{**self.rec(idx=0, walk=9), "reference": True}, self.rec(idx=1, walk=1)]
        self.assertEqual(r2.rank_training(h, 0), [1])

    def test_gate_threshold_is_five_seeds_among_preserving_candidates(self):
        inc = self.rec(arm="incumbent", walk=40, surv=45)
        good = self.rec(idx=3, walk=45, surv=47)
        under = self.rec(arm="T", idx=4, walk=44, surv=47)
        g = r2.futility_gate({"S": [{"validated": [good]}], "T": [{"validated": [under]}], "I": [{"validated": []}]}, inc)
        self.assertTrue(g["proceed"])
        self.assertTrue(g["arms"]["S"]["meets_threshold"] and not g["arms"]["T"]["meets_threshold"])
        self.assertEqual(g["arms"]["S"]["gain_seeds"], 5)
        self.assertIsNone(g["arms"]["I"]["best"])
        none = r2.futility_gate({"S": [{"validated": [under]}], "T": [{"validated": []}], "I": [{"validated": []}]}, inc)
        self.assertFalse(none["proceed"])

    def test_preservation_excludes_regressions_in_survival_or_dragging(self):
        inc = self.rec(arm="incumbent", walk=40, surv=45)
        falls_more = self.rec(idx=1, walk=60, surv=44)
        drags = self.rec(idx=2, walk=60, surv=50, drag=True)
        fine = self.rec(idx=3, walk=50, surv=45)
        self.assertFalse(r2.eligible(falls_more, inc))
        self.assertFalse(r2.eligible(drags, inc))
        self.assertTrue(r2.eligible(fine, inc))
        win = r2.select_winner([{"validated": [falls_more, drags, fine]}], inc)
        self.assertEqual(win["index"], 3)
        with self.assertRaises(RuntimeError):
            r2.select_winner([{"validated": [falls_more]}], inc)

    def test_selection_ties_break_by_arm_order_replicate_index(self):
        inc = self.rec(arm="incumbent", walk=10, surv=10)
        a = self.rec(arm="T", rep=1, idx=1, walk=20, surv=20, mean=1)
        b = self.rec(arm="S", rep=2, idx=9, walk=20, surv=20, mean=1)
        c = self.rec(arm="S", rep=1, idx=50, walk=20, surv=20, mean=1)
        self.assertEqual(r2.select_winner([{"validated": [a, b, c]}], inc)["index"], 50)


class LedgerAndStageTests(unittest.TestCase):
    def setUp(self):
        # the resource floor is exercised by its own tests; fake-physics tests must not depend on this machine's free RAM
        p = mock.patch.object(r1, "free_memory_gb", return_value=16.0)
        p.start()
        self.addCleanup(p.stop)

    def test_caps_pilot_100_and_hard_12000(self):
        with tempfile.TemporaryDirectory() as d:
            led = r2.Ledger(Path(d) / "l.jsonl")
            led.begin("pilot", 96)
            with self.assertRaises(r1.BudgetExceeded):
                led.begin("pilot", 5)
            with mock.patch.object(r2, "BUDGET_CAP", 200):
                with self.assertRaises(r1.BudgetExceeded):
                    led.begin("x", 105)
                led.begin("x", 104)
            led.verify()

    def test_wall_limit_is_sixty_minutes_of_active_time(self):
        self.assertEqual(r2.WALL_LIMIT_S, 3600)
        with tempfile.TemporaryDirectory() as d:
            led = r2.Ledger(Path(d) / "l.jsonl")
            led.session_begin("x")
            led._session_t0 -= 3700.0
            with self.assertRaises(r1.ResourceAbort):
                r2.check_resources(led)

    def test_planned_budget_fits_the_cap(self):
        p = r2.planned_budget()
        self.assertEqual(p["pilot"], 96)
        self.assertLessEqual(p["pilot"], r2.PILOT_CAP)
        self.assertLessEqual(p["total"], r2.BUDGET_CAP)
        self.assertEqual(p["total"], 10700)

    def test_arm_s_counts_exactly_and_refuses_repeat(self):
        seeds = tuple(range(16))
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            led = r2.Ledger(out / "l.jsonl")
            with Executor(1, fn=fake_job) as ex:
                hist = r2.run_training_S(1, ex, led, seeds, out_dir=out)
                with self.assertRaises(FileExistsError):
                    r2.run_training_S(1, ex, led, seeds, out_dir=out)
            self.assertEqual(len(hist), 120)
            self.assertEqual(led.total_rollouts(), 120 * 16)

    def test_arm_i_executes_48_and_never_runs_the_reference(self):
        seeds = tuple(range(16))
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            led = r2.Ledger(out / "l.jsonl")
            with Executor(1, fn=fake_job) as ex:
                hist = r2.run_training_I(ex, led, seeds, out_dir=out)
            self.assertEqual(len(hist), 48)
            self.assertNotIn(7, [h["index"] for h in hist])
            self.assertEqual(led.total_rollouts(), 48 * 16)

    def test_arm_t_is_reproducible_bounded_counts_exactly_and_follows_the_step_rule(self):
        seeds = tuple(range(16))
        parent = {"error": None, "walking_count": 8, "survival_count": 12, "objective": {"mean": 1.0}}
        runs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as d:
                out = Path(d)
                led = r2.Ledger(out / "l.jsonl")
                with Executor(1, fn=fake_job) as ex:
                    runs.append(r2.run_training_T(1, ex, led, seeds, 8, parent, out_dir=out))
                self.assertEqual(led.total_rollouts(), 15 * 8 * 16)
        a, b = runs
        self.assertEqual([r["vector"] for r in a], [r["vector"] for r in b])
        self.assertEqual(len(a), 120)
        for r in a:
            v = np.asarray(r["vector"])
            self.assertTrue(((v >= r2.LOWER15 - 1e-12) & (v <= r2.UPPER15 + 1e-12)).all())
        sig = [a[g * 8]["sigma"] for g in range(15)]
        self.assertEqual(sig[0], r2.T_SIGMA0)
        for g in range(14):                                       # check the 1/5 rule on the recorded success rates
            ps = a[g * 8]["generation_success_rate"]
            expect = sig[g] * (r2.T_UP if ps > 0.2 else (r2.T_DOWN if ps < 0.2 else 1.0))
            self.assertAlmostEqual(sig[g + 1], float(np.clip(expect, *r2.T_SIGMA_RANGE)))


class ProtocolAndAnalysisTests(unittest.TestCase):
    def test_protocol_is_self_consistent_and_hashes_are_line_ending_independent(self):
        p = r2.build_protocol()
        self.assertEqual(p, json.loads(json.dumps(r2.build_protocol())))
        self.assertEqual(p["budget"]["hard_cap_rollouts"], 12000)
        self.assertEqual(p["resources"]["wall_clock_hard_stop_s"], 3600)
        self.assertEqual(p["final_evaluation"]["n"], 150)
        self.assertEqual(p["final_evaluation"]["engineering_criterion"]["min_walking_seeds"], 135)
        self.assertIn("Tango", p["final_evaluation"]["confirmatory_hierarchy"]["step1_noninferiority"]["test"])
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a", Path(d) / "b"
            a.write_bytes(b"x\ny\n")
            b.write_bytes(b"x\r\ny\r\n")
            self.assertEqual(r2.sha256_lf(a), r2.sha256_lf(b))

    def test_final_analysis_reports_hierarchy_engineering_and_descriptive_parts_separately(self):
        win = [fake_seed(i, walking=i < 140, fell=False) for i in range(150)]
        inc = [fake_seed(i, walking=i < 100, fell=False) for i in range(150)]
        out = r2.final_analysis(win, inc)
        self.assertEqual(out["paired_table"], {"both": 100, "new_only": 40, "old_only": 0, "neither": 10, "n": 150})
        h = out["confirmatory_hierarchy"]
        self.assertTrue(h["claims"]["preservation_confirmed"] and h["claims"]["improvement_confirmed"])
        self.assertTrue(out["engineering"]["winner"]["meets_engineering_criterion"])
        self.assertFalse(out["engineering"]["incumbent"]["meets_engineering_criterion"])
        self.assertIn("descriptive_paired_comparison", out)
        # statistical success without engineering success, and vice versa, are kept distinct
        win2 = [fake_seed(i, walking=i < 120, fell=False) for i in range(150)]
        out2 = r2.final_analysis(win2, inc)
        self.assertTrue(out2["confirmatory_hierarchy"]["claims"]["improvement_confirmed"])
        self.assertFalse(out2["engineering"]["winner"]["meets_engineering_criterion"])


if __name__ == "__main__":
    unittest.main()
