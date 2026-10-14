"""Parametric planar biped morphology. MuJoCo MJCF is generated from bounded parameters."""
from __future__ import annotations

from dataclasses import dataclass, asdict, fields

import mujoco

# (min, max) physical bounds. Changes outside these are rejected, not clipped.
BOUNDS = {
    "torso_mass": (1.0, 15.0),
    "thigh_length": (0.15, 0.6),
    "shank_length": (0.15, 0.6),
    "foot_length": (0.06, 0.30),
    "foot_friction": (0.05, 2.0),
    "torque_limit": (2.0, 200.0),
    "leg_density": (200.0, 3000.0),
}

JOINTS = ("hip_l", "knee_l", "ankle_l", "hip_r", "knee_r", "ankle_r")


@dataclass(frozen=True)
class BipedParams:
    torso_mass: float = 5.0  # kg
    thigh_length: float = 0.30  # m
    shank_length: float = 0.30  # m
    foot_length: float = 0.16  # m
    foot_friction: float = 1.0  # Coulomb coefficient
    torque_limit: float = 60.0  # N*m per joint
    leg_density: float = 1000.0  # kg/m^3

    def validate(self) -> "BipedParams":
        for k, (lo, hi) in BOUNDS.items():
            v = getattr(self, k)
            if not (lo <= v <= hi):
                raise ValueError(f"{k}={v} outside bounds [{lo}, {hi}]")
        return self

    def replace(self, **kw) -> "BipedParams":
        return BipedParams(**{**asdict(self), **kw}).validate()

    def as_dict(self) -> dict:
        return asdict(self)


def _leg(side: str, p: BipedParams) -> str:
    return _leg_xml(side, p.thigh_length, p.shank_length, p.foot_length, p)


def _leg_xml(side: str, t: float, s: float, f: float, p: BipedParams) -> str:
    """One leg with explicit segment lengths (the scientific path passes the shared lengths; the sandbox may differ per leg)."""
    col = 'contype="2" conaffinity="1" condim="3"'
    return f"""
      <body name="thigh_{side}" pos="0 0 -0.12">
        <joint name="hip_{side}" type="hinge" axis="0 1 0" range="-1.2 1.2" damping="0.5" armature="0.01"/>
        <geom type="capsule" fromto="0 0 0 0 0 {-t}" size="0.04" density="{p.leg_density}" {col}/>
        <body name="shank_{side}" pos="0 0 {-t}">
          <joint name="knee_{side}" type="hinge" axis="0 1 0" range="-2.2 0.0" damping="0.5" armature="0.01"/>
          <geom type="capsule" fromto="0 0 0 0 0 {-s}" size="0.035" density="{p.leg_density}" {col}/>
          <body name="foot_{side}" pos="0 0 {-s}">
            <joint name="ankle_{side}" type="hinge" axis="0 1 0" range="-0.8 0.8" damping="0.5" armature="0.005"/>
            <geom name="foot_{side}" type="box" pos="{f * 0.25} 0 -0.02" size="{f / 2} 0.04 0.02"
                  density="{p.leg_density}" friction="{p.foot_friction} 0.005 0.0001" {col}/>
          </body>
        </body>
      </body>"""


def build_mjcf(p: BipedParams) -> str:
    p.validate()
    leg_h = p.thigh_length + p.shank_length + 0.04 + 0.12
    z0 = leg_h + 0.02
    torso_vol = 0.2 * 0.12 * 0.3
    torso_density = p.torso_mass / torso_vol
    tl = p.torque_limit
    acts = "\n".join(
        f'    <motor name="{j}" joint="{j}" ctrllimited="true" ctrlrange="{-tl} {tl}"/>' for j in JOINTS
    )
    return f"""<mujoco model="biped">
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
{_leg("l", p)}
{_leg("r", p)}
    </body>
  </worldbody>
  <actuator>
{acts}
  </actuator>
</mujoco>"""


def build_model(p: BipedParams) -> mujoco.MjModel:
    builder = getattr(p, "build_model", None)  # sandbox bodies bring their own validated compiler
    if builder is not None:
        return builder()
    return mujoco.MjModel.from_xml_string(build_mjcf(p))
