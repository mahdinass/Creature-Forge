"""Forge Loop interventions: the parameter whitelist, edit validation, and application to a creature version.

Trust boundary: an edit list comes from a model (untrusted). `validate_edits` parses it, applies the rules of
docs/FORGE_LOOP_CONTRACTS.md section 5.2 and REJECTS violations with a reason that names the parameter and the rule. Nothing is ever
clipped into range. `apply_edits` is the only place a body/controller is changed; it never mutates its input and refuses (ValueError)
to produce a value outside the mode's hard bounds.

Vocabulary
  * version: a creature-version dict (contracts 4.2): `mode` ("guided" | "experimental"), `body` (SandboxBody fields, per-leg `*_r`
    explicit; the LEFT leg (un-suffixed fields) is the REAR leg, the right leg (`*_r`) the FRONT leg) and `controllers`
    (`stand`: GaitParams dict, `walk`: null | {"vector": [15], "provenance": ...}).
  * op "scale": new = old * value.   op "set": new = value.
  * target (leg lengths only): "both" | "rear" | "front". Guided mode forbids "rear"/"front" (legs stay symmetric).
  * u (control parameters): normalised position inside the parameter's bounds, u = (x - lo) / (hi - lo).

Rules (all must hold; every violated rule produces one reason):
  at most 4 edits (at least 1); no two edits touch the same field; value is a finite number; scale needs value > 0;
  the edit changes something; morphology/actuation new/old ratio in [0.5, 1.5]; control |delta u| <= 0.25;
  the result lies inside the mode's bounds (guided: morphology.BOUNDS, experimental: sandbox.SANDBOX_BOUNDS; control: CTRL_BOUNDS for the
  stand controller and phasegait_init.LOWER15/UPPER15 for the walk vector); walk.* only for "walk" challenges, stand.* only for "stand"
  and "push"; the model may not set the pose or anything else not on the whitelist.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

from . import r3
from .controller import CTRL_BOUNDS, GaitParams
from .morphology import BOUNDS as GUIDED_BOUNDS
from .phasegait_init import LOWER15, UPPER15
from .sandbox import SANDBOX_BOUNDS, SandboxBody

MAX_EDITS = 4
RATIO_RANGE = (0.5, 1.5)          # morphology / actuation: new / old
MAX_ABS_DELTA_U = 0.25            # control: linear over the parameter's bounds
TOL = 1e-9                        # slack on the policy limits (ratio, delta u) so that exactly-on-the-limit edits are not lost to float error
LEG_PARAMS = ("thigh_length", "shank_length", "foot_length")
MORPH_PARAMS = ("torso_mass", "thigh_length", "shank_length", "foot_length", "leg_density", "foot_friction")
ACTUATION_PARAMS = ("torque_limit",)
STAND_NAMES = ("kp", "kd", "balance_gain", "stand_hip", "stand_knee")
STAND_PARAMS = tuple(f"stand.{n}" for n in STAND_NAMES)
WALK_PARAMS = tuple(f"walk.{n}" for n in r3.PARAM_NAMES)
WHITELIST = MORPH_PARAMS + ACTUATION_PARAMS + STAND_PARAMS + WALK_PARAMS
OPS = ("scale", "set")
TARGETS = ("both", "rear", "front")
CHALLENGE_KINDS = ("stand", "push", "walk")
MODES = ("guided", "experimental")
CATEGORIES = ("morphology", "control", "combined")
_EDIT_KEYS = {"param", "op", "value", "target"}
_R2_SELECTION = Path(__file__).resolve().parents[1] / "experiments" / "phase2a_r2" / "results" / "selection.json"

# Physical meaning of every whitelisted parameter (neutral wording; shown to the model).
PARAM_MEANINGS = {
    "torso_mass": "torso mass parameter (kg); sets the torso box density",
    "thigh_length": "thigh length, hip to knee (m)",
    "shank_length": "shank length, knee to ankle (m)",
    "foot_length": "foot length (m); the foot extends mostly forward of the ankle",
    "leg_density": "density of every leg segment incl. feet (kg/m^3)",
    "foot_friction": "foot-floor Coulomb friction coefficient",
    "torque_limit": "motor torque limit of every joint (N*m)",
    "stand.kp": "joint position-gain (N*m/rad) of the standing PD controller",
    "stand.kd": "joint damping gain (N*m*s/rad) of the standing PD controller",
    "stand.balance_gain": "ankle torque feedback on torso pitch and pitch rate",
    "stand.stand_hip": "hip angle the standing controller holds (rad)",
    "stand.stand_knee": "knee angle the standing controller holds (rad, negative = flexed)",
    **{f"walk.{n}": d for n, d in r3.PARAM_DESCRIPTIONS.items()},
}

Space = Literal["body", "stand", "walk"]


# ------------------------------------------------------------------------------------------------------------------ edits
@dataclass(frozen=True)
class Edit:
    param: str
    op: Literal["scale", "set"]
    value: float
    target: Literal["both", "rear", "front"] = "both"

    def to_dict(self) -> dict:
        return {"param": self.param, "op": self.op, "value": self.value, "target": self.target}

    @staticmethod
    def from_dict(d: dict) -> "Edit":
        return Edit(d["param"], d["op"], float(d["value"]), d.get("target", "both"))


def kind_of(param: str) -> str:
    """'morphology' | 'actuation' | 'control' for a whitelisted parameter id (ValueError otherwise)."""
    if param in MORPH_PARAMS:
        return "morphology"
    if param in ACTUATION_PARAMS:
        return "actuation"
    if param in STAND_PARAMS or param in WALK_PARAMS:
        return "control"
    raise ValueError(f"{param!r} is not a whitelisted parameter")


def category(edits) -> str:
    """Pure. 'morphology' (morphology and/or actuation edits only), 'control' (stand.*/walk.* only) or 'combined' (both kinds).
    Raises ValueError for an empty edit list. Used both to check the model's declared category and by the matched-random baseline."""
    kinds = {"control" if kind_of(e.param) == "control" else "morphology" for e in edits}
    if not kinds:
        raise ValueError("category() needs at least one edit")
    return "combined" if len(kinds) == 2 else kinds.pop()


