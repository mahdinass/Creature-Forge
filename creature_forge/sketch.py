"""Sketch-to-Creature boundary (side-view 2D skeleton -> BipedParams).

Only the supported template is compiled: a straight-legged biped skeleton hip-knee-ankle-toe
(symmetric legs). Anything else is rejected with reasons; nothing is silently approximated.
Coordinates: metres, x forward, z up. Toe is the front end of the foot box
(0.75 * foot_length ahead of the ankle, matching morphology._leg).
"""
from __future__ import annotations

import math

from .morphology import BOUNDS, BipedParams

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


# ---------------------------------------------------------------------------------------------
# Normalisation: project a NEAR-valid sketch onto the supported planar biped, deterministically.
# Every change is reported; anything beyond the tolerances is an error with a reason, never a guess.
# ---------------------------------------------------------------------------------------------
LATERAL_SNAP = 0.12   # m: knee/hip this close to the vertical through the ankle are straightened onto it
FOOT_LEVEL_SNAP = 0.06  # m: a toe this close to ankle height is levelled
CLAMP_MARGIN = 0.10   # m: a segment this far beyond its physical bound is clamped; further is an error
EXTRA_KEYS = ("torso_mass", "foot_friction", "torque_limit", "leg_density")
LENGTH_KEYS = {"thigh_length": ("hip", "knee"), "shank_length": ("knee", "ankle")}


def support_info() -> dict:
    return {
        "summary": "A planar (2-D) biped with two identical straight legs, a fixed-shape torso and flat feet. "
                   "Directly editable: leg segment lengths, foot length and the torso, material and actuator values below.",
        "freedoms": {**{k: list(BOUNDS[k]) for k in ("thigh_length", "shank_length", "foot_length")},
                     **{k: list(BOUNDS[k]) for k in EXTRA_KEYS}},
        "snaps": {"lateral_m": LATERAL_SNAP, "foot_level_m": FOOT_LEVEL_SNAP, "clamp_margin_m": CLAMP_MARGIN},
        "not_supported": [
            "extra limbs, tails, arms or a head (the compiler only builds the hip-knee-ankle-toe leg template)",
            "bent or leaning legs and tilted feet (the leg is built straight; the controller bends the joints)",
            "different left and right legs (both legs share one set of lengths)",
            "a different torso shape (only its mass is editable)",
            "3-D bodies (the model is planar)",
        ],
    }


def _result(ok, params=None, sketch=None, adjustments=None, errors=None) -> dict:
    return {"ok": ok, "params": params, "sketch": sketch, "adjustments": adjustments or [], "errors": errors or []}


