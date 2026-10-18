"""Hidden-Damage Bench (HDB, phase 3): failing robots whose cause is a hidden physical deviation of a healthy nominal design.

An instance = a verified-walking BASE design (body + 17-D vector, what the engineer designed and sees) + a hidden PLANT
(`hidden_plant`: deviation from a mechanism family at one severity, plus a per-instance reality gap). Policies see only
`policy_view`: the nominal design and the policy-visible seeds (train / obs / robust / twin).

Population and eligibility are physics-only and fixed before any comparative run (docs/HAS_SCIENTIST.md):
  * families come from an engineering failure taxonomy, organised as symptom-twins that need different interventions;
  * severities are a fixed grid per family (`FAMILIES[...]["grid"]`), not tuned on any policy;
  * eligible = the plant fails: walking on <= FAIL_MAX_WALKING of CHECK_N check seeds, no ERROR. Nothing else.
Oracle repairability (R/U) and identifiability (ambiguity) are LABELS computed later, never filters.

Held-out families (sensor latency, joint damping wear, leg asymmetry, novel compositions) live in a sealed module that
agent-facing code never imports; this module defines the dev families only.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from . import creature_gen as cg
from . import hidden_plant as hp

VERSION = "hdb_v1"
CAMPAIGN = "hdb-v1"
CHECK_N = 8
FAIL_MAX_WALKING = 2
# role -> walkrec seed namespace. "robust" and "twin" are policy-visible extra namespaces (robustness check; twin-only seeds).
SEED_ROLES = {"check": "screen", "train": "train", "obs": "probe", "robust": "selection", "twin": "gen",
              "validate": "validate", "confirm": "confirm"}
SEED_COUNTS = {"check": CHECK_N, "train": 8, "obs": 8, "robust": 16, "twin": 16, "validate": 24, "confirm": 24}
POLICY_ROLES = ("train", "obs", "robust", "twin")


def prim(kind: str, target: str, **params) -> dict:
    return hp.validate_primitive({"kind": kind, "target": target, "params": params})


def _payload(frac: float, x: float):
    """Payload as a fraction of the design's total mass (resolved per base in `deviation_for`)."""
    return {"payload_frac": frac, "x_m": x}


# Dev families. grid entries are deviations (lists of primitives) or payload placeholders resolved per base.
FAMILIES: dict[str, dict] = {
    # T2 lean: a mis-calibrated pitch sensor vs a mass offset on the torso. Fixes differ (sensor offset compensation in the
    # posture reference vs redistributing support / posture for the true COM); the sign matters in both.
    "pitch_sensor_bias": {"pair": "T2", "split": "dev", "taxonomy": "sensing",
                          "grid": [[prim("sensor_bias", "pitch", rad=r)] for r in (0.06, 0.1, 0.15, 0.22, -0.06, -0.1, -0.15, -0.22)]},
    "payload_offset": {"pair": "T2", "split": "dev", "taxonomy": "mass properties",
                       "grid": [_payload(f, x) for f in (0.2, 0.35, 0.5) for x in (0.12, -0.12)]},
    # T4 slip vs support: low foot-floor friction vs feet too short for the gait. Fixes differ (grip or gentler gait vs a longer
    # support polygon).
    "low_ground_friction": {"pair": "T4", "split": "dev", "taxonomy": "contact / environment",
                            "grid": [[prim("contact_friction", "feet", factor=f)] for f in (0.45, 0.32, 0.23, 0.16, 0.11)]},
    "short_feet": {"pair": "T4", "split": "dev", "taxonomy": "geometry",
                   "grid": [[prim("segment_length", "feet", factor=f)] for f in (0.75, 0.62, 0.52, 0.43)]},
}


