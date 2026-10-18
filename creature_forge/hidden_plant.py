"""Hidden plant: a robot whose physics differs from its nominal design by a hidden deviation (phase 3, HaS scientist).

The engineer (any policy) sees the NOMINAL design: the body dict and the 17-D walking vector it designed. The PLANT that actually
walks is that design plus
  * a deviation: 1-2 primitives of the generic deviation DSL below (damage, wear, mis-calibration, environment), and
  * a reality gap: small per-instance nuisance primitives that no hypothesis models.
The digital TWIN used by the belief engine is the same code with a hypothesised deviation and no reality gap.

Deviation DSL (`PRIMITIVES`). Every primitive is {"kind", "target", "params": {name: value}}; values outside the declared
ranges are rejected with a reason, never clipped. Stages:
  body        segment_length          per-segment/per-side lengths (sandbox per-leg fields), before compilation
  model       actuator_strength       actuator gear (output torque per unit command) per joint group
              joint_damping           joint damping per joint group
              torso_mass              torso mass and inertia scale
              payload                 a point mass at a forward/backward offset on the torso (mass, COM and inertia)
              contact_friction        foot-floor Coulomb friction
  vector      gain_scale              degradation of controller gains (balance feedback, foot placement), factor <= 1
  controller  sensor_delay            latency of the state the controller reads (pitch, joints or all)
              sensor_bias             constant offset on the pitch or a joint angle reading
              clock_scale             controller clock rate error (gait timing runs fast or slow)

Bit-identity: with no primitives the rollout is `physics_probe.rich_rollout` (itself a verbatim copy of `creature_walk.rollout`)
exactly; tested in tests/test_hidden_plant.py. The design body still drives the controller geometry, the torque limit the
controller assumes and the walking criteria (the controller is calibrated for the design, not for the hidden plant).

Pool jobs are module-level functions over plain dicts (spawn-safe): `observe_job`, `walk_job`, `seed_job`.
Hooks for existing code: `observe` (Workbench observe_fn), `plant_cma` (Workbench cma_fn; uses walk_opt.cma_search's
eval_fn), `seed_job` with functools.partial (recovery.assess job_fn), `verify` (full_recovery_v1 on the plant).
"""
from __future__ import annotations

import copy
import functools
import math
import time
from typing import Sequence

import mujoco
import numpy as np

from . import creature_walk as cw
from . import locomotion as loc
from .forge_pool import InlinePool, is_error
from .locomotion import FALL_HEIGHT_FRAC, FALL_PITCH, FALL_SUSTAIN_SAMPLES, LOG_EVERY, PERTURB
from .morphology import JOINTS, build_model
from .physics_probe import CONTACT_MIN_FRAC, PROBE_DOCS, SWING_OFF_FRAC, _leg_length, _median_dicts, summarize

VERSION = "hidden_plant_v1"

_J = {j: i for i, j in enumerate(JOINTS)}
JOINT_GROUPS = {"all": (0, 1, 2, 3, 4, 5), "left": (0, 1, 2), "right": (3, 4, 5), "hips": (0, 3), "knees": (1, 4),
                "ankles": (2, 5), **{j: (i,) for j, i in _J.items()}}
SEGMENTS = ("thigh_l", "thigh_r", "shank_l", "shank_r", "foot_l", "foot_r", "feet", "legs")
SENSOR_SIGNALS = ("pitch", "joints", "all")

