"""Tests for creature_forge.creature_gen (fake job_fn for the logic; one real MuJoCo smoke)."""
import json
import math
import unittest
from pathlib import Path

import numpy as np

from creature_forge import creature_gen as cg
from creature_forge.creatures import seed_block
from creature_forge.forge_pool import InlinePool
from creature_forge.morphology import BipedParams
from creature_forge.sandbox import SandboxBody

ROOT = Path(__file__).resolve().parent.parent


def feat(L=0.6, f=0.1, t=0.4, q=0.2, mass=6.0, fr=1.0):
    return {"L": L, "foot_to_leg": f, "mass_total": mass, "torso_frac": t, "tau_ratio": q, "friction": fr,
            "leg_density": 1000.0}


def fake_job(outcome_for):
    """job_fn returning scripted outcomes: outcome_for(job) -> 'PASS'|'POOR'|'FAIL'|'ERROR'."""
    def fn(job):
        o = outcome_for(job)
        return {"seed": job["seed"], "outcome": o, "score": 0.1, "metrics": {"fall_time": 1.5, "label": "x"},
                "events": [], "rollouts": 1, "error": "boom" if o == "ERROR" else None}
    return fn


class SeedBlockTests(unittest.TestCase):
    def test_deterministic_and_shape(self):
        a = cg.walkrec_seed_block("c", "selection", "draw0", 8)
        self.assertEqual(a, cg.walkrec_seed_block("c", "selection", "draw0", 8))
        self.assertEqual(a, tuple(range(a[0], a[0] + 8)))
        self.assertNotEqual(a, cg.walkrec_seed_block("c", "selection", "draw1", 8))
        self.assertNotEqual(a[0], cg.walkrec_seed_block("d", "selection", "draw0", 8)[0])

    def test_ranges_and_role_disjoint(self):
        spans = {r: [] for r in cg.ROLES}
        for role in cg.ROLES:
            for i in range(300):
                s = cg.walkrec_seed_block("camp", role, f"k{i}", 64)
                self.assertGreaterEqual(s[0], 10_000_000)
                self.assertLess(s[-1], 2 ** 31)
                self.assertGreaterEqual(s[0], cg.ROLE_BASE[role])
                self.assertLess(s[-1], cg.ROLE_BASE[role] + 10_000_000)
                spans[role].append((s[0], s[-1]))
        for r1 in cg.ROLES:
            for r2 in cg.ROLES:
                if r1 < r2:
                    self.assertTrue(max(a for a, _ in spans[r1]) < min(a for a, _ in spans[r2])
                                    or max(a for a, _ in spans[r2]) < min(a for a, _ in spans[r1]))

    def test_no_collision_with_existing(self):
        old = seed_block("creature", 3, 1, "challenge", 8)
        self.assertLess(max(old), 1_000_000)
        self.assertGreater(min(cg.walkrec_seed_block("c", "gen", "k", 1)), 1_000_000)

    def test_validation(self):
        for args in [("", "gen", "k", 1), ("c", "gen", "", 1), ("c", "nope", "k", 1), ("c", "gen", "k", 0),
                     ("c", "gen", "k", 65), ("c", "gen", "k", 1.5), (None, "gen", "k", 1)]:
            with self.assertRaises(ValueError, msg=str(args)):
                cg.walkrec_seed_block(*args)


