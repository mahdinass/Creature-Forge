"""Hybrid phase-based, contact-aware gait controller (Phase 2A) and baseline controller adapters.

Controller protocol used by `locomotion.rollout`:
    reset(torque_limit, weight_n)            called once before a rollout
    torque(t, pitch, pitch_rate, q, qd)      demanded joint torque (6), every physics step (1 kHz)
    sense(t, forces)                         per-foot normal force (N), every 200 Hz sample

`GaitParams` / `controller.compute_torque` (the Phase 0 standing + open-loop controller) are untouched;
`OpenLoopController` only adapts them to this protocol.

PhaseGait design (angles in rad, hip>0 swings the foot backward, knee<0 flexes):
* one continuous phase clock phi in [0,1); leg A uses phi, leg B uses phi+0.5. Stance while the leg phase is
  below `duty`, swing afterwards.
* hip: raised-cosine stroke, foot ahead (-A) at touchdown to foot behind (+A) at liftoff during stance, back
  again during swing. Position and velocity are continuous across stance/swing transitions.
* knee: sin^2 swing-lift bump (zero value and slope at both ends) whose timing can be shifted by `knee_shift`
  (the hip-knee phase relationship).
* contact awareness: the debounced estimator (`contact.py`) only influences the controller through (a) a
  *guarded* phase advance when a swing foot lands early (late-swing window, refractory period, rate-limited
  clock speed-up, so impact chatter cannot reset the oscillator) and (b) enabling stance feedback only on
  feet that are actually loaded.
* stance feedback: bounded hip torque on the loaded leg regulating torso pitch to `pitch_ref`, and ankle
  balance torque on loaded feet. Each term is clipped to a fraction of the actuator limit.
* amplitudes ramp in with a smoothstep over RAMP_S so the first references are continuous with standing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict, fields

import numpy as np

from .contact import ContactConfig, FootContactEstimator
from .controller import GaitParams, compute_torque

RAMP_S = 0.5            # amplitude ramp-in time (s)
FB_CAP = 0.5            # stance-feedback torque cap, fraction of the actuator limit
MAX_PHASE_BOOST = 1.0   # clock can speed up by at most this fraction (2x rate) while applying a correction
SYNC_WINDOW = 0.5       # early touchdown is only honoured in the last (1-SYNC_WINDOW) of swing
SYNC_REFRACTORY_S = 0.15
ANKLE_LIM = 0.8

BOUNDS = {
    "freq": (0.5, 2.0),
    "duty": (0.5, 0.8),
    "hip_amp": (0.05, 0.5),
    "knee_amp": (0.1, 1.0),
    "knee_shift": (-0.15, 0.15),
    "stance_knee": (-0.4, 0.0),
    "hip_bias": (-0.2, 0.2),
    "kp": (40.0, 300.0),
    "kd": (2.0, 25.0),
    "balance_gain": (0.0, 150.0),
    "pitch_kp": (0.0, 120.0),
    "pitch_ref": (-0.05, 0.25),
    "sync_gain": (0.0, 1.0),
}


@dataclass(frozen=True)
class PhaseGaitParams:
    freq: float = 1.0
    duty: float = 0.6
    hip_amp: float = 0.25
    knee_amp: float = 0.5
    knee_shift: float = 0.0
    stance_knee: float = -0.1
    hip_bias: float = 0.0
    kp: float = 150.0
    kd: float = 8.0
    balance_gain: float = 60.0
    pitch_kp: float = 40.0
    pitch_ref: float = 0.05
    sync_gain: float = 0.5

    NAMES = tuple(BOUNDS)  # class attribute (not a dataclass field: no annotation)

    def validate(self) -> "PhaseGaitParams":
        for k, (lo, hi) in BOUNDS.items():
            v = getattr(self, k)
            if not (math.isfinite(v) and lo <= v <= hi):
                raise ValueError(f"{k}={v} outside bounds [{lo}, {hi}]")
        return self

    def replace(self, **kw) -> "PhaseGaitParams":
        return PhaseGaitParams(**{**asdict(self), **kw}).validate()

    def as_dict(self) -> dict:
        return asdict(self)

    def to_vector(self) -> np.ndarray:
        return np.array([getattr(self, k) for k in BOUNDS], dtype=float)

    @staticmethod
    def from_vector(v) -> "PhaseGaitParams":
        return PhaseGaitParams(**{k: float(x) for k, x in zip(BOUNDS, v)}).validate()


assert [f.name for f in fields(PhaseGaitParams)] == list(BOUNDS)

LOWER = np.array([lo for lo, _ in BOUNDS.values()])
UPPER = np.array([hi for _, hi in BOUNDS.values()])


def _smoothstep(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def leg_references(p: PhaseGaitParams, phi_leg: float, ramp: float, pitch: float) -> tuple[float, float, float]:
    """Reference (hip, knee, ankle) for one leg at leg phase `phi_leg`, amplitude ramp in [0,1]."""
    a = p.hip_amp * ramp
    if phi_leg < p.duty:
        hip = p.hip_bias - a * math.cos(math.pi * phi_leg / p.duty)
    else:
        hip = p.hip_bias + a * math.cos(math.pi * (phi_leg - p.duty) / (1.0 - p.duty))
    u = ((phi_leg - p.duty - p.knee_shift) % 1.0) / (1.0 - p.duty)
    bump = math.sin(math.pi * u) ** 2 if u < 1.0 else 0.0
    knee = p.stance_knee * ramp - p.knee_amp * ramp * bump
    ankle = -(pitch + hip + knee)
    return hip, knee, min(max(ankle, -ANKLE_LIM), ANKLE_LIM)


class PhaseGaitController:
    name = "phase_gait"

    def __init__(self, params: PhaseGaitParams, contact: ContactConfig = ContactConfig()):
        self.p = params.validate()
        self.contact_cfg = contact

    # Extension hooks (R1 gait initiation overrides these; the defaults reproduce the Phase 2A behaviour exactly).
    _ramp_s = RAMP_S

    def _pitch_ref(self, t: float) -> float:
        return self.p.pitch_ref

    def reset(self, torque_limit: float, weight_n: float) -> None:
        self.limit = torque_limit
        self.est = FootContactEstimator(weight_n, 2, self.contact_cfg)
        self.phi = 0.0
        self.pending = 0.0
        self.last_sync = [-1e9, -1e9]
        self.sync_count = 0
        self._t_prev = 0.0

    # --- per 200 Hz sample -------------------------------------------------------------------------------
    def sense(self, t: float, forces) -> None:
        for ev in self.est.update(t, forces):
            if ev["kind"] != "touchdown" or self.p.sync_gain <= 0.0:
                continue
            k = ev["foot"]
            leg_phi = (self.phi + 0.5 * k) % 1.0
            late_swing = self.p.duty + SYNC_WINDOW * (1.0 - self.p.duty)
            if leg_phi >= late_swing and t - self.last_sync[k] >= SYNC_REFRACTORY_S:
                self.pending += self.p.sync_gain * (1.0 - leg_phi)  # touchdown came early: advance toward stance
                self.last_sync[k] = t
                self.sync_count += 1

    # --- per physics step --------------------------------------------------------------------------------
    def torque(self, t: float, pitch: float, pitch_rate: float, q, qd) -> np.ndarray:
        p = self.p
        dt = t - self._t_prev if t > self._t_prev else 0.0
        self._t_prev = t
        step = min(self.pending, MAX_PHASE_BOOST * p.freq * dt)
        self.pending -= step
        self.phi = (self.phi + p.freq * dt + step) % 1.0
        ramp = _smoothstep(t / self._ramp_s)
        q = q.tolist() if hasattr(q, "tolist") else list(q)
        qd = qd.tolist() if hasattr(qd, "tolist") else list(qd)
        tau = [0.0] * 6
        cap = FB_CAP * self.limit
        for leg in (0, 1):
            ref = leg_references(p, (self.phi + 0.5 * leg) % 1.0, ramp, pitch)
            for j in range(3):
                i = 3 * leg + j
                tau[i] = p.kp * (ref[j] - q[i]) - p.kd * qd[i]
            if self.est.deb[leg]:  # stance feedback only on a physically loaded foot
                fb = p.pitch_kp * (pitch - self._pitch_ref(t)) + 0.25 * p.pitch_kp * pitch_rate
                tau[3 * leg] += min(max(fb, -cap), cap)
                ab = p.balance_gain * (pitch + 0.3 * pitch_rate)
                tau[3 * leg + 2] += min(max(ab, -cap), cap)
        return np.array(tau)


class OpenLoopController:
    """Adapter running the Phase 0 `GaitParams` controller (standing when gait_freq == 0) unchanged."""
    name = "open_loop"

    def __init__(self, gait: GaitParams):
        self.gait = gait.validate()

    def reset(self, torque_limit: float, weight_n: float) -> None:
        pass

    def sense(self, t: float, forces) -> None:
        pass

    def torque(self, t, pitch, pitch_rate, q, qd) -> np.ndarray:
        return compute_torque(self.gait, t, pitch, pitch_rate, q, qd)


@dataclass(frozen=True)
class LagSinusoidParams:
    """Phase 0 sinusoid plus a hip-knee phase lag (rad). Not part of the product controller: it reproduces the
    Phase 2A feasibility exploit (forward displacement via chatter-hopping) as a regression/negative control."""
    gait_freq: float = 1.0
    hip_amp: float = 0.4
    knee_amp: float = 0.4
    lag: float = 0.0
    stand_hip: float = 0.0
    stand_knee: float = -0.1
    kp: float = 150.0
    kd: float = 8.0
    balance_gain: float = 80.0

    def as_dict(self) -> dict:
        return asdict(self)


class LagSinusoidController:
    name = "lag_sinusoid"

    def __init__(self, params: LagSinusoidParams):
        self.p = params

    def reset(self, torque_limit: float, weight_n: float) -> None:
        pass

    def sense(self, t: float, forces) -> None:
        pass

    def torque(self, t, pitch, pitch_rate, q, qd) -> np.ndarray:
        g = self.p
        w = 2 * math.pi * g.gait_freq
        ref = np.zeros(6)
        for i, ph in enumerate((0.0, math.pi)):
            hip = g.stand_hip + g.hip_amp * math.sin(w * t + ph)
            knee = g.stand_knee - g.knee_amp * max(0.0, math.cos(w * t + ph + g.lag))
            ref[3 * i], ref[3 * i + 1], ref[3 * i + 2] = hip, knee, -(pitch + hip + knee)
        tau = g.kp * (ref - q) - g.kd * qd
        tau[2] += g.balance_gain * (pitch + 0.3 * pitch_rate)
        tau[5] += g.balance_gain * (pitch + 0.3 * pitch_rate)
        return tau
