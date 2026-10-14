"""Walking Lab data: the starting walking controller next to the one found by classical local optimisation (R2).

Read-only over committed records (`experiments/phase2a_r2/results`); replays are fresh deterministic MuJoCo rollouts of the two stored
controller vectors on seeds the R2 final evaluation already used. No model is involved, and nothing here changes a registered record.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import overview as overview_mod
from . import r2

RESULTS = overview_mod.EXP / "phase2a_r2" / "results"
WHICH = {"incumbent": "Starting controller", "r2_winner": "Improved controller (classical optimiser)"}
DURATION = 10.0


class WalkingError(KeyError):
    pass


def _read(name: str, results: Path = RESULTS) -> dict:
    p = results / name
    if not p.is_file():
        raise WalkingError(f"missing committed record {name}")
    return json.loads(p.read_text(encoding="utf-8"))


def vector(which: str, results: Path = RESULTS) -> list[float]:
    if which == "incumbent":
        return [float(x) for x in r2.incumbent_theta()]
    if which == "r2_winner":
        return [float(x) for x in _read("selection.json", results)["winner"]["vector"]]
    raise WalkingError(f"unknown controller {which!r}")


def summary(results: Path = RESULTS) -> dict:
    final = _read("final.json", results)
    inc, win = final["per_seed"]["incumbent"], final["per_seed"]["winner"]
    seeds = []
    for o, n in zip(inc, win):
        seeds.append({"seed": o["seed"],
                      "incumbent": {"label": o["label"], "walking": o["walking"], "fall_time": o["fall_time"]},
                      "winner": {"label": n["label"], "walking": n["walking"], "fall_time": n["fall_time"]}})
    featured = [s["seed"] for s in seeds if s["incumbent"]["label"] == "fall" and s["winner"]["walking"]][:6]
    table = final["paired_table"]
    return {
        "n": table["n"], "incumbent_walking": table["both"] + table["old_only"], "winner_walking": table["both"] + table["new_only"],
        "paired": {"both": table["both"], "winner_only": table["new_only"], "incumbent_only": table["old_only"], "neither": table["neither"]},
        "seeds": seeds, "featured": featured, "controllers": WHICH, "duration": DURATION,
        "provenance": {"protocol_commit": final["protocol_commit"], "selection_commit": final["selection_commit"], "winner_source": final["winner_source"],
                       "evidence_platform": final["provenance"].get("platform"),
                       "note": "Outcomes were measured on Linux. A replay here is a fresh run on this machine; each replay reports its own outcome next to the committed one."},
        "attribution": "Found by classical local optimisation (random-subset perturbation, initiation grid, (1+8)-ES). No language model was involved.",
    }


@lru_cache(maxsize=24)
def _replay(which: str, seed: int) -> dict:
    from .locomotion_view import build_locomotion_payload
    from .morphology import BipedParams
    from .phasegait_init import controller_from_vector
    v = vector(which)
    payload = build_locomotion_payload(controller_from_vector(v), BipedParams(), {"vector": v}, seed=seed, duration=DURATION)
    payload["role"] = "walking_lab"
    rec = next((s for s in summary()["seeds"] if s["seed"] == seed), None)
    payload["committed"] = None if rec is None else rec["incumbent" if which == "incumbent" else "winner"]
    payload["controller_label"] = WHICH[which]
    return payload


def replay(which: str, seed: int) -> dict:
    if which not in WHICH:
        raise WalkingError(f"unknown controller {which!r}")
    if seed not in {s["seed"] for s in summary()["seeds"]}:
        raise WalkingError("replay seed must be one of the R2 final-evaluation seeds")
    return _replay(which, seed)
