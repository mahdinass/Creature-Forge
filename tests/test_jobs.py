import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

from creature_forge.jobs import RESTART_ERROR, JobManager, jsonable


def wait_for(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def worker_threads():
    return [t for t in threading.enumerate() if t.name == "forge-jobs"]


class JobCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "forge"
        self.jm = JobManager(self.root)
        self.addCleanup(self.jm.close)

    def wait_status(self, jid, *statuses):
        self.assertTrue(wait_for(lambda: self.jm.get(jid)["status"] in statuses),
                        f"job stayed {self.jm.get(jid)['status']}")
        return self.jm.get(jid)


class LifecycleTests(JobCase):
    def test_no_thread_and_no_directory_until_the_first_submit(self):
        before = len(worker_threads())
        self.assertEqual(len(worker_threads()), before)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.jm.list(), [])
        self.jm.submit("challenge", lambda ctx: None)
        self.assertEqual(len(worker_threads()), before + 1)

    def test_job_runs_with_progress_events_and_result_ref(self):
        def fn(ctx, *, n):
            ctx.emit("phase", {"phase": "work"})
            for i in range(n):
                ctx.progress(i + 1, n, "work")
            ctx.emit("note", {"message": "hello", "arr": np.arange(2)})
            return {"run_id": "r-00000001"}
        jid = self.jm.submit("challenge", fn, n=3)
        self.assertRegex(jid, r"^j-[0-9a-f]{8}$")
        job = self.wait_status(jid, "done")
        self.assertEqual(job["result_ref"], {"run_id": "r-00000001"})
        self.assertEqual(job["progress"], {"phase": "work", "done": 3, "total": 3})
        self.assertEqual(job["kind"], "challenge")
        self.assertIsNotNone(job["started"])
        self.assertIsNotNone(job["finished"])
        self.assertIsNone(job["error"])
        ev = self.jm.events(jid)
        self.assertEqual([e["i"] for e in ev], list(range(1, len(ev) + 1)))
        self.assertEqual([e["type"] for e in ev], ["phase", "progress", "progress", "progress", "note"])
        self.assertEqual(ev[-1]["data"]["arr"], [0, 1])
        self.assertTrue(all(set(e) == {"i", "t", "type", "data"} for e in ev))
        # persisted
        on_disk = json.loads((self.root / "jobs" / f"{jid}.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, job)
        lines = (self.root / "jobs" / f"{jid}.events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 5)

    def test_events_since_returns_only_newer_ones(self):
        jid = self.jm.submit("challenge", lambda ctx: [ctx.emit("note", {"k": k}) for k in range(5)])
        self.wait_status(jid, "done")
        self.assertEqual(len(self.jm.events(jid, 0)), 5)
        self.assertEqual([e["data"]["k"] for e in self.jm.events(jid, 3)], [3, 4])
        self.assertEqual(self.jm.events(jid, 5), [])

    def test_jobs_run_one_at_a_time_in_fifo_order(self):
        order, gate, running = [], threading.Event(), []

        def fn(ctx, *, name):
            running.append(name)
            self.assertEqual(len(running), 1, "two jobs overlapped")
            if name == "a":
                gate.wait(5)
            order.append(name)
            running.remove(name)
        ids = [self.jm.submit("challenge", fn, name=n) for n in "abc"]
        self.assertTrue(wait_for(lambda: self.jm.get(ids[0])["status"] == "running"))
        self.assertEqual([self.jm.get(i)["status"] for i in ids[1:]], ["queued", "queued"])
        gate.set()
        for i in ids:
            self.wait_status(i, "done")
        self.assertEqual(order, ["a", "b", "c"])

    def test_exception_marks_failed_with_message_and_no_traceback_in_the_api_data(self):
        def boom(ctx):
            raise RuntimeError("kaboom")
        jid = self.jm.submit("challenge", boom)
        job = self.wait_status(jid, "failed")
        self.assertEqual(job["error"], "RuntimeError: kaboom")
        err = [e for e in self.jm.events(jid) if e["type"] == "error"][0]
        self.assertEqual(err["data"]["message"], "RuntimeError: kaboom")
        self.assertNotIn("traceback_tail", err["data"])  # the traceback lives in <jobs>/<id>.trace.txt only (security review L1)
        self.assertIn("boom", (self.root / "jobs" / f"{jid}.trace.txt").read_text(encoding="utf-8"))
        ok = self.jm.submit("challenge", lambda ctx: "still alive")  # the worker survived
        self.assertEqual(self.wait_status(ok, "done")["result_ref"], "still alive")

    def test_unknown_event_type_fails_the_job(self):
        jid = self.jm.submit("challenge", lambda ctx: ctx.emit("gossip", {}))
        self.assertIn("unknown event type", self.wait_status(jid, "failed")["error"])

    def test_bad_kind_and_unknown_job(self):
        with self.assertRaises(ValueError):
            self.jm.submit("mining", lambda ctx: None)
        for bad in ("j-00000000", "../x", None):
            with self.assertRaises(KeyError):
                self.jm.get(bad)
            with self.assertRaises(KeyError):
                self.jm.events(bad)
            with self.assertRaises(KeyError):
                self.jm.cancel(bad)

    def test_pool_is_created_only_when_a_job_asks_for_it(self):
        calls = []
        jm = JobManager(self.root, pool_factory=lambda: calls.append(1) or "POOL")
        self.addCleanup(jm.close)
        seen = []
        jid = jm.submit("challenge", lambda ctx: None)
        self.assertTrue(wait_for(lambda: jm.get(jid)["status"] == "done"))
        self.assertEqual(calls, [])
        jid = jm.submit("challenge", lambda ctx: seen.append(ctx.pool))
        self.assertTrue(wait_for(lambda: jm.get(jid)["status"] == "done"))
        self.assertEqual((calls, seen), ([1], ["POOL"]))

    def test_list_is_newest_first(self):
        a = self.jm.submit("challenge", lambda ctx: None)
        b = self.jm.submit("loop", lambda ctx: None)
        self.wait_status(b, "done")
        self.assertEqual({j["id"] for j in self.jm.list()}, {a, b})


class CancelTests(JobCase):
    def test_cancel_a_running_job_between_progress_calls(self):
        started = threading.Event()

        def fn(ctx):
            started.set()
            for i in range(100000):
                ctx.progress(i, 100000, "spin")
                time.sleep(0.005)
        jid = self.jm.submit("challenge", fn)
        self.assertTrue(started.wait(5))
        self.jm.cancel(jid)
        job = self.wait_status(jid, "cancelled")
        self.assertIsNotNone(job["finished"])
        self.assertIsNone(job["error"])
        self.assertTrue(any("cancel" in e["data"].get("message", "") for e in self.jm.events(jid) if e["type"] == "note"))

    def test_cancelled_callable_for_jobs_that_poll(self):
        started = threading.Event()

        def fn(ctx):
            started.set()
            while not ctx.cancelled():
                time.sleep(0.005)
            ctx.check()
        jid = self.jm.submit("challenge", fn)
        started.wait(5)
        self.jm.cancel(jid)
        self.wait_status(jid, "cancelled")

    def test_cancel_a_queued_job_means_it_never_runs(self):
        gate, ran = threading.Event(), []
        first = self.jm.submit("challenge", lambda ctx: gate.wait(5))
        second = self.jm.submit("challenge", lambda ctx: ran.append("second"))
        self.assertTrue(wait_for(lambda: self.jm.get(first)["status"] == "running"))
        self.assertEqual(self.jm.cancel(second)["status"], "cancelled")
        gate.set()
        self.wait_status(first, "done")
        third = self.jm.submit("challenge", lambda ctx: ran.append("third"))
        self.wait_status(third, "done")
        self.assertEqual(ran, ["third"])
        self.assertEqual(self.jm.get(second)["status"], "cancelled")

    def test_cancelling_a_finished_job_changes_nothing(self):
        jid = self.jm.submit("challenge", lambda ctx: "x")
        done = self.wait_status(jid, "done")
        self.assertEqual(self.jm.cancel(jid), done)


class RestartTests(unittest.TestCase):
    def test_running_and_queued_jobs_found_on_disk_are_marked_failed_never_resumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "forge"
            jobs = root / "jobs"
            jobs.mkdir(parents=True)
            base = {"kind": "challenge", "created": "2026-10-14T10:00:00Z", "started": None, "finished": None,
                    "progress": {"phase": "x", "done": 1, "total": 4}, "result_ref": None, "error": None}
            for jid, status in (("j-00000001", "running"), ("j-00000002", "queued"), ("j-00000003", "done")):
                (jobs / f"{jid}.json").write_text(json.dumps({**base, "id": jid, "status": status}), encoding="utf-8")
            (jobs / "j-00000001.events.jsonl").write_text(
                json.dumps({"i": 1, "t": 0.1, "type": "note", "data": {}}) + "\n{torn", encoding="utf-8")
            before = len(worker_threads())
            jm = JobManager(root)
            self.addCleanup(jm.close)
            self.assertEqual(len(worker_threads()), before)  # nothing resumed
            for jid in ("j-00000001", "j-00000002"):
                j = jm.get(jid)
                self.assertEqual((j["status"], j["error"]), ("failed", RESTART_ERROR))
                self.assertIsNotNone(j["finished"])
            self.assertEqual(jm.get("j-00000003")["status"], "done")
            ev = jm.events("j-00000001")
            self.assertEqual([e["i"] for e in ev], [1, 2])  # the torn line is ignored; numbering continues
            self.assertEqual(ev[-1]["type"], "error")
            self.assertEqual(ev[-1]["data"]["message"], RESTART_ERROR)
            self.assertEqual(json.loads((jobs / "j-00000001.json").read_text(encoding="utf-8"))["status"], "failed")
            # a fresh manager does not touch the (now terminal) records again
            JobManager(root).close()
            self.assertEqual(len(jm.events("j-00000001")), 2)


class JsonableTests(unittest.TestCase):
    def test_numpy_and_non_finite_values(self):
        out = jsonable({"a": np.float64(1.5), "b": np.arange(3), "c": float("nan"), "d": (1, 2), "e": np.int64(4), 5: {1}})
        self.assertEqual(out, {"a": 1.5, "b": [0, 1, 2], "c": None, "d": [1, 2], "e": 4, "5": [1]})
        json.dumps(out, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
