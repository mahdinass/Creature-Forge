"""S2 dev-pilot analysis (pre-declared in protocol_s2.json "analysis"; descriptive; run once after all shards completed).

    python scripts/walk_s2_analysis.py <shard*.jsonl ...> [--out summary.json]

Reports: per method x budget FULL / PARTIAL / NOT counts (12 creatures), per-creature table, the R* rule, the primary
comparator rule, G2 checks (ledger == sum of lines <= budget for every unit; AI valid-plan rate), AI cost, and H6: the AI's
round-1 probe choices vs the census ranking of probes (full vs no-gait evidence).
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

NON_AI = ("cma_joint", "cma_ctrl", "fix")


def load(paths):
    out = []
    for p in paths:
        out += [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
    return out


def census_ranking(rec) -> list[tuple]:
    """Probes of the census pipeline ranked by (delta_walking, delta_mean_fitness), best first."""
    rows = []
    for rnd in rec["pipeline"]["rounds"]:
        for p in rnd["probes"]:
            if p.get("status") == "ok":
                rows.append((p["probe_id"], p["delta_walking"], p["delta_mean_fitness"]))
    return sorted(rows, key=lambda r: (-r[1], -r[2]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    recs = load(a.files)
    errors = [r for r in recs if r.get("status") == "UNIT_ERROR"]
    print(f"{len(recs)} units; unit errors: {len(errors)}")
    for r in errors:
        print("  UNIT_ERROR", r["unit"], r["error"])
    creatures = list(dict.fromkeys(r["creature"] for r in recs))
    by = defaultdict(dict)
    for r in recs:
        by[(r["method"], r["budget"])][r["creature"]] = r
    # G2: accounting
    acct_bad = []
    for r in recs:
        if r.get("status") == "UNIT_ERROR":
            continue
        p = r["pipeline"]
        if p["used"] != sum(l["n"] for l in p["budget_lines"]) or p["used"] > r["budget"]:
            acct_bad.append(r["unit"])
    print(f"G2 accounting: {len(recs) - len(errors) - len(acct_bad)} units OK, violations {acct_bad}")
    # main counts
    keys = sorted(by, key=lambda k: (k[0], k[1]))
    print("\n| method | budget | FULL | PARTIAL | NOT | other |")
    print("|---|---|---|---|---|---|")
    full = {}
    for k in keys:
        if k[0] == "census":
            continue
        sts = [by[k][c].get("status") for c in creatures if c in by[k]]
        f = sts.count("FULL_RECOVERY")
        full[k] = f
        print(f"| {k[0]} | {k[1]} | {f} | {sts.count('PARTIAL_IMPROVEMENT')} | {sts.count('NOT_RECOVERED')} | "
              f"{len(sts) - f - sts.count('PARTIAL_IMPROVEMENT') - sts.count('NOT_RECOVERED')} |")
    # per creature
    cols = [k for k in keys if k[0] != "census"]
    print("\n| creature | " + " | ".join(f"{m}@{b}" for m, b in cols) + " |")
    print("|---|" + "---|" * len(cols))
    for c in creatures:
        cells = []
        for k in cols:
            r = by[k].get(c)
            if not r or not r.get("assessment"):
                cells.append(r.get("status", "-")[:4] if r else "-")
                continue
            cells.append(f"{r['status'][:4]} {r['assessment']['validation']['walking_frac']:.2f}")
        print(f"| {c} | " + " | ".join(cells) + " |")
    # R* rule
    budgets = sorted({b for (m, b) in full if m in NON_AI})
    n = len(creatures)
    r_star, why = None, ""
    for b in budgets:
        best = max(full.get((m, b), 0) for m in NON_AI)
        if 0.25 * n <= best <= 0.60 * n:
            r_star, why = b, f"best non-AI method recovers {best}/{n} (25-60% rule)"
            break
    if r_star is None:
        dist = {b: min(abs(max(full.get((m, b), 0) for m in NON_AI) - 0.25 * n), abs(max(full.get((m, b), 0) for m in NON_AI) - 0.6 * n)) for b in budgets}
        r_star = min(dist, key=lambda b: (dist[b], b))
        why = f"no budget in the 25-60% range; closest is {r_star} ({ {b: max(full.get((m, b), 0) for m in NON_AI) for b in budgets} })"
    comp = "cma_joint" if full.get(("cma_joint", r_star), 0) >= full.get(("fix", r_star), 0) else "fix"
    print(f"\nR* = {r_star}: {why}")
    print(f"primary comparator at R*: {comp} (cma_joint {full.get(('cma_joint', r_star))} vs fix {full.get(('fix', r_star))}; ties -> cma_joint)")
    # AI decision quality
    for meth in ("ai", "ai_nogait"):
        units = [r for r in recs if r["method"] == meth and r.get("director_record")]
        if not units:
            continue
        n_ok_plans = 0
        statuses = defaultdict(int)
        cost = 0.0
        calls = 0
        for r in units:
            d = r["director_record"]
            cost += d.get("cost_usd") or 0.0
            calls += len(d.get("calls") or [])
            plan_ok = any(x["kind"] == "plans" and x["status"] == "ok" and x["returned"] for x in d["decisions"])
            n_ok_plans += plan_ok
            for x in d["decisions"]:
                statuses[x["status"]] += 1
        print(f"\n{meth}: {len(units)} pipelines; valid plan in {n_ok_plans}/{len(units)} = {n_ok_plans / len(units):.0%} (G2 needs >= 80%); "
              f"decision statuses {dict(statuses)}; {calls} calls, ${cost:.4f}")
    # H6: AI round-1 probe choices vs census ranking
    census = {r["creature"]: census_ranking(r) for r in recs if r["method"] == "census" and r.get("pipeline")}
    for meth in ("ai", "ai_nogait"):
        hits, tot, rand_exp = 0, 0, 0.0
        for r in recs:
            if r["method"] != meth or not r.get("director_record") or r["creature"] not in census:
                continue
            rank = census[r["creature"]]
            top2 = {p for p, _, _ in rank[:2]}
            avail = [p for p, _, _ in rank]
            chosen = next((x["returned"] for x in r["director_record"]["decisions"] if x["kind"] == "probes" and x["round"] == 1), [])
            chosen = [p for p in chosen if p in avail]
            if not chosen:
                continue
            tot += 1
            hits += bool(set(chosen) & top2)
            k = len(chosen)
            m_ = len(avail)
            from math import comb
            rand_exp += 1 - (comb(m_ - 2, k) / comb(m_, k) if m_ - 2 >= k else 0.0)
        if tot:
            print(f"H6 {meth}: round-1 probes include a census top-2 probe in {hits}/{tot} pipelines (random choice of the same size: {rand_exp:.1f}/{tot} expected)")
    if census:
        print("\ncensus best probes per creature: " + "; ".join(f"{c}: {rk[0][0]} ({rk[0][1]:+d}), {rk[1][0]} ({rk[1][1]:+d})"
                                                                for c, rk in census.items() if len(rk) >= 2))
    if a.out:
        Path(a.out).write_text(json.dumps({"full": {f"{m}@{b}": v for (m, b), v in full.items()}, "r_star": r_star, "r_star_reason": why,
                                           "primary_comparator": comp, "accounting_violations": acct_bad,
                                           "unit_errors": [r["unit"] for r in errors]}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
