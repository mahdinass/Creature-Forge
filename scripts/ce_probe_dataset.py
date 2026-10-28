"""Probe dataset for experience learning (Levels B/C): what the instruments show for each fault-bench instance.

    python scripts/ce_probe_dataset.py --instances <fault_bench jsonl ...> --out <jsonl> [--workers 6] [--shard i/k] [--resume]

For every valid instance WITH a measured repair matrix (kept or not): the initial observation of the faulty robot on its own obs
seeds (n_obs = 4, the same observation a policy pays for) and the response to every available entry of the fixed counterfactual
catalogue (`eng_tools.COUNTERFACTUALS`, each on the same obs seeds), through `eng_tools.Workbench` (budget-exact ledger).

Output rows carry `instance_id` only for joining with the instance file; the learning inputs are the observation, the responses,
the body features and the measured repair matrix. Fault labels stay in the instance file and are used only for scoring. Run on the VM.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import eng_tools  # noqa: E402
from creature_forge.forge_pool import ForgePool  # noqa: E402

VERSION = "ce_probe_dataset_v1"
N_OBS = 4


def _compact(obs: dict) -> dict:
    per = [{k: p.get(k) for k in ("seed", "walking", "fell", "label", "fall_direction", "fall_time", "time_upright")}
           for p in obs.get("per_seed") or []]
    return {"median": obs.get("median"), "pre_fall_median": obs.get("pre_fall_median"), "n_walking": obs.get("n_walking"),
            "n_fell": obs.get("n_fell"), "per_seed": per, "errors": obs.get("errors")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    i_sh, k_sh = (int(x) for x in a.shard.split("/"))
    insts = []
    for p in a.instances:
        with open(p, encoding="utf-8") as fh:
            insts += [json.loads(l) for l in fh if l.strip()]
    insts = sorted((r for r in insts if r.get("valid") and r.get("repair_matrix")), key=lambda r: r["instance_id"])
    insts = [r for j, r in enumerate(insts) if j % k_sh == i_sh]
    done = set()
    if a.resume and os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as fh:
            done = {json.loads(l)["instance_id"] for l in fh if l.strip()}
    print(f"{len(insts)} instance(s); {len(done)} done", flush=True)
    t0, total = time.time(), 0
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "a", encoding="utf-8") as out:
        for n, inst in enumerate(insts, 1):
            if inst["instance_id"] in done:
                continue
            seeds = inst["seeds"]
            bench = eng_tools.Workbench(inst["robot"], total_budget=N_OBS * (2 + len(eng_tools.COUNTERFACTUALS)), seeds=seeds,
                                        pool=pool, n_train=4, n_obs=N_OBS)
            r0 = bench.observe()
            row = {"version": VERSION, "instance_id": inst["instance_id"], "base_id": inst["base_id"], "region": inst["region"],
                   "features": inst["features"], "robot": inst["robot"], "repair_matrix": inst["repair_matrix"],
                   "observation": _compact(r0["observation"]), "counterfactuals": {}}
            for cid in eng_tools.COUNTERFACTUALS:
                res = bench.counterfactual(cid)
                if res.get("ok"):
                    row["counterfactuals"][cid] = {"observation": _compact(res["observation"]), "deltas": res["deltas_vs_current"]}
                else:
                    row["counterfactuals"][cid] = {"refused": res.get("refused")}
            led = bench.ledger()
            row["rollouts"] = led["used"]
            total += led["used"]
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(f"[{n}/{len(insts)}] used={led['used']} total={total} t={time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
