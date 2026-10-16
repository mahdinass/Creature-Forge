"""Regression tests for the PR #16 security review (M1-M3, L1-L5, hardening). No network, no MuJoCo."""
import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import test_forge_ai as tfa
import test_forge_api as tapi
from creature_forge import forge_ai as fa
from creature_forge import investigation
from creature_forge import interventions as iv
from creature_forge import nebius
from creature_forge.config import validate_base_url
from creature_forge.creatures import CreatureStore, canonical_json, default_controllers
from creature_forge.jobs import JobManager, QueueFull, public_error
from creature_forge.nebius import NebiusClient, NebiusError
from creature_forge.studio.app import create_app
from creature_forge.studio.security import RequestGuard

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra" / "nebius"))


def wait_for(pred, timeout=5.0):
    return tapi.wait_for(pred, timeout)


# ------------------------------------------------------------------------------------------------------------------ M1
class FloodingTests(tapi.ApiCase):
    def test_queue_cap_answers_429_and_frees_up_afterwards(self):
        self.fakes.block = threading.Event()
        cr = self.create()
        with mock.patch.dict(os.environ, {"CF_MAX_QUEUED_JOBS": "2"}):
            ids = [self.start(cr["id"], seeds=1) for _ in range(2)]
            self.assertTrue(all(r.status_code == 200 for r in ids))
            r = self.start(cr["id"], seeds=1)
            self.assertEqual(r.status_code, 429, r.text)
            self.assertIn("detail", r.json())
            self.fakes.block.set()
            for r in ids:
                self.wait_job(r.json()["job_id"], "done")
            self.assertEqual(self.start(cr["id"], seeds=1).status_code, 200)

    def test_creature_cap_answers_429(self):
        with mock.patch.dict(os.environ, {"CF_MAX_CREATURES": "2"}):
            self.create(name="a")
            self.create(name="b")
            r = self.c.post("/api/forge/creatures", json={"name": "c", "body": tapi.body(), "mode": "guided", "drawing": {}})
            self.assertEqual(r.status_code, 429, r.text)
            self.assertEqual(len(self.c.get("/api/forge/creatures").json()), 2)


class BodySizeTests(unittest.TestCase):
    def test_bodies_over_4mb_are_413_before_the_endpoint_runs(self):
        app = FastAPI()
        app.add_middleware(RequestGuard)
        hits = []

        @app.post("/api/x")
        def x(payload: dict):
            hits.append(1)
            return {"ok": True}

        c = TestClient(app)
        self.assertEqual(c.post("/api/x", json={"a": "b"}).status_code, 200)
        r = c.post("/api/x", content=b'{"a":"' + b"x" * (4 * 1024 * 1024 + 10) + b'"}', headers={"content-type": "application/json"})
        self.assertEqual(r.status_code, 413, r.text)
        self.assertIn("detail", r.json())
        self.assertEqual(len(hits), 1)

        def chunks():  # no Content-Length: counted while streaming
            for _ in range(5):
                yield b"x" * (1024 * 1024)
        r = c.post("/api/x", content=chunks(), headers={"content-type": "application/json"})
        self.assertEqual(r.status_code, 413, r.text)


