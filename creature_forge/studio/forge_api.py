"""`/api/forge/*` router: creatures, challenge runs, jobs, replay, status (Forge Loop contracts sections 4, 8, 9).

`create_forge_router(forge_dir, ...)` returns an `APIRouter` and does nothing else: the creature store, the job
manager (and its worker thread) and every directory are created lazily on first use. The challenge runner and the
replay builder are injectable; the defaults import `creature_forge.challenges` inside the function that needs it.
Investigation endpoints (start, list, get, replay of an arm, accept) delegate to `creature_forge.investigation`; the arena, the
baselines, the model client and the ledger are injectable (`ledger`, `client_factory`, `investigation_options`).
"""
from __future__ import annotations

import json
import logging
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

from .. import investigation as inv
from .. import recoveries as rec_mod
from ..creatures import CreatureStore, StoreFull, atomic_write_json, now_iso, seed_block
from ..inference_ledger import InferenceLedger
from ..jobs import JobCancelled, JobContext, JobManager, QueueFull, jsonable, public_error
from ..sandbox import SandboxBody

log = logging.getLogger(__name__)

API_VERSION = "forge-v1"
RUN_ID_RE = re.compile(r"r-[0-9a-f]{8}")  # always used with fullmatch
MAX_CONCURRENT_REPLAYS = 2   # uncached replay simulations running at once; more are answered 429
FORCE_STEP = 0.5             # replay force is quantised to 0.5 N so the cache and the simulator cannot be flooded with distinct values
REPLAY_CACHE_SIZE = 16
DEFAULT_SEED_COUNT = 8
MAX_SEED_COUNT = 64

# Contract defaults (section 3); used when `creature_forge.challenges` is not injected/importable.
_KIND_DEFAULTS = {
    "stand": {"duration": 8.0, "perturb": 0.02, "start": "drawn"},
    "push": {"duration": 5.0, "perturb": 0.02, "start": "drawn"},
    "walk": {"duration": 10.0, "perturb": 0.03, "start": "neutral"},
}
_COMMON_DEFAULTS = {"target_force": 10.0, "push_time": 1.0, "push_duration": 0.15, "max_force": 80.0, "settle_s": 0.3}
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


class InvestigationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    mode: Literal["live", "scripted"]
    profile: Literal["default", "deep"] = "default"
    loop: bool = False
    probes: bool = False   # diagnostic-probe protocol (2 model calls + MuJoCo probes before the proposals)
    memory: bool = False   # engineering memory: lessons from other creatures' past investigations enter the evidence


class RecoveryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    director: Literal["ai", "fix"]
    mode: Literal["live", "scripted"] | None = None   # ai only; defaults to scripted
    budget: int = Field(default=rec_mod.DEFAULT_BUDGET, ge=rec_mod.MIN_BUDGET, le=rec_mod.MAX_BUDGET)


class AcceptRecoveryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recovery_id: str


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


def _investigation_job(ctx: JobContext, *, loop: bool, store, cid: str, n: int, run_id: str, iid: str, mode: str, profile: str,
                       forge_dir: Path, ledger, options: dict, model_config_path) -> dict:
    kw = dict(mode=mode, forge_dir=forge_dir, ledger=ledger, emit=ctx.emit, progress=ctx.progress, cancelled=ctx.cancelled, pool=ctx.pool,
              investigation_id=iid, profile=profile, model_config_path=model_config_path, **options)
    ctx.emit("phase", {"phase": "loop" if loop else "investigation", "mode": mode, "provenance": inv.PROVENANCE[mode]})
    if loop:
        out = inv.run_loop(store, cid, n, run_id, **kw)
        if out["stop_reason"] == "cancelled":
            raise JobCancelled()
        return {"investigation_id": iid, "loop": out, "provenance": out["provenance"]}
    rec = inv.run_investigation(store, cid, n, run_id, **kw)
    if rec["status"] == "cancelled":
        raise JobCancelled()
    if rec["status"] == "failed":
        raise RuntimeError(rec["error"] or "investigation failed")
    return {"investigation_id": iid, "status": rec["status"], "provenance": rec["provenance"]}


