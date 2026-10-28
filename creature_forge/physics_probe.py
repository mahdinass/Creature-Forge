"""Physics measurement instruments for the causal engineer: a rich walking rollout and compact, documented summaries.

An investigator (a language model) must explain WHY a planar biped fails, so it needs measurements that mean something
physically, not just "it fell". This module adds nothing to the dynamics: `rich_rollout` is a line-for-line copy of the
step loop of `creature_walk.rollout` (same model build, initial state, controller calls, control clipping, fall early-stop
rule); every extra quantity is read from MuJoCo state AFTER the step and never written back. `tests/test_physics_probe.py`
proves bit-identity of x / z / pitch / q / qd / tau / demand against `creature_walk.rollout`.

Conventions (all measurements; none asserts a cause)
  * x is forward, z is up, the model is planar (x-z plane, hinges about +y), SI units, g = 9.81;
  * pitch is the torso hinge angle about +y: POSITIVE = FORWARD LEAN (rotating +z toward +x), pitch rate its time derivative;
    angular momentum about +y has the same sign (positive = pitching forward);
  * joint order of q / tau / demand / saturated / tracking_error is (hip, knee, ankle) of the left, then the right leg;
  * "L" is the mean leg length (thigh + shank, averaged over both legs), `creature_walk._leg_lengths`;
  * the "upright period" is samples 0..iu, iu = first sample of a sustained fall (height < 0.5 x initial or |pitch| > 1 rad
    for 20 samples, `locomotion.FALL_*`) or the last sample when no fall; time_upright / fall_time use `compute_metrics` rules;
  * "loaded" for step / friction statistics = the debounced contact of `contact.replay`, ignoring the first
    `DEFAULT_CRITERIA.skip_after_touchdown_s` after each touchdown (the impact), exactly as `compute_metrics` does for slip;
  * every summary value is a finite float or None (None = undefined, e.g. no loaded contact, no fall).

Rich trace (200 Hz, arrays of length n; the first 13 keys are exactly those of `creature_walk.rollout`)
  t, x, z, pitch, q, qd, tau (applied actuator force), demand (controller output before clipping), force (per foot
  normal force, N), slip (force-weighted horizontal contact-point speed, m/s), foot_x, foot_z (foot-geom centre), body_contact,
  plus
  com (n,3) whole-body centre of mass `subtree_com[0]`; com_vel (n,3) its velocity `subtree_linvel[0]` after `mj_subtreeVel`;
  angmom_y (n) y-component of angular momentum about the COM `subtree_angmom[0]` (kg m^2/s);
  pitch_rate (n) = qvel[2];
  ft_x (n,2) signed world-x tangential (friction) force on each foot, summed over its contacts (N; + = pushes the foot forward);
  util (n,2) foot friction utilisation |sum of tangential force (x)| / (mu * sum of normal force) of each foot, mu = the contact's
  sliding friction coefficient (the planar model has no y-slip, so the tangential force is the x component); 1 = the foot's resultant
  is on the friction cone, NaN when the foot's normal force is < 0.1 % of weight;
  contact_x (n,2) force-weighted contact-point x of each foot (NaN if unloaded); cop_x (n) centre of pressure x over both feet (NaN in flight);
  sup_min / sup_max (n) x extent of all foot contact points carrying > 0.1 % of weight (NaN if none) = the support interval;
  saturated (n,6) bool |demand| >= 0.99 x torque limit (same rule as `compute_metrics`);
  tracking_error (n,6) demand / kp (rad), a PROXY: the controller's PD law is tau = kp*(ref - q) - kd*qd (+ stance feedback),
  so demand/kp equals the reference error only when the damping and feedback terms vanish; NaN if the controller has no `p.kp`;
  foot_low (n,2) height of the lowest point of each foot geom above the floor (m); swing_clear (n) the lowest of the unloaded
  feet (force <= 2 % of weight), NaN if both feet are loaded.
"""
from __future__ import annotations

import math
import time

import mujoco
import numpy as np

