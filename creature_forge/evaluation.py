"""Pre-registered independent evaluation protocol shared by EVERY proposer (Nemotron, random, heuristic).

A candidate (one body-parameter change) is judged only here, on seeds no proposer ever saw, across several
push strengths including values near the baseline's tipping threshold. The tier rule is fixed in code and in
`experiments/phase1/protocol.json` BEFORE any live model request. Nothing in this module depends on who
proposed the candidate.
"""
from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, asdict

import numpy as np

from .controller import GaitParams
from .failures import detect_failures
from .morphology import BipedParams
from .simulate import Push, run_rollout


@dataclass(frozen=True)
class Protocol:
    push_levels_N: tuple[float, ...] = (15.0, 20.0, 25.0, 30.0, 35.0)
    primary_push_N: float = 25.0
    push_time_s: float = 1.0
    push_duration_s: float = 0.15
    duration_s: float = 5.0
    heldout_seeds: tuple[int, ...] = tuple(range(200, 210))  # never used for evidence, screening or exploration
    # success: primary fall rate <= success_max_fall_rate, no push level worse than baseline,
    #          primary mean survival time >= baseline's
    success_max_fall_rate: float = 0.2
    # partial: not success, but primary fall rate reduced by >= partial_min_reduction
    partial_min_reduction: float = 0.3

    def as_dict(self) -> dict:
        return asdict(self)

    def sims_per_design(self) -> int:
        return len(self.push_levels_N) * len(self.heldout_seeds)


def _one(args) -> dict:
    body_d, gait_d, seed, force, t, dur, duration = args
    body, gait = BipedParams(**body_d), GaitParams(**gait_d)
    tel = run_rollout(body, gait, seed=seed, duration=duration, push=Push(t, force, dur))
    fall = next((e for e in detect_failures(tel, body) if e.kind == "fall"), None)
    return {"seed": seed, "force_N": force, "fell": fall is not None,
            "survival_s": float(fall.time if fall else duration),
            "min_torso_height_m": float(tel["torso_pos"][:, 1].min()),
            "max_abs_pitch_rad": float(np.abs(tel["torso_pitch"]).max())}


def evaluate_design_protocol(body: BipedParams, gait: GaitParams, protocol: Protocol, *,
                             workers: int = 1) -> dict:
    """Run the full held-out grid for one design. Returns per-push aggregates and the simulation count."""
    jobs = [(body.as_dict(), gait.as_dict(), s, f, protocol.push_time_s, protocol.push_duration_s,
             protocol.duration_s) for f in protocol.push_levels_N for s in protocol.heldout_seeds]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            runs = list(ex.map(_one, jobs, chunksize=4))
    else:
        runs = [_one(j) for j in jobs]
    by_push = {}
    for f in protocol.push_levels_N:
        r = [x for x in runs if x["force_N"] == f]
        by_push[str(f)] = {
            "fall_rate": float(np.mean([x["fell"] for x in r])),
            "mean_survival_s": float(np.mean([x["survival_s"] for x in r])),
            "mean_min_torso_height_m": float(np.mean([x["min_torso_height_m"] for x in r])),
            "mean_max_abs_pitch_rad": float(np.mean([x["max_abs_pitch_rad"] for x in r])),
            "falls": int(sum(x["fell"] for x in r)), "n": len(r)}
    return {"body": body.as_dict(), "by_push": by_push, "simulations": len(runs)}


def classify(baseline: dict, candidate: dict, protocol: Protocol) -> dict:
    """Apply the pre-registered tier rule to two `evaluate_design_protocol` results."""
    key = str(protocol.primary_push_N)
    b, c = baseline["by_push"], candidate["by_push"]
    worse = [f for f in b if c[f]["fall_rate"] > b[f]["fall_rate"]]
    primary_b, primary_c = b[key], c[key]
    reduction = primary_b["fall_rate"] - primary_c["fall_rate"]
    survival_ok = primary_c["mean_survival_s"] >= primary_b["mean_survival_s"] - 1e-9
    success = (primary_c["fall_rate"] <= protocol.success_max_fall_rate + 1e-9 and not worse and survival_ok)
    partial = (not success) and reduction >= protocol.partial_min_reduction - 1e-9
    return {"tier": "success" if success else "partial" if partial else "none",
            "primary_fall_rate": {"baseline": primary_b["fall_rate"], "candidate": primary_c["fall_rate"],
                                  "reduction": reduction},
            "levels_where_candidate_worse": worse, "primary_survival_not_worse": bool(survival_ok),
            "falls_by_push": {f: [b[f]["falls"], c[f]["falls"]] for f in b}}


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))
