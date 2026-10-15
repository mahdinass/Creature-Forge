"""Process pool with per-job progress for the Forge Loop (contracts section 3, `forge_pool`).

`optimize.Executor.map` blocks until every job of a batch is done. The Forge needs to report progress per finished job
(a seed of a challenge, a candidate of an adaptation), so `ForgePool.imap` yields `(index, result)` pairs as soon as
each job completes. Properties:
  * lazy: no process exists until the first `imap`/`map`; importing this module never creates a pool;
  * "spawn" start method (Windows-safe, no inherited MuJoCo state); worker count from env `CF_WORKERS`
    (default 6, clamped to 1..7); with one worker jobs run inline in the calling process;
  * errors are values: a job that raises (or a worker that dies) yields `(index, ("error", message))`, never an
    exception in the consumer; the pool is rebuilt lazily after a worker death;
  * job functions must be module-level (picklable) and take one picklable argument (by convention a dict).
This module deliberately imports only the standard library, so spawned workers start quickly.
"""
from __future__ import annotations

import atexit
import os
import threading
from collections import namedtuple
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
import multiprocessing as mp
from typing import Any, Callable, Iterator

DEFAULT_WORKERS = 6
MAX_WORKERS = 7

PoolError = namedtuple("PoolError", ["tag", "message"])  # equals the plain tuple ("error", message)


def is_error(result: Any) -> bool:
    return isinstance(result, tuple) and len(result) == 2 and result[0] == "error" and isinstance(result[1], str)


def configured_workers(env: dict | None = None) -> int:
    """Worker count from `CF_WORKERS` (default 6), clamped to 1..7. Garbage falls back to the default."""
    raw = (os.environ if env is None else env).get("CF_WORKERS")
    try:
        n = int(str(raw).strip()) if raw is not None else DEFAULT_WORKERS
    except ValueError:
        n = DEFAULT_WORKERS
    return max(1, min(MAX_WORKERS, n))


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _call(fn: Callable, job: Any):
    """Runs inside a worker: exceptions become values so one bad job cannot poison the batch."""
    try:
        return fn(job)
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        return PoolError("error", _describe(exc))


class ForgePool:
    """Lazy, spawn-based process pool yielding results as they complete."""

    def __init__(self, max_workers: int | None = None):
        self.max_workers = configured_workers() if max_workers is None else max(1, min(MAX_WORKERS, int(max_workers)))
        self._executor: ProcessPoolExecutor | None = None
        self._lock = threading.Lock()
        self._closed = False

    @property
    def started(self) -> bool:
        return self._executor is not None

    def _executor_or_create(self) -> ProcessPoolExecutor:
        with self._lock:
            if self._closed:
                raise RuntimeError("ForgePool is closed")
            if self._executor is None:
                self._executor = ProcessPoolExecutor(max_workers=self.max_workers, mp_context=mp.get_context("spawn"))
            return self._executor

    def _discard(self, executor: ProcessPoolExecutor) -> None:
        with self._lock:
            if self._executor is executor:
                self._executor = None
        executor.shutdown(wait=False, cancel_futures=True)

    def imap(self, fn: Callable, jobs: list) -> Iterator[tuple[int, Any]]:
        """Yield `(index, result)` as each job completes; a failure is `(index, ("error", message))`."""
        jobs = list(jobs)
        if not jobs:
            return
        if self.max_workers == 1:
            for i, job in enumerate(jobs):
                yield i, _call(fn, job)
            return
        executor = self._executor_or_create()
        futures: dict[Future, int] = {}
        yielded: set[int] = set()
        try:
            for i, job in enumerate(jobs):
                futures[executor.submit(_call, fn, job)] = i
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    res = fut.result()
                except BrokenProcessPool as exc:
                    self._discard(executor)
                    msg = f"worker process died: {_describe(exc)}"
                    for k in range(len(jobs)):
                        if k not in yielded:
                            yielded.add(k)
                            yield k, PoolError("error", msg)
                    return
                except Exception as exc:  # noqa: BLE001 - e.g. an unpicklable result
                    res = PoolError("error", _describe(exc))
                yielded.add(i)
                yield i, res
        finally:  # consumer stopped early (cancel): drop jobs that have not started
            for fut in futures:
                fut.cancel()

    def map(self, fn: Callable, jobs: list) -> list:
        """Blocking convenience: results in job order (errors as values)."""
        out: list = [None] * len(jobs)
        for i, res in self.imap(fn, jobs):
            out[i] = res
        return out

    def close(self) -> None:
        with self._lock:
            self._closed = True
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    def __enter__(self) -> "ForgePool":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class InlinePool:
    """Same interface, runs in the calling process in job order (used when no pool is given)."""
    max_workers = 1

    def imap(self, fn: Callable, jobs: list) -> Iterator[tuple[int, Any]]:
        for i, job in enumerate(list(jobs)):
            yield i, _call(fn, job)

    def map(self, fn: Callable, jobs: list) -> list:
        return [res for _, res in self.imap(fn, jobs)]

    def close(self) -> None:
        pass


_singleton: ForgePool | None = None
_singleton_lock = threading.Lock()


def get_pool() -> ForgePool:
    """Process-wide pool; created on first call (never at import), closed at interpreter exit."""
    global _singleton
    with _singleton_lock:
        if _singleton is None or _singleton._closed:
            _singleton = ForgePool()
            atexit.register(_singleton.close)
        return _singleton