class FeatureTests(unittest.TestCase):
    def test_default_body(self):
        b = {"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.16, "foot_friction": 1.0,
             "torque_limit": 60.0, "leg_density": 1000.0, "pose": [0.0] * 7}
        f = cg.features(b)
        self.assertAlmostEqual(f["L"], 0.6)
        self.assertAlmostEqual(f["foot_to_leg"], 0.16 / 0.6)
        self.assertGreater(f["mass_total"], 5.0)
        self.assertAlmostEqual(f["torso_frac"], 5.0 / f["mass_total"])
        self.assertAlmostEqual(f["tau_ratio"], 60.0 / (f["mass_total"] * 9.81 * 0.6))
        self.assertEqual(f["friction"], 1.0)
        self.assertEqual(f["leg_density"], 1000.0)

    def test_asymmetric_legs_use_mean(self):
        b = {"torso_mass": 5.0, "thigh_length": 0.3, "shank_length": 0.3, "foot_length": 0.1, "foot_friction": 1.0,
             "torque_limit": 60.0, "leg_density": 1000.0, "thigh_length_r": 0.4, "shank_length_r": 0.4,
             "foot_length_r": 0.2, "pose": [0.0] * 7}
        f = cg.features(b)
        self.assertAlmostEqual(f["L"], 0.7)
        self.assertAlmostEqual(f["foot_to_leg"], 0.15 / 0.7)

    def test_regions(self):
        self.assertEqual(len(cg.REGIONS), 24)
        self.assertEqual(len(set(cg.REGIONS)), 24)
        self.assertEqual(cg.region_of(feat(L=0.5, f=0.1, t=0.4, q=0.2)), "L0-f0-t0-q0")
        self.assertEqual(cg.region_of(feat(L=0.7, f=0.2, t=0.6, q=0.5)), "L1-f1-t1-q1")
        self.assertEqual(cg.region_of(feat(L=1.2, f=0.0, t=0.0, q=0.0)), "L2-f0-t0-q0")
        self.assertEqual(cg.region_of(feat(L=0.30)), "L0-f0-t0-q0")

    def test_exact_boundaries_go_up(self):
        self.assertEqual(cg.region_of(feat(L=0.60))[:2], "L1")
        self.assertEqual(cg.region_of(feat(L=0.5999999))[:2], "L0")
        self.assertEqual(cg.region_of(feat(L=0.90))[:2], "L2")
        self.assertEqual(cg.region_of(feat(L=0.8999999))[:2], "L1")
        self.assertIn("-f1-", cg.region_of(feat(f=0.15)))
        self.assertIn("-f0-", cg.region_of(feat(f=0.1499999)))
        self.assertIn("-t1-", cg.region_of(feat(t=0.5)))
        self.assertIn("-t0-", cg.region_of(feat(t=0.4999999)))
        self.assertTrue(cg.region_of(feat(q=0.35)).endswith("q1"))
        self.assertTrue(cg.region_of(feat(q=0.3499999)).endswith("q0"))
        for r in (cg.region_of(feat(L=l, f=ff, t=t, q=q)) for l in (0.4, 0.7, 1.0) for ff in (0.1, 0.2)
                  for t in (0.3, 0.7) for q in (0.1, 0.6)):
            self.assertIn(r, cg.REGIONS)


class SampleTests(unittest.TestCase):
    def test_determinism(self):
        a = [cg.sample_body(np.random.default_rng(5)) for _ in range(2)]
        self.assertEqual(a[0], a[1])
        r1, r2 = np.random.default_rng(1), np.random.default_rng(1)
        self.assertEqual([cg.sample_body(r1) for _ in range(20)], [cg.sample_body(r2) for _ in range(20)])
        self.assertNotEqual(cg.sample_body(np.random.default_rng(1)), cg.sample_body(np.random.default_rng(2)))

    def test_validity_500(self):
        rng = np.random.default_rng(123)
        for _ in range(500):
            b = cg.sample_body(rng)
            BipedParams(**{k: b[k] for k in cg.GEN_DIST}).validate()
            SandboxBody(**{**b, "pose": tuple(b["pose"])}).validate()
            for k in ("thigh_length", "shank_length", "foot_length"):
                self.assertEqual(b[k], b[k + "_r"])
            self.assertEqual(b["pose"], [0.0] * 7)
            for k, s in cg.GEN_DIST.items():
                self.assertTrue(s["lo"] <= b[k] <= s["hi"], k)
        json.dumps(b)


class DistanceTests(unittest.TestCase):
    def test_properties(self):
        a, b = feat(), feat(L=0.9, f=0.2, t=0.6, q=0.5, mass=10.0, fr=0.5)
        self.assertEqual(cg.distance(a, a), 0.0)
        self.assertAlmostEqual(cg.distance(a, b), cg.distance(b, a))
        self.assertGreater(cg.distance(a, b), 0.0)
        self.assertLess(cg.distance(a, b), 5.0)
        self.assertGreater(cg.distance(a, feat(fr=1.1)), 0.0)


class IsFailingTests(unittest.TestCase):
    def check(self, outs):
        return cg.is_failing([{"outcome": o} for o in outs])

    def test_table(self):
        F, P, W = "FAIL", "PASS", "POOR"
        self.assertTrue(self.check([F] * 8)[0])
        self.assertTrue(self.check([F] * 7 + [P])[0])
        self.assertTrue(self.check([F] * 4 + [W] * 4)[0])
        self.assertFalse(self.check([F] * 6 + [P] * 2)[0])      # two walk
        self.assertTrue(self.check([F] * 4 + [P] + [W] * 3)[0])  # 4 FAIL = 50 %, one PASS
        self.assertFalse(self.check([F] * 3 + [W] * 5)[0])      # < 50 % fall
        self.assertFalse(self.check([P] * 8)[0])
        self.assertFalse(self.check([W] * 8)[0])
        ok, why = self.check([F] * 7 + ["ERROR"])
        self.assertFalse(ok)
        self.assertIn("error", why)
        self.assertFalse(cg.is_failing([])[0])

    def test_accepts_strings(self):
        self.assertTrue(cg.is_failing(["FAIL"] * 8)[0])


