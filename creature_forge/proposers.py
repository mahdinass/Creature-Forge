"""Non-AI proposers using exactly the intervention space the model gets: ONE body parameter, within BOUNDS.

* `random_proposals`: uniformly random (parameter, value). It never sees evidence, results or any list of
  successful candidates; the only input is an RNG seed and the baseline (to avoid no-op proposals).
* `heuristic_proposal`: a rule table keyed on a deterministic mechanism screen of the forensic evidence.
  HONEST PRIOR KNOWLEDGE: the author knew, before the rule was written, that a larger support polygon
  (longer foot) generally helps against tipping, and from Phase 0 that foot length mattered for this very
  scenario. The multiplicative factors below are generic rules of thumb fixed BEFORE any candidate was
  evaluated; they were not tuned to the known 16 cm answer (x1.5 gives 12 cm, not 16 cm).
"""
from __future__ import annotations

import numpy as np

from .morphology import BOUNDS, BipedParams

HEURISTIC_FACTORS = {"foot_length": 1.5, "torque_limit": 1.5, "foot_friction": 1.5}
SATURATION_FRACTION = 0.05
SLIP_FRACTION = 0.10
SLIP_SPEED_MPS = 0.15
MECHANISMS = ("tipping_support_margin", "actuator_saturation", "foot_slip")


def random_proposals(seed: int, n: int, body: BipedParams) -> list[dict]:
    rng = np.random.default_rng(seed)
    names = sorted(BOUNDS)
    out = []
    while len(out) < n:
        p = names[int(rng.integers(len(names)))]
        lo, hi = BOUNDS[p]
        v = float(rng.uniform(lo, hi))
        if v != getattr(body, p):
            out.append({"parameter": p, "value": v})
    return out


def classify_mechanism(forensics: dict) -> str | None:
    """Deterministic screen over measured quantities; None when no mechanism is supported by the data."""
    act, con, fail = (forensics[k] for k in ("actuation", "contacts", "failure"))
    if act["fraction_samples_saturated_push_to_fall"] > SATURATION_FRACTION:
        return "actuator_saturation"
    if (con["fraction_samples_slipping_push_to_fall"] > SLIP_FRACTION
            and con["peak_slip_speed_mps"] > SLIP_SPEED_MPS):
        return "foot_slip"
    if fail["fell"] and fail["instability_onset_s"] is not None and fail["xcom_margin_recovered_s"] is None:
        return "tipping_support_margin"
    return None


def heuristic_proposal(forensics: dict, body: BipedParams) -> dict | None:
    """One rule-based proposal, or None (abstain) when the mechanism screen finds nothing."""
    mech = classify_mechanism(forensics)
    param = {"tipping_support_margin": "foot_length", "actuator_saturation": "torque_limit",
             "foot_slip": "foot_friction"}.get(mech or "")
    if param is None:
        return None
    lo, hi = BOUNDS[param]
    value = min(hi, max(lo, getattr(body, param) * HEURISTIC_FACTORS[param]))
    if value == getattr(body, param):
        return None
    return {"parameter": param, "value": float(value), "mechanism": mech,
            "rule": f"{mech} -> {param} x{HEURISTIC_FACTORS[param]} (bounded)"}
