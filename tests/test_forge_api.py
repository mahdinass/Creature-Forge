import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from creature_forge.creatures import seed_block
from creature_forge.sandbox import SandboxBody
from creature_forge.studio.forge_api import create_forge_router


def wait_for(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def body(**kw) -> dict:
    return {**SandboxBody().as_dict(), **kw}


class Fakes:
    """Fast stand-ins for challenges.run_challenge / replay_payload."""

    def __init__(self):
        self.runs, self.replays = [], []
        self.block = None  # a threading.Event the runner waits on when set
        self.fail = None

    def runner(self, b, controllers, spec, progress):
        self.runs.append({"body": b, "controllers": controllers, "spec": spec})
        if self.fail:
            raise RuntimeError(self.fail)
        total = len(spec["seeds"])
        for i in range(total):
            if self.block is not None:
                self.block.wait(5)
            progress(i + 1, total)
        return {"spec": spec, "body": b, "controller": {"stand": {"kind": "stand-pd"}},
                "per_seed": [{"seed": s, "outcome": "PASS", "score": 1.0, "metrics": {}, "events": [], "rollouts": 1,
                              "error": None} for s in spec["seeds"]],
                "outcome": "PASS", "summary": {}, "forensics": {}, "rollouts": total, "wall_s": 0.01}

    def replay(self, b, controllers, spec, seed, *, force=None, direction=1):
        self.replays.append((seed, force, direction))
        return {"seed": seed, "force": force, "direction": direction, "frames": {"pos": [[0, 0]]}}


class ApiCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "forge"
        self.fakes = Fakes()
        self.make_client()

    def make_client(self):
        self.router = create_forge_router(self.dir, challenge_runner=self.fakes.runner, replay_builder=self.fakes.replay)
        self.addCleanup(self.router.forge.close)
        app = FastAPI()
        app.include_router(self.router)
        self.c = TestClient(app)

    def create(self, mode="guided", name="Stubby", **kw):
        r = self.c.post("/api/forge/creatures", json={"name": name, "body": body(**kw), "mode": mode, "drawing": {"strokes": []}})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def job(self, jid, since=0):
        r = self.c.get(f"/api/forge/jobs/{jid}", params={"since": since})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def wait_job(self, jid, *statuses):
        self.assertTrue(wait_for(lambda: self.job(jid)["job"]["status"] in statuses), self.job(jid)["job"])
        return self.job(jid)

    def start(self, cid, n=1, **req):
        r = self.c.post(f"/api/forge/creatures/{cid}/versions/{n}/challenges", json={"kind": "push", **req})
        return r


class LazinessTests(ApiCase):
    def test_creating_the_router_and_listing_create_nothing(self):
        workers_before = [t for t in threading.enumerate() if t.name == "forge-jobs"]
        self.make_client()
        self.assertFalse(self.dir.exists())
        self.assertEqual(self.c.get("/api/forge/creatures").json(), [])
        self.assertEqual(self.c.get("/api/forge/investigations").json(), [])
        self.assertFalse(self.dir.exists())
        self.assertEqual([t for t in threading.enumerate() if t.name == "forge-jobs"], workers_before)


class CreatureTests(ApiCase):
    def test_empty_list_then_create_list_get(self):
        r = self.c.get("/api/forge/creatures")
        self.assertEqual((r.status_code, r.json()), (200, []))
        cr = self.create()
        self.assertEqual(cr["current"], 1)
        self.assertEqual(cr["versions"][0]["body"]["thigh_length_r"], cr["versions"][0]["body"]["thigh_length"])
        listed = self.c.get("/api/forge/creatures").json()
        self.assertEqual(listed, [{"id": cr["id"], "name": "Stubby", "current": 1, "n_versions": 1, "created": cr["created"]}])
        self.assertEqual(self.c.get(f"/api/forge/creatures/{cr['id']}").json(), cr)

    def test_invalid_bodies_per_mode(self):
        r = self.c.post("/api/forge/creatures", json={"name": "A", "mode": "guided", "body": body(thigh_length_r=0.45), "drawing": {}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("symmetric", r.json()["detail"])
        r = self.c.post("/api/forge/creatures", json={"name": "A", "mode": "guided", "body": body(torso_mass=40.0), "drawing": {}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("guided range", r.json()["detail"])
        ok = self.c.post("/api/forge/creatures", json={"name": "A", "mode": "experimental",
                                                       "body": body(torso_mass=40.0, thigh_length_r=0.45), "drawing": {}})
        self.assertEqual(ok.status_code, 200, ok.text)
        r = self.c.post("/api/forge/creatures", json={"name": "A", "mode": "experimental", "body": body(torso_mass=5000.0), "drawing": {}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("sandbox range", r.json()["detail"])
        self.assertEqual(len(self.c.get("/api/forge/creatures").json()), 1)

    def test_malformed_requests_are_rejected_clearly(self):
        for payload in ({"name": "", "mode": "guided", "body": body()},
                        {"name": "A", "mode": "wild", "body": body()},
                        {"name": "A", "mode": "guided"},
                        {"name": "A", "mode": "guided", "body": body(), "extra": 1}):
            r = self.c.post("/api/forge/creatures", json=payload)
            self.assertEqual(r.status_code, 422, payload)
        self.assertEqual(self.c.post("/api/forge/creatures", json={"name": "A", "mode": "guided", "body": {**body(), "wings": 1}}).status_code, 422)

    def test_unknown_and_hostile_ids_are_json_404(self):
        for cid in ("c-00000000", "nope", "..%2Fetc"):
            r = self.c.get(f"/api/forge/creatures/{cid}")
            self.assertEqual(r.status_code, 404, cid)
            self.assertIn("detail", r.json())

    def test_current_switch_and_errors(self):
        cr = self.create()
        r = self.c.post(f"/api/forge/creatures/{cr['id']}/current", json={"n": 1})
        self.assertEqual((r.status_code, r.json()["current"]), (200, 1))
        self.assertEqual(self.c.post(f"/api/forge/creatures/{cr['id']}/current", json={"n": 2}).status_code, 404)
        self.assertEqual(self.c.post("/api/forge/creatures/c-00000000/current", json={"n": 1}).status_code, 404)
        self.assertEqual(self.c.post(f"/api/forge/creatures/{cr['id']}/current", json={"n": 0}).status_code, 422)

    def test_accept_revert_lineage_through_the_store(self):
        """The router owns the store; accept is an HTTP stub for now, but the store behind it follows the contract."""
        cr = self.create()
        store = self.router.forge.store()
        with self.assertRaises(ValueError):
            store.accept(cr["id"], parent_n=1, body=body(), controllers=None,
                         change={"verdict": {"status": "NOT_VERIFIED"}})
        store.accept(cr["id"], parent_n=1, body=body(torso_mass=6.0), controllers=None,
                     change={"verdict": {"status": "VERIFIED_IMPROVEMENT"}})
        got = self.c.get(f"/api/forge/creatures/{cr['id']}").json()
        self.assertEqual((got["current"], [v["parent"] for v in got["versions"]]), (2, [None, 1]))
        back = self.c.post(f"/api/forge/creatures/{cr['id']}/current", json={"n": 1}).json()
        self.assertEqual((back["current"], len(back["versions"])), (1, 2))


class ChallengeTests(ApiCase):
    def test_challenge_run_end_to_end_with_events_and_stored_result(self):
        cr = self.create()
        r = self.start(cr["id"])
        self.assertEqual(r.status_code, 200, r.text)
        out = r.json()
        self.assertEqual(set(out), {"job_id", "run_id"})
        self.assertRegex(out["run_id"], r"^r-[0-9a-f]{8}$")
        done = self.wait_job(out["job_id"], "done", "failed")
        self.assertEqual(done["job"]["status"], "done", done)
        self.assertEqual(done["job"]["result_ref"], {"run_id": out["run_id"]})
        self.assertEqual(done["job"]["progress"], {"phase": "challenge", "done": 8, "total": 8})
        types = [e["type"] for e in done["events"]]
        self.assertEqual(types, ["phase"] + ["progress"] * 8)
        later = self.job(out["job_id"], since=done["events"][3]["i"])["events"]
        self.assertEqual([e["i"] for e in later], [e["i"] for e in done["events"][4:]])
        run = self.c.get(f"/api/forge/runs/{out['run_id']}").json()
        v = cr["versions"][0]
        self.assertEqual(run["creature"], {"cid": cr["id"], "n": 1, "content_hash": v["content_hash"]})
        self.assertEqual(run["run_id"], out["run_id"])
        self.assertTrue(run["created"].endswith("Z"))
        self.assertEqual(run["outcome"], "PASS")
        self.assertEqual(run["spec"]["kind"], "push")
        self.assertEqual(run["spec"]["seeds"], list(seed_block(cr["id"], 1, 0, "challenge", 8)))
        self.assertEqual(run["spec"]["target_force"], 10.0)
        self.assertEqual(run["controllers"], v["controllers"])
        self.assertEqual(len(run["per_seed"]), 8)
        # the runner got the stored, explicit version data
        got = self.fakes.runs[0]
        self.assertEqual(got["body"], v["body"])
        self.assertEqual(got["controllers"], v["controllers"])

    def test_seed_count_overrides_and_run_counter(self):
        cr = self.create()
        a = self.start(cr["id"], seeds=3, overrides={"target_force": 30, "duration": 4.0}).json()
        b = self.start(cr["id"], seeds=3).json()
        self.wait_job(a["job_id"], "done")
        self.wait_job(b["job_id"], "done")
        ra, rb = (self.c.get(f"/api/forge/runs/{x['run_id']}").json() for x in (a, b))
        self.assertEqual(ra["spec"]["seeds"], list(seed_block(cr["id"], 1, 0, "challenge", 3)))
        self.assertEqual(rb["spec"]["seeds"], list(seed_block(cr["id"], 1, 1, "challenge", 3)))
        self.assertTrue(all(s >= 100_000 for s in ra["spec"]["seeds"] + rb["spec"]["seeds"]))
        self.assertNotEqual(ra["spec"]["seeds"], rb["spec"]["seeds"])
        self.assertEqual((ra["spec"]["target_force"], ra["spec"]["duration"]), (30.0, 4.0))
        self.assertEqual((rb["spec"]["target_force"], rb["spec"]["duration"]), (10.0, 5.0))

    def test_run_counter_survives_a_restart(self):
        cr = self.create()
        first = self.start(cr["id"], seeds=2).json()
        self.wait_job(first["job_id"], "done")
        self.router.forge.close()
        self.make_client()
        second = self.start(cr["id"], seeds=2).json()
        self.wait_job(second["job_id"], "done")
        self.assertEqual(self.c.get(f"/api/forge/runs/{second['run_id']}").json()["spec"]["seeds"],
                         list(seed_block(cr["id"], 1, 1, "challenge", 2)))

    def test_walk_and_stand_defaults(self):
        cr = self.create()
        w = self.c.post(f"/api/forge/creatures/{cr['id']}/versions/1/challenges", json={"kind": "walk"}).json()
        s = self.c.post(f"/api/forge/creatures/{cr['id']}/versions/1/challenges", json={"kind": "stand"}).json()
        self.wait_job(s["job_id"], "done")
        rw = self.c.get(f"/api/forge/runs/{w['run_id']}").json()["spec"]
        rs = self.c.get(f"/api/forge/runs/{s['run_id']}").json()["spec"]
        self.assertEqual((rw["duration"], rw["start"], rw["perturb"]), (10.0, "neutral", 0.03))
        self.assertEqual((rs["duration"], rs["start"], rs["perturb"]), (8.0, "drawn", 0.02))

    def test_bad_requests(self):
        cr = self.create()
        url = f"/api/forge/creatures/{cr['id']}/versions/1/challenges"
        self.assertEqual(self.c.post(url, json={"kind": "swim"}).status_code, 422)
        self.assertEqual(self.c.post(url, json={"kind": "push", "seeds": 0}).status_code, 422)
        self.assertEqual(self.c.post(url, json={"kind": "push", "seeds": 1000}).status_code, 422)
        for bad in ({"bogus": 1}, {"duration": -1}, {"duration": "long"}, {"target_force": 1e9}, {"start": "sideways"},
                    {"seeds": [1, 2]}, {"kind": "stand"}):
            r = self.c.post(url, json={"kind": "push", "overrides": bad})
            self.assertEqual(r.status_code, 422, bad)
            self.assertIn("detail", r.json())
        self.assertEqual(self.c.post(f"/api/forge/creatures/{cr['id']}/versions/9/challenges", json={"kind": "push"}).status_code, 404)
        self.assertEqual(self.c.post("/api/forge/creatures/c-00000000/versions/1/challenges", json={"kind": "push"}).status_code, 404)
        self.assertEqual(self.fakes.runs, [])
        self.assertFalse((self.dir / "jobs").exists())

    def test_runner_failure_becomes_a_failed_job_and_no_run_is_stored(self):
        cr = self.create()
        self.fakes.fail = "MuJoCo exploded"
        out = self.start(cr["id"]).json()
        done = self.wait_job(out["job_id"], "failed")
        self.assertEqual(done["job"]["error"], "RuntimeError: MuJoCo exploded")
        self.assertEqual([e["type"] for e in done["events"]][-1], "error")
        r = self.c.get(f"/api/forge/runs/{out['run_id']}")
        self.assertEqual(r.status_code, 404)

    def test_cancel_a_running_challenge(self):
        cr = self.create()
        self.fakes.block = threading.Event()
        out = self.start(cr["id"]).json()
        self.assertTrue(wait_for(lambda: self.job(out["job_id"])["job"]["status"] == "running"))
        r = self.c.post(f"/api/forge/jobs/{out['job_id']}/cancel")
        self.assertEqual(r.status_code, 200, r.text)
        self.fakes.block.set()
        done = self.wait_job(out["job_id"], "cancelled")
        self.assertIsNone(done["job"]["error"])
        self.assertEqual(self.c.get(f"/api/forge/runs/{out['run_id']}").status_code, 404)  # no half-result stored
        again = self.c.post(f"/api/forge/jobs/{out['job_id']}/cancel")
        self.assertEqual(again.json()["status"], "cancelled")

    def test_unknown_jobs_and_runs(self):
        self.assertEqual(self.c.get("/api/forge/jobs/j-00000000").status_code, 404)
        self.assertEqual(self.c.get("/api/forge/jobs/zzz").status_code, 404)
        self.assertEqual(self.c.post("/api/forge/jobs/j-00000000/cancel").status_code, 404)
        self.assertEqual(self.c.get("/api/forge/runs/r-00000000").status_code, 404)
        self.assertEqual(self.c.get("/api/forge/runs/..%2F..%2Fsecret").status_code, 404)
        self.assertEqual(self.c.get("/api/forge/jobs/j-00000000", params={"since": -1}).status_code, 422)

    def test_restart_marks_unfinished_jobs_failed(self):
        jobs = self.dir / "jobs"
        jobs.mkdir(parents=True)
        rec = {"id": "j-0000abcd", "kind": "challenge", "status": "running", "created": "2026-10-14T10:00:00Z",
               "started": "2026-10-14T10:00:01Z", "finished": None, "progress": {"phase": "challenge", "done": 2, "total": 8},
               "result_ref": None, "error": None}
        (jobs / "j-0000abcd.json").write_text(json.dumps(rec), encoding="utf-8")
        self.make_client()  # a "restarted server"
        got = self.job("j-0000abcd")
        self.assertEqual((got["job"]["status"], got["job"]["error"]), ("failed", "server restarted"))
        self.assertEqual(got["events"][-1]["type"], "error")


class ReplayTests(ApiCase):
    def run_one(self):
        cr = self.create()
        out = self.start(cr["id"], seeds=3).json()
        self.wait_job(out["job_id"], "done")
        run = self.c.get(f"/api/forge/runs/{out['run_id']}").json()
        return out["run_id"], run["spec"]["seeds"]

    def test_replay_is_built_cached_and_keyed_by_seed_direction_force(self):
        rid, seeds = self.run_one()
        url = "/api/forge/replay"
        a = self.c.get(url, params={"run_id": rid, "seed": seeds[0]})
        self.assertEqual(a.status_code, 200, a.text)
        self.assertEqual(a.json()["seed"], seeds[0])
        self.c.get(url, params={"run_id": rid, "seed": seeds[0]})
        self.assertEqual(self.fakes.replays, [(seeds[0], None, 1)])  # second hit was cached
        b = self.c.get(url, params={"run_id": rid, "seed": seeds[0], "direction": -1, "force": 12.5}).json()
        self.assertEqual((b["direction"], b["force"]), (-1, 12.5))
        self.assertEqual(len(self.fakes.replays), 2)

    def test_cache_is_a_bounded_lru(self):
        rid, seeds = self.run_one()
        for f in range(16):
            self.c.get("/api/forge/replay", params={"run_id": rid, "seed": seeds[0], "force": float(f)})
        self.assertEqual(len(self.fakes.replays), 16)
        self.c.get("/api/forge/replay", params={"run_id": rid, "seed": seeds[0], "force": 0.0})  # still cached
        self.assertEqual(len(self.fakes.replays), 16)
        self.c.get("/api/forge/replay", params={"run_id": rid, "seed": seeds[0], "force": 99.0})  # evicts force=1 (oldest)
        self.c.get("/api/forge/replay", params={"run_id": rid, "seed": seeds[0], "force": 1.0})   # rebuilt: it was evicted
        self.assertEqual(len(self.fakes.replays), 18)

    def test_unknown_run_seed_and_bad_params(self):
        rid, seeds = self.run_one()
        url = "/api/forge/replay"
        self.assertEqual(self.c.get(url, params={"run_id": "r-00000000", "seed": 1}).status_code, 404)
        self.assertEqual(self.c.get(url, params={"run_id": rid, "seed": 123}).status_code, 404)
        self.assertEqual(self.c.get(url, params={"run_id": rid}).status_code, 422)
        self.assertEqual(self.c.get(url, params={"seed": 1}).status_code, 422)
        self.assertEqual(self.c.get(url, params={"run_id": rid, "seed": seeds[0], "direction": 0}).status_code, 422)
        self.assertEqual(self.c.get(url, params={"run_id": rid, "seed": seeds[0], "force": -5}).status_code, 422)
        self.assertEqual(self.c.get(url, params={"run_id": rid, "seed": seeds[0], "force": "nan"}).status_code, 422)
        self.assertEqual(self.fakes.replays, [])
        r = self.c.get(url, params={"run_id": rid, "seed": 123})
        self.assertIn("detail", r.json())

    def test_a_failing_builder_is_a_json_error_not_cached(self):
        rid, seeds = self.run_one()
        calls = []

        def bad(*a, **k):
            calls.append(1)
            raise ValueError("no such push")
        self.fakes.replay = bad
        self.make_client()
        for _ in range(2):
            r = self.c.get("/api/forge/replay", params={"run_id": rid, "seed": seeds[0]})
            self.assertEqual(r.status_code, 422)
            self.assertIn("no such push", r.json()["detail"])
        self.assertEqual(len(calls), 2)


class StatusAndStubTests(ApiCase):
    def test_status_shape_and_the_key_is_never_returned(self):
        env = {k: v for k, v in os.environ.items() if k not in ("CREATURE_FORGE_ENABLE_LIVE", "NEBIUS_API_KEY", "CF_WORKERS", "CF_INFERENCE_LEDGER")}
        # isolate from any real .env on this machine: status loads it (like the live gate does), so stub the loader
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("creature_forge.config.load_env", return_value=False):
            s = self.c.get("/api/forge/status").json()
            self.assertEqual((s["live_available"], s["workers"], s["version"]), (False, 6, "forge-v1"))
            self.assertEqual(s["model"]["model"], "nvidia/nemotron-3-super-120b-a12b")
            self.assertEqual(set(s["model"]["profiles"]), {"default", "deep"})
            self.assertEqual((s["ledger"]["requests"], s["ledger"]["usd"], s["ledger"]["caps"]["requests"]), (0, 0, 4000))
            os.environ["NEBIUS_API_KEY"] = "sk-super-secret-value"
            self.assertFalse(self.c.get("/api/forge/status").json()["live_available"])  # live flag missing
            os.environ["CREATURE_FORGE_ENABLE_LIVE"] = "1"
            os.environ["CF_WORKERS"] = "3"
            r = self.c.get("/api/forge/status")
            self.assertTrue(r.json()["live_available"])
            self.assertEqual(r.json()["workers"], 3)
            self.assertNotIn("sk-super-secret-value", r.text)
            del os.environ["NEBIUS_API_KEY"]
            self.assertFalse(self.c.get("/api/forge/status").json()["live_available"])
            os.environ["CF_WORKERS"] = "banana"
            self.assertEqual(self.c.get("/api/forge/status").json()["workers"], 6)



# ---- investigations (fake arena, fake baselines, scripted fixture transport: no MuJoCo, no network)
try:
    from tests.test_investigation import FakeArena, FakeBaselines
except ImportError:  # run from inside tests/
    from test_investigation import FakeArena, FakeBaselines

from creature_forge import investigation as inv
from creature_forge.inference_ledger import InferenceLedger


class InvestigationApiCase(ApiCase):
    def make_client(self):
        self.arena, self.bl = FakeArena(), FakeBaselines()
        self.ledger = InferenceLedger(Path(self._tmp.name) / "ledger.jsonl")
        self.router = create_forge_router(
            self.dir, challenge_runner=self.fakes.runner, replay_builder=self.fakes.replay, ledger=self.ledger,
            investigation_options={"arena_runner": self.arena, "baseline_fns": self.bl.fns(),
                                   "code_fn": lambda: {"commit": "abc", "dirty": False}})
        self.addCleanup(self.router.forge.close)
        app = FastAPI()
        app.include_router(self.router)
        self.c = TestClient(app)

    def run_challenge(self, cid, n=1):
        out = self.start(cid, n, kind="push", seeds=4).json()
        self.wait_job(out["job_id"], "done")
        return out["run_id"]

    def investigate(self, cid, run_id, n=1, **req):
        r = self.c.post(f"/api/forge/creatures/{cid}/versions/{n}/investigations", json={"run_id": run_id, "mode": "scripted", **req})
        self.assertEqual(r.status_code, 200, r.text)
        out = r.json()
        self.wait_job(out["job_id"], "done", "failed", "cancelled")
        return out

    def setup_scripted(self):
        cr = self.create(mode="experimental")
        run_id = self.run_challenge(cr["id"])
        return cr["id"], run_id, self.investigate(cr["id"], run_id)


class InvestigationTests(InvestigationApiCase):
    def test_scripted_investigation_job_events_record_list_get(self):
        cid, run_id, out = self.setup_scripted()
        self.assertEqual(set(out), {"job_id", "investigation_id"})
        done = self.job(out["job_id"])
        self.assertEqual(done["job"]["status"], "done")
        self.assertEqual(done["job"]["result_ref"]["provenance"], "SCRIPTED_MOCK")
        types = {e["type"] for e in done["events"]}
        self.assertTrue({"phase", "model_request", "model_response", "validation", "arm_result", "verdict"} <= types, types)
        self.assertTrue(all(e["data"].get("provenance") == "SCRIPTED_MOCK" for e in done["events"]
                            if e["type"] in ("model_request", "model_response", "validation", "arm_result", "verdict")))
        self.assertEqual(done["job"]["kind"], "investigation")
        rec = self.c.get(f"/api/forge/investigations/{out['investigation_id']}").json()
        self.assertEqual((rec["id"], rec["status"], rec["provenance"], rec["challenge_run_id"]),
                         (out["investigation_id"], "done", "SCRIPTED_MOCK", run_id))
        self.assertEqual(rec["creature"]["cid"], cid)
        rows = self.c.get("/api/forge/investigations", params={"cid": cid}).json()
        self.assertEqual([r["id"] for r in rows], [out["investigation_id"]])
        self.assertEqual(rows[0]["verdicts"]["ai:P1"], "VERIFIED_IMPROVEMENT")
        self.assertEqual(self.c.get("/api/forge/investigations", params={"cid": "c-00000000"}).json(), [])
        self.assertEqual(self.ledger.status()["requests"], 0)  # scripted calls never spend the real ledger

    def test_live_refusals_are_503_with_a_reason_and_start_no_job(self):
        cr = self.create(mode="experimental")
        run_id = self.run_challenge(cr["id"])
        url = f"/api/forge/creatures/{cr['id']}/versions/1/investigations"
        env = {k: v for k, v in os.environ.items() if k != "CREATURE_FORGE_ENABLE_LIVE"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(inv, "api_key_present", return_value=True):
            r = self.c.post(url, json={"run_id": run_id, "mode": "live"})
            self.assertEqual(r.status_code, 503)
            self.assertIn("CREATURE_FORGE_ENABLE_LIVE", r.json()["detail"])
            os.environ["CREATURE_FORGE_ENABLE_LIVE"] = "1"
            with mock.patch.object(inv, "api_key_present", return_value=False):
                r = self.c.post(url, json={"run_id": run_id, "mode": "live"})
                self.assertEqual((r.status_code, "API key" in r.json()["detail"]), (503, True))
        self.assertFalse((self.dir / "investigations").exists())

    def test_bad_requests(self):
        cr = self.create(mode="experimental")
        run_id = self.run_challenge(cr["id"])
        base = f"/api/forge/creatures/{cr['id']}/versions/1/investigations"
        self.assertEqual(self.c.post(base, json={"run_id": run_id, "mode": "mock"}).status_code, 422)
        self.assertEqual(self.c.post(base, json={"run_id": run_id, "mode": "scripted", "profile": "turbo"}).status_code, 422)
        self.assertEqual(self.c.post(base, json={"run_id": "r-ffffffff", "mode": "scripted"}).status_code, 404)
        self.assertEqual(self.c.post(base, json={"run_id": "../x", "mode": "scripted"}).status_code, 404)
        self.assertEqual(self.c.post(f"/api/forge/creatures/{cr['id']}/versions/9/investigations",
                                     json={"run_id": run_id, "mode": "scripted"}).status_code, 404)
        other = self.create(mode="experimental", name="Other")
        r = self.c.post(f"/api/forge/creatures/{other['id']}/versions/1/investigations", json={"run_id": run_id, "mode": "scripted"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.c.get("/api/forge/investigations/i-ffffffffffff").status_code, 404)
        self.assertEqual(self.c.get("/api/forge/investigations/..%2Fsecret").status_code, 404)

    def test_accept_409_unless_verified_then_lineage(self):
        self.arena.plan = [{"ai:P1": "VERIFIED_IMPROVEMENT", "ai:P2": "NOT_VERIFIED", "random:P1": "VERIFIED_IMPROVEMENT"}]
        cid, run_id, out = self.setup_scripted()
        iid = out["investigation_id"]
        acc = f"/api/forge/creatures/{cid}/accept"
        r = self.c.post(acc, json={"investigation_id": iid, "arm_id": "ai:P2"})
        self.assertEqual(r.status_code, 409)
        self.assertIn("NOT_VERIFIED", r.json()["detail"])
        self.assertEqual(self.c.post(acc, json={"investigation_id": iid, "arm_id": "heuristic"}).status_code, 409)
        self.assertEqual(self.c.post(acc, json={"investigation_id": iid, "arm_id": "nope"}).status_code, 409)
        self.assertEqual(self.c.post(acc, json={"investigation_id": "i-ffffffffffff", "arm_id": "ai:P1"}).status_code, 404)
        self.assertEqual(self.c.post("/api/forge/creatures/c-00000000/accept", json={"investigation_id": iid, "arm_id": "ai:P1"}).status_code, 404)
        self.assertEqual(len(self.c.get(f"/api/forge/creatures/{cid}").json()["versions"]), 1)
        rec = self.c.post(acc, json={"investigation_id": iid, "arm_id": "ai:P1"}).json()
        self.assertEqual((rec["current"], len(rec["versions"])), (2, 2))
        v2 = rec["versions"][1]
        self.assertEqual((v2["parent"], v2["origin"]), (1, "ai_accepted"))
        ch = v2["change"]
        self.assertEqual((ch["investigation_id"], ch["arm_id"], ch["source"], ch["provenance"]), (iid, "ai:P1", "scripted_mock", "SCRIPTED_MOCK"))
        self.assertEqual(ch["verdict"]["status"], "VERIFIED_IMPROVEMENT")
        self.assertTrue(ch["rationale"] and ch["edits"] and ch["category"])
        self.assertNotEqual(v2["content_hash"], rec["versions"][0]["content_hash"])
        # a verified random twin may be accepted but is attributed honestly
        r2 = self.c.post(acc, json={"investigation_id": iid, "arm_id": "random:P1"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["versions"][2]["change"]["source"], "random_baseline")
        self.assertIsNone(r2.json()["versions"][2]["change"]["model"])

    def test_replay_of_an_arm_is_resimulated_cached_and_bounded_to_used_seeds(self):
        cid, run_id, out = self.setup_scripted()
        iid = out["investigation_id"]
        rec = self.c.get(f"/api/forge/investigations/{iid}").json()
        seed = rec["seeds"]["validate"][0]
        q = {"investigation_id": iid, "arm": "ai:P1", "seed": seed}
        a = self.c.get("/api/forge/replay", params=q)
        self.assertEqual(a.status_code, 200, a.text)
        self.assertEqual(self.c.get("/api/forge/replay", params=q).json(), a.json())
        self.assertEqual(len(self.fakes.replays), 1)  # LRU cache hit
        arm_body = next(x for x in rec["arms"] if x["arm_id"] == "ai:P1")["body"]
        self.assertNotEqual(arm_body, rec["arms"][0]["body"])
        self.assertEqual(self.c.get("/api/forge/replay", params={**q, "arm": "original"}).status_code, 200)
        self.assertEqual(self.c.get("/api/forge/replay", params={**q, "seed": 1}).status_code, 404)
        self.assertEqual(self.c.get("/api/forge/replay", params={**q, "arm": "zzz"}).status_code, 404)
        self.assertEqual(self.c.get("/api/forge/replay", params={"investigation_id": iid, "arm": "ai:P1"}).status_code, 422)
        self.assertEqual(self.c.get("/api/forge/replay", params={**q, "investigation_id": "i-ffffffffffff"}).status_code, 404)

    def test_loop_job_never_accepts(self):
        cr = self.create(mode="experimental")
        run_id = self.run_challenge(cr["id"])
        out = self.investigate(cr["id"], run_id, loop=True)
        j = self.job(out["job_id"])
        self.assertEqual((j["job"]["kind"], j["job"]["status"]), ("loop", "done"))
        loop = j["job"]["result_ref"]["loop"]
        self.assertEqual((len(loop["rounds"]), loop["stop_reason"], loop["auto_accepted"]), (3, "max_rounds", False))
        self.assertEqual(loop["rounds"][0]["investigation_id"], out["investigation_id"])
        self.assertEqual(len(self.c.get(f"/api/forge/creatures/{cr['id']}").json()["versions"]), 1)
        self.assertEqual(len(self.c.get("/api/forge/investigations", params={"cid": cr["id"]}).json()), 3)

    def test_arena_failure_is_a_failed_job_and_a_stored_failed_record(self):
        self.arena.fail = "pool crashed"
        cr = self.create(mode="experimental")
        run_id = self.run_challenge(cr["id"])
        out = self.investigate(cr["id"], run_id)
        j = self.job(out["job_id"])
        self.assertEqual(j["job"]["status"], "failed")
        self.assertIn("pool crashed", j["job"]["error"])
        rec = self.c.get(f"/api/forge/investigations/{out['investigation_id']}").json()
        self.assertEqual(rec["status"], "failed")
        self.assertEqual(rec["verdicts"], {})


# ---- diagnostic probes flag (fake pool: no MuJoCo)
try:
    from tests.test_investigation import ProbePool
except ImportError:  # run from inside tests/
    from test_investigation import ProbePool


class ProbeApiTests(InvestigationApiCase):
    def make_client(self):
        self.arena, self.bl, self.pool = FakeArena(), FakeBaselines(), ProbePool()
        self.ledger = InferenceLedger(Path(self._tmp.name) / "ledger.jsonl")
        self.router = create_forge_router(
            self.dir, challenge_runner=self.fakes.runner, replay_builder=self.fakes.replay, ledger=self.ledger, pool_factory=lambda: self.pool,
            investigation_options={"arena_runner": self.arena, "baseline_fns": self.bl.fns(),
                                   "code_fn": lambda: {"commit": "abc", "dirty": False}})
        self.addCleanup(self.router.forge.close)
        app = FastAPI()
        app.include_router(self.router)
        self.c = TestClient(app)

    def test_probes_flag_runs_the_probe_protocol(self):
        cr = self.create(mode="experimental")
        run_id = self.run_challenge(cr["id"])
        out = self.investigate(cr["id"], run_id, probes=True)
        self.assertEqual(self.job(out["job_id"])["job"]["status"], "done")
        rec = self.c.get(f"/api/forge/investigations/{out['investigation_id']}").json()
        self.assertEqual((rec["status"], rec["provenance"], len(rec["model_calls"])), ("done", "SCRIPTED_MOCK", 2))
        self.assertTrue(rec["probes"]["requested"] and rec["probes"]["results"] and rec["probes"]["expectations"])
        self.assertEqual(len(rec["probes"]["seeds"]), 4)
        events = self.job(out["job_id"])["events"]
        names = [e["data"].get("event", e["type"]) for e in events]
        self.assertEqual((names.count("probe_request"), names.count("probe_result")), (1, 3))   # the job manager has no such types: recorded as notes

    def test_default_has_no_probes(self):
        cr = self.create(mode="experimental")
        run_id = self.run_challenge(cr["id"])
        out = self.investigate(cr["id"], run_id)
        rec = self.c.get(f"/api/forge/investigations/{out['investigation_id']}").json()
        self.assertIsNone(rec["probes"])
        self.assertEqual(len(rec["model_calls"]), 1)
        self.assertEqual(self.pool.jobs, [])

    def test_probes_must_be_a_boolean(self):
        cr = self.create(mode="experimental")
        run_id = self.run_challenge(cr["id"])
        r = self.c.post(f"/api/forge/creatures/{cr['id']}/versions/1/investigations", json={"run_id": run_id, "mode": "scripted", "probes": 5})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
