"""Control-law mechanisms: a small, safe DSL for new walking-controller terms, plus the controller hook that applies them.

A *mechanism* is a JSON dict
    {"id": str (1-24 chars [A-Za-z0-9_-]), "target": TARGETS, "leg": LEGS, "terms": [1-4 DSL strings],
     "gain_bound": float in (0, 5], optional "rationale": str, optional "revises": str}
and contributes `offset = ramp * sum_i gain_i * term_i` to the base 15-D phase-gait controller (`MechanismController`). The gains are
the only free numbers (searched by CMA-ES, each in [-gain_bound, gain_bound]); the structure (terms, target, leg) is fixed.

DSL (Python expression syntax parsed with `ast`; an explicit node whitelist; anything else is REJECTED with a reason, never repaired)
  * numbers (finite int/float literals), the names in `SIGNALS`, unary + -, binary + - * / (NOT **, %, //), and calls to
    tanh, clip(x, lo, hi), abs, min, max (two arguments), sin, cos, sqrt_abs (sqrt of |x|). No comparisons, attributes, subscripts,
    keywords, lambdas, comprehensions, strings, conditionals, boolean operators. Length <= 200 characters, nesting depth <= 6
    (a number or name has depth 0; each operator/call adds one).
  * Division is safe: a / b -> a / (b if |b| > 1e-6 else copysign(1e-6, b)).
  * Each term value goes through nan_to_num (nan -> 0, +-inf -> +-10) and is clipped to [-10, 10]. A term whose evaluation raises an
    arithmetic error (overflow, sin of inf) is 0.0.
  * Compiled from the validated AST (constants are floats, `/` becomes a call to the safe divide) and run with
    `{"__builtins__": {}}` plus only the whitelisted functions; the signals are the local namespace.

Application (per physics step, per leg), after the base controller's own reference/feedback terms
  * the mechanism applies to a leg when `leg` is "both", or "swing"/"stance" matches the phase clock (swing = leg phase >= duty);
  * target hip/knee/ankle: the offset is clipped to +-OFFSET_LIM (0.5 rad) and added to that joint's REFERENCE angle only (the ankle
    reference is NOT re-levelled when hip/knee change; a targeted ankle reference is clipped to +-ANKLE_LIM like the base);
  * target torque_*: the offset is added to that joint's torque after the stance feedback, clipped to +-FB_CAP * torque_limit;
  * several mechanisms on one joint add before clipping;
  * a gain of exactly 0 skips its term entirely (it is not even evaluated). If every gain is 0 no mechanism code runs and the torque
    arithmetic is the base controller's, so the 10 s trace is BIT-IDENTICAL to `PhaseGaitInitController` (tested with ==).

Signals (`SIGNAL_DOCS`) are per leg and per physics step. `d`, `v`, `h` use the same forward kinematics and stance-leg choice as
`phasegait_fp` (loaded legs preferring those in clock stance, the one whose ankle is furthest behind the hip; hold the last value if
none is loaded) but are UNFILTERED and un-latched: phasegait_fp low-passes (d, v) with FILTER_S, slew-limits the target and latches it
over stance; the DSL counterpart `expert_foot_placement()` has none of that, so it is not numerically the same law as the 17-D one.
"""
from __future__ import annotations

import ast
import math
import re
from typing import Sequence

import numpy as np

from .contact import ContactConfig
from .phasegait import ANKLE_LIM, BOUNDS as _BASE_BOUNDS, FB_CAP, MAX_PHASE_BOOST, PhaseGaitParams, _smoothstep, leg_references
from .phasegait_fp import G, OFFSET_LIM, PhaseGaitFPController, _legs
from .phasegait_init import INIT_BOUNDS as _INIT_BOUNDS, InitParams, PhaseGaitInitController, controller_from_vector

N_BASE = len(_BASE_BOUNDS) + len(_INIT_BOUNDS)      # 15
TARGETS = ("hip", "knee", "ankle", "torque_hip", "torque_knee", "torque_ankle")
LEGS = ("swing", "stance", "both")
MAX_MECHANISMS = 2
MAX_GAINS = 8
MAX_TERMS = 4
MAX_EXPR_LEN = 200
MAX_DEPTH = 6
TERM_CLIP = 10.0
EPS = 1e-6
FUNCS = ("tanh", "clip", "abs", "min", "max", "sin", "cos", "sqrt_abs")
_ARITY = {"tanh": 1, "clip": 3, "abs": 1, "min": 2, "max": 2, "sin": 1, "cos": 1, "sqrt_abs": 1}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}\Z")
_KEYS = {"id", "target", "leg", "terms", "gain_bound", "rationale", "revises"}

