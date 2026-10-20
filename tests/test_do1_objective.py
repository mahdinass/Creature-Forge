"""No-physics tests of DO-1 (scripts/do1_objective.py, scripts/do1_repair_ablation.py).

Fakes and monkeypatching only: every rollout entry point is patched to fail unless a test replaces it with a fake. The real
`walk_opt.cma_search` runs with a fake evaluator (no MuJoCo)."""
import argparse
import contextlib
import copy
import io
import json
import os
import pickle
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import ta1_tool_access as ta1                         # noqa: E402
import do1_objective as do1                           # noqa: E402
import do1_repair_ablation as abl                     # noqa: E402
from creature_forge import creature_walk as cw        # noqa: E402
from creature_forge import hidden_plant as hp         # noqa: E402
from creature_forge import locomotion as loc          # noqa: E402
from creature_forge import walk_opt as wo             # noqa: E402
from creature_forge.hdb_evidence import EvidenceWorkbench  # noqa: E402
from creature_forge.hdb_workbench import HDBWorkbench, min_budget  # noqa: E402

RECORDS = os.path.join(os.path.dirname(ROOT), "Creature-Forge", "artifacts", "vm", "ds1", "eval")
CRIT = loc.DEFAULT_CRITERIA


def _no_physics(*a, **k):
    raise AssertionError("physics entry point called in a no-physics test")


def _guard():
    stack = contextlib.ExitStack()
    for target in (hp, "plant_rollout"), (hp, "walk_job"), (hp, "verify"), (hp, "observe"):
        stack.enter_context(mock.patch.object(*target, _no_physics))
    return stack


def _stored(fname, line):
    return ta1.load_stored(RECORDS, fname, line)


def _l4_design0():
    d = _stored("eval_A1e6_s3.jsonl", 4)["designs"][0]
    return dict(d["body"]), list(d["vector"])


def _view():
    body, vec = _l4_design0()
    return {"robot_id": "test", "robot": {"body": body, "vector": vec},
            "seeds": {"train": list(range(1, 9)), "obs": list(range(11, 19)), "robust": list(range(21, 37)),
                      "twin": list(range(41, 57))}}


def _metrics(**over):
    m = {"walking": True, "fell": False, "label": "walking", "forward_disp_upright": 3.1, "valid_steps": 12, "fall_time": None,
         "raw_touchdown_rate": 1.5, "flight_frac": 0.02, "slip_frac": 0.05, "saturation_frac": 0.01, "body_contact_frac": 0.0,
         "time_upright": 10.0, "duration": 10.0, "speed_effective": 0.31, "valid_step_rate": 1.2, "effort": 0.3,
         "max_abs_pitch": 0.3, "speed_upright": 0.31, "alternation": 1.0}
    m.update(over)
    return m


def _row(walking=True, fell=False, disp=3.0, fit=4.0, seed=1, fall_time=None, valid_steps=10, **gates):
    g = {"speed_upright": 0.31, "valid_step_rate": 1.2, "alternation": 1.0, "raw_touchdown_rate": 1.5, "flight_frac": 0.02,
         "slip_frac": 0.05, "body_contact_frac": 0.0, "saturation_frac": 0.01, "max_abs_pitch": 0.3}
    g.update(gates)
    return {"ok": True, "seed": seed, "walking": walking, "fell": fell, "label": "walking" if walking else "fall",
            "fitness": fit, "forward_disp_upright": disp, "valid_steps": valid_steps, "fall_time": fall_time,
            "gates": g, "criteria": {attr: float(getattr(CRIT, attr)) for _, _, attr, _ in do1.GATES}}


class FakeBody:
    def __init__(self, d):
        self.d = dict(d)

    def as_dict(self):
        return dict(self.d)


def fake_job(job):
    """Deterministic fake rollout row from the candidate vector and seed (no physics)."""
    v = np.asarray(job["vector"], dtype=float)
    q = float(np.tanh(v[:3].sum()))
    walking = (q + 0.1 * (job["seed"] % 3)) > -0.5
    return _row(walking=bool(walking), fell=not walking, disp=2.0 + q + 0.01 * job["seed"], fit=3.0 + q, seed=job["seed"],
                fall_time=None if walking else 4.0, max_abs_pitch=0.3 + 0.2 * abs(q))


