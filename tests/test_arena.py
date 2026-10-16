"""Arena: arms, retune fairness, screening/selection, validation, verdicts, seeds, determinism (contracts section 6).

Most tests patch `arena.seed_job` / `creature_walk.adapt_controller` with cheap deterministic fakes; the determinism and
end-to-end tests run a few short real MuJoCo stand rollouts on the InlinePool."""
import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from creature_forge import arena
from creature_forge import interventions as iv
from creature_forge.arena import ArenaConfig
from creature_forge.forge_pool import InlinePool
from creature_forge.interventions import Edit

FX = Path(__file__).parent / "fixtures" / "forge_ai"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def fake_seed_job(job):
    """Score = torso mass of the arm (+ a tiny seed term, below the walk resolution); one rollout; ERROR for a marked arm."""
    b = job["body"]
    if b["leg_density"] == 1500.0:
        return {"seed": job["seed"], "outcome": "ERROR", "score": 0.0, "metrics": {}, "events": [], "rollouts": 0, "error": "boom"}
    return {"seed": job["seed"], "outcome": "PASS", "score": float(b["torso_mass"]) + 0.001 * (job["seed"] % 3),
            "metrics": {"label": "walking", "walking": True}, "events": [], "rollouts": 1, "error": None}


class FakeAdapt:
    def __init__(self):
        self.calls = []

    def __call__(self, body, init_vector, *, budget, train_seeds, noise_seed, pool=None, progress=None, **kw):
        self.calls.append({"body": body.torso_mass, "budget": budget, "train_seeds": list(train_seeds), "noise_seed": noise_seed,
                           "init": list(init_vector)})
        return {"vector": list(init_vector), "rollouts_used": 51, "init_score": [1, 1, 0.5], "best_score": [1, 1, 0.6], "improved": False}


def cfg(**kw):
    base = dict(screen_seeds=(101, 102, 103, 104), validate_seeds=tuple(range(201, 209)), train_seeds=(301, 302, 303),
                retune_budget=48, noise_seed=77)
    base.update(kw)
    return ArenaConfig(**base)


def mass_edit(f):
    return [Edit("torso_mass", "scale", f)]


def arms_walk(retune=True):
    return [
        {"arm_id": "ai:P1", "source": "nemotron", "proposal_id": "P1", "edits": mass_edit(1.2), "retune_controller": retune},
        {"arm_id": "ai:P2", "source": "nemotron", "proposal_id": "P2", "edits": mass_edit(1.4)},
        {"arm_id": "random:P1", "source": "random_baseline", "proposal_id": "P1", "edits": mass_edit(0.8)},
        {"arm_id": "heuristic", "source": "heuristic", "edits": mass_edit(1.05)},
    ]


class Config(unittest.TestCase):
    def test_validation(self):
        with self.assertRaises(ValueError):
            ArenaConfig(screen_seeds=(1, 2), validate_seeds=(2, 3))
        with self.assertRaises(ValueError):
            ArenaConfig(screen_seeds=(1,), validate_seeds=(3,), train_seeds=(3,))
        with self.assertRaises(ValueError):
            ArenaConfig(screen_seeds=(1,), validate_seeds=(2,), n_validate_arms=3)
        with self.assertRaises(ValueError):
            ArenaConfig(screen_seeds=(1,), validate_seeds=(2,), validation_variation={"bogus": 1})
        with self.assertRaises(ValueError):
            ArenaConfig(screen_seeds=(1,), validate_seeds=(2,), validation_variation={"friction_pct": 0.9})
        c = ArenaConfig(screen_seeds=(1,), validate_seeds=(2,))
        self.assertIsNone(c.validation_variation)                 # off by default
        self.assertEqual(c.to_dict()["n_validate_arms"], 2)


