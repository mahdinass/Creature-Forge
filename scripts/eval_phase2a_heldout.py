"""Phase 2A Stage D: one-shot held-out evaluation of the frozen selections and the baselines.

    .venv\\Scripts\\python scripts\\eval_phase2a_heldout.py [--workers 8]

Refuses to run unless protocol.json and results/selection.json are committed and unmodified, and unless the
protocol still matches the code. Nothing here selects or tunes anything; the verdict is computed from the
success criteria fixed in the protocol. Writes results/heldout.json. No Nebius calls.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge.controller import GaitParams  # noqa: E402
from creature_forge.locomotion import aggregate, compute_metrics, fitness_components, rollout  # noqa: E402
from creature_forge.morphology import BipedParams  # noqa: E402
from creature_forge.optimize import default_workers, jsonable, provenance  # noqa: E402
from creature_forge.phase2a import (DURATIONS, HELDOUT_SEEDS, OPEN_LOOP_REFERENCE, SELECTION, SUCCESS,  # noqa: E402
                                    require_preregistration)
from creature_forge.phasegait import OpenLoopController, PhaseGaitController, PhaseGaitParams  # noqa: E402

OUT = ROOT / "experiments" / "phase2a" / "results"


def build(spec: dict):
    if spec["kind"] == "open_loop":
        return OpenLoopController(GaitParams(**spec["params"]))
    return PhaseGaitController(PhaseGaitParams(**spec["params"]).validate())


def job(arg):
    spec, seed = arg
    m = compute_metrics(rollout(build(spec), BipedParams(), seed, DURATIONS["heldout"]))
    m["fitness"] = fitness_components(m)
    return m


def verdict(agg: dict) -> dict:
    w, p = SUCCESS["walking"], SUCCESS["partial"]
    per = agg["per_seed"]
    drag = sum("body_dragging" in m["violations"] for m in per)
    frac = agg["walking_fraction"]
    ok = frac >= w["min_fraction_seeds_walking"] and agg["median_speed"] >= w["min_median_speed_upright"] \
        and drag <= w["max_body_dragging_seeds"]
    return {"meets_walking_criteria": bool(ok), "meets_partial_criteria": bool(frac >= p["min_fraction_seeds_walking"]),
            "fraction_seeds_walking": frac, "median_speed_upright": agg["median_speed"], "body_dragging_seeds": drag}


def summarise(agg: dict) -> dict:
    per = agg["per_seed"]

    def mean(k):
        return float(np.mean([m[k] for m in per]))
    return {"label_counts": {l: agg["labels"].count(l) for l in sorted(set(agg["labels"]))},
            "survival_rate": float(np.mean([not m["fell"] for m in per])), "mean_distance_upright": mean("forward_disp_upright"),
            "mean_speed_upright": mean("speed_upright"), "mean_valid_steps": mean("valid_steps"),
            "mean_valid_step_rate": mean("valid_step_rate"), "mean_step_advance": mean("mean_step_advance"),
            "mean_slip_frac": mean("slip_frac"), "mean_saturation_frac": mean("saturation_frac"),
            "mean_effort": mean("effort"), "mean_flight_frac": mean("flight_frac"),
            "mean_raw_touchdown_rate": mean("raw_touchdown_rate"), "mean_fitness": agg["fitness"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=default_workers())
    a = ap.parse_args()
    commits = require_preregistration()
    sel = json.loads(SELECTION.read_text(encoding="utf-8"))
    diag = json.loads((OUT / "diagnosis.json").read_text(encoding="utf-8"))
    ol_best = max((diag["open_loop"]["best_by_fitness"],), key=lambda r: r["fitness"])
    ol_names = diag["config"]["open_loop_names"]
    specs = {
        "standing": {"kind": "open_loop", "params": GaitParams().as_dict()},
        "open_loop_reference": {"kind": "open_loop", "params": OPEN_LOOP_REFERENCE.as_dict()},
        "open_loop_best_of_500": {"kind": "open_loop",
                                  "params": GaitParams(**dict(zip(ol_names, ol_best["vector"]))).as_dict()},
    }
    for method, s in sel["selected"].items():
        specs[method] = {"kind": "phase_gait", "params": s["params"]}
    jobs = [(spec, seed) for spec in specs.values() for seed in HELDOUT_SEEDS]
    t0 = time.perf_counter()
    with mp.get_context("spawn").Pool(a.workers) as pool:
        rows = pool.map(job, jobs, chunksize=1)
    assert len(rows) == len(jobs)
    n = len(HELDOUT_SEEDS)
    out = {"protocol_commit": commits["protocol"], "selection_commit": commits["selection"],
           "seeds": list(HELDOUT_SEEDS), "duration": DURATIONS["heldout"], "rollouts": len(jobs),
           "criteria": SUCCESS, "controllers": {}}
    for i, (name, spec) in enumerate(specs.items()):
        agg = aggregate(rows[i * n:(i + 1) * n])
        out["controllers"][name] = {"spec": spec, "verdict": verdict(agg), "summary": summarise(agg), "aggregate": agg}
        v, s = out["controllers"][name]["verdict"], out["controllers"][name]["summary"]
        print(f"{name:24s} walking {v['fraction_seeds_walking']:.2f}  median v {v['median_speed_upright']:+.2f} m/s  "
              f"survive {s['survival_rate']:.2f}  steps/s {s['mean_valid_step_rate']:.2f}  labels {s['label_counts']}")
    out["wall_s"] = time.perf_counter() - t0
    out["provenance"] = provenance(a.workers)
    (OUT / "heldout.json").write_text(json.dumps(jsonable(out), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT / 'heldout.json'} ({len(jobs)} rollouts, {out['wall_s']:.0f}s)")


if __name__ == "__main__":
    main()