# ---------------------------------------------------------------------------------------------------------
# v2 severities: relative to each base's own failure threshold (physics only; no policy or oracle outcome is used)
# ---------------------------------------------------------------------------------------------------------
# A family variant maps a fault STRENGTH s >= 0 (0 = no fault, monotone) to a deviation. The threshold s* of a (base, variant)
# is found by bisection on the GAP-FREE plant: the smallest strength at which the nominal design walks on <= FAIL_MAX_WALKING
# of the CHECK_N check seeds. Instances use s = MULTS x s* (capped at the variant's maximum), so every failure is real and
# severities range from just past the edge to clearly past it. Introduced 2026-10-18 before any frozen population: with the
# v1 fixed grid even the exact-deviation oracle (MKV K2) and A0 almost never recovered, i.e. the population measured nothing.
MULTS = (1.0, 1.3, 1.7)
BISECT_STEPS = 6


def _strength_dev(kind, target, pname, transform):
    return lambda s, base: [prim(kind, target, **{pname: transform(s, base)})]


FAMILY_SPECS: dict[str, dict] = {
    "pitch_sensor_bias": {"pair": "T2", "split": "dev", "taxonomy": "sensing", "variants": {
        "+": {"make": _strength_dev("sensor_bias", "pitch", "rad", lambda s, b: round(s, 6)), "max": 0.4},
        "-": {"make": _strength_dev("sensor_bias", "pitch", "rad", lambda s, b: round(-s, 6)), "max": 0.4}}},
    "payload_offset": {"pair": "T2", "split": "dev", "taxonomy": "mass properties", "variants": {
        "fwd": {"make": lambda s, b: [prim("payload", "torso", mass_kg=round(s * design_mass(b["body"]), 6), x_m=0.12)],
                "max": None},
        "back": {"make": lambda s, b: [prim("payload", "torso", mass_kg=round(s * design_mass(b["body"]), 6), x_m=-0.12)],
                 "max": None}}},
    "low_ground_friction": {"pair": "T4", "split": "dev", "taxonomy": "contact / environment", "variants": {
        "": {"make": _strength_dev("contact_friction", "feet", "factor", lambda s, b: round(math.exp(-s), 6)),
             "max": math.log(1 / 0.02)}}},
    "short_feet": {"pair": "T4", "split": "dev", "taxonomy": "geometry", "variants": {
        "": {"make": _strength_dev("segment_length", "feet", "factor", lambda s, b: round(math.exp(-s), 6)),
             "max": None}}},
}


def variant_max(base: dict, family: str, variant: str) -> float:
    v = FAMILY_SPECS[family]["variants"][variant]
    if v["max"] is not None:
        return v["max"]
    if family == "payload_offset":
        return min(0.75, 15.0 / design_mass(base["body"]))
    if family == "short_feet":       # factor >= 0.3 (DSL) and foot length >= 0.02 m (sandbox)
        return math.log(1 / max(0.3, 0.02 / float(base["body"]["foot_length"]) + 1e-6))
    raise ValueError(family)


def threshold(base: dict, family: str, variant: str, pool=None) -> dict:
    """Bisection for the failure threshold s* on the gap-free plant (check seeds of the variant's own key)."""
    smax = variant_max(base, family, variant)
    seeds = instance_seeds(base["base_id"], f"{family}{variant}", -1)["check"]
    make = FAMILY_SPECS[family]["variants"][variant]["make"]

    def walking(s):
        rows = hp.walk_seeds({"deviation": make(s, base)}, base["body"], base["vector"], seeds, pool=pool)
        return int(sum(1 for r in rows if r.get("ok") and r["walking"]))
    trace = []
    w = walking(smax)
    trace.append((smax, w))
    if w > FAIL_MAX_WALKING:
        return {"base_id": base["base_id"], "family": family, "variant": variant, "s_star": None, "s_max": smax,
                "trace": trace, "reason": "the nominal design still walks at the strongest allowed fault"}
    lo, hi = 0.0, smax
    for _ in range(BISECT_STEPS):
        mid = 0.5 * (lo + hi)
        w = walking(mid)
        trace.append((mid, w))
        if w <= FAIL_MAX_WALKING:
            hi = mid
        else:
            lo = mid
    return {"base_id": base["base_id"], "family": family, "variant": variant, "s_star": hi, "s_max": smax, "trace": trace,
            "rollouts": CHECK_N * len(trace)}


