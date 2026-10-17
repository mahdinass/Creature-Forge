"""Physics digest for the causal scientist (added 2026-10-17 after the pilot1 audit, finding F3).

The pilot showed the model reading 58 absolute numbers with no notion of what a healthy walker shows on the same instruments, and
misreading signs (a backward fall described as a forward lean). This module adds two kinds of EVIDENCE, never a diagnosis:

  derived(obs, body, vector)   physics calculations from the observation and the robot: the pendulum frequency sqrt(g/L)/(2 pi), the
                               commanded touchdown rate (2 x freq: two touchdowns per gait cycle), measured / commanded cadence,
                               stride frequency / pendulum frequency, Froude number v^2/(g L), peak joint saturation.
  key_facts(...)               short factual lines with signs spelled out in words (fall direction per seed, fall times, cadence,
                               saturation, slip, clearance) and, per digest quantity, the HEALTHY REFERENCE range: p10-p90 of the same
                               quantity over verified-walking dev base robots observed on the same instruments
                               (`scripts/ce_healthy_reference.py`). The reference is laboratory knowledge about healthy walkers in
                               general; it contains nothing about the robot under investigation, its fault or its repair.

No line names a cause, a fault, a tool or a repair; the comparison words are BELOW / WITHIN / ABOVE the healthy range.
"""
from __future__ import annotations

import json
import math
import os
from typing import Sequence

G = 9.81
VERSION = "physics_digest_v1"
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE_PATH = os.path.join(_REPO, "experiments", "causal_engineer", "dev", "healthy_reference.json")

# Quantities compared with the healthy range (observation medians, then derived ones).
DIGEST_KEYS = ("time_upright", "com_vx_mean", "step_freq_hz", "step_length_over_L", "double_support_fraction", "flight_fraction",
               "swing_peak_clearance_min_over_L", "swing_peak_clearance_mean_over_L", "pitch_mean", "pitch_rate_mean",
               "com_height_over_L_mean", "com_ahead_of_cop_over_L_mean", "capture_margin_over_L_mean", "angmom_norm_mean",
               "tracking_error_hip", "tracking_error_knee", "friction_utilisation_p95", "slip_fraction")
DERIVED_KEYS = ("cadence_measured_over_commanded", "stride_freq_over_pendulum", "froude_number", "max_saturation_frac")


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _g(d, k):
    v = (d or {}).get(k)
    return float(v) if _num(v) else None


def _r(v, nd: int = 3) -> str:
    if v is None:
        return "None"
    if v == 0:
        return "0"
    return f"{v:.{nd}g}"


def leg_length(obs: dict, body: dict | None = None) -> float | None:
    """L = mean over both legs of thigh + shank (the observation's leg_length_m, else computed from the body)."""
    L = _g(obs.get("median"), "leg_length_m")
    if L is None and body:
        legs = []
        for side in ("", "_r"):
            th, sh = _g(body, "thigh_length" + side) or _g(body, "thigh_length"), _g(body, "shank_length" + side) or _g(body, "shank_length")
            if th is not None and sh is not None:
                legs.append(th + sh)
        L = sum(legs) / len(legs) if legs else None
    return L


def derived(obs: dict, body: dict | None, vector: Sequence[float] | None) -> dict:
    """Physics calculations (None where an input is missing)."""
    med = obs.get("median") or {}
    L = leg_length(obs, body)
    freq = float(vector[0]) if vector is not None and len(vector) >= 1 and _num(vector[0]) else None
    f_pend = math.sqrt(G / L) / (2 * math.pi) if L else None
    commanded = 2.0 * freq if freq is not None else None
    meas = _g(med, "step_freq_hz")
    v = _g(med, "com_vx_mean")
    sats = [_g(med, f"saturation_frac_{j}") for j in ("hip", "knee", "ankle")]
    sats = [s for s in sats if s is not None]
    return {"leg_length_m": L, "pendulum_freq_hz": f_pend, "commanded_touchdowns_hz": commanded,
            "cadence_measured_over_commanded": (meas / commanded) if (meas is not None and commanded) else None,
            "stride_freq_over_pendulum": (freq / f_pend) if (freq is not None and f_pend) else None,
            "froude_number": (v * v / (G * L)) if (v is not None and L) else None,
            "max_saturation_frac": max(sats) if sats else None}


_REF_CACHE: dict = {}


def healthy_reference(path: str | None = None) -> dict | None:
    """The committed healthy-walker reference ({"quantities": {key: {"p10","median","p90","n"}}, provenance...}) or None."""
    p = path or REFERENCE_PATH
    if p not in _REF_CACHE:
        try:
            with open(p, encoding="utf-8") as fh:
                _REF_CACHE[p] = json.load(fh)
        except (OSError, ValueError):
            _REF_CACHE[p] = None
    return _REF_CACHE[p]