SIGNAL_DOCS = {
    "phase": "this leg's phase in [0, 1) (the clock; leg B is offset by 0.5)",
    "swing": "1.0 if this leg is in swing by the phase clock (phase >= duty), else 0.0",
    "stance": "1.0 if this leg is in stance by the phase clock, else 0.0",
    "loaded": "1.0 if this leg's foot has debounced ground contact, else 0.0",
    "pitch": "torso pitch (rad), positive = leaning forward",
    "pitch_rate": "torso pitch rate (rad/s)",
    "hip": "this leg's hip angle (rad); positive swings the foot backward",
    "knee": "this leg's knee angle (rad); negative = flexed",
    "ankle": "this leg's ankle angle (rad)",
    "hip_rate": "this leg's hip angular rate (rad/s)",
    "knee_rate": "this leg's knee angular rate (rad/s)",
    "ankle_rate": "this leg's ankle angular rate (rad/s)",
    "d": "horizontal hip-minus-ankle offset of the current STANCE leg divided by leg length L (positive = hip ahead of the ankle)",
    "v": "time derivative of that offset divided by sqrt(g L) (positive = hip moving forward over the stance foot)",
    "h": "height of the stance hip above its ankle divided by L",
    "t": "time since the start of the rollout (s)",
}
SIGNALS = tuple(SIGNAL_DOCS)
_GEO = ("d", "v", "h")


# ----------------------------------------------------------------------------------------------------------
# safe functions
# ----------------------------------------------------------------------------------------------------------
def _sdiv(a, b):
    if not abs(b) > EPS:
        b = math.copysign(EPS, b)
    return a / b


def _sin(x):
    return math.sin(x) if math.isfinite(x) else math.nan


def _cos(x):
    return math.cos(x) if math.isfinite(x) else math.nan


def _clip(x, lo, hi):
    return min(max(x, lo), hi)


def _sqrt_abs(x):
    return math.sqrt(abs(x))


def _make_namespace() -> dict:
    return {"__builtins__": {}, "tanh": math.tanh, "clip": _clip, "abs": abs, "min": min, "max": max, "sin": _sin,
            "cos": _cos, "sqrt_abs": _sqrt_abs, "_sdiv": _sdiv}


# ----------------------------------------------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------------------------------------------
_OK_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_OK_UNOPS = (ast.UAdd, ast.USub)


def _depth(node) -> int:
    if isinstance(node, (ast.Constant, ast.Name)):
        return 0
    if isinstance(node, ast.BinOp):
        return 1 + max(_depth(node.left), _depth(node.right))
    if isinstance(node, ast.UnaryOp):
        return 1 + _depth(node.operand)
    if isinstance(node, ast.Call):
        return 1 + max([_depth(a) for a in node.args] or [0])
    return 0


def _check_node(node, reasons: list, names: set) -> None:
    if isinstance(node, ast.Constant):
        v = node.value
        if type(v) not in (int, float):
            reasons.append(f"only numeric literals are allowed (got {type(v).__name__})")
            return
        try:
            ok = math.isfinite(float(v))
        except OverflowError:
            ok = False
        if not ok:
            reasons.append("numeric literal is not finite")
    elif isinstance(node, ast.Name):
        if node.id not in SIGNALS:
            reasons.append(f"unknown name {node.id!r} (allowed signals: {', '.join(SIGNALS)})")
        else:
            names.add(node.id)
    elif isinstance(node, ast.BinOp):
        if not isinstance(node.op, _OK_BINOPS):
            reasons.append(f"operator {type(node.op).__name__} is not allowed (only + - * /)")
        _check_node(node.left, reasons, names)
        _check_node(node.right, reasons, names)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _OK_UNOPS):
            reasons.append(f"unary operator {type(node.op).__name__} is not allowed (only + -)")
        _check_node(node.operand, reasons, names)
    elif isinstance(node, ast.Call):
        f = node.func
        if not isinstance(f, ast.Name) or f.id not in FUNCS:
            reasons.append(f"calls are only allowed to {', '.join(FUNCS)}")
            return
        if node.keywords:
            reasons.append("keyword arguments are not allowed")
        if any(isinstance(a, ast.Starred) for a in node.args):
            reasons.append("starred arguments are not allowed")
        if len(node.args) != _ARITY[f.id]:
            reasons.append(f"{f.id} takes {_ARITY[f.id]} argument(s), got {len(node.args)}")
        for a in node.args:
            _check_node(a, reasons, names)
    else:
        reasons.append(f"{type(node).__name__} expressions are not allowed")


