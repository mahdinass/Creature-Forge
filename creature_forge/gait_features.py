"""Scalar gait diagnostics measured from an existing 200 Hz walking trace.

Every output is one finite float or None (None = undefined, e.g. fewer than 2 touchdowns). They are measurements of
what the trace shows, not explanations: nothing here asserts a cause. `FEATURE_DOCS` holds the one-line definition of
every key and is meant to be quoted as evidence text.

Conventions (all shared with `locomotion.compute_metrics`, which is frozen and not modified):
  * the "upright period" is samples 0..iu, where iu is the first sample of a sustained fall (torso height < 0.5 x its
    first value or |pitch| > 1 rad for 20 samples, `locomotion.FALL_*`), or the last sample when no fall occurs;
  * contacts use the debounced force estimator of `contact.replay` (default `ContactConfig`), the same one
    `compute_metrics` uses, so touchdown / liftoff / support-state agree with it;
  * `x` and `z` in the trace are the TORSO position (there is no centre of mass in the trace); the torso is used as the
    COM proxy wherever a capture point or a Froude number needs a body position;
  * positive pitch is a forward lean (hinge about +y), joint order of q / tau is (hip, knee, ankle) of left then right.
"""
from __future__ import annotations

import math

import numpy as np

from . import creature_walk as cw
from . import locomotion as loc
from .contact import ContactConfig, SAMPLE_DT, replay
from .failures import _first_sustained

G = 9.81
SMOOTH_S = 0.2   # window of the forward-velocity smoothing

FEATURE_DOCS: dict[str, str] = {
    "leg_length_m": "L = mean over both legs of thigh + shank length (m).",
    "pendulum_freq_hz": "Natural frequency of a pendulum of length L: sqrt(g/L)/(2*pi) (Hz), g = 9.81.",
    "controller_freq_hz": "Gait frequency parameter 'freq' of the controller vector (Hz); None if no vector was given.",
    "controller_freq_ratio": "controller_freq_hz / pendulum_freq_hz.",
    "step_freq_hz": "Debounced touchdowns of either foot per second, (n-1)/(t_last - t_first) over the upright period; needs >= 2.",
    "step_length_over_leg": "Mean |x distance between the foot of a touchdown and the other foot's previous touchdown| over alternating touchdowns, / L.",
    "froude": "v^2/(g*L) with v = mean forward torso velocity over the upright period (0 if it moved backward).",
    "speed_trend_mps2": "Least-squares slope of the torso forward velocity (0.2 s centred moving average) over the upright period; positive = speeding up.",
    "pitch_mean_rad": "Mean torso pitch over the upright period (rad, positive = forward lean).",
    "pitch_drift_radps": "Least-squares slope of torso pitch against time over the upright period (rad/s).",
    "pitch_at_end_rad": "Torso pitch at the last upright sample (the fall onset when the creature fell) (rad).",
    "touchdown_foot_ahead_over_leg_mean": "Mean over touchdowns of (touchdown foot x - torso x)/L; positive = foot lands ahead of the torso.",
    "touchdown_foot_ahead_over_leg_last": "(touchdown foot x - torso x)/L at the last touchdown of the upright period.",
    "touchdown_foot_ahead_trend": "Least-squares slope of (touchdown foot x - torso x)/L against touchdown index (per step).",
    "capture_margin_over_leg_mean": "Mean over touchdowns of (foot x - (x + xdot/w))/L, w = sqrt(g/torso z), xdot = smoothed torso velocity; negative = foot lands behind the capture point.",
    "capture_margin_over_leg_min": "Minimum over touchdowns of the capture margin / L.",
    "capture_margin_over_leg_last": "Capture margin / L at the last touchdown of the upright period.",
    "fall_direction": "+1 if the sustained fall is a forward lean (pitch > 0 at fall detection, else torso moved forward), -1 backward, 0 no fall.",
    "fall_time_s": "Time of the first sustained-fall sample (s); None if no fall.",
    "support_at_fall": "Debounced feet loaded at the fall time: 0 flight, 1 single, 2 double support; None if no fall.",
    "torque_authority": "torque_limit / (mass * g * L): joint torque limit relative to the weight acting at one leg length.",
    "saturation_frac": "Fraction of upright samples with any joint torque demand >= 0.99 x the torque limit (as compute_metrics).",
    "peak_tau_over_limit_hip": "Maximum over the upright period and both legs of |hip torque| / torque limit.",
    "peak_tau_over_limit_knee": "Maximum over the upright period and both legs of |knee torque| / torque limit.",
    "peak_tau_over_limit_ankle": "Maximum over the upright period and both legs of |ankle torque| / torque limit.",
    "double_support_frac": "Fraction of upright samples with both feet debounced-loaded (as compute_metrics).",
    "flight_frac": "Fraction of upright samples with neither foot debounced-loaded (as compute_metrics).",
}
KEYS = tuple(FEATURE_DOCS)