from . import creature_walk as cw
from . import locomotion as loc
from .arena import VARIATION_PRESET
from .contact import ContactConfig, SAMPLE_DT, replay
from .failures import _first_sustained
from .forge_pool import InlinePool, is_error
from .locomotion import DEFAULT_CRITERIA, FALL_HEIGHT_FRAC, FALL_PITCH, FALL_SUSTAIN_SAMPLES, LOG_EVERY, PERTURB
from .morphology import build_model
from .simulate import _geom_lowest

G = 9.81
PRE_FALL_S = 0.5            # window before fall onset
END_WINDOW_S = 0.2          # "end of upright" values average this much time before the last upright sample
CONTACT_MIN_FRAC = 1e-3     # a contact point counts for support / friction above this fraction of body weight
SWING_OFF_FRAC = 0.02       # a foot is unloaded (swinging) below this fraction of weight
JOINT_TYPES = ("hip", "knee", "ankle")

# ---------------------------------------------------------------------------------------------------------
# documentation of every summary key
# ---------------------------------------------------------------------------------------------------------
_SERIES_DOCS = {
    "com_vx": ("whole-body COM forward velocity", "m/s", "positive = moving forward"),
    "com_height_over_L": ("whole-body COM height above the floor divided by L", "dimensionless", "positive up"),
    "com_ahead_of_cop_over_L": ("(x_com - x_cop)/L, COM horizontal position relative to the centre of pressure of the "
                                "loaded feet, averaged over samples with ground contact", "dimensionless",
                                "positive = COM ahead of the CoP (forward-toppling moment)"),
    "capture_margin_over_L": ("capture-point margin to the support interval / L, x_cp = x_com + v_com/omega, "
                              "omega = sqrt(g/z_com); distance from x_cp to the nearest edge of the support interval "
                              "[min, max] x of loaded foot contact points", "dimensionless",
                              "positive = capture point inside the support interval, negative = outside (either side)"),
    "cp_ahead_of_front_edge_over_L": ("(x_cp - front edge of the support interval)/L, the signed overshoot of the capture "
                                      "point beyond the toe side", "dimensionless",
                                      "positive = capture point beyond the front edge (forward instability)"),
    "angmom_norm": ("angular momentum about the COM (y component) / (m*L*sqrt(g*L))", "dimensionless",
                    "positive = rotating forward (about +y, nose down)"),
    "pitch": ("torso pitch", "rad", "positive = forward lean"),
    "pitch_rate": ("torso pitch rate", "rad/s", "positive = leaning further forward"),
}
SERIES = tuple(_SERIES_DOCS)

