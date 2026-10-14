"""Experimental sandbox bodies: a wider, still safe, design space for creative (and deliberately bad) bipeds.

Scientific validation (`morphology.BOUNDS`, `BipedParams.validate`) is untouched and still governs every registered
experiment. A `SandboxBody` extends it with
  * wider finite, strictly positive bounds (`SANDBOX_BOUNDS`),
  * real per-leg lengths (left and right may differ),
  * a real initial joint configuration (`pose`: torso pitch, then hip/knee/ankle of the left and right leg).
It is still a planar two-legged model with a fixed-shape torso, the same joint ranges and the same actuators.
Safety is not relaxed: values must be finite and positive, the model must compile in MuJoCo, runs are bounded in
time by the API, and non-finite telemetry is reported as an error instead of being served.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace

import mujoco
import numpy as np

from .controller import GaitParams
from .failures import detect_failures
from .morphology import BOUNDS, JOINTS, BipedParams, _leg_xml
from .render_export import payload_from_telemetry
from .simulate import Push, run_rollout

SANDBOX_BOUNDS = {
    "torso_mass": (0.2, 80.0),
    "thigh_length": (0.05, 1.2),
    "shank_length": (0.05, 1.2),
    "foot_length": (0.02, 0.6),
    "foot_friction": (0.01, 3.0),
    "torque_limit": (0.5, 500.0),
    "leg_density": (50.0, 8000.0),
}
# pitch, then (hip, knee, ankle) of the left and right leg. Joint ranges are those of the model in morphology.py.
POSE_RANGES = [(-1.5, 1.5), (-1.2, 1.2), (-2.2, 0.0), (-0.8, 0.8), (-1.2, 1.2), (-2.2, 0.0), (-0.8, 0.8)]
POSE_NAMES = ["torso pitch", "left hip", "left knee", "left ankle", "right hip", "right knee", "right ankle"]


class SandboxError(ValueError):
    """The sandbox body cannot be built or run; the message says exactly why."""


@dataclass(frozen=True)
class SandboxBody(BipedParams):
    thigh_length_r: float | None = None  # None: the right leg uses the left leg's length
    shank_length_r: float | None = None
    foot_length_r: float | None = None
    pose: tuple = (0.0,) * 7

    def leg(self, side: str) -> tuple[float, float, float]:
        if side == "l":
            return self.thigh_length, self.shank_length, self.foot_length
        return (self.thigh_length if self.thigh_length_r is None else self.thigh_length_r,
                self.shank_length if self.shank_length_r is None else self.shank_length_r,
                self.foot_length if self.foot_length_r is None else self.foot_length_r)

    def validate(self) -> "SandboxBody":
        def check(name: str, v, key: str) -> None:
            lo, hi = SANDBOX_BOUNDS[key]
            if v is None:
                return
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
                raise ValueError(f"{name} must be a finite number, got {v!r}")
            if not (lo <= v <= hi):
                raise ValueError(f"{name}={v:g} is outside the sandbox range [{lo:g}, {hi:g}]")
        for k in SANDBOX_BOUNDS:
            check(k, getattr(self, k), k)
        check("thigh_length (right)", self.thigh_length_r, "thigh_length")
        check("shank_length (right)", self.shank_length_r, "shank_length")
        check("foot_length (right)", self.foot_length_r, "foot_length")
        if len(self.pose) != 7:
            raise ValueError("pose needs 7 numbers: torso pitch, then hip/knee/ankle for the left and right leg")
        for name, v, (lo, hi) in zip(POSE_NAMES, self.pose, POSE_RANGES):
            if not (isinstance(v, (int, float)) and math.isfinite(v)):
                raise ValueError(f"{name} angle must be a finite number, got {v!r}")
            if not (lo <= v <= hi):
                raise ValueError(f"{name} angle {v:.2f} rad is outside the joint range [{lo:g}, {hi:g}]")
        return self

    def replace(self, **kw) -> "SandboxBody":
        return replace(self, **kw).validate()

    def as_dict(self) -> dict:
        d = asdict(self)
        d["pose"] = list(self.pose)
        return d

    def build_model(self) -> mujoco.MjModel:  # called by morphology.build_model
        return sandbox_model(self)

    def outside_scientific_bounds(self) -> list[str]:
        """Human-readable list of values that fall outside the range used by the registered experiments."""
        out = []
        for k, (lo, hi) in BOUNDS.items():
            v = getattr(self, k)
            if not (lo <= v <= hi):
                out.append(f"{k.replace('_', ' ')} {v:g} (verified experiments use {lo:g} to {hi:g})")
        for key in ("thigh_length", "shank_length", "foot_length"):
            v = getattr(self, key + "_r")
            lo, hi = BOUNDS[key]
            if v is not None and not (lo <= v <= hi):
                out.append(f"right {key.replace('_', ' ')} {v:g} (verified experiments use {lo:g} to {hi:g})")
        return out


def _mjcf(b: SandboxBody) -> str:
    tl, sl, _ = zip(b.leg("l"), b.leg("r"))
    leg_h = max(tl[i] + sl[i] for i in range(2)) + 0.04 + 0.12
    z0 = leg_h + 0.02
    torso_density = b.torso_mass / (0.2 * 0.12 * 0.3)
    lim = b.torque_limit
    acts = "\n".join(f'    <motor name="{j}" joint="{j}" ctrllimited="true" ctrlrange="{-lim} {lim}"/>' for j in JOINTS)
    legs = "\n".join(_leg_xml(s, *b.leg(s), b) for s in "lr")
    return f"""<mujoco model="sandbox_biped">
  <compiler angle="radian"/>
  <option timestep="0.001" integrator="implicitfast" gravity="0 0 -9.81"/>
  <worldbody>
    <geom name="floor" type="plane" size="50 5 0.1" contype="1" conaffinity="2" friction="0.05 0.005 0.0001"/>
    <body name="torso" pos="0 0 {z0}">
      <joint name="root_x" type="slide" axis="1 0 0"/>
      <joint name="root_z" type="slide" axis="0 0 1"/>
      <joint name="root_pitch" type="hinge" axis="0 1 0"/>
      <geom name="torso" type="box" pos="0 0 0.03" size="0.06 0.06 0.15" density="{torso_density}"
            contype="2" conaffinity="1"/>
{legs}
    </body>
  </worldbody>
  <actuator>
{acts}
  </actuator>