PRIMITIVES: dict[str, dict] = {
    "segment_length": {"stage": "body", "targets": SEGMENTS, "params": {"factor": (0.3, 2.0)},
                       "doc": "length of a segment (or both feet / both legs) times factor"},
    "actuator_strength": {"stage": "model", "targets": tuple(JOINT_GROUPS), "params": {"factor": (0.05, 2.0)},
                          "doc": "torque delivered per unit command (actuator gear) times factor"},
    "joint_damping": {"stage": "model", "targets": tuple(JOINT_GROUPS), "params": {"factor": (0.1, 100.0)},
                      "doc": "viscous joint damping times factor (nominal 0.5 N*m*s/rad)"},
    "torso_mass": {"stage": "model", "targets": ("torso",), "params": {"factor": (0.3, 4.0)},
                   "doc": "torso mass and rotational inertia times factor"},
    "payload": {"stage": "model", "targets": ("torso",), "params": {"mass_kg": (0.0, 15.0), "x_m": (-0.3, 0.3)},
                "doc": "point mass rigidly attached to the torso at x_m forward (+) of the torso centre"},
    "contact_friction": {"stage": "model", "targets": ("feet", "foot_l", "foot_r"), "params": {"factor": (0.02, 3.0)},
                         "doc": "foot-floor Coulomb friction times factor"},
    "gain_scale": {"stage": "vector", "targets": ("balance_feedback", "placement"), "params": {"factor": (0.0, 1.0)},
                   "doc": "effective controller gain times factor (balance_gain and pitch_kp, or fp_kd and fp_kv)"},
    "sensor_delay": {"stage": "controller", "targets": SENSOR_SIGNALS, "params": {"seconds": (0.0, 0.15)},
                     "doc": "the controller reads the state from `seconds` ago"},
    "sensor_bias": {"stage": "controller", "targets": ("pitch",) + JOINTS, "params": {"rad": (-0.4, 0.4)},
                    "doc": "constant offset added to a reading (pitch: positive = reads more nose-down than true)"},
    "clock_scale": {"stage": "controller", "targets": ("clock",), "params": {"factor": (0.4, 2.5)},
                    "doc": "the controller's clock runs at factor x real time (gait timing error)"},
}
GAIN_TARGETS = {"balance_feedback": ("balance_gain", "pitch_kp"), "placement": ("fp_kd", "fp_kv")}
MASS_KINDS = ("segment_length", "torso_mass", "payload")
TORSO_GEOM_Z = 0.03          # torso box centre in the torso frame (morphology/sandbox MJCF)


class DeviationError(ValueError):
    """A deviation primitive is malformed or out of range (rejected, never clipped)."""


# ---------------------------------------------------------------------------------------------------------
# DSL validation
# ---------------------------------------------------------------------------------------------------------
def validate_primitive(p) -> dict:
    if not isinstance(p, dict):
        raise DeviationError(f"a primitive must be a dict, got {type(p).__name__}")
    kind = p.get("kind")
    if kind not in PRIMITIVES:
        raise DeviationError(f"unknown primitive kind {kind!r}; known: {sorted(PRIMITIVES)}")
    spec = PRIMITIVES[kind]
    target = p.get("target")
    if target not in spec["targets"]:
        raise DeviationError(f"{kind}: unknown target {target!r}; allowed: {list(spec['targets'])}")
    params = p.get("params")
    if not isinstance(params, dict) or set(params) != set(spec["params"]):
        raise DeviationError(f"{kind}: params must be exactly {sorted(spec['params'])}, got {params!r}")
    out = {}
    for name, (lo, hi) in spec["params"].items():
        v = params[name]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise DeviationError(f"{kind}.{name} must be a finite number, got {v!r}")
        if not (lo <= v <= hi):
            raise DeviationError(f"{kind}.{name}={v:g} outside [{lo:g}, {hi:g}] (rejected, not clipped)")
        out[name] = float(v)
    return {"kind": kind, "target": target, "params": out}


def validate_deviation(prims) -> list[dict]:
    if prims is None:
        return []
    if not isinstance(prims, (list, tuple)):
        raise DeviationError("a deviation is a list of primitives")
    return [validate_primitive(p) for p in prims]


def normalize_plant(plant) -> dict:
    """{"deviation": [...], "gap": [...]} with validated primitives; None or {} is the nominal (unchanged) robot."""
    plant = plant or {}
    unknown = set(plant) - {"deviation", "gap", "label"}
    if unknown:
        raise DeviationError(f"unknown plant fields {sorted(unknown)}")
    return {"deviation": validate_deviation(plant.get("deviation")), "gap": validate_deviation(plant.get("gap"))}


