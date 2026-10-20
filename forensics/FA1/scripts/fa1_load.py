"""FA-1 shared loaders (read-only). Every function reads stored JSON records; nothing imports creature_forge runtime code,
runs a simulation or touches the network."""
from __future__ import annotations

import glob
import json
import math
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Creature-Forge"))
EVAL_DIR = os.path.join(REPO, "artifacts", "vm", "ds1", "eval")
DS1_DIR = os.path.join(REPO, "artifacts", "vm", "ds1")
STREAM_DIR = os.path.join(REPO, "artifacts", "vm", "hdb", "artifacts", "hdb", "ds1", "stream")
HDB_DIR = os.path.join(REPO, "artifacts", "vm", "hdb", "artifacts", "hdb")
FULL = "FULL_RECOVERY"
UNM = [["unmodelled", "any"]]

# per-seed evidence of one walking-only check seed (belief_engine.loglik with keys=["walking"], FEATURES sd 0.35, NU 3,
# SEED_OUTLIER 0.1, OUTLIER_FEATURE_LOGP -3): match vs mismatch log-density, recomputed here from the constants.
_NU, _SD, _EPS, _OUT = 3.0, 0.35, 0.1, -3.0


def _lse(a, b):
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))


def seed_ll(mismatch: bool) -> float:
    r = (1.0 / _SD) if mismatch else 0.0
    inl = -0.5 * (_NU + 1.0) * math.log1p(r * r / _NU)
    return _lse(math.log1p(-_EPS) + inl, math.log(_EPS) + _OUT)


PER_SEED_NATS = seed_ll(False) - seed_ll(True)          # raw differential per disagreeing seed


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def load_eval():
    """{arm: [(relpath, line, record)]} for the DS-1 dev-eval-2 records (36 per arm expected)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(EVAL_DIR, "eval_*.jsonl"))):
        for i, r in enumerate(read_jsonl(f)):
            out.setdefault(r["arm"], []).append((os.path.relpath(f, REPO).replace("\\", "/"), i, r))
    return out


def base_of(iid: str) -> str:
    return iid.split(":")[0]


def is_comp(r) -> bool:
    return r["family"].startswith("devcomp")


def st_key(st) -> tuple:
    return tuple(sorted(tuple(x) for x in (st or [])))


def st_str(st) -> str:
    return "+".join(f"{k}:{t}" for k, t in st_key(st)) or "none"


def shares_primitive(a, b) -> bool:
    return bool(set(st_key(a)) & set(st_key(b)))


def shares_kind(a, b) -> bool:
    return bool({k for k, _ in st_key(a)} & {k for k, _ in st_key(b)})


def verification_flags(v: dict) -> dict:
    rs = " | ".join(v.get("reasons") or [])
    m = re.search(r"walking on (\d+) of (\d+)", rs)
    return {"status": v["status"], "full": v["status"] == FULL, "walking_frac": v.get("walking_frac"),
            "fail_walk_robustness": "aggregate is" in rs,
            "fail_displacement": "verdict_v1 is" in rs,
            "verdict": (re.search(r"verdict_v1 is (\w+)", rs) or [None, None])[1],
            "fail_confirmation": "confirmation" in rs,
            "fail_error": "errored" in rs or v["status"] == "INCONCLUSIVE_ERROR",
            "val_walking_seeds": int(m.group(1)) if m else (round(v["walking_frac"] * 24) if v.get("walking_frac") is not None else None),
            "reasons": rs}


def fail_category(fl: dict) -> str:
    """Mutually exclusive FA-1 category (finer than ds1_report.category, which folds 'walk fail + verdict fail' into one)."""
    if fl["full"]:
        return "FULL"
    if fl["fail_error"]:
        return "error/inconclusive"
    if fl["fail_confirmation"]:
        return "long-run confirmation"
    if fl["fail_walk_robustness"] and fl["fail_displacement"]:
        return "walking robustness (+displacement)"
    if fl["fail_walk_robustness"]:
        return "walking robustness only (displacement verified)"
    if fl["fail_displacement"]:
        return "displacement only (walks >=80%)"
    return "other"


def twin_breakdown(ledger: dict) -> dict:
    """Twin rollouts by operation, from the twin ledger tags."""
    out = {}
    for x in ledger["twin"]["lines"]:
        item, tag, n = x["item"], (x["detail"].get("tag") or ""), int(x.get("n") or 0)
        if item == "twin_observe":
            if "|eig:" in tag:
                k = "eig_ranking"
            elif ":check@" in tag:
                k = "assimilation"
            elif "#screen" in tag:
                k = "generic_screen"
            else:
                k = "particle_scoring"
        elif item == "twin_walk":
            k = "tool_probe_screen" if tag.startswith("screen:") else "twin_walk_other"
        elif item == "twin_cma":
            k = ("tool_cma_screen" if tag.startswith("screen_cma:") else "warm_start_cma" if tag.startswith("robust:")
                 else "nemotron_twin_repair" if tag.startswith("agent:") else "twin_cma_other")
        else:
            k = item
        out[k] = out.get(k, 0) + n
    return out


def plant_breakdown(ledger: dict) -> dict:
    out = {}
    for x in ledger["lines"]:
        out[x["item"]] = out.get(x["item"], 0) + int(x.get("n") or 0)
    return out


def repair_of(r):
    return r.get("repair") or ((r["agent"].get("conclusion") or {}).get("repair"))


def design_source(r, idx):
    for d in r["designs"]:
        if d["index"] == idx:
            return d["source"]
    return None


def snapshots(r):
    return r["engine"]["history"]


def pre_repair_snapshot(r):
    """Last posterior snapshot before the first assimilated plant check of a repaired design (= the belief the repair used)."""
    last = None
    for h in snapshots(r):
        if ":check@" in h["label"]:
            break
        last = h
    return last


def mcnemar_one_sided(b: int, c: int) -> float:
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


def mcnemar_two_sided(b: int, c: int) -> float:
    n = b + c
    if not n:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n)


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)