def v2_severities(family: str) -> list[tuple[str, float]]:
    return [(v, m) for v in FAMILY_SPECS[family]["variants"] for m in MULTS]


def make_instance_v2(base: dict, family: str, severity: int, thresholds: dict, *, gap: bool = True) -> dict | None:
    """v2 instance; None when the variant has no threshold or the multiple exceeds the variant's maximum strength."""
    variant, mult = v2_severities(family)[severity]
    th = thresholds.get(f"{base['base_id']}|{family}|{variant}")
    if not th or th.get("s_star") is None:
        return None
    s = mult * th["s_star"]
    if s > th["s_max"] + 1e-12:
        return None
    key = instance_key(base["base_id"], family, severity)
    seeds = instance_seeds(base["base_id"], family, severity)
    assert_disjoint(seeds)
    fam = FAMILY_SPECS[family]
    dev = FAMILY_SPECS[family]["variants"][variant]["make"](s, base)
    plant = {"deviation": dev, "gap": reality_gap(key) if gap else []}
    return {"version": "hdb_v2", "instance_id": key, "base_id": base["base_id"], "family": family, "pair": fam["pair"],
            "split": fam["split"], "severity": int(severity), "variant": variant, "strength": s, "mult": mult,
            "s_star": th["s_star"], "plant": hp.normalize_plant(plant),
            "robot": {"body": dict(base["body"]), "vector": [float(x) for x in base["vector"]]}, "seeds": seeds}


def design_mass(body: dict) -> float:
    from .creature_walk import _body
    from .morphology import build_model
    return float(build_model(_body(body)).body_mass.sum())


def deviation_for(base: dict, family: str, severity: int) -> list[dict]:
    g = FAMILIES[family]["grid"][severity]
    if isinstance(g, dict) and "payload_frac" in g:
        m = g["payload_frac"] * design_mass(base["body"])
        return [prim("payload", "torso", mass_kg=round(min(m, 15.0), 6), x_m=g["x_m"])]
    return hp.validate_deviation(g)


def instance_key(base_id: str, family: str, severity: int) -> str:
    return f"{base_id}:{family}:{int(severity)}"


def instance_seeds(base_id: str, family: str, severity: int, campaign: str = CAMPAIGN) -> dict:
    key = instance_key(base_id, family, severity)
    return {r: list(cg.walkrec_seed_block(campaign, ns, key, SEED_COUNTS[r])) for r, ns in SEED_ROLES.items()}


def assert_disjoint(seeds: dict) -> None:
    roles = list(seeds)
    for i, a in enumerate(roles):
        for b in roles[i + 1:]:
            if set(seeds[a]) & set(seeds[b]):
                raise ValueError(f"seed roles {a} and {b} overlap")


def reality_gap(key: str, campaign: str = CAMPAIGN) -> list[dict]:
    """Per-instance nuisance deviation that no hypothesis models (sealed seed): small mass, actuator, damping and friction
    differences between any real robot and its design."""
    h = int.from_bytes(hashlib.sha256(f"{campaign}:gap:{key}".encode()).digest()[:8], "big")
    rng = np.random.default_rng(h)
    gap = [prim("torso_mass", "torso", factor=float(rng.uniform(0.97, 1.03))),
           prim("joint_damping", "all", factor=float(rng.uniform(0.8, 1.25))),
           prim("contact_friction", "feet", factor=float(rng.uniform(0.95, 1.05)))]
    gap += [prim("actuator_strength", j, factor=float(rng.uniform(0.95, 1.05))) for j in hp.JOINTS]
    return gap


def make_instance(base: dict, family: str, severity: int, *, gap: bool = True) -> dict:
    """The (hidden) instance record, before the eligibility check."""
    key = instance_key(base["base_id"], family, severity)
    seeds = instance_seeds(base["base_id"], family, severity)
    assert_disjoint(seeds)
    fam = FAMILIES[family]
    plant = {"deviation": deviation_for(base, family, severity), "gap": reality_gap(key) if gap else []}
    return {"version": VERSION, "instance_id": key, "base_id": base["base_id"], "family": family, "pair": fam["pair"],
            "split": fam["split"], "severity": int(severity), "plant": hp.normalize_plant(plant),
            "robot": {"body": dict(base["body"]), "vector": [float(x) for x in base["vector"]]}, "seeds": seeds}