class Seeds(unittest.TestCase):
    def test_disjoint_and_outside_consumed(self):
        s = arena.seed_sets("c-abc", 1, 1, {"challenge": 8, "train": 3, "screen": 4, "validate": 8})
        roles = s["seeds"]
        allv = [x for r in roles.values() for x in r]
        self.assertEqual(len(allv), len(set(allv)))
        self.assertEqual([len(roles[r]) for r in ("challenge", "train", "screen", "validate")], [8, 3, 4, 8])
        forbidden = set().union(*(set(v) for v in arena._forbidden_seeds().values()))
        self.assertFalse(forbidden & set(allv))
        self.assertGreaterEqual(min(allv), 100_000)
        self.assertLess(max(x for v in arena._forbidden_seeds().values() for x in v), 100_000)
        self.assertEqual(s["round"], 1)
        self.assertEqual(s["bumped"], 0)
        self.assertEqual(s, arena.seed_sets("c-abc", 1, 1))        # deterministic (defaults = the sizes above)

    def test_collision_bumps_round(self):
        real = arena.seed_block

        def clash(cid, n, rnd, role, k):
            if rnd == 5 and role == "validate":
                return real(cid, n, rnd, "screen", k)          # overlaps the screen block of the same round
            return real(cid, n, rnd, role, k)

        with mock.patch.object(arena, "seed_block", clash):
            s = arena.seed_sets("c-abc", 2, 5, {"screen": 4, "validate": 4})
        self.assertEqual(s["round"], 6)
        self.assertEqual(s["bumped"], 1)
        self.assertFalse(set(s["seeds"]["screen"]) & set(s["seeds"]["validate"]))

    def test_unknown_role(self):
        with self.assertRaises(ValueError):
            arena.seed_sets("c", 1, 1, {"oops": 3})


class Selection(unittest.TestCase):
    def rec(self, scores, rollouts=1):
        return [{"seed": i, "score": s, "outcome": "PASS" if s is not None else "ERROR", "rollouts": rollouts, "error": None, "metrics": {}}
                for i, s in enumerate(scores)]

    def arm(self, i, src, error=None):
        return {"arm_id": i, "source": src, "error": error}

    def test_median_then_mean_then_order(self):
        arms = [self.arm("original", "original"), self.arm("ai:1", "nemotron"), self.arm("ai:2", "nemotron"), self.arm("ai:3", "nemotron"),
                self.arm("random:1", "random_baseline"), self.arm("heuristic", "heuristic")]
        scr = {"ai:1": self.rec([5, 5, 5]), "ai:2": self.rec([5, 5, 9]), "ai:3": self.rec([5, 5, 9]),     # 2 and 3 tie on median and mean
               "random:1": self.rec([1, 2, 3]), "heuristic": self.rec([2, 2, 2])}
        sel = arena.select_arms(arms, scr)
        self.assertEqual(sel["ai"], "ai:2")                    # mean beats ai:1; arm order breaks the 2/3 tie
        self.assertEqual(sel["baseline"], "random:1")          # median and mean tie at 2.0: arm order decides
        self.assertIn("MEDIAN", sel["rule"])

    def test_baseline_tie_goes_to_arm_order(self):
        arms = [self.arm("random:1", "random_baseline"), self.arm("heuristic", "heuristic")]
        sel = arena.select_arms(arms, {"random:1": self.rec([2, 2]), "heuristic": self.rec([2, 2])})
        self.assertEqual(sel["baseline"], "random:1")

    def test_errors_excluded_and_listed(self):
        arms = [self.arm("ai:1", "nemotron"), self.arm("ai:2", "nemotron", error="edits rejected"), self.arm("ai:3", "nemotron")]
        sel = arena.select_arms(arms, {"ai:1": self.rec([1, None]), "ai:3": self.rec([4, 4])})
        self.assertEqual(sel["ai"], "ai:3")
        self.assertIn("ai:1", sel["excluded"])
        self.assertIn("ai:2", sel["excluded"])
        self.assertIsNone(sel["baseline"])

    def test_no_ai_arm(self):
        sel = arena.select_arms([self.arm("heuristic", "heuristic")], {"heuristic": self.rec([1, 1])})
        self.assertIsNone(sel["ai"])
        self.assertEqual(sel["baseline"], "heuristic")


class Fakes(unittest.TestCase):
    def setUp(self):
        self.v = load("version_walk.json")
        p = mock.patch.object(arena, "seed_job", fake_seed_job)
        p.start()
        self.addCleanup(p.stop)
        self.adapt = FakeAdapt()
        p2 = mock.patch.object(arena.cw, "adapt_controller", self.adapt)
        p2.start()
        self.addCleanup(p2.stop)

    def run_arena(self, arms=None, c=None, **kw):
        return arena.run_arena(self.v, "walk", arms if arms is not None else arms_walk(), c or cfg(), pool=InlinePool(), **kw)


