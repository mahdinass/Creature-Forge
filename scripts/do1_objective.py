"""DO-1: a versioned, recovery-aware objective for the plant repair CMA-ES (no change to the engine or the frozen verifier).

Why (source analysis, 2026-10-21). The plant repair (`HDBWorkbench.repair` -> `hidden_plant.plant_cma` -> `walk_opt.cma_search`)
evaluates each candidate on the first 4 train seeds and
  * updates the CMA mean/covariance by the rank of `mean_fitness` only (walk_opt `_CMA.update`, rank-based);
  * reports the best candidate by `_score` = (walking_count, survival_count, mean_fitness).
`locomotion.fitness_components` = survival + 3 progress + steps - effort - pitch + walking bonus, with
progress = clip(speed_effective / 0.4, -1, 1) * validity. It never sees the faulty robot, so
  * L1: the faulty robot slides 6.88 m per 10 s; above 4 m (0.4 m/s) progress is saturated, so the objective has no gradient
    towards "clearly farther than faulty" (needs >= ~7.4 m) and every candidate walks 23/24 but is WORSE;
  * L4: candidates walk 4/4 train seeds (walking bonus saturated); `validity` is 1 everywhere inside the walking gates, so
    nothing rewards distance from the gates, while progress still rewards speed up to 0.4 m/s. The submitted designs walk
    15/16 robust and 19/24 validation (one seed short of PASS).

DO-1 replaces ONLY the per-candidate scalar handed to the unchanged `cma_search` (as `mean_fitness`), with
  J = 1000 W + (100 + 10 M                     if W = n and shortfall = 0      feasible: robustness margin
              -10 min(shortfall, 50) + M       otherwise)                      infeasible: paired displacement first
        + 0.01 f                                                               frozen fitness, tie-break only
  W          walking train seeds (n = 4), strict precedence (steps of 1000 exceed every other term's range);
  shortfall  max(0, TAU_D - median_s(score_s - faulty_s)) / TAU_D: paired forward displacement against the faulty design on
             the SAME train seeds and conditions, with the verifier's walk-score rule (hdb_evidence.walk_score);
  M          mean over seeds of the seed margin: -1 if fell, else the smallest normalised slack of the frozen walking gates
             (speed, step rate, alternation, chatter, flight, slip, body contact, saturation, pitch), each clipped to [-1, 1];
  f          the frozen mean fitness.
Feasible candidates always rank above infeasible ones with the same W (Deb's feasibility rules, encoded for the rank-based CMA).
Because `_score` is unchanged, the reported best is still the most-walking candidate, then survival, then J.

Costs and seeds: the faulty design is walked once per episode on the same train seeds (4 plant rollouts, charged as the
ledger line `do1_train_baseline` and deducted from that repair's budget, so the plant total stays <= 700). No validation,
confirmation, check or sealed seed is used. Bounds, tool spaces, CMA settings and noise seeds are those of the frozen repair.
Not covered by v1: 20 s (long-duration) stability, which enters only through the pitch/fall margins; a dedicated term would
double the rollout cost per candidate.

`Do1Workbench` subclasses the frozen `EvidenceWorkbench` and overrides `repair` only.
"""
from __future__ import annotations

import copy
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import creature_walk as cw                        # noqa: E402
from creature_forge import hidden_plant as hp                         # noqa: E402
from creature_forge import locomotion as loc                          # noqa: E402
from creature_forge import r2                                         # noqa: E402
from creature_forge import walk_opt as wo                             # noqa: E402
from creature_forge.forge_pool import InlinePool, is_error            # noqa: E402
from creature_forge.hdb_evidence import EvidenceWorkbench, walk_score # noqa: E402
from creature_forge.hdb_workbench import min_budget, tool_space       # noqa: E402