def mode_bounds(mode: str) -> dict:
    if mode == "guided":
        return GUIDED_BOUNDS
    if mode == "experimental":
        return SANDBOX_BOUNDS
    raise ValueError(f"mode must be one of {MODES}, got {mode!r}")


def control_bounds(param: str) -> tuple[float, float]:
    """Hard bounds of a control parameter id such as 'stand.kp' or 'walk.freq' (same in both modes)."""
    space, name = param.split(".", 1)
    if space == "stand":
        return CTRL_BOUNDS[name]
    i = r3.PARAM_NAMES.index(name)
    return float(LOWER15[i]), float(UPPER15[i])


# ------------------------------------------------------------------------------------------------------------------ current values
_R2_CACHE: list[float] | None = None


def r2_winner_vector() -> list[float]:
    """The frozen R2 walking vector (read-only experiments/phase2a_r2/results/selection.json); the base of an un-adapted walk controller."""
    global _R2_CACHE
    if _R2_CACHE is None:
        _R2_CACHE = [float(x) for x in json.loads(_R2_SELECTION.read_text(encoding="utf-8"))["winner"]["vector"]]
    return list(_R2_CACHE)


def walk_vector(version: dict) -> list[float]:
    """The 15-vector the walk challenge uses for this version: its own vector, else the R2 winner."""
    w = (version.get("controllers") or {}).get("walk")
    vec = w.get("vector") if isinstance(w, dict) else w
    return [float(x) for x in vec] if vec else r2_winner_vector()


def stand_params(version: dict) -> dict:
    return {**GaitParams().as_dict(), **((version.get("controllers") or {}).get("stand") or {})}


def full_body(version: dict) -> dict:
    """Body dict with every `*_r` field explicit (a missing/None right leg value equals the left leg's) and a list pose."""
    b = dict(version["body"])
    for k in LEG_PARAMS:
        if b.get(k + "_r") is None:
            b[k + "_r"] = b[k]
    b["pose"] = list(b.get("pose") or [0.0] * 7)
    return b


