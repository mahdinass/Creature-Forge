import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from creature_forge.studio.causal_api import RECORDS_DIR, create_causal_router

RID = "c-0123456789ab"


def make_record(rid=RID, with_submitted=True) -> dict:
    body = {"foot_length": 0.08, "foot_friction": 1.0}
    return {"schema": "causal_record_v1", "id": rid, "steps": [],
            "robot": {"initial": {"body": body, "vector": [0.1] * 17},
                      "submitted": {"body": body if with_submitted else None, "vector": [0.2] * 17 if with_submitted else None}}}


class CausalApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / f"{RID}.json").write_text(json.dumps(make_record()), encoding="utf-8")
        (self.dir / "c-aaaaaaaaaaaa.json").write_text(json.dumps(make_record("c-aaaaaaaaaaaa", with_submitted=False)), encoding="utf-8")
        (self.dir / "index.json").write_text(json.dumps({"schema": "causal_record_v1", "records": [{"id": RID}, {"id": "c-aaaaaaaaaaaa"}]}),
                                             encoding="utf-8")
        (self.dir / "secret.json").write_text("{}", encoding="utf-8")   # exists on disk but is not in the index
        self.calls = []

        def fake(body, vec, seed):
            self.calls.append((body, vec, seed))
            return {"seed": seed, "duration": 10.0, "vec0": vec[0]}

        app = FastAPI()
        app.include_router(create_causal_router(self.dir, replayer=fake))
        self.c = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_index_lists_records_and_replay_options(self):
        j = self.c.get("/api/causal/records").json()
        self.assertEqual([r["id"] for r in j["records"]], [RID, "c-aaaaaaaaaaaa"])
        self.assertEqual(j["replay"]["designs"], ["initial", "submitted"])
        self.assertTrue(j["replay"]["seeds"])

    def test_empty_index_when_nothing_exported(self):
        app = FastAPI()
        app.include_router(create_causal_router(self.dir / "nowhere"))
        self.assertEqual(TestClient(app).get("/api/causal/records").json()["records"], [])

    def test_record_and_404(self):
        self.assertEqual(self.c.get(f"/api/causal/records/{RID}").json()["id"], RID)
        self.assertEqual(self.c.get("/api/causal/records/c-ffffffffffff").status_code, 404)

    def test_ids_are_validated_against_the_index_not_the_filesystem(self):
        for bad in ("secret", "index", "..%2Findex", "%2e%2e/index", "c-0123456789ab.json", "C-0123456789AB", "c-0123456789abc"):
            self.assertEqual(self.c.get(f"/api/causal/records/{bad}").status_code, 404, bad)
            self.assertEqual(self.c.get(f"/api/causal/records/{bad}/replay").status_code, 404, bad)
        self.assertEqual(self.calls, [])

    def test_replay_initial_and_submitted_use_their_own_vector(self):
        a = self.c.get(f"/api/causal/records/{RID}/replay?design=initial&seed=3").json()
        b = self.c.get(f"/api/causal/records/{RID}/replay?design=submitted&seed=3").json()
        self.assertEqual((a["vec0"], b["vec0"], a["seed"]), (0.1, 0.2, 3))

    def test_replay_defaults_and_cache(self):
        r = self.c.get(f"/api/causal/records/{RID}/replay")
        self.assertEqual(r.status_code, 200)
        self.c.get(f"/api/causal/records/{RID}/replay")
        self.assertEqual(len(self.calls), 1)        # second call served from the cache

    def test_replay_input_validation(self):
        for q in ("design=other", "seed=-1", "seed=abc", f"seed={2 ** 31}", "seed=1.5"):
            self.assertEqual(self.c.get(f"/api/causal/records/{RID}/replay?{q}").status_code, 422, q)
        self.assertEqual(self.calls, [])

    def test_missing_submitted_design_is_404(self):
        self.assertEqual(self.c.get("/api/causal/records/c-aaaaaaaaaaaa/replay?design=submitted").status_code, 404)
        self.assertEqual(self.c.get("/api/causal/records/c-aaaaaaaaaaaa/replay?design=initial").status_code, 200)

    def test_replay_error_is_reported_not_leaked(self):
        app = FastAPI()

        def boom(body, vec, seed):
            raise RuntimeError("secret path C:\\Users\\x")
        app.include_router(create_causal_router(self.dir, replayer=boom))
        r = TestClient(app).get(f"/api/causal/records/{RID}/replay")
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("Users", r.text)

    def test_posts_are_not_allowed(self):
        self.assertEqual(self.c.post("/api/causal/records").status_code, 405)

    def test_committed_demo_records_are_consistent(self):
        idx = json.loads((RECORDS_DIR / "index.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(idx["records"]), 3)
        statuses = {r["status"] for r in idx["records"]}
        self.assertTrue({"FULL_RECOVERY", "NOT_RECOVERED"} <= statuses)
        for row in idx["records"]:
            rec = json.loads((RECORDS_DIR / f"{row['id']}.json").read_text(encoding="utf-8"))
            self.assertEqual(rec["id"], row["id"])
            self.assertEqual(len(rec["robot"]["initial"]["vector"]), 17)
            self.assertEqual(len(rec["robot"]["submitted"]["vector"]), 17)
            self.assertIn("evaluation_only", rec)


if __name__ == "__main__":
    unittest.main()