def _prims(plant) -> list[dict]:
    p = normalize_plant(plant)
    return p["gap"] + p["deviation"]


# ---------------------------------------------------------------------------------------------------------
# applying primitives
# ---------------------------------------------------------------------------------------------------------
def plant_body(design_body: dict, prims: Sequence[dict]) -> dict:
    """Body-stage primitives -> a sandbox body dict with explicit per-leg lengths when any segment changes."""
    seg = [p for p in prims if p["kind"] == "segment_length"]
    if not seg:
        return design_body
    b = dict(design_body)
    lengths = {"thigh_l": b["thigh_length"], "shank_l": b["shank_length"], "foot_l": b["foot_length"],
               "thigh_r": b.get("thigh_length_r") or b["thigh_length"], "shank_r": b.get("shank_length_r") or b["shank_length"],
               "foot_r": b.get("foot_length_r") or b["foot_length"]}
    groups = {"feet": ("foot_l", "foot_r"), "legs": ("thigh_l", "thigh_r", "shank_l", "shank_r")}
    for p in seg:
        for k in groups.get(p["target"], (p["target"],)):
            lengths[k] *= p["params"]["factor"]
    b.update(thigh_length=lengths["thigh_l"], shank_length=lengths["shank_l"], foot_length=lengths["foot_l"],
             thigh_length_r=lengths["thigh_r"], shank_length_r=lengths["shank_r"], foot_length_r=lengths["foot_r"])
    return b


def plant_vector(vector, prims: Sequence[dict]) -> list[float]:
    gains = [p for p in prims if p["kind"] == "gain_scale"]
    v = [float(x) for x in vector]
    if not gains:
        return v
    from .fault_bench import ALL_NAMES
    for p in gains:
        for name in GAIN_TARGETS[p["target"]]:
            v[ALL_NAMES.index(name)] *= p["params"]["factor"]
    return v


def apply_model(model: mujoco.MjModel, prims: Sequence[dict]) -> bool:
    """Model-stage primitives, in place. Returns True if anything changed (then mj_setConst must run)."""
    changed = False
    torso = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
    for p in prims:
        k, f = p["kind"], p["params"]
        if k == "actuator_strength":
            for i in JOINT_GROUPS[p["target"]]:
                model.actuator_gear[i, 0] *= f["factor"]
        elif k == "joint_damping":
            for i in JOINT_GROUPS[p["target"]]:
                model.dof_damping[3 + i] *= f["factor"]
        elif k == "torso_mass":
            model.body_mass[torso] *= f["factor"]
            model.body_inertia[torso] *= f["factor"]
        elif k == "payload":
            m = f["mass_kg"]
            if m <= 0.0:
                continue
            if not np.allclose(model.body_iquat[torso], [1.0, 0.0, 0.0, 0.0]):
                raise DeviationError("payload needs an axis-aligned torso inertia frame")
            M, c, inertia = float(model.body_mass[torso]), model.body_ipos[torso].copy(), model.body_inertia[torso].copy()
            pnt = np.array([f["x_m"], 0.0, TORSO_GEOM_Z])
            M2 = M + m
            c2 = (M * c + m * pnt) / M2
            dc, dp = c - c2, pnt - c2
            par = lambda d: np.array([d[1] ** 2 + d[2] ** 2, d[0] ** 2 + d[2] ** 2, d[0] ** 2 + d[1] ** 2])  # noqa: E731
            model.body_mass[torso] = M2
            model.body_ipos[torso] = c2
            model.body_inertia[torso] = inertia + M * par(dc) + m * par(dp)
        elif k == "contact_friction":
            for side in (("l", "r") if p["target"] == "feet" else (p["target"][-1],)):
                g = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"foot_{side}")
                model.geom_friction[g, 0] *= f["factor"]
        else:
            continue
        changed = True
    return changed


