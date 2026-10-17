"""Causal-engineer evaluation analysis (descriptive; one run per results set).

    python scripts/ce_analysis.py --results <ce_eval jsonl ...> --instances <fault_bench jsonl ...> [--out summary.json]

Per policy: verified FULL / PARTIAL / NOT, mean validation walking fraction, rollouts used, number of experiments; DECISION
QUALITY from the ground-truth repair matrix (never shown to policies): share of episodes whose repairs included at least one
tool that repairs the instance (matrix walking frac >= 0.75), and whether the FIRST repair tool was such a tool; for the
scientist arms also diagnosis-category match with the injected mechanism, prediction accuracy (vs the 1/3 chance level and the
majority-direction baseline), hypothesis revisions, LLM calls and cost. Per-fault breakdown.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

FULL = "FULL_RECOVERY"
REPAIR_OK = 0.75


def load(paths):
    return [json.loads(l) for p in paths for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def repair_tools(rec) -> list[str]:
    out = []
    for line in rec.get("ledger", {}).get("lines", []) if isinstance(rec.get("ledger"), dict) else (rec.get("ledger") or []):
        item = line.get("item", "") if isinstance(line, dict) else ""
        det = (line.get("detail") or {}) if isinstance(line, dict) else {}
        if item.startswith("repair") and not item.endswith("refund") and det.get("tool"):
            out.append(det["tool"])
    if not out:
        pr = rec.get("policy_record") or {}
        for e in pr.get("experiments", []) or []:
            if e.get("kind") == "repair" and e.get("status") != "refused":
                out.append(e.get("tool"))
        for r in pr.get("repairs", []) or []:
            if r.get("tool"):
                out.append(r["tool"])
    return [t for t in out if t]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--instances", nargs="+", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    inst = {r["instance_id"]: r for r in load(a.instances) if r.get("kept")}
    recs = load(a.results)
    by_pol = defaultdict(list)
    for r in recs:
        by_pol[r["policy"]].append(r)
    print(f"{len(recs)} episodes over {len({r['instance_id'] for r in recs})} instances; policies {sorted(by_pol)}")
    rows = {}
    print("\n| policy | FULL | PARTIAL | NOT | err | mean walking | rollouts | experiments | chose a repairing tool | first repair repairs | diag match | pred acc (n) | LLM $ |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for pol, rs in sorted(by_pol.items()):
        st = [((r.get("verification") or {}).get("status") or ("ERROR" if r.get("error") else None)) for r in rs]
        walk = [(r.get("verification") or {}).get("walking_frac") for r in rs]
        walk = [w for w in walk if isinstance(w, (int, float))]
        chose = first = n_dec = 0
        for r in rs:
            m = (inst.get(r["instance_id"]) or {}).get("repair_matrix") or {}
            tools = repair_tools(r)
            if not m:
                continue
            n_dec += 1
            good = {t for t, v in m.items() if isinstance(v, (int, float)) and v >= REPAIR_OK}
            chose += bool(set(tools) & good)
            first += bool(tools and tools[0] in good)
        dm = [r.get("diagnosis", {}).get("match") for r in rs if isinstance(r.get("diagnosis"), dict) and r["diagnosis"].get("match") is not None]
        pa_c = sum((r.get("prediction_accuracy") or {}).get("n_correct") or 0 for r in rs)
        pa_n = sum((r.get("prediction_accuracy") or {}).get("n_scored") or 0 for r in rs)
        cost = sum(((r.get("llm") or {}).get("cost_usd") or 0) for r in rs)
        row = {"n": len(rs), "full": st.count(FULL), "partial": st.count("PARTIAL_IMPROVEMENT"), "not": st.count("NOT_RECOVERED"),
               "err": sum(1 for x in st if x not in (FULL, "PARTIAL_IMPROVEMENT", "NOT_RECOVERED")),
               "walk": sum(walk) / max(1, len(walk)), "rollouts": sum(r.get("rollouts_used") or 0 for r in rs) / max(1, len(rs)),
               "experiments": sum(r.get("n_experiments") or 0 for r in rs) / max(1, len(rs)),
               "chose_repairing": f"{chose}/{n_dec}", "first_repairs": f"{first}/{n_dec}",
               "diag_match": f"{sum(bool(x) for x in dm)}/{len(dm)}" if dm else "-",
               "pred_acc": f"{pa_c / pa_n:.2f} ({pa_n})" if pa_n else "-", "cost": cost}
        rows[pol] = row
        print(f"| {pol} | {row['full']} | {row['partial']} | {row['not']} | {row['err']} | {row['walk']:.2f} | {row['rollouts']:.0f} | "
              f"{row['experiments']:.1f} | {row['chose_repairing']} | {row['first_repairs']} | {row['diag_match']} | {row['pred_acc']} | {cost:.3f} |")
    faults = sorted({r.get("fault") for r in recs})
    print("\nFULL recoveries by fault:")
    print("| policy | " + " | ".join(faults) + " |")
    print("|---|" + "---|" * len(faults))
    for pol, rs in sorted(by_pol.items()):
        cells = []
        for f in faults:
            sub = [r for r in rs if r.get("fault") == f]
            cells.append(f"{sum(1 for r in sub if (r.get('verification') or {}).get('status') == FULL)}/{len(sub)}")
        print(f"| {pol} | " + " | ".join(cells) + " |")
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
