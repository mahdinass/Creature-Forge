"""Closed-loop mechanism investigation pipeline (`mech_pipelines_v1`) for the walking-recovery study.

Mirrors `walk_pipelines` (same Budget ledger, same shared start evaluation, same noise seed, same screening/selection framework) but
replaces "probe round, plan round" by an INVESTIGATION loop in which a director may propose control-law MECHANISMS (a safe DSL,
`creature_forge.mechanisms`), run diagnostic probes, read the measured feedback and decide again, followed by ONE final plan step.
Every method (AI or not) gets the same TOTAL rollout budget; everything is charged to one ledger.

Declared rules (all tested; nothing is repaired, clipped or silently relaxed)
  * Nothing runs before it is charged. Probes and plans are RESERVED up front and SETTLED after (negative "<item>:refund" ledger
    lines). `used` = sum of all lines <= `total_budget` always (asserted).
  * Shared start evaluation: the unchanged creature (15-D R2 controller, no mechanisms) is evaluated once on the TRAIN seeds
    (n_train rollouts, "start_eval"). All methods pay it.
  * Screening reservation: (screen_top_k + 1) * screen_n rollouts are reserved up front: screen_top_k candidates plus the ORIGINAL
    (needed by selection rule v2). The reservation is released at the end and the screening runs actually performed are charged;
    the original's screen is measured once and reused if the original is itself among the screened candidates.
  * INVESTIGATE decision (per round, up to `max_rounds`; exactly 1 in mode "one_shot"): a dict with optional keys
        mechanisms: 0-2 mechanisms (new or revisions), probes: 0-2 ids of MECH_PROBE_IDS, stop: bool.
    Mechanisms and probes beyond the cap, invalid mechanisms (reasons from `mechanisms.validate_mechanism` plus the pipeline rules
    below), unknown / unavailable / duplicate / unaffordable probes are REJECTED with reasons, cost 0 rollouts, and are reported back to the
    director in the next state (`rejected_last_round`). Nothing is repaired.
  * Pipeline rules for a mechanism: id is a fresh identifier (`^[A-Za-z][A-Za-z0-9_]{0,23}$`, not a probe id / "start" / "f0" / "f1"
    / an id used before); a mechanism with the same (target, leg, terms) as an earlier one is a duplicate and rejected; a REVISION
    carries `revises: <id>` which must be a mechanism probed in an EARLIER round (probe attempted, status ok or error) and a non-empty
    `rationale`; it receives a NEW id.
  * MECHANISM PROBE: a cma_search over ONLY the mechanism's gains (budget `probe_budget`, TRAIN seeds, VARIATION_PRESET), then the
    best candidate is rolled out on the DIAG seeds for post-probe gait features (`gait_features.summarize`), CHARGED (n_diag
    rollouts). Cost = probe_budget + n_diag (the CMA refund applies to the first part). Feedback (recorded and returned in the next
    state) = delta_walking, delta_mean_fitness against the start on TRAIN seeds, the fitted gains with at_bound / near_zero flags,
    the post-probe gait summary and its change against the baseline summary. FEEDBACK NEVER USES SCREEN, VALIDATE OR CONFIRM SEEDS.
  * STOP: `stop: true` ends the investigation after the items of that same decision have run. It is allowed at any time, never
    penalised and never forced; investigation also ends when `max_rounds` is reached or fewer than n_train rollouts remain.
  * FINAL PLAN decision (`director.final_plan(state)`): 1-2 plans {init, ctrl_subspaces, body_params (<= 4), mechanisms (<= 2 ids of
    mechanisms whose probe status is ok), budget_share} (+ optional rationale), run as cma_search jointly over the chosen control
    subspaces, body params and the chosen mechanisms' gains. init is "start", an ok probe id or an ok mechanism-probe id; every
    mechanism that init carries must be in the plan's mechanisms. Shares are fractions of the budget remaining when the final plan
    is requested; cumulative share > 1 -> rejected; plan budget floor(share * remaining) must pay one evaluation. Budget left
    over after the final step is WASTED (recorded as `unspent`).
  * Candidate pool: start, every ok probe's best (also mechanism probes), every ok final plan's best; (body, vector, mechanisms)
    duplicates merged. Top `screen_top_k` by train score (walking, survival, mean fitness) are screened on the SCREEN seeds
    (10 s, VARIATION_PRESET).
  * SELECTION RULE v2: key = (passes_effect_bar, walking_count_on_screen, median_screen_score), then train score, then pool order;
    passes_effect_bar = candidate screen median >= the ORIGINAL's screen median + 0.5 m (the verdict_v1 minimum effect for walk).
    This removes a method-independent artifact of selection v1 (a candidate that walks on as many screen seeds but gains nothing over
    the original could win on ties).
  * Final assessment (`assess_final`, NOT charged, done identically for all methods) = `recovery.assess` with the final mechanisms.

Test-only hook: `eval_override` replaces everything that needs MuJoCo. Keys: `cma_fn(body, vector, space, budget, train_seeds, noise_seed) ->
cma_search-like dict` (space = {"ctrl_params", "body_params", "mechanisms"}), `screen_fn(body, vector, mechanisms, seeds) -> rows`,
`diag_fn(body, vector15, seeds)` (baseline), `mech_diag_fn(body, vector, mechanisms, seeds) -> {"gait": {...}}`, `features_fn(body)`,
`similarity_fn` is not used. Real experiments never pass it.
"""
from __future__ import annotations

import copy
import functools
import hashlib
import inspect
import json
import math
import re
import time
from typing import Callable, Sequence

import numpy as np

from . import arena, creature_gen, creature_walk as cw, gait_features as gf, recovery as rc, walk_opt as wo
from . import interventions as iv
from . import r3
from . import verdict as vd
from . import walk_pipelines as wp
from .optimize import jsonable

VERSION = "mech_pipelines_v1"
SELECTION_RULE = "selection_v2"
MIN_EFFECT_M = float(vd.MIN_EFFECT["walk"]["abs"])      # 0.5 m: the verdict_v1 minimum effect for walking
MECH_PROBE_IDS = ("opt_timing", "opt_posture", "opt_feedback", "opt_stride", "opt_body",
                  "foot_x1_5", "torso_x0_7", "torque_x1_5", "legs_x0_8", "legs_x1_2")
