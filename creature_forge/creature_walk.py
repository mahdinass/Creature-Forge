"""Walking for user-drawn creatures: a sandbox-aware rollout, body-scaled walking criteria and controller adaptation.

`locomotion.py` is frozen and ignores `body.pose`; this module reuses its metrics/classification unchanged and only adds
  * `rollout`   - the same 200 Hz trace as `locomotion.rollout` (bit-identical for the default body with start="neutral"),
                  optionally starting from the drawn joint configuration (start="drawn");
  * `creature_criteria` - the walking gates that carry a length (`min_speed`, `min_step_advance`) scaled by the creature's
                  mean leg length / 0.60 m; exactly `DEFAULT_CRITERIA` for the default body;
  * `adapt_controller`  - a short (1+8)-ES around a starting controller in R2's normalised 15-D space, with a fixed noise
                  stream so every arm of an experiment that uses the same `noise_seed` sees the same random draws.
"""
from __future__ import annotations

import math
import time
from dataclasses import replace

import mujoco
import numpy as np

from . import locomotion as loc
from . import r2
from .locomotion import DEFAULT_CRITERIA, FALL_HEIGHT_FRAC, FALL_PITCH, FALL_SUSTAIN_SAMPLES, LOG_EVERY, PERTURB, WalkingCriteria
from .forge_pool import InlinePool, is_error
from .morphology import build_model
from .optimize import jsonable
from .phasegait_init import LOWER15, UPPER15, controller_from_vector
from .sandbox import SandboxBody
from .simulate import _geom_lowest

REFERENCE_LEG_M = 0.60          # thigh + shank of the default body; the scale of the length-carrying gates
LAMBDA = r2.T_LAMBDA            # offspring per generation (the "8" of (1+8))
N_PARAMS = 15
ERROR_FITNESS = r2.ERROR_FITNESS


def _load_r2_winner() -> tuple[float, ...]:
    import json
    sel = json.loads(r2.SELECTION.read_text(encoding="utf-8"))
    v = tuple(float(x) for x in sel["winner"]["vector"])
    if len(v) != N_PARAMS:
        raise ValueError(f"R2 winner has {len(v)} parameters, expected {N_PARAMS}")
    return v


R2_WINNER: tuple[float, ...] = _load_r2_winner()   # frozen record, read-only


# ---------------------------------------------------------------------------------------------------------
# criteria
# ---------------------------------------------------------------------------------------------------------
def _leg_lengths(body) -> tuple[float, float]:
    if hasattr(body, "leg"):
        return tuple(sum(body.leg(s)[:2]) for s in "lr")
    return (body.thigh_length + body.shank_length,) * 2


def length_scale(body) -> float:
    return float(sum(_leg_lengths(body)) / 2.0 / REFERENCE_LEG_M)


def creature_criteria(body: SandboxBody) -> WalkingCriteria:
    """Walking gates scaled to the creature: speed and step-advance thresholds grow with mean leg length / 0.60 m.

    Everything else (alternation, flight, slip, saturation, pitch, timing) is dimensionless or a time and is unchanged.
    The default body returns the frozen `DEFAULT_CRITERIA` object itself."""
    s = length_scale(body)
    if s == 1.0:
        return DEFAULT_CRITERIA
    return replace(DEFAULT_CRITERIA, min_speed=DEFAULT_CRITERIA.min_speed * s,
                   min_step_advance=DEFAULT_CRITERIA.min_step_advance * s)


# ---------------------------------------------------------------------------------------------------------
# rollout (copy of locomotion.rollout's loop; the only additions are the optional drawn start and settle window)
# ---------------------------------------------------------------------------------------------------------
def rollout(controller, body: SandboxBody, seed: int, duration: float, *, start: str = "neutral",
            perturb: float = PERTURB, record_poses: bool = False, settle_s: float = 0.0) -> dict:
    """One episode; returns the same 200 Hz trace dict as `locomotion.rollout`.

    start="neutral": the model's zero configuration (identical to `locomotion.rollout`; the drawn pose is ignored).
    start="drawn":   the body's `pose` is added to the seeded perturbation and the creature is placed on the floor from its
                     lowest geom (as `simulate.run_rollout` does). The early-stop fall rule ignores t < settle_s."""
    if start not in ("neutral", "drawn"):
        raise ValueError(f"start must be 'neutral' or 'drawn', got {start!r}")
    body.validate()
    model = build_model(body)
    data = mujoco.MjData(model)
    rng = np.random.default_rng(seed)
    data.qpos[2] = perturb * rng.standard_normal()
    data.qpos[3:9] = perturb * rng.standard_normal(6)
    pose = getattr(body, "pose", None) if start == "drawn" else None
    if pose is not None:
        data.qpos[2] += pose[0]
        data.qpos[3:9] += np.asarray(pose[1:], dtype=float)
    mujoco.mj_forward(model, data)
    foot_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"foot_{s}") for s in "lr"]
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
    lowest = min(data.geom_xpos[i][2] - np.abs(data.geom_xmat[i].reshape(3, 3)[2]) @ model.geom_size[i]
                 for i in foot_ids)
    if pose is not None:  # a bent or tilted start can put a knee or shank lower than the feet
        lowest = min(_geom_lowest(model, data, i) for i in range(model.ngeom) if i != floor_id)
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
        bad = bad + 1 if (z < FALL_HEIGHT_FRAC * z0 or abs(pitch) > FALL_PITCH) and data.time >= settle_s else 0
        if bad >= FALL_SUSTAIN_SAMPLES:
            break
    out = {k: np.asarray(v, dtype=float) for k, v in tr.items()}
    out["meta"] = {"seed": seed, "duration": duration, "mass": mass, "weight": weight, "torque_limit": limit,
                   "controller": controller.name}
    return out


