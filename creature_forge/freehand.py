"""Deterministic freehand-stroke interpretation: a drawn side-view biped -> a `SandboxBody` (or a clear refusal).

Pure geometry, no model or network. The same strokes always give the same answer. Nothing is silently substituted:
every assumption, snap and approximation is returned for the UI to show, and a drawing the physics cannot represent
produces `body = None` plus the exact reason (and, when one exists, a consent-gated `approximation`).

Coordinates in: canvas pixels, y down, 400 px = 1 m, creature facing right (a drawing that faces left is mirrored and
reported). Roles: torso, leg, foot (pen roles or auto-detected), ignore.

What the physics can and cannot take (planar two-legged model, see `sandbox.py`):
  exact: leg segment lengths (per leg), foot lengths, torso mass (from drawn area), initial lean, hip/knee/ankle angles
  per leg inside the joint ranges, friction, motor limit, leg density.
  fixed: torso shape (0.12 x 0.30 m box), planar motion, two legs, a knee that only points backward.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .morphology import BOUNDS
from .sandbox import POSE_RANGES, SANDBOX_BOUNDS, SandboxBody

PX_PER_M = 400.0
TORSO_AREA_TO_MASS = 5.0 / (0.12 * 0.30)  # kg per m^2 of drawn side-view torso area (default torso = 5 kg)
DEFAULT_TORSO_DEPTH = 0.12
TORSO_H = 0.30
MIN_STROKE_M = 0.015  # shorter than ~6 px: an accidental dot
SNAP_DEG = {"leg": 6.0, "foot": 8.0, "lean": 5.0}
EQUAL_LEG_FRAC = 0.15
GUIDED_CLAMP_FRAC = 0.20  # guided: a value up to 20% beyond the supported range is clamped (reported); more is refused
DEFAULT_MATERIALS = {"foot_friction": 1.0, "torque_limit": 60.0, "leg_density": 1000.0}
KNEE_MIN, KNEE_MAX = POSE_RANGES[2]
KNEE_TOL = 0.1  # rad: wobble in a straight hand-drawn leg


# ------------------------------------------------------------------ geometry helpers
def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _length(pts) -> float:
    return sum(_dist(a, b) for a, b in zip(pts, pts[1:]))


def _resample(pts, step=0.01):
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = _dist(a, b)
        if seg == 0:
            continue
        d = step - carry
        while d <= seg:
            t = d / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            d += step
        carry = seg - (d - step)
    if _dist(out[-1], pts[-1]) > 1e-9:
        out.append(pts[-1])
    return out


def _perp(p, a, b) -> float:
    ab = _dist(a, b)
    if ab == 0:
        return _dist(p, a)
    return abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / ab


def _rdp(pts, eps):
    if len(pts) < 3:
        return list(pts)
    idx, dmax = 0, 0.0
    for i in range(1, len(pts) - 1):
        d = _perp(pts[i], pts[0], pts[-1])
        if d > dmax:
            idx, dmax = i, d
    if dmax <= eps:
        return [pts[0], pts[-1]]
    return _rdp(pts[:idx + 1], eps)[:-1] + _rdp(pts[idx:], eps)


def _polygon_area(pts) -> float:
    s = 0.0
    for a, b in zip(pts, pts[1:] + pts[:1]):
        s += a[0] * b[1] - b[0] * a[1]
    return abs(s) / 2


def _principal_axis(pts):
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    mz = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    szz = sum((p[1] - mz) ** 2 for p in pts)
    sxz = sum((p[0] - mx) * (p[1] - mz) for p in pts)
    ang = 0.5 * math.atan2(2 * sxz, sxx - szz)
    ax = (math.cos(ang), math.sin(ang))
    if ax[1] < 0:
        ax = (-ax[0], -ax[1])
    return (mx, mz), ax


# ------------------------------------------------------------------ stroke model
@dataclass
class S:
    id: str
    role: str  # requested: auto | torso | leg | foot | ignore
    pts: list  # metres (x right, z up), simplified polyline
    raw_len: float
    closed: bool = False
    final: str = ""
    source: str = ""
    reason: str = ""

    @property
    def bbox(self):
        xs = [p[0] for p in self.pts]
        zs = [p[1] for p in self.pts]
        return min(xs), min(zs), max(xs), max(zs)

    @property
    def w(self):
        b = self.bbox
        return b[2] - b[0]

    @property
    def h(self):
        b = self.bbox
        return b[3] - b[1]

    @property
    def cz(self):
        return sum(p[1] for p in self.pts) / len(self.pts)


def _parse(strokes, px_per_m):
    out: list[S] = []
    for s in strokes:
        raw = [(float(x) / px_per_m, -float(y) / px_per_m) for x, y in s.get("points", [])]
        L = _length(raw)
        st = S(id=str(s["id"]), role=s.get("role", "auto"), pts=[], raw_len=L)
        if len(raw) < 2 or L < MIN_STROKE_M:
            st.final, st.source, st.reason = "ignore", "auto", "too short to mean anything (an accidental dot)"
            st.pts = raw or [(0.0, 0.0)]
            out.append(st)
            continue
        st.closed = _dist(raw[0], raw[-1]) < 0.35 * L and L >= 0.25
        rs = _resample(raw)
        st.pts = rs if st.closed else _rdp(rs, 0.015)
        if st.closed:
            st.pts = _rdp(rs, 0.01)
        out.append(st)
    return out


def _classify(strokes: list[S]):
    """Assign roles; returns ambiguities. Explicit pen roles are always respected."""
    ambiguities: list[dict] = []
    for s in strokes:
        if s.final:
            continue
        if s.role in ("torso", "leg", "foot", "ignore"):
            s.final, s.source, s.reason = s.role, "pen", "drawn with the " + s.role + " pen" if s.role != "ignore" else "set to ignore"
    live = [s for s in strokes if s.final != "ignore"]
    if not live:
        return ambiguities
    zmin = min(s.bbox[1] for s in live)
    zmax = max(s.bbox[3] for s in live)
    span = max(zmax - zmin, 1e-6)
    auto = [s for s in live if not s.final]
    for s in auto:
        if not s.closed and s.w >= 0.03 and s.w >= 1.5 * s.h and s.cz <= zmin + 0.3 * span:
            s.final, s.source, s.reason = "foot", "auto", "short, mostly horizontal stroke near the ground"
    if not any(s.final == "torso" for s in live):
        cand = [s for s in auto if not s.final and s.raw_len >= 0.12]
        closed = [s for s in cand if s.closed]
        pool = closed or cand
        if pool:
            pool = sorted(pool, key=lambda s: (-s.bbox[3], s.id))
            top = pool[0]
            twins = [s for s in pool[1:] if abs(s.bbox[3] - top.bbox[3]) <= 0.05 and (s.closed == top.closed)]
            if twins:
                group = [top] + twins
                ambiguities.append({
                    "kind": "torso", "strokes": [s.id for s in group],
                    "message": f"{len(group)} strokes could be the torso (they reach the same height). Tell me which one is the torso.",
                    "options": [{"label": f"{g.id} is the torso", "assign": {**{h.id: "leg" for h in group if h is not g}, g.id: "torso"}} for g in group]})
            else:
                top.final, top.source = "torso", "auto"
                top.reason = ("highest closed shape" if top.closed else "highest stroke: the other strokes hang below it")
    for s in auto:
        if not s.final and not any(a["kind"] == "torso" and s.id in a["strokes"] for a in ambiguities):
            if s.raw_len >= 0.1:
                s.final, s.source, s.reason = "leg", "auto", "open stroke hanging below the torso"
            else:
                s.final, s.source, s.reason = "ignore", "auto", "too short to be a leg"
    return ambiguities


def _orient_top_first(pts):
    return pts if pts[0][1] >= pts[-1][1] else list(reversed(pts))


def _merge_legs(legs: list[list]):
    """Join leg strokes that continue each other (thigh drawn, then shank from its end)."""
    legs = [_orient_top_first(p) for p in legs]
    changed = True
    while changed and len(legs) > 1:
        changed = False
        for i, a in enumerate(legs):
            for j, b in enumerate(legs):
                if i != j and _dist(a[-1], b[0]) < 0.06 and b[0][1] <= a[0][1]:
                    legs[i] = a + b[1:]
                    legs.pop(j)
                    changed = True
                    break
            if changed:
                break
    return legs


def _knee(poly):
    """Knee = vertex of greatest bend; a straight stroke gets its knee halfway along (and says so)."""
    a, b = poly[0], poly[-1]
    best, dmax = None, 0.0
    for p in poly[1:-1]:
        d = _perp(p, a, b)
        if d > dmax:
            best, dmax = p, d
    if best is not None and dmax >= 0.025:
        return best, False
    half, acc = _length(poly) / 2, 0.0
    for p, q in zip(poly, poly[1:]):
        seg = _dist(p, q)
        if acc + seg >= half and seg > 0:
            t = (half - acc) / seg
            return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t), True
        acc += seg
    return poly[len(poly) // 2], True


def _abs_angle(a, b) -> float:
    """World angle (rad, rotation about +y as in MuJoCo) of the direction a -> b measured from straight down."""
    return math.atan2(-(b[0] - a[0]), -(b[1] - a[1]))


# ------------------------------------------------------------------ main entry
def _result(**kw) -> dict:
    base = {"status": "unbuildable", "outcome": "unrepresentable", "roles": {}, "ambiguities": [], "errors": [], "notes": [],
            "assumptions": [], "adjustments": [], "body": None, "approximation": None, "skeleton": None, "guided": True}
    base.update(kw)
    return base


def interpret(strokes: list[dict], *, guided: bool = True, materials: dict | None = None, px_per_m: float = PX_PER_M) -> dict:
    res = _interpret(strokes, guided=guided, materials=materials, px_per_m=px_per_m)
    for k in ("notes", "assumptions", "errors"):  # the same observation about two legs is said once
        res[k] = list(dict.fromkeys(res[k]))
    return res


def _interpret(strokes: list[dict], *, guided: bool = True, materials: dict | None = None, px_per_m: float = PX_PER_M) -> dict:
    mats = {**DEFAULT_MATERIALS, **{k: float(v) for k, v in (materials or {}).items() if k in DEFAULT_MATERIALS}}
    ss = _parse(strokes, px_per_m)
    ambiguities = _classify(ss)
    roles = {s.id: {"role": s.final or "unassigned", "source": s.source or "none", "reason": s.reason} for s in ss}
    res = _result(roles=roles, guided=guided, ambiguities=ambiguities)
    notes, assumptions, errors = res["notes"], res["assumptions"], res["errors"]
    if ambiguities:
        res["status"] = "needs_input"
        res["errors"] = [a["message"] for a in ambiguities]
        return res

    torsos = [s for s in ss if s.final == "torso"]
    leg_strokes = [s for s in ss if s.final == "leg"]
    foot_strokes = [s for s in ss if s.final == "foot"]
    if not torsos:
        errors.append("No torso found. Draw the body (a closed shape or a vertical stroke) above the legs, or pick the Torso pen.")
    if not leg_strokes:
        errors.append("No leg found. Draw at least one leg hanging down from the torso, or pick the Leg pen.")
    if errors:
        return res
    if len(torsos) > 1:
        res["ambiguities"] = [{"kind": "torso", "strokes": [t.id for t in torsos], "message": "More than one stroke is marked as torso. Set all but one to another role.",
                               "options": [{"label": f"{t.id} is the torso", "assign": {**{u.id: "leg" for u in torsos if u is not t}, t.id: "torso"}} for t in torsos]}]
        res["status"], res["errors"] = "needs_input", [res["ambiguities"][0]["message"]]
        return res

    # ---- torso
    t = torsos[0]
    if t.closed:
        centre, ax = _principal_axis(_resample(t.pts, 0.01))
        proj = [((p[0] - centre[0]) * ax[0] + (p[1] - centre[1]) * ax[1]) for p in _resample(t.pts, 0.01)]
        base = (centre[0] + ax[0] * min(proj), centre[1] + ax[1] * min(proj))
        top = (centre[0] + ax[0] * max(proj), centre[1] + ax[1] * max(proj))
        area = _polygon_area(t.pts)
    else:
        a, b = _orient_top_first(t.pts)[-1], _orient_top_first(t.pts)[0]
        base, top = a, b
        area = _dist(base, top) * DEFAULT_TORSO_DEPTH
        assumptions.append(f"The torso is a line, so its width is assumed to be {DEFAULT_TORSO_DEPTH:.2f} m when estimating its mass.")
    torso_len = _dist(base, top)
    pitch = math.atan2(top[0] - base[0], top[1] - base[1])
    torso_mass = area * TORSO_AREA_TO_MASS

    # ---- legs
    merged = _merge_legs([s.pts for s in leg_strokes])
    if len(merged) > 2:
        ids = [s.id for s in leg_strokes]
        amb = {"kind": "leg_count", "strokes": ids, "message": f"{len(merged)} separate legs were drawn; the creature has two. Set the extra strokes to Ignore.",
               "options": [{"label": f"Ignore {i}", "assign": {i: "ignore"}} for i in ids]}
        res["ambiguities"], res["status"], res["errors"] = [amb], "needs_input", [amb["message"]]
        return res
    legs = []
    for poly in merged:
        hip, ankle = poly[0], poly[-1]
        knee, guessed = _knee(poly)
        if guessed:
            assumptions.append("A straight leg stroke has no visible knee: the knee was placed halfway along it. Use Refine to move it.")
        legs.append({"hip": hip, "knee": knee, "ankle": ankle})
    if _dist(legs[0]["hip"], base) > 0.35 and (len(legs) == 1 or _dist(legs[1]["hip"], base) > 0.35):
        errors.append(f"The leg starts {_dist(legs[0]['hip'], base):.2f} m from the bottom of the torso. A leg has to hang from the torso.")
        res["status"] = "unbuildable"
        return res
    for L in legs:
        d = _dist(L["hip"], base)
        if d > 0.12:
            notes.append(f"A leg starts {d:.2f} m from the bottom of the torso; the model attaches both legs at the torso's lower end.")
    legs.sort(key=lambda L: (L["ankle"][0], L["ankle"][1]))
    if len(legs) == 1:
        legs.append(dict(legs[0]))
        assumptions.append("Only one leg was drawn: the second leg mirrors it exactly (same lengths and pose).")

    # ---- feet and facing
    def foot_on(f, i: int) -> dict:
        a, b, ank = f.pts[0], f.pts[-1], legs[i]["ankle"]
        toe, heel = (b, a) if abs(b[0] - ank[0]) >= abs(a[0] - ank[0]) else (a, b)
        return {"leg": i, "toe": toe, "heel": heel, "dir": 1 if toe[0] >= ank[0] else -1}

    dist = [[min(_dist(p, legs[i]["ankle"]) for p in f.pts) for i in range(2)] for f in foot_strokes]
    near = [min(range(2), key=lambda i: dist[k][i]) for k in range(len(foot_strokes))]
    for k, f in enumerate(foot_strokes):
        d = dist[k][near[k]]
        if d > 0.2:
            res["status"] = "needs_input"
            amb = {"kind": "foot", "strokes": [f.id], "message": f"Foot stroke {f.id} is {d:.2f} m from the nearest ankle, so it is unclear which leg it belongs to.",
                   "options": [{"label": f"Ignore {f.id}", "assign": {f.id: "ignore"}}]}
            res["ambiguities"], res["errors"] = [amb], [amb["message"]]
            return res
    feet = [foot_on(f, near[k]) for k, f in enumerate(foot_strokes)]
    if len(foot_strokes) == 2 and len({f["dir"] for f in feet}) > 1:
        # Two feet close to both ankles (legs drawn a few cm apart) can each look nearest to the other leg, which flips
        # toe and heel. Use the one-to-one assignment in which both feet point the same way (closest first); only if no
        # such reading exists is the facing genuinely ambiguous and the user is asked below.
        options = []
        for perm in ((0, 1), (1, 0)):
            cand = [foot_on(f, perm[k]) for k, f in enumerate(foot_strokes)]
            if len({c["dir"] for c in cand}) == 1 and max(dist[k][perm[k]] for k in range(2)) <= 0.2:
                options.append((dist[0][perm[0]] + dist[1][perm[1]], cand))
        if options:
            feet = min(options, key=lambda o: o[0])[1]
    mirror = False
    if feet:
        dirs = {f["dir"] for f in feet}
        if len(dirs) > 1:
            ids = [s.id for s in foot_strokes]
            amb = {"kind": "facing", "strokes": ids, "message": "The feet point in opposite directions, so I cannot tell which way the creature faces. Ignore the foot that points the wrong way.",
                   "options": [{"label": f"Ignore {i}", "assign": {i: "ignore"}} for i in ids]}
            res["ambiguities"], res["status"], res["errors"] = [amb], "needs_input", [amb["message"]]
            return res
        mirror = dirs == {-1}
    else:
        assumptions.append("No foot was drawn: both feet use the default 0.16 m flat foot, facing right.")
    if mirror:
        notes.append("Mirrored: the drawing faces left; the physics model faces right, so every x coordinate was flipped.")
        flip = lambda p: (-p[0], p[1])
        base, top = flip(base), flip(top)
        pitch = math.atan2(top[0] - base[0], top[1] - base[1])
        for L in legs:
            for k in ("hip", "knee", "ankle"):
                L[k] = flip(L[k])
        for f in feet:
            f["toe"], f["heel"] = flip(f["toe"]), flip(f["heel"])
        legs.sort(key=lambda L: (L["ankle"][0], L["ankle"][1]))
        # feet were attached to indexes before the re-sort; re-associate by nearest ankle
        for f in feet:
            f["leg"] = min(range(2), key=lambda i: _dist(f["heel"], legs[i]["ankle"]) + _dist(f["toe"], legs[i]["ankle"]))
    for L in legs:
        L["foot"] = None
    for f in feet:
        L = legs[f["leg"]]
        chord = _dist(f["heel"], f["toe"])
        L["foot"] = {"length": chord, "tilt": -math.atan2(f["toe"][1] - f["heel"][1], f["toe"][0] - f["heel"][0])}
    drawn = [L["foot"] for L in legs if L["foot"]]
    for L in legs:
        if L["foot"] is None:
            if drawn:
                L["foot"] = dict(drawn[0])
                assumptions.append("Only one foot was drawn: the other foot copies it.")
            else:
                L["foot"] = {"length": 0.16, "tilt": 0.0}

    design = {
        "pitch": pitch, "torso_mass": torso_mass, **mats, "torso_len": torso_len,
        "legs": [{"thigh": _dist(L["hip"], L["knee"]), "shank": _dist(L["knee"], L["ankle"]), "foot": L["foot"]["length"],
                  "th_t": _abs_angle(L["hip"], L["knee"]), "th_s": _abs_angle(L["knee"], L["ankle"]), "tilt": L["foot"]["tilt"]} for L in legs],
    }
    return _finish(res, design, base, guided, mirror)


# ------------------------------------------------------------------ guided snapping, validation, compile
def _joints(d: dict, i: int) -> tuple[float, float, float]:
    L = d["legs"][i]
    return L["th_t"] - d["pitch"], L["th_s"] - L["th_t"], L["tilt"] - L["th_s"]


def _snap(d: dict, adjustments: list):
    if abs(d["pitch"]) < math.radians(SNAP_DEG["lean"]) and d["pitch"] != 0.0:
        adjustments.append({"kind": "straighten", "what": "torso", "message": f"Stood the torso upright (it leaned {math.degrees(d['pitch']):.1f}°)."})
        d["pitch"] = 0.0
    names = ("rear", "front")
    for i, L in enumerate(d["legs"]):
        for key, label in (("th_t", "thigh"), ("th_s", "shank")):
            if 0 < abs(L[key]) < math.radians(SNAP_DEG["leg"]):
                adjustments.append({"kind": "straighten", "what": f"{names[i]} {label}", "message": f"Made the {names[i]} leg's {label} vertical (it was {math.degrees(L[key]):.1f}° off)."})
                L[key] = 0.0
        if 0 < abs(L["tilt"]) < math.radians(SNAP_DEG["foot"]):
            adjustments.append({"kind": "level", "what": f"{names[i]} foot", "message": f"Levelled the {names[i]} foot (it was tilted {math.degrees(L['tilt']):.1f}°)."})
            L["tilt"] = 0.0
        knee = L["th_s"] - L["th_t"]
        if 0 < knee <= 0.1:
            adjustments.append({"kind": "straighten", "what": f"{names[i]} knee", "message": f"Straightened the {names[i]} knee (it bent {math.degrees(knee):.1f}° the wrong way)."})
            L["th_s"] = L["th_t"]
    a, b = d["legs"]
    for key, label in (("thigh", "thigh"), ("shank", "shank"), ("foot", "foot")):
        hi, lo = max(a[key], b[key]), min(a[key], b[key])
        if lo != hi and (hi - lo) / hi < EQUAL_LEG_FRAC:
            m = (a[key] + b[key]) / 2
            adjustments.append({"kind": "equalize", "what": label, "message": f"Made both {label}s {m:.3f} m (they differed by {(hi - lo) * 100:.0f} cm)."})
            a[key] = b[key] = m


def _violations(d: dict, guided: bool) -> list[dict]:
    """Things the chosen mode cannot build as drawn. Each carries the value it could be moved to (for an approximation)."""
    B = BOUNDS if guided else SANDBOX_BOUNDS
    where = "the supported design range" if guided else "the sandbox limits"
    out: list[dict] = []

    def bound(what: str, key: str, v: float, setter):
        lo, hi = B[key]
        if v < lo or v > hi:
            to = min(max(v, lo), hi)
            out.append({"what": what, "from": round(v, 4), "to": to, "setter": setter,
                        "message": f"The {what} is {v:.3g}, outside {where} [{lo:g}, {hi:g}]."})

    bound("torso mass", "torso_mass", d["torso_mass"], lambda x: d.__setitem__("torso_mass", x))
    for k in ("foot_friction", "torque_limit", "leg_density"):
        bound(k.replace("_", " "), k, d[k], (lambda key: lambda x: d.__setitem__(key, x))(k))
    names = ("rear", "front")
    for i, L in enumerate(d["legs"]):
        for key, label in (("thigh", "thigh length"), ("shank", "shank length"), ("foot", "foot length")):
            bound(f"{names[i]} {label}", {"thigh": "thigh_length", "shank": "shank_length", "foot": "foot_length"}[key], L[key],
                  (lambda LL, kk: lambda x: LL.__setitem__(kk, x))(L, key))
        hip, knee, ankle = _joints(d, i)
        lo, hi = POSE_RANGES[1]
        if not lo <= hip <= hi:
            to = min(max(hip, lo), hi)
            out.append({"what": f"{names[i]} hip angle", "from": round(hip, 3), "to": to, "setter": (lambda LL, dd, v: lambda x: LL.__setitem__("th_t", x + dd["pitch"]))(L, d, 0),
                        "message": f"The {names[i]} thigh swings {math.degrees(hip):.0f}° from the torso; the hip only turns ±{math.degrees(hi):.0f}°."})
        if not KNEE_MIN <= knee <= KNEE_MAX:
            msg = (f"The {names[i]} knee points forward (bends {math.degrees(knee):.0f}°). In this model a knee only bends backward, "
                   f"like a bird's: the knee sits behind the toes and the lower leg swings forward." if knee > 0 else
                   f"The {names[i]} knee bends {math.degrees(-knee):.0f}°, past the {math.degrees(-KNEE_MIN):.0f}° the joint allows.")
            to = min(max(knee, KNEE_MIN), KNEE_MAX)
            out.append({"what": f"{names[i]} knee angle", "from": round(knee, 3), "to": to, "setter": (lambda LL: lambda x: LL.__setitem__("th_s", LL["th_t"] + x))(L), "message": msg})
        lo, hi = POSE_RANGES[3]
        if not lo <= ankle <= hi:
            to = min(max(ankle, lo), hi)
            out.append({"what": f"{names[i]} ankle angle", "from": round(ankle, 3), "to": to, "setter": (lambda LL: lambda x: LL.__setitem__("tilt", LL["th_s"] + x))(L),
                        "message": f"The {names[i]} foot is turned {math.degrees(ankle):.0f}° from the shank; the ankle only turns ±{math.degrees(hi):.0f}°."})
    lo, hi = POSE_RANGES[0]
    if not lo <= d["pitch"] <= hi:
        out.append({"what": "torso lean", "from": round(d["pitch"], 3), "to": min(max(d["pitch"], lo), hi), "setter": lambda x: d.__setitem__("pitch", x),
                    "message": f"The torso leans {math.degrees(d['pitch']):.0f}°; the starting lean is limited to ±{math.degrees(hi):.0f}°."})
    if guided:
        a, b = d["legs"]
        for key, label in (("thigh", "thigh"), ("shank", "shank"), ("foot", "foot")):
            if abs(a[key] - b[key]) > 1e-9:
                m = (a[key] + b[key]) / 2
                out.append({"what": f"{label}s (rear vs front)", "from": round(abs(a[key] - b[key]), 3), "to": 0.0,
                            "setter": (lambda aa, bb, kk, mm: lambda x: (aa.__setitem__(kk, mm), bb.__setitem__(kk, mm)))(a, b, key, m),
                            "message": f"The two {label}s are different ({a[key]:.2f} m and {b[key]:.2f} m). Guided mode builds symmetric legs; turn Guided constraints off to keep them different."})
    return out


def _questionable(d: dict, body_checks: SandboxBody) -> list[str]:
    notes = [f"Outside the verified design range: {s}. It will still simulate." for s in body_checks.outside_scientific_bounds()]
    if abs(d["pitch"]) > 0.3:
        notes.append(f"It starts leaning {math.degrees(abs(d['pitch'])):.0f}°.")
    for i, L in enumerate(d["legs"]):
        hip, knee, ankle = _joints(d, i)
        if abs(hip) > 0.7 or knee < -1.6 or abs(ankle) > 0.5:
            notes.append(f"{('rear', 'front')[i].capitalize()} leg starts in an extreme pose (hip {math.degrees(hip):.0f}°, knee {math.degrees(knee):.0f}°, ankle {math.degrees(ankle):.0f}°).")
    leg_mass = 2 * math.pi * 0.0375 ** 2 * (d["legs"][0]["thigh"] + d["legs"][0]["shank"]) * d["leg_density"]
    if leg_mass > 0 and d["torso_mass"] / leg_mass > 8:
        notes.append(f"Top-heavy: the torso weighs {d['torso_mass'] / leg_mass:.0f}× both legs together.")
    if d["torque_limit"] < 10:
        notes.append(f"Very weak motors ({d['torque_limit']:g} N·m).")
    if d["foot_friction"] < 0.2:
        notes.append(f"Very slippery feet (μ = {d['foot_friction']:g}).")
    return notes


def _to_body(d: dict) -> SandboxBody:
    a, b = d["legs"]
    pose = (d["pitch"], *_joints(d, 0), *_joints(d, 1))
    return SandboxBody(torso_mass=round(d["torso_mass"], 4), thigh_length=round(a["thigh"], 6), shank_length=round(a["shank"], 6), foot_length=round(a["foot"], 6),
                       foot_friction=d["foot_friction"], torque_limit=d["torque_limit"], leg_density=d["leg_density"],
                       thigh_length_r=round(b["thigh"], 6), shank_length_r=round(b["shank"], 6), foot_length_r=round(b["foot"], 6),
                       pose=tuple(round(float(x), 6) for x in pose))


def _skeleton(d: dict, base_m: tuple, px_per_m: float) -> dict:
    """The compiled physical structure as canvas pixels, anchored at the drawn torso base (forward kinematics, no physics)."""
    def px(p):
        return [round(p[0] * px_per_m, 2), round(-p[1] * px_per_m, 2)]
    bx, bz = base_m
    top = (bx + TORSO_H * math.sin(d["pitch"]), bz + TORSO_H * math.cos(d["pitch"]))
    legs = []
    for L in d["legs"]:
        hip = (bx, bz)
        knee = (hip[0] - L["thigh"] * math.sin(L["th_t"]), hip[1] - L["thigh"] * math.cos(L["th_t"]))
        ankle = (knee[0] - L["shank"] * math.sin(L["th_s"]), knee[1] - L["shank"] * math.cos(L["th_s"]))
        c, s = math.cos(L["tilt"]), -math.sin(L["tilt"])
        toe = (ankle[0] + 0.75 * L["foot"] * c, ankle[1] + 0.75 * L["foot"] * s)
        heel = (ankle[0] - 0.25 * L["foot"] * c, ankle[1] - 0.25 * L["foot"] * s)
        legs.append({"hip": px(hip), "knee": px(knee), "ankle": px(ankle), "toe": px(toe), "heel": px(heel)})
    lowest = max(max(j[1] for j in leg.values()) for leg in legs)
    return {"torso": {"base": px((bx, bz)), "top": px(top), "half_width": round(0.06 * px_per_m, 2)}, "legs": legs, "ground_y": lowest}


def _copy(d: dict) -> dict:
    return {**d, "legs": [{**L} for L in d["legs"]]}


def _finish(res: dict, design: dict, base_m: tuple, guided: bool, mirror: bool) -> dict:
    notes = res["notes"]
    d = _copy(design)
    if guided:
        _snap(d, res["adjustments"])
    else:
        # a hand-drawn "straight" leg is never exactly straight: a knee bent less than ~6 degrees the wrong way is the joint limit
        # at work, not a different creature. It is clamped and reported (no other snapping happens when guidance is off).
        for i, L in enumerate(d["legs"]):
            knee = L["th_s"] - L["th_t"]
            if 0 < knee <= KNEE_TOL:
                if math.degrees(knee) >= 0.5:
                    notes.append(f"The {('rear', 'front')[i]} knee bent {math.degrees(knee):.1f}° the wrong way; the joint limit makes it straight.")
                L["th_s"] = L["th_t"]
    viol = _violations(d, guided)
    if viol:
        res["errors"] = [v["message"] for v in viol]
        res["outcome"], res["status"] = "unrepresentable", "ok"
        if guided:
            res["errors"].append("Turn Guided constraints off to try this drawing in the experimental sandbox." if any("verified" in v["message"] or "design range" in v["message"] for v in viol) else "")
            res["errors"] = [e for e in res["errors"] if e]
        ap = _copy(d)
        before = _skeleton(d, base_m, PX_PER_M)
        changes = []
        for v in _violations(ap, guided):
            v["setter"](v["to"])
            changes.append({"what": v["what"], "from": v["from"], "to": round(v["to"], 4), "why": v["message"]})
        # clamping can expose a further violation (e.g. a clamped length changes nothing else): iterate once more, bounded
        for _ in range(3):
            more = _violations(ap, guided)
            if not more:
                break
            for v in more:
                v["setter"](v["to"])
                changes.append({"what": v["what"], "from": v["from"], "to": round(v["to"], 4), "why": v["message"]})
        try:
            body = _to_body(ap).validate()
            res["approximation"] = {"body": body.as_dict(), "changes": changes, "before": before, "after": _skeleton(ap, base_m, PX_PER_M),
                                    "notice": "This is a different creature from the one you drew. It is only simulated if you confirm."}
        except ValueError:
            res["approximation"] = None
        res["skeleton"] = before
        res["detected"] = before
        return res
    try:
        body = _to_body(d).validate()
    except ValueError as exc:
        res["errors"] = [str(exc)]
        res["outcome"] = "unrepresentable"
        return res
    res["body"] = body.as_dict()
    res["status"] = "ok"
    q = _questionable(d, body)
    res["skeleton"] = _skeleton(d, base_m, PX_PER_M)
    res["detected"] = _skeleton(design, base_m, PX_PER_M)
    if q:
        res["outcome"] = "questionable"
        notes.extend(q)
    else:
        res["outcome"] = "valid_with_snaps" if res["adjustments"] else "valid"
    return res