MAX_MECH_PER_ROUND = 2
MAX_PROBES_PER_ROUND = 2
MAX_FINAL_PLANS = 2
MAX_PLAN_MECHANISMS = 2
SCREEN_DURATION = wp.SCREEN_DURATION
FIX_BODY_PARAMS = wp.FIX_BODY_PARAMS
SUBSPACES15 = tuple(s for s in wo.SUBSPACES if s != "placement")
FINAL_PLAN_KEYS = {"init", "ctrl_subspaces", "body_params", "mechanisms", "budget_share"}
FINAL_PLAN_OPTIONAL = {"rationale"}
DECISION_KEYS = {"mechanisms", "probes", "stop"}
DECISION_OPTIONAL = {"rationale"}
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,23}$")
RESERVED_IDS = frozenset(set(wp.PROBES) | {"start", "f0", "f1", "none"})
GAIN_BOUND_FRAC = 0.98            # |gain| >= 0.98 * bound counts as "at bound"
GAIN_ZERO_FRAC = 0.05             # |gain| <= 0.05 * bound counts as "near zero"
GAIT_CHANGE_NDIGITS = 6
GENERIC_FALLBACK_SUBSPACES = ("posture", "timing")      # the FIX rule's subspaces when fewer than two subspace probes ran

_MX_OVERRIDE = None


# ---------------------------------------------------------------------------------------------------------- mechanisms module
def set_mechanisms_module(mod) -> None:
    """Tests (and integration experiments) inject a stand-in for `creature_forge.mechanisms`; None restores the real one."""
    global _MX_OVERRIDE
    _MX_OVERRIDE = mod


def mx():
    """The mechanisms module (`creature_forge.mechanisms`), or the injected stand-in."""
    if _MX_OVERRIDE is not None:
        return _MX_OVERRIDE
    try:
        from . import mechanisms
    except ImportError as e:        # pragma: no cover - until the parallel module is integrated
        raise ImportError("creature_forge.mechanisms is not available (not integrated yet)") from e
    return mechanisms


def n_gains(m: dict) -> int:
    """One signed gain per term, in term order."""
    return len(m["terms"])


def _mech_core(m: dict) -> dict:
    return {"id": m["id"], "target": m["target"], "leg": m["leg"], "terms": list(m["terms"]), "gain_bound": float(m["gain_bound"]),
            **({"rationale": m["rationale"]} if m.get("rationale") else {}), **({"revises": m["revises"]} if m.get("revises") else {})}


def _structure_key(m: dict) -> str:
    return json.dumps([m.get("target"), m.get("leg"), list(m.get("terms") or [])], sort_keys=True)


# ---------------------------------------------------------------------------------------------------------- real-physics adapters
def mech_seed_job(job: dict, mechanisms=()) -> dict:
    """challenges.seed_job with the mechanisms attached to the walk controller whenever the vector carries gains (len > 15).
    Module level (used through functools.partial) so it pickles under 'spawn'. The unchanged original has a 15-D vector."""
    from . import challenges
    w = job["controllers"].get("walk")
    if mechanisms and w is not None and len(w["vector"]) > 15:
        job = {**job, "controllers": {**job["controllers"], "walk": {**w, "mechanisms": [dict(m) for m in mechanisms]}}}
    return challenges.seed_job(job)


def job_fn_for(mechanisms) -> Callable | None:
    return functools.partial(mech_seed_job, mechanisms=tuple(dict(m) for m in mechanisms)) if mechanisms else None


def features_with_mechanisms(body: dict, vector, mechanisms, seed: int) -> dict:
    """gait_features for one rollout of (body, vector, mechanisms). Without mechanisms: gf.features_for. With mechanisms this needs the
    integrated hook (features_for(..., mechanisms=...)); it fails loudly if the hook is absent (never silently runs without them)."""
    if not mechanisms:
        return gf.features_for(body, vector, seed)
    if "mechanisms" in inspect.signature(gf.features_for).parameters:
        return gf.features_for(body, vector, seed, mechanisms=[dict(m) for m in mechanisms])
    raise NotImplementedError("gait_features.features_for has no `mechanisms` parameter yet: wire the integration hook")


def assess_final(original: dict, candidate: dict, validate_seeds, confirm_seeds, *, pool=None,
                 variation: dict | None = arena.VARIATION_PRESET) -> dict:
    """UNCHARGED final assessment: `recovery.assess` with the candidate's mechanisms (dict with body, vector, mechanisms)."""
    return rc.assess({"body": original["body"], "vector": original["vector"]},
                     {"body": candidate["body"], "vector": candidate["vector"]}, validate_seeds, confirm_seeds, pool=pool,
                     variation=variation, job_fn=job_fn_for(candidate.get("mechanisms") or ()))


# ---------------------------------------------------------------------------------------------------------- helpers
def _ctrl_params(subspaces: Sequence[str]) -> tuple:
    chosen = {p for n in subspaces for p in wo.SUBSPACES[n]}
    return tuple(p for p in r3.PARAM_NAMES if p in chosen)


def _cand_key(body: dict, vector, mechanisms) -> str:
    ms = [[m["id"], m["target"], m["leg"], list(m["terms"]), float(m["gain_bound"])] for m in mechanisms]
    return hashlib.sha256(json.dumps(jsonable({"body": body, "vector": [float(x) for x in vector], "mechanisms": ms}),
                                     sort_keys=True).encode()).hexdigest()


def vector_for(cand_vector: Sequence[float], cand_mechs: Sequence[dict], new_mechs: Sequence[dict]) -> list[float]:
    """The 15 + sum(terms) vector of `new_mechs` that reproduces the candidate: control part copied, gains of mechanisms the candidate
    already carries copied by id, other gains 0. Raises if the candidate carries a mechanism that `new_mechs` lacks."""
    old = {}
    off = 15
    for m in cand_mechs:
        old[m["id"]] = [float(x) for x in cand_vector[off:off + n_gains(m)]]
        off += n_gains(m)
    if off != len(cand_vector):
        raise ValueError(f"candidate vector has {len(cand_vector)} entries, expected {off}")
    lost = [i for i in old if i not in {m["id"] for m in new_mechs}]
    if lost:
        raise ValueError(f"mechanism(s) {lost} carried by the init are not in the plan")
    out = [float(x) for x in cand_vector[:15]]
    for m in new_mechs:
        out += old.get(m["id"], [0.0] * n_gains(m))
    return out


