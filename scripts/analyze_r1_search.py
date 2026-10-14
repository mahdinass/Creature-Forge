"""Offline, post-hoc analysis of the R1 candidate histories (NO MuJoCo rollouts, no ledger writes).

    python scripts/analyze_r1_search.py     # writes experiments/phase2a_r1/results/search_analysis.json and prints a summary

Questions: did broad uniform sampling in 13/15-D produce too few viable gaits for the robustness objectives to matter?
All statistics are descriptive and post-hoc; nothing here selects a controller or changes the registered result.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r1  # noqa: E402
from creature_forge.phasegait import PhaseGaitParams  # noqa: E402
from creature_forge.phasegait_init import LOWER15, UPPER15  # noqa: E402

RES = r1.RESULTS
NAMES = list(PhaseGaitParams.__dataclass_fields__) + ["ramp_s", "start_lean"]


def load(arm):
    return [json.loads(x) for x in (RES / f"history_{arm}1.jsonl").read_text(encoding="utf-8").splitlines()]


def rank(x):
    o = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    r[o] = np.arange(len(x))
    for v in np.unique(x):                     # average ties
        m = x == v
        r[m] = r[m].mean()
    return r


def spearman(a, b):
    a, b = rank(np.asarray(a, float)), rank(np.asarray(b, float))
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def norm(v, d):
    return (np.asarray(v, float) - LOWER15[:d]) / (UPPER15[:d] - LOWER15[:d])


def main() -> None:
    out: dict = {"note": "post-hoc descriptive analysis of R1 replicate-1 histories; no new rollouts"}
    H = {a: load(a) for a in "ABC"}
    inc = np.asarray(r1.incumbent_vector(15), float)
    u_inc = norm(inc, 15)
    out["incumbent_normalized"] = dict(zip(NAMES, np.round(u_inc, 3).tolist()))

    # 1. effective sample size: common random numbers
    X = {a: np.array([h["vector"] for h in H[a]]) for a in "ABC"}
    out["common_random_numbers"] = {
        "A_equals_B_candidates_1_149": bool(np.array_equal(X["A"][1:], X["B"][1:])),
        "C_first13_equals_A_candidates_1_149": bool(np.array_equal(X["C"][1:, :13], X["A"][1:])),
        "distinct_13d_points_evaluated": int(len({tuple(r) for r in np.vstack([X["A"][1:], X["B"][1:], X["C"][1:, :13]])})),
    }

    # 2. coverage: how close did uniform sampling get to the incumbent?
    U = norm(X["A"][1:], 13)
    d2 = np.linalg.norm(U - u_inc[:13], axis=1)
    dinf = np.abs(U - u_inc[:13]).max(axis=1)
    rng = np.random.default_rng(0)
    sim = np.linalg.norm(rng.random((200000, 13)) - u_inc[:13], axis=1)
    cov = {}
    for delta in (0.05, 0.10, 0.20, 0.30):
        lo, hi = np.clip(u_inc[:13] - delta, 0, 1), np.clip(u_inc[:13] + delta, 0, 1)
        p = float(np.prod(hi - lo))
        cov[f"box_halfwidth_{delta}"] = {"prob_per_uniform_draw": p, "expected_hits_in_149": 149 * p,
                                         "observed_hits": int((dinf <= delta).sum())}
    out["coverage_13d"] = {"min_L2_to_incumbent": float(d2.min()), "median_L2": float(np.median(d2)),
                           "uniform_L2_p1_p50_p99": [float(np.percentile(sim, q)) for q in (1, 50, 99)],
                           "min_Linf": float(dinf.min()), "boxes": cov}

    # 3. viability of the sampled candidates (training, 8 seeds each; incumbent excluded)
    stats = {}
    for a in "ABC":
        c = H[a][1:]
        ps = [m for h in c for m in h["per_seed"]]
        steps = np.array([m["valid_steps"] for m in ps])
        per_cand_max_steps = np.array([max(m["valid_steps"] for m in h["per_seed"]) for h in c])
        stats[a] = {
            "candidates": len(c),
            "walking_seeds_total": int(sum(m["walking"] for m in ps)),
            "candidates_with_any_valid_step": int((per_cand_max_steps >= 1).sum()),
            "candidates_with_ge3_valid_steps_on_some_seed": int((per_cand_max_steps >= 3).sum()),
            "max_valid_steps_any_seed": int(steps.max()),
            "candidates_surviving_all_8": int(sum(h["survival_count"] == 8 for h in c)),
            "candidates_surviving_ge4": int(sum(h["survival_count"] >= 4 for h in c)),
            "candidates_surviving_ge1": int(sum(h["survival_count"] >= 1 for h in c)),
            "label_counts_seed_level": dict(Counter(m["label"] for m in ps).most_common()),
            "median_fall_time_s": float(np.median([m["fall_time"] for m in ps if m["fall_time"] is not None])),
        }
    out["viability_random_candidates"] = stats
    out["incumbent_training"] = {"walking_of_8": H["A"][0]["walking_count"], "survival_of_8": H["A"][0]["survival_count"],
                                 "labels": dict(Counter(H["A"][0]["labels"])),
                                 "objective": H["A"][0]["objective"],
                                 "per_seed_valid_steps": [m["valid_steps"] for m in H["A"][0]["per_seed"]]}

    # 4. objective behaviour: what do mean / worst2 reward?
    mean = np.array([h["objective"]["mean"] for h in H["A"][1:]])
    w2 = np.array([h["objective"]["worst2"] for h in H["A"][1:]])
    surv = np.array([h["survival_count"] for h in H["A"][1:]])
    fit_all = np.array([m["fitness"] for h in H["A"][1:] for m in h["per_seed"]])
    out["objective_behaviour"] = {
        "incumbent_mean": H["A"][0]["objective"]["mean"], "incumbent_worst2": H["A"][0]["objective"]["worst2"],
        "best_candidate_mean": float(mean.max()), "best_candidate_worst2": float(w2.max()),
        "candidates_with_worst2_above_incumbent": int((w2 > H["A"][0]["objective"]["worst2"]).sum()),
        "candidates_with_mean_above_incumbent": int((mean > H["A"][0]["objective"]["mean"]).sum()),
        "spearman_mean_vs_worst2": spearman(mean, w2),
        "top5_overlap_A_vs_B_excluding_incumbent_idx": None,
        "per_seed_fitness_percentiles_random_candidates": {str(q): float(np.percentile(fit_all, q)) for q in (1, 10, 50, 90, 99, 100)},
        "per_seed_fitness_walking_incumbent": [m["fitness"] for m in H["A"][0]["per_seed"]],
    }
    topA = [json.loads((RES / "validation_A1.json").read_text())["top5_training_indices"]][0]
    topB = json.loads((RES / "validation_B1.json").read_text())["top5_training_indices"]
    topC = json.loads((RES / "validation_C1.json").read_text())["top5_training_indices"]
    out["objective_behaviour"]["top5_training_indices"] = {"A": topA, "B": topB, "C": topC}
    out["objective_behaviour"]["top5_overlap_A_B"] = len(set(topA) & set(topB))
    out["objective_behaviour"]["incumbent_rank_B_worst2"] = int(1 + (w2 > H["B"][0]["objective"]["worst2"]).sum())

    # 5. training -> validation transfer (14 validated non-incumbent candidates)
    tr, va = [], []
    for a in "ABC":
        v = json.loads((RES / f"validation_{a}1.json").read_text())
        for r in v["validated"]:
            tr.append((r["training_objective"]["mean"], H[a][r["index"]]["survival_count"] / 8))
            va.append((r["objective"]["mean"], r["survival_count"] / 16))
    out["train_validation_transfer"] = {"n": len(tr), "validated_survival_fraction": [round(x[1], 3) for x in va],
                                        "training_survival_fraction": [round(x[1], 3) for x in tr],
                                        "spearman_train_vs_val_mean_fitness": spearman([t[0] for t in tr], [x[0] for x in va])}

    # 6. which parameters track survival / fitness among random candidates (Spearman, uncorrected, descriptive)
    sp = {}
    for j, nme in enumerate(NAMES[:13]):
        sp[nme] = {"spearman_with_mean_fitness": round(spearman(U[:, j], mean), 3), "spearman_with_survival_count": round(spearman(U[:, j], surv), 3)}
    out["parameter_association_13d_uncorrected"] = sp
    best = np.argsort(-mean)[:10]
    out["top10_by_mean_fitness_vs_incumbent_normalized_abs_diff"] = {
        NAMES[j]: {"incumbent_u": round(float(u_inc[j]), 3), "top10_mean_abs_diff": round(float(np.abs(U[best, j] - u_inc[j]).mean()), 3)}
        for j in range(13)}
    (RES / "search_analysis.json").write_text(json.dumps(out, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("common_random_numbers", "coverage_13d", "viability_random_candidates", "incumbent_training",
                                           "objective_behaviour", "train_validation_transfer")}, indent=1))
    print(json.dumps(out["parameter_association_13d_uncorrected"], indent=0))


if __name__ == "__main__":
    main()
