"""Failure event detectors. Each emits an event plus measured evidence, never a causal verdict."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np

from .morphology import BipedParams, JOINTS

SAMPLE_DT = 1.0 / 200.0  # matches simulate.LOG_EVERY * timestep


@dataclass(frozen=True)
class FailureEvent:
    kind: str
    time: float  # onset of the sustained condition (s)
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _first_sustained(mask: np.ndarray, min_samples: int) -> int | None:
    """Index where `mask` first stays True for at least `min_samples` consecutive samples."""
    run = 0
    for i, v in enumerate(mask):
        run = run + 1 if v else 0
        if run >= min_samples:
            return i - min_samples + 1
    return None


def detect_failures(tel: dict, body: BipedParams, *, fall_height_frac: float = 0.5,
                    fall_pitch: float = 1.0, sustain_s: float = 0.1,
                    slip_speed: float = 0.15, saturation_s: float = 0.25) -> list[FailureEvent]:
    t = tel["t"]
    n_sus = max(1, int(round(sustain_s / SAMPLE_DT)))
    events: list[FailureEvent] = []

    z = tel["torso_pos"][:, 1]
    z_ref = z[0]
    low = z < fall_height_frac * z_ref
    tilted = np.abs(tel["torso_pitch"]) > fall_pitch
    i = _first_sustained(low | tilted, n_sus)
    if i is not None:
        events.append(FailureEvent("fall", float(t[i]), {
            "torso_height": float(z[i]), "initial_torso_height": float(z_ref),
            "torso_pitch": float(tel["torso_pitch"][i]), "min_torso_height": float(z.min()),
        }))

    demand = np.abs(tel["ctrl_demand"])
    saturated = demand > body.torque_limit * 0.999
    j = _first_sustained(saturated.any(axis=1), max(1, int(round(saturation_s / SAMPLE_DT))))
    if j is not None:
        per_joint = saturated.mean(axis=0)
        events.append(FailureEvent("actuator_saturation", float(t[j]), {
            "torque_limit": body.torque_limit,
            "fraction_saturated_by_joint": {JOINTS[k]: float(per_joint[k]) for k in range(6)},
            "overall_fraction_saturated": float(saturated.any(axis=1).mean()),
            "peak_demand": float(demand.max()),
        }))

    slipping = ((tel["foot_slip_speed"] > slip_speed) & (tel["foot_contact"] > 0.5)).any(axis=1)
    k = _first_sustained(slipping, n_sus)
    if k is not None:
        events.append(FailureEvent("foot_slip", float(t[k]), {
            "peak_slip_speed": float(tel["foot_slip_speed"].max()),
            "foot_friction": body.foot_friction,
            "fraction_of_time_slipping": float(slipping.mean()),
        }))
    return events