def reference_stats(values_by_key: dict) -> dict:
    """{key: [values over healthy robots]} -> {key: {p10, median, p90, n}} (numpy-free percentiles, linear interpolation)."""
    def pct(xs, q):
        xs = sorted(xs)
        if len(xs) == 1:
            return xs[0]
        pos = q * (len(xs) - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, len(xs) - 1)
        return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)
    out = {}
    for k, xs in values_by_key.items():
        xs = [float(x) for x in xs if _num(x)]
        if xs:
            out[k] = {"p10": pct(xs, 0.1), "median": pct(xs, 0.5), "p90": pct(xs, 0.9), "n": len(xs)}
    return out


def _cmp(v, st) -> str:
    if v is None or not st:
        return ""
    if v < st["p10"]:
        return "BELOW"
    if v > st["p90"]:
        return "ABOVE"
    return "WITHIN"


def _fall_lines(obs: dict) -> list[str]:
    per = obs.get("per_seed") or []
    n = len(per)
    if not n:
        return [f"falls: {obs.get('n_fell')} fell, {obs.get('n_walking')} walking (per-seed detail unavailable)"]
    fell = [p for p in per if p.get("fell")]
    fwd = sum(1 for p in fell if _num(p.get("fall_direction")) and p["fall_direction"] > 0)
    bwd = sum(1 for p in fell if _num(p.get("fall_direction")) and p["fall_direction"] < 0)
    times = sorted(float(p["fall_time"]) for p in fell if _num(p.get("fall_time")))
    walking = sum(1 for p in per if p.get("walking"))
    labels: dict = {}
    for p in per:
        labels[p.get("label")] = labels.get(p.get("label"), 0) + 1
    lines = [f"seeds: {n}; walking {walking}; fell {len(fell)} (FORWARD, i.e. nose down / torso ahead, on {fwd}; BACKWARD on {bwd}; "
             f"other {len(fell) - fwd - bwd}); labels {', '.join(f'{k}: {v}' for k, v in sorted(labels.items(), key=str))}"]
    if times:
        lines.append(f"fall times (s): median {_r(times[len(times) // 2])}, range {_r(times[0])}-{_r(times[-1])} of a 10 s rollout")
    return lines


def key_facts(obs: dict, body: dict | None, vector: Sequence[float] | None, ref: dict | None = None) -> list[str]:
    """Factual lines for the user message. `ref` defaults to the committed healthy reference (lines without it if absent)."""
    med = obs.get("median") or {}
    d = derived(obs, body, vector)
    ref = ref if ref is not None else healthy_reference()
    rq = (ref or {}).get("quantities") or {}
    lines = _fall_lines(obs)
    pitch_end = _g(med, "pitch_end")
    if pitch_end is not None:
        lines.append(f"torso pitch over the last 0.2 s before the end/fall: {_r(pitch_end)} rad "
                     f"({'leaning FORWARD (nose down)' if pitch_end > 0 else 'leaning BACKWARD'}); mean COM forward speed over the "
                     f"last 0.2 s {_r(_g(med, 'com_vx_end'))} m/s ({'moving forward' if (_g(med, 'com_vx_end') or 0) > 0 else 'moving backward'})")
    if d["pendulum_freq_hz"] is not None:
        lines.append(f"leg length L = {_r(d['leg_length_m'])} m; pendulum frequency sqrt(g/L)/(2 pi) = {_r(d['pendulum_freq_hz'])} Hz; "
                     f"commanded gait frequency freq = {_r(vector[0] if vector else None)} Hz -> commanded touchdowns "
                     f"{_r(d['commanded_touchdowns_hz'])}/s; measured touchdowns {_r(_g(med, 'step_freq_hz'))}/s")
    sat = d["max_saturation_frac"]
    lines.append("torque saturation: " + ("none measured (no joint reached 0.99 x the torque limit)" if sat == 0 else
                                          f"up to {_r(sat)} of upright samples (hip {_r(_g(med, 'saturation_frac_hip'))}, knee "
                                          f"{_r(_g(med, 'saturation_frac_knee'))}, ankle {_r(_g(med, 'saturation_frac_ankle'))})"))
    lines.append(f"slip: {_r(_g(med, 'slip_fraction'))} of loaded foot-time; friction utilisation p95 {_r(_g(med, 'friction_utilisation_p95'))}, "
                 f"max {_r(_g(med, 'max_friction_utilisation'))} (1 = on the friction cone)")
    if rq:
        src = (ref or {}).get("source", "healthy reference")
        lines.append(f"HEALTHY REFERENCE: p10-p90 of the same quantity over {(ref or {}).get('n_robots', '?')} verified-walking robots "
                     f"of other shapes ({src}); BELOW / WITHIN / ABOVE that range:")
        for k in DIGEST_KEYS + DERIVED_KEYS:
            v = _g(med, k) if k in DIGEST_KEYS else d.get(k)
            st = rq.get(k)
            if v is None or not st:
                continue
            lines.append(f"  {k} = {_r(v)} | healthy [{_r(st['p10'])}, {_r(st['p90'])}] (median {_r(st['median'])}) -> {_cmp(v, st)}")
    else:
        for k in DERIVED_KEYS:
            if d.get(k) is not None:
                lines.append(f"  {k} = {_r(d[k])}")
    return lines