class WalkJobEquivalence(unittest.TestCase):
    def _run_both(self, job):
        m = _metrics()
        with mock.patch.object(hp, "plant_rollout", lambda *a, **k: {"trace": True}), \
                mock.patch.object(loc, "compute_metrics", lambda tr, crit: dict(m)), \
                mock.patch.object(cw, "_body", FakeBody), mock.patch.object(cw, "creature_criteria", lambda b: CRIT), \
                mock.patch("creature_forge.arena._body_with_friction", lambda d, f: (dict(d, mu=f),)):
            return hp.walk_job(dict(job)), do1.do1_walk_job(dict(job))

    def test_shared_fields_identical_and_gates_added(self):
        for ff in (None, 0.95):
            job = {"vector": [0.1] * 17, "body": {"a": 1}, "seed": 7, "duration": 10.0, "perturb": 0.2, "friction_factor": ff,
                   "plant": {}}
            a, b = self._run_both(job)
            self.assertTrue(a["ok"] and b["ok"])
            for k in a:
                if k != "wall_s":
                    self.assertEqual(a[k], b[k], k)
            self.assertEqual(set(b) - set(a), {"gates", "criteria"})
            self.assertEqual(b["gates"]["slip_frac"], 0.05)
            self.assertEqual(b["criteria"]["min_speed"], CRIT.min_speed)

    def test_error_rows(self):
        with mock.patch.object(hp, "plant_rollout", mock.Mock(side_effect=RuntimeError("boom"))), \
                mock.patch.object(cw, "_body", FakeBody):
            job = {"vector": [0.0] * 17, "body": {}, "seed": 1, "duration": 10.0, "plant": {}}
            a, b = hp.walk_job(dict(job)), do1.do1_walk_job(dict(job))
        self.assertEqual((a["ok"], a["error"]), (b["ok"], b["error"]))
        self.assertFalse(b["ok"])

    def test_job_is_picklable_by_reference(self):
        # round-trips our own function object in-process (what the spawn pool does); no untrusted data is loaded
        self.assertIs(pickle.loads(pickle.dumps(do1.do1_walk_job)), do1.do1_walk_job)