# ---------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------
def _num(v) -> float | None:
    if v is None:
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def _slope(xs, ys) -> float | None:
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if len(xs) < 2:
        return None
    dx = xs - xs.mean()
    den = float((dx * dx).sum())
    if den <= 0.0:
        return None
    return float((dx * (ys - ys.mean())).sum() / den)


def _smooth_velocity(t: np.ndarray, x: np.ndarray, window_s: float = SMOOTH_S) -> np.ndarray:
    """Central-difference d x / d t, then a centred moving average of about `window_s`. Near the ends the window
    shrinks symmetrically (so a linear velocity stays exact); at the very ends it is the raw gradient."""
    n = len(x)
    if n < 2:
        return np.zeros(n)
    v = np.gradient(x, t)
    h = max(int(round(window_s / SAMPLE_DT / 2.0)), 0)
    c = np.concatenate([[0.0], np.cumsum(v)])
    out = np.empty(n)
    for i in range(n):
        k = min(h, i, n - 1 - i)
        out[i] = (c[i + k + 1] - c[i - k]) / (2 * k + 1)
    return out


def _leg_length(body) -> float:
    return float(sum(cw._leg_lengths(body)) / 2.0)


def _empty() -> dict:
    return {k: None for k in KEYS}


# ---------------------------------------------------------------------------------------------------------
# features
# ---------------------------------------------------------------------------------------------------------
def gait_features(trace: dict, body, vector=None) -> dict:
    """Scalar gait diagnostics of one trace (see `FEATURE_DOCS`). Every value is a finite float or None."""
    out = _empty()
    meta = trace["meta"]
    L = _leg_length(body)
    out["leg_length_m"] = _num(L)
    f_pend = math.sqrt(G / L) / (2.0 * math.pi)
    out["pendulum_freq_hz"] = _num(f_pend)
    if vector is not None:
        from .phasegait_init import controller_from_vector
        f_ctrl = float(controller_from_vector(vector).p.freq)
        out["controller_freq_hz"] = _num(f_ctrl)
        out["controller_freq_ratio"] = _num(f_ctrl / f_pend)
    limit = float(meta["torque_limit"])
    mass = float(meta["mass"])
    out["torque_authority"] = _num(limit / (mass * G * L))

    t = np.asarray(trace["t"], dtype=float)
    x = np.asarray(trace["x"], dtype=float)
    z = np.asarray(trace["z"], dtype=float)
    pitch = np.asarray(trace["pitch"], dtype=float)
    n = len(t)
    if n < 2:
        return out
    low = (z < loc.FALL_HEIGHT_FRAC * z[0]) | (np.abs(pitch) > loc.FALL_PITCH)
    fi = _first_sustained(low, loc.FALL_SUSTAIN_SAMPLES)
    fell = fi is not None
    iu = fi if fell else n - 1
    sl = slice(0, iu + 1)
    tu, xu, zu, pu = t[sl], x[sl], z[sl], pitch[sl]
    nu = len(tu)

    est, _raw, deb = replay(tu, np.asarray(trace["force"], dtype=float)[sl], float(meta["weight"]), ContactConfig())
    n_loaded = deb.sum(1)
    out["double_support_frac"] = _num(np.mean(n_loaded == 2))
    out["flight_frac"] = _num(np.mean(n_loaded == 0))

    # torque
    if "demand" in trace:
        dem = np.abs(np.asarray(trace["demand"], dtype=float)[sl])
        out["saturation_frac"] = _num(np.mean((dem >= 0.99 * limit).any(axis=1)))
    tau = np.abs(np.asarray(trace["tau"], dtype=float)[sl]) / limit
    out["peak_tau_over_limit_hip"] = _num(tau[:, [0, 3]].max())
    out["peak_tau_over_limit_knee"] = _num(tau[:, [1, 4]].max())
    out["peak_tau_over_limit_ankle"] = _num(tau[:, [2, 5]].max())

    # fall
    if fell:
        out["fall_time_s"] = _num(t[fi])
        out["support_at_fall"] = _num(n_loaded[fi])
        pe = pitch[min(fi + loc.FALL_SUSTAIN_SAMPLES - 1, n - 1)]
        if abs(pe) >= 0.3:
            d = 1.0 if pe > 0 else -1.0
        else:
            j = max(fi - int(round(0.5 / SAMPLE_DT)), 0)
            dx = x[fi] - x[j]
            d = 1.0 if dx > 0 else (-1.0 if dx < 0 else 0.0)
        out["fall_direction"] = d
    else:
        out["fall_direction"] = 0.0

    # posture and speed over the upright period
    if nu >= 2:
        span = float(tu[-1] - tu[0])
        out["pitch_mean_rad"] = _num(pu.mean())
        out["pitch_drift_radps"] = _num(_slope(tu, pu))
        out["pitch_at_end_rad"] = _num(pu[-1])
        v_mean = float(xu[-1] - xu[0]) / span if span > 0 else 0.0
        out["froude"] = _num(max(v_mean, 0.0) ** 2 / (G * L))
        vs = _smooth_velocity(tu, xu)
        out["speed_trend_mps2"] = _num(_slope(tu, vs))
    else:
        vs = np.zeros(nu)

    # touchdowns
    tds = sorted((e for e in est.events if e["kind"] == "touchdown"), key=lambda e: (e["t"], e["foot"]))
    if len(tds) < 2 or nu < 2:
        return out
    fx = np.asarray(trace["foot_x"], dtype=float)[sl]
    idx = [int(np.clip(np.searchsorted(tu, e["t"] - 1e-9), 0, nu - 1)) for e in tds]
    feet = [e["foot"] for e in tds]
    td_t = [float(e["t"]) for e in tds]
    if td_t[-1] > td_t[0]:
        out["step_freq_hz"] = _num((len(tds) - 1) / (td_t[-1] - td_t[0]))
    adv = [abs(fx[idx[i], feet[i]] - fx[idx[i - 1], feet[i - 1]]) for i in range(1, len(tds)) if feet[i] != feet[i - 1]]
    if adv:
        out["step_length_over_leg"] = _num(np.mean(adv) / L)
    ahead = np.array([(fx[i, k] - xu[i]) / L for i, k in zip(idx, feet)])
    out["touchdown_foot_ahead_over_leg_mean"] = _num(ahead.mean())
    out["touchdown_foot_ahead_over_leg_last"] = _num(ahead[-1])
    out["touchdown_foot_ahead_trend"] = _num(_slope(np.arange(len(ahead)), ahead))
    omega = np.sqrt(G / np.maximum(zu[idx], 1e-6))
    cap = np.array([(fx[i, k] - (xu[i] + vs[i] / w)) / L for i, k, w in zip(idx, feet, omega)])
    out["capture_margin_over_leg_mean"] = _num(cap.mean())
    out["capture_margin_over_leg_min"] = _num(cap.min())
    out["capture_margin_over_leg_last"] = _num(cap[-1])
    return out