# ------------------------------------------------------------------------------------------------------------------ M2 / L5
class LedgerAccountingTests(tfa.Case):
    def rows(self, led):
        return [json.loads(line) for line in led.path.read_text(encoding="utf-8").splitlines()]

    def call(self, items, led=None):
        t = tfa.Scripted(items)
        led = led or self.ledger()
        return fa.call_model(self.client(t), self.cfg, self.msgs(), led, investigation_id="i-1"), led

    def msgs(self):
        return fa.build_messages(self.ev, allowed=iv.editable_params(self.version, self.kind))

    def worst(self, led):
        reserve = [r for r in self.rows(led) if r.get("kind") == "reserve"][0]
        return reserve["worst_case_usd"], reserve["est_prompt_tokens"], reserve["max_tokens"]

    def test_sent_request_with_http_error_settles_at_worst_case(self):
        c, led = self.call([NebiusError("HTTP 500: boom")])
        worst, est, mx = self.worst(led)
        last = self.rows(led)[-1]
        self.assertTrue(last["usage_estimated"])
        self.assertAlmostEqual(last["cost_usd"], worst)
        self.assertEqual((last["prompt_tokens"], last["completion_tokens"]), (est, mx))
        self.assertEqual(led.status()["requests"], 1)
        self.assertAlmostEqual(led.status()["usd"], round(worst, 6), places=6)
        self.assertAlmostEqual(c.cost_usd, worst)
        self.assertTrue(c.usage.get("usage_estimated"))

    def test_response_without_usage_settles_at_worst_case(self):
        resp = tfa.completion("{}")
        del resp["usage"]
        c, led = self.call([resp])
        self.assertTrue(self.rows(led)[-1]["usage_estimated"])
        self.assertAlmostEqual(self.rows(led)[-1]["cost_usd"], self.worst(led)[0])

    def test_known_usage_is_not_flagged(self):
        c, led = self.call([tfa.completion("{}", pt=100, ct=50)])
        last = self.rows(led)[-1]
        self.assertNotIn("usage_estimated", last)
        self.assertEqual((last["prompt_tokens"], last["completion_tokens"]), (100, 50))

    def test_request_never_sent_is_released_not_charged(self):
        t = tfa.Scripted([tfa.completion("{}")])
        client = self.client(t)
        client.limits = nebius.Limits(max_requests=0)        # the client refuses before any transport call
        led = self.ledger()
        c = fa.call_model(client, self.cfg, self.msgs(), led, investigation_id="i-1")
        self.assertFalse(c.sent)
        self.assertEqual(t.calls, [])
        self.assertEqual(self.rows(led)[-1]["status"], "not_sent")
        self.assertEqual(led.status()["requests"], 0)
        self.assertEqual(led.status()["usd"], 0)

    def test_unexpected_exception_after_send_settles_worst_case_and_reraises(self):
        led = self.ledger()
        t = tfa.Scripted([RuntimeError("transport exploded")])
        with self.assertRaises(RuntimeError):
            fa.call_model(self.client(t), self.cfg, self.msgs(), led, investigation_id="i-1")
        last = self.rows(led)[-1]
        self.assertTrue(last["usage_estimated"])
        self.assertAlmostEqual(last["cost_usd"], self.worst(led)[0])
        self.assertEqual(led.status()["requests"], 1)

    def test_unexpected_exception_before_send_releases_the_reservation_and_reraises(self):
        led = self.ledger()
        client = self.client(tfa.Scripted([]))
        client.chat = mock.Mock(side_effect=ValueError("bad argument"))
        with self.assertRaises(ValueError):
            fa.call_model(client, self.cfg, self.msgs(), led, investigation_id="i-1")
        self.assertEqual(self.rows(led)[-1]["status"], "not_sent")
        self.assertEqual(led.status()["requests"], 0)
        self.assertEqual(led.status()["usd"], 0)


# ------------------------------------------------------------------------------------------------------------------ M3
class HostOriginTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.app = create_app(forge_dir=root / "forge", dist_dir=root / "nodist")

    def client(self, base):
        return TestClient(self.app, base_url=base)

    def test_loopback_hosts_with_any_port_are_served(self):
        for base in ("http://127.0.0.1:8765", "http://localhost:8000", "http://[::1]:5173", "http://127.0.0.1"):
            self.assertEqual(self.client(base).get("/api/schema").status_code, 200, base)

    def test_foreign_host_is_refused_dns_rebinding(self):
        r = self.client("http://evil.example:8000").get("/api/schema")
        self.assertEqual(r.status_code, 403)
        self.assertIn("detail", r.json())

    def test_extra_hosts_from_env_and_testserver_gate(self):
        with mock.patch.dict(os.environ, {"CF_ALLOWED_HOSTS": "studio.lan, other.lan"}):
            self.assertEqual(self.client("http://studio.lan:9000").get("/api/schema").status_code, 200)
        self.assertEqual(self.client("http://studio.lan:9000").get("/api/schema").status_code, 403)
        with mock.patch.dict(os.environ, {"CF_ALLOW_TESTSERVER": "0"}):
            self.assertEqual(TestClient(self.app).get("/api/schema").status_code, 403)

    def test_cross_site_write_is_refused_but_same_origin_and_originless_pass(self):
        c = self.client("http://127.0.0.1:8765")
        payload = {"name": "x", "body": {}, "mode": "guided"}
        r = c.post("/api/forge/creatures", json=payload, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403, r.text)
        self.assertIn("detail", r.json())
        r = c.post("/api/forge/creatures", json=payload, headers={"Origin": "http://localhost:8765"})   # other name: not same-origin
        self.assertEqual(r.status_code, 403)
        r = c.post("/api/forge/creatures", json=payload, headers={"Origin": "null"})
        self.assertEqual(r.status_code, 403)
        for headers in ({"Origin": "http://127.0.0.1:8765"}, {}):
            self.assertNotEqual(c.post("/api/forge/creatures", json=payload, headers=headers).status_code, 403)
        self.assertEqual(c.get("/api/schema", headers={"Origin": "https://evil.example"}).status_code, 200)  # reads are not writes