def gain_report(m: dict, vector: Sequence[float]) -> list[dict]:
    b = float(m["gain_bound"])
    out = []
    for i, (term, g) in enumerate(zip(m["terms"], vector[15:15 + n_gains(m)])):
        g = float(g)
        out.append({"term_index": i, "term": term, "value": g, "bound": b, "fraction_of_bound": g / b if b else 0.0,
                    "at_bound": abs(g) >= GAIN_BOUND_FRAC * b, "near_zero": abs(g) <= GAIN_ZERO_FRAC * b})
    return out


def gait_change(base: dict, post: dict) -> dict:
    out = {}
    for k, v in (post or {}).items():
        b = (base or {}).get(k)
        if isinstance(v, (int, float)) and isinstance(b, (int, float)) and not isinstance(v, bool) \
                and math.isfinite(v) and math.isfinite(b):
            out[k] = round(float(v) - float(b), GAIT_CHANGE_NDIGITS)
    return out


def _improved(p: dict) -> bool:
    return (p.get("delta_walking", 0), p.get("delta_mean_fitness", 0.0)) > (0, 0.0)


# ---------------------------------------------------------------------------------------------------------- validation
def validate_decision_mechanism(m, *, used_ids: set, probed_before: set, structures: dict) -> list[str]:
    """Reasons a proposed mechanism is invalid (empty = valid): the mechanisms module's validator plus the pipeline rules."""
    if not isinstance(m, dict):
        return [f"mechanism must be a dict, got {type(m).__name__}"]
    reasons: list[str] = []
    mid = m.get("id")
    if not isinstance(mid, str) or not ID_RE.match(mid):
        reasons.append(f"id {mid!r} must match {ID_RE.pattern}")
    elif mid in RESERVED_IDS:
        reasons.append(f"id {mid!r} is reserved")
    elif mid in used_ids:
        reasons.append(f"id {mid!r} was already used")
    try:
        reasons += [str(r) for r in mx().validate_mechanism(m)]
    except Exception as e:      # noqa: BLE001 - a validator crash is a rejection with a reason, never an accepted mechanism
        reasons.append(f"mechanism validator raised {type(e).__name__}: {e}")
    rev = m.get("revises")
    if rev is not None:
        if not isinstance(rev, str) or rev not in probed_before:
            reasons.append(f"revises {rev!r} is not a mechanism probed in an earlier round (probed: {sorted(probed_before)})")
        rat = m.get("rationale")
        if not isinstance(rat, str) or not rat.strip():
            reasons.append("a revision needs a non-empty rationale")
    if not reasons:
        dup = structures.get(_structure_key(m))
        if dup:
            reasons.append(f"same target, leg and terms as the earlier mechanism {dup!r}")
    return reasons


def validate_final_plan(plan, *, runs: dict, mech_ids: set) -> list[str]:
    """Reasons a final plan is invalid. `runs` maps ok probe / mechanism-probe ids to the list of mechanism ids their candidate
    carries; `mech_ids` = ids of mechanisms whose probe status is ok."""
    if not isinstance(plan, dict):
        return [f"plan must be a dict, got {type(plan).__name__}"]
    out = []
    extra = set(plan) - FINAL_PLAN_KEYS - FINAL_PLAN_OPTIONAL
    missing = FINAL_PLAN_KEYS - set(plan)
    if extra:
        out.append(f"unknown plan key(s) {sorted(map(str, extra))}")
    if missing:
        return out + [f"missing plan key(s) {sorted(missing)}"]
    init = plan["init"]
    if not isinstance(init, str) or not (init == "start" or init in runs):
        out.append(f"init {init!r} is neither 'start' nor an ok probe / mechanism probe (ok: {sorted(runs)})")
        init = None
    subs = plan["ctrl_subspaces"]
    if not isinstance(subs, (list, tuple)) or not all(isinstance(s, str) for s in subs):
        out.append("ctrl_subspaces must be a list of names")
        subs = []
    else:
        bad = [s for s in subs if s not in SUBSPACES15]
        if bad:
            out.append(f"unknown subspace(s) {bad}; known: {list(SUBSPACES15)}")
        if len(set(subs)) != len(subs):
            out.append("duplicate subspaces")
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
    ms = plan["mechanisms"]
    if not isinstance(ms, (list, tuple)) or not all(isinstance(s, str) for s in ms):
        out.append("mechanisms must be a list of mechanism ids")
        ms = []
    else:
        bad = [s for s in ms if s not in mech_ids]
        if bad:
            out.append(f"mechanism(s) {bad} were not probed successfully (ok: {sorted(mech_ids)})")
        if len(set(ms)) != len(ms):
            out.append("duplicate mechanisms")
        if len(ms) > MAX_PLAN_MECHANISMS:
            out.append(f"at most {MAX_PLAN_MECHANISMS} mechanisms (got {len(ms)})")
    if init is not None and init != "start":
        lost = [i for i in runs.get(init, []) if i not in ms]
        if lost:
            out.append(f"init {init!r} carries mechanism(s) {lost} that the plan does not include")
    if not subs and not bp and not ms:
        out.append("a plan needs at least one dimension")
    sh = plan["budget_share"]
    if isinstance(sh, bool) or not isinstance(sh, (int, float, np.integer, np.floating)) or not math.isfinite(float(sh)) \
            or not 0.0 < float(sh) <= 1.0:
        out.append(f"budget_share must be a number in (0, 1], got {sh!r}")
    return out


# ---------------------------------------------------------------------------------------------------------- selection v2
def passes_effect_bar(cand_median, orig_median, min_effect: float = MIN_EFFECT_M) -> bool:
    """Candidate screen median >= original screen median + min_effect. A candidate without a finite median never passes; if the
    original has no finite median (errors) the bar reduces to 'the candidate has a finite median'."""
    if cand_median is None or not math.isfinite(float(cand_median)):
        return False
    if orig_median is None or not math.isfinite(float(orig_median)):
        return True
    return float(cand_median) >= float(orig_median) + min_effect


def select_final_v2(cands: list[dict], orig_median) -> int:
    """Index of the final candidate. Each: {train_score: [w, s, f], screen: {walking, median, median_score}, order}.
    key = (passes_effect_bar, screen walking seeds, screen median score), then train score, then lower order."""
    best = None
    for i, c in enumerate(cands):
        sc = c["screen"]
        key = (passes_effect_bar(sc.get("median_score"), orig_median), sc["walking"], sc["median"], tuple(c["train_score"]),
               -c["order"])
        if best is None or key > best[0]:
            best = (key, i)
    return best[1]


