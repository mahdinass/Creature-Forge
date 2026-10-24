"""RL-1 repair response matrix (dev only; docs/RL1_PLAN.md §3). For each dev instance and EVERY repair tool: a plant-only CMA
repair in that tool's subspace from the nominal design at a fixed budget, then the independent verification
(full_recovery_v1 on the hidden plant). The full matrix (no missing-not-at-random rows: every tool is tried on every
instance) is the training and offline-evaluation data for repair learning. The policy-visible context of each instance comes
from the stored A1c5 record of the same instance (identical engine diagnosis; G-R shows it reproduces exactly).

Never touches the sealed test side: instances are rebuilt from the dev bases and dev thresholds, ids taken from the stored
fresh-dev A1c5 file.

Usage (VM): python scripts/rl1_matrix.py --records artifacts/hdb/fresh_A1c5.jsonl --thresholds artifacts/hdb/thresholds_dev.json
            --budget 300 --workers 7 --shard k/K --out artifacts/rl1/matrix_sK.jsonl [--resume]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import fault_bench as fb                      # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge.forge_pool import ForgePool                   # noqa: E402
from creature_forge.hdb_workbench import HDBWorkbench             # noqa: E402

VERSION = "rl1_matrix_v1"
N_TRAIN = 4


def noise_seed(iid: str) -> int:
    return int.from_bytes(iid.encode()[:4], "big") % (2 ** 31)


def repair_job(args) -> dict:
    """One (instance, tool) cell, inline (runs inside a pool worker)."""
    inst, tool, budget = args
    t0 = time.perf_counter()
    bench = HDBWorkbench(hb.policy_view(inst), inst["plant"], total_budget=budget, twin_budget=0, pool=None,
                         noise_seed=noise_seed(inst["instance_id"]))
    rep = bench.repair(tool, budget, n_train=N_TRAIN)
    out = {"version": VERSION, "instance_id": inst["instance_id"], "family": inst["family"], "base_id": inst["base_id"],
           "mult": inst.get("mult"), "tool": tool, "budget": budget, "ok": bool(rep.get("ok"))}
    if not rep.get("ok"):
        out.update(refused=rep.get("refused"), status=None, walking_frac=None)
    else:
        d = bench.best_design()
        ver = hb.verify(inst, {"body": d["body"], "vector": d["vector"]})
        out.update(train_walking=(rep.get("best") or {}).get("train_walking"), plant_used=bench.ledger()["used"],
                   status=ver["status"], walking_frac=ver["validation"]["walking_frac"],
                   design={"body": d["body"], "vector": d["vector"]})
    out["wall_s"] = time.perf_counter() - t0
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--budget", type=int, default=300)
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    k, n = (int(x) for x in a.shard.split("/"))
    ids = [r["instance_id"] for r in map(json.loads, open(a.records, encoding="utf-8")) if r.get("verification")][k::n]
    th = json.load(open(a.thresholds, encoding="utf-8"))
    bases = {b["base_id"]: b for b in hb.load_bases("dev")}
    done = set()
    if a.resume and os.path.exists(a.out):
        done = {(r["instance_id"], r["tool"]) for r in map(json.loads, open(a.out, encoding="utf-8"))}
    jobs = []
    for iid in ids:
        base_id, fam, sev = iid.rsplit(":", 2)
        inst = hb.check_eligibility(hb.make_instance_v2(bases[base_id], fam, int(sev), th))
        if not inst["eligible"]:
            raise SystemExit(f"{iid} is no longer eligible: {inst['reason']}")
        jobs += [(inst, t, a.budget) for t in fb.TOOLS if (iid, t) not in done]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "a", encoding="utf-8") as fh:
        for i, r in pool.imap(repair_job, jobs):
            if isinstance(r, tuple):
                r = {"version": VERSION, "instance_id": jobs[i][0]["instance_id"], "tool": jobs[i][1], "error": str(r[1])[:500]}
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            print(r["instance_id"], r["tool"], r.get("status"), r.get("error", ""), flush=True)


if __name__ == "__main__":
    main()