# ------------------------------------------------------------------------------------------------------------------ L1
class TracebackLeakTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "forge"
        self.jm = JobManager(self.root)
        self.addCleanup(self.jm.close)

    def test_public_error_strips_paths_and_truncates(self):
        e = RuntimeError(r"cannot open C:\Users\bob\secret\file.json and /home/bob/.cache/x/y.txt now")
        text = public_error(e)
        self.assertNotIn("bob", text)
        self.assertTrue(text.startswith("RuntimeError: "))
        self.assertLessEqual(len(public_error(ValueError("x" * 5000))), 300)

    def test_failed_job_exposes_no_traceback_but_keeps_a_trace_file(self):
        def boom(ctx):
            raise RuntimeError("bad thing at /srv/forge/private/mod.py")
        jid = self.jm.submit("challenge", boom)
        self.assertTrue(wait_for(lambda: self.jm.get(jid)["status"] == "failed"))
        job, events = self.jm.get(jid), self.jm.events(jid)
        blob = json.dumps([job, events])
        self.assertNotIn("Traceback", blob)
        self.assertNotIn("traceback_tail", blob)
        self.assertNotIn("/srv/forge/private", blob)
        self.assertTrue(job["error"].startswith("RuntimeError: bad thing"))
        trace = (self.root / "jobs" / f"{jid}.trace.txt").read_text(encoding="utf-8")
        self.assertIn("Traceback", trace)
        self.assertIn("boom", trace)

    def test_queue_full_on_the_manager(self):
        gate = threading.Event()
        with mock.patch.dict(os.environ, {"CF_MAX_QUEUED_JOBS": "1"}):
            self.jm.submit("challenge", lambda ctx: gate.wait(5))
            with self.assertRaises(QueueFull):
                self.jm.submit("challenge", lambda ctx: None)
        gate.set()


class ReplayHardeningTests(tapi.ApiCase):
    def run_one(self):
        cr = self.create()
        out = self.start(cr["id"], seeds=3).json()
        self.wait_job(out["job_id"], "done")
        run = self.c.get(f"/api/forge/runs/{out['run_id']}").json()
        return out["run_id"], run["spec"]["seeds"]

    def test_replay_failure_has_no_traceback_or_path(self):
        rid, seeds = self.run_one()

        def bad(*a, **k):
            raise OSError("cannot read /srv/forge/private/x.bin")
        self.fakes.replay = bad
        self.make_client_keep_runs()
        r = self.c.get("/api/forge/replay", params={"run_id": rid, "seed": seeds[0]})
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("/srv/forge", r.text)
        self.assertNotIn("Traceback", r.text)
        self.assertIn("OSError", r.text)

    def make_client_keep_runs(self):
        # the router was built with the bound method `self.fakes.replay`; rebuild it over the same directory with the new fake
        self.router.forge.close()
        self.make_client()

    def test_force_is_quantised_and_bounded_to_the_spec_max(self):
        rid, seeds = self.run_one()
        url, s = "/api/forge/replay", seeds[0]
        self.c.get(url, params={"run_id": rid, "seed": s, "force": 2.3})
        self.c.get(url, params={"run_id": rid, "seed": s, "force": 2.4})        # same 0.5 N bucket: cached
        self.c.get(url, params={"run_id": rid, "seed": s, "force": 300.0})
        self.assertEqual([f for _, f, _ in self.fakes.replays], [2.5, 80.0])  # default spec max_force is 80 N
        self.assertEqual(self.c.get(url, params={"run_id": rid, "seed": s, "force": -1}).status_code, 422)

    def test_at_most_two_uncached_replays_run_at_once(self):
        rid, seeds = self.run_one()
        gate, entered = threading.Event(), threading.Semaphore(0)

        def slow(b, controllers, spec, seed, *, force=None, direction=1):
            entered.release()
            gate.wait(5)
            return {"seed": seed, "force": force}
        self.fakes.replay = slow
        self.router.forge.close()
        self.make_client()
        results = []

        def go(f):
            results.append(self.c.get("/api/forge/replay", params={"run_id": rid, "seed": seeds[0], "force": f}).status_code)
        threads = [threading.Thread(target=go, args=(f,)) for f in (1.0, 2.0)]
        for t in threads:
            t.start()
        self.assertTrue(entered.acquire(timeout=5) and entered.acquire(timeout=5))
        self.assertEqual(self.c.get("/api/forge/replay", params={"run_id": rid, "seed": seeds[0], "force": 3.0}).status_code, 429)
        gate.set()
        for t in threads:
            t.join(5)
        self.assertEqual(sorted(results), [200, 200])


