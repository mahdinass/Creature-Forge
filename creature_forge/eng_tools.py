"""Budgeted engineering instruments for the causal engineer (`eng_tools_v1`).

`Workbench` is a lab bench for ONE faulty robot. Every instrument call is charged to a `walk_pipelines.Budget` BEFORE it runs
and unused rollouts are refunded; `ledger()` returns every line. Refusals (unknown tool, budget too small, counterfactual out of
bounds, over budget) cost nothing, are never clipped and are written to the ledger as zero-cost lines.

Instruments
  observe()              physics_probe.observe on the obs seeds of the current best design (cost n_obs).
  counterfactual(change) one change of `COUNTERFACTUALS` applied to the current best design, observed on the SAME obs seeds
                         (cost n_obs) with deltas of the numeric median summary vs the current design. If the current design
                         has not been observed yet it is observed first and charged as its own ledger line (so the first
                         counterfactual costs 2 * n_obs; later ones n_obs).
  repair(tool, budget)   CMA-ES restricted to the tool's dimensions, starting at the current best design, on the TRAIN seeds
                         (cost <= budget, refused unless it covers the initial point and >= 3 generations).
Final verification is NOT on the bench (`fault_bench.verify`).
"""
from __future__ import annotations

import copy
import math
from typing import Callable, Sequence

from .arena import VARIATION_PRESET
from .fault_bench import InvalidInstance, TOOLS, apply_changes
from .walk_pipelines import Budget, BudgetExceeded
from . import walk_opt as wo

VERSION = "eng_tools_v1"
MIN_GENERATIONS = 3

# The fixed counterfactual catalogue: small matched interventions. id -> list of atomic changes. A change that would leave the
# guided / controller bounds is UNAVAILABLE for that robot (never clipped).
COUNTERFACTUALS = {
    "foot_length_x1.3": [{"param": "foot_length", "op": "scale", "value": 1.3}],
    "torso_mass_x0.75": [{"param": "torso_mass", "op": "scale", "value": 0.75}],
    "torque_limit_x1.6": [{"param": "torque_limit", "op": "scale", "value": 1.6}],
    "foot_friction_x2.5": [{"param": "foot_friction", "op": "scale", "value": 2.5}],
    "pitch_ref_-0.08": [{"param": "pitch_ref", "op": "add", "value": -0.08}],
    "freq_x0.85": [{"param": "freq", "op": "scale", "value": 0.85}],
    "feedback_gains_x2": [{"param": "balance_gain", "op": "scale", "value": 2.0}, {"param": "pitch_kp", "op": "scale", "value": 2.0}],
    "placement_gains_0.5": [{"param": "fp_kd", "op": "set", "value": 0.5}, {"param": "fp_kv", "op": "set", "value": 0.5}],
    "leg_length_x0.85": [{"param": "leg_length", "op": "scale", "value": 0.85}],
}

# Parametric counterfactuals (added 2026-10-17 after the pilot1 audit, F4: the fixed catalogue is one-directional). A policy composes
# its own matched intervention of ONE or TWO atomic changes, each a parameter with a symbolic level. Multiplicative parameters take a
# scale level; parameters that are signed or may sit at 0 take an additive level, a signed fraction of the parameter's bound range
# (R = upper - lower). Id grammar: "<param>@<level>" or "<param>@<level>&<param>@<level>" (two different parameters). A change that
# would leave the guided / controller bounds is refused, never clipped. The fixed catalogue above is unchanged (non-AI baselines).
CF_SCALE_LEVELS = {"x0.5": 0.5, "x0.7": 0.7, "x0.85": 0.85, "x1.2": 1.2, "x1.5": 1.5, "x2": 2.0}
CF_ADD_LEVELS = {"-0.2R": -0.2, "-0.1R": -0.1, "-0.05R": -0.05, "+0.05R": 0.05, "+0.1R": 0.1, "+0.2R": 0.2}
CF_ADDITIVE = ("duty", "knee_shift", "stance_knee", "hip_bias", "pitch_ref", "sync_gain", "start_lean", "fp_kd", "fp_kv")
CF_BODY_PARAMS = ("torso_mass", "foot_length", "torque_limit", "foot_friction", "leg_length", "leg_density")
CF_PARAMS = tuple(wo.ALL_NAMES) + CF_BODY_PARAMS
CF_LEVELS = tuple(CF_SCALE_LEVELS) + tuple(CF_ADD_LEVELS)
CF_MAX_ATOMS = 2


