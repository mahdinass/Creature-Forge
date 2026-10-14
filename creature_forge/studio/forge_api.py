"""`/api/forge/*` router: creatures, challenge runs, jobs, replay, status (Forge Loop contracts sections 4, 8, 9).

`create_forge_router(forge_dir, ...)` returns an `APIRouter` and does nothing else: the creature store, the job
manager (and its worker thread) and every directory are created lazily on first use. The challenge runner and the
replay builder are injectable; the defaults import `creature_forge.challenges` inside the function that needs it.
Investigation endpoints are stubs (503) until the orchestration module lands.
"""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import threading
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..creatures import CreatureStore, atomic_write_json, now_iso, seed_block
from ..jobs import JobContext, JobManager, jsonable
from ..sandbox import SandboxBody

API_VERSION = "forge-v1"
RUN_ID_RE = re.compile(r"^r-[0-9a-f]{8}$")
REPLAY_CACHE_SIZE = 16
DEFAULT_SEED_COUNT = 8
MAX_SEED_COUNT = 64
NOT_YET = "investigations not yet available"

# Contract defaults (section 3); used when `creature_forge.challenges` is not injected/importable.
_KIND_DEFAULTS = {
    "stand": {"duration": 8.0, "perturb": 0.02, "start": "drawn"},
    "push": {"duration": 5.0, "perturb": 0.02, "start": "drawn"},
    "walk": {"duration": 10.0, "perturb": 0.03, "start": "neutral"},
}
_COMMON_DEFAULTS = {"target_force": 25.0, "push_time": 1.0, "push_duration": 0.15, "max_force": 80.0, "settle_s": 0.3}
_OVERRIDE_RANGES = {  # key -> (lo, hi)
    "duration": (0.5, 30.0), "perturb": (0.0, 0.2), "target_force": (0.0, 200.0), "push_time": (0.0, 20.0),
    "push_duration": (0.01, 1.0), "max_force": (1.0, 500.0), "settle_s": (0.0, 2.0),
}


# ---- request models
class CreateCreatureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    body: dict
    mode: Literal["guided", "experimental"]
    drawing: dict = Field(default_factory=dict)


class CurrentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int = Field(ge=1)


class ChallengeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["stand", "push", "walk"]
    seeds: int | None = Field(default=None, ge=1, le=MAX_SEED_COUNT)  # a count; the seeds come from the namespace
    overrides: dict | None = None


class AcceptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    investigation_id: str
    arm_id: str


# ---- helpers
def _sandbox_body(d: dict) -> SandboxBody:
    return SandboxBody(**{**d, "pose": tuple(d.get("pose", (0.0,) * 7))})


def _default_challenge_runner(pool_factory: Callable | None) -> Callable:
    def run(body: dict, controllers: dict, spec_dict: dict, progress) -> dict:
        import dataclasses

        from .. import challenges  # lazy: owned by another module, imported only when a run really executes
        pool = pool_factory() if pool_factory else None
        res = challenges.run_challenge(_sandbox_body(body), controllers, challenges.ChallengeSpec.from_dict(spec_dict),
                                       pool=pool, progress=progress)
        return dataclasses.asdict(res) if dataclasses.is_dataclass(res) else res
    return run


def _default_replay_builder(body: dict, controllers: dict, spec: dict, seed: int, *, force=None, direction=1) -> dict:
    from .. import challenges  # lazy
    return challenges.replay_payload(_sandbox_body(body), controllers, challenges.ChallengeSpec.from_dict(spec), seed,
                                     force=force, direction=direction)


def build_spec_dict(kind: str, seeds: tuple[int, ...], overrides: dict | None, *, use_challenges: bool) -> dict:
    """Spec dict for a challenge. Raises ValueError (-> 422) naming the offending override."""
    spec = None
    if use_challenges:
        try:
            from .. import challenges
            spec = challenges.default_spec(kind, list(seeds)).to_dict()
        except ImportError:
            spec = None
    if spec is None:
        spec = {"kind": kind, "seeds": list(seeds), **_COMMON_DEFAULTS, **_KIND_DEFAULTS[kind]}
    for key, val in (overrides or {}).items():
        if key not in _OVERRIDE_RANGES and key != "start":
            raise ValueError(f"unknown override {key!r}; allowed: {sorted([*_OVERRIDE_RANGES, 'start'])}")
        if key == "start":
            if val not in ("drawn", "neutral"):
                raise ValueError("override start must be 'drawn' or 'neutral'")
        else:
            lo, hi = _OVERRIDE_RANGES[key]
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or not lo <= val <= hi:
                raise ValueError(f"override {key}={val!r} must be a number in [{lo:g}, {hi:g}]")
            val = float(val)
        spec[key] = val
    if use_challenges:
        try:
            from .. import challenges
            challenges.ChallengeSpec.from_dict(spec)  # the real validator has the last word
        except ImportError:
            pass
    return spec


