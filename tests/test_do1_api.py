"""`/api/do1/*`: the verified static DO-1 replays (no simulation). Uses the committed export and the audited record."""
import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from creature_forge.studio.do1_api import DEMO_DIR, RECORD, create_do1_router

DEFAULT_SEED = 66645963


def _client(**kw) -> TestClient:
    app = FastAPI()
    app.include_router(create_do1_router(**kw))
    return TestClient(app)


def _no_sim(*a, **k):
    raise AssertionError("the DO-1 API must not simulate")


@mock.patch("creature_forge.hidden_plant.plant_rollout", _no_sim)
@mock.patch("creature_forge.recovery.run_walk_seeds", _no_sim)
class Do1ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = _client()
        cls.idx = cls.c.get("/api/do1/index").json()

    def test_index_is_the_export_plus_recorded_verification(self):
        idx = self.idx
        self.assertEqual(idx["default_seed"], DEFAULT_SEED)
        self.assertEqual(idx["aggregates"]["walking"], {"faulty": 5, "frozen": 19, "do1": 21, "do1_confirm": 22})
        self.assertEqual(idx["verification"]["frozen"]["status"], "PARTIAL_IMPROVEMENT")
        self.assertEqual(idx["verification"]["do1"]["status"], "FULL_RECOVERY")
        self.assertEqual(idx["verification"]["frozen"]["aggregate"], "POOR")
        self.assertFalse(idx["verification"]["frozen"]["confirmation"]["run"])
        self.assertTrue(idx["verification"]["do1"]["confirmation"]["passed"])
        self.assertEqual((idx["verification"]["frozen"]["verdict"]["wins"], idx["verification"]["do1"]["verdict"]["losses"]), (20, 0))
        self.assertEqual(idx["criteria"], {"rule": "full_recovery_v1", "pass_frac": 0.8})
        self.assertEqual(idx["provenance"]["arms_nemotron"], [None, None])
        self.assertEqual(idx["provenance"]["arms_provenance_recorded"], ["NO_AI", "NO_AI"])
        self.assertEqual(len(idx["available"]), 96)
        self.assertNotIn("files", idx)

    def test_index_matches_the_audited_record(self):
        rec = {r["harness"]["do1"]["arm"]: r for r in map(json.loads, RECORD.read_text(encoding="utf-8").splitlines())}
        for arm in ("frozen", "do1"):
            v = rec[arm]["verification"]["full"]
            self.assertEqual(self.idx["verification"][arm]["verdict"]["median_diff"], v["validation"]["verdict"]["median_diff"])
            self.assertEqual(self.idx["verification"][arm]["reasons"], v["reasons"])
        self.assertEqual(self.idx["rows"]["frozen"][0]["score"], rec["frozen"]["verification"]["full"]["validation"]["candidate"][0]["score"])

    def test_payload_is_the_verified_file_byte_for_byte(self):
        sums = dict(ln.split(" *")[::-1] for ln in (DEMO_DIR / "SHA256SUMS").read_text(encoding="utf-8").splitlines())
        for design in ("faulty", "frozen", "do1"):
            r = self.c.get(f"/api/do1/payload/{design}/10/{DEFAULT_SEED}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers["content-type"], "application/json")
            self.assertEqual(hashlib.sha256(r.content).hexdigest(), sums[f"payloads/{design}_10s_{DEFAULT_SEED}.json"])
            p = r.json()
            self.assertEqual((p["seed"], p["do1_demo"]["design"], p["do1_demo"]["frame_state"]), (DEFAULT_SEED, design, "pre-step"))
        conf = self.idx["seeds"]["confirm"][0]
        self.assertEqual(self.c.get(f"/api/do1/payload/do1/20/{conf}").json()["do1_demo"]["duration_s"], 20.0)

    def test_inputs_are_validated_and_files_come_from_the_index(self):
        for path, code in (("/api/do1/payload/robot/10/66645963", 422), ("/api/do1/payload/do1/15/66645963", 422),
                           ("/api/do1/payload/do1/10/abc", 422), ("/api/do1/payload/do1/10/-1", 422),
                           ("/api/do1/payload/do1/10/12345", 404),                       # not an exported seed
                           ("/api/do1/payload/frozen/20/79386176", 404),                 # confirmation exists for DO-1 only
                           ("/api/do1/payload/do1/10/..%2f..%2findex.json", 404),
                           ("/api/do1/payload/do1/10/66645963.json", 422)):
            self.assertEqual(self.c.get(path).status_code, code, path)
        self.assertEqual(self.c.post("/api/do1/index").status_code, 405)


class Do1ApiIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="do1api_"))
        shutil.copytree(DEMO_DIR, self.tmp / "demo")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tampered_payload_is_refused(self):
        p = self.tmp / "demo" / "payloads" / f"frozen_10s_{DEFAULT_SEED}.json"
        p.write_bytes(p.read_bytes().replace(b'"seed":', b'"seed" :', 1))
        c = _client(demo_dir=self.tmp / "demo")
        self.assertEqual(c.get("/api/do1/index").status_code, 200)
        r = c.get(f"/api/do1/payload/frozen/10/{DEFAULT_SEED}")
        self.assertEqual(r.status_code, 503)
        self.assertIn("integrity", r.json()["detail"])
        self.assertEqual(c.get(f"/api/do1/payload/do1/10/{DEFAULT_SEED}").status_code, 200)

    def test_tampered_index_sums_or_record_are_refused(self):
        idx = self.tmp / "demo" / "index.json"
        idx.write_text(idx.read_text(encoding="utf-8").replace('"default_seed": 66645963', '"default_seed": 66645952'), encoding="utf-8")
        self.assertEqual(_client(demo_dir=self.tmp / "demo").get("/api/do1/index").status_code, 503)
        shutil.copy(DEMO_DIR / "index.json", idx)
        sums = self.tmp / "demo" / "SHA256SUMS"
        sums.write_text(sums.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(_client(demo_dir=self.tmp / "demo").get("/api/do1/index").status_code, 503)
        shutil.copy(DEMO_DIR / "SHA256SUMS", sums)
        rec = self.tmp / "rec.jsonl"
        rec.write_bytes(RECORD.read_bytes() + b"\n")
        self.assertEqual(_client(demo_dir=self.tmp / "demo", record=rec).get("/api/do1/index").status_code, 503)

    def test_missing_export_is_404(self):
        self.assertEqual(_client(demo_dir=self.tmp / "absent").get("/api/do1/index").status_code, 404)


if __name__ == "__main__":
    unittest.main()
