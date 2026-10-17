"""Tests of the non-AI policies (`creature_forge.ce_policies`) and the episode runner (`scripts/ce_eval.py`). No network, no MuJoCo: a real
`eng_tools.Workbench` / `ce_policies.UnionWorkbench` with fake observe / cma functions."""
import json
import unittest

from creature_forge import ce_policies as cp
from creature_forge import eng_tools as et
from creature_forge import fault_bench as fb
from scripts import ce_eval

from tests.test_fault_bench import BODY, VEC, fake_cma
from tests import test_scientist as ts


def fake_observe(slip=0.05, sat=0.0):
    """foot_length >= 0.2 -> 4 walking; torso_mass < 4 or torque_limit > 80 -> 2 walking; otherwise 0."""
    def fn(body, vector, seeds, *, mechanisms=(), variation=None, duration=10.0, pool=None):
        fl, tm, tl = body["foot_length"], body["torso_mass"], body["torque_limit"]
        walking = 4 if fl >= 0.2 else 2 if (tm < 4.0 or tl > 80.0) else 0
        med = {"slip_fraction": slip, "saturation_frac_hip": sat, "pitch_end": 0.02, "leg_length_m": 0.8, "step_freq_hz": 1.5,
               "time_upright": 2.0 + walking, "fall_time": 3.0}
        return {"per_seed": [{} for _ in seeds], "median": med, "pre_fall_median": None, "rollouts": len(seeds),
                "n_fell": len(seeds) - walking, "n_walking": walking, "errors": []}
    return fn


def bench(total=700, cls=cp.UnionWorkbench, log=None, **kw):
    s = fb.instance_seeds("camp", "b0", "short_feet", 0.5)
    return cls({"body": BODY, "vector": VEC}, total_budget=total, seeds={"train": s["train"], "obs": s["obs"]},
               observe_fn=kw.pop("observe_fn", fake_observe()), cma_fn=fake_cma(log), **kw)


def run(policy, **kw):
    b = bench(**kw)
    rec = policy.run(b, {"robot": {"body": BODY, "vector": VEC}})
    return rec, b


class Common:
    def assert_within_budget(self, b):
        led = b.ledger()
        self.assertLessEqual(led["used"], led["total"])
        self.assertEqual(led["used"], sum(l["n"] for l in led["lines"]))


class TestExhaustive(unittest.TestCase, Common):
    def test_runs_every_available_counterfactual_then_top2(self):
        rec, b = run(cp.Exhaustive())
        avail = cp.available_counterfactuals(bench())
        led = b.ledger()
        cfl = [l for l in led["lines"] if l["item"] == "counterfactual" and l["n"] > 0]
        self.assertEqual(len(cfl), len(avail))
        self.assertEqual(len(rec["counterfactuals"]), len(avail))
        # foot length gives 4 walking, torso mass / torque limit give 2: that order, then catalogue order
        self.assertEqual(rec["ranking"][:3], ["foot_length_x1.3", "torso_mass_x0.75", "torque_limit_x1.6"])
        reps = [r for r in rec["repairs"] if r.get("ok")]
        self.assertEqual([r["tool"] for r in reps], ["foot_length", "torso_mass"])
        self.assertEqual(rec["submitted_design"]["source"].split(":")[0], "repair")
        self.assert_within_budget(b)

    def test_split_first_gets_half(self):
        rec, b = run(cp.Exhaustive())
        spent_before = sum(l["n"] for l in b.ledger()["lines"] if l["item"] in ("counterfactual", "observe"))
        self.assertEqual(rec["repairs"][0]["budget"], (700 - spent_before) // 2)

    def test_deterministic(self):
        a, ba = run(cp.Exhaustive())
        c, bc = run(cp.Exhaustive())
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(c, sort_keys=True))

    def test_table_is_complete(self):
        self.assertEqual(set(cp.CF_TO_TOOL), set(et.COUNTERFACTUALS))
        self.assertTrue(set(cp.CF_TO_TOOL.values()) <= set(fb.TOOLS))


class FakePredictor:
    """Ranks torque_limit, then stride, ... and records what it was given."""
    def __init__(self):
        self.seen = None

    def advise(self, observation, features, cf_results=None):
        self.seen = (observation, features, cf_results)
        order = ["torque_limit", "stride"] + [t for t in fb.TOOLS if t not in ("torque_limit", "stride")]
        return [{"tool": t, "p_repair": 0.9 - 0.05 * i, "uncertainty": None, "rank": i + 1, "setting": "obs+cf"} for i, t in enumerate(order)]


