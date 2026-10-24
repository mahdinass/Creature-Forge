"""E-2 bench builder (docs/RL1_PLAN.md §6-7): the fresh hdb-v2 walker cohort x (dev families + sealed HF2 families). Bench
builder only; never imported by agent-facing code (guarded by tests/test_rl1.py).

It applies the frozen HDB v2 rules exactly as hdb_testbench does for E-1 (that module stays frozen under the E-1
registration):
- threshold bisection on the gap-free plant, BISECT_STEPS steps, the variant's own check seeds;
- singles at MULTS x s* within the variant's maximum;
- the per-instance reality gap and campaign-hdb-v1 seed roles;
- eligibility via hdb_bench.check_eligibility.

The family specs are the union of the dev specs and HF2. The physics-only sampler is hdb_testbench.Sampler (strict round
robin, per-base caps; tested), reused unchanged.
"""
from __future__ import annotations

import hashlib
import json

from . import hdb_bench as hb
from . import hdb_heldout2 as h2
from . import hidden_plant as hp
from .hdb_testbench import Sampler, cand_id  # noqa: F401  (re-exported for the builder)

VERSION = "hdb_v2_cohort2_e2"
SPECS: dict[str, dict] = {**hb.FAMILY_SPECS, **h2.HF2_FAMILY_SPECS}
if len(SPECS) != len(hb.FAMILY_SPECS) + len(h2.HF2_FAMILY_SPECS):
    raise RuntimeError("dev and HF2 family names overlap")


def load_cohort(walkers_path: str) -> list[dict]:
    """Bases of the fresh cohort: FULL_RECOVERY walkers of the given hdb-v2 walker file, test-side regions only."""
    out = []
    for line in open(walkers_path, encoding="utf-8"):
        r = json.loads(line)
        if r.get("status") == "FULL_RECOVERY" and r.get("hdb_split") == "test":
            fin = r["pipeline"]["final"]
            out.append({"base_id": r["creature"], "creature": r["creature"], "body": dict(fin["body"]),
                        "vector": [float(x) for x in fin["vector"]], "features": r.get("features"),
                        "region": r.get("region"), "source": "hdb-v2-walkers"})
    return sorted(out, key=lambda b: b["base_id"])


def variant_max(base: dict, family: str, variant: str) -> float:
    if family in hb.FAMILY_SPECS:
        return hb.variant_max(base, family, variant)
    return SPECS[family]["variants"][variant]["max"]


def threshold(base: dict, family: str, variant: str, pool=None) -> dict:
    smax = variant_max(base, family, variant)
    seeds = hb.instance_seeds(base["base_id"], f"{family}{variant}", -1)["check"]
    make = SPECS[family]["variants"][variant]["make"]

    def walking(s):
        rows = hp.walk_seeds({"deviation": make(s, base)}, base["body"], base["vector"], seeds, pool=pool)
        return int(sum(1 for r in rows if r.get("ok") and r["walking"]))
    trace = [(smax, walking(smax))]
    if trace[0][1] > hb.FAIL_MAX_WALKING:
        return {"base_id": base["base_id"], "family": family, "variant": variant, "s_star": None, "s_max": smax,
                "trace": trace, "reason": "the nominal design still walks at the strongest allowed fault",
                "rollouts": hb.CHECK_N * len(trace)}
    lo, hi = 0.0, smax
    for _ in range(hb.BISECT_STEPS):
        mid = 0.5 * (lo + hi)
        w = walking(mid)
        trace.append((mid, w))
        if w <= hb.FAIL_MAX_WALKING:
            hi = mid
        else:
            lo = mid
    return {"base_id": base["base_id"], "family": family, "variant": variant, "s_star": hi, "s_max": smax, "trace": trace,
            "rollouts": hb.CHECK_N * len(trace)}


def th_key(base_id: str, family: str, variant: str) -> str:
    return f"{base_id}|{family}|{variant}"


def severities(family: str) -> list[tuple[str, float]]:
    return [(v, m) for v in SPECS[family]["variants"] for m in hb.MULTS]


def candidates(family: str, bases: list[dict], seed: int) -> list[dict]:
    out = [{"stratum": family, "base_id": b["base_id"], "family": family, "severity": sev, "variant": v, "mult": m}
           for b in bases for sev, (v, m) in enumerate(severities(family))]
    return sorted(out, key=lambda c: hashlib.sha256(f"{seed}:{c['stratum']}:{c['base_id']}:{c['severity']}".encode()).hexdigest())


def make_instance(base: dict, cand: dict, thresholds: dict, *, gap: bool = True) -> dict | None:
    th = thresholds.get(th_key(base["base_id"], cand["family"], cand["variant"]))
    if not th or th.get("s_star") is None:
        return None
    s = cand["mult"] * th["s_star"]
    if s > th["s_max"] + 1e-12:
        return None
    fam = cand["family"]
    key = hb.instance_key(base["base_id"], fam, cand["severity"])
    seeds = hb.instance_seeds(base["base_id"], fam, cand["severity"])
    hb.assert_disjoint(seeds)
    plant = {"deviation": SPECS[fam]["variants"][cand["variant"]]["make"](s, base), "gap": hb.reality_gap(key) if gap else []}
    return {"version": VERSION, "instance_id": key, "base_id": base["base_id"], "family": fam, "stratum": fam,
            "pair": SPECS[fam]["pair"], "split": "e2", "heldout": fam in h2.HF2_FAMILY_SPECS, "severity": int(cand["severity"]),
            "variant": cand["variant"], "strength": s, "mult": cand["mult"], "s_star": th["s_star"],
            "plant": hp.normalize_plant(plant), "robot": {"body": dict(base["body"]), "vector": [float(x) for x in base["vector"]]},
            "seeds": seeds}


def needed_thresholds(cand: dict) -> list[tuple[str, str]]:
    return [(cand["family"], cand["variant"])]
