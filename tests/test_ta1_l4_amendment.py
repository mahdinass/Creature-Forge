"""No-physics tests of protocol amendment A1 (paired L4 pilot, phase `2a-L4-pilot`) and the per-seed robust-check record.

Fakes, mocks and read-only checks of the stored DS-1 reference only; every simulation entry point is patched to fail."""
import contextlib
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import ta1_tool_access as ta1                         # noqa: E402
from creature_forge import hidden_plant as hp         # noqa: E402

PILOT = "2a-L4-pilot"
L4 = "hdb-v1-gen-0137:low_ground_friction:0"
RECORDS = os.path.join(os.path.dirname(ROOT), "Creature-Forge", "artifacts", "vm", "ds1", "eval")


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class AmendmentDefinition(unittest.TestCase):
    def test_pilot_runs_and_cap(self):
        self.assertEqual(ta1.planned_runs(PILOT), [("L4", "control", 0), ("L4", "treatment", 0)])
        self.assertEqual(ta1.phase_cap(ta1.planned_runs(PILOT))["total"], 7208)
        self.assertEqual(ta1.phase_cap(ta1.planned_runs(PILOT))["plant"], 1608)
        self.assertEqual(ta1.phase_cap(ta1.planned_runs(PILOT))["twin"], 5600)
        self.assertEqual(ta1.CASES["L4"]["instance_id"], L4)
        self.assertEqual(ta1.stored_record_files(ta1.planned_runs(PILOT)), ["eval_A1e6_s3.jsonl"])
        self.assertIn("eval_A1e6_s3.jsonl", ta1.REFERENCE["stored_records_sha256"])

    def test_preregistered_phases_are_unchanged(self):
        self.assertEqual(ta1.PHASES["1B"], [("L1", "control", 0), ("L1", "treatment", 0)])
        self.assertEqual(ta1.PHASES["2a"], [(c, "treatment", 0) for c in ("L2", "L3", "L4", "L5")])
        self.assertEqual(ta1.PHASES["2a-contingency"], [(c, "control", 0) for c in ("L2", "L3", "L4", "L5")])
        self.assertEqual(len(ta1.PHASES["2b"]), 16)
        self.assertEqual(set(ta1.PHASES), {"1B", "2a", "2a-contingency", "2b", PILOT})

    def test_amendment_is_documented(self):
        a = ta1.AMENDMENT_BY_PHASE[PILOT]
        self.assertEqual((a["id"], a["date"]), ("A1", "2026-10-21"))
        for key in ("amends", "change", "rationale", "unchanged", "overlap", "requires"):
            self.assertTrue(a[key], key)
        self.assertIn("Phase 2a execution order", a["amends"])
        self.assertIn("not authorised by this amendment", a["unchanged"])
        self.assertIn("A1", ta1.__doc__)

    def test_stored_l4_reference_resolves(self):
        if not os.path.isdir(RECORDS):
            self.skipTest("stored DS-1 records not available locally")
        f, line, idx, h = ta1.CASES["L4"]["stored"]
        self.assertEqual(ta1.sha256_file(os.path.join(RECORDS, f)), ta1.REFERENCE["stored_records_sha256"][f])
        rec = ta1.load_stored(RECORDS, f, line)
        self.assertEqual((rec["instance_id"], rec["arm"], rec["submitted"]), (L4, "A1e6", idx))
        self.assertEqual(ta1.design_hash(rec["designs"][idx]), h)
        self.assertEqual((rec["verification"]["status"], round(rec["verification"]["walking_frac"] * 24)), ("PARTIAL_IMPROVEMENT", 19))
        cma = next(e for e in rec["engine"]["events"] if e["kind"] == "tool_screen_cma")
        self.assertNotIn("foot_friction", [r["tool"] for r in cma["ranking"]])     # the treatment changes the order


