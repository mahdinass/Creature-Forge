"""Tests of the Nemotron scientist (`creature_forge.scientist`). No network, no MuJoCo simulation: a real `eng_tools.Workbench` runs with
fake observe / cma functions and the model is a scripted fixture."""
import json
import re
import unittest

from creature_forge import eng_tools as et
from creature_forge import fault_bench as fb
from creature_forge import scientist as sc

from tests.test_fault_bench import BODY, VEC, fake_cma

REF = {"foot_to_leg": 0.1, "mass_total": 10.0}
FEATS = {"foot_to_leg": 0.04, "mass_total": 12.0}
FAULT_WORDS = list(fb.FAULTS) + ["severity", "repair_matrix", "matching_tool"]


def fake_observe(log=None):
    def fn(body, vector, seeds, *, mechanisms=(), variation=None, duration=10.0, pool=None):
        if log is not None:
            log.append("observe")
        fl, tm = body["foot_length"], body["torso_mass"]
        walking = 4 if fl >= 0.2 else 0
        med = {"pitch_end": 0.15, "slip_fraction": 0.3, "saturation_frac_ankle": 0.1 * tm / 5.0, "step_freq_hz": 2.0,
               "leg_length_m": 0.8, "fall_time": 2.0 + 10 * (fl - 0.16), "time_upright": 2.5,
               "com_ahead_of_cop_over_L_mean": 0.05, "capture_inside_fraction": None}
        return {"per_seed": [{} for _ in seeds], "median": med, "pre_fall_median": {"capture_margin_over_L": -0.1},
                "rollouts": len(seeds), "n_fell": len(seeds) - walking, "n_walking": walking, "errors": []}
    return fn


class LoggedBench(et.Workbench):
    def __init__(self, *a, log=None, **kw):
        super().__init__(*a, **kw)
        self.log = log if log is not None else []

    def counterfactual(self, change):
        self.log.append("bench:counterfactual")
        return super().counterfactual(change)

    def repair(self, tool, budget):
        self.log.append("bench:repair")
        return super().repair(tool, budget)


def make_bench(total=400, log=None):
    seeds = fb.instance_seeds("camp", "b0", "short_feet", 0.5)
    return LoggedBench({"body": BODY, "vector": VEC}, total_budget=total, seeds={"train": seeds["train"], "obs": seeds["obs"]},
                       observe_fn=fake_observe(), cma_fn=fake_cma(), log=log)


VIEW = {"robot": {"body": BODY, "vector": VEC}, "features": FEATS}


def hyp(i, cat="short_support_base", ev=("robot.body.foot_length", "observation.median.slip_fraction")):
    return {"id": i, "mechanism": "small foot support", "causal_chain": "short foot -> CoP leaves the toe -> forward fall",
            "category": cat, "evidence": list(ev), "confidence": 0.5}


def reply(action, *, new=(), status=(), cf=(), rep=(), con=(), mem=None):
    r = {"action": action, "new_hypotheses": list(new), "status_updates": list(status), "counterfactual": list(cf),
         "repair": list(rep), "conclude": list(con)}
    if mem is not None:
        r["memory_assessments"] = list(mem)
    return r


def cf(change, preds, purpose="test the support base"):
    return {"change": change, "purpose": purpose, "predictions": [{"hypothesis": h, "quantity": q, "direction": d} for h, q, d in preds]}


def upd(i, status, exps, reason="measured"):
    return {"id": i, "status": status, "confidence": 0.7, "reason": reason, "experiments": list(exps)}


S1 = reply("counterfactual", new=[hyp("H1")], cf=[cf("foot_length_x1.3", [("H1", "n_walking", "increase"), ("H1", "slip_fraction", "increase")])])
S2 = reply("counterfactual", new=[hyp("H2", "low_traction")], status=[upd("H1", "supported", ["E1"])],
           cf=[cf("torso_mass_x0.75", [("H2", "saturation_frac_ankle", "decrease"), ("H1", "n_walking", "no_change")])])
S3 = reply("repair", status=[upd("H2", "refuted", ["E2"])],
           rep=[{"tool": "foot_length", "budget_share": 0.5, "hypothesis": "H1", "predicted_n_walking": 4}])
S4 = reply("conclude", con=[{"diagnosis_category": "short_support_base", "explanation": "feet too short", "confidence": 0.8, "submit": "best"}])
GOOD = [S1, S2, S3, S4]