class PlantController:
    """Wraps a walking controller with controller-stage primitives: sensor latency and bias, clock rate.

    The wrapped controller is called once per physics step (1 kHz) exactly as in the rollout; it receives the delayed and
    biased readings and a scaled clock. Attribute access falls through to the wrapped controller (e.g. `.p`, `.name`)."""

    def __init__(self, inner, prims: Sequence[dict], timestep: float):
        self.inner = inner
        self.clock = 1.0
        self.pitch_bias = 0.0
        self.joint_bias = np.zeros(6)
        self.delay = {"pitch": 0, "joints": 0}
        for p in prims:
            k, f = p["kind"], p["params"]
            if k == "clock_scale":
                self.clock *= f["factor"]
            elif k == "sensor_bias":
                if p["target"] == "pitch":
                    self.pitch_bias += f["rad"]
                else:
                    self.joint_bias[_J[p["target"]]] += f["rad"]
            elif k == "sensor_delay":
                n = int(round(f["seconds"] / timestep))
                for sig in (("pitch", "joints") if p["target"] == "all" else (p["target"],)):
                    self.delay[sig] = max(self.delay[sig], n)
        self._buf: list = []

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def reset(self, torque_limit: float, weight_n: float) -> None:
        self._buf = []
        self.inner.reset(torque_limit, weight_n)

    def sense(self, t: float, forces) -> None:
        self.inner.sense(t * self.clock, forces)

    def torque(self, t: float, pitch: float, pitch_rate: float, q, qd):
        self._buf.append((float(pitch), float(pitch_rate), np.array(q, dtype=float), np.array(qd, dtype=float)))
        keep = max(self.delay.values()) + 1
        if len(self._buf) > keep:
            del self._buf[: len(self._buf) - keep]
        n = len(self._buf)
        dp, dq = self._buf[max(0, n - 1 - self.delay["pitch"])], self._buf[max(0, n - 1 - self.delay["joints"])]
        return self.inner.torque(t * self.clock, dp[0] + self.pitch_bias, dp[1], dq[2] + self.joint_bias, dq[3])


