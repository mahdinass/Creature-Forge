"""Forge Loop evidence pack: a compact, deterministic JSON object the model reasons over, plus citation resolution.

Everything in the pack is a measurement or a deterministic function of measurements (creature description, MuJoCo challenge results
computed by `challenges.run_challenge`, MuJoCo's own compiled masses). It contains no hypotheses and no hint of a fix. The model cites
values by path (`resolve`); a citation must resolve to a SCALAR (number, string or bool) or it is invalid.

Size: `build_evidence` returns <= `PACK_LIMIT_BYTES` of compact JSON (about 2-2.5k tokens) whenever it is possible, by stepping through
`LEVELS` from rich to lean (fewer seeds, fewer metrics, shorter timelines, shorter history). Earlier live runs returned `content=null` when
the prompt was ~2.7k tokens and reasoning ate the completion budget, so this limit is deliberate.

Layout (stable keys):
  creature.{mode, body.{torso_mass, leg_density, foot_friction, torque_limit, rear.{thigh_length, shank_length, foot_length}, front.{..}},
            start?, derived.{leg_length_rear, leg_length_front, foot_to_leg, mass_total, weight_n, torque_to_weight}}
  challenge.{kind, seeds_n, duration, settle_s?, start?, target_force?}
  controller.stand.{kind, edited, kp, kd, ...}            (stand/push)   |   controller.walk.{kind, edited, adaptation?, params.{freq, ...}} (walk)
  outcome.{aggregate, counts.{FAIL, POOR, PASS, ERROR}, seeds_n, score.{median, mean, min, max}}
  seeds[i].{seed, outcome, score, metrics.{...}, events[j].{kind, time}}     ordered worst -> best by score; seeds[0] is the worst
  forensics.{...}                                          compacted ChallengeResult.forensics
  history[k].{round, ...}                                  prior rounds (scalars only)
  bounds.<param> = {lo, hi, current | rear, front, u?}     editable parameters only; control params are nested: bounds.stand.kp, bounds.walk.freq
Derived quantities: leg_length_* = thigh + shank; foot_to_leg = mean foot_length / mean leg length; mass_total = sum of MuJoCo body masses
(note: the torso box mass MuJoCo compiles is not necessarily the `torso_mass` parameter); weight_n = mass_total * 9.81;
torque_to_weight = torque_limit / (weight_n * mean leg length) (dimensionless).
"""
from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass

from . import interventions as iv
from .sandbox import SandboxBody, sandbox_model

G = 9.81
PACK_LIMIT_BYTES = 6000
MAX_SEEDS = 6
MAX_HISTORY = 5
_DROP_KEYS = {"definitions", "note", "notes", "description", "caveat", "columns_help"}
_METRIC_PRIORITY = (
    "critical_force_fwd", "critical_force_bwd", "weak_direction", "censored", "survival_s", "fell", "fall_time",
    "max_abs_pitch_after_settle", "min_height_ratio", "saturation_frac", "slip_frac", "settle_s", "z_ref",
    "forward_distance", "distance", "valid_steps", "label", "speed_upright")
_POSE_NAMES = ("torso_pitch", "rear_hip", "rear_knee", "rear_ankle", "front_hip", "front_knee", "front_ankle")


@dataclass(frozen=True)
class Level:
    seeds: int
    metrics: int
    events: int
    rows: int           # forensics timeline rows kept (0 drops the timeline)
    history: int
    items: int          # list items kept in forensics lists
    depth: int          # forensics nesting depth kept
    fx_bytes: int       # byte budget of the compacted forensics block


LEVELS = (
    Level(MAX_SEEDS, 8, 1, 4, MAX_HISTORY, 5, 4, 2200),
    Level(MAX_SEEDS, 6, 1, 4, 3, 4, 4, 1800),
    Level(4, 6, 1, 4, 2, 4, 4, 1400),
    Level(3, 5, 1, 3, 1, 3, 4, 1000),
    Level(3, 4, 0, 0, 0, 3, 3, 700),
    Level(3, 3, 0, 0, 0, 2, 2, 400),
)