def summarize(features_list: list[dict]) -> dict:
    """Median of every numeric field across seeds (None values are ignored; a field that is None in every seed is None);
    `fall_direction` becomes `forward_fall_frac` (fraction of seeds with a forward fall); plus `n_seeds`."""
    out: dict = {"n_seeds": len(features_list)}
    for k in KEYS:
        if k == "fall_direction":
            continue
        vals = [f[k] for f in features_list if f.get(k) is not None]
        out[k] = _num(np.median(vals)) if vals else None
    dirs = [f.get("fall_direction") for f in features_list if f.get("fall_direction") is not None]
    out["forward_fall_frac"] = _num(sum(1 for d in dirs if d > 0) / len(dirs)) if dirs else None
    return out


SUMMARY_DOCS: dict[str, str] = {
    **{k: "Median across seeds of: " + v for k, v in FEATURE_DOCS.items() if k != "fall_direction"},
    "forward_fall_frac": "Fraction of seeds whose sustained fall was a forward lean.",
    "n_seeds": "Number of seeds summarised.",
}


def features_for(body, vector, seed: int, *, duration: float = 10.0, perturb=None) -> dict:
    """Roll out `vector` on `body` (start "neutral") and return `gait_features`."""
    from .phasegait_init import controller_from_vector
    kw = {} if perturb is None else {"perturb": perturb}
    tr = cw.rollout(controller_from_vector(vector), body, seed, duration, start="neutral", **kw)
    return gait_features(tr, body, vector)
