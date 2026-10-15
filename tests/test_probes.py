"""Diagnostic probes: catalogue, applicability, bounds, determinism, summaries, expectation logic. A fake pool replaces MuJoCo, except one
small real stand run (determinism through the real simulator)."""
import copy
import json
import unittest
from pathlib import Path

from creature_forge import evidence as evm
from creature_forge import interventions as iv
from creature_forge import probes as pb

FX = Path(__file__).parent / "fixtures" / "forge_ai"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def fake_result(job):
    """Deterministic stand-in for challenges.seed_job: score grows with foot length, friction, torque, kp and a neutral start."""
    b, sp, seed = job["body"], job["spec"], job["seed"]
    stand = (job["controllers"] or {}).get("stand") or {}
    score = (4.0 + 10 * (b["foot_length"] + b.get("foot_length_r", b["foot_length"])) + b["foot_friction"] + b["torque_limit"] / 100 + stand.get("kp", 0) / 1000
             + (0.5 if sp["start"] == "neutral" else 0) + (seed % 7) * 0.01)
    return {"seed": seed, "outcome": "PASS", "score": score, "metrics": {"fell": sp["kind"] == "stand" and seed % 2 == 0, "survival_s": score},
            "rollouts": 17 if sp["kind"] == "push" else 1, "error": None}


class FakePool:
    def __init__(self, fail_seed=None):
        self.jobs, self.fail_seed = [], fail_seed

    def imap(self, fn, jobs):
        for i, j in enumerate(jobs):
            self.jobs.append(j)
            if self.fail_seed is not None and j["seed"] == self.fail_seed:
                yield i, ("error", "boom")
            else:
                yield i, fake_result(j)


class Base(unittest.TestCase):
    def setUp(self):
        self.version = load("version_experimental.json")
        self.spec = load("challenge_push.json")["spec"]
        self.spec["bisection_steps"] = 7
        self.stand_spec = {**self.spec, "kind": "stand"}
        self.seeds = [200001, 200002, 200003, 200004]


class CatalogueTests(Base):
    def test_fixed_whitelist_without_invented_parameters(self):
        self.assertEqual(set(pb.PROBE_IDS), {"friction_x2", "torque_x1_5", "foot_x1_5", "torso_mass_x0_7", "balance_gain_x1_5", "stiffer_pd",
                                             "neutral_start", "no_push"})
        self.assertFalse([i for i in pb.PROBE_IDS if i.startswith("heel")], "no heel parameter exists, so no heel probe")
        for p in pb.PROBES.values():
            for e in p.edits:
                self.assertIn(e.param, iv.WHITELIST, "a probe may only use existing whitelisted parameters")

    def test_applicability_by_challenge_kind(self):
        push = pb.available_probes(self.version, "push", self.spec)
        stand = pb.available_probes(self.version, "stand", self.stand_spec)
        walk = pb.available_probes(self.version, "walk", {**self.spec, "kind": "walk"})
        self.assertIn("no_push", push)
        self.assertNotIn("no_push", stand + walk)
        self.assertTrue({"balance_gain_x1_5", "stiffer_pd"} <= set(push) and {"balance_gain_x1_5", "stiffer_pd"} <= set(stand))
        self.assertFalse({"balance_gain_x1_5", "stiffer_pd"} & set(walk), "stand.* parameters are not editable in a walk challenge")
        self.assertTrue({"friction_x2", "torque_x1_5", "foot_x1_5", "torso_mass_x0_7", "neutral_start"} <= set(walk))
        with self.assertRaises(pb.ProbeUnavailable):
            pb.transformation(self.version, "walk", self.spec, "stiffer_pd")

    def test_probes_may_exceed_edit_caps_but_not_hard_bounds(self):
        # friction x2 is a ratio of 2.0 (> the 1.5 edit cap) yet allowed...
        t = pb.transformation(self.version, "push", self.spec, "friction_x2")
        self.assertEqual(t["body"]["foot_friction"], 2.0)
        # ...but not beyond the mode's hard bounds (sandbox friction <= 3.0)
        v = copy.deepcopy(self.version)
        v["body"]["foot_friction"] = 2.5
        why = pb.availability(v, "push", self.spec)
        self.assertIn("outside the bounds", why["friction_x2"])
        self.assertNotIn("friction_x2", pb.available_probes(v, "push", self.spec))
        with self.assertRaises(pb.ProbeUnavailable):
            pb.transformation(v, "push", self.spec, "friction_x2")

    def test_guided_bounds_are_the_guided_ones(self):
        g = load("version_guided.json")
        g["body"]["foot_friction"] = 1.5
        self.assertIsNotNone(pb.availability(g, "push", self.spec)["friction_x2"])   # 3.0 > guided max 2.0

    def test_exact_transformations_and_inputs_untouched(self):
        before = copy.deepcopy(self.version)
        spec_before = copy.deepcopy(self.spec)
        t = pb.transformation(self.version, "push", self.spec, "foot_x1_5")
        self.assertAlmostEqual(t["body"]["foot_length"], 0.08 * 1.5)
        self.assertAlmostEqual(t["body"]["foot_length_r"], 0.1 * 1.5)
        self.assertEqual(t["body"]["torque_limit"], 45.0)
        t = pb.transformation(self.version, "push", self.spec, "stiffer_pd")
        self.assertEqual((t["controllers"]["stand"]["kp"], t["controllers"]["stand"]["kd"]), (225.0, 12.0))
        self.assertEqual(t["body"]["foot_length"], 0.08)
        t = pb.transformation(self.version, "push", self.spec, "torso_mass_x0_7")
        self.assertAlmostEqual(t["body"]["torso_mass"], 6.3)
        t = pb.transformation(self.version, "push", self.spec, "neutral_start")
        self.assertEqual(t["spec"]["start"], "neutral")
        t = pb.transformation(self.version, "push", self.spec, "no_push")
        self.assertEqual(t["spec"]["kind"], "stand")
        self.assertEqual((self.version, self.spec), (before, spec_before))

    def test_neutral_start_is_unavailable_when_already_neutral(self):
        self.assertIn("already", pb.availability(self.version, "push", {**self.spec, "start": "neutral"})["neutral_start"])

    def test_catalogue_lines_cover_the_ids(self):
        lines = pb.catalogue_lines(["foot_x1_5", "no_push"])
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("- foot_x1_5:") and "measurement only" in lines[1])