class Fairness(Fakes):
    def test_retune_applies_to_every_arm_identically(self):
        rec = self.run_arena()
        names = [(c["budget"], tuple(c["train_seeds"]), c["noise_seed"]) for c in self.adapt.calls]
        self.assertEqual(len(self.adapt.calls), 5)            # original + 4 arms, though only ai:P1 asked
        self.assertEqual(set(names), {(48, (301, 302, 303), 77)})
        self.assertTrue(rec["retune"]["applied"])
        self.assertEqual(rec["retune"]["requested_by"], ["ai:P1"])
        for a in rec["arms"]:
            self.assertEqual(a["retune"], {"budget": 48, "noise_seed": 77, "rollouts_used": 51})
            ad = a["controller_provenance"]["walk"]
            self.assertEqual(ad["kind"], "adapted")
            self.assertEqual(ad["adaptation"]["noise_seed"], 77)
        # adaptation rollouts are charged to every arm
        self.assertTrue(all(v["adaptation"] == 51 for v in rec["rollouts"]["per_arm"].values()))

    def test_no_request_no_retune(self):
        rec = self.run_arena(arms_walk(retune=False))
        self.assertEqual(self.adapt.calls, [])
        self.assertFalse(rec["retune"]["applied"])
        self.assertTrue(all(a["retune"] is None for a in rec["arms"]))

    def test_retune_without_budget_is_refused(self):
        with self.assertRaises(ValueError):
            self.run_arena(c=cfg(retune_budget=0))
        with self.assertRaises(ValueError):
            self.run_arena(c=cfg(train_seeds=()))

    def test_retune_ignored_outside_walk(self):
        v = load("version_guided.json")
        arms = [{"arm_id": "ai:P1", "source": "nemotron", "edits": mass_edit(1.2), "retune_controller": True}]
        rec = arena.run_arena(v, "stand", arms, cfg(), pool=InlinePool(), spec_overrides={"duration": 2.0})
        self.assertEqual(self.adapt.calls, [])
        self.assertTrue(rec["notes"])

    def test_edited_walk_vector_is_the_adaptation_start(self):
        lo, hi = iv.control_bounds("walk.balance_gain")
        cur = iv.walk_vector(self.v)[iv.r3.PARAM_NAMES.index("balance_gain")]
        arms = [{"arm_id": "ai:P1", "source": "nemotron", "retune_controller": True,
                 "edits": [Edit("walk.balance_gain", "set", cur + 0.1 * (hi - lo))]}]
        self.run_arena(arms)
        orig_init, ai_init = self.adapt.calls[0]["init"], self.adapt.calls[1]["init"]
        i = iv.r3.PARAM_NAMES.index("balance_gain")
        self.assertNotEqual(orig_init[i], ai_init[i])