class PanelTests(unittest.TestCase):
    def test_all_fail_deterministic_and_accounted(self):
        fn = fake_job(lambda j: "FAIL")
        kw = dict(n=5, min_dist=0.0, max_per_region=99, max_draws=50, job_fn=fn)
        a = cg.generate_panel("fake", **kw)
        b = cg.generate_panel("fake", **kw)
        self.assertEqual(a, b)
        self.assertEqual(len(a["accepted"]), 5)
        self.assertEqual(a["draws"], 5)
        self.assertEqual(a["rollouts"], 5 * 8)
        self.assertEqual(a["version"], "creature_gen_v1")
        self.assertEqual([x["id"] for x in a["accepted"]], [f"fake-{i:04d}" for i in range(5)])
        sel = a["accepted"][0]["selection"]
        self.assertEqual(sel["seeds"], list(cg.walkrec_seed_block("fake", "selection", "draw0", 8)))
        self.assertEqual(len(sel["per_seed"]), 8)
        self.assertEqual(set(sel["per_seed"][0]), {"seed", "outcome", "score", "fall_time", "label"})
        self.assertNotEqual(cg.generate_panel("other", **kw)["accepted"][0]["body"], a["accepted"][0]["body"])
        json.dumps(a)

    def test_every_draw_accounted(self):
        # draws alternate: even draw index -> all FAIL, odd -> all PASS
        def out(job):
            d = [i for i in range(100) if job["seed"] in cg.walkrec_seed_block("acct", "selection", f"draw{i}", 8)][0]
            return "FAIL" if d % 2 == 0 else "PASS"
        r = cg.generate_panel("acct", 3, min_dist=0.0, max_per_region=99, max_draws=100, job_fn=fake_job(out))
        self.assertEqual(len(r["accepted"]), 3)
        self.assertEqual(r["draws"], 5)
        draws = sorted([x["draw"] for x in r["accepted"]] + [x["draw"] for x in r["rejected"]])
        self.assertEqual(draws, list(range(5)))
        self.assertEqual([x["draw"] for x in r["accepted"]], [0, 2, 4])
        for x in r["rejected"]:
            self.assertIn("not_failing", x["reason"])
            self.assertEqual(len(x["selection"]["per_seed"]), 8)
        self.assertEqual(r["rollouts"], 5 * 8)

    def test_error_rejected_with_reason(self):
        r = cg.generate_panel("err", 1, min_dist=0.0, max_per_region=99, max_draws=3, job_fn=fake_job(lambda j: "ERROR"))
        self.assertEqual(r["accepted"], [])
        self.assertEqual(len(r["rejected"]), 3)
        self.assertTrue(all(x["reason"].startswith("error") for x in r["rejected"]))

    def test_max_draws_stops(self):
        r = cg.generate_panel("stop", 10, min_dist=0.0, max_per_region=99, max_draws=4, job_fn=fake_job(lambda j: "FAIL"))
        self.assertEqual(r["draws"], 4)
        self.assertEqual(len(r["accepted"]), 4)

    def test_region_cap_and_allowed(self):
        fn = fake_job(lambda j: "FAIL")
        r = cg.generate_panel("cap", 8, min_dist=0.0, max_per_region=1, max_draws=300, job_fn=fn)
        regs = [x["region"] for x in r["accepted"]]
        self.assertEqual(len(regs), len(set(regs)))
        self.assertTrue(any(x["reason"].startswith("region_cap") for x in r["rejected"]))
        self.assertEqual(len(r["accepted"]) + len(r["rejected"]), r["draws"])
        # default cap = ceil(n / 24) + 1 = 2 for n=4
        self.assertEqual(cg.generate_panel("cap", 1, max_draws=1, job_fn=fn)["max_per_region"], 2)
        allowed = [regs[0]]
        r2 = cg.generate_panel("cap", 1, allowed_regions=allowed, min_dist=0.0, max_draws=200, job_fn=fn)
        self.assertEqual([x["region"] for x in r2["accepted"]], allowed)
        self.assertTrue(all(x["reason"] == "region_not_allowed" for x in r2["rejected"]))
        self.assertEqual(r2["regions_allowed"], allowed)
        with self.assertRaises(ValueError):
            cg.generate_panel("cap", 1, allowed_regions=["bogus"], job_fn=fn)

    def test_min_dist(self):
        fn = fake_job(lambda j: "FAIL")
        r = cg.generate_panel("dist", 4, min_dist=0.5, max_per_region=99, max_draws=80, job_fn=fn)
        acc = r["accepted"]
        for i in range(len(acc)):
            for j in range(i):
                self.assertGreaterEqual(cg.distance(acc[i]["features"], acc[j]["features"]), 0.5)
        r2 = cg.generate_panel("dist", 3, min_dist=100.0, max_per_region=99, max_draws=10, job_fn=fn)
        self.assertEqual(len(r2["accepted"]), 1)
        self.assertEqual(r2["draws"], 10)
        self.assertTrue(all(x["reason"].startswith("too_close") for x in r2["rejected"]))

    def test_pool_errors_become_error_outcomes(self):
        class BadPool:
            def imap(self, fn, jobs):
                for i, _ in enumerate(jobs):
                    yield i, ("error", "worker died")
        r = cg.generate_panel("bp", 1, max_draws=2, pool=BadPool(), job_fn=lambda j: None)
        self.assertEqual(len(r["rejected"]), 2)
        self.assertEqual(r["rejected"][0]["selection"]["per_seed"][0]["outcome"], "ERROR")


