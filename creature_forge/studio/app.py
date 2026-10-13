"""Creature Forge Studio backend: thin FastAPI layer over the MuJoCo pipeline.

No physics here; every pose served comes from creature_forge.render_export (MuJoCo rollouts).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..controller import CTRL_BOUNDS, GaitParams
from ..experiment import (PHASE0_BASELINE, PHASE0_CANDIDATE, PHASE0_DURATION, PHASE0_PUSH, PHASE0_SEEDS,
                          compare_designs)
from ..investigator import INVESTIGATIONS_DIR, list_trials, load_trial
from ..morphology import BOUNDS, BipedParams
from ..render_export import build_run_payload
from ..simulate import Push
from ..sketch import SketchError, compile_sketch, default_sketch

DIST = Path(__file__).resolve().parents[2] / "studio" / "dist"


class PushIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: float = Field(ge=0, le=20)
    force: float = Field(ge=-200, le=200)
    duration: float = Field(default=0.15, gt=0, le=2)


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


def create_app(investigations_dir: Path = INVESTIGATIONS_DIR) -> FastAPI:
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

    @app.get("/api/sketch/default")
    def sketch_default():
        return default_sketch(BipedParams())

    @app.post("/api/sketch/compile")
    def sketch_compile(sketch: dict):
        try:
            return {"ok": True, "params": compile_sketch(sketch).as_dict()}
        except SketchError as exc:
            return {"ok": False, "errors": exc.errors}

    if DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            f = DIST / path
            return FileResponse(f if path and f.is_file() else DIST / "index.html")

    return app


app = create_app()