def _ctrl_range(param: str) -> tuple[float, float]:
    from .phasegait_fp import LOWER17, UPPER17
    i = wo.ALL_NAMES.index(param)
    return float(LOWER17[i]), float(UPPER17[i])


def levels_for(param: str) -> tuple[str, ...]:
    if param not in CF_PARAMS:
        raise ValueError(f"unknown parameter {param!r}; known: {list(CF_PARAMS)}")
    return tuple(CF_ADD_LEVELS) if param in CF_ADDITIVE else tuple(CF_SCALE_LEVELS)


def parametric_change(param: str, level: str) -> dict:
    """One atomic change {"param", "op", "value"} for (param, level). Raises ValueError for an unknown parameter or a level of the
    wrong kind (a scale level on an additive parameter or vice versa)."""
    if level not in levels_for(param):
        raise ValueError(f"level {level!r} is not valid for {param}; valid: {list(levels_for(param))}")
    if param in CF_ADDITIVE:
        lo, hi = _ctrl_range(param)
        return {"param": param, "op": "add", "value": round(CF_ADD_LEVELS[level] * (hi - lo), 10)}
    return {"param": param, "op": "scale", "value": CF_SCALE_LEVELS[level]}


def parametric_id(atoms) -> str:
    """Canonical id of [(param, level), ...] (order kept: the first atom is the primary change)."""
    return "&".join(f"{p}@{l}" for p, l in atoms)


def parse_counterfactual(cid: str) -> list[dict]:
    """Atomic changes of a catalogue id or a parametric id. Raises ValueError if neither."""
    if cid in COUNTERFACTUALS:
        return copy.deepcopy(COUNTERFACTUALS[cid])
    parts = str(cid).split("&")
    if not 1 <= len(parts) <= CF_MAX_ATOMS:
        raise ValueError(f"a counterfactual has 1-{CF_MAX_ATOMS} atomic changes, got {len(parts)}")
    out, seen = [], set()
    for part in parts:
        if part.count("@") != 1:
            raise ValueError(f"atomic change {part!r} must be '<param>@<level>'")
        p, l = part.split("@")
        if p in seen:
            raise ValueError(f"parameter {p!r} appears twice")
        seen.add(p)
        out.append(parametric_change(p, l))
    return out


class RepairRefused(ValueError):
    """A repair cannot run as asked (unknown tool, budget too small, no search room)."""


def tool_space(tool: str, family: int = 17) -> wo.SearchSpace:
    from .walk_pipelines import _space
    if tool not in TOOLS:
        raise RepairRefused(f"unknown tool {tool!r}; known: {list(TOOLS)}")
    t = TOOLS[tool]
    return _space(family, t["subspaces"], t["body"])


def population(space: wo.SearchSpace) -> int:
    return max(2, 4 + int(math.floor(3 * math.log(space.dim))))


def min_repair_budget(tool: str, n_train: int) -> int:
    """Initial evaluation + MIN_GENERATIONS generations of the default population, in rollouts."""
    return n_train * (1 + MIN_GENERATIONS * population(tool_space(tool)))


def run_repair(robot: dict, tool: str, budget: int, train_seeds: Sequence[int], noise_seed: int, pool=None, *,
               cma_fn: Callable | None = None, variation=VARIATION_PRESET) -> dict:
    """cma_search over the tool's dimensions from `robot` ({"body","vector"}). Raises RepairRefused (a ValueError) when the budget
    is below `min_repair_budget`, or ValueError when the tool has no room inside the bounds. Returns the cma_search result."""
    space = tool_space(tool)
    need = min_repair_budget(tool, len(train_seeds))
    if int(budget) < need:
        raise RepairRefused(f"budget {budget} is below the minimum {need} for tool {tool} ({MIN_GENERATIONS} generations)")
    fn = cma_fn or wo.cma_search
    res = fn(robot["body"], list(robot["vector"]), space, budget=int(budget), train_seeds=list(train_seeds),
             noise_seed=int(noise_seed), pool=pool, variation=variation)
    if int(res["rollouts_used"]) > int(budget):
        raise RuntimeError(f"cma_search used {res['rollouts_used']} rollouts, over the budget {budget}")
    return res


