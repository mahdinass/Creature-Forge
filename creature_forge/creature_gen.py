"""Deterministic generator of guided-mode test creatures for the walking-recovery study.

Pieces (each is pure/deterministic given its arguments):
  * `walkrec_seed_block`: a seed namespace (>= 10_000_000) disjoint from `creatures.seed_block` (100_000..1_000_000)
    and disjoint between roles, so dev / selection / training / confirmatory data never share a seed.
  * `features` / `region_of` / `REGIONS`: dimensionless morphology features and a fixed 24-cell partition.
  * `GEN_DIST` / `sample_body`: the sampling distribution of guided bodies. GEN_DIST is TUNABLE on development data
    before any freeze; once a campaign is frozen, changing it changes every draw.
  * `distance`: a normalised feature-space distance for the minimum-spacing rule.
  * `is_failing` / `generate_panel`: the "genuinely failing" panel entry rule and the full-logging panel builder.
  * `dev_named_bodies`: hand-built development creatures (not part of any confirmatory panel).

Nothing here edits records or fixtures. Every draw made by `generate_panel` ends up in `accepted` or `rejected`.
"""
from __future__ import annotations

import hashlib
import math
from typing import Callable, Sequence

import numpy as np

VERSION = "creature_gen_v1"

# --------------------------------------------------------------------------------------------------------- seeds
ROLES = ("gen", "selection", "train", "screen", "probe", "validate", "confirm")
ROLE_BASE = {role: 10_000_000 * (i + 1) for i, role in enumerate(ROLES)}
_SLOTS = 150_000          # block starts: base + (h % _SLOTS) * 64; the largest start + 64 stays < base + 9_600_064 < next role
_BLOCK = 64


def walkrec_seed_block(campaign: str, role: str, key: str, k: int) -> tuple[int, ...]:
    """`k` (1..64) consecutive seeds in [ROLE_BASE[role], ROLE_BASE[role] + 9_600_064).

    base = ROLE_BASE[role] + (sha256(f"{campaign}:{role}:{key}") as an integer % 150_000) * 64. Roles occupy disjoint
    10M-wide ranges, all seeds are >= 10_000_000 (existing seeds are < 1_000_000) and < 2**31."""
    if not isinstance(campaign, str) or not campaign:
        raise ValueError("campaign must be a non-empty string")
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a non-empty string")
    if role not in ROLE_BASE:
        raise ValueError(f"role must be one of {ROLES}, got {role!r}")
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= _BLOCK:
        raise ValueError(f"k must be an integer in [1, {_BLOCK}], got {k!r}")
    h = int.from_bytes(hashlib.sha256(f"{campaign}:{role}:{key}".encode("utf-8")).digest(), "big")
    base = ROLE_BASE[role] + (h % _SLOTS) * _BLOCK
    return tuple(range(base, base + k))


# --------------------------------------------------------------------------------------------------------- features
G = 9.81
LEG_FIELDS = ("thigh_length", "shank_length", "foot_length")
BODY_FIELDS = ("torso_mass", "thigh_length", "shank_length", "foot_length", "foot_friction", "torque_limit",
               "leg_density", "thigh_length_r", "shank_length_r", "foot_length_r", "pose")

# Fixed region bands. A value equal to a boundary belongs to the UPPER band.
L_EDGES = (0.60, 0.90)          # L0 < 0.60 <= L1 < 0.90 <= L2 (values below 0.30 / above 1.20 clamp into L0 / L2)
FOOT_EDGE = 0.15                # f0 < 0.15 <= f1
TORSO_EDGE = 0.5                # t0 < 0.5 <= t1
TAU_EDGE = 0.35                 # q0 < 0.35 <= q1
REGIONS = tuple(f"L{a}-f{b}-t{c}-q{d}" for a in range(3) for b in range(2) for c in range(2) for d in range(2))


def _sandbox(body):
    from .sandbox import SandboxBody
    if isinstance(body, SandboxBody):
        return body
    d = dict(body)
    for k in LEG_FIELDS:
        if d.get(k + "_r") is None:
            d[k + "_r"] = d[k]
    d["pose"] = tuple(d.get("pose") or (0.0,) * 7)
    return SandboxBody(**{k: d[k] for k in BODY_FIELDS if k in d})