class TestLearned(unittest.TestCase, Common):
    def test_same_experiments_as_exhaustive_then_predicted_top2(self):
        p = FakePredictor()
        b = bench()
        rec = cp.Learned(p).run(b, {"robot": {"body": BODY, "vector": VEC}, "features": {"foot_to_leg": 0.2}})
        ex, bex = run(cp.Exhaustive())
        n_cf = lambda bb: sum(1 for l in bb.ledger()["lines"] if l["item"] == "counterfactual" and l["n"] > 0)
        self.assertEqual(n_cf(b), n_cf(bex))                                # identical instruments and costs
        self.assertEqual([r["tool"] for r in rec["repairs"] if r.get("ok")], ["torque_limit", "stride"])
        obs, feats, cfr = p.seen
        self.assertEqual(feats, {"foot_to_leg": 0.2})
        self.assertEqual(set(cfr), set(et.COUNTERFACTUALS))                 # unavailable entries are marked refused
        self.assertIn("deltas", cfr["foot_length_x1.3"])
        self.assertIn("median", obs)
        self.assert_within_budget(b)

    def test_needs_a_predictor(self):
        with self.assertRaises(ValueError):
            cp.make_policy("learned")


class TestExpert(unittest.TestCase, Common):
    def test_rules(self):
        base = {"median": {"leg_length_m": 0.8}}
        s, _ = cp.expert_scores({"median": {"leg_length_m": 0.8, "slip_fraction": 0.3}}, BODY)
        self.assertEqual(max(s, key=s.get), "foot_friction")
        s, f = cp.expert_scores({"median": {"leg_length_m": 0.8, "saturation_frac_knee": 0.4}}, BODY)
        self.assertEqual(max(s, key=s.get), "torque_limit")
        s, f = cp.expert_scores({"median": {"leg_length_m": 0.8, "pitch_end": 0.2, "tracking_error_hip": 0.02}}, BODY)
        self.assertEqual(max(s, key=s.get), "posture")
        s, f = cp.expert_scores({"median": {"leg_length_m": 0.8, "cp_ahead_of_front_edge_over_L_end": 0.3, "step_length_over_L": 0.2}}, BODY)
        self.assertEqual(max(s, key=s.get), "placement")
        s, f = cp.expert_scores({"median": {"leg_length_m": 0.8, "step_freq_hz": 3.5, "pitch_slope": 0.1}}, BODY)   # 3.5 / 0.79 Hz
        self.assertEqual(max(s, key=s.get), "timing")
        s, f = cp.expert_scores(base, {**BODY, "foot_length": 0.1})                                         # 0.125 of the leg
        self.assertEqual(max(s, key=s.get), "foot_length")
        s, f = cp.expert_scores({"median": {}}, BODY)                                                       # nothing fires
        self.assertEqual(f, [])
        self.assertTrue(all(v == 0 for v in s.values()))

    def test_run_repairs_top2_after_one_observation(self):
        rec, b = run(cp.ExpertRules(), observe_fn=fake_observe(slip=0.3, sat=0.3))
        self.assertEqual(rec["ranking"][:2], ["torque_limit", "foot_friction"])
        reps = [r["tool"] for r in rec["repairs"] if r.get("ok")]
        self.assertEqual(reps, ["torque_limit", "foot_friction"])
        led = b.ledger()
        self.assertEqual([l["item"] for l in led["lines"] if l["n"] > 0][:1], ["observe"])
        self.assertEqual(sum(1 for l in led["lines"] if l["item"] == "counterfactual"), 0)
        self.assert_within_budget(b)

    def test_fallback_order_when_no_rule_fires(self):
        rec, _ = run(cp.ExpertRules())
        self.assertEqual(rec["ranking"][:2], ["posture", "timing"])

    def test_deterministic(self):
        a, _ = run(cp.ExpertRules())
        c, _ = run(cp.ExpertRules())
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(c, sort_keys=True))


