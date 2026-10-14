"""Phase 2A training: random search vs bounded differential evolution at a matched 600-rollout budget each.

    .venv\\Scripts\\python scripts\\run_phase2a.py [--workers 8] [--wall-limit-s 1800]

Requires the committed protocol (scripts/preregister_phase2a.py). Writes, under experiments/phase2a/results/:
  history_<method>.jsonl     every candidate: params, per-seed metrics, fitness components, label, provenance
  summary_<method>.json      budget accounting, hyperparameters, best-so-far curve, timing, versions
  best_<method>.json         replayable controller export of the candidate chosen by the pre-registered rule
  selection.json             the frozen selection (training data only); commit it before the held-out run
  diagnostic_eval.json       selected + top-5 candidates re-run on DIAGNOSTIC seeds (analysis only)
No Nebius calls.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge.optimize import (Executor, candidate_export, controller_from_export, default_workers,  # noqa: E402
                                     differential_evolution, jsonable, provenance, random_search)
from creature_forge.locomotion import evaluate_controller  # noqa: E402
from creature_forge.phase2a import (DIAGNOSTIC_SEEDS, DURATIONS, PROTOCOL, SELECTION, committed_unmodified,  # noqa: E402
                                    optimizer_config, protocol_sha256)

OUT = ROOT / "experiments" / "phase2a" / "results"


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(jsonable(obj), indent=1, allow_nan=False) + "\n", encoding="utf-8")


def select(history: list[dict]) -> dict:
    """Pre-registered rule: highest mean training fitness; ties go to the earlier candidate."""
    return max(history, key=lambda r: (r["fitness"], -r["rollouts_before"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--wall-limit-s", type=float, default=1800.0, help="per-batch pool timeout (raises, never drops)")
    a = ap.parse_args()
    protocol_commit = committed_unmodified(PROTOCOL)
    cfg = optimizer_config()
    OUT.mkdir(parents=True, exist_ok=True)
    t_all = time.perf_counter()
    results = {}
    with Executor(a.workers, timeout_s=a.wall_limit_s) as ex:
        for name, fn in (("random_search", random_search), ("differential_evolution", differential_evolution)):
            hist, summ = fn(cfg, ex)
            assert summ["rollouts"] == cfg.rollout_budget, (name, summ["rollouts"])
            summ["protocol_commit"], summ["protocol_sha256"] = protocol_commit, protocol_sha256()
            (OUT / f"history_{name}.jsonl").write_text(
                "\n".join(json.dumps(r, allow_nan=False) for r in hist) + "\n", encoding="utf-8")
            write_json(OUT / f"summary_{name}.json", summ)
            results[name] = (hist, summ)
            print(f"{name}: {summ['candidates']} candidates, {summ['rollouts']} rollouts, {summ['errors']} errors, "
                  f"{summ['wall_s']:.0f}s, best fitness {summ['best_fitness']:.3f}, feasible {summ['n_feasible']}")
            print("  labels:", summ["label_counts"])

    selection = {"rule": "highest mean training fitness (ties: earlier)", "protocol_commit": protocol_commit,
                 "protocol_sha256": protocol_sha256(), "training_seeds": list(cfg.train_seeds),
                 "selected": {}}
    diag = {"seeds": list(DIAGNOSTIC_SEEDS), "duration": DURATIONS["diagnostic"],
            "note": "analysis only; not used for selection", "candidates": []}
    for name, (hist, summ) in results.items():
        best = select(hist)
        exp = candidate_export(best, cfg.body, {"method": name, "index": hist.index(best),
                                                "rollouts_before": best["rollouts_before"],
                                                "protocol_commit": protocol_commit})
        write_json(OUT / f"best_{name}.json", exp)
        selection["selected"][name] = {"index": hist.index(best), "params": best["params"],
                                       "training_fitness": best["fitness"], "training_label": best["label"],
                                       "training_feasible": best["feasible"], "export": f"best_{name}.json"}
        top = sorted(range(len(hist)), key=lambda i: -hist[i]["fitness"])[:5]
        for rank, i in enumerate(top):
            ctrl, body = controller_from_export(candidate_export(hist[i], cfg.body, {}))
            r = evaluate_controller(ctrl, body, DIAGNOSTIC_SEEDS, DURATIONS["diagnostic"])
            diag["candidates"].append({"method": name, "rank": rank, "index": i, "params": hist[i]["params"],
                                       "training_fitness": hist[i]["fitness"], "training_label": hist[i]["label"],
                                       "diagnostic": r})
    write_json(SELECTION, selection)
    diag["rollouts"] = sum(len(c["diagnostic"]["per_seed"]) for c in diag["candidates"])
    diag["provenance"] = provenance(a.workers)
    write_json(OUT / "diagnostic_eval.json", diag)
    print(f"selection written to {SELECTION}; diagnostic rollouts (outside the optimiser budgets): {diag['rollouts']}")
    print(f"total wall {time.perf_counter() - t_all:.0f}s")


if __name__ == "__main__":
    main()
