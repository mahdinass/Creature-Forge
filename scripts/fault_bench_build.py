"""Build fault-benchmark instances (append-only JSONL, one record per (base, fault, severity), invalid ones included).

  python scripts/fault_bench_build.py --split dev --campaign cebench-dev-v1 --out out.jsonl --workers 2 \
      [--faults short_feet slippery] [--severities 0.25 0.5 0.75] [--shard 0/4] [--resume] [--rollout-cap 20000] [--budget 160]

Run on the VM (MuJoCo). Records contain ground truth (fault, repair matrix); they are never shown to a policy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import fault_bench as fb  # noqa: E402
from creature_forge.forge_pool import ForgePool  # noqa: E402


def items(split: str, faults, severities, bases=None, max_bases=None):
    bs = fb.load_bases(split)
    if bases:
        bs = [b for b in bs if b["base_id"] in set(bases)]
    if max_bases:
        bs = bs[:max_bases]
    return [(b, f, float(s)) for b in bs for f in faults for s in severities]


def done_ids(path: str) -> set:
    if not os.path.exists(path):
        return set()
    out = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.add(json.loads(line)["instance_id"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=sorted(fb.SPLITS), required=True)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--faults", nargs="+", default=list(fb.FAULTS))
    ap.add_argument("--severities", nargs="+", type=float, default=[0.25, 0.5, 0.75])
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--shard", default="0/1", help="i/k: this process builds items with index %% k == i")
    ap.add_argument("--resume", action="store_true", help="skip instance ids already in --out")
    ap.add_argument("--budget", type=int, default=fb.DEFAULT_BUDGET, help="rollouts of every tool in the repair matrix (B)")
    ap.add_argument("--n-train", type=int, default=fb.DEFAULT_TRAIN)
    ap.add_argument("--n-check", type=int, default=fb.CHECK_N)
    ap.add_argument("--rollout-cap", type=int, default=0, help="stop starting new instances once this many rollouts were used (0 = none)")
    ap.add_argument("--bases", nargs="*", help="restrict to these base ids")
    ap.add_argument("--max-bases", type=int, default=0)
    a = ap.parse_args(argv)
    unknown = [f for f in a.faults if f not in fb.FAULTS]
    if unknown:
        ap.error(f"unknown faults {unknown}; known: {list(fb.FAULTS)}")
    i, k = (int(x) for x in a.shard.split("/"))
    if not 0 <= i < k:
        ap.error("--shard must be i/k with 0 <= i < k")
    todo = [it for n, it in enumerate(items(a.split, a.faults, a.severities, a.bases, a.max_bases)) if n % k == i]
    if a.resume:
        seen = done_ids(a.out)
        todo = [(b, f, s) for b, f, s in todo if fb.instance_key(b["base_id"], f, s) not in seen]
    elif os.path.exists(a.out) and os.path.getsize(a.out):
        ap.error(f"{a.out} exists; use --resume (the file is append-only)")
    print(f"{len(todo)} instance(s) to build", flush=True)
    used, t0 = 0, time.time()
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "a", encoding="utf-8") as out:
        for n, (b, f, s) in enumerate(todo):
            if a.rollout_cap and used >= a.rollout_cap:
                print(f"rollout cap {a.rollout_cap} reached after {n} instances", flush=True)
                break
            rec = fb.build_instance(b, f, s, a.campaign, pool, budget=a.budget, n_train=a.n_train, n_check=a.n_check)
            rec["split"] = a.split
            used += rec["rollouts"]
            out.write(json.dumps(rec, sort_keys=True) + "\n")
            out.flush()
            print(f"[{n + 1}/{len(todo)}] {rec['instance_id']} valid={rec['valid']} kept={rec['kept']} "
                  f"rollouts={rec['rollouts']} total={used} t={time.time() - t0:.0f}s {rec.get('reason') or ''}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
