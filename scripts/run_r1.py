"""Staged R1 runner. Every stage requires a committed, unmodified, code-consistent protocol and writes to the ledger.

    python scripts/run_r1.py pilot                 # 32 rollouts: throughput + peak memory + resource checks
    python scripts/run_r1.py train --rep 1         # arms A, B, C, replicate 1 (3 x 150 candidates x 8 seeds)
    python scripts/run_r1.py validate --rep 1      # top-5 per run on the 16 validation seeds (+ incumbent once)
    python scripts/run_r1.py gate                  # futility rule; writes results/gate.json
    python scripts/run_r1.py train --rep 2 ; python scripts/run_r1.py validate --rep 2     # only if the gate says proceed
    python scripts/run_r1.py select                # one overall winner -> results/selection.json (then COMMIT it)

Never run alongside verification (unit tests, browser, CI). Workers <= 4 and further limited by the pilot. No Nebius calls.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r1  # noqa: E402
from creature_forge.optimize import Executor, jsonable, provenance  # noqa: E402

RES = r1.RESULTS


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(jsonable(obj), indent=1, allow_nan=False) + "\n", encoding="utf-8")


def load_history(arm: str, rep: int) -> list[dict]:
    return [json.loads(x) for x in (RES / f"history_{arm}{rep}.jsonl").read_text(encoding="utf-8").splitlines()]


def workers_for(args) -> int:
    w = min(args.workers, r1.MAX_WORKERS)
    pilot = RES / "pilot.json"
    if not pilot.exists():
        raise SystemExit("run the pilot first")
    p = json.loads(pilot.read_text(encoding="utf-8"))
    if not p["passed"]:
        raise SystemExit("the pilot failed its resource checks; stopping (see results/pilot.json)")
    return min(w, p["recommended_workers"])


def stage_pilot(args, ledger):
    w = min(args.workers, r1.MAX_WORKERS)
    free_before = r1.free_memory_gb()
    if free_before < r1.MIN_FREE_GB:
        raise SystemExit(f"free memory {free_before:.2f} GB is below the {r1.MIN_FREE_GB} GB floor: not starting the pilot "
                         "(no rollouts were run or counted). Free memory and retry.")
    vecs = r1.candidate_vectors("A", 1)[:4]          # incumbent + 3 replicate-1 candidates: 4 jobs x 8 seeds = 32 rollouts
    t0 = time.perf_counter()
    with Executor(w, timeout_s=900, fn=r1.r1_job) as ex:
        outs = r1.run_batch(ex, ledger, "pilot", vecs, r1.TRAIN_SEEDS, "pilot: incumbent + 3 replicate-1 candidates")
    wall = time.perf_counter() - t0                  # includes pool start-up: conservative
    n = len(vecs) * len(r1.TRAIN_SEEDS)
    peak = max(o["peak_rss_mb"] for o in outs)
    errors = sum(not o["ok"] for o in outs)
    planned = r1.build_protocol()["budget"]["planned"]
    remaining = planned["training"] + planned["validation"] + planned["final"]
    rate = n / wall
    free_after = r1.free_memory_gb()
    rec_workers = max((k for k in range(1, w + 1) if k * peak / 1024 <= 0.5 * free_before), default=0)
    checks = {"no_job_errors": errors == 0, "free_memory_after_ok": free_after >= r1.MIN_FREE_GB,
              "projected_wall_within_80pct_of_limit": remaining / rate <= 0.8 * r1.WALL_LIMIT_S,
              "memory_headroom_for_some_worker_count": rec_workers >= 1}
    res = {"rollouts": n, "workers_used": w, "wall_s": wall, "throughput_rollouts_per_s": rate,
           "peak_worker_rss_mb": peak, "free_memory_gb_before": free_before, "free_memory_gb_after": free_after,
           "remaining_planned_rollouts": remaining, "projected_wall_s_at_this_rate": remaining / rate,
           "recommended_workers": rec_workers, "checks": checks, "passed": all(checks.values()),
           "rule": "recommended_workers = largest k <= 4 with k * peak_worker_rss <= 50% of free memory before the pilot",
           "provenance": provenance(w)}
    write_json(RES / "pilot.json", res)
    print(json.dumps({k: v for k, v in res.items() if k != "provenance"}, indent=1))
    if not res["passed"]:
        raise SystemExit("PILOT FAILED its resource checks: stopping and reporting, as pre-registered")


def stage_train(args, ledger, w):
    if args.rep == 2:
        gate = RES / "gate.json"
        if not gate.exists() or not json.loads(gate.read_text(encoding="utf-8"))["proceed"]:
            raise SystemExit("replicate 2 requires a passing futility gate (results/gate.json)")
    with Executor(w, timeout_s=1800, fn=r1.r1_job) as ex:
        for arm in r1.ARM_ORDER:
            t0 = time.perf_counter()
            hist = r1.run_training(arm, args.rep, ex, ledger)
            key = r1.ARMS[arm]["objective"]
            best = max(hist, key=lambda r: r["objective"][key])
            print(f"{arm}{args.rep}: {len(hist)} candidates in {time.perf_counter() - t0:.0f}s; best {key} "
                  f"{best['objective'][key]:.3f} (index {best['index']}); errors {sum(r['error'] is not None for r in hist)}; "
                  f"ledger {ledger.total_rollouts()}", flush=True)


def stage_validate(args, ledger, w):
    with Executor(w, timeout_s=1800, fn=r1.r1_job) as ex:
        if not (RES / "validation_incumbent.json").exists():
            inc = r1.run_incumbent_validation(ex, ledger)
            print(f"incumbent validation: walking {inc['walking_count']}/16, survived {inc['survival_count']}/16")
        for arm in r1.ARM_ORDER:
            res = r1.run_validation(arm, args.rep, load_history(arm, args.rep), ex, ledger)
            counts = [v["walking_count"] for v in res["validated"]]
            print(f"{arm}{args.rep}: top-5 training indices {res['top5_training_indices']}; validated walking counts {counts}",
                  flush=True)


def stage_gate(ledger):
    inc = json.loads((RES / "validation_incumbent.json").read_text(encoding="utf-8"))
    vals = {a: [json.loads((RES / f"validation_{a}1.json").read_text(encoding="utf-8"))] for a in r1.ARM_ORDER}
    g = r1.futility_gate(vals, inc)
    g["ledger_rollouts"] = ledger.total_rollouts()
    write_json(RES / "gate.json", g)
    print(json.dumps(g, indent=1))
    print("GATE: PROCEED to replicate 2" if g["proceed"] else "GATE: STOP - null result under the pre-registered futility rule")


def stage_select(ledger, commits):
    if (RES / "selection.json").exists():
        raise SystemExit("selection.json exists; the selection is frozen")
    vals = [json.loads((RES / f"validation_{a}{r}.json").read_text(encoding="utf-8")) for a in r1.ARM_ORDER for r in r1.REPLICATES]
    win = r1.select_winner(vals)
    ranked = r1.rank_validated([r for v in vals for r in v["validated"]])
    inc = json.loads((RES / "validation_incumbent.json").read_text(encoding="utf-8"))
    keep = ("arm", "replicate", "index", "walking_count", "survival_count", "objective")
    sel = {"protocol_commit": commits["protocol"], "rule": r1.SELECTION_RULE, "ledger_rollouts_at_selection": ledger.total_rollouts(),
           "winner": {**{k: win[k] for k in keep}, "vector": win["vector"], "training_rank": win["training_rank"],
                      "training_objective": win["training_objective"]},
           "winner_export": r1.vector_export(win["vector"], {"protocol": "phase2a-r1-protocol-v1", "arm": win["arm"],
                                                              "replicate": win["replicate"], "index": win["index"]}),
           "incumbent_validation": {k: inc[k] for k in ("walking_count", "survival_count", "objective")},
           "validation_ranking": [{k: r[k] for k in keep} for r in ranked],
           "note": "final seeds were not used; commit this file before running scripts/eval_r1_final.py"}
    write_json(RES / "selection.json", sel)
    write_json(RES / "best_r1_winner.json", sel["winner_export"])
    print(f"selected {win['arm']}{win['replicate']} candidate {win['index']}: validation walking {win['walking_count']}/16 "
          f"(incumbent {inc['walking_count']}/16)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["pilot", "train", "validate", "gate", "select"])
    ap.add_argument("--rep", type=int, choices=[1, 2], default=1)
    ap.add_argument("--workers", type=int, default=r1.MAX_WORKERS)
    args = ap.parse_args()
    commits = r1.require_preregistration()
    ledger = r1.Ledger()
    ledger.verify()
    RES.mkdir(parents=True, exist_ok=True)
    if args.stage == "pilot":
        return stage_pilot(args, ledger)
    if args.stage == "gate":
        return stage_gate(ledger)
    if args.stage == "select":
        return stage_select(ledger, commits)
    w = workers_for(args)
    (stage_train if args.stage == "train" else stage_validate)(args, ledger, w)


if __name__ == "__main__":
    main()
