"""Pre-declared definition of FULL walking recovery (`full_recovery_v1`).

A failing creature counts as *recovered* only if the candidate (body + walking vector) genuinely walks. Small distance
gains are a "partial improvement", never a recovery. The rule is built only from existing frozen rules plus one extra test:

1. Validation conditions equal the existing arena's held-out walk validation: `VALIDATE_N` (24) seeds, 10 s,
   `arena.VARIATION_PRESET` (2x perturbation, push-time jitter, +-10 % friction), built exactly as `arena.evaluate_arms`
   builds its per-seed jobs. `verdict_v1` (`verdict.verdict`) and the frozen `WalkingCriteria` / `aggregate_outcome` are
   reused unchanged. The candidate must have aggregate PASS (>= 80 % of seeds with the frozen `walking` label) AND
   `VERIFIED_IMPROVEMENT` against the original on the same seeds.
2. Confirmation is an ADDITIONAL, HARDER test (not part of the arena): only for candidates that passed step 1 (to save
   rollouts), the candidate runs on `CONFIRM_N` (24) further, disjoint seeds for 20 s under the same variation. It passes
   iff walking fraction >= 0.8 AND median `speed_upright` >= the creature's `min_speed` (`creature_criteria`) AND no seed
   has `body_contact_frac` above `DEFAULT_CRITERIA.max_body_contact_frac`.
3. Any ERROR seed makes the assessment INCONCLUSIVE_ERROR; an error is never counted as success.

`AUDIT_CHECKLIST` lists what a human must still confirm by replaying the recovered gait; the numbers alone do not
replace that audit.
"""
from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np

from . import creature_walk as cw
from . import verdict as vd
from .arena import VARIATION_PRESET, _body_with_friction, _condition
from .challenges import ChallengeSpec, _as_body, aggregate_outcome, default_spec, seed_job
from .forge_pool import InlinePool, is_error
from .locomotion import DEFAULT_CRITERIA
from .optimize import jsonable

RECOVERY_RULE = "full_recovery_v1"
VALIDATE_N = 24
CONFIRM_N = 24
TRAIN_DURATION = 10.0
CONFIRM_DURATION = 20.0
PASS_FRAC = 0.8
STATUSES = ("FULL_RECOVERY", "PARTIAL_IMPROVEMENT", "NOT_RECOVERED", "INCONCLUSIVE_ERROR")
AUDIT_CHECKLIST = (
    "alternating left/right steps are visible",
    "no knee or torso dragging on the ground",
    "no hopping or chattering gait",
    "torso is upright at the end of the run",
    "forward progress throughout the run",
    "not a fall that is merely delayed past the horizon",
)


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def run_walk_seeds(body: dict, vector: Sequence[float], seeds: Sequence[int], *, duration: float = TRAIN_DURATION,
                   variation: dict | None = VARIATION_PRESET, pool=None, job_fn: Callable | None = None) -> list[dict]:
    """Run one walk rollout per seed (one pool job each) under the arena's per-seed conditions; errors stay as ERROR rows."""
    pool = pool or InlinePool()
    seeds = [int(s) for s in seeds]
    base = ChallengeSpec.from_dict({**default_spec("walk", seeds).to_dict(), "duration": float(duration)})
    controllers = {"stand": None, "walk": {"vector": [float(x) for x in vector], "provenance": {"kind": "custom"}}}
    jobs, conds = [], []
    for s in seeds:
        b, spec = body, base
        cond = {"perturb": base.perturb, "push_time": base.push_time, "friction_used": body.get("foot_friction")}
        if variation:
            c = _condition(s, base, variation)
            b, used = _body_with_friction(body, c["friction_factor"])
            spec = ChallengeSpec.from_dict({**base.to_dict(), "seeds": [s], "perturb": c["perturb"], "push_time": c["push_time"]})
            cond = {"perturb": c["perturb"], "push_time": c["push_time"], "friction_used": used}
        jobs.append({"body": b, "controllers": controllers, "spec": spec.to_dict(), "seed": s})
        conds.append(cond)
    out: dict[int, dict] = {}
    for i, res in pool.imap(job_fn or seed_job, jobs):
        if is_error(res):
            res = {"seed": seeds[i], "outcome": "ERROR", "score": None, "metrics": {}, "error": str(res[1])}
        out[i] = res
    rows = []
    for i, s in enumerate(seeds):
        res = out.get(i) or {"outcome": "ERROR", "metrics": {}, "error": "no result returned by the pool"}
        m = res.get("metrics") or {}
        outcome = res.get("outcome", "ERROR")
        err = res.get("error") or ("ERROR without a message" if outcome == "ERROR" else None)
        rows.append({"seed": s, "outcome": outcome, "score": None if outcome == "ERROR" else _num(res.get("score")),
                     "walking": outcome == "PASS", "fell": m.get("fell"), "label": m.get("label"),
                     "fall_time": m.get("fall_time"), "forward_disp_upright": m.get("forward_disp_upright"),
                     "speed_upright": m.get("speed_upright"), "body_contact_frac": m.get("body_contact_frac"),
                     "valid_steps": m.get("valid_steps"), "error": err, **conds[i]})
    return jsonable(rows)


def _frac(rows: list[dict]) -> float:
    return sum(r["outcome"] == "PASS" for r in rows) / len(rows) if rows else 0.0