def _parse_term(src) -> tuple:
    """(reasons, validated tree or None, signal names used) for one DSL expression."""
    if not isinstance(src, str):
        return [f"a term must be a string, got {type(src).__name__}"], None, set()
    if not src.strip():
        return ["empty term"], None, set()
    if len(src) > MAX_EXPR_LEN:
        return [f"term longer than {MAX_EXPR_LEN} characters"], None, set()
    try:
        tree = ast.parse(src.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        return [f"not a valid expression ({type(exc).__name__})"], None, set()
    reasons: list = []
    names: set = set()
    try:
        _check_node(tree.body, reasons, names)
        if not reasons and _depth(tree.body) > MAX_DEPTH:
            reasons.append(f"nesting depth above {MAX_DEPTH}")
    except RecursionError:
        reasons.append("expression too deeply nested")
    return reasons, (None if reasons else tree), names


def validate_term(src) -> list:
    return _parse_term(src)[0]


def validate_mechanism(m) -> list:
    """Reasons the mechanism is invalid (empty list = valid)."""
    if not isinstance(m, dict):
        return [f"a mechanism must be a dict, got {type(m).__name__}"]
    r: list = []
    extra = sorted(str(k) for k in m if k not in _KEYS)
    if extra:
        r.append(f"unknown key(s) {extra}")
    mid = m.get("id")
    if not isinstance(mid, str) or not _ID_RE.match(mid):
        r.append("id must be 1-24 characters of [A-Za-z0-9_-]")
    if m.get("target") not in TARGETS:
        r.append(f"target must be one of {list(TARGETS)}")
    if m.get("leg") not in LEGS:
        r.append(f"leg must be one of {list(LEGS)}")
    terms = m.get("terms")
    if not isinstance(terms, (list, tuple)) or not 1 <= len(terms) <= MAX_TERMS:
        r.append(f"terms must be a list of 1-{MAX_TERMS} expression strings")
    else:
        for i, t in enumerate(terms):
            r.extend(f"term {i}: {x}" for x in validate_term(t))
    gb = m.get("gain_bound")
    if isinstance(gb, bool) or not isinstance(gb, (int, float)) or not (math.isfinite(gb) and 0 < gb <= 5):
        r.append("gain_bound must be a number in (0, 5]")
    for k in ("rationale", "revises"):
        if k in m and (not isinstance(m[k], str) or len(m[k]) > 2000):
            r.append(f"{k} must be a string of at most 2000 characters")
    return r


def n_gains(mechs) -> int:
    return sum(len(m["terms"]) for m in mechs)


def validate_mechanisms(mechs) -> list:
    """Reasons a mechanism SET is invalid: each valid, at most 2, at most 8 gains in total, unique ids."""
    if not isinstance(mechs, (list, tuple)):
        return ["mechanisms must be a list"]
    r: list = []
    if len(mechs) > MAX_MECHANISMS:
        r.append(f"at most {MAX_MECHANISMS} mechanisms (got {len(mechs)})")
    for i, m in enumerate(mechs):
        r.extend(f"mechanism {i}: {x}" for x in validate_mechanism(m))
    if not r:
        ids = [m["id"] for m in mechs]
        if len(set(ids)) != len(ids):
            r.append("mechanism ids must be unique")
        if n_gains(mechs) > MAX_GAINS:
            r.append(f"at most {MAX_GAINS} gains in total (got {n_gains(mechs)})")
    return r


# ----------------------------------------------------------------------------------------------------------
# compilation
# ----------------------------------------------------------------------------------------------------------
class _Rewrite(ast.NodeTransformer):
    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(float(node.value)), node)

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Div):
            return ast.copy_location(ast.Call(ast.Name("_sdiv", ast.Load()), [node.left, node.right], []), node)
        return node


