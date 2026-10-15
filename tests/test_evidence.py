"""Evidence pack: size, structure, determinism, citation resolution (docs/FORGE_LOOP_CONTRACTS.md section 5.1)."""
import copy
import json
import unittest
from pathlib import Path

from creature_forge import evidence as ev

FX = Path(__file__).parent / "fixtures" / "forge_ai"
HISTORY = [{"round": i, "category": "morphology", "summary": f"foot x1.{i}", "verdict": {"status": "NOT_VERIFIED", "median_diff": 0.1 * i},
            "nested": {"a": {"b": {"c": 1}}}} for i in range(1, 9)]


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


class PackTests(unittest.TestCase):
    def setUp(self):
        self.cases = {"push": (load("version_guided.json"), load("challenge_push.json")),
                      "stand": (load("version_experimental.json"), load("challenge_stand.json")),
                      "walk": (load("version_walk.json"), load("challenge_walk.json"))}

    def pack(self, kind, history=None):
        v, c = self.cases[kind]
        return ev.build_evidence(v, c, history)

    def test_size_limit_all_challenges(self):
        for kind in self.cases:
            for hist in (None, HISTORY):
                p = self.pack(kind, hist)
                self.assertLessEqual(ev.pack_size(p), 6144, kind)
                self.assertLessEqual(ev.pack_size(p), ev.PACK_LIMIT_BYTES, kind)
                self.assertNotIn("truncated", p)

    def test_stable_top_level_keys(self):
        p = self.pack("push", HISTORY)
        for k in ("creature", "challenge", "controller", "outcome", "seeds", "forensics", "history", "bounds"):
            self.assertIn(k, p)
        self.assertEqual(p["challenge"]["kind"], "push")
        self.assertEqual(p["challenge"]["target_force"], 25.0)
        self.assertEqual(p["challenge"]["seeds_n"], 8)
        self.assertNotIn("target_force", self.pack("stand")["challenge"])

    def test_creature_block_uses_rear_front_names(self):
        p = self.pack("stand")
        b = p["creature"]["body"]
        self.assertEqual(b["rear"], {"thigh_length": 0.35, "shank_length": 0.25, "foot_length": 0.08})
        self.assertEqual(b["front"], {"thigh_length": 0.3, "shank_length": 0.28, "foot_length": 0.1})
        self.assertEqual(p["creature"]["mode"], "experimental")
        self.assertEqual(p["creature"]["start"]["torso_pitch"], 0.12)          # drawn start with a lean
        d = p["creature"]["derived"]
        self.assertAlmostEqual(d["leg_length_rear"], 0.6)
        self.assertAlmostEqual(d["leg_length_front"], 0.58)
        self.assertAlmostEqual(d["foot_to_leg"], round((0.08 + 0.1) / 2 / 0.59, 4), places=4)
        self.assertNotIn("start", self.pack("push")["creature"])               # zero pose: nothing to report

    def test_derived_mass_comes_from_mujoco(self):
        d = self.pack("push")["creature"]["derived"]
        self.assertGreater(d["mass_total"], 1.0)
        self.assertAlmostEqual(d["weight_n"], d["mass_total"] * 9.81, delta=0.01)
        leg = (d["leg_length_rear"] + d["leg_length_front"]) / 2
        self.assertAlmostEqual(d["torque_to_weight"], 60.0 / (d["weight_n"] * leg), delta=0.005)

    def test_seeds_ordered_worst_to_best_and_limited(self):
        p = self.pack("push")
        scores = [s["score"] for s in p["seeds"]]
        self.assertLessEqual(len(scores), 6)
        self.assertEqual(scores, sorted(scores))
        all_scores = sorted(s["score"] for s in self.cases["push"][1]["per_seed"])
        self.assertEqual(scores[0], round(all_scores[0], 4))                    # seeds[0] is the worst
        self.assertEqual(scores[-1], round(all_scores[-1], 4))                  # and the last one the best
        for s in p["seeds"]:
            self.assertIn("critical_force_bwd", s["metrics"])
            self.assertNotIn("bisection_trace", s["metrics"])                   # containers are not metrics

    def test_few_seeds_all_kept(self):
        v, c = self.cases["stand"]
        c = copy.deepcopy(c)
        c["per_seed"] = c["per_seed"][:3]
        p = ev.build_evidence(v, c)
        self.assertEqual(len(p["seeds"]), 3)
        self.assertEqual(p["challenge"]["seeds_n"], 3)

    def test_outcome_block_recomputed_from_seeds(self):
        p = self.pack("walk")
        per = self.cases["walk"][1]["per_seed"]
        self.assertEqual(sum(p["outcome"]["counts"].values()), len(per))
        self.assertEqual(p["outcome"]["counts"]["FAIL"], sum(1 for s in per if s["outcome"] == "FAIL"))
        self.assertEqual(p["outcome"]["aggregate"], self.cases["walk"][1]["outcome"])
        self.assertLessEqual(p["outcome"]["score"]["min"], p["outcome"]["score"]["median"])
        self.assertLessEqual(p["outcome"]["score"]["median"], p["outcome"]["score"]["max"])

    def test_events_are_compact(self):
        p = self.pack("stand")
        evs = [e for s in p["seeds"] for e in s.get("events", [])]
        self.assertTrue(evs)
        for e in evs:
            self.assertEqual(set(e), {"kind", "time"})

    def test_forensics_compacted(self):
        p = self.pack("push")
        f = p["forensics"]
        self.assertNotIn("definitions", f)
        self.assertIn("support", f)
        self.assertLessEqual(len(f["timeline"]["rows"]), 4)
        self.assertEqual(f["timeline"]["rows"][0][0], 0.9)                      # first row kept
        self.assertEqual(f["timeline"]["rows"][-1][0], 2.2)                     # and the last (rows spread evenly)
        self.assertLessEqual(len(f["contacts"]["transitions"]), 5)
        self.assertNotIn("xcom_margin_recovered_s", f["failure"])               # null values dropped

    def test_controller_blocks(self):
        s = self.pack("push")["controller"]
        self.assertEqual(set(s), {"stand"})
        self.assertEqual(s["stand"]["kp"], 150.0)
        self.assertFalse(s["stand"]["edited"])
        w = self.pack("walk")["controller"]
        self.assertEqual(set(w), {"walk"})
        self.assertEqual(w["walk"]["kind"], "r2-transfer")
        self.assertEqual(len(w["walk"]["params"]), 15)

    def test_bounds_follow_mode_and_challenge(self):
        g = self.pack("push")["bounds"]
        self.assertEqual((g["foot_length"]["lo"], g["foot_length"]["hi"]), (0.06, 0.3))
        self.assertEqual((g["foot_length"]["rear"], g["foot_length"]["front"]), (0.16, 0.16))
        self.assertEqual(g["torso_mass"]["current"], 5.0)
        self.assertIn("kp", g["stand"])
        self.assertNotIn("walk", g)
        x = self.pack("stand")["bounds"]
        self.assertEqual((x["foot_length"]["lo"], x["foot_length"]["hi"]), (0.02, 0.6))
        self.assertEqual((x["foot_length"]["rear"], x["foot_length"]["front"]), (0.08, 0.1))
        w = self.pack("walk")["bounds"]
        self.assertIn("freq", w["walk"])
        self.assertNotIn("stand", w)
        self.assertEqual(set(w["walk"]["freq"]), {"lo", "hi", "current", "u"})

    def test_history_trimmed_and_scalar_only(self):
        p = self.pack("push", HISTORY)
        self.assertLessEqual(len(p["history"]), ev.MAX_HISTORY)
        self.assertEqual(p["history"][-1]["round"], 8)                          # most recent entries are kept
        self.assertEqual(p["history"][-1]["verdict"]["status"], "NOT_VERIFIED")
        self.assertNotIn("nested", p["history"][-1])                            # containers nested deeper than two levels are dropped
        self.assertNotIn("history", self.pack("push"))

    def test_no_none_nan_and_json_safe(self):
        for kind in self.cases:
            text = json.dumps(self.pack(kind, HISTORY), allow_nan=False)
            self.assertNotIn("null", text)

    def test_deterministic_and_inputs_untouched(self):
        v, c = self.cases["push"]
        v0, c0 = copy.deepcopy(v), copy.deepcopy(c)
        a, b = ev.build_evidence(v, c, HISTORY), ev.build_evidence(v, c, HISTORY)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual((v, c), (v0, c0))

    def test_oversized_forensics_shrinks_to_limit(self):
        v, c = self.cases["push"]
        c = copy.deepcopy(c)
        c["forensics"] = {f"group{i}": {f"metric{j}": 0.123456789 * j for j in range(20)} for i in range(30)}
        p = ev.build_evidence(v, c, HISTORY)
        self.assertLessEqual(ev.pack_size(p), ev.PACK_LIMIT_BYTES)
        self.assertLessEqual(len(json.dumps(p["forensics"], separators=(",", ":"))), ev.LEVELS[0].fx_bytes)
        self.assertIn("seeds", p)
        self.assertNotIn("truncated", p)

    def test_error_seed_is_reported_not_hidden(self):
        v, c = self.cases["stand"]
        c = copy.deepcopy(c)
        c["per_seed"][0].update(outcome="ERROR", error="MuJoCo could not compile this body: boom", score=0.0)
        p = ev.build_evidence(v, c)
        self.assertEqual(p["outcome"]["counts"]["ERROR"], 1)
        errs = [s for s in p["seeds"] if s["outcome"] == "ERROR"]
        self.assertTrue(errs and "boom" in errs[0]["error"])


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.p = {"seeds": [{"score": 1.5, "metrics": {"fell": True, "weak": "bwd"}}, {"score": 2}], "forensics": {"timeline": {"rows": [[0.1, 0.2], [0.3, 0.4]]}},
                  "a": {"b": 3}, "nan": float("nan"), "none": None, "empty": [], "x.y": 1}

    def test_scalars_resolve(self):
        r = lambda path: ev.resolve(self.p, path)
        self.assertEqual(r("seeds[0].score"), 1.5)
        self.assertEqual(r("seeds[1].score"), 2)
        self.assertIs(r("seeds[0].metrics.fell"), True)
        self.assertEqual(r("seeds[0].metrics.weak"), "bwd")
        self.assertEqual(r("forensics.timeline.rows[1][0]"), 0.3)
        self.assertEqual(r("a.b"), 3)
        self.assertEqual(r("seeds.0.score"), 1.5)                   # dotted integer also accepted
        self.assertEqual(r("  a.b "), 3)

    def test_non_scalars_and_garbage_rejected(self):
        for path in ("seeds", "seeds[0]", "seeds[0].metrics", "forensics.timeline.rows", "forensics.timeline.rows[0]", "empty", "none", "nan",
                     "seeds[2].score", "seeds[0].nope", "nope", "a.b.c", "seeds[0", "seeds[a]", "", "   ", ".", "a..b", "seeds[0].score: 1.5",
                     "seeds[0].score=1.5", "seeds[-1].score", "seeds[0][0]", "a[0]"):
            with self.assertRaises(ev.UnresolvedCitation, msg=path):
                ev.resolve(self.p, path)

    def test_non_string_path(self):
        for bad in (None, 3, ["a"]):
            with self.assertRaises(ev.UnresolvedCitation):
                ev.resolve(self.p, bad)

    def test_try_resolve(self):
        self.assertEqual(ev.try_resolve(self.p, "a.b"), (True, 3))
        ok, why = ev.try_resolve(self.p, "a")
        self.assertFalse(ok)
        self.assertIn("single value", why)

    def test_unresolved_is_a_valueerror(self):
        self.assertTrue(issubclass(ev.UnresolvedCitation, ValueError))