def check_eligibility(inst: dict, pool=None) -> dict:
    """Physics-only eligibility: the plant walks on <= FAIL_MAX_WALKING of the check seeds and nothing errors."""
    rows = hp.walk_seeds(inst["plant"], inst["robot"]["body"], inst["robot"]["vector"], inst["seeds"]["check"], pool=pool)
    errors = [r.get("error") for r in rows if not r.get("ok")]
    walking = int(sum(1 for r in rows if r.get("ok") and r["walking"]))
    if errors:
        eligible, reason = False, f"ERROR on {len(errors)} check seed(s): {errors[0]}"
    elif walking > FAIL_MAX_WALKING:
        eligible, reason = False, f"plant still walks on {walking}/{CHECK_N} check seeds (needs <= {FAIL_MAX_WALKING})"
    else:
        eligible, reason = True, None
    return {**inst, "check": {"walking": walking, "n": CHECK_N, "labels": [r.get("label") for r in rows],
                              "rollouts": CHECK_N}, "eligible": eligible, "reason": reason}


def policy_view(inst: dict) -> dict:
    """Everything a policy may see: an opaque id, the NOMINAL design and the policy-visible seeds. Never the plant, family,
    severity, check results, strata labels or verification seeds."""
    oid = hashlib.sha256(("hdb-view:" + inst["instance_id"]).encode()).hexdigest()[:12]
    return {"robot_id": oid, "robot": {"body": dict(inst["robot"]["body"]), "vector": list(inst["robot"]["vector"])},
            "seeds": {r: list(inst["seeds"][r]) for r in POLICY_ROLES}}


def verify(inst: dict, design: dict, pool=None) -> dict:
    """Independent final verification: full_recovery_v1 on the hidden plant, original = the nominal design on the same plant."""
    return hp.verify(inst["plant"], inst["robot"], design, inst["seeds"]["validate"], inst["seeds"]["confirm"], pool=pool)


def mechanism_signature(inst: dict) -> list[tuple]:
    """The injected deviation's structure (kind, target) list: the scoring key for identification."""
    return sorted((p["kind"], p["target"]) for p in inst["plant"]["deviation"])


def severity_count(family: str) -> int:
    return len(FAMILIES[family]["grid"])




WALKERS_GLOB = "artifacts/hdb/walkers_s*.jsonl"


def load_bases(split: str, walkers_glob: str | None = None) -> list[dict]:
    """HDB bases. "dev": the 12 earlier dev walkers (fault_bench dev split) followed by the fresh hdb-v1 walkers whose region is
    on the dev side; "test": fresh walkers on the test side only (never used in development); "olddev": the 12 only.
    Fresh walkers are the FULL_RECOVERY designs of scripts/hdb_walkers.py (other creatures are not bases)."""
    import glob
    import json
    import os
    from . import fault_bench as fb
    if split not in ("dev", "test", "olddev"):
        raise ValueError(f"split must be dev, test or olddev, got {split!r}")
    out = [] if split == "test" else list(fb.load_bases("dev"))
    if split == "olddev":
        return out
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pattern = walkers_glob or os.environ.get("CF_HDB_WALKERS") or os.path.join(root, WALKERS_GLOB)
    fresh = []
    for path in sorted(glob.glob(pattern)):
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            if r.get("status") == "FULL_RECOVERY" and r.get("hdb_split") == split:
                fin = r["pipeline"]["final"]
                fresh.append({"base_id": r["creature"], "creature": r["creature"], "body": dict(fin["body"]),
                              "vector": [float(x) for x in fin["vector"]], "features": r.get("features"),
                              "region": r.get("region"), "source": "hdb-v1-walkers"})
    return out + sorted(fresh, key=lambda b: b["base_id"])
