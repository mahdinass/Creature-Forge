"""Select the registered held-out evaluation instances (rule in experiments/causal_engineer/heldout/PROTOCOL.md).

    python scripts/ce_heldout_select.py --instances <heldout_shard*.jsonl ...> [--n 40] [--out ids.json]

Order the kept pool by SHA-256("ce-heldout-eval-v1:" + instance_id); take instances in that order with at most 6 per fault and
`cap` per base robot (3, raised to 4, then 5 if fewer than N qualify); if the pool is still short, all kept instances.
Reads only ids, faults, bases and the kept flag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter

SALT = "ce-heldout-eval-v1:"
PER_FAULT = 6


def select(pool: list[dict], n: int = 40) -> tuple[list[str], int | None]:
    kept = sorted((r for r in pool if r.get("kept")), key=lambda r: hashlib.sha256((SALT + r["instance_id"]).encode()).hexdigest())
    for cap in (3, 4, 5):
        out, fc, bc = [], Counter(), Counter()
        for r in kept:
            if fc[r["fault"]] < PER_FAULT and bc[r["base_id"]] < cap:
                out.append(r["instance_id"])
                fc[r["fault"]] += 1
                bc[r["base_id"]] += 1
            if len(out) == n:
                return out, cap
    return [r["instance_id"] for r in kept], None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--out")
    a = ap.parse_args()
    pool = [json.loads(l) for p in a.instances for l in open(p, encoding="utf-8") if l.strip()]
    ids, cap = select(pool, a.n)
    kept = [r for r in pool if r.get("kept")]
    sel = [r for r in kept if r["instance_id"] in set(ids)]
    summary = {"n_candidates": len(pool), "n_kept": len(kept), "n_selected": len(ids), "base_cap_used": cap,
               "kept_per_fault": dict(Counter(r["fault"] for r in kept)), "selected_per_fault": dict(Counter(r["fault"] for r in sel)),
               "selected_bases": len({r["base_id"] for r in sel})}
    print(json.dumps(summary, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"rule": "PROTOCOL.md (ce-heldout-eval-v1)", "summary": summary, "instance_ids": ids}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
