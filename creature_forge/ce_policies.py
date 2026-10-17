"""Non-AI policies of the causal engineer, run on the SAME `eng_tools.Workbench` and the SAME total budget as the scientist.

Every policy sees only what the bench gives it (the faulty robot, train/obs seeds, its own measurements). None sees the fault, the
severity, the repair matrix or the check/validate/confirm seeds. `run(bench, robot_view) -> record`; the record carries the submitted
design (`bench.best_design()`), the decisions and the bench ledger. All four are deterministic (`RandomPolicy` given its seed).

  Exhaustive   run every available counterfactual, rank them by (n_walking up, n_fell down, time_upright up), repair the top-2 distinct
               tools via the FIXED table `CF_TO_TOOL`. Budget split: the first repair gets floor(remaining / 2) after the experiments, the
               second repair gets everything that is left (refunds make it >= the first).
  ExpertRules  observe once, score each tool with the hand-written telemetry rules below (RULES), repair the two best-scored tools with the
               same split. The thresholds are nominal engineering values chosen by us BEFORE the evaluation instances existed in this
               work (not fitted to them, not tuned on them) and are disclosed here; unmatched cases fall back to FALLBACK_ORDER.
  RandomPolicy two random available counterfactuals, then two random tools, same split.
  Learned      (Level C, 2026-10-17) Exhaustive's procedure with the hand-made ranking replaced by a TRAINED repair-effect predictor
               (`repair_learner.RepairPredictor`, fitted on training robots only): observe, run every available catalogue counterfactual,
               rank the tools by predicted P(repair | observation, body features, counterfactual responses), repair the top two.
  Blind        one CMA-ES over the UNION of all control dimensions (posture, timing, feedback, stride, placement = 17) and four body
               parameters (foot_length, torso_mass, torque_limit, foot_friction), with the whole remaining budget. `walk_opt` allows at
               most four body parameters (`MAX_BODY_PARAMS`), so leg length (thigh and shank) is the only repair tool whose dimensions are
               NOT in the union; no benchmark fault uses it. The search is run by `UnionWorkbench.repair_union`, which uses the same
               accounting (charge before, refund unused, ledger line, best-design bookkeeping) as `Workbench.repair`.
"""
from __future__ import annotations

import copy
import random

from . import eng_tools
from . import fault_bench as fb
from . import walk_opt as wo

VERSION = "ce_policies_v1"

# counterfactual id -> repair tool (fixed table)
CF_TO_TOOL = {
    "foot_length_x1.3": "foot_length",
    "torso_mass_x0.75": "torso_mass",
    "torque_limit_x1.6": "torque_limit",
    "foot_friction_x2.5": "foot_friction",
    "pitch_ref_-0.08": "posture",
    "freq_x0.85": "timing",
    "feedback_gains_x2": "feedback",
    "placement_gains_0.5": "placement",
    "leg_length_x0.85": "leg_length",
}
UNION_BODY_PARAMS = ("foot_length", "torso_mass", "torque_limit", "foot_friction")
UNION_SUBSPACES = ("posture", "timing", "feedback", "stride", "placement")
FALLBACK_ORDER = ("posture", "timing", "feedback", "placement", "foot_length", "torso_mass", "torque_limit", "foot_friction",
                  "stride", "leg_length")


# ------------------------------------------------------------------------------------------------------------------ bench helpers
def available_counterfactuals(bench) -> list[str]:
    """Catalogue ids (catalogue order) whose change stays inside the bounds for the bench's current best design."""
    best = bench.best_design()
    out = []
    for cid, ch in eng_tools.COUNTERFACTUALS.items():
        try:
            fb.apply_changes(best["body"], best["vector"], ch)
        except fb.InvalidInstance:
            continue
        out.append(cid)
    return out


def _cf_score(res: dict) -> tuple:
    """Improvement key of a counterfactual result: more walking seeds, then fewer falls, then more time upright (proxy for fitness)."""
    d = res.get("deltas_vs_current") or {}
    return (float(d.get("n_walking", 0)), -float(d.get("n_fell", 0)), float(d.get("time_upright", 0.0)))


def run_repairs(bench, ranked_tools, n: int, min_budget_fn, log: list) -> list:
    """Repair up to `n` tools in rank order. First repair: floor(remaining / n) (n=2: half) -- all remaining when n == 1; the last one
    gets all that is left. A tool the bench refuses (no search room) is skipped. Returns the bench results."""
    done = []
    for tool in ranked_tools:
        if len(done) >= n:
            break
        rem = bench.remaining
        share = rem if len(done) == n - 1 else rem // (n - len(done))
        try:
            need = int(min_budget_fn(tool, bench.n_train))
        except Exception:       # noqa: BLE001 - tool without search room
            log.append({"tool": tool, "skipped": "no search room"})
            continue
        budget = share if share >= need else rem
        if budget < need:
            log.append({"tool": tool, "skipped": f"remaining {rem} < minimum {need}"})
            continue
        res = bench.repair(tool, int(budget))
        log.append({"tool": tool, "budget": int(budget), "ok": bool(res.get("ok")), "refused": res.get("refused"),
                    "train_walking": (res.get("best") or {}).get("train_walking"), "is_current_best": res.get("is_current_best")})
        if res.get("ok"):
            done.append(res)
    return done


