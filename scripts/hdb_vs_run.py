"""Vertical-slice runner (phase 3): Hidden-Damage Bench episodes with the belief engine (arm A1 engine-only, or with a proposer).

hidden damage -> competing executable hypotheses -> discriminating experiment -> updated belief -> intervention -> independent
verification (full_recovery_v1 on the hidden plant). Development only; nothing here is a registered comparison.

Usage (VM): python scripts/hdb_vs_run.py --bases 3 --families pitch_sensor_bias,payload_offset,low_ground_friction,short_feet
            --severities mid,max --workers 8 --out artifacts/hdb/vs_a1.jsonl [--proposer mock] [--smoke]
Appends one JSON line per instance (resumable with --resume: instance ids already in --out are skipped).
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
from creature_forge.forge_pool import ForgePool, InlinePool       # noqa: E402
from creature_forge.hdb_workbench import HDBWorkbench             # noqa: E402
from creature_forge.optimize import jsonable                      # noqa: E402


def mock_proposer(state: dict) -> list:
    """SCRIPTED_MOCK proposer (labelled; never counted as LIVE): fixed residual-to-hypothesis rules, no knowledge of the bench."""
    out = []
    for r in state.get("residuals_of_map", {}).values():
        if not isinstance(r, dict):
            continue
        if abs(r.get("slip_fraction", 0.0)) > 1.0:
            out.append([{"kind": "contact_friction", "target": "feet", "params": {"factor": 0.25}}])
        if abs(r.get("pitch_mean", 0.0)) > 1.0:
            s = 1.0 if r["pitch_mean"] > 0 else -1.0
            out.append([{"kind": "sensor_bias", "target": "pitch", "params": {"rad": -0.1 * s}}])
            out.append([{"kind": "payload", "target": "torso", "params": {"mass_kg": 3.0, "x_m": 0.1 * s}}])
    return out


def severities(family: str, which: str) -> list[int]:
    n = hb.severity_count(family)
    pick = {"mid": [n // 2], "max": [n - 1], "min": [0], "all": list(range(n))}
    out = []
    for w in which.split(","):
        out += pick[w]
    return sorted(set(out))


def run_one(inst: dict, pool, a) -> dict:
    t0 = time.perf_counter()
    view = hb.policy_view(inst)
    bench = HDBWorkbench(view, inst["plant"], total_budget=a.budget, twin_budget=a.twin_budget, pool=pool,
                         noise_seed=int.from_bytes(inst["instance_id"].encode()[:4], "big") % (2 ** 31))
    proposer = mock_proposer if a.proposer == "mock" else None
    kinds = ("contact_friction", "segment_length", "sensor_bias", "payload") if a.smoke else None
    ep = be.Episode(bench, proposer=proposer, use_generic=not a.no_generic, max_alive=a.max_alive, generic_kinds=kinds)
    diag = ep.diagnose(max_experiments=a.max_experiments)
    rep = ep.robust_repair(twin_budget=a.twin_repair, plant_budget=a.plant_repair)
    design = bench.best_design()
    ver = hb.verify(inst, {"body": design["body"], "vector": design["vector"]}, pool=pool)
    inj = [list(x) for x in hb.mechanism_signature(inst)]
    sp = ep.structure_posterior()
    mass_inj = sum(w for s, w in sp if [list(x) for x in s] == inj)
    return jsonable({
        "version": "hdb_vs_v1", "instance_id": inst["instance_id"], "family": inst["family"], "pair": inst["pair"],
        "severity": inst["severity"], "provenance": "SCRIPTED_MOCK" if a.proposer == "mock" else "NO_AI",
        "arm": "A1" if a.proposer is None else "A1+mock", "check": inst["check"],
        "injected_structure": inj, "map_structure": diag["map_structure"], "map_mass": diag["map_mass"],
        "posterior_mass_on_injected": mass_inj, "repair": rep,
        "verification": {"status": ver["status"], "walking_frac": ver["validation"]["walking_frac"], "reasons": ver["reasons"],
                         "rollouts": ver["rollouts"]},
        "engine": ep.record(), "designs": [{k: d[k] for k in ("index", "source", "body", "vector")} for d in bench.designs],
        "wall_s": time.perf_counter() - t0})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--bases", type=int, default=3)
    ap.add_argument("--base-offset", type=int, default=0)
    ap.add_argument("--families", default=",".join(hb.FAMILIES))
    ap.add_argument("--severities", default="mid,max")
    ap.add_argument("--budget", type=int, default=700)
    ap.add_argument("--twin-budget", type=int, default=2800)
    ap.add_argument("--twin-repair", type=int, default=800)
    ap.add_argument("--plant-repair", type=int, default=300)
    ap.add_argument("--max-alive", type=int, default=12)
    ap.add_argument("--max-experiments", type=int, default=6)
    ap.add_argument("--proposer", choices=["mock"], default=None)
    ap.add_argument("--no-generic", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    k, n = (int(x) for x in a.shard.split("/"))
    bases = fb.load_bases(a.split)[a.base_offset:a.base_offset + a.bases]
    todo = [(b, f, s) for b in bases for f in a.families.split(",") for s in severities(f, a.severities)]
    todo = todo[k::n]
    done = set()
    if a.resume and os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as fh:
            done = {json.loads(l)["instance_id"] for l in fh if l.strip()}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    with pool_cm as pool, open(a.out, "a", encoding="utf-8") as out:
        for b, f, s in todo:
            iid = hb.instance_key(b["base_id"], f, s)
            if iid in done:
                continue
            inst = hb.check_eligibility(hb.make_instance(b, f, s), pool=pool)
            if not inst["eligible"]:
                rec = {"version": "hdb_vs_v1", "instance_id": iid, "family": f, "severity": s, "eligible": False,
                       "reason": inst["reason"], "check": inst["check"]}
            else:
                rec = run_one(inst, pool, a)
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(iid, rec.get("map_structure"), round(rec.get("posterior_mass_on_injected", 0) or 0, 3),
                  (rec.get("verification") or {}).get("status"), rec.get("reason"), flush=True)


if __name__ == "__main__":
    main()
