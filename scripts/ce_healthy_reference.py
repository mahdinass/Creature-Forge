"""Healthy-walker reference for the physics digest (`creature_forge/physics_digest.py`).

    python scripts/ce_healthy_reference.py --out experiments/causal_engineer/dev/healthy_reference.json [--workers 6] [--n-seeds 8]

Observes every verified-walking DEV base robot (`fault_bench.load_bases("dev")`, unmodified, no fault) with `physics_probe.observe`
on its own "probe"-role seed block of the namespace "ce-healthy-ref" (the validate / confirm roles occupy other seed ranges, so
these seeds can never be verification seeds), takes each robot's medians and derived quantities, and writes p10 / median / p90 over robots per quantity. Held-out bases
are never used. Run on the VM (MuJoCo).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import creature_gen as cg  # noqa: E402
from creature_forge import fault_bench as fb  # noqa: E402
from creature_forge import physics_digest as pd  # noqa: E402
from creature_forge.forge_pool import ForgePool  # noqa: E402
from creature_forge.physics_probe import observe  # noqa: E402

NAMESPACE = "ce-healthy-ref"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--n-seeds", type=int, default=8)
    a = ap.parse_args()
    bases = fb.load_bases("dev")
    per_robot, vals = [], {k: [] for k in pd.DIGEST_KEYS + pd.DERIVED_KEYS}
    t0 = time.time()
    with ForgePool(max_workers=a.workers) as pool:
        for b in bases:
            seeds = list(cg.walkrec_seed_block(NAMESPACE, "probe", b["base_id"], a.n_seeds))
            obs = observe(b["body"], b["vector"], seeds, pool=pool)
            d = pd.derived(obs, b["body"], b["vector"])
            row = {"robot": f"healthy-{len(per_robot):02d}", "n_walking": obs["n_walking"], "n_fell": obs["n_fell"],
                   "errors": len(obs["errors"]), "median": {k: obs["median"].get(k) for k in pd.DIGEST_KEYS},
                   "derived": {k: d.get(k) for k in pd.DERIVED_KEYS}}
            per_robot.append(row)
            for k in pd.DIGEST_KEYS:
                vals[k].append(obs["median"].get(k))
            for k in pd.DERIVED_KEYS:
                vals[k].append(d.get(k))
            print(f"[{len(per_robot)}/{len(bases)}] walking {obs['n_walking']}/{len(seeds)} t={time.time() - t0:.0f}s", flush=True)
    out = {"version": pd.VERSION, "source": "verified-walking dev base robots, unmodified, variation preset, 10 s rollouts",
           "namespace": NAMESPACE, "n_seeds_per_robot": a.n_seeds, "n_robots": len(per_robot),
           "quantities": pd.reference_stats(vals), "per_robot": per_robot}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("wrote", a.out, "rollouts", len(bases) * a.n_seeds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
