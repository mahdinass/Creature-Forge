import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from creature_forge import lab
from creature_forge.studio.app import create_app

DEMO = lab.DEMO_DIR
REJECTED = "20261013T010325Z-9d9310"  # forensic prompt, valid hypothesis, rejected by the verifier
INVALID = "20261013T010405Z-9a3be8"  # model reply failed validation; never tested in MuJoCo
FIRST = "20261013T002054Z-aaad96"  # first live trial (legacy evidence)


def load(tid):
    return json.loads((DEMO / f"{tid}.json").read_text(encoding="utf-8"))


class DemoRecordTests(unittest.TestCase):
    """The bundled records must be exactly the real, unedited trials and must not overstate results."""

    def test_manifest_hashes_match_files_byte_for_byte(self):
        man = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))["trials"]
        files = sorted(p.stem for p in DEMO.glob("2*.json"))
        self.assertEqual(files, sorted(man))
        self.assertEqual(len(files), 4)
        for tid in files:
            self.assertEqual(hashlib.sha256((DEMO / f"{tid}.json").read_bytes()).hexdigest(), man[tid]["sha256"], tid)

    def test_no_fabricated_success_and_all_are_live_records(self):
        statuses = {t: load(t)["status"] for t in (p.stem for p in DEMO.glob("2*.json"))}
        self.assertNotIn("accepted", statuses.values())
        self.assertEqual(sorted(statuses.values()), ["invalid_model_output", "rejected_by_verifier",
                                                     "rejected_by_verifier", "rejected_by_verifier"])
        for tid in statuses:
            t = load(tid)
            self.assertEqual(t["mode"], "live")
            self.assertEqual(t["model_call"]["http_status"], 200)

    def test_records_contain_no_credentials(self):
        pattern = re.compile(r"(sk-[A-Za-z0-9]{8,}|bearer\s+[A-Za-z0-9._-]{12,}|api[_-]?key\s*[:=]\s*\S{8,})", re.I)
        for p in DEMO.glob("*.json"):
            self.assertIsNone(pattern.search(p.read_text(encoding="utf-8")), p.name)

    def test_lab_module_makes_no_model_calls(self):
        src = (Path(lab.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("NebiusClient", src)
        self.assertNotIn("urllib", src)


class ListLoadViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.local = self.tmp / "local"
        self.local.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fresh_install_lists_only_bundled_demo_records(self):
        rows = lab.list_lab_trials(self.local / "missing", DEMO)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["source"] == "bundled-demo" and r["readable"] for r in rows))
        self.assertEqual([r["trial_id"] for r in rows], sorted((r["trial_id"] for r in rows), reverse=True))

    def test_local_record_listed_once_and_unreadable_files_are_surfaced(self):
        shutil.copy(DEMO / f"{REJECTED}.json", self.local)
        (self.local / "20269999T000000Z-bad000.json").write_text("{not json", encoding="utf-8")
        (self.local / "20269999T000000Z-mism00.json").write_text(json.dumps({"trial_id": "other"}), encoding="utf-8")
        rows = {r["trial_id"]: r for r in lab.list_lab_trials(self.local, DEMO)}
        self.assertEqual(len([1 for r in lab.list_lab_trials(self.local, DEMO) if r["trial_id"] == REJECTED]), 1)
        self.assertEqual(rows[REJECTED]["source"], "local")
        self.assertTrue(rows[REJECTED]["also_bundled"])
        self.assertFalse(rows["20269999T000000Z-bad000"]["readable"])
        self.assertEqual(rows["20269999T000000Z-bad000"]["status"], "unreadable")
        self.assertFalse(rows["20269999T000000Z-mism00"]["readable"])

    def test_load_rejects_bad_ids_and_reports_missing(self):
        for bad in ("../manifest", "..\\x", "a/b", "", "x" * 80):
            with self.assertRaises(lab.LabError):
                lab.load_lab_trial(bad, self.local, DEMO)
        with self.assertRaises(KeyError):
            lab.load_lab_trial("20260101T000000Z-nope00", self.local, DEMO)

    def test_view_of_rejected_trial_separates_claims_from_measurements(self):
        v = lab.lab_view(load(REJECTED), "bundled-demo", DEMO)
        self.assertEqual(v["outcome"]["status"], "rejected_by_verifier")
        self.assertTrue(all(v["sections"][k] for k in ("observe", "hypothesis", "intervene", "verify", "compare")))
        self.assertEqual(set(v["provenance"]), {"observed", "hypothesis", "confidence", "measured"})
        self.assertIn("Untrusted", v["provenance"]["hypothesis"])
        self.assertIn("never used by the verifier", v["provenance"]["confidence"])
        self.assertIn("untrusted", v["rationale"]["source"])
        self.assertEqual(v["integrity"]["verified"], True)
        self.assertEqual(v["design_change"]["parameter"], "torso_mass")
        self.assertEqual(v["missing"], [])

    def test_view_reports_evidence_and_screening_seeds_separately_from_saved_metadata(self):
        v = lab.lab_view(load(REJECTED), "bundled-demo", DEMO)
        self.assertEqual(v["seeds"], {"evidence": [0, 1, 2], "screening": [0, 1, 2, 3, 4]})
        t = load(REJECTED)  # future experiment with other seeds: the view must follow the record, not constants
        t["config"]["evidence_seeds"], t["config"]["verify_seeds"] = [7, 8], [8, 9, 10]
        t["measured_outcome"]["seeds"] = [8, 9, 10]
        self.assertEqual(lab.lab_view(t, "local", DEMO)["seeds"], {"evidence": [7, 8], "screening": [8, 9, 10]})
        inv = lab.lab_view(load(INVALID), "bundled-demo", DEMO)  # never screened: no screening seeds claimed from outcome
        self.assertEqual(inv["seeds"]["evidence"], [0, 1, 2])

    def test_view_of_invalid_response_has_no_hypothesis_or_verdict_and_labels_raw_reply(self):
        v = lab.lab_view(load(INVALID), "bundled-demo", DEMO)
        self.assertEqual(v["outcome"]["status"], "invalid_model_output")
        self.assertFalse(v["sections"]["hypothesis"] or v["sections"]["verify"] or v["sections"]["compare"])
        self.assertTrue(v["sections"]["observe"])
        self.assertIn("cited evidence path does not exist", v["outcome"]["reason"])
        self.assertIsNone(v["design_change"])
        self.assertIn("Untrusted", v["raw_model_reply"]["note"])
        self.assertIn("no valid hypothesis", " ".join(v["missing"]))
        self.assertTrue(v["replay"]["available"] and not v["replay"]["has_candidate"])

    def test_legacy_trial_reports_missing_forensics_instead_of_failing(self):
        v = lab.lab_view(load(FIRST), "bundled-demo", DEMO)
        self.assertTrue(any("forensic timeline" in m for m in v["missing"]))
        self.assertIsNone(v["observed"]["timeline"])

    def test_malformed_and_empty_records_degrade_gracefully(self):
        broken = {"trial_id": "20260101T000000Z-brk000", "status": "started", "config": {},
                  "observed_evidence": {"scenario": {}}, "hypothesis": {"claim": "x"}}  # missing most fields
        v = lab.lab_view(broken, "local", DEMO)
        self.assertIn("degraded", v)
        self.assertFalse(v["replay"]["available"])
        empty = lab.lab_view({"trial_id": "20260101T000000Z-emp000", "status": "model_error", "config": {}}, "local", DEMO)
        self.assertFalse(any(empty["sections"].values()))
        self.assertIn("no observed evidence was saved", empty["missing"])


