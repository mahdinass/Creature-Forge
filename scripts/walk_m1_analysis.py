"""M1 analysis (pre-declared in protocol_m1.json "analysis"; descriptive, run once after all shards completed).

    python scripts/walk_m1_analysis.py <shard*.jsonl ...> [--out summary.json]

Prints:
  * per creature x condition: final-checkpoint status of each replicate and the best walking fraction;
  * a creature counts as "recovered by condition X" if ANY replicate of X is FULL_RECOVERY at its final checkpoint
    (replicate agreement reported);
  * G1: creatures (of all) fully recovered at the final checkpoint by the best condition, and by any condition/checkpoint;
  * secondary: per-checkpoint status counts (budget curves), ctrl17 vs ctrl15 and joint vs ctrl paired per creature,
    H7 (3 nominal vs 8 varied seeds at 4k), train-vs-validation gap.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

RANK = {"FULL_RECOVERY": 3, "PARTIAL_IMPROVEMENT": 2, "NOT_RECOVERED": 1, "INCONCLUSIVE_ERROR": 0}


def load(paths) -> list[dict]:
    recs = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                recs.append(json.loads(line))
    return recs


def final_cp(rec: dict) -> tuple[int, dict]:
    k = max(rec["checkpoints"], key=lambda c: int(c))
    return int(k), rec["checkpoints"][k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    recs = load(a.files)
    creatures = list(dict.fromkeys(r["creature"] for r in recs))
    conds = list(dict.fromkeys(r["condition"]["id"] for r in recs))
    units = {(r["creature"], r["condition"]["id"], r["noise_seed"]): r for r in recs}
    print(f"{len(recs)} units, {len(creatures)} creatures, conditions {conds}")
    print(f"protocol sha256 {sorted({r['protocol_sha256'] for r in recs})}, commits {sorted({r['code_commit'] for r in recs})}, "
          f"panel {sorted({str(r.get('panel_sha256')) for r in recs})}")
    table = defaultdict(dict)
    recovered_by = defaultdict(set)
    any_cp_recovered = set()
    for (c, cond, ns), r in units.items():
        k, v = final_cp(r)
        w = v["assessment"]["validation"]["walking_frac"]
        table[c].setdefault(cond, []).append((ns, v["status"], w, k))
        if v["status"] == "FULL_RECOVERY":
            recovered_by[cond].add(c)
        if any(x["status"] == "FULL_RECOVERY" for x in r["checkpoints"].values()):
            any_cp_recovered.add(c)
    print("\n| creature | " + " | ".join(conds) + " |")
    print("|---|" + "---|" * len(conds))
    for c in creatures:
        cells = []
        for cond in conds:
            reps = sorted(table[c].get(cond, []))
            cells.append(" / ".join(f"{s.split('_')[0][:4]} {w:.2f}" for _, s, w, _ in reps) or "-")
        print(f"| {c} | " + " | ".join(cells) + " |")
    print("\nRecovered (FULL at final checkpoint, any replicate) by condition:")
    for cond in conds:
        reps_agree = []
        for c in recovered_by[cond]:
            sts = [s for _, s, _, _ in table[c][cond]]
            reps_agree.append(f"{c}({sum(s == 'FULL_RECOVERY' for s in sts)}/{len(sts)})")
        print(f"- {cond}: {len(recovered_by[cond])}/{len(creatures)}  {sorted(reps_agree)}")
    best = max(conds, key=lambda cd: len(recovered_by[cd]))
    union_final = set().union(*recovered_by.values()) if recovered_by else set()
    print(f"\nG1: best single condition {best}: {len(recovered_by[best])}/{len(creatures)} = {len(recovered_by[best]) / len(creatures):.0%}; "
          f"union over conditions (final checkpoint): {len(union_final)}/{len(creatures)}; "
          f"any condition, any checkpoint: {len(any_cp_recovered)}/{len(creatures)}")
    # budget curves
    print("\nStatus counts per condition x checkpoint (all replicates):")
    curve = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for r in recs:
        for k, v in r["checkpoints"].items():
            curve[r["condition"]["id"]][int(k)][v["status"]] += 1
    for cond in conds:
        for k in sorted(curve[cond]):
            d = curve[cond][k]
            print(f"- {cond} @{k}: " + ", ".join(f"{s} {n}" for s, n in sorted(d.items())))
    # paired comparisons (best replicate status per creature)

    def best_status(c, cond):
        reps = table[c].get(cond, [])
        return max((RANK[s] for _, s, _, _ in reps), default=None)

    for x, y in (("ctrl17", "ctrl15"), ("joint17", "ctrl17"), ("joint15", "ctrl15"), ("joint17", "joint15")):
        if x in conds and y in conds:
            better = sum(1 for c in creatures if best_status(c, x) is not None and best_status(c, y) is not None and best_status(c, x) > best_status(c, y))
            worse = sum(1 for c in creatures if best_status(c, x) is not None and best_status(c, y) is not None and best_status(c, x) < best_status(c, y))
            print(f"paired {x} vs {y}: better on {better}, worse on {worse}, equal on {len(creatures) - better - worse} (status rank, best replicate)")
    # H7 at 4k
    h7 = [r for r in recs if r["condition"]["id"].startswith("h7")]
    if h7:
        print("\nH7 (status at 4000):")
        for r in h7:
            c = r["creature"]
            ref = units.get((c, "ctrl15", 1))
            s_ref = ref["checkpoints"].get("4000", {}).get("status") if ref else None
            w_ref = ref["checkpoints"]["4000"]["assessment"]["validation"]["walking_frac"] if ref and "4000" in ref["checkpoints"] else None
            v = r["checkpoints"]["4000"]
            print(f"- {c}: 3 nominal seeds {v['status']} ({v['assessment']['validation']['walking_frac']:.2f}) vs 8 varied {s_ref} ({w_ref})")
    # train vs validation gap at the final checkpoint
    gaps = []
    for r in recs:
        if not r.get("search"):
            continue
        k, v = final_cp(r)
        n_train = len(r["train_seeds_used"])
        tw = v["train_score"][0] / n_train if v.get("train_score") else None
        if tw is not None:
            gaps.append(tw - v["assessment"]["validation"]["walking_frac"])
    if gaps:
        gaps.sort()
        print(f"\ntrain walking frac - validation walking frac at the final checkpoint: median {gaps[len(gaps) // 2]:+.2f}, "
              f"min {gaps[0]:+.2f}, max {gaps[-1]:+.2f} (n={len(gaps)})")
    if a.out:
        Path(a.out).write_text(json.dumps({"recovered_by": {k: sorted(v) for k, v in recovered_by.items()},
                                           "union_final": sorted(union_final), "any_checkpoint": sorted(any_cp_recovered),
                                           "best_condition": best, "n_creatures": len(creatures),
                                           "table": {c: {cd: v for cd, v in d.items()} for c, d in table.items()}}, indent=1),
                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