class ObjectiveComponents(unittest.TestCase):
    def test_gate_slacks(self):
        sl = do1.gate_slacks(_row())
        self.assertTrue(all(v > 0 for v in sl.values()), sl)
        self.assertAlmostEqual(sl["slip"], (0.15 - 0.05) / 0.15)
        self.assertAlmostEqual(sl["alternation"], 1.0)
        self.assertAlmostEqual(sl["pitch"], (0.8 - 0.3) / 0.8)
        bad = do1.gate_slacks(_row(slip_frac=0.30, alternation=0.85, max_abs_pitch=5.0))
        self.assertAlmostEqual(bad["slip"], -1.0)
        self.assertAlmostEqual(bad["alternation"], -0.5)
        self.assertEqual(bad["pitch"], -1.0)                                   # clipped

    def test_seed_margin(self):
        self.assertEqual(do1.seed_margin(_row(walking=False, fell=True)), (-1.0, "fall"))
        self.assertEqual(do1.seed_margin({"ok": False, "error": "x"}), (-1.0, "error"))
        m, gate = do1.seed_margin(_row(slip_frac=0.14))
        self.assertEqual(gate, "slip")
        self.assertAlmostEqual(m, 0.01 / 0.15)

    def test_paired_displacement_uses_walk_score_rule(self):
        rows = [_row(disp=4.0), _row(disp=4.0), _row(walking=False, fell=True, fall_time=0.5, disp=3.0),
                _row(valid_steps=0, disp=5.0)]
        c = do1.objective(rows, [2.0, 2.0, 2.0, 2.0])
        self.assertEqual([p["score"] for p in c["per_seed"]], [4.0, 4.0, 0.0, 0.0])
        self.assertEqual([p["diff_m"] for p in c["per_seed"]], [2.0, 2.0, -2.0, -2.0])
        self.assertEqual(c["median_diff_m"], 0.0)
        self.assertAlmostEqual(c["shortfall"], 1.0)
        self.assertEqual((c["wins"], c["losses"]), (2, 2))

    def test_lexicographic_precedence(self):
        base = [2.0] * 4
        feasible = do1.objective([_row(disp=3.0)] * 4, base)                    # 4/4 walking, +1.0 m
        self.assertTrue(feasible["feasible"])
        tight = do1.objective([_row(disp=3.0, slip_frac=0.14)] * 4, base)       # same, smaller margin
        short = do1.objective([_row(disp=2.5)] * 4, base)                       # 4/4 walking, +0.5 m < TAU_D
        far_short = do1.objective([_row(disp=1.0)] * 4, base)
        three = do1.objective([_row(disp=9.0)] * 3 + [_row(walking=False, fell=True, fall_time=5.0, disp=9.0)], base)
        self.assertFalse(short["feasible"])
        self.assertGreater(feasible["J"], tight["J"])
        self.assertGreater(tight["J"], short["J"])
        self.assertGreater(short["J"], far_short["J"])
        self.assertGreater(far_short["J"], three["J"])                           # walking count first

    def test_walking_count_dominates_random_candidates(self):
        rng = np.random.default_rng(3)
        cands = []
        for _ in range(400):
            rows = []
            for s in range(4):
                w = bool(rng.random() < 0.6)
                rows.append(_row(walking=w, fell=not w and rng.random() < 0.5, disp=float(rng.uniform(-1, 12)),
                                 fit=float(rng.uniform(-10, 7)), fall_time=float(rng.uniform(0, 10)),
                                 slip_frac=float(rng.uniform(0, 0.3)), max_abs_pitch=float(rng.uniform(0, 1.2))))
            cands.append(do1.objective(rows, list(rng.uniform(0, 8, 4))))
        for a in cands:
            for b in cands:
                if a["walking_count"] > b["walking_count"]:
                    self.assertGreater(a["J"], b["J"])
                if a["walking_count"] == b["walking_count"] and a["feasible"] and not b["feasible"]:
                    self.assertGreater(a["J"], b["J"])

    def test_objective_needs_paired_baseline(self):
        with self.assertRaises(ValueError):
            do1.objective([_row()] * 4, [1.0] * 3)


class EvalFn(unittest.TestCase):
    def test_same_jobs_as_frozen_eval_fn_and_scalar_is_J(self):
        seeds = [1, 2, 3, 4]
        cands = [({"x": 1}, [0.1] * 17), ({"x": 2}, [-0.4] * 17)]
        frozen_jobs, do1_jobs = [], []

        def rec_frozen(job):
            frozen_jobs.append(copy.deepcopy(job))
            return fake_job(job)

        def rec_do1(job):
            do1_jobs.append(copy.deepcopy(job))
            return fake_job(job)
        with _guard(), mock.patch.object(hp, "walk_job", rec_frozen), mock.patch.object(do1, "do1_walk_job", rec_do1):
            f_recs = hp.make_eval_fn({}, seeds)(cands)
            log = []
            d_recs = do1.make_do1_eval_fn({}, seeds, [2.0] * 4, log=log)(cands)
        self.assertEqual(frozen_jobs, do1_jobs)
        for f, d, entry in zip(f_recs, d_recs, log):
            self.assertEqual((f["walking_count"], f["survival_count"]), (d["walking_count"], d["survival_count"]))
            self.assertEqual(d["mean_fitness"], entry["J"])
            self.assertAlmostEqual(f["mean_fitness"], entry["mean_fitness_v1"])
        self.assertEqual([e["vector"] for e in log], [v for _, v in cands])


def _benches(cls_a=HDBWorkbench, cls_b=do1.Do1Workbench, noise=1751409197):
    return (cls_a(_view(), {}, total_budget=700, noise_seed=noise), cls_b(_view(), {}, total_budget=700, noise_seed=noise))


def _fake_walk_seeds(plant, body, vector, seeds, **kw):
    return [_row(disp=2.0 + 0.1 * i, seed=s, walking=i != 1, fell=False) for i, s in enumerate(seeds)]


