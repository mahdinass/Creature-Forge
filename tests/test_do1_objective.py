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


VEC = [0.5] * 17


def _repair(k=0, design_index=1, tool="leg_length", vec=None, refused=None, sel_override=None):
    if refused is not None:
        return {"tool": tool, "parent": 0, "refused": refused, "train_baseline_rollouts": 4}
    cand = {"vector": list(vec or VEC), "J": 40100.0, "walking_count": 4, "survival_count": 4, "margin": 0.3}
    sel = {key: v for key, v in cand.items() if key != "vector"}
    sel.update(sel_override or {})
    return {"repair_index": 0, "tool": tool, "design_index": design_index, "selected_log_index": k, "selected": sel,
            "candidates": [cand]}


def _arm_rec(arm, lines, repairs=None, used=700, cls=None, version=None, designs=None):
    return {"engine": {"ledger": _ledger(lines, used)},
            "designs": designs if designs is not None else [{"index": 0, "source": "initial", "vector": [0.0] * 17},
                                                            {"index": 1, "source": "repair:leg_length", "vector": list(VEC)}],
            "harness": {"do1": {"arm": arm, "bench_class": cls or ("Do1Workbench" if arm == "do1" else "EvidenceWorkbench"),
                                "version": version if version is not None else (do1.VERSION if arm == "do1" else None),
                                "repairs": repairs if repairs is not None else []}}}


class ArmChecks(unittest.TestCase):
    BASE = {"item": "do1_train_baseline", "n": 4, "detail": {"objective": do1.VERSION}}

    def test_valid(self):
        self.assertEqual(abl.arm_checks(_arm_rec("do1", [self.BASE], [_repair()])), [])
        self.assertEqual(abl.arm_checks(_arm_rec("do1", [self.BASE], [_repair(), _repair(refused="out of bounds")])), [])
        self.assertEqual(abl.arm_checks(_arm_rec("frozen", [{"item": "repair", "n": 300, "detail": {}}])), [])

    def test_missing_or_wrong_baseline(self):
        for lines in ([], [self.BASE, self.BASE], [dict(self.BASE, n=8)], [dict(self.BASE, detail={})]):
            probs = abl.arm_checks(_arm_rec("do1", lines, [_repair()]))
            self.assertTrue(any("train baseline" in p for p in probs), lines)

    def test_no_completed_repair_is_not_exposed(self):
        for repairs in ([], [_repair(refused="out of bounds")], [_repair(refused="a"), _repair(refused="b")]):
            probs = abl.arm_checks(_arm_rec("do1", [self.BASE], repairs))
            self.assertTrue(any(p.startswith("NOT_EXPOSED") for p in probs), repairs)
        # missing baseline AND no repair: both reported
        probs = abl.arm_checks(_arm_rec("do1", [], []))
        self.assertTrue(any(p.startswith("NOT_EXPOSED") for p in probs))
        self.assertTrue(any("train baseline" in p for p in probs))

    def test_selected_candidate_must_match_logged_evidence(self):
        bad = [_repair(k=None), _repair(k=1), _repair(k=True), _repair(sel_override={"J": 1.0}),
               _repair(vec=[0.4] * 17), _repair(design_index=5), _repair(tool="posture")]
        for rep in bad:
            self.assertTrue(abl.arm_checks(_arm_rec("do1", [self.BASE], [rep])), rep)
        no_sel = _repair()
        no_sel["selected"] = None
        self.assertTrue(abl.arm_checks(_arm_rec("do1", [self.BASE], [no_sel])))

    def test_other_invalid(self):
        self.assertTrue(abl.arm_checks(_arm_rec("frozen", [self.BASE])))
        self.assertTrue(abl.arm_checks(_arm_rec("do1", [self.BASE], [_repair()], used=701)))
        self.assertTrue(abl.arm_checks(_arm_rec("do1", [self.BASE], [_repair()], cls="EvidenceWorkbench")))

    def test_real_do1_bench_record_passes_and_tampering_fails(self):
        _, d = _benches()
        with _guard(), mock.patch.object(hp, "walk_seeds", _fake_walk_seeds), mock.patch.object(do1, "do1_walk_job", fake_job):
            self.assertTrue(d.repair("leg_length", 200, n_train=4, init={"index": 0})["ok"])
            self.assertTrue(d.repair("posture", 150, n_train=4, init={"index": 1})["ok"])
        rec = ta1.jsonable({"engine": {"ledger": d.ledger()},
                            "designs": [{k: x[k] for k in ("index", "source", "body", "vector")} for x in d.designs],
                            "harness": {"do1": {"arm": "do1", "bench_class": "Do1Workbench", **d.do1_record()}}})
        self.assertEqual(abl.arm_checks(rec), [])
        t = copy.deepcopy(rec)
        k = t["harness"]["do1"]["repairs"][1]["selected_log_index"]
        t["harness"]["do1"]["repairs"][1]["candidates"][k]["vector"][0] += 1e-9
        self.assertTrue(abl.arm_checks(t))


