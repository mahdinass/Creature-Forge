import json
import math
import unittest

import numpy as np

from creature_forge import creature_walk as cw
from creature_forge import interventions as iv
from creature_forge import r2, r3, walk_opt as wo
from creature_forge.forge_pool import ForgePool
from creature_forge.phasegait_init import LOWER15, UPPER15
from creature_forge.sandbox import SandboxBody

BASE = SandboxBody().as_dict()
VEC = list(cw.R2_WINNER)
TIMING = wo.SearchSpace.from_subspaces(["timing"])
BODY4 = ("torso_mass", "thigh_length", "foot_friction", "torque_limit")


def synthetic(space, target_x, base=BASE, vec=VEC, log=None):
    """eval_fn: objective = -squared distance (in the [0,1] encoding) to a target point."""
    def fn(cands):
        out = []
        for b, v in cands:
            x = wo.encode(space, base, vec, b, v)
            d = float(np.sum((x - target_x) ** 2))
            rec = {"walking_count": int(d < 0.05) + int(d < 0.2), "survival_count": int(d < 0.5), "mean_fitness": -d,
                   "error": None}
            out.append(rec)
            if log is not None:
                log.append(rec)
        return out
    return fn


class SpaceTests(unittest.TestCase):
    def test_subspaces_partition_param_names(self):
        names = [p for v in wo.SUBSPACES.values() for p in v]
        self.assertEqual(sorted(names), sorted(r3.PARAM_NAMES))
        self.assertEqual(len(names), len(set(names)))

    def test_validation_errors(self):
        S = wo.SearchSpace
        with self.assertRaises(ValueError):
            S(("nope",))
        with self.assertRaises(ValueError):
            S(("freq",), ("nope",))
        with self.assertRaises(ValueError):
            S(("freq", "freq"))
        with self.assertRaises(ValueError):
            S(("freq",), ("torso_mass", "torso_mass"))
        with self.assertRaises(ValueError):
            S(("freq",), ("torso_mass", "thigh_length", "shank_length", "foot_length", "leg_density"))
        with self.assertRaises(ValueError):
            S(())
        with self.assertRaises(ValueError):
            S(("freq",), mode="wild")
        with self.assertRaises(ValueError):
            S(("freq",), body_ratio=(1.2, 1.5))
        with self.assertRaises(ValueError):
            wo.SearchSpace.from_subspaces(["bogus"])
        self.assertEqual(wo.SearchSpace.full_ctrl().dim, 15)
        self.assertEqual(wo.SearchSpace.from_subspaces(["timing", "stride"], ("torso_mass",)).dim, 7)

    def test_round_trip(self):
        sp = wo.SearchSpace.full_ctrl(BODY4)
        x = np.random.default_rng(1).uniform(0, 1, sp.dim)
        body, vec = wo.decode(sp, BASE, VEC, x)
        np.testing.assert_allclose(wo.encode(sp, BASE, VEC, body, vec), x, atol=1e-9)

    def test_decoded_candidates_pass_validate_edits(self):
        rng = np.random.default_rng(2)
        stilts = SandboxBody(thigh_length=0.55, shank_length=0.55, foot_length=0.07).as_dict()
        cases = [("guided", BASE, wo.BODY_PARAMS[:4]), ("guided", BASE, wo.BODY_PARAMS[3:]),
                 ("experimental", stilts, wo.BODY_PARAMS[:4]), ("experimental", stilts, wo.BODY_PARAMS[3:])]
        for mode, base, bps in cases:
            sp = wo.SearchSpace(tuple(r3.PARAM_NAMES[:3]), bps, mode=mode)
            version = {"mode": mode, "body": base, "controllers": {"walk": {"vector": VEC}}}
            for _ in range(40):
                x = rng.uniform(-0.3, 1.3, sp.dim)       # outside [0,1] is folded
                body, vec = wo.decode(sp, base, VEC, x)
                edits = wo.body_edits(base, body)
                parsed, reasons = iv.validate_edits(version, "walk", edits)
                self.assertEqual(reasons, [], (mode, bps, edits))
                self.assertTrue(np.all(np.asarray(vec) >= LOWER15) and np.all(np.asarray(vec) <= UPPER15))

    def test_corner_candidates_validate(self):
        sp = wo.SearchSpace(("freq",), BODY4)
        version = {"mode": "guided", "body": BASE, "controllers": {"walk": {"vector": VEC}}}
        for corner in (0.0, 1.0):
            body, _ = wo.decode(sp, BASE, VEC, np.full(sp.dim, corner))
            _, reasons = iv.validate_edits(version, "walk", wo.body_edits(BASE, body))
            self.assertEqual(reasons, [])

    def test_legs_stay_symmetric(self):
        sp = wo.SearchSpace(("freq",), ("thigh_length", "foot_length"))
        body, _ = wo.decode(sp, BASE, VEC, np.array([0.5, 0.9, 0.1]))
        self.assertEqual(body["thigh_length"], body["thigh_length_r"])
        self.assertEqual(body["foot_length"], body["foot_length_r"])