class Do1WorkbenchRepair(unittest.TestCase):
    def test_overrides_only_repair(self):
        public = {k for k, v in do1.Do1Workbench.__dict__.items() if not k.startswith("_") and callable(v)}
        self.assertEqual(public, {"repair", "do1_record"})
        self.assertTrue(issubclass(do1.Do1Workbench, EvidenceWorkbench))

    def test_prehook_bench_state_identical(self):
        e, d = _benches(EvidenceWorkbench)
        self.assertEqual(ta1.fingerprint(ta1._bench_state(e)), ta1.fingerprint(ta1._bench_state(d)))

    def test_refusals_identical_to_frozen(self):
        cases = [("nope", 100, {}), ("leg_length", 100, {"n_train": 5}), ("leg_length", 1, {}),
                 ("leg_length", 10_000, {}), ("leg_length", -1, {})]
        with _guard():
            for tool, budget, kw in cases:
                h, d = _benches()
                self.assertEqual(h.repair(tool, budget, **kw), d.repair(tool, budget, **kw), (tool, budget, kw))
                self.assertEqual(h.ledger()["lines"], d.ledger()["lines"])

    def test_baseline_shortfall_refusal_charges_nothing(self):
        need = min_budget("leg_length", 4)
        _, d = _benches()
        with _guard():
            out = d.repair("leg_length", need, init={"index": 0})
        self.assertFalse(out["ok"])
        self.assertIn("DO-1 train baseline", out["refused"])
        self.assertEqual(d.budget.used, 0)
        self.assertIsNone(d._do1_base)

    def test_cma_call_matches_frozen_except_budget_and_eval_fn(self):
        frozen_calls, do1_calls = [], []

        def fake_plant_cma(body, vec, space, *, plant, budget, train_seeds, noise_seed, pool, variation):
            frozen_calls.append({"body": body, "vec": vec, "space": space.to_dict(), "budget": budget,
                                 "seeds": list(train_seeds), "noise": noise_seed, "variation": variation})
            return {"rollouts_used": budget - 2, "best": {"body": dict(body), "vector": list(vec), "walking_count": 4,
                                                          "survival_count": 4, "mean_fitness": 1.0, "found_at_rollouts": 4}}

        def fake_cma(body, vec, space, *, budget, train_seeds, noise_seed, pool, variation, duration, eval_fn):
            do1_calls.append({"body": body, "vec": vec, "space": space.to_dict(), "budget": budget,
                              "seeds": list(train_seeds), "noise": noise_seed, "variation": variation})
            self.assertEqual(duration, 10.0)
            rec = eval_fn([(dict(body), list(vec))])[0]
            return {"rollouts_used": budget - 2, "best": {"body": dict(body), "vector": [float(x) for x in vec],
                                                          "walking_count": rec["walking_count"],
                                                          "survival_count": rec["survival_count"],
                                                          "mean_fitness": rec["mean_fitness"], "found_at_rollouts": 4}}
        h, d = _benches()
        with _guard(), mock.patch.object(hp, "plant_cma", fake_plant_cma), mock.patch.object(wo, "cma_search", fake_cma), \
                mock.patch.object(hp, "walk_seeds", _fake_walk_seeds), mock.patch.object(do1, "do1_walk_job", fake_job):
            for tool, budget in (("leg_length", 388), ("posture", 236)):
                rh = h.repair(tool, budget, n_train=4, init={"index": 0})
                rd = d.repair(tool, budget, n_train=4, init={"index": 0})
                self.assertTrue(rh["ok"] and rd["ok"])
        self.assertEqual(len(frozen_calls), 2)
        for k, (f, g) in enumerate(zip(frozen_calls, do1_calls)):
            for key in ("body", "vec", "space", "seeds", "noise", "variation"):
                self.assertEqual(f[key], g[key], (k, key))
            self.assertEqual(g["budget"], f["budget"] - (4 if k == 0 else 0))
        self.assertEqual(frozen_calls[0]["seeds"], [1, 2, 3, 4])
        self.assertEqual(frozen_calls[1]["noise"], 1751409197 + 7919)
        self.assertEqual(h.budget.used, d.budget.used)                          # matched plant spend
        items = [(ln["item"], ln["n"]) for ln in d.ledger()["lines"]]
        self.assertEqual([x for x in items if x[0] == "do1_train_baseline"], [("do1_train_baseline", 4)])
        rec = d.do1_record()
        self.assertEqual([r["train_baseline_rollouts"] for r in rec["repairs"]], [4, 0])
        self.assertEqual(rec["train_baseline"]["scores"], [2.0, 2.1, 2.2, 2.3])
        self.assertTrue(all(r["selected_log_index"] == 0 for r in rec["repairs"]))
        self.assertEqual(d.designs[-1]["objective"], do1.VERSION)

    def test_real_cma_search_with_fake_rollouts(self):
        _, d = _benches()
        with _guard(), mock.patch.object(hp, "walk_seeds", _fake_walk_seeds), mock.patch.object(do1, "do1_walk_job", fake_job):
            out = d.repair("leg_length", 200, n_train=4, init={"index": 0})
        self.assertTrue(out["ok"], out)
        rep = d.do1_record()["repairs"][0]
        self.assertIsNotNone(rep["selected_log_index"])
        self.assertEqual(rep["selected"]["J"], out["best"]["train_fitness"])
        self.assertEqual(rep["n_candidates"] * 4, rep["rollouts_used"])
        self.assertEqual(d.budget.used, 4 + rep["rollouts_used"])
        self.assertLessEqual(d.budget.used, 200)
        # the reported best is the lexicographic best (walking, survival, J) of every logged candidate
        key = max((c["walking_count"], c["survival_count"], c["J"]) for c in rep["candidates"])
        sel = rep["candidates"][rep["selected_log_index"]]
        self.assertEqual((sel["walking_count"], sel["survival_count"], sel["J"]), key)
        self.assertTrue(all("per_seed" in c and len(c["per_seed"]) == 4 for c in rep["candidates"]))

    def test_cma_value_error_refunds_cma_budget_keeps_baseline(self):
        _, d = _benches()
        with _guard(), mock.patch.object(hp, "walk_seeds", _fake_walk_seeds), \
                mock.patch.object(wo, "cma_search", mock.Mock(side_effect=ValueError("out of bounds"))):
            out = d.repair("leg_length", 388, init={"index": 0})
        self.assertFalse(out["ok"])
        self.assertEqual(d.budget.used, 4)
        self.assertEqual(d.do1_repairs[0]["refused"], "out of bounds")

    def test_other_train_seeds_refused(self):
        _, d = _benches()
        d._do1_base = {"seeds": [9, 9, 9, 9], "scores": [0] * 4, "pass": [False] * 4, "errors": []}
        with _guard():
            out = d.repair("leg_length", 388, init={"index": 0})
        self.assertFalse(out["ok"])
        self.assertEqual(d.budget.used, 0)