# ------------------------------------------------------------------------------------------------------------------ L2 / L3
class IdRegexTests(tapi.ApiCase):
    def test_trailing_newline_ids_are_rejected(self):
        cr = self.create()
        store = CreatureStore(self.dir)
        for bad in (cr["id"] + "\n", "c-12345678\n"):
            with self.assertRaises(KeyError):
                store.get(bad)
        jm = JobManager(self.dir)
        self.addCleanup(jm.close)
        with self.assertRaises(KeyError):
            jm.get("j-12345678\n")
        with self.assertRaises(KeyError):
            investigation.load_investigation(self.dir, "i-123456\n")
        self.assertEqual(self.c.get("/api/forge/runs/r-12345678%0A").status_code, 404)
        self.assertEqual(self.c.get("/api/forge/jobs/j-12345678%0A").status_code, 404)

    def test_unreadable_record_is_a_404_not_a_500(self):
        (self.dir / "creatures" / "c-aaaaaaaa.json").mkdir(parents=True)     # reading a directory raises OSError
        (self.dir / "runs" / "r-aaaaaaaa.json").mkdir(parents=True)
        (self.dir / "jobs" / "j-aaaaaaaa.json").mkdir(parents=True)
        (self.dir / "investigations" / "i-aaaaaaaa.json").mkdir(parents=True)
        for path in ("creatures/c-aaaaaaaa", "runs/r-aaaaaaaa", "jobs/j-aaaaaaaa", "investigations/i-aaaaaaaa"):
            self.assertEqual(self.c.get(f"/api/forge/{path}").status_code, 404, path)


class AcceptIdempotencyTests(unittest.TestCase):
    def test_same_investigation_and_arm_cannot_be_accepted_twice(self):
        from test_creatures import body, change
        with tempfile.TemporaryDirectory() as tmp:
            store = CreatureStore(Path(tmp))
            c = store.create(name="S", body=body(), mode="guided", drawing={})
            ch = {**change(), "investigation_id": "i-abcdef", "arm_id": "ai:P1"}
            store.accept(c["id"], parent_n=1, body=body(), controllers=default_controllers(), change=ch)
            with self.assertRaisesRegex(ValueError, "already accepted"):
                store.accept(c["id"], parent_n=1, body=body(), controllers=default_controllers(), change=ch)
            self.assertEqual(len(store.get(c["id"])["versions"]), 2)
            other = {**ch, "arm_id": "ai:P2"}
            store.accept(c["id"], parent_n=1, body=body(), controllers=default_controllers(), change=other)
            self.assertEqual(len(store.get(c["id"])["versions"]), 3)


