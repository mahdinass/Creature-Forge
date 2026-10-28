import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from creature_forge import recoveries as rcv
from creature_forge.creatures import CreatureStore, seed_block
from creature_forge.sandbox import SandboxBody
from creature_forge.studio.forge_api import create_forge_router

VEC17 = [0.5] * 17


def body(**kw) -> dict:
    return {**SandboxBody().as_dict(), **kw}


def stub_pipeline(status_pool_jobs: bool = True):
    """run_pipeline stand-in: pushes a few fake pool jobs (so the progress/phase tracking runs) and returns a complete pipeline record."""
    def run(b, director, *, total_budget, seeds, pool, log, probe_budget, rounds, screen_top_k, screen_n, start_vector, **kw):
        log("round 1: probe opt_placement")
        list(pool.imap(lambda j: j, [{"seeds": [1]}, {"seeds": [2]}]))
        log("round 1: plan r1p0 budget 10")
        list(pool.imap(lambda j: j, [{"seed": s, "x": 1} for s in seeds["screen"][:screen_n]]))
        if hasattr(director, "choose_probes"):
            director.choose_probes({"round": 1, "available_probes": ["opt_placement", "opt_body", "opt_posture"]})
        return {"version": "stub", "used": min(total_budget, 77), "total_budget": total_budget, "family": 17,
                "final": {"body": b, "vector": [*start_vector, 0.1, 0.1], "edits": [{"param": "foot_length", "op": "scale", "value": 1.2,
                                                                                    "target": "both"}],
                          "source": "plan:r1p0", "aliases": [], "train_score": {"walking_count": 1}, "screen": {"walking": 1}},
                "decisions": [], "seeds": {"train": seeds["train"], "screen": seeds["screen"], "diag": seeds["diag"]}}
    return run


def stub_assess(status: str):
    def run(original, candidate, validate_seeds, confirm_seeds, *, pool=None, **kw):
        list(pool.imap(lambda j: j, [{"seed": s} for s in validate_seeds]))
        return {"rule": "full_recovery_v1", "status": status, "reasons": [] if status == "FULL_RECOVERY" else ["stub: not enough seeds walk"],
                "validation": {"verdict": {"status": "VERIFIED_IMPROVEMENT"}, "walking_frac": 1.0 if status == "FULL_RECOVERY" else 0.25,
                               "aggregate": "PASS"},
                "confirmation": {"run": status == "FULL_RECOVERY"}, "rollouts": {"validation": 2 * len(validate_seeds), "confirmation": 0},
                "seeds": {"validate": list(validate_seeds), "confirm": list(confirm_seeds)}}
    return run