# ---------------------------------------------------------------------------------------------------------- pipeline
def run_mech_pipeline(body, director, *, total_budget: int, seeds: dict, noise_seed: int, pool=None, probe_budget: int = 300,
                      max_rounds: int = 3, screen_top_k: int = 3, screen_n: int = 12, mode: str = "iterative",
                      director_name: str = "", log: Callable | None = None, start_vector: Sequence[float] | None = None,
                      eval_override: dict | None = None) -> dict:
    t0 = time.perf_counter()
    ov = dict(eval_override or {})
    say = log or (lambda msg: None)
    if mode not in ("iterative", "one_shot"):
        raise ValueError("mode must be 'iterative' or 'one_shot'")
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
    S, D = len(train), len(diag)
    if len(set(train)) != S:
        raise ValueError("train seeds must be distinct")
    for nm, v, lo in (("probe_budget", probe_budget, 0), ("max_rounds", max_rounds, 0), ("screen_top_k", screen_top_k, 1),
                      ("screen_n", screen_n, 1)):
        if isinstance(v, bool) or not isinstance(v, int) or v < lo:
            raise ValueError(f"{nm} must be an integer >= {lo}")
    rounds = 1 if mode == "one_shot" else max_rounds
    reserve = (screen_top_k + 1) * screen_n
    budget = wp.Budget(total_budget)
    if total_budget < reserve + S:
        raise ValueError(f"total_budget {total_budget} cannot pay for screening ({reserve}) and the start evaluation ({S})")
    mech_cost = probe_budget + D

    base = wp._full(body)
    vec15 = [float(x) for x in (cw.R2_WINNER if start_vector is None else start_vector)]
    if len(vec15) != 15:
        raise ValueError("start_vector must be the 15-D transfer vector")
    start_vec = list(vec15)
    cma_kw = dict(train_seeds=train, noise_seed=noise_seed, pool=pool, variation=arena.VARIATION_PRESET)

    def search(b: dict, v: Sequence[float], ctrl: tuple, bodyp: tuple, mechs: Sequence[dict], bud: int) -> dict:
        """Every optimisation goes through here (TRAIN seeds only)."""
        if "cma_fn" in ov:
            return ov["cma_fn"](b, list(v), {"ctrl_params": list(ctrl), "body_params": list(bodyp),
                                             "mechanisms": [dict(m) for m in mechs]}, bud, list(train), noise_seed)
        space = wo.SearchSpace(ctrl_params=ctrl, body_params=bodyp, **({"mechanisms": tuple(mechs)} if mechs else {}))
        return wo.cma_search(b, list(v), space, budget=bud, checkpoints=(), **cma_kw)

    def screen_rows(b: dict, v: Sequence[float], mechs: Sequence[dict]) -> list[dict]:
        if "screen_fn" in ov:
            return ov["screen_fn"](b, list(v), [dict(m) for m in mechs], list(screen_seeds))
        return rc.run_walk_seeds(b, list(v), screen_seeds, duration=SCREEN_DURATION, variation=arena.VARIATION_PRESET, pool=pool,
                                 job_fn=job_fn_for(mechs))

    decisions: list[dict] = []
    probes_run: list[dict] = []          # non-mechanism probes
    mech_probes: list[dict] = []         # mechanism probes (feedback records)
    registry: dict[str, dict] = {}       # mechanism id -> {"mechanism", "round", "probe_status"}
    structures: dict[str, str] = {}
    ledger_runs: dict[str, dict] = {}    # ok probe / mechanism-probe id -> {"body","vector","mechanisms","score"}
    plans_run: list[dict] = []
    round_records: list[dict] = []
    rejected_all: list[dict] = []

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
    budget.charge(reserve, "screen_reserve", {"screen_top_k": screen_top_k, "screen_n": screen_n, "includes_original": True})
    budget.charge(S, "start_eval", {"n_train": S})
    start_rec = search(base, start_vec, ("freq",), (), (), S)["init"]
    start_score = wp._score_dict(start_rec)
    start = {"body": base, "vector": start_vec, "mechanisms": [], "score": start_score}

    def spendable_used() -> int:
        return budget.used - reserve

    def morph_edit(pid: str):
        new, edits = dict(base), []
        bounds = iv.mode_bounds("guided")
        for p, r in wp._MORPH[pid]["scale"].items():
            for f in wo._fields(p):
                new[f] = float(base[f]) * r
                lo, hi = bounds[p]
                if not lo <= new[f] <= hi:
                    return None, [], f"{f} would be {new[f]:.6g}, outside the guided bounds [{lo:g}, {hi:g}]"
            edits.append({"param": p, "op": "scale", "value": r, "target": "both"})
        return new, edits, None

    def availability() -> tuple[list[str], dict]:
        avail, un = [], {}
        done = {p["probe_id"] for p in probes_run}
        for pid in MECH_PROBE_IDS:
            spec = wp.PROBES[pid]
            opt = spec["kind"] in ("subspace", "body")
            cost = probe_budget if opt else S
            if pid in done:
                un[pid] = "already run"
            elif spec["kind"] == "morphology" and morph_edit(pid)[2]:
                un[pid] = morph_edit(pid)[2]
            elif opt and probe_budget < S:
                un[pid] = f"probe_budget {probe_budget} cannot pay the initial evaluation ({S} rollouts)"
            elif cost > budget.remaining:
                un[pid] = f"needs {cost} rollouts, {budget.remaining} remain"
            else:
                avail.append(pid)
        return avail, un

    def mech_affordable() -> str | None:
        if probe_budget < S:
            return f"probe_budget {probe_budget} cannot pay the initial evaluation ({S} rollouts)"
        if mech_cost > budget.remaining:
            return f"a mechanism probe needs {mech_cost} rollouts ({probe_budget} search + {D} diagnostic), {budget.remaining} remain"
        return None

    def make_state(rnd: int, stage: str, rejected_last: list) -> dict:
        avail, unavail = availability()
        return jsonable({
            "stage": stage, "mode": mode,
            "creature": {"body": base, "features": features}, "baseline": baseline, "family": 15,
            "budget": {"total": total_budget, "reserved_for_screening": reserve, "spendable_total": total_budget - reserve,
                       "used": spendable_used(), "remaining": budget.remaining},
            "round": rnd, "rounds_total": rounds, "n_train": S, "n_diag": D, "probe_budget": probe_budget,
            "mechanism_probe_cost": mech_cost, "mechanism_probe_affordable": mech_affordable() is None,
            "start_score": start_score,
            "probes_run": copy.deepcopy(probes_run), "mechanism_probes": copy.deepcopy(mech_probes),
            "mechanisms_registry": {k: {"round": v["round"], "probe_status": v["probe_status"]} for k, v in registry.items()},
            "plans_run": copy.deepcopy(plans_run), "rejected_last_round": copy.deepcopy(rejected_last),
            "available_probes": avail, "unavailable_probes": unavail,
            "probe_costs": {p: (probe_budget if wp.PROBES[p]["kind"] in ("subspace", "body") else S) for p in MECH_PROBE_IDS},
            "probe_catalogue": {"version": wp.WALK_PROBES_VERSION,
                                "probes": {k: dict(wp.PROBES[k]) for k in MECH_PROBE_IDS}}})

    def settle(item: str, reserved: int, used: int) -> int:
        if used > reserved:
            raise wp.BudgetExceeded(f"{item}: used {used} > reserved {reserved}")
        if used < reserved:
            budget.refund(reserved - used, item + ":refund", {"reserved": reserved, "used": used})
        return reserved - used

    # ---- non-mechanism probes (same implementations as walk_pipelines)
    def run_opt_probe(pid: str, rnd: int) -> dict:
        spec = wp.PROBES[pid]
        rec = {"probe_id": pid, "kind": "probe", "round": rnd, "status": "ok", "rollouts": 0, "start_score": start_score}
        try:
            if spec["kind"] in ("subspace", "body"):
                budget.charge(probe_budget, f"probe:{pid}", {"round": rnd, "reserved": probe_budget})
                if spec["kind"] == "subspace":
                    ctrl, bodyp = _ctrl_params([spec["subspace"]]), ()
                else:
                    ctrl, bodyp = (), tuple(spec["body_params"])
                res = search(base, start_vec, ctrl, bodyp, (), probe_budget)
                used = res["rollouts_used"]
                settle(f"probe:{pid}", probe_budget, used)
                best = res["best"]
                rec.update(rollouts=used, best_body=best["body"], best_vector=best["vector"], best_score=wp._score_dict(best),
                           edits=wo.body_edits(base, best["body"]), errors=len(res.get("errors", [])))
            else:
                nb, edits, why = morph_edit(pid)
                if why:
                    raise ValueError(why)
                budget.charge(S, f"probe:{pid}", {"round": rnd})
                r = search(nb, start_vec, ("freq",), (), (), S)["init"]
                rec.update(rollouts=S, best_body=nb, best_vector=list(start_vec), best_score=wp._score_dict(r), edits=edits)
        except wp.BudgetExceeded:
            raise
        except Exception as e:          # noqa: BLE001 - recorded, charge kept (rollouts may have run)
            rec.update(status="error", reason=f"{type(e).__name__}: {e}")
            rec.setdefault("best_score", None)
            return jsonable(rec)
        rec["delta_mean_fitness"] = rec["best_score"]["mean_fitness"] - start_score["mean_fitness"]
        rec["delta_walking"] = rec["best_score"]["walking_count"] - start_score["walking_count"]
        return jsonable(rec)

    # ---- mechanism probe
    def post_gait(b: dict, v: Sequence[float], mechs: Sequence[dict]) -> dict:
        if "mech_diag_fn" in ov:
            return ov["mech_diag_fn"](b, list(v), [dict(m) for m in mechs], list(diag))
        feats = [features_with_mechanisms(b, v, mechs, s) for s in diag]
        return {"gait": gf.summarize(feats)}

    def run_mech_probe(m: dict, rnd: int) -> dict:
        mid = m["id"]
        rec = {"probe_id": mid, "kind": "mechanism", "round": rnd, "status": "ok", "rollouts": 0, "diag_rollouts": 0,
               "start_score": start_score, "mechanism": jsonable(_mech_core(m)), "revises": m.get("revises"),
               "feedback_seed_roles": {"search": "train", "gait": "diag"}}
        budget.charge(probe_budget, f"probe:{mid}", {"round": rnd, "reserved": probe_budget, "kind": "mechanism"})
        budget.charge(D, f"probe:{mid}:diag", {"round": rnd, "n_diag": D})
        try:
            res = search(base, vector_for(start_vec, [], [m]), (), (), [m], probe_budget)
            used = res["rollouts_used"]
            settle(f"probe:{mid}", probe_budget, used)
            best = res["best"]
            vec = [float(x) for x in best["vector"]]
            if len(vec) != 15 + n_gains(m):
                raise ValueError(f"mechanism probe returned a {len(vec)}-D vector, expected {15 + n_gains(m)}")
            rec.update(rollouts=used, best_body=best["body"], best_vector=vec, best_score=wp._score_dict(best),
                       errors=len(res.get("errors", [])), gains=gain_report(m, vec))
        except wp.BudgetExceeded:
            raise
        except Exception as e:          # noqa: BLE001
            rec.update(status="error", reason=f"{type(e).__name__}: {e}", rollouts=probe_budget, best_score=None)
            return jsonable(rec)
        rec["delta_mean_fitness"] = rec["best_score"]["mean_fitness"] - start_score["mean_fitness"]
        rec["delta_walking"] = rec["best_score"]["walking_count"] - start_score["walking_count"]
        rec["improved"] = _improved(rec)
        rec["all_gains_near_zero"] = all(g["near_zero"] for g in rec["gains"])
        rec["any_gain_at_bound"] = any(g["at_bound"] for g in rec["gains"])
        rec["diag_rollouts"] = D
        try:
            pg = post_gait(rec["best_body"], vec, [m])
            rec["post_gait"] = jsonable(pg.get("gait") or {})
            rec["baseline_gait"] = jsonable(baseline.get("gait") or {})
            rec["gait_change"] = gait_change(baseline.get("gait") or {}, rec["post_gait"])
        except Exception as e:          # noqa: BLE001 - the candidate is still valid; the missing feedback is recorded
            rec.update(post_gait=None, post_gait_error=f"{type(e).__name__}: {e}")
        return jsonable(rec)

    # ---- final plans
    def run_plan(pid: str, plan: dict, rnd: int, budget_p: int) -> dict:
        init = start if plan["init"] == "start" else ledger_runs[plan["init"]]
        mechs = [registry[i]["mechanism"] for i in plan["mechanisms"]]
        rec = {"plan_id": pid, "round": rnd, "plan": jsonable(plan), "budget": budget_p, "status": "ok", "init_score": init["score"]}
        budget.charge(budget_p, f"plan:{pid}", {"round": rnd, "reserved": budget_p, "init": plan["init"]})
        try:
            vec0 = vector_for(init["vector"], init["mechanisms"], mechs)
            res = search(init["body"], vec0, _ctrl_params(plan["ctrl_subspaces"]), tuple(plan["body_params"]), mechs, budget_p)
        except wp.BudgetExceeded:
            raise
        except Exception as e:          # noqa: BLE001
            rec.update(status="error", reason=f"{type(e).__name__}: {e}", rollouts_used=budget_p, refunded=0)
            return jsonable(rec)
        used = res["rollouts_used"]
        refunded = settle(f"plan:{pid}", budget_p, used)
        best = res["best"]
        rec.update(rollouts_used=used, refunded=refunded, best_score=wp._score_dict(best), best_body=best["body"],
                   best_vector=[float(x) for x in best["vector"]], mechanisms=[dict(m) for m in mechs],
                   edits=wo.body_edits(base, best["body"]),
                   improvement={"delta_mean_fitness": best["mean_fitness"] - start_score["mean_fitness"],
                                "delta_walking": best["walking_count"] - start_score["walking_count"]},
                   errors=len(res.get("errors", [])))
        return jsonable(rec)

    # ---------------------------------------------------------------------------------------- investigation loop
    rejected_last: list[dict] = []
    stopped_by = "max_rounds"
    for rnd in range(1, rounds + 1):
        if budget.remaining < S:
            stopped_by = "budget"
            break
        rr = {"round": rnd, "mechanisms": [], "probes": [], "rejected_mechanisms": [], "rejected_probes": [], "stop": False,
              "ignored_keys": []}
        round_records.append(rr)
        raw = director.investigate(make_state(rnd, "investigate", rejected_last))
        decisions.append({"round": rnd, "kind": "investigate", "returned": jsonable(copy.deepcopy(raw))})
        rejected_last = []
        if not isinstance(raw, dict):
            r = {"kind": "decision", "id": None, "reasons": [f"investigate must return a dict, got {type(raw).__name__}"]}
            rr["rejected_mechanisms"].append(r)
            rejected_last.append(r)
            raw = {}
        rr["ignored_keys"] = sorted(map(str, set(raw) - DECISION_KEYS - DECISION_OPTIONAL))
        probed_before = {k for k, v in registry.items() if v["round"] < rnd}
        mlist = raw.get("mechanisms", [])
        if not isinstance(mlist, list):
            r = {"kind": "mechanism", "id": None, "reasons": [f"mechanisms must be a list, got {type(mlist).__name__}"]}
            rr["rejected_mechanisms"].append(r)
            rejected_last.append(r)
            mlist = []
        for k, m in enumerate(mlist):
            mid = m.get("id") if isinstance(m, dict) else None
            reasons = [f"more than {MAX_MECH_PER_ROUND} mechanisms in a round"] if k >= MAX_MECH_PER_ROUND else \
                validate_decision_mechanism(m, used_ids=set(registry), probed_before=probed_before, structures=structures)
            if not reasons:
                why = mech_affordable()
                if why:
                    reasons.append(why)
            if reasons:
                r = {"kind": "mechanism", "index": k, "id": jsonable(mid), "mechanism": jsonable(m), "reasons": reasons}
                rr["rejected_mechanisms"].append(r)
                rejected_last.append(r)
                continue
            say(f"round {rnd}: mechanism probe {mid}")
            registry[mid] = {"mechanism": copy.deepcopy(m), "round": rnd, "probe_status": None}
            structures[_structure_key(m)] = mid
            res = run_mech_probe(m, rnd)
            registry[mid]["probe_status"] = res["status"]
            rr["mechanisms"].append(res)
            mech_probes.append(res)
            if res["status"] == "ok":
                ledger_runs[mid] = {"body": res["best_body"], "vector": res["best_vector"], "mechanisms": [dict(m)],
                                    "score": res["best_score"]}
        plist = raw.get("probes", [])
        if not isinstance(plist, list):
            r = {"kind": "probe", "id": None, "reasons": [f"probes must be a list, got {type(plist).__name__}"]}
            rr["rejected_probes"].append(r)
            rejected_last.append(r)
            plist = []
        for k, pid in enumerate(plist):
            if k >= MAX_PROBES_PER_ROUND:
                reason = f"more than {MAX_PROBES_PER_ROUND} probes in a round"
            elif not isinstance(pid, str) or pid not in MECH_PROBE_IDS:
                reason = f"unknown probe (catalogue: {list(MECH_PROBE_IDS)})"
            else:
                avail, un = availability()
                reason = None if pid in avail else un.get(pid, "unavailable")
            if reason:
                r = {"kind": "probe", "index": k, "id": jsonable(pid), "reasons": [reason]}
                rr["rejected_probes"].append(r)
                rejected_last.append(r)
                continue
            say(f"round {rnd}: probe {pid}")
            res = run_opt_probe(pid, rnd)
            rr["probes"].append(res)
            probes_run.append(res)
            if res["status"] == "ok":
                ledger_runs[pid] = {"body": res["best_body"], "vector": res["best_vector"], "mechanisms": [], "score": res["best_score"]}
        stop = raw.get("stop", False)
        if not isinstance(stop, bool):
            r = {"kind": "decision", "id": None, "reasons": [f"stop must be a boolean, got {stop!r}; treated as false"]}
            rr["rejected_mechanisms"].append(r)
            rejected_last.append(r)
            stop = False
        rr["stop"] = stop
        rejected_all += [dict(r, round=rnd) for r in rejected_last]
        if stop:
            stopped_by = "director_stop"
            break

    # ---------------------------------------------------------------------------------------- final plan
    final_round = (round_records[-1]["round"] if round_records else 0) + 1
    fstate = make_state(final_round, "final", rejected_last)
    raw = director.final_plan(fstate)
    decisions.append({"round": final_round, "kind": "final_plan", "returned": jsonable(copy.deepcopy(raw))})
    final_rec = {"plans": [], "rejected_plans": [], "remaining_before": budget.remaining}
    rem0 = budget.remaining
    if not isinstance(raw, list):
        final_rec["rejected_plans"].append({"index": None, "plan": None, "reasons": [f"final_plan must return a list, got {type(raw).__name__}"]})
        raw = []
    runs_carry = {k: [m["id"] for m in v["mechanisms"]] for k, v in ledger_runs.items()}
    ok_mech_ids = {k for k, v in registry.items() if v["probe_status"] == "ok"}
    cum = 0.0
    for idx, plan in enumerate(raw):
        reasons = [f"more than {MAX_FINAL_PLANS} plans"] if idx >= MAX_FINAL_PLANS else \
            validate_final_plan(plan, runs=runs_carry, mech_ids=ok_mech_ids)
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
                if plan["ctrl_subspaces"] or plan["body_params"]:
                    sp = wo.SearchSpace(ctrl_params=_ctrl_params(plan["ctrl_subspaces"]), body_params=tuple(plan["body_params"]))
                    wo.encode(sp, init["body"], init["vector"][:15], init["body"], init["vector"][:15])
                vector_for(init["vector"], init["mechanisms"], [registry[i]["mechanism"] for i in plan["mechanisms"]])
            except ValueError as e:
                reasons.append(f"search space not usable from this init: {e}")
        if reasons:
            final_rec["rejected_plans"].append({"index": idx, "plan": jsonable(plan), "reasons": reasons})
            continue
        cum += float(plan["budget_share"])
        pid = f"f{idx}"
        say(f"final plan {pid} budget {plan_budget}")
        res = run_plan(pid, plan, final_round, plan_budget)
        final_rec["plans"].append(res)
        plans_run.append(res)
        if res["status"] == "ok":
            ledger_runs[pid] = {"body": res["best_body"], "vector": res["best_vector"], "mechanisms": res["mechanisms"],
                                "score": res["best_score"]}
    final_rec["unspent"] = budget.remaining
    final_rec["round"] = final_round

    # ---------------------------------------------------------------------------------------- screening and selection v2
    def tup(sc):
        return [int(sc["walking_count"]), int(sc["survival_count"]), float(sc["mean_fitness"])]

    pool_c: list[dict] = []
    seen: dict[str, int] = {}

    def add(source, b, v, ms, sc):
        key = _cand_key(b, v, ms)
        if key in seen:
            pool_c[seen[key]]["aliases"].append(source)
            return
        seen[key] = len(pool_c)
        pool_c.append({"source": source, "body": b, "vector": [float(x) for x in v], "mechanisms": [dict(m) for m in ms],
                       "train_score": tup(sc), "order": len(pool_c), "aliases": [], "key": key})

    add("start", base, start_vec, [], start_score)
    for p in probes_run:
        if p["status"] == "ok":
            add(p["probe_id"], p["best_body"], p["best_vector"], [], p["best_score"])
    for p in mech_probes:
        if p["status"] == "ok":
            add(p["probe_id"], p["best_body"], p["best_vector"], [registry[p["probe_id"]]["mechanism"]], p["best_score"])
    for p in plans_run:
        if p["status"] == "ok":
            add(p["plan_id"], p["best_body"], p["best_vector"], p["mechanisms"], p["best_score"])
    top = sorted(pool_c, key=lambda c: (c["train_score"], -c["order"]), reverse=True)[:screen_top_k]
    budget.refund(reserve, "screen_reserve:release", {})
    start_key = pool_c[0]["key"]
    budget.charge(screen_n, "screen:original", {"screen_n": screen_n, "purpose": "effect bar of selection v2"})
    orig_screen = wp._screen_summary(screen_rows(base, start_vec, []))
    screened = []
    for c in top:
        if c["key"] == start_key:
            c["screen"] = orig_screen            # the original's screen, measured once and charged once
        else:
            budget.charge(screen_n, f"screen:{c['source']}", {"screen_n": screen_n})
            c["screen"] = wp._screen_summary(screen_rows(c["body"], c["vector"], c["mechanisms"]))
        screened.append(c)
    orig_median = orig_screen["median_score"]
    wi = select_final_v2(screened, orig_median)
    win = screened[wi]
    used = budget.used
    assert used <= total_budget, "budget exceeded"
    assert used == sum(l["n"] for l in budget.lines), "ledger sum mismatch"

    def cand_rec(c):
        sc = {k: v for k, v in c["screen"].items() if k != "median"}
        return {"source": c["source"], "aliases": c["aliases"], "train_score": c["train_score"], "screen": sc,
                "passes_effect_bar": passes_effect_bar(c["screen"].get("median_score"), orig_median),
                "mechanism_ids": [m["id"] for m in c["mechanisms"]]}

    return jsonable({
        "version": VERSION, "selection_rule": SELECTION_RULE, "director": director_name or type(director).__name__, "mode": mode,
        "family": 15, "total_budget": total_budget, "budget_lines": budget.lines, "used": used, "unspent_after_final_step": final_rec["unspent"],
        "rounds": round_records, "stopped_by": stopped_by, "final_step": final_rec, "baseline": baseline, "start_score": start_score,
        "mechanisms": {k: {"mechanism": v["mechanism"], "round": v["round"], "probe_status": v["probe_status"]} for k, v in registry.items()},
        "mechanism_probes": mech_probes, "probes": probes_run, "rejected": rejected_all,
        "candidates": [cand_rec(c) for c in screened],
        "selection": {"rule": SELECTION_RULE, "min_effect_m": MIN_EFFECT_M, "original_screen": orig_screen,
                      "original_median_score": orig_median, "bar": None if orig_median is None else orig_median + MIN_EFFECT_M,
                      "winner_index": wi, "key": "(passes_effect_bar, screen_walking, screen_median_score, train_score, -order)"},
        "final": {"body": win["body"], "vector": win["vector"], "mechanisms": win["mechanisms"],
                  "mechanism_ids": [m["id"] for m in win["mechanisms"]], "edits": wo.body_edits(base, win["body"]),
                  "source": win["source"], "aliases": win["aliases"], "train_score": win["train_score"],
                  "screen": {k: v for k, v in win["screen"].items() if k != "median"}},
        "decisions": decisions,
        "seeds": {"train": train, "screen": screen_seeds, "diag": diag},
        "seed_roles": {"feedback": ["train", "diag"], "selection": ["screen"], "note": "no screen/validate/confirm seed enters any feedback"},
        "settings": {"probe_budget": probe_budget, "max_rounds": max_rounds, "rounds_used": len(round_records), "screen_top_k": screen_top_k,
                     "screen_n": screen_n, "noise_seed": noise_seed, "mode": mode, "mechanism_probe_cost": mech_cost,
                     "rejection_rule": "rejected item costs 0, never repaired"},
        "wall_s": time.perf_counter() - t0})


