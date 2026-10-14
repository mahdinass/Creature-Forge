"""Presentation-layer export of real MuJoCo rigid-body poses.

All coordinate conversion happens here (MuJoCo Z-up, X forward, Y lateral  ->  three.js Y-up:
(x, y, z) -> (x, z, -y), a proper rotation). The frontend only renders what it is given.
"""
from __future__ import annotations

import mujoco
import numpy as np

from .controller import GaitParams
from .failures import detect_failures
from .morphology import BipedParams, build_model
from .simulate import Push, run_rollout

FRAME = "three-y-up"
DISPLAY_LATERAL_OFFSET = 0.07


def mj_to_three_pos(p) -> np.ndarray:
    x, y, z = np.asarray(p, dtype=float)
    return np.array([x, z, -y])


def mj_to_three_quat(q_wxyz) -> np.ndarray:
    """MuJoCo (w, x, y, z) -> three.js (x, y, z, w) after conjugating by the basis change."""
    w, x, y, z = np.asarray(q_wxyz, dtype=float)
    return np.array([x, z, -y, w])


def export_scene(model: mujoco.MjModel) -> dict:
    """Static geometry. Capsule axis is local Y and box extents are reordered to three.js axes."""
    floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    geoms = []
    for i in range(model.ngeom):
        if i == floor:
            continue
        s = model.geom_size[i]
        kind = mujoco.mjtGeom(model.geom_type[i])
        if kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
            entry = {"type": "capsule", "size": [float(s[0]), float(s[1])]}  # radius, half-length
        elif kind == mujoco.mjtGeom.mjGEOM_BOX:
            entry = {"type": "box", "size": [float(s[0]), float(s[2]), float(s[1])]}
        else:
            raise ValueError(f"unsupported geom type for export: {kind.name}")
        entry["part"] = model.body(model.geom_bodyid[i]).name
        geoms.append(entry)
    # Presentation only: the model is planar (both legs share the x-z plane). The viewer draws the left/right
# legs this far apart (metres, three.js z axis) so they are distinguishable; physics is unaffected.
    return {"frame": FRAME, "geoms": geoms, "display_lateral_offset": DISPLAY_LATERAL_OFFSET}


def build_run_payload(body: BipedParams, gait: GaitParams, *, seed: int = 0, duration: float = 5.0,
                      push: Push | None = None, ndigits: int = 5) -> dict:
    tel = run_rollout(body, gait, seed=seed, duration=duration, push=push, record_poses=True)
    return payload_from_telemetry(body, gait, tel, seed=seed, duration=duration, push=push, ndigits=ndigits)


def payload_from_telemetry(body: BipedParams, gait: GaitParams, tel: dict, *, seed: int, duration: float,
                           push: Push | None, ndigits: int = 5) -> dict:
    events = detect_failures(tel, body)
    pos = np.round([[mj_to_three_pos(p) for p in f] for f in tel["geom_xpos"]], ndigits)
    quat = np.round([[mj_to_three_quat(q) for q in f] for f in tel["geom_xquat"]], ndigits)
    cpos = np.round([[mj_to_three_pos(p) for p in f] for f in tel["foot_contact_pos"]], ndigits)
    z = tel["torso_pos"][:, 1]
    return {
        "scene": export_scene(build_model(body)),
        "body": body.as_dict(), "gait": gait.as_dict(), "seed": seed, "duration": duration,
        "push": None if push is None else {"time": push.time, "force": push.force, "duration": push.duration},
        "time": np.round(tel["t"], 4).tolist(),
        "frames": {"pos": pos.tolist(), "quat": quat.tolist(), "contact_pos": cpos.tolist()},
        "series": {
            "torso_height": np.round(z, 5).tolist(),
            "torso_pitch": np.round(tel["torso_pitch"], 5).tolist(),
            "torso_x": np.round(tel["torso_pos"][:, 0], 5).tolist(),
            "foot_contact": tel["foot_contact"].astype(int).tolist(),
            "foot_slip_speed": np.round(tel["foot_slip_speed"], 4).tolist(),
            "max_torque_frac": np.round(np.abs(tel["joint_torque"]).max(axis=1) / body.torque_limit, 4).tolist(),
        },
        "events": [e.as_dict() for e in events],
        "metrics": {
            "initial_torso_height": float(z[0]), "min_torso_height": float(z.min()),
            "final_torso_height": float(z[-1]),
            "max_abs_pitch": float(np.abs(tel["torso_pitch"]).max()),
            "peak_torso_vx": float(np.abs(tel["torso_linvel"][:, 0]).max()),
            "fell": any(e.kind == "fall" for e in events),
        },
    }
