"""Descriptive summary of a walk_oracle results file (one analysis; no test statistic).

    python scripts/walk_oracle_report.py experiments/walk_recovery/oracle/results/m1a.jsonl [--md]
Prints one row per (unit, checkpoint): recovery status, candidate walking fraction on the 24 validation seeds, original
walking fraction, verdict_v1 status and median paired gain, confirmation result, edits and rollouts.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def rows(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        for cp, v in sorted(r["checkpoints"].items(), key=lambda kv: int(kv[0])):
            a = v["assessment"]
            val = a["validation"]
            orig_w = sum(x["walking"] for x in val["original"]) / max(1, len(val["original"]))
            conf = a["confirmation"]
            out.append({
                "creature": r["creature"], "region": r.get("region"), "condition": r["condition"]["id"], "noise": r["noise_seed"],
                "checkpoint": int(cp), "status": v["status"], "cand_walk": val["walking_frac"], "orig_walk": orig_w,
                "verdict": val["verdict"]["status"], "median_gain_m": val["verdict"].get("median_diff"),
                "confirm": (conf.get("passed") if conf.get("run") else None),
                "confirm_walk": (conf.get("checks", {}).get("walking_frac", {}).get("value") if conf.get("run") else None),
                "edits": v.get("edits") or [], "found_at": v.get("found_at_rollouts"),
                "search_rollouts": r["rollouts"]["search"]})
    return out


def fmt(x, nd=2):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    a = ap.parse_args()
    rs = rows(Path(a.results))
    print("| creature | condition | ckpt | status | cand walk | orig walk | verdict | median gain m | confirm walk | body edits |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rs:
        ed = ", ".join(f"{e['param']} x{e['value']:.2f}" for e in r["edits"]) or "-"
        print(f"| {r['creature']} | {r['condition']} | {r['checkpoint']} | {r['status']} | {fmt(r['cand_walk'])} | "
              f"{fmt(r['orig_walk'])} | {r['verdict']} | {fmt(r['median_gain_m'])} | {fmt(r['confirm_walk'])} | {ed} |")
    final = defaultdict(dict)
    for r in rs:
        key = (r["creature"], r["condition"], r["noise"])
        if r["checkpoint"] >= final[key].get("checkpoint", -1):
            final[key] = r
    by_cond = defaultdict(lambda: defaultdict(int))
    for (c, cond, _), r in final.items():
        by_cond[cond][r["status"]] += 1
    print("\nFinal checkpoint per unit, status counts by condition:")
    for cond, cnt in by_cond.items():
        print(f"- {cond}: " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