class RobustEvidence(unittest.TestCase):
    def test_robust_scores_and_baseline_are_recorded(self):
        class B:
            view_seeds = {"robust": list(range(16))}
            scores = {3: {"n": 16, "scores": [6.9] * 16, "pass": [True] * 16}, 4: {"n": 8, "scores": [7.0] * 8, "pass": [True] * 8}}
            _baseline = {"scores": [6.88] * 16, "pass": [False] * 16}
        ev = ta1.robust_evidence(B())
        self.assertEqual(ev["robust_seeds"], list(range(16)))
        self.assertEqual(set(ev["by_design"]), {"3", "4"})
        self.assertEqual(len(ev["by_design"]["3"]["scores"]), 16)
        self.assertEqual(ev["baseline"]["scores"][0], 6.88)
        B.scores[3]["scores"][0] = 0.0                       # deep copy: later mutation does not change the record
        self.assertEqual(ev["by_design"]["3"]["scores"][0], 6.9)

    def test_missing_attributes_are_none(self):
        ev = ta1.robust_evidence(object())
        self.assertEqual(ev, {"robust_seeds": None, "by_design": None, "baseline": None})

    def test_run_episode_records_robust_evidence(self):
        import inspect
        src = inspect.getsource(ta1.run_episode)
        self.assertIn('"robust_checks": robust_evidence(bench)', src)


def _stored():
    return {"instance_id": L4, "arm": "A1e6", "submitted": 1, "designs": [{"body": {"a": 1}, "vector": [0.0]}, {"body": {"a": 2}, "vector": [0.1]}],
            "verification": {"status": "PARTIAL_IMPROVEMENT", "walking_frac": 19 / 24,
                             "reasons": ["candidate aggregate is POOR, not PASS (walking on 19 of 24 seeds; PASS needs >= 80%)"],
                             "rollouts": {"validation": 48, "confirmation": 0, "confirmation_rollout_equivalents": 0.0}},
            "check": {"walking": 2, "n": 8, "labels": ["contact_chatter"] * 6 + ["walking"] * 2, "rollouts": 8},
            "strength": 2.5672650973122204, "mult": 1.0,
            "engine": {"events": [{"seq": 0, "kind": "tool_screen"}, {"seq": 1, "kind": "assimilated_check"}],
                       "history": [{"label": "after_observation"}], "particles": [],
                       "ledger": {"used": 700, "lines": [{"item": "observe", "n": 4}, {"item": "repair", "n": 696}],
                                  "twin": {"used": 2514, "lines": [{"item": "twin_observe", "n": 4}, {"item": "twin_cma", "n": 2510}]}}}}


def _episode(stored, arm, fp="F"):
    rec = copy.deepcopy(stored)
    rec["engine"]["events"].insert(1, {"seq": 1, "kind": "engineer_plan", "plan": {}})
    rec["verification"] = {"summary": dict(stored["verification"]), "full": {}}
    rec["harness"] = {"ta1_arm": arm, "replicate": 0, "noise_seed": 1751409197, "verification_complete": True,
                      "verification_problems": [], "rescreen": {"classification": "no re-screen"},
                      "resources": {"total_rollout_equivalents": 3270}, "robust_checks": {"by_design": {}},
                      "hook_calls": [{"prehook_fingerprint": fp, "prehook_component_fingerprints": {"ledgers": fp},
                                      "prehook_n_plant_lines": 1, "prehook_n_twin_lines": 1, "prehook_n_events": 1,
                                      "prehook_n_history": 1}]}
    return rec