# ---------------------------------------------------------------------------------------------------------
# evaluation of a candidate vector on a creature
# ---------------------------------------------------------------------------------------------------------
def _body(d) -> SandboxBody:
    if isinstance(d, SandboxBody):
        return d
    d = dict(d)
    d["pose"] = tuple(d.get("pose", (0.0,) * 7))
    return SandboxBody(**d)


def eval_vector(vector, body, seeds, duration: float, *, start: str = "neutral", perturb: float = PERTURB) -> dict:
    """Walk one vector on one creature for each seed; compact per-seed outcomes (creature criteria)."""
    b = _body(body)
    crit = creature_criteria(b)
    ctrl = controller_from_vector(vector)
    per = []
    for s in seeds:
        m = loc.compute_metrics(rollout(ctrl, b, s, duration, start=start, perturb=perturb), crit)
        fit = loc.fitness_components(m, crit)["total"]
        per.append({"seed": int(s), "walking": bool(m["walking"]), "fell": bool(m["fell"]), "label": m["label"],
                    "fitness": float(fit), "forward_disp_upright": float(m["forward_disp_upright"]),
                    "valid_steps": int(m["valid_steps"]), "fall_time": m["fall_time"]})
    return {"per_seed": per}


def eval_job(job: dict) -> dict:
    """Pool job: {vector, body, seeds, duration, start?, perturb?} -> {ok, per_seed, wall_s} (errors as values)."""
    t0 = time.perf_counter()
    try:
        res = eval_vector(job["vector"], job["body"], job["seeds"], job["duration"], start=job.get("start", "neutral"),
                          perturb=job.get("perturb", PERTURB))
        return {"ok": True, **res, "wall_s": time.perf_counter() - t0}
    except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "wall_s": time.perf_counter() - t0}


def _record(out: dict, n_seeds: int) -> dict:
    """A r2-style record (so `r2.score_of`/`r2.better` apply) from one job output."""
    if isinstance(out, tuple) and is_error(out):
        out = {"ok": False, "error": out[1]}
    if not out.get("ok"):
        return {"error": out.get("error", "unknown error"), "walking_count": 0, "survival_count": 0,
                "objective": {"mean": ERROR_FITNESS}, "rollouts": n_seeds}
    per = out["per_seed"]
    return {"error": None, "walking_count": int(sum(p["walking"] for p in per)),
            "survival_count": int(sum(not p["fell"] for p in per)),
            "objective": {"mean": float(np.mean([p["fitness"] for p in per]))}, "rollouts": n_seeds}


def _feasible(rec: dict, w0: int) -> bool:
    return r2.is_feasible(rec, w0)


# ---------------------------------------------------------------------------------------------------------
# adaptation: (1 + 8)-ES with the 1/5 success rule, exactly r2's training arm T, on this creature
# ---------------------------------------------------------------------------------------------------------
def adaptation_noise(noise_seed: int, generations: int) -> np.ndarray:
    """All Gaussian draws, shape (generations, 8, 15). A prefix of a longer stream: budgets nest."""
    rng = np.random.default_rng(np.random.SeedSequence([int(noise_seed), 0xADA97]))
    return rng.standard_normal((generations, LAMBDA, N_PARAMS))


def _check_vector(v) -> np.ndarray:
    a = np.asarray(v, dtype=float)
    if a.shape != (N_PARAMS,) or not np.all(np.isfinite(a)):
        raise ValueError(f"init_vector must be {N_PARAMS} finite numbers")
    bad = [i for i in range(N_PARAMS) if not (LOWER15[i] <= a[i] <= UPPER15[i])]
    if bad:
        raise ValueError(f"init_vector entries {bad} are outside the controller bounds (not clipped)")
    return a