PROBE_DOCS: dict[str, str] = {
    "leg_length_m": "L, mean over both legs of thigh + shank length (m); the length used to normalise.",
    "fall_time": "Time of the first sample of a sustained fall (s, the frozen compute_metrics definition); None if no fall.",
    "fall_direction": "+1 forward fall (pitch beyond 0.3 rad at detection is positive, else the torso moved forward), -1 backward, 0 no fall.",
    "time_upright": "Seconds the creature stayed upright (fall onset, or the episode length if it never fell) (s).",
    "capture_inside_fraction": "Fraction of upright samples with a support interval in which the capture point lies inside it (margin >= 0); dimensionless. Ordinary walking steps with the capture point outside the stance foot, so it is low for healthy gaits at speed.",
    "slip_fraction": "Fraction of loaded foot-time (debounced, after the impact window) with horizontal contact-point speed > 0.1 m/s; dimensionless in [0, 1].",
    "max_friction_utilisation": "Maximum over loaded foot-samples of |Ft|/(mu*Fn) of the foot (summed contacts); 1 = on the friction cone, dimensionless.",
    "friction_utilisation_p95": "95th percentile over loaded foot-samples of |Ft|/(mu*Fn) of the foot; dimensionless.",
    "step_freq_hz": "Debounced touchdowns of either foot per second over the upright period (Hz); None with fewer than 2 touchdowns.",
    "step_length_over_L": "Mean |x distance between a touchdown foot and the other foot's previous touchdown| over alternating touchdowns / L; dimensionless.",
    "double_support_fraction": "Fraction of upright samples with both feet debounced-loaded; dimensionless.",
    "flight_fraction": "Fraction of upright samples with neither foot debounced-loaded; dimensionless.",
    "swing_clearance_min_over_L": "Lowest height of an unloaded foot's lowest point over the upright period / L; ~0 at every touchdown and liftoff, so see swing_peak_clearance_min_over_L for dragging.",
    "swing_peak_clearance_min_over_L": "Over complete swing phases (a foot unloaded between liftoff and touchdown), the minimum of the peak foot-clearance reached in the phase / L; small = toe drag or shuffling.",
    "swing_peak_clearance_mean_over_L": "Mean over complete swing phases of the peak foot clearance / L.",
    "n_swing_phases": "Number of complete swing phases in the upright period (count).",
    **{f"saturation_frac_{j}": f"Fraction of upright samples in which a {j} torque demand (either leg) reaches 0.99 x the torque limit; dimensionless."
       for j in JOINT_TYPES},
    **{f"tracking_error_{j}": f"Mean over the upright period and both legs of |demand|/kp for the {j} joint (rad): a proxy for the "
                              f"joint reference tracking error (exact only if damping and feedback terms vanish); None if unavailable."
       for j in JOINT_TYPES},
    "pre_fall": "None if the creature did not fall, else a dict of the quantities named pre_fall.<key>, averaged over the 0.5 s before fall onset.",
}
for _k, (_what, _unit, _sign) in _SERIES_DOCS.items():
    PROBE_DOCS[f"{_k}_mean"] = f"Mean over the upright period of the {_what} ({_unit}); {_sign}."
    PROBE_DOCS[f"{_k}_end"] = f"Mean over the last {END_WINDOW_S:g} s of the upright period of the {_what} ({_unit}); {_sign}."
    PROBE_DOCS[f"{_k}_slope"] = f"Least-squares slope against time over the upright period of the {_what} ({_unit} per s); positive = increasing."
    PROBE_DOCS[f"pre_fall.{_k}"] = f"Mean over the 0.5 s before fall onset of the {_what} ({_unit}); {_sign}."
PROBE_DOCS.update({
    "pre_fall.slip_fraction": "Slip fraction (as slip_fraction) restricted to the 0.5 s before fall onset.",
    "pre_fall.max_friction_utilisation": "Maximum friction utilisation (as max_friction_utilisation) in the 0.5 s before fall onset.",
    "pre_fall.saturation_frac_hip": "Hip saturation fraction in the 0.5 s before fall onset.",
    "pre_fall.saturation_frac_knee": "Knee saturation fraction in the 0.5 s before fall onset.",
    "pre_fall.saturation_frac_ankle": "Ankle saturation fraction in the 0.5 s before fall onset.",
    "pre_fall.window_s": "Length of the pre-fall window actually available (s), at most 0.5.",
})


# ---------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------
def _num(v) -> float | None:
    if v is None:
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def _nanmean(a) -> float | None:
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    return _num(a.mean()) if len(a) else None


def _slope(t, y) -> float | None:
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(y) & np.isfinite(t)
    t, y = t[m], y[m]
    if len(t) < 2:
        return None
    dt = t - t.mean()
    den = float((dt * dt).sum())
    if den <= 0.0:
        return None
    return _num((dt * (y - y.mean())).sum() / den)


def _leg_length(body) -> float:
    return float(sum(cw._leg_lengths(body)) / 2.0)


