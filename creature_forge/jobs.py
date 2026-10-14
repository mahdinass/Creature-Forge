"""Background job manager with persisted progress events (Forge Loop contracts section 8).

One worker thread runs jobs one at a time, FIFO. The thread is created lazily on the first `submit`; nothing is
started or created on disk at import or construction. Every job has `<root>/jobs/<job_id>.json` (status, progress,
result reference, error) and an append-only `<job_id>.events.jsonl` (`{i, t, type, data}`, `i` counting from 1, `t`
seconds since the job was created). A job found `running` or `queued` at start-up belongs to a dead process and is
marked `failed` ("server restarted"); it is never resumed.
"""
from __future__ import annotations

import copy
import json
import logging
import math
import os
import queue
import re
import secrets
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .creatures import atomic_write_json, now_iso

log = logging.getLogger(__name__)

KINDS = ("challenge", "investigation", "loop")
STATUSES = ("queued", "running", "done", "failed", "cancelled")
TERMINAL = ("done", "failed", "cancelled")
EVENT_TYPES = ("phase", "progress", "model_request", "model_response", "validation", "arm_result", "verdict",
               "error", "note")
JOB_ID_RE = re.compile(r"^j-[0-9a-f]{8}$")
RESTART_ERROR = "server restarted"
_TRACE_TAIL = 2000


class JobCancelled(Exception):
    """Raised inside a job function (by `ctx.check()` / `ctx.progress`) once cancellation was requested."""


def jsonable(obj: Any) -> Any:
    """JSON-safe copy: numpy scalars/arrays become Python values, non-finite floats become None."""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in obj]
    if hasattr(obj, "tolist"):  # numpy
        return jsonable(obj.tolist())
    if hasattr(obj, "item"):
        return jsonable(obj.item())
    return str(obj)


@dataclass
class JobContext:
    """What a job function receives: `emit`, `progress`, `cancelled`, `check` and a lazily created `pool`."""
    job_id: str
    _emit: Callable
    _progress: Callable
    _cancelled: Callable
    _pool_factory: Callable | None = None

    def emit(self, type: str, data: dict | None = None) -> None:
        self._emit(type, data or {})

    def progress(self, done: int, total: int, phase: str | None = None) -> None:
        """Record progress, then raise JobCancelled if the job was cancelled (so long loops stop promptly)."""
        self._progress(done, total, phase)
        self.check()

    def cancelled(self) -> bool:
        return self._cancelled()

    def check(self) -> None:
        if self._cancelled():
            raise JobCancelled()

    @property
    def pool(self):
        return self._pool_factory() if self._pool_factory else None


