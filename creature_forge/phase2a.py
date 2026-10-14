"""Phase 2A pre-registered protocol: seed roles, budgets, success criteria and the committed-file guard.

Seed roles (disjoint, enforced by `check_disjoint`):
  train       optimisation fitness only
  diagnostic  failure analysis, baseline choice and regression checks; never used to select the controller
  heldout     touched exactly once by `scripts/eval_phase2a_heldout.py`, after the protocol and the frozen
              selection are committed; never used to select or tune anything
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from .contact import ContactConfig
from .controller import GaitParams
from .locomotion import DEFAULT_CRITERIA
from .morphology import BipedParams
from .optimize import OptimizerConfig

ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = ROOT / "experiments" / "phase2a"
PROTOCOL = EXP_DIR / "protocol.json"
SELECTION = EXP_DIR / "results" / "selection.json"

TRAIN_SEEDS = (1000, 1001, 1002)
DIAGNOSTIC_SEEDS = tuple(range(2000, 2010))
HELDOUT_SEEDS = tuple(range(3000, 3020))
DURATIONS = {"train": 6.0, "diagnostic": 8.0, "heldout": 10.0}
ROLLOUT_BUDGET = 600  # per method; 3 seeds per candidate => 200 candidates

# Fixed Phase 0 reference gait (the best-known stable open-loop pattern: it walks backward).
OPEN_LOOP_REFERENCE = GaitParams(gait_freq=1.0, hip_amp=0.4, knee_amp=0.4, stand_knee=-0.1)

SUCCESS = {
    "walking": {"min_fraction_seeds_walking": 0.9, "min_median_speed_upright": 0.25, "max_body_dragging_seeds": 0},
    "partial": {"min_fraction_seeds_walking": 0.5},
}
SELECTION_RULE = ("per method, the candidate with the highest mean TRAINING fitness over the training seeds "
                  "(ties: earlier evaluated). Diagnostic and held-out seeds are not used.")


def check_disjoint() -> None:
    sets = {"train": set(TRAIN_SEEDS), "diagnostic": set(DIAGNOSTIC_SEEDS), "heldout": set(HELDOUT_SEEDS)}
    names = list(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if sets[a] & sets[b]:
                raise ValueError(f"seed sets overlap: {a} & {b}")


def optimizer_config(rng_seed: int = 0) -> OptimizerConfig:
    return OptimizerConfig(rollout_budget=ROLLOUT_BUDGET, train_seeds=TRAIN_SEEDS, duration=DURATIONS["train"],
                           rng_seed=rng_seed)


def build_protocol() -> dict:
    check_disjoint()
    cfg = optimizer_config()
    return {
        "id": "phase2a-protocol-v1",
        "objective": "learn forward locomotion of a fixed planar biped with a compact phase-based controller",
        "morphology": BipedParams().as_dict(),
        "contact_estimator": ContactConfig().as_dict(),
        "walking_criteria": DEFAULT_CRITERIA.as_dict(),
        "seeds": {"train": list(TRAIN_SEEDS), "diagnostic": list(DIAGNOSTIC_SEEDS), "heldout": list(HELDOUT_SEEDS)},
        "durations_s": DURATIONS,
        "initial_state": "torso pitch and 6 joint angles ~ N(0, 0.03 rad) from the episode seed; feet 2 mm above floor",
        "fitness": ("mean over seeds of: survival + 3*progress + steps - 0.5*effort - pitch_penalty + 1*[walking]; "
                    "progress/steps are multiplied by a soft validity factor (chatter, flight, slip, saturation, "
                    "body contact); see creature_forge.locomotion.fitness_components"),
        "optimization": {
            "methods": ["random_search", "differential_evolution"],
            "rollout_budget_per_method": cfg.rollout_budget, "candidates_per_method": cfg.n_candidates,
            "rollouts_per_candidate": len(cfg.train_seeds), "rng_seed": cfg.rng_seed,
            "de": {"population": cfg.de_pop, "F": cfg.de_f, "CR": cfg.de_cr, "strategy": "rand/1/bin",
                   "polish": False, "bounds": "clip"},
            "random_search": {"sampling": "uniform in bounds", "batch_size": cfg.batch_size},
            "shared_initial_population": "first 20 candidates are identical for both methods",
            "single_run_each": True,
        },
        "selection_rule": SELECTION_RULE,
        "success_criteria": SUCCESS,
        "baselines": {
            "standing": GaitParams().as_dict(),
            "open_loop_reference": OPEN_LOOP_REFERENCE.as_dict(),
            "open_loop_best_of_500": "best-by-fitness open_loop sample in results/diagnosis.json (diagnostic seeds)",
            "exploit_regression": "tests/test_locomotion.py::test_phase2a_feasibility_exploit_fails_walking_classification",
        },
        "heldout_policy": ("evaluated once, after this file and results/selection.json are committed unmodified; "
                           "results are reported as-is and never used for selection or tuning"),
    }


def protocol_sha256(path: Path = PROTOCOL) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def committed_unmodified(path: Path) -> str:
    """Return the commit that last touched `path`; raise unless it is tracked and identical to HEAD."""
    rel = path.relative_to(ROOT).as_posix()
    try:
        _git("ls-files", "--error-unmatch", rel)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{rel} is not committed") from e
    if _git("status", "--porcelain", "--", rel):
        raise RuntimeError(f"{rel} has uncommitted changes")
    return _git("log", "-1", "--format=%H", "--", rel)


def require_preregistration() -> dict:
    """Held-out guard: protocol and frozen selection must be committed, and the protocol must match the code."""
    commits = {"protocol": committed_unmodified(PROTOCOL), "selection": committed_unmodified(SELECTION)}
    stored = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if stored != json.loads(json.dumps(build_protocol())):
        raise RuntimeError("protocol.json no longer matches the code that defines it; re-registration required")
    return commits
