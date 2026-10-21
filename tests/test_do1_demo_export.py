"""No-physics tests of the DO-1 demo exporter (scripts/do1_demo_export.py).

They read the committed, audited DO1-L4-r0 record and drive the fidelity gate with fake replays. Nothing is simulated:
hidden_plant.plant_rollout and recovery.run_walk_seeds are patched to fail if anything reaches them.
"""
from __future__ import annotations

import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)

import do1_demo_export as dx  # noqa: E402

RECORD = os.path.join(ROOT, dx.RECORD_REL)


def _no_physics(*a, **k):
    raise AssertionError("a no-physics test reached a simulation")


class _Fixture:
    loaded = dx.load_record(RECORD)
    st = dx.stored_rows(loaded)


def _inst(st, loaded, **over):
    faulty = dx.designs_of(loaded)["faulty"]
    inst = {"seeds": {"validate": list(st["seeds"]["validate"]), "confirm": list(st["seeds"]["confirm"])},
            "robot": {"body": faulty["body"], "vector": faulty["vector"]}, "plant": {"deviation": []}}
    inst.update(over)
    return inst


def _fakes(st, *, bad_production=None, bad_trace=None):
    """Replays that return the stored rows, optionally with one field changed (to prove the gate fails closed)."""
    stored = {"validate": {k: st["rows"][k] for k in dx.DESIGNS}, "confirm": {"do1": st["rows"]["do1_confirm"]}}

    def which(design, seeds):
        name = next(k for k, v in dx.designs_of(_Fixture.loaded).items() if dx.ta1.design_hash(v) == dx.ta1.design_hash(design))
        part = "confirm" if list(seeds) == st["seeds"]["confirm"] else "validate"
        return name, part

    def production(inst, design, seeds, duration, variation, pool):
        name, part = which(design, seeds)
        rows = copy.deepcopy(stored[part][name])
        if bad_production and bad_production[0] == (name, part):
            rows[bad_production[1]]["score"] = rows[bad_production[1]]["score"] + 1e-12
        return rows

    def traced(inst, design, seeds, seed, duration, variation):
        name, part = which(design, seeds)
        row = copy.deepcopy(next(r for r in stored[part][name] if r["seed"] == seed))
        trow = {k: row[k] for k in dx.METRIC_FIELDS + ("seed", "walking", "perturb", "push_time", "friction_used")}
        if bad_trace and bad_trace == (name, part, seed):
            trow["label"] = "fall" if trow["label"] != "fall" else "walking"
        return {"t": [0.0, duration]}, trow, design["body"]

    def frames(inst, body, tr, max_hz):
        return {"fk_max_err_m": 0.0}

    def payload(name, design, body, seed, duration, tr, fr, row):
        return {"seed": seed, "do1_demo": {"design": name, "fk_max_err_m": fr["fk_max_err_m"], "evidence_row": row}}

    return {"production_fn": production, "traced_fn": traced, "frames_fn": frames, "payload_fn": payload}


