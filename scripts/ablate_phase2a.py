"""Phase 2A ablation of the selected random-search controller on DIAGNOSTIC seeds only (analysis, not selection).

Switches off one controller component at a time (contact-informed phase sync, stance pitch feedback, stance ankle
balance, knee-lift) and reports gate outcomes, to see which parts of the hybrid controller the gait depends on.
Writes experiments/phase2a/results/ablation.json. 10 seeds x 8 s x 5 variants = 50 rollouts. No Nebius calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge.locomotion import evaluate_controller  # noqa: E402
from creature_forge.optimize import controller_from_export, jsonable, provenance  # noqa: E402
from creature_forge.phase2a import DIAGNOSTIC_SEEDS, DURATIONS  # noqa: E402
from creature_forge.phasegait import PhaseGaitController, PhaseGaitParams  # noqa: E402

OUT = ROOT / "experiments" / "phase2a" / "results"
VARIANTS = {
    "selected": {},
    "no_contact_sync": {"sync_gain": 0.0},
    "no_pitch_feedback": {"pitch_kp": 0.0},
    "no_ankle_balance": {"balance_gain": 0.0},
    "no_knee_lift": {"knee_amp": 0.1},  # lower bound of the parameter space
}


def main() -> None:
    ctrl, body = controller_from_export(json.loads((OUT / "best_random_search.json").read_text(encoding="utf-8")))
    rows = {}
    for name, change in VARIANTS.items():
        r = evaluate_controller(PhaseGaitController(ctrl.p.replace(**change)), body, DIAGNOSTIC_SEEDS, DURATIONS["diagnostic"])
        rows[name] = {"change": change, "walking_fraction": r["walking_fraction"], "labels": r["labels"],
                      "median_speed": r["median_speed"], "fitness": r["fitness"]}
        print(f"{name:20s} walking {r['walking_fraction']:.1f}  median v {r['median_speed']:+.2f}  {r['label']}  {r['labels']}")
    out = {"seeds": list(DIAGNOSTIC_SEEDS), "duration": DURATIONS["diagnostic"], "rollouts": 5 * len(DIAGNOSTIC_SEEDS),
           "note": "analysis only; diagnostic seeds; not used to select or tune", "variants": rows,
           "provenance": provenance(1)}
    (OUT / "ablation.json").write_text(json.dumps(jsonable(out), indent=1, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
