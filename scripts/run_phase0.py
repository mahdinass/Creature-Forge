#!/usr/bin/env python
"""Phase 0 demo: fail a creature, detect why-relevant evidence, change one physical parameter, re-verify.

Run:  .venv\Scripts\python scripts\run_phase0.py   (writes artifacts/phase0/<run_id>/)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from creature_forge.artifacts import save_run  # noqa: E402
from creature_forge.controller import GaitParams  # noqa: E402
from creature_forge.experiment import compare_designs  # noqa: E402
from creature_forge.failures import detect_failures  # noqa: E402
from creature_forge.morphology import BipedParams  # noqa: E402
from creature_forge.simulate import run_rollout  # noqa: E402

from creature_forge.experiment import PHASE0_DURATION as DURATION, PHASE0_PUSH as PUSH, PHASE0_SEEDS as SEEDS  # noqa: E402
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "phase0"


def main() -> int:
    gait = GaitParams()
    baseline = BipedParams(foot_length=0.08)
    candidate = baseline.replace(foot_length=0.16)  # the single bounded physical modification

    print(f"Disturbance: {PUSH.force} N horizontal push on torso for {PUSH.duration}s at t={PUSH.time}s")
    for name, body in (("baseline", baseline), ("candidate", candidate)):
        tel = run_rollout(body, gait, seed=0, duration=DURATION, push=PUSH)
        events = detect_failures(tel, body)
        save_run(OUT, f"{name}_seed0", body, gait, seed=0, duration=DURATION, push=PUSH,
                 telemetry=tel, events=events)
        z = tel["torso_pos"][:, 1]
        print(f"[{name}] foot_length={body.foot_length} m  torso height {z[0]:.2f}->{z[-1]:.2f} m "
              f"(min {z.min():.2f})  max|pitch|={np.abs(tel['torso_pitch']).max():.2f} rad  "
              f"peak torso vx={tel['torso_linvel'][:, 0].max():.2f} m/s  "
              f"events={[(e.kind, round(e.time, 2)) for e in events] or 'none'}")

    res = compare_designs(baseline, candidate, gait, seeds=SEEDS, duration=DURATION, push=PUSH)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "comparison.json").write_text(json.dumps(res, indent=2))
    b, c = res["baseline"], res["candidate"]
    print(f"\nMatched seeds {list(SEEDS)}:")
    print(f"  baseline  fall_rate={b['fall_rate']:.2f}  mean min torso height={b['mean_min_torso_height']:.2f} m")
    print(f"  candidate fall_rate={c['fall_rate']:.2f}  mean min torso height={c['mean_min_torso_height']:.2f} m")
    improved = c["fall_rate"] < b["fall_rate"]
    print("VERIFIED IMPROVEMENT" if improved else "NO IMPROVEMENT")
    print(f"Artifacts: {OUT}")
    return 0 if improved else 1


if __name__ == "__main__":
    raise SystemExit(main())