class RunProbesTests(Base):
    def run_p(self, ids=("foot_x1_5", "stiffer_pd"), kind="push", spec=None, pool=None, seeds=None):
        pool = pool or FakePool()
        return pb.run_probes(self.version, kind, spec or self.spec, list(ids), seeds or self.seeds, pool), pool

    def test_deterministic(self):
        a, _ = self.run_p()
        b, _ = self.run_p()
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_original_and_every_probe_use_the_same_seeds(self):
        out, pool = self.run_p(("foot_x1_5", "friction_x2", "torque_x1_5"))
        by_arm = {}
        for j in pool.jobs:
            by_arm.setdefault(json.dumps(j["body"], sort_keys=True) + json.dumps(j["controllers"], sort_keys=True), []).append(j["seed"])
        self.assertEqual(len(by_arm), 4)   # original + 3 probes
        self.assertTrue(all(v == self.seeds for v in by_arm.values()))
        self.assertEqual(out["seeds"], self.seeds)
        self.assertEqual(out["rollouts"], 4 * 4 * 17)

    def test_push_uses_the_challenge_bisection_steps_and_resolution(self):
        out, pool = self.run_p()
        self.assertTrue(all(j["spec"]["bisection_steps"] == 7 for j in pool.jobs))
        self.assertEqual((out["resolution"], out["bisection_steps"]), (80.0 / 2 ** 7, 7))

    def test_summary_numbers(self):
        out, _ = self.run_p(("foot_x1_5",))
        r = out["results"]["foot_x1_5"]
        self.assertEqual(r["status"], "ok")
        # foot_length x1.5 on both feet: score + 10 * (0.04 + 0.05) = +0.9 (the fake score formula), per seed
        self.assertAlmostEqual(r["median_delta"], 0.9, places=5)
        self.assertEqual(len(r["deltas"]), 4)
        self.assertEqual((r["wins"], r["losses"], r["ties"]), (4, 0, 0))   # 0.9 > resolution 0.625
        self.assertAlmostEqual(r["median"], out["original"]["median"] + 0.9, places=5)

    def test_ties_wins_and_losses_use_the_resolution(self):
        out, _ = self.run_p(("friction_x2", "torso_mass_x0_7"))
        f = out["results"]["friction_x2"]           # +1.0 > 0.625 -> wins
        t = out["results"]["torso_mass_x0_7"]       # no change in the fake formula -> ties
        self.assertEqual((f["wins"], f["ties"]), (4, 0))
        self.assertEqual((t["wins"], t["losses"], t["ties"]), (0, 0, 4))
        self.assertEqual(pb.observed_direction(t["median_delta"], out["resolution"]), "no_change")

    def test_no_push_is_a_measurement_not_a_delta(self):
        out, pool = self.run_p(("no_push",))
        r = out["results"]["no_push"]
        self.assertEqual(r["measurement"], "static")
        self.assertNotIn("median_delta", r)
        self.assertEqual(r["static_fall_frac"], 0.5)   # the fake falls on even seeds
        self.assertIsNone(out["original"])
        self.assertTrue(all(j["spec"]["kind"] == "stand" for j in pool.jobs))
        self.assertEqual(out["rollouts"], 4)           # one stand rollout per seed, no bisection

    def test_error_seed_marks_the_probe_error_without_inventing_numbers(self):
        out, _ = self.run_p(("foot_x1_5",), pool=FakePool(fail_seed=self.seeds[1]))
        self.assertEqual(out["original"]["status"], "error")
        r = out["results"]["foot_x1_5"]
        self.assertEqual(r["status"], "error")
        self.assertNotIn("median_delta", r)
        self.assertEqual(pb.evaluate_expectations([{"probe_id": "foot_x1_5", "hypothesis": "H1", "expect": "increase"}], out)[0]["confirmed"], None)

    def test_budget_limits(self):
        with self.assertRaises(ValueError):
            self.run_p(("friction_x2", "torque_x1_5", "foot_x1_5", "torso_mass_x0_7"))
        with self.assertRaises(ValueError):
            self.run_p(("foot_x1_5",), seeds=[1, 2, 3, 4, 5])
        with self.assertRaises(ValueError):
            self.run_p(("foot_x1_5", "foot_x1_5"))
        with self.assertRaises(ValueError):
            self.run_p(())
        with self.assertRaises(ValueError):
            self.run_p(("foot_x1_5",), seeds=[7, 7])

    def test_unavailable_probe_is_refused_not_clipped(self):
        v = copy.deepcopy(self.version)
        v["body"]["foot_friction"] = 2.5
        with self.assertRaises(pb.ProbeUnavailable):
            pb.run_probes(v, "push", self.spec, ["friction_x2"], self.seeds, FakePool())

    def test_probes_never_change_the_creature(self):
        before = copy.deepcopy(self.version)
        self.run_p()
        self.assertEqual(self.version, before)

    def test_real_mujoco_stand_probe_is_deterministic(self):
        spec = {**self.stand_spec, "duration": 3.0}
        a = pb.run_probes(self.version, "stand", spec, ["torque_x1_5"], [200001])
        b = pb.run_probes(self.version, "stand", spec, ["torque_x1_5"], [200001])
        self.assertEqual(a, b)
        self.assertEqual(a["results"]["torque_x1_5"]["status"], "ok")
        self.assertEqual(a["rollouts"], 2)


