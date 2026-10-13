"""Failure forensics: a compact, time-localized summary computed ONLY from MuJoCo telemetry.

Everything here is a measurement or a deterministic function of measurements. There are no causal claims:
the summary says what happened (pitch, centre-of-mass vs. support, contacts, torque, slip), never why.

Conventions: +x is the push direction; "margin" is the distance from a point to the NEAREST edge of the
support interval [support_x_min, support_x_max] (the extent of loaded foot-floor contact points), positive
inside and negative outside. The "extrapolated" COM adds v*sqrt(h/g) (linear-inverted-pendulum capture
point); it is an approximation, labelled as such. Quantities are NaN-safe: when no foot is loaded the
support is undefined and those samples are excluded (and counted in `feet_unloaded_fraction`).
"""
from __future__ import annotations

import math

import numpy as np

from .failures import SAMPLE_DT, FailureEvent, _first_sustained
from .morphology import BipedParams
from .simulate import Push

G = 9.81
INSTABILITY_SUSTAIN_S = 0.05
SLIP_THRESHOLD_MPS = 0.15
ANKLE = (2, 5)  # indices into the 6 joints (hip_l, knee_l, ankle_l, hip_r, knee_r, ankle_r)

DEFINITIONS = {
    "com_margin_m": "distance from whole-body COM x to nearest support edge; negative = COM outside support",
    "xcom_margin_m": "same for extrapolated COM x + vx*sqrt(h/g) (LIP approximation); negative = momentum carries COM past support",
    "support": "interval between min and max x of loaded foot-floor contact points (MuJoCo contacts)",
    "instability_onset_s": f"first time the extrapolated-COM margin stays negative for {INSTABILITY_SUSTAIN_S} s after the push starts",
    "xcom_margin_recovered_s": "first time after onset the extrapolated-COM margin stays positive for 0.05 s (null = never)",
    "ankle_demand_over_limit": "|demanded ankle torque| / actuator torque limit; >1 means the actuator clipped the demand",
}


def _r(x, nd: int = 4):
    """Round a float; NaN/inf -> None so the summary is strict JSON."""
    if x is None:
        return None
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def support_margins(tel: dict) -> dict[str, np.ndarray]:
    """Per-sample COM / extrapolated-COM margins to the support interval (NaN when no foot is loaded)."""
    lo, hi = tel["support_x_min"], tel["support_x_max"]
    com_x, com_vx, com_z = tel["com_pos"][:, 0], tel["com_vel"][:, 0], tel["com_pos"][:, 2]
    xcom = com_x + com_vx * np.sqrt(np.maximum(com_z, 1e-6) / G)
    return {"com": np.minimum(com_x - lo, hi - com_x), "xcom": np.minimum(xcom - lo, hi - xcom),
            "support_length": hi - lo}


def contact_transitions(foot_contact: np.ndarray, t: np.ndarray, limit: int = 12) -> list[dict]:
    """Touchdown / liftoff events per foot from the 0/1 contact flags (first `limit`)."""
    out = []
    for k, name in enumerate(("left", "right")):
        flag = foot_contact[:, k] > 0.5
        for i in np.flatnonzero(flag[1:] != flag[:-1]) + 1:
            out.append({"foot": name, "t_s": _r(t[i], 3), "event": "touchdown" if flag[i] else "liftoff"})
    return sorted(out, key=lambda e: e["t_s"])[:limit]


def _idx(t: np.ndarray, time: float) -> int:
    return int(min(max(np.searchsorted(t, time), 0), len(t) - 1))