class TestRandom(unittest.TestCase, Common):
    def test_two_cfs_two_tools_deterministic_given_seed(self):
        a, ba = run(cp.RandomPolicy(7))
        c, bc = run(cp.RandomPolicy(7))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(c, sort_keys=True))
        self.assertEqual(len(a["counterfactuals"]), 2)
        self.assertEqual(len([r for r in a["repairs"] if r.get("ok")]), 2)
        self.assert_within_budget(ba)

    def test_seed_changes_choices(self):
        picks = {tuple(c["id"] for c in run(cp.RandomPolicy(s))[0]["counterfactuals"]) for s in range(6)}
        self.assertGreater(len(picks), 1)


class TestBlind(unittest.TestCase, Common):
    def test_single_union_repair_whole_budget(self):
        log = []
        rec, b = run(cp.Blind(), log=log)
        led = b.ledger()
        reps = [l for l in led["lines"] if l["item"] == "repair" and l["n"] > 0]
        self.assertEqual(len(reps), 1)
        self.assertEqual(reps[0]["detail"]["tool"], "union")
        self.assertEqual(rec["repairs"][0]["budget"], 700)
        self.assertEqual(len(log), 1)
        dims = log[0]["dims"]
        self.assertEqual(sorted(dims["body_params"]), sorted(cp.UNION_BODY_PARAMS))
        self.assertEqual(len(dims["ctrl_params"]), 17)
        self.assertLessEqual(led["used"], 700)
        self.assertEqual(b.best_design()["source"], "repair:union")

    def test_requires_union_bench(self):
        s = fb.instance_seeds("camp", "b0", "short_feet", 0.5)
        plain = et.Workbench({"body": BODY, "vector": VEC}, total_budget=700, seeds={"train": s["train"], "obs": s["obs"]},
                             observe_fn=fake_observe(), cma_fn=fake_cma())
        with self.assertRaises(TypeError):
            cp.Blind().run(plain)

    def test_too_small_budget_refused_not_raised(self):
        rec, b = run(cp.Blind(), total=50)
        self.assertFalse(rec["repairs"][0]["ok"])
        self.assertEqual(b.ledger()["used"], 0)


class TestSmallBudgets(unittest.TestCase, Common):
    def test_every_policy_respects_small_budgets(self):
        for total in (0, 8, 60, 130, 260):
            for pol in (cp.Exhaustive(), cp.ExpertRules(), cp.RandomPolicy(1), cp.Blind()):
                with self.subTest(total=total, policy=pol.name):
                    rec, b = run(pol, total=total)
                    self.assert_within_budget(b)
                    self.assertEqual(rec["policy"], pol.name)
                    json.dumps(rec)


# ------------------------------------------------------------------------------------------------------------------ ce_eval
def instance(fault="short_feet"):
    s = fb.instance_seeds("camp", "b0", fault, 0.5)
    return {"instance_id": f"b0:{fault}:0.5", "base_id": "b0", "region": "L1-f1-t0-q1", "fault": fault, "severity": 0.5,
            "matching_tool": fb.MATCHING_TOOL[fault], "kept": True, "split": "dev", "seeds": s,
            "robot": {"body": BODY, "vector": VEC}, "repair_matrix": {"foot_length": 1.0}}


def verify_fn(instance_, design, pool=None):
    verify_fn.calls.append((instance_["instance_id"], design["vector"][0]))
    ok = design["vector"][0] != VEC[0]            # the fake repair moves vector[0]
    return {"status": "FULL_RECOVERY" if ok else "NOT_RECOVERED", "reasons": [], "rollouts": {"validation": 48},
            "validation": {"walking_frac": 0.9 if ok else 0.0}}


verify_fn.calls = []


def bench_factory(spy=None):
    def f(view, *, budget, n_train, n_obs, pool, noise_seed):
        if spy is not None:
            spy.append(json.dumps(view))
        return cp.UnionWorkbench(view["robot"], total_budget=budget, seeds=view["seeds"], n_train=n_train, n_obs=n_obs,
                                 noise_seed=noise_seed, observe_fn=ts.fake_observe(), cma_fn=fake_cma())
    return f


def scientist_factory(fixture):
    from creature_forge.scientist import Scientist

    def f(mode, order_seed):
        return Scientist(mode, fixture=json.loads(json.dumps(fixture)), reference_features=ts.REF, order_seed=order_seed)
    return f


