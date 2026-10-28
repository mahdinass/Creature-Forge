"""Swing-foot placement feedback on top of the R1 gait-initiation controller (17 parameters).

Two extra dimensionless gains on `PhaseGaitInitController` (Raibert; SIMBICON, Yin et al. 2007: swing hip target += c_d*d + c_v*v):
  fp_kd   gain on the stance hip's horizontal offset from the stance ankle, d / L
  fp_kv   gain on its rate, v / sqrt(g L)          (L = mean leg length, thigh + shank)

Proprioceptive estimate, no extra sensors. MuJoCo hinges about +y: hip > 0 swings the foot backward and pitch > 0 leans the torso
forward, so the absolute segment angles (positive = segment points back-and-down) are a1 = pitch + hip, a2 = pitch + hip + knee and
the horizontal hip-minus-ankle offset of a leg is d_leg = thigh*sin(a1) + shank*sin(a2) (positive = hip ahead of the ankle; verified
against `data.xpos` in the tests). With the stance foot fixed, v = d(d_leg)/dt is the hip's horizontal speed. The stance leg is the
loaded one per the controller's debounced estimator, preferring legs the clock has in stance (a swing foot that lands early is
not yet the stance leg); both candidates: the one whose ankle is further behind the hip; none: hold. The estimate is low-passed
(FILTER_S) and the swing target is slew-limited (SLEW) so a stance hand-over cannot make the hip reference jump.

Swing-hip offset: -(fp_kd*d/L + fp_kv*v/sqrt(g L)) clipped to +-OFFSET_LIM rad (negative hip = foot placed further forward),
times the amplitude ramp, blended in with a smoothstep over the first BLEND of swing. At touchdown the value is latched and decays to
zero with (1 - smoothstep) over stance, so the hip reference stays continuous. At fp_kd = fp_kv = 0 every offset is exactly 0.0 and
the torque is bit-identical to `PhaseGaitInitController`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from .contact import ContactConfig
from .phasegait import ANKLE_LIM, FB_CAP, MAX_PHASE_BOOST, PhaseGaitParams, _smoothstep, leg_references
from .phasegait_init import LOWER15, UPPER15, InitParams, PhaseGaitInitController

G = 9.81
OFFSET_LIM = 0.5
BLEND = 0.3
FILTER_S = 0.03          # first-order low-pass time constant of the (d, v) estimate (stance-leg hand-over, contact chatter)
SLEW = 20.0              # rad/s: the raw swing target may not move faster than this (keeps the hip reference continuous)
FP_BOUNDS = {"fp_kd": (0.0, 1.5), "fp_kv": (0.0, 1.5)}
FP_NAMES = tuple(FP_BOUNDS)
LOWER17 = np.concatenate([LOWER15, [lo for lo, _ in FP_BOUNDS.values()]])
UPPER17 = np.concatenate([UPPER15, [hi for _, hi in FP_BOUNDS.values()]])


@dataclass(frozen=True)
class FPParams:
    fp_kd: float = 0.0
    fp_kv: float = 0.0

    def validate(self) -> "FPParams":
        for k, (lo, hi) in FP_BOUNDS.items():
            v = getattr(self, k)
            if not (math.isfinite(v) and lo <= v <= hi):
                raise ValueError(f"{k}={v} outside bounds [{lo}, {hi}]")
        return self

    def as_dict(self) -> dict:
        return asdict(self)


def _legs(body) -> list[tuple[float, float]]:
    if hasattr(body, "leg"):
        return [tuple(body.leg(s)[:2]) for s in "lr"]
    return [(float(body.thigh_length), float(body.shank_length))] * 2


class PhaseGaitFPController(PhaseGaitInitController):
    name = "phase_gait_fp"

    def __init__(self, params: PhaseGaitParams, init: InitParams = InitParams(), fp: FPParams = FPParams(), *, body,
                 contact: ContactConfig = ContactConfig()):
        super().__init__(params, init, contact)
        if body is None:
            raise ValueError("PhaseGaitFPController needs the body (leg geometry)")
        self.fp = fp.validate()
        self.legs = _legs(body)
        self.L = sum(t + s for t, s in self.legs) / 2.0

    def reset(self, torque_limit: float, weight_n: float) -> None:
        super().reset(torque_limit, weight_n)
        self._d = 0.0
        self._v = 0.0
        self._have = False
        self._tgt = 0.0                 # slew-limited raw swing target (rad), before ramp and blend
        self._off = [0.0, 0.0]          # last applied offset per leg
        self._latch = [0.0, 0.0]
        self._swing = [False, False]

    def leg_offset(self, leg: int, pitch: float, pitch_rate: float, q, qd) -> tuple[float, float]:
        """(d_leg, d_leg rate): horizontal hip-minus-ankle offset of one leg (positive = hip ahead) from joint angles/rates."""
        t, s = self.legs[leg]
        a1 = pitch + q[3 * leg]
        a2 = a1 + q[3 * leg + 1]
        w1 = pitch_rate + qd[3 * leg]
        w2 = w1 + qd[3 * leg + 1]
        return (t * math.sin(a1) + s * math.sin(a2), t * math.cos(a1) * w1 + s * math.cos(a2) * w2)

    def _estimate(self, dt: float, pitch, pitch_rate, q, qd) -> None:
        loaded = [leg for leg in (0, 1) if self.est.deb[leg]]
        if not loaded:
            return                      # hold the last estimate
        clock = [leg for leg in loaded if (self.phi + 0.5 * leg) % 1.0 < self.p.duty]
        cands = clock or loaded
        geo = {leg: self.leg_offset(leg, pitch, pitch_rate, q, qd) for leg in cands}
        d, v = geo[max(cands, key=lambda leg: geo[leg][0])]
        if not self._have:
            self._d, self._v, self._have = d, v, True
        else:
            a = dt / (FILTER_S + dt)
            self._d += a * (d - self._d)
            self._v += a * (v - self._v)

    def _update_target(self, dt: float) -> None:
        fp = self.fp
        raw = -(fp.fp_kd * self._d / self.L + fp.fp_kv * self._v / math.sqrt(G * self.L))
        raw = min(max(raw, -OFFSET_LIM), OFFSET_LIM)
        lim = SLEW * dt
        self._tgt += min(max(raw - self._tgt, -lim), lim)

    def _offset(self, leg: int, phi_leg: float, ramp: float) -> float:
        p = self.p
        in_swing = phi_leg >= p.duty
        if in_swing:
            off = _smoothstep((phi_leg - p.duty) / (1.0 - p.duty) / BLEND) * (self._tgt * ramp)
        else:
            if self._swing[leg]:        # swing -> stance: latch the value the hip reference had
                self._latch[leg] = self._off[leg]
            off = self._latch[leg] * (1.0 - _smoothstep(phi_leg / p.duty))
        self._swing[leg] = in_swing
        self._off[leg] = off
        return off

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
        self._estimate(dt, pitch, pitch_rate, q, qd)
        self._update_target(dt)
        tau = [0.0] * 6
        cap = FB_CAP * self.limit
        for leg in (0, 1):
            phi_leg = (self.phi + 0.5 * leg) % 1.0
            ref = leg_references(p, phi_leg, ramp, pitch)
            off = self._offset(leg, phi_leg, ramp)
            if off != 0.0:
                hip = ref[0] + off
                ankle = -(pitch + hip + ref[1])     # the foot stays flat relative to the world
                ref = (hip, ref[1], min(max(ankle, -ANKLE_LIM), ANKLE_LIM))
            for j in range(3):
                i = 3 * leg + j
                tau[i] = p.kp * (ref[j] - q[i]) - p.kd * qd[i]
            if self.est.deb[leg]:
                fb = p.pitch_kp * (pitch - self._pitch_ref(t)) + 0.25 * p.pitch_kp * pitch_rate
                tau[3 * leg] += min(max(fb, -cap), cap)
                ab = p.balance_gain * (pitch + 0.3 * pitch_rate)
                tau[3 * leg + 2] += min(max(ab, -cap), cap)
        return np.array(tau)