class Protocol(Fakes):
    def test_selection_validation_verdicts(self):
        rec = self.run_arena(arms_walk(retune=False))
        sel = rec["selection"]
        self.assertEqual(sel["ai"], "ai:P2")                  # heaviest AI arm has the best screening median
        self.assertEqual(sel["baseline"], "heuristic")
        self.assertEqual(sel["validated"], ["ai:P2", "heuristic"])
        self.assertEqual(set(rec["validation"]), {"original", "ai:P2", "heuristic"})   # screening-only arms are NOT validated
        self.assertEqual(set(rec["screening"]), {"original", "ai:P1", "ai:P2", "random:P1", "heuristic"})
        self.assertEqual(set(rec["verdicts"]), {"ai:P2", "heuristic"})
        v = rec["verdicts"]["ai:P2"]
        self.assertEqual(v["rule"], "verdict_v1")
        self.assertEqual(v["status"], "VERIFIED_IMPROVEMENT")      # +2 kg-score on 8/8 seeds
        self.assertEqual((v["n"], v["wins"]), (8, 8))
        self.assertEqual(rec["verdicts"]["heuristic"]["status"], "NOT_VERIFIED")   # +0.25 on 8/8 seeds: significant but below the 0.5 minimum effect
        self.assertEqual([r["seed"] for r in rec["validation"]["original"]["seeds"]], list(range(201, 209)))
        self.assertEqual([r["seed"] for r in rec["screening"]["ai:P1"]["seeds"]], [101, 102, 103, 104])
        self.assertFalse(set(rec["config"]["screen_seeds"]) & set(rec["config"]["validate_seeds"]))

    def test_n_validate_arms_one(self):
        rec = self.run_arena(arms_walk(retune=False), c=cfg(n_validate_arms=1))
        self.assertEqual(rec["selection"]["validated"], ["ai:P2"])
        self.assertEqual(set(rec["verdicts"]), {"ai:P2"})

    def test_rollout_accounting(self):
        rec = self.run_arena(arms_walk(retune=False))
        per = rec["rollouts"]["per_arm"]
        self.assertEqual(per["original"], {"adaptation": 0, "screening": 4, "validation": 8, "total": 12})
        self.assertEqual(per["ai:P1"]["total"], 4)             # screened only
        self.assertEqual(per["ai:P2"]["total"], 12)
        self.assertEqual(rec["rollouts"]["total"], sum(v["total"] for v in per.values()))
        self.assertIn("wall_s", rec)

    def test_original_added_and_exact_params_recorded(self):
        rec = self.run_arena(arms_walk(retune=False))
        self.assertEqual(rec["arms"][0]["arm_id"], "original")
        a = next(x for x in rec["arms"] if x["arm_id"] == "ai:P2")
        self.assertEqual(a["edits"], [{"param": "torso_mass", "op": "scale", "value": 1.4, "target": "both"}])
        self.assertAlmostEqual(a["body"]["torso_mass"], 7.0)
        self.assertEqual(a["category"], "morphology")
        self.assertEqual(a["source"], "nemotron")
        json.dumps(rec)                                          # JSON-safe

    def test_error_arm_recorded_not_dropped(self):
        arms = arms_walk(retune=False) + [{"arm_id": "ai:bad", "source": "nemotron", "edits": [Edit("foot_length", "scale", 3.0)]}]
        rec = self.run_arena(arms)
        bad = next(a for a in rec["arms"] if a["arm_id"] == "ai:bad")
        self.assertIn("rejected", bad["error"])
        self.assertIsNone(bad["body"])
        self.assertIn("ai:bad", rec["selection"]["excluded"])
        self.assertNotIn("ai:bad", rec["screening"])
        self.assertEqual(rec["selection"]["ai"], "ai:P2")

    def test_error_seed_arm_excluded_from_selection(self):
        # the fake runner returns ERROR for leg_density == 1500: scaling the default 1000 by 1.5 gives exactly that
        arms = [{"arm_id": "ai:err", "source": "nemotron", "edits": [Edit("leg_density", "scale", 1.5)]},
                {"arm_id": "ai:ok", "source": "nemotron", "edits": mass_edit(0.9)}]
        rec = self.run_arena(arms, c=cfg(retune_budget=0))
        self.assertIn("ai:err", rec["selection"]["excluded"])
        self.assertEqual(rec["selection"]["ai"], "ai:ok")
        self.assertTrue(all(r["outcome"] == "ERROR" for r in rec["screening"]["ai:err"]["seeds"]))
        self.assertIsNone(rec["screening"]["ai:err"]["seeds"][0]["score"])
        self.assertEqual(rec["screening"]["ai:err"]["summary"]["errors"], 4)
        self.assertNotIn("ai:err", rec["verdicts"])

    def test_duplicate_and_unknown_arms(self):
        with self.assertRaises(ValueError):
            self.run_arena([{"arm_id": "a", "source": "nemotron", "edits": mass_edit(1.2)}, {"arm_id": "a", "source": "heuristic", "edits": mass_edit(1.1)}])
        with self.assertRaises(ValueError):
            self.run_arena([{"arm_id": "a", "source": "oracle", "edits": mass_edit(1.2)}])

    def test_baselines_only_still_recorded(self):
        rec = self.run_arena([{"arm_id": "heuristic", "source": "heuristic", "edits": mass_edit(1.4)}], c=cfg(retune_budget=0))
        self.assertIsNone(rec["selection"]["ai"])
        self.assertEqual(rec["selection"]["validated"], ["heuristic"])

    def test_emit_and_progress(self):
        events, prog = [], []
        self.run_arena(arms_walk(retune=False), emit=lambda t, d: events.append(t), progress=lambda d, t: prog.append((d, t)))
        self.assertEqual(events[0], "phase")
        self.assertIn("verdict", events)
        self.assertIn("arm_result", events)
        self.assertEqual(prog[-1][0], prog[-1][1])

    def test_model_confidence_is_never_read(self):
        a = arms_walk(retune=False)
        r1 = self.run_arena(copy.deepcopy(a))
        for x in a:
            x["confidence"] = 0.99
        r2 = self.run_arena(a)
        for r in (r1, r2):
            r.pop("wall_s")
        self.assertEqual(r1["verdicts"], r2["verdicts"])
        self.assertEqual(r1["selection"], r2["selection"])


