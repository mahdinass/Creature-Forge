"""Tests for creature_forge.repair_learner (synthetic data only; fast, no MuJoCo, no files)."""
import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np

from creature_forge import repair_learner as rl


def planted(n=240, d=6, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    Y = np.stack([(X[:, 0] + 0.5 * X[:, 1] > 0), (X[:, 2] > 0.3), (X[:, 3] - X[:, 4] > 0)], 1).astype(float)
    return X, Y, np.ones_like(Y)


def acc(model, X, Y):
    P, _ = model.predict_proba(X)
    return float(((P > 0.5) == (Y > 0.5)).mean())


def fake_row(instance_id="a:b:1", fault="short_feet", base="b0"):
    med = {"leg_length_m": 0.8, "time_upright": 3.0, "pitch_end": 0.1, "com_vx_end": 0.2, "step_freq_hz": 2.0, "saturation_frac_hip": 0.1,
           "capture_margin_over_L_end": -0.2}
    cf = {"foot_length_x1.3": {"observation": {}, "deltas": {"n_walking": 2, "time_upright": 1.5, "pitch_end": -0.1}},
          "foot_friction_x2.5": {"refused": "unavailable"}}
    return {"instance_id": instance_id, "fault": fault, "severity": 0.5, "base_id": base, "region": "r",
            "features": {"L": 1.0, "foot_to_leg": 0.1, "friction": 1.0, "leg_density": 1000.0, "mass_total": 10.0, "tau_ratio": 0.4,
                         "torso_frac": 0.3},
            "observation": {"median": med, "n_walking": 0, "n_fell": 4}, "counterfactuals": cf,
            "repair_matrix": {t: (1.0 if i % 3 == 0 else 0.25) for i, t in enumerate(rl.TOOLS)}}


class RepairLearnerTests(unittest.TestCase):
    def test_models_learn_planted_rule(self):
        X, Y, M = planted()
        Xt, Yt, _ = planted(seed=1)
        for model in (rl.LogisticModel().fit(X, Y, M), rl.MLPModel(n_members=3).fit(X, Y, M)):
            self.assertGreater(acc(model, Xt, Yt), 0.85, model.name)

    def test_shuffled_control_near_chance(self):
        X, Y, M = planted()
        Xt, Yt, _ = planted(seed=1)
        perm = np.random.default_rng(3).permutation(len(X))
        for model in (rl.LogisticModel(lam=10.0).fit(X, Y[perm], M), rl.MLPModel(n_members=3).fit(X, Y[perm], M)):
            self.assertLess(acc(model, Xt, Yt), 0.65, model.name)

    def test_masks_respected(self):
        X, Y, M = planted()
        Y2, M2 = Y.copy(), M.copy()
        M2[:, 0] = 0.0
        Y2[:, 0] = 1.0 - Y[:, 0]            # garbage in a masked column must have no effect
        for mk in (lambda: rl.LogisticModel(lam=10.0), lambda: rl.MLPModel(n_members=2), rl.PriorModel):
            a, b = mk().fit(X, Y2, M2), mk().fit(X, np.where(M2 > 0, Y2, 0.0), M2)
            np.testing.assert_allclose(a.predict_proba(X[:20])[0][:, 1:], b.predict_proba(X[:20])[0][:, 1:])
            np.testing.assert_allclose(a.predict_proba(X[:20])[0][:, 0], b.predict_proba(X[:20])[0][:, 0])
        y, m = rl.targets({"feedback": 0.75, "posture": 0.5})
        self.assertEqual(m.sum(), 2)
        self.assertEqual(y[rl.TOOLS.index("feedback")], 1.0)
        self.assertEqual(y[rl.TOOLS.index("posture")], 0.0)
        self.assertEqual(m[rl.TOOLS.index("timing")], 0.0)

    def test_determinism(self):
        X, Y, M = planted(n=80)
        a = rl.MLPModel(n_members=2).fit(X, Y, M).predict_proba(X)[0]
        b = rl.MLPModel(n_members=2).fit(X, Y, M).predict_proba(X)[0]
        np.testing.assert_array_equal(a, b)

    def test_lobo_splitter(self):
        groups = ["a", "a", "b", "c", "c", "c"]
        splits = rl.lobo_splits(groups)
        self.assertEqual(len(splits), 3)
        for tr, te, g in splits:
            self.assertFalse(set(tr) & set(te))
            self.assertTrue(all(groups[i] == g for i in te))
            self.assertTrue(all(groups[i] != g for i in tr))
            self.assertEqual(len(tr) + len(te), len(groups))

    def test_leakage_guard(self):
        r1 = fake_row("stilts:short_feet:0.1", "short_feet", "stilts")
        r2 = copy.deepcopy(r1)
        r2.update(instance_id="zzz:slippery:0.9", fault="slippery", severity=0.99, base_id="other", region="q")
        r2["repair_matrix"] = {t: 0.0 for t in rl.TOOLS}
        for s in rl.SETTINGS:
            x1, _ = rl.build_features(r1, s)
            x2, _ = rl.build_features(r2, s)
            np.testing.assert_array_equal(x1, x2)
            self.assertEqual(len(x1), len(rl.feature_names(s)))
        self.assertFalse(any(k in n for n in rl.feature_names("obs+cf") for k in ("instance", "fault", "severity", "base_id")))

    def test_predictor_roundtrip_and_advice(self):
        rows = []
        for i in range(30):
            r = fake_row(base=f"b{i % 5}")
            r["observation"]["median"]["pitch_end"] = 0.02 * i
            r["repair_matrix"] = {t: (1.0 if (0.02 * i > 0.3) == (j % 2 == 0) else 0.0) for j, t in enumerate(rl.TOOLS)}
            rows.append(r)
        p = rl.RepairPredictor(seed=1).fit(rows)
        adv = p.advise(rows[0]["observation"], rows[0]["features"])
        self.assertEqual([a["rank"] for a in adv], list(range(1, 11)))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "m.json"
            p.save(path)
            q = rl.RepairPredictor.load(path)
            self.assertEqual(adv, q.advise(rows[0]["observation"], rows[0]["features"]))
            adv_cf = q.advise(rows[3]["observation"], rows[3]["features"], rows[3]["counterfactuals"])
            self.assertEqual(adv_cf[0]["setting"], "obs+cf")
            q.save(Path(d) / "m2.json")
            self.assertEqual(path.read_text(), (Path(d) / "m2.json").read_text())
        text = p.advice_text(rows[0]["observation"], rows[0]["features"], heldout={"top1": 0.41})
        self.assertLessEqual(len(text), 400)
        self.assertIn("statistical prediction", text)
        self.assertIn("30 training", text)


if __name__ == "__main__":
    unittest.main()