def _challenge_job(ctx: JobContext, *, runner: Callable, runs_dir: Path, run_id: str, creature: dict,
                   body: dict, controllers: dict, spec: dict) -> dict:
    ctx.emit("phase", {"phase": "challenge", "kind": spec["kind"], "seeds": len(spec["seeds"])})

    def progress(done=0, total=0, *_ignored) -> None:
        ctx.progress(done, total, "challenge")  # raises JobCancelled once cancelled

    result = runner(body, controllers, spec, progress)
    ctx.check()
    if not isinstance(result, dict):
        raise TypeError(f"challenge runner returned {type(result).__name__}, expected a dict")
    record = jsonable({**result, "run_id": run_id, "creature": creature, "created": now_iso(), "controllers": controllers})
    record.setdefault("spec", spec)
    record.setdefault("body", body)
    atomic_write_json(runs_dir / f"{run_id}.json", record)
    return {"run_id": run_id}


def create_forge_router(forge_dir: Path, *, challenge_runner: Callable | None = None,
                        replay_builder: Callable | None = None, pool_factory: Callable | None = None) -> APIRouter:
    forge_dir = Path(forge_dir)
    runs_dir = forge_dir / "runs"
    use_real_challenges = challenge_runner is None
    runner = challenge_runner or _default_challenge_runner(pool_factory)
    replayer = replay_builder or _default_replay_builder
    router = APIRouter(prefix="/api/forge", tags=["forge"])

    lock = threading.RLock()
    services: dict = {}
    replay_cache: OrderedDict = OrderedDict()

    def store() -> CreatureStore:
        with lock:
            if "store" not in services:
                services["store"] = CreatureStore(forge_dir)
            return services["store"]

    def jobs() -> JobManager:
        with lock:
            if "jobs" not in services:
                services["jobs"] = JobManager(forge_dir, pool_factory)
            return services["jobs"]

    def close() -> None:
        with lock:
            mgr = services.get("jobs")
        if mgr is not None:
            mgr.close()

    router.forge = SimpleNamespace(store=store, jobs=jobs, close=close, forge_dir=forge_dir)  # for the orchestrator

    def next_run_counter(cid: str, n: int) -> int:
        """Per-(creature, version) run counter, persisted so seed blocks never repeat across restarts."""
        path = runs_dir / "_counters.json"
        with lock:
            try:
                counters = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                counters = {}
            key = f"{cid}:{n}"
            k = int(counters.get(key, 0))
            counters[key] = k + 1
            atomic_write_json(path, counters)
            return k

    # ---- status
    @router.get("/status")
    def status():
        try:
            workers = int(os.environ.get("CF_WORKERS") or 6)
        except ValueError:
            workers = 6
        live = os.environ.get("CREATURE_FORGE_ENABLE_LIVE") == "1" and bool(os.environ.get("NEBIUS_API_KEY"))
        return {"live_available": live, "model": None, "ledger": None, "workers": max(1, min(7, workers)),
                "version": API_VERSION}

    # ---- creatures
    @router.get("/creatures")
    def list_creatures():
        return store().list()

    @router.post("/creatures")
    def create_creature(req: CreateCreatureIn):
        try:
            return store().create(name=req.name, body=req.body, mode=req.mode, drawing=req.drawing)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/creatures/{cid}")
    def get_creature(cid: str):
        try:
            return store().get(cid)
        except KeyError:
            raise HTTPException(404, f"No such creature: {cid}") from None

    @router.post("/creatures/{cid}/current")
    def set_current(cid: str, req: CurrentIn):
        try:
            return store().set_current(cid, req.n)
        except KeyError as exc:
            raise HTTPException(404, f"No such creature or version: {cid} v{req.n}") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    # ---- challenge runs
    @router.post("/creatures/{cid}/versions/{n}/challenges")
    def start_challenge(cid: str, n: int, req: ChallengeIn):
        try:
            version = store().version(cid, n)
        except KeyError:
            raise HTTPException(404, f"No such creature or version: {cid} v{n}") from None
        count = req.seeds or DEFAULT_SEED_COUNT
        try:
            build_spec_dict(req.kind, tuple(range(count)), req.overrides, use_challenges=use_real_challenges)  # validate
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        round_ = next_run_counter(cid, n)
        seeds = seed_block(cid, n, round_, "challenge", count)
        spec = build_spec_dict(req.kind, seeds, req.overrides, use_challenges=use_real_challenges)
        run_id = "r-" + secrets.token_hex(4)
        creature = {"cid": cid, "n": n, "content_hash": version["content_hash"]}
        try:
            job_id = jobs().submit("challenge", _challenge_job, runner=runner, runs_dir=runs_dir, run_id=run_id,
                                   creature=creature, body=version["body"], controllers=version["controllers"], spec=spec)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"job_id": job_id, "run_id": run_id}

    def load_run(run_id: str) -> dict:
        if not RUN_ID_RE.match(run_id or ""):
            raise HTTPException(404, f"No such run: {run_id}")
        try:
            return json.loads((runs_dir / f"{run_id}.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HTTPException(404, f"No such run: {run_id} (it may still be running, or it failed)") from None

    @router.get("/runs/{run_id}")
    def get_run(run_id: str):
        return load_run(run_id)

    # ---- jobs
    @router.get("/jobs/{job_id}")
    def get_job(job_id: str, since: int = Query(0, ge=0)):
        mgr = jobs()
        try:
            job = mgr.get(job_id)
            return {"job": job, "events": mgr.events(job_id, since)}
        except KeyError:
            raise HTTPException(404, f"No such job: {job_id}") from None

    @router.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        try:
            return jobs().cancel(job_id)
        except KeyError:
            raise HTTPException(404, f"No such job: {job_id}") from None

    # ---- replay
    @router.get("/replay")
    def replay(run_id: str | None = None, investigation_id: str | None = None, arm: str | None = None,
               seed: int | None = None, direction: int = 1, force: float | None = None):
        if investigation_id or arm:
            raise HTTPException(503, NOT_YET)
        if not run_id:
            raise HTTPException(422, "run_id is required")
        if seed is None:
            raise HTTPException(422, "seed is required")
        if direction not in (-1, 1):
            raise HTTPException(422, "direction must be +1 or -1")
        if force is not None and not (math.isfinite(force) and 0 <= force <= 500):
            raise HTTPException(422, "force must be a number in [0, 500] N")
        run = load_run(run_id)
        spec = run.get("spec") or {}
        if seed not in (spec.get("seeds") or []):
            raise HTTPException(404, f"Run {run_id} has no seed {seed}")
        key = (run_id, seed, direction, force)
        with lock:
            if key in replay_cache:
                replay_cache.move_to_end(key)
                return replay_cache[key]
        try:
            payload = replayer(run.get("body") or store().version(run["creature"]["cid"], run["creature"]["n"])["body"],
                               run["controllers"], spec, seed, force=force, direction=direction)
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, f"replay failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - report instead of an opaque 500
            raise HTTPException(500, f"replay failed: {type(exc).__name__}: {exc}") from exc
        with lock:
            replay_cache[key] = payload
            while len(replay_cache) > REPLAY_CACHE_SIZE:
                replay_cache.popitem(last=False)
        return payload

    # ---- investigations: stubs until the orchestration milestone
    @router.post("/creatures/{cid}/versions/{n}/investigations")
    def start_investigation(cid: str, n: int):
        raise HTTPException(503, NOT_YET)

    @router.get("/investigations")
    def list_investigations(cid: str | None = None):
        return []  # nothing can exist yet; an empty list keeps list views free of errors

    @router.get("/investigations/{iid}")
    def get_investigation(iid: str):
        raise HTTPException(503, NOT_YET)

    @router.post("/creatures/{cid}/accept")
    def accept(cid: str, req: AcceptIn):
        raise HTTPException(503, NOT_YET)

    return router
