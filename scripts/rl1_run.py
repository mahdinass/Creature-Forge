"""RL-1 online arm runner (docs/RL1_PLAN.md §5.2 dev test; reused by the registered E-2). One JSON line per instance.

Arms (identical to A1c5 in everything except the order in which the engine's robust repair tries tools; plant budget 700,
twin budget 2,800, the same seeds, noise seed and calibrated stop rule):
  A1    belief engine v5 + calibrated stopping (e1_run arm A1)
  A1S   + simple repair memory (P-mem0: tools that verified on the 5 nearest past cases)
  A1M   + RL-1 repair memory (calibrated memory + twin evidence, abstain / commit / hedge)
The memory acts through belief_engine's `ranker` hook, AFTER the engine's own tool screens (same twin compute as A1), and
only reorders tools. `--model` is a repair_memory model JSON, or {"by_family": {family: model}} for leave-one-family-out dev
tests (the family only selects which training data are excluded; it is never a model input).

Usage (VM): python scripts/rl1_run.py --arm A1M --instances <instances.jsonl> --model <model.json> --stop-model <map>
            --workers 6 --shard k/n --out <file> [--resume]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from creature_forge import belief_engine as be                    # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge import repair_memory as rm                    # noqa: E402
from creature_forge.forge_pool import ForgePool, InlinePool       # noqa: E402
from creature_forge.hdb_workbench import HDBWorkbench             # noqa: E402
from creature_forge.optimize import jsonable                      # noqa: E402
import e1_run                                                     # noqa: E402
import hdb_vs_run as vs                                           # noqa: E402

ARMS = ("A1", "A1S", "A1M", "A1I")   # A1I: identity ranker (equivalence gate: must reproduce A1 exactly)
VERSION = "rl1_run_v1"


def identity_ranker(ep, hyps, ranking):
    return ranking


def make_ranker(model: dict, simple: bool, trace: list):
    def ranker(ep, hyps, ranking):
        rec = {"engine": ep.record()}
        nominal = ep.b.designs[0]["body"]
        dec = rm.apply_simple(model, rec, nominal) if simple else rm.apply(model, rec, nominal)
        by_tool = {r["tool"]: r for r in ranking}
        new = [by_tool.get(t, {"tool": t, "probe": None, "score": None, "from": "memory"}) for t in dec["order"]]
        info = {"mode": dec["mode"], "order": dec["order"][:4], "engine_order": [r["tool"] for r in ranking][:4]}
        if not simple:
            info.update(n_eff=round(dec["n_eff"], 4), d_min=round(dec["d_min"], 4),
                        P_top={t: round(dec["P"][t], 4) for t in dec["order"][:3]})
        ep._event("repair_memory", **info)
        trace.append(info)
        return new
    return ranker


def run_memory_arm(inst: dict, pool, a, model: dict | None, simple: bool, identity: bool = False) -> dict:
    """hdb_vs_run.run_one (arm A1) with the memory ranker; the record schema is the same plus `repair_memory`."""
    t0 = time.perf_counter()
    view = hb.policy_view(inst)
    bench = HDBWorkbench(view, inst["plant"], total_budget=a.budget, twin_budget=a.twin_budget, pool=pool,
                         noise_seed=e1_run.noise_seed(inst))
    ep = be.Episode(bench, proposer=None, use_generic=True, max_alive=a.max_alive)
    diag = ep.diagnose(max_experiments=a.max_experiments)
    trace: list = []
    rep = ep.robust_repair(twin_budget=a.twin_repair, plant_budget=a.plant_repair, accept_fn=vs.stop_rule(a),
                           ranker=identity_ranker if identity else make_ranker(model, simple, trace))
    design = bench.best_design()
    ver = hb.verify(inst, {"body": design["body"], "vector": design["vector"]}, pool=pool)
    return jsonable({
        "version": "hdb_vs_v1", "instance_id": inst["instance_id"], "family": inst["family"], "pair": inst["pair"],
        "severity": inst["severity"], "bench": inst["version"], "strength": inst.get("strength"), "mult": inst.get("mult"),
        "provenance": "NO_AI", "arm": "A1I" if identity else ("A1S" if simple else "A1M"), "check": inst["check"],
        "injected_structure": [list(x) for x in hb.mechanism_signature(inst)], "map_structure": diag["map_structure"],
        "map_mass": diag["map_mass"], "repair": rep, "repair_memory": trace,
        "verification": {"status": ver["status"], "walking_frac": ver["validation"]["walking_frac"], "reasons": ver["reasons"],
                         "rollouts": ver["rollouts"]},
        "stop_rule": {"model": a.stop_model, "tau": a.tau}, "engine": ep.record(),
        "designs": [{k: d[k] for k in ("index", "source", "body", "vector")} for d in bench.designs],
        "wall_s": time.perf_counter() - t0})


def pick_model(models: dict, inst: dict) -> dict:
    return models["by_family"][inst["family"]] if "by_family" in models else models


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--instances", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--stop-model", required=True)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", required=True)
    c = ap.parse_args()
    if c.arm in ("A1S", "A1M") and not c.model:
        raise SystemExit("memory arms need --model")
    k, n = (int(x) for x in c.shard.split("/"))
    a = e1_run.settings("A1", c.stop_model)
    insts = e1_run.load_instances(c.instances)[k::n]
    models = json.load(open(c.model, encoding="utf-8")) if c.model else None
    meta = {"rl1": VERSION, "instances_sha256": e1_run.file_sha(c.instances),
            "model_sha256": e1_run.file_sha(c.model) if c.model else None, "stop_model_sha256": e1_run.file_sha(c.stop_model)}
    done = set()
    if c.resume and os.path.exists(c.out):
        done = {json.loads(l)["instance_id"] for l in open(c.out, encoding="utf-8") if l.strip()}
    os.makedirs(os.path.dirname(os.path.abspath(c.out)), exist_ok=True)
    pool_cm = ForgePool(max_workers=c.workers) if c.workers else contextlib.nullcontext(InlinePool())
    with pool_cm as pool, open(c.out, "a", encoding="utf-8") as out:
        for inst in insts:
            if inst["instance_id"] in done:
                continue
            if c.arm == "A1":
                rec = e1_run.run_arm("A1", inst, pool, a)
            elif c.arm == "A1I":
                rec = run_memory_arm(inst, pool, a, None, simple=False, identity=True)
            else:
                rec = run_memory_arm(inst, pool, a, pick_model(models, inst), simple=(c.arm == "A1S"))
            rec = {**rec, **meta, "stratum": inst.get("stratum"), "base_id": inst["base_id"]}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(c.arm, inst["instance_id"], rec["verification"]["status"], round(rec["wall_s"]), flush=True)


if __name__ == "__main__":
    main()
