"""Non-AI baselines for the Forge arena (contracts section 6.1). Both are labelled non-AI everywhere.

* `matched_random`: the random twin of an AI proposal. Same number of edits; each AI edit is replaced by an edit of a random
  whitelisted parameter of the SAME kind (morphology / actuation / control) with target `both`, the SAME `magnitude`
  (`interventions.magnitude`) and a random sign. It never sees evidence, results or the AI's rationale; its only inputs are the
  AI edits' kinds and sizes, the version and an RNG seeded from (investigation_id, proposal_id) by a stable hash.
* `heuristic`: a small deterministic rule table over the challenge result's measured metrics/forensics (see `RULES`). It is
  generic prior knowledge (a longer foot widens the support polygon, more torque relieves saturation, more friction stops slip),
  fixed before any candidate was evaluated. Output always passes `validate_edits`; `None` means abstain.
"""
from __future__ import annotations

import hashlib
import math
from typing import Sequence

import numpy as np

from . import interventions as iv
from .interventions import Edit

MAX_REDRAWS = 20
HEURISTIC_SCALE = 1.3          # x1.3 on foot_length / torque_limit / foot_friction
HEURISTIC_DELTA_U = 0.1        # +0.1 u on walk.balance_gain / walk.pitch_kp
SATURATION_FRACTION = 0.05     # same screens as proposers.classify_mechanism
SLIP_FRACTION = 0.10
SLIP_SPEED_MPS = 0.15
RULES = (
    "1 torque saturation (saturation fraction > 0.05) -> torque_limit x1.3",
    "2 foot slip (slip fraction > 0.10 and peak slip speed > 0.15 m/s where known) -> foot_friction x1.3",
    "3 stand/push: falls without a push, any seed FAIL, or backward push is the weak direction while not PASS -> foot_length x1.3",
    "4 walk: more than half of the seeds fell -> walk.balance_gain +0.1 u and walk.pitch_kp +0.1 u",
)


def make_rng(investigation_id: str, proposal_id: str) -> np.random.Generator:
    """RNG for (investigation_id, proposal_id) from a sha256 hash (never Python's salted `hash()`)."""
    h = hashlib.sha256(f"forge-baseline:{investigation_id}:{proposal_id}".encode("utf-8")).digest()
    return np.random.default_rng(np.random.SeedSequence(int.from_bytes(h[:16], "big")))


def _control_value(version: dict, param: str) -> float:
    """Current value of a control parameter (stand.* or walk.*)."""
    return iv._plan(version, Edit(param, "scale", 1.0))[0].old


def _twin_edit(version: dict, param: str, mag: float, sign: int) -> Edit:
    if iv.kind_of(param) == "control":
        lo, hi = iv.control_bounds(param)
        return Edit(param, "set", float(_control_value(version, param) + sign * mag * (hi - lo)), "both")
    return Edit(param, "scale", float(math.exp(sign * mag)), "both")


def matched_random(version: dict, kind: str, ai_edits: Sequence[Edit], rng: np.random.Generator) -> list[Edit] | None:
    """Matched-magnitude random twin of `ai_edits`, or None when no valid twin was found (record it as `unavailable`).

    Per AI edit: draw a random whitelisted parameter of the same kind for challenge `kind` (no field is used twice), the
    AI edit's magnitude and a random sign; if `validate_edits` rejects the list, flip the sign; if still rejected, redraw
    (at most MAX_REDRAWS draws per edit), else return None. Nothing is ever clipped into range."""
    if kind not in iv.CHALLENGE_KINDS:
        raise ValueError(f"challenge kind must be one of {iv.CHALLENGE_KINDS}, got {kind!r}")
    ai_edits = list(ai_edits)
    if not ai_edits:
        return None
    pool_all = iv.allowed_params(kind)
    chosen: list[Edit] = []
    for ai in ai_edits:
        k = iv.kind_of(ai.param)
        mag = iv.magnitude(version, ai)
        candidates = [p for p in pool_all if iv.kind_of(p) == k and p not in {c.param for c in chosen}]
        found: Edit | None = None
        for _ in range(MAX_REDRAWS):
            if not candidates:
                break
            param = candidates[int(rng.integers(len(candidates)))]
            sign = 1 if rng.random() < 0.5 else -1
            for s in (sign, -sign):
                e = _twin_edit(version, param, mag, s)
                ok, reasons = iv.validate_edits(version, kind, [c.to_dict() for c in chosen] + [e.to_dict()])
                if not reasons:
                    found = e
                    break
            if found is not None:
                break
        if found is None:
            return None
        chosen.append(found)
    return chosen