def sandbox_body(version: dict) -> SandboxBody:
    """SandboxBody for a version (no bound check beyond the dataclass; call .validate() when needed)."""
    b = full_body(version)
    names = {f.name for f in fields(SandboxBody)}
    kw = {k: v for k, v in b.items() if k in names}
    kw["pose"] = tuple(kw["pose"])
    return SandboxBody(**kw)


# ------------------------------------------------------------------------------------------------------------------ planning
@dataclass(frozen=True)
class _Change:
    space: Space
    key: str | int          # body field name, stand field name, or walk vector index
    old: float
    new: float
    lo: float
    hi: float


def _body_fields(param: str, target: str) -> list[str]:
    if param in LEG_PARAMS:
        return {"both": [param, param + "_r"], "rear": [param], "front": [param + "_r"]}[target]
    return [param]


def _plan(version: dict, e: Edit) -> list[_Change]:
    """The concrete value changes an edit would cause (no rule checking)."""
    def newval(old: float) -> float:
        return old * e.value if e.op == "scale" else e.value

    if e.param in STAND_PARAMS:
        name = e.param.split(".", 1)[1]
        old = float(stand_params(version)[name])
        lo, hi = control_bounds(e.param)
        return [_Change("stand", name, old, newval(old), lo, hi)]
    if e.param in WALK_PARAMS:
        i = r3.PARAM_NAMES.index(e.param.split(".", 1)[1])
        old = walk_vector(version)[i]
        lo, hi = control_bounds(e.param)
        return [_Change("walk", i, old, newval(old), lo, hi)]
    body = full_body(version)
    lo, hi = mode_bounds(version["mode"])[e.param]
    return [_Change("body", k, float(body[k]), newval(float(body[k])), lo, hi) for k in _body_fields(e.param, e.target)]


def magnitude(version: dict, edit: Edit) -> float:
    """Pure size of an edit, comparable across edits of the same kind. Morphology/actuation: max over the touched fields of
    |ln(new/old)|. Control: |delta u| = |new - old| / (hi - lo), linear over the parameter's bounds. Bounds/rules are NOT checked
    (the matched-random baseline calls this on edits it constructs itself). ValueError if a log is undefined (non-positive value)."""
    ch = _plan(version, edit)
    if kind_of(edit.param) == "control":
        return max(abs(c.new - c.old) / (c.hi - c.lo) for c in ch)
    if any(c.old <= 0 or c.new <= 0 for c in ch):
        raise ValueError(f"{edit.param}: magnitude is undefined for non-positive values")
    return max(abs(math.log(c.new / c.old)) for c in ch)


# ------------------------------------------------------------------------------------------------------------------ catalog
def allowed_params(challenge_kind: str) -> tuple[str, ...]:
    """Whitelist for a challenge: shared morphology/actuation plus stand.* (stand, push) or walk.* (walk)."""
    if challenge_kind not in CHALLENGE_KINDS:
        raise ValueError(f"challenge kind must be one of {CHALLENGE_KINDS}, got {challenge_kind!r}")
    return MORPH_PARAMS + ACTUATION_PARAMS + (WALK_PARAMS if challenge_kind == "walk" else STAND_PARAMS)


def _r(x: float) -> float:
    return round(float(x), 4)


def editable_params(version: dict, challenge_kind: str) -> dict:
    """Editable parameters for this version and challenge: {param: {kind, meaning, lo, hi, targets, current | rear/front, u?}}.
    Morphology bounds follow the mode. Used to build the prompt and the evidence `bounds` block."""
    mode = version["mode"]
    guided = mode == "guided"
    body = full_body(version)
    bounds = mode_bounds(mode)
    out: dict = {}
    for p in allowed_params(challenge_kind):
        k = kind_of(p)
        d: dict = {"kind": k, "meaning": PARAM_MEANINGS[p]}
        if k == "control":
            lo, hi = control_bounds(p)
            cur = _plan(version, Edit(p, "scale", 1.0))[0].old
            d.update(lo=_r(lo), hi=_r(hi), current=_r(cur), u=_r((cur - lo) / (hi - lo)), targets=["both"])
        else:
            lo, hi = bounds[p]
            d.update(lo=_r(lo), hi=_r(hi))
            if p in LEG_PARAMS:
                d.update(rear=_r(body[p]), front=_r(body[p + "_r"]), targets=["both"] if guided else list(TARGETS))
            else:
                d.update(current=_r(body[p]), targets=["both"])
        out[p] = d
    return out


