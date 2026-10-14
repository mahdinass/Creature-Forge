"""Phase 2A Stage A diagnosis: can the existing open-loop gait family walk, and what does 'forward' really mean?

Reproduces the 2026-10-13 feasibility search on the *committed* evaluator (`creature_forge.locomotion`):
random samples of (a) the Phase 0 sinusoidal `GaitParams` family and (b) the same family plus a hip-knee phase
lag, each evaluated on DIAGNOSTIC seeds (never the training or held-out seeds) and classified by the physical
walking gates. The earlier scratch search used its own simpler loop, so numbers here can differ slightly.

    .venv\\Scripts\\python scripts\\diagnose_locomotion.py [--samples 500] [--workers 8]

Writes experiments/phase2a/results/diagnosis.json (inputs, outputs, provenance). No Nebius calls.
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

from creature_forge.controller import CTRL_BOUNDS, GaitParams  # noqa: E402
from creature_forge.locomotion import evaluate_controller  # noqa: E402
from creature_forge.morphology import BipedParams  # noqa: E402
from creature_forge.optimize import default_workers, jsonable, provenance  # noqa: E402
from creature_forge.phasegait import (LagSinusoidController, LagSinusoidParams, OpenLoopController)  # noqa: E402

DIAG_SEEDS = (2000, 2001, 2002)
DURATION = 5.0
OL_NAMES = ("gait_freq", "hip_amp", "knee_amp", "stand_hip", "stand_knee", "kp", "kd", "balance_gain")
OL_LO = np.array([0.3] + [CTRL_BOUNDS[k][0] for k in OL_NAMES[1:]])  # gait_freq 0 means standing, so start at 0.3
OL_HI = np.array([2.5] + [CTRL_BOUNDS[k][1] for k in OL_NAMES[1:]])
LAG_RANGE = (0.0, 2 * np.pi)


def _make(family: str, v):
    if family == "open_loop":
        return OpenLoopController(GaitParams(**dict(zip(OL_NAMES, map(float, v)))))
    gp = dict(zip(OL_NAMES, map(float, v[:-1])))
    return LagSinusoidController(LagSinusoidParams(
        gait_freq=gp["gait_freq"], hip_amp=gp["hip_amp"], knee_amp=gp["knee_amp"], lag=float(v[-1]),
        stand_hip=gp["stand_hip"], stand_knee=gp["stand_knee"], kp=gp["kp"], kd=gp["kd"],
        balance_gain=gp["balance_gain"]))


def job(args):
    family, v = args
    r = evaluate_controller(_make(family, v), BipedParams(), DIAG_SEEDS, DURATION)
    keep = ("label", "speed_upright", "forward_disp_upright", "fell", "flight_frac", "raw_touchdown_rate",
            "saturation_frac", "valid_step_rate", "slip_frac", "body_contact_frac", "violations")
    return {"family": family, "vector": [float(x) for x in v], "fitness": r["fitness"], "label": r["label"],
            "feasible": r["feasible"], "walking_fraction": r["walking_fraction"],
            "per_seed": [{k: m[k] for k in keep} for m in r["per_seed"]]}


def summarise(rows: list[dict]) -> dict:
    labels: dict[str, int] = {}
    for r in rows:
        labels[r["label"]] = labels.get(r["label"], 0) + 1
    seed_rows = [m for r in rows for m in r["per_seed"]]
    surv = [r for r in rows if not any(m["fell"] for m in r["per_seed"])]
    fwd_surv = [r for r in surv if np.mean([m["speed_upright"] for m in r["per_seed"]]) > 0.2]
    # forward displacement that is NOT walking: the reward-hacking signature
    fake = [r for r in rows if np.mean([m["speed_upright"] for m in r["per_seed"]]) > 0.2 and not r["feasible"]]
    best = max(rows, key=lambda r: r["fitness"])
    return {"n": len(rows), "label_counts": labels, "seed_rollouts": len(seed_rows),
            "survive_all_seeds": len(surv), "survive_and_forward_gt_0.2": len(fwd_surv),
            "forward_gt_0.2_but_not_walking": len(fake), "walking_all_seeds": sum(r["feasible"] for r in rows),
            "walking_any_seed": sum(r["walking_fraction"] > 0 for r in rows),
            "best_survivor_speed": max((np.mean([m["speed_upright"] for m in r["per_seed"]]) for r in surv),
                                       default=None),
            "worst_survivor_speed": min((np.mean([m["speed_upright"] for m in r["per_seed"]]) for r in surv),
                                        default=None),
            "best_by_fitness": best,
            "forward_not_walking_examples": sorted(fake, key=lambda r: -r["fitness"])[:5]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=500)
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--rng-seed", type=int, default=123)
    ap.add_argument("--out", type=Path, default=ROOT / "experiments" / "phase2a" / "results" / "diagnosis.json")
    a = ap.parse_args()
    rng = np.random.default_rng(a.rng_seed)
    ol = OL_LO + (OL_HI - OL_LO) * rng.random((a.samples, len(OL_NAMES)))
    lag = np.column_stack([ol, LAG_RANGE[0] + (LAG_RANGE[1] - LAG_RANGE[0]) * rng.random(a.samples)])
    jobs = [("open_loop", v) for v in ol] + [("lag_sinusoid", v) for v in lag]
    t0 = time.perf_counter()
    with mp.get_context("spawn").Pool(a.workers) as pool:
        rows = pool.map(job, jobs, chunksize=2)
    assert len(rows) == len(jobs)
    out = {
        "purpose": "Phase 2A Stage A: capability of the existing open-loop gait family, evaluated by physical gates",
        "config": {"samples_per_family": a.samples, "rng_seed": a.rng_seed, "diagnostic_seeds": list(DIAG_SEEDS),
                   "duration": DURATION, "open_loop_names": OL_NAMES,
                   "open_loop_bounds": [OL_LO.tolist(), OL_HI.tolist()], "lag_range": list(LAG_RANGE),
                   "rollouts": len(jobs) * len(DIAG_SEEDS)},
        "open_loop": summarise(rows[: a.samples]), "lag_sinusoid": summarise(rows[a.samples:]),
        "wall_s": time.perf_counter() - t0, "provenance": provenance(a.workers),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(jsonable(out), indent=1, allow_nan=False), encoding="utf-8")
    for fam in ("open_loop", "lag_sinusoid"):
        s = out[fam]
        print(f"{fam}: n={s['n']} survive_all={s['survive_all_seeds']} survive+fwd={s['survive_and_forward_gt_0.2']} "
              f"fwd_but_not_walking={s['forward_gt_0.2_but_not_walking']} walking_all_seeds={s['walking_all_seeds']} "
              f"best_survivor_speed={s['best_survivor_speed']}")
        print("  labels:", s["label_counts"])
    print(f"wrote {a.out} in {out['wall_s']:.0f}s")


if __name__ == "__main__":
    main()
