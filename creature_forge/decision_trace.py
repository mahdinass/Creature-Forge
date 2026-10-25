"""DI-1 observation-only hooks. No extra physics, optimizer or policy calls.

The hash-chained journal is exclusive-created and fsynced BEFORE delegating.
Hidden plant parameters never enter the journal. Job order/results are preserved.
Use in a single investigation process (the simulator pool may have workers).
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import math
import os
from pathlib import Path


def plain(x):
    if x is None or isinstance(x, (str, bool, int)):
        return x
    if isinstance(x, float):
        return x if math.isfinite(x) else {"nonfinite": str(x)}
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items() if k not in ("_plant", "plant")}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if hasattr(x, "pid"):
        return {"pid": x.pid, "deviation": plain(x.deviation), "logw": plain(x.logw), "seen": plain(x.seen)}
    if hasattr(x, "tolist"):
        return plain(x.tolist())
    if callable(x):
        return {"callable": getattr(x, "__qualname__", type(x).__name__)}
    raise TypeError(f"unsupported trace type: {type(x)}")


def canonical(x):
    return (json.dumps(plain(x), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


class Journal:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.file = open(path, "xb")
        self.seq, self.previous, self.stack = 0, "0" * 64, []

    def emit(self, kind, **data):
        rec = {"seq": self.seq, "previous": self.previous, "kind": kind, "scope": list(self.stack), **plain(data)}
        digest = hashlib.sha256(canonical(rec)).hexdigest()
        self.file.write(canonical({**rec, "sha256": digest}))
        self.file.flush()
        os.fsync(self.file.fileno())
        self.seq += 1
        self.previous = digest
        return rec["seq"]

    def close(self):
        self.file.close()


class TracePool:
    def __init__(self, pool, journal):
        self.pool, self.journal = pool, journal

    def imap(self, fn, jobs):
        jobs = list(jobs)
        batch = self.journal.emit("jobs_before", function=fn.__qualname__, jobs=jobs)
        for i, result in self.pool.imap(fn, jobs):
            self.journal.emit("job_after", batch=batch, index=i, result=result)
            yield i, result

    def map(self, fn, jobs):
        jobs = list(jobs)
        out = [None] * len(jobs)
        for i, result in self.imap(fn, jobs):
            out[i] = result
        return out


def snapshot(ep):
    return {"posterior": [(p.as_dict(), w) for p, w in ep.posterior()],
            "experiments": ep.experiments, "plant_remaining": ep.b.remaining,
            "twin_remaining": ep.b.twin.remaining, "selected": ep.b.best_design()}


@contextlib.contextmanager
def instrument(ep, journal):
    """Install reversible instance hooks; original methods called exactly once."""
    from . import fault_bench
    restored = []
    pool = ep.b.pool
    ep.b.pool = TracePool(pool, journal)

    def hook(obj, name, state=False):
        original = getattr(obj, name)
        @functools.wraps(original)
        def wrapped(*args, **kwargs):
            op = journal.emit("call_before", method=name, args=args, kwargs=kwargs,
                              state=snapshot(ep) if state else None)
            journal.stack.append(op)
            try:
                result = original(*args, **kwargs)
                journal.emit("call_after", method=name, call=op, result=result,
                             state=snapshot(ep) if state else None)
                return result
            except BaseException as exc:
                journal.emit("call_error", method=name, call=op, error=f"{type(exc).__name__}: {exc}")
                raise
            finally:
                journal.stack.pop()
        setattr(obj, name, wrapped)
        restored.append((obj, name, original))

    for name in ("candidate_experiments", "_predict", "rank_experiments", "experiment_step", "screen_tools",
                 "screen_tools_cma", "robust_repair", "diagnosis_done", "_repair_hyps"):
        hook(ep, name, name not in ("_predict", "diagnosis_done"))
    for name in ("observe", "counterfactual", "floor_test", "weigh_test", "robustness_check", "repair",
                 "twin_walk", "twin_observe", "twin_weigh", "twin_cma", "select", "add_twin_design", "stress_test"):
        hook(ep.b, name, name in ("observe", "counterfactual", "floor_test", "weigh_test", "repair", "robustness_check"))
    original_apply = fault_bench.apply_changes
    def apply_changes(*args, **kwargs):
        op = journal.emit("candidate_before", args=args, kwargs=kwargs)
        try:
            result = original_apply(*args, **kwargs)
        except Exception as exc:
            journal.emit("candidate_rejected", call=op, reason=f"{type(exc).__name__}: {exc}")
            raise
        journal.emit("candidate_legal", call=op, body=result[0], vector=result[1])
        return result
    fault_bench.apply_changes = apply_changes
    try:
        journal.emit("instrumentation_start", state=snapshot(ep), seeds=ep.b.view_seeds,
                     variation=ep.b.variation, plant_budget=ep.b.budget.total, twin_budget=ep.b.twin.total)
        yield
    finally:
        fault_bench.apply_changes = original_apply
        for obj, name, original in reversed(restored):
            setattr(obj, name, original)
        ep.b.pool = pool


def verify_journal(path):
    previous, count, batches, calls = "0" * 64, 0, {}, set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            digest = r.pop("sha256")
            if r["seq"] != count or r["previous"] != previous or hashlib.sha256(canonical(r)).hexdigest() != digest:
                raise ValueError("journal sequence/hash chain invalid")
            if r["kind"] == "jobs_before":
                batches[count] = len(r["jobs"])
            if r["kind"] == "job_after" and (r["batch"] not in batches or not 0 <= r["index"] < batches[r["batch"]]):
                raise ValueError("outcome precedes candidate/seeds")
            if r["kind"] == "call_before":
                calls.add(count)
            if r["kind"] in ("call_after", "call_error") and r["call"] not in calls:
                raise ValueError("return precedes call")
            previous, count = digest, count + 1
    return {"records": count, "last_sha256": previous, "batches": len(batches)}