class SimilarityTests(unittest.TestCase):
    def test_identity_on_default_body(self):
        vec, rep = wo.similarity_init(SandboxBody(), VEC)
        self.assertTrue(vec == VEC)
        self.assertEqual(rep["at_bound"], [])

    def test_stilts_frequency_factor(self):
        body = SandboxBody(thigh_length=0.55, shank_length=0.55)
        vec, rep = wo.similarity_init(body, VEC)
        i = r3.PARAM_NAMES.index("freq")
        self.assertAlmostEqual(vec[i] / VEC[i], math.sqrt(0.6 / 1.1), places=9)
        self.assertAlmostEqual(rep["L"], 1.1)
        self.assertAlmostEqual(rep["L0"], 0.6)
        k = r3.PARAM_NAMES.index("kd")
        g = rep["factors"]["kp"]
        self.assertAlmostEqual(rep["factors"]["kd"], g * math.sqrt(1.1 / 0.6))
        for name in ("duty", "hip_amp", "knee_amp", "start_lean", "sync_gain"):
            j = r3.PARAM_NAMES.index(name)
            self.assertEqual(vec[j], VEC[j])
        self.assertTrue(LOWER15[k] <= vec[k] <= UPPER15[k])

    def test_at_bound_is_explicit(self):
        v = list(VEC)
        i = r3.PARAM_NAMES.index("freq")
        v[i] = float(UPPER15[i])
        body = SandboxBody(thigh_length=0.1, shank_length=0.1)
        vec, rep = wo.similarity_init(body, v)
        names = {e["param"]: e for e in rep["at_bound"]}
        self.assertIn("freq", names)
        self.assertEqual(vec[i], float(UPPER15[i]))
        self.assertGreater(names["freq"]["unbounded"], float(UPPER15[i]))
        for j, x in enumerate(vec):
            self.assertTrue(LOWER15[j] <= x <= UPPER15[j])

    def test_rejects_out_of_bounds_input(self):
        v = list(VEC)
        v[0] = float(UPPER15[0]) + 1
        with self.assertRaises(ValueError):
            wo.similarity_init(SandboxBody(), v)