# ---------------------------------------------------------------------------------------------------------
# rich rollout
# ---------------------------------------------------------------------------------------------------------
def rich_rollout(body, vector, seed: int, *, duration: float = 10.0, start: str = "neutral", perturb: float | None = None,
                 mechanisms=(), friction_factor: float | None = None) -> dict:
    """Walk `vector` on `body` and return the 200 Hz rich trace documented in the module docstring.

    The dynamics are those of `creature_walk.rollout` (loop copied verbatim; extras are read-only). `body` is a SandboxBody
    or a body dict; `vector` is 15-D (or 17-D foot placement, or 15 + gains with `mechanisms`); `perturb=None` uses
    `locomotion.PERTURB`; `friction_factor` scales the foot friction as `arena._body_with_friction` does (a test condition;
    the value used is in meta["foot_friction"])."""
    from .mechanisms import controller_from_spec
    from .phasegait_init import controller_from_vector
    if start not in ("neutral", "drawn"):
        raise ValueError(f"start must be 'neutral' or 'drawn', got {start!r}")
    b = cw._body(body)
    if friction_factor is not None:
        from .arena import _body_with_friction
        b = cw._body(_body_with_friction(b.as_dict(), float(friction_factor))[0])
    controller = controller_from_spec(vector, mechanisms, body=b) if mechanisms else controller_from_vector(vector, body=b)
    perturb = PERTURB if perturb is None else perturb
    settle_s = 0.0

    # ---- copy of creature_walk.rollout (setup) ----
    b.validate()
    model = build_model(b)
    data = mujoco.MjData(model)
    rng = np.random.default_rng(seed)
    data.qpos[2] = perturb * rng.standard_normal()
    data.qpos[3:9] = perturb * rng.standard_normal(6)
    pose = getattr(b, "pose", None) if start == "drawn" else None
    if pose is not None:
        data.qpos[2] += pose[0]
        data.qpos[3:9] += np.asarray(pose[1:], dtype=float)
    mujoco.mj_forward(model, data)
    foot_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"foot_{s}") for s in "lr"]
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
    lowest = min(data.geom_xpos[i][2] - np.abs(data.geom_xmat[i].reshape(3, 3)[2]) @ model.geom_size[i]
                 for i in foot_ids)
    if pose is not None:
        lowest = min(_geom_lowest(model, data, i) for i in range(model.ngeom) if i != floor_id)
    data.qpos[1] -= max(lowest, 0.0) - 0.002
    mujoco.mj_forward(model, data)

    mass = float(model.body_mass.sum())
    weight = mass * 9.81
    controller.reset(b.torque_limit, weight)
    limit = b.torque_limit
    kp = getattr(getattr(controller, "p", None), "kp", None)
    keys = ("t", "x", "z", "pitch", "q", "qd", "tau", "demand", "force", "slip", "foot_x", "foot_z", "body_contact")
    extra = ("com", "com_vel", "angmom_y", "pitch_rate", "ft_x", "util", "contact_x", "cop_x", "sup_min", "sup_max",
             "saturated", "tracking_error", "foot_low", "swing_clear")
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
        # additions (read-only)
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
                    v = vel6[3:] + np.cross(vel6[:3], con.pos - data.geom_xpos[other])  # contact-point velocity
                    slip[k] += f6[0] * abs(v[0])
                    cpos[k] += f6[0] * con.pos
                    # force on the foot in world coordinates (contact frame rows = normal, tangent1, tangent2; force acts on geom2)
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
        tr["tau"].append(data.actuator_force.copy())
        tr["demand"].append(np.array(demand, dtype=float))
        tr["force"].append(force)
        tr["slip"].append(slip)
        tr["foot_x"].append([float(data.geom_xpos[i][0]) for i in foot_ids])
        tr["foot_z"].append([float(data.geom_xpos[i][2]) for i in foot_ids])
        tr["body_contact"].append(body_contact)
        # ---- additions ----
        mujoco.mj_subtreeVel(model, data)
        tr["com"].append(data.subtree_com[0].copy())
        tr["com_vel"].append(data.subtree_linvel[0].copy())
        tr["angmom_y"].append(float(data.subtree_angmom[0][1]))
        tr["pitch_rate"].append(float(data.qvel[2]))
        tr["ft_x"].append(ft_x)
        tr["util"].append([abs(ft_x[k]) / (mu_foot[k] * force[k]) if mu_foot[k] and force[k] > contact_min else nan
                           for k in (0, 1)])
        tr["contact_x"].append([float(cpos[k][0]) if force[k] > 0.0 else nan for k in (0, 1)])
        fsum = sum(p[1] for p in pts)
        allf = force[0] + force[1]
        tr["cop_x"].append(float((force[0] * cpos[0][0] + force[1] * cpos[1][0]) / allf) if allf > 0.0 else nan)
        tr["sup_min"].append(min(p[0] for p in pts) if pts else nan)
        tr["sup_max"].append(max(p[0] for p in pts) if pts else nan)
        tr["saturated"].append(np.abs(np.asarray(demand, dtype=float)) >= 0.99 * limit)
        tr["tracking_error"].append(np.asarray(demand, dtype=float) / kp if kp else np.full(6, nan))
        low = [float(data.geom_xpos[i][2] - np.abs(data.geom_xmat[i].reshape(3, 3)[2]) @ model.geom_size[i]) for i in foot_ids]
        tr["foot_low"].append(low)
        free = [low[k] for k in (0, 1) if force[k] <= off_thr]
        tr["swing_clear"].append(min(free) if free else nan)
        # ---- end additions ----
        bad = bad + 1 if (z < FALL_HEIGHT_FRAC * z0 or abs(pitch) > FALL_PITCH) and data.time >= settle_s else 0
        if bad >= FALL_SUSTAIN_SAMPLES:
            break
    out = {k: np.asarray(v, dtype=float) for k, v in tr.items()}
    out["saturated"] = np.asarray(tr["saturated"], dtype=bool).reshape(-1, 6)
    out["meta"] = {"seed": seed, "duration": duration, "mass": mass, "weight": weight, "torque_limit": limit,
                   "controller": controller.name, "foot_friction": float(b.foot_friction), "leg_length": _leg_length(b),
                   "has_kp": kp is not None}
    return out