def wait_job(client, job_id, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/forge/jobs/{job_id}").json()
        if j["job"]["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


class Case(unittest.TestCase):
    options = None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "forge"
        self.replays = []
        self.make_client()

    def replay(self, b, controllers, spec, seed, *, force=None, direction=1):
        self.replays.append((seed, spec.get("duration"), controllers["walk"]["vector"]))
        return {"seed": seed, "frames": {"pos": [[0, 0]]}}

    def make_client(self, **kw):
        router = create_forge_router(self.dir, replay_builder=self.replay, **kw)
        self.addCleanup(router.forge.close)
        app = FastAPI()
        app.include_router(router)
        self.c = TestClient(app)

    def make_stubbed(self, status="FULL_RECOVERY"):
        self.make_client(recovery_options={"pipeline_fn": stub_pipeline(), "assess_fn": stub_assess(status),
                                           "code_fn": lambda: {"commit": "abc", "dirty": False}})

    def creature(self):
        r = self.c.post("/api/forge/creatures", json={"name": "Stubby", "body": body(), "mode": "guided", "drawing": {}})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def start(self, cid, n=1, **req):
        return self.c.post(f"/api/forge/creatures/{cid}/versions/{n}/recoveries", json=req)

    def run_ok(self, cid, **req):
        r = self.start(cid, **req)
        self.assertEqual(r.status_code, 200, r.text)
        out = r.json()
        job = wait_job(self.c, out["job_id"])
        self.assertEqual(job["job"]["status"], "done", job)
        return out, job


class StoreAndSeeds(Case):
    def test_ids_are_fullmatch_validated(self):
        for bad in ("", "r-abc", "r-" + "0" * 8, "r-" + "0" * 12 + "\n", "../x", "r-" + "g" * 12, "r-" + "0" * 13):
            with self.assertRaises(KeyError):
                rcv.recovery_path(self.dir, bad)
        self.assertTrue(rcv.RECOVERY_ID_RE.fullmatch(rcv.new_recovery_id()))

    def test_atomic_roundtrip_and_no_tmp_left(self):
        rid = rcv.new_recovery_id()
        rec = {"id": rid, "created": "2026-01-01T00:00:00Z", "creature": {"cid": "c-00000000", "n": 1}, "director": "fix", "mode": None,
               "provenance": "NON_AI", "status": "NOT_RECOVERED", "budget": {"total": 400, "used": 10}, "x": float("nan")}
        rcv.save_recovery(self.dir, rec)
        got = rcv.load_recovery(self.dir, rid)
        self.assertIsNone(got["x"])   # non-finite becomes null, never NaN in a file
        self.assertEqual([p.name for p in (self.dir / "recoveries").iterdir()], [f"{rid}.json"])
        self.assertEqual([s["id"] for s in rcv.list_recoveries(self.dir)], [rid])
        self.assertEqual(rcv.list_recoveries(self.dir, "c-11111111"), [])
        with self.assertRaises(KeyError):
            rcv.load_recovery(self.dir, "r-" + "1" * 12)

    def test_seed_blocks_disjoint_and_in_product_namespace(self):
        from creature_forge.arena import _forbidden_seeds
        forbidden = set().union(*(set(v) for v in _forbidden_seeds().values()))
        for sizes in (rcv.FULL_SIZES, rcv.SMOKE_SIZES):
            for idx in range(5):
                plan = rcv.recovery_seeds("c-0a1b2c3d", 1, idx, sizes)
                flat = [s for r in rcv.ROLES for s in plan["seeds"][r]]
                self.assertEqual(len(flat), len(set(flat)), "roles must be pairwise disjoint")
                self.assertEqual({r: len(plan["seeds"][r]) for r in rcv.ROLES}, sizes)
                self.assertFalse(set(flat) & forbidden)
                self.assertTrue(all(100_000 <= s < 1_000_000 < rcv.RESEARCH_NAMESPACE_START for s in flat))
        # distinct role names: never the investigation blocks of the same (creature, version, round)
        plan = rcv.recovery_seeds("c-0a1b2c3d", 1, 0, rcv.FULL_SIZES)
        for role in ("train", "screen", "validate", "probe", "challenge"):
            self.assertFalse(set(plan["seeds"]["validate"]) & set(seed_block("c-0a1b2c3d", 1, plan["index"], role, 24)))
        a, b = rcv.recovery_seeds("c-0a1b2c3d", 1, 0, rcv.FULL_SIZES), rcv.recovery_seeds("c-0a1b2c3d", 1, 1, rcv.FULL_SIZES)
        self.assertNotEqual(a["seeds"]["validate"], b["seeds"]["validate"])

    def test_scale_settings(self):
        self.assertEqual(rcv.scale_settings("full", 2000)[0], 2000)
        self.assertEqual(rcv.scale_settings("full", 2000)[2]["probe_budget"], 200)
        total, sizes, st = rcv.scale_settings("smoke", 4000)
        self.assertEqual((total, st["probe_budget"], st["screen_n"], st["rounds"]), (400, 40, 2, 1))
        self.assertEqual((sizes["train"], sizes["validate"], sizes["confirm"]), (2, 4, 4))

    def test_accepts_only_full_recovery_in_the_store(self):
        st = CreatureStore(self.dir)
        rec = st.create(name="a", body=body(), mode="guided")
        for status in ("PARTIAL_IMPROVEMENT", "NOT_RECOVERED", "INCONCLUSIVE_ERROR", "VERIFIED_IMPROVEMENT", None):
            with self.assertRaisesRegex(ValueError, "FULL_RECOVERY"):
                st.accept_recovery(rec["id"], parent_n=1, body=body(), vector=VEC17, change={"status": status, "recovery_id": "r-x"},
                                   origin="ai_accepted")
        with self.assertRaises(ValueError):   # user origin is not an acceptance
            st.accept_recovery(rec["id"], parent_n=1, body=body(), vector=VEC17, change={"status": "FULL_RECOVERY"}, origin="user")
        with self.assertRaises(ValueError):   # a 3-number vector is not a controller
            st.accept_recovery(rec["id"], parent_n=1, body=body(), vector=[1, 2, 3], change={"status": "FULL_RECOVERY"}, origin="ai_accepted")
        self.assertEqual(len(st.get(rec["id"])["versions"]), 1)


class Api(Case):
    def test_request_validation(self):
        self.make_stubbed()
        cid = self.creature()["id"]
        self.assertEqual(self.start(cid, director="ai", mode="scripted", budget=399).status_code, 422)
        self.assertEqual(self.start(cid, director="ai", mode="scripted", budget=4001).status_code, 422)
        self.assertEqual(self.start(cid, director="magic").status_code, 422)
        self.assertEqual(self.start(cid, director="fix", mode="scripted").status_code, 422)
        self.assertEqual(self.start(cid, director="ai", mode="scripted", extra=1).status_code, 422)
        self.assertEqual(self.start(cid, n=9, director="fix").status_code, 404)
        self.assertEqual(self.start("c-00000000", director="fix").status_code, 404)
        self.assertEqual(self.c.get("/api/forge/recoveries/r-nothex").status_code, 404)
        self.assertEqual(self.c.get("/api/forge/recoveries/r-" + "0" * 12).status_code, 404)

    def test_scripted_ai_happy_path_stubbed(self):
        self.make_stubbed("FULL_RECOVERY")
        cid = self.creature()["id"]
        out, job = self.run_ok(cid, director="ai", mode="scripted", budget=800)
        rid = out["recovery_id"]
        self.assertTrue(rcv.RECOVERY_ID_RE.fullmatch(rid))
        rec = self.c.get(f"/api/forge/recoveries/{rid}").json()
        self.assertEqual((rec["director"], rec["mode"], rec["provenance"], rec["model"]), ("ai", "scripted", "SCRIPTED_MOCK", "scripted-fixture"))
        self.assertEqual(rec["director_record"]["provenance"], "SCRIPTED_MOCK")
        self.assertEqual((rec["status"], rec["family"], rec["scale"], rec["rule"]), ("FULL_RECOVERY", 17, "full", "full_recovery_v1"))
        self.assertEqual((rec["budget"]["requested"], rec["budget"]["total"], rec["budget"]["probe_budget"], rec["budget"]["used"]),
                         (800, 800, 80, 77))
        self.assertEqual(rec["creature"]["n"], 1)
        self.assertEqual(rec["code"], {"commit": "abc", "dirty": False})
        self.assertEqual(len(rec["candidate"]["vector"]), 17)
        self.assertEqual(rec["candidate"]["edits"][0]["param"], "foot_length")
        self.assertEqual({r: len(v) for r, v in rec["seeds"].items()}, rcv.FULL_SIZES)
        # events: the phases came through jobs.py, in order, with progress carrying used/total
        events = job["events"]
        phases = [e["data"]["phase"] for e in events if e["type"] == "phase"]
        self.assertEqual(phases[0], "diagnostics")
        for p in ("probes", "plans", "screening", "validation", "done"):
            self.assertIn(p, phases)
        self.assertEqual(phases, sorted(phases, key=rcv.PHASES.index))
        prog = [e["data"] for e in events if e["type"] == "progress"]
        self.assertTrue(prog and all(p["done"] <= p["total"] for p in prog))
        self.assertTrue(any(p["total"] == 800 for p in prog))
        self.assertEqual(job["job"]["kind"], "recovery")
        listing = self.c.get("/api/forge/recoveries").json()
        self.assertEqual([s["id"] for s in listing], [rid])
        self.assertEqual(listing[0]["provenance"], "SCRIPTED_MOCK")
        self.assertNotIn("pipeline", listing[0])
        self.assertEqual(self.c.get(f"/api/forge/recoveries?cid={cid}").json()[0]["id"], rid)
        self.assertEqual(self.c.get("/api/forge/recoveries?cid=c-00000000").json(), [])

    def test_fix_director_is_non_ai(self):
        self.make_stubbed("FULL_RECOVERY")
        cid = self.creature()["id"]
        out, _ = self.run_ok(cid, director="fix")
        rec = self.c.get(f"/api/forge/recoveries/{out['recovery_id']}").json()
        self.assertEqual((rec["provenance"], rec["model"], rec["mode"], rec["director_record"]), ("NON_AI", None, None, None))
        self.assertEqual(rec["budget"]["total"], rcv.DEFAULT_BUDGET)
        r = self.c.post(f"/api/forge/creatures/{cid}/accept-recovery", json={"recovery_id": out["recovery_id"]})
        self.assertEqual(r.status_code, 200, r.text)
        v2 = r.json()["versions"][-1]
        self.assertEqual((v2["origin"], v2["change"]["source"], v2["change"]["model"]), ("baseline_accepted", "fix_rule", None))

    def test_accept_full_recovery_once(self):
        self.make_stubbed("FULL_RECOVERY")
        cid = self.creature()["id"]
        out, _ = self.run_ok(cid, director="ai", mode="scripted")
        rid = out["recovery_id"]
        r = self.c.post(f"/api/forge/creatures/{cid}/accept-recovery", json={"recovery_id": rid})
        self.assertEqual(r.status_code, 200, r.text)
        rec = r.json()
        v2 = rec["versions"][-1]
        self.assertEqual((rec["current"], v2["n"], v2["parent"], v2["origin"]), (2, 2, 1, "ai_accepted"))
        self.assertEqual(len(v2["controllers"]["walk"]["vector"]), 17)
        self.assertEqual(v2["controllers"]["walk"]["provenance"],
                         {"kind": "recovery", "recovery_id": rid, "director": "ai", "status": "FULL_RECOVERY"})
        ch = v2["change"]
        self.assertEqual((ch["recovery_id"], ch["director"], ch["status"], ch["source"], ch["provenance"]),
                         (rid, "ai", "FULL_RECOVERY", "scripted_mock", "SCRIPTED_MOCK"))
        self.assertEqual(ch["edits"][0]["param"], "foot_length")
        again = self.c.post(f"/api/forge/creatures/{cid}/accept-recovery", json={"recovery_id": rid})
        self.assertEqual(again.status_code, 409)
        self.assertIn("already accepted", again.json()["detail"])
        self.assertEqual(len(self.c.get(f"/api/forge/creatures/{cid}").json()["versions"]), 2)

    def test_accept_refused_unless_full_recovery(self):
        self.make_stubbed("PARTIAL_IMPROVEMENT")
        cid = self.creature()["id"]
        out, _ = self.run_ok(cid, director="ai", mode="scripted")
        rec = self.c.get(f"/api/forge/recoveries/{out['recovery_id']}").json()
        self.assertEqual(rec["status"], "PARTIAL_IMPROVEMENT")
        r = self.c.post(f"/api/forge/creatures/{cid}/accept-recovery", json={"recovery_id": out["recovery_id"]})
        self.assertEqual(r.status_code, 409)
        self.assertIn("FULL_RECOVERY", r.json()["detail"])
        self.assertIn("stricter", r.json()["detail"])
        self.assertEqual(len(self.c.get(f"/api/forge/creatures/{cid}").json()["versions"]), 1)

    def test_accept_constructed_records(self):
        self.make_stubbed()
        cid = self.creature()["id"]
        other = self.creature()["id"]
        v1 = self.c.get(f"/api/forge/creatures/{cid}").json()["versions"][0]

        def make(status, **over):
            rid = rcv.new_recovery_id()
            rec = {"id": rid, "created": "2026-01-01T00:00:00Z", "creature": {"cid": cid, "n": 1, "content_hash": v1["content_hash"]},
                   "director": "ai", "mode": "live", "provenance": "LIVE", "model": "nvidia/x", "status": status,
                   "assessment": {"rule": "full_recovery_v1", "status": status, "reasons": ["r1"], "validation": {"verdict": {"status": "V"}}},
                   "candidate": {"body": v1["body"], "vector": VEC17, "edits": []}, "budget": {"total": 2000},
                   "director_record": {"decisions": [{"kind": "plans", "diagnosis": "feet too short"}]}, **over}
            rcv.save_recovery(self.dir, rec)
            return rid

        def post(rid, c=cid):
            return self.c.post(f"/api/forge/creatures/{c}/accept-recovery", json={"recovery_id": rid})

        for st in ("PARTIAL_IMPROVEMENT", "NOT_RECOVERED", "INCONCLUSIVE_ERROR", "failed", "cancelled"):
            r = post(make(st))
            self.assertEqual(r.status_code, 409, st)
            self.assertIn("FULL_RECOVERY", r.json()["detail"])
        self.assertEqual(post(make("FULL_RECOVERY"), other).status_code, 409)             # another creature's recovery
        stale = make("FULL_RECOVERY", creature={"cid": cid, "n": 1, "content_hash": "0" * 64})
        self.assertEqual(post(stale).status_code, 409)                                   # the version changed
        forged = make("FULL_RECOVERY", assessment={"rule": "full_recovery_v1", "status": "NOT_RECOVERED"})
        self.assertEqual(post(forged).status_code, 409)                                  # record status and assessment disagree
        short = make("FULL_RECOVERY", candidate={"body": v1["body"], "vector": [0.1] * 5, "edits": []})
        self.assertEqual(post(short).status_code, 409)
        self.assertEqual(post("r-" + "f" * 12).status_code, 404)
        self.assertEqual(post("nope").status_code, 404)
        self.assertEqual(len(self.c.get(f"/api/forge/creatures/{cid}").json()["versions"]), 1)
        ok = make("FULL_RECOVERY")
        r = post(ok)
        self.assertEqual(r.status_code, 200, r.text)
        v2 = r.json()["versions"][-1]
        self.assertEqual((v2["origin"], v2["change"]["source"], v2["change"]["model"], v2["change"]["rationale"]),
                         ("ai_accepted", "nemotron", "nvidia/x", "feet too short"))
        self.assertEqual(post(ok).status_code, 409)

    def test_replay_arms(self):
        self.make_stubbed()
        cid = self.creature()["id"]
        out, _ = self.run_ok(cid, director="fix")
        rid = out["recovery_id"]
        rec = self.c.get(f"/api/forge/recoveries/{rid}").json()
        seed = rec["seeds"]["validate"][0]
        url = f"/api/forge/recoveries/{rid}/replay"
        a = self.c.get(url, params={"arm": "original", "seed": seed})
        b = self.c.get(url, params={"arm": "candidate", "seed": seed})
        self.assertEqual((a.status_code, b.status_code), (200, 200), a.text + b.text)
        self.assertEqual(len(self.replays), 2)
        self.assertEqual(len(self.replays[0][2]), 15)   # the original runs its own 15-parameter controller
        self.assertEqual(len(self.replays[1][2]), 17)
        self.assertEqual(self.replays[0][1], 10.0)
        self.c.get(url, params={"arm": "original", "seed": seed})
        self.assertEqual(len(self.replays), 2)           # cached
        self.assertEqual(self.c.get(url, params={"arm": "candidate", "seed": 5}).status_code, 404)   # not a recovery seed
        self.assertEqual(self.c.get(url, params={"arm": "other", "seed": seed}).status_code, 422)
        self.assertEqual(self.c.get(url, params={"arm": "candidate"}).status_code, 422)
        # confirmation ran (stub FULL_RECOVERY) for the candidate only, for 20 s; the original never ran on those seeds
        cseed = rec["seeds"]["confirm"][0]
        self.assertEqual(self.c.get(url, params={"arm": "original", "seed": cseed}).status_code, 404)
        self.assertEqual(self.c.get(url, params={"arm": "candidate", "seed": cseed}).status_code, 200)
        self.assertEqual(self.replays[-1][1], 20.0)
        self.assertEqual(self.c.get("/api/forge/recoveries/r-" + "0" * 12 + "/replay", params={"arm": "original", "seed": 1}).status_code, 404)

    def test_failed_run_is_recorded_and_job_fails(self):
        def boom(*a, **k):
            raise RuntimeError("boom at /srv/private/x.py")
        self.make_client(recovery_options={"pipeline_fn": boom, "assess_fn": stub_assess("FULL_RECOVERY")})
        cid = self.creature()["id"]
        r = self.start(cid, director="fix")
        job = wait_job(self.c, r.json()["job_id"])
        self.assertEqual(job["job"]["status"], "failed")
        rec = self.c.get(f"/api/forge/recoveries/{r.json()['recovery_id']}").json()
        self.assertEqual(rec["status"], "failed")
        self.assertNotIn("/srv/private", json.dumps(rec["error"]))
        self.assertIsNone(rec["candidate"])
        acc = self.c.post(f"/api/forge/creatures/{cid}/accept-recovery", json={"recovery_id": r.json()["recovery_id"]})
        self.assertEqual(acc.status_code, 409)

    def test_cancel(self):
        import threading
        gate, started = threading.Event(), threading.Event()

        def slow(b, director, *, pool, **kw):
            started.set()
            gate.wait(5)
            list(pool.imap(lambda j: j, [{"seeds": [1]}] * 3))   # the cancel is noticed on the next finished job
            raise AssertionError("must have been cancelled")
        self.make_client(recovery_options={"pipeline_fn": slow, "assess_fn": stub_assess("FULL_RECOVERY")})
        cid = self.creature()["id"]
        r = self.start(cid, director="fix").json()
        self.assertTrue(started.wait(10))
        self.c.post(f"/api/forge/jobs/{r['job_id']}/cancel")
        gate.set()
        job = wait_job(self.c, r["job_id"])
        self.assertEqual(job["job"]["status"], "cancelled")
        self.assertEqual(self.c.get(f"/api/forge/recoveries/{r['recovery_id']}").json()["status"], "cancelled")


class LiveGate(Case):
    def test_live_refused_without_env_gate(self):
        self.make_stubbed()
        cid = self.creature()["id"]
        with mock.patch.dict(os.environ, {"CREATURE_FORGE_ENABLE_LIVE": "0"}):
            r = self.start(cid, director="ai", mode="live")
        self.assertEqual(r.status_code, 503)
        self.assertIn("CREATURE_FORGE_ENABLE_LIVE", r.json()["detail"])
        self.assertEqual(self.c.get("/api/forge/recoveries").json(), [])

    def test_live_refused_under_smoke_scale_even_when_enabled(self):
        self.make_stubbed()
        cid = self.creature()["id"]
        with mock.patch.dict(os.environ, {"CREATURE_FORGE_ENABLE_LIVE": "1", "CF_INVESTIGATION_SCALE": "smoke", "NEBIUS_API_KEY": "k-test"}):
            r = self.start(cid, director="ai", mode="live")
        self.assertEqual(r.status_code, 503)
        self.assertIn("full scale", r.json()["detail"])
        self.assertNotIn("k-test", r.text)

    def test_live_refused_inside_run_too(self):
        # defence in depth: run_recovery itself refuses a live smoke run before anything is written
        st = CreatureStore(self.dir)
        cr = st.create(name="a", body=body(), mode="guided")
        plan = rcv.recovery_seeds(cr["id"], 1, 0, rcv.SMOKE_SIZES)
        with self.assertRaises(rcv.inv.LiveRefused):
            rcv.run_recovery(store=st, forge_dir=self.dir, rid=rcv.new_recovery_id(), cid=cr["id"], n=1, director="ai", mode="live",
                             requested_budget=400, total=400, settings=rcv.SMOKE_SETTINGS, scale="smoke", plan=plan,
                             options={"director_factory": lambda *a, **k: (object(), "LIVE", "m")})
        self.assertFalse((self.dir / "recoveries").exists() and any((self.dir / "recoveries").glob("r-*.json")))


class RealSmoke(Case):
    """Real MuJoCo at smoke scale with the scripted director (run on the VM, never on the Windows machine)."""

    def test_end_to_end_smoke(self):
        with mock.patch.dict(os.environ, {"CF_INVESTIGATION_SCALE": "smoke", "CREATURE_FORGE_ENABLE_LIVE": "0"}):
            self.make_client()
            cid = self.creature()["id"]
            r = self.start(cid, director="ai", mode="scripted", budget=4000)
            self.assertEqual(r.status_code, 200, r.text)
            job = wait_job(self.c, r.json()["job_id"], timeout=1500)
            self.assertEqual(job["job"]["status"], "done", job)
            rec = self.c.get(f"/api/forge/recoveries/{r.json()['recovery_id']}").json()
        self.assertEqual(rec["scale"], "smoke")
        self.assertEqual((rec["budget"]["requested"], rec["budget"]["total"], rec["budget"]["probe_budget"]), (4000, 400, 40))
        self.assertLessEqual(rec["budget"]["used"], 400)
        self.assertEqual({k: len(v) for k, v in rec["seeds"].items()}, rcv.SMOKE_SIZES)
        self.assertEqual((rec["provenance"], rec["model"]), ("SCRIPTED_MOCK", "scripted-fixture"))
        self.assertIn(rec["status"], ("FULL_RECOVERY", "PARTIAL_IMPROVEMENT", "NOT_RECOVERED", "INCONCLUSIVE_ERROR"))
        self.assertEqual(len(rec["candidate"]["vector"]), 17)
        self.assertEqual(rec["assessment"]["rule"], "full_recovery_v1")
        self.assertEqual(rec["assessment"]["seeds"]["validate"], rec["seeds"]["validate"])
        self.assertEqual(rec["pipeline"]["family"], 17)
        self.assertEqual(rec["director_record"]["provenance"], "SCRIPTED_MOCK")
        # accept follows the rule whatever the tiny run found
        acc = self.c.post(f"/api/forge/creatures/{cid}/accept-recovery", json={"recovery_id": rec["id"]})
        self.assertEqual(acc.status_code, 200 if rec["status"] == "FULL_RECOVERY" else 409, acc.text)


class NoSecrets(Case):
    def test_no_api_key_in_records_or_responses(self):
        self.make_stubbed()
        cid = self.creature()["id"]
        with mock.patch.dict(os.environ, {"NEBIUS_API_KEY": "sk-secret-123456", "CREATURE_FORGE_ENABLE_LIVE": "0"}):
            out, job = self.run_ok(cid, director="ai", mode="scripted")
            texts = [self.c.get(f"/api/forge/recoveries/{out['recovery_id']}").text, json.dumps(job), self.c.get("/api/forge/recoveries").text,
                     (self.dir / "recoveries" / f"{out['recovery_id']}.json").read_text(encoding="utf-8")]
        for t in texts:
            self.assertNotIn("sk-secret-123456", t)


if __name__ == "__main__":
    unittest.main()