class _Policy:
    name = "policy"

    def __init__(self, min_budget_fn=None):
        self._min = min_budget_fn or eng_tools.min_repair_budget

    def _record(self, bench, decisions: dict) -> dict:
        return {"version": VERSION, "policy": self.name, **decisions, "diagnosis_category": None,
                "submitted_design": bench.best_design(), "ledger": bench.ledger()}


# ------------------------------------------------------------------------------------------------------------------ Exhaustive
class Exhaustive(_Policy):
    name = "exhaustive"

    def run(self, bench, robot_view=None) -> dict:
        cfs = []
        for cid in available_counterfactuals(bench):
            res = bench.counterfactual(cid)
            if res.get("ok"):
                cfs.append({"id": cid, "tool": CF_TO_TOOL[cid], "score": _cf_score(res), "deltas": res.get("deltas_vs_current")})
        order = {c: i for i, c in enumerate(eng_tools.COUNTERFACTUALS)}
        ranked = sorted(cfs, key=lambda c: (tuple(-x for x in c["score"]), order[c["id"]]))
        tools = [c["tool"] for c in ranked]
        log: list = []
        run_repairs(bench, tools, 2, self._min, log)
        return self._record(bench, {"counterfactuals": [{k: v for k, v in c.items() if k != "deltas"} | {"score": list(c["score"])} for c in cfs],
                                    "ranking": [c["id"] for c in ranked], "repairs": log})


# ------------------------------------------------------------------------------------------------------------------ ExpertRules
def _g(med: dict, key: str, default=None):
    v = med.get(key)
    return default if v is None else v


def expert_scores(obs: dict, body: dict) -> tuple[dict, list]:
    """Score each tool from the initial observation summary. Returns ({tool: score}, fired rules [(rule, tool, weight)])."""
    med = obs.get("median") or {}
    pre = obs.get("pre_fall_median") or {}
    sat = max(_g(med, f"saturation_frac_{j}", 0.0) for j in ("hip", "knee", "ankle"))
    slip = _g(med, "slip_fraction", 0.0)
    fu95 = _g(med, "friction_utilisation_p95", 0.0)
    fumax = _g(med, "max_friction_utilisation", 0.0)
    pitch_end = _g(med, "pitch_end", 0.0)
    pitch_mean = _g(med, "pitch_mean", 0.0)
    pitch_slope = _g(med, "pitch_slope", 0.0)
    cop_slope = _g(med, "com_ahead_of_cop_over_L_slope", 0.0)
    ang_slope = _g(med, "angmom_norm_slope", 0.0)
    height_slope = _g(med, "com_height_over_L_slope", 0.0)
    trk = _g(med, "tracking_error_hip", 1.0)
    L = _g(med, "leg_length_m", None)
    f_hz = _g(med, "step_freq_hz", None)
    cp_front_end = _g(med, "cp_ahead_of_front_edge_over_L_end", _g(pre, "cp_ahead_of_front_edge_over_L", 0.0))
    cp_front_mean = _g(med, "cp_ahead_of_front_edge_over_L_mean", 0.0)
    cap_end = _g(med, "capture_margin_over_L_end", 0.0)
    step_len = _g(med, "step_length_over_L", None)
    foot_ratio = None
    try:
        if L:
            foot_ratio = float(body["foot_length"]) / float(L)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        foot_ratio = None
    ratio_f = None
    if f_hz is not None and L:
        ratio_f = f_hz / ((9.81 / L) ** 0.5 / (2 * 3.141592653589793))     # touchdown rate over the leg's pendulum frequency
    scores = {t: 0.0 for t in fb.TOOLS}
    fired = []

    def fire(rule, tool, w):
        scores[tool] += w
        fired.append((rule, tool, w))
    # R1 traction: horizontal foot-slip or a foot on its friction cone
    if slip > 0.10:
        fire("R1a slip_fraction > 0.10", "foot_friction", 2.0)
    if fu95 > 0.90 or fumax > 1.0:
        fire("R1b friction_utilisation_p95 > 0.9 or max > 1", "foot_friction", 1.0)
    # R2 actuator authority: torque demand pinned at the limit
    if sat > 0.20:
        fire("R2a max saturation_frac > 0.20", "torque_limit", 2.0)
    elif sat > 0.05:
        fire("R2b max saturation_frac > 0.05", "torque_limit", 1.0)
    # R3 heavy trunk: knees sag (COM height falling) with some torque saturation
    if height_slope < -0.02 and sat > 0.05:
        fire("R3 com_height_over_L_slope < -0.02 with saturation > 0.05", "torso_mass", 1.5)
    # R4 cadence: touchdown rate > 3.2 x the leg-pendulum frequency while the forward fall grows
    if ratio_f is not None and ratio_f > 3.2:
        fire("R4a step_freq_hz / f_pendulum > 3.2", "timing", 2.0)
        if pitch_slope > 0.02 or cop_slope > 0.02:
            fire("R4b ... with growing pitch or COM-ahead-of-CoP", "timing", 1.0)
    # R5 posture: steady forward lean while the joints still track their references
    if pitch_end > 0.10 and trk < 0.10:
        fire("R5a pitch_end > 0.10 rad with tracking_error_hip < 0.10 rad", "posture", 2.0)
    elif pitch_mean > 0.08:
        fire("R5b pitch_mean > 0.08 rad", "posture", 1.0)
    # R6 feedback: pitch and angular momentum drift away without saturation or slip (disturbances not rejected)
    if ang_slope > 0.05 and pitch_slope > 0.02 and sat <= 0.05 and slip <= 0.10:
        fire("R6 angmom_norm_slope > 0.05 and pitch_slope > 0.02, no saturation/slip", "feedback", 1.5)
    # R7 foot placement: the capture point ends beyond the toe edge and the steps are short
    if cp_front_end > 0.20:
        fire("R7a cp_ahead_of_front_edge_over_L_end > 0.20", "placement", 1.5)
    if step_len is not None and step_len < 0.35 and cp_front_end > 0.0:
        fire("R7b step_length_over_L < 0.35 with the capture point beyond the toe", "placement", 1.0)
    # R8 support base: short feet and the capture point outside the support interval
    if foot_ratio is not None and foot_ratio < 0.18:
        fire("R8a foot_length / leg length < 0.18", "foot_length", 1.5)
    if cap_end < 0.0 and cp_front_mean > 0.05:
        fire("R8b capture_margin_over_L_end < 0 with cp beyond the toe on average", "foot_length", 1.0)
    return scores, fired


