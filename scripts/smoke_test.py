#!/usr/bin/env python
"""Executable end-to-end smoke test (physics only; no network). Exit 0 = pass."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from creature_forge.artifacts import save_run, telemetry_hash  # noqa: E402
from creature_forge.controller import GaitParams  # noqa: E402
from creature_forge.failures import detect_failures  # noqa: E402
from creature_forge.morphology import BipedParams  # noqa: E402
from creature_forge.simulate import Push, run_rollout  # noqa: E402


def check(cond: bool, msg: str) -> None:
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        raise SystemExit(1)


def main() -> int:
    g = GaitParams()
    stable = run_rollout(BipedParams(), g, seed=0, duration=10.0)
    check(len(stable["t"]) == 2000 and stable["t"][-1] > 9.9, "10 s headless rollout (2000 telemetry samples)")
    check(not detect_failures(stable, BipedParams()), "default creature stands 10 s with no failure events")
    check(telemetry_hash(stable) == telemetry_hash(run_rollout(BipedParams(), g, seed=0, duration=10.0)),
          "same seed reproduces identical telemetry")
    push = Push(1.0, 25.0, 0.15)
    short = BipedParams(foot_length=0.08)
    tel = run_rollout(short, g, seed=0, duration=5.0, push=push)
    check(any(e.kind == "fall" for e in detect_failures(tel, short)), "short-footed creature falls under 25 N push")
    ok = run_rollout(BipedParams(), g, seed=0, duration=5.0, push=push)
    check(not any(e.kind == "fall" for e in detect_failures(ok, BipedParams())),
          "lengthening foot to 0.16 m prevents the fall (same seed, same push)")
    with tempfile.TemporaryDirectory() as d:
        p = save_run(Path(d), "smoke", short, g, seed=0, duration=5.0, push=push, telemetry=tel,
                     events=detect_failures(tel, short))
        check((p / "manifest.json").exists() and (p / "telemetry.npz").exists(), "artifacts written")
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