def _confirm(candidate: dict, rows: list[dict]) -> dict:
    crit = cw.creature_criteria(_as_body(candidate["body"]))
    med = float(np.median([_num(r["speed_upright"]) or 0.0 for r in rows])) if rows else 0.0
    bad = [r["seed"] for r in rows
           if _num(r["body_contact_frac"]) is None or _num(r["body_contact_frac"]) > DEFAULT_CRITERIA.max_body_contact_frac]
    agg = aggregate_outcome([r["outcome"] for r in rows])
    checks = {"walking_frac": {"value": _frac(rows), "need": PASS_FRAC, "passed": agg == "PASS"},
              "median_speed_upright": {"value": med, "need": crit.min_speed, "passed": med >= crit.min_speed},
              "body_contact": {"seeds_over": bad, "max_frac": DEFAULT_CRITERIA.max_body_contact_frac, "passed": not bad}}
    return {"run": True, "duration": CONFIRM_DURATION, "per_seed": rows, "aggregate": agg, "checks": checks,
            "passed": all(c["passed"] for c in checks.values())}


def assess(original: dict, candidate: dict, validate_seeds: Sequence[int], confirm_seeds: Sequence[int], *, pool=None,
           variation: dict | None = VARIATION_PRESET, job_fn: Callable | None = None) -> dict:
    """Classify a candidate against the original under `full_recovery_v1`. original/candidate = {"body": dict, "vector": list}."""
    vs, cs = [int(s) for s in validate_seeds], [int(s) for s in confirm_seeds]
    if set(vs) & set(cs):
        raise ValueError(f"validation and confirmation seeds must be disjoint, shared: {sorted(set(vs) & set(cs))}")
    kw = {"variation": variation, "pool": pool, "job_fn": job_fn}
    orig = run_walk_seeds(original["body"], original["vector"], vs, duration=TRAIN_DURATION, **kw)
    cand = run_walk_seeds(candidate["body"], candidate["vector"], vs, duration=TRAIN_DURATION, **kw)
    outcomes = [r["outcome"] for r in cand]
    aggregate = aggregate_outcome(outcomes)
    vd_out = vd.verdict("walk", [r["score"] for r in orig], [r["score"] for r in cand],
                        original_pass=[r["walking"] for r in orig], candidate_pass=[r["walking"] for r in cand])
    errors = [("original", r["seed"], r["error"]) for r in orig if r["outcome"] == "ERROR"] + \
             [("candidate", r["seed"], r["error"]) for r in cand if r["outcome"] == "ERROR"]
    verified = vd_out["status"] == "VERIFIED_IMPROVEMENT"
    reasons: list[str] = []
    conf: dict = {"run": False, "reason": ""}
    if errors:
        conf["reason"] = "validation had ERROR seeds"
        reasons.append(f"{len(errors)} validation rollout(s) errored; nothing is counted as success")
    elif aggregate != "PASS" or not verified:
        conf["reason"] = "validation conditions not met"
        if aggregate != "PASS":
            reasons.append(f"candidate aggregate is {aggregate}, not PASS (walking on {outcomes.count('PASS')} of "
                           f"{len(outcomes)} seeds; PASS needs >= {PASS_FRAC:.0%})")
        if not verified:
            reasons.append(f"verdict_v1 is {vd_out['status']}, not VERIFIED_IMPROVEMENT")
    else:
        conf = _confirm(candidate, run_walk_seeds(candidate["body"], candidate["vector"], cs, duration=CONFIRM_DURATION, **kw))
        bad = [r for r in conf["per_seed"] if r["outcome"] == "ERROR"]
        if bad:
            errors += [("candidate-confirm", r["seed"], r["error"]) for r in bad]
            reasons.append("confirmation rollout(s) errored; nothing is counted as success")
        else:
            ck = conf["checks"]
            if not ck["walking_frac"]["passed"]:
                reasons.append(f"confirmation: walking on {ck['walking_frac']['value']:.0%} of seeds at {CONFIRM_DURATION:g} s, "
                               f"needs >= {PASS_FRAC:.0%}")
            if not ck["median_speed_upright"]["passed"]:
                reasons.append(f"confirmation: median upright speed {ck['median_speed_upright']['value']:.3f} m/s below the "
                               f"minimum {ck['median_speed_upright']['need']:.3f} m/s")
            if not ck["body_contact"]["passed"]:
                reasons.append(f"confirmation: body contact above {ck['body_contact']['max_frac']} on seeds "
                               f"{ck['body_contact']['seeds_over']}")
    if errors:
        status = "INCONCLUSIVE_ERROR"
    elif conf.get("run") and conf["passed"]:
        status = "FULL_RECOVERY"
    elif verified:
        status = "PARTIAL_IMPROVEMENT"
    else:
        status = "NOT_RECOVERED"
    n_conf = len(cs) if conf.get("run") else 0
    out = {"rule": RECOVERY_RULE, "status": status, "reasons": reasons,
           "validation": {"original": orig, "candidate": cand, "verdict": vd_out, "aggregate": aggregate,
                          "walking_frac": _frac(cand)},
           "confirmation": conf,
           "rollouts": {"validation": len(orig) + len(cand), "confirmation": n_conf,
                        "confirmation_rollout_equivalents": n_conf * CONFIRM_DURATION / TRAIN_DURATION},
           "variation": dict(variation) if variation else None,
           "seeds": {"validate": vs, "confirm": cs}}
    if errors:
        out["errors"] = [{"arm": a, "seed": s, "error": e} for a, s, e in errors]
    if status == "NOT_RECOVERED":
        out["worse"] = vd_out["status"] == "WORSE"
    return jsonable(out)


def summarize_statuses(assessments: Sequence[dict]) -> dict:
    counts = {s: 0 for s in STATUSES}
    for a in assessments:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    return {"rule": RECOVERY_RULE, "n": len(assessments), "counts": counts}