# ---------------------------------------------------------------------------------------------------------- non-AI directors
def _fix_final_plan(state: dict, *, mechanisms_enabled: bool = True) -> list[dict]:
    """The FIX rule (as walk_pipelines.FixedDirector round 1) extended with improved mechanism probes: union of the top-2 subspace
    probes (ranked by delta_walking, delta_mean_fitness, FIX priority order; default posture + timing if fewer than two ran), body
    params if opt_body (or a morphology probe) improved, init = the best improved run (probe or mechanism probe) else "start", the
    (at most 2) best improved mechanism probes, share 1.0."""
    order = {p: i for i, p in enumerate(wp.FIX_PRIORITY)}
    runs = [p for p in state["probes_run"] if p["status"] == "ok"]
    mruns = [p for p in state["mechanism_probes"] if p["status"] == "ok"] if mechanisms_enabled else []
    key = lambda p: (-p["delta_walking"], -p["delta_mean_fitness"], order.get(p["probe_id"], 99))   # noqa: E731
    sub = sorted((p for p in runs if wp.PROBES[p["probe_id"]]["kind"] == "subspace"), key=key)[:2]
    subs = [wp.PROBES[p["probe_id"]]["subspace"] for p in sub]
    for s in GENERIC_FALLBACK_SUBSPACES:
        if len(subs) < 2 and s not in subs:
            subs.append(s)
    allr = sorted(runs + mruns, key=key)
    init = allr[0]["probe_id"] if allr and _improved(allr[0]) else "start"
    body = any(_improved(p) for p in runs if wp.PROBES[p["probe_id"]]["kind"] in ("morphology", "body"))
    mech = [p["probe_id"] for p in sorted((p for p in mruns if _improved(p)), key=key)[:MAX_PLAN_MECHANISMS]]
    return [{"init": init, "ctrl_subspaces": subs, "body_params": list(FIX_BODY_PARAMS) if body else [], "mechanisms": mech,
             "budget_share": 1.0}]


