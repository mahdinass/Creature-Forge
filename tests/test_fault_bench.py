import json
import os
import sys
import tempfile
import unittest

from creature_forge import eng_tools as et
from creature_forge import fault_bench as fb
from creature_forge.phasegait_fp import LOWER17, UPPER17
from creature_forge.walk_opt import ALL_NAMES

BODY = {"torso_mass": 5.0, "thigh_length": 0.4, "shank_length": 0.4, "foot_length": 0.16, "thigh_length_r": 0.4,
        "shank_length_r": 0.4, "foot_length_r": 0.16, "foot_friction": 1.0, "torque_limit": 60.0, "leg_density": 1000.0,
        "pose": [0.0] * 7}
# a mid-range 17-D vector (inside the controller bounds) with foot placement in use
VEC = [float(0.5 * (lo + hi)) for lo, hi in zip(LOWER17, UPPER17)]
VEC[ALL_NAMES.index("fp_kd")] = 0.4
VEC[ALL_NAMES.index("fp_kv")] = 0.3
BASE = {"base_id": "b0", "creature": "b0", "source_unit": "u", "body": BODY, "vector": VEC, "features": {}, "region": "L1-f1-t0-q1"}


def fake_cma(log=None, improve=True):
    """cma_search stand-in: uses the initial point + all whole generations that fit; best differs from init."""
    def fn(body, vector, space, *, budget, train_seeds, noise_seed, pool=None, variation=None):
        S = len(train_seeds)
        lam = max(2, 4 + int(3 * __import__("math").log(space.dim)))
        gens = (budget - S) // (lam * S)
        used = S + gens * lam * S
        if log is not None:
            log.append({"dims": space.to_dict(), "budget": budget, "seeds": list(train_seeds), "used": used})
        init = {"body": dict(body), "vector": list(vector), "walking_count": 0, "survival_count": 0, "mean_fitness": 0.1}
        best = dict(init)
        if improve:
            v = list(vector)
            v[0] += 1e-3                                   # a different design than the start
            best.update(walking_count=S, survival_count=S, mean_fitness=0.9, vector=v)
        return {"best": best, "init": init, "rollouts_used": used, "budget": budget}
    return fn


def fake_observe(log=None):
    def fn(body, vector, seeds, *, mechanisms=(), variation=None, duration=10.0, pool=None):
        if log is not None:
            log.append({"seeds": list(seeds), "body": dict(body), "vector": list(vector)})
        return {"per_seed": [{} for _ in seeds], "median": {"support_margin": body["foot_length"] * 2 + vector[0] * 0,
                                                            "label": "x"},
                "rollouts": len(seeds), "n_fell": len(seeds), "n_walking": 0}
    return fn


def seeds_for(n=8):
    s = fb.instance_seeds("camp", "b0", "short_feet", 0.5)
    return {"train": s["train"], "obs": s["obs"]}


