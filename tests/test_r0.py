"""R0 engineering tests: synthetic objectives, no physical rollouts."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

from creature_forge import r0_repair as rp
from creature_forge import walk_opt as wo
from creature_forge import hidden_plant as hp
from creature_forge import creature_walk as cw
from creature_forge.fault_bench import full_body
from creature_forge.hdb_workbench import tool_space
from creature_forge.sandbox import SandboxBody

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("r0_driver", ROOT / "scripts/r0_experiment.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def view():
    return {"robot_id": "opaque", "robot": {"body": full_body(SandboxBody().as_dict()),
            "vector": list(cw.R2_WINNER) + [0.0, 0.0]},
            "seeds": {"train": [1, 2, 3, 4], "select": list(range(11, 19))}}


def fake_evaluator(candidates, role):
    if role.endswith("baseline"):
        return []
    n = 4 if role == "train" else 8
    return [{"walking_count": n, "survival_count": n,
             "mean_fitness": -sum((float(x) - .25)**2 for x in c["vector"]), "error": None}
            for c in candidates]


class R0PolicyTests(unittest.TestCase):
    def setUp(self):
        self.stack = mock.patch.object(hp, "plant_rollout", side_effect=AssertionError("unexpected physics"))
        self.stack.start()
        self.addCleanup(self.stack.stop)

    def test_singleton_spaces_equal_existing(self):
        for tool in rp.TOOLS:
            self.assertEqual(rp.space([tool]).to_dict(), tool_space(tool).to_dict())

    def test_joint_union_and_partition(self):
        for pair in rp.PAIRS:
            sp = rp.space(pair)
            singles = [rp.space([t]) for t in pair]
            self.assertEqual(sp.dim, sum(s.dim for s in singles))
            self.assertEqual(set(sp.ctrl_params), set().union(*(set(s.ctrl_params) for s in singles)))
            self.assertEqual(set(sp.body_params), set().union(*(set(s.body_params) for s in singles)))
            self.assertLessEqual(len(sp.body_params), 4)
        for bad in [[], ["feedback", "feedback"], ["truth"]]:
            with self.assertRaises(ValueError):
                rp.space(bad)

    def test_original_anchor_rejects_compounded_body_edit(self):
        original = view()["robot"]
        c = copy.deepcopy(original)
        c["body"]["foot_friction"] = original["body"]["foot_friction"] * .2
        with self.assertRaises(ValueError):
            rp.assert_bounds(original, c)

    def test_controller_bounds_reject_nan(self):
        c = view()["robot"]
        c["vector"][0] = float("nan")
        with self.assertRaises(ValueError):
            rp.assert_bounds(view()["robot"], c)

    def test_all_six_conditions_exact_budget_and_determinism(self):
        for action in rp.ACTIONS:
            for objective in rp.OBJECTIVES:
                v = view()
                before = copy.deepcopy(v)
                a = rp.solve(v, action, objective, 0, fake_evaluator, budget=3000)
                b = rp.solve(v, action, objective, 0, fake_evaluator, budget=3000)
                self.assertEqual(a, b)
                self.assertEqual(v, before)
                self.assertEqual(a["ledger"]["used"], 3000)
                self.assertEqual(sum(x["n"] for x in a["ledger"]["lines"]), 3000)
                self.assertEqual(len(a["selection"]), 2)
                rp.assert_bounds(v["robot"], a["design"])

    def test_policy_rejects_hidden_fields_and_seed_overlap(self):
        for key in ["plant", "family", "severity", "validate", "confirmation"]:
            v = view()
            v[key] = "hidden"
            with self.assertRaises(ValueError):
                rp.solve(v, "single", "frozen", 0, fake_evaluator)
        v = view()
        v["seeds"]["select"][0] = 1
        with self.assertRaises(ValueError):
            rp.check_view(v)

    def test_errors_fail_closed(self):
        def ev(c, role):
            return [] if role.endswith("baseline") else [{"error": "physics failed"}] * len(c)
        with self.assertRaises(RuntimeError):
            rp.solve(view(), "joint", "frozen", 0, ev)

    def test_no_verifier_or_truth_argument_to_policy(self):
        import inspect
        names = inspect.signature(rp.solve).parameters
        self.assertNotIn("plant", names)
        self.assertNotIn("verify", names)


class R0RecordTests(unittest.TestCase):
    def test_frozen_smoke_gets_reporting_cohort_without_changing_case_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            directory = Path(t)
            driver.write_new(directory/"smoke_cases.json", [{"instance_id": "excluded", "base_id": "b"}])
            raw = (directory/"smoke_cases.json").read_bytes()
            driver.write_new(directory/"protocol.json", {"smoke_cases_sha256": driver.sha(raw),
                "code_sha256_lf": {}, "pairs": [list(p) for p in rp.PAIRS],
                "actions": list(rp.ACTIONS), "objectives": list(rp.OBJECTIVES)})
            with mock.patch.object(driver, "code_hashes", return_value={}):
                _, cases = driver.load_study(directory, smoke=True)
            self.assertEqual(cases[0]["cohort"], "engineering")
            self.assertEqual((directory/"smoke_cases.json").read_bytes(), raw)

    def test_missing_metadata_rejected_before_any_physics_or_optimization(self):
        with mock.patch.object(rp, "solve", side_effect=AssertionError("optimization started")), \
             mock.patch.object(hp, "verify", side_effect=AssertionError("verification started")):
            with self.assertRaisesRegex(ValueError, "metadata before physics"):
                driver.run_unit({"case": {"instance_id": "incomplete"}})

    def test_sampling_is_balanced_base_disjoint_deterministic(self):
        cs = [{"instance_id": f"b{i}:f{j}:0", "base_id": f"b{i}", "family": f"f{j}"}
              for i in range(18) for j in range(3)]
        a = driver.balanced_pick(cs, 12)
        self.assertEqual(a, driver.balanced_pick(list(reversed(cs)), 12))
        self.assertEqual(len({c["base_id"] for c in a}), 12)
        b = driver.balanced_pick(cs, 6, [c["base_id"] for c in a])
        self.assertFalse({c["base_id"] for c in a} & {c["base_id"] for c in b})
        with self.assertRaises(ValueError):
            driver.balanced_pick(cs, 19)

    def test_seed_roles_are_disjoint_fresh_and_repeatable(self):
        x = driver.fresh_seeds("case")
        self.assertEqual(x, driver.fresh_seeds("case"))
        self.assertNotEqual(x, driver.fresh_seeds("other"))
        flat = [s for ss in x.values() for s in ss]
        self.assertEqual(len(set(flat)), 60)

    def test_checkpoint_is_immutable_and_bad_json_not_resumable(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "unit.json"
            driver.write_new(path, {"ok": 1})
            driver.write_new(path, {"ok": 1})
            with self.assertRaises(ValueError):
                driver.write_new(path, {"ok": 0})
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                driver.read(path)

    def test_recovery_called_after_submission_and_full_rows_kept(self):
        v = view()
        case = {"instance_id": "development", "base_id": "b", "family": "dev", "cohort": "failed",
                "policy_id": "opaque", "robot": v["robot"], "plant": {"deviation": []},
                "seeds": {**v["seeds"], "validate": list(range(101, 125)), "confirm": list(range(201, 225))}}
        job = {"case": case, "action": "single", "objective": "frozen", "replicate": 0,
               "budget": 3000, "provenance": {"test": True}}
        result = rp.solve(v, "single", "frozen", 0, fake_evaluator)
        ver = {"rule": "full_recovery_v1", "status": "NOT_RECOVERED", "seeds": {k: case["seeds"][k]
               for k in ("validate", "confirm")}, "validation": {
                   arm: [{"seed": s, "outcome": "FAIL"} for s in case["seeds"]["validate"]]
                   for arm in ("original", "candidate")},
               "confirmation": {"run": False},
               "rollouts": {"validation": 48, "confirmation": 0, "confirmation_rollout_equivalents": 0}}
        ver["validation"]["walking_frac"] = 0
        with mock.patch.object(rp, "solve", return_value=result) as solve, mock.patch.object(hp, "verify", return_value=ver) as verify:
            row = driver.run_unit(job)
            self.assertEqual(verify.call_args.args[2], solve.return_value["design"])
            driver.validate_record(row, job, job["provenance"])
            for key in ("provenance", "unit_id", "verification"):
                bad = copy.deepcopy(row)
                bad.pop(key)
                with self.assertRaises((ValueError, KeyError)):
                    driver.validate_record(bad, job, job["provenance"])
            bad = copy.deepcopy(row)
            bad["verification"]["status"] = "FULL_RECOVERY"
            with self.assertRaises(ValueError):
                driver.validate_record(bad, job, job["provenance"])
            for mutate in (
                lambda r: r["verification"]["validation"]["original"].pop(),
                lambda r: r["verification"]["validation"].update(walking_frac=1),
                lambda r: r["result"]["ledger"]["lines"][0].update(n=-4),
                lambda r: r.update(verification_rollout_equivalents=0),
            ):
                bad = copy.deepcopy(row)
                mutate(bad)
                with self.assertRaises(ValueError):
                    driver.validate_record(bad, job, job["provenance"])

    def test_analysis_rejects_missing_or_unexpected_units(self):
        import argparse
        with tempfile.TemporaryDirectory() as t:
            driver.write_new(Path(t) / "execution.json", {})
            (Path(t) / "units").mkdir()
            with mock.patch.object(driver, "load_study", return_value=(
                    {"actions": ["single"], "objectives": ["frozen"], "replicates": [0], "budget": 3000},
                    [{"instance_id": "x"}])), mock.patch.object(driver,"validate_provenance"):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    driver.analyze(argparse.Namespace(study=t, out=t, smoke=False))

    def test_run_units_have_unique_deterministic_shards(self):
        p={"actions":list(rp.ACTIONS),"objectives":list(rp.OBJECTIVES),"replicates":[0,1,2],"budget":3000}
        jobs=driver.units(p,[{"instance_id":f"dev{i}"} for i in range(18)])
        self.assertEqual(len(jobs),324)
        self.assertEqual(len({driver.unit_id(j) for j in jobs}),324)
        shards=[{driver.unit_id(j) for j in jobs[k::8]} for k in range(8)]
        self.assertEqual(sum(map(len,shards)),len(set.union(*shards)))

    def test_full_analysis_clusters_technical_replicates_and_rejects_control_regression(self):
        import argparse
        import contextlib
        import io
        p = {"actions": list(rp.ACTIONS), "objectives": list(rp.OBJECTIVES),
             "replicates": [0, 1, 2], "budget": 3000,
             "analysis": {"bootstrap_seed": 2026102507, "bootstrap": 10000}}
        cases = [{"instance_id": f"dev{i}", "base_id": f"b{i}", "family": f"f{i%2}",
                  "cohort": "failed" if i < 12 else "control"} for i in range(18)]
        with tempfile.TemporaryDirectory() as t:
            for regress in (False, True):
                out = Path(t)/str(regress)
                driver.write_new(out/"execution.json", {})
                for j in driver.units(p, cases):
                    c = j["case"]
                    joint = j["action"] == "joint" and j["objective"] == "do1"
                    success = c["cohort"] == "control" or (
                        int(c["base_id"][1:]) < 3 and joint and j["replicate"] < 2)
                    if regress and c["base_id"] == "b12" and joint:
                        success = False
                    row = {**{k: c[k] for k in ("instance_id", "base_id", "family", "cohort")},
                           **{k: j[k] for k in ("action", "objective", "replicate")},
                           "result": {"ledger": {"used": 3000}}, "wall_s": 1,
                           "verification_rollout_equivalents": 48,
                           "verification": {"status": driver.FULL if success else "NOT_RECOVERED",
                                            "validation": {"walking_frac": int(success)}}}
                    driver.write_new(out/"units"/(driver.unit_id(j)+".json"), row)
                # Aggregation fixture only: measured-record integrity is covered separately.
                with mock.patch.object(driver, "load_study", return_value=(p, cases)), \
                     mock.patch.object(driver, "validate_provenance"), \
                     mock.patch.object(driver, "validate_record"), contextlib.redirect_stdout(io.StringIO()):
                    driver.analyze(argparse.Namespace(study=t, out=out, smoke=False))
                result = driver.read(out/"analysis.json")
                self.assertEqual(result["n"], 324)
                self.assertEqual(result["gate"]["PASS"], not regress)
                self.assertEqual(result["gate"]["material_control_regressions"], int(regress))
                contrast = result["contrasts_failed_cohort"]["joint/do1 - sequential/do1"]
                self.assertEqual(contrast["n_bases"], 12)
                self.assertAlmostEqual(contrast["mean_base_difference"], 1/6)

    def test_provenance_rejects_wrong_protocol_sources_and_missing_environment(self):
        with tempfile.TemporaryDirectory() as t:
            protocol = Path(t)/"protocol.json"
            driver.write_new(protocol, {"study": "fixture"})
            provenance = {"protocol_sha256": driver.sha(protocol.read_bytes()),
                          "code_sha256_lf": {"source": "hash"}, "source_commit": "a"*40,
                          "environment": {"mujoco": "3.15.0", "numpy": "2.4.6", "python": "3.11",
                                          "platform": "fixture", "executable": "existing"}}
            with mock.patch.object(driver, "code_hashes", return_value={"source": "hash"}):
                driver.validate_provenance(provenance, t)
                for key in ("protocol_sha256", "code_sha256_lf", "source_commit", "environment"):
                    bad = copy.deepcopy(provenance)
                    bad.pop(key)
                    with self.assertRaises(ValueError):
                        driver.validate_provenance(bad, t)

    def test_resume_validates_completed_unit_without_reexecution(self):
        import argparse
        with tempfile.TemporaryDirectory() as t:
            p={"actions":["single"],"objectives":["frozen"],"replicates":[0],"budget":3000}
            jobs=driver.units(p,[{"instance_id":"dev"}])
            path=Path(t)/"units"/(driver.unit_id(jobs[0])+".json")
            driver.write_new(path,{"checkpoint":True})
            with mock.patch.object(driver,"load_study",return_value=(p,[{"instance_id":"dev"}])), \
                 mock.patch.object(driver,"fingerprint",return_value={}), \
                 mock.patch.object(driver,"execution_provenance",return_value={"p":1}), \
                 mock.patch.object(driver,"validate_provenance"), \
                 mock.patch.object(driver,"validate_record") as validate, \
                 mock.patch.object(driver.subprocess,"check_output",return_value=b""), \
                 mock.patch.object(driver,"run_unit",side_effect=AssertionError("completed unit rerun")):
                driver.execute(argparse.Namespace(study=t,out=t,smoke=False,shard="0/1",workers=1))
                validate.assert_called_once()


class R0OpsTests(unittest.TestCase):
    def test_legacy_start_entry_point_uses_service_account_without_personal_login(self):
        import r0_nebius as ops
        with tempfile.TemporaryDirectory() as t:
            (Path(t)/"sa.json").write_text(json.dumps({"key_expires_epoch": 9999999999}))
            fc = ops.cloud(t, "batch")
            self.assertIs(fc.ctl, fc.nebius)
            with mock.patch.object(fc, "nebius_sa") as api:
                fc.nebius("compute", "instance", "start", "--id", "fake")
                api.assert_called_with("compute", "instance", "start", "--id", "fake", "--async")
                fc.ctl("compute", "instance", "stop", "--id", "fake")
                api.assert_called_with("compute", "instance", "stop", "--id", "fake", "--async")
                fc.ctl("compute", "instance", "get", "--id", "fake")
                api.assert_called_with("compute", "instance", "get", "--id", "fake")

    def test_resource_limits_cannot_exceed_credit_or_ten_hours(self):
        import r0_nebius as ops
        c={"first_start_epoch":1000,"verified_credit_usd":20,"initial_spend_usd":100}
        h,m=ops.limits(c,105,1000+9*3600)
        self.assertLess(h,1)
        self.assertEqual(m,15)
        h,m=ops.limits(c,125,1000+11*3600)
        self.assertEqual(h,0)
        self.assertLess(m,0)
        c["verified_credit_usd"]=1000
        self.assertEqual(ops.limits(c,100,1000)[1],35)

    def test_archive_exact_bytes_and_compare_scientific_records(self):
        import r0_integrity as integrity
        import tarfile
        with tempfile.TemporaryDirectory() as t:
            a,b=Path(t)/"a",Path(t)/"b"
            for p,w in [(a,1),(b,2)]:
                driver.write_new(p/"units/u.json",{"wall_s":w,"design":[1,2]})
            self.assertTrue(integrity.compare(a,b)["exact"])
            result=integrity.archive(a)
            with tarfile.open(result["archive"]) as archive:
                self.assertEqual(archive.extractfile("a/units/u.json").read(),(a/"units/u.json").read_bytes())
            (b/"units/u.json").write_text('{"design":[0]}',encoding="utf-8")
            with self.assertRaises(ValueError):
                integrity.compare(a,b)


if __name__ == "__main__":
    unittest.main()
