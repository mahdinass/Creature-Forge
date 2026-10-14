"""Lean, reproducible locomotion evaluator: rollout, physical metrics, hard walking gates, fitness.

Forward displacement alone never counts as walking. A rollout is classified from measured physics:
upright displacement, debounced foot-contact events (force-based), valid alternating forward steps, flight and
chatter, contact-point slip, body-ground contact, actuator saturation and effort. Hard gates define "walking"
(`WalkingCriteria`); a separate continuous fitness ranks candidates that do not yet pass every gate.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import mujoco
import numpy as np

from .contact import ContactConfig, SAMPLE_DT, replay
from .failures import _first_sustained
from .morphology import BipedParams, build_model

LOG_EVERY = 5   # physics steps per recorded/sensed sample (200 Hz at dt = 1 ms)
FALL_HEIGHT_FRAC = 0.5
FALL_PITCH = 1.0
FALL_SUSTAIN_SAMPLES = 20  # 0.1 s, same definition as failures.detect_failures
PERTURB = 0.03             # std of the random initial pitch / joint perturbation (rad)


@dataclass(frozen=True)
class WalkingCriteria:
    """Hard seed-level gates for genuine walking. Frozen; hashed into the pre-registration protocol."""
    min_speed: float = 0.20            # m/s upright displacement / elapsed upright time
    min_step_rate: float = 0.8         # valid alternating forward steps per second
    min_alternation: float = 0.9       # fraction of consecutive touchdowns that alternate feet
    max_touchdown_rate: float = 3.0    # raw touchdowns per foot per second (chatter)
    max_flight_frac: float = 0.10      # time with neither foot loaded
    max_slip_frac: float = 0.15        # loaded foot-time with contact-point speed > slip_speed
    slip_speed: float = 0.10           # m/s
    max_body_contact_frac: float = 0.005
    max_saturation_frac: float = 0.10
    max_abs_pitch: float = 0.8         # rad, torso must stay upright
    # valid-step definition
    min_swing_s: float = 0.10
    min_stance_s: float = 0.12
    min_step_advance: float = 0.05     # m, foot x at touchdown minus foot x at previous liftoff
    skip_after_touchdown_s: float = 0.03  # impact transient excluded from slip

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT_CRITERIA = WalkingCriteria()


# ---------------------------------------------------------------------------------------------------------
# rollout
# ---------------------------------------------------------------------------------------------------------
def rollout(controller, body: BipedParams, seed: int, duration: float, *, perturb: float = PERTURB,
            record_poses: bool = False) -> dict:
    """Simulate one episode; returns a 200 Hz trace. The seed drives only the initial perturbation.
    Stops early (trace ends) once the fall condition has persisted 0.1 s."""
    body.validate()
    model = build_model(body)
    data = mujoco.MjData(model)
    rng = np.random.default_rng(seed)
    data.qpos[2] = perturb * rng.standard_normal()
    data.qpos[3:9] = perturb * rng.standard_normal(6)
    mujoco.mj_forward(model, data)
    foot_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"foot_{s}") for s in "lr"]
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
    lowest = min(data.geom_xpos[i][2] - np.abs(data.geom_xmat[i].reshape(3, 3)[2]) @ model.geom_size[i]
                 for i in foot_ids)
    data.qpos[1] -= max(lowest, 0.0) - 0.002
    mujoco.mj_forward(model, data)

    mass = float(model.body_mass.sum())
    weight = mass * 9.81
    controller.reset(body.torque_limit, weight)
    limit = body.torque_limit
    render_geoms = [i for i in range(model.ngeom) if i != floor_id]
    keys = ("t", "x", "z", "pitch", "q", "qd", "tau", "demand", "force", "slip", "foot_x", "foot_z", "body_contact")
    tr: dict[str, list] = {k: [] for k in keys}
    if record_poses:
        tr.update({"geom_xpos": [], "geom_xquat": [], "foot_contact_pos": []})
    quat = np.zeros(4)
    vel6 = np.zeros(6)
    f6 = np.zeros(6)
    steps = int(round(duration / model.opt.timestep))
    demand = np.zeros(6)
    z0 = None
    bad = 0
    for step in range(steps):
        demand = controller.torque(data.time, data.qpos[2], data.qvel[2], data.qpos[3:9], data.qvel[3:9])
        data.ctrl[:] = np.clip(demand, -limit, limit)
        mujoco.mj_step(model, data)
        if step % LOG_EVERY:
            continue
        force = [0.0, 0.0]
        slip = [0.0, 0.0]
        cpos = np.zeros((2, 3))
        body_contact = 0.0
        for c in range(data.ncon):
            con = data.contact[c]
            g1, g2 = con.geom1, con.geom2
            if floor_id not in (g1, g2):
                continue
            mujoco.mj_contactForce(model, data, c, f6)
            other = g2 if g1 == floor_id else g1
            if other in foot_ids:
                if f6[0] > 1e-6:
                    k = foot_ids.index(other)
                    force[k] += f6[0]
                    mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_GEOM, other, vel6, 0)
                    v = vel6[3:] + np.cross(vel6[:3], con.pos - data.geom_xpos[other])  # contact-point velocity
                    slip[k] += f6[0] * abs(v[0])
                    cpos[k] += f6[0] * con.pos
            elif f6[0] > 1e-6:
                body_contact = 1.0
        for k in (0, 1):
            if force[k] > 0.0:
                slip[k] /= force[k]
                cpos[k] /= force[k]
        controller.sense(data.time, force)
        x, z, pitch = float(data.xpos[torso_id][0]), float(data.xpos[torso_id][2]), float(data.qpos[2])
        if z0 is None:
            z0 = z
        tr["t"].append(data.time)
        tr["x"].append(x)
        tr["z"].append(z)
        tr["pitch"].append(pitch)
        tr["q"].append(data.qpos[3:9].copy())
        tr["qd"].append(data.qvel[3:9].copy())
        tr["tau"].append(data.actuator_force.copy())
        tr["demand"].append(np.array(demand, dtype=float))
        tr["force"].append(force)
        tr["slip"].append(slip)
        tr["foot_x"].append([float(data.geom_xpos[i][0]) for i in foot_ids])
        tr["foot_z"].append([float(data.geom_xpos[i][2]) for i in foot_ids])
        tr["body_contact"].append(body_contact)
        if record_poses:
            xq = np.zeros((len(render_geoms), 4))
            for r, gi in enumerate(render_geoms):
                mujoco.mju_mat2Quat(quat, data.geom_xmat[gi])
                xq[r] = quat
            tr["geom_xpos"].append(data.geom_xpos[render_geoms].copy())
            tr["geom_xquat"].append(xq)
            tr["foot_contact_pos"].append(cpos.copy())
        bad = bad + 1 if (z < FALL_HEIGHT_FRAC * z0 or abs(pitch) > FALL_PITCH) else 0
        if bad >= FALL_SUSTAIN_SAMPLES:
            break
    out = {k: np.asarray(v, dtype=float) for k, v in tr.items()}
    out["meta"] = {"seed": seed, "duration": duration, "mass": mass, "weight": weight, "torque_limit": limit,
                   "controller": controller.name}
    return out


# ---------------------------------------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------------------------------------
def step_events(est_events: list[dict], foot_x: np.ndarray, crit: WalkingCriteria) -> dict:
    """Valid alternating forward steps from debounced contact events (+ foot placement).

    A touchdown is a valid step when: it alternates with the previous valid step's foot; the foot was
    airborne >= min_swing_s; the foot's preceding stance lasted >= min_stance_s; and the foot landed at least
    min_step_advance ahead of where it lifted (a rearward landing is counted as a backward step instead).
    """
    last_td = {0: None, 1: None}
    last_lo = {0: None, 1: None}
    valid, backward, stance, swing = [], 0, [], []
    last_valid_foot = None
    n_td = n_alt = 0
    prev_td_foot = None
    for ev in sorted(est_events, key=lambda e: (e["t"], e["foot"])):
        k, t = ev["foot"], ev["t"]
        i = min(max(int(round(t / SAMPLE_DT)), 0), len(foot_x) - 1)
        if ev["kind"] == "touchdown":
            n_td += 1
            if prev_td_foot is not None and k != prev_td_foot:
                n_alt += 1
            prev_td_foot = k
            if last_lo[k] is not None and last_td[k] is not None:
                sw = t - last_lo[k][0]
                st = last_lo[k][0] - last_td[k][0]
                adv = foot_x[i, k] - last_lo[k][1]
                swing.append(sw)
                stance.append(st)
                if sw >= crit.min_swing_s and st >= crit.min_stance_s:
                    if adv >= crit.min_step_advance and k != last_valid_foot:
                        valid.append({"t": t, "foot": k, "advance": float(adv), "swing_s": float(sw),
                                      "stance_s": float(st)})
                        last_valid_foot = k
                    elif adv <= -crit.min_step_advance:
                        backward += 1
            last_td[k] = (t, foot_x[i, k])
        else:
            last_lo[k] = (t, foot_x[i, k])
    return {"valid": valid, "backward": backward, "touchdowns": n_td,
            "alternation": (n_alt / (n_td - 1)) if n_td > 1 else 0.0,
            "mean_stance_s": float(np.mean(stance)) if stance else 0.0,
            "mean_swing_s": float(np.mean(swing)) if swing else 0.0}


def compute_metrics(tr: dict, crit: WalkingCriteria = DEFAULT_CRITERIA,
                    contact: ContactConfig = ContactConfig()) -> dict:
    meta = tr["meta"]
    t, x, z, pitch = tr["t"], tr["x"], tr["z"], tr["pitch"]
    duration, limit = meta["duration"], meta["torque_limit"]
    n = len(t)
    low = (z < FALL_HEIGHT_FRAC * z[0]) | (np.abs(pitch) > FALL_PITCH)
    fi = _first_sustained(low, FALL_SUSTAIN_SAMPLES)
    fell = fi is not None
    iu = fi if fell else n - 1                      # last upright sample index
    t_up = float(t[iu] + SAMPLE_DT) if iu > 0 else SAMPLE_DT
    t_up = min(t_up, duration)
    dx_up = float(x[iu] - x[0])
    v_up = dx_up / max(t_up, 0.5) if t_up >= 0.5 else 0.0
    sl = slice(0, iu + 1)

    est, raw, deb = replay(t[sl], tr["force"][sl], meta["weight"], contact)
    n_loaded = deb.sum(1)
    flight = float(np.mean(n_loaded == 0))
    single = float(np.mean(n_loaded == 1))
    double = float(np.mean(n_loaded == 2))
    # raw touchdowns per foot per second; the very first landing after spawn is not chatter
    raw_td = np.array(est.raw_touchdowns, dtype=float)
    td_rate = float(max(raw_td.max() - 1.0, 0.0) / t_up)

    st = step_events(est.events, tr["foot_x"][sl], crit)
    valid = st["valid"]
    step_rate = len(valid) / t_up
    skip = int(round(crit.skip_after_touchdown_s / SAMPLE_DT))
    loaded_n = slipping_n = 0
    slip_dist = 0.0
    for k in (0, 1):
        run = 0
        for i in range(iu + 1):
            run = run + 1 if deb[i, k] else 0
            if run > skip:
                loaded_n += 1
                s = tr["slip"][i, k]
                slip_dist += s * SAMPLE_DT
                slipping_n += s > crit.slip_speed
    slip_frac = slipping_n / loaded_n if loaded_n else 0.0
    demand = np.abs(tr["demand"][sl])
    sat_frac = float(np.mean((demand >= 0.99 * limit).any(axis=1)))
    effort = float(np.mean(((tr["tau"][sl] / limit) ** 2).mean(axis=1)))
    power = np.maximum(tr["tau"][sl] * tr["qd"][sl], 0.0).sum(1)
    mech_energy = float(power.sum() * SAMPLE_DT)
    cot = mech_energy / (meta["weight"] * dx_up) if dx_up > 0.1 else float("inf")
    m = {
        "seed": meta["seed"], "duration": duration, "controller": meta["controller"],
        "fell": bool(fell), "fall_time": float(t[fi]) if fell else None, "time_upright": t_up,
        "fall_pitch": float(pitch[fi]) if fell else None,
        "forward_disp_upright": dx_up, "speed_upright": v_up, "speed_effective": dx_up / duration,
        "valid_steps": len(valid), "valid_step_rate": step_rate, "backward_steps": st["backward"],
        "touchdowns": st["touchdowns"], "alternation": st["alternation"],
        "mean_step_advance": float(np.mean([s["advance"] for s in valid])) if valid else 0.0,
        "mean_stance_s": st["mean_stance_s"], "mean_swing_s": st["mean_swing_s"],
        "flight_frac": flight, "single_support_frac": single, "double_support_frac": double,
        "raw_touchdown_rate": td_rate,
        "slip_frac": float(slip_frac), "slip_distance": float(slip_dist),
        "body_contact_frac": float(np.mean(tr["body_contact"][sl])),
        "saturation_frac": sat_frac, "effort": effort, "mech_energy": mech_energy, "cot": cot,
        "max_abs_pitch": float(np.abs(pitch[sl]).max()), "mean_pitch": float(pitch[sl].mean()),
        "min_torso_height": float(z.min()),
    }
    m.update(classify(m, crit))
    return m


def classify(m: dict, crit: WalkingCriteria = DEFAULT_CRITERIA) -> dict:
    """Hard gates + a single primary label (first applicable, in priority order)."""
    v = []
    if m["fell"]:
        v.append("fall")
    if m["body_contact_frac"] > crit.max_body_contact_frac:
        v.append("body_dragging")
    if m["raw_touchdown_rate"] > crit.max_touchdown_rate:
        v.append("contact_chatter")
    if m["flight_frac"] > crit.max_flight_frac:
        v.append("hopping")
    if m["saturation_frac"] > crit.max_saturation_frac:
        v.append("torque_saturated")
    if m["slip_frac"] > crit.max_slip_frac:
        v.append("foot_sliding")
    if m["max_abs_pitch"] > crit.max_abs_pitch:
        v.append("not_upright")
    if m["speed_upright"] < crit.min_speed:
        v.append("too_slow")
    if m["valid_step_rate"] < crit.min_step_rate:
        v.append("too_few_steps")
    if m["alternation"] < crit.min_alternation:
        v.append("not_alternating")
    if not v:
        label = "walking"
    elif m["fell"]:
        label = "falling_forward" if (m["fall_pitch"] or 0.0) > 0 and m["forward_disp_upright"] > 0 else "fall"
    elif "body_dragging" in v:
        label = "body_dragging"
    elif "contact_chatter" in v:
        label = "contact_chatter"
    elif "hopping" in v:
        label = "hopping"
    elif "torque_saturated" in v:
        label = "torque_saturated"
    elif "foot_sliding" in v:
        label = "foot_sliding"
    elif m["speed_upright"] < -0.05:
        label = "backward_shuffle"
    elif abs(m["speed_upright"]) < 0.05:
        label = "stationary"
    elif m["valid_step_rate"] < crit.min_step_rate and m["forward_disp_upright"] > 0.2:
        label = "sliding_without_steps"
    else:
        label = "slow_or_few_steps"
    return {"violations": v, "label": label, "walking": not v}


# ---------------------------------------------------------------------------------------------------------
# fitness: gate-aware but continuous, so candidates that fail gates are still rankable
# ---------------------------------------------------------------------------------------------------------
def _soft(x: float, ok: float, bad: float) -> float:
    """1 when x <= ok, 0 when x >= bad, linear between."""
    return float(min(max((bad - x) / (bad - ok), 0.0), 1.0))


def fitness_components(m: dict, crit: WalkingCriteria = DEFAULT_CRITERIA) -> dict:
    validity = min(
        _soft(m["raw_touchdown_rate"], crit.max_touchdown_rate - 0.5, 2.0 * crit.max_touchdown_rate),
        _soft(m["flight_frac"], crit.max_flight_frac, 0.4),
        _soft(m["slip_frac"], crit.max_slip_frac, 0.5),
        _soft(m["saturation_frac"], crit.max_saturation_frac, 0.5),
        _soft(m["body_contact_frac"], crit.max_body_contact_frac, 0.05),
    )
    survival = m["time_upright"] / m["duration"]
    progress = float(np.clip(m["speed_effective"] / 0.4, -1.0, 1.0)) * validity
    steps = min(m["valid_step_rate"] / 1.5, 1.0) * validity
    effort_pen = 0.5 * min(m["effort"], 1.0)
    pitch_pen = 0.5 * float(np.clip((m["max_abs_pitch"] - 0.5) / 0.5, 0.0, 1.0))
    bonus = 1.0 if m["walking"] else 0.0
    total = 1.0 * survival + 3.0 * progress + 1.0 * steps - effort_pen - pitch_pen + bonus
    return {"survival": survival, "progress": progress, "steps": steps, "validity": validity,
            "effort_penalty": effort_pen, "pitch_penalty": pitch_pen, "walking_bonus": bonus, "total": total}


def evaluate_controller(controller, body: BipedParams, seeds, duration: float,
                        crit: WalkingCriteria = DEFAULT_CRITERIA) -> dict:
    """Run one rollout per seed. Returns per-seed metrics + components and candidate-level aggregates."""
    per = []
    for s in seeds:
        m = compute_metrics(rollout(controller, body, s, duration), crit)
        m["fitness"] = fitness_components(m, crit)
        per.append(m)
    return aggregate(per)


def aggregate(per: list[dict]) -> dict:
    fit = [m["fitness"]["total"] for m in per]
    labels = [m["label"] for m in per]
    return {
        "seeds": [m["seed"] for m in per], "per_seed": per, "rollouts": len(per),
        "fitness": float(np.mean(fit)), "fitness_worst": float(np.min(fit)),
        "fitness_components": {k: float(np.mean([m["fitness"][k] for m in per])) for k in per[0]["fitness"]},
        "walking_fraction": float(np.mean([m["walking"] for m in per])),
        "feasible": all(m["walking"] for m in per),
        "labels": labels,
        "label": max(set(labels), key=lambda s: (labels.count(s), s)),
        "median_speed": float(np.median([m["speed_upright"] for m in per])),
    }