class Fix15Director:
    """FIX15: no mechanisms. Probes opt_body, opt_posture, opt_timing (the per-round cap is 2: opt_body + opt_posture in round 1,
    opt_timing in round 2, then stop; with a single round the first two); final plan = FIX rule."""
    PRIORITY = ("opt_body", "opt_posture", "opt_timing")

    def investigate(self, state):
        todo = [p for p in self.PRIORITY if p in state["available_probes"]]
        if state["rounds_total"] < 2:
            return {"probes": todo[:MAX_PROBES_PER_ROUND], "stop": True}
        if state["round"] == 1:
            return {"probes": todo[:MAX_PROBES_PER_ROUND]}
        return {"probes": todo[:MAX_PROBES_PER_ROUND], "stop": True}

    def final_plan(self, state):
        return _fix_final_plan(state, mechanisms_enabled=False)


class GenericDirector:
    """GENERIC: round 1 = opt_body + one mechanism probe per generic linear mechanism (`mechanisms.generic_linear_mechanisms()`,
    2 mechanisms, 8 gains); then stop. Final plan = FIX rule + the generic mechanisms that improved."""

    def investigate(self, state):
        if state["round"] != 1:
            return {"stop": True}
        probes = [p for p in ("opt_body",) if p in state["available_probes"]]
        return {"mechanisms": [dict(m) for m in mx().generic_linear_mechanisms()], "probes": probes, "stop": True}

    def final_plan(self, state):
        return _fix_final_plan(state)


