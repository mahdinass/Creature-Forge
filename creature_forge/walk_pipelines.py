"""Equal-budget method framework for the walking-recovery study (`walk_pipelines_v1`).

Several methods try to make a failing creature walk. They are compared at an EQUAL TOTAL rollout budget R: every rollout a
method executes (diagnostic probes, the optimisation of every plan including discarded or failed ones, screening, every round)
is charged to one `Budget` ledger, and the method returns ONE candidate (body + controller vector). Final validation /
confirmation (`recovery.assess`) is NOT charged and is done by the caller, identically for all methods. A director (rule
based, random, scripted, or an AI implemented elsewhere) plugs into the same interface, so the only difference between methods
is who makes the decisions.

Declared rules (all of them are tested; none is repaired, clipped or silently relaxed)
  * Nothing runs before it is charged. Probes and plans are RESERVED up front (charged at their full budget) and SETTLED after:
    if the run used fewer rollouts the difference is returned as a negative ledger line ("<item>:refund"). `used` is the sum of
    all lines; `used <= total_budget` always.
  * Shared start evaluation: the unchanged creature is evaluated once on the train seeds (n_train rollouts, ledger item
    "start_eval") so every candidate has a comparable train score and every probe a start_score. All methods pay it.
  * Screening reservation: screen_top_k * screen_n rollouts are charged up front ("screen_reserve") so screening can always
    run. At the end the reservation is released (negative line) and the screening runs actually performed are charged
    (screen_n each); fewer distinct candidates than screen_top_k therefore cost less. `state["budget"]["remaining"]` is what
    the director may still spend and already excludes the reservation.
  * Invalid plans are REJECTED with reasons and cost 0 rollouts; their budget share is FORFEITED (not redistributed). The same
    holds for unknown / unavailable / duplicate / unaffordable probes. More than 3 probes or 2 plans in a round: the extra ones
    are rejected. Plans are processed in order; a plan whose cumulative share (valid earlier plans of the round + its own)
    exceeds 1 is rejected. Shares are fractions of the budget remaining when `choose_plans` is called (after that round's
    probes); the plan budget is floor(share * remaining_at_that_point), and a plan whose budget cannot pay the initial
    evaluation (n_train rollouts) is rejected.
  * A plan's init is "start", a probe id already run with status "ok", or (extension needed by continuing rounds) a plan id
    ("r<round>p<index>") already run with status "ok". Plan ids are assigned per returned plan, index counted from 0.
  * Opt probes cost `probe_budget`; they are unavailable when fewer rollouts remain. Morphology counterfactuals cost n_train
    and are unavailable (never clipped) if an edit would leave the guided bounds (`morphology.BOUNDS`).
  * Every run uses the same noise_seed. A run that raises is recorded with status "error" and keeps its full charge (the
    rollouts may have been executed); it never becomes a candidate.
  * Candidate pool for final selection, in this order: start, each ok probe's best, each ok plan's best; identical
    (body, vector) pairs are merged (first occurrence wins). Train score = lexicographic (walking, survival, mean fitness),
    higher is better, ties keep pool order. The top `screen_top_k` are screened on `seeds["screen"][:screen_n]` (10 s,
    VARIATION_PRESET). Final = most walking seeds on screen; ties: higher median screen score (an ERROR seed counts as -inf),
    then higher train score, then earlier pool order.
  * Family 17 means the vectors carry the two foot-placement gains. The start vector is the frozen R2 winner (15-D) padded with
    fp_kd = fp_kv = 0 (bit-identical behaviour). Diagnostics always use the 15-D R2 vector. Searches use `_FPSpace` so that
    non-placement subspaces still pass the 17-D vector through.

Test-only hook: `run_pipeline(..., eval_override=...)` replaces everything that needs MuJoCo with synthetic functions. Keys
(all optional): `eval_fn` (the `walk_opt.cma_search` batch evaluator, used by every search AND every train evaluation),
`screen_fn(body, vector, seeds) -> rows`, `diag_fn(body, vector15, seeds) -> {"outcomes": [...], "gait": {...}}`,
`similarity_fn(body, vector) -> (vector, report)`, `features_fn(body) -> dict`. Real experiments never pass it.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
import time
from typing import Callable, Sequence

import numpy as np

from . import arena, creature_gen, creature_walk as cw, gait_features as gf, recovery as rc, walk_opt as wo
from . import interventions as iv
from .optimize import jsonable

VERSION = "walk_pipelines_v1"
WALK_PROBES_VERSION = "walk_probes_v1"
MAX_PROBES_PER_ROUND = 3
MAX_PLANS_PER_ROUND = 2
SCREEN_DURATION = 10.0
FIX_BODY_PARAMS = ("foot_length", "thigh_length", "shank_length", "torso_mass")
PLAN_KEYS = {"init", "ctrl_subspaces", "body_params", "budget_share"}
PLAN_OPTIONAL_KEYS = {"rationale"}          # recorded, never used

_MORPH = {
    "foot_x1_5": {"scale": {"foot_length": 1.5}, "description": "foot_length x1.5"},
    "torso_x0_7": {"scale": {"torso_mass": 0.7}, "description": "torso_mass x0.7"},
    "torque_x1_5": {"scale": {"torque_limit": 1.5}, "description": "torque_limit x1.5"},
    "legs_x0_8": {"scale": {"thigh_length": 0.8, "shank_length": 0.8}, "description": "thigh and shank length x0.8"},
    "legs_x1_2": {"scale": {"thigh_length": 1.2, "shank_length": 1.2}, "description": "thigh and shank length x1.2"},
}
PROBES: dict[str, dict] = {
    "opt_timing": {"kind": "subspace", "subspace": "timing", "description": "short CMA over the timing subspace"},
    "opt_posture": {"kind": "subspace", "subspace": "posture", "description": "short CMA over the posture subspace"},
    "opt_feedback": {"kind": "subspace", "subspace": "feedback", "description": "short CMA over the feedback subspace"},
    "opt_stride": {"kind": "subspace", "subspace": "stride", "description": "short CMA over the stride subspace"},
    "opt_placement": {"kind": "subspace", "subspace": "placement", "description": "short CMA over fp_kd, fp_kv (family 17 only)"},
    "opt_body": {"kind": "body", "body_params": ("foot_length", "thigh_length", "shank_length", "torso_mass"),
                 "description": "short CMA over four body parameters, controller fixed"},
    **{k: {"kind": "morphology", **v} for k, v in _MORPH.items()},
    "similarity": {"kind": "similarity", "description": "dynamic-similarity controller transfer, evaluated once"},
}
OPT_PROBE_IDS = tuple(k for k, v in PROBES.items() if v["kind"] in ("subspace", "body"))
FIX_PRIORITY = ("opt_placement", "opt_posture", "opt_timing", "opt_feedback", "opt_stride")


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    """Hard rollout ledger. `charge` reserves, `refund` settles; `used` is the sum of all lines and never exceeds `total`."""

    def __init__(self, total: int):
        if isinstance(total, bool) or not isinstance(total, (int, np.integer)) or total < 0:
            raise ValueError("total must be a non-negative integer")
        self.total = int(total)
        self.lines: list[dict] = []

    @property
    def used(self) -> int:
        return self.lines[-1]["cumulative"] if self.lines else 0

    @property
    def remaining(self) -> int:
        return self.total - self.used

    def _add(self, n: int, item: str, detail: dict | None) -> None:
        self.lines.append({"item": str(item), "n": int(n), "detail": jsonable(dict(detail or {})), "cumulative": self.used + int(n)})

    def charge(self, n: int, item: str, detail: dict | None = None) -> None:
        if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 0:
            raise ValueError(f"charge must be a non-negative integer, got {n!r}")
        if self.used + int(n) > self.total:
            raise BudgetExceeded(f"{item}: charging {n} would exceed the budget ({self.used} used of {self.total})")
        self._add(int(n), item, detail)

    def refund(self, n: int, item: str, detail: dict | None = None) -> None:
        if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 0:
            raise ValueError(f"refund must be a non-negative integer, got {n!r}")
        if int(n) > self.used:
            raise ValueError("cannot refund more than was charged")
        self._add(-int(n), item, detail)


class _FPSpace(wo.SearchSpace):
    """SearchSpace for the 17-D family: vectors are always 17-D, whichever dimensions are searched."""

    @property
    def uses_fp(self) -> bool:
        return True


def _space(family: int, subspaces: Sequence[str], body_params: Sequence[str] = ()) -> wo.SearchSpace:
    chosen = {p for n in subspaces for p in wo.SUBSPACES[n]}
    ctrl = tuple(p for p in wo.ALL_NAMES if p in chosen)
    return (_FPSpace if family == 17 else wo.SearchSpace)(ctrl, tuple(body_params))


def available_probes(state: dict) -> list[str]:
    return list(state["available_probes"])


def _full(body) -> dict:
    d = body.as_dict() if hasattr(body, "as_dict") else dict(body)
    return iv.full_body({"body": d})


def _score(rec) -> tuple:
    return (int(rec["walking_count"]), int(rec["survival_count"]), float(rec["mean_fitness"]))


def _score_dict(rec) -> dict:
    return {"walking_count": int(rec["walking_count"]), "survival_count": int(rec["survival_count"]),
            "mean_fitness": float(rec["mean_fitness"])}


def _cand_key(body: dict, vector) -> str:
    return hashlib.sha256(json.dumps(jsonable({"body": body, "vector": [float(x) for x in vector]}), sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------------------- plan validation
def validate_plan(plan, *, family: int, runs: dict) -> list[str]:
    """Reasons a plan is invalid (empty list = valid). `runs` maps already-run ok probe/plan ids to anything."""
    if not isinstance(plan, dict):
        return [f"plan must be a dict, got {type(plan).__name__}"]
    out = []
    extra = set(plan) - PLAN_KEYS - PLAN_OPTIONAL_KEYS
    missing = PLAN_KEYS - set(plan)
    if extra:
        out.append(f"unknown plan key(s) {sorted(map(str, extra))}")
    if missing:
        out.append(f"missing plan key(s) {sorted(missing)}")
    if missing:
        return out
    init = plan["init"]
    if not isinstance(init, str) or not (init == "start" or init in runs):
        out.append(f"init {init!r} is neither 'start' nor a probe/plan already run successfully")
    subs = plan["ctrl_subspaces"]
    if not isinstance(subs, (list, tuple)) or not all(isinstance(s, str) for s in subs):
        out.append("ctrl_subspaces must be a list of names")
        subs = []
    else:
        bad = [s for s in subs if s not in wo.SUBSPACES]
        if bad:
            out.append(f"unknown subspace(s) {bad}; known: {list(wo.SUBSPACES)}")
        if len(set(subs)) != len(subs):
            out.append("duplicate subspaces")
        if "placement" in subs and family != 17:
            out.append("placement subspace requires family 17")
    bp = plan["body_params"]
    if not isinstance(bp, (list, tuple)) or not all(isinstance(s, str) for s in bp):
        out.append("body_params must be a list of names")
        bp = []
    else:
        bad = [s for s in bp if s not in wo.BODY_PARAMS]
        if bad:
            out.append(f"unknown body parameter(s) {bad}; known: {list(wo.BODY_PARAMS)}")
        if len(set(bp)) != len(bp):
            out.append("duplicate body parameters")
        if len(bp) > wo.MAX_BODY_PARAMS:
            out.append(f"at most {wo.MAX_BODY_PARAMS} body parameters (got {len(bp)})")
    if not subs and not bp:
        out.append("a plan needs at least one dimension")
    sh = plan["budget_share"]
    if isinstance(sh, bool) or not isinstance(sh, (int, float, np.integer, np.floating)) or not math.isfinite(float(sh)) \
            or not 0.0 < float(sh) <= 1.0:
        out.append(f"budget_share must be a number in (0, 1], got {sh!r}")
    return out


# ---------------------------------------------------------------------------------------------------------- final selection
def select_final(cands: list[dict], effect_bar: float | None = None) -> int:
    """Index (into `cands`) of the final candidate. Each: {train_score: [w, s, f], screen: {walking, median}, order}.
    selection v1 (effect_bar None): most screen-walking seeds; ties: higher median screen score, then higher train score, then
    lower order. selection v2 (effect_bar = the original's screen median + verdict_v1's walk minimum effect): candidates whose
    screen median reaches the bar rank first, then the v1 key (fixes the method-independent artifact found after S2: a stable
    walker that does not out-distance a runaway original cannot be verified)."""
    best = None
    for i, c in enumerate(cands):
        bar = () if effect_bar is None else (c["screen"]["median"] >= effect_bar - 1e-9,)
        key = bar + (c["screen"]["walking"], c["screen"]["median"], tuple(c["train_score"]), -c["order"])
        if best is None or key > best[0]:
            best = (key, i)
    return best[1]


def _screen_summary(rows: list[dict]) -> dict:
    scores = [float("-inf") if r.get("score") is None else float(r["score"]) for r in rows]
    med = statistics.median(scores) if scores else float("-inf")
    return {"walking": sum(1 for r in rows if r.get("walking")), "n": len(rows),
            "errors": sum(1 for r in rows if r.get("outcome") == "ERROR"),
            "median": med if math.isfinite(med) else -1e18,
            "median_score": None if not math.isfinite(med) else med,
            "per_seed": [{"seed": r.get("seed"), "outcome": r.get("outcome"), "walking": bool(r.get("walking")),
                          "score": r.get("score")} for r in rows]}


# ---------------------------------------------------------------------------------------------------------- pipeline
def run_pipeline(body, director, *, total_budget: int, family: int, seeds: dict, noise_seed: int, pool=None,
                 probe_budget: int = 300, rounds: int = 2, screen_top_k: int = 3, screen_n: int = 12,
                 director_name: str = "", log: Callable | None = None, start_vector: Sequence[float] | None = None,
                 eval_override: dict | None = None, selection: str = "v1") -> dict:
    t0 = time.perf_counter()
    ov = dict(eval_override or {})
    say = log or (lambda msg: None)
    if selection not in ("v1", "v2"):
        raise ValueError("selection must be 'v1' or 'v2'")
    if family not in (15, 17):
        raise ValueError("family must be 15 or 17")
    for k in ("diag", "train", "screen"):
        if k not in seeds or not len(seeds[k]):
            raise ValueError(f"seeds[{k!r}] is required")
    train = [int(s) for s in seeds["train"]]
    screen_seeds = [int(s) for s in seeds["screen"]][:screen_n]
    diag = [int(s) for s in seeds["diag"]]
    if len(screen_seeds) < screen_n:
        raise ValueError(f"seeds['screen'] has fewer than screen_n={screen_n} seeds")
    roles = {k: {int(s) for s in v} for k, v in seeds.items()}
    roles["screen"] = set(screen_seeds)
    names = sorted(roles)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if (a, b) in (("diag", "train"), ("train", "diag")):
                continue
            if roles[a] & roles[b]:
                raise ValueError(f"seed roles {a!r} and {b!r} overlap")
    S = len(train)
    if len(set(train)) != S:
        raise ValueError("train seeds must be distinct")
    for nm, v, lo in (("probe_budget", probe_budget, 0), ("rounds", rounds, 0), ("screen_top_k", screen_top_k, 1),
                      ("screen_n", screen_n, 1)):
        if isinstance(v, bool) or not isinstance(v, int) or v < lo:
            raise ValueError(f"{nm} must be an integer >= {lo}")
    reserve = (screen_top_k + (1 if selection == "v2" else 0)) * screen_n   # v2 also screens the original once
    budget = Budget(total_budget)
    if total_budget < reserve + S:
        raise ValueError(f"total_budget {total_budget} cannot pay for screening ({reserve}) and the start evaluation ({S})")

    base = _full(body)
    vec15 = [float(x) for x in (cw.R2_WINNER if start_vector is None else start_vector)]
    if len(vec15) != 15:
        raise ValueError("start_vector must be the 15-D transfer vector (padded to 17-D automatically for family 17)")
    start_vec = wo.pad_to_17(vec15) if family == 17 else list(vec15)
    eval_fn = ov.get("eval_fn")
    cma_kw = dict(train_seeds=train, noise_seed=noise_seed, pool=pool, variation=arena.VARIATION_PRESET)
    if eval_fn is not None:
        cma_kw["eval_fn"] = eval_fn
    tiny = _space(family, ("timing",))

    decisions: list[dict] = []
    ledger_runs: dict[str, dict] = {}      # id -> {"body","vector","score"} for ok probes and plans (init sources)
    probes_run: list[dict] = []
    plans_run: list[dict] = []
    round_records: list[dict] = []

    # ---- shared diagnostics (NOT charged)
    if "diag_fn" in ov:
        baseline = jsonable(ov["diag_fn"](base, vec15, diag))
    else:
        feats = [gf.features_for(base, vec15, s) for s in diag]
        rows = rc.run_walk_seeds(base, vec15, diag, duration=SCREEN_DURATION, pool=pool)
        baseline = {"outcomes": [{k: r.get(k) for k in ("seed", "outcome", "label", "fall_time", "forward_disp_upright",
                                                          "speed_upright", "valid_steps")} for r in rows],
                    "gait": gf.summarize(feats)}
    baseline = {"seeds": diag, "note": "unchanged creature, R2 transfer vector, not charged", **baseline}
    features = jsonable(ov["features_fn"](base) if "features_fn" in ov else creature_gen.features(base))

    # ---- reservation and shared start evaluation
    budget.charge(reserve, "screen_reserve", {"screen_top_k": screen_top_k, "screen_n": screen_n})

    def train_eval(b: dict, v) -> dict:
        res = wo.cma_search(b, v, tiny, budget=S, **cma_kw)
        return res["init"]

    budget.charge(S, "start_eval", {"n_train": S})
    start_rec = train_eval(base, start_vec)
    start_score = _score_dict(start_rec)
    start = {"body": base, "vector": start_vec, "score": start_score}

    def spendable_used() -> int:
        return budget.used - reserve

    def make_state(rnd: int) -> dict:
        avail, unavail = _availability()
        return jsonable({
            "creature": {"body": base, "features": features}, "baseline": baseline, "family": family,
            "budget": {"total": total_budget, "reserved_for_screening": reserve, "spendable_total": total_budget - reserve,
                       "used": spendable_used(), "remaining": budget.remaining},
            "round": rnd, "rounds_total": rounds, "n_train": S, "probe_budget": probe_budget,
            "start_score": start_score,
            "probes_run": copy.deepcopy(probes_run), "plans_run": copy.deepcopy(plans_run),
            "available_probes": avail, "unavailable_probes": unavail,
            "probe_costs": {p: (probe_budget if PROBES[p]["kind"] in ("subspace", "body") else S) for p in PROBES},
            "probe_catalogue": {"version": WALK_PROBES_VERSION, "probes": {k: {kk: vv for kk, vv in v.items()}
                                                                          for k, v in PROBES.items()}}})

    def morph_edit(pid: str) -> tuple[dict | None, list[dict], str | None]:
        new, edits = dict(base), []
        bounds = iv.mode_bounds("guided")
        for p, r in _MORPH[pid]["scale"].items():
            for f in wo._fields(p):
                new[f] = float(base[f]) * r
                lo, hi = bounds[p]
                if not lo <= new[f] <= hi:
                    return None, [], f"{f} would be {new[f]:.6g}, outside the guided bounds [{lo:g}, {hi:g}]"
            edits.append({"param": p, "op": "scale", "value": r, "target": "both"})
        return new, edits, None

    def _availability() -> tuple[list[str], dict]:
        avail, un = [], {}
        done = {p["probe_id"] for p in probes_run}
        for pid, spec in PROBES.items():
            cost = probe_budget if spec["kind"] in ("subspace", "body") else S
            if pid in done:
                un[pid] = "already run"
            elif pid == "opt_placement" and family != 17:
                un[pid] = "placement requires family 17"
            elif spec["kind"] == "morphology" and morph_edit(pid)[2]:
                un[pid] = morph_edit(pid)[2]
            elif spec["kind"] in ("subspace", "body") and probe_budget < S:
                un[pid] = f"probe_budget {probe_budget} cannot pay the initial evaluation ({S} rollouts)"
            elif cost > budget.remaining:
                un[pid] = f"needs {cost} rollouts, {budget.remaining} remain"
            else:
                avail.append(pid)
        return avail, un

    def settle(item: str, reserved: int, used: int) -> int:
        if used > reserved:
            raise BudgetExceeded(f"{item}: used {used} > reserved {reserved}")
        if used < reserved:
            budget.refund(reserved - used, item + ":refund", {"reserved": reserved, "used": used})
        return reserved - used

    # ---- probes
    def run_probe(pid: str, rnd: int) -> dict:
        spec = PROBES[pid]
        rec = {"probe_id": pid, "round": rnd, "status": "ok", "rollouts": 0, "start_score": start_score}
        try:
            if spec["kind"] in ("subspace", "body"):
                budget.charge(probe_budget, f"probe:{pid}", {"round": rnd, "reserved": probe_budget})
                space = _space(family, (spec["subspace"],)) if spec["kind"] == "subspace" else \
                    _space(family, (), spec["body_params"])
                res = wo.cma_search(base, start_vec, space, budget=probe_budget, checkpoints=(), **cma_kw)
                used = res["rollouts_used"]
                settle(f"probe:{pid}", probe_budget, used)
                best = res["best"]
                rec.update(rollouts=used, best_body=best["body"], best_vector=best["vector"], best_score=_score_dict(best),
                           edits=wo.body_edits(base, best["body"]), space=res["space"], errors=len(res["errors"]))
            elif spec["kind"] == "morphology":
                nb, edits, why = morph_edit(pid)
                if why:
                    raise ValueError(why)
                budget.charge(S, f"probe:{pid}", {"round": rnd})
                r = train_eval(nb, start_vec)
                rec.update(rollouts=S, best_body=nb, best_vector=list(start_vec), best_score=_score_dict(r), edits=edits)
            else:  # similarity
                budget.charge(S, f"probe:{pid}", {"round": rnd})
                fn = ov.get("similarity_fn") or wo.similarity_init
                sv, report = fn(base, start_vec)
                sv = wo.pad_to_17(sv) if family == 17 else [float(x) for x in sv]
                r = train_eval(base, sv)
                rec.update(rollouts=S, best_body=dict(base), best_vector=sv, best_score=_score_dict(r), edits=[],
                           similarity_report=report)
        except BudgetExceeded:
            raise
        except Exception as e:          # noqa: BLE001  recorded, charge kept (rollouts may have run)
            rec.update(status="error", reason=f"{type(e).__name__}: {e}", rollouts=rec["rollouts"])
            rec.setdefault("best_score", None)
            return jsonable(rec)
        rec["delta_mean_fitness"] = rec["best_score"]["mean_fitness"] - start_score["mean_fitness"]
        rec["delta_walking"] = rec["best_score"]["walking_count"] - start_score["walking_count"]
        return jsonable(rec)

    # ---- plans
    def run_plan(pid: str, plan: dict, rnd: int, budget_p: int) -> dict:
        init = start if plan["init"] == "start" else ledger_runs[plan["init"]]
        space = _space(family, plan["ctrl_subspaces"], plan["body_params"])
        rec = {"plan_id": pid, "round": rnd, "plan": jsonable(plan), "budget": budget_p, "status": "ok",
               "init_score": init["score"]}
        budget.charge(budget_p, f"plan:{pid}", {"round": rnd, "reserved": budget_p, "init": plan["init"]})
        try:
            res = wo.cma_search(init["body"], init["vector"], space, budget=budget_p, checkpoints=(), **cma_kw)
        except Exception as e:          # noqa: BLE001
            rec.update(status="error", reason=f"{type(e).__name__}: {e}", rollouts_used=budget_p, refunded=0)
            return jsonable(rec)
        used = res["rollouts_used"]
        refunded = settle(f"plan:{pid}", budget_p, used)
        best = res["best"]
        rec.update(rollouts_used=used, refunded=refunded, best_score=_score_dict(best), walking_count=best["walking_count"],
                   best_body=best["body"], best_vector=best["vector"], edits=wo.body_edits(base, best["body"]),
                   improvement={"delta_mean_fitness": best["mean_fitness"] - start_score["mean_fitness"],
                                "delta_walking": best["walking_count"] - start_score["walking_count"]},
                   generations=len(res["history"]), restarts=len(res["restarts"]), errors=len(res["errors"]))
        return jsonable(rec)

    def listify(x):
        return x if isinstance(x, list) else None

    for rnd in range(1, rounds + 1):
        if budget.remaining < S:
            break
        rr = {"round": rnd, "probes": [], "rejected_probes": [], "plans": [], "rejected_plans": []}
        round_records.append(rr)
        # probes
        raw = director.choose_probes(make_state(rnd))
        decisions.append({"round": rnd, "kind": "probes", "returned": jsonable(copy.deepcopy(raw))})
        lst = listify(raw)
        if lst is None:
            rr["rejected_probes"].append({"probe_id": None, "reason": f"choose_probes must return a list, got {type(raw).__name__}"})
            lst = []
        for k, pid in enumerate(lst):
            if k >= MAX_PROBES_PER_ROUND:
                rr["rejected_probes"].append({"probe_id": jsonable(pid), "reason": f"more than {MAX_PROBES_PER_ROUND} probes in a round"})
                continue
            if not isinstance(pid, str) or pid not in PROBES:
                rr["rejected_probes"].append({"probe_id": jsonable(pid), "reason": "unknown probe"})
                continue
            avail, un = _availability()
            if pid not in avail:
                rr["rejected_probes"].append({"probe_id": pid, "reason": un.get(pid, "unavailable")})
                continue
            say(f"round {rnd}: probe {pid}")
            res = run_probe(pid, rnd)
            rr["probes"].append(res)
            probes_run.append(res)
            if res["status"] == "ok":
                ledger_runs[pid] = {"body": res["best_body"], "vector": res["best_vector"], "score": res["best_score"]}
        # plans
        state = make_state(rnd)
        raw = director.choose_plans(state)
        decisions.append({"round": rnd, "kind": "plans", "returned": jsonable(copy.deepcopy(raw))})
        lst = listify(raw)
        if lst is None:
            rr["rejected_plans"].append({"index": None, "plan": None, "reasons": [f"choose_plans must return a list, got {type(raw).__name__}"]})
            lst = []
        rem0 = budget.remaining
        cum = 0.0
        for idx, plan in enumerate(lst):
            reasons = [f"more than {MAX_PLANS_PER_ROUND} plans in a round"] if idx >= MAX_PLANS_PER_ROUND else \
                validate_plan(plan, family=family, runs=ledger_runs)
            plan_budget = 0
            if not reasons:
                share = float(plan["budget_share"])
                if cum + share > 1.0 + 1e-9:
                    reasons.append(f"cumulative budget shares {cum + share:.4g} exceed 1")
                plan_budget = int(math.floor(share * rem0 + 1e-9))
                if plan_budget < S:
                    reasons.append(f"plan budget {plan_budget} cannot pay the initial evaluation ({S} rollouts)")
                if plan_budget > budget.remaining:
                    reasons.append(f"plan budget {plan_budget} exceeds the {budget.remaining} rollouts remaining")
            if not reasons:
                init = start if plan["init"] == "start" else ledger_runs[plan["init"]]
                try:
                    sp = _space(family, plan["ctrl_subspaces"], plan["body_params"])
                    wo.encode(sp, init["body"], init["vector"], init["body"], init["vector"])
                except ValueError as e:
                    reasons.append(f"search space not usable from this init: {e}")
            if reasons:
                rr["rejected_plans"].append({"index": idx, "plan": jsonable(plan), "reasons": reasons})
                continue
            cum += float(plan["budget_share"])
            pid = f"r{rnd}p{idx}"
            say(f"round {rnd}: plan {pid} budget {plan_budget}")
            res = run_plan(pid, plan, rnd, plan_budget)
            rr["plans"].append(res)
            if res["status"] == "ok":
                plans_run.append(res)
                ledger_runs[pid] = {"body": res["best_body"], "vector": res["best_vector"], "score": res["best_score"]}
            else:
                plans_run.append({k: v for k, v in res.items()})
    # ---- final selection (charged)
    pool_c: list[dict] = []
    seen: dict[str, int] = {}

    def add(source, b, v, sc):
        key = _cand_key(b, v)
        if key in seen:
            pool_c[seen[key]]["aliases"].append(source)
            return
        seen[key] = len(pool_c)
        pool_c.append({"source": source, "body": b, "vector": [float(x) for x in v], "train_score": _score_tuple(sc),
                       "order": len(pool_c), "aliases": []})

    def _score_tuple(sc):
        return [int(sc["walking_count"]), int(sc["survival_count"]), float(sc["mean_fitness"])]

    add("start", base, start_vec, start_score)
    for p in probes_run:
        if p["status"] == "ok":
            add(p["probe_id"], p["best_body"], p["best_vector"], p["best_score"])
    for p in plans_run:
        if p["status"] == "ok":
            add(p["plan_id"], p["best_body"], p["best_vector"], p["best_score"])
    top = sorted(pool_c, key=lambda c: (c["train_score"], -c["order"]), reverse=True)[:screen_top_k]
    budget.refund(reserve, "screen_reserve:release", {})
    screened = []
    for c in top:
        budget.charge(screen_n, f"screen:{c['source']}", {"screen_n": screen_n})
        if "screen_fn" in ov:
            rows = ov["screen_fn"](c["body"], c["vector"], screen_seeds)
        else:
            rows = rc.run_walk_seeds(c["body"], c["vector"], screen_seeds, duration=SCREEN_DURATION,
                                     variation=arena.VARIATION_PRESET, pool=pool)
        c["screen"] = _screen_summary(rows)
        screened.append(c)
    effect_bar = None
    orig_screen = None
    if selection == "v2":
        from . import verdict as vd
        start_c = next((c for c in screened if c["source"] == "start" or "start" in c["aliases"]), None)
        if start_c is not None:
            orig_screen = start_c["screen"]
        else:
            budget.charge(screen_n, "screen:original", {"screen_n": screen_n, "purpose": "selection v2 effect bar"})
            if "screen_fn" in ov:
                rows = ov["screen_fn"](base, start_vec, screen_seeds)
            else:
                rows = rc.run_walk_seeds(base, start_vec, screen_seeds, duration=SCREEN_DURATION, variation=arena.VARIATION_PRESET,
                                         pool=pool)
            orig_screen = _screen_summary(rows)
        effect_bar = orig_screen["median"] + float(vd.MIN_EFFECT["walk"]["abs"])
    win = screened[select_final(screened, effect_bar)]
    used = budget.used
    assert used <= total_budget, "budget exceeded"
    assert used == sum(l["n"] for l in budget.lines), "ledger sum mismatch"
    scr = {k: v for k, v in win["screen"].items() if k != "median"}
    return jsonable({
        "version": VERSION, "probes_version": WALK_PROBES_VERSION, "director": director_name or type(director).__name__,
        "family": family, "total_budget": total_budget, "budget_lines": budget.lines, "used": used,
        "rounds": round_records, "baseline": baseline, "start_score": start_score,
        "candidates": [{"source": c["source"], "aliases": c["aliases"], "train_score": c["train_score"],
                        "screen": {k: v for k, v in c["screen"].items() if k != "median"}} for c in screened],
        "final": {"body": win["body"], "vector": win["vector"], "edits": wo.body_edits(base, win["body"]),
                  "source": win["source"], "aliases": win["aliases"], "train_score": win["train_score"], "screen": scr},
        "decisions": decisions, "seeds": {"train": train, "screen": screen_seeds, "diag": diag},
        "selection": {"rule": selection, "effect_bar": effect_bar,
                      "original_screen": None if orig_screen is None else {k: v for k, v in orig_screen.items() if k != "median"}},
        "settings": {"probe_budget": probe_budget, "rounds": rounds, "screen_top_k": screen_top_k, "screen_n": screen_n,
                     "noise_seed": noise_seed, "plan_rejection_rule": "rejected plan costs 0, share forfeited"},
        "wall_s": time.perf_counter() - t0})


# ---------------------------------------------------------------------------------------------------------- directors
def _plan_id_ok(state) -> list[str]:
    return [p["plan_id"] for p in state["plans_run"] if p.get("status") == "ok"]


def _share(state) -> float:
    """Rule shared by FIX and RANDOM: spend everything in the last round, half before it (so later rounds can still act)."""
    return 1.0 if state["round"] >= state["rounds_total"] else 0.5


def _improved(p: dict) -> bool:
    return (p.get("delta_walking", 0), p.get("delta_mean_fitness", 0.0)) > (0, 0.0)


class FullSpaceDirector:
    """CMA-ctrl (no body params) or CMA-joint (with them): no probes, one plan over all control subspaces, share 1.0, round 1."""

    def __init__(self, body_params=()):
        self.body_params = tuple(body_params)

    def choose_probes(self, state):
        return []

    def choose_plans(self, state):
        if state["round"] != 1:
            return []
        subs = [s for s in wo.SUBSPACES if s != "placement" or state["family"] == 17]
        return [{"init": "start", "ctrl_subspaces": subs, "body_params": list(self.body_params), "budget_share": 1.0}]


class FixedDirector:
    """FIX: deterministic engineering rule with the same information an AI director gets.

    Round 1 probes: the first three available of FIX_PRIORITY = (opt_placement [family 17 only], opt_posture, opt_timing,
    opt_feedback, opt_stride), i.e. placement/posture/timing for family 17 and posture/timing/feedback for family 15.
    Round 1 plan: union of the top-2 ok subspace probes ranked by (delta_walking, delta_mean_fitness, priority order);
    init = the best ok probe if it improved on the start (delta_walking, delta_mean) > (0, 0), else "start"; the four body
    params (foot_length, thigh_length, shank_length, torso_mass) are added only if a morphology counterfactual or opt_body
    was run and improved (never true with the default three probes). Share: `_share` (0.5 before the last round, 1.0 in it).
    Later rounds: continue the best ok plan's subspaces and body params from its best candidate (init = its plan id), share
    1.0 of what remains."""

    def __init__(self, probes: Sequence[str] | None = None):
        self.priority = tuple(probes) if probes is not None else FIX_PRIORITY

    def choose_probes(self, state):
        if state["round"] != 1:
            return []
        avail = set(state["available_probes"])
        return [p for p in self.priority if p in avail][:MAX_PROBES_PER_ROUND]

    def choose_plans(self, state):
        runs = [p for p in state["probes_run"] if p["status"] == "ok"]
        if state["round"] == 1:
            order = {p: i for i, p in enumerate(FIX_PRIORITY)}
            key = lambda p: (-p["delta_walking"], -p["delta_mean_fitness"], order.get(p["probe_id"], 99))   # noqa: E731
            sub = sorted((p for p in runs if PROBES[p["probe_id"]]["kind"] == "subspace"), key=key)[:2]
            subs = [PROBES[p["probe_id"]]["subspace"] for p in sub]
            if not subs:
                subs = [PROBES[p]["subspace"] for p in self.priority if PROBES[p]["kind"] == "subspace"][:2]
            best = sorted(runs, key=key)
            init = best[0]["probe_id"] if best and _improved(best[0]) else "start"
            body = any(_improved(p) for p in runs if PROBES[p["probe_id"]]["kind"] in ("morphology", "body"))
            return [{"init": init, "ctrl_subspaces": subs, "body_params": list(FIX_BODY_PARAMS) if body else [],
                     "budget_share": _share(state)}]
        plans = [p for p in state["plans_run"] if p.get("status") == "ok"]
        if not plans:
            return []
        best = max(enumerate(plans), key=lambda ip: (tuple(ip[1]["best_score"][k] for k in ("walking_count", "survival_count", "mean_fitness")), -ip[0]))[1]
        return [{"init": best["plan_id"], "ctrl_subspaces": list(best["plan"]["ctrl_subspaces"]),
                 "body_params": list(best["plan"]["body_params"]), "budget_share": 1.0}]


class RandomDirector:
    """Same structure as FixedDirector with random choices from default_rng(SeedSequence([seed, 0x5A4D])): round 1 probes =
    random min(3, available) probes; every round one plan with 1-3 random allowed subspaces, a random init among start / ok
    probes / ok plans, 0-4 random body params, share `_share`."""

    def __init__(self, seed: int):
        self.rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0x5A4D]))

    def choose_probes(self, state):
        if state["round"] != 1:
            return []
        avail = list(state["available_probes"])
        k = min(MAX_PROBES_PER_ROUND, len(avail))
        return [avail[int(i)] for i in self.rng.choice(len(avail), size=k, replace=False)] if k else []

    def choose_plans(self, state):
        names = [s for s in wo.SUBSPACES if s != "placement" or state["family"] == 17]
        n_sub = int(self.rng.integers(1, 4))
        subs = [names[int(i)] for i in sorted(self.rng.choice(len(names), size=n_sub, replace=False))]
        pool = ["start"] + [p["probe_id"] for p in state["probes_run"] if p["status"] == "ok"] + _plan_id_ok(state)
        init = pool[int(self.rng.integers(len(pool)))]
        n_body = int(self.rng.integers(0, 5))
        body = [wo.BODY_PARAMS[int(i)] for i in sorted(self.rng.choice(len(wo.BODY_PARAMS), size=n_body, replace=False))]
        return [{"init": init, "ctrl_subspaces": subs, "body_params": body, "budget_share": _share(state)}]


class ScriptedDirector:
    """Replays decisions: a list of {"round": r, "kind": "probes"|"plans", "returned": [...]} (the `decisions` field of a
    pipeline record, so an AI's recorded decisions replay exactly). A (round, kind) without an entry returns []."""

    def __init__(self, decisions: Sequence[dict]):
        self.table = {}
        for d in decisions:
            if not isinstance(d, dict) or d.get("kind") not in ("probes", "plans") or "round" not in d or "returned" not in d:
                raise ValueError("each decision needs round, kind in ('probes', 'plans') and returned")
            self.table[(int(d["round"]), d["kind"])] = d["returned"]

    def choose_probes(self, state):
        return copy.deepcopy(self.table.get((state["round"], "probes"), []))

    def choose_plans(self, state):
        return copy.deepcopy(self.table.get((state["round"], "plans"), []))