# ------------------------------------------------------------------------------------------------------------------ validation
def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _parse_edit(i: int, raw) -> tuple[Edit | None, list[str]]:
    w = f"edits[{i}]"
    if isinstance(raw, Edit):
        raw = raw.to_dict()
    if not isinstance(raw, dict):
        return None, [f"{w}: rule 'each edit is an object with param, op, value, target' violated (got {type(raw).__name__})"]
    extra = sorted(set(raw) - _EDIT_KEYS)
    param = raw.get("param")
    name = param if isinstance(param, str) else "?"
    reasons = []
    if extra:
        reasons.append(f"{w} {name}: rule 'only param, op, value, target are allowed' violated by field(s) {extra}")
    if not isinstance(param, str) or param not in WHITELIST:
        reasons.append(f"{w}: unknown parameter {param!r}; rule 'the parameter must be on the whitelist' violated")
        return None, reasons
    op = raw.get("op")
    if op not in OPS:
        reasons.append(f"{w} {param}: op {op!r} violates rule 'op is one of {list(OPS)}'")
    value = raw.get("value")
    if not _num(value):
        reasons.append(f"{w} {param}: value {value!r} violates rule 'value is a finite number'")
    target = raw.get("target", "both")
    if target not in TARGETS:
        reasons.append(f"{w} {param}: target {target!r} violates rule 'target is one of {list(TARGETS)}'")
    if reasons:
        return None, reasons
    return Edit(param, op, float(value), target), []


def _check_edit(version: dict, kind: str, i: int, e: Edit) -> list[str]:
    w = f"edits[{i}] {e.param}"
    guided = version["mode"] == "guided"
    out: list[str] = []
    if e.param not in allowed_params(kind):
        out.append(f"{w}: rule '{'walk' if e.param in WALK_PARAMS else 'stand'}.* parameters apply only to "
                   f"{'walk' if e.param in WALK_PARAMS else 'stand and push'} challenges' violated (challenge is '{kind}')")
        return out
    if e.target != "both" and e.param not in LEG_PARAMS:
        out.append(f"{w}: rule 'only leg lengths have per-leg targets' violated by target '{e.target}'")
    if guided and e.target != "both":
        out.append(f"{w}: rule 'guided mode keeps both legs symmetric (target must be both)' violated by target '{e.target}'")
    if e.op == "scale" and e.value <= 0:
        out.append(f"{w}: rule 'scale factor must be positive' violated by value {e.value:g}")
        return out
    if out:
        return out
    ch = _plan(version, e)
    control = kind_of(e.param) == "control"
    for c in ch:
        where = f"{w}" + ("" if control or len(ch) == 1 else f" ({c.key})")
        if abs(c.new - c.old) <= 1e-12 * max(1.0, abs(c.old)):
            hint = " (scaling a value of 0 changes nothing; use op 'set')" if c.old == 0 and e.op == "scale" else ""
            out.append(f"{where}: rule 'the edit must change the value' violated: {c.old:g} -> {c.new:g}{hint}")
            continue
        if not math.isfinite(c.new):
            out.append(f"{where}: rule 'the result must be finite' violated")
            continue
        if control:
            du = abs(c.new - c.old) / (c.hi - c.lo)
            if du > MAX_ABS_DELTA_U + TOL:
                out.append(f"{where}: rule '|delta u| <= {MAX_ABS_DELTA_U}' violated: {c.old:g} -> {c.new:g} is "
                           f"|delta u| = {du:.3f} over bounds [{c.lo:g}, {c.hi:g}]")
        else:
            ratio = c.new / c.old if c.old else math.inf
            if not (RATIO_RANGE[0] - TOL <= ratio <= RATIO_RANGE[1] + TOL):
                out.append(f"{where}: rule 'new/old ratio in {list(RATIO_RANGE)}' violated: {c.old:g} -> {c.new:g} is ratio {ratio:.3f}")
        if not (c.lo <= c.new <= c.hi):
            mode = version["mode"] if not control else "control"
            out.append(f"{where}: rule 'result inside the {mode} bounds [{c.lo:g}, {c.hi:g}]' violated: {c.old:g} -> {c.new:g}")
    if guided and not out and e.param in LEG_PARAMS:
        b = full_body(version)
        if abs(b[e.param] - b[e.param + "_r"]) > 1e-9:
            out.append(f"{w}: rule 'guided mode keeps both legs symmetric' violated: the creature's legs already differ")
    return out


