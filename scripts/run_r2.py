"""Staged R2 runner. Every stage requires a committed, unmodified, code-consistent protocol and writes to the ledger.

    python scripts/run_r2.py pilot                         # <= 100 rollouts: code paths + throughput + memory (pilot seeds 7300-7315)
    python scripts/run_r2.py screen                        # theta0 on the 64 screen seeds (once)
    python scripts/run_r2.py freeze                        # 0 rollouts: writes training_set.json (COMMIT it before training)
    python scripts/run_r2.py train --arm S|T|I --rep N     # needs the committed training set
    python scripts/run_r2.py validate --arm S|T|I --rep N  # top-5 on the 64 validation seeds (+ theta0 once)
    python scripts/run_r2.py gate                          # futility rule after S1, T1, I1 -> results/gate.json
    python scripts/run_r2.py select                        # one winner -> results/selection.json (COMMIT it)
    python scripts/run_r2.py final                         # winner vs theta0 on the 150 final seeds (once; needs committed selection)
    python scripts/run_r2.py diagnostic                    # post-hoc, after the final
Never run alongside verification (tests, browser, CI). Workers <= 4. No Nebius calls.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from creature_forge import r1, r2  # noqa: E402
from creature_forge.optimize import Executor, provenance  # noqa: E402

RES = r2.RESULTS


def load_hist(arm, rep):
    return [json.loads(x) for x in (RES / f"history_{arm}{rep}.jsonl").read_text(encoding="utf-8").splitlines()]


def load_json(name):
    return json.loads((RES / name).read_text(encoding="utf-8"))


def workers_for(args) -> int:
    pilot = RES / "pilot.json"
    if not pilot.exists():
        raise SystemExit("run the pilot first")
    p = load_json("pilot.json")
    if not p["passed"]:
        raise SystemExit("the pilot failed its resource checks; stopping (see results/pilot.json)")
    return min(args.workers, r2.MAX_WORKERS, p["recommended_workers"])


def stage_pilot(args, ledger):
    w = min(args.workers, r2.MAX_WORKERS)
    free_before = r1.free_memory_gb()
    if free_before < r2.MIN_FREE_GB:
        raise SystemExit(f"free memory {free_before:.2f} GB is below the {r2.MIN_FREE_GB} GB floor: not starting (nothing counted)")
    s1, noise = r2.s_candidates(1), r2.t_noise(1)
    t_off = r2.t_offspring(1, 0, r2.to_u(r2.incumbent_theta()), r2.T_SIGMA0, noise)
    vecs = [r2.incumbent_theta(), s1[0]["vector"], s1[6]["vector"], t_off[0], t_off[1], r2.i_candidates()[24]["vector"]]
    for v in vecs:
        assert (np.asarray(v) >= r2.LOWER15 - 1e-12).all() and (np.asarray(v) <= r2.UPPER15 + 1e-12).all(), "candidate outside bounds"
    t0 = time.perf_counter()
    with Executor(w, timeout_s=900, fn=r2.r2_job) as ex:
        outs = r2.run_batch(ex, ledger, "pilot", vecs, r2.PILOT_SEEDS, "pilot: theta0 + S0 + S6 + T0 + T1 + I24 on pilot seeds 7300-7315")
    wall = time.perf_counter() - t0
    n = len(vecs) * len(r2.PILOT_SEEDS)
    peak = max(o["peak_rss_mb"] for o in outs)
    errors = sum(not o["ok"] for o in outs)
    rate = n / wall
    remaining = r2.planned_budget()["total"] - 96
    free_after = r1.free_memory_gb()
    rec_workers = max((k for k in range(1, w + 1) if k * peak / 1024 <= 0.5 * free_before), default=0)
    checks = {"no_job_errors": errors == 0, "free_memory_after_ok": free_after >= r2.MIN_FREE_GB,
              "projected_wall_within_80pct_of_limit": remaining / rate <= 0.8 * r2.WALL_LIMIT_S,
              "memory_headroom_for_some_worker_count": rec_workers >= 1, "rollouts_within_pilot_cap": n <= r2.PILOT_CAP}
    res = {"rollouts": n, "pilot_seeds": list(r2.PILOT_SEEDS),
           "seed_provenance": "pilot-only seeds 7300-7315, disjoint from all other roles; results are used only for implementation/resource checks",
           "workers_used": w, "wall_s": wall, "throughput_rollouts_per_s": rate, "peak_worker_rss_mb": peak,
           "free_memory_gb_before": free_before, "free_memory_gb_after": free_after, "remaining_planned_rollouts": remaining,
           "projected_wall_s_at_this_rate": remaining / rate, "recommended_workers": rec_workers, "checks": checks, "passed": all(checks.values()),
           "rule": "recommended_workers = largest k <= 4 with k * peak_worker_rss <= 50% of free memory before the pilot",
           "provenance": provenance(w)}
    r2.write_json(RES / "pilot.json", res)
    print(json.dumps({k: v for k, v in res.items() if k != "provenance"}, indent=1))
    if not res["passed"]:
        raise SystemExit("PILOT FAILED its resource checks: stopping and reporting, as pre-registered")


def stage_screen(args, ledger):
    w = workers_for(args)
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        res = r2.run_screen(ex, ledger)
    print(f"screen: theta0 walking {res['walking_count']}/64, survived {res['survival_count']}/64")


def stage_freeze(args, ledger):
    sel = r2.freeze_training_set()
    print(json.dumps({k: sel[k] for k in ("stop", "n_incumbent_walking", "n_incumbent_failing", "train_seeds")}, indent=1))
    if sel["stop"]:
        print("REGISTERED STOP:", sel["reason"])
    else:
        print("training_set.json written; COMMIT it before running any training stage")


def stage_train(args, ledger):
    r2.require_preregistration(need_training_set=True)
    ts = json.loads(r2.TRAINING_SET.read_text(encoding="utf-8"))
    seeds = r2.train_seeds()
    w0 = r2.incumbent_training_reference(ts)["walking_count"]
    w = workers_for(args)
    if args.rep not in r2.REPLICATES[args.arm]:
        raise SystemExit(f"arm {args.arm} has no replicate {args.rep}")
    if args.rep == 2:
        if not (RES / "gate.json").exists() or not load_json("gate.json")["proceed"]:
            raise SystemExit("replicate 2 requires a passing futility gate (results/gate.json)")
    t0 = time.perf_counter()
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        if args.arm == "S":
            hist = r2.run_training_S(args.rep, ex, ledger, seeds)
        elif args.arm == "I":
            hist = r2.run_training_I(ex, ledger, seeds)
        else:
            hist = r2.run_training_T(args.rep, ex, ledger, seeds, w0, r2.incumbent_parent_record(ts))
    best = max(hist, key=lambda r: (r2.score_of(r), -r["index"]))
    feas = sum(r2.is_feasible(r, w0) for r in hist)
    print(f"{args.arm}{args.rep}: {len(hist)} candidates in {time.perf_counter() - t0:.0f}s; feasible {feas}; best score {r2.score_of(best)} "
          f"(index {best['index']}); theta0 {w0}/16 walking; errors {sum(r['error'] is not None for r in hist)}; ledger {ledger.total_rollouts()}")


def stage_validate(args, ledger):
    r2.require_preregistration(need_training_set=True)
    ts = json.loads(r2.TRAINING_SET.read_text(encoding="utf-8"))
    w0 = r2.incumbent_training_reference(ts)["walking_count"]
    w = workers_for(args)
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        if not (RES / "validation_incumbent.json").exists():
            inc = r2.run_incumbent_validation(ex, ledger)
            print(f"theta0 validation: walking {inc['walking_count']}/64, survived {inc['survival_count']}/64, dragging {r2.n_dragging(inc)}")
        res = r2.run_validation(args.arm, args.rep, load_hist(args.arm, args.rep), w0, ex, ledger)
    print(f"{args.arm}{args.rep}: validated walking {[v['walking_count'] for v in res['validated']]}, "
          f"survived {[v['survival_count'] for v in res['validated']]}")


def stage_gate(args, ledger):
    inc = load_json("validation_incumbent.json")
    vals = {a: [load_json(f"validation_{a}1.json")] for a in r2.ARM_ORDER}
    g = r2.futility_gate(vals, inc)
    g["ledger_rollouts"] = ledger.total_rollouts()
    r2.write_json(RES / "gate.json", g)
    print(json.dumps(g, indent=1))
    print("GATE: PROCEED to replicate 2" if g["proceed"] else "GATE: STOP - null result under the pre-registered futility rule")


def stage_select(args, ledger, commits):
    if (RES / "selection.json").exists():
        raise SystemExit("selection.json exists; the selection is frozen")
    if not load_json("gate.json")["proceed"]:
        raise SystemExit("the futility gate said STOP; there is nothing to select")
    inc = load_json("validation_incumbent.json")
    vals = [load_json(f"validation_{a}{r}.json") for a in r2.ARM_ORDER for r in r2.REPLICATES[a]]
    win = r2.select_winner(vals, inc)
    ranked = r2.rank_eligible([r for v in vals for r in v["validated"]], inc)
    keep = ("arm", "replicate", "index", "walking_count", "survival_count", "objective")
    sel = {"protocol_commit": commits["protocol"], "training_set_commit": commits["training_set"], "rule": r2.build_protocol()["selection_rule"],
           "ledger_rollouts_at_selection": ledger.total_rollouts(),
           "winner": {**{k: win[k] for k in keep}, "vector": win["vector"], "training_score": win["training_score"]},
           "incumbent_validation": {k: inc[k] for k in ("walking_count", "survival_count", "objective")},
           "validation_ranking": [{k: r[k] for k in keep} for r in ranked],
           "note": "final seeds were not used; commit this file before running the final stage"}
    r2.write_json(RES / "selection.json", sel)
    print(f"selected {win['arm']}{win['replicate']} candidate {win['index']}: validation walking {win['walking_count']}/64 (theta0 {inc['walking_count']}/64)")


def stage_final(args, ledger):
    commits = r2.require_preregistration(need_training_set=True, need_selection=True)
    out_path = RES / "final.json"
    if out_path.exists():
        raise SystemExit("final.json exists: the final evaluation is run once")
    w = workers_for(args)
    sel = load_json("selection.json")
    vecs = [sel["winner"]["vector"], r2.incumbent_theta()]
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        outs = r2.run_batch(ex, ledger, "final", vecs, r2.FINAL_SEEDS, "selected winner vs frozen theta0, identical seeds (once)")
    if not all(o["ok"] for o in outs):
        raise SystemExit("a final-evaluation job failed: " + "; ".join(o.get("error", "") for o in outs if not o["ok"]))
    per = [o["result"]["per_seed"] for o in outs]
    out = {"protocol_commit": commits["protocol"], "training_set_commit": commits["training_set"], "selection_commit": commits["selection"],
           "seeds": list(r2.FINAL_SEEDS), "winner_source": f"{sel['winner']['arm']}{sel['winner']['replicate']}#{sel['winner']['index']}",
           **r2.final_analysis(per[0], per[1]),
           "per_seed": {"winner": [r1._compact_seed(m) for m in per[0]], "incumbent": [r1._compact_seed(m) for m in per[1]]},
           "ledger_rollouts_total": ledger.total_rollouts(), "provenance": provenance(w)}
    r2.write_json(out_path, out)
    h = out["confirmatory_hierarchy"]
    print(f"paired table {out['paired_table']}; non-inferior: {h['claims']['preservation_confirmed']}; superior: {h['claims']['improvement_confirmed']}")
    for k in ("winner", "incumbent"):
        e = out["engineering"][k]
        print(f"{k:10s} walking {e['walking_seeds']}/{e['n_seeds']} median v {e['median_speed_upright']:+.2f} engineering criterion: {e['meets_engineering_criterion']}")


def stage_diagnostic(args, ledger):
    if not (RES / "final.json").exists():
        raise SystemExit("diagnostics run only after the final evaluation")
    out_path = RES / "diagnostic.json"
    if out_path.exists():
        raise SystemExit("diagnostic.json exists")
    w = workers_for(args)
    sel = load_json("selection.json")
    vecs = [sel["winner"]["vector"], r2.incumbent_theta()]
    res = {}
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        for name, pert in (("standard", None), ("stress", r2.STRESS_PERTURB)):
            outs = r2.run_batch(ex, ledger, f"diagnostic-{name}", vecs, r2.DIAGNOSTIC_SEEDS, f"post-hoc {name}", perturb=pert)
            res[name] = {n: {"walking": int(sum(m["walking"] for m in o["result"]["per_seed"])),
                             "survived": int(sum(not m["fell"] for m in o["result"]["per_seed"])),
                             "per_seed": [r1._compact_seed(m) for m in o["result"]["per_seed"]]}
                         for n, o in zip(("winner", "incumbent"), outs)}
    r2.write_json(out_path, {"note": "post-hoc, descriptive; never used to select", "seeds": list(r2.DIAGNOSTIC_SEEDS), "results": res})
    for k, v in res.items():
        print(k, {n: f"{d['walking']}/32 walking" for n, d in v.items()})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["pilot", "screen", "freeze", "train", "validate", "gate", "select", "final", "diagnostic"])
    ap.add_argument("--arm", choices=["S", "T", "I"])
    ap.add_argument("--rep", type=int, choices=[1, 2], default=1)
    ap.add_argument("--workers", type=int, default=r2.MAX_WORKERS)
    args = ap.parse_args()
    if args.stage in ("train", "validate") and not args.arm:
        raise SystemExit("--arm is required")
    r2.require_preregistration()
    ledger = r2.Ledger()
    ledger.verify()
    RES.mkdir(parents=True, exist_ok=True)
    ledger.session_begin(args.stage)
    try:
        if args.stage == "pilot":
            return stage_pilot(args, ledger)
        if args.stage == "screen":
            return stage_screen(args, ledger)
        if args.stage == "freeze":
            return stage_freeze(args, ledger)
        if args.stage == "train":
            return stage_train(args, ledger)
        if args.stage == "validate":
            return stage_validate(args, ledger)
        if args.stage == "gate":
            return stage_gate(args, ledger)
        if args.stage == "select":
            return stage_select(args, ledger, r2.require_preregistration(need_training_set=True))
        if args.stage == "final":
            return stage_final(args, ledger)
        if args.stage == "diagnostic":
            return stage_diagnostic(args, ledger)
    finally:
        ledger.session_end()


if __name__ == "__main__":
    main()
