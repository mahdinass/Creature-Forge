"""Failure thresholds for the v2 Hidden-Damage Bench (physics only): bisection of each family variant's fault strength on the
gap-free plant per base (hdb_bench.threshold). Output: {"<base_id>|<family>|<variant>": {...}} JSON.

Usage (VM): python scripts/hdb_thresholds.py --split dev --workers 32 --out artifacts/hdb/thresholds_dev.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge.forge_pool import ForgePool                   # noqa: E402


def job(args):
    base, fam, var = args
    return hb.threshold(base, fam, var)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--families", default=",".join(hb.FAMILY_SPECS))
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = json.load(open(a.out, encoding="utf-8")) if os.path.exists(a.out) else {}
    jobs = [(b, f, v) for b in hb.load_bases(a.split) for f in a.families.split(",") for v in hb.FAMILY_SPECS[f]["variants"]
            if f"{b['base_id']}|{f}|{v}" not in out]
    with ForgePool(max_workers=a.workers) as pool:
        for _, r in pool.imap(job, jobs):
            if isinstance(r, tuple):
                print("ERROR", r, flush=True)
                continue
            out[f"{r['base_id']}|{r['family']}|{r['variant']}"] = r
            print(r["base_id"], r["family"], r["variant"], r["s_star"], flush=True)
            with open(a.out + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(out, fh)
            os.replace(a.out + ".tmp", a.out)


if __name__ == "__main__":
    main()
