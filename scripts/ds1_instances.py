"""DS-1 instance lists (docs/DS1_PROTOCOL.md §5-7), fixed before any run that uses them: a seeded shuffle of the candidate
instances on the requested bases, minus every instance id in any earlier record (--exclude-ids), kept in order while eligible
(the frozen physics-only eligibility rule) until the requested numbers of single-mechanism and composition instances.

Usage (VM): python scripts/ds1_instances.py --which stream --mults 1.0,1.7 --sample-seed 20261021 --n-single 24 --n-comp 6
            --exclude-ids experiments/causal_engineer/dev/hdb/ds1/used_instance_ids.txt --thresholds artifacts/hdb/thresholds_dev.json
            --out experiments/causal_engineer/dev/hdb/ds1/stream_instances.json [--workers 6]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from creature_forge import hdb_bench as hb                       # noqa: E402
from creature_forge.forge_pool import ForgePool, InlinePool      # noqa: E402
import hdb_agent_run as har                                      # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["init", "stream", "transfer"], required=True)
    ap.add_argument("--split-file", default="experiments/causal_engineer/dev/hdb/stage2_split.json")
    ap.add_argument("--mults", default="1.0,1.7")
    ap.add_argument("--sample-seed", type=int, required=True)
    ap.add_argument("--n-single", type=int, required=True)
    ap.add_argument("--n-comp", type=int, required=True)
    ap.add_argument("--exclude-ids", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    used = {l.strip() for l in open(a.exclude_ids, encoding="utf-8") if l.strip()}
    th = json.load(open(a.thresholds, encoding="utf-8"))
    out = {"which": a.which, "mults": a.mults, "sample_seed": a.sample_seed, "exclude_ids": a.exclude_ids,
           "single": [], "comp": [], "ineligible": 0, "excluded_used": 0}
    pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    with pool_cm as pool:
        for comp, n_want, key in ((False, a.n_single, "single"), (True, a.n_comp, "comp")):
            ns = types.SimpleNamespace(split_file=a.split_file, which=a.which, devcomp=comp, sample=True,
                                       sample_seed=a.sample_seed, families=None, mults=a.mults)
            for b, f, s in har.instances(ns):
                if len(out[key]) >= n_want:
                    break
                if comp:
                    from creature_forge import hdb_devcomp
                    raw = hdb_devcomp.make_instance(b, f, th)
                else:
                    raw = hb.make_instance_v2(b, f, s, th)
                if raw is None:
                    continue
                if raw["instance_id"] in used:
                    out["excluded_used"] += 1
                    continue
                if not hb.check_eligibility(raw, pool=pool)["eligible"]:
                    out["ineligible"] += 1
                    continue
                out[key].append(raw["instance_id"])
                print(key, raw["instance_id"], flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in out.items()}))


if __name__ == "__main__":
    main()
