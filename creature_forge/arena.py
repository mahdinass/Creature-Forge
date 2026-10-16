"""The Forge arena (contracts sections 6.1-6.2): matched comparison of the original creature against AI, random-baseline and
heuristic redesigns, judged by `verdict_v1` on held-out validation seeds.

Protocol (every number comes from a MuJoCo rollout via `challenges.seed_job`; nothing here reads model confidence):

  1. build  every arm's body/controllers from its edits (`interventions.validate_edits` + `apply_edits`). An arm that cannot be
            built is recorded with its error and never run, never dropped.
  2. retune walk only. If ANY arm requests `retune_controller`, EVERY arm including the original gets `adapt_controller` with the
            identical budget, training seeds and noise seed (the fairness rule).
  3. screen all arms x screen seeds, one pool job per (arm, seed).
  4. select best AI arm = highest median screening score among AI arms (ties: higher mean, then arm order); best baseline likewise
            among random + heuristic arms. Screening only selects.
  5. validate original + selected arms on the validation seeds (used once, never for selection); `verdict_v1` per selected arm
            against the original, paired by seed. Only validation decides.

Same inputs give the identical record (wall time excepted). `validation_variation` (off by default) varies the validation
CONDITIONS per seed identically for every arm: larger initial perturbation, extra push-time jitter, foot friction +-pct.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from . import creature_walk as cw
from . import interventions as iv
from .challenges import PUSH_BISECTION_STEPS, ChallengeSpec, default_spec, controller_provenance, seed_job
from .creatures import seed_block
from .forge_pool import InlinePool, is_error
from .interventions import Edit
from .optimize import jsonable
from .sandbox import SANDBOX_BOUNDS
from . import verdict as vd

ARENA_VERSION = "arena_v1"
AI_SOURCES = ("nemotron", "scripted_mock")
BASELINE_SOURCES = ("random_baseline", "heuristic")
SOURCES = ("original",) + AI_SOURCES + BASELINE_SOURCES
SELECTION_RULE = ("Screening only selects. Best AI arm = highest MEDIAN screening score among AI arms (ties: higher mean, then arm order); "
                  "best baseline = the same rule among random_baseline + heuristic arms. Arms with any ERROR seed are excluded and listed. "
                  "Validation (held-out seeds, original + selected arms + the selected AI arm's own matched-random twin, so every AI "
                  "verdict has a like-for-like control on the same seeds) decides via verdict_v1. Model confidence is never read.")
VARIATION_PRESET = {"perturb_mult": 2.0, "push_time_jitter_s": 0.15, "friction_pct": 0.10}   # proposed, off by default
_KEEP = {
    "stand": ("survival_s", "fell", "fall_time", "max_abs_pitch_after_settle", "min_height_ratio", "saturation_frac", "slip_frac"),
    "push": ("critical_force_fwd", "critical_force_bwd", "weak_direction", "censored", "falls_without_push", "force_resolution_N"),
    "walk": ("label", "walking", "forward_disp_upright", "valid_steps", "fell", "fall_time", "time_upright"),
}


# ---------------------------------------------------------------------------------------------------------
# config and seeds
# ---------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ArenaConfig:
    screen_seeds: tuple
    validate_seeds: tuple
    train_seeds: tuple = ()
    retune_budget: int = 0
    n_validate_arms: int = 2          # best AI arm + best baseline arm (the original is always validated)
    noise_seed: int = 0               # adaptation noise stream, identical for every retuned arm
    validation_variation: dict | None = None   # None = off; keys perturb_mult, push_time_jitter_s, friction_pct

    def __post_init__(self):
        for name in ("screen_seeds", "validate_seeds", "train_seeds"):
            object.__setattr__(self, name, tuple(int(s) for s in getattr(self, name)))
        if not self.screen_seeds or not self.validate_seeds:
            raise ValueError("screen_seeds and validate_seeds must not be empty")
        sets = {"screen": set(self.screen_seeds), "validate": set(self.validate_seeds), "train": set(self.train_seeds)}
        for n, v in sets.items():
            if len(v) != len(getattr(self, n + "_seeds")):
                raise ValueError(f"{n} seeds must be distinct")
        for a, b in (("screen", "validate"), ("screen", "train"), ("validate", "train")):
            if sets[a] & sets[b]:
                raise ValueError(f"{a} and {b} seeds must be disjoint")
        if isinstance(self.retune_budget, bool) or not isinstance(self.retune_budget, int) or self.retune_budget < 0:
            raise ValueError("retune_budget must be a non-negative integer")
        if not isinstance(self.n_validate_arms, int) or not (0 <= self.n_validate_arms <= 2):
            raise ValueError("n_validate_arms must be 0, 1 or 2 (best AI arm, best baseline arm)")
        if self.validation_variation is not None:
            object.__setattr__(self, "validation_variation", _check_variation(self.validation_variation))

    def to_dict(self) -> dict:
        return {"screen_seeds": list(self.screen_seeds), "validate_seeds": list(self.validate_seeds),
                "train_seeds": list(self.train_seeds), "retune_budget": self.retune_budget,
                "n_validate_arms": self.n_validate_arms, "noise_seed": self.noise_seed,
                "validation_variation": None if self.validation_variation is None else dict(self.validation_variation)}


def _check_variation(v: dict) -> dict:
    allowed = {"perturb_mult", "push_time_jitter_s", "friction_pct"}
    extra = sorted(set(v) - allowed)
    if extra:
        raise ValueError(f"unknown validation_variation field(s): {extra}")
    out = {"perturb_mult": 1.0, "push_time_jitter_s": 0.0, "friction_pct": 0.0, **v}
    for k, (lo, hi) in {"perturb_mult": (1.0, 10.0), "push_time_jitter_s": (0.0, 0.5), "friction_pct": (0.0, 0.5)}.items():
        x = out[k]
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not (lo <= x <= hi):
            raise ValueError(f"validation_variation.{k}={x!r} must be a number in [{lo:g}, {hi:g}]")
        out[k] = float(x)
    return out


DEFAULT_SIZES = {"challenge": 8, "train": 3, "screen": 4, "validate": 8}


def _forbidden_seeds() -> dict[str, tuple]:
    from . import demo, r2, r3     # lazy: heavy modules only needed for the disjointness check
    sets = {**r2.consumed_seed_sets(), **{f"r3:{k}": v for k, v in r3.consumed_seed_sets().items()},
            "r3_evidence_pool": r3.EVIDENCE_POOL_SEEDS, "r3_screen_pool": r3.SCREEN_POOL_SEEDS,
            "r3_validation": r3.VALIDATION_SEEDS, "r3_pilot": r3.PILOT_SEEDS, "demo_verify": demo.VERIFY_SEEDS}
    top = max(max(v) for v in sets.values() if len(v))
    assert top < 100_000, f"a consumed seed set reaches {top}; the >= 100000 namespace is no longer safe"
    return sets


def seed_sets(cid: str, n: int, round: int, sizes: dict | None = None, *, max_bumps: int = 64) -> dict:
    """Role blocks of one investigation from `creatures.seed_block` (contracts section 7). Roles: any of challenge, train, screen,
    validate, probe with their sizes (default `DEFAULT_SIZES`). Asserts the blocks are pairwise disjoint and disjoint from every
    consumed/registered seed set (all < 100000); on a collision the round salt is bumped.
    Returns {"round": round_used, "bumped": int, "seeds": {role: tuple}}."""
    sizes = dict(DEFAULT_SIZES if sizes is None else sizes)
    roles = [r for r, k in sizes.items() if k]
    for r in roles:
        if r not in ("challenge", "train", "screen", "validate", "probe"):
            raise ValueError(f"unknown seed role {r!r}")
        if not isinstance(sizes[r], int) or sizes[r] < 0:
            raise ValueError(f"size of {r} must be a non-negative integer")
    forbidden = set().union(*(set(v) for v in _forbidden_seeds().values()))
    for r_try in range(round, round + max_bumps):
        blocks = {role: seed_block(cid, n, r_try, role, sizes[role]) for role in roles}
        seen: set = set()
        clash = False
        for role in roles:
            s = set(blocks[role])
            if s & seen or s & forbidden:
                clash = True
                break
            seen |= s
        if not clash:
            assert all(x >= 100_000 for b in blocks.values() for x in b)
            return {"round": r_try, "bumped": r_try - round, "seeds": blocks}
    raise RuntimeError(f"no disjoint seed blocks found within {max_bumps} round bumps for {cid} v{n}")


# ---------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------
def resolution_for(kind: str, spec: ChallengeSpec) -> float:
    """Score resolution (tie tolerance of the sign test): push = one bisection step, otherwise the verdict default."""
    if kind == "push":
        return float(spec.max_force) / 2 ** spec.bisection_steps
    return vd.DEFAULT_RESOLUTION[kind]


def make_spec(kind: str, seeds: Sequence[int], overrides: dict | None = None) -> ChallengeSpec:
    d = {**default_spec(kind, seeds).to_dict(), **(overrides or {}), "kind": kind, "seeds": [int(s) for s in seeds]}
    return ChallengeSpec.from_dict(d)


def compact(res: dict, kind: str) -> dict:
    """Stored per-seed record: seed, score (None for ERROR), outcome, rollouts, error, a metrics subset."""
    m = res.get("metrics") or {}
    err = res.get("error")
    return {"seed": int(res["seed"]), "score": None if res.get("outcome") == "ERROR" else float(res["score"]),
            "outcome": res["outcome"], "rollouts": int(res.get("rollouts") or 0), "error": err,
            "metrics": {k: m[k] for k in _KEEP[kind] if k in m}}


def _condition(seed: int, spec: ChallengeSpec, variation: dict) -> dict:
    """Validation conditions of one seed; a pure function of (seed, spec, variation), identical for every arm."""
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0x7A11]))
    jitter = float(variation["push_time_jitter_s"])
    pct = float(variation["friction_pct"])
    return {"perturb": min(0.2, spec.perturb * variation["perturb_mult"]),
            "push_time": float(spec.push_time + (rng.uniform(-jitter, jitter) if jitter > 0 else 0.0)),
            "friction_factor": float(1.0 + (rng.uniform(-pct, pct) if pct > 0 else 0.0))}


def _body_with_friction(body: dict, factor: float) -> tuple[dict, float]:
    """Friction scaled by `factor` for the validation condition. A TEST condition, not a model edit: it is clipped into the
    sandbox hull and the value actually used is recorded."""
    lo, hi = SANDBOX_BOUNDS["foot_friction"]
    used = float(min(hi, max(lo, body["foot_friction"] * factor)))
    return {**body, "foot_friction": used}, used


def build_arm(version: dict, kind: str, arm: dict) -> dict:
    """Arm record with body/controllers from its edits. `error` is set (and body/controllers None) if the edits are rejected."""
    arm_id = arm["arm_id"]
    source = arm.get("source", "original" if arm_id == "original" else None)
    if source not in SOURCES:
        raise ValueError(f"arm {arm_id!r}: source must be one of {SOURCES}, got {source!r}")
    edits_in = [e.to_dict() if isinstance(e, Edit) else dict(e) for e in (arm.get("edits") or [])]
    rec = {"arm_id": arm_id, "source": source, "proposal_id": arm.get("proposal_id"), "edits": edits_in, "category": None,
           "body": None, "controllers": None, "controller_provenance": None, "retune": None, "error": None,
           "retune_requested": bool(arm.get("retune_controller") or arm.get("retune"))}
    try:
        if source == "original":
            if edits_in:
                raise ValueError("the original arm has no edits")
            edits: list[Edit] = []
        elif not edits_in:
            raise ValueError("an arm other than the original needs at least one edit")
        else:
            edits, reasons = iv.validate_edits(version, kind, edits_in)
            if reasons:
                raise ValueError("edits rejected: " + " | ".join(reasons))
        body, controllers = iv.apply_edits(version, edits)
        rec["category"] = iv.category(edits) if edits else None
        rec["body"], rec["controllers"] = body, controllers
    except Exception as exc:  # noqa: BLE001 - recorded, never silently dropped
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def _retune(rec: dict, cfg: ArenaConfig, pool, kind: str) -> None:
    init = iv.walk_vector({"controllers": rec["controllers"]})
    res = cw.adapt_controller(iv.sandbox_body({"body": rec["body"]}), init, budget=cfg.retune_budget,
                              train_seeds=list(cfg.train_seeds), noise_seed=cfg.noise_seed, pool=pool)
    adaptation = {"budget": cfg.retune_budget, "rollouts_used": int(res["rollouts_used"]), "train_seeds": list(cfg.train_seeds),
                  "noise_seed": cfg.noise_seed, "parent_vector": [float(x) for x in init],
                  "init_score": res.get("init_score"), "best_score": res.get("best_score"), "improved": res.get("improved")}
    prev = (rec["controllers"].get("walk") or {}).get("provenance") or {}
    rec["controllers"] = {**rec["controllers"], "walk": {
        "vector": [float(x) for x in res["vector"]],
        "provenance": {"kind": "adapted", "edited": bool(prev.get("edited", False)), "adaptation": adaptation}}}
    rec["retune"] = {"budget": cfg.retune_budget, "noise_seed": cfg.noise_seed, "rollouts_used": adaptation["rollouts_used"]}


def evaluate_arms(kind: str, arms: Sequence[dict], seeds: Sequence[int], spec_overrides: dict | None = None, *, pool=None,
                  variation: dict | None = None, progress: Callable | None = None, phase: str = "evaluate") -> dict:
    """Run every built arm (dicts with arm_id, body, controllers) on every seed: ONE pool job per (arm, seed).
    Returns {"results": {arm_id: [compact per-seed record in seed order]}, "conditions": {seed: {...}} | None}."""
    pool = pool or InlinePool()
    base = make_spec(kind, seeds, spec_overrides)
    seeds = [int(s) for s in seeds]
    cond = {s: _condition(s, base, variation) for s in seeds} if variation else None
    jobs, index = [], []
    for arm in arms:
        for s in seeds:
            body, spec = arm["body"], base
            if cond:
                c = cond[s]
                body, _ = _body_with_friction(body, c["friction_factor"])
                spec = ChallengeSpec.from_dict({**base.to_dict(), "seeds": [s], "perturb": c["perturb"], "push_time": c["push_time"]})
            jobs.append({"body": body, "controllers": arm["controllers"], "spec": spec.to_dict(), "seed": s})
            index.append((arm["arm_id"], s))
    results: dict = {a["arm_id"]: {} for a in arms}
    done = 0
    for i, out in pool.imap(seed_job, jobs):
        arm_id, s = index[i]
        if is_error(out):
            out = {"seed": s, "outcome": "ERROR", "score": 0.0, "metrics": {}, "rollouts": 0, "error": out[1]}
        results[arm_id][s] = compact(out, kind)
        done += 1
        if progress is not None:
            progress(done, len(jobs))
    return {"results": {a: [r[s] for s in seeds] for a, r in results.items()}, "conditions": cond}


def _summ(per_seed: list[dict]) -> dict:
    scores = [r["score"] for r in per_seed if r["score"] is not None]
    n_err = sum(r["outcome"] == "ERROR" for r in per_seed)
    return {"median": vd.median(scores) if scores else None, "mean": (sum(scores) / len(scores)) if scores else None,
            "n": len(per_seed), "errors": n_err, "counts": {o: sum(r["outcome"] == o for r in per_seed) for o in ("PASS", "POOR", "FAIL", "ERROR")},
            "rollouts": sum(r["rollouts"] for r in per_seed)}


def select_arms(arms: Sequence[dict], screening: dict) -> dict:
    """Pure selection (see SELECTION_RULE). `arms` in their given order; `screening` {arm_id: [compact seed records]}."""
    groups: dict[str, list] = {"ai": [], "baseline": []}
    excluded: dict[str, str] = {}
    for order, arm in enumerate(arms):
        src = arm["source"]
        if src == "original":
            continue
        group = "ai" if src in AI_SOURCES else "baseline"
        if arm.get("error"):
            excluded[arm["arm_id"]] = f"not built: {arm['error']}"
            continue
        per = screening.get(arm["arm_id"]) or []
        s = _summ(per)
        if not per or s["errors"]:
            excluded[arm["arm_id"]] = f"{s['errors']} of {len(per)} screening seeds errored"
            continue
        groups[group].append({"arm_id": arm["arm_id"], "median": s["median"], "mean": s["mean"], "order": order})
    out: dict = {"rule": SELECTION_RULE, "excluded": excluded, "ranking": {}}
    for g, rows in groups.items():
        rows.sort(key=lambda r: (-r["median"], -r["mean"], r["order"]))
        out["ranking"][g] = rows
        out["ai" if g == "ai" else "baseline"] = rows[0]["arm_id"] if rows else None
    return out


# ---------------------------------------------------------------------------------------------------------
# the arena
# ---------------------------------------------------------------------------------------------------------
def run_arena(version: dict, kind: str, arms: Sequence[dict], cfg: ArenaConfig, *, pool=None, progress: Callable | None = None,
              emit: Callable | None = None, spec_overrides: dict | None = None) -> dict:
    """Run the protocol above and return a JSON-safe record. `arms`: dicts {arm_id, source, proposal_id?, edits, retune_controller?};
    the original arm is added (first) when absent. `emit(type, data)` receives phase / arm_result / verdict / error events;
    `progress(done, total)` counts seed jobs of the current phase."""
    t0 = time.perf_counter()
    if kind not in iv.CHALLENGE_KINDS:
        raise ValueError(f"challenge kind must be one of {iv.CHALLENGE_KINDS}, got {kind!r}")
    pool = pool or InlinePool()

    def ev(t: str, data: dict) -> None:
        if emit is not None:
            emit(t, jsonable(data))

    ids = [a["arm_id"] for a in arms]
    if len(set(ids)) != len(ids):
        raise ValueError("arm ids must be unique")
    arm_list = [dict(a) for a in arms]
    if "original" not in ids:
        arm_list.insert(0, {"arm_id": "original", "source": "original", "edits": []})
    ev("phase", {"phase": "build", "arms": len(arm_list)})
    built = [build_arm(version, kind, a) for a in arm_list]
    notes: list[str] = []
    for r in built:
        if r["error"]:
            ev("error", {"arm_id": r["arm_id"], "error": r["error"]})
    requested = [r["arm_id"] for r in built if r["retune_requested"] and not r["error"]]
    retune_rec = {"applied": False, "requested_by": requested, "budget": cfg.retune_budget, "noise_seed": cfg.noise_seed,
                  "train_seeds": list(cfg.train_seeds)}
    if requested and kind != "walk":
        notes.append(f"retune requested by {requested} is ignored: controller retuning applies to walk challenges only")
    elif requested:
        if cfg.retune_budget < 1 or not cfg.train_seeds:
            raise ValueError("an arm requests retune_controller but the config has no retune_budget / train_seeds")
        ev("phase", {"phase": "retune", "arms": [r["arm_id"] for r in built if not r["error"]]})
        for r in built:      # fairness: EVERY buildable arm, original included, gets the identical adaptation
            if r["error"]:
                continue
            try:
                _retune(r, cfg, pool, kind)
            except Exception as exc:  # noqa: BLE001
                r["error"] = f"retune failed: {type(exc).__name__}: {exc}"
                ev("error", {"arm_id": r["arm_id"], "error": r["error"]})
        retune_rec["applied"] = True
    for r in built:
        if not r["error"]:
            r["controller_provenance"] = controller_provenance(r["controllers"], kind)

    runnable = [r for r in built if not r["error"]]
    screen_spec = make_spec(kind, cfg.screen_seeds, spec_overrides)
    ev("phase", {"phase": "screen", "jobs": len(runnable) * len(cfg.screen_seeds)})
    scr = evaluate_arms(kind, runnable, cfg.screen_seeds, spec_overrides, pool=pool, progress=progress, phase="screen")["results"]
    for a, per in scr.items():
        ev("arm_result", {"phase": "screen", "arm_id": a, "summary": _summ(per)})
    selection = select_arms(built, scr)
    chosen = [a for a in (selection["ai"], selection["baseline"]) if a][:cfg.n_validate_arms]
    twin = None
    if selection["ai"] and selection["ai"] in chosen:
        pid = next((r.get("proposal_id") for r in built if r["arm_id"] == selection["ai"]), None)
        twin = next((r["arm_id"] for r in built if r["source"] == "random_baseline" and pid is not None
                     and r.get("proposal_id") == pid and not r["error"]), None)
        if twin and twin not in chosen:
            chosen.append(twin)
    selection["matched_twin"] = twin
    selection["validated"] = chosen
    val_spec = make_spec(kind, cfg.validate_seeds, spec_overrides)
    validation: dict = {}
    verdicts: dict = {}
    conditions = None
    if chosen:
        ev("phase", {"phase": "validate", "arms": ["original"] + chosen})
        by_id = {r["arm_id"]: r for r in built}
        run_list = [by_id["original"]] + [by_id[a] for a in chosen] if not by_id["original"]["error"] else [by_id[a] for a in chosen]
        out = evaluate_arms(kind, run_list, cfg.validate_seeds, spec_overrides, pool=pool, progress=progress,
                            variation=cfg.validation_variation, phase="validate")
        validation, conditions = out["results"], out["conditions"]
        res = resolution_for(kind, val_spec)
        orig = validation.get("original")
        for a in chosen:
            cand = validation[a]
            if orig is None:
                verdicts[a] = vd.verdict(kind, [None] * len(cand), [r["score"] for r in cand], resolution=res)
            else:
                verdicts[a] = vd.verdict(kind, [r["score"] for r in orig], [r["score"] for r in cand], resolution=res,
                                         original_pass=[r["outcome"] == "PASS" for r in orig],
                                         candidate_pass=[r["outcome"] == "PASS" for r in cand])
            ev("verdict", {"arm_id": a, "verdict": verdicts[a]})
    per_arm_rollouts = {}
    for r in built:
        a = r["arm_id"]
        ad = (r["retune"] or {}).get("rollouts_used", 0)
        sc = sum(x["rollouts"] for x in scr.get(a, []))
        va = sum(x["rollouts"] for x in validation.get(a, []))
        per_arm_rollouts[a] = {"adaptation": ad, "screening": sc, "validation": va, "total": ad + sc + va}
        r["rollouts"] = per_arm_rollouts[a]
    record = {
        "arena_version": ARENA_VERSION, "rule_version": vd.VERDICT_RULE_VERSION, "kind": kind, "config": cfg.to_dict(),
        "spec": {"screen": screen_spec.to_dict(), "validate": val_spec.to_dict(), "overrides": dict(spec_overrides or {})},
        "arms": built, "retune": retune_rec,
        "screening": {a: {"seeds": per, "summary": _summ(per)} for a, per in scr.items()},
        "selection": selection,
        "validation": {a: {"seeds": per, "summary": _summ(per)} for a, per in validation.items()},
        "validation_conditions": None if conditions is None else {str(s): c for s, c in conditions.items()},
        "verdicts": verdicts, "notes": notes,
        "rollouts": {"per_arm": per_arm_rollouts, "total": sum(v["total"] for v in per_arm_rollouts.values())},
        "wall_s": time.perf_counter() - t0}
    return jsonable(record)