# ---------------------------------------------------------------------------------------------------------
# heuristic
# ---------------------------------------------------------------------------------------------------------
def _get(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def _median(xs: list[float]) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return float(xs[n // 2]) if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def _as_dict(challenge_result) -> dict:
    return challenge_result.as_dict() if hasattr(challenge_result, "as_dict") else challenge_result


def _signals(kind: str, cr: dict) -> dict:
    seeds = [s for s in cr.get("per_seed", []) if s.get("outcome") != "ERROR"]
    metrics = [s.get("metrics") or {} for s in seeds]
    sat = _median([m.get("saturation_frac") for m in metrics])
    slip = _median([m.get("slip_frac") for m in metrics])
    peak_slip = None
    fx = cr.get("forensics") or {}
    if kind == "push":     # push seeds carry no per-seed saturation: the weak direction's forensics do
        sat = sat if sat is not None else _get(fx, "actuation", "fraction_samples_saturated_push_to_fall")
        slip = slip if slip is not None else _get(fx, "contacts", "fraction_samples_slipping_push_to_fall")
        peak_slip = _get(fx, "contacts", "peak_slip_speed_mps")
    outcomes = [s.get("outcome") for s in seeds]
    return {
        "saturation": sat, "slip": slip, "peak_slip": peak_slip,
        "any_fail": "FAIL" in outcomes, "fell_frac": (sum(bool(m.get("fell")) for m in metrics) / len(metrics)) if metrics else 0.0,
        "falls_without_push": any(m.get("falls_without_push") for m in metrics),
        "backward_weak": any(m.get("weak_direction") in ("backward", "bwd") for m in metrics),
        "outcome": cr.get("outcome"),
    }


def heuristic(version: dict, kind: str, challenge_result) -> list[Edit] | None:
    """Rule-table proposal (`RULES`, first match wins), validated; None if no rule applies or the edits are invalid.

    Deterministic: the same (version, kind, challenge_result) always gives the same edits. If the whole proposal is rejected by
    `validate_edits` (for example the parameter already sits at its bound) each edit is tried alone and the valid ones kept."""
    if kind not in iv.CHALLENGE_KINDS:
        raise ValueError(f"challenge kind must be one of {iv.CHALLENGE_KINDS}, got {kind!r}")
    sig = _signals(kind, _as_dict(challenge_result))
    wanted: list[Edit] = []
    if sig["saturation"] is not None and sig["saturation"] > SATURATION_FRACTION:
        wanted = [Edit("torque_limit", "scale", HEURISTIC_SCALE)]
    elif (sig["slip"] is not None and sig["slip"] > SLIP_FRACTION
          and (sig["peak_slip"] is None or sig["peak_slip"] > SLIP_SPEED_MPS)):
        wanted = [Edit("foot_friction", "scale", HEURISTIC_SCALE)]
    elif kind in ("stand", "push") and (sig["falls_without_push"] or sig["any_fail"]
                                         or (sig["backward_weak"] and sig["outcome"] != "PASS")):
        wanted = [Edit("foot_length", "scale", HEURISTIC_SCALE)]
    elif kind == "walk" and sig["fell_frac"] > 0.5:
        for p in ("walk.balance_gain", "walk.pitch_kp"):
            lo, hi = iv.control_bounds(p)
            wanted.append(Edit(p, "set", float(_control_value(version, p) + HEURISTIC_DELTA_U * (hi - lo)), "both"))
    if not wanted:
        return None
    ok, reasons = iv.validate_edits(version, kind, [e.to_dict() for e in wanted])
    if not reasons:
        return ok
    kept = [e for e in wanted if not iv.validate_edits(version, kind, [e.to_dict()])[1]]
    if not kept:
        return None
    ok, reasons = iv.validate_edits(version, kind, [e.to_dict() for e in kept])
    return ok if not reasons else None
