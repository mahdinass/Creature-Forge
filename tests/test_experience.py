import math
import unittest

import numpy as np

from creature_forge import experience as ex
from creature_forge import walk_opt as wo
from creature_forge.phasegait_fp import LOWER17, UPPER17
from creature_forge.sandbox import SandboxBody

BASE = SandboxBody().as_dict()
NAMES = list(wo.ALL_NAMES) + list(ex.BODY_DIMS)


def feats(L=0.6, f=0.2, m=8.0, t=0.6, q=0.5, mu=1.0):
    return {"L": L, "foot_to_leg": f, "mass_total": m, "torso_frac": t, "tau_ratio": q, "friction": mu}


def fake_record(name, region, seed, n=60, f=None, ntr=8):
    """cma-like record; walking_count is a known function of the design (closeness to a random target)."""
    rng = np.random.default_rng(seed)
    target = rng.random(21)
    cands = []
    for i in range(n):
        x = rng.random(21)
        d = ex.to_design(NAMES, x, BASE)
        dist = float(np.linalg.norm(d - target)) / math.sqrt(21)
        cands.append({"x": x.tolist(), "walking_count": int(round(ntr * max(0.0, 1 - 2.5 * dist))),
                      "survival_count": ntr, "mean_fitness": -dist, "rollouts_cumulative": (i + 1) * ntr})
    return {"creature": name, "region": region, "body": BASE, "features": f or feats(),
            "search": {"candidates": cands, "space_names": NAMES, "train_seeds": list(range(ntr))}}


class DesignTests(unittest.TestCase):
    def test_round_trip(self):
        d = np.random.default_rng(1).random(21)
        d[17:] = 0.3 + 0.4 * d[17:]                       # keep the body inside the guided bounds
        body, vec = ex.from_design(d, BASE)
        np.testing.assert_allclose(ex.design_of(body, vec, BASE), d, atol=1e-9)
        self.assertEqual(len(vec), 17)
        self.assertTrue(np.all(np.asarray(vec) >= LOWER17) and np.all(np.asarray(vec) <= UPPER17))
        self.assertEqual(body["thigh_length"], body["thigh_length_r"])        # legs stay symmetric

    def test_to_design_matches_decode(self):
        space = wo.SearchSpace.full_ctrl_fp(body_params=ex.BODY_DIMS)
        x = np.random.default_rng(3).random(21)
        vec0 = [0.5 * (a + b) for a, b in zip(LOWER17, UPPER17)]
        body, vec = wo.decode(space, BASE, vec0, x)
        d = ex.to_design(list(space.ctrl_params) + list(space.body_params), x, BASE)
        np.testing.assert_allclose(ex.design_of(body, vec, BASE), d, atol=1e-8)
        b2, _ = ex.from_design(d, BASE)
        for k in ("thigh_length", "shank_length", "foot_length", "torso_mass"):
            self.assertAlmostEqual(b2[k], body[k], places=9)

    def test_out_of_bounds_is_rejected_not_clipped(self):
        small = dict(BASE, foot_length=0.06, foot_length_r=0.06)
        d = np.full(21, 0.5)
        d[17] = 0.0                                          # ratio 0.5 on a foot already at the lower bound
        with self.assertRaises(ex.OutOfBounds):
            ex.from_design(d, small)
        d[17] = 0.9
        ex.from_design(d, small)
        with self.assertRaises(ValueError):
            ex.from_design(np.full(21, 1.5), BASE)

    def test_missing_controller_names(self):
        with self.assertRaises(ValueError):
            ex.to_design(NAMES[1:], np.zeros(20), BASE)

    def test_morph_features(self):
        m = ex.morph_features(feats())
        np.testing.assert_allclose(m, [math.log(0.6), math.log(0.2), 0.6, math.log(0.5), 1.0, math.log(8.0)])
        self.assertEqual(m.shape, (6,))


class DatasetTests(unittest.TestCase):
    def test_build_dataset(self):
        rec = fake_record("c0", "L2-f0-t0-q0", 0, n=10)
        ds = ex.build_dataset([rec, fake_record("c1", "L0-f1-t0-q0", 1, n=7)])
        self.assertEqual(ds["X"].shape, (17, 27))
        np.testing.assert_allclose(ds["y"][:10], [c["walking_count"] / 8 for c in rec["search"]["candidates"]])
        self.assertEqual(list(ds["groups"][:10]), ["c0"] * 10)
        self.assertEqual(ds["regions"][-1], "L0-f1-t0-q0")
        self.assertTrue(np.all((ds["X"][:, 6:] >= 0) & (ds["X"][:, 6:] <= 1)))

    def test_leakage_check(self):
        ex.leakage_check(["a"], ["b"], ["L0"], ["L2"])
        with self.assertRaises(ValueError):
            ex.leakage_check(["a"], ["a"], ["L0"], ["L2"])
        with self.assertRaises(ValueError):
            ex.leakage_check(["a"], ["b"], ["L0", "L2"], ["L2"])


