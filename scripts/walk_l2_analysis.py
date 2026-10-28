"""L2 experience-pilot analysis (pre-declared in protocol_l2.json "analysis"; descriptive; run once after evaluation completed).

    python scripts/walk_l2_analysis.py <eval*.jsonl ...> [--out summary.json]

Per variant x N: test creatures (of 12) FULL_RECOVERY after the 1000-rollout search ("final") and the zero-budget warm-start
assessment ("warm": the decision alone); mean validation walking fractions; applicability vs outcome; G3 rule:
PASS iff learned@40 final FULL > knn@40, > mean_best@40 and > r2, AND learned@40 > learned@10.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    recs = [json.loads(l) for p in a.files for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"{len(recs)} evaluation units over {len({r['creature'] for r in recs})} test creatures")
    cells = defaultdict(list)
    for r in recs:
        cells[(r["variant"], int(r.get("n_train", 0) or 0))].append(r)
    full = {}
    print("\n| variant | N | final FULL | final PARTIAL | warm FULL | warm walking (mean) | final walking (mean) | fallback |")
    print("|---|---|---|---|---|---|---|---|")
    for k in sorted(cells, key=lambda k: (k[0], k[1])):
        rs = cells[k]
        fs = [r["final"]["status"] for r in rs]
        ws = [r["warm_assessment"]["status"] for r in rs]
        fw = sum(r["final"]["walking_frac"] for r in rs) / len(rs)
        ww = sum(r["warm_assessment"]["walking_frac"] for r in rs) / len(rs)
        fb = sum(bool(r.get("decision", {}).get("fallback_to_r2")) for r in rs)
        full[k] = fs.count("FULL_RECOVERY")
        print(f"| {k[0]} | {k[1]} | {full[k]}/{len(rs)} | {fs.count('PARTIAL_IMPROVEMENT')} | {ws.count('FULL_RECOVERY')} | {ww:.2f} | {fw:.2f} | {fb} |")
    nmax = max(n for (v, n) in full if v == "learned")
    nmin = min(n for (v, n) in full if v == "learned")
    L = full.get(("learned", nmax), 0)
    cond = {f"learned@{nmax} > knn@{nmax}": L > full.get(("knn", nmax), 0),
            f"learned@{nmax} > mean_best@{nmax}": L > full.get(("mean_best", nmax), 0),
            "learned > r2": L > full.get(("r2", 0), 0),
            f"learned@{nmax} > learned@{nmin}": L > full.get(("learned", nmin), 0)}
    g3 = all(cond.values())
    print("\nG3 conditions: " + "; ".join(f"{k}: {v}" for k, v in cond.items()))
    print(f"G3 = {'PASS' if g3 else 'FAIL'}")
    # applicability vs outcome (learned variant)
    rows = [(r["decision"].get("applicability"), r["final"]["status"]) for r in recs if r["variant"] == "learned" and r.get("decision")]
    rows = [(x, s) for x, s in rows if isinstance(x, (int, float))]
    if rows:
        rows.sort()
        lo = rows[: len(rows) // 2]
        hi = rows[len(rows) // 2:]
        f = lambda rs: sum(s == "FULL_RECOVERY" for _, s in rs)
        print(f"applicability (lower = more confident): lower half FULL {f(lo)}/{len(lo)}, upper half FULL {f(hi)}/{len(hi)}")
    if a.out:
        Path(a.out).write_text(json.dumps({"full": {f"{v}@{n}": c for (v, n), c in full.items()}, "g3": g3, "conditions": cond},
                                          indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