class Variation(Fakes):
    def test_off_by_default_and_matched_when_on(self):
        jobs = []

        def spy(job):
            jobs.append(job)
            return fake_seed_job(job)

        base_perturb = arena.make_spec("walk", (1,)).perturb
        with mock.patch.object(arena, "seed_job", spy):
            arena.run_arena(self.v, "walk", arms_walk(retune=False), cfg(retune_budget=0), pool=InlinePool())
        self.assertEqual({j["spec"]["perturb"] for j in jobs}, {base_perturb})
        self.assertEqual({j["body"]["foot_friction"] for j in jobs}, {1.0})
        jobs.clear()
        c = cfg(retune_budget=0, validation_variation=dict(arena.VARIATION_PRESET))
        with mock.patch.object(arena, "seed_job", spy):
            rec = arena.run_arena(self.v, "walk", arms_walk(retune=False), c, pool=InlinePool())
        val = [j for j in jobs if j["seed"] in range(201, 209)]
        scr = [j for j in jobs if j["seed"] in (101, 102, 103, 104)]
        self.assertEqual({j["spec"]["perturb"] for j in scr}, {base_perturb})          # screening is never varied
        self.assertEqual({j["body"]["foot_friction"] for j in scr}, {1.0})
        self.assertEqual({j["spec"]["perturb"] for j in val}, {base_perturb * 2.0})
        for s in range(201, 209):                                                     # identical conditions for every arm of a seed
            same = [j for j in val if j["seed"] == s]
            self.assertEqual(len({j["spec"]["push_time"] for j in same}), 1)
            self.assertEqual(len({j["body"]["foot_friction"] for j in same}), 1)
        self.assertEqual(len({j["body"]["foot_friction"] for j in val}), 8)           # friction differs between seeds
        for j in val:
            self.assertTrue(0.9 - 1e-9 <= j["body"]["foot_friction"] <= 1.1 + 1e-9)
        self.assertEqual(len(rec["validation_conditions"]), 8)
        self.assertIsNone(self.run_arena(arms_walk(retune=False), c=cfg(retune_budget=0))["validation_conditions"])

    def test_condition_is_pure(self):
        spec = arena.make_spec("push", (1, 2))
        v = arena._check_variation(arena.VARIATION_PRESET)
        self.assertEqual(arena._condition(5, spec, v), arena._condition(5, spec, v))
        self.assertNotEqual(arena._condition(5, spec, v), arena._condition(6, spec, v))


class RealPhysics(unittest.TestCase):
    """A few short real stand rollouts (2 s episodes) on the InlinePool."""

    def setUp(self):
        self.v = load("version_guided.json")
        self.arms = [
            {"arm_id": "ai:P1", "source": "nemotron", "proposal_id": "P1", "edits": [Edit("foot_length", "scale", 1.3)]},
            {"arm_id": "random:P1", "source": "random_baseline", "proposal_id": "P1", "edits": [Edit("leg_density", "scale", 0.8)]},
        ]
        self.cfg = ArenaConfig(screen_seeds=(100501, 100502), validate_seeds=tuple(range(100601, 100607)))

    def test_deterministic_and_matched(self):
        r1 = arena.run_arena(self.v, "stand", self.arms, self.cfg, pool=InlinePool(), spec_overrides={"duration": 2.0})
        r2 = arena.run_arena(self.v, "stand", self.arms, self.cfg, pool=InlinePool(), spec_overrides={"duration": 2.0})
        for r in (r1, r2):
            r.pop("wall_s")
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))
        self.assertEqual(r1["spec"]["validate"]["duration"], 2.0)
        orig = [s["score"] for s in r1["validation"]["original"]["seeds"]]
        self.assertEqual(len(orig), 6)
        self.assertTrue(all(x is not None for x in orig))
        for a in r1["selection"]["validated"]:
            self.assertEqual(r1["verdicts"][a]["n"], 6)
        # the original arm equals the arm built from no edits: A/A on the same seeds is all ties, never VERIFIED
        self.assertEqual(r1["arms"][0]["controllers"]["stand"], iv.stand_params(self.v))

    def test_a_a_pairs_are_ties(self):
        from creature_forge import verdict as vd
        r = arena.run_arena(self.v, "stand", self.arms[:1], self.cfg, pool=InlinePool(), spec_overrides={"duration": 2.0})
        o = [s["score"] for s in r["validation"]["original"]["seeds"]]
        a = vd.verdict("stand", o, list(o), resolution=arena.resolution_for("stand", arena.make_spec("stand", self.cfg.validate_seeds)))
        self.assertNotEqual(a["status"], "VERIFIED_IMPROVEMENT")
        self.assertEqual(a["ties"], 6)


if __name__ == "__main__":
    unittest.main()
