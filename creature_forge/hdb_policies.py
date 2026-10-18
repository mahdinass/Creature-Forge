"""Non-LLM policies on the Hidden-Damage Bench (phase 3).

A0 `generic_exhaustive`: the old champion procedure adapted without its fault-inverse catalogue. Screen every generic candidate
counterfactual (belief_engine.CANDIDATE_CFS, one level each way of the design parameters) plus the high-friction floor test on
the plant, rank the tools by the measured effect (walking up, falls down, time upright up; ties by tool order), and spend the
whole remaining plant budget on the top-2 tools as chained repairs (half each, as ce_policies.Exhaustive). No twin, no model.
"""
from __future__ import annotations

from .belief_engine import CANDIDATE_CFS
from .hdb_workbench import min_budget

CF_TOOL = {"pitch_ref": "posture", "hip_bias": "posture", "foot_length": "foot_length", "torque_limit": "torque_limit",
           "freq": "timing", "balance_gain": "feedback", "fp_kd": "placement", "foot_friction": "foot_friction",
           "torso_mass": "torso_mass", "floor_test": "foot_friction"}
TOOL_ORDER = ("posture", "timing", "feedback", "placement", "foot_length", "torso_mass", "torque_limit", "foot_friction",
              "stride", "leg_length")


def _effect(base: dict, new: dict) -> tuple:
    def tu(o):
        v = (o.get("median") or {}).get("time_upright")
        return float(v) if isinstance(v, (int, float)) else 0.0
    return (new["n_walking"] - base["n_walking"], -(new["n_fell"] - base["n_fell"]), tu(new) - tu(base))


def generic_exhaustive(bench) -> dict:
    base = bench.observe()["observation"]
    scored = {}
    for cid in CANDIDATE_CFS:
        r = bench.counterfactual(cid)
        if not r.get("ok"):
            continue
        tool = CF_TOOL[cid.split("@")[0]]
        eff = _effect(base, r["observation"])
        scored[tool] = max(scored.get(tool, eff), eff)
    ft = bench.floor_test(3.0)
    if ft.get("ok"):
        eff = _effect(base, ft["observation"])
        scored["foot_friction"] = max(scored.get("foot_friction", eff), eff)
    ranking = sorted(scored, key=lambda t: (tuple(-x for x in scored[t]), TOOL_ORDER.index(t)))
    repairs = []
    for i, tool in enumerate(ranking[:2]):
        budget = bench.remaining // 2 if i == 0 else bench.remaining
        if budget < min_budget(tool, bench.n_train):
            continue
        r = bench.repair(tool, budget)
        repairs.append({"tool": tool, "ok": r.get("ok"), "train_walking": (r.get("best") or {}).get("train_walking")})
    return {"policy": "A0_generic_exhaustive", "ranking": [{"tool": t, "effect": list(scored[t])} for t in ranking],
            "repairs": repairs}
