"""Tests of the equal-budget walking-recovery pipelines. Everything except the last class runs WITHOUT MuJoCo simulation: the
`eval_override` hook (test-only) replaces rollouts by cheap synthetic functions."""
import copy
import json
import math
import os
import unittest

import numpy as np

from creature_forge import creature_gen as cg
from creature_forge import creature_walk as cw
from creature_forge import walk_opt as wo
from creature_forge import walk_pipelines as wp
from creature_forge.phasegait_init import LOWER15, UPPER15

BODY = cg.dev_named_bodies()["stilts-drawn"]
SEEDS = {"diag": [11, 12, 13, 14], "train": [21, 22, 23, 24], "screen": list(range(100, 112))}
S = len(SEEDS["train"])
SCREEN_N, TOPK = 4, 3
RESERVE = SCREEN_N * TOPK


class Fake:
    """Synthetic evaluator. Counts every candidate evaluation (x n_train rollouts) and every screening row."""

    def __init__(self):
        self.train_rollouts = 0
        self.screen_rollouts = 0

    @staticmethod
    def objective(body, vec):
        v = np.asarray(vec[:15], float)
        u = (v - LOWER15) / (UPPER15 - LOWER15)
        return -float(np.sum((u - 0.6) ** 2)) - 2.0 * math.log(body["foot_length"] / 0.12) ** 2 \
            - 0.5 * math.log(body["torso_mass"] / 4.0) ** 2 + (0.3 * (len(vec) == 17 and vec[15] + vec[16]))

    def eval_fn(self, cands):
        out = []
        for b, v in cands:
            self.train_rollouts += S
            o = self.objective(b, v)
            w = int(o > -1.2) + int(o > -0.8) + int(o > -0.5) + int(o > -0.3)
            out.append({"walking_count": min(S, w), "survival_count": min(S, w + 1), "mean_fitness": o, "error": None})
        return out

    def screen_fn(self, body, vec, seeds):
        self.screen_rollouts += len(seeds)
        o = self.objective(body, vec)
        return [{"seed": s, "outcome": "PASS" if o > -0.9 - 0.1 * (i % 3) else "FAIL", "walking": o > -0.9 - 0.1 * (i % 3),
                 "score": o + 0.01 * i} for i, s in enumerate(seeds)]

    @staticmethod
    def similarity_fn(body, vec):
        v = list(vec)
        v[0] = min(float(UPPER15[0]), v[0] * 1.05)
        return v, {"fake": True}

    def override(self):
        return {"eval_fn": self.eval_fn, "screen_fn": self.screen_fn, "similarity_fn": self.similarity_fn,
                "diag_fn": lambda b, v, s: {"outcomes": [], "gait": {}}, "features_fn": lambda b: {"L": 1.1}}

    @property
    def rollouts(self):
        return self.train_rollouts + self.screen_rollouts


def run(director, total=2000, family=15, fake=None, rounds=2, probe_budget=60, seeds=None, **kw):
    fake = fake or Fake()
    rec = wp.run_pipeline(copy.deepcopy(BODY), director, total_budget=total, family=family, seeds=seeds or SEEDS, noise_seed=7,
                          probe_budget=probe_budget, rounds=rounds, screen_top_k=TOPK, screen_n=SCREEN_N,
                          eval_override=fake.override(), **kw)
    return rec, fake


def plan(init="start", subs=("timing",), body=(), share=1.0):
    return {"init": init, "ctrl_subspaces": list(subs), "body_params": list(body), "budget_share": share}


def invariant(tc, rec, fake=None, total=None):
    tc.assertLessEqual(rec["used"], rec["total_budget"])
    tc.assertEqual(rec["used"], sum(l["n"] for l in rec["budget_lines"]))
    cum = 0
    for l in rec["budget_lines"]:
        cum += l["n"]
        tc.assertEqual(l["cumulative"], cum)
        tc.assertLessEqual(cum, rec["total_budget"])
    if fake is not None:       # every rollout the fake executed is on the ledger
        tc.assertEqual(rec["used"], fake.rollouts)
    json.dumps(rec)