def _fields_of(e: Edit) -> set:
    if e.param in STAND_PARAMS or e.param in WALK_PARAMS:
        return {e.param}
    return set(_body_fields(e.param, e.target))


def validate_edits(version: dict, challenge_kind: str, edits: list) -> tuple[list[Edit], list[str]]:
    """Parse and check a model's edit list. Returns (edits, reasons). Any violation rejects the WHOLE list: `reasons` is then non-empty and
    the returned edit list is empty (nothing is clipped or silently dropped). Each reason names the parameter and the rule violated."""
    if challenge_kind not in CHALLENGE_KINDS:
        raise ValueError(f"challenge kind must be one of {CHALLENGE_KINDS}, got {challenge_kind!r}")
    if not isinstance(edits, list):
        return [], ["edits: rule 'edits is a list' violated"]
    if not edits:
        return [], ["edits: rule 'at least one edit' violated"]
    if len(edits) > MAX_EDITS:
        return [], [f"edits: rule 'at most {MAX_EDITS} edits' violated by {len(edits)} edits"]
    parsed: list[Edit] = []
    reasons: list[str] = []
    for i, raw in enumerate(edits):
        e, why = _parse_edit(i, raw)
        reasons += why
        if e is None:
            continue
        reasons += _check_edit(version, challenge_kind, i, e)
        parsed.append(e)
    seen: dict = {}
    for i, e in enumerate(parsed):
        for f in _fields_of(e):
            if f in seen:
                reasons.append(f"edits[{i}] {e.param}: rule 'no two edits may change the same field' violated (target '{e.target}' "
                               f"overlaps an earlier {seen[f]!r} edit)")
            seen.setdefault(f, e.target)
    if reasons:
        return [], reasons
    return parsed, []


# ------------------------------------------------------------------------------------------------------------------ application
def apply_edits(version: dict, edits: list[Edit]) -> tuple[dict, dict]:
    """New (body, controllers) dicts with the edits applied; the version is not mutated. Raises ValueError if a result would leave the
    hard bounds (never clips). Policy rules (ratio, delta u, counts) are validate_edits's job. The returned `walk` controller carries
    the edited 15-vector (starting from the version's vector, else the R2 winner) and its provenance marked `edited`."""
    body = full_body(copy.deepcopy(version))
    stand = stand_params(version)
    vec = walk_vector(version)
    touched_walk = False
    for e in edits:
        for c in _plan(version, e):
            if not (math.isfinite(c.new) and c.lo <= c.new <= c.hi):
                raise ValueError(f"{e.param}: result {c.new:g} is outside the bounds [{c.lo:g}, {c.hi:g}]; edits are rejected, never clipped")
            if c.space == "body":
                body[c.key] = c.new
            elif c.space == "stand":
                stand[c.key] = c.new
            else:
                vec[c.key] = c.new
                touched_walk = True
    old_walk = (version.get("controllers") or {}).get("walk")
    walk = copy.deepcopy(old_walk) if isinstance(old_walk, dict) else None
    if touched_walk:
        prov = dict((walk or {}).get("provenance") or {"kind": "r2-transfer"})
        prov["edited"] = True
        walk = {"vector": vec, "provenance": prov}
    controllers = {"stand": stand, "walk": walk}
    return body, controllers