class ExpectationTests(Base):
    def out(self, delta, res=0.625, status="ok"):
        r = {"status": status}
        if delta is not None:
            r["median_delta"] = delta
        return {"resolution": res, "seeds": [1], "results": {"foot_x1_5": r}}

    def verdict(self, delta, expect, **kw):
        return pb.evaluate_expectations([{"probe_id": "foot_x1_5", "hypothesis": "H1", "expect": expect}], self.out(delta, **kw))[0]

    def test_increase_decrease_no_change(self):
        self.assertEqual(self.verdict(2.0, "increase"), {"probe_id": "foot_x1_5", "hypothesis": "H1", "expect": "increase", "observed": "increase", "confirmed": True})
        self.assertFalse(self.verdict(2.0, "decrease")["confirmed"])
        self.assertTrue(self.verdict(-2.0, "decrease")["confirmed"])
        self.assertTrue(self.verdict(0.3, "no_change")["confirmed"])
        self.assertFalse(self.verdict(0.3, "increase")["confirmed"])
        self.assertTrue(self.verdict(0.0, "no_change")["confirmed"])

    def test_threshold_is_strictly_beyond_the_resolution(self):
        self.assertEqual(self.verdict(0.625, "no_change")["observed"], "no_change")
        self.assertEqual(self.verdict(0.6251, "increase")["observed"], "increase")
        self.assertEqual(self.verdict(-0.625, "no_change")["observed"], "no_change")

    def test_error_and_measurement_only_are_not_evaluated(self):
        self.assertEqual((self.verdict(None, "increase", status="error")["observed"], self.verdict(None, "increase")["confirmed"]), (None, None))

    def test_evidence_block_is_scalar_and_citable(self):
        out = pb.run_probes(self.version, "push", self.spec, ["foot_x1_5", "no_push"], self.seeds, FakePool())
        block = pb.evidence_block(out)
        paths = evm.leaf_paths({"probes": block})
        for p in ("probes.foot_x1_5.median_delta", "probes.foot_x1_5.wins", "probes.no_push.static_fall_frac", "probes.resolution", "probes.n_seeds"):
            self.assertIn(p, paths)
            evm.resolve({"probes": block}, p)
        self.assertNotIn("probes.no_push.median_delta", paths)


if __name__ == "__main__":
    unittest.main()
