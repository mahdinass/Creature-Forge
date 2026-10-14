import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from creature_forge import r1, r1_stats
from creature_forge.locomotion import rollout
from creature_forge.morphology import BipedParams
from creature_forge.optimize import Executor
from creature_forge.phasegait import PhaseGaitController, PhaseGaitParams
from creature_forge.phasegait_init import (INIT_BOUNDS, InitParams, PhaseGaitInitController, controller_from_export,
                                           controller_from_vector)

P2A = Path(__file__).resolve().parents[1] / "experiments" / "phase2a" / "results"


class InitControllerTests(unittest.TestCase):
    def test_defaults_are_bit_identical_to_phase2a_controller(self):
        p = PhaseGaitParams().replace(pitch_kp=85.0, pitch_ref=0.155)
        a = rollout(PhaseGaitController(p), BipedParams(), 3000, 3.0)
        b = rollout(PhaseGaitInitController(p, InitParams()), BipedParams(), 3000, 3.0)
        for k in ("t", "x", "z", "pitch", "q", "qd", "tau", "demand", "force"):
            self.assertTrue(np.array_equal(a[k], b[k]), k)

    def test_frozen_incumbent_reproduces_saved_heldout_results_exactly(self):
        held = json.loads((P2A / "heldout.json").read_text(encoding="utf-8"))["controllers"]["random_search"]["aggregate"]["per_seed"]
        saved = {r["seed"]: r for r in held}
        ctrl = controller_from_vector(r1.incumbent_vector(15))   # goes through the 15-D init path
        from creature_forge.locomotion import compute_metrics
        for seed in (3000, 3006):
            m = compute_metrics(rollout(ctrl, BipedParams(), seed, 10.0))
            self.assertEqual(m["forward_disp_upright"], saved[seed]["forward_disp_upright"])
            self.assertEqual(m["valid_steps"], saved[seed]["valid_steps"])
            self.assertEqual(m["fall_time"], saved[seed]["fall_time"])

    def test_nondefault_parameters_change_behaviour_as_specified(self):
        p = PhaseGaitParams()
        c = PhaseGaitInitController(p, InitParams(ramp_s=1.5, start_lean=0.1))
        self.assertAlmostEqual(c._pitch_ref(0.0), p.pitch_ref + 0.1)
        self.assertAlmostEqual(c._pitch_ref(1.0), p.pitch_ref)
        self.assertAlmostEqual(c._pitch_ref(5.0), p.pitch_ref)
        self.assertEqual(c._ramp_s, 1.5)
        a = rollout(PhaseGaitController(p), BipedParams(), 4000, 2.0)
        b = rollout(c, BipedParams(), 4000, 2.0)
        self.assertFalse(np.array_equal(a["tau"], b["tau"]))

    def test_bounds_and_vector_lengths(self):
        with self.assertRaises(ValueError):
            InitParams(ramp_s=0.05).validate()
        with self.assertRaises(ValueError):
            InitParams(start_lean=0.5).validate()
        with self.assertRaises(ValueError):
            controller_from_vector(np.zeros(14))
        self.assertIsInstance(controller_from_vector(r1.incumbent_vector(13)), PhaseGaitController)
        self.assertIsInstance(controller_from_vector(r1.incumbent_vector(15)), PhaseGaitInitController)

    def test_export_round_trip(self):
        d = {"controller": "phase_gait_init", "params": PhaseGaitParams().as_dict(), "init": {"ramp_s": 0.8, "start_lean": 0.05},
             "body": BipedParams().as_dict()}
        ctrl, body = controller_from_export(d)
        self.assertEqual(ctrl.init.ramp_s, 0.8)
        with self.assertRaises(ValueError):
            controller_from_export({**d, "controller": "nope"})


