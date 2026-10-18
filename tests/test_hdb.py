"""Fast tests (no rollouts) for the Hidden-Damage Bench, its workbench helpers and the belief engine's pure functions."""
import json
import math
import unittest

from creature_forge import belief_engine as be
from creature_forge import fault_bench as fb
from creature_forge import hdb_bench as hb
from creature_forge import hidden_plant as hp
from creature_forge import hdb_workbench as hw


class Bench(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fb.load_bases("dev")[0]

    def test_policy_view_hides_plant(self):
        inst = hb.make_instance(self.base, "payload_offset", 1)
        view = hb.policy_view(inst)
        text = json.dumps(view)
        for secret in ("payload", "deviation", "gap", "family", "severity", "validate", "confirm", "check"):
            self.assertNotIn(secret, text, secret)
        self.assertEqual(view["robot"]["body"], inst["robot"]["body"])
        self.assertEqual(set(view["seeds"]), set(hb.POLICY_ROLES))

    def test_seed_roles_disjoint_and_deterministic(self):
        a = hb.instance_seeds("b", "short_feet", 2)
        hb.assert_disjoint(a)
        self.assertEqual(a, hb.instance_seeds("b", "short_feet", 2))
        self.assertNotEqual(a["validate"], hb.instance_seeds("b", "short_feet", 3)["validate"])

    def test_reality_gap_small_and_deterministic(self):
        g = hb.reality_gap("x:y:1")
        self.assertEqual(g, hb.reality_gap("x:y:1"))
        for p in g:
            (v,) = p["params"].values()
            self.assertTrue(0.79 <= v <= 1.26, p)

    def test_families_valid_and_payload_resolved(self):
        for fam, spec in hb.FAMILIES.items():
            for s in range(hb.severity_count(fam)):
                dev = hb.deviation_for(self.base, fam, s)
                self.assertEqual(dev, hp.validate_deviation(dev))
        dev = hb.deviation_for(self.base, "payload_offset", 0)
        self.assertAlmostEqual(dev[0]["params"]["mass_kg"], 0.2 * hb.design_mass(self.base["body"]), places=5)

    def test_wide_tool_space_and_static_mass(self):
        sp = hw.tool_space("foot_friction")
        self.assertEqual(sp.body_ratio, (0.25, 4.0))
        d = hw.static_mass_com(None, self.base["body"])
        p = hw.static_mass_com({"deviation": [hb.prim("payload", "torso", mass_kg=2.0, x_m=0.1)]}, self.base["body"])
        self.assertAlmostEqual(p["mass_kg"] - d["mass_kg"], 2.0, places=6)
        self.assertGreater(p["com_x_m"], d["com_x_m"])


class Engine(unittest.TestCase):
    def test_loglik_paired_and_missing(self):
        f = {"walking": 1.0, "time_upright": 10.0, "pitch_mean": 0.1}
        obs = {1: dict(f), 2: dict(f)}
        same = be.loglik(obs, {1: dict(f), 2: dict(f)})
        off = be.loglik(obs, {1: dict(f, pitch_mean=0.3), 2: dict(f)})
        self.assertGreater(same, off)
        self.assertEqual(be.loglik(obs, {3: dict(f)}), 0.0)           # unpaired seeds say nothing
        miss = be.loglik({1: {"step_freq_hz": None}}, {1: {"step_freq_hz": 2.0}})
        self.assertEqual(miss, -be.MISSING_PENALTY)

    def test_generic_library(self):
        lib = be.generic_particles(20.0)
        self.assertIn([], lib)
        kinds = {d[0]["kind"] for d in lib if d}
        self.assertEqual(kinds, set(be.GENERIC))
        self.assertEqual(len(lib), len({be._pid(d) for d in lib}))

    def test_neighbours_stay_in_range(self):
        for d in be.generic_particles(20.0):
            for n in be.neighbours(d):
                hp.validate_deviation(n)

    def test_eig_bounded_by_entropy(self):
        class P:
            def __init__(self, pred):
                self.seen = {"eig:c#2": pred}
        eng = be.Episode.__new__(be.Episode)
        eng.b = type("B", (), {"obs_seeds": [1, 2]})()
        eng.design_mass = 20.0
        a = {1: {"walking": 1.0}, 2: {"walking": 1.0}}
        b = {1: {"walking": 0.0}, 2: {"walking": 0.0}}
        cand = {"id": "c", "kind": "counterfactual"}
        top = [(P(a), 0.5), (P(b), 0.5)]
        g = eng.eig(cand, top)
        self.assertGreater(g, 0.5 * math.log(2))
        self.assertLessEqual(g, math.log(2) + 1e-9)
        self.assertAlmostEqual(eng.eig(cand, [(P(a), 0.5), (P(a), 0.5)]), 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
