"""R1 gait-initiation extension of the Phase 2A phase-gait controller (arm C).

Two optional parameters on top of the 13 `PhaseGaitParams`:
  ramp_s      amplitude ramp-in time (s); Phase 2A fixed this at RAMP_S = 0.5 s
  start_lean  extra forward torso-pitch reference (rad) that decays to zero over LEAN_DECAY_S with a smoothstep

At the defaults (ramp_s = 0.5, start_lean = 0.0) the controller is bit-identical to `PhaseGaitController`
(tested): `x + 0.0 * k == x` exactly in IEEE arithmetic and the ramp divisor is the same constant. The frozen Phase 2A
controller therefore reproduces exactly, and is candidate zero of every R1 run.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .contact import ContactConfig
from .morphology import BipedParams
from .phasegait import (BOUNDS, LOWER, RAMP_S, UPPER, PhaseGaitController, PhaseGaitParams, _smoothstep)

LEAN_DECAY_S = 1.0
INIT_BOUNDS = {"ramp_s": (0.2, 2.0), "start_lean": (0.0, 0.15)}
INIT_DEFAULTS = {"ramp_s": RAMP_S, "start_lean": 0.0}
LOWER15 = np.concatenate([LOWER, [lo for lo, _ in INIT_BOUNDS.values()]])
UPPER15 = np.concatenate([UPPER, [hi for _, hi in INIT_BOUNDS.values()]])


@dataclass(frozen=True)
class InitParams:
    ramp_s: float = INIT_DEFAULTS["ramp_s"]
    start_lean: float = INIT_DEFAULTS["start_lean"]

    def validate(self) -> "InitParams":
        for k, (lo, hi) in INIT_BOUNDS.items():
            v = getattr(self, k)
            if not (np.isfinite(v) and lo <= v <= hi):
                raise ValueError(f"{k}={v} outside bounds [{lo}, {hi}]")
        return self

    def as_dict(self) -> dict:
        return asdict(self)


class PhaseGaitInitController(PhaseGaitController):
    name = "phase_gait_init"

    def __init__(self, params: PhaseGaitParams, init: InitParams = InitParams(),
                 contact: ContactConfig = ContactConfig()):
        super().__init__(params, contact)
        self.init = init.validate()
        self._ramp_s = self.init.ramp_s

    def _pitch_ref(self, t: float) -> float:
        return self.p.pitch_ref + self.init.start_lean * (1.0 - _smoothstep(t / LEAN_DECAY_S))


def controller_from_vector(vector, body=None):
    """13-D -> PhaseGaitController (Phase 2A family); 15-D -> PhaseGaitInitController (arm C);
    17-D -> PhaseGaitFPController (15 + fp_kd, fp_kv; needs `body` for the leg geometry). `body` is ignored for 13/15-D."""
    v = np.asarray(vector, dtype=float)
    n15 = len(BOUNDS) + len(INIT_BOUNDS)
    if len(v) == n15 + 2:
        if body is None:
            raise ValueError("a 17-parameter controller needs the body (leg geometry)")
        from .phasegait_fp import FPParams, PhaseGaitFPController  # local import: phasegait_fp imports this module
        n = len(BOUNDS)
        return PhaseGaitFPController(PhaseGaitParams.from_vector(v[:n]), InitParams(*[float(x) for x in v[n:n15]]),
                                     FPParams(*[float(x) for x in v[n15:]]), body=body)
    base = PhaseGaitParams.from_vector(v[:len(BOUNDS)])
    if len(v) == len(BOUNDS):
        return PhaseGaitController(base)
    if len(v) == len(BOUNDS) + len(INIT_BOUNDS):
        return PhaseGaitInitController(base, InitParams(*[float(x) for x in v[len(BOUNDS):]]))
    raise ValueError(f"expected 13, 15 or 17 parameters, got {len(v)}")


def controller_from_export(d: dict):
    """(controller, body) from a candidate export; supports both `phase_gait` and `phase_gait_init`."""
    kind = d.get("controller")
    base = PhaseGaitParams(**d["params"]).validate()
    if kind == "phase_gait":
        ctrl = PhaseGaitController(base)
    elif kind == "phase_gait_init":
        ctrl = PhaseGaitInitController(base, InitParams(**d["init"]))
    else:
        raise ValueError(f"unsupported controller {kind!r}")
    return ctrl, BipedParams(**d["body"]).validate()