def normalize_sketch(sketch: dict, extras: dict | None = None, base: BipedParams | None = None) -> dict:
    base = base or BipedParams()
    nodes_in = sketch.get("nodes", {})
    errors: list[str] = []
    extra_nodes = sorted(set(nodes_in) - set(NODES))
    if extra_nodes:
        errors.append(f"Unsupported part(s) {extra_nodes}: Creature Forge simulates a planar biped with the leg template "
                      f"{list(NODES)} only. Extra limbs, tails or heads would need a new morphology compiler.")
    if set(NODES) - set(nodes_in):
        errors.append(f"Missing node(s) {sorted(set(NODES) - set(nodes_in))}")
    extras = dict(extras or {})
    unknown = sorted(set(extras) - set(EXTRA_KEYS))
    if unknown:
        errors.append(f"Unknown body setting(s) {unknown}: editable settings are {list(EXTRA_KEYS)}")
    if errors:
        return _result(False, errors=errors)

    n = {k: [float(nodes_in[k][0]), float(nodes_in[k][1])] for k in NODES}
    adj: list[dict] = []

    def note(kind: str, node: str, message: str, amount: float) -> None:
        adj.append({"kind": kind, "node": node, "message": message, "amount": round(amount, 4)})

    # 1. stand on the ground (rigid translation: changes no length)
    dz = ANKLE_HEIGHT - n["ankle"][1]
    if abs(dz) > 1e-9:
        for k in NODES:
            n[k][1] += dz
        note("translate", "ankle", f"Moved the whole skeleton {'down' if dz < 0 else 'up'} {abs(dz):.3f} m so the foot stands on the ground.", dz)
    # 2. straighten: hip and knee onto the vertical through the ankle
    for k in ("knee", "hip"):
        dx = n[k][0] - n["ankle"][0]
        if abs(dx) > LATERAL_SNAP:
            errors.append(f"The {k} is {abs(dx):.2f} m sideways of the ankle. Bent or leaning legs are not supported "
                          f"(a straight leg is built; snapping works up to {LATERAL_SNAP:.2f} m).")
        elif abs(dx) > 1e-9:
            note("straighten", k, f"Straightened the leg: moved the {k} {abs(dx):.3f} m sideways onto the vertical through the ankle.", -dx)
            n[k][0] = n["ankle"][0]
    # 3. level the foot
    dzt = n["toe"][1] - n["ankle"][1]
    if abs(dzt) > FOOT_LEVEL_SNAP:
        errors.append(f"The toe is {abs(dzt):.2f} m from ankle height. Tilted feet are not supported (levelling works up to {FOOT_LEVEL_SNAP:.2f} m).")
    elif abs(dzt) > 1e-9:
        note("level", "toe", f"Levelled the foot: moved the toe {abs(dzt):.3f} m to ankle height.", -dzt)
        n["toe"][1] = n["ankle"][1]
    if n["toe"][0] <= n["ankle"][0]:
        errors.append("The toe must be in front of the ankle (the foot points forward).")
    if not n["knee"][1] < n["hip"][1]:
        errors.append("The knee must be below the hip.")
    if not n["ankle"][1] < n["knee"][1]:
        errors.append("The ankle must be below the knee.")
    if errors:
        return _result(False, errors=errors)

    # 4. clamp lengths to physical bounds (small overshoot only)
    def clamp_to(a: str, b: str, key: str, length: float, fraction: float = 1.0) -> None:
        lo, hi = BOUNDS[key]
        phys = length / fraction
        if lo <= phys <= hi:
            return
        target = min(max(phys, lo), hi)
        if abs(phys - target) * fraction > CLAMP_MARGIN:
            errors.append(f"The {key.replace('_length', '')} is {phys:.2f} m; it must be between {lo:.2f} and {hi:.2f} m.")
            return
        if key == "foot_length":
            n["toe"][0] = n["ankle"][0] + fraction * target
        else:
            grow = target - phys  # lengthen/shorten by moving the nodes above the segment
            for k in (("knee", "hip") if key == "shank_length" else ("hip",)):
                n[k][1] += grow
        note("clamp", b if key != "foot_length" else "toe", f"Clamped the {key.replace('_', ' ')} from {phys:.3f} m to the physical limit {target:.3f} m.", target - phys)

    clamp_to("hip", "knee", "thigh_length", math.dist(n["hip"], n["knee"]))
    clamp_to("knee", "ankle", "shank_length", math.dist(n["knee"], n["ankle"]))
    clamp_to("ankle", "toe", "foot_length", math.dist(n["ankle"], n["toe"]), TOE_FRACTION)
    if errors:
        return _result(False, errors=errors)

    try:
        params = compile_sketch({"nodes": n, "segments": sketch.get("segments", [])}, base)
        # round to micrometres: removes float noise from the geometry so the same drawing always gives the same model
        params = params.replace(**{k: round(getattr(params, k), 6) for k in ("thigh_length", "shank_length", "foot_length")})
        if extras:
            params = params.replace(**{k: float(v) for k, v in extras.items()})
    except SketchError as exc:
        return _result(False, errors=exc.errors)
    except ValueError as exc:
        return _result(False, errors=[str(exc)])
    return _result(True, params.as_dict(), {"nodes": n, "segments": [list(s) for s in sketch.get("segments", [])]}, adj)
