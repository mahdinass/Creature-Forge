"""Summaries of phase-3 development runs (vertical slice episodes and the MKV study). Development evidence only: no claim.

Usage: python scripts/hdb_report.py vs  <vs_*.jsonl ...>
       python scripts/hdb_report.py mkv <mkv_*.jsonl ...>
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict


def _rows(paths):
    return [json.loads(l) for p in paths for l in open(p, encoding="utf-8") if l.strip()]


def exact_mcnemar_one_sided(b: int, c: int) -> float:
    """P(X >= b) for X ~ Bin(b + c, 1/2): b = pairs where the first condition wins."""
    n = b + c
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n


def vs(paths) -> str:
    rows = _rows(paths)
    el = [r for r in rows if r.get("eligible", True) and "verification" in r]
    L = ["# Vertical slice (dev): engine-only episodes on the Hidden-Damage Bench", "",
         f"Instances: {len(rows)}; eligible and run: {len(el)}; not eligible: {len(rows) - len(el)} "
         f"({', '.join(r['instance_id'] for r in rows if r not in el)}).", "",
         "| family | n | MAP = injected structure | mean posterior on injected | FULL | PARTIAL | NOT | plant used | twin used |",
         "|---|---|---|---|---|---|---|---|---|"]
    for fam in sorted({r["family"] for r in el}):
        fr = [r for r in el if r["family"] == fam]
        st = Counter(r["verification"]["status"] for r in fr)
        hit = sum(r["map_structure"] == r["injected_structure"] for r in fr)
        mp = sum(r["posterior_mass_on_injected"] for r in fr) / len(fr)
        pu = sum(r["engine"]["ledger"]["used"] for r in fr) / len(fr)
        tu = sum(r["engine"]["ledger"]["twin"]["used"] for r in fr) / len(fr)
        L.append(f"| {fam} | {len(fr)} | {hit} | {mp:.2f} | {st['FULL_RECOVERY']} | {st['PARTIAL_IMPROVEMENT']} | "
                 f"{st['NOT_RECOVERED']} | {pu:.0f} | {tu:.0f} |")
    st = Counter(r["verification"]["status"] for r in el)
    L += ["", f"Total: MAP correct {sum(r['map_structure'] == r['injected_structure'] for r in el)}/{len(el)}; "
              f"FULL {st['FULL_RECOVERY']}/{len(el)}.", "", "Per episode:", ""]
    for r in el:
        rep = r["repair"]
        L.append(f"- {r['instance_id']}: MAP {r['map_structure']} ({r['map_mass']:.2f}); repair "
                 f"{[(x.get('tool'), x.get('twin_walking'), x.get('check'), x.get('check16')) for x in rep['log']]} -> "
                 f"{r['verification']['status']} ({r['verification']['walking_frac']:.2f})")
    return "\n".join(L) + "\n"


def mkv(paths) -> str:
    rows = [r for r in _rows(paths) if "status" in r]
    by = defaultdict(dict)
    for r in rows:
        by[r["instance_id"]][r["condition"]] = r
    conds = ["K2", "K1", "K3", "K0n", "K4", "K0"]
    L = ["# Mechanism-Knowledge Value study (dev, NO_AI): same pipeline, different mechanism information", "",
         f"Instances: {len(by)}.", "", "| condition | FULL | PARTIAL | NOT | mean walking (validation) |", "|---|---|---|---|---|"]
    for c in conds:
        cr = [v[c] for v in by.values() if c in v]
        if not cr:
            continue
        st = Counter(x["status"] for x in cr)
        L.append(f"| {c} | {st['FULL_RECOVERY']}/{len(cr)} | {st['PARTIAL_IMPROVEMENT']} | {st['NOT_RECOVERED']} | "
                 f"{sum(x['walking_frac'] for x in cr) / len(cr):.2f} |")
    L += ["", "C-MKV analysis (fixed 2026-10-19 by the owner before any sealed evaluation; choosing K2 vs K0n as primary was",
          "motivated by development results). FULL: exact one-sided McNemar. Walking: one-sided Wilcoxon signed-rank on the",
          "paired validation walking fraction. Development data only, not a registered test.", ""]
    for role, (a, b) in MKV_CONTRASTS:
        pairs = [(v[a], v[b]) for v in by.values() if a in v and b in v]
        w = sum(x["status"] == "FULL_RECOVERY" and y["status"] != "FULL_RECOVERY" for x, y in pairs)
        l = sum(y["status"] == "FULL_RECOVERY" and x["status"] != "FULL_RECOVERY" for x, y in pairs)
        wil = wilcoxon_one_sided([x["walking_frac"] - y["walking_frac"] for x, y in pairs])
        L.append(f"- [{role}] {a} vs {b}: n {len(pairs)}; FULL {a} only {w}, {b} only {l}, p = {exact_mcnemar_one_sided(w, l):.3f}; "
                 f"walking mean diff {wil['mean_diff']:+.3f}, Wilcoxon p = {wil['p']:.3f} (n nonzero {wil['n']})")
    return "\n".join(L) + "\n"


# C-MKV registered form (owner decision 2026-10-19):
# - primary: K2 (exact deviation) vs K0n (same pipeline, nominal model only);
# - secondary: K1 vs K3 (correct vs symptom-twin structure) and K2 vs K1 (value of quantitative identification);
# - the paired walking fraction is a secondary engineering outcome of every contrast.
# Oracle mechanism knowledge is never a Nemotron capability.
MKV_CONTRASTS = (("primary", ("K2", "K0n")), ("secondary", ("K1", "K3")), ("secondary", ("K2", "K1")),
                 ("descriptive", ("K4", "K0n")), ("descriptive", ("K4", "K0")))


def wilcoxon_one_sided(diffs) -> dict:
    """One-sided Wilcoxon signed-rank test of median(diff) > 0.
    Zero differences are dropped and ties get average ranks; normal approximation with tie-corrected variance and
    continuity correction."""
    d = [x for x in diffs if abs(x) > 1e-12]
    n = len(d)
    mean = sum(diffs) / len(diffs) if diffs else 0.0
    if n == 0:
        return {"n": 0, "w_plus": 0.0, "p": 1.0, "mean_diff": mean}
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    ties = 0.0
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(abs(d[order[j + 1]]) - abs(d[order[i]])) < 1e-12:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2.0 + 1.0
        ties += (j - i + 1) ** 3 - (j - i + 1)
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    mu = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0 - ties / 48.0
    if var <= 0:
        return {"n": n, "w_plus": w_plus, "p": 1.0 if w_plus <= mu else 0.0, "mean_diff": mean}
    z = (w_plus - mu - 0.5) / math.sqrt(var)
    return {"n": n, "w_plus": w_plus, "p": 0.5 * math.erfc(z / math.sqrt(2.0)), "mean_diff": mean}


def arms(paths) -> str:
    """Per-arm FULL counts and paired contrasts on shared eligible instances (development only)."""
    rows = [r for r in _rows(paths) if "verification" in r]
    by = defaultdict(dict)
    for r in rows:
        by[r["instance_id"]][r.get("arm", "A1")] = r
    names = sorted({a for v in by.values() for a in v})
    L = ["# Arms on the Hidden-Damage Bench (dev; development only, no claim)", "",
         "| arm | n | FULL | PARTIAL | NOT | mean plant used | mean twin used |", "|---|---|---|---|---|---|---|"]
    for a in names:
        ar = [v[a] for v in by.values() if a in v]
        st = Counter(x["verification"]["status"] for x in ar)
        led = [x.get("ledger") or (x.get("engine") or {}).get("ledger") or {} for x in ar]
        pu = sum(l.get("used", 0) for l in led) / max(1, len(led))
        tu = sum((l.get("twin") or {}).get("used", 0) for l in led) / max(1, len(led))
        L.append(f"| {a} | {len(ar)} | {st['FULL_RECOVERY']} | {st['PARTIAL_IMPROVEMENT']} | {st['NOT_RECOVERED']} | {pu:.0f} | {tu:.0f} |")
    L += ["", "Paired contrasts on FULL (exact one-sided McNemar, first arm better; development only):", ""]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pairs = [(v[a]["verification"]["status"] == "FULL_RECOVERY", v[b]["verification"]["status"] == "FULL_RECOVERY")
                     for v in by.values() if a in v and b in v]
            w = sum(x and not y for x, y in pairs)
            l = sum(y and not x for x, y in pairs)
            L.append(f"- {a} vs {b}: n {len(pairs)}, {a} only {w}, {b} only {l}, p({a}>{b}) = {exact_mcnemar_one_sided(w, l):.3f}, "
                     f"p({b}>{a}) = {exact_mcnemar_one_sided(l, w):.3f}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    kind, paths = sys.argv[1], sys.argv[2:]
    print({"vs": vs, "mkv": mkv, "arms": arms}[kind](paths))