class LeafPathTests(unittest.TestCase):
    def test_every_leaf_path_resolves_to_its_value(self):
        for ver, ch in (("version_guided.json", "challenge_push.json"), ("version_experimental.json", "challenge_stand.json"),
                        ("version_walk.json", "challenge_walk.json")):
            p = ev.build_evidence(load(ver), load(ch), HISTORY)
            items = ev.leaf_items(p)
            self.assertGreater(len(items), 50)
            self.assertEqual(len({k for k, _ in items}), len(items))
            for path, value in items:
                self.assertEqual(ev.resolve(p, path), value, path)

    def test_bounds_excluded_by_default_but_still_resolvable(self):
        p = ev.build_evidence(load("version_guided.json"), load("challenge_push.json"))
        paths = ev.leaf_paths(p)
        self.assertFalse(any(x.startswith("bounds") for x in paths))
        self.assertTrue(any(x.startswith("bounds") for x in ev.leaf_paths(p, exclude=())))
        self.assertEqual(ev.resolve(p, "bounds.foot_length.hi"), 0.3)

    def test_includes_seed_metrics_and_forensics(self):
        paths = ev.leaf_paths(ev.build_evidence(load("version_guided.json"), load("challenge_push.json")))
        for needle in ("seeds[0].score", "seeds[0].metrics.critical_force_bwd", "forensics.support.min_xcom_margin_after_push_m", "outcome.aggregate",
                       "creature.body.rear.foot_length", "controller.stand.kp"):
            self.assertIn(needle, paths)


if __name__ == "__main__":
    unittest.main()