def make(fixture, mode="iterative", **kw):
    log = kw.pop("log", None)
    hook = (lambda ev: log.append("event:" + ev["type"])) if log is not None else None
    return sc.Scientist(mode, fixture=json.loads(json.dumps(fixture)), reference_features=REF, event_hook=hook,
                        order_seed=kw.pop("order_seed", 5), **kw)


class Scoring(unittest.TestCase):
    def test_tolerances(self):
        self.assertEqual(sc.tolerance("n_walking"), 0.0)
        self.assertEqual(sc.tolerance("n_fell", 3), 0.0)
        self.assertAlmostEqual(sc.tolerance("fall_time", 1.0), 0.25)
        self.assertAlmostEqual(sc.tolerance("fall_time", 10.0), 0.5)         # 5 % of the baseline
        self.assertAlmostEqual(sc.tolerance("pre_fall.pitch", 0.1), 0.02)
        self.assertAlmostEqual(sc.tolerance("slip_fraction", 0.1), 0.02)

    def test_direction_scoring(self):
        s = sc.score_direction("n_walking", "increase", 0, 2)
        self.assertEqual((s["status"], s["observed"]), ("correct", "increase"))
        self.assertEqual(sc.score_direction("n_walking", "no_change", 2, 2)["status"], "correct")
        self.assertEqual(sc.score_direction("n_walking", "no_change", 2, 3)["status"], "incorrect")   # tolerance 0
        self.assertEqual(sc.score_direction("slip_fraction", "decrease", 0.3, 0.29)["status"], "incorrect")  # inside tolerance = no_change
        self.assertEqual(sc.score_direction("slip_fraction", "no_change", 0.3, 0.29)["status"], "correct")
        self.assertEqual(sc.score_direction("fall_time", "increase", None, 3.0)["status"], "unscored")

    def test_quantity_value(self):
        o = {"median": {"pitch_end": 0.1, "fall_time": None}, "pre_fall_median": {"pitch": 0.2}, "n_walking": 3}
        self.assertEqual(sc.quantity_value(o, "pitch_end"), 0.1)
        self.assertIsNone(sc.quantity_value(o, "fall_time"))
        self.assertEqual(sc.quantity_value(o, "pre_fall.pitch"), 0.2)
        self.assertEqual(sc.quantity_value(o, "n_walking"), 3.0)