class JobManager:
    def __init__(self, root: Path, pool_factory: Callable | None = None):
        self.root = Path(root)
        self.dir = self.root / "jobs"
        self._pool_factory = pool_factory
        self._lock = threading.RLock()
        self._live: dict[str, dict] = {}  # jobs of this process, authoritative while they exist
        self._cancel: dict[str, threading.Event] = {}
        self._seq: dict[str, int] = {}
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._closed = False
        self._mark_stale_failed()

    # ---- paths and persistence
    def _job_path(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not JOB_ID_RE.match(job_id):
            raise KeyError(job_id)
        return self.dir / f"{job_id}.json"

    def _events_path(self, job_id: str) -> Path:
        return self.dir / f"{job_id}.events.jsonl"

    def _save(self, job: dict) -> None:
        atomic_write_json(self._job_path(job["id"]), job)

    def _read_job(self, job_id: str) -> dict:
        try:
            return json.loads(self._job_path(job_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(job_id) from None

    def _append_event(self, job_id: str, type: str, data: dict) -> dict:
        with self._lock:
            job = self._live.get(job_id)
            i = self._seq.get(job_id, 0) + 1
            self._seq[job_id] = i
            created = job["_created_ts"] if job else time.time()
            ev = {"i": i, "t": round(max(0.0, time.time() - created), 3), "type": type, "data": jsonable(data)}
            self.dir.mkdir(parents=True, exist_ok=True)
            path = self._events_path(job_id)
            torn = False
            if path.is_file() and path.stat().st_size:
                with open(path, "rb") as fh:
                    fh.seek(-1, os.SEEK_END)
                    torn = fh.read(1) != b"\n"  # a crash left a partial line: start a fresh one
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(("\n" if torn else "") + json.dumps(ev, allow_nan=False) + "\n")
            return ev

    def _public(self, job: dict) -> dict:
        return {k: copy.deepcopy(v) for k, v in job.items() if not k.startswith("_")}

    def _mark_stale_failed(self) -> None:
        if not self.dir.is_dir():
            return
        for p in sorted(self.dir.glob("j-*.json")):
            try:
                job = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if job.get("status") not in ("queued", "running"):
                continue
            job.update(status="failed", finished=now_iso(), error=RESTART_ERROR)
            self._seq[job["id"]] = max([e.get("i", 0) for e in self._read_events(job["id"], 0)], default=0)
            self._save(job)
            self._append_event(job["id"], "error", {"message": RESTART_ERROR})

    # ---- public API
    def submit(self, kind: str, fn: Callable, **kw) -> str:
        """Queue `fn(ctx, **kw)`; returns the job id. `fn`'s return value (JSON-safe) becomes `result_ref`."""
        if kind not in KINDS:
            raise ValueError(f"job kind must be one of {list(KINDS)}, got {kind!r}")
        with self._lock:
            if self._closed:
                raise RuntimeError("job manager is closed")
            while True:
                job_id = "j-" + secrets.token_hex(4)
                if job_id not in self._live and not self._job_path(job_id).exists():
                    break
            job = {"id": job_id, "kind": kind, "status": "queued", "created": now_iso(), "started": None,
                   "finished": None, "progress": {"phase": None, "done": 0, "total": 0}, "result_ref": None,
                   "error": None, "_created_ts": time.time()}
            self._live[job_id] = job
            self._cancel[job_id] = threading.Event()
            self._seq[job_id] = 0
            self._save(self._persisted(job))
            if self._thread is None:
                self._thread = threading.Thread(target=self._worker, name="forge-jobs", daemon=True)
                self._thread.start()
            self._queue.put((job_id, fn, kw))
        return job_id

    @staticmethod
    def _persisted(job: dict) -> dict:
        return {k: v for k, v in job.items() if not k.startswith("_")}

    def get(self, job_id: str) -> dict:
        with self._lock:
            live = self._live.get(job_id)
            if live is not None:
                return self._public(live)
        return self._read_job(job_id)

    def events(self, job_id: str, since: int = 0) -> list[dict]:
        """Events with `i > since` (since=0 returns everything). KeyError for an unknown job."""
        self.get(job_id)
        return self._read_events(job_id, since)

    def _read_events(self, job_id: str, since: int) -> list[dict]:
        path = self._events_path(job_id)
        if not path.is_file():
            return []
        out = []
        with self._lock, open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue  # a torn trailing line is ignored, never invented
                if isinstance(ev, dict) and ev.get("i", 0) > since:
                    out.append(ev)
        return out

    def list(self) -> list[dict]:
        out: dict[str, dict] = {}
        if self.dir.is_dir():
            for p in self.dir.glob("j-*.json"):
                try:
                    j = json.loads(p.read_text(encoding="utf-8"))
                    out[j["id"]] = j
                except (OSError, ValueError, KeyError):
                    continue
        with self._lock:
            for jid, j in self._live.items():
                out[jid] = self._public(j)
        return sorted(out.values(), key=lambda j: (j["created"], j["id"]), reverse=True)

    def cancel(self, job_id: str) -> dict:
        """Cancel a queued job at once, or flag a running one (checked by the job via `ctx.check()`)."""
        with self._lock:
            job = self._live.get(job_id)
            if job is None:
                return self._read_job(job_id)  # not ours (finished earlier): unchanged
            if job["status"] == "queued":
                self._finish(job, "cancelled")
                self._append_event(job_id, "note", {"message": "cancelled before it started"})
            elif job["status"] == "running":
                self._cancel[job_id].set()
                self._append_event(job_id, "note", {"message": "cancel requested"})
            return self._public(job)

    def close(self, timeout: float = 5.0) -> None:
        """Stop the worker after the current job; queued jobs are cancelled. Safe to call repeatedly."""
        with self._lock:
            self._closed = True
            thread = self._thread
            for job in self._live.values():
                if job["status"] == "queued":
                    self._finish(job, "cancelled")
                elif job["status"] == "running":
                    self._cancel[job["id"]].set()
        self._queue.put(None)
        if thread is not None:
            thread.join(timeout)

    # ---- worker
    def _finish(self, job: dict, status: str, error: str | None = None, result_ref: Any = None) -> None:
        job.update(status=status, finished=now_iso(), error=error)
        if result_ref is not None:
            job["result_ref"] = result_ref
        self._save(self._persisted(job))

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            job_id, fn, kw = item
            with self._lock:
                job = self._live[job_id]
                if job["status"] != "queued":  # cancelled while waiting
                    continue
                job.update(status="running", started=now_iso())
                self._save(self._persisted(job))
            self._run_one(job, fn, kw)

    def _run_one(self, job: dict, fn: Callable, kw: dict) -> None:
        job_id = job["id"]
        flag = self._cancel[job_id]

        def emit(type: str, data: dict) -> None:
            if type not in EVENT_TYPES:
                raise ValueError(f"unknown event type {type!r}; use one of {list(EVENT_TYPES)}")
            self._append_event(job_id, type, data)

        def progress(done: int, total: int, phase: str | None) -> None:
            with self._lock:
                job["progress"] = {"phase": phase if phase is not None else job["progress"].get("phase"),
                                   "done": int(done), "total": int(total)}
                self._save(self._persisted(job))
                self._append_event(job_id, "progress", dict(job["progress"]))

        ctx = JobContext(job_id, emit, progress, flag.is_set, self._pool_factory)
        try:
            result_ref = jsonable(fn(ctx, **kw))
        except JobCancelled:
            with self._lock:
                self._append_event(job_id, "note", {"message": "cancelled"})
                self._finish(job, "cancelled")
        except Exception as exc:  # a failing job must never kill the worker thread
            tb = traceback.format_exc()
            msg = f"{type(exc).__name__}: {exc}"
            log.warning("job %s failed: %s", job_id, msg)
            with self._lock:
                self._append_event(job_id, "error", {"message": msg, "traceback_tail": tb[-_TRACE_TAIL:]})
                self._finish(job, "failed", error=msg)
        else:
            with self._lock:
                self._finish(job, "done", result_ref=result_ref)
