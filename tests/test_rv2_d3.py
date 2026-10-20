"""No-physics tests of the X1 post-hoc exploratory verification of TA-1 treatment candidate d3 (scripts/rv2_d3_reverify.py).

Fakes, mocks and read-only checks of the pinned files only; every simulation entry point is patched to fail."""
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

import rv2_d3_reverify as rv2                         # noqa: E402
import ta1_tool_access as ta1                         # noqa: E402
from creature_forge import hidden_plant as hp         # noqa: E402

RUNS = os.path.join(os.path.dirname(ROOT), "creature_forge_runs")
TA1_OUT = os.path.join(RUNS, "fa1c_phase1b_2026-10-20", "ta1_phase1b.jsonl")
P1A_OUT = os.path.join(RUNS, "fa1c_phase1a_2026-10-20", "rv1_phase1a.jsonl")
L1 = rv2.L1


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _rows(seeds, score, label="walking", walking=True):
    keys = ta1.VALIDATION_ROW_FIELDS
    return [{**{k: 0.5 for k in keys}, "seed": s, "score": score(i), "label": label, "walking": walking, "outcome": "PASS"}
            for i, s in enumerate(seeds)]


def _full(cand_score, status="NOT_RECOVERED", confirm=False):
    seeds = list(range(63230784, 63230808))
    vd = {k: 0 for k in ta1.VERDICT_FIELDS}
    vd.update(status="INCONCLUSIVE", median_diff=0.01, reasons=["x"], min_effect={"required": 0.5})
    out = {"status": status, "reasons": [] if status == "FULL_RECOVERY" else ["verdict_v1 is INCONCLUSIVE, not VERIFIED_IMPROVEMENT"],
           "validation": {"original": _rows(seeds, lambda i: 6.9 + 0.001 * i, "contact_chatter", False),
                          "candidate": _rows(seeds, cand_score), "verdict": vd, "aggregate": "PASS", "walking_frac": 1.0},
           "confirmation": ({"run": True, "per_seed": _rows(range(900, 924), lambda i: 13.0), "checks": {"walking_frac": {}},
                             "passed": True} if confirm else {"run": False, "reason": "validation conditions not met"}),
           "rollouts": {"validation": 48, "confirmation": 24 if confirm else 0,
                        "confirmation_rollout_equivalents": 48.0 if confirm else 0.0},
           "seeds": {"validate": seeds, "confirm": list(range(900, 924))}}
    return out


def _stored():
    return {"arm": "A1e6", "check": {"walking": 0, "n": 8, "labels": ["contact_chatter"] * 8, "rollouts": 8},
            "strength": 0.6234786664901107, "mult": 1.7, "severity": 2, "family": "low_ground_friction"}


class PinnedInputs(unittest.TestCase):
    """Reads the real Phase 1B / Phase 1A outputs (data only) to confirm the pins; skipped where they are absent."""

    def test_d3_resolves_exactly(self):
        if not os.path.isfile(TA1_OUT):
            self.skipTest("Phase 1B output not available")
        r = rv2.resolve_d3(TA1_OUT)
        self.assertEqual(r["problems"], [])
        self.assertAlmostEqual(r["design"]["body"]["foot_friction"], 1.992713483600537, places=12)
        self.assertEqual(r["record"]["submitted"], 4)                      # d3 was discarded, d4 submitted
        self.assertEqual(r["record"]["harness"]["hook_calls"][0]["plan"], {"tool_order": ["foot_friction"]})
        self.assertEqual(rv2.legality_problems(r["design"]), [])

    def test_phase1a_faulty_rows_resolve(self):
        if not os.path.isfile(P1A_OUT):
            self.skipTest("Phase 1A output not available")
        r = rv2.resolve_phase1a(P1A_OUT)
        self.assertEqual(r["problems"], [])
        self.assertEqual(len(r["row"]["verification"]["full"]["validation"]["original"]), 24)

    def test_wrong_files_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "ta1_phase1b.jsonl")
            _write(p, "{}\n{}\n")
            self.assertIn("sha256", rv2.resolve_d3(p)["problems"][0])
            self.assertIn("sha256", rv2.resolve_phase1a(p)["problems"][0])

    def test_pins_reject_a_tampered_record(self):
        if not os.path.isfile(TA1_OUT):
            self.skipTest("Phase 1B output not available")
        with tempfile.TemporaryDirectory() as d:
            with open(TA1_OUT, encoding="utf-8") as fh:
                lines = fh.readlines()
            rec = json.loads(lines[1])
            rec["designs"][3]["body"]["foot_friction"] = 1.99
            p = os.path.join(d, "ta1_phase1b.jsonl")
            _write(p, lines[0] + json.dumps(rec) + "\n")
            with mock.patch.dict(rv2.TA1_RECORD, {"sha256": ta1.sha256_file(p)}):
                probs = rv2.resolve_d3(p)["problems"]
            self.assertTrue(any("design hash" in x for x in probs), probs)