@mock.patch("creature_forge.hidden_plant.plant_rollout", _no_physics)
@mock.patch("creature_forge.recovery.run_walk_seeds", _no_physics)
class Do1DemoExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="do1demo_test_")
        self.loaded, self.st = _Fixture.loaded, _Fixture.st

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_record_hash_refusal(self):
        bad = os.path.join(self.tmp, "do1_l4_r0.jsonl")
        shutil.copy(RECORD, bad)
        shutil.copy(dx.ta1.manifest_path(RECORD), dx.ta1.manifest_path(bad))
        self.assertEqual(dx.load_record(bad)["manifest"]["phase"], "DO1-L4-r0")   # an exact copy passes
        with open(bad, "ab") as fh:
            fh.write(b"\n")
        with self.assertRaisesRegex(dx.FidelityError, "not the audited"):
            dx.load_record(bad)

    def test_designs_and_hashes(self):
        d = dx.designs_of(self.loaded)
        self.assertEqual({k: dx.ta1.design_hash(v) for k, v in d.items() if k != "faulty"}, dx.DESIGN_HASHES)
        self.assertEqual(len(d["faulty"]["vector"]), 17)

    def test_aggregates_match_the_audit(self):
        agg = dx.aggregates(self.st)
        self.assertEqual((agg["walking"]["frozen"], agg["walking"]["do1"], agg["walking"]["do1_confirm"]), (19, 21, 22))
        self.assertAlmostEqual(agg["median_score_m"]["faulty"], 2.336818, places=6)
        self.assertAlmostEqual(agg["median_score_m"]["frozen"], 3.429721, places=6)
        self.assertAlmostEqual(agg["median_score_m"]["do1"], 3.052606, places=6)
        self.assertEqual(agg["status"], {"frozen": "PARTIAL_IMPROVEMENT", "do1": "FULL_RECOVERY"})

    def test_default_seed_rule(self):
        s = dx.default_seed(self.st["rows"])
        fr = next(r for r in self.st["rows"]["frozen"] if r["seed"] == s)
        do = next(r for r in self.st["rows"]["do1"] if r["seed"] == s)
        self.assertFalse(fr["walking"])
        self.assertTrue(do["walking"])
        earlier = [i for i, r in enumerate(self.st["rows"]["frozen"]) if r["seed"] == s][0]
        for f, d in zip(self.st["rows"]["frozen"][:earlier], self.st["rows"]["do1"][:earlier]):
            self.assertFalse(not f["walking"] and d["walking"])
        rows = {"frozen": [{"seed": 1, "walking": True}], "do1": [{"seed": 1, "walking": True}]}
        with self.assertRaises(dx.FidelityError):
            dx.default_seed(rows)

    def test_row_mismatches_are_exact(self):
        rows = self.st["rows"]["do1"]
        self.assertEqual(dx.row_mismatches(rows, copy.deepcopy(rows)), [])
        tweaked = copy.deepcopy(rows)
        tweaked[3]["score"] += 1e-15
        self.assertEqual(len(dx.row_mismatches(rows, tweaked)), 1)
        self.assertIn("seed lists differ", dx.row_mismatches(rows, rows[:-1])[0])
        self.assertIn("seed lists differ", dx.row_mismatches(rows, rows + rows[:1])[0])

    def test_export_writes_only_when_every_row_matches(self):
        out = os.path.join(self.tmp, "demo")
        index = dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None, **_fakes(self.st))
        self.assertEqual(index["fidelity"]["trace_rows_exact"], 96)
        self.assertEqual(index["default_seed"], dx.default_seed(self.st["rows"]))
        self.assertEqual(len(index["files"]), 96)
        with open(os.path.join(out, "index.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["provenance"]["arms_provenance"], "NO_AI (A1e6, no Nemotron)")
        self.assertIn(dx.CAPTIONS["attribution"], json.dumps(index))
        with self.assertRaisesRegex(dx.FidelityError, "refusing to overwrite"):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None, **_fakes(self.st))

    def test_production_mismatch_writes_nothing(self):
        out = os.path.join(self.tmp, "demo")
        with self.assertRaisesRegex(dx.FidelityError, "production frozen"):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None,
                      **_fakes(self.st, bad_production=(("frozen", "validate"), 5)))
        self.assertFalse(os.path.exists(out))
        self.assertEqual([p for p in os.listdir(self.tmp) if p.startswith("do1demo_")], [])

    def test_trace_mismatch_writes_nothing(self):
        out = os.path.join(self.tmp, "demo")
        seed = self.st["seeds"]["confirm"][7]
        with self.assertRaisesRegex(dx.FidelityError, "trace do1 20s"):
            dx.export(self.loaded, self.st, _inst(self.st, self.loaded), out, pool=None,
                      **_fakes(self.st, bad_trace=("do1", "confirm", seed)))
        self.assertFalse(os.path.exists(out))

    def test_instance_must_match_the_record(self):
        out = os.path.join(self.tmp, "demo")
        wrong = _inst(self.st, self.loaded)
        wrong["seeds"]["validate"] = wrong["seeds"]["validate"][::-1]
        with self.assertRaisesRegex(dx.FidelityError, "verification seeds"):
            dx.export(self.loaded, self.st, wrong, out, pool=None, **_fakes(self.st))
        other = _inst(self.st, self.loaded, robot={"body": dx.designs_of(self.loaded)["do1"]["body"],
                                                  "vector": dx.designs_of(self.loaded)["do1"]["vector"]})
        with self.assertRaisesRegex(dx.FidelityError, "nominal robot"):
            dx.export(self.loaded, self.st, other, out, pool=None, **_fakes(self.st))

    def test_dry_run_simulates_nothing(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dx.main(["--out", os.path.join(self.tmp, "demo")])
        self.assertEqual(rc, 0)
        text = buf.getvalue()
        self.assertIn("Dry run: nothing was simulated", text)
        self.assertIn("walking 21/24", text)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "demo")))

    def test_execute_refuses_without_approval_and_inputs(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = dx.main(["--execute", "--out", os.path.join(self.tmp, "demo")])
        self.assertEqual(rc, 2)
        self.assertIn("--approved-by is required", buf.getvalue())
        self.assertIn("--artifacts-root is required", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