def create_forge_router(forge_dir: Path, *, challenge_runner: Callable | None = None,
                        replay_builder: Callable | None = None, pool_factory: Callable | None = None,
                        ledger: InferenceLedger | None = None, investigation_options: dict | None = None,
                        model_config_path: Path | str | None = None, recovery_options: dict | None = None) -> APIRouter:
    """`recovery_options`: test hooks for `recoveries.run_recovery` (pipeline_fn, assess_fn, code_fn, director_factory).
    `investigation_options`: extra keyword arguments for `run_investigation` / `run_loop` (arena_runner, baseline_fns,
    client_factory, code_fn, challenge_runner, ...). `ledger` defaults to `InferenceLedger(default_path=<forge_dir>/inference_ledger.jsonl)`."""
    forge_dir = Path(forge_dir)
    runs_dir = forge_dir / "runs"
    use_real_challenges = challenge_runner is None
    runner = challenge_runner or _default_challenge_runner(pool_factory)
    replayer = replay_builder or _default_replay_builder
    router = APIRouter(prefix="/api/forge", tags=["forge"])

    lock = threading.RLock()
    replay_slots = threading.BoundedSemaphore(MAX_CONCURRENT_REPLAYS)
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

    def get_ledger() -> InferenceLedger:
        with lock:
            if "ledger" not in services:
                services["ledger"] = ledger or InferenceLedger(default_path=forge_dir / "inference_ledger.jsonl")
            return services["ledger"]

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
        from ..investigation import api_key_present   # loads .env like the live gate does; never returns the key
        live = os.environ.get("CREATURE_FORGE_ENABLE_LIVE") == "1" and api_key_present()
        try:
            led = get_ledger().status()
        except Exception as exc:  # noqa: BLE001 - status must never fail because of the ledger
            led = {"error": public_error(exc)}
        return {"live_available": live, "model": inv.model_summary(model_config_path), "ledger": led,
                "workers": max(1, min(7, workers)), "version": API_VERSION}

    # ---- creatures
    @router.get("/creatures")
    def list_creatures():
        return store().list()

    @router.post("/creatures")
    def create_creature(req: CreateCreatureIn):
        try:
            return store().create(name=req.name, body=req.body, mode=req.mode, drawing=req.drawing)
        except StoreFull as exc:
            raise HTTPException(429, str(exc)) from exc
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
        except QueueFull as exc:
            raise HTTPException(429, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"job_id": job_id, "run_id": run_id}

    def load_run(run_id: str) -> dict:
        if not RUN_ID_RE.fullmatch(run_id or ""):
            raise HTTPException(404, f"No such run: {run_id}")
        try:
            return json.loads((runs_dir / f"{run_id}.json").read_text(encoding="utf-8"))
        except OSError:
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
    def clean_force(force, spec: dict):
        """Quantise to 0.5 N and bound to [0, spec.max_force] (a bounded set of cache keys); None stays None."""
        if force is None:
            return None
        try:
            top = float(spec.get("max_force", _COMMON_DEFAULTS["max_force"]))
        except (TypeError, ValueError):
            top = _COMMON_DEFAULTS["max_force"]
        return min(max(round(force / FORCE_STEP) * FORCE_STEP, 0.0), top)

    def run_replay(call: Callable):
        """Run an uncached replay simulation if one of the 2 slots is free, else 429."""
        if not replay_slots.acquire(blocking=False):
            raise HTTPException(429, "too many replays are running; try again in a moment")
        try:
            return call()
        finally:
            replay_slots.release()

    @router.get("/replay")
    def replay(run_id: str | None = None, investigation_id: str | None = None, arm: str | None = None,
               seed: int | None = None, direction: int = 1, force: float | None = None):
        if investigation_id or arm:
            return replay_arm(investigation_id, arm, seed, direction, force)
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
        force = clean_force(force, spec)
        key = (run_id, seed, direction, force)
        with lock:
            if key in replay_cache:
                replay_cache.move_to_end(key)
                return replay_cache[key]
        try:
            payload = run_replay(lambda: replayer(
                run.get("body") or store().version(run["creature"]["cid"], run["creature"]["n"])["body"],
                run["controllers"], spec, seed, force=force, direction=direction))
        except HTTPException:
            raise
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, f"replay failed: {public_error(exc)}") from exc
        except Exception as exc:  # noqa: BLE001 - report instead of an opaque 500
            log.exception("replay of run %s failed", run_id)
            raise HTTPException(500, f"replay failed: {public_error(exc)}") from exc
        with lock:
            replay_cache[key] = payload
            while len(replay_cache) > REPLAY_CACHE_SIZE:
                replay_cache.popitem(last=False)
        return payload

    # ---- investigations
    def load_investigation(iid: str) -> dict:
        try:
            return inv.load_investigation(forge_dir, iid)
        except KeyError:
            raise HTTPException(404, f"No such investigation: {iid}") from None

    def replay_arm(iid, arm_id, seed, direction, force):
        if not iid or not arm_id or seed is None:
            raise HTTPException(422, "investigation_id, arm and seed are all required to replay an arm")
        if direction not in (-1, 1):
            raise HTTPException(422, "direction must be +1 or -1")
        if force is not None and not (math.isfinite(force) and 0 <= force <= 500):
            raise HTTPException(422, "force must be a number in [0, 500] N")
        rec = load_investigation(iid)
        arm = next((a for a in rec.get("arms") or [] if a.get("arm_id") == arm_id), None)
        if arm is None or arm.get("unavailable"):
            raise HTTPException(404, f"Investigation {iid} has no runnable arm {arm_id}")
        allowed = {s for k in ("train", "screen", "validate") for s in (rec.get("seeds") or {}).get(k, []) if isinstance(s, int)}
        allowed |= set((rec.get("spec") or {}).get("seeds") or [])
        if seed not in allowed:
            raise HTTPException(404, f"Investigation {iid} used no seed {seed}")
        force = clean_force(force, rec.get("spec") or {})
        key = ("arm", iid, arm_id, seed, direction, force)
        with lock:
            if key in replay_cache:
                replay_cache.move_to_end(key)
                return replay_cache[key]
        try:
            cr = rec["creature"]
            parent = store().version(cr["cid"], cr["n"])
            if cr.get("hypothetical_parent"):  # the evaluated parent was a proposal: its body is stored with its challenge run
                run = load_run(rec["challenge_run_id"])
                parent = {**parent, "body": run["body"], "controllers": run["controllers"]}
            body, controllers = inv.materialize_arm(parent, arm)
            payload = run_replay(lambda: replayer(body, controllers, {**rec["spec"], "seeds": [seed]}, seed, force=force, direction=direction))
        except HTTPException:
            raise
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, f"replay failed: {public_error(exc)}") from exc
        except Exception as exc:  # noqa: BLE001
            log.exception("replay of investigation %s arm %s failed", iid, arm_id)
            raise HTTPException(500, f"replay failed: {public_error(exc)}") from exc
        with lock:
            replay_cache[key] = payload
            while len(replay_cache) > REPLAY_CACHE_SIZE:
                replay_cache.popitem(last=False)
        return payload

    @router.post("/creatures/{cid}/versions/{n}/investigations")
    def start_investigation(cid: str, n: int, req: InvestigationIn):
        try:
            version = store().version(cid, n)
        except KeyError:
            raise HTTPException(404, f"No such creature or version: {cid} v{n}") from None
        run = load_run(req.run_id)
        rc = run.get("creature") or {}
        if rc.get("cid") != cid or rc.get("n") != n or rc.get("content_hash") != version["content_hash"]:
            raise HTTPException(409, f"Run {req.run_id} is not a challenge run of {cid} v{n}")
        try:
            cfg = inv.load_model_config(req.profile, model_config_path)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(503, f"model configuration unavailable: {exc}") from exc
        if req.mode == "live":
            reason = inv.live_refusal(get_ledger(), cfg)
            if reason:
                raise HTTPException(503, reason)
        iid = inv.new_investigation_id()
        options = dict(investigation_options or {})
        if req.probes:
            options["probes"] = True
        if req.memory:
            options["memory"] = True
        if req.loop and challenge_runner is not None:
            options.setdefault("challenge_runner", challenge_runner)
        try:
            job_id = jobs().submit("loop" if req.loop else "investigation", _investigation_job, loop=req.loop, store=store(), cid=cid,
                                   n=n, run_id=req.run_id, iid=iid, mode=req.mode, profile=req.profile, forge_dir=forge_dir,
                                   ledger=get_ledger(), options=options, model_config_path=model_config_path)
        except QueueFull as exc:
            raise HTTPException(429, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"job_id": job_id, "investigation_id": iid}

    @router.get("/memory")
    def get_memory():
        from ..memory import MemoryBank
        lessons = MemoryBank.for_forge_dir(forge_dir).summaries()
        return {"bank_size": len(lessons), "lessons": lessons}

    @router.get("/investigations")
    def list_investigations(cid: str | None = None):
        return inv.list_investigations(forge_dir, cid)

    @router.get("/investigations/{iid}")
    def get_investigation(iid: str):
        return load_investigation(iid)

    @router.post("/creatures/{cid}/accept")
    def accept(cid: str, req: AcceptIn):
        try:
            store().get(cid)
        except KeyError:
            raise HTTPException(404, f"No such creature: {cid}") from None
        rec = load_investigation(req.investigation_id)
        try:
            parent_n, body, controllers, change = inv.build_accept(store(), cid, rec, req.arm_id)
            return store().accept(cid, parent_n=parent_n, body=body, controllers=controllers, change=change)
        except inv.AcceptRefused as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:  # store-level refusal
            raise HTTPException(409, str(exc)) from exc

    # ---- walking recoveries ("Recover walking")
    def load_recovery(rid: str) -> dict:
        try:
            return rec_mod.load_recovery(forge_dir, rid)
        except KeyError:
            raise HTTPException(404, f"No such recovery: {rid} (it may still be running, or it failed)") from None

    @router.post("/creatures/{cid}/versions/{n}/recoveries")
    def start_recovery(cid: str, n: int, req: RecoveryIn):
        mode = (req.mode or "scripted") if req.director == "ai" else None
        if req.director == "fix" and req.mode is not None:
            raise HTTPException(422, "mode applies to the ai director only")
        try:
            job_id, rid = rec_mod.start_recovery(jobs(), store(), forge_dir, cid, n, director=req.director, mode=mode, budget=req.budget,
                                                 ledger=get_ledger(), model_config_path=model_config_path, options=recovery_options)
        except KeyError:
            raise HTTPException(404, f"No such creature or version: {cid} v{n}") from None
        except inv.LiveRefused as exc:
            raise HTTPException(503, str(exc)) from exc
        except QueueFull as exc:
            raise HTTPException(429, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(503, public_error(exc)) from exc
        return {"job_id": job_id, "recovery_id": rid}

    @router.get("/recoveries")
    def list_recoveries(cid: str | None = None):
        return rec_mod.list_recoveries(forge_dir, cid)

    @router.get("/recoveries/{rid}")
    def get_recovery(rid: str):
        return load_recovery(rid)

    @router.get("/recoveries/{rid}/replay")
    def replay_recovery(rid: str, arm: str, seed: int):
        if arm not in ("original", "candidate"):
            raise HTTPException(422, "arm must be 'original' or 'candidate'")
        rec = load_recovery(rid)
        cr = rec["creature"]
        key = ("recovery", rid, arm, seed)
        with lock:
            if key in replay_cache:
                replay_cache.move_to_end(key)
                return replay_cache[key]
        try:
            version = store().version(cr["cid"], cr["n"])
            body, controllers, spec = rec_mod.replay_inputs(rec, version, arm, seed)
        except KeyError:
            raise HTTPException(404, f"Recovery {rid} has no replayable {arm} run on seed {seed}") from None
        except ValueError as exc:
            raise HTTPException(422, f"replay failed: {public_error(exc)}") from exc
        try:
            payload = run_replay(lambda: replayer(body, controllers, spec, seed, force=None, direction=1))
        except HTTPException:
            raise
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, f"replay failed: {public_error(exc)}") from exc
        except Exception as exc:  # noqa: BLE001
            log.exception("replay of recovery %s %s failed", rid, arm)
            raise HTTPException(500, f"replay failed: {public_error(exc)}") from exc
        with lock:
            replay_cache[key] = payload
            while len(replay_cache) > REPLAY_CACHE_SIZE:
                replay_cache.popitem(last=False)
        return payload

    @router.post("/creatures/{cid}/accept-recovery")
    def accept_recovery(cid: str, req: AcceptRecoveryIn):
        try:
            store().get(cid)
        except KeyError:
            raise HTTPException(404, f"No such creature: {cid}") from None
        rec = load_recovery(req.recovery_id)
        try:
            parent_n, body, vector, change, origin = rec_mod.build_accept(store(), cid, rec)
            return store().accept_recovery(cid, parent_n=parent_n, body=body, vector=vector, change=change, origin=origin)
        except ValueError as exc:   # RecoveryRefused is a ValueError; so are store-level refusals (not FULL_RECOVERY, already accepted, body invalid)
            raise HTTPException(409, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(409, f"the evaluated version is missing: {exc}") from exc

    return router