class CandidateAndSeedTests(unittest.TestCase):
    def test_seed_sets_disjoint_and_roles(self):
        r1.check_disjoint()
        self.assertEqual(r1.seed_role(6000), "r1_final")
        self.assertEqual(r1.seed_role(4100), "r1_validation")
        self.assertIsNone(r1.seed_role(3000))   # consumed Phase 2A held-out seeds are not R1 seeds

    def test_candidates(self):
        a, b, c = (r1.candidate_vectors(x, 1) for x in "ABC")
        self.assertEqual(a.shape, (150, 13))
        self.assertEqual(c.shape, (150, 15))
        self.assertTrue(np.array_equal(a, b))                   # common random numbers
        self.assertTrue(np.array_equal(a, c[:, :13]))
        self.assertTrue(np.array_equal(a[0], r1.incumbent_vector(13)))
        self.assertEqual(c[0, 13], 0.5)
        self.assertEqual(c[0, 14], 0.0)
        self.assertTrue(np.all(c[:, 13] >= INIT_BOUNDS["ramp_s"][0]) and np.all(c[:, 13] <= INIT_BOUNDS["ramp_s"][1]))
        self.assertTrue(np.all(c[:, 14] >= 0.0) and np.all(c[:, 14] <= 0.15))
        self.assertTrue(np.array_equal(a, r1.candidate_vectors("A", 1)))            # deterministic
        self.assertFalse(np.array_equal(a[1:], r1.candidate_vectors("A", 2)[1:]))   # independent replicates
        self.assertTrue(np.array_equal(a[0], r1.candidate_vectors("A", 2)[0]))
        for v in a:
            PhaseGaitParams.from_vector(v)   # in bounds

    def test_lower_tail_objective(self):
        o = r1.objective_values([5, 1, 4, 3, 2, 6, 7, 8])
        self.assertAlmostEqual(o["mean"], 4.5)
        self.assertAlmostEqual(o["worst2"], 1.5)

    def test_initial_perturbation_matches_phase2a_record(self):
        diag = json.loads((P2A / "failure_diagnosis.json").read_text(encoding="utf-8"))
        for row in diag["rows"]:
            self.assertAlmostEqual(r1.initial_perturbation(row["seed"])["pitch0"], row["init"]["pitch0"], places=12)


class LedgerTests(unittest.TestCase):
    def test_counts_persist_and_chain_and_caps(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ledger.jsonl"
            led = r1.Ledger(path)
            b = led.begin("pilot", 30)
            led.end(b, 30, 0, 1.0, 200.0, 8.0)
            self.assertEqual(r1.Ledger(path).total_rollouts(), 30)           # survives a "restart"
            with self.assertRaises(r1.BudgetExceeded):
                led.begin("pilot", 11)                                      # pilot cap 40
            led.begin("train-A1", 160)                                      # begun but never ended (crash): still counted
            self.assertEqual(r1.Ledger(path).total_rollouts(), 190)
            with mock.patch.object(r1, "BUDGET_CAP", 200):
                with self.assertRaises(r1.BudgetExceeded):
                    led.begin("train-A1", 11)
                led.begin("train-A1", 10)
            led.verify()
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[1] = lines[1].replace('"executed": 30', '"executed": 3')   # tamper
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                r1.Ledger(path).verify()

    def test_wall_limit_and_memory_abort(self):
        with tempfile.TemporaryDirectory() as d:
            led = r1.Ledger(Path(d) / "l.jsonl")
            b = led.begin("x", 1)
            led.end(b, 1, 0, r1.WALL_LIMIT_S + 1, 1.0, 9.0)
            with self.assertRaises(r1.ResourceAbort):
                r1.check_resources(led)
            led2 = r1.Ledger(Path(d) / "l2.jsonl")
            with mock.patch.object(r1, "free_memory_gb", return_value=3.0):
                with self.assertRaises(r1.ResourceAbort):
                    r1.check_resources(led2)

    def test_resource_probes_return_sane_values(self):
        self.assertGreater(r1.free_memory_gb(), 0.1)
        self.assertGreater(r1.peak_rss_mb(), 10.0)


class RunTests(unittest.TestCase):
    """Tiny end-to-end runs (1 s episodes, 3 candidates) through the real batch/ledger/history code."""

    def setUp(self):
        orig = r1.make_jobs
        self.p = [mock.patch.object(r1, "CANDIDATES", 3), mock.patch.object(r1, "TRAIN_SEEDS", (4000, 4001)),
                  mock.patch.object(r1, "VALIDATION_SEEDS", (4100, 4101)),
                  mock.patch.object(r1, "make_jobs", lambda v, s: orig(v, s, 1.0)),
                  mock.patch.object(r1, "free_memory_gb", return_value=16.0)]   # tests must not depend on host memory
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_training_validation_ledger_and_no_silent_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            led = r1.Ledger(out / "ledger.jsonl")
            with Executor(1, fn=r1.r1_job) as ex:
                hist = r1.run_training("C", 1, ex, led, out_dir=out, batch=2)
                self.assertEqual(len(hist), 3)
                self.assertTrue(hist[0]["incumbent"])
                self.assertEqual(led.total_rollouts(), 3 * 2)
                lines = (out / "history_C1.jsonl").read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(lines), 3)
                with self.assertRaises(FileExistsError):
                    r1.run_training("C", 1, ex, led, out_dir=out, batch=2)
                before = led.total_rollouts()
                val = r1.run_validation("C", 1, hist, ex, led, out_dir=out)
                self.assertEqual(len(val["validated"]), len(r1.rank_training(hist, "worst2")[:r1.TOP_K]) - int(val["incumbent_in_top5"]))
                self.assertEqual(led.total_rollouts(), before + 2 * len(val["validated"]))
                self.assertTrue(all(not v["incumbent"] if "incumbent" in v else True for v in val["validated"]))
            led.verify()

    def test_pool_run_matches_inline_and_worker_count_invariance(self):
        vecs = r1.candidate_vectors("A", 1)[:2]
        jobs = r1.make_jobs(vecs, (4000, 4001))
        inline = [r1.r1_job(j) for j in jobs]
        with Executor(2, fn=r1.r1_job) as ex:
            pooled = ex.map(jobs)
        for a, b in zip(inline, pooled):
            self.assertTrue(a["ok"] and b["ok"])
            self.assertEqual(a["result"]["fitness"], b["result"]["fitness"])
            self.assertGreater(b["peak_rss_mb"], 10.0)

    def test_a_and_b_evaluate_identical_rollouts(self):
        """Determinism audit: arms A and B share candidates and seeds, so their evaluations must be identical."""
        a = r1.r1_job(r1.make_jobs(r1.candidate_vectors("A", 1)[1:2], (4000, 4001))[0])
        b = r1.r1_job(r1.make_jobs(r1.candidate_vectors("B", 1)[1:2], (4000, 4001))[0])
        self.assertEqual(a["result"]["fitness"], b["result"]["fitness"])
        self.assertEqual(a["result"]["labels"], b["result"]["labels"])

    def test_errors_are_recorded_and_counted(self):
        with tempfile.TemporaryDirectory() as d:
            led = r1.Ledger(Path(d) / "l.jsonl")
            bad = [[0.0] * 13]       # outside bounds -> ValueError inside the job
            with Executor(1, fn=r1.r1_job) as ex:
                outs = r1.run_batch(ex, led, "t", bad, (4000,))
            self.assertFalse(outs[0]["ok"])
            self.assertEqual(led.total_rollouts(), 1)
            rec = r1._record(bad[0], outs[0], (4000,), {"arm": "A", "replicate": 1, "index": 0})
            self.assertIsNotNone(rec["error"])
            self.assertEqual(rec["objective"]["mean"], r1.ERROR_FITNESS)