class TestCeEval(unittest.TestCase):
    def ev(self, policy, inst=None, **kw):
        spy = []
        rec = ce_eval.evaluate(inst or instance(), policy, budget=400, bench_factory=bench_factory(spy), verify_fn=verify_fn,
                               features_fn=lambda body: ts.FEATS, scientist_factory=scientist_factory(ts.GOOD), **kw)
        return rec, spy

    def test_scientist_record_fields_and_hidden_mapping(self):
        verify_fn.calls.clear()
        rec, spy = self.ev("scientist")
        for k in ("policy", "instance_id", "base_id", "region", "fault", "severity", "matching_tool", "verification", "verified",
                  "walking_frac", "rollouts_used", "ledger", "n_experiments", "n_repairs", "diagnosis", "prediction_accuracy",
                  "llm", "policy_record"):
            self.assertIn(k, rec)
        self.assertEqual(rec["fault"], "short_feet")
        self.assertTrue(rec["verified"])
        self.assertEqual(rec["verification"]["status"], "FULL_RECOVERY")
        self.assertEqual(rec["diagnosis"]["category"], "short_support_base")
        self.assertEqual(rec["diagnosis"]["injected_category"], "short_support_base")
        self.assertTrue(rec["diagnosis"]["match"])
        self.assertEqual((rec["n_counterfactuals"], rec["n_repairs"]), (2, 1))
        self.assertEqual(rec["llm"]["calls"], 4)
        self.assertEqual(rec["provenance"], "SCRIPTED_MOCK")
        self.assertEqual(verify_fn.calls[0][0], rec["instance_id"])
        json.dumps(rec)

    def test_wrong_diagnosis_does_not_match(self):
        rec, _ = self.ev("scientist", instance("slippery"))
        self.assertEqual(rec["diagnosis"]["injected_category"], "low_traction")
        self.assertFalse(rec["diagnosis"]["match"])

    def test_policy_view_is_blind(self):
        _, spy = self.ev("exhaustive")
        blob = " ".join(spy)
        for w in list(fb.FAULTS) + ["severity", "repair_matrix", "matching_tool", "kept"]:
            self.assertNotIn(w, blob)
        inst = instance()
        for role in ("check", "validate", "confirm"):
            for seed in inst["seeds"][role]:
                self.assertNotIn(str(seed), blob)

    def test_mapping_only_in_runner(self):
        from creature_forge import scientist
        with open(scientist.__file__, encoding="utf-8") as fh:
            src = fh.read()
        with open(cp.__file__, encoding="utf-8") as fh:
            src2 = fh.read()
        for f in fb.FAULTS:
            self.assertNotIn(f, src)
            self.assertNotIn(f, src2)
        self.assertEqual(set(ce_eval.HIDDEN_MAPPING), set(fb.FAULTS))

    def test_non_ai_policies(self):
        for p in ("exhaustive", "expert", "random", "blind", "scientist_1shot"):
            fx = ts.OneShot.ONE
            sf = scientist_factory([fx])
            rec = ce_eval.evaluate(instance(), p, budget=400, bench_factory=bench_factory(), verify_fn=verify_fn,
                                   features_fn=lambda body: ts.FEATS, scientist_factory=sf)
            self.assertIsNone(rec["error"], p)
            self.assertEqual(rec["policy"], p)
            self.assertLessEqual(rec["rollouts_used"], 400)
            self.assertIn("verification", rec)
            self.assertEqual("diagnosis" in rec, p.startswith("scientist"))

    def test_error_is_recorded_not_verified(self):
        def boom(*a, **k):
            raise RuntimeError("simulator exploded")
        rec = ce_eval.evaluate(instance(), "expert", budget=400, bench_factory=lambda view, **k: type("B", (), {"observe": boom, "ledger": lambda s: {}})(),
                               verify_fn=verify_fn, features_fn=lambda body: {})
        self.assertIn("simulator exploded", rec["error"])
        self.assertIsNone(rec["verified"])
        self.assertEqual(rec["fault"], "short_feet")

    def test_instances_loader_keeps_only_kept(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "i.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(instance()) + "\n" + json.dumps({**instance("slippery"), "kept": False}) + "\n")
            self.assertEqual([i["fault"] for i in ce_eval.load_instances(p)], ["short_feet"])
            self.assertEqual(len(ce_eval.load_instances(p, kept_only=False)), 2)
            out = os.path.join(d, "o.jsonl")
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"instance_id": "i1", "policy": "blind"}) + "\n")
            self.assertEqual(ce_eval.done_pairs(out), {("i1", "blind")})
            self.assertEqual(ce_eval.done_pairs(p + ".missing"), set())


if __name__ == "__main__":
    unittest.main()