# ---------------------------------------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------------------------------------
def _series(tr: dict, body, upto: int) -> dict[str, np.ndarray]:
    """The normalised time series of SERIES over samples 0..upto (inclusive)."""
    s = slice(0, upto + 1)
    L = _leg_length(body)
    m = float(tr["meta"]["mass"])
    com = np.asarray(tr["com"], dtype=float)[s]
    vel = np.asarray(tr["com_vel"], dtype=float)[s]
    lo = np.asarray(tr["sup_min"], dtype=float)[s]
    hi = np.asarray(tr["sup_max"], dtype=float)[s]
    cop = np.asarray(tr["cop_x"], dtype=float)[s]
    omega = np.sqrt(G / np.maximum(com[:, 2], 1e-6))
    xcp = com[:, 0] + vel[:, 0] / omega
    inside = (xcp >= lo) & (xcp <= hi)
    with np.errstate(invalid="ignore"):
        margin = np.where(inside, np.minimum(xcp - lo, hi - xcp), -np.maximum(lo - xcp, xcp - hi))
    margin = np.where(np.isfinite(lo) & np.isfinite(hi), margin, np.nan)
    return {
        "com_vx": vel[:, 0],
        "com_height_over_L": com[:, 2] / L,
        "com_ahead_of_cop_over_L": (com[:, 0] - cop) / L,
        "capture_margin_over_L": margin / L,
        "cp_ahead_of_front_edge_over_L": (xcp - hi) / L,
        "angmom_norm": np.asarray(tr["angmom_y"], dtype=float)[s] / (m * L * math.sqrt(G * L)),
        "pitch": np.asarray(tr["pitch"], dtype=float)[s],
        "pitch_rate": np.asarray(tr["pitch_rate"], dtype=float)[s],
    }