# ------------------------------------------------------------------------------------------------------------------ hardening
class NebiusHardeningTests(unittest.TestCase):
    def test_key_is_redacted_from_provider_error_text(self):
        import io
        import urllib.error
        key = "sk-test-SECRET-123"

        class Opener:
            def open(self, req, timeout=None):
                raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(f"bad key {key} / Bearer {key}".encode()))
        with mock.patch.object(nebius, "_OPENER", Opener()):
            with self.assertRaises(NebiusError) as cm:
                nebius._urllib_transport("https://x.test/v1/chat/completions", {"Authorization": f"Bearer {key}"}, {}, 1.0)
        self.assertNotIn(key, str(cm.exception))
        self.assertIn("HTTP 401", str(cm.exception))

    def test_custom_transport_errors_are_redacted_in_calls_and_exception(self):
        key = "sk-test-SECRET-123"

        def tr(url, headers, body, timeout):
            raise NebiusError(f"echo {key}")
        c = NebiusClient(transport=tr, api_key=key, base_url="https://x.test/v1")
        with self.assertRaises(NebiusError) as cm:
            c.chat([{"role": "user", "content": "hi"}])
        self.assertNotIn(key, str(cm.exception))
        self.assertNotIn(key, json.dumps(c.calls))

    def test_redirects_are_not_followed(self):
        import urllib.request
        h = nebius._NoRedirect()
        self.assertIsNone(h.redirect_request(urllib.request.Request("https://a.test/"), None, 302, "Found", {}, "https://evil.test/"))

    def test_base_url_must_be_https_except_the_scripted_placeholder(self):
        self.assertEqual(validate_base_url("https://api.example.com/v1/"), "https://api.example.com/v1")
        self.assertEqual(validate_base_url("http://scripted.invalid"), "http://scripted.invalid")
        for bad in ("http://api.example.com/v1", "ftp://x", "api.example.com", "", "https://", "http://localhost:1/v1"):
            with self.assertRaises(ValueError, msg=bad):
                validate_base_url(bad)
        with mock.patch.dict(os.environ, {"NEBIUS_BASE_URL": "http://evil.test/v1"}):
            with self.assertRaises(ValueError):
                NebiusClient(api_key="k")
        with self.assertRaises(ValueError):
            NebiusClient(api_key="k", base_url="http://evil.test/v1")


class ForgeDevValidationTests(unittest.TestCase):
    def setUp(self):
        import argparse
        import importlib
        self.argparse = argparse
        self.fd = importlib.import_module("forge_dev")

    def test_slot_alphabet_and_length(self):
        self.assertEqual(self.fd.slot_arg("s9-sec_1.x"), "s9-sec_1.x")
        for bad in ("", "a b", "a;rm -rf", "a/b", "x" * 41, "a\n", "$(id)", ".."):
            with self.assertRaises(self.argparse.ArgumentTypeError, msg=repr(bad)):
                self.fd.slot_arg(bad)

    def test_pull_path_rejects_absolute_and_parent_components(self):
        self.assertEqual(self.fd.safe_pull_path("artifacts/forge"), "artifacts/forge")
        for bad in ("/etc/passwd", "../x", "a/../../b", "C:\\x", "C:/x", "a\\..\\b", ""):
            with self.assertRaises(SystemExit, msg=repr(bad)):
                self.fd.safe_pull_path(bad)

    def test_cloud_sync_down_extracts_with_the_data_filter(self):
        src = (Path(__file__).resolve().parents[1] / "infra" / "nebius" / "forge_cloud.py").read_text(encoding="utf-8")
        self.assertIn('filter="data"', src)
        self.assertNotIn('"tar", "xzf"', src)


class DeepNestingTests(unittest.TestCase):
    def test_canonical_json_refuses_absurd_nesting_with_value_error(self):
        deep = cur = []
        for _ in range(100_000):
            nxt = []
            cur.append(nxt)
            cur = nxt
        with self.assertRaises(ValueError):
            canonical_json(deep)

    def test_api_answers_422_for_a_deeply_nested_drawing(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(forge_dir=Path(tmp) / "forge", dist_dir=Path(tmp) / "nodist")
            c = TestClient(app, raise_server_exceptions=False)
            deep = "[" * 50_000 + "]" * 50_000
            raw = '{"name":"x","mode":"guided","body":{},"drawing":{"strokes":' + deep + "}}"
            r = c.post("/api/forge/creatures", content=raw, headers={"content-type": "application/json"})
            self.assertIn(r.status_code, (400, 422), r.text[:200])  # a client error, never a 500 or a hang


class VersionEndpointTests(unittest.TestCase):
    def test_version_does_not_leak_the_repo_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(forge_dir=Path(tmp) / "forge", dist_dir=Path(tmp) / "nodist")
            v = TestClient(app).get("/api/version").json()
            self.assertNotIn("repo_root", v)
            self.assertIn("api_routes", v)


if __name__ == "__main__":
    unittest.main()
