"""E-1 arm runner (docs/E1_PROTOCOL.md): runs one arm over a fixed instance file, one JSON line per instance (resumable).

Arms (identical instruments: plant budget 700, twin budget 2,800, the instance's seeds and noise seed):
  A0   generic exhaustive (hdb_policies.generic_exhaustive)                    = hdb_vs_run.run_a0
  A1   belief engine v5 + calibrated stopping (stop map, tau)                  = hdb_vs_run.run_one(arm="A1"), i.e. A1c5
  K0n  the same engine and repair pipeline with the nominal hypothesis only    (no diagnosis; MKV K0n with A1's stop rule)
The arms never see the plant, family, severity, check results or verification seeds (hdb_bench.policy_view).

Usage (VM): python scripts/e1_run.py --arm A1 --instances <instances.jsonl> --stop-model <stopmap.json> --workers 7
            --shard 0/9 --out <dir>/A1_s0.jsonl [--resume]
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from creature_forge import belief_engine as be                    # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge.forge_pool import ForgePool, InlinePool       # noqa: E402
from creature_forge.hdb_workbench import HDBWorkbench             # noqa: E402
from creature_forge.optimize import jsonable                      # noqa: E402
import hdb_vs_run as vs                                           # noqa: E402

ARMS = ("A0", "A1", "K0n")
VERSION = "e1_run_v1"
# Fresh-dev A1c5 settings (hdb_vs_run defaults; experiments/causal_engineer/dev/hdb/ARMS_fresh_dev_9families.md)
DEFAULTS = {"budget": 700, "twin_budget": 2800, "twin_repair": 800, "plant_repair": 300, "max_alive": 12,
            "max_experiments": 6, "tau": 0.75}


def settings(arm: str, stop_model: str | None) -> types.SimpleNamespace:
    if arm in ("A1", "K0n") and not stop_model:
        raise SystemExit(f"arm {arm} needs --stop-model (the frozen dev stop map)")
    return types.SimpleNamespace(**DEFAULTS, arm="A1" if arm == "A1" else arm, proposer=None, source="live", smoke=False,
                                 no_generic=False, stop_model=stop_model)


def noise_seed(inst: dict) -> int:
    return int.from_bytes(inst["instance_id"].encode()[:4], "big") % (2 ** 31)


def run_k0n(inst: dict, pool, a) -> dict:
    """Engine pipeline with the nominal hypothesis only (hdb_mkv K0n), calibrated stopping as in A1."""
    t0 = time.perf_counter()
    view = hb.policy_view(inst)
    bench = HDBWorkbench(view, inst["plant"], total_budget=a.budget, twin_budget=a.twin_budget, pool=pool,
                         noise_seed=noise_seed(inst))
    ep = be.Episode(bench, use_generic=False, max_alive=a.max_alive)
    ep.proposer = lambda state: [[]]
    ep.refine_top = 0
    diag = ep.diagnose(max_experiments=0)
    rep = ep.robust_repair(twin_budget=a.twin_repair, plant_budget=a.plant_repair, accept_fn=vs.stop_rule(a))
    design = bench.best_design()
    ver = hb.verify(inst, {"body": design["body"], "vector": design["vector"]}, pool=pool)
    return jsonable({
        "version": "hdb_vs_v1", "instance_id": inst["instance_id"], "family": inst["family"], "pair": inst["pair"],
        "severity": inst["severity"], "bench": inst["version"], "strength": inst.get("strength"), "mult": inst.get("mult"),
        "provenance": "NO_AI", "arm": "K0n", "check": inst["check"], "map_structure": diag.get("map_structure"),
        "repair": rep,
        "verification": {"status": ver["status"], "walking_frac": ver["validation"]["walking_frac"], "reasons": ver["reasons"],
                         "rollouts": ver["rollouts"]},
        "stop_rule": {"model": a.stop_model, "tau": a.tau}, "engine": ep.record(),
        "designs": [{k: d[k] for k in ("index", "source", "body", "vector")} for d in bench.designs],
        "submitted": design["index"], "wall_s": time.perf_counter() - t0})


def run_arm(arm: str, inst: dict, pool, a) -> dict:
    if arm == "A0":
        view = hb.policy_view(inst)
        bench = HDBWorkbench(view, inst["plant"], total_budget=a.budget, twin_budget=a.twin_budget, pool=pool,
                             noise_seed=noise_seed(inst))
        return vs.run_a0(inst, bench, pool, time.perf_counter())
    if arm == "A1":
        return vs.run_one(inst, pool, a)
    if arm == "K0n":
        return run_k0n(inst, pool, a)
    raise ValueError(arm)


def file_sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_instances(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    ids = [r["instance_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate instance ids in the instance file")
    if not all(r.get("eligible") for r in rows):
        raise SystemExit("the instance file must contain eligible instances only")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--instances", required=True)
    ap.add_argument("--stop-model", default=None)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", required=True)
    a_cli = ap.parse_args()
    k, n = (int(x) for x in a_cli.shard.split("/"))
    a = settings(a_cli.arm, a_cli.stop_model)
    insts = load_instances(a_cli.instances)[k::n]
    meta = {"e1": VERSION, "instances_sha256": file_sha(a_cli.instances),
            "stop_model_sha256": file_sha(a_cli.stop_model) if a_cli.stop_model else None}
    done = set()
    if a_cli.resume and os.path.exists(a_cli.out):
        with open(a_cli.out, encoding="utf-8") as fh:
            done = {json.loads(l)["instance_id"] for l in fh if l.strip()}
    os.makedirs(os.path.dirname(os.path.abspath(a_cli.out)), exist_ok=True)
    pool_cm = ForgePool(max_workers=a_cli.workers) if a_cli.workers else contextlib.nullcontext(InlinePool())
    with pool_cm as pool, open(a_cli.out, "a", encoding="utf-8") as out:
        for inst in insts:
            if inst["instance_id"] in done:
                continue
            rec = {**run_arm(a_cli.arm, inst, pool, a), **meta, "stratum": inst.get("stratum"), "base_id": inst["base_id"]}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(a_cli.arm, inst["instance_id"], rec["verification"]["status"], round(rec["wall_s"]), flush=True)


if __name__ == "__main__":
    main()