class Loop(unittest.TestCase):
    def run_good(self, **kw):
        log = []
        bench = make_bench(log=log)
        s = make(GOOD, log=log, **kw)
        rec = s.investigate(bench, VIEW)
        return rec, bench, log

    def test_end_to_end(self):
        rec, bench, _ = self.run_good()
        self.assertEqual(rec["final"]["ended_by"], "concluded")
        self.assertEqual(rec["final"]["diagnosis_category"], "short_support_base")
        self.assertEqual([s["action"] for s in rec["steps"]], ["counterfactual", "counterfactual", "repair", "conclude"])
        self.assertEqual(rec["n_model_calls"], 4)
        self.assertEqual(rec["provenance"], "SCRIPTED_MOCK")
        self.assertEqual(rec["submitted_design"]["source"], "repair:foot_length")
        self.assertEqual(rec["scientist_mode"], "iterative")
        json.dumps(rec)

    def test_predictions_registered_before_execution(self):
        rec, bench, log = self.run_good()
        for i, e in enumerate(log):
            if e == "bench:counterfactual":
                self.assertEqual(log[i - 1], "event:bench_call")
                self.assertIn("event:prediction_registered", log[:i])
        self.assertLess(log.index("event:prediction_registered"), log.index("bench:counterfactual"))
        for e in rec["experiments"]:
            if e["kind"] in ("counterfactual", "repair"):
                self.assertLess(e["registered_seq"], e["executed_seq"])
        ev = {x["seq"]: x for x in rec["events"]}
        e1 = next(e for e in rec["experiments"] if e["id"] == "E1")
        self.assertEqual(ev[e1["registered_seq"]]["predictions"],
                         [{"hypothesis": "H1", "quantity": "n_walking", "direction": "increase"},
                          {"hypothesis": "H1", "quantity": "slip_fraction", "direction": "increase"}])

    def test_prediction_scoring_in_record(self):
        rec, _, _ = self.run_good()
        e1 = next(e for e in rec["experiments"] if e["id"] == "E1")
        self.assertEqual({p["quantity"]: p["status"] for p in e1["scoring"]}, {"n_walking": "correct", "slip_fraction": "incorrect"})
        e2 = next(e for e in rec["experiments"] if e["id"] == "E2")
        self.assertEqual({p["quantity"]: p["status"] for p in e2["scoring"]},
                         {"saturation_frac_ankle": "correct", "n_walking": "correct"})
        ps = rec["prediction_summary"]
        self.assertEqual((ps["n_scored"], ps["n_correct"]), (4, 3))
        self.assertAlmostEqual(ps["accuracy"], 0.75)
        r = next(e for e in rec["experiments"] if e["id"] == "R1")
        self.assertEqual((r["predicted_n_walking"], r["train_walking"]), (4, 4))
        self.assertEqual(ps["repair_predictions"]["within_one"], 1)

    def test_hypothesis_transitions(self):
        rec, _, _ = self.run_good()
        h = rec["hypotheses"]
        self.assertEqual((h["H1"]["status"], h["H2"]["status"]), ("supported", "refuted"))
        self.assertEqual([x["status"] for x in h["H1"]["history"]], ["open", "supported"])
        tr = rec["steps"][1]["hypothesis_transitions"]
        supp = next(t for t in tr if t["id"] == "H1")
        self.assertEqual((supp["from"], supp["to"]), ("open", "supported"))
        self.assertEqual(supp["cited_predictions"], {"n_scored": 2, "n_correct": 1})

    def test_budget_never_exceeded_and_costs(self):
        rec, bench, _ = self.run_good()
        led = bench.ledger()
        self.assertLessEqual(led["used"], led["total"])
        self.assertEqual(rec["initial_observation_cost"], 4)
        e1, e2, r1 = (next(e for e in rec["experiments"] if e["id"] == i) for i in ("E1", "E2", "R1"))
        self.assertEqual((e1["cost"], e2["cost"]), (4, 4))
        self.assertEqual(r1["budget"], (400 - 4 - 4 - 4) // 2)           # floor(0.5 x remaining)

    def test_refused_step_budget_too_small(self):
        bad = reply("repair", new=[hyp("H1")], rep=[{"tool": "foot_length", "budget_share": 0.01, "hypothesis": "H1", "predicted_n_walking": 1}])
        s = make([bad, bad, S4])
        rec = s.investigate(make_bench(), VIEW)
        self.assertEqual(rec["steps"][0]["status"], "invalid_after_repair")
        self.assertTrue(any("below the minimum" in e for e in rec["steps"][0]["validation_errors"]))
        self.assertEqual(rec["experiments"], [])

    def test_one_repair_call_then_valid(self):
        s = make(["not json at all", S1, S4])
        rec = s.investigate(make_bench(), VIEW)
        self.assertEqual(rec["steps"][0]["status"], "ok")
        self.assertTrue(rec["steps"][0]["repaired"])
        self.assertEqual(rec["steps"][0]["calls"], [0, 1])
        self.assertEqual(rec["n_model_calls"], 3)

    def test_two_consecutive_failures_end_without_substitution(self):
        bench = make_bench()
        s = make(["bad", "bad", "bad", "bad", S4])
        rec = s.investigate(bench, VIEW)
        self.assertEqual(rec["final"]["ended_by"], "consecutive_invalid")
        self.assertIsNone(rec["final"]["diagnosis_category"])
        self.assertEqual([x["status"] for x in rec["steps"]], ["invalid_after_repair"] * 2)
        self.assertEqual(rec["n_model_calls"], 4)
        self.assertEqual(rec["experiments"], [])
        self.assertEqual(bench.ledger()["used"], 4)                    # only the initial observation
        self.assertEqual(rec["submitted_design"]["source"], "initial")

    def test_failure_then_recovery_continues(self):
        s = make(["bad", "bad", S1, S4])
        rec = s.investigate(make_bench(), VIEW)
        self.assertEqual([x["status"] for x in rec["steps"]], ["invalid_after_repair", "ok", "ok"])
        self.assertEqual(rec["final"]["ended_by"], "concluded")

    def test_repeated_counterfactual_rejected(self):
        again = reply("counterfactual", status=[upd("H1", "open", ["E1"])], cf=[cf("foot_length_x1.3", [("H1", "n_walking", "increase")])])
        s = make([S1, again, again, S4])
        rec = s.investigate(make_bench(), VIEW)
        self.assertEqual(rec["steps"][1]["status"], "invalid_after_repair")
        self.assertTrue(any("not available now" in e for e in rec["steps"][1]["validation_errors"]))

    def test_max_steps_leaves_only_conclude(self):
        s = make([S1, S4], max_steps=2)
        rec = s.investigate(make_bench(), VIEW)
        self.assertEqual(rec["steps"][1]["allowed_actions"], ["conclude"])
        self.assertEqual(rec["final"]["ended_by"], "concluded")

    def test_max_steps_without_conclusion(self):
        s = make([S1, S2, S2], max_steps=2)
        rec = s.investigate(make_bench(), VIEW)
        self.assertEqual(rec["steps"][1]["status"], "invalid_after_repair")     # a non-conclude action is not allowed on the last step
        self.assertIsNone(rec["final"]["diagnosis_category"])
        self.assertEqual(rec["final"]["ended_by"], "max_steps")

    def test_request_cap(self):
        s = make([S1, S2, S3, S4], max_requests=3)
        rec = s.investigate(make_bench(), VIEW)
        self.assertLessEqual(rec["n_model_calls"], 3)

    def test_cannot_run_twice(self):
        s = make(GOOD)
        s.investigate(make_bench(), VIEW)
        with self.assertRaises(RuntimeError):
            s.investigate(make_bench(), VIEW)

    def test_conclude_immediately(self):
        s = make([reply("conclude", new=[hyp("H1")], con=[{"diagnosis_category": "unresolved", "explanation": "no idea", "confidence": 0.1,
                                                          "submit": "best"}])])
        bench = make_bench()
        rec = s.investigate(bench, VIEW)
        self.assertEqual(rec["final"]["diagnosis_category"], "unresolved")
        self.assertEqual(bench.ledger()["used"], 4)


class NoLeakage(unittest.TestCase):
    def test_prompts_contain_no_ground_truth(self):
        inst_seeds = fb.instance_seeds("camp", "b0", "short_feet", 0.5)
        rec = make(GOOD).investigate(make_bench(), VIEW)
        texts = [rec["system_prompt"]] + [m["content"] for c in rec["calls"] for m in c["messages"]]
        self.assertTrue(texts)
        blob = "\n".join(texts)
        for w in FAULT_WORDS:
            self.assertNotIn(w, blob, w)
        for role in ("check", "validate", "confirm", "train", "obs"):
            for seed in inst_seeds[role]:
                self.assertIsNone(re.search(rf"(?<!\d){seed}(?!\d)", blob), f"{role} seed {seed} appears in a prompt")
        self.assertNotIn("HIDDEN_MAPPING", blob)

    def test_module_has_no_fault_mapping(self):
        with open(sc.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for f in fb.FAULTS:
            self.assertNotIn(f, src)

    def test_system_prompt_lists_instruments(self):
        rec = make(GOOD).investigate(make_bench(), VIEW)
        self.assertEqual(rec["calls"][0]["schema_name"], sc.SCHEMA_STEP)
        for cid in et.COUNTERFACTUALS:
            self.assertIn(cid, rec["system_prompt"])
        for t in fb.TOOLS:
            self.assertIn(t, rec["system_prompt"])
        for c in sc.CATEGORIES:
            self.assertIn(c, rec["system_prompt"])


class SchemaAndValidation(unittest.TestCase):
    CTX = dict(new_ids=["H1", "H2", "H3"], hypotheses={}, exp_ids=["O0"], cf_available=["foot_length_x1.3"], tools=["foot_length"],
               tool_min={"foot_length": 52}, remaining=400, n_train=4, paths={"robot.body.foot_length", "observation.median.slip_fraction"},
               actions=["counterfactual", "repair", "conclude"], mem_ids=None, first_step=True)

    def test_valid(self):
        self.assertEqual(sc.validate_step(S1, self.CTX), [])

    def test_rejects(self):
        bad = json.loads(json.dumps(S1))
        bad["counterfactual"][0]["predictions"][0]["hypothesis"] = "H9"
        bad["new_hypotheses"][0]["evidence"] = ["robot.body.nonexistent"]
        bad["conclude"] = S4["conclude"]
        errs = sc.validate_step(bad, self.CTX)
        self.assertTrue(any("H9" in e for e in errs))
        self.assertTrue(any("not an evidence path" in e for e in errs))
        self.assertTrue(any("conclude: must be empty" in e for e in errs))

    def test_schema_shape(self):
        sch = sc.step_schema(paths=["a"], new_ids=["H1"], existing=[], all_hyp=["H1"], exp_ids=["O0"], cf_ids=["x"], tools=["t"],
                             quantities=sc.QUANTITIES, actions=["conclude"], mem_ids=["M1"])
        self.assertEqual(set(sch["required"]), set(sch["properties"]))
        self.assertEqual(sch["properties"]["action"]["enum"], ["conclude"])
        self.assertIn("memory_assessments", sch["properties"])
        q = sch["properties"]["counterfactual"]["items"]["properties"]["predictions"]["items"]["properties"]["quantity"]["enum"]
        self.assertIn("n_walking", q)
        self.assertIn("pre_fall.capture_margin_over_L", q)


class OneShot(unittest.TestCase):
    ONE = {"hypotheses": [hyp("H1"), hyp("H2", "low_traction")],
           "repairs": [{"tool": "foot_length", "budget_share": 0.4, "hypothesis": "H1", "predicted_n_walking": 4},
                       {"tool": "foot_friction", "budget_share": 0.4, "hypothesis": "H2", "predicted_n_walking": 2}],
           "diagnosis_category": "short_support_base", "explanation": "short feet", "confidence": 0.6}

    def test_one_call_two_repairs(self):
        bench = make_bench()
        rec = make([self.ONE], mode="one_shot").investigate(bench, VIEW)
        self.assertEqual(rec["n_model_calls"], 1)
        self.assertEqual(rec["final"]["ended_by"], "one_shot")
        self.assertEqual([e["kind"] for e in rec["experiments"]], ["repair", "repair"])
        self.assertEqual(rec["experiments"][0]["budget"], int(0.4 * 396))
        self.assertLessEqual(bench.ledger()["used"], 400)
        self.assertNotIn("counterfactual", [l["item"] for l in bench.ledger()["lines"] if l["n"] > 0])
        self.assertEqual(rec["scientist_mode"], "one_shot")
        self.assertIn("ONCE", rec["system_prompt"])

    def test_invalid_one_shot_submits_unrepaired(self):
        bad = dict(self.ONE, repairs=[])
        bench = make_bench()
        rec = make([bad, bad], mode="one_shot").investigate(bench, VIEW)
        self.assertEqual(rec["final"]["ended_by"], "invalid_reply")
        self.assertEqual(rec["submitted_design"]["source"], "initial")
        self.assertEqual(rec["n_model_calls"], 2)

    def test_shares_over_one_rejected(self):
        bad = json.loads(json.dumps(self.ONE))
        bad["repairs"][0]["budget_share"] = 0.7
        rec = make([bad, bad], mode="one_shot").investigate(make_bench(), VIEW)
        self.assertTrue(any("sum" in e for e in rec["steps"][0]["validation_errors"]))


class FakeMemory:
    def __init__(self):
        self.calls = []

    def retrieve(self, observation_summary, robot_features):
        self.calls.append((observation_summary, robot_features))
        return [{"id": "M1", "kind": "episode", "text": "a robot with short feet walked after a foot-length repair"},
                {"id": "M2", "kind": "mechanism_card", "text": "slip raises friction utilisation"}]


class Memory(unittest.TestCase):
    MEM = [{"item": "M1", "verdict": "test_first", "reason": "similar symptom"}, {"item": "M2", "verdict": "does_not_apply", "reason": "no slip"}]

    def test_assessments_recorded(self):
        first = reply("counterfactual", new=[hyp("H1")], cf=[cf("foot_length_x1.3", [("H1", "n_walking", "increase")])], mem=self.MEM)
        later = reply("conclude", con=S4["conclude"], mem=[{"item": "M1", "verdict": "applies", "reason": "confirmed by E1"}])
        mem = FakeMemory()
        rec = make([first, later]).investigate(make_bench(), VIEW, memory=mem)
        self.assertEqual(len(mem.calls), 1)
        self.assertEqual(rec["memory"]["assessments"]["M1"]["verdict"], "applies")
        self.assertEqual(rec["memory"]["assessments"]["M2"]["verdict"], "does_not_apply")
        self.assertEqual([m["step"] for m in rec["memory"]["log"]], [1, 1, 2])
        self.assertIn("RETRIEVED MEMORY ITEMS", rec["steps"][0]["user_message"])
        self.assertIn("MEMORY.", rec["system_prompt"])

    def test_missing_assessment_rejected(self):
        first = reply("counterfactual", new=[hyp("H1")], cf=[cf("foot_length_x1.3", [("H1", "n_walking", "increase")])], mem=self.MEM[:1])
        rec = make([first, first]).investigate(make_bench(), VIEW, memory=FakeMemory())
        self.assertTrue(any("missing" in e for e in rec["steps"][0]["validation_errors"]))

    def test_inert_without_memory(self):
        rec = make(GOOD).investigate(make_bench(), VIEW)
        self.assertEqual(rec["memory"]["items"], [])
        self.assertNotIn("RETRIEVED MEMORY", rec["steps"][0]["user_message"])
        self.assertNotIn("MEMORY.", rec["system_prompt"])


if __name__ == "__main__":
    unittest.main()