class NamedBodyTests(unittest.TestCase):
    def test_valid_and_complete(self):
        named = cg.dev_named_bodies()
        self.assertEqual(set(named), {"stilts-drawn", "tiny-feet", "top-heavy", "weak-slippery"})
        self.assertEqual(set(named), set(cg.NAMED_NOTES))
        for name, b in named.items():
            BipedParams(**{k: b[k] for k in cg.GEN_DIST}).validate()
            SandboxBody(**{**b, "pose": tuple(b["pose"])}).validate()
            f = cg.features(b)
            self.assertIn(cg.region_of(f), cg.REGIONS)
        self.assertEqual(named["stilts-drawn"]["torso_mass"], 4.7917)
        self.assertEqual(named["stilts-drawn"]["thigh_length"], 0.55)
        self.assertIsNot(cg.dev_named_bodies()["tiny-feet"], named["tiny-feet"])

    def test_match_zoo_fixture_except_documented(self):
        zoo = {c["id"]: c["body"] for c in json.loads((ROOT / "tests/fixtures/forge_zoo.json").read_text())["creatures"]}
        named = cg.dev_named_bodies()
        changed = {"tiny-feet": {"foot_length", "foot_length_r"}, "top-heavy": {"torso_mass"}, "weak-slippery": set()}
        for name, ch in changed.items():
            z = zoo[name if name != "weak-slippery" else "weak-slippery"]
            diff = {k for k in z if z[k] != named[name][k]}
            self.assertEqual(diff - {"pose"} if name == "weak-slippery" else diff, ch, name)

    @unittest.skipUnless((ROOT / "experiments/forge_loop/demo_capture/live3-walk-stilts/i-2ed39b130df0.json").exists(),
                         "live3 record not present in this checkout")
    def test_stilts_matches_record(self):
        rec = json.loads((ROOT / "experiments/forge_loop/demo_capture/live3-walk-stilts/i-2ed39b130df0.json").read_text())
        b = rec["evidence"]["creature"]["body"]
        n = cg.dev_named_bodies()["stilts-drawn"]
        for k in ("torso_mass", "leg_density", "torque_limit"):
            self.assertAlmostEqual(b[k], n[k])
        # the record's evidence pack stores leg geometry per leg; the drawn stilts are symmetric
        for leg in ("rear", "front"):
            for k in ("thigh_length", "shank_length", "foot_length"):
                self.assertAlmostEqual(b[leg][k], n[k], msg=f"{leg}.{k}")


class RealPhysicsSmoke(unittest.TestCase):
    def test_generate_panel_real(self):
        r = cg.generate_panel("smoke", 1, max_draws=3, selection_k=2, pool=InlinePool())
        self.assertLessEqual(r["draws"], 3)
        self.assertEqual(len(r["accepted"]) + len(r["rejected"]), r["draws"])
        sim = [x for x in r["accepted"] + r["rejected"] if "selection" in x]
        self.assertTrue(sim)
        for x in sim:
            self.assertEqual(len(x["selection"]["per_seed"]), 2)
            for s in x["selection"]["per_seed"]:
                self.assertIn(s["outcome"], ("PASS", "POOR", "FAIL", "ERROR"))
        self.assertGreater(r["rollouts"], 0)


if __name__ == "__main__":
    unittest.main()