class Legality(unittest.TestCase):
    def test_bounds_are_enforced_without_physics(self):
        if not os.path.isfile(TA1_OUT):
            self.skipTest("Phase 1B output not available")
        d = rv2.resolve_d3(TA1_OUT)["design"]
        bad = copy.deepcopy(d)
        bad["body"]["foot_friction"] = 2.05
        self.assertTrue(rv2.legality_problems(bad))
        bad = copy.deepcopy(d)
        bad["vector"] = bad["vector"][:16]
        self.assertTrue(rv2.legality_problems(bad))


class Evidence(unittest.TestCase):
    def test_paired_table_counts_ties_wins_losses(self):
        t = rv2.paired_table(_full(lambda i: 6.9 + 0.001 * i + (0.0 if i < 12 else 0.2 if i < 18 else -0.3)))
        self.assertEqual((t["n"], t["ties"], t["wins"], t["losses"]), (24, 12, 6, 6))
        self.assertEqual(t["rows"][0]["faulty_label"], "contact_chatter")
        self.assertEqual(set(t["verdict"]), set(ta1.VERDICT_FIELDS))

    def test_faulty_rows_must_match_phase1a_exactly(self):
        full = _full(lambda i: 7.0)
        ref = {"verification": {"full": copy.deepcopy(full)}}
        self.assertTrue(rv2.faulty_rows_check(full, ref)["exact"])
        ref["verification"]["full"]["validation"]["original"][5]["score"] += 1e-9
        res = rv2.faulty_rows_check(full, ref)
        self.assertFalse(res["exact"])
        self.assertFalse(res["checks"]["faulty_rows"])

    def test_preregistered_reading_and_label(self):
        self.assertIn("passes the frozen verifier on L1", rv2.preregistered_reading("FULL_RECOVERY"))
        self.assertIn("exploratory, single design", rv2.preregistered_reading("FULL_RECOVERY"))
        self.assertIn("no verified recovery", rv2.preregistered_reading("NOT_RECOVERED"))
        self.assertIn("no verified recovery", rv2.preregistered_reading("PARTIAL_IMPROVEMENT"))
        self.assertTrue(rv2.STUDY["design_selected_after_results"])
        self.assertIn("post-hoc exploratory", rv2.STUDY["label"])
        self.assertEqual(rv2.CAP, 104)