class Compiled:
    """A validated, compiled mechanism. `evaluate(signals)` -> term values (nan_to_num, clipped to +-10)."""

    def __init__(self, mechanism: dict):
        reasons = validate_mechanism(mechanism)
        if reasons:
            raise ValueError("invalid mechanism: " + "; ".join(reasons))
        self.mechanism = mechanism
        self.id, self.target, self.leg = mechanism["id"], mechanism["target"], mechanism["leg"]
        self.gain_bound = float(mechanism["gain_bound"])
        self.namespace = _make_namespace()
        self.codes, used = [], set()
        for src in mechanism["terms"]:
            _, tree, names = _parse_term(src)
            used |= names
            expr = ast.fix_missing_locations(_Rewrite().visit(tree))
            self.codes.append(compile(expr, f"<mechanism {self.id}>", "eval"))
        self.signals_used = frozenset(used)
        self.n_terms = len(self.codes)

    def term(self, i: int, signals: dict) -> float:
        try:
            v = eval(self.codes[i], self.namespace, signals)  # noqa: S307 - validated whitelist AST, empty builtins
        except (ArithmeticError, ValueError):
            return 0.0
        if v != v:
            return 0.0
        return TERM_CLIP if v > TERM_CLIP else (-TERM_CLIP if v < -TERM_CLIP else float(v))

    def evaluate(self, signals: dict) -> np.ndarray:
        return np.array([self.term(i, signals) for i in range(self.n_terms)], dtype=float)


def compile_mechanism(m: dict) -> Compiled:
    return Compiled(m)


