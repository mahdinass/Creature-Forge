"""DI-1 bounded engineering pilot. Never loads sealed cohorts or prior outcomes.

prepare reads only nominal designs from an explicitly named development file.
The pilot is not the registered prospective scientific evaluation.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from r0_experiment import write_new

CAMPAIGN = "di1-pilot-20261025-v1"


def sha(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def science(x):
    if isinstance(x, dict):
        return {k: science(v) for k, v in x.items() if k not in ("wall_s", "elapsed_s")}
    if isinstance(x, list):
        return [science(v) for v in x]
    return x


def prepare(source, output):
    parents = {}
    for line in Path(source).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if not r.get("designs"):
            continue
        key = r["instance_id"].split(":")[0]
        d = r["designs"][0]
        parents[key] = {"body": d["body"], "vector": d["vector"]}
    if len(parents) != 18:
        raise ValueError("requires the explicit 18-base fresh development source")
    old = {sha(d["body"]) for d in parents.values()}
    bases = []
    for i in range(8):
        rng = random.Random(f"{CAMPAIGN}:morphology:{i}")
        parent = sorted(parents)[rng.randrange(len(parents))]
        d = parents[parent]
        body = json.loads(json.dumps(d["body"]))
        # Independent unrounded draws, ±3%, symmetric scaling per leg field.
        for k in ("torso_mass", "thigh_length", "shank_length", "foot_length", "foot_friction", "torque_limit", "leg_density"):
            factor = rng.uniform(.97, 1.03)
            body[k] *= factor
            if k + "_r" in body and body[k + "_r"] is not None:
                body[k + "_r"] *= factor
        if sha(body) in old:
            raise ValueError("new morphology duplicates a prior base")
        old.add(sha(body))
        bases.append({"base_id": f"{CAMPAIGN}-{i:03d}", "parent_dev_base": parent,
                      "body": body, "vector": d["vector"], "generator_index": i})
    write_new(output, {"campaign": CAMPAIGN, "purpose": "engineering-only; excluded from future evaluation",
                       "source_sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                       "parent_designs": parents, "bases": bases, "generation_seed": CAMPAIGN,
                       "arms": ["baseline", "raw_eig", "random"], "plant_cap": 700, "twin_cap": 2800,
                       "attempts": 8, "replacement": False, "nominal_check": "at least 7/8 walking, no errors",
                       "fault": "index cycles dev FAMILY_SPECS, first variant, 1.3 times six-step failure threshold",
                       "candidate_sampling": "all legal first-decision probes; random arm uniform among nonbaseline probes",
                       "equivalence": "original versus instrumented full baseline on every eligible pilot base"})


def choose(scored, mode, key, *, include_original=False):
    if mode == "baseline":
        return scored[0][2], 1.0
    if mode == "raw_eig":
        return max(scored, key=lambda t: t[1])[2], 1.0
    others = [t[2] for t in scored if include_original or t[2]["id"] != scored[0][2]["id"]]
    if not others:
        return scored[0][2], 1.0
    return random.Random(f"{CAMPAIGN}:choice:{key}").choice(others), 1 / len(others)


def run_path(inst, mode, pool, stop_model, trace_path=None, *, force_first=False):
    from creature_forge import belief_engine as be, hdb_bench as hb
    from creature_forge.hdb_workbench import HDBWorkbench
    from creature_forge.decision_trace import Journal, instrument, verify_journal, snapshot, plain
    bench = HDBWorkbench(hb.policy_view(inst), inst["plant"], total_budget=700, twin_budget=2800, pool=pool,
                         noise_seed=int.from_bytes(inst["instance_id"].encode()[:4], "big") % (2**31))
    ep = be.Episode(bench, max_alive=12)
    journal = Journal(trace_path) if trace_path else None
    cm = instrument(ep, journal) if journal else contextlib.nullcontext()
    first = None
    t0 = time.perf_counter()
    try:
        with cm:
            ep.start()
            for step in range(6):
                would_stop = ep.diagnosis_done(.9)
                forced = force_first and step == 0 and mode != "baseline" and would_stop
                if would_stop and not forced:
                    break
                origin = plain(snapshot(ep)) if step == 0 else None
                ranked = ep.rank_experiments()
                if not ranked:
                    break
                pick, probability = choose(ranked, mode if step == 0 else "baseline", inst["base_id"],
                                           include_original=forced)
                if step == 0:
                    first = plain({"state": snapshot(ep), "candidates": ranked, "selected": pick,
                                   "inclusion_probability": probability, "policy": mode})
                    if force_first:
                        first.update(origin_state=origin, baseline_would_stop=would_stop, forced=forced)
                    if journal:
                        journal.emit("panel_frozen_before_plant", **first)
                ep.experiment_step(pick, by="eig" if mode == "baseline" or step else mode, scored=ranked)
            rep = ep.robust_repair(twin_budget=800, plant_budget=300,
                                   accept_fn=be.calibrated_accept(stop_model, .75))
            result = plain({"diagnosis": ep.diagnosis_summary(), "repair": rep, "engine": ep.record(),
                            "designs": bench.designs, "selected": bench.best_design(), "ledger": bench.ledger()})
    finally:
        if journal:
            journal.close()
    policy_s = time.perf_counter() - t0
    # Verification is trusted research evaluation, never policy input.
    ver = hb.verify(inst, result["selected"], pool=pool)
    return {"scientific": science(result), "first_decision": first, "verification": science(ver),
            "policy_wall_s": policy_s, "wall_s": time.perf_counter() - t0,
            "trace_integrity": verify_journal(trace_path) if trace_path else None}


def run(a):
    from creature_forge import hdb_bench as hb, hidden_plant as hp
    from creature_forge.forge_pool import ForgePool
    from creature_forge.decision_trace import plain
    cfg = json.loads(Path(a.config).read_text())
    base = cfg["bases"][a.index]
    out = Path(a.out) / base["base_id"]
    out.mkdir(parents=True, exist_ok=True)
    stop = json.loads(Path(a.stop_model).read_text())
    t0 = time.perf_counter()
    with ForgePool(max_workers=6) as pool:
        ns = hb.instance_seeds(base["base_id"], "nominal", 0, campaign=CAMPAIGN)["check"]
        nominal = hp.walk_seeds({}, base["body"], base["vector"], ns, pool=pool)
        write_new(out / "nominal.json", {"base": base, "seeds": ns, "rows": nominal})
        if any(not r.get("ok") for r in nominal) or sum(r["walking"] for r in nominal) < 7:
            write_new(out / "complete.json", {"base_id": base["base_id"], "eligible": False,
                      "reason": "nominal qualification", "wall_s": time.perf_counter()-t0})
            return
        family = list(hb.FAMILY_SPECS)[a.index % len(hb.FAMILY_SPECS)]
        variant = next(iter(hb.FAMILY_SPECS[family]["variants"]))
        th = hb.threshold(base, family, variant, pool=pool)
        write_new(out / "threshold.json", th)
        raw = hb.make_instance_v2(base, family, 1, {f"{base['base_id']}|{family}|{variant}": th})
        if raw is None:
            write_new(out / "complete.json", {"base_id": base["base_id"], "eligible": False,
                      "reason": "no legal 1.3 threshold fault", "wall_s": time.perf_counter()-t0})
            return
        raw["seeds"] = hb.instance_seeds(base["base_id"], family, 1, campaign=CAMPAIGN)
        hb.assert_disjoint(raw["seeds"])
        inst = hb.check_eligibility(raw, pool=pool)
        write_new(out / "instance.json", inst)
        if not inst["eligible"]:
            write_new(out / "complete.json", {"base_id": base["base_id"], "eligible": False,
                      "reason": inst["reason"], "wall_s": time.perf_counter()-t0})
            return
        original = run_path(inst, "baseline", pool, stop)
        write_new(out / "uninstrumented.json", original)
        records = {}
        for mode in cfg["arms"]:
            rec = run_path(inst, mode, pool, stop, out / f"{mode}.jsonl")
            write_new(out / f"{mode}.json", rec)
            records[mode] = {"status": rec["verification"]["status"], "wall_s": rec["wall_s"],
                             "plant_used": rec["scientific"]["ledger"]["used"],
                             "twin_used": rec["scientific"]["ledger"]["twin"]["used"],
                             "probe": (rec["first_decision"] or {}).get("selected", {}).get("id")}
            if original is not None and mode == "baseline":
                equal = original["scientific"] == rec["scientific"] and original["verification"] == rec["verification"]
                write_new(out / "equivalence.json", {"equal": equal,
                          "original_sha": sha([original["scientific"], original["verification"]]),
                          "instrumented_sha": sha([rec["scientific"], rec["verification"]])})
                if not equal:
                    raise RuntimeError("baseline scientific equivalence failed; stop before alternatives")
        write_new(out / "complete.json", {"base_id": base["base_id"], "eligible": True, "arms": records,
                  "wall_s": time.perf_counter()-t0})
        print(json.dumps({"index": a.index, "arms": records}), flush=True)


def main():
    p = argparse.ArgumentParser(__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("prepare"); q.add_argument("--source", required=True); q.add_argument("--output", required=True)
    q = sub.add_parser("run"); q.add_argument("--config", required=True); q.add_argument("--index", type=int, required=True)
    q.add_argument("--stop-model", required=True); q.add_argument("--out", required=True)
    a = p.parse_args()
    if a.cmd == "prepare":
        prepare(a.source, a.output)
    else:
        run(a)


if __name__ == "__main__":
    main()