# ---------------------------------------------------------------------------------------------------------
# rollout
# ---------------------------------------------------------------------------------------------------------
def plant_rollout(plant, body, vector, seed: int, *, duration: float = 10.0, perturb: float | None = None,
                  friction_factor: float | None = None, rich: bool = True, settle_s: float = 0.0) -> dict:
    """Walk the design (`body`, `vector`) on the hidden plant; returns the `physics_probe.rich_rollout` trace (rich=True) or the
    `creature_walk.rollout` keys only (rich=False). Same seed handling, conditions and early-stop rule (the fall rule ignores
    t < settle_s, as `creature_walk.rollout`; challenges pass spec.settle_s, the CMA and probe paths 0); with an empty plant
    the dynamics are bit-identical to both. Neutral start only."""
    from .phasegait_init import controller_from_vector
    prims = _prims(plant)
    b = cw._body(body)
    if friction_factor is not None:
        from .arena import _body_with_friction
        b = cw._body(_body_with_friction(b.as_dict(), float(friction_factor))[0])
    pb = cw._body(plant_body(b.as_dict(), prims))
    controller = controller_from_vector(plant_vector(vector, prims), body=b)
    perturb = PERTURB if perturb is None else perturb

    # ---- copy of physics_probe.rich_rollout (setup), plant model ----
    b.validate()
    pb.validate()
    model = build_model(pb)
    data = mujoco.MjData(model)
    if apply_model(model, prims):
        mujoco.mj_setConst(model, data)
    if any(p["stage"] == "controller" for p in (PRIMITIVES[q["kind"]] for q in prims)):
        controller = PlantController(controller, [q for q in prims if PRIMITIVES[q["kind"]]["stage"] == "controller"],
                                     model.opt.timestep)
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
    ctrl_weight = weight
    if any(q["kind"] in MASS_KINDS for q in prims):      # the controller is calibrated for the design's weight
        ctrl_weight = float(build_model(b).body_mass.sum()) * 9.81
    controller.reset(b.torque_limit, ctrl_weight)
    limit = b.torque_limit
    kp = getattr(getattr(controller, "p", None), "kp", None)
    keys = ("t", "x", "z", "pitch", "q", "qd", "tau", "demand", "force", "slip", "foot_x", "foot_z", "body_contact")
    extra = ("com", "com_vel", "angmom_y", "pitch_rate", "ft_x", "util", "contact_x", "cop_x", "sup_min", "sup_max",
             "saturated", "tracking_error", "foot_low", "swing_clear") if rich else ()
    tr: dict[str, list] = {k: [] for k in keys + extra}
    vel6 = np.zeros(6)
    f6 = np.zeros(6)
    steps = int(round(duration / model.opt.timestep))
    demand = np.zeros(6)
    z0 = None
    bad = 0
    nan = float("nan")
    contact_min = CONTACT_MIN_FRAC * weight
    off_thr = SWING_OFF_FRAC * weight
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
        ft_x = [0.0, 0.0]
        mu_foot: list = [None, None]
        pts: list[tuple[float, float]] = []
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
                    v = vel6[3:] + np.cross(vel6[:3], con.pos - data.geom_xpos[other])
                    slip[k] += f6[0] * abs(v[0])
                    cpos[k] += f6[0] * con.pos
                    if rich:
                        fw = np.asarray(con.frame, dtype=float).reshape(3, 3).T @ f6[:3]
                        ft_x[k] += float(fw[0] if other == g2 else -fw[0])
                        if f6[0] > contact_min:
                            pts.append((float(con.pos[0]), float(f6[0])))
                            if mu_foot[k] is None:
                                mu_foot[k] = float(con.friction[0])
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
        tr["tau"].append(data.actuator_force * model.actuator_gear[:, 0])   # delivered joint torque (gear 1: identical)
        tr["demand"].append(np.array(demand, dtype=float))
        tr["force"].append(force)
        tr["slip"].append(slip)
        tr["foot_x"].append([float(data.geom_xpos[i][0]) for i in foot_ids])
        tr["foot_z"].append([float(data.geom_xpos[i][2]) for i in foot_ids])
        tr["body_contact"].append(body_contact)
        if rich:
            mujoco.mj_subtreeVel(model, data)
            tr["com"].append(data.subtree_com[0].copy())
            tr["com_vel"].append(data.subtree_linvel[0].copy())
            tr["angmom_y"].append(float(data.subtree_angmom[0][1]))
            tr["pitch_rate"].append(float(data.qvel[2]))
            tr["ft_x"].append(ft_x)
            tr["util"].append([abs(ft_x[k]) / (mu_foot[k] * force[k]) if mu_foot[k] and force[k] > contact_min else nan
                               for k in (0, 1)])
            tr["contact_x"].append([float(cpos[k][0]) if force[k] > 0.0 else nan for k in (0, 1)])
            allf = force[0] + force[1]
            tr["cop_x"].append(float((force[0] * cpos[0][0] + force[1] * cpos[1][0]) / allf) if allf > 0.0 else nan)
            tr["sup_min"].append(min(p[0] for p in pts) if pts else nan)
            tr["sup_max"].append(max(p[0] for p in pts) if pts else nan)
            tr["saturated"].append(np.abs(np.asarray(demand, dtype=float)) >= 0.99 * limit)
            tr["tracking_error"].append(np.asarray(demand, dtype=float) / kp if kp else np.full(6, nan))
            low = [float(data.geom_xpos[i][2] - np.abs(data.geom_xmat[i].reshape(3, 3)[2]) @ model.geom_size[i])
                   for i in foot_ids]
            tr["foot_low"].append(low)
            free = [low[k] for k in (0, 1) if force[k] <= off_thr]
            tr["swing_clear"].append(min(free) if free else nan)
        bad = bad + 1 if (z < FALL_HEIGHT_FRAC * z0 or abs(pitch) > FALL_PITCH) and data.time >= settle_s else 0
        if bad >= FALL_SUSTAIN_SAMPLES:
            break
    out = {k: np.asarray(v, dtype=float) for k, v in tr.items()}
    if rich:
        out["saturated"] = np.asarray(tr["saturated"], dtype=bool).reshape(-1, 6)
    out["meta"] = {"seed": seed, "duration": duration, "mass": mass, "weight": weight, "torque_limit": limit,
                   "controller": controller.name, "foot_friction": float(b.foot_friction), "leg_length": _leg_length(b),
                   "has_kp": kp is not None, "plant": VERSION, "n_primitives": len(prims)}
    return out