def summarize(trace: dict, body) -> dict:
    """Compact scalar summary of a rich trace (keys and meanings in `PROBE_DOCS`). Every value is a finite float or None;
    `pre_fall` is None without a fall, else a dict of `pre_fall.<key>` quantities (stored without the prefix)."""
    from .gait_features import gait_features
    body = cw._body(body)
    out: dict = {k: None for k in PROBE_DOCS if "." not in k}
    meta = trace["meta"]
    L = _leg_length(body)
    out["leg_length_m"] = _num(L)
    t = np.asarray(trace["t"], dtype=float)
    z = np.asarray(trace["z"], dtype=float)
    pitch = np.asarray(trace["pitch"], dtype=float)
    n = len(t)
    if n < 2:
        out["fall_direction"] = 0.0
        return out
    low = (z < FALL_HEIGHT_FRAC * z[0]) | (np.abs(pitch) > FALL_PITCH)
    fi = _first_sustained(low, FALL_SUSTAIN_SAMPLES)
    fell = fi is not None
    iu = fi if fell else n - 1
    t_up = min(float(t[iu] + SAMPLE_DT) if iu > 0 else SAMPLE_DT, float(meta["duration"]))
    out["time_upright"] = _num(t_up)
    out["fall_time"] = _num(t[fi]) if fell else None

    gf = gait_features(trace, body)
    out["fall_direction"] = gf["fall_direction"]
    out["step_freq_hz"] = gf["step_freq_hz"]
    out["step_length_over_L"] = gf["step_length_over_leg"]
    out["double_support_fraction"] = gf["double_support_frac"]
    out["flight_fraction"] = gf["flight_frac"]

    sl = slice(0, iu + 1)
    tu = t[sl]
    ser = _series(trace, body, iu)
    for k, y in ser.items():
        out[k + "_mean"] = _nanmean(y)
        end = tu >= tu[-1] - END_WINDOW_S
        out[k + "_end"] = _nanmean(y[end])
        out[k + "_slope"] = _slope(tu, y)

    # contact statistics over loaded foot-samples (debounced, after the impact window)
    force = np.asarray(trace["force"], dtype=float)
    _est, _raw, deb = replay(tu, force[sl], float(meta["weight"]), ContactConfig())
    skip = int(round(DEFAULT_CRITERIA.skip_after_touchdown_s / SAMPLE_DT))
    counted = np.zeros(deb.shape, dtype=bool)
    for k in (0, 1):
        run = 0
        for i in range(len(tu)):
            run = run + 1 if deb[i, k] else 0
            counted[i, k] = run > skip
    slip = np.asarray(trace["slip"], dtype=float)[sl]
    util = np.asarray(trace["util"], dtype=float)[sl]
    sat = np.asarray(trace["saturated"], dtype=bool)[sl]
    terr = np.abs(np.asarray(trace["tracking_error"], dtype=float)[sl])

    def contact_stats(mask_t: np.ndarray) -> dict:
        cm = counted & mask_t[:, None]
        u = util[cm]
        u = u[np.isfinite(u)]
        return {"slip": _num((slip[cm] > DEFAULT_CRITERIA.slip_speed).mean()) if cm.any() else None,
                "util_max": _num(u.max()) if len(u) else None,
                "util_p95": _num(np.percentile(u, 95)) if len(u) else None}

    cs = contact_stats(np.ones(len(tu), dtype=bool))
    mg = ser["capture_margin_over_L"]
    out["capture_inside_fraction"] = _num((mg >= 0).sum() / np.isfinite(mg).sum()) if np.isfinite(mg).any() else None
    out["slip_fraction"] = cs["slip"]
    out["max_friction_utilisation"] = cs["util_max"]
    out["friction_utilisation_p95"] = cs["util_p95"]
    jt = {"hip": [0, 3], "knee": [1, 4], "ankle": [2, 5]}
    for name, cols in jt.items():
        out[f"saturation_frac_{name}"] = _num(sat[:, cols].any(axis=1).mean())
        out[f"tracking_error_{name}"] = _nanmean(terr[:, cols])

    # swing clearance: per complete swing phase (a foot below the swing threshold between a liftoff and a touchdown)
    foot_low = np.asarray(trace["foot_low"], dtype=float)[sl]
    off_thr = SWING_OFF_FRAC * float(meta["weight"])
    unloaded = force[sl] <= off_thr
    peaks = []
    for k in (0, 1):
        i = 0
        nu = len(tu)
        while i < nu:
            if unloaded[i, k]:
                j = i
                while j < nu and unloaded[j, k]:
                    j += 1
                if i > 0 and j < nu:    # liftoff and touchdown both observed
                    peaks.append(float(foot_low[i:j, k].max()))
                i = j
            else:
                i += 1
    out["n_swing_phases"] = len(peaks)
    out["swing_peak_clearance_min_over_L"] = _num(min(peaks) / L) if peaks else None
    out["swing_peak_clearance_mean_over_L"] = _num(np.mean(peaks) / L) if peaks else None
    sc = np.asarray(trace["swing_clear"], dtype=float)[sl]
    out["swing_clearance_min_over_L"] = _num(np.nanmin(sc) / L) if np.isfinite(sc).any() else None

    # pre-fall window
    if fell:
        w = tu >= tu[-1] - PRE_FALL_S
        pf: dict = {"window_s": _num(tu[-1] - tu[w][0])}
        for k, y in ser.items():
            pf[k] = _nanmean(y[w])
        cs = contact_stats(w)
        pf["slip_fraction"] = cs["slip"]
        pf["max_friction_utilisation"] = cs["util_max"]
        for name, cols in jt.items():
            pf[f"saturation_frac_{name}"] = _num(sat[w][:, cols].any(axis=1).mean())
        out["pre_fall"] = pf
    return out