class Phases(unittest.TestCase):
    def test_run_lists(self):
        l4 = abl.PHASES["DO1-L4"]
        self.assertEqual(len(l4), 10)
        self.assertEqual(l4[:2], [("L4", "frozen", 0), ("L4", "do1", 0)])
        self.assertEqual(sorted({r for _, _, r in l4}), [0, 1, 2, 3, 4])
        for r in range(5):
            self.assertEqual(sorted(a for c, a, rr in l4 if rr == r), ["do1", "frozen"])
        self.assertEqual(abl.PHASES["DO1-L1"], [("L1", "frozen", 0), ("L1", "do1", 0)])
        self.assertEqual(abl.PHASES["DO1-L4-r0"], [("L4", "frozen", 0), ("L4", "do1", 0)])
        self.assertEqual(ta1.phase_cap(abl.PHASES["DO1-L4-r0"])["total"], 7208)
        self.assertEqual(abl.PHASES["DO1-L4-r0"], l4[:2])                       # the pilot is DO1-L4's first pair
        self.assertEqual(ta1.phase_cap(l4)["total"], 36040)
        self.assertEqual(ta1.phase_cap(abl.PHASES["DO1-L1"])["total"], 7208)
        self.assertNotIn("DO1-L4", ta1.PHASES)                                  # TA-1 phase lists untouched

    def test_preregistration_fields(self):
        pre = abl.PREREGISTRATION
        for k in ("hypothesis", "unit", "primary_outcome", "primary_test", "success", "suggestive", "no_improvement_observed",
                  "null_wording", "pilot_DO1-L4-r0"):
            self.assertTrue(pre[k])
        self.assertTrue(pre["no_outcome_based_stopping"])
        self.assertIn("McNemar", pre["primary_test"])
        self.assertNotIn("Fisher", json.dumps(pre))
        self.assertNotIn("falsified", pre)
        self.assertIn("NOT a falsification", pre["no_improvement_observed"])

    def test_paired_sign_test_thresholds_quoted(self):
        from math import comb

        def mcnemar_one_sided(for_do1, against):
            n = for_do1 + against
            return sum(comb(n, k) for k in range(for_do1, n + 1)) / 2 ** n
        self.assertAlmostEqual(mcnemar_one_sided(5, 0), 0.03125)
        self.assertAlmostEqual(mcnemar_one_sided(4, 0), 0.0625)
        self.assertGreater(mcnemar_one_sided(4, 1), 0.05)
        self.assertIn("0.031", abl.PREREGISTRATION["success"])
        self.assertIn("0.0625", abl.PREREGISTRATION["suggestive"])

    def test_dry_runs_simulate_nothing(self):
        with _guard(), mock.patch.object(ta1, "build_instance", _no_physics), \
                mock.patch.object(abl, "run_do1_episode", _no_physics), contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(abl.main([]), 0)
            for phase in ("DO1-L4-r0", "DO1-L4", "DO1-L1"):
                self.assertEqual(abl.main(["--phase", phase, "--records-root", RECORDS]), 0)
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

    def _fake_run(self, fp_do1="f" * 16, ref=("eval_A1e6_s1.jsonl", 1), do1_repairs=None, baseline=True):
        stored = _stored(*ref)

        def run(inst, arm, r, inputs, pool=None):
            rec = copy.deepcopy(stored)
            rec["verification"] = {"summary": copy.deepcopy(stored["verification"]), "full": {}}
            lines = rec["engine"]["ledger"]["lines"]
            repairs = []
            if arm == "do1":
                if baseline:
                    lines.append({"item": "do1_train_baseline", "n": 4, "detail": {"objective": do1.VERSION},
                                  "cumulative": 0})
                j = next(x["index"] for x in rec["designs"] if x["source"].startswith("repair:"))
                tool = rec["designs"][j]["source"].split(":", 1)[1]
                repairs = do1_repairs if do1_repairs is not None else [
                    _repair(design_index=j, tool=tool, vec=rec["designs"][j]["vector"])]
            rec["engine"]["ledger"]["used"] = min(rec["engine"]["ledger"]["used"], 700)
            rec["harness"] = {"verification_complete": True, "replicate": r, "noise_seed": 1,
                              "hook_calls": [{"prehook_fingerprint": fp_do1 if arm == "do1" else "f" * 16,
                                              "prehook_component_fingerprints": {}, "prehook_n_plant_lines": 1,
                                              "prehook_n_twin_lines": 1, "prehook_n_events": 1, "prehook_n_history": 1}],
                              "resources": {"total_rollout_equivalents": 10.0}, "rescreen": {"classification": "none"},
                              "do1": {"arm": arm, "bench_class": "Do1Workbench" if arm == "do1" else "EvidenceWorkbench",
                                      "version": do1.VERSION if arm == "do1" else None, "repairs": repairs}}
            return rec
        return run

    def _execute(self, run, phase="DO1-L1"):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        a = argparse.Namespace(out=os.path.join(tmp, "o.jsonl"), phase=phase, approved_by="test", max_rollouts=10 ** 6,
                               max_wall_s=0.0, harness_commit="0" * 40, records_root=RECORDS, workers=0)
        inputs = ta1.config_inputs(ta1.ROOT, os.path.join(ta1.ROOT, "artifacts", "hdb"))
        with _guard(), contextlib.redirect_stdout(io.StringIO()):
            rc = abl._execute(a, abl.planned_runs(phase), inputs, ta1.phase_cap(abl.planned_runs(phase)),
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

    def test_pilot_phase_gates(self):
        rc, recs, man = self._execute(self._fake_run(ref=("eval_A1e6_s3.jsonl", 4)), phase="DO1-L4-r0")
        self.assertEqual(rc, 0)
        self.assertEqual(man["phase"], "DO1-L4-r0")
        self.assertEqual([(r["instance_id"], r["harness"]["do1"]["arm"]) for r in recs],
                         [(ta1.CASES["L4"]["instance_id"], "frozen"), (ta1.CASES["L4"]["instance_id"], "do1")])
        self.assertTrue(recs[0]["harness"]["reproduction"]["exact"])
        self.assertTrue(recs[1]["harness"]["stored_prefix"]["match"])
        self.assertTrue(recs[1]["harness"]["paired_prehook"]["equal"])

    def test_pilot_not_exposed_pauses_and_is_recorded(self):
        for kw in ({"do1_repairs": []}, {"do1_repairs": [_repair(refused="out of bounds")]}, {"baseline": False}):
            rc, recs, _ = self._execute(self._fake_run(ref=("eval_A1e6_s3.jsonl", 4), **kw), phase="DO1-L4-r0")
            self.assertEqual(rc, ta1.PAUSE_EXIT, kw)
            self.assertEqual(len(recs), 2)                                       # persisted before pausing
            ac = recs[1]["harness"]["arm_checks"]
            self.assertFalse(ac["valid"])
            self.assertEqual(ac["exposed"], "baseline" in kw)                    # missing baseline only: still exposed
            self.assertTrue(recs[0]["harness"]["arm_checks"]["valid"])
            self.assertIsNone(recs[0]["harness"]["arm_checks"]["exposed"])

    def test_prehook_mismatch_pauses(self):
        rc, recs, _ = self._execute(self._fake_run(fp_do1="0" * 16))
        self.assertEqual(rc, ta1.PAUSE_EXIT)
        self.assertEqual(len(recs), 2)                                           # persisted before pausing
        self.assertFalse(recs[1]["harness"]["paired_prehook"]["equal"])


def _cand(gain, n_walk=4, base=2.0, n_fall=0, **gates):
    """4 train rows whose paired gain over a faulty score of `base` is `gain` on every seed; the first 4 - n_walk seeds do
    not walk (the first n_fall of them fall), otherwise identical."""
    rows = []
    for k in range(4):
        walking = k >= 4 - n_walk
        fell = k < n_fall
        rows.append(_row(walking=walking, fell=fell, disp=base + gain, fall_time=5.0 if fell else None, seed=k + 1, **gates))
    return do1.objective(rows, [base] * 4)


class ObjectiveV2Behaviour(unittest.TestCase):
    """Review DO-1 point 2: search signal below feasibility, one priority structure for CMA update and best ranking,
    normalisation and penalties."""

    def test_displacement_signal_below_feasibility(self):
        a, b = _cand(0.70), _cand(0.10)
        self.assertFalse(a["feasible"] or b["feasible"])
        self.assertEqual((a["walking_count"], a["survival_count"], a["margin"], a["mean_fitness_v1"]),
                         (b["walking_count"], b["survival_count"], b["margin"], b["mean_fitness_v1"]))  # otherwise equal
        self.assertGreater(a["J"], b["J"])
        self.assertAlmostEqual(a["J"] - b["J"], do1.SHORT_WEIGHT * 0.60 / do1.TAU_D)     # 8.0: linear, no plateau

    def test_strictly_monotone_up_to_threshold_then_feasible_jump(self):
        for n_walk in (4, 3):
            grid = [-2.0 + 0.05 * i for i in range(55)]                                  # -2.00 ... +0.70 (base 2.0)
            js = [_cand(g, n_walk=n_walk)["J"] for g in grid]
            self.assertTrue(all(y > x for x, y in zip(js, js[1:])), n_walk)
        # below a gain of -faulty score the candidate's walk score is floored at 0 (frozen walk-score rule): flat there
        self.assertAlmostEqual(_cand(-2.5)["J"], _cand(-4.0)["J"])
        below, at = _cand(0.749), _cand(0.75)
        self.assertFalse(below["feasible"])
        self.assertTrue(at["feasible"])
        self.assertGreater(at["J"] - below["J"], 90.0)
        self.assertAlmostEqual(_cand(0.75)["J"], _cand(3.0)["J"])                      # capped above TAU_D by design

    def test_exchange_rates(self):
        # infeasible: 0.02 m more median gain beats the full margin span
        lo_margin = _cand(0.30, slip_frac=0.149999)
        hi_margin = _cand(0.28)
        self.assertLess(lo_margin["margin"], hi_margin["margin"])
        self.assertGreater(lo_margin["J"], hi_margin["J"])
        # infeasible: 0.2 margin units beat the full fitness span
        rows_a = [_row(disp=2.3, fit=-10.0, slip_frac=0.08)] * 4             # slip binds (speed slack 0.55)
        rows_b = [_row(disp=2.3, fit=6.0, slip_frac=0.11)] * 4
        a, b = do1.objective(rows_a, [2.0] * 4), do1.objective(rows_b, [2.0] * 4)
        self.assertGreaterEqual(a["margin"] - b["margin"], 0.19)
        self.assertGreater(a["J"], b["J"])
        # feasible: 0.01 margin units beat the full fitness span
        rows_a = [_row(disp=3.0, fit=-10.0, slip_frac=0.0800)] * 4
        rows_b = [_row(disp=3.0, fit=6.0, slip_frac=0.0815)] * 4
        a, b = do1.objective(rows_a, [2.0] * 4), do1.objective(rows_b, [2.0] * 4)
        self.assertTrue(a["feasible"] and b["feasible"])
        self.assertAlmostEqual(a["margin"] - b["margin"], 0.01)
        self.assertGreater(a["J"], b["J"])

    def test_J_order_is_the_frozen_best_key_order(self):
        rng = np.random.default_rng(11)
        cands = []
        for _ in range(500):
            rows = []
            for _s in range(4):
                u = rng.random()
                if u < 0.05:
                    rows.append({"ok": False, "error": "boom", "seed": 1})
                    continue
                walking = u < 0.65
                fell = (not walking) and rng.random() < 0.5
                rows.append(_row(walking=walking, fell=fell, disp=float(rng.uniform(-1, 12)), fit=float(rng.uniform(-4, 6)),
                                 fall_time=float(rng.uniform(0, 10)), slip_frac=float(rng.uniform(0, 0.3)),
                                 max_abs_pitch=float(rng.uniform(0, 1.2))))
            cands.append(do1.objective(rows, list(rng.uniform(0, 8, 4))))
        for a in cands:
            for b in cands:
                ka = (a["walking_count"], a["survival_count"], a["J"])
                kb = (b["walking_count"], b["survival_count"], b["J"])
                self.assertEqual(ka > kb, a["J"] > b["J"])        # wo._score order == J order (CMA update)

    def test_cma_update_receives_J_and_best_is_top_J(self):
        _, d = _benches()
        seen = []
        original = wo._CMA.update

        def spy(self_, x, fitness):
            seen.append([float(v) for v in fitness])
            return original(self_, x, fitness)
        with _guard(), mock.patch.object(hp, "walk_seeds", _fake_walk_seeds), \
                mock.patch.object(do1, "do1_walk_job", fake_job), mock.patch.object(wo._CMA, "update", spy):
            out = d.repair("leg_length", 200, n_train=4, init={"index": 0})
        self.assertTrue(out["ok"])
        rep = d.do1_record()["repairs"][0]
        logged = [c["J"] for c in rep["candidates"]]
        self.assertEqual(rep["cma"]["restarts"], [])
        lam = rep["cma"]["popsize"]
        self.assertTrue(seen)
        for g, fit in enumerate(seen):                         # generation g = log entries 1 + g*lam ... (no restart)
            self.assertEqual(fit, logged[1 + g * lam: 1 + (g + 1) * lam])
        self.assertEqual(rep["selected"]["J"], max(logged))

    def test_gate_normalisation(self):
        at = _row(**{key: float(getattr(CRIT, attr)) for _, key, attr, _ in do1.GATES})
        self.assertTrue(all(abs(v) < 1e-12 for v in do1.gate_slacks(at).values()))
        best = _row(speed_upright=2 * CRIT.min_speed, valid_step_rate=2 * CRIT.min_step_rate, alternation=1.0,
                    raw_touchdown_rate=0.0, flight_frac=0.0, slip_frac=0.0, body_contact_frac=0.0, saturation_frac=0.0,
                    max_abs_pitch=0.0)
        self.assertTrue(all(v == 1.0 for v in do1.gate_slacks(best).values()))
        worst = _row(speed_upright=-5.0, valid_step_rate=0.0, alternation=0.0, raw_touchdown_rate=99.0, flight_frac=1.0,
                     slip_frac=1.0, body_contact_frac=1.0, saturation_frac=1.0, max_abs_pitch=9.0)
        self.assertTrue(all(v == -1.0 for v in do1.gate_slacks(worst).values()))
        self.assertEqual(do1.gate_slacks(_row(slip_frac=float("nan")))["slip"], -1.0)
        self.assertEqual(set(do1.gate_slacks(at)), {g[0] for g in do1.GATES})

    def test_errors_and_falls_penalised(self):
        good = do1.objective([_row(disp=3.0)] * 4, [2.0] * 4)
        fall = do1.objective([_row(disp=3.0)] * 3 + [_row(walking=False, fell=True, fall_time=6.0, disp=3.0)], [2.0] * 4)
        err = do1.objective([_row(disp=3.0)] * 3 + [{"ok": False, "error": "unstable", "seed": 9}], [2.0] * 4)
        self.assertGreater(good["J"], fall["J"])
        self.assertGreater(good["J"], err["J"])
        self.assertEqual((err["walking_count"], err["survival_count"]), (3, 3))
        e = err["per_seed"][3]
        self.assertEqual((e["margin"], e["binding_gate"], e["fitness_v1"], e["score"]), (-1.0, "error", -10.0, None))
        self.assertEqual(e["diff_m"], -2.0)                                   # an error scores 0 against the faulty robot
        self.assertIn("unstable", err["error"])
        self.assertEqual(fall["per_seed"][3]["margin"], -1.0)
        self.assertEqual(fall["survival_count"], 3)

    def test_objective_rejects_more_than_max_train(self):
        with self.assertRaises(ValueError):
            do1.objective([_row()] * 9, [1.0] * 9)


if __name__ == "__main__":
    unittest.main()
