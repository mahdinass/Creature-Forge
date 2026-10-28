"""DS-1 report (docs/DS1_PROTOCOL.md §7.5): the two learning signals scored separately, cross-feedback, memory use, the learning
stream (updating vs frozen experience) and the paired arm contrasts. Development evidence only.

Usage: python scripts/ds1_report.py --eval <records.jsonl ...> [--stream-dir artifacts/vm/hdb/artifacts/hdb/ds1_stream]
       [--cases experiments/causal_engineer/dev/hdb/ds1/cases_init.json] [--out experiments/causal_engineer/dev/hdb/DS1_RESULTS.md]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creature_forge import has_cases as hc                       # noqa: E402
from hdb_report import wilcoxon_one_sided                        # noqa: E402

FULL = "FULL_RECOVERY"


def rows(paths):
    return [json.loads(l) for p in paths for l in open(p, encoding="utf-8") if l.strip()]


def mcnemar(b, c):
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


def category(r):
    v = r["verification"]
    if v["status"] == FULL:
        return "FULL"
    rs = " ".join(v["reasons"])
    if "verdict" in rs and "aggregate" not in rs:
        return "walks, not farther than faulty"
    if "confirmation" in rs:
        return "20 s confirmation"
    return "validation walking < 80 %"


def inj(r):
    return sorted(tuple(x) for x in r["injected_structure"])


def mapped(r):
    return sorted(tuple(x) for x in (r["map_structure"] or []))


def diagnostic(rs):
    """Diagnostic signal: posterior on the truth, calibration of the leading explanation's mass, confident-wrong rate."""
    lp = [math.log(max(r["posterior_mass_on_injected"], 1e-4)) for r in rs]
    corr = [mapped(r) == inj(r) for r in rs]
    mass = np.array([r["map_mass"] for r in rs])
    bins = np.minimum((mass * 5).astype(int), 4)
    ece = sum(abs(mass[bins == k].mean() - np.mean(np.array(corr)[bins == k])) * (bins == k).sum() for k in range(5)
              if (bins == k).any()) / len(rs)
    part = [any(tuple(x) in set(inj(r)) for x in (r["map_structure"] or [])) for r in rs]
    eng = [r["engine"] for r in rs]
    return {"n": len(rs), "mean_log_p_truth": float(np.mean(lp)), "map_correct": int(sum(corr)), "ece_map_mass": float(ece),
            "confident_wrong": int(sum(1 for r, c in zip(rs, corr) if r["map_mass"] >= 0.95 and not c)),
            "map_shares_a_true_primitive": int(sum(part)),
            "mean_unmodelled_mass": float(np.mean([e.get("unmodelled_mass", 0.0) for e in eng])),
            "composite_expansions": int(sum(any(ev["kind"] == "composite_expansion" for ev in e["events"]) for e in eng)),
            "composite_skipped_for_budget": int(sum(any(ev["kind"] == "composite_skipped" for ev in e["events"]) for e in eng))}


def repair(rs, rhead=None, T=6.0):
    cats = collections.Counter(category(r) for r in rs)
    out = {"n": len(rs), "full": cats.get("FULL", 0), "categories": dict(cats),
           "mean_walking": float(np.mean([r["verification"]["walking_frac"] for r in rs])),
           "plant_used": float(np.mean([r["engine"]["ledger"]["used"] for r in rs])),
           "twin_used": float(np.mean([r["engine"]["ledger"]["twin"]["used"] for r in rs]))}
    ps = [(d["p_success"], d["full"]) for r in rs if (d := hc.agent_decision(r)) and d["p_success"] is not None]
    if ps:
        out["nemotron_p_success"] = {"n": len(ps), "mean": float(np.mean([p for p, _ in ps])),
                                     "brier": float(np.mean([(p - f) ** 2 for p, f in ps]))}
    ds = [d for r in rs if (d := hc.agent_decision(r))]
    if ds:
        dev = [d for d in ds if d["deviated"]]
        out["deviation"] = {"episodes": len(ds), "deviated": len(dev), "full_when_deviated": sum(d["full"] for d in dev),
                            "full_when_delegated": sum(d["full"] for d in ds if not d["deviated"])}
    if rhead is not None:
        pr = []
        for r in rs:
            c = hc.repair_case(r, T, "engine_final")
            if c:
                pr.append((rhead.p(c["sit"], {c["tool"]: c["ev"]}, c["tool"]), c["full"]))
        if pr:
            out["rhead_brier_on_submitted"] = {"n": len(pr), "brier": float(np.mean([(p - f) ** 2 for p, f in pr]))}
    return out


def feedback(rs):
    ev = [e for r in rs for e in r["engine"]["events"]]
    a = [e for e in ev if e["kind"] == "assimilated_check"]
    return {"assimilated_checks": len(a), "leader_changed": sum(1 for e in a if e.get("leader_changed")),
            "episodes_with_change": sum(1 for r in rs if any(e["kind"] == "assimilated_check" and e.get("leader_changed")
                                                             for e in r["engine"]["events"])),
            "rescreens": sum(1 for e in ev if e["kind"] == "rescreen_after_assimilation"),
            "skipped_for_budget": sum(1 for e in ev if e["kind"] == "assimilation_skipped")}