def features(body) -> dict:
    """Dimensionless features of a body dict (or SandboxBody). mass_total is the compiled MuJoCo model's total mass."""
    from .morphology import build_model
    b = _sandbox(body)
    tl, sl, fl = zip(b.leg("l"), b.leg("r"))
    L = float(np.mean([tl[i] + sl[i] for i in range(2)]))
    foot = float(np.mean(fl))
    model = build_model(b)
    mass = float(np.sum(model.body_mass))
    return {"L": L, "foot_to_leg": foot / L, "mass_total": mass, "torso_frac": float(b.torso_mass) / mass,
            "tau_ratio": float(b.torque_limit) / (mass * G * L), "friction": float(b.foot_friction),
            "leg_density": float(b.leg_density)}


def region_of(f: dict) -> str:
    """Region id like "L1-f0-t1-q0" from the fixed bands above."""
    a = sum(f["L"] >= e for e in L_EDGES)
    b = int(f["foot_to_leg"] >= FOOT_EDGE)
    c = int(f["torso_frac"] >= TORSO_EDGE)
    d = int(f["tau_ratio"] >= TAU_EDGE)
    return f"L{a}-f{b}-t{c}-q{d}"


# --------------------------------------------------------------------------------------------------------- sampling
# Tunable on development data BEFORE any freeze. Order of this dict is the order of rng draws in `sample_body`.
GEN_DIST = {
    "thigh_length": {"dist": "uniform", "lo": 0.15, "hi": 0.60},
    "shank_length": {"dist": "uniform", "lo": 0.15, "hi": 0.60},
    "foot_length": {"dist": "loguniform", "lo": 0.06, "hi": 0.30},
    "torso_mass": {"dist": "loguniform", "lo": 1.0, "hi": 15.0},
    "leg_density": {"dist": "loguniform", "lo": 300.0, "hi": 3000.0},
    "foot_friction": {"dist": "uniform", "lo": 0.4, "hi": 1.5},
    "torque_limit": {"dist": "loguniform", "lo": 15.0, "hi": 200.0},
}


def _draw(rng, spec: dict) -> float:
    u = float(rng.random())
    lo, hi = spec["lo"], spec["hi"]
    if spec["dist"] == "uniform":
        v = lo + u * (hi - lo)
    elif spec["dist"] == "loguniform":
        v = math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo)))
    else:  # pragma: no cover
        raise ValueError(f"unknown distribution {spec['dist']!r}")
    return min(hi, max(lo, round(v, 6)))


def sample_body(rng) -> dict:
    """One guided body from GEN_DIST (symmetric legs, zero pose), in the `interventions.full_body` format."""
    from .morphology import BipedParams
    from .sandbox import SandboxBody
    b = {k: _draw(rng, spec) for k, spec in GEN_DIST.items()}
    for k in LEG_FIELDS:
        b[k + "_r"] = b[k]
    b["pose"] = [0.0] * 7
    BipedParams(**{k: b[k] for k in GEN_DIST}).validate()
    SandboxBody(**{**b, "pose": tuple(b["pose"])}).validate()
    return b


# --------------------------------------------------------------------------------------------------------- distance
# Approximate range of each dimension under GEN_DIST (log units for L, foot_to_leg, mass_total, tau_ratio; linear for
# torso_frac, friction). Fixed constants so `distance` does not depend on a sampling run: ln(1.2/0.3), ln(0.30/0.06 * 4)
# (foot 0.06..0.30 over leg 0.3..1.2), ln of total mass spread (~1.6 kg .. ~30 kg), ln of tau_ratio spread, torso_frac
# spread 0.1..0.9, friction 1.1.
DIST_SCALE = {"L": 1.39, "foot_to_leg": 3.0, "mass_total": 3.0, "tau_ratio": 4.0, "torso_frac": 0.8, "friction": 1.1}
_LOG_DIMS = ("L", "foot_to_leg", "mass_total", "tau_ratio")


def distance(fa: dict, fb: dict) -> float:
    """Euclidean distance after mapping each of DIST_SCALE's dimensions to log (L, foot_to_leg, mass_total, tau_ratio)
    or linear (torso_frac, friction) and dividing by its typical range. Symmetric, zero iff identical on these dims;
    unrelated random creatures are typically ~0.5-1."""
    s = 0.0
    for k, scale in DIST_SCALE.items():
        a, b = (math.log(fa[k]), math.log(fb[k])) if k in _LOG_DIMS else (fa[k], fb[k])
        s += ((a - b) / scale) ** 2
    return math.sqrt(s)


# --------------------------------------------------------------------------------------------------------- panel rule
def _outcome(r) -> str:
    return r if isinstance(r, str) else (r.get("outcome") if isinstance(r, dict) else getattr(r, "outcome"))