# ----------------------------------------------------------------------------------------------------------
# the controller
# ----------------------------------------------------------------------------------------------------------
class MechanismController(PhaseGaitInitController):
    """15-D phase-gait controller plus up to 2 DSL mechanisms with fitted gains (see the module docstring)."""
    name = "phase_gait_mech"

    def __init__(self, params: PhaseGaitParams, init: InitParams, mechanisms: Sequence[dict], gains: Sequence[float],
                 body=None, contact: ContactConfig = ContactConfig()):
        super().__init__(params, init, contact)
        mechanisms = list(mechanisms)
        reasons = validate_mechanisms(mechanisms)
        if reasons:
            raise ValueError("invalid mechanisms: " + "; ".join(reasons))
        gains = [float(g) for g in gains]
        if len(gains) != n_gains(mechanisms) or not all(math.isfinite(g) for g in gains):
            raise ValueError(f"expected {n_gains(mechanisms)} finite gains, got {len(gains)}")
        self.mechanisms = [dict(m) for m in mechanisms]
        self.gains = gains
        self._active = []      # (Compiled, [(term index, gain)] with gain != 0)
        k = 0
        for m in self.mechanisms:
            c = Compiled(m)
            g = gains[k:k + c.n_terms]
            k += c.n_terms
            bad = [x for x in g if abs(x) > c.gain_bound]
            if bad:
                raise ValueError(f"mechanism {c.id}: gain(s) {bad} outside +-{c.gain_bound} (not clipped)")
            nz = [(i, x) for i, x in enumerate(g) if x != 0.0]
            if nz:
                self._active.append((c, nz))
        self._need_geo = any(s in _GEO for c, _ in self._active for s in c.signals_used)
        if self._need_geo:
            if body is None:
                raise ValueError("mechanisms using d, v or h need the body (leg geometry)")
            self.legs = _legs(body)
            self.L = sum(t + s for t, s in self.legs) / 2.0

    def reset(self, torque_limit: float, weight_n: float) -> None:
        super().reset(torque_limit, weight_n)
        self._geo = (0.0, 0.0, 1.0)
        self._have_geo = False

    def _stance_geometry(self, pitch, pitch_rate, q, qd) -> None:
        """(d/L, v/sqrt(gL), h/L) of the stance leg, with phasegait_fp's FK and choice (unfiltered)."""
        loaded = [leg for leg in (0, 1) if self.est.deb[leg]]
        if not loaded:
            if self._have_geo:
                return
            loaded = [0, 1]
        clock = [leg for leg in loaded if (self.phi + 0.5 * leg) % 1.0 < self.p.duty]
        cands = clock or loaded
        geo = {leg: PhaseGaitFPController.leg_offset(self, leg, pitch, pitch_rate, q, qd) for leg in cands}
        leg = max(cands, key=lambda k: geo[k][0])
        d, v = geo[leg]
        t, s = self.legs[leg]
        a1 = pitch + q[3 * leg]
        h = t * math.cos(a1) + s * math.cos(a1 + q[3 * leg + 1])
        self._geo = (d / self.L, v / math.sqrt(G * self.L), h / self.L)
        self._have_geo = True

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
        active = self._active
        if self._need_geo:
            self._stance_geometry(pitch, pitch_rate, q, qd)
        tau = [0.0] * 6
        cap = FB_CAP * self.limit
        for leg in (0, 1):
            phi_leg = (self.phi + 0.5 * leg) % 1.0
            ref = leg_references(p, phi_leg, ramp, pitch)
            ref_off = tq_off = None
            if active:
                swing = phi_leg >= p.duty
                sig = None
                for c, nz in active:
                    if c.leg != "both" and (c.leg == "swing") != swing:
                        continue
                    if sig is None:
                        i0 = 3 * leg
                        sig = {"phase": phi_leg, "swing": 1.0 if swing else 0.0, "stance": 0.0 if swing else 1.0,
                               "loaded": 1.0 if self.est.deb[leg] else 0.0, "pitch": pitch, "pitch_rate": pitch_rate,
                               "hip": q[i0], "knee": q[i0 + 1], "ankle": q[i0 + 2], "hip_rate": qd[i0],
                               "knee_rate": qd[i0 + 1], "ankle_rate": qd[i0 + 2], "d": self._geo[0], "v": self._geo[1],
                               "h": self._geo[2], "t": t}
                    off = 0.0
                    for i, g in nz:
                        off += g * c.term(i, sig)
                    off *= ramp
                    is_tq = c.target.startswith("torque_")
                    j = ("hip", "knee", "ankle").index(c.target[7:] if is_tq else c.target)
                    if is_tq:
                        tq_off = tq_off or [0.0, 0.0, 0.0]
                        tq_off[j] += off
                    else:
                        ref_off = ref_off or [0.0, 0.0, 0.0]
                        ref_off[j] += off
            if ref_off is not None:
                r = [ref[0], ref[1], ref[2]]
                for j in range(3):
                    if ref_off[j] != 0.0:
                        r[j] = r[j] + min(max(ref_off[j], -OFFSET_LIM), OFFSET_LIM)
                if ref_off[2] != 0.0:
                    r[2] = min(max(r[2], -ANKLE_LIM), ANKLE_LIM)
                ref = tuple(r)
            for j in range(3):
                i = 3 * leg + j
                tau[i] = p.kp * (ref[j] - q[i]) - p.kd * qd[i]
            if self.est.deb[leg]:
                fb = p.pitch_kp * (pitch - self._pitch_ref(t)) + 0.25 * p.pitch_kp * pitch_rate
                tau[3 * leg] += min(max(fb, -cap), cap)
                ab = p.balance_gain * (pitch + 0.3 * pitch_rate)
                tau[3 * leg + 2] += min(max(ab, -cap), cap)
            if tq_off is not None:
                for j in range(3):
                    if tq_off[j] != 0.0:
                        tau[3 * leg + j] += min(max(tq_off[j], -cap), cap)
        return np.array(tau)


def controller_from_spec(vector, mechanisms: Sequence[dict] = (), body=None):
    """vector = 15 base parameters followed by the gains (mechanism order, then term order).

    No mechanisms: exactly `phasegait_init.controller_from_vector(vector, body=body)` (for a 15-D vector the same as vector[:15]).
    With mechanisms the vector must have 15 + n_gains entries; 17-D foot-placement vectors are not combined with mechanisms."""
    mechs = list(mechanisms or ())
    if not mechs:
        return controller_from_vector(vector, body=body)
    reasons = validate_mechanisms(mechs)
    if reasons:
        raise ValueError("invalid mechanisms: " + "; ".join(reasons))
    v = np.asarray(vector, dtype=float)
    ng = n_gains(mechs)
    if len(v) != N_BASE + ng:
        raise ValueError(f"vector must have {N_BASE} base parameters + {ng} gains = {N_BASE + ng} entries, got {len(v)} "
                         "(17-D foot-placement vectors cannot be combined with mechanisms)")
    n = len(_BASE_BOUNDS)
    return MechanismController(PhaseGaitParams.from_vector(v[:n]), InitParams(*[float(x) for x in v[n:N_BASE]]), mechs,
                               [float(x) for x in v[N_BASE:]], body=body)