def _rec(arm, rep, idx, walk, surv, fit):
    return {"arm": arm, "replicate": rep, "index": idx, "walking_count": walk, "survival_count": surv,
            "objective": {"mean": fit, "worst2": fit}, "error": None}


class SelectionTests(unittest.TestCase):
    def test_deterministic_ranking_and_tiebreakers(self):
        recs = [_rec("B", 1, 5, 10, 12, 3.0), _rec("A", 2, 9, 10, 12, 3.0), _rec("A", 1, 7, 10, 12, 3.0),
                _rec("C", 1, 2, 11, 11, 1.0), _rec("A", 1, 3, 10, 13, 0.0), _rec("A", 1, 4, 10, 12, 3.5)]
        order = [(r["arm"], r["replicate"], r["index"]) for r in r1.rank_validated(recs)]
        self.assertEqual(order[0], ("C", 1, 2))        # most walking seeds wins
        self.assertEqual(order[1], ("A", 1, 3))        # then survival
        self.assertEqual(order[2], ("A", 1, 4))        # then mean fitness
        self.assertEqual(order[3:], [("A", 1, 7), ("A", 2, 9), ("B", 1, 5)])   # then arm order, replicate, index
        self.assertEqual(r1.select_winner([{"validated": recs}])["index"], 2)
        self.assertEqual(r1.rank_validated(list(reversed(recs))), r1.rank_validated(recs))

    def test_futility_gate(self):
        inc = {"walking_count": 8}
        mk = lambda w: [{"validated": [_rec("A", 1, 1, w, 16, 1.0)]}]  # noqa: E731
        stop = r1.futility_gate({"A": mk(9), "B": mk(8), "C": [{"validated": []}]}, inc)
        self.assertFalse(stop["proceed"])                               # +1 seed = 6.25 pp < 10 pp
        go = r1.futility_gate({"A": mk(9), "B": mk(10), "C": mk(7)}, inc)
        self.assertTrue(go["proceed"])                                  # +2 seeds = 12.5 pp
        self.assertTrue(go["arms"]["B"]["meets_threshold"] and not go["arms"]["A"]["meets_threshold"])
        self.assertEqual(go["arms"]["B"]["gain_percentage_points"], 12.5)

    def test_engineering_verdict(self):
        mk = lambda n, speed=0.5, drag=0: [{"walking": i < n, "speed_upright": speed,  # noqa: E731
                                            "violations": ["body_dragging"] if i < drag else []} for i in range(30)]
        self.assertTrue(r1.engineering_verdict(mk(27))["meets_engineering_criterion"])
        self.assertFalse(r1.engineering_verdict(mk(26))["meets_engineering_criterion"])
        self.assertFalse(r1.engineering_verdict(mk(30, speed=0.2))["meets_engineering_criterion"])
        self.assertFalse(r1.engineering_verdict(mk(30, drag=1))["meets_engineering_criterion"])
        self.assertFalse(r1.engineering_verdict(mk(30)[:29])["meets_engineering_criterion"])

    def test_knee_test_is_deterministic_and_handles_degenerate(self):
        seeds = list(r1.FINAL_SEEDS)
        walking = [i % 3 != 0 for i in range(30)]
        a, b = r1.knee_hypothesis_test(seeds, walking, n_perm=500), r1.knee_hypothesis_test(seeds, walking, n_perm=500)
        self.assertEqual(a, b)
        self.assertIsNone(r1.knee_hypothesis_test(seeds, [True] * 30)["p_two_sided"])