class RandMechDirector:
    """RANDMECH: rounds 1-2 propose two random mechanisms each (`mechanisms.random_mechanism`), round 1 also probes opt_body; then
    stop. Final plan = FIX rule + the (at most 2) best-improving random mechanisms."""

    def __init__(self, seed: int, n_terms: int = 2):
        self.rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0x4D45]))
        self.n_terms = n_terms

    def investigate(self, state):
        rnd = state["round"]
        if rnd > 2:
            return {"stop": True}
        ms = [mx().random_mechanism(self.rng, n_terms=self.n_terms, id=f"rnd_r{rnd}_{i}") for i in range(2)]
        probes = [p for p in ("opt_body",) if rnd == 1 and p in state["available_probes"]]
        return {"mechanisms": ms, "probes": probes, "stop": rnd >= 2 or state["rounds_total"] <= rnd}

    def final_plan(self, state):
        return _fix_final_plan(state)


class ExpertDirector:
    """EXPERT (reference): round 1 = opt_body + the human-designed law (`mechanisms.expert_foot_placement()`); then stop. Final plan
    = FIX rule + the expert mechanism if it improved."""

    def investigate(self, state):
        if state["round"] != 1:
            return {"stop": True}
        probes = [p for p in ("opt_body",) if p in state["available_probes"]]
        return {"mechanisms": [dict(mx().expert_foot_placement())], "probes": probes, "stop": True}

    def final_plan(self, state):
        return _fix_final_plan(state)


class ScriptedMechDirector:
    """Replays decisions: a list of {"round": r, "kind": "investigate"|"final_plan", "returned": ...} (the `decisions` field of a
    pipeline record). A missing (round, kind) returns {} (investigate) or [] (final_plan); the final plan is looked up by kind only."""

    def __init__(self, decisions: Sequence[dict]):
        self.table = {}
        self.final = None
        for d in decisions:
            if not isinstance(d, dict) or d.get("kind") not in ("investigate", "final_plan") or "returned" not in d:
                raise ValueError("each decision needs kind in ('investigate', 'final_plan') and returned")
            if d["kind"] == "final_plan":
                self.final = d["returned"]
            else:
                if "round" not in d:
                    raise ValueError("an investigate decision needs a round")
                self.table[int(d["round"])] = d["returned"]

    def investigate(self, state):
        return copy.deepcopy(self.table.get(state["round"], {}))

    def final_plan(self, state):
        return copy.deepcopy(self.final if self.final is not None else [])