class ReplayTests(unittest.TestCase):
    """Replay re-runs MuJoCo from saved parameters (no model) and must reproduce the saved statistics."""

    def test_replay_reproduces_saved_per_seed_statistics_for_both_designs(self):
        r = lab.build_replay(load(REJECTED), 1)
        self.assertEqual(r["engine"]["model_calls"], 0)
        for arm in ("baseline", "candidate"):
            c = r["consistency"][arm]
            self.assertTrue(c["checked"], arm)
            self.assertTrue(c["matches_saved_record"], c["failures"])
        self.assertEqual(r["baseline"]["body"]["torso_mass"], 5.0)
        self.assertEqual(r["candidate"]["body"]["torso_mass"], 3.0)
        # only the proposed parameter differs; controller, push, seed and duration are shared
        self.assertEqual(r["baseline"]["gait"], r["candidate"]["gait"])
        self.assertEqual(r["baseline"]["push"], r["candidate"]["push"])
        self.assertEqual(r["baseline"]["seed"], r["candidate"]["seed"])
        diff = {k for k in r["baseline"]["body"] if r["baseline"]["body"][k] != r["candidate"]["body"][k]}
        self.assertEqual(diff, {"torso_mass"})

    def test_replay_of_invalid_trial_shows_only_the_original_failure(self):
        r = lab.build_replay(load(INVALID), 0)
        self.assertIsNone(r["candidate"])
        self.assertTrue(r["consistency"]["baseline"]["matches_saved_record"])
        self.assertTrue(r["baseline"]["metrics"]["fell"])

    def test_consistency_check_detects_a_doctored_record(self):
        t = load(REJECTED)
        t["measured_outcome"]["per_seed"]["candidate"][0]["fell"] = False
        t["measured_outcome"]["per_seed"]["baseline"][0]["min_torso_height"] += 0.01
        r = lab.build_replay(t, 0)
        self.assertFalse(r["consistency"]["candidate"]["matches_saved_record"])
        self.assertFalse(r["consistency"]["baseline"]["matches_saved_record"])
        self.assertTrue(r["consistency"]["baseline"]["failures"])

    def test_replay_input_validation(self):
        t = load(REJECTED)
        with self.assertRaises(lab.LabError):
            lab.build_replay(t, 99)
        with self.assertRaises(lab.LabError):
            lab.build_replay({"trial_id": "x", "observed_evidence": None}, 0)
        t["observed_evidence"]["body"]["foot_length"] = 9.0  # outside bounds
        with self.assertRaises(lab.LabError):
            lab.build_replay(t, 0)

    def test_heldout_protocol_aggregates_recompute_to_the_saved_numbers(self):
        rep = lab.reverify_protocol(load(REJECTED), push_levels=[25.0])  # primary push only: 20 simulations
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(set(rep["arms"]), {"baseline", "candidate"})
        with self.assertRaises(lab.LabError):
            lab.reverify_protocol(load(INVALID))


class LabApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.c = TestClient(create_app(investigations_dir=cls.tmp / "none", demo_dir=DEMO))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_list_and_view(self):
        rows = self.c.get("/api/lab/trials").json()
        self.assertEqual(len(rows), 4)
        v = self.c.get(f"/api/lab/trials/{REJECTED}")
        self.assertEqual(v.status_code, 200)
        self.assertEqual(v.json()["source"], "bundled-demo")

    def test_errors_are_clean(self):
        self.assertEqual(self.c.get("/api/lab/trials/20260101T000000Z-nope00").status_code, 404)
        for url in ("/api/lab/trials/..%2Fmanifest", "/api/lab/trials/%2e%2e%2f%2e%2e%2fprotocol"):
            r = self.c.get(url)  # must never serve a file outside the record directories
            self.assertNotIn("trial_id", r.text)
            self.assertNotIn("registered_before_any", r.text)
        self.assertEqual(self.c.get(f"/api/lab/trials/{REJECTED}/replay?seed=99").status_code, 422)
        self.assertEqual(self.c.get(f"/api/lab/trials/{REJECTED}/replay?seed=abc").status_code, 422)

    def test_replay_endpoint_returns_two_synchronised_runs(self):
        r = self.c.get(f"/api/lab/trials/{REJECTED}/replay?seed=0").json()
        b, c = r["baseline"], r["candidate"]
        self.assertEqual(b["time"], c["time"])
        self.assertEqual(len(b["frames"]["pos"]), len(b["time"]))
        self.assertTrue(r["consistency"]["baseline"]["matches_saved_record"])

    def test_empty_install_returns_empty_list(self):
        empty = TestClient(create_app(investigations_dir=self.tmp / "a", demo_dir=self.tmp / "b"))
        self.assertEqual(empty.get("/api/lab/trials").json(), [])


if __name__ == "__main__":
    unittest.main()
