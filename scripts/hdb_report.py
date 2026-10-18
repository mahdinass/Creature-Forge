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
    L += ["", "Paired contrasts on FULL (exact one-sided McNemar; development only, not a registered test):", ""]
    for a, b in (("K1", "K3"), ("K1", "K0"), ("K1", "K0n"), ("K2", "K1"), ("K4", "K0"), ("K4", "K3")):
        pairs = [(v[a]["status"] == "FULL_RECOVERY", v[b]["status"] == "FULL_RECOVERY") for v in by.values() if a in v and b in v]
        w = sum(x and not y for x, y in pairs)
        l = sum(y and not x for x, y in pairs)
        L.append(f"- {a} vs {b}: n {len(pairs)}, {a} only {w}, {b} only {l}, p = {exact_mcnemar_one_sided(w, l):.3f}")
    return "\n".join(L) + "\n"


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
    return "
".join(L) + "
"


if __name__ == "__main__":
    kind, paths = sys.argv[1], sys.argv[2:]
    print({"vs": vs, "mkv": mkv, "arms": arms}[kind](paths))