VERSION = "do1_objective_v1"
TAU_D = 0.75            # m: 1.5 x verdict_v1's 0.5 m minimum effect (margin for train -> validation shrinkage); fixed a priori
W_STEP = 1000.0
FEASIBLE_OFFSET = 100.0
MARGIN_WEIGHT = 10.0
SHORT_WEIGHT = 10.0
SHORT_CAP = 50.0
FIT_WEIGHT = 0.01
DURATION = 10.0
# (gate, metric key, criteria attribute, kind): "min" gates need metric >= threshold, "max" gates metric <= threshold
GATES = (
    ("speed", "speed_upright", "min_speed", "min"),
    ("step_rate", "valid_step_rate", "min_step_rate", "min"),
    ("alternation", "alternation", "min_alternation", "min"),
    ("touchdown", "raw_touchdown_rate", "max_touchdown_rate", "max"),
    ("flight", "flight_frac", "max_flight_frac", "max"),
    ("slip", "slip_frac", "max_slip_frac", "max"),
    ("body_contact", "body_contact_frac", "max_body_contact_frac", "max"),
    ("saturation", "saturation_frac", "max_saturation_frac", "max"),
    ("pitch", "max_abs_pitch", "max_abs_pitch", "max"),
)
OBJECTIVE_SPEC = {"version": VERSION, "tau_d_m": TAU_D, "w_step": W_STEP, "feasible_offset": FEASIBLE_OFFSET,
                  "margin_weight": MARGIN_WEIGHT, "short_weight": SHORT_WEIGHT, "short_cap": SHORT_CAP,
                  "fit_weight": FIT_WEIGHT, "gates": [g[0] for g in GATES], "baseline": "faulty design 0, same train seeds"}


# ------------------------------------------------------------------------------------------------------------ physics job
def do1_walk_job(job: dict) -> dict:
    """hidden_plant.walk_job plus the walking-gate metrics and thresholds (same rollout, metrics and fitness; the returned
    walk_job fields are identical)."""
    t0 = time.perf_counter()
    try:
        b = cw._body(job["body"])
        tr = hp.plant_rollout(job.get("plant"), b, job["vector"], job["seed"], duration=job["duration"],
                              perturb=job.get("perturb"), friction_factor=job.get("friction_factor"), rich=False)
        if job.get("friction_factor") is not None:
            from creature_forge.arena import _body_with_friction
            b = cw._body(_body_with_friction(b.as_dict(), float(job["friction_factor"]))[0])
        crit = cw.creature_criteria(b)
        m = loc.compute_metrics(tr, crit)
        fit = loc.fitness_components(m, crit)["total"]
        return {"ok": True, "seed": int(job["seed"]), "walking": bool(m["walking"]), "fell": bool(m["fell"]),
                "label": m["label"], "fitness": float(fit), "forward_disp_upright": float(m["forward_disp_upright"]),
                "valid_steps": int(m["valid_steps"]), "fall_time": m["fall_time"], "wall_s": time.perf_counter() - t0,
                "gates": {key: float(m[key]) for _, key, _, _ in GATES},
                "criteria": {attr: float(getattr(crit, attr)) for _, _, attr, _ in GATES}}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "wall_s": time.perf_counter() - t0}


# ------------------------------------------------------------------------------------------------------------ objective
def gate_slacks(row: dict) -> dict:
    """Normalised slack of every walking gate (> 0 inside, < 0 violated), clipped to [-1, 1]."""
    out = {}
    for name, key, attr, kind in GATES:
        x, thr = float(row["gates"][key]), float(row["criteria"][attr])
        if name == "alternation":
            scale = 1.0 - thr
        else:
            scale = thr
        s = (x - thr) / scale if kind == "min" else (thr - x) / scale
        out[name] = float(np.clip(s, -1.0, 1.0)) if math.isfinite(s) else -1.0
    return out


