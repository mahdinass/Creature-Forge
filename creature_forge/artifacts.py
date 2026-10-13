"""Reproducible experiment artifacts: telemetry.npz + manifest.json (params, seed, versions, events, hash)."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path

import mujoco
import numpy as np

from .controller import GaitParams
from .failures import FailureEvent
from .morphology import BipedParams


def telemetry_hash(tel: dict) -> str:
    h = hashlib.sha256()
    for k in sorted(tel):
        h.update(k.encode())
        h.update(np.ascontiguousarray(tel[k], dtype=np.float64).tobytes())
    return h.hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def save_run(root: Path, run_id: str, body: BipedParams, gait: GaitParams, *, seed: int,
             duration: float, push, telemetry: dict, events: list[FailureEvent]) -> Path:
    out = Path(root) / run_id
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "telemetry.npz", **telemetry)
    manifest = {
        "run_id": run_id, "seed": seed, "duration": duration,
        "body": body.as_dict(), "gait": gait.as_dict(),
        "push": None if push is None else {"time": push.time, "force": push.force, "duration": push.duration},
        "events": [e.as_dict() for e in events],
        "telemetry_sha256": telemetry_hash(telemetry),
        "mujoco_version": mujoco.__version__, "numpy_version": np.__version__,
        "python_version": platform.python_version(), "git_commit": _git_commit(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return out
