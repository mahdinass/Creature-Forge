"""Print compact traces of agent records next to the engine-only record of the same instance (development inspection).

Usage: python scripts/hdb_agent_trace.py <agent records.jsonl ...> --baseline <A1c5/A1e records.jsonl ...> [--full]
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    args = sys.argv[1:]
    full = "--full" in args
    args = [a for a in args if a != "--full"]
    i = args.index("--baseline") if "--baseline" in args else len(args)
    recs = [json.loads(l) for p in args[:i] for l in open(p, encoding="utf-8") if l.strip()]
    base = {}
    for p in args[i + 1:]:
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            if "verification" in r:
                base[r["instance_id"]] = r
    for r in recs:
        b = base.get(r["instance_id"])
        print(f"\n=== {r['instance_id']} {r['arm']}: {r['verification']['status']} walk {r['verification']['walking_frac']:.2f}; "
              f"MAP {r['map_structure']} ({r['map_mass']:.2f}) truth {r['injected_structure']}; plant "
              f"{r['engine']['ledger']['used']} twin {r['engine']['ledger']['twin']['used']}; "
              f"${(r.get('nemotron') or {}).get('cost_usd', 0):.4f}")
        if b:
            print(f"    engine-only: {b['verification']['status']} walk {b['verification']['walking_frac']:.2f}; MAP "
                  f"{b['map_structure']}; plant {b['engine']['ledger']['used']} tools "
                  f"{[s.get('tool') for s in (b.get('repair') or {}).get('log', [])]}")
        notes = {n["turn"]: n for n in (r["agent"].get("notes") or [])}
        for t in r["agent"]["trace"]:
            a = {k: v for k, v in t["action"].items() if k not in ("understanding", "uncertainty", "why", "prediction", "hypotheses")}
            res = t["result"]
            short = {k: res[k] for k in ("refused", "id", "eig", "best_eig", "measured", "design", "evidence", "ran", "accepted",
                                         "before", "after") if k in res}
            hy = [(h["pid"], h.get("fitted"), h.get("weight"), h.get("rank")) for h in (res.get("proposals") or {}).get("added") or []]
            print(f"  [{t['seq']}] {t['actor']:8s} {json.dumps(a)[:150]} | +{t['plant_cost']}p +{t['twin_cost']}t")
            if hy:
                print(f"       hypotheses: {hy}")
            if short:
                print(f"       -> {json.dumps(short)[:300]}")
            n = notes.get(t.get("turn")) if t["actor"] == "nemotron" else None
            if n and full:
                print(f"       WHY: {n['why'][:400]}")
                print(f"       UNDERSTANDING: {n['understanding'][:400]}")
        rep = (r.get("repair") or {}).get("log")
        if rep:
            print(f"    engine repair log: {[(s.get('step'), s.get('tool'), s.get('check16'), (s.get('evidence') or {}).get('p_full')) for s in rep]}")


if __name__ == "__main__":
    main()