</mujoco>"""


def sandbox_model(body: SandboxBody) -> mujoco.MjModel:
    try:
        body.validate()
    except ValueError as exc:
        raise SandboxError(str(exc)) from exc
    try:
        model = mujoco.MjModel.from_xml_string(_mjcf(body))
    except Exception as exc:  # MuJoCo raises ValueError with its own message
        raise SandboxError(f"MuJoCo could not compile this body: {exc}") from exc
    if not (np.all(np.isfinite(model.body_mass)) and np.all(model.body_mass >= 0) and np.all(np.isfinite(model.body_inertia))):
        raise SandboxError("MuJoCo compiled this body with a non-finite or negative mass or inertia")
    return model


def explain_outcome(tel: dict, body: SandboxBody, events=None) -> dict:
    """Plain-language account of a rollout. Every reason cites a measurement; none claims a proven cause."""
    events = detect_failures(tel, body)
    by = {e.kind: e for e in events}
    z = tel["torso_pos"][:, 1]
    t = tel["t"]
    reasons: list[dict] = []
    fall = by.get("fall")
    if fall is None:
        verdict = "stayed_upright"
        reasons.append({"kind": "upright", "text": f"It stayed upright for the whole run. Lowest torso height {z.min():.2f} m of {z[0]:.2f} m at the start.",
                        "measured": {"min_torso_height": float(z.min()), "initial_torso_height": float(z[0])}})
    else:
        verdict = "fell"
        i = int(np.searchsorted(t, fall.time))
        pitch = float(tel["torso_pitch"][min(i, len(t) - 1)])
        direction = "forward" if pitch > 0 else "backward"
        reasons.append({"kind": "fall", "text": f"It fell at {fall.time:.2f} s, toppling {direction} (torso pitch {pitch:.2f} rad, torso height {fall.evidence['torso_height']:.2f} m of {z[0]:.2f} m).",
                        "measured": {"time": fall.time, "pitch": pitch, "torso_height": fall.evidence["torso_height"]}})
        j = max(0, i - 40)  # the 0.2 s before the fall
        lo, hi, com = tel["support_x_min"][j:i + 1], tel["support_x_max"][j:i + 1], tel["com_pos"][j:i + 1, 0]
        ok = np.isfinite(lo) & np.isfinite(hi)
        if ok.any():
            k = np.where(ok)[0][-1]
            if com[k] > hi[k] + 1e-3:
                reasons.append({"kind": "support", "text": f"Just before the fall the centre of mass was {com[k] - hi[k]:.2f} m ahead of the front of the feet, so nothing under it could catch the lean.",
                                "measured": {"com_beyond_front_m": float(com[k] - hi[k])}})
            elif com[k] < lo[k] - 1e-3:
                reasons.append({"kind": "support", "text": f"Just before the fall the centre of mass was {lo[k] - com[k]:.2f} m behind the heel, so nothing under it could catch the lean.",
                                "measured": {"com_behind_heel_m": float(lo[k] - com[k])}})
        else:
            reasons.append({"kind": "support", "text": "No foot was carrying load just before the fall.", "measured": {"loaded_samples": 0}})
    sat = by.get("actuator_saturation")
    if sat is not None:
        frac = sat.evidence["overall_fraction_saturated"]
        reasons.append({"kind": "actuators", "text": f"The motors were at their {body.torque_limit:g} N·m limit for {frac * 100:.0f}% of the run (the controller asked for up to {sat.evidence['peak_demand']:.0f} N·m).",
                        "measured": {"fraction_saturated": frac, "peak_demand": sat.evidence["peak_demand"], "torque_limit": body.torque_limit}})
    slip = by.get("foot_slip")
    if slip is not None:
        reasons.append({"kind": "slip", "text": f"A foot slid on the floor (up to {slip.evidence['peak_slip_speed']:.2f} m/s) with friction μ = {body.foot_friction:g}.",
                        "measured": {"peak_slip_speed": slip.evidence["peak_slip_speed"], "friction": body.foot_friction}})
    if any(abs(v) > 1e-6 for v in body.pose):
        reasons.append({"kind": "pose", "text": f"It started from the pose you drew (torso lean {math.degrees(body.pose[0]):.0f}°), not from standing.",
                        "measured": {"initial_pose": list(body.pose)}})
    notes = [f"Outside the verified design range: {s}." for s in body.outside_scientific_bounds()]
    headline = ("It stayed on its feet." if verdict == "stayed_upright" else f"It fell after {by['fall'].time:.1f} s.")
    return {"verdict": verdict, "headline": headline, "reasons": reasons, "design_notes": notes,
            "caveat": "These are measurements from this one run, listed as contributing observations, not proven causes."}


def run_sandbox(body: SandboxBody, gait: GaitParams, *, seed: int = 0, duration: float = 5.0, push: Push | None = None) -> dict:
    """Run a sandbox body and return (telemetry with poses). Raises SandboxError, never lets MuJoCo state escape."""
    sandbox_model(body)  # structured compile errors before any rollout
    try:
        tel = run_rollout(body, gait, seed=seed, duration=duration, push=push, record_poses=True)
    except SandboxError:
        raise
    except Exception as exc:
        raise SandboxError(f"The simulation could not run: {exc}") from exc
    for k, v in tel.items():
        if k in ("support_x_min", "support_x_max", "cop_x"):
            continue  # NaN means "no foot loaded", by design
        if not np.all(np.isfinite(v)):
            raise SandboxError(f"The simulation became numerically unstable (non-finite {k}). Try a more moderate body.")
    return tel


def build_sandbox_payload(body: SandboxBody, gait: GaitParams, *, seed: int = 0, duration: float = 5.0,
                          push: Push | None = None) -> dict:
    tel = run_sandbox(body, gait, seed=seed, duration=duration, push=push)
    payload = payload_from_telemetry(body, gait, tel, seed=seed, duration=duration, push=push)
    payload["sandbox"] = True
    payload["explanation"] = explain_outcome(tel, body)
    return payload
