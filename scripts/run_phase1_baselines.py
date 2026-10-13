#!/usr/bin/env python
"""Evaluate the non-AI proposers (and two reference designs) through the pre-registered held-out protocol.

No model calls. Output: experiments/phase1/results/baselines.json
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from creature_forge.controller import GaitParams
from creature_forge.evaluation import Protocol, classify, evaluate_design_protocol, wilson_interval
from creature_forge.experiment import PHASE0_BASELINE, PHASE0_DURATION, PHASE0_PUSH
from creature_forge.failures import detect_failures
from creature_forge.forensics import build_forensics
from creature_forge.proposers import heuristic_proposal, random_proposals
from creature_forge.simulate import run_rollout

OUT = Path("experiments") / "phase1" / "results" / "baselines.json"
WORKERS = 12


def main() -> int:
    reg = json.loads(Path("experiments/phase1/protocol.json").read_text(encoding="utf-8"))
    n_random, rng_seed = reg["baselines"]["random"]["n_proposals"], reg["baselines"]["random"]["rng_seed"]
    body, gait, proto = PHASE0_BASELINE, GaitParams(), Protocol()
    t0 = time.perf_counter()
    base = evaluate_design_protocol(body, gait, proto, workers=WORKERS)
    sims = {"baseline_eval": base["simulations"]}

    def judge(p):
        cand = evaluate_design_protocol(body.replace(**{p["parameter"]: p["value"]}), gait, proto, workers=WORKERS)
        return cand["simulations"], classify(base, cand, proto) | {"candidate_by_push": cand["by_push"]}

    out = {"protocol": proto.as_dict(), "baseline_design": {"body": body.as_dict(), "by_push": base["by_push"]}}
    # reference designs (NOT proposers)
    ref_sims = 0
    out["references"] = {}
    for name, p in (("foot_length_0.16_known_phase0_answer", {"parameter": "foot_length", "value": 0.16}),):
        n, v = judge(p)
        ref_sims += n
        out["references"][name] = {"proposal": p} | v
    # heuristic (single proposal, from the forensic evidence of the baseline failure, seed 0)
    tel = run_rollout(body, gait, seed=0, duration=PHASE0_DURATION, push=PHASE0_PUSH)
    forensics = build_forensics(tel, body, PHASE0_PUSH, detect_failures(tel, body))
    h = heuristic_proposal(forensics, body)
    if h is None:
        out["heuristic"] = {"proposal": None, "note": "abstained"}
        sims["heuristic"] = 0
    else:
        n, v = judge(h)
        sims["heuristic"] = n
        out["heuristic"] = {"proposal": h, "evidence_simulations": 1, "model_calls": 0} | v
    # random
    props = random_proposals(rng_seed, n_random, body)
    results, rs = [], 0
    for p in props:
        n, v = judge(p)
        rs += n
        results.append({"proposal": p, "tier": v["tier"], "primary_fall_rate": v["primary_fall_rate"],
                        "levels_worse": v["levels_where_candidate_worse"]})
    sims["random"] = rs
    tiers = Counter(r["tier"] for r in results)
    k_succ = tiers["success"]
    lo, hi = wilson_interval(k_succ, n_random)
    p_hat = k_succ / n_random
    by_param: dict[str, dict] = {}
    for r in results:
        d = by_param.setdefault(r["proposal"]["parameter"], {"n": 0, "success": 0})
        d["n"] += 1
        d["success"] += r["tier"] == "success"
    out["random"] = {
        "n_proposals": n_random, "rng_seed": rng_seed, "tiers": dict(tiers),
        "per_proposal_success_rate": p_hat, "wilson95": [lo, hi],
        "best_of_k_success_probability_analytic": {str(k): 1 - (1 - p_hat) ** k for k in (1, 3, 5, 10, 20)},
        "note_best_of_k": "analytic 1-(1-p)^k from the pooled per-proposal rate; assumes k independent proposals, "
                          "each fully evaluated; it is an estimate with the Wilson interval above, not an observation",
        "by_parameter": by_param, "proposals": results,
        "simulations_per_proposal": proto.sims_per_design()}
    out["budget"] = {"held_out_simulations": sims, "reference_simulations": ref_sims,
                     "simulations_per_candidate_evaluation": proto.sims_per_design(),
                     "wall_seconds": round(time.perf_counter() - t0, 1)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"random": {k: out["random"][k] for k in ("tiers", "per_proposal_success_rate", "wilson95",
                                                                 "by_parameter")},
                      "heuristic": out["heuristic"].get("proposal") and
                      {"proposal": out["heuristic"]["proposal"], "tier": out["heuristic"]["tier"],
                       "falls_by_push": out["heuristic"]["falls_by_push"]},
                      "known_answer": {k: out["references"][k]["tier"] for k in out["references"]},
                      "budget": out["budget"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