# ---------------------------------------------------------------------------------------------------------
# pool jobs and hooks
# ---------------------------------------------------------------------------------------------------------
def _conditions(seeds, variation) -> list[dict]:
    """Per-seed walk conditions exactly as walk_opt.cma_search / physics_probe.observe build them."""
    from . import arena, challenges
    out = []
    for s in seeds:
        spec = challenges.default_spec("walk", [int(s)])
        if variation:
            c = arena._condition(int(s), spec, dict(variation))
            out.append({"perturb": c["perturb"], "friction_factor": c["friction_factor"], "start": spec.start})
        else:
            out.append({"perturb": spec.perturb, "friction_factor": None, "start": spec.start})
    return out


def observe_job(job: dict) -> dict:
    """{vector, body, seed, duration, perturb, friction_factor, plant} -> {ok, summary, wall_s} (as physics_probe.observe_job)."""
    t0 = time.perf_counter()
    try:
        body = cw._body(job["body"])
        tr = plant_rollout(job.get("plant"), body, job["vector"], job["seed"], duration=job["duration"],
                           perturb=job.get("perturb"), friction_factor=job.get("friction_factor"))
        if job.get("friction_factor") is not None:
            from .arena import _body_with_friction
            body = cw._body(_body_with_friction(body.as_dict(), float(job["friction_factor"]))[0])
        summ = summarize(tr, body)
        m = loc.compute_metrics(tr, cw.creature_criteria(body))
        summ.update({"seed": int(job["seed"]), "walking": bool(m["walking"]), "fell": bool(m["fell"]), "label": m["label"]})
        return {"ok": True, "summary": summ, "wall_s": time.perf_counter() - t0}
    except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "wall_s": time.perf_counter() - t0}


def observe(body, vector, seeds, *, plant=None, variation=None, duration: float = 10.0, pool=None,
            friction_mult: float = 1.0, mechanisms=()) -> dict:
    """`physics_probe.observe` on the plant (same output shape). `friction_mult` scales the per-seed friction condition (a
    test-surface condition: e.g. 3.0 = a high-grip floor)."""
    if mechanisms:
        raise ValueError("mechanism controllers are not supported on the hidden plant")
    from .arena import VARIATION_PRESET
    variation = VARIATION_PRESET if variation is None else variation
    b = cw._body(body)
    body_d = b.as_dict()
    if "pose" in body_d:
        body_d["pose"] = list(body_d["pose"])
    seeds = [int(s) for s in seeds]
    plant = normalize_plant(plant)
    jobs = []
    for s, c in zip(seeds, _conditions(seeds, variation)):
        ff = c["friction_factor"]
        if friction_mult != 1.0:
            ff = (1.0 if ff is None else ff) * float(friction_mult)
        jobs.append({"vector": [float(x) for x in vector], "body": body_d, "seed": s, "duration": duration,
                     "perturb": c["perturb"], "friction_factor": ff, "plant": plant})
    pool = pool or InlinePool()
    results: list = [None] * len(jobs)
    for i, out in pool.imap(observe_job, jobs):
        results[i] = out
    per, errors = [], []
    for s, out in zip(seeds, results):
        if isinstance(out, tuple) and is_error(out):
            errors.append({"seed": s, "error": out[1]})
        elif not out.get("ok"):
            errors.append({"seed": s, "error": out.get("error", "unknown error")})
        else:
            per.append(out["summary"])
    scalar_keys = [k for k in PROBE_DOCS if k != "pre_fall" and "." not in k]
    pf_keys = [k[len("pre_fall."):] for k in PROBE_DOCS if k.startswith("pre_fall.")]
    pfs = [p["pre_fall"] for p in per if p.get("pre_fall")]
    return {"per_seed": per, "median": _median_dicts(per, scalar_keys),
            "pre_fall_median": _median_dicts(pfs, pf_keys) if pfs else None, "rollouts": len(seeds),
            "n_fell": int(sum(p["fell"] for p in per)), "n_walking": int(sum(p["walking"] for p in per)), "errors": errors}


