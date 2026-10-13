"""Sketch-to-Creature boundary (side-view 2D skeleton -> BipedParams).

Only the supported template is compiled: a straight-legged biped skeleton hip-knee-ankle-toe
(symmetric legs). Anything else is rejected with reasons; nothing is silently approximated.
Coordinates: metres, x forward, z up. Toe is the front end of the foot box
(0.75 * foot_length ahead of the ankle, matching morphology._leg).
"""
from __future__ import annotations

import math

from .morphology import BipedParams

NODES = ("hip", "knee", "ankle", "toe")
SEGMENTS = {frozenset(("hip", "knee")), frozenset(("knee", "ankle")), frozenset(("ankle", "toe"))}
ANKLE_HEIGHT = 0.04  # ankle joint to sole (foot box bottom)
TOE_FRACTION = 0.75
COLLINEAR_TOL = 0.01  # m
FOOT_FLAT_TOL = 0.03  # m


class SketchError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def default_sketch(body: BipedParams) -> dict:
    ankle_z = ANKLE_HEIGHT
    knee_z = ankle_z + body.shank_length
    hip_z = knee_z + body.thigh_length
    return {
        "nodes": {"hip": [0.0, hip_z], "knee": [0.0, knee_z], "ankle": [0.0, ankle_z],
                  "toe": [TOE_FRACTION * body.foot_length, ankle_z]},
        "segments": [["hip", "knee"], ["knee", "ankle"], ["ankle", "toe"]],
    }


def compile_sketch(sketch: dict, base: BipedParams | None = None) -> BipedParams:
    base = base or BipedParams()
    errors: list[str] = []
    nodes = sketch.get("nodes", {})
    extra = sorted(set(nodes) - set(NODES))
    missing = sorted(set(NODES) - set(nodes))
    if extra:
        errors.append(f"Unsupported nodes {extra}: only the biped template {list(NODES)} compiles")
    if missing:
        errors.append(f"Missing nodes {missing}")
    segs = {frozenset(s) for s in sketch.get("segments", [])}
    if segs != SEGMENTS:
        errors.append("Unsupported segment topology: expected exactly hip-knee, knee-ankle, ankle-toe; "
                      f"got {sorted(sorted(s) for s in segs)}")
    if errors:
        raise SketchError(errors)

    hip, knee, ankle, toe = (tuple(map(float, nodes[n])) for n in NODES)
    if not knee[1] < hip[1]:
        errors.append("Knee must be below the hip")
    if not ankle[1] < knee[1]:
        errors.append("Ankle must be below the knee")
    if not toe[0] > ankle[0]:
        errors.append("Toe must be in front of the ankle")
    if abs(toe[1] - ankle[1]) > FOOT_FLAT_TOL:
        errors.append("Foot must be flat (toe at ankle height); tilted feet are not supported")
    if not errors:
        (x1, z1), (x2, z2), (x0, z0) = hip, ankle, knee
        d = abs((x2 - x1) * (z1 - z0) - (x1 - x0) * (z2 - z1)) / math.dist(hip, ankle)
        if d > COLLINEAR_TOL:
            errors.append(f"Bent-knee poses are not supported yet: knee is {d:.3f} m off the hip-ankle line")
    if errors:
        raise SketchError(errors)

    try:
        return base.replace(thigh_length=math.dist(hip, knee), shank_length=math.dist(knee, ankle),
                            foot_length=math.dist(ankle, toe) / TOE_FRACTION)
    except ValueError as exc:
        raise SketchError([str(exc)]) from exc
