"""Creature Forge Studio backend: thin FastAPI layer over the MuJoCo pipeline.

No physics here; every pose served comes from creature_forge.render_export (MuJoCo rollouts).
"""
from __future__ import annotations

import subprocess
import threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .. import demo as demo_mod
from .. import overview as overview_mod
from ..controller import CTRL_BOUNDS, GaitParams
from ..experiment import (PHASE0_BASELINE, PHASE0_CANDIDATE, PHASE0_DURATION, PHASE0_PUSH, PHASE0_SEEDS,
                          compare_designs)
from ..investigator import INVESTIGATIONS_DIR, list_trials, load_trial
from ..lab import (DEMO_DIR, LabError, build_replay, lab_view, list_lab_trials, load_lab_trial)
from ..locomotion_view import CONTROLLER_INFO, RESULTS as LOCOMOTION_DIR, cached_replay, load_summary
from ..morphology import BOUNDS, BipedParams
from ..render_export import build_run_payload
from ..simulate import Push
from ..sketch import SketchError, compile_sketch, default_sketch, normalize_sketch, support_info
from ..trial_view import trial_view

DIST = Path(__file__).resolve().parents[2] / "studio" / "dist"


class PushIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: float = Field(ge=0, le=20)
    force: float = Field(ge=-200, le=200)
    duration: float = Field(default=0.15, gt=0, le=2)


class DemoRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str = Field(pattern="^(live|mock)$")
    confirm_live: bool = False


_DEMO_LOCK = threading.Lock()
_DEMO_LIVE_CALLS = {"n": 0}


class NormalizeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: dict[str, list[float]]
    segments: list[list[str]] = []
    extras: dict[str, float] = {}


class SimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: dict[str, float] = {}
    gait: dict[str, float] = {}
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    duration: float = Field(default=5.0, ge=0.5, le=15.0)
    push: PushIn | None = None


def _params(cls, values: dict, label: str):
    unknown = set(values) - set(cls.__dataclass_fields__)
    if unknown:
        raise HTTPException(422, f"unknown {label} parameter(s): {sorted(unknown)}")
    try:
        return cls(**values).validate()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@lru_cache(maxsize=1)
def _phase0() -> dict:
    gait = GaitParams()
    runs = {name: build_run_payload(b, gait, seed=0, duration=PHASE0_DURATION, push=PHASE0_PUSH)
            for name, b in (("baseline", PHASE0_BASELINE), ("candidate", PHASE0_CANDIDATE))}
    summary = compare_designs(PHASE0_BASELINE, PHASE0_CANDIDATE, gait, seeds=PHASE0_SEEDS,
                              duration=PHASE0_DURATION, push=PHASE0_PUSH)
    runs["matched_seed_summary"] = {
        "seeds": summary["seeds"],
        **{k: {m: summary[k][m] for m in ("fall_rate", "mean_min_torso_height", "mean_max_abs_pitch")}
           for k in ("baseline", "candidate")}}
    return runs


@asynccontextmanager
async def _warm(_: FastAPI):
    _phase0()  # run the (deterministic) Phase 0 experiment once, before serving
    yield


def resolve_static(root: Path, path: str) -> Path | None:
    """Return the file under `root` that `path` names, or None. Never leaves `root` (.., absolute, symlinks)."""
    if not path:
        return None
    try:
        base = root.resolve()
        f = (base / path).resolve()
        f.relative_to(base)
    except (ValueError, OSError):
        return None
    return f if f.is_file() else None


_DEMO_REPLAYS: dict = {}


def _demo_replay_cached(run_id: str, which: str, seed: int, rec: dict) -> dict:
    """Fresh deterministic MuJoCo replay of a stored controller vector; cached per (run, which, seed, vector)."""
    key = (run_id, which, seed, hash(tuple(demo_mod.replay_vector(rec, which))))
    if key not in _DEMO_REPLAYS:
        if len(_DEMO_REPLAYS) >= 24:
            _DEMO_REPLAYS.pop(next(iter(_DEMO_REPLAYS)))
        _DEMO_REPLAYS[key] = demo_mod.build_replay(rec, which, seed)
    return _DEMO_REPLAYS[key]