class FailClosedExecution(unittest.TestCase):
    def _run(self, verify_result, inst_check=None, robot=None):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        out = os.path.join(d, "x1.jsonl")
        a = __import__("argparse").Namespace(out=out, approved_by="unit test", harness_commit="9" * 40, workers=0,
                                             ta1_record=os.path.join(d, "t"), phase1a_record=os.path.join(d, "p"),
                                             records_root=d)
        stored = _stored()
        d3 = {"record": dict(stored), "design": {"body": {"foot_friction": 1.99}, "vector": [0.0] * 17}}
        inst = {**copy.deepcopy(stored), **(inst_check or {})}
        inst["robot"] = robot or {"body": {"marker": 1}, "vector": [0.0]}
        verify = mock.Mock(return_value=verify_result)
        p1a = {"verification": {"full": _full(lambda i: 0.0)}}
        with mock.patch.dict(rv2.TA1_RECORD, {"original_design_hash": ta1.design_hash({"body": {"marker": 1}, "vector": [0.0]})}), \
                mock.patch("sys.stdout"):
            code = rv2._execute(a, {}, d3, dict(stored), p1a, build_fn=lambda iid, inputs, pool=None: inst, verify_fn=verify,
                                pool_cm=contextlib.nullcontext(None))
        with open(out, encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
        return code, verify, rows, out

    def test_outcome_is_recorded_with_full_paired_evidence(self):
        for status, confirm in (("NOT_RECOVERED", False), ("FULL_RECOVERY", True)):
            code, verify, rows, out = self._run(_full(lambda i: 6.9 + 0.001 * i, status, confirm))
            self.assertEqual((code, verify.call_count), (0, 1))
            row = rows[-1]
            self.assertEqual([r["kind"] for r in rows], ["instance_check", "design"])
            self.assertTrue(row["faulty_rows_vs_phase1a"]["exact"])
            self.assertEqual(row["paired"]["ties"], 24)
            self.assertEqual(row["study"]["label"], rv2.STUDY["label"])
            self.assertEqual(bool(row["verification"]["full"]["confirmation"]["run"]), confirm)
            if confirm:
                self.assertEqual(len(row["verification"]["full"]["confirmation"]["per_seed"]), 24)
            with open(ta1.manifest_path(out), encoding="utf-8") as fh:
                m = json.load(fh)
            self.assertEqual(m["cap"], 104)
            self.assertIn("preregistered_reading", m)

    def test_instance_mismatch_pauses_before_verification(self):
        code, verify, rows, _ = self._run(_full(lambda i: 7.0), inst_check={"strength": 0.62})
        self.assertEqual((code, verify.call_count, len(rows)), (ta1.PAUSE_EXIT, 0, 1))

    def test_wrong_original_design_pauses_before_verification(self):
        code, verify, rows, _ = self._run(_full(lambda i: 7.0), robot={"body": {"marker": 2}, "vector": [0.0]})
        self.assertEqual((code, verify.call_count), (ta1.PAUSE_EXIT, 0))

    def test_faulty_row_mismatch_is_written_but_flagged(self):
        full = _full(lambda i: 7.0)
        full["validation"]["original"][0]["score"] = 99.0
        code, verify, rows, _ = self._run(full)
        self.assertEqual((code, verify.call_count, len(rows)), (ta1.PAUSE_EXIT, 1, 2))
        self.assertFalse(rows[-1]["faulty_rows_vs_phase1a"]["exact"])

    def test_incomplete_record_pauses(self):
        full = _full(lambda i: 7.0)
        full["validation"]["candidate"] = full["validation"]["candidate"][:20]
        code, _, rows, _ = self._run(full)
        self.assertEqual(code, ta1.PAUSE_EXIT)
        self.assertTrue(rows[-1]["verification_problems"])


class Guards(unittest.TestCase):
    def setUp(self):
        boom = mock.Mock(side_effect=AssertionError("simulation attempted"))
        self.p = [mock.patch.object(hp, n, boom) for n in ("plant_rollout", "walk_seeds", "observe", "plant_cma", "verify")]
        self.p += [mock.patch.object(ta1, "build_instance", boom), mock.patch.object(rv2, "_execute", boom)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_dry_run_and_refusals(self):
        outside = os.path.join(tempfile.gettempdir(), "x1_unit_test_never_written.jsonl")
        base = ["--ta1-record", TA1_OUT, "--phase1a-record", P1A_OUT]
        with mock.patch("sys.stdout"):
            self.assertEqual(rv2.main(base), 0)
            self.assertEqual(rv2.main(base + ["--execute"]), 2)
            self.assertEqual(rv2.main(base + ["--execute", "--phase", "X1", "--approved-by", "x", "--max-rollouts", "103",
                                              "--out", outside]), 2)
            self.assertEqual(rv2.main(base + ["--execute", "--phase", "X1", "--approved-by", "x", "--max-rollouts", "104",
                                              "--out", os.path.join(ROOT, "x1.jsonl")]), 2)
            self.assertEqual(rv2.main(["--execute", "--phase", "X1", "--approved-by", "x", "--max-rollouts", "104",
                                       "--out", outside]), 2)          # pinned records missing
        self.assertFalse(os.path.exists(outside))

    def test_complete_command_reaches_execution(self):
        if not (os.path.isfile(TA1_OUT) and os.path.isfile(P1A_OUT)):
            self.skipTest("pinned outputs not available")
        with tempfile.TemporaryDirectory() as d:
            for name in (ta1.A1E6["thresholds"], ta1.A1E6["walkers"]):
                _write(os.path.join(d, name), name)
            _write(os.path.join(d, rv2.DS1_RECORD[0]), json.dumps(_stored()) + "\n")
            with mock.patch.object(ta1, "preflight_refusals", mock.Mock(return_value=[])), \
                    mock.patch.object(rv2, "_execute", mock.Mock(return_value=0)) as ex, mock.patch("sys.stdout"):
                code = rv2.main(["--ta1-record", TA1_OUT, "--phase1a-record", P1A_OUT, "--execute", "--phase", "X1",
                                 "--approved-by", "owner (unit test)", "--harness-commit", "9" * 40, "--max-rollouts", "104",
                                 "--artifacts-root", d, "--records-root", d, "--out", os.path.join(d, "out", "x1.jsonl")])
            self.assertEqual((code, ex.call_count), (0, 1))

    def test_import_and_dry_run_never_step_physics(self):
        import subprocess
        code = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
                "import mujoco\n"
                "def boom(*a, **k):\n    raise SystemExit(7)\n"
                "mujoco.mj_step = boom\n"
                "from creature_forge import hidden_plant as hp\n"
                "for n in ('plant_rollout', 'walk_seeds', 'observe', 'plant_cma', 'verify'): setattr(hp, n, boom)\n"
                "import rv2_d3_reverify as r\n"
                "assert r.main(['--ta1-record', %r, '--phase1a-record', %r]) == 0\n"
                "print('no-physics-ok')\n") % (ROOT, os.path.join(ROOT, "scripts"), TA1_OUT, P1A_OUT)
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertIn("no-physics-ok", p.stdout)


if __name__ == "__main__":
    unittest.main()