def seed_margin(row: dict) -> tuple[float, str | None]:
    """(margin, binding gate): -1 for an error or a fall, else the smallest gate slack."""
    if not row.get("ok"):
        return -1.0, "error"
    if row["fell"]:
        return -1.0, "fall"
    sl = gate_slacks(row)
    gate = min(sl, key=lambda k: (sl[k], k))
    return sl[gate], gate


def objective(rows: list, base_scores: list) -> dict:
    """All DO-1 components of one candidate from its train-seed rows and the faulty design's walk scores on the same seeds."""
    n = len(rows)
    if n == 0 or len(base_scores) != n:
        raise ValueError("objective needs one faulty walk score per train row")
    fits = [r2.ERROR_FITNESS if not r.get("ok") or not math.isfinite(r["fitness"]) else float(r["fitness"]) for r in rows]
    walking = sum(1 for r in rows if r.get("ok") and r["walking"])
    survival = sum(1 for r in rows if r.get("ok") and not r["fell"])
    scores = [walk_score(r) for r in rows]
    diffs = [(0.0 if s is None else s) - float(b) for s, b in zip(scores, base_scores)]
    med = float(np.median(diffs))
    short = max(0.0, TAU_D - med) / TAU_D
    margins = [seed_margin(r) for r in rows]
    m = float(np.mean([g for g, _ in margins]))
    mean_fit = float(np.mean(fits))
    feasible = walking == n and short == 0.0
    tier = (FEASIBLE_OFFSET + MARGIN_WEIGHT * m) if feasible else (-SHORT_WEIGHT * min(short, SHORT_CAP) + m)
    j = W_STEP * walking + tier + FIT_WEIGHT * mean_fit
    errs = [f"seed {r.get('seed')}: {r['error']}" for r in rows if not r.get("ok")]
    return {"J": float(j), "walking_count": int(walking), "survival_count": int(survival), "feasible": bool(feasible),
            "median_diff_m": med, "mean_diff_m": float(np.mean(diffs)), "wins": int(sum(1 for d in diffs if d > 0.05)),
            "losses": int(sum(1 for d in diffs if d < -0.05)), "shortfall": float(short), "margin": m,
            "mean_fitness_v1": mean_fit, "n": n, "error": "; ".join(errs) if errs else None,
            "per_seed": [{"seed": r.get("seed"), "ok": bool(r.get("ok")), "walking": bool(r.get("walking")),
                          "fell": bool(r.get("fell")), "label": r.get("label"), "fall_time": r.get("fall_time"),
                          "fitness_v1": fits[k], "score": scores[k], "faulty_score": float(base_scores[k]),
                          "diff_m": diffs[k], "margin": margins[k][0], "binding_gate": margins[k][1],
                          "slacks": gate_slacks(r) if r.get("ok") else None}
                         for k, r in enumerate(rows)]}


def make_do1_eval_fn(plant, train_seeds, base_scores, *, variation=None, duration: float = DURATION, pool=None,
                     log: list | None = None):
    """An `eval_fn` for walk_opt.cma_search, built like hidden_plant.make_eval_fn (same jobs, seeds and conditions) but
    returning the DO-1 scalar as `mean_fitness`; every candidate's components are appended to `log` in evaluation order."""
    from creature_forge.arena import VARIATION_PRESET
    variation = VARIATION_PRESET if variation is None else variation
    seeds = [int(s) for s in train_seeds]
    conds = hp._conditions(seeds, variation)
    plant = hp.normalize_plant(plant)
    pool = pool or InlinePool()
    base = [float(b) for b in base_scores]
    if len(base) != len(seeds):
        raise ValueError("one faulty walk score per train seed is required")

    def eval_fn(cands):
        jobs = []
        for b, v in cands:
            for s, c in zip(seeds, conds):
                jobs.append({"vector": [float(x) for x in v], "body": dict(b), "seed": s, "duration": duration,
                             "perturb": c["perturb"], "friction_factor": c["friction_factor"], "plant": plant})
        res: list = [None] * len(jobs)
        for i, r in pool.imap(do1_walk_job, jobs):
            res[i] = {"ok": False, "error": r[1]} if isinstance(r, tuple) and is_error(r) else r
        recs = []
        S = len(seeds)
        for ci, (b, v) in enumerate(cands):
            comp = objective(res[ci * S:(ci + 1) * S], base)
            if log is not None:
                log.append({"vector": [float(x) for x in v], "body": copy.deepcopy(dict(b)), **comp})
            recs.append({"walking_count": comp["walking_count"], "survival_count": comp["survival_count"],
                         "mean_fitness": comp["J"], "error": comp["error"]})
        return recs

    return eval_fn


