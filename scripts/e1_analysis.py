"""E-1 registered analysis (docs/E1_PROTOCOL.md §6). Stdlib only, deterministic. Run once on the complete arm files.

Primary H-E1: FULL(A1) > FULL(A0), exact one-sided McNemar (binomial on discordant pairs), alpha 0.05.
Secondary (Holm over 2, alpha 0.05): H-E2 FULL(A1) > FULL(K0n); H-E3 FULL(K0n) > FULL(A0).
Sensitivity: base-clustered sign-flip permutation test of the mean per-base FULL difference (seeded, 200,000 flips).
ITT: every registered instance counts; a missing or errored episode counts as not FULL for that arm (and is listed).
Descriptive: per stratum, held-out vs dev-family, severity multiple; plant / twin rollouts; validation walking fraction.

Usage: python scripts/e1_analysis.py --instances <instances.jsonl> --arm A0=<a0.jsonl> --arm A1=<a1.jsonl> --arm K0n=<k.jsonl>
       --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
from collections import defaultdict

FULL = "FULL_RECOVERY"
PERM_N = 200_000
PERM_SEED = 2026102402


def binom_tail_ge(k: int, n: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 1/2), exact."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def mcnemar_one_sided(a: list[bool], b: list[bool]) -> dict:
    """H1: arm a better than arm b. Paired lists of FULL indicators."""
    a_only = sum(1 for x, y in zip(a, b) if x and not y)
    b_only = sum(1 for x, y in zip(a, b) if y and not x)
    return {"a_only": a_only, "b_only": b_only, "discordant": a_only + b_only, "p_one_sided": binom_tail_ge(a_only, a_only + b_only)}


def holm(ps: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    order = sorted(ps, key=lambda k: ps[k])
    out, stop = {}, False
    for i, k in enumerate(order):
        if not stop and ps[k] <= alpha / (len(order) - i):
            out[k] = True
        else:
            stop = True
            out[k] = False
    return out


def cluster_signflip(diffs_by_base: dict[str, list[int]], n: int = PERM_N, seed: int = PERM_SEED) -> dict:
    """One-sided p for mean over instances of d (d = a - b in {-1, 0, 1}), flipping the sign of each base's block jointly."""
    blocks = [sum(v) for v in diffs_by_base.values()]
    m = sum(len(v) for v in diffs_by_base.values())
    obs = sum(blocks) / m if m else 0.0
    rng = random.Random(seed)
    ge = 0
    for _ in range(n):
        s = sum(b if rng.random() < 0.5 else -b for b in blocks)
        if s / m >= obs - 1e-12:
            ge += 1
    return {"mean_diff": obs, "p_one_sided": (ge + 1) / (n + 1), "n_bases": len(blocks), "n_instances": m, "flips": n}


def load(path: str) -> dict[str, dict]:
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                if r["instance_id"] in out:
                    raise SystemExit(f"duplicate {r['instance_id']} in {path}")
                out[r["instance_id"]] = r
    return out


def full(rec: dict | None) -> bool:
    return bool(rec) and (rec.get("verification") or {}).get("status") == FULL


def analyse(instances: list[dict], arms: dict[str, dict[str, dict]]) -> dict:
    ids = [i["instance_id"] for i in instances]
    meta = {i["instance_id"]: i for i in instances}
    missing = {a: sorted(set(ids) - set(recs)) for a, recs in arms.items()}
    extra = {a: sorted(set(recs) - set(ids)) for a, recs in arms.items()}
    F = {a: [full(arms[a].get(i)) for i in ids] for a in arms}
    res = {"n": len(ids), "missing": missing, "extra": extra,
           "full": {a: sum(v) for a, v in F.items()}, "contrasts": {}}
    pairs = {"H-E1": ("A1", "A0"), "H-E2": ("A1", "K0n"), "H-E3": ("K0n", "A0")}
    for h, (x, y) in pairs.items():
        if x in F and y in F:
            c = mcnemar_one_sided(F[x], F[y])
            by_base = defaultdict(list)
            for i, fx, fy in zip(ids, F[x], F[y]):
                by_base[meta[i]["base_id"]].append(int(fx) - int(fy))
            c["cluster_signflip"] = cluster_signflip(dict(sorted(by_base.items())))
            res["contrasts"][h] = {"arms": [x, y], **c}
    if "H-E1" in res["contrasts"]:
        res["primary"] = {"hypothesis": "H-E1", "reject_null": res["contrasts"]["H-E1"]["p_one_sided"] <= 0.05}
    sec = {h: res["contrasts"][h]["p_one_sided"] for h in ("H-E2", "H-E3") if h in res["contrasts"]}
    res["secondary_holm"] = holm(sec) if sec else {}
    strata = defaultdict(lambda: defaultdict(int))
    for k, i in enumerate(ids):
        m = meta[i]
        for key in (f"stratum:{m.get('stratum')}", "heldout" if m.get("heldout") else "dev_family", f"mult:{m.get('mult')}"):
            strata[key]["n"] += 1
            for a in F:
                strata[key][a] += int(F[a][k])
    res["strata"] = {k: dict(v) for k, v in sorted(strata.items())}
    use = {}
    for a, recs in arms.items():
        led = [r.get("ledger") or (r.get("engine") or {}).get("ledger") for r in recs.values()]
        led = [l for l in led if isinstance(l, dict)]
        plant = [l["used"] for l in led]
        twin = [l["twin"]["used"] for l in led if isinstance(l.get("twin"), dict)]
        wf = [r["verification"]["walking_frac"] for r in recs.values() if r.get("verification")]
        use[a] = {"mean_plant_used": sum(plant) / len(plant) if plant else None,
                  "mean_twin_used": sum(twin) / len(twin) if twin else None,
                  "mean_validation_walking_frac": sum(wf) / len(wf) if wf else None}
    res["usage"] = use
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", required=True)
    ap.add_argument("--arm", action="append", required=True, help="NAME=path.jsonl (one file per arm; shards concatenated)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.instances, encoding="utf-8") as fh:
        instances = [json.loads(l) for l in fh if l.strip()]
    arms = {}
    for spec in a.arm:
        name, path = spec.split("=", 1)
        arms[name] = load(path)
    res = analyse(instances, arms)
    res["inputs"] = {"instances_sha256": hashlib.sha256(open(a.instances, "rb").read()).hexdigest(),
                     **{f"{n}_sha256": hashlib.sha256(open(p.split('=', 1)[1], 'rb').read()).hexdigest()
                        for n, p in ((s.split('=', 1)[0], s) for s in a.arm)}}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "e1_results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print(json.dumps({k: res[k] for k in ("n", "full", "primary", "secondary_holm") if k in res}, indent=1))
    for h, c in res["contrasts"].items():
        print(h, c["arms"], f"{c['a_only']} vs {c['b_only']}", f"p={c['p_one_sided']:.4g}",
              f"cluster p={c['cluster_signflip']['p_one_sided']:.4g}")


if __name__ == "__main__":
    main()