def is_failing(seed_results) -> tuple[bool, str]:
    """Panel entry rule on the selection seeds (R2-transfer controller): the challenge aggregate is FAIL (>= 50 % of
    seeds fall/FAIL) AND at most one seed PASSes (== the frozen `walking` label). Any ERROR rejects. Accepts SeedResult
    objects, their dicts, or bare outcome strings."""
    from .challenges import aggregate_outcome
    outs = [_outcome(r) for r in seed_results]
    if not outs:
        return False, "no_results"
    n_err = sum(o == "ERROR" for o in outs)
    if n_err:
        return False, f"error: {n_err} of {len(outs)} seeds could not run"
    agg = aggregate_outcome(outs)
    n_pass, n_fail = sum(o == "PASS" for o in outs), sum(o == "FAIL" for o in outs)
    if agg != "FAIL":
        return False, f"not_failing: aggregate {agg} ({n_fail} FAIL, {n_pass} PASS of {len(outs)})"
    if n_pass > 1:
        return False, f"not_failing: {n_pass} seeds walk (max 1)"
    return True, f"failing: {n_fail} FAIL, {n_pass} PASS of {len(outs)}"


def _per_seed(seeds, results) -> list[dict]:
    out = []
    for s, r in zip(seeds, results):
        m = r.get("metrics") or {}
        out.append({"seed": int(s), "outcome": r["outcome"], "score": r.get("score"), "fall_time": m.get("fall_time"),
                    "label": m.get("label")})
    return out


# --------------------------------------------------------------------------------------------------------- panel
def generate_panel(campaign: str, n: int, *, allowed_regions=None, min_dist: float = 0.15, max_per_region=None,
                   max_draws: int = 2000, selection_k: int = 8, pool=None, job_fn: Callable | None = None) -> dict:
    """Draw bodies in a fixed order until `n` genuinely failing ones are accepted or `max_draws` draws were used.

    Draw stream: np.random.default_rng(np.random.SeedSequence([int.from_bytes(sha256(f"{campaign}:gen").digest()[:8],
    "big")])), one `sample_body` call per draw (the stream advances for rejected draws too). For each draw: reject if
    its region is not allowed, the region already holds `max_per_region` accepted creatures (default
    ceil(n / max(1, len(allowed_regions or REGIONS))) + 1), or it is closer than `min_dist` to an accepted creature;
    otherwise run the 10 s walk challenge on seeds `walkrec_seed_block(campaign, "selection", f"draw{i}", selection_k)`
    with the R2-transfer controller (controllers None) and apply `is_failing`. Every draw is in `accepted` or
    `rejected`; rejected draws that were simulated keep their per-seed results."""
    from . import challenges
    from .forge_pool import InlinePool, is_error
    if not isinstance(campaign, str) or not campaign:
        raise ValueError("campaign must be a non-empty string")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive integer")
    allowed = sorted(allowed_regions) if allowed_regions is not None else None
    if allowed is not None:
        bad = [r for r in allowed if r not in REGIONS]
        if bad:
            raise ValueError(f"unknown region(s): {bad}")
    cap = (max_per_region if max_per_region is not None
           else math.ceil(n / max(1, len(allowed or REGIONS))) + 1)
    pool = pool or InlinePool()
    job_fn = job_fn or challenges.seed_job
    rng = np.random.default_rng(np.random.SeedSequence(
        [int.from_bytes(hashlib.sha256(f"{campaign}:gen".encode("utf-8")).digest()[:8], "big")]))
    accepted: list[dict] = []
    rejected: list[dict] = []
    counts: dict[str, int] = {}
    rollouts = 0
    draws = 0
    while len(accepted) < n and draws < max_draws:
        i = draws
        draws += 1
        body = sample_body(rng)
        f = features(body)
        reg = region_of(f)
        rec = {"draw": i, "body": body, "features": f, "region": reg}
        if allowed is not None and reg not in allowed:
            rejected.append({**rec, "reason": "region_not_allowed"})
            continue
        if counts.get(reg, 0) >= cap:
            rejected.append({**rec, "reason": f"region_cap: {reg} already has {counts[reg]} (cap {cap})"})
            continue
        near = next((a for a in accepted if distance(f, a["features"]) < min_dist), None)
        if near is not None:
            rejected.append({**rec, "reason": f"too_close: {distance(f, near['features']):.4f} < {min_dist} to {near['id']}"})
            continue
        seeds = walkrec_seed_block(campaign, "selection", f"draw{i}", selection_k)
        spec = challenges.default_spec("walk", seeds).to_dict()
        ctrl = {"stand": None, "walk": None}
        jobs = [{"body": body, "controllers": ctrl, "spec": spec, "seed": int(s)} for s in seeds]
        results: list = [None] * len(jobs)
        for j, out in pool.imap(job_fn, jobs):
            if is_error(out):
                results[j] = {"seed": int(seeds[j]), "outcome": "ERROR", "score": 0.0, "metrics": {"error": out[1]},
                              "rollouts": 0, "error": out[1]}
            else:
                results[j] = out
        for j, r in enumerate(results):
            if r is None:
                results[j] = {"seed": int(seeds[j]), "outcome": "ERROR", "score": 0.0, "metrics": {},
                              "rollouts": 0, "error": "no result returned"}
        rollouts += sum(int(r.get("rollouts") or 0) for r in results)
        sel = {"seeds": [int(s) for s in seeds], "per_seed": _per_seed(seeds, results)}
        ok, why = is_failing(results)
        sel["rule"] = why
        if ok:
            counts[reg] = counts.get(reg, 0) + 1
            accepted.append({**rec, "id": f"{campaign}-{len(accepted):04d}", "selection": sel})
        else:
            rejected.append({**rec, "reason": why, "selection": sel})
    return {"version": VERSION, "campaign": campaign, "gen_dist": GEN_DIST,
            "regions_allowed": list(allowed) if allowed is not None else list(REGIONS),
            "min_dist": min_dist, "max_per_region": cap, "selection_k": selection_k, "n_requested": n,
            "accepted": accepted, "rejected": rejected, "draws": draws, "rollouts": rollouts}