# ----------------------------------------------------------------------------------------------------------
# non-AI structure generators
# ----------------------------------------------------------------------------------------------------------
_BIN = ("+", "-", "*", "/")
_UN1 = ("tanh", "abs", "sin", "cos", "sqrt_abs")


def _rand_expr(rng, depth: int) -> str:
    if depth == 0 or rng.random() < 0.25:
        if rng.random() < 0.8:
            return SIGNALS[int(rng.integers(len(SIGNALS)))]
        return repr(round(float(rng.uniform(0.1, 2.0)), 2))
    kind = int(rng.integers(0, 4))          # binary, unary function, negation, min/max/clip
    if kind == 0:
        return f"({_rand_expr(rng, depth - 1)} {_BIN[int(rng.integers(4))]} {_rand_expr(rng, depth - 1)})"
    if kind == 1:
        return f"{_UN1[int(rng.integers(len(_UN1)))]}({_rand_expr(rng, depth - 1)})"
    if kind == 2:
        return f"(-{_rand_expr(rng, depth - 1)})"
    if rng.random() < 0.5:
        return f"{('min', 'max')[int(rng.integers(2))]}({_rand_expr(rng, depth - 1)}, {_rand_expr(rng, depth - 1)})"
    lo = round(float(rng.uniform(0.1, 1.0)), 2)
    return f"clip({_rand_expr(rng, depth - 1)}, -{lo}, {round(lo + float(rng.uniform(0.0, 1.0)), 2)})"


def random_mechanism(rng, n_terms: int = 2, id: str = "rand") -> dict:
    """A valid random mechanism. Distribution: target uniform over TARGETS, leg uniform over LEGS; each term an independent random
    tree of depth <= 2 (a leaf with prob 1/4 before the depth limit; leaf = uniform signal w.p. 0.8, else a constant uniform in
    [0.1, 2] rounded to 2 decimals; inner node uniform over {binary + - * /, unary tanh/abs/sin/cos/sqrt_abs, negation,
    min/max, clip with constant bounds}); terms containing no signal are redrawn. gain_bound is 1.0 for reference targets and 5.0
    for torque targets. `rng` is a numpy Generator; the draw is deterministic per seed."""
    if not 1 <= n_terms <= MAX_TERMS:
        raise ValueError(f"n_terms must be 1-{MAX_TERMS}")
    target = TARGETS[int(rng.integers(len(TARGETS)))]
    leg = LEGS[int(rng.integers(len(LEGS)))]
    terms = []
    while len(terms) < n_terms:
        s = _rand_expr(rng, 2)
        reasons, _, names = _parse_term(s)
        if not reasons and names:
            terms.append(s)
    m = {"id": id, "target": target, "leg": leg, "terms": terms, "gain_bound": 5.0 if target.startswith("torque_") else 1.0}
    bad = validate_mechanism(m)
    if bad:
        raise AssertionError(f"random_mechanism produced an invalid mechanism: {bad}")
    return m


def generic_linear_mechanisms() -> list:
    """The fixed generic structure: a linear hip-reference law in (d, v, pitch, pitch_rate) for swing and for stance (8 gains)."""
    return [{"id": f"gen_hip_{leg}", "target": "hip", "leg": leg, "terms": ["d", "v", "pitch", "pitch_rate"], "gain_bound": 1.5}
            for leg in ("swing", "stance")]


def expert_foot_placement() -> dict:
    """The DSL counterpart of phasegait_fp's law (swing hip += -(kd d + kv v)); no filtering, slew limit, blend or latch."""
    return {"id": "expert_fp", "target": "hip", "leg": "swing", "terms": ["-d", "-v"], "gain_bound": 1.5}
