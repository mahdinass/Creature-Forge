"""Mechanism-Knowledge Value (MKV) study (phase 3, non-LLM): does knowing the mechanism add engineering value?

Within each instance every condition runs on a fresh bench with the SAME seeds, plant budget, twin budget and noise seed; the
conditions differ only in the mechanism information given to the same posterior-robust repair pipeline (belief_engine):
  K2  exact deviation (structure and parameters)
  K1  true structure; parameters identified by the engine from plant data (true structure's coarse grid + refinement)
  K3  wrong structure: the symptom-twin family's structure (twin pairs), else the engine's best wrong structure
  K0n nominal hypothesis (no deviation): the pipeline with no mechanism information
  K4  the engine's own inference from the generic library (= arm A1)
  K0  model-free procedure (A0 generic exhaustive), the strongest no-model engineer
Primary contrast proposed for registration: K1 vs K3 (correct vs wrong mechanism, identical pipeline and compute).
Development only until registered. Verification: full_recovery_v1 on the hidden plant (hdb_bench.verify).

Usage (VM): python scripts/hdb_mkv.py --bases 3 --severities mid --workers 6 --out artifacts/hdb/mkv_dev.jsonl
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import belief_engine as be                    # noqa: E402
from creature_forge import fault_bench as fb                      # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge import hdb_policies as pol                    # noqa: E402
from creature_forge.forge_pool import ForgePool, InlinePool       # noqa: E402
from creature_forge.hdb_workbench import HDBWorkbench             # noqa: E402
from creature_forge.optimize import jsonable                      # noqa: E402

CONDITIONS = ("K2", "K1", "K3", "K0n", "K4", "K0")


def structure_grid(structure, design_mass: float) -> list[list[dict]]:
    """The generic library's coarse magnitudes for one (kind, target) structure (falls back to the DSL range midpoints)."""
    (kind, target), = structure
    return [d for d in be.generic_particles(design_mass) if d and (d[0]["kind"], d[0]["target"]) == (kind, target)] or \
        [[{"kind": kind, "target": target, "params": {n: (lo + hi) / 2 for n, (lo, hi) in
                                                      __import__("creature_forge.hidden_plant", fromlist=["P"]).PRIMITIVES[kind]["params"].items()}}]]


def twin_structure(inst: dict):
    fam = inst["family"]
    pair = hb.FAMILIES[fam]["pair"]
    rivals = [f for f, s in hb.FAMILIES.items() if s["pair"] == pair and f != fam]
    if not rivals:
        return None
    dev = hb.deviation_for({"base_id": inst["base_id"], "body": inst["robot"]["body"]}, rivals[0], 0)
    return tuple(sorted((p["kind"], p["target"]) for p in dev))


def run_condition(inst: dict, cond: str, pool, a) -> dict:
    view = hb.policy_view(inst)
    bench = HDBWorkbench(view, inst["plant"], total_budget=a.budget, twin_budget=a.twin_budget, pool=pool,
                         noise_seed=int.from_bytes(inst["instance_id"].encode()[:4], "big") % (2 ** 31))
    t0 = time.perf_counter()
    info = {}
    if cond == "K0":
        info = pol.generic_exhaustive(bench)
    else:
        if cond == "K4":
            ep = be.Episode(bench)
        else:
            ep = be.Episode(bench, use_generic=False)
        if cond == "K2":
            fixed = [inst["plant"]["deviation"]]
        elif cond == "K1":
            fixed = structure_grid(tuple(sorted((p["kind"], p["target"]) for p in inst["plant"]["deviation"])), ep.design_mass)
        elif cond == "K3":
            ts = twin_structure(inst)
            fixed = structure_grid(ts, ep.design_mass) if ts else None
        else:   # K0n
            fixed = [[]]
        if cond == "K4":
            info["diagnosis"] = ep.diagnose(max_experiments=a.max_experiments)
        else:
            if fixed is None:
                return {"condition": cond, "skipped": "no symptom twin for this family"}
            ep.proposer = lambda state, f=fixed: f
            ep.refine_top = 1 if cond in ("K1", "K3") else 0
            info["diagnosis"] = ep.diagnose(max_experiments=a.max_experiments if cond in ("K1", "K3") else 0)
        info["repair"] = ep.robust_repair(twin_budget=a.twin_repair, plant_budget=a.plant_repair)
        info["engine"] = ep.record()
    design = bench.best_design()
    ver = hb.verify(inst, {"body": design["body"], "vector": design["vector"]}, pool=pool)
    return {"condition": cond, "status": ver["status"], "walking_frac": ver["validation"]["walking_frac"],
            "ledger": bench.ledger() if cond == "K0" else None, "info": info,
            "designs": [{k: d[k] for k in ("index", "source", "body", "vector")} for d in bench.designs],
            "submitted": design["index"], "wall_s": time.perf_counter() - t0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", type=int, default=3)
    ap.add_argument("--base-offset", type=int, default=0)
    ap.add_argument("--families", default=",".join(hb.FAMILIES))
    ap.add_argument("--severities", default="mid")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--budget", type=int, default=700)
    ap.add_argument("--twin-budget", type=int, default=2800)
    ap.add_argument("--twin-repair", type=int, default=400)
    ap.add_argument("--plant-repair", type=int, default=300)
    ap.add_argument("--max-experiments", type=int, default=4)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from hdb_vs_run import severities          # same severity selection rule as the VS runner
    k, n = (int(x) for x in a.shard.split("/"))
    bases = fb.load_bases("dev")[a.base_offset:a.base_offset + a.bases]
    todo = [(b, f, s) for b in bases for f in a.families.split(",") for s in severities(f, a.severities)][k::n]
    done = set()
    if os.path.exists(a.out):
        done = {(r["instance_id"], r["condition"]) for r in map(json.loads, open(a.out, encoding="utf-8")) if "condition" in r}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    with pool_cm as pool, open(a.out, "a", encoding="utf-8") as out:
        for b, f, s in todo:
            inst = hb.check_eligibility(hb.make_instance(b, f, s), pool=pool)
            if not inst["eligible"]:
                continue
            for cond in a.conditions.split(","):
                if (inst["instance_id"], cond) in done:
                    continue
                rec = {"version": "hdb_mkv_v1", "instance_id": inst["instance_id"], "family": f, "severity": s,
                       "provenance": "NO_AI", **run_condition(inst, cond, pool, a)}
                out.write(json.dumps(jsonable(rec)) + "\n")
                out.flush()
                print(inst["instance_id"], cond, rec.get("status"), rec.get("skipped"), round(rec.get("wall_s", 0)), flush=True)


if __name__ == "__main__":
    main()