# --------------------------------------------------------------------------------------------------------- named bodies
def _legs(thigh, shank, foot, thigh_r=None, shank_r=None, foot_r=None) -> dict:
    return {"thigh_length": thigh, "shank_length": shank, "foot_length": foot,
            "thigh_length_r": thigh if thigh_r is None else thigh_r,
            "shank_length_r": shank if shank_r is None else shank_r,
            "foot_length_r": foot if foot_r is None else foot_r}


# Canonical sources: tests/fixtures/forge_zoo.json (generated by scripts/forge_zoo_pilot.py from the Studio starters)
# for tiny-feet / top-heavy / weak-slippery, and the live3 demo record's evidence.creature.body for stilts-drawn.
# Values are copied verbatim (including the fixtures' small asymmetries and non-zero poses) except where noted.
NAMED_NOTES = {
    "stilts-drawn": "Copied from experiments/forge_loop/demo_capture/live3-walk-stilts/i-2ed39b130df0.json "
                    "(evidence.creature.body, as given in the task; the record was not present in this worktree, "
                    "so the values are embedded). No change; symmetric legs 0.55+0.55 m, zero pose.",
    "tiny-feet": "Fixture foot_length 0.030501 (left) / 0.030949 (right) is below the guided bound 0.06; both set to "
                 "0.06 (nearest valid). All other values verbatim from the zoo fixture.",
    "top-heavy": "Fixture torso_mass 38.984 kg exceeds the guided bound 15; set to 15.0 (nearest valid). All other values "
                 "verbatim from the zoo fixture (foot 0.0805/0.080826 is valid).",
    "weak-slippery": "Valid as in the zoo fixture (friction 0.05 and torque 5.0 are on the guided bounds); no change.",
}

_FIX = {"foot_friction": 1.0, "torque_limit": 60.0, "leg_density": 1000.0}


def dev_named_bodies() -> dict[str, dict]:
    """Development creatures (guided-valid). Returns fresh dicts each call."""
    base = {"stilts-drawn": {"torso_mass": 4.7917, **_legs(0.55, 0.55, 0.07), **_FIX, "pose": [0.0] * 7},
            "tiny-feet": {"torso_mass": 5.0071, **_legs(0.301626, 0.301626, 0.06, 0.299876, 0.299876, 0.06), **_FIX,
                          "pose": [0.015281, -0.017767, 0.0, -0.00571, -0.018198, -0.0, -0.110416]},
            "top-heavy": {"torso_mass": 15.0, **_legs(0.301626, 0.301626, 0.0805, 0.299876, 0.299876, 0.080826), **_FIX,
                          "pose": [0.0077, -0.010186, 0.0, -0.000619, -0.010618, 0.0, -0.040399]},
            "weak-slippery": {"torso_mass": 5.0071, **_legs(0.300751, 0.300751, 0.160788), **_FIX,
                              "foot_friction": 0.05, "torque_limit": 5.0, "pose": [0.0] * 7}}
    return {k: {**v, "pose": list(v["pose"])} for k, v in base.items()}
