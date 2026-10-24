"""E-1 descriptive analysis (POST HOC, written after the registered analysis was seen; no inference here changes or
supplements the registered verdicts in e1_results.json). Effect sizes with intervals, diagnosis accuracy, discordant-case
lists, continuous validation-walking outcome, compute use. Stdlib only, deterministic (seeded bootstrap).

Usage: python scripts/e1_descriptive.py <dir containing build/ and arms/> > E1_DESCRIPTIVE.json
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter, defaultdict

FULL = "FULL_RECOVERY"


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def wilson(k, n, z=1.959964):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def newcombe_paired(a, b, z=1.959964):
    """Newcombe (1998) method 10 interval for a paired difference of proportions p_a - p_b."""
    n = len(a)
    e = sum(1 for x, y in zip(a, b) if x and y)
    f = sum(1 for x, y in zip(a, b) if x and not y)
    g = sum(1 for x, y in zip(a, b) if y and not x)
    h = n - e - f - g
    pa, pb = (e + f) / n, (e + g) / n
    l1, u1 = wilson(e + f, n, z)
    l2, u2 = wilson(e + g, n, z)
    d = pa - pb
    denom = (e + f) * (g + h) * (e + g) * (f + h)
    phi = 0.0 if denom == 0 else (e * h - f * g) / math.sqrt(denom)
    dl = math.sqrt((pa - l1) ** 2 - 2 * phi * (pa - l1) * (u2 - pb) + (u2 - pb) ** 2)
    du = math.sqrt((u1 - pa) ** 2 - 2 * phi * (u1 - pa) * (pb - l2) + (pb - l2) ** 2)
    return d, (d - dl, d + du)


def cluster_boot(ids, base_of, a, b, n=20000, seed=2026102403):
    by = defaultdict(list)
    for i, x, y in zip(ids, a, b):
        by[base_of[i]].append(int(x) - int(y))
    blocks = list(by.values())
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        s, m = 0, 0
        for _ in range(len(blocks)):
            blk = blocks[rng.randrange(len(blocks))]
            s += sum(blk)
            m += len(blk)
        stats.append(s / m)
    stats.sort()
    return (stats[int(0.025 * n)], stats[int(0.975 * n) - 1])


def clopper_pearson(k, n, alpha=0.05):
    def betainv(p, a, b):  # bisection on the regularised incomplete beta via continued fraction-free summation
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if binom_cdf_ge(a, a + b - 1, mid) < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def binom_cdf_ge(k_, n_, p_):
        return sum(math.comb(n_, i) * p_ ** i * (1 - p_) ** (n_ - i) for i in range(k_, n_ + 1))
    lo = 0.0 if k == 0 else betainv(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else betainv(1 - alpha / 2, k + 1, n - k)
    return lo, hi


def main():
    d = sys.argv[1]
    insts = load(f"{d}/build/instances.jsonl")
    meta = {i["instance_id"]: i for i in insts}
    ids = [i["instance_id"] for i in insts]
    arms = {a: {r["instance_id"]: r for r in load(f"{d}/arms/{a}.jsonl")} for a in ("A0", "A1", "K0n")}
    F = {a: [arms[a][i]["verification"]["status"] == FULL for i in ids] for a in arms}
    W = {a: [arms[a][i]["verification"]["walking_frac"] for i in ids] for a in arms}
    base_of = {i: meta[i]["base_id"] for i in ids}
    out = {"note": "POST HOC DESCRIPTIVE; registered verdicts are in analysis/e1_results.json", "n": len(ids)}
    out["full_rates"] = {a: {"k": sum(v), "rate": sum(v) / len(v), "wilson95": wilson(sum(v), len(v))} for a, v in F.items()}
    eff = {}
    for x, y in (("A1", "A0"), ("A1", "K0n"), ("K0n", "A0")):
        dd, ci = newcombe_paired(F[x], F[y])
        fo = sum(1 for p, q in zip(F[x], F[y]) if p and not q)
        go = sum(1 for p, q in zip(F[x], F[y]) if q and not p)
        lo, hi = clopper_pearson(fo, fo + go)
        wd = [p - q for p, q in zip(W[x], W[y])]
        eff[f"{x}-{y}"] = {
            "risk_difference": dd, "newcombe95": ci, "cluster_bootstrap95_by_base": cluster_boot(ids, base_of, F[x], F[y]),
            "discordant": [fo, go], "conditional_odds_ratio": fo / go if go else None,
            "conditional_or_95": [lo / (1 - lo) if lo < 1 else None, hi / (1 - hi) if hi < 1 else None],
            "walking_frac_mean_diff": sum(wd) / len(wd),
            "walking_frac_better_worse_tied": [sum(1 for v in wd if v > 1e-12), sum(1 for v in wd if v < -1e-12),
                                               sum(1 for v in wd if abs(v) <= 1e-12)]}
    out["effects"] = eff
    strata = defaultdict(lambda: {"n": 0, "A0": 0, "A1": 0, "K0n": 0, "A1_only_vs_A0": 0, "A0_only_vs_A1": 0})
    for k, i in enumerate(ids):
        m = meta[i]
        grp = "dev family (unseen base)" if not m["heldout"] else ("sealed composition" if m["family"].startswith("heldcomp") else "sealed single")
        for key in (grp, m["stratum"]):
            s = strata[key]
            s["n"] += 1
            for a in F:
                s[a] += int(F[a][k])
            s["A1_only_vs_A0"] += int(F["A1"][k] and not F["A0"][k])
            s["A0_only_vs_A1"] += int(F["A0"][k] and not F["A1"][k])
    out["strata"] = dict(strata)
    diag = defaultdict(lambda: {"n": 0, "map_correct": 0, "full_if_correct": 0, "full_if_wrong": 0, "n_correct": 0})
    for i in ids:
        r = arms["A1"][i]
        inj = sorted(tuple(x) for x in r.get("injected_structure") or [])
        mp = sorted(tuple(x) for x in r.get("map_structure") or [])
        ok = inj == mp
        key = "sealed" if meta[i]["heldout"] else "dev family"
        g = diag[key]
        g["n"] += 1
        g["map_correct"] += int(ok)
        if ok:
            g["full_if_correct"] += int(r["verification"]["status"] == FULL)
        else:
            g["full_if_wrong"] += int(r["verification"]["status"] == FULL)
    out["a1_diagnosis"] = dict(diag)
    out["discordant_A0_only_vs_A1"] = [{"instance_id": i, "stratum": meta[i]["stratum"], "mult": meta[i]["mult"],
                                        "A1_status": arms["A1"][i]["verification"]["status"],
                                        "A1_map": arms["A1"][i].get("map_structure")}
                                       for k, i in enumerate(ids) if F["A0"][k] and not F["A1"][k]]
    out["status_counts"] = {a: Counter(arms[a][i]["verification"]["status"] for i in ids) for a in arms}
    out["none_recovered"] = sum(1 for k in range(len(ids)) if not any(F[a][k] for a in F))
    out["all_recovered"] = sum(1 for k in range(len(ids)) if all(F[a][k] for a in F))
    out["union_full"] = sum(1 for k in range(len(ids)) if any(F[a][k] for a in F))
    wall = {a: sum(r["wall_s"] for r in arms[a].values()) / len(arms[a]) for a in arms}
    out["mean_wall_s"] = wall
    json.dump(out, sys.stdout, indent=1, default=list)


if __name__ == "__main__":
    main()