def walk_job(job: dict) -> dict:
    """{vector, body, seed, duration, perturb, friction_factor, plant} -> {ok, walking, fell, fitness, ...} (cw.eval_vector row)."""
    t0 = time.perf_counter()
    try:
        b = cw._body(job["body"])
        tr = plant_rollout(job.get("plant"), b, job["vector"], job["seed"], duration=job["duration"],
                           perturb=job.get("perturb"), friction_factor=job.get("friction_factor"), rich=False)
        if job.get("friction_factor") is not None:
            from .arena import _body_with_friction
            b = cw._body(_body_with_friction(b.as_dict(), float(job["friction_factor"]))[0])
        crit = cw.creature_criteria(b)
        m = loc.compute_metrics(tr, crit)
        fit = loc.fitness_components(m, crit)["total"]
        return {"ok": True, "seed": int(job["seed"]), "walking": bool(m["walking"]), "fell": bool(m["fell"]),
                "label": m["label"], "fitness": float(fit), "forward_disp_upright": float(m["forward_disp_upright"]),
                "valid_steps": int(m["valid_steps"]), "fall_time": m["fall_time"], "wall_s": time.perf_counter() - t0}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "wall_s": time.perf_counter() - t0}


def walk_seeds(plant, body, vector, seeds, *, variation=None, duration: float = 10.0, pool=None) -> list[dict]:
    """One walk_job per seed under the per-seed conditions; error rows stay as {"ok": False, ...}."""
    from .arena import VARIATION_PRESET
    variation = VARIATION_PRESET if variation is None else variation
    plant = normalize_plant(plant)
    jobs = []
    for s, c in zip(seeds, _conditions(seeds, variation)):
        jobs.append({"vector": [float(x) for x in vector], "body": dict(body), "seed": int(s), "duration": duration,
                     "perturb": c["perturb"], "friction_factor": c["friction_factor"], "plant": plant})
    pool = pool or InlinePool()
    out: list = [None] * len(jobs)
    for i, r in pool.imap(walk_job, jobs):
        out[i] = {"ok": False, "error": r[1]} if isinstance(r, tuple) and is_error(r) else r
    return out


def make_eval_fn(plant, train_seeds, *, variation=None, duration: float = 10.0, pool=None):
    """An `eval_fn` for walk_opt.cma_search: candidates [(body_dict, vector)] -> records, evaluated on the plant."""
    from .arena import VARIATION_PRESET
    from . import r2
    variation = VARIATION_PRESET if variation is None else variation
    seeds = [int(s) for s in train_seeds]
    conds = _conditions(seeds, variation)
    plant = normalize_plant(plant)
    pool = pool or InlinePool()

    def eval_fn(cands):
        jobs = []
        for b, v in cands:
            for s, c in zip(seeds, conds):
                jobs.append({"vector": [float(x) for x in v], "body": dict(b), "seed": s, "duration": duration,
                             "perturb": c["perturb"], "friction_factor": c["friction_factor"], "plant": plant})
        res: list = [None] * len(jobs)
        for i, r in pool.imap(walk_job, jobs):
            res[i] = {"ok": False, "error": r[1]} if isinstance(r, tuple) and is_error(r) else r
        recs = []
        S = len(seeds)
        for ci in range(len(cands)):
            row = res[ci * S:(ci + 1) * S]
            fits = [r2.ERROR_FITNESS if not r.get("ok") or not math.isfinite(r["fitness"]) else r["fitness"] for r in row]
            errs = [f"seed {seeds[k]}: {r['error']}" for k, r in enumerate(row) if not r.get("ok")]
            recs.append({"walking_count": sum(1 for r in row if r.get("ok") and r["walking"]),
                         "survival_count": sum(1 for r in row if r.get("ok") and not r["fell"]),
                         "mean_fitness": float(np.mean(fits)), "error": "; ".join(errs) if errs else None})
        return recs

    return eval_fn


