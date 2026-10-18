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


