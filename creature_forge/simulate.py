"""Deterministic headless MuJoCo rollout with full telemetry capture."""
from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np

from .controller import GaitParams, compute_torque
from .morphology import BipedParams, build_model

LOG_EVERY = 5  # steps => 200 Hz telemetry at dt=0.001


@dataclass(frozen=True)
class Push:
    """Horizontal external force on the torso (N) applied for `duration` s starting at `time`."""
    time: float
    force: float
    duration: float = 0.1


def run_rollout(body: BipedParams, gait: GaitParams, seed: int = 0, duration: float = 10.0,
                perturb: float = 0.02, push: Push | None = None,
                record_poses: bool = False) -> dict[str, np.ndarray]:
    """Simulate; the seed drives a small initial pitch/joint perturbation (only source of randomness)."""
    body.validate()
    gait.validate()
    model = build_model(body)
    data = mujoco.MjData(model)
    rng = np.random.default_rng(seed)
    data.qpos[2] = perturb * rng.standard_normal()
    data.qpos[3:9] = perturb * rng.standard_normal(6)
    mujoco.mj_forward(model, data)
    # Place the body so the lowest foot sits just above the floor.
    foot_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"foot_{s}") for s in "lr"]
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
    # exact lowest point of each (rotated) foot box
    lowest = min(data.geom_xpos[i][2] - np.abs(data.geom_xmat[i].reshape(3, 3)[2]) @ model.geom_size[i]
                 for i in foot_ids)
    data.qpos[1] -= max(lowest, 0.0) - 0.002
    mujoco.mj_forward(model, data)

    steps = int(round(duration / model.opt.timestep))
    rows: dict[str, list] = {k: [] for k in (
        "t", "torso_pos", "torso_pitch", "torso_linvel", "torso_angvel", "qpos_joints",
        "qvel_joints", "joint_torque", "ctrl_demand", "com_pos", "com_vel", "foot_contact",
        "foot_slip_speed", "contact_force_total", "support_x_min", "support_x_max", "cop_x")}
    render_geoms = [i for i in range(model.ngeom) if i != floor_id]
    if record_poses:
        rows.update({"geom_xpos": [], "geom_xquat": [], "foot_contact_pos": []})
    quat = np.zeros(4)
    vel6 = np.zeros(6)
    demand = np.zeros(6)
    for step in range(steps):
        pitch, pitch_rate = data.qpos[2], data.qvel[2]
        demand = compute_torque(gait, data.time, pitch, pitch_rate, data.qpos[3:9], data.qvel[3:9])
        data.ctrl[:] = np.clip(demand, -body.torque_limit, body.torque_limit)
        if push is not None:
            on = push.time <= data.time < push.time + push.duration
            data.xfrc_applied[torso_id, 0] = push.force if on else 0.0
        mujoco.mj_step(model, data)
        if step % LOG_EVERY:
            continue
        mujoco.mj_subtreeVel(model, data)
        contact = np.zeros(2)
        cpos = np.zeros((2, 3))
        ccount = np.zeros(2)
        slip = np.zeros(2)
        fsum = 0.0
        f6 = np.zeros(6)
        foot_cx: list[float] = []  # world x of every loaded foot-floor contact point
        foot_cf: list[float] = []  # its normal force (N)
        for c in range(data.ncon):
            con = data.contact[c]
            g1, g2 = con.geom1, con.geom2
            if floor_id not in (g1, g2):
                continue
            mujoco.mj_contactForce(model, data, c, f6)
            fsum += f6[0]
            other = g2 if g1 == floor_id else g1
            if other in foot_ids and f6[0] > 1e-6:
                k = foot_ids.index(other)
                contact[k] = 1.0
                foot_cx.append(float(con.pos[0]))
                foot_cf.append(float(f6[0]))
                cpos[k] += con.pos
                ccount[k] += 1
                mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_GEOM, other, vel6, 0)
                slip[k] = max(slip[k], abs(vel6[3]))  # world-frame x linear velocity of foot geom
        if record_poses:
            xq = np.zeros((len(render_geoms), 4))
            for r, gi in enumerate(render_geoms):
                mujoco.mju_mat2Quat(quat, data.geom_xmat[gi])
                xq[r] = quat
            rows["geom_xpos"].append(data.geom_xpos[render_geoms].copy())
            rows["geom_xquat"].append(xq)
            rows["foot_contact_pos"].append(cpos / np.maximum(ccount, 1)[:, None])
        rows["t"].append(data.time)
        rows["torso_pos"].append([data.xpos[torso_id][0], data.xpos[torso_id][2], data.qpos[2]])
        rows["torso_pitch"].append(data.qpos[2])
        rows["torso_linvel"].append([data.qvel[0], data.qvel[1]])
        rows["torso_angvel"].append(data.qvel[2])
        rows["qpos_joints"].append(data.qpos[3:9].copy())
        rows["qvel_joints"].append(data.qvel[3:9].copy())
        rows["joint_torque"].append(data.actuator_force.copy())
        rows["ctrl_demand"].append(demand.copy())
        rows["com_pos"].append(data.subtree_com[0].copy())
        rows["com_vel"].append(data.subtree_linvel[0].copy())
        # support polygon extent (min/max loaded contact x) and center of pressure; NaN = no foot loaded
        if foot_cx:
            rows["support_x_min"].append(min(foot_cx))
            rows["support_x_max"].append(max(foot_cx))
            rows["cop_x"].append(float(np.dot(foot_cx, foot_cf) / sum(foot_cf)))
        else:
            for k in ("support_x_min", "support_x_max", "cop_x"):
                rows[k].append(float("nan"))
        rows["foot_contact"].append(contact)
        rows["foot_slip_speed"].append(slip)
        rows["contact_force_total"].append(fsum)
    return {k: np.asarray(v, dtype=float) for k, v in rows.items()}