def create_app(investigations_dir: Path = INVESTIGATIONS_DIR, dist_dir: Path = DIST,
               demo_dir: Path = DEMO_DIR, locomotion_dir: Path = LOCOMOTION_DIR) -> FastAPI:
    app = FastAPI(title="Creature Forge Studio", lifespan=_warm)

    @app.get("/api/schema")
    def schema():
        return {
            "body": {"bounds": {k: list(v) for k, v in BOUNDS.items()}, "defaults": BipedParams().as_dict()},
            "gait": {"bounds": {k: list(v) for k, v in CTRL_BOUNDS.items()}, "defaults": GaitParams().as_dict()},
            "preset": {"push": {"time": PHASE0_PUSH.time, "force": PHASE0_PUSH.force,
                                "duration": PHASE0_PUSH.duration},
                       "seed": 0, "duration": PHASE0_DURATION},
        }

    @app.post("/api/simulate")
    def simulate(req: SimRequest):
        body = _params(BipedParams, {**BipedParams().as_dict(), **req.body}, "body")
        gait = _params(GaitParams, {**GaitParams().as_dict(), **req.gait}, "gait")
        push = Push(**req.push.model_dump()) if req.push else None
        return build_run_payload(body, gait, seed=req.seed, duration=req.duration, push=push)

    @app.get("/api/experiments/phase0")
    def phase0():
        return _phase0()

    @app.get("/api/investigations")
    def investigations():
        return list_trials(investigations_dir)  # read-only: trials are written by scripts, never by the web

    @app.get("/api/investigations/{trial_id}")
    def investigation(trial_id: str):
        try:
            return load_trial(trial_id, investigations_dir)
        except (KeyError, FileNotFoundError):
            raise HTTPException(404, "no such investigation") from None

    @app.get("/api/investigations/{trial_id}/view")
    def investigation_view(trial_id: str):
        try:
            return trial_view(load_trial(trial_id, investigations_dir))
        except (KeyError, FileNotFoundError):
            raise HTTPException(404, "no such investigation") from None

    # ---- Investigation Laboratory: read-only records + deterministic re-simulation (no model calls, no writes)
    @app.get("/api/lab/trials")
    def lab_trials():
        return list_lab_trials(investigations_dir, demo_dir)

    def _lab_trial(trial_id: str):
        try:
            return load_lab_trial(trial_id, investigations_dir, demo_dir)
        except KeyError:
            raise HTTPException(404, "no such investigation record") from None
        except LabError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/lab/trials/{trial_id}")
    def lab_trial(trial_id: str):
        trial, source = _lab_trial(trial_id)
        return lab_view(trial, source, demo_dir)

    @app.get("/api/lab/trials/{trial_id}/replay")
    def lab_replay(trial_id: str, seed: int = 0):
        trial, _ = _lab_trial(trial_id)
        try:
            return build_replay(trial, seed)
        except LabError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/locomotion/summary")
    def locomotion_summary():
        try:
            return load_summary(locomotion_dir)  # read-only: results are written by scripts/run_phase2a.py
        except FileNotFoundError:
            raise HTTPException(404, "no Phase 2A locomotion results found") from None

    @app.get("/api/locomotion/replay")
    def locomotion_replay(controller: str, seed: int = 3000, duration: float = 10.0):
        if controller not in CONTROLLER_INFO:
            raise HTTPException(404, f"unknown controller; choose one of {sorted(CONTROLLER_INFO)}")
        try:  # a fresh deterministic MuJoCo rollout of a committed controller; no model call
            return cached_replay(controller, seed, round(float(duration), 3), str(locomotion_dir))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except FileNotFoundError:
            raise HTTPException(404, "controller export not found") from None

    @app.get("/api/overview")
    def overview():
        return overview_mod.overview()  # read from committed experiment records at request time

    @app.get("/api/demo/status")
    def demo_status():
        used = demo_mod.r3v2.prior_usage()
        return {"live_enabled": demo_mod.live_enabled(), "live_calls_this_process": _DEMO_LIVE_CALLS["n"],
                "live_calls_cap_per_process": demo_mod.MAX_LIVE_REQUESTS_PER_PROCESS,
                "combined_budget": {"requests_used": used["requests"], "requests_cap": demo_mod.r3v2.TOTAL_REQUESTS_CAP,
                                    "tokens_used": used["tokens"], "tokens_cap": demo_mod.r3v2.TOTAL_TOKENS_CAP},
                "setting": demo_mod.SETTING, "limits": demo_mod.LIMITS,
                "kinds": {"LIVE": "a real Nebius call made during this run",
                          "RECORDED_LIVE": "a stored, hash-verified copy of an earlier real call",
                          "SCRIPTED_MOCK": "text written by this repository to exercise the pipeline; not a model"}}

    @app.get("/api/demo/runs")
    def demo_runs():
        return demo_mod.list_runs()

    @app.get("/api/demo/runs/{run_id}")
    def demo_run(run_id: str):
        try:
            return demo_mod.load_run(run_id)
        except (KeyError, FileNotFoundError):
            raise HTTPException(404, "no such demo run") from None

    @app.get("/api/demo/runs/{run_id}/replay")
    def demo_replay(run_id: str, which: str = "baseline", seed: int = demo_mod.FAILING_SEED):
        try:
            rec = demo_mod.load_run(run_id)
            return _demo_replay_cached(run_id, which, seed, rec)
        except (KeyError, FileNotFoundError):
            raise HTTPException(404, "no such demo run or replay") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/demo/run")
    def demo_run_new(req: DemoRunIn):
        from ..optimize import Executor
        from ..r2 import r2_job
        if req.mode == "live":
            if not demo_mod.live_enabled():
                raise HTTPException(403, "live mode is disabled on this server (needs CREATURE_FORGE_ENABLE_LIVE=1 and a Nebius key)")
            if not req.confirm_live:
                raise HTTPException(422, "live mode needs confirm_live=true: it spends Nebius inference budget")
            if _DEMO_LIVE_CALLS["n"] >= demo_mod.MAX_LIVE_REQUESTS_PER_PROCESS:
                raise HTTPException(429, "live-call cap for this server process reached")
        if not _DEMO_LOCK.acquire(blocking=False):
            raise HTTPException(409, "another demo run is in progress")
        try:
            client = None
            if req.mode == "live":
                client = demo_mod.r3v2.make_client()
                client.limits = type(client.limits)(max_requests=client.limits.max_requests, max_total_tokens=client.limits.max_total_tokens,
                                                    max_tokens_per_request=demo_mod.SETTING["max_tokens"], timeout_s=client.limits.timeout_s)
                _DEMO_LIVE_CALLS["n"] += 1
            with Executor(4, timeout_s=600, fn=r2_job) as ex:
                rec = demo_mod.run_investigation(req.mode, ex, client)
            if req.mode == "live":
                demo_mod.record_live_request(rec)
            demo_mod.save_local(rec)
            return rec
        except RuntimeError as exc:
            raise HTTPException(500, str(exc)) from exc
        finally:
            _DEMO_LOCK.release()

    @app.get("/api/sketch/default")
    def sketch_default():
        return default_sketch(BipedParams())

    @app.post("/api/sketch/compile")
    def sketch_compile(sketch: dict):
        try:
            return {"ok": True, "params": compile_sketch(sketch).as_dict()}
        except SketchError as exc:
            return {"ok": False, "errors": exc.errors}

    @app.get("/api/sketch/support")
    def sketch_support():
        return support_info()

    @app.post("/api/sketch/normalize")
    def sketch_normalize(req: NormalizeIn):
        """Project a near-valid sketch onto the supported planar biped; every change is reported, nothing is guessed."""
        if any(len(v) != 2 for v in req.nodes.values()):
            raise HTTPException(422, "each node must be [x, z]")
        return normalize_sketch({"nodes": req.nodes, "segments": req.segments}, req.extras)

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    repo = Path(__file__).resolve().parents[2]

    def _git(*args: str) -> str | None:
        try:
            out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=5)
            return out.stdout.strip() or None if out.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    git_info = {"git_commit": _git("rev-parse", "--short", "HEAD"), "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD")}

    @app.get("/api/version")
    def version():
        """Identify the running backend so a stale process can be told apart from the current code."""
        index = dist_dir / "index.html"
        built = (datetime.fromtimestamp(index.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                 if index.is_file() else None)
        return {**git_info, "started_at": started_at, "dist_built": built, "repo_root": str(repo),
                "api_routes": sorted(r.path for r in app.routes if r.path.startswith("/api/"))}

    @app.api_route("/api", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/api/{rest:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def api_not_found(rest: str = ""):
        # Registered after every real /api route; keeps unknown API paths from falling into the SPA's HTML.
        raise HTTPException(404, f"No such API route: /api/{rest}. If you expected it to exist, the running "
                                 "server may be older than the frontend; restart it with scripts/start_studio.ps1.")

    if dist_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            return FileResponse(resolve_static(dist_dir, path) or dist_dir / "index.html",
                                headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