def build_forensics(tel: dict, body: BipedParams, push: Push, events: list[FailureEvent], *,
                    timeline_step_s: float = 0.1, max_rows: int = 14) -> dict:
    t = tel["t"]
    pitch, rate = tel["torso_pitch"], tel["torso_angvel"]
    m = support_margins(tel)
    i_push, i_end = _idx(t, push.time), _idx(t, push.time + push.duration)
    fall = next((e for e in events if e.kind == "fall"), None)
    t_fall = None if fall is None else fall.time
    i_fall = len(t) - 1 if fall is None else _idx(t, fall.time)
    after = slice(i_push, i_fall + 1)  # from push start to fall (or end of run)

    with np.errstate(all="ignore"):
        xm = m["xcom"][after]
        unstable = np.where(np.isnan(xm), False, xm < 0)
        k = _first_sustained(unstable, max(1, int(round(INSTABILITY_SUSTAIN_S / SAMPLE_DT))))
        onset = None if k is None else float(t[after][k])
        recovered = None
        if k is not None:
            safe = np.where(np.isnan(xm), False, xm > 0)[k:]
            r = _first_sustained(safe, max(1, int(round(INSTABILITY_SUSTAIN_S / SAMPLE_DT))))
            recovered = None if r is None else float(t[after][k + r])
        cm = m["com"][after]
        com_out = _first_sustained(np.where(np.isnan(cm), False, cm < 0), 3)
        t_com_out = None if com_out is None else float(t[after][com_out])
        pre = max(i_push - 1, 0)
        win_pitch = np.abs(pitch[i_push:min(i_push + int(1.0 / SAMPLE_DT), len(t))])
        ip = i_push + int(np.argmax(win_pitch))
        demand = np.abs(tel["ctrl_demand"])
        applied = np.abs(tel["joint_torque"])
        ank_d, ank_a = demand[:, ANKLE], applied[:, ANKLE]
        over = (demand[after] > body.torque_limit * 0.999).any(axis=1)
        slip = tel["foot_slip_speed"]
        loaded = tel["foot_contact"] > 0.5
        slipping = ((slip > SLIP_THRESHOLD_MPS) & loaded).any(axis=1)
        feet_loaded = loaded.sum(axis=1)

        summary = {
            "definitions": DEFINITIONS,
            "disturbance": {
                "push_time_s": push.time, "push_force_N": push.force, "push_duration_s": push.duration,
                "impulse_Ns": _r(push.force * push.duration),
                "pitch_before_push_rad": _r(pitch[pre]),
                "com_vx_before_push_mps": _r(tel["com_vel"][pre, 0]),
                "com_vx_at_push_end_mps": _r(tel["com_vel"][i_end, 0]),
                "com_x_shift_during_push_m": _r(tel["com_pos"][i_end, 0] - tel["com_pos"][pre, 0]),
                "peak_abs_pitch_within_1s_rad": _r(np.abs(pitch[ip])),
                "time_of_peak_pitch_s": _r(t[ip], 3),
                "peak_pitch_rate_within_1s_rad_s": _r(np.abs(rate[i_push:ip + 1]).max()),
            },
            "failure": {
                "fell": fall is not None, "fall_time_s": _r(t_fall, 3),
                "fall_after_push_end_s": None if t_fall is None else _r(t_fall - push.time - push.duration, 3),
                "instability_onset_s": _r(onset, 3),
                "onset_after_push_start_s": None if onset is None else _r(onset - push.time, 3),
                "xcom_margin_recovered_s": _r(recovered, 3),
                "com_left_support_s": _r(t_com_out, 3),
                "pitch_at_fall_rad": None if fall is None else _r(pitch[i_fall]),
                "min_torso_height_m": _r(tel["torso_pos"][:, 1].min()),
            },
            "support": {
                "support_length_before_push_m": _r(m["support_length"][pre]),
                "com_margin_before_push_m": _r(m["com"][pre]),
                "xcom_margin_before_push_m": _r(m["xcom"][pre]),
                "min_com_margin_after_push_m": _r(np.nanmin(cm)) if not np.all(np.isnan(cm)) else None,
                "min_xcom_margin_after_push_m": _r(np.nanmin(xm)) if not np.all(np.isnan(xm)) else None,
                "time_of_min_xcom_margin_s": None if np.all(np.isnan(xm)) else _r(t[after][int(np.nanargmin(xm))], 3),
                "cop_minus_com_x_at_push_end_m": _r(tel["cop_x"][i_end] - tel["com_pos"][i_end, 0]),
                "feet_unloaded_fraction_after_push": _r(np.mean(feet_loaded[after] == 0), 3),
            },
            "actuation": {
                "torque_limit_Nm": body.torque_limit,
                "ankle_peak_demand_Nm": _r(ank_d[after].max(), 2),
                "ankle_peak_applied_Nm": _r(ank_a[after].max(), 2),
                "ankle_demand_over_limit_peak": _r(ank_d[after].max() / body.torque_limit, 3),
                "any_joint_demand_over_limit_peak": _r(demand[after].max() / body.torque_limit, 3),
                "fraction_samples_saturated_push_to_fall": _r(over.mean(), 3),
            },
            "contacts": {
                "transitions": contact_transitions(tel["foot_contact"], t),
                "peak_slip_speed_mps": _r(slip[after].max(), 3),
                "fraction_samples_slipping_push_to_fall": _r(slipping[after].mean(), 3),
                "foot_friction": body.foot_friction,
            },
        }

        # time-localized window: from just before the push to just after the fall (or +1.5 s)
        t0 = max(push.time - timeline_step_s, 0.0)
        t1 = min((t_fall + timeline_step_s) if t_fall is not None else push.time + 1.5, float(t[-1]))
        times = np.arange(t0, t1 + 1e-9, timeline_step_s)[:max_rows]
        rows = []
        for tt in times:
            i = _idx(t, tt)
            rows.append([_r(t[i], 3), _r(pitch[i], 3), _r(rate[i], 3), _r(tel["com_vel"][i, 0], 3),
                         _r(m["com"][i], 3), _r(m["xcom"][i], 3), int(feet_loaded[i]),
                         _r(ank_d[i].max() / body.torque_limit, 2), _r(slip[i].max(), 3)])
        summary["timeline"] = {"columns": ["t_s", "pitch_rad", "pitch_rate_rad_s", "com_vx_mps", "com_margin_m",
                                           "xcom_margin_m", "feet_loaded", "ankle_demand_over_limit",
                                           "max_slip_speed_mps"], "rows": rows}
    return summary