def contrasts(by_arm):
    L = []
    arms = sorted(by_arm)
    for i, a in enumerate(arms):
        for b in arms[i + 1:]:
            A = {r["instance_id"]: r for r in by_arm[a]}
            B = {r["instance_id"]: r for r in by_arm[b]}
            sh = sorted(set(A) & set(B))
            if not sh:
                continue
            x = sum(1 for k in sh if A[k]["verification"]["status"] == FULL and B[k]["verification"]["status"] != FULL)
            y = sum(1 for k in sh if B[k]["verification"]["status"] == FULL and A[k]["verification"]["status"] != FULL)
            d = [A[k]["verification"]["walking_frac"] - B[k]["verification"]["walking_frac"] for k in sh]
            w = wilcoxon_one_sided(d)
            L.append(f"- {a} vs {b}: n {len(sh)}; FULL {sum(A[k]['verification']['status'] == FULL for k in sh)} vs "
                     f"{sum(B[k]['verification']['status'] == FULL for k in sh)}; discordant {x}/{y}; p({a}>{b}) = {mcnemar(x, y):.3f}, "
                     f"p({b}>{a}) = {mcnemar(y, x):.3f}; walking diff {w['mean_diff']:+.3f} (Wilcoxon p({a}>{b}) = {w['p']:.3f})")
    return L


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", nargs="*", default=[])
    ap.add_argument("--stream-dir", default=None)
    ap.add_argument("--cases", default="experiments/causal_engineer/dev/hdb/ds1/cases_init.json")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    store = hc.CaseStore.load(a.cases)
    L = ["# DS-1 results (development only; no claim)", ""]
    if a.eval:
        rs = rows(a.eval)
        by_arm = collections.defaultdict(list)
        for r in rs:
            by_arm[r["arm"]].append(r)
        for part, pred in (("single mechanism", lambda r: not r["family"].startswith("devcomp")),
                           ("development compositions", lambda r: r["family"].startswith("devcomp"))):
            sub = {k: [r for r in v if pred(r)] for k, v in by_arm.items()}
            sub = {k: v for k, v in sub.items() if v}
            if not sub:
                continue
            L += [f"## dev-eval-2: {part}", "", "### Diagnostic signal", "",
                  "| arm | n | mean log P(truth) | leading correct | ECE of leading mass | confident wrong | shares a true primitive | mean unmodelled | composite expansions (skipped) |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for k, v in sorted(sub.items()):
                d = diagnostic(v)
                L.append(f"| {k} | {d['n']} | {d['mean_log_p_truth']:.2f} | {d['map_correct']} | {d['ece_map_mass']:.3f} | "
                         f"{d['confident_wrong']} | {d['map_shares_a_true_primitive']} | {d['mean_unmodelled_mass']:.2f} | "
                         f"{d['composite_expansions']} ({d['composite_skipped_for_budget']}) |")
            L += ["", "### Repair signal", ""]
            for k, v in sorted(sub.items()):
                L.append(f"- {k}: {json.dumps(repair(v, store.rhead, store.T))}")
            L += ["", "### Cross-feedback (intervention outcomes folded into the belief)", ""]
            for k, v in sorted(sub.items()):
                L.append(f"- {k}: {json.dumps(feedback(v))}")
            L += ["", "### Paired contrasts (exact one-sided McNemar on FULL; Wilcoxon on validation walking)", "",
                  *contrasts(sub), ""]
    if a.stream_dir:
        L += ["## Learning stream (A4x updating vs frozen experience; same instances, same order)", ""]
        order = json.load(open(os.path.join(a.stream_dir, "order.json")))
        per_round = collections.defaultdict(lambda: {"upd": [], "frz": []})
        for f in sorted(glob.glob(os.path.join(a.stream_dir, "r*_*.jsonl"))):
            name = os.path.basename(f)
            rnd, tag = int(name.split("_")[0][1:]), name.split("_")[1]
            per_round[rnd][tag] += rows([f])
        L += ["| round | n | FULL updating | FULL frozen | mean log P(truth) upd / frz | Nemotron P(success) Brier upd / frz | "
              "repair model Brier on this round (store before round) upd / init |", "|---|---|---|---|---|---|---|"]
        for rnd in sorted(per_round):
            u, f = per_round[rnd]["upd"], per_round[rnd]["frz"]
            if not u or not f:
                continue
            st_path = os.path.join(a.stream_dir, f"cases_upd_r{rnd}.json")
            st = hc.CaseStore.load(st_path) if os.path.exists(st_path) else store
            ru, ri = repair(u, st.rhead, st.T), repair(u, store.rhead, store.T)
            pu, pf = repair(u).get("nemotron_p_success", {}), repair(f).get("nemotron_p_success", {})
            L.append(f"| {rnd} | {len(u)} | {ru['full']} | {repair(f)['full']} | {diagnostic(u)['mean_log_p_truth']:.2f} / "
                     f"{diagnostic(f)['mean_log_p_truth']:.2f} | {pu.get('brier', float('nan')):.3f} / {pf.get('brier', float('nan')):.3f} | "
                     f"{ru.get('rhead_brier_on_submitted', {}).get('brier', float('nan')):.3f} / "
                     f"{ri.get('rhead_brier_on_submitted', {}).get('brier', float('nan')):.3f} |")
        allu = [r for v in per_round.values() for r in v["upd"]]
        allf = [r for v in per_round.values() for r in v["frz"]]
        if allu and allf:
            L += ["", "Paired over the whole stream:", *contrasts({"A4x-updating": allu, "A4x-frozen": allf})]
    text = "\n".join(L) + "\n"
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