# ---------------------------------------------------------------------------------------------------------
# observe (arena conditions, pool-friendly)
# ---------------------------------------------------------------------------------------------------------
def observe_job(job: dict) -> dict:
    """Pool job (module level, picklable): {vector, body (dict), seed, duration, perturb, friction_factor, mechanisms, start}
    -> {ok, summary, wall_s} (errors as values)."""
    t0 = time.perf_counter()
    try:
        body = cw._body(job["body"])
        tr = rich_rollout(body, job["vector"], job["seed"], duration=job["duration"], start=job.get("start", "neutral"),
                          perturb=job.get("perturb"), mechanisms=job.get("mechanisms") or (),
                          friction_factor=job.get("friction_factor"))
        if job.get("friction_factor") is not None:
            from .arena import _body_with_friction
            body = cw._body(_body_with_friction(body.as_dict(), float(job["friction_factor"]))[0])
        summ = summarize(tr, body)
        m = loc.compute_metrics(tr, cw.creature_criteria(body))
        summ.update({"seed": int(job["seed"]), "walking": bool(m["walking"]), "fell": bool(m["fell"]), "label": m["label"]})
        return {"ok": True, "summary": summ, "wall_s": time.perf_counter() - t0}
    except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "wall_s": time.perf_counter() - t0}


def _median_dicts(items: list[dict], keys) -> dict:
    out = {}
    for k in keys:
        vals = [d[k] for d in items if d.get(k) is not None]
        out[k] = _num(np.median(vals)) if vals else None
    return out


def observe(body, vector, seeds, *, mechanisms=(), variation=VARIATION_PRESET, duration: float = 10.0, pool=None) -> dict:
    """Run `rich_rollout` for each seed under the arena's per-seed conditions and summarise.

    Conditions: `arena._condition(seed, default_spec("walk", [seed]), variation)` (perturbation and a friction factor applied by
    `arena._body_with_friction`); the default is `arena.VARIATION_PRESET`; `variation=None` means the plain walk challenge (no friction change, spec perturbation). Walking is the frozen `locomotion.compute_metrics` label with
    `creature_walk.creature_criteria(body)` (of the friction-adjusted body).
    Returns {"per_seed": [summary + seed/walking/fell/label], "median": {key: median over seeds (None if undefined)},
    "pre_fall_median": {...over seeds that fell}, "rollouts", "n_fell", "n_walking", "errors": [{seed, error}]}.
    A seed whose rollout raises is listed in "errors" and excluded from the medians, never dropped silently."""
    from . import arena, challenges
    b = cw._body(body)
    body_d = b.as_dict()
    if "pose" in body_d:
        body_d["pose"] = list(body_d["pose"])
    seeds = [int(s) for s in seeds]
    jobs = []
    for s in seeds:
        spec = challenges.default_spec("walk", [s])
        if variation:
            c = arena._condition(s, spec, variation)
            perturb, ff = c["perturb"], c["friction_factor"]
        else:
            perturb, ff = spec.perturb, None
        jobs.append({"vector": [float(x) for x in vector], "body": body_d, "seed": s, "duration": duration, "perturb": perturb,
                     "friction_factor": ff, "mechanisms": [dict(m) for m in mechanisms] if mechanisms else [], "start": "neutral"})
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
