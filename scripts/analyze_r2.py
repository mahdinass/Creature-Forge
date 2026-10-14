"""Descriptive post-hoc summaries of the R2 records (NO rollouts): basin map for arm S, arm comparison, winner vs theta0 parameters.

    python scripts/analyze_r2.py   # writes experiments/phase2a_r2/results/analysis.json
Everything here is exploratory and never used to select; the confirmatory result is final.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r1_stats, r2  # noqa: E402

RES = r2.RESULTS
NAMES = ["freq", "duty", "hip_amp", "knee_amp", "knee_shift", "stance_knee", "hip_bias", "kp", "kd", "balance_gain", "pitch_kp",
         "pitch_ref", "sync_gain", "ramp_s", "start_lean"]


def load(name):
    return json.loads((RES / name).read_text(encoding="utf-8"))


def hist(arm, rep):
    return [json.loads(x) for x in (RES / f"history_{arm}{rep}.jsonl").read_text(encoding="utf-8").splitlines()]


def main() -> None:
    ts = load("training_set.json")
    w0 = ts["incumbent_on_training_seeds"]["walking_count"]
    out: dict = {"note": "descriptive, exploratory; the confirmatory analysis is final.json", "theta0_training_walking_of_16": w0}
    # basin map: arm S candidates (both replicates) by (sigma, k)
    cells = {}
    for rep in (1, 2):
        for h in hist("S", rep):
            cells.setdefault((h["sigma"], h["k"]), []).append(h)
    basin = []
    for (sigma, k), hs in sorted(cells.items()):
        n = len(hs)
        keep = sum(h["walking_count"] >= w0 - 1 for h in hs)          # feasible: preserves walking on the training seeds
        better = sum(h["walking_count"] > w0 for h in hs)
        full = sum(h["walking_count"] == 16 for h in hs)
        lo, hi = r1_stats.wilson(keep, n)
        basin.append({"sigma_u": sigma, "k": k, "n": n, "feasible": keep, "feasible_frac": keep / n, "wilson95": [lo, hi],
                      "improved_on_training_seeds": better, "walk_all_16": full})
    out["basin_map_arm_S_training_seeds"] = basin
    # arm comparison on validation (exploratory)
    inc = load("validation_incumbent.json")
    arms = {}
    for a, reps in r2.REPLICATES.items():
        for r in reps:
            v = load(f"validation_{a}{r}.json")
            arms[f"{a}{r}"] = {"validated_walking": [x["walking_count"] for x in v["validated"]],
                               "best_gain_over_theta0": max(x["walking_count"] for x in v["validated"]) - inc["walking_count"]}
    out["validation_by_run"] = {"theta0_walking_of_64": inc["walking_count"], "runs": arms}
    # candidates that reach 16/16 on training seeds, per arm
    out["train_all16_counts"] = {f"{a}{r}": int(sum(h["walking_count"] == 16 for h in hist(a, r))) for a, reps in r2.REPLICATES.items() for r in reps}
    # which parameters moved in the winner (normalised distance from theta0)
    sel = load("selection.json")
    u, u0 = r2.to_u(sel["winner"]["vector"]), r2.to_u(r2.incumbent_theta())
    out["winner"] = {"source": f"{sel['winner']['arm']}{sel['winner']['replicate']}#{sel['winner']['index']}",
                     "normalised_delta_vs_theta0": {n: round(float(d), 3) for n, d in zip(NAMES, u - u0)},
                     "l2_distance_normalised": float(np.linalg.norm(u - u0)), "ramp_s": sel["winner"]["vector"][13],
                     "start_lean": sel["winner"]["vector"][14]}
    # final seeds: where did theta0 fail?
    fin = load("final.json")
    inc_fail = [m for m in fin["per_seed"]["incumbent"] if not m["walking"]]
    from collections import Counter
    out["theta0_final_failures"] = {"n": len(inc_fail), "labels": dict(Counter(m["label"] for m in inc_fail)),
                                    "valid_steps_le_1": int(sum(m["valid_steps"] <= 1 for m in inc_fail))}
    out["diagnostic_walking_of_32"] = {k: {n: d["walking"] for n, d in v.items()} for k, v in load("diagnostic.json")["results"].items()}
    out["exact_intervals_final"] = {"winner": fin["descriptive_paired_comparison"]["new"], "incumbent": fin["descriptive_paired_comparison"]["old"]}
    (RES / "analysis.json").write_text(json.dumps(out, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