class FaultTransformTests(unittest.TestCase):
    def test_exact_ranges(self):
        cases = {"posture_lean": ("pitch_ref", lambda b, v, x: x - v, (0.05, 0.20), "add"),
                 "cadence_fast": ("freq", lambda b, v, x: x / v, (1.2, 1.6), "scale")}
        for fault, (p, f, rng, kind) in cases.items():
            i = ALL_NAMES.index(p)
            base = {**BASE, "vector": list(VEC)}
            base["vector"][i] = (LOWER17[i] + UPPER17[i]) / 2 * 0.5
            for s, want in ((0.0, rng[0]), (1.0, rng[1]), (0.5, (rng[0] + rng[1]) / 2)):
                out = fb.inject(base, fault, s)
                self.assertTrue(out["valid"], out["reason"])
                self.assertAlmostEqual(f(None, base["vector"][i], out["vector"][i]), want, places=9)
                self.assertEqual([x for j, x in enumerate(out["vector"]) if j != i],
                                 [x for j, x in enumerate(base["vector"]) if j != i])

    def test_body_and_feedback_faults(self):
        base = {**BASE, "vector": list(VEC)}
        o = fb.inject(base, "short_feet", 1.0)
        self.assertAlmostEqual(o["body"]["foot_length"], 0.16 * 0.55)
        self.assertAlmostEqual(o["body"]["foot_length_r"], 0.16 * 0.55)
        o = fb.inject(base, "heavy_torso", 0.0)
        self.assertAlmostEqual(o["body"]["torso_mass"], 7.0)
        o = fb.inject(base, "weak_motors", 1.0)
        self.assertAlmostEqual(o["body"]["torque_limit"], 15.0)
        o = fb.inject(base, "slippery", 1.0)
        self.assertAlmostEqual(o["body"]["foot_friction"], 0.08)
        o = fb.inject(base, "feedback_loss", 1.0)
        for n in ("balance_gain", "pitch_kp"):
            i = ALL_NAMES.index(n)
            self.assertAlmostEqual(o["vector"][i], base["vector"][i] * 0.1)
        self.assertEqual(o["body"], fb.full_body(BODY))
        self.assertEqual(base["body"], BODY)        # inputs untouched

    def test_out_of_bounds_is_invalid_never_clipped(self):
        b = {**BASE, "body": {**BODY, "foot_length": 0.07, "foot_length_r": 0.07}}
        o = fb.inject(b, "short_feet", 1.0)               # 0.0385 < 0.06
        self.assertFalse(o["valid"])
        self.assertIsNone(o["body"])
        self.assertIn("guided bounds", o["reason"])
        b = {**BASE, "body": {**BODY, "torso_mass": 9.0}}
        self.assertFalse(fb.inject(b, "heavy_torso", 1.0)["valid"])      # 18 kg > 15
        self.assertTrue(fb.inject(b, "heavy_torso", 0.0)["valid"])       # 9 * 1.4 = 12.6 kg is inside
        b = {**BASE, "body": {**BODY, "foot_friction": 0.3}}
        self.assertFalse(fb.inject(b, "slippery", 1.0)["valid"])         # 0.024 < 0.05
        v = list(VEC)
        i = ALL_NAMES.index("freq")
        v[i] = UPPER17[i] * 0.9
        self.assertFalse(fb.inject({**BASE, "vector": v}, "cadence_fast", 0.0)["valid"])

    def test_placement_loss_validity(self):
        o = fb.inject(BASE, "placement_loss", 0.7)
        self.assertTrue(o["valid"])
        self.assertEqual(o["vector"][ALL_NAMES.index("fp_kd")], 0.0)
        self.assertEqual(o["vector"][ALL_NAMES.index("fp_kv")], 0.0)
        v = list(VEC)
        v[ALL_NAMES.index("fp_kd")] = 0.05
        v[ALL_NAMES.index("fp_kv")] = 0.0
        o = fb.inject({**BASE, "vector": v}, "placement_loss", 0.5)
        self.assertFalse(o["valid"])
        self.assertIn("foot placement", o["reason"])
        v[ALL_NAMES.index("fp_kv")] = 0.06
        self.assertTrue(fb.inject({**BASE, "vector": v}, "placement_loss", 0.5)["valid"])

    def test_catalogue_complete(self):
        self.assertEqual(set(fb.FAULTS), set(fb.FAULT_DOCS))
        for f, t in fb.MATCHING_TOOL.items():
            self.assertIn(t, fb.TOOLS)
        self.assertEqual(len(set(fb.MATCHING_TOOL.values())), len(fb.FAULTS))
        with self.assertRaises(ValueError):
            fb.inject(BASE, "nope", 0.5)
        with self.assertRaises(ValueError):
            fb.inject(BASE, "short_feet", 1.5)