def adapt_controller(body: SandboxBody, init_vector, *, budget: int, train_seeds, noise_seed: int, pool=None,
                     progress=None, duration: float = r2.DURATION, start: str = "neutral", perturb: float = PERTURB,
                     init_score: tuple | None = None) -> dict:
    """Adapt the walking controller to `body`: (1+8)-ES in r2's normalised space, score = (walking, surviving, mean fitness).

    Budget accounting is exact: each generation evaluates 8 offspring on every training seed, so
    `generations = budget // (8 * len(train_seeds))` and `es_rollouts = generations * 8 * len(train_seeds) <= budget`.
    The starting vector's own score on the training seeds is also needed (as the parent); evaluating it costs
    `len(train_seeds)` extra rollouts (`init_eval_rollouts`) unless the caller already has it and passes `init_score`
    (walking_count, survival_count, mean_fitness). `rollouts_used` is the true total of physics episodes.
    `progress(done, total)` counts rollouts. Offspring are evaluated per candidate over `pool` (any object with `imap`;
    default inline). The same `noise_seed` always yields the same random draws, whatever the budget."""
    seeds = [int(s) for s in train_seeds]
    if not seeds:
        raise ValueError("train_seeds must not be empty")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
        raise ValueError("budget must be a non-negative integer")
    if not isinstance(noise_seed, int) or isinstance(noise_seed, bool) or noise_seed < 0:
        raise ValueError("noise_seed must be a non-negative integer")
    init = _check_vector(init_vector)
    n = len(seeds)
    gens = budget // (LAMBDA * n)
    pool = pool or InlinePool()
    body_d = _body(body).as_dict()
    total = gens * LAMBDA * n + (0 if init_score is not None else n)
    done = 0

    def job(vec) -> dict:
        return {"vector": [float(x) for x in vec], "body": body_d, "seeds": seeds, "duration": duration,
                "start": start, "perturb": perturb}

    def evaluate(vectors) -> list[dict]:
        nonlocal done
        recs: list[dict | None] = [None] * len(vectors)
        for i, out in pool.imap(eval_job, [job(v) for v in vectors]):
            recs[i] = _record(out, n)
            done += n
            if progress is not None:
                progress(done, total)
        return recs

    t0 = time.perf_counter()
    init_eval = 0
    if init_score is None:
        parent = evaluate([init])[0]
        init_eval = n
    else:
        parent = {"error": None, "walking_count": int(init_score[0]), "survival_count": int(init_score[1]),
                  "objective": {"mean": float(init_score[2])}, "rollouts": 0}
    w0 = parent["walking_count"]
    init_rec = parent
    parent_u = r2.to_u(init)
    parent_vec = init.copy()
    sigma = r2.T_SIGMA0
    noise = adaptation_noise(noise_seed, gens)
    history: list[dict] = []
    for g in range(gens):
        vecs = [r2.from_u(r2.reflect(parent_u + sigma * noise[g, i])) for i in range(LAMBDA)]
        recs = evaluate(vecs)
        succ = [i for i, r in enumerate(recs) if _feasible(r, w0) and r2.better(r, parent)]
        ps = len(succ) / LAMBDA
        parent_before = r2.score_of(parent)
        if succ:
            best_i = max(succ, key=lambda i: (r2.score_of(recs[i]), -i))
            parent, parent_u, parent_vec = recs[best_i], r2.to_u(vecs[best_i]), vecs[best_i]
        history.append({
            "generation": g, "sigma": float(sigma), "success_rate": ps, "parent_score_before": list(parent_before),
            "parent_score_after": list(r2.score_of(parent)),
            "candidates": [{"score": list(r2.score_of(r)), "feasible": _feasible(r, w0), "error": r["error"]} for r in recs],
            "parent_vector": [float(x) for x in parent_vec], "rollouts_cumulative": init_eval + (g + 1) * LAMBDA * n})
        sigma = float(np.clip(sigma * (r2.T_UP if ps > 0.2 else (r2.T_DOWN if ps < 0.2 else 1.0)), *r2.T_SIGMA_RANGE))
    return jsonable({
        "vector": [float(x) for x in parent_vec], "init_vector": [float(x) for x in init], "budget": budget,
        "generations": gens, "lambda": LAMBDA, "es_rollouts": gens * LAMBDA * n, "init_eval_rollouts": init_eval,
        "rollouts_used": gens * LAMBDA * n + init_eval, "train_seeds": seeds, "noise_seed": noise_seed,
        "history": history, "init_score": list(r2.score_of(init_rec)), "best_score": list(r2.score_of(parent)),
        "improved": bool(r2.better(parent, init_rec)), "duration": duration, "wall_s": time.perf_counter() - t0})