class BudgetTests(unittest.TestCase):
    def test_charge_refund_exceed(self):
        b = wp.Budget(10)
        b.charge(6, "a", {"x": 1})
        self.assertEqual((b.used, b.remaining), (6, 4))
        with self.assertRaises(wp.BudgetExceeded):
            b.charge(5, "b")
        self.assertEqual(b.used, 6)
        b.refund(2, "a:refund")
        self.assertEqual(b.remaining, 6)
        self.assertEqual([l["n"] for l in b.lines], [6, -2])
        self.assertEqual(b.lines[-1]["cumulative"], 4)
        b.charge(6, "c")
        self.assertEqual(b.remaining, 0)
        for bad in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                b.charge(bad, "d")


class PlanValidation(unittest.TestCase):
    runs = {"opt_timing": 1, "r1p0": 1}

    def check(self, p, family=15):
        return wp.validate_plan(p, family=family, runs=self.runs)

    def test_valid(self):
        self.assertEqual(self.check(plan()), [])
        self.assertEqual(self.check(plan("opt_timing", ("timing", "posture"), ("foot_length",), 0.4)), [])
        self.assertEqual(self.check(plan("r1p0")), [])
        self.assertEqual(self.check(plan(subs=("placement",)), family=17), [])
        self.assertEqual(self.check({**plan(), "rationale": "why"}), [])

    def test_errors(self):
        cases = [plan(subs=("placement",)), plan(body=wo.BODY_PARAMS[:5]), plan(subs=("nope",)), plan(body=("nope",)),
                 plan(share=0), plan(share=1.5), plan(share=True), plan(share=float("nan")), plan(init="opt_stride"),
                 plan(init="bogus"), plan(subs=(), body=()), plan(subs=("timing", "timing")), {"init": "start"},
                 {**plan(), "extra": 1}, "not a dict", plan(body=("foot_length", "foot_length"))]
        for c in cases:
            self.assertTrue(self.check(c), c)


class SelectionRule(unittest.TestCase):
    @staticmethod
    def c(walk, med, train, order):
        return {"screen": {"walking": walk, "median": med}, "train_score": train, "order": order}

    def test_rule(self):
        s = wp.select_final
        self.assertEqual(s([self.c(3, 0.0, [0, 0, 0], 0), self.c(5, -9.0, [0, 0, 0], 1)]), 1)             # most walking
        self.assertEqual(s([self.c(5, 0.2, [0, 0, 0], 0), self.c(5, 0.5, [0, 0, 0], 1)]), 1)              # median
        self.assertEqual(s([self.c(5, 0.5, [1, 2, 0.1], 0), self.c(5, 0.5, [1, 2, 0.3], 1)]), 1)          # train score
        self.assertEqual(s([self.c(5, 0.5, [1, 2, 0.3], 0), self.c(5, 0.5, [1, 2, 0.3], 1)]), 0)          # order
        self.assertEqual(s([self.c(5, 0.5, [2, 0, -5.0], 0), self.c(5, 0.5, [1, 9, 9.0], 1)]), 0)          # lexicographic train

    def test_error_seed_median_is_lowest(self):
        a = wp._screen_summary([{"seed": 1, "outcome": "ERROR", "score": None, "walking": False}])
        b = wp._screen_summary([{"seed": 1, "outcome": "FAIL", "score": -100.0, "walking": False}])
        self.assertLess(a["median"], b["median"])
        self.assertEqual(a["errors"], 1)