def toy_data(n_groups=12, per=150, seed=0):
    rng = np.random.default_rng(seed)
    X, y, g = [], [], []
    for gi in range(n_groups):
        morph = rng.normal(size=6) * 0.3 + np.array([0, 0, 0.5, 0, 1, 2])
        for _ in range(per):
            d = rng.random(21)
            X.append(np.concatenate([morph, d]))
            y.append(float(d[0] > 0.5) * 0.9 * (0.5 + 0.5 * d[1]))
            g.append(f"g{gi}")
    return np.array(X), np.array(y), np.array(g)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.X, cls.y, cls.g = toy_data()
        cls.model = ex.SurrogateEnsemble(n_models=4, hidden=(24, 24), epochs=120, seed=3).fit(cls.X, cls.y, cls.g)

    def test_learns_function(self):
        Xt, yt, _ = toy_data(4, 100, seed=99)
        mean, std = self.model.predict(Xt)
        self.assertGreater(np.corrcoef(mean, yt)[0, 1], 0.8)
        self.assertLess(np.mean(np.abs(mean - yt)), 0.12)
        self.assertTrue(np.all((mean >= 0) & (mean <= 1)) and np.all(std >= 0))

    def test_std_grows_off_distribution(self):
        Xt, _, _ = toy_data(4, 100, seed=99)
        far = Xt.copy()
        far[:, :6] = far[:, :6] + np.array([6, -6, 5, 6, -4, 7])
        far[:, 6:] = np.random.default_rng(5).random(far[:, 6:].shape)
        _, s_in = self.model.predict(Xt)
        _, s_out = self.model.predict(far)
        self.assertGreater(np.median(s_out), 2 * np.median(s_in))

    def test_deterministic(self):
        m2 = ex.SurrogateEnsemble(n_models=4, hidden=(24, 24), epochs=120, seed=3).fit(self.X, self.y, self.g)
        a, b = self.model.predict(self.X[:50]), m2.predict(self.X[:50])
        np.testing.assert_array_equal(a[0], b[0])
        np.testing.assert_array_equal(a[1], b[1])
        m3 = ex.SurrogateEnsemble(n_models=4, hidden=(24, 24), epochs=120, seed=4).fit(self.X, self.y, self.g)
        self.assertFalse(np.array_equal(a[0], m3.predict(self.X[:50])[0]))

    def test_early_stopping_uses_held_out_creatures(self):
        for info in self.model.info:
            self.assertGreaterEqual(len(info["val_creatures"]), 1)
            self.assertIsNotNone(info["val_bce"])


class DecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recs = [fake_record(f"c{i}", "L0-f1-t0-q0", i, n=80, f=feats(L=0.4 + 0.1 * i)) for i in range(6)]
        ds = ex.build_dataset(cls.recs)
        cls.model = ex.SurrogateEnsemble(n_models=3, hidden=(16, 16), epochs=25, seed=1).fit(ds["X"], ds["y"], ds["groups"])

    def test_pool(self):
        pool = ex.build_pool(self.recs, per_creature=5, include_r2=False)
        self.assertEqual(len(pool), 30)
        self.assertTrue(all(p["design"].shape == (21,) for p in pool))
        np.testing.assert_allclose(pool[0]["design"], ex.record_best(self.recs[0])[0])

    def test_propose_ranking_and_applicability(self):
        pool = ex.build_pool(self.recs, per_creature=10, include_r2=False)
        out = ex.propose_warm_starts(self.model, BASE, pool, k=3, beta=0.5, features=feats(L=0.6))
        self.assertEqual(len(out), 3)
        sc = [o["mean"] - 0.5 * o["std"] for o in out]
        self.assertEqual(sc, sorted(sc, reverse=True))
        D = np.array([p["design"] for p in pool])
        mean, std = self.model.predict(np.hstack([np.tile(ex.morph_features(feats(L=0.6)), (len(D), 1)), D]))
        self.assertGreaterEqual(out[0]["score"], float((mean - 0.5 * std).max()) - 1e-12)   # best point is feasible here
        ref = max(self.model.train_median_std, ex.STD_FLOOR)
        self.assertAlmostEqual(out[0]["applicability"], np.mean([o["std"] for o in out]) / ref)
        self.assertEqual(out[0]["may_not_apply"], out[0]["applicability"] > 2)
        np.testing.assert_allclose(ex.design_of(out[0]["body"], out[0]["vector"], BASE), out[0]["design"], atol=1e-8)

    def test_propose_discards_out_of_bounds(self):
        small = dict(BASE, foot_length=0.06, foot_length_r=0.06)
        bad = np.full(21, 0.5)
        bad[17] = 0.0
        pool = [{"design": bad, "source": "bad"}, {"design": np.full(21, 0.7), "source": "good"}]

        class Stub:
            train_median_std = 0.1

            def predict(self, X):
                return np.array([0.9, 0.1]), np.array([0.0, 0.0])

        out = ex.propose_warm_starts(Stub(), small, pool, k=2, features=feats())
        self.assertEqual([o["source"] for o in out], ["good"])
        self.assertEqual(out[0]["discarded_before"][0]["source"], "bad")

    def test_knn_picks_nearest(self):
        recs = [fake_record("far", "r", 0, f=feats(L=1.1, m=20.0)), fake_record("near", "r", 1, f=feats(L=0.62, m=8.5)),
                fake_record("mid", "r", 2, f=feats(L=0.8, m=12.0))]
        out = ex.knn_warm_start(BASE, recs, k=3, features=feats(L=0.6, m=8.0))
        self.assertEqual([o["source"] for o in out], ["near", "mid", "far"])
        np.testing.assert_allclose(out[0]["design"], ex.record_best(recs[1])[0])

    def test_mean_best_is_medoid(self):
        recs = []
        for i, c in enumerate([0.2, 0.25, 0.8]):
            r = fake_record(f"c{i}", "r", i, n=5)
            r["search"]["candidates"][0].update(walking_count=8, survival_count=8, mean_fitness=10.0)
            r["search"]["candidates"][0]["x"] = [c] * 21
            recs.append(r)
        out = ex.mean_best_start(recs)
        self.assertIn(out[0]["source"], ("c0", "c1"))
        self.assertEqual(out[-1]["source"], "c2")

    def test_realise_falls_through(self):
        small = dict(BASE, foot_length=0.06, foot_length_r=0.06)
        bad = np.full(21, 0.5)
        bad[17] = 0.0
        item, disc = ex.realise([{"design": bad, "source": "a"}, {"design": np.full(21, 0.7), "source": "b"}], small)
        self.assertEqual(item["source"], "b")
        self.assertEqual(len(disc), 1)
        none, _ = ex.realise([{"design": bad, "source": "a"}], small)
        self.assertIsNone(none)


