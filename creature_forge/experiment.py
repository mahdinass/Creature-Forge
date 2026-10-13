"""Matched-seed design comparison: same controller, seeds, disturbance; only the body differs."""
from __future__ import annotations

import numpy as np

from .controller import GaitParams
from .failures import detect_failures
from .morphology import BipedParams
from .simulate import Push, run_rollout


# Phase 0 reference experiment (shared by scripts/run_phase0.py and the Studio)
PHASE0_PUSH = Push(time=1.0, force=25.0, duration=0.15)
PHASE0_SEEDS = (0, 1, 2, 3, 4)
PHASE0_DURATION = 5.0
PHASE0_BASELINE = BipedParams(foot_length=0.08)
PHASE0_CANDIDATE = PHASE0_BASELINE.replace(foot_length=0.16)


def _evaluate(body: BipedParams, gait: GaitParams, seeds, duration, push) -> dict:
    runs = []
    for s in seeds:
        tel = run_rollout(body, gait, seed=s, duration=duration, push=push)
        events = detect_failures(tel, body)
        runs.append({"seed": s, "fell": any(e.kind == "fall" for e in events),
                     "events": [e.kind for e in events],
                     "min_torso_height": float(tel["torso_pos"][:, 1].min()),
                     "max_abs_pitch": float(np.abs(tel["torso_pitch"]).max())})
    return {"body": body.as_dict(), "runs": runs,
            "fall_rate": float(np.mean([r["fell"] for r in runs])),
            "mean_min_torso_height": float(np.mean([r["min_torso_height"] for r in runs])),
            "mean_max_abs_pitch": float(np.mean([r["max_abs_pitch"] for r in runs]))}


def compare_designs(baseline: BipedParams, candidate: BipedParams, gait: GaitParams, *,
                    seeds=(0, 1, 2), duration: float = 5.0, push: Push | None = None) -> dict:
    return {"seeds": list(seeds), "duration": duration,
            "baseline": _evaluate(baseline, gait, seeds, duration, push),
            "candidate": _evaluate(candidate, gait, seeds, duration, push)}


evaluate_design = _evaluate  # public name: matched-seed evaluation of one body (used by the investigator)