class PipelineTests(unittest.TestCase):
    def test_fullspace_matches_direct_cma(self):
        rec, fake = run(wp.FullSpaceDirector(), total=1500)
        invariant(self, rec, fake)
        plan_rec = rec["rounds"][0]["plans"][0]
        budget_p = 1500 - RESERVE - S                     # screening reservation and shared start evaluation come first
        self.assertEqual(plan_rec["budget"], budget_p)
        direct = wo.cma_search(copy.deepcopy(BODY), list(cw.R2_WINNER), wo.SearchSpace.full_ctrl(), budget=budget_p,
                               train_seeds=SEEDS["train"], noise_seed=7, checkpoints=(), eval_fn=Fake().eval_fn)
        self.assertEqual(plan_rec["best_vector"], direct["best"]["vector"])
        self.assertEqual(plan_rec["rollouts_used"], direct["rollouts_used"])
        self.assertEqual(plan_rec["best_score"]["mean_fitness"], direct["best"]["mean_fitness"])
        self.assertTrue(all(r["plans"] == [] and r["probes"] == [] for r in rec["rounds"][1:]))
        self.assertEqual(rec["rounds"][0]["probes"], [])

    def test_fullspace_joint_uses_body(self):
        rec, fake = run(wp.FullSpaceDirector(("foot_length", "torso_mass")), total=1500)
        invariant(self, rec, fake)
        self.assertEqual(rec["rounds"][0]["plans"][0]["plan"]["body_params"], ["foot_length", "torso_mass"])

    def test_adversarial_never_exceeds_budget(self):
        every = list(wp.PROBES) * 2
        script = [
            {"round": 1, "kind": "probes", "returned": every},
            {"round": 1, "kind": "plans", "returned": [plan(share=0.9), plan(share=0.2), plan(share=0.05)]},
            {"round": 2, "kind": "probes", "returned": ["opt_stride", "nonsense", None, 3]},
            {"round": 2, "kind": "plans", "returned": [plan(share=1.0), plan(share=1.0)]},
        ]
        for total in (30, 40, 200, 700, 3000):
            if total < RESERVE + S:
                with self.assertRaises(ValueError):
                    run(wp.ScriptedDirector(script), total=total)
                continue
            rec, fake = run(wp.ScriptedDirector(script), total=total)
            invariant(self, rec, fake)

    def test_rejections_recorded_and_free(self):
        script = [
            {"round": 1, "kind": "probes", "returned": ["opt_placement", "opt_timing", "bogus", "similarity"]},
            {"round": 2, "kind": "probes", "returned": ["opt_timing"]},
            {"round": 1, "kind": "plans", "returned": [
                plan(share=0.6), plan(share=0.6), plan(share=0.1)]},
        ]
        rec, fake = run(wp.ScriptedDirector(script), total=2000)
        invariant(self, rec, fake)
        r = rec["rounds"][0]
        self.assertEqual([p["probe_id"] for p in r["probes"]], ["opt_timing"])
        rej = [(x["probe_id"], x["reason"]) for x in r["rejected_probes"]]
        self.assertEqual([k for k, _ in rej], ["opt_placement", "bogus", "similarity"])
        self.assertIn("family 17", rej[0][1])
        self.assertIn("unknown", rej[1][1])
        self.assertIn("more than 3", rej[2][1])
        self.assertEqual(rec["rounds"][1]["rejected_probes"][0]["reason"], "already run")
        self.assertEqual(len(r["plans"]), 1)                 # 0.6 + 0.6 > 1 -> second rejected; third is beyond 2 plans
        self.assertEqual(len(r["rejected_plans"]), 2)
        self.assertIn("cumulative", r["rejected_plans"][0]["reasons"][0])
        self.assertIn("more than 2", r["rejected_plans"][1]["reasons"][0])
        # forfeited: the rejected 0.6 share is not re-spent -> budget used by the one plan only
        plan_lines = [l for l in rec["budget_lines"] if l["item"].startswith("plan:")]
        self.assertEqual(len([l for l in plan_lines if l["n"] > 0]), 1)

    def test_invalid_plan_costs_nothing(self):
        bad = [plan(subs=("placement",)), plan(body=wo.BODY_PARAMS[:5]), plan(subs=("zzz",)), plan(share=2), plan(share=0),
               plan(init="opt_stride")]
        script = [{"round": 1, "kind": "plans", "returned": bad[:2]}, {"round": 2, "kind": "plans", "returned": bad[2:4]}]
        rec, fake = run(wp.ScriptedDirector(script), total=800)
        invariant(self, rec, fake)
        self.assertEqual([l["item"] for l in rec["budget_lines"] if not l["item"].startswith(("screen", "start"))], [])
        self.assertEqual(sum(len(r["rejected_plans"]) for r in rec["rounds"]), 4)
        self.assertEqual(rec["final"]["source"], "start")

    def test_refund_and_exactness(self):
        # probe_budget 60 with 4 seeds: init 4 + generations of lam*4 (lam 7 for 3-D) -> not a multiple -> refund line
        rec, fake = run(wp.ScriptedDirector([{"round": 1, "kind": "probes", "returned": ["opt_timing"]}]), total=600,
                        probe_budget=50)
        invariant(self, rec, fake)
        items = [l["item"] for l in rec["budget_lines"]]
        self.assertIn("probe:opt_timing", items)
        refund = [l for l in rec["budget_lines"] if l["item"] == "probe:opt_timing:refund"]
        pr = rec["rounds"][0]["probes"][0]
        self.assertEqual(pr["rollouts"], 4 + 28)           # init + one generation of 7 x 4
        self.assertEqual(refund[0]["n"], -(50 - pr["rollouts"]))
        self.assertLess(pr["rollouts"], 50)
        self.assertIn("screen_reserve:release", items)

    def test_screening_reservation_always_runs(self):
        total = RESERVE + S + 10                  # only 10 rollouts spendable after start eval: probes unavailable
        rec, fake = run(wp.FixedDirector(), total=total)
        invariant(self, rec, fake)
        self.assertEqual(rec["rounds"][0]["probes"], [] if rec["rounds"] else [])
        self.assertTrue(rec["final"]["screen"]["n"] == SCREEN_N)
        self.assertEqual(rec["final"]["source"], "start")
        # exactly enough for screening + start eval and nothing else
        rec2, fake2 = run(wp.FullSpaceDirector(), total=RESERVE + S)
        invariant(self, rec2, fake2)
        self.assertEqual(rec2["final"]["source"], "start")

    def test_probes_when_budget_exhausted(self):
        script = [{"round": 1, "kind": "plans", "returned": [plan(share=1.0)]},
                  {"round": 2, "kind": "probes", "returned": ["opt_posture", "foot_x1_5", "similarity"]},
                  {"round": 2, "kind": "plans", "returned": [plan(share=1.0)]}]
        rec, fake = run(wp.ScriptedDirector(script), total=400)
        invariant(self, rec, fake)
        r2 = rec["rounds"][1]
        left = 400 - RESERVE - S - rec["rounds"][0]["plans"][0]["rollouts_used"]
        self.assertLess(left, 60)
        self.assertTrue(any(x["probe_id"] == "opt_posture" and "remain" in x["reason"] for x in r2["rejected_probes"]))
        self.assertTrue(all(p["rollouts"] <= left for p in r2["probes"]))

    def test_morphology_out_of_bounds_unavailable(self):
        # stilts legs 0.55: legs_x1_2 -> 0.66 > 0.6 (never clipped); foot 0.07 x1.5 fine; legs_x0_8 fine
        rec, fake = run(wp.ScriptedDirector([{"round": 1, "kind": "probes", "returned": ["legs_x1_2", "foot_x1_5", "legs_x0_8"]}]), total=800)
        invariant(self, rec, fake)
        r = rec["rounds"][0]
        self.assertEqual([p["probe_id"] for p in r["probes"]], ["foot_x1_5", "legs_x0_8"])
        self.assertIn("outside the guided bounds", r["rejected_probes"][0]["reason"])
        p = r["probes"][0]
        self.assertAlmostEqual(p["best_body"]["foot_length"], 0.105)
        self.assertEqual(p["best_vector"], list(cw.R2_WINNER))
        self.assertEqual(p["edits"][0]["param"], "foot_length")
        self.assertEqual(p["rollouts"], S)
        self.assertEqual(r["probes"][1]["best_body"]["thigh_length"], 0.55 * 0.8)
        for k in ("probe_id", "status", "rollouts", "start_score", "best_score", "delta_mean_fitness", "delta_walking",
                  "best_body", "best_vector", "edits"):
            self.assertIn(k, p)

    def test_similarity_probe_and_opt_body(self):
        rec, fake = run(wp.ScriptedDirector([{"round": 1, "kind": "probes", "returned": ["similarity", "opt_body", "opt_stride"]}]),
                        total=900)
        invariant(self, rec, fake)
        by = {p["probe_id"]: p for p in rec["rounds"][0]["probes"]}
        self.assertEqual(by["similarity"]["rollouts"], S)
        self.assertNotEqual(by["similarity"]["best_vector"], list(cw.R2_WINNER))
        self.assertEqual(by["opt_body"]["best_vector"], list(cw.R2_WINNER))        # controller fixed
        self.assertEqual(by["opt_body"]["space"]["ctrl_params"], [])
        self.assertEqual(by["opt_body"]["space"]["body_params"], list(wp.PROBES["opt_body"]["body_params"]))

    def test_plan_from_probe_and_from_plan(self):
        script = [{"round": 1, "kind": "probes", "returned": ["opt_posture"]},
                  {"round": 1, "kind": "plans", "returned": [plan("opt_posture", ("timing",), (), 0.4)]},
                  {"round": 2, "kind": "plans", "returned": [plan("r1p0", ("timing",), ("foot_length",), 1.0)]}]
        rec, fake = run(wp.ScriptedDirector(script), total=1500)
        invariant(self, rec, fake)
        p0, p1 = rec["rounds"][0]["plans"][0], rec["rounds"][1]["plans"][0]
        self.assertEqual(p0["plan_id"], "r1p0")
        self.assertEqual(p1["init_score"], p0["best_score"])
        self.assertGreaterEqual(p1["best_score"]["mean_fitness"], p0["best_score"]["mean_fitness"])

    def test_state_is_json_safe_and_complete(self):
        seen = []

        class Spy(wp.FixedDirector):
            def choose_probes(self, state):
                seen.append(copy.deepcopy(state))
                json.dumps(state)
                return super().choose_probes(state)

            def choose_plans(self, state):
                seen.append(copy.deepcopy(state))
                json.dumps(state)
                return super().choose_plans(state)

        rec, fake = run(Spy(), total=2000)
        invariant(self, rec, fake)
        st = seen[0]
        for k in ("creature", "baseline", "family", "budget", "round", "probes_run", "plans_run", "available_probes"):
            self.assertIn(k, st)
        self.assertEqual(set(st["budget"]) >= {"total", "remaining", "used"}, True)
        self.assertEqual(st["budget"]["used"], S)                       # start evaluation only
        self.assertEqual(st["budget"]["remaining"], 2000 - RESERVE - S)
        self.assertNotIn("opt_placement", st["available_probes"])      # family 15
        st2 = seen[1]
        self.assertEqual(len(st2["probes_run"]), 3)
        self.assertEqual(wp.available_probes(st2), st2["available_probes"])
        later = [s for s in seen if s["round"] == 2]
        if later:
            self.assertTrue(later[-1]["plans_run"] and "improvement" in later[-1]["plans_run"][0])

    def test_fixed_director_rules(self):
        rec, fake = run(wp.FixedDirector(), total=2500)
        invariant(self, rec, fake)
        r1 = rec["rounds"][0]
        self.assertEqual([p["probe_id"] for p in r1["probes"]], ["opt_posture", "opt_timing", "opt_feedback"])
        ranked = sorted(r1["probes"], key=lambda p: (-p["delta_walking"], -p["delta_mean_fitness"],
                                                     wp.FIX_PRIORITY.index(p["probe_id"])))
        want = [wp.PROBES[p["probe_id"]]["subspace"] for p in ranked[:2]]
        self.assertEqual(r1["plans"][0]["plan"]["ctrl_subspaces"], want)
        self.assertEqual(r1["plans"][0]["plan"]["budget_share"], 0.5)           # not the last round
        self.assertEqual(r1["plans"][0]["plan"]["body_params"], [])
        r2 = rec["rounds"][1]
        self.assertEqual(r2["plans"][0]["plan"]["init"], "r1p0")
        self.assertEqual(r2["plans"][0]["plan"]["ctrl_subspaces"], want)
        self.assertEqual(r2["plans"][0]["plan"]["budget_share"], 1.0)
        one, _ = run(wp.FixedDirector(), total=2500, rounds=1)
        self.assertEqual(one["rounds"][0]["plans"][0]["plan"]["budget_share"], 1.0)

    def test_fixed_family17_priority_and_placement(self):
        rec, fake = run(wp.FixedDirector(), total=2500, family=17)
        invariant(self, rec, fake)
        self.assertEqual([p["probe_id"] for p in rec["rounds"][0]["probes"]], ["opt_placement", "opt_posture", "opt_timing"])
        self.assertEqual(len(rec["final"]["vector"]), 17)
        self.assertEqual(len(rec["rounds"][0]["probes"][0]["best_vector"]), 17)
        # a non-placement search keeps a 17-D vector (and the fp gains of its init)
        sc = [{"round": 1, "kind": "probes", "returned": ["opt_placement"]},
              {"round": 1, "kind": "plans", "returned": [plan("opt_placement", ("timing",), (), 1.0)]}]
        rec2, fake2 = run(wp.ScriptedDirector(sc), total=1500, family=17)
        invariant(self, rec2, fake2)
        pl = rec2["rounds"][0]["plans"][0]
        self.assertEqual(pl["best_vector"][15:], rec2["rounds"][0]["probes"][0]["best_vector"][15:])
        # placement plans are rejected for family 15
        rec3, _ = run(wp.ScriptedDirector([{"round": 1, "kind": "plans", "returned": [plan(subs=("placement",))]}]), total=800)
        self.assertEqual(rec3["rounds"][0]["plans"], [])
        self.assertIn("family 17", rec3["rounds"][0]["rejected_plans"][0]["reasons"][0])

    def test_fixed_uses_body_params_when_morphology_improved(self):
        class D(wp.FixedDirector):
            def choose_probes(self, state):
                return ["opt_posture", "opt_timing", "foot_x1_5"] if state["round"] == 1 else []
        rec, _ = run(D(), total=2500, rounds=1)
        probes = {p["probe_id"]: p for p in rec["rounds"][0]["probes"]}
        pl = rec["rounds"][0]["plans"][0]["plan"]
        improved = wp._improved(probes["foot_x1_5"])
        self.assertEqual(pl["body_params"], list(wp.FIX_BODY_PARAMS) if improved else [])

    def test_random_director_deterministic(self):
        a, _ = run(wp.RandomDirector(5), total=2500)
        b, _ = run(wp.RandomDirector(5), total=2500)
        c, _ = run(wp.RandomDirector(6), total=2500)
        for r in (a, b):
            r.pop("wall_s")
            for k in ("wall_s",):
                pass
        self.assertEqual(json.dumps(strip(a), sort_keys=True), json.dumps(strip(b), sort_keys=True))
        self.assertNotEqual(json.dumps(strip(a["decisions"])), json.dumps(strip(c["decisions"])))
        invariant(self, a)
        # structure: <= 3 probes, <= 1 plan per round, params valid
        for d in a["decisions"]:
            if d["kind"] == "probes":
                self.assertLessEqual(len(d["returned"]), 3)
            else:
                self.assertEqual(len(d["returned"]), 1)
                self.assertLessEqual(len(d["returned"][0]["body_params"]), 4)

    def test_pipeline_deterministic(self):
        a, _ = run(wp.FixedDirector(), total=1800)
        b, _ = run(wp.FixedDirector(), total=1800)
        self.assertEqual(json.dumps(strip(a), sort_keys=True), json.dumps(strip(b), sort_keys=True))

    def test_scripted_replay_equals_original(self):
        for director in (wp.RandomDirector(3), wp.FixedDirector()):
            orig, _ = run(director, total=2200)
            rep, _ = run(wp.ScriptedDirector(orig["decisions"]), total=2200)
            self.assertEqual(strip(orig["decisions"]), strip(rep["decisions"]))
            for k in ("budget_lines", "final", "rounds", "used"):
                self.assertEqual(json.dumps(orig[k], sort_keys=True), json.dumps(rep[k], sort_keys=True), k)
        with self.assertRaises(ValueError):
            wp.ScriptedDirector([{"round": 1}])

    def test_non_list_director_output_rejected(self):
        class Bad:
            def choose_probes(self, state):
                return "opt_timing"

            def choose_plans(self, state):
                return {"init": "start"}
        rec, fake = run(Bad(), total=500)
        invariant(self, rec, fake)
        self.assertTrue(rec["rounds"][0]["rejected_probes"])
        self.assertTrue(rec["rounds"][0]["rejected_plans"])

    def test_final_is_screened_best_and_dedup(self):
        script = [{"round": 1, "kind": "probes", "returned": ["opt_timing", "opt_posture", "similarity"]},
                  {"round": 1, "kind": "plans", "returned": [plan("opt_timing", ("timing", "posture"), (), 1.0)]}]
        rec, fake = run(wp.ScriptedDirector(script), total=2500)
        invariant(self, rec, fake)
        cands = rec["candidates"]
        self.assertLessEqual(len(cands), TOPK)
        # train ranking: non-increasing
        ts = [c["train_score"] for c in cands]
        self.assertEqual(ts, sorted(ts, reverse=True))
        # final = argmax of the declared rule
        key = lambda c: (c["screen"]["walking"], c["screen"]["median_score"] if c["screen"]["median_score"] is not None else -1e18,
                         tuple(c["train_score"]))
        best = max(range(len(cands)), key=lambda i: (key(cands[i]), -i))
        self.assertEqual(cands[best]["source"], rec["final"]["source"])
        self.assertEqual(rec["final"]["screen"]["n"], SCREEN_N)

    def test_seed_roles_must_be_disjoint(self):
        bad = {**SEEDS, "screen": SEEDS["train"] + list(range(200, 210))}
        with self.assertRaises(ValueError):
            run(wp.FullSpaceDirector(), seeds=bad)
        bad2 = {**SEEDS, "validate": [100]}
        with self.assertRaises(ValueError):
            run(wp.FullSpaceDirector(), seeds=bad2)

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            run(wp.FullSpaceDirector(), family=16)
        with self.assertRaises(ValueError):
            run(wp.FullSpaceDirector(), total=RESERVE + S - 1)


def strip(o):
    """Drop wall-clock fields."""
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k != "wall_s"}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


@unittest.skipUnless(os.environ.get("CF_VM_TESTS"), "real MuJoCo smoke: set CF_VM_TESTS=1 on the VM")
class RealSmoke(unittest.TestCase):
    def test_stilts_fixed_director(self):
        body = {"torso_mass": 4.7917, "thigh_length": 0.55, "shank_length": 0.55, "foot_length": 0.07,
                "foot_friction": 1.0, "torque_limit": 60.0, "leg_density": 1000.0, "pose": [0.0] * 7}
        seeds = {"diag": [31, 32, 33, 34], "train": [41, 42], "screen": [51, 52]}
        rec = wp.run_pipeline(body, wp.FixedDirector(), total_budget=400, family=15, seeds=seeds, noise_seed=3,
                              probe_budget=40, rounds=1, screen_top_k=3, screen_n=2)
        self.assertLessEqual(rec["used"], 400)
        self.assertEqual(rec["used"], sum(l["n"] for l in rec["budget_lines"]))
        self.assertEqual(len(rec["final"]["vector"]), 15)
        json.dumps(rec)


if __name__ == "__main__":
    unittest.main()