class SelectedIndex(unittest.TestCase):
    def test_matches_only_the_logged_candidate(self):
        log = [{"vector": [0.0], "J": 1.0}, {"vector": [1.0], "J": 2.0}]
        self.assertEqual(do1.selected_log_index({"found_at_rollouts": 8, "vector": [1.0], "mean_fitness": 2.0}, log, 4), 1)
        self.assertIsNone(do1.selected_log_index({"found_at_rollouts": 8, "vector": [0.5], "mean_fitness": 2.0}, log, 4))
        self.assertIsNone(do1.selected_log_index({"found_at_rollouts": 12, "vector": [1.0], "mean_fitness": 2.0}, log, 4))


class RunEpisodeHook(unittest.TestCase):
    def test_ta1_default_bench_unchanged(self):
        import inspect
        sig = inspect.signature(ta1.run_episode)
        self.assertIsNone(sig.parameters["bench_cls"].default)
        self.assertIn("(bench_cls or EvidenceWorkbench)(view", inspect.getsource(ta1.run_episode))

    def test_run_do1_episode_builds_the_arm_bench_with_control_plan(self):
        seen = {}

        def fake_run(inst, arm, r, inputs, pool=None, bench_cls=None):
            seen["arm"] = arm
            bench_cls(_view(), {}, total_budget=700, twin_budget=2800, pool=pool, noise_seed=5)
            return {"harness": {}}
        for arm, cls in (("frozen", "EvidenceWorkbench"), ("do1", "Do1Workbench")):
            with _guard():
                rec = abl.run_do1_episode({}, arm, 0, {}, run_fn=fake_run)
            self.assertEqual(seen["arm"], "control")
            self.assertEqual(rec["harness"]["do1"]["bench_class"], cls)
            self.assertEqual(rec["harness"]["do1"]["arm"], arm)
        self.assertEqual(rec["harness"]["do1"]["version"], do1.VERSION)
        with self.assertRaises(ValueError):
            abl.bench_factory("treatment", {})