class CmaTests(unittest.TestCase):
    def run_cma(self, space, target, budget, seeds=(1, 2, 3), noise=7, **kw):
        log = []
        res = wo.cma_search(BASE, VEC, space, budget=budget, train_seeds=list(seeds), noise_seed=noise,
                            eval_fn=synthetic(space, target, log=log), **kw)
        return res, log

    def test_improves_strongly(self):
        sp = wo.SearchSpace.from_subspaces(["timing"], ("thigh_length", "torso_mass"))
        x0 = wo.encode(sp, BASE, VEC, BASE, VEC)
        target = np.where(x0 < 0.5, 0.9, 0.1)          # far from the start
        res, _ = self.run_cma(sp, target, 3 * 600, ipop=False)
        self.assertLess(res["init"]["mean_fitness"], -0.2)
        self.assertGreater(res["best"]["mean_fitness"], -1e-3)
        json.dumps(res)

    def test_budget_exactness_and_accounting(self):
        sp = wo.SearchSpace.from_subspaces(["timing", "posture"])
        target = np.full(sp.dim, 0.4)
        for budget, seeds in ((100, (1, 2, 3)), (101, (1, 2, 3)), (97, (5,)), (999, (1, 2)), (7, (1, 2, 3))):
            res, log = self.run_cma(sp, target, budget, seeds=seeds)
            S = len(seeds)
            self.assertLessEqual(res["rollouts_used"], budget)
            self.assertEqual(res["rollouts_used"], S * len(log))
            gen_cost = sum(h["lambda"] for h in res["history"]) * S
            self.assertEqual(res["rollouts_used"], S + gen_cost)
            if res["history"]:
                self.assertEqual(res["history"][-1]["rollouts_cumulative"], res["rollouts_used"])
            if not res["restarts"]:                      # a further generation would not have fitted
                self.assertGreater(res["rollouts_used"] + res["popsize"] * S, budget)

    def test_budget_below_initial_evaluation_raises(self):
        with self.assertRaises(ValueError):
            self.run_cma(TIMING, np.full(3, 0.5), 2, seeds=(1, 2, 3))

    def test_progress_callback(self):
        calls = []
        wo.cma_search(BASE, VEC, TIMING, budget=40, train_seeds=[1, 2], noise_seed=1,
                      eval_fn=synthetic(TIMING, np.full(3, 0.5)), progress=lambda d, b: calls.append((d, b)))
        self.assertTrue(calls)
        self.assertEqual(calls[-1][1], 40)
        self.assertEqual([c[0] for c in calls], sorted(c[0] for c in calls))

    def test_determinism(self):
        sp = wo.SearchSpace.from_subspaces(["feedback"], ("foot_friction",))
        target = np.full(sp.dim, 0.3)
        a, _ = self.run_cma(sp, target, 600, noise=11)
        b, _ = self.run_cma(sp, target, 600, noise=11)
        c, _ = self.run_cma(sp, target, 600, noise=12)
        self.assertEqual(a["history"], b["history"])
        self.assertEqual(a["best"], b["best"])
        self.assertNotEqual(a["history"], c["history"])

    def test_checkpoint_semantics(self):
        sp = wo.SearchSpace.from_subspaces(["timing"], ("thigh_length",))
        target = np.array([0.9, 0.1, 0.6, 0.2])
        S = 2
        res, log = self.run_cma(sp, target, 500, seeds=(1, 2), checkpoints=(2, 9, 50, 200, 500, 5000))
        self.assertNotIn("5000", res["checkpoints"])
        prev = None
        for c in (2, 9, 50, 200, 500):
            cp = res["checkpoints"][str(c)]
            k = c // S                                    # evaluations completed by c rollouts
            best = None
            for r in log[:k]:
                s = (r["walking_count"], r["survival_count"], r["mean_fitness"])
                if best is None or s > best:
                    best = s
            self.assertEqual(tuple(cp["score"]), best)
            self.assertLessEqual(cp["found_at_rollouts"], c)
            if prev is not None:
                self.assertGreaterEqual(tuple(cp["score"]), prev)
            prev = tuple(cp["score"])
        self.assertEqual(res["checkpoints"]["500"]["vector"], res["best"]["vector"])
        self.assertEqual(res["best"]["edits"], wo.body_edits(BASE, res["best"]["body"]))

    def test_ipop_restarts_double_lambda(self):
        const = lambda cands: [{"walking_count": 0, "survival_count": 0, "mean_fitness": -1.0, "error": None} for _ in cands]
        res = wo.cma_search(BASE, VEC, TIMING, budget=3000, train_seeds=[1], noise_seed=3, eval_fn=const, ipop=True)
        self.assertGreaterEqual(len(res["restarts"]), 1)
        lams = [h["lambda"] for h in res["history"]]
        self.assertEqual(lams[0], 7)
        first = res["restarts"][0]
        self.assertEqual(first["new_lambda"], 14)
        self.assertIn(first["reason"], ("stagnation", "sigma_below_1e-3", "condition_number_above_1e14"))
        self.assertIn(14, lams)
        self.assertTrue(1 <= max(h["restart"] for h in res["history"]) <= len(res["restarts"]))
        off = wo.cma_search(BASE, VEC, TIMING, budget=3000, train_seeds=[1], noise_seed=3, eval_fn=const, ipop=False)
        self.assertEqual(off["restarts"], [])
        self.assertEqual({h["lambda"] for h in off["history"]}, {7})
        self.assertLessEqual(off["rollouts_used"], 3000)

    def test_errors_are_recorded_not_raised(self):
        def bad(cands):
            return [{"walking_count": 0, "survival_count": 0, "mean_fitness": r2.ERROR_FITNESS, "error": "boom"} for _ in cands]
        res = wo.cma_search(BASE, VEC, TIMING, budget=60, train_seeds=[1, 2], noise_seed=1, eval_fn=bad, ipop=False)
        self.assertEqual(len(res["errors"]), res["rollouts_used"] // 2)
        self.assertEqual(res["best"]["mean_fitness"], r2.ERROR_FITNESS)

    def test_input_validation(self):
        f = synthetic(TIMING, np.full(3, 0.5))
        for kw in ({"train_seeds": []}, {"train_seeds": [1, 1]}, {"budget": -1}, {"noise_seed": -1}, {"sigma0": 0.0}):
            args = {"budget": 50, "train_seeds": [1], "noise_seed": 1, "eval_fn": f, **kw}
            with self.assertRaises(ValueError):
                wo.cma_search(BASE, VEC, TIMING, **args)
        bad = list(VEC)
        bad[0] = float(UPPER15[0]) + 1
        with self.assertRaises(ValueError):
            wo.cma_search(BASE, bad, TIMING, budget=50, train_seeds=[1], noise_seed=1, eval_fn=f)


class MujocoSmokeTests(unittest.TestCase):
    def test_stilts_smoke(self):
        body = SandboxBody(thigh_length=0.55, shank_length=0.55, foot_length=0.07)
        vec, _ = wo.similarity_init(body, VEC)
        with ForgePool(max_workers=2) as pool:
            res = wo.cma_search(body, vec, TIMING, budget=30, train_seeds=[100001, 100002], noise_seed=5, pool=pool,
                                duration=1.0, checkpoints=(10, 30))
        self.assertLessEqual(res["rollouts_used"], 30)
        self.assertEqual(res["version"], "walk_opt_v1")
        self.assertEqual(res["errors"], [])
        self.assertIsNotNone(res["best"])
        self.assertTrue(math.isfinite(res["best"]["mean_fitness"]))
        self.assertEqual(len(res["best"]["vector"]), 15)
        self.assertEqual(res["rollouts_used"], 2 + sum(h["lambda"] for h in res["history"]) * 2)
        json.dumps(res)


if __name__ == "__main__":
    unittest.main()


class BaseOnBoundTests(unittest.TestCase):
    def test_base_body_on_a_mode_bound_encodes(self):
        # regression (M1a, 2026-10-16): tiny-feet has foot_length exactly on the guided lower bound 0.06
        from creature_forge import walk_opt as wo
        import creature_forge.creature_walk as cw
        body = {"torso_mass": 15.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.06, "foot_friction": 1.0,
                "torque_limit": 60.0, "leg_density": 1000.0, "pose": [0.0] * 7}
        space = wo.SearchSpace.full_ctrl(body_params=("foot_length", "torso_mass"))
        x = wo.encode(space, body, list(cw.R2_WINNER), body, list(cw.R2_WINNER))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in x))