def plant_cma(body, init_vector, space, *, plant=None, budget: int, train_seeds, noise_seed: int, pool=None,
              variation=None, **kw) -> dict:
    """walk_opt.cma_search with every candidate evaluated on the plant (a Workbench `cma_fn`)."""
    from . import walk_opt as wo
    from .arena import VARIATION_PRESET
    variation = VARIATION_PRESET if variation is None else variation
    duration = kw.pop("duration", 10.0)
    fn = make_eval_fn(plant, train_seeds, variation=variation, duration=duration, pool=pool)
    return wo.cma_search(body, init_vector, space, budget=budget, train_seeds=train_seeds, noise_seed=noise_seed, pool=pool,
                         variation=variation, duration=duration, eval_fn=fn, **kw)


def seed_job(job: dict, plant=None) -> dict:
    """`challenges.seed_job` for walk challenges on the plant (recovery.assess job_fn via functools.partial)."""
    from .challenges import WALK_KEEP, ChallengeSpec, SeedResult, _as_body, walk_vector
    from .optimize import jsonable
    spec = ChallengeSpec.from_dict(job["spec"])
    seed = int(job["seed"])
    try:
        if spec.kind != "walk" or spec.start != "neutral":
            raise ValueError(f"the hidden plant runs neutral-start walk challenges only, got {spec.kind!r}/{spec.start!r}")
        if (job["controllers"] or {}).get("walk", {}).get("mechanisms"):
            raise ValueError("mechanism controllers are not supported on the hidden plant")
        body = _as_body(job["body"])
        vec = walk_vector(job["controllers"])
        crit = cw.creature_criteria(body)
        tr = plant_rollout(plant, body.as_dict(), vec, seed, duration=spec.duration, perturb=spec.perturb, rich=False,
                           settle_s=spec.settle_s)
        for k in ("x", "z", "pitch", "tau"):
            if not np.all(np.isfinite(tr[k])):
                raise ValueError(f"the simulation became numerically unstable (non-finite {k})")
        m = loc.compute_metrics(tr, crit)
        fell_early = bool(m["fell"]) and (m["fall_time"] or 0.0) < 1.0
        score = 0.0 if (fell_early or m["valid_steps"] < 1) else max(0.0, float(m["forward_disp_upright"]))
        outcome = "PASS" if m["walking"] else ("FAIL" if m["fell"] else "POOR")
        metrics = {k: m[k] for k in WALK_KEEP}
        return jsonable(SeedResult(seed, outcome, score, metrics, [], 1).as_dict())
    except Exception as exc:  # noqa: BLE001 - reported as ERROR with its message
        msg = f"{type(exc).__name__}: {exc}"
        return SeedResult(seed, "ERROR", 0.0, {"error": msg}, [], 0, error=msg).as_dict()


def verify(plant, original: dict, candidate: dict, validate_seeds, confirm_seeds, *, pool=None) -> dict:
    """`full_recovery_v1` (recovery.assess, unchanged) with every rollout on the plant. original/candidate = {"body","vector"}
    designs: the original is the faulty robot's nominal design running on the same plant."""
    from . import recovery
    return recovery.assess(copy.deepcopy(original), copy.deepcopy(candidate), validate_seeds, confirm_seeds, pool=pool,
                           job_fn=functools.partial(seed_job, plant=normalize_plant(plant)))