class PilotExecutionGates(unittest.TestCase):
    def _run(self, recs):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        f, line, _, _ = ta1.CASES["L4"]["stored"]
        _write(os.path.join(d, f), "{}\n" * (line - 1) + json.dumps(_stored()) + "\n")
        out = os.path.join(d, "out", "ta1_l4.jsonl")
        a = __import__("argparse").Namespace(out=out, records_root=d, approved_by="unit test", harness_commit="9" * 40, workers=0,
                                             phase=PILOT, max_rollouts=7208, max_wall_s=0.0)
        run = mock.Mock(side_effect=recs)
        with mock.patch("sys.stdout"):
            code = ta1._execute(a, ta1.planned_runs(PILOT), {}, ta1.phase_cap(ta1.planned_runs(PILOT)),
                                build_fn=mock.Mock(return_value={"instance_id": L4}), run_fn=run,
                                pool_cm=contextlib.nullcontext(None))
        with open(out, encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
        with open(ta1.manifest_path(out), encoding="utf-8") as fh:
            manifest = json.load(fh)
        return code, run, rows, manifest

    def test_valid_pilot_passes_gates_and_documents_the_amendment(self):
        st = _stored()
        code, run, rows, manifest = self._run([_episode(st, "control"), _episode(st, "treatment")])
        self.assertEqual((code, run.call_count), (0, 2))
        self.assertTrue(rows[0]["harness"]["reproduction"]["exact"])
        self.assertTrue(rows[1]["harness"]["stored_prefix"]["match"])
        self.assertTrue(rows[1]["harness"]["paired_prehook"]["equal"])
        self.assertEqual(manifest["amendment"]["id"], "A1")
        self.assertEqual(manifest["runs"], [["L4", "control", 0], ["L4", "treatment", 0]])

    def test_control_not_reproducing_stops_before_treatment(self):
        st = _stored()
        c = _episode(st, "control")
        c["engine"]["ledger"]["twin"]["used"] = 2515
        code, run, rows, _ = self._run([c, _episode(st, "treatment")])
        self.assertEqual((code, run.call_count, len(rows)), (ta1.PAUSE_EXIT, 1, 1))

    def test_fingerprint_mismatch_stops(self):
        st = _stored()
        code, _, rows, _ = self._run([_episode(st, "control"), _episode(st, "treatment", fp="G")])
        self.assertEqual(code, ta1.PAUSE_EXIT)
        self.assertFalse(rows[1]["harness"]["paired_prehook"]["equal"])


class Guards(unittest.TestCase):
    def setUp(self):
        boom = mock.Mock(side_effect=AssertionError("simulation attempted"))
        self.p = [mock.patch.object(hp, n, boom) for n in ("plant_rollout", "walk_seeds", "observe", "plant_cma", "verify")]
        self.p += [mock.patch.object(ta1, "build_instance", boom), mock.patch.object(ta1, "run_episode", boom)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_dry_run_and_refusals(self):
        outside = os.path.join(tempfile.gettempdir(), "ta1_l4_unit_never_written.jsonl")
        with mock.patch("sys.stdout"), mock.patch.object(ta1, "_execute", mock.Mock(side_effect=AssertionError("executed"))):
            self.assertEqual(ta1.main(["--phase", PILOT]), 0)
            self.assertEqual(ta1.main(["--phase", PILOT, "--execute"]), 2)
            self.assertEqual(ta1.main(["--phase", PILOT, "--execute", "--approved-by", "x", "--max-rollouts", "7207",
                                       "--out", outside]), 2)
            self.assertEqual(ta1.main(["--phase", PILOT, "--execute", "--approved-by", "x", "--max-rollouts", "7208",
                                       "--harness-commit", "0" * 40, "--out", outside]), 2)     # not HEAD
            with self.assertRaises(ValueError):
                ta1.main(["--phase", PILOT, "--cases", "L4"])      # --cases belongs to 2a-contingency only
        self.assertFalse(os.path.exists(outside))

    def test_cases_flag_is_rejected_for_the_pilot(self):
        with self.assertRaises(ValueError):
            ta1.planned_runs(PILOT, cases=["L4"])

    def test_complete_command_reaches_execution_with_the_pilot_runs(self):
        with tempfile.TemporaryDirectory() as d:
            for name in (ta1.A1E6["thresholds"], ta1.A1E6["walkers"]):
                _write(os.path.join(d, name), name)
            with mock.patch.object(ta1, "preflight_refusals", mock.Mock(return_value=[])), \
                    mock.patch.object(ta1, "_execute", mock.Mock(return_value=0)) as ex, mock.patch("sys.stdout"):
                code = ta1.main(["--phase", PILOT, "--execute", "--approved-by", "owner (unit test)", "--harness-commit", "9" * 40,
                                 "--max-rollouts", "7208", "--artifacts-root", d, "--records-root", d,
                                 "--out", os.path.join(d, "out", "l4.jsonl")])
            self.assertEqual((code, ex.call_count), (0, 1))
            self.assertEqual(ex.call_args[0][1], [("L4", "control", 0), ("L4", "treatment", 0)])

    def test_import_and_dry_run_never_step_physics(self):
        import subprocess
        code = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
                "import mujoco\n"
                "def boom(*a, **k):\n    raise SystemExit(7)\n"
                "mujoco.mj_step = boom\n"
                "from creature_forge import hidden_plant as hp\n"
                "for n in ('plant_rollout', 'walk_seeds', 'observe', 'plant_cma', 'verify'): setattr(hp, n, boom)\n"
                "import ta1_tool_access as t\n"
                "assert t.main(['--phase', %r]) == 0\n"
                "print('no-physics-ok')\n") % (ROOT, os.path.join(ROOT, "scripts"), PILOT)
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertIn("no-physics-ok", p.stdout)


if __name__ == "__main__":
    unittest.main()