def _ledger(lines, used=700):
    return {"used": used, "lines": lines, "twin": {"used": 0, "lines": []}}


def _arm_rec(arm, lines, repairs=None, used=700, cls=None, version=None):
    return {"engine": {"ledger": _ledger(lines, used)},
            "harness": {"do1": {"arm": arm, "bench_class": cls or ("Do1Workbench" if arm == "do1" else "EvidenceWorkbench"),
                                "version": version if version is not None else (do1.VERSION if arm == "do1" else None),
                                "repairs": repairs or []}}}


class ArmChecks(unittest.TestCase):
    BASE = {"item": "do1_train_baseline", "n": 4, "detail": {"objective": do1.VERSION}}

    def test_valid(self):
        self.assertEqual(abl.arm_checks(_arm_rec("do1", [self.BASE], [{"selected_log_index": 3}])), [])
        self.assertEqual(abl.arm_checks(_arm_rec("frozen", [{"item": "repair", "n": 300, "detail": {}}])), [])

    def test_invalid(self):
        self.assertTrue(abl.arm_checks(_arm_rec("frozen", [self.BASE])))
        self.assertTrue(abl.arm_checks(_arm_rec("do1", [self.BASE, self.BASE])))
        self.assertTrue(abl.arm_checks(_arm_rec("do1", [self.BASE], [{"selected_log_index": None}])))
        self.assertTrue(abl.arm_checks(_arm_rec("do1", [self.BASE], used=701)))
        self.assertTrue(abl.arm_checks(_arm_rec("do1", [self.BASE], cls="EvidenceWorkbench")))
        self.assertEqual(abl.arm_checks(_arm_rec("do1", [self.BASE], [{"refused": "x", "selected_log_index": None}])), [])


class Phases(unittest.TestCase):
    def test_run_lists(self):
        l4 = abl.PHASES["DO1-L4"]
        self.assertEqual(len(l4), 10)
        self.assertEqual(l4[:2], [("L4", "frozen", 0), ("L4", "do1", 0)])
        self.assertEqual(sorted({r for _, _, r in l4}), [0, 1, 2, 3, 4])
        for r in range(5):
            self.assertEqual(sorted(a for c, a, rr in l4 if rr == r), ["do1", "frozen"])
        self.assertEqual(abl.PHASES["DO1-L1"], [("L1", "frozen", 0), ("L1", "do1", 0)])
        self.assertEqual(ta1.phase_cap(l4)["total"], 36040)
        self.assertEqual(ta1.phase_cap(abl.PHASES["DO1-L1"])["total"], 7208)
        self.assertNotIn("DO1-L4", ta1.PHASES)                                  # TA-1 phase lists untouched

    def test_preregistration_fields(self):
        for k in ("hypothesis", "primary_outcome", "primary_test", "success", "falsified", "null_wording"):
            self.assertTrue(abl.PREREGISTRATION[k])
        self.assertTrue(abl.PREREGISTRATION["no_outcome_based_stopping"])

    def test_dry_runs_simulate_nothing(self):
        with _guard(), mock.patch.object(ta1, "build_instance", _no_physics), \
                mock.patch.object(abl, "run_do1_episode", _no_physics), contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(abl.main([]), 0)
            self.assertEqual(abl.main(["--phase", "DO1-L4", "--records-root", RECORDS]), 0)
        self.assertIn("preflight", buf.getvalue())
        self.assertIn("Dry run", buf.getvalue())

    def test_execute_refuses_without_approval(self):
        tmp = tempfile.mkdtemp()
        try:
            out = os.path.join(tmp, "x.jsonl")
            with _guard(), mock.patch.object(abl, "_execute", _no_physics), contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = abl.main(["--phase", "DO1-L1", "--execute", "--max-rollouts", "1", "--out", out,
                               "--records-root", RECORDS])
            self.assertEqual(rc, 2)
            self.assertIn("--approved-by is required", buf.getvalue())
            self.assertIn("below the phase cap", buf.getvalue())
            self.assertFalse(os.path.exists(out))
        finally:
            shutil.rmtree(tmp)