class ToolTests(unittest.TestCase):
    def test_tool_dims(self):
        self.assertEqual(fb.tool_dims("posture")["ctrl_params"], ["hip_bias", "pitch_ref", "stance_knee", "start_lean"])
        self.assertEqual(fb.tool_dims("placement")["ctrl_params"], ["fp_kd", "fp_kv"])
        self.assertEqual(fb.tool_dims("leg_length")["body_params"], ["thigh_length", "shank_length"])
        self.assertEqual(fb.tool_dims("torque_limit")["dim"], 1)
        ctrl = [fb.tool_dims(t)["ctrl_params"] for t in fb.CONTROL_TOOLS]
        self.assertEqual(sum(len(c) for c in ctrl), 17)
        sp = et.tool_space("leg_length")
        self.assertEqual(sp.body_params, ("thigh_length", "shank_length"))
        self.assertTrue(sp.uses_fp)                         # 17-D vectors even for body-only tools
        self.assertEqual(sp.body_ratio, (0.5, 1.5))
        self.assertEqual(sp.mode, "guided")


class WorkbenchTests(unittest.TestCase):
    def bench(self, total=400, **kw):
        self.olog, self.clog = [], []
        return et.Workbench({"body": BODY, "vector": VEC}, total_budget=total, seeds=seeds_for(), n_train=4, n_obs=4,
                            observe_fn=fake_observe(self.olog), cma_fn=fake_cma(self.clog), **kw)

    def test_observe_charges_and_ledger_sums(self):
        wb = self.bench()
        r = wb.observe()
        self.assertTrue(r["ok"])
        self.assertEqual(wb.remaining, 396)
        wb.counterfactual("foot_length_x1.3")        # current design already observed: only the change (4)
        led = wb.ledger()
        self.assertEqual(led["used"], sum(l["n"] for l in led["lines"]))
        self.assertEqual(led["used"], 8)                         # observe 4 + counterfactual 4
        self.assertEqual(led["used"], wb.budget.total - wb.remaining)
        wb.counterfactual("torso_mass_x0.75")        # current already observed: 4 only
        self.assertEqual(wb.ledger()["used"], 4 + 4 + 4)
        wb2 = self.bench()
        wb2.counterfactual("foot_length_x1.3")       # not observed yet: observes the current design first, charged separately
        self.assertEqual(wb2.ledger()["used"], 8)
        self.assertEqual([l["item"] for l in wb2.ledger()["lines"]], ["observe", "counterfactual"])
        self.assertTrue(all(o["seeds"] == wb.obs_seeds for o in self.olog))     # same obs seeds every time

    def test_counterfactual_applies_change_and_deltas(self):
        wb = self.bench()
        r = wb.counterfactual("foot_length_x1.3")
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(self.olog[-1]["body"]["foot_length"], 0.16 * 1.3)
        self.assertAlmostEqual(r["deltas_vs_current"]["support_margin"], 0.16 * 0.3 * 2)
        self.assertNotIn("label", r["deltas_vs_current"])
        self.assertEqual(wb.best_design()["body"]["foot_length"], 0.16)          # the bench did not adopt the change

    def test_counterfactual_catalogue_bounds(self):
        self.assertEqual(len(et.COUNTERFACTUALS), 9)
        for cid, changes in et.COUNTERFACTUALS.items():
            body, vec = fb.apply_changes({**BODY, "foot_friction": 0.6}, VEC, changes)        # all available for a mid-range robot
            self.assertEqual(len(vec), 17)
        wb = self.bench()
        wb.designs[0]["body"]["foot_length"] = 0.25                 # x1.3 = 0.325 > 0.30 -> unavailable, never clipped
        wb.designs[0]["body"]["foot_length_r"] = 0.25
        before = wb.remaining
        r = wb.counterfactual("foot_length_x1.3")
        self.assertFalse(r["ok"])
        self.assertIn("unavailable", r["refused"])
        self.assertEqual(wb.remaining, before)
        self.assertEqual(self.olog, [])
        self.assertFalse(wb.counterfactual("not_in_catalogue")["ok"])
        self.assertFalse(wb.counterfactual({"id": "bogus"})["ok"])

    def test_budget_never_exceeded(self):
        wb = self.bench(total=30)
        self.assertTrue(wb.observe()["ok"])
        r = wb.repair("timing", 30)
        self.assertFalse(r["ok"])                                    # minimum is 4*(1+3*7)=88
        self.assertTrue(wb.observe()["ok"])
        for _ in range(10):
            wb.observe()
        self.assertLessEqual(wb.ledger()["used"], 30)
        self.assertEqual(wb.remaining, 30 - 7 * 4)
        self.assertFalse(wb.observe()["ok"])
        self.assertFalse(wb.counterfactual("freq_x0.85")["ok"])
        self.assertEqual(len(self.olog), 7)

    def test_repair_refund_refusal_and_best(self):
        wb = self.bench(total=300)
        need = et.min_repair_budget("timing", 4)
        self.assertEqual(need, 4 * (1 + 3 * 7))
        r = wb.repair("timing", need - 1)
        self.assertFalse(r["ok"])
        self.assertEqual(wb.ledger()["used"], 0)
        self.assertFalse(wb.repair("timing", 10_000)["ok"])          # more than remains
        self.assertFalse(wb.repair("unknown_tool", 200)["ok"])
        r = wb.repair("timing", 150)                                 # fake cma stops at whole generations: 4 + 5*28 = 144
        self.assertTrue(r["ok"])
        self.assertEqual(r["rollouts_used"], 144)
        led = wb.ledger()
        self.assertEqual(led["used"], 144)                           # 150 charged, 6 refunded
        self.assertEqual(sum(l["n"] for l in led["lines"]), 144)
        self.assertEqual(self.clog[-1]["dims"]["ctrl_params"], ["freq", "duty", "knee_shift"])
        self.assertEqual(self.clog[-1]["seeds"], wb.train_seeds)
        self.assertEqual(wb.best_design()["source"], "repair:timing")
        self.assertEqual(r["best"]["train_walking"], 4)
        self.assertEqual(wb.remaining, 156)

    def test_repair_error_refunds(self):
        def boom(*a, **k):
            raise RuntimeError("sim crashed")
        wb = et.Workbench({"body": BODY, "vector": VEC}, total_budget=200, seeds=seeds_for(), cma_fn=boom,
                          observe_fn=fake_observe())
        with self.assertRaises(RuntimeError):
            wb.repair("timing", 100)
        self.assertEqual(wb.ledger()["used"], 0)

    def test_train_obs_disjoint_and_required(self):
        s = seeds_for()
        with self.assertRaises(ValueError):
            et.Workbench({"body": BODY, "vector": VEC}, total_budget=10, seeds={"train": [1, 2, 3, 4], "obs": [4, 5, 6, 7]})
        with self.assertRaises(ValueError):
            et.Workbench({"body": BODY, "vector": VEC}, total_budget=10, seeds={"train": s["train"]})