class ProtocolTests(unittest.TestCase):
    def test_protocol_is_serialisable_and_within_budget(self):
        p = r1.build_protocol()
        json.dumps(p, allow_nan=False)
        planned = p["budget"]["planned"]
        self.assertEqual(planned["training"], 7200)
        self.assertLessEqual(sum(planned.values()), r1.BUDGET_CAP)
        self.assertTrue(any("BOTH the number of training seeds" in n for n in p["interpretation_notes"]))
        self.assertEqual(p["final_evaluation"]["engineering_criterion"]["min_walking_seeds"], 27)
        self.assertEqual(p["resources"]["max_workers"], 4)


class StatsTests(unittest.TestCase):
    def test_exact_mcnemar(self):
        self.assertAlmostEqual(r1_stats.exact_mcnemar(7, 1), 18 / 256)
        self.assertEqual(r1_stats.exact_mcnemar(0, 0), 1.0)
        self.assertEqual(r1_stats.exact_mcnemar(5, 5), 1.0)
        self.assertAlmostEqual(r1_stats.exact_mcnemar(0, 8), 2 / 256)

    def test_intervals_match_reference_values(self):
        lo, hi = r1_stats.clopper_pearson(27, 30)
        self.assertAlmostEqual(lo, 0.7347, places=3)
        self.assertAlmostEqual(hi, 0.9789, places=3)
        lo, hi = r1_stats.wilson(27, 30)
        self.assertAlmostEqual(lo, 0.7438, places=3)
        self.assertAlmostEqual(hi, 0.9654, places=3)
        self.assertEqual(r1_stats.clopper_pearson(0, 10)[0], 0.0)
        self.assertEqual(r1_stats.clopper_pearson(10, 10)[1], 1.0)

    def test_paired_comparison(self):
        new = [True] * 24 + [False] * 6
        old = [True] * 15 + [False] * 15
        r = r1_stats.paired_comparison(new, old)
        self.assertEqual(r["table"], {"both": 15, "new_only": 9, "old_only": 0, "neither": 6, "n": 30})
        self.assertAlmostEqual(r["mcnemar_exact_two_sided_p"], 2 / 512)
        self.assertTrue(r["superior"])
        d = r["paired_difference"]
        self.assertAlmostEqual(d["estimate"], 0.3)
        self.assertTrue(0 < d["newcombe_95ci"][0] < 0.3 < d["newcombe_95ci"][1] < 0.6)
        self.assertEqual(r["conditional_odds_ratio"]["estimate"], None)   # old_only == 0
        same = r1_stats.paired_comparison(old, old)
        self.assertFalse(same["superior"])
        self.assertEqual(same["mcnemar_exact_two_sided_p"], 1.0)
        worse = r1_stats.paired_comparison(old, new)
        self.assertFalse(worse["superior"])                              # significant but negative difference
        self.assertLess(worse["mcnemar_exact_two_sided_p"], 0.05)
        with self.assertRaises(ValueError):
            r1_stats.paired_comparison([True], [True, False])

    def test_newcombe_symmetry(self):
        diff, lo, hi = r1_stats.newcombe_paired_diff(10, 4, 4, 12)
        self.assertEqual(diff, 0.0)
        self.assertAlmostEqual(lo, -hi, places=9)
        self.assertTrue(math.isfinite(lo) and lo < 0 < hi)


if __name__ == "__main__":
    unittest.main()