# ------------------------------------------------------------------------------------------------------------ workbench
class Do1Workbench(EvidenceWorkbench):
    """EvidenceWorkbench whose plant repair optimises the DO-1 objective. Every other instrument is inherited unchanged."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._do1_base: dict | None = None        # the faulty design on the train seeds (charged once)
        self.do1_repairs: list[dict] = []

    def _do1_baseline(self, seeds: list) -> tuple[dict, int]:
        """(baseline, rollouts charged now): the faulty design 0 on `seeds`, walked once and cached (repair refuses other seeds)."""
        if self._do1_base is not None:
            return self._do1_base, 0
        d = self.designs[0]
        self._spend(len(seeds), "do1_train_baseline", {"design": 0, "n": len(seeds), "objective": VERSION})
        rows = hp.walk_seeds(self._plant, d["body"], d["vector"], seeds, variation=self.variation, pool=self.pool)
        self._do1_base = {"seeds": list(seeds), "scores": [0.0 if walk_score(r) is None else walk_score(r) for r in rows],
                          "pass": [bool(r.get("ok") and r["walking"]) for r in rows],
                          "errors": [r.get("error") for r in rows if not r.get("ok")]}
        return self._do1_base, len(seeds)

    def repair(self, tool: str, budget: int, *, n_train: int | None = None, init: dict | None = None) -> dict:
        """HDBWorkbench.repair with the DO-1 eval_fn. Identical refusals, seeds, bounds, noise seed and bookkeeping; the
        first repair also pays the 4-rollout train baseline out of its budget."""
        from creature_forge import fault_bench as fb
        n_train = self.n_train if n_train is None else int(n_train)
        if tool not in fb.TOOLS:
            return self._refuse("repair", f"unknown tool {tool!r}; known: {list(fb.TOOLS)}")
        if n_train not in (4, 8) or n_train > len(self.view_seeds["train"]):
            return self._refuse("repair", f"n_train must be 4 or 8, got {n_train}", tool=tool)
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            return self._refuse("repair", "budget must be a non-negative integer", tool=tool)
        need = min_budget(tool, n_train)
        if budget < need:
            return self._refuse("repair", f"budget {budget} is below the minimum {need} for tool {tool}", tool=tool)
        if budget > self.remaining:
            return self._refuse("repair", f"budget {budget} exceeds the {self.remaining} rollouts remaining", tool=tool)
        seeds = self.view_seeds["train"][:n_train]
        if self._do1_base is not None and self._do1_base["seeds"] != seeds:
            return self._refuse("repair", f"the DO-1 train baseline was measured on seeds {self._do1_base['seeds']}, "
                                          f"not {seeds}", tool=tool)
        base_cost = 0 if (self._do1_base is not None and self._do1_base["seeds"] == seeds) else n_train
        if budget - base_cost < need:
            return self._refuse("repair", f"budget {budget} minus the {base_cost}-rollout DO-1 train baseline is below the "
                                          f"minimum {need} for tool {tool}", tool=tool)
        parent = self._best if init is None else int(init["index"])
        d = self.designs[parent]
        base, charged = self._do1_baseline(seeds)
        cma_budget = budget - charged
        noise = self._noise + 7919 * self._n_repairs
        self._spend(cma_budget, "repair", {"tool": tool, "design": parent, "budget": cma_budget, "n_train": n_train,
                                           "objective": VERSION, "train_baseline_rollouts": charged})
        log: list = []
        fn = make_do1_eval_fn(self._plant, seeds, base["scores"], variation=self.variation, duration=DURATION,
                              pool=self.pool, log=log)
        try:
            res = wo.cma_search(d["body"], list(d["vector"]), tool_space(tool), budget=cma_budget, train_seeds=seeds,
                                noise_seed=noise, pool=self.pool, variation=self.variation, duration=DURATION, eval_fn=fn)
        except ValueError as exc:
            self.budget.refund(cma_budget, "repair", {"tool": tool, "reason": str(exc)})
            self.do1_repairs.append({"tool": tool, "parent": parent, "refused": str(exc), "train_baseline_rollouts": charged})
            return {"ok": False, "refused": f"tool {tool} unavailable for this design: {exc}"}
        repair_index = self._n_repairs
        self._n_repairs += 1
        used = int(res["rollouts_used"])
        if used < cma_budget:
            self.budget.refund(cma_budget - used, "repair", {"tool": tool, "unused": cma_budget - used})
        best = res["best"]
        k = selected_log_index(best, log, len(seeds))
        sel = None if k is None else {key: val for key, val in log[k].items() if key not in ("body", "vector")}
        j = self._add_design(f"repair:{tool}", best["body"], best["vector"], parent=parent, tool=tool, n_train=n_train,
                             train_walking=int(best["walking_count"]), train_fitness=float(best["mean_fitness"]), rollouts=used,
                             objective=VERSION,
                             train_fitness_v1=None if sel is None else sel["mean_fitness_v1"],
                             train_median_diff_m=None if sel is None else sel["median_diff_m"],
                             train_margin=None if sel is None else sel["margin"],
                             train_feasible=None if sel is None else sel["feasible"])
        score = (int(best["walking_count"]) * (4 / n_train), int(best["survival_count"]) * (4 / n_train),
                 float(best["mean_fitness"]))
        if self._best_score is None or score > self._best_score:
            self._best_score, self._best = score, j
        self.do1_repairs.append({"repair_index": repair_index, "tool": tool, "parent": parent, "design_index": j,
                                 "budget": budget, "train_baseline_rollouts": charged, "cma_budget": cma_budget,
                                 "rollouts_used": used, "noise_seed": noise, "train_seeds": list(seeds),
                                 "n_candidates": len(log), "selected_log_index": k, "selected": sel,
                                 "cma": {"restarts": res.get("restarts"), "errors": res.get("errors"),
                                         "history": res.get("history"), "popsize": res.get("popsize")},
                                 "candidates": [{key: val for key, val in c.items() if key != "body"} for c in log]})
        return {"ok": True, "tool": tool, "design_index": j, "rollouts_used": used, "n_train": n_train,
                "best": {"body": copy.deepcopy(best["body"]), "vector": list(best["vector"]),
                         "train_walking": int(best["walking_count"]), "train_n": n_train,
                         "train_fitness": float(best["mean_fitness"])},
                "is_current_best": self._best == j}

    def do1_record(self) -> dict:
        return copy.deepcopy({"version": VERSION, "objective": OBJECTIVE_SPEC, "train_baseline": self._do1_base,
                              "repairs": self.do1_repairs})


def selected_log_index(best: dict, log: list, n_seeds: int) -> int | None:
    """Index in the evaluation log of cma_search's reported best: candidate k completes at (k + 1) * n_seeds rollouts (the
    initial point is k = 0, then each generation in sample order). Verified against the logged vector."""
    k = int(best["found_at_rollouts"]) // n_seeds - 1
    if 0 <= k < len(log) and log[k]["vector"] == [float(x) for x in best["vector"]] \
            and log[k]["J"] == float(best["mean_fitness"]):
        return k
    return None