class ExpertRules(_Policy):
    name = "expert"

    def run(self, bench, robot_view=None) -> dict:
        r = bench.observe()
        if not r.get("ok"):
            return self._record(bench, {"scores": {}, "fired": [], "ranking": [], "repairs": [], "refused": r.get("refused")})
        best = bench.best_design()
        scores, fired = expert_scores(r["observation"], best["body"])
        pos = {t: i for i, t in enumerate(FALLBACK_ORDER)}
        ranked = sorted(scores, key=lambda t: (-scores[t], pos.get(t, 99)))
        log: list = []
        run_repairs(bench, ranked, 2, self._min, log)
        return self._record(bench, {"scores": scores, "fired": [list(f) for f in fired], "ranking": ranked, "repairs": log})


# ------------------------------------------------------------------------------------------------------------------ Random
class RandomPolicy(_Policy):
    name = "random"

    def __init__(self, seed: int, min_budget_fn=None):
        super().__init__(min_budget_fn)
        self.seed = int(seed)

    def run(self, bench, robot_view=None) -> dict:
        rng = random.Random(self.seed)
        avail = available_counterfactuals(bench)
        picks = rng.sample(avail, min(2, len(avail)))
        cfs = []
        for cid in picks:
            res = bench.counterfactual(cid)
            cfs.append({"id": cid, "ok": bool(res.get("ok")), "refused": res.get("refused")})
        tools = list(fb.TOOLS)
        rng.shuffle(tools)
        log: list = []
        run_repairs(bench, tools, 2, self._min, log)
        return self._record(bench, {"seed": self.seed, "counterfactuals": cfs, "tool_order": tools, "repairs": log})