def _score(rec: dict) -> tuple:
    return (int(rec["walking_count"]), int(rec["survival_count"]), float(rec["mean_fitness"]))


def _numeric(d) -> dict:
    return {k: float(v) for k, v in (d or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}


class Workbench:
    """A budgeted lab bench for one faulty robot. See the module docstring."""

    def __init__(self, robot: dict, *, total_budget: int, seeds: dict, pool=None, n_train: int = 4, n_obs: int = 4,
                 observe_fn: Callable | None = None, cma_fn: Callable | None = None, noise_seed: int = 0,
                 variation=VARIATION_PRESET):
        if len(robot["vector"]) != 17:
            raise ValueError("robot vector must be 17-D")
        for role, n in (("train", n_train), ("obs", n_obs)):
            if role not in seeds or len(seeds[role]) < n or n < 1:
                raise ValueError(f"seeds[{role!r}] needs at least {n} seeds")
        self.train_seeds = [int(s) for s in seeds["train"][:n_train]]
        self.obs_seeds = [int(s) for s in seeds["obs"][:n_obs]]
        if set(self.train_seeds) & set(self.obs_seeds):
            raise ValueError("train and obs seeds must be disjoint")
        self.n_train, self.n_obs = int(n_train), int(n_obs)
        self.budget = Budget(int(total_budget))
        self.pool, self.variation = pool, variation
        self._observe_fn, self._cma_fn, self._noise = observe_fn, cma_fn, int(noise_seed)
        self.designs: list[dict] = []
        self._add_design("initial", robot["body"], robot["vector"])
        self._best = 0                 # index into designs
        self._best_score: tuple | None = None
        self._obs_cache: dict[int, dict] = {}
        self._n_repairs = 0

    # ------------------------------------------------------------------ bookkeeping
    @property
    def remaining(self) -> int:
        return self.budget.remaining

    def _add_design(self, source: str, body, vector, **extra) -> int:
        self.designs.append({"index": len(self.designs), "source": source, "body": copy.deepcopy(dict(body)),
                             "vector": [float(x) for x in vector], **extra})
        return len(self.designs) - 1

    def best_design(self) -> dict:
        d = self.designs[self._best]
        return {"body": copy.deepcopy(d["body"]), "vector": list(d["vector"]), "index": d["index"], "source": d["source"]}

    def ledger(self) -> dict:
        lines = copy.deepcopy(self.budget.lines)
        assert self.budget.used == sum(l["n"] for l in lines)
        return {"version": VERSION, "total": self.budget.total, "used": self.budget.used, "remaining": self.budget.remaining,
                "lines": lines, "designs": [{k: v for k, v in d.items() if k not in ("body", "vector")} for d in self.designs]}

    def _refuse(self, item: str, reason: str, **detail) -> dict:
        self.budget.charge(0, f"refused:{item}", {"reason": reason, **detail})
        return {"ok": False, "refused": reason}

    def _spend(self, n: int, item: str, detail: dict):
        self.budget.charge(n, item, detail)

    def _observe(self, body, vector, seeds) -> dict:
        fn = self._observe_fn
        if fn is None:
            from .physics_probe import observe as fn
        return fn(body, list(vector), list(seeds), variation=self.variation, duration=10.0, pool=self.pool)

    # ------------------------------------------------------------------ instruments
    def observe(self, seeds_role: str = "obs") -> dict:
        if seeds_role != "obs":
            return self._refuse("observe", f"seeds_role must be 'obs', got {seeds_role!r}")
        if self.remaining < self.n_obs:
            return self._refuse("observe", f"needs {self.n_obs} rollouts, {self.remaining} remain")
        idx = self._best
        d = self.designs[idx]
        self._spend(self.n_obs, "observe", {"design": idx})
        try:
            out = self._observe(d["body"], d["vector"], self.obs_seeds)
        except Exception:
            self.budget.refund(self.n_obs, "observe", {"design": idx, "reason": "error"})
            raise
        self._settle(self.n_obs, out, "observe", idx)
        self._obs_cache[idx] = out
        return {"ok": True, "design_index": idx, "observation": out}

    def _settle(self, charged: int, out: dict, item: str, idx) -> None:
        used = out.get("rollouts") if isinstance(out, dict) else None
        if isinstance(used, int) and not isinstance(used, bool) and 0 <= used < charged:
            self.budget.refund(charged - used, item, {"design": idx, "unused": charged - used})

    def counterfactual(self, change) -> dict:
        cid = change.get("id") if isinstance(change, dict) else change
        try:
            atoms = parse_counterfactual(cid)
        except ValueError as exc:
            return self._refuse("counterfactual", f"unknown counterfactual {cid!r} ({exc}); catalogue: {list(COUNTERFACTUALS)} or "
                                                  f"parametric '<param>@<level>[&<param>@<level>]'")
        d = self.designs[self._best]
        try:
            body, vec = apply_changes(d["body"], d["vector"], atoms)
        except InvalidInstance as exc:
            return self._refuse("counterfactual", f"unavailable: {exc}", id=cid)
        need = self.n_obs * (1 if self._best in self._obs_cache else 2)
        if self.remaining < need:
            return self._refuse("counterfactual", f"needs {need} rollouts, {self.remaining} remain", id=cid)
        if self._best not in self._obs_cache:
            self.observe()
        cur = self._obs_cache[self._best]
        self._spend(self.n_obs, "counterfactual", {"id": cid, "design": self._best})
        try:
            out = self._observe(body, vec, self.obs_seeds)
        except Exception:
            self.budget.refund(self.n_obs, "counterfactual", {"id": cid, "reason": "error"})
            raise
        self._settle(self.n_obs, out, "counterfactual", self._best)
        j = self._add_design(f"counterfactual:{cid}", body, vec, parent=self._best)
        a, b = _numeric(cur.get("median")), _numeric(out.get("median"))
        deltas = {k: b[k] - a[k] for k in b if k in a}
        for k in ("n_walking", "n_fell"):
            if isinstance(out.get(k), (int, float)) and isinstance(cur.get(k), (int, float)):
                deltas[k] = out[k] - cur[k]
        return {"ok": True, "id": cid, "changes": copy.deepcopy(atoms), "design_index": j,
                "observation": out, "deltas_vs_current": deltas}

    def repair(self, tool: str, budget: int) -> dict:
        if tool not in TOOLS:
            return self._refuse("repair", f"unknown tool {tool!r}; known: {list(TOOLS)}")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            return self._refuse("repair", "budget must be a non-negative integer", tool=tool)
        need = min_repair_budget(tool, self.n_train)
        if budget < need:
            return self._refuse("repair", f"budget {budget} is below the minimum {need} (initial point + "
                                          f"{MIN_GENERATIONS} generations) for tool {tool}", tool=tool)
        if budget > self.remaining:
            return self._refuse("repair", f"budget {budget} exceeds the {self.remaining} rollouts remaining", tool=tool)
        parent = self._best
        d = self.designs[parent]
        self._spend(budget, "repair", {"tool": tool, "design": parent, "budget": budget})
        try:
            res = run_repair({"body": d["body"], "vector": d["vector"]}, tool, budget, self.train_seeds,
                             self._noise + 7919 * self._n_repairs, self.pool, cma_fn=self._cma_fn, variation=self.variation)
        except ValueError as exc:
            self.budget.refund(budget, "repair", {"tool": tool, "reason": str(exc)})
            return {"ok": False, "refused": f"tool {tool} unavailable for this design: {exc}"}
        except Exception:
            self.budget.refund(budget, "repair", {"tool": tool, "reason": "error"})
            raise
        self._n_repairs += 1
        used = int(res["rollouts_used"])
        if used < budget:
            self.budget.refund(budget - used, "repair", {"tool": tool, "unused": budget - used})
        best = res["best"]
        j = self._add_design(f"repair:{tool}", best["body"], best["vector"], parent=parent, tool=tool,
                             train_walking=int(best["walking_count"]), train_fitness=float(best["mean_fitness"]),
                             rollouts=used)
        init = res.get("init") or {}
        if self._best_score is None and init:
            self._best_score = _score(init)
        if self._best_score is None or _score(best) > self._best_score:
            self._best_score, self._best = _score(best), j
        return {"ok": True, "tool": tool, "design_index": j, "rollouts_used": used,
                "start": {"walking_count": init.get("walking_count"), "mean_fitness": init.get("mean_fitness")},
                "best": {"body": copy.deepcopy(best["body"]), "vector": list(best["vector"]),
                         "train_walking": int(best["walking_count"]), "train_n": len(self.train_seeds),
                         "train_fitness": float(best["mean_fitness"])},
                "is_current_best": self._best == j}