def pack_size(pack: dict) -> int:
    """Bytes of the compact UTF-8 JSON the prompt will carry."""
    return len(json.dumps(pack, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8"))


# ------------------------------------------------------------------------------------------------------------------ citations
class UnresolvedCitation(ValueError):
    """The path does not exist in the evidence pack or does not point to a scalar."""


_SEG = re.compile(r"^([^.\[\]\s]+)((?:\[\d+\])*)$")
_IDX = re.compile(r"\[(\d+)\]")


def resolve(evidence: dict, path: str):
    """Look up a dotted/indexed path such as `seeds[0].metrics.critical_force_bwd` (a bare dotted integer, `seeds.0.score`, also works).
    Returns the scalar (str, bool, finite int/float). Raises UnresolvedCitation if the path is malformed, absent, null, or points to a
    list/object."""
    if not isinstance(path, str) or not path.strip():
        raise UnresolvedCitation("empty path")
    cur = evidence
    for seg in path.strip().split("."):
        m = _SEG.match(seg)
        if not m:
            raise UnresolvedCitation(f"malformed path segment {seg!r} in {path!r}")
        key, idx = m.group(1), _IDX.findall(m.group(2))
        if isinstance(cur, dict):
            if key not in cur:
                raise UnresolvedCitation(f"{path!r}: no key {key!r}")
            cur = cur[key]
        elif isinstance(cur, list) and key.isdigit():
            if int(key) >= len(cur):
                raise UnresolvedCitation(f"{path!r}: index {key} out of range ({len(cur)} items)")
            cur = cur[int(key)]
        else:
            raise UnresolvedCitation(f"{path!r}: cannot take {key!r} of a {type(cur).__name__}")
        for i in idx:
            if not isinstance(cur, list) or int(i) >= len(cur):
                raise UnresolvedCitation(f"{path!r}: index [{i}] is not available")
            cur = cur[int(i)]
    if cur is None or isinstance(cur, (dict, list)):
        raise UnresolvedCitation(f"{path!r} does not point to a single value (it is {'null' if cur is None else type(cur).__name__})")
    if isinstance(cur, float) and not math.isfinite(cur):
        raise UnresolvedCitation(f"{path!r} is not a finite number")
    return cur


CITABLE_EXCLUDE = ("bounds",)   # edit bounds are rules stated in their own prompt section, not measurements to cite (they still resolve)


def leaf_items(evidence: dict, limit: int = 400, exclude: tuple = CITABLE_EXCLUDE) -> list[tuple[str, object]]:
    """(path, scalar) for every citable scalar leaf of the pack, in pack order; each path round-trips through `resolve`. Top-level keys in
    `exclude` are skipped, as are keys that cannot be written as a path segment."""
    out: list[tuple[str, object]] = []

    def walk(obj, prefix: str) -> None:
        if len(out) >= limit:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if not (isinstance(k, str) and _SEG.match(k)) or (not prefix and (k in exclude or k in ("detail_level", "truncated"))):
                    continue
                walk(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{prefix}[{i}]")
        elif obj is not None and not (isinstance(obj, float) and not math.isfinite(obj)):
            out.append((prefix, obj))

    walk(evidence, "")
    return out


def leaf_paths(evidence: dict, limit: int = 400, exclude: tuple = CITABLE_EXCLUDE) -> list[str]:
    """The citable paths (see `leaf_items`). Used to constrain the model's citations (JSON-schema enum + prompt lines)."""
    return [p for p, _ in leaf_items(evidence, limit, exclude)]


def try_resolve(evidence: dict, path: str):
    """(True, value) or (False, reason)."""
    try:
        return True, resolve(evidence, path)
    except UnresolvedCitation as e:
        return False, str(e)


# ------------------------------------------------------------------------------------------------------------------ helpers
def _r(x):
    return round(x, 4) if isinstance(x, float) and math.isfinite(x) else x


def _clip(s: str, n: int = 120) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _compact(obj, lv: Level, depth: int = 0):
    """JSON-safe, rounded, None/NaN-free copy of `obj` limited by the level. Returns a `_GONE` sentinel for empty results."""
    if obj is None or (isinstance(obj, float) and not math.isfinite(obj)):
        return _GONE
    if isinstance(obj, bool) or isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return _r(obj)
    if isinstance(obj, str):
        return _clip(obj)
    if depth >= lv.depth:
        return _GONE
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _DROP_KEYS or not isinstance(k, str):
                continue
            if k == "timeline" and isinstance(v, dict):
                tl = _timeline(v, lv.rows)
                if tl is not None:
                    out[k] = tl
                continue
            c = _compact(v, lv, depth + 1)
            if c is not _GONE:
                out[k] = c
        return out or _GONE
    if isinstance(obj, (list, tuple)):
        items = list(obj)
        if items and all(isinstance(x, (list, tuple)) for x in items) and lv.rows:
            items = _spread(items, lv.rows)
        else:
            items = items[: lv.items]
        out = [c for c in (_compact(x, lv, depth + 1) for x in items) if c is not _GONE]
        return out or _GONE
    return _GONE


class _Gone:
    pass


_GONE = _Gone()


def _spread(items: list, n: int) -> list:
    """n items spread evenly over the list, always including the first and the last."""
    if len(items) <= n:
        return items
    if n <= 1:
        return items[:1]
    idx = sorted({round(i * (len(items) - 1) / (n - 1)) for i in range(n)})
    return [items[i] for i in idx]


def _timeline(tl: dict, rows: int) -> dict | None:
    """Columns (kept whole, they label the cells) and up to `rows` rows spread evenly over the window, first and last included."""
    cols = [c for c in (tl.get("columns") or []) if isinstance(c, str)]
    good = [r for r in (tl.get("rows") or []) if isinstance(r, (list, tuple)) and len(r) == len(cols) and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in r)]
    if rows <= 0 or not good or not cols:
        return None
    return {"columns": cols, "rows": [[_r(x) for x in r] for r in _spread(good, rows)]}


def _sz(obj) -> int:
    return len(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _fit(obj, budget: int):
    """`obj` limited to about `budget` bytes of compact JSON: whole entries are kept in order while they fit, an oversized dict entry is
    trimmed recursively, anything else that does not fit is dropped. Returns None if nothing fits."""
    if _sz(obj) <= budget:
        return obj
    if not isinstance(obj, dict):
        return None
    out: dict = {}
    used = 2
    for k, v in obj.items():
        cost = _sz({k: v}) - 1
        if used + cost <= budget:
            out[k] = v
            used += cost
        elif isinstance(v, dict):
            sub = _fit(v, budget - used - len(k) - 4)
            if sub:
                out[k] = sub
                used += _sz({k: sub}) - 1
    return out or None


def _scalars(d, keep: int) -> dict:
    """Up to `keep` scalar entries of a metrics dict: known important keys first, then the rest alphabetically; containers are skipped."""
    flat = {k: v for k, v in (d or {}).items() if isinstance(k, str) and isinstance(v, (bool, int, float, str))
            and not (isinstance(v, float) and not math.isfinite(v))}
    order = [k for k in _METRIC_PRIORITY if k in flat] + sorted(k for k in flat if k not in _METRIC_PRIORITY)
    return {k: (_clip(flat[k], 60) if isinstance(flat[k], str) else _r(flat[k])) for k in order[:keep]}


def _pick_seeds(per_seed: list[dict], n: int) -> list[dict]:
    """Worst-to-best by score; if more than n: the worst n//3, the middle ones, the best n//3."""
    ordered = sorted(per_seed, key=lambda s: (s.get("score") if isinstance(s.get("score"), (int, float)) else 0.0, s.get("seed", 0)))
    if len(ordered) <= n:
        return ordered
    kw = max(1, n // 3)
    km = n - 2 * kw
    start = max(kw, min((len(ordered) - km) // 2, len(ordered) - kw - km))
    return ordered[:kw] + ordered[start:start + km] + ordered[len(ordered) - kw:]


def _seed_block(s: dict, lv: Level) -> dict:
    d = {"seed": s.get("seed"), "outcome": s.get("outcome"), "score": _r(float(s.get("score") or 0.0)),
         "metrics": _scalars(s.get("metrics"), lv.metrics)}
    ev = [{"kind": e.get("kind"), "time": _r(float(e["time"]))} for e in (s.get("events") or [])
          if isinstance(e, dict) and isinstance(e.get("time"), (int, float)) and isinstance(e.get("kind"), str)][: lv.events]
    if ev:
        d["events"] = ev
    if s.get("error"):
        d["error"] = _clip(str(s["error"]), 100)
    return d


def _outcome_block(cr: dict) -> dict:
    per = cr.get("per_seed") or []
    scores = [float(s.get("score") or 0.0) for s in per]
    counts = {k: sum(1 for s in per if s.get("outcome") == k) for k in ("FAIL", "POOR", "PASS", "ERROR")}
    out = {"aggregate": cr.get("outcome"), "counts": counts, "seeds_n": len(per)}
    if scores:
        out["score"] = {"median": _r(statistics.median(scores)), "mean": _r(statistics.fmean(scores)),
                        "min": _r(min(scores)), "max": _r(max(scores))}
    return out


def _derived(version: dict) -> dict:
    b = iv.full_body(version)
    rear, front = b["thigh_length"] + b["shank_length"], b["thigh_length_r"] + b["shank_length_r"]
    mean_leg = (rear + front) / 2
    d = {"leg_length_rear": _r(rear), "leg_length_front": _r(front),
         "foot_to_leg": _r((b["foot_length"] + b["foot_length_r"]) / 2 / mean_leg)}
    try:
        mass = float(sum(sandbox_model(iv.sandbox_body(version)).body_mass))
    except Exception:  # the body cannot be compiled: leave the mass-derived fields out rather than invent them
        return d
    d.update(mass_total=_r(mass), weight_n=_r(mass * G), torque_to_weight=_r(b["torque_limit"] / (mass * G * mean_leg)))
    return d


def _creature_block(version: dict, spec: dict) -> dict:
    b = iv.full_body(version)
    body = {k: _r(float(b[k])) for k in ("torso_mass", "leg_density", "foot_friction", "torque_limit")}
    body["rear"] = {k: _r(float(b[k])) for k in iv.LEG_PARAMS}
    body["front"] = {k: _r(float(b[k + "_r"])) for k in iv.LEG_PARAMS}
    c = {"mode": version["mode"], "body": body}
    pose = [float(x) for x in b["pose"]]
    if spec.get("start") == "drawn" and any(abs(x) > 1e-9 for x in pose):
        c["start"] = {n: _r(x) for n, x in zip(_POSE_NAMES, pose)}
    c["derived"] = _derived(version)
    return c


def _challenge_block(spec: dict, per_seed: list) -> dict:
    d = {"kind": spec["kind"], "seeds_n": len(per_seed), "duration": _r(float(spec.get("duration", 0.0)))}
    for k in ("settle_s", "start", "target_force"):
        if k == "target_force" and spec["kind"] != "push":
            continue
        if spec.get(k) is not None:
            d[k] = _r(spec[k]) if not isinstance(spec[k], str) else spec[k]
    return d


def _controller_block(version: dict, cr: dict, kind: str) -> dict:
    prov = cr.get("controller") or {}
    if kind == "walk":
        wp = prov.get("walk") or {}
        vec = wp.get("vector") or iv.walk_vector(version)
        blk = {"kind": wp.get("kind", "r2-transfer"), "params": {n: _r(float(v)) for n, v in zip(iv.r3.PARAM_NAMES, vec)}}
        ad = wp.get("adaptation")
        if isinstance(ad, dict):
            blk["adaptation"] = {k: ad[k] for k in ("budget", "rollouts_used") if isinstance(ad.get(k), (int, float))}
        return {"walk": blk}
    sp = prov.get("stand") or {}
    params = sp.get("params") or iv.stand_params(version)
    return {"stand": {"kind": sp.get("kind", "stand-pd"), "edited": bool(sp.get("edited", False)),
                      **{k: _r(float(v)) for k, v in params.items()}}}


def _bounds_block(version: dict, kind: str) -> dict:
    out: dict = {}
    for p, d in iv.editable_params(version, kind).items():
        entry = {k: d[k] for k in ("lo", "hi", "current", "rear", "front", "u") if k in d}
        if d["kind"] == "control":
            space, name = p.split(".", 1)
            out.setdefault(space, {})[name] = entry
        else:
            out[p] = entry
    return out


def _history_block(history: list | None, lv: Level) -> list:
    if not history or lv.history <= 0:
        return []
    out = []
    for h in list(history)[-lv.history:]:
        c = _compact(h if isinstance(h, dict) else {"summary": str(h)}, Level(1, 1, 1, 0, 0, 3, 2, 0))
        if c is not _GONE:
            out.append(c)
    return out


# ------------------------------------------------------------------------------------------------------------------ public API
def build_evidence(version: dict, challenge_result: dict, history: list[dict] | None = None) -> dict:
    """Compact evidence pack for one creature version and one ChallengeResult dict (contracts section 3). Deterministic; inputs are not
    mutated. Tries `LEVELS` in order and returns the first pack of at most PACK_LIMIT_BYTES (the leanest level otherwise, with
    `truncated` listing what was cut)."""
    spec = challenge_result["spec"]
    kind = spec["kind"]
    per_seed = challenge_result.get("per_seed") or []
    pack: dict = {}
    for n, lv in enumerate(LEVELS):
        pack = {
            "creature": _creature_block(version, spec),
            "challenge": _challenge_block(spec, per_seed),
            "controller": _controller_block(version, challenge_result, kind),
            "outcome": _outcome_block(challenge_result),
            "seeds": [_seed_block(s, lv) for s in _pick_seeds(per_seed, lv.seeds)],
        }
        fx = _compact(challenge_result.get("forensics") or {}, lv)
        fx = None if fx is _GONE else _fit(fx, lv.fx_bytes)
        if fx:
            pack["forensics"] = fx
        hist = _history_block(history, lv)
        if hist:
            pack["history"] = hist
        pack["bounds"] = _bounds_block(version, kind)
        if n:
            pack["detail_level"] = n
        if pack_size(pack) <= PACK_LIMIT_BYTES:
            return pack
    pack["truncated"] = True
    return pack