class DriverStubTests(unittest.TestCase):
    """walk_experience.run_eval_unit with the simulator replaced (cma_search eval_fn + stubbed recovery.assess): no MuJoCo rollouts."""

    def test_eval_unit_all_variants(self):
        import importlib.util
        import json
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "scripts" / "walk_experience.py"
        spec = importlib.util.spec_from_file_location("walk_experience", path)
        we = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(we)
        real_cma, real_assess = we.wo.cma_search, we.rc.assess

        def fake_cma(body, init, space, **kw):
            def ev(cands):
                return [{"walking_count": 0, "survival_count": 1, "mean_fitness": -float(np.sum(np.asarray(v) ** 2)), "error": None}
                        for _, v in cands]
            return real_cma(body, init, space, eval_fn=ev, **kw)

        def fake_assess(original, cand, vs, cs, **kw):
            return {"status": "NOT_RECOVERED", "reasons": [], "validation": {"walking_frac": 0.0},
                    "rollouts": {"validation": 48, "confirmation": 0}}

        we.wo.cma_search = fake_cma
        we.rc.assess = fake_assess
        try:
            proto = {"campaign": "t", "seeds": {"train": 2, "validate": 3, "confirm": 3}, "evaluate": {"budget": 80, "k_warm": 2}}
            recs = [fake_record(f"c{i}", "L0-f1-t0-q0", i, n=40, f=feats(L=0.4 + 0.1 * i)) for i in range(4)]
            ds = ex.build_dataset(recs)
            model = ex.SurrogateEnsemble(n_models=2, hidden=(8,), epochs=5, seed=0).fit(ds["X"], ds["y"], ds["groups"])
            pool_ = ex.build_pool(recs, per_creature=5)
            test = {"id": "t0", "body": BASE, "features": feats(L=1.0, f=0.1), "region": "L2-f0-t0-q0"}
            for variant in ("r2", "knn", "mean_best", "learned"):
                rec = we.run_eval_unit(proto, test, variant, 0 if variant == "r2" else 4, recs, model, pool_, 5, None)
                self.assertEqual(rec["unit"].split("|")[1], variant)
                self.assertLessEqual(rec["search"]["rollouts_used"], 80)
                self.assertEqual(rec["search"]["init"]["vector"], rec["warm_start"]["vector"])
                self.assertFalse(rec["decision"]["fallback_to_r2"])
                lo, hi = rec["warm_start"]["body_ratio_box"]
                self.assertTrue(0 < lo <= 1 <= hi)
                if variant == "learned":
                    self.assertIn("applicability", rec["decision"])
                json.dumps(rec)
        finally:
            we.wo.cma_search, we.rc.assess = real_cma, real_assess


if __name__ == "__main__":
    unittest.main()
