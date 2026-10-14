"""Presentation-layer data for Phase 2A locomotion results (Studio): training history summary and replays.

Everything is read from the committed result files or produced by a fresh deterministic MuJoCo rollout; nothing
is invented or prerecorded here. Replay payloads follow `render_export.build_run_payload` (so the existing 3D
viewer, timeline and metric panels work unchanged) plus a `locomotion` block with the gate verdict.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from .contact import replay as contact_replay
from .controller import GaitParams
from .locomotion import compute_metrics, rollout
from .morphology import BipedParams, build_model
from .phase2a import (DIAGNOSTIC_SEEDS, DURATIONS, EXP_DIR, HELDOUT_SEEDS, OPEN_LOOP_REFERENCE, TRAIN_SEEDS)
from .phasegait import OpenLoopController
from .optimize import controller_from_export
from .render_export import export_scene, mj_to_three_pos, mj_to_three_quat

RESULTS = EXP_DIR / "results"
MAX_DURATION = 12.0

CONTROLLER_INFO = {
    "standing": "Phase 0 standing-balance controller (no gait)",
    "open_loop_reference": "Phase 0 open-loop sinusoid, 1.0 Hz (stable but travels backward)",
    "random_search": "Phase-gait controller chosen by random search (600 rollouts) - frozen before held-out",
    "differential_evolution": "Phase-gait controller chosen by differential evolution (600 rollouts) - frozen before held-out",
}


def seed_role(seed: int) -> str | None:
    if seed in TRAIN_SEEDS:
        return "train"
    if seed in DIAGNOSTIC_SEEDS:
        return "diagnostic"
    if seed in HELDOUT_SEEDS:
        return "heldout"
    return None


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_summary(results_dir: Path = RESULTS) -> dict:
    """Compact training/evaluation summary for the progress panel. Raises FileNotFoundError if absent."""
    out: dict = {"protocol_id": None, "methods": {}, "heldout": None, "controllers": CONTROLLER_INFO,
                 "seed_roles": {"train": list(TRAIN_SEEDS), "diagnostic": list(DIAGNOSTIC_SEEDS),
                                "heldout": list(HELDOUT_SEEDS)}, "durations": DURATIONS}
    proto = results_dir.parent / "protocol.json"
    if proto.is_file():
        p = _read(proto)
        out["protocol_id"], out["success_criteria"] = p["id"], p["success_criteria"]
        out["walking_criteria"] = p["walking_criteria"]
    names = ("random_search", "differential_evolution")
    for m in names:
        s = _read(results_dir / f"summary_{m}.json")
        hist = [json.loads(line) for line in (results_dir / f"history_{m}.jsonl").read_text(encoding="utf-8").splitlines()]
        out["methods"][m] = {
            "rollouts": s["rollouts"], "candidates": s["candidates"], "errors": s["errors"], "wall_s": s["wall_s"],
            "hyperparameters": s["hyperparameters"], "best_so_far": s["best_so_far"], "label_counts": s["label_counts"],
            "n_feasible": s["n_feasible"], "best_index": s["best_index"],
            "candidate_fitness": [r["fitness"] for r in hist], "candidate_labels": [r["label"] for r in hist],
            "rng_seed": s["config"]["rng_seed"],
        }
    held = results_dir / "heldout.json"
    if held.is_file():
        h = _read(held)
        out["heldout"] = {"seeds": h["seeds"], "duration": h["duration"], "rollouts": h["rollouts"],
                          "controllers": {k: {"verdict": v["verdict"], "summary": v["summary"]}
                                          for k, v in h["controllers"].items()}}
    return out


def replay_controller(name: str, results_dir: Path = RESULTS):
    """(controller, body, gait_params_dict) for a named replayable controller."""
    if name == "standing":
        g = GaitParams()
        return OpenLoopController(g), BipedParams(), g.as_dict()
    if name == "open_loop_reference":
        return OpenLoopController(OPEN_LOOP_REFERENCE), BipedParams(), OPEN_LOOP_REFERENCE.as_dict()
    files = {"random_search": "best_random_search.json", "differential_evolution": "best_differential_evolution.json"}
    if name not in files:
        raise KeyError(name)
    ctrl, body = controller_from_export(_read(results_dir / files[name]))
    return ctrl, body, ctrl.p.as_dict()


def build_locomotion_payload(controller, body: BipedParams, gait_params: dict, *, seed: int, duration: float,
                             ndigits: int = 5) -> dict:
    tr = rollout(controller, body, seed, duration, record_poses=True)
    m = compute_metrics(tr)
    pos = np.round([[mj_to_three_pos(p) for p in f] for f in tr["geom_xpos"]], ndigits)
    quat = np.round([[mj_to_three_quat(q) for q in f] for f in tr["geom_xquat"]], ndigits)
    cpos = np.round([[mj_to_three_pos(p) for p in f] for f in tr["foot_contact_pos"]], ndigits)
    _, _, deb = contact_replay(tr["t"], tr["force"], tr["meta"]["weight"])
    events = []
    if m["fell"]:
        events.append({"kind": "fall", "time": m["fall_time"],
                       "evidence": {"torso_pitch": m["fall_pitch"], "min_torso_height": m["min_torso_height"]}})
    keep = ("label", "walking", "violations", "speed_upright", "forward_disp_upright", "valid_steps",
            "valid_step_rate", "backward_steps", "mean_step_advance", "mean_stance_s", "mean_swing_s",
            "single_support_frac", "double_support_frac", "flight_frac", "raw_touchdown_rate", "slip_frac",
            "saturation_frac", "effort", "time_upright", "fell", "fall_time")
    z = tr["z"]
    return {
        "scene": export_scene(build_model(body)),
        "body": body.as_dict(), "gait": gait_params, "seed": seed, "role": seed_role(seed), "duration": float(tr["t"][-1]),
        "push": None,
        "time": np.round(tr["t"], 4).tolist(),
        "frames": {"pos": pos.tolist(), "quat": quat.tolist(), "contact_pos": cpos.tolist()},
        "series": {
            "torso_height": np.round(z, 5).tolist(), "torso_pitch": np.round(tr["pitch"], 5).tolist(),
            "torso_x": np.round(tr["x"], 5).tolist(), "foot_contact": deb.astype(int).tolist(),
            "foot_slip_speed": np.round(tr["slip"], 4).tolist(),
            "max_torque_frac": np.round(np.abs(tr["tau"]).max(axis=1) / body.torque_limit, 4).tolist(),
        },
        "events": events,
        "metrics": {"initial_torso_height": float(z[0]), "min_torso_height": float(z.min()),
                    "final_torso_height": float(z[-1]), "max_abs_pitch": float(np.abs(tr["pitch"]).max()),
                    "peak_torso_vx": float(np.abs(np.gradient(tr["x"], tr["t"])).max()) if len(tr["t"]) > 1 else 0.0, "fell": bool(m["fell"])},
        "locomotion": {k: (None if isinstance(m[k], float) and not np.isfinite(m[k]) else m[k]) for k in keep},
    }


@lru_cache(maxsize=32)
def cached_replay(name: str, seed: int, duration: float, results_dir: str = str(RESULTS)) -> dict:
    if seed_role(seed) is None:
        raise ValueError(f"seed {seed} is not one of the registered train/diagnostic/held-out seeds")
    if not (1.0 <= duration <= MAX_DURATION):
        raise ValueError(f"duration must be within [1, {MAX_DURATION}] s")
    ctrl, body, gait = replay_controller(name, Path(results_dir))
    return build_locomotion_payload(ctrl, body, gait, seed=seed, duration=duration)
