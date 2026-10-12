"""Baseline controller: joint PD with a bounded open-loop sinusoidal gait and ankle balance."""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

# index layout matches morphology.JOINTS: hip_l, knee_l, ankle_l, hip_r, knee_r, ankle_r
CTRL_BOUNDS = {
    "kp": (0.0, 500.0),
    "kd": (0.0, 50.0),
    "gait_freq": (0.0, 3.0),
    "hip_amp": (0.0, 0.8),
    "knee_amp": (0.0, 1.2),
    "balance_gain": (0.0, 200.0),
    "stand_hip": (-0.3, 0.3),
    "stand_knee": (-0.8, 0.0),
}


@dataclass(frozen=True)
class GaitParams:
    kp: float = 150.0
    kd: float = 8.0
    gait_freq: float = 0.0  # Hz; 0 => standing
    hip_amp: float = 0.0  # rad
    knee_amp: float = 0.0  # rad
    balance_gain: float = 80.0  # ankle torque feedback on torso pitch / rate
    stand_hip: float = 0.0
    stand_knee: float = 0.0

    def validate(self) -> "GaitParams":
        for k, (lo, hi) in CTRL_BOUNDS.items():
            v = getattr(self, k)
            if not (lo <= v <= hi):
                raise ValueError(f"{k}={v} outside bounds [{lo}, {hi}]")
        return self

    def replace(self, **kw) -> "GaitParams":
        return GaitParams(**{**asdict(self), **kw}).validate()

    def as_dict(self) -> dict:
        return asdict(self)


def joint_targets(g: GaitParams, t: float, pitch: float) -> np.ndarray:
    """Reference joint angles [hip_l, knee_l, ankle_l, hip_r, knee_r, ankle_r]."""
    w = 2 * np.pi * g.gait_freq
    ref = np.zeros(6)
    for i, phase in enumerate((0.0, np.pi)):
        s = np.sin(w * t + phase)
        hip = g.stand_hip + g.hip_amp * s
        knee = g.stand_knee - g.knee_amp * max(0.0, np.cos(w * t + phase))
        ref[3 * i] = hip
        ref[3 * i + 1] = knee
        ref[3 * i + 2] = -(pitch + hip + knee)  # keep foot flat in the world
    return ref


def compute_torque(g: GaitParams, t: float, pitch: float, pitch_rate: float,
                   q: np.ndarray, qd: np.ndarray) -> np.ndarray:
    """Unclipped demanded torque (the actuator clips to its limit; demand is logged)."""
    ref = joint_targets(g, t, pitch)
    tau = g.kp * (ref - q) - g.kd * qd
    tau[2] += g.balance_gain * (pitch + 0.3 * pitch_rate)
    tau[5] += g.balance_gain * (pitch + 0.3 * pitch_rate)
    return tau