class ExecuteGates(unittest.TestCase):
    """_execute with fake episodes built from the stored L1 record (no physics)."""

    def _fake_run(self, fp_do1="f" * 16):
        stored = _stored("eval_A1e6_s1.jsonl", 1)

        def run(inst, arm, r, inputs, pool=None):
            rec = copy.deepcopy(stored)
            rec["verification"] = {"summary": copy.deepcopy(stored["verification"]), "full": {}}
            lines = rec["engine"]["ledger"]["lines"]
            if arm == "do1":
                lines.append({"item": "do1_train_baseline", "n": 4, "detail": {"objective": do1.VERSION}, "cumulative": 0})
            rec["engine"]["ledger"]["used"] = min(rec["engine"]["ledger"]["used"], 700)
            rec["harness"] = {"verification_complete": True, "replicate": r, "noise_seed": 1,
                              "hook_calls": [{"prehook_fingerprint": fp_do1 if arm == "do1" else "f" * 16,
                                              "prehook_component_fingerprints": {}, "prehook_n_plant_lines": 1,
                                              "prehook_n_twin_lines": 1, "prehook_n_events": 1, "prehook_n_history": 1}],
                              "resources": {"total_rollout_equivalents": 10.0}, "rescreen": {"classification": "none"},
                              "do1": {"arm": arm, "bench_class": "Do1Workbench" if arm == "do1" else "EvidenceWorkbench",
                                      "version": do1.VERSION if arm == "do1" else None, "repairs": []}}
            return rec
        return run

    def _execute(self, run):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        a = argparse.Namespace(out=os.path.join(tmp, "o.jsonl"), phase="DO1-L1", approved_by="test", max_rollouts=10 ** 6,
                               max_wall_s=0.0, harness_commit="0" * 40, records_root=RECORDS, workers=0)
        inputs = ta1.config_inputs(ta1.ROOT, os.path.join(ta1.ROOT, "artifacts", "hdb"))
        with _guard(), contextlib.redirect_stdout(io.StringIO()):
            rc = abl._execute(a, abl.planned_runs("DO1-L1"), inputs, ta1.phase_cap(abl.planned_runs("DO1-L1")),
                              build_fn=lambda iid, inputs, pool=None: {"instance_id": iid}, run_fn=run,
                              pool_cm=contextlib.nullcontext(None))
        with open(a.out, encoding="utf-8") as fh:
            recs = [json.loads(x) for x in fh]
        with open(ta1.manifest_path(a.out), encoding="utf-8") as fh:
            man = json.load(fh)
        return rc, recs, man

    def test_valid_pair_passes(self):
        rc, recs, man = self._execute(self._fake_run())
        self.assertEqual(rc, 0)
        self.assertEqual([r["harness"]["do1"]["arm"] for r in recs], ["frozen", "do1"])
        self.assertTrue(recs[0]["harness"]["reproduction"]["exact"])
        self.assertTrue(recs[1]["harness"]["paired_prehook"]["equal"])
        self.assertEqual(man["objective"], do1.OBJECTIVE_SPEC)
        self.assertEqual(man["runner_version"], abl.RUNNER_VERSION)

    def test_prehook_mismatch_pauses(self):
        rc, recs, _ = self._execute(self._fake_run(fp_do1="0" * 16))
        self.assertEqual(rc, ta1.PAUSE_EXIT)
        self.assertEqual(len(recs), 2)                                           # persisted before pausing
        self.assertFalse(recs[1]["harness"]["paired_prehook"]["equal"])


if __name__ == "__main__":
    unittest.main()