# ------------------------------------------------------------------------------------------------------------------ Blind
class UnionWorkbench(eng_tools.Workbench):
    """`Workbench` plus `repair_union` (see the module docstring). Everything else is inherited unchanged."""

    def union_space(self) -> wo.SearchSpace:
        from .walk_pipelines import _space
        return _space(17, UNION_SUBSPACES, UNION_BODY_PARAMS)

    def union_min_budget(self) -> int:
        return self.n_train * (1 + eng_tools.MIN_GENERATIONS * eng_tools.population(self.union_space()))

    def repair_union(self, budget: int) -> dict:
        tool = "union"
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            return self._refuse("repair", "budget must be a non-negative integer", tool=tool)
        need = self.union_min_budget()
        if budget < need:
            return self._refuse("repair", f"budget {budget} is below the minimum {need} for the union space", tool=tool)
        if budget > self.remaining:
            return self._refuse("repair", f"budget {budget} exceeds the {self.remaining} rollouts remaining", tool=tool)
        parent = self._best
        d = self.designs[parent]
        self._spend(budget, "repair", {"tool": tool, "design": parent, "budget": budget})
        try:
            fn = self._cma_fn or wo.cma_search
            res = fn(d["body"], list(d["vector"]), self.union_space(), budget=int(budget), train_seeds=list(self.train_seeds),
                     noise_seed=self._noise + 7919 * self._n_repairs, pool=self.pool, variation=self.variation)
            if int(res["rollouts_used"]) > int(budget):
                raise RuntimeError(f"cma_search used {res['rollouts_used']} rollouts, over the budget {budget}")
        except ValueError as exc:
            self.budget.refund(budget, "repair", {"tool": tool, "reason": str(exc)})
            return {"ok": False, "refused": f"union repair unavailable for this design: {exc}"}
        except Exception:
            self.budget.refund(budget, "repair", {"tool": tool, "reason": "error"})
            raise
        self._n_repairs += 1
        used = int(res["rollouts_used"])
        if used < budget:
            self.budget.refund(budget - used, "repair", {"tool": tool, "unused": budget - used})
        best = res["best"]
        j = self._add_design("repair:union", best["body"], best["vector"], parent=parent, tool=tool,
                             train_walking=int(best["walking_count"]), train_fitness=float(best["mean_fitness"]), rollouts=used)
        init = res.get("init") or {}
        if self._best_score is None and init:
            self._best_score = eng_tools._score(init)
        if self._best_score is None or eng_tools._score(best) > self._best_score:
            self._best_score, self._best = eng_tools._score(best), j
        return {"ok": True, "tool": tool, "design_index": j, "rollouts_used": used,
                "start": {"walking_count": init.get("walking_count"), "mean_fitness": init.get("mean_fitness")},
                "best": {"body": copy.deepcopy(best["body"]), "vector": list(best["vector"]),
                         "train_walking": int(best["walking_count"]), "train_n": len(self.train_seeds),
                         "train_fitness": float(best["mean_fitness"])},
                "is_current_best": self._best == j}


class Blind(_Policy):
    name = "blind"

    def run(self, bench, robot_view=None) -> dict:
        if not hasattr(bench, "repair_union"):
            raise TypeError("Blind needs a UnionWorkbench (ce_policies.UnionWorkbench)")
        budget = int(bench.remaining)
        res = bench.repair_union(budget)
        return self._record(bench, {"space": {"subspaces": list(UNION_SUBSPACES), "body_params": list(UNION_BODY_PARAMS)},
                                    "repairs": [{"tool": "union", "budget": budget, "ok": bool(res.get("ok")),
                                                 "refused": res.get("refused"),
                                                 "train_walking": (res.get("best") or {}).get("train_walking")}]})


class Learned(_Policy):
    name = "learned"

    def __init__(self, predictor, min_budget_fn=None):
        super().__init__(min_budget_fn)
        if predictor is None:
            raise ValueError("the learned policy needs a trained RepairPredictor")
        self.predictor = predictor

    def run(self, bench, robot_view=None) -> dict:
        r0 = bench.observe()
        obs0 = r0.get("observation") or {}
        cf_results = {}
        for cid in available_counterfactuals(bench):
            res = bench.counterfactual(cid)
            cf_results[cid] = {"deltas": res.get("deltas_vs_current") or {}} if res.get("ok") else {"refused": res.get("refused")}
        for cid in eng_tools.COUNTERFACTUALS:
            cf_results.setdefault(cid, {"refused": "unavailable for this design"})
        feats = (robot_view or {}).get("features") or {}
        advice = self.predictor.advise(obs0, feats, cf_results)
        log: list = []
        run_repairs(bench, [a["tool"] for a in advice], 2, self._min, log)
        return self._record(bench, {"advice": advice, "repairs": log, "counterfactuals": sorted(k for k, v in cf_results.items()
                                                                                                if "deltas" in v)})


def make_policy(name: str, *, seed: int = 0, min_budget_fn=None, predictor=None):
    if name == "learned":
        return Learned(predictor, min_budget_fn)
    if name == "exhaustive":
        return Exhaustive(min_budget_fn)
    if name == "expert":
        return ExpertRules(min_budget_fn)
    if name == "random":
        return RandomPolicy(seed, min_budget_fn)
    if name == "blind":
        return Blind(min_budget_fn)
    raise ValueError(f"unknown policy {name!r}")