class InstanceTests(unittest.TestCase):
    def test_seed_roles_disjoint(self):
        s = fb.instance_seeds("camp", "b0", "short_feet", 0.5)
        self.assertEqual({k: len(v) for k, v in s.items()}, fb.SEED_COUNTS)
        allv = [x for v in s.values() for x in v]
        self.assertEqual(len(allv), len(set(allv)))
        fb.assert_disjoint_roles(s)
        bad = dict(s)
        bad["obs"] = [s["validate"][0]] + s["obs"][1:]
        with self.assertRaises(ValueError):
            fb.assert_disjoint_roles(bad)
        self.assertEqual(s, fb.instance_seeds("camp", "b0", "short_feet", 0.5))            # deterministic
        self.assertNotEqual(s["check"], fb.instance_seeds("camp", "b0", "short_feet", 0.75)["check"])

    def test_verify_uses_only_validate_confirm(self):
        inst = {"instance_id": "x", "robot": {"body": BODY, "vector": VEC},
                "seeds": fb.instance_seeds("camp", "b0", "short_feet", 0.5)}
        seen = {}

        def assess(original, candidate, validate_seeds, confirm_seeds, pool=None):
            seen.update(v=list(validate_seeds), c=list(confirm_seeds), orig=original)
            return {"status": "FULL_RECOVERY"}
        out = fb.verify(inst, {"body": BODY, "vector": VEC}, None, assess_fn=assess)
        self.assertEqual(out["status"], "FULL_RECOVERY")
        s = inst["seeds"]
        self.assertEqual(seen["v"], s["validate"])
        self.assertEqual(seen["c"], s["confirm"])
        self.assertEqual(seen["orig"], inst["robot"])
        used = set(seen["v"]) | set(seen["c"])
        self.assertFalse(used & (set(s["check"]) | set(s["train"]) | set(s["obs"])))
        inst["seeds"] = {**s, "obs": s["obs"][:-1] + [s["validate"][3]]}
        with self.assertRaises(ValueError):
            fb.verify(inst, {"body": BODY, "vector": VEC}, None, assess_fn=assess)

    def test_policy_view_hides_truth(self):
        inst = fb.build_instance(BASE, "short_feet", 0.5, "camp", cma_fn=fake_cma(), walk_fn=self.walk_fn(0, 8))
        v = fb.policy_view(inst)
        txt = json.dumps(v)
        self.assertNotIn("short_feet", txt)
        self.assertEqual(set(v["seeds"]), {"train", "obs"})
        self.assertEqual(v["robot"]["body"], inst["robot"]["body"])

    @staticmethod
    def walk_fn(faulty_walking, repaired_walking, per_tool=None):
        """walk stand-in: the faulty robot (foot_length 0.16*0.65) walks on `faulty_walking` seeds; others per tool result."""
        def fn(body, vector, seeds, duration=10.0, variation=None, pool=None):
            faulty = abs(body["foot_length"] - 0.104) < 1e-9 and list(vector) == VEC
            k = faulty_walking if faulty else repaired_walking
            if per_tool is not None and not faulty:
                k = per_tool(body, vector)
            return [{"seed": s, "outcome": "PASS" if i < k else "FAIL", "walking": i < k} for i, s in enumerate(seeds)]
        return fn

    def test_build_instance_matrix(self):
        calls = []
        base_cma = fake_cma(calls)

        def cma(body, vector, space, **kw):
            res = base_cma(body, vector, space, **kw)
            if space.body_params == ("foot_length",):                     # only the matching tool changes the design
                res["best"]["body"] = {**body, "foot_length": body["foot_length"] * 1.4, "foot_length_r": body["foot_length_r"] * 1.4}
            return res
        walk = self.walk_fn(1, 0, per_tool=lambda b, v: 7 if b["foot_length"] > 0.12 else 1)
        rec = fb.build_instance(BASE, "short_feet", 0.5, "camp", None, budget=160, cma_fn=cma, walk_fn=walk)
        self.assertTrue(rec["valid"])
        self.assertTrue(rec["kept"], rec["reason"])
        self.assertEqual(set(rec["repair_matrix"]), set(fb.TOOLS))
        self.assertEqual(rec["repair_matrix"]["foot_length"], 7 / 8)
        self.assertEqual(rec["repair_matrix"]["timing"], 1 / 8)
        self.assertEqual(rec["ranking"][0], "foot_length")
        self.assertEqual(rec["n_tools_that_repair"], 1)
        self.assertEqual(rec["matching_tool"], "foot_length")
        self.assertEqual(len(calls), len(fb.TOOLS))
        self.assertTrue(all(c["budget"] == 160 and c["seeds"] == rec["seeds"]["train"][:4] for c in calls))
        self.assertEqual(rec["rollouts"], 8 + sum(c["used"] for c in calls) + 8 * len(fb.TOOLS))
        self.assertAlmostEqual(rec["robot"]["body"]["foot_length"], 0.104)

    def test_build_instance_rejections(self):
        # faulty robot still walks -> not kept, no repair attempted
        calls = []
        rec = fb.build_instance(BASE, "short_feet", 0.5, "camp", None, cma_fn=fake_cma(calls), walk_fn=self.walk_fn(5, 8))
        self.assertTrue(rec["valid"])
        self.assertFalse(rec["kept"])
        self.assertIn("still walks", rec["reason"])
        self.assertEqual(calls, [])
        # matching tool does not repair -> not kept
        rec = fb.build_instance(BASE, "short_feet", 0.5, "camp", None, cma_fn=fake_cma(), walk_fn=self.walk_fn(0, 3))
        self.assertFalse(rec["kept"])
        self.assertIn("matching tool", rec["reason"])
        # all tools repair -> kept, ambiguity recorded
        rec = fb.build_instance(BASE, "short_feet", 0.5, "camp", None, cma_fn=fake_cma(), walk_fn=self.walk_fn(0, 8))
        self.assertTrue(rec["kept"])
        self.assertEqual(rec["n_tools_that_repair"], len(fb.TOOLS))
        # invalid injection
        rec = fb.build_instance({**BASE, "body": {**BODY, "foot_friction": 0.3}}, "slippery", 1.0, "camp",
                                cma_fn=fake_cma(), walk_fn=self.walk_fn(0, 8))
        self.assertFalse(rec["valid"])
        self.assertIn("bounds", rec["reason"])
        self.assertNotIn("repair_matrix", rec)

    def test_load_bases_from_records(self):
        with tempfile.TemporaryDirectory() as d:
            for sub, pat in (("experiments/walk_recovery/confirmatory/results", "shard0.jsonl"),):
                os.makedirs(os.path.join(d, sub))
                with open(os.path.join(d, sub, pat), "w", encoding="utf-8") as fh:
                    def rec(creature, method, status, unit):
                        return json.dumps({"unit": unit, "creature": creature, "method": method, "status": status,
                                           "features": {"L": 1.0}, "region": "L1-f0-t0-q0",
                                           "pipeline": {"final": {"body": BODY, "vector": VEC}}})
                    fh.write(rec("c1", "rand", "FULL_RECOVERY", "c1|rand|2000|1") + "\n")
                    fh.write(rec("c1", "fix", "FULL_RECOVERY", "c1|fix|2000|1") + "\n")
                    fh.write(rec("c1", "ai", "PARTIAL_IMPROVEMENT", "c1|ai|2000|1") + "\n")
                    fh.write(rec("c2", "ai", "NOT_RECOVERED", "c2|ai|2000|1") + "\n")
            bases = fb.load_bases("heldout", root=d)
        self.assertEqual([b["base_id"] for b in bases], ["c1"])
        self.assertEqual(bases[0]["source_unit"], "c1|fix|2000|1")
        self.assertEqual(len(bases[0]["vector"]), 17)
        self.assertEqual(fb.base_families(bases), {"c1": "L1-f0-t0-q0"})

    def test_real_records_load(self):
        dev, held = fb.load_bases("dev"), fb.load_bases("heldout")
        self.assertGreaterEqual(len(dev), 10)
        self.assertGreaterEqual(len(held), 20)
        self.assertFalse({b["base_id"] for b in dev} & {b["base_id"] for b in held})
        for b in dev + held:
            self.assertEqual(len(b["vector"]), 17)
            self.assertTrue(all(lo <= x <= hi for x, lo, hi in zip(b["vector"], LOWER17, UPPER17)))


@unittest.skipIf(sys.platform == "win32" or os.environ.get("CF_NO_MUJOCO"), "MuJoCo smoke runs on the VM only")
class MuJocoSmoke(unittest.TestCase):
    def test_one_instance_end_to_end(self):
        from creature_forge.forge_pool import ForgePool
        base = fb.load_bases("dev")[0]
        with ForgePool(max_workers=int(os.environ.get("CF_WORKERS", "2"))) as pool:
            rec = fb.build_instance(base, "short_feet", 0.5, "cebench-smoke", pool, budget=64, n_train=2, n_check=4)
        print("SMOKE", json.dumps({k: rec.get(k) for k in ("instance_id", "valid", "kept", "reason", "faulty_check",
                                                           "repair_matrix", "ranking", "n_tools_that_repair", "rollouts")}))
        self.assertTrue(rec["valid"] or rec["reason"])
        if rec["valid"] and "repair_matrix" in rec:
            self.assertEqual(set(rec["repair_matrix"]) | set(rec["repair_detail"]), set(fb.TOOLS))


if __name__ == "__main__":
    unittest.main()
