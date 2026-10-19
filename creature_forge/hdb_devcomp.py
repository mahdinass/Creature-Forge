"""Development composition instances (phase 3, Stage 2): two DEV mechanisms at a fraction of their own failure thresholds,
which fail only jointly. They exercise a capability the engine's generic single-primitive library lacks by construction
(two-cause explanations), on experience bases only.

The sealed held-out compositions (hdb_heldout) are excluded programmatically. The sealed list is read only to exclude its
pairs; it is never printed or used otherwise. This module is a bench builder: agent-facing code never imports it.
Development evidence only. The registered held-out compositions stay sealed.
"""
from __future__ import annotations

import hashlib
import itertools

from . import hdb_bench as hb
from . import hidden_plant as hp

FRACTION = 0.8
N_PAIRS = 8
SEED = 20261019


def candidate_pairs() -> list[tuple]:
    """(famA, varA, famB, varB) over dev families of DIFFERENT twin pairs (first variant of each), minus the sealed pairs."""
    from . import hdb_heldout          # exclusion only (bench builder)
    sealed = {frozenset([(a, va), (b, vb)]) for a, va, b, vb in hdb_heldout.COMPOSITIONS}
    fams = [(f, next(iter(s["variants"])), s["pair"]) for f, s in hb.FAMILY_SPECS.items()]
    out = []
    for (a, va, pa), (b, vb, pb) in itertools.combinations(fams, 2):
        if pa == pb or frozenset([(a, va), (b, vb)]) in sealed:
            continue
        out.append((a, va, b, vb))
    out.sort(key=lambda t: hashlib.sha256(f"{SEED}:{t}".encode()).hexdigest())
    return out[:N_PAIRS]


def family_key(pair: tuple) -> str:
    a, va, b, vb = pair
    return f"devcomp:{a}{('.' + va) if va else ''}+{b}{('.' + vb) if vb else ''}"


def make_instance(base: dict, pair: tuple, thresholds: dict, *, gap: bool = True) -> dict | None:
    a, va, b, vb = pair
    devs = []
    for fam, var in ((a, va), (b, vb)):
        th = thresholds.get(f"{base['base_id']}|{fam}|{var}")
        if not th or th.get("s_star") is None:
            return None
        devs += hb.FAMILY_SPECS[fam]["variants"][var]["make"](FRACTION * th["s_star"], base)
    fam = family_key(pair)
    key = hb.instance_key(base["base_id"], fam, 0)
    seeds = hb.instance_seeds(base["base_id"], fam, 0)
    hb.assert_disjoint(seeds)
    plant = {"deviation": devs, "gap": hb.reality_gap(key) if gap else []}
    return {"version": "hdb_v2_devcomp", "instance_id": key, "base_id": base["base_id"], "family": fam, "pair": "DC",
            "split": "dev", "severity": 0, "variant": "", "strength": FRACTION, "mult": FRACTION, "s_star": None,
            "plant": hp.normalize_plant(plant), "robot": {"body": dict(base["body"]), "vector": [float(x) for x in base["vector"]]},
            "seeds": seeds}
