"""R0 policy: bounded search over existing groups. No plant, fault labels or verifier.

The trusted runner injects a measured-score evaluator; this module sees only the
nominal design, train/selection seeds and scalar candidate scores. Frozen physics,
CMA, objective and verifier implementations are reused without monkeypatching.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np

from . import fault_bench as fb
from . import walk_opt as wo
from .eng_tools import MIN_GENERATIONS, population
from .hdb_workbench import BODY_RATIO, tool_space
from .walk_pipelines import Budget, _FPSpace

VERSION = "r0_repair_v1"
TOOLS = tuple(fb.TOOLS)
# Shared by sequential and joint conditions; no outcome-conditioned pair choice.
PAIRS = (("timing", "feedback"), ("posture", "placement"),
         ("timing", "stride"), ("foot_length", "placement"),
         ("torso_mass", "feedback"), ("leg_length", "timing"),
         ("foot_friction", "stride"), ("torque_limit", "timing"))
ACTIONS = ("single", "sequential", "joint")
OBJECTIVES = ("frozen", "do1")
N_TRAIN, N_SELECT, TOP_SELECT = 4, 8, 2
RESERVE = N_TRAIN + N_SELECT + N_SELECT * TOP_SELECT


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def seed(*parts) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big") % (2**31)


def space(groups):
    groups = tuple(groups)
    if not groups or len(set(groups)) != len(groups) or any(g not in TOOLS for g in groups):
        raise ValueError("invalid or duplicate tool group")
    if len(groups) == 1:
        return tool_space(groups[0])
    ctrl = {p for g in groups for p in fb.TOOLS[g]["ctrl"]}
    body = {p for g in groups for p in fb.TOOLS[g]["body"]}
    return _FPSpace(tuple(p for p in wo.ALL_NAMES if p in ctrl),
                    tuple(p for p in wo.BODY_PARAMS if p in body), body_ratio=BODY_RATIO)


def assert_bounds(original, candidate):
    """Absolute guided bounds plus cumulative original-relative body limits."""
    fb.apply_changes(candidate["body"], candidate["vector"], [])
    for p in wo.BODY_PARAMS:
        for f in wo._fields(p):
            old, new = float(original["body"][f]), float(candidate["body"][f])
            if not math.isfinite(new) or not BODY_RATIO[0] - 1e-10 <= new / old <= BODY_RATIO[1] + 1e-10:
                raise ValueError(f"original-relative bound violated: {f}")


def score(rec):
    return (int(rec["walking_count"]), int(rec["survival_count"]), float(rec["mean_fitness"]))


def check_view(view):
    if set(view) != {"robot_id", "robot", "seeds"} or set(view["seeds"]) != {"train", "select"}:
        raise ValueError("policy view contains forbidden or missing fields")
    if len(view["seeds"]["train"]) != N_TRAIN or len(view["seeds"]["select"]) != N_SELECT:
        raise ValueError("wrong policy seed counts")
    ss = list(view["seeds"]["train"]) + list(view["seeds"]["select"])
    if len(set(ss)) != len(ss):
        raise ValueError("policy seeds overlap")


def solve(view, action, objective, replicate, evaluate, *, budget=3000):
    """evaluate(candidates, role) is supplied by the trusted plant runner.

    Both objectives pay the same faulty train and selection baselines. Candidate
    selection is objective-matched on eight disjoint policy-visible seeds. The
    verifier is absent from this interface. All six arms consume exactly budget
    rollouts (multiple of four) using admissible random candidates for CMA tails.
    """
    check_view(view)
    if action not in ACTIONS or objective not in OBJECTIVES:
        raise ValueError("unknown condition")
    if isinstance(replicate, bool) or replicate not in (0, 1, 2):
        raise ValueError("replicate must be 0, 1 or 2")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget % 4 or budget < 1200:
        raise ValueError("budget must be a multiple of four >= 1200")
    original = copy.deepcopy(view["robot"])
    assert_bounds(original, original)
    ledger = Budget(budget)
    candidates, searches, plans, refusals, tail_log = [], [], [], [], []
    # Evaluator caches baseline rows while charging them here, not in closures.
    for role, cost in (("train_baseline", N_TRAIN), ("select_baseline", N_SELECT)):
        ledger.charge(cost, role)
        evaluate([original], role)

    def measured(cands, role):
        for c in cands:
            assert_bounds(original, c)
        n = N_TRAIN if role == "train" else N_SELECT
        ledger.charge(len(cands) * n, role)
        rows = evaluate(cands, role)
        if len(rows) != len(cands) or any(r.get("error") for r in rows):
            raise RuntimeError("invalid or errored candidate measurement")
        for r in rows:
            if not math.isfinite(float(r["mean_fitness"])):
                raise RuntimeError("nonfinite measurement")
        return rows

    def search(start, groups, cap, noise, label):
        sp = space(groups)
        need = N_TRAIN * (1 + MIN_GENERATIONS * population(sp))
        plans.append((copy.deepcopy(start), tuple(groups)))
        if cap < need:
            raise ValueError(f"insufficient allocated budget for {groups}: {cap} < {need}")
        before = ledger.used

        def ev(batch):
            return measured([{"body": b, "vector": list(v)} for b, v in batch], "train")

        try:
            result = wo.cma_search(start["body"], start["vector"], sp, budget=cap,
                                   train_seeds=view["seeds"]["train"], noise_seed=noise,
                                   eval_fn=ev, log_candidates=True)
        except ValueError as exc:
            # A zero-width legal interval is a recorded refusal, never clipping.
            if ledger.used != before:
                raise
            refusals.append({"groups": list(groups), "reason": str(exc)})
            return copy.deepcopy(start)
        if ledger.used - before != result["rollouts_used"]:
            raise RuntimeError("CMA ledger mismatch")
        best = result["best"]
        d = {"body": best["body"], "vector": best["vector"]}
        assert_bounds(original, d)
        candidates.append({"design": d, "score": list(score(best)), "source": label})
        searches.append({"source": label, "groups": list(groups), "cap": cap,
                         "used": result["rollouts_used"], "noise_seed": noise,
                         "start": copy.deepcopy(start), "train_seeds": result["train_seeds"],
                         "popsize": result["popsize"], "sigma0": result["sigma0"], "ipop": result["ipop"],
                         "duration": result["duration"], "restarts": result["restarts"],
                         "space": sp.to_dict(), "history": result["history"],
                         "candidate_scores": result["candidates"], "best": best})
        return copy.deepcopy(d)

    search_budget = budget - RESERVE
    programs = [(t,) for t in TOOLS] if action == "single" else list(PAIRS)
    cap = search_budget // len(programs)
    # Initial allocation is fixed, not contingent on outcomes or unused tails.
    for i, groups in enumerate(programs):
        noise = seed("r0-cma-v1", view["robot_id"], replicate, i)
        if action == "sequential":
            mid = search(original, (groups[0],), cap // 2, noise, f"{i}:first")
            search(mid, (groups[1],), cap - cap // 2, noise + 1, f"{i}:second")
        else:
            search(original, groups, cap, noise, f"{i}:search")
    # Consume generation-rounding tails with legitimate within-condition random
    # search. Sequential tails modify only one group of an existing chain state.
    rng = np.random.default_rng(seed("r0-tail-v1", view["robot_id"], replicate))
    tail = 0
    while ledger.remaining - TOP_SELECT * N_SELECT >= N_TRAIN:
        start, groups = plans[tail % len(plans)]
        sp = space(groups)
        before = ledger.used
        try:
            x = rng.uniform(size=sp.dim)
            b, v = wo.decode(sp, start["body"], start["vector"], x)
            d = {"body": b, "vector": v}
            r = measured([d], "train")[0]
            candidates.append({"design": d, "score": list(score(r)), "source": f"tail:{tail}"})
            tail_log.append({"plan": tail % len(plans), "x": list(x), "score": list(score(r))})
        except ValueError as exc:
            if ledger.used != before:
                raise
            refusals.append({"groups": list(groups), "reason": str(exc), "tail": tail})
            if tail >= len(plans) * 2 and not candidates:
                raise RuntimeError("all spaces unavailable") from exc
            if tail > 10000:
                raise RuntimeError("cannot spend tail within legal bounds") from exc
        tail += 1
    ranked = sorted(enumerate(candidates), key=lambda x: (tuple(x[1]["score"]), -x[0]), reverse=True)
    unique = []
    seen = set()
    for _, c in ranked:
        h = digest(c["design"])
        if h not in seen:
            seen.add(h)
            unique.append(c)
        if len(unique) == TOP_SELECT:
            break
    if not unique:
        raise RuntimeError("no candidate")
    # A duplicate selected design is harmless but still charged, preserving caps.
    while len(unique) < TOP_SELECT:
        unique.append(unique[0])
    checks = measured([c["design"] for c in unique], "select")
    pick = max(range(len(unique)), key=lambda i: (score(checks[i]), -i))
    if ledger.used != budget:
        raise RuntimeError(f"budget not exhausted exactly: {ledger.used}/{budget}")
    return {"version": VERSION, "design": unique[pick]["design"], "selected": pick,
            "selection": [{"source": c["source"], "design_hash": digest(c["design"]), **r}
                          for c, r in zip(unique, checks)],
            "ledger": {"total": budget, "used": ledger.used, "lines": ledger.lines},
            "searches": searches, "tail_candidates": tail, "refusals": refusals,
            "tail_log": tail_log, "tail_plans": [{"start": st, "groups": list(gs)} for st, gs in plans],
            "candidate_count": len(candidates)}
