"""The Nemotron scientist of the causal engineer (`causal_scientist_v1`).

A closed-loop investigation of WHY one robot fails. The model sees the robot, a physics observation of it, its own hypothesis ledger
and experiment ledger, and each step chooses exactly one action on the budgeted `eng_tools.Workbench`:

  counterfactual  one catalogue change applied to the current best design and measured on the matched observation seeds. The model
                  registers PREDICTIONS (hypothesis, observable quantity, direction) BEFORE the bench runs; they are scored
                  deterministically afterwards (`score_direction`, tolerances in `tolerance`).
  repair          CMA-ES over one tool's dimensions on the train seeds (budget = floor(share x remaining), refused below the tool's
                  minimum). The model also predicts the train walking count of the result.
  conclude        diagnosis category + explanation + confidence; the design submitted is the bench's best training design.

Hypothesis changes (new hypotheses, status updates citing experiment ids) ride along in every reply, so a step is one model call.
`one_shot` mode is the ablation: ONE call from the initial observation (hypotheses + up to two repairs), no experiments, no feedback.

Trust boundary (physics-integrity): the reply is validated against strict schemas whose ids are enums; invalid replies get ONE repair call
carrying the validator errors; if the step is still invalid it is recorded and the investigation continues, and two consecutive failed
steps END the investigation with the bench's current best design submitted. No rule-based or other non-AI substitute ever makes a decision.
The model never sees: the fault name, severity, repair matrix, check/validate/confirm seeds (the bench only holds train/obs seeds).
Mapping diagnosis categories to benchmark faults lives in `scripts/ce_eval.py`, never here.
Model confidence is recorded and never used.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Sequence

from . import director as dr
from . import eng_tools
from . import fault_bench as fb
from .forge_ai import ModelCall, parse_reply
from .inference_ledger import Caps, InferenceLedger
from .investigation import SCRIPTED_MODEL, new_investigation_id
from .physics_probe import PROBE_DOCS

VERSION = "causal_scientist_v1"
MODES = ("iterative", "one_shot")
SCHEMA_STEP = "scientist_step"
SCHEMA_ONE_SHOT = "scientist_one_shot"
MAX_STEPS = 12
MAX_REQUESTS = 24
MAX_NEW_HYPOTHESES = 3
MAX_CITATIONS = 6
MAX_PREDICTIONS = 8
TEXT_MAX = 1500
STATUSES = ("open", "supported", "refuted", "unresolved")
DIRECTIONS = ("increase", "decrease", "no_change")
MEMORY_VERDICTS = ("applies", "needs_adaptation", "test_first", "does_not_apply")
ACTIONS = ("counterfactual", "repair", "conclude")
NO_ID = "(none)"
INITIAL_OBS = "O0"

# Neutral taxonomy of failure mechanisms (internal id -> phrase an engineer would use). The benchmark's fault names are NOT here.
CATEGORIES = {
    "posture_bias": "forward lean / posture bias",
    "cadence_too_fast": "step cadence too fast for the leg",
    "weak_balance_feedback": "insufficient balance feedback",
    "poor_foot_placement": "inadequate foot placement against forward momentum",
    "short_support_base": "insufficient support base (feet too short)",
    "heavy_upper_body": "excessive or high upper-body mass",
    "low_torque_authority": "insufficient actuator torque authority",
    "low_traction": "insufficient foot traction (slipping)",
    "low_joint_impedance": "joint impedance too low",
    "leg_geometry_mismatch": "leg geometry mismatch",
    "gait_initiation_failure": "gait initiation failure",
    "unresolved": "unresolved",
}

TOOL_NOTES = {   # neutral one-liners: what the tool lets the optimiser change (never when it helps)
    "posture": "control parameters for the trunk/hip posture trim",
    "timing": "control parameters for stride frequency, duty and knee timing",
    "feedback": "control parameters for the balance and pitch feedback gains",
    "stride": "control parameters for stride amplitude",
    "placement": "the two swing-foot placement gains",
    "foot_length": "the foot length (body)",
    "torso_mass": "the torso mass (body)",
    "torque_limit": "the joint torque limit (body)",
    "foot_friction": "the foot friction coefficient (body)",
    "leg_length": "thigh and shank length (body)",
}

# ------------------------------------------------------------------------------------------------------------------ quantities
_NON_QUANTITIES = {"leg_length_m", "fall_direction", "pre_fall", "pre_fall.window_s", "n_swing_phases"}


def build_quantities() -> list[str]:
    """Observable summary keys a prediction may name: every numeric key of `physics_probe.PROBE_DOCS` except bookkeeping ones, plus
    n_walking and n_fell (counts over the observation seeds)."""
    qs = ["n_walking", "n_fell"] + [k for k in PROBE_DOCS if k not in _NON_QUANTITIES]
    return qs


QUANTITIES = build_quantities()

# Tolerance (absolute, in the unit of the quantity); the effective tolerance is max(abs, REL_TOL x |baseline value|). Ordered rules;
# first match on the key without a "pre_fall." prefix. n_walking / n_fell: 0 (exact integer counts).
REL_TOL = 0.05
_TOL_RULES = (
    (re.compile(r"^(fall_time|time_upright)$"), 0.25),                       # seconds
    (re.compile(r"_slope$"), 0.005),                                          # per second
    (re.compile(r"^pitch_rate"), 0.05),
    (re.compile(r"^pitch"), 0.02),                                            # rad
    (re.compile(r"^tracking_error_"), 0.005),                                 # rad
    (re.compile(r"^(max_)?friction_utilisation"), 0.05),
    (re.compile(r"fraction$|^saturation_frac_|^slip_fraction$"), 0.02),
    (re.compile(r"^step_freq_hz$"), 0.15),                                    # Hz
    (re.compile(r"^com_vx"), 0.05),                                           # m/s
    (re.compile(r"over_L|angmom_norm"), 0.02),                                # dimensionless, leg-length normalised
)
DEFAULT_ABS_TOL = 0.02
TOLERANCE_DOCS = ("n_walking, n_fell: exact (tolerance 0). Others: max(absolute, 5 % of the baseline value); absolute tolerances: "
                  "fall_time and time_upright 0.25 s; any *_slope 0.005; pitch_rate 0.05 rad/s; pitch 0.02 rad; tracking_error 0.005 rad; "
                  "friction_utilisation 0.05; fractions and saturation_frac 0.02; step_freq_hz 0.15 Hz; com_vx 0.05 m/s; "
                  "*_over_L and angmom_norm 0.02; anything else 0.02.")


def tolerance(quantity: str, baseline: float | None = None) -> float:
    if quantity in ("n_walking", "n_fell"):
        return 0.0
    key = quantity[len("pre_fall."):] if quantity.startswith("pre_fall.") else quantity
    absolute = DEFAULT_ABS_TOL
    for rx, tol in _TOL_RULES:
        if rx.search(key):
            absolute = tol
            break
    rel = REL_TOL * abs(baseline) if isinstance(baseline, (int, float)) and math.isfinite(baseline) else 0.0
    return max(absolute, rel)


def observed_direction(delta: float, tol: float) -> str:
    if delta > tol:
        return "increase"
    if delta < -tol:
        return "decrease"
    return "no_change"


def quantity_value(obs: dict | None, quantity: str):
    """Value of a prediction quantity in a `physics_probe.observe` result (None when undefined)."""
    if not isinstance(obs, dict):
        return None
    v = None
    if quantity in ("n_walking", "n_fell"):
        v = obs.get(quantity)
    elif quantity.startswith("pre_fall."):
        v = (obs.get("pre_fall_median") or {}).get(quantity[len("pre_fall."):])
    else:
        v = (obs.get("median") or {}).get(quantity)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def score_direction(quantity: str, predicted: str, base: float | None, new: float | None) -> dict:
    """Deterministic scoring of one prediction. status: correct | incorrect | unscored (a value is undefined)."""
    if base is None or new is None:
        return {"quantity": quantity, "predicted": predicted, "observed": None, "status": "unscored", "base": base, "new": new,
                "delta": None, "tolerance": None, "reason": "quantity undefined (None) in the baseline or the intervention"}
    tol = tolerance(quantity, base)
    delta = new - base
    obs = observed_direction(delta, tol)
    return {"quantity": quantity, "predicted": predicted, "observed": obs, "status": "correct" if obs == predicted else "incorrect",
            "base": base, "new": new, "delta": delta, "tolerance": tol}


# ------------------------------------------------------------------------------------------------------------------ helpers
def _r(v, nd=4):
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            return None
        if v == 0.0:
            return 0.0
        return float(f"{v:.{nd}g}")
    return v


def _flat(d, prefix: str, out: dict) -> None:
    for k, v in (d or {}).items():
        p = f"{prefix}.{k}"
        if isinstance(v, dict):
            _flat(v, p, out)
        elif isinstance(v, bool):
            continue
        elif isinstance(v, (int, float)) and math.isfinite(float(v)):
            out[p] = v


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _text(v, where: str, errs: list) -> None:
    if not isinstance(v, str) or not v.strip():
        errs.append(f"{where}: must be a non-empty string")
    elif len(v) > TEXT_MAX:
        errs.append(f"{where}: longer than {TEXT_MAX} characters")


def _unit(v, where: str, errs: list) -> None:
    if not _num(v) or not 0.0 <= float(v) <= 1.0:
        errs.append(f"{where}: must be a number in [0, 1]")


# ------------------------------------------------------------------------------------------------------------------ system prompt
def build_system_prompt(mode: str = "iterative", order_seed: int | None = None, *, max_steps: int = MAX_STEPS,
                        with_memory: bool = False, counterfactuals=None, tools=None) -> str:
    """Deterministic for (mode, order_seed, memory flag). Neutral: describes instruments, costs, quantities, scoring and rules; never says
    which counterfactual, tool or category tends to be right."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    cfs = counterfactuals if counterfactuals is not None else eng_tools.COUNTERFACTUALS
    tls = tools if tools is not None else fb.TOOLS
    cf_lines = []
    for cid in dr._order(list(cfs), order_seed):
        ch = "; ".join(f"{c['param']} {c['op']} {c['value']:g}" for c in cfs[cid])
        cf_lines.append(f"- {cid}: {ch}")
    tool_lines = []
    for t in dr._order(list(tls), order_seed):
        dims = fb.tool_dims(t) if t in fb.TOOLS else {"ctrl_params": [], "body_params": []}
        names = list(dims["ctrl_params"]) + list(dims["body_params"])
        tool_lines.append(f"- {t}: {TOOL_NOTES.get(t, 'a repair tool')}; searched parameters: {', '.join(names)}")
    cat_lines = [f"- {c}: {CATEGORIES[c]}" for c in dr._order([c for c in CATEGORIES if c != "unresolved"], order_seed)]
    cat_lines.append("- unresolved: " + CATEGORIES["unresolved"])
    q_lines = ", ".join(dr._order(QUANTITIES, order_seed))
    head = ("You are a causal engineering scientist. A bipedal robot simulated in MuJoCo, which is known to have walked well in some "
            "earlier configuration, now fails to walk. Your job: find out WHY it fails, by experiment, then direct a repair that is "
            "checked by an independent verification you cannot see. The GOAL is a design that genuinely walks in that hidden "
            "verification: a correct diagnosis alone repairs nothing, and concluding before any repair has improved the robot submits "
            "the unchanged, failing robot.")
    if mode == "one_shot":
        head += (" In this session you answer ONCE, from the initial observation only: you receive no experimental feedback. Give your "
                 "hypotheses and up to two repairs.")
    body = [head, "",
            "INSTRUMENTS AND COSTS (one shared rollout budget; every instrument call is charged before it runs):",
            "- observation: the initial physics observation of the robot (already done; its cost is spent). Rollouts are 10 s simulated "
            "walks on a fixed set of observation seeds with random initial perturbations and floor friction variation.",
            "- counterfactual: apply ONE catalogue change to the CURRENT BEST design and re-observe it on the SAME observation seeds. Cost "
            "n_obs rollouts (2 x n_obs if the current best design has not yet been observed, because it is observed first). You get the "
            "measured change of every summary quantity. Catalogue (an entry whose change would leave the allowed parameter bounds is not "
            "offered):", *cf_lines,
            "- repair: a CMA-ES search over the dimensions of ONE tool, starting from the current best design, scored on training "
            "seeds. Cost = the budget you grant it = floor(budget_share x remaining rollouts); it must reach the tool's minimum budget "
            "(shown in each message) or it is refused. A repair that improves the training result (more walking seeds, then more "
            "surviving seeds, then fitness) becomes the new current best design. A repair action may contain one or two repairs, run in "
            "order; their budget_shares are fractions of the rollouts remaining at that step and must sum to at most 1. Tools:", *tool_lines,
            "- conclude: stop. Available once at least one repair has been attempted (or when no repair is affordable any more). The "
            "design submitted is always the best training design found so far (\"best\").", "",
            "Experiments are expensive: every rollout spent on experiments is not available for repair. Verification of the submitted "
            "design is independent, uses different seeds and is hidden from you; training walking counts can overstate it.", "",
            "PHYSICS QUANTITIES. Sign conventions: pitch and pitch_rate are positive for forward lean; angmom_norm is positive for forward "
            "rotation; com_ahead_of_cop_over_L is positive when the centre of mass is ahead of the centre of pressure; "
            "capture_margin_over_L is positive when the capture point lies inside the support interval and negative outside; "
            "cp_ahead_of_front_edge_over_L is positive when the capture point is beyond the front (toe) edge. Quantities with the prefix "
            "pre_fall. are averages over the 0.5 s before the fall and are None for seeds that did not fall. A healthy walker's capture "
            "point often lies ahead of its support interval during normal stepping, so trends, pre-fall values and changes against the "
            "robot's own baseline are more informative than absolute levels. The keys of the observation are documented in each message.", "",
            "HYPOTHESES. Keep a ledger. Each hypothesis has a mechanism in words, a causal chain (how the mechanism produces the "
            "observed symptoms), a category, cited evidence paths and a status: "
            "open, supported, refuted or unresolved. Several subsystems can sometimes compensate for one fault, and one symptom can have "
            "several causes, so a repair that works does not by itself identify the cause. A hypothesis must make falsifiable predictions; "
            "revise its status when the measurements contradict them (cite the experiment ids). A refuted hypothesis cannot be "
            "re-opened; propose a new one instead. Confidence values you give are recorded but never used by any decision rule. "
            "Evidence paths (the response schema lists every valid one) are named like this: robot.body.<parameter>, "
            "robot.controller.<parameter>, robot.features.<feature>, reference.features.<feature>, observation.median.<key>, "
            "observation.pre_fall.<key> (the key without its pre_fall. prefix), observation.n_walking, observation.n_fell, "
            "experiments.<E#>.delta.<quantity> (measured change of a quantity in counterfactual E#), experiments.<E#>.n_walking, "
            "experiments.<E#>.n_fell, repairs.<R#>.budget, repairs.<R#>.start_walking, repairs.<R#>.train_walking, "
            "repairs.<R#>.train_fitness. Only values that exist are citable.", "",
            "PREDICTIONS. Before each counterfactual you register, per hypothesis, the direction (increase, decrease, no_change) "
            "of named quantities. Quantities you may predict: " + q_lines + ". They are logged before the experiment runs and scored "
            "afterwards: the observed direction is the sign of the measured change beyond a tolerance. " + TOLERANCE_DOCS + " "
            "Predicting a quantity that is undefined (None) in the baseline or the intervention is not scored. For a repair you predict "
            "the number of training seeds walked afterwards.", "",
            "DIAGNOSIS CATEGORIES (physical mechanisms; use \"unresolved\" if the evidence does not decide):", *cat_lines, "",
            "You may conclude at any time, including immediately if you judge that no further experiment is worth its cost. A repair "
            "should follow evidence. Do not assume any particular intervention or tool will work; the evidence decides.", ""]
    if with_memory:
        body += ["MEMORY. Some messages list retrieved memory items (earlier episodes or mechanism cards, each with an id). They are "
                 "hearsay from other robots, not facts about this robot. In your first reply assess EVERY retrieved item: applies, "
                 "needs_adaptation, test_first (verify with an experiment before relying on it) or does_not_apply, with a reason. You "
                 "may revise an assessment later.", ""]
    if mode == "iterative":
        body += [f"PROTOCOL. One model call per step, at most {max_steps} steps. Each reply carries exactly ONE action (counterfactual, "
                 "repair or conclude) in the field of that name (a list with one element; the other action lists empty), plus optional "
                 "new_hypotheses and status_updates. Reply with a single JSON object that follows the response schema; no prose."]
    else:
        body += ["PROTOCOL. A single reply: JSON object following the response schema, no prose. The repairs you list are run in order "
                 "from the current best design; their budget shares are fractions of the rollouts remaining at your decision and must sum "
                 "to at most 1."]
    return "\n".join(body)


# ------------------------------------------------------------------------------------------------------------------ schemas
def _hyp_schema(new_ids, paths) -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": ["id", "mechanism", "causal_chain", "category", "evidence", "confidence"],
            "properties": {"id": {"type": "string", "enum": list(new_ids)}, "mechanism": {"type": "string"},
                           "causal_chain": {"type": "string"}, "category": {"type": "string", "enum": list(CATEGORIES)},
                           "evidence": {"type": "array", "items": {"type": "string", "enum": list(paths)}},
                           "confidence": {"type": "number"}}}


def _status_schema(existing, exp_ids) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["id", "status", "confidence", "reason", "experiments"],
            "properties": {"id": {"type": "string", "enum": list(existing) or [NO_ID]},
                           "status": {"type": "string", "enum": list(STATUSES)}, "confidence": {"type": "number"},
                           "reason": {"type": "string"},
                           "experiments": {"type": "array", "items": {"type": "string", "enum": list(exp_ids)}}}}


def _memory_schema(mem_ids) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["item", "verdict", "reason"],
            "properties": {"item": {"type": "string", "enum": list(mem_ids)},
                           "verdict": {"type": "string", "enum": list(MEMORY_VERDICTS)}, "reason": {"type": "string"}}}


def step_schema(*, paths, new_ids, existing, all_hyp, exp_ids, cf_ids, tools, quantities, actions, mem_ids=None) -> dict:
    pred = {"type": "object", "additionalProperties": False, "required": ["hypothesis", "quantity", "direction"],
            "properties": {"hypothesis": {"type": "string", "enum": list(all_hyp) or [NO_ID]},
                           "quantity": {"type": "string", "enum": list(quantities)},
                           "direction": {"type": "string", "enum": list(DIRECTIONS)}}}
    cf = {"type": "object", "additionalProperties": False, "required": ["change", "purpose", "predictions"],
          "properties": {"change": {"type": "string", "enum": list(cf_ids) or ["(none available)"]}, "purpose": {"type": "string"},
                         "predictions": {"type": "array", "items": pred}}}
    rep = {"type": "object", "additionalProperties": False,
           "required": ["tool", "budget_share", "hypothesis", "predicted_n_walking"],
           "properties": {"tool": {"type": "string", "enum": list(tools)}, "budget_share": {"type": "number"},
                          "hypothesis": {"type": "string", "enum": list(all_hyp) or [NO_ID]}, "predicted_n_walking": {"type": "integer"}}}
    con = {"type": "object", "additionalProperties": False, "required": ["diagnosis_category", "explanation", "confidence", "submit"],
           "properties": {"diagnosis_category": {"type": "string", "enum": list(CATEGORIES)}, "explanation": {"type": "string"},
                          "confidence": {"type": "number"}, "submit": {"type": "string", "enum": ["best"]}}}
    props = {"action": {"type": "string", "enum": list(actions)},
             "new_hypotheses": {"type": "array", "items": _hyp_schema(new_ids, paths)},
             "status_updates": {"type": "array", "items": _status_schema(existing, exp_ids)}}
    if mem_ids is not None:
        props["memory_assessments"] = {"type": "array", "items": _memory_schema(mem_ids)}
    props.update(counterfactual={"type": "array", "items": cf}, repair={"type": "array", "items": rep},
                 conclude={"type": "array", "items": con})
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def one_shot_schema(*, paths, new_ids, tools, mem_ids=None) -> dict:
    rep = {"type": "object", "additionalProperties": False,
           "required": ["tool", "budget_share", "hypothesis", "predicted_n_walking"],
           "properties": {"tool": {"type": "string", "enum": list(tools)}, "budget_share": {"type": "number"},
                          "hypothesis": {"type": "string", "enum": list(new_ids)}, "predicted_n_walking": {"type": "integer"}}}
    props = {"hypotheses": {"type": "array", "items": _hyp_schema(new_ids, paths)},
             "repairs": {"type": "array", "items": rep},
             "diagnosis_category": {"type": "string", "enum": list(CATEGORIES)}, "explanation": {"type": "string"},
             "confidence": {"type": "number"}}
    if mem_ids is not None:
        props["memory_assessments"] = {"type": "array", "items": _memory_schema(mem_ids)}
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


# ------------------------------------------------------------------------------------------------------------------ validators
def _validate_new_hyps(items, new_ids, paths, where, errs) -> list[str]:
    ids = []
    if not isinstance(items, list):
        errs.append(f"{where}: must be a list")
        return ids
    if len(items) > MAX_NEW_HYPOTHESES:
        errs.append(f"{where}: at most {MAX_NEW_HYPOTHESES} (got {len(items)})")
    for i, h in enumerate(items):
        w = f"{where}[{i}]"
        if not dr._exact(h, {"id", "mechanism", "causal_chain", "category", "evidence", "confidence"}, w, errs):
            continue
        if h["id"] not in new_ids:
            errs.append(f"{w}: id {h['id']!r} must be one of {list(new_ids)}")
        elif h["id"] in ids:
            errs.append(f"{w}: duplicate id {h['id']!r}")
        else:
            ids.append(h["id"])
        _text(h["mechanism"], f"{w}.mechanism", errs)
        _text(h["causal_chain"], f"{w}.causal_chain", errs)
        if h["category"] not in CATEGORIES:
            errs.append(f"{w}.category: {h['category']!r} is not a category")
        dr._cites(h["evidence"], f"{w}.evidence", paths, MAX_CITATIONS, errs)
        _unit(h["confidence"], f"{w}.confidence", errs)
    return ids


def _validate_memory(items, mem_ids, first: bool, errs) -> None:
    if not isinstance(items, list):
        errs.append("memory_assessments: must be a list")
        return
    seen = []
    for i, m in enumerate(items):
        w = f"memory_assessments[{i}]"
        if not dr._exact(m, {"item", "verdict", "reason"}, w, errs):
            continue
        if m["item"] not in mem_ids:
            errs.append(f"{w}: item {m['item']!r} is not a retrieved item {list(mem_ids)}")
        elif m["item"] in seen:
            errs.append(f"{w}: duplicate item {m['item']!r}")
        else:
            seen.append(m["item"])
        if m["verdict"] not in MEMORY_VERDICTS:
            errs.append(f"{w}.verdict: must be one of {list(MEMORY_VERDICTS)}")
        _text(m["reason"], f"{w}.reason", errs)
    if first and set(seen) != set(mem_ids):
        errs.append(f"memory_assessments: assess every retrieved item exactly once; missing {sorted(set(mem_ids) - set(seen))}")


def validate_step(reply, ctx: dict) -> list[str]:
    """Errors (empty = valid). ctx: new_ids, hypotheses {id: status}, exp_ids, cf_available (ids affordable and not yet run on the current
    design) with cf_cost, tools, tool_min {tool: min budget}, remaining, n_train, paths, actions, mem_ids (or None), first_step."""
    errs: list[str] = []
    required = {"action", "new_hypotheses", "status_updates", "counterfactual", "repair", "conclude"}
    if ctx.get("mem_ids") is not None:
        required.add("memory_assessments")
    if not dr._exact(reply, required, "reply", errs):
        return errs
    action = reply["action"]
    if action not in ctx["actions"]:
        errs.append(f"action: {action!r} is not allowed now; allowed: {list(ctx['actions'])}")
    for a in ACTIONS:
        v = reply[a]
        if not isinstance(v, list):
            errs.append(f"{a}: must be a list")
        elif a == action and not (len(v) == 1 or (a in ("repair", "counterfactual") and len(v) == 2)):
            errs.append(f"{a}: the chosen action needs exactly one element" + (" (repair and counterfactual: one or two, run in order)"
                                                                              if a in ("repair", "counterfactual") else ""))
        elif a != action and v:
            errs.append(f"{a}: must be empty when the action is {action!r}")
    hyp_status = dict(ctx["hypotheses"])
    new_ids = _validate_new_hyps(reply["new_hypotheses"], ctx["new_ids"], ctx["paths"], "new_hypotheses", errs)
    if ctx.get("first_step") and not new_ids and action != "conclude":
        errs.append("new_hypotheses: state at least one hypothesis in your first reply")
    # status updates
    su = reply["status_updates"]
    updated: dict[str, str] = {}
    if not isinstance(su, list):
        errs.append("status_updates: must be a list")
        su = []
    for i, u in enumerate(su):
        w = f"status_updates[{i}]"
        if not dr._exact(u, {"id", "status", "confidence", "reason", "experiments"}, w, errs):
            continue
        if u["id"] not in hyp_status:
            errs.append(f"{w}: id {u['id']!r} is not an existing hypothesis {list(hyp_status)}")
        elif hyp_status[u["id"]] == "refuted":
            errs.append(f"{w}: hypothesis {u['id']!r} is refuted and cannot be changed; propose a new hypothesis")
        elif u["id"] in updated:
            errs.append(f"{w}: duplicate id {u['id']!r}")
        else:
            updated[u["id"]] = u["status"]
        if u["status"] not in STATUSES:
            errs.append(f"{w}.status: must be one of {list(STATUSES)}")
        _unit(u["confidence"], f"{w}.confidence", errs)
        _text(u["reason"], f"{w}.reason", errs)
        ex = u["experiments"]
        if not isinstance(ex, list) or not ex or any(e not in ctx["exp_ids"] for e in ex):
            errs.append(f"{w}.experiments: cite 1+ experiment ids from {list(ctx['exp_ids'])}")
    usable = {h for h, s in hyp_status.items() if s != "refuted" and updated.get(h) != "refuted"} | set(new_ids)
    if ctx.get("mem_ids") is not None:
        _validate_memory(reply["memory_assessments"], ctx["mem_ids"], bool(ctx.get("first_step")), errs)
    if action == "counterfactual" and isinstance(reply["counterfactual"], list) and len(reply["counterfactual"]) in (1, 2):
        cfs = reply["counterfactual"]
        if len(cfs) == 2 and isinstance(cfs[0], dict) and isinstance(cfs[1], dict) and cfs[0].get("change") == cfs[1].get("change"):
            errs.append("counterfactual: the two counterfactuals must be different changes")
        if len(cfs) == 2 and ctx["remaining"] < ctx["cf_cost"] + ctx.get("cf_cost_next", ctx["cf_cost"]):
            errs.append(f"counterfactual: two counterfactuals cost {ctx['cf_cost'] + ctx.get('cf_cost_next', ctx['cf_cost'])} rollouts; "
                        f"only {ctx['remaining']} remain")
        for k, c in enumerate(cfs):
            w0 = f"counterfactual[{k}]"
            if not dr._exact(c, {"change", "purpose", "predictions"}, w0, errs):
                continue
            if c["change"] not in ctx["cf_available"]:
                errs.append(f"{w0}.change: {c['change']!r} is not available now; available (affordable, not yet run on "
                            f"the current design): {list(ctx['cf_available'])}")
            _text(c["purpose"], f"{w0}.purpose", errs)
            ps = c["predictions"]
            if not isinstance(ps, list) or not 1 <= len(ps) <= MAX_PREDICTIONS:
                errs.append(f"{w0}.predictions: give 1-{MAX_PREDICTIONS} predictions")
                continue
            seen = set()
            for j, p in enumerate(ps):
                w = f"{w0}.predictions[{j}]"
                if not dr._exact(p, {"hypothesis", "quantity", "direction"}, w, errs):
                    continue
                if p["hypothesis"] not in usable:
                    errs.append(f"{w}.hypothesis: {p['hypothesis']!r} is not an open/supported/unresolved hypothesis {sorted(usable)}"
                                + (" - declare it in new_hypotheses in the same reply" if not usable else ""))
                if p["quantity"] not in QUANTITIES:
                    errs.append(f"{w}.quantity: {p['quantity']!r} is not a predictable quantity")
                if p["direction"] not in DIRECTIONS:
                    errs.append(f"{w}.direction: must be one of {list(DIRECTIONS)}")
                if (p["hypothesis"], p["quantity"]) in seen:
                    errs.append(f"{w}: duplicate (hypothesis, quantity)")
                seen.add((p["hypothesis"], p["quantity"]))
    if action == "repair" and isinstance(reply["repair"], list) and len(reply["repair"]) in (1, 2):
        for k, r in enumerate(reply["repair"]):
            errs += _validate_repair(r, f"repair[{k}]", ctx, usable)
        shares = [r.get("budget_share") for r in reply["repair"] if isinstance(r, dict)]
        if len(shares) == 2 and all(isinstance(x, (int, float)) for x in shares) and sum(shares) > 1 + 1e-9:
            errs.append("repair: the budget_shares of the two repairs must sum to at most 1 (both are fractions of the rollouts "
                        "remaining at this step)")
    if action == "conclude" and isinstance(reply["conclude"], list) and len(reply["conclude"]) == 1:
        c = reply["conclude"][0]
        if dr._exact(c, {"diagnosis_category", "explanation", "confidence", "submit"}, "conclude[0]", errs):
            if c["diagnosis_category"] not in CATEGORIES:
                errs.append(f"conclude[0].diagnosis_category: {c['diagnosis_category']!r} is not a category")
            _text(c["explanation"], "conclude[0].explanation", errs)
            _unit(c["confidence"], "conclude[0].confidence", errs)
            if c["submit"] != "best":
                errs.append("conclude[0].submit: must be 'best'")
    return errs


REPAIR_CALLS_PER_STEP = 2   # dev change 2026-10-17 (live smoke): the step schema is demanding; two repair calls per step
_PLACEHOLDER_IDS = {"", "none", "(none)", "null", "n/a", "-"}


def _drop_placeholders(reply):
    """Drop obviously empty placeholder entries the model sometimes emits (e.g. a status update with id "(none)"); recorded as a
    warning. Nothing else is changed: real content is never repaired or invented."""
    warn = []
    if isinstance(reply, dict) and isinstance(reply.get("status_updates"), list):
        keep = []
        for u in reply["status_updates"]:
            if isinstance(u, dict) and str(u.get("id", "")).strip().lower() in _PLACEHOLDER_IDS:
                warn.append(f"dropped placeholder status update {u.get('id')!r}")
            else:
                keep.append(u)
        reply = {**reply, "status_updates": keep}
    return reply, warn


def repair_budget(share, remaining: int) -> int:
    return int(math.floor(float(share) * int(remaining) + 1e-9))


def _validate_repair(r, where, ctx, usable) -> list[str]:
    errs: list[str] = []
    if not dr._exact(r, {"tool", "budget_share", "hypothesis", "predicted_n_walking"}, where, errs):
        return errs
    if r["tool"] not in ctx["tools"]:
        errs.append(f"{where}.tool: {r['tool']!r} is not a tool {list(ctx['tools'])}")
    sh = r["budget_share"]
    if not _num(sh) or not 0.0 < float(sh) <= 1.0:
        errs.append(f"{where}.budget_share: must be a number in (0, 1]")
    elif r["tool"] in ctx["tool_min"]:
        b = repair_budget(sh, ctx["remaining"])
        need = ctx["tool_min"][r["tool"]]
        if b < need:
            errs.append(f"{where}.budget_share: floor({sh} x {ctx['remaining']}) = {b} rollouts is below the minimum {need} of tool "
                        f"{r['tool']}; use a share of at least {need / max(ctx['remaining'], 1):.3f}")
    if r["hypothesis"] not in usable:
        errs.append(f"{where}.hypothesis: {r['hypothesis']!r} is not a usable hypothesis {sorted(usable)}")
    p = r["predicted_n_walking"]
    if isinstance(p, bool) or not isinstance(p, int) or not 0 <= p <= ctx["n_train"]:
        errs.append(f"{where}.predicted_n_walking: integer in [0, {ctx['n_train']}] (number of training seeds)")
    return errs


def validate_one_shot(reply, ctx: dict) -> list[str]:
    errs: list[str] = []
    required = {"hypotheses", "repairs", "diagnosis_category", "explanation", "confidence"}
    if ctx.get("mem_ids") is not None:
        required.add("memory_assessments")
    if not dr._exact(reply, required, "reply", errs):
        return errs
    ids = _validate_new_hyps(reply["hypotheses"], ctx["new_ids"], ctx["paths"], "hypotheses", errs)
    if not ids:
        errs.append("hypotheses: state at least one hypothesis")
    if reply["diagnosis_category"] not in CATEGORIES:
        errs.append(f"diagnosis_category: {reply['diagnosis_category']!r} is not a category")
    _text(reply["explanation"], "explanation", errs)
    _unit(reply["confidence"], "confidence", errs)
    if ctx.get("mem_ids") is not None:
        _validate_memory(reply["memory_assessments"], ctx["mem_ids"], True, errs)
    reps = reply["repairs"]
    if not isinstance(reps, list) or not 1 <= len(reps) <= 2:
        errs.append("repairs: give 1-2 repairs")
        return errs
    total = 0.0
    for i, r in enumerate(reps):
        errs += _validate_repair(r, f"repairs[{i}]", ctx, set(ids))
        if isinstance(r, dict) and _num(r.get("budget_share")):
            total += float(r["budget_share"])
    if total > 1.0 + 1e-9:
        errs.append(f"repairs: budget shares sum to {total:.4g} > 1")
    return errs


# ------------------------------------------------------------------------------------------------------------------ the scientist
class Scientist(dr.NemotronDirector):
    """One scientist = ONE investigation (a fresh id, ledger lines and call list per instance; use a new Scientist per robot).

    `source`: "live" or "scripted" (default: scripted iff `fixture` or `transport` is given). A scripted / injected-transport run is
    labelled SCRIPTED_MOCK and never counted as LIVE. `order_seed` shuffles the listing order of catalogues and categories (recorded).
    `event_hook(event_dict)` (optional) receives every ordered event of the record as it happens (used by tests to assert that predictions
    are registered before the bench runs)."""

    def __init__(self, mode: str = "iterative", *, source: str | None = None, profile: str = "default",
                 ledger: InferenceLedger | None = None, investigation_id: str | None = None, transport=None,
                 fixture: Sequence | None = None, max_steps: int = MAX_STEPS, max_requests: int = MAX_REQUESTS,
                 max_total_tokens: int = 400_000, config=None, order_seed: int | None = None,
                 reference_features: dict | None = None, show_controller: bool = True, event_hook=None,
                 min_budget_fn=None, require_repair_before_conclude: bool = True, repair_calls: int = REPAIR_CALLS_PER_STEP):
        self.require_repair_before_conclude = bool(require_repair_before_conclude)
        self.repair_calls = int(repair_calls)
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        src = source or ("scripted" if fixture is not None or transport is not None else "live")
        if src == "scripted" and ledger is None:
            import tempfile
            from pathlib import Path
            ledger = InferenceLedger(Path(tempfile.mkdtemp(prefix="cf_scientist_")) / "scripted_inference_ledger.jsonl",
                                     prices={SCRIPTED_MODEL: (0.0, 0.0)},
                                     caps=Caps(inv_max_requests=max_requests, inv_max_tokens=max_total_tokens))
        super().__init__(mode=src, profile=profile, ledger=ledger, investigation_id=investigation_id or new_investigation_id(),
                         transport=transport, fixture=fixture, max_requests=max_requests, max_total_tokens=max_total_tokens,
                         config=config, evidence_mode="full", prompt_version="v2", order_seed=order_seed)
        self.sci_mode = mode
        self.max_steps = int(max_steps)
        self.show_controller = bool(show_controller)
        self._reference = reference_features
        self._hook = event_hook
        self._min_budget = min_budget_fn or eng_tools.min_repair_budget
        self.system = None          # built in investigate() (needs to know whether memory is used)
        self._used = False
        self.events: list[dict] = []
        self.steps: list[dict] = []
        self.ledger_h: dict[str, dict] = {}        # hypothesis ledger
        self.experiments: list[dict] = []          # experiment ledger (counterfactuals, repairs, re-observations)
        self.memory_items: list[dict] = []
        self.memory_assessments: dict[str, dict] = {}
        self.memory_log: list[dict] = []
        self.final: dict = {}
        self.submitted: dict | None = None
        self._obs: dict[int, dict] = {}
        self._seq = 0

    # -------------------------------------------------------------------------------------------- events
    def _event(self, type_: str, step: int, **kw) -> dict:
        self._seq += 1
        ev = {"seq": self._seq, "type": type_, "step": step, **kw}
        self.events.append(ev)
        if self._hook:
            self._hook(copy.deepcopy(ev))
        return ev

    # -------------------------------------------------------------------------------------------- evidence
    def _static_evidence(self, bench, view) -> dict:
        rb = view["robot"]
        body = {k: v for k, v in rb["body"].items() if _num(v)}
        ev: dict = {"robot": {"body": body}}
        if self.show_controller:
            from .walk_opt import ALL_NAMES
            ev["robot"]["controller"] = {n: v for n, v in zip(ALL_NAMES, rb["vector"])}
        feats = view.get("features")
        if feats is None:
            try:
                from . import creature_gen as cg
                feats = cg.features(rb["body"])
            except Exception:       # noqa: BLE001 - features are descriptive context only
                feats = {}
        ev["robot"]["features"] = {k: v for k, v in (feats or {}).items() if _num(v)}
        ref = self._reference
        if ref is None:
            try:
                ref = dr.reference_features()
            except Exception:       # noqa: BLE001
                ref = {}
        ev["reference"] = {"features": {k: v for k, v in (ref or {}).items() if _num(v)}}
        return ev

    def _obs_evidence(self, obs: dict) -> dict:
        med = {k: v for k, v in (obs.get("median") or {}).items() if _num(v)}
        pf = {k: v for k, v in (obs.get("pre_fall_median") or {}).items() if _num(v)}
        return {"median": med, "pre_fall": pf, "n_walking": obs.get("n_walking"), "n_fell": obs.get("n_fell")}

    def _evidence(self, view=None, **_) -> dict:      # signature differs from the base class on purpose
        ev = copy.deepcopy(self._ev_static)
        ev["observation"] = self._obs_evidence(self._obs0)
        for e in self.experiments:
            if e["kind"] == "counterfactual" and e.get("status") == "ok":
                d = {"n_walking": e["outcome"]["n_walking"], "n_fell": e["outcome"]["n_fell"],
                     "delta": {q: x["delta"] for q, x in e["outcome"]["quantities"].items() if x["delta"] is not None}}
                ev.setdefault("experiments", {})[e["id"]] = d
            elif e["kind"] == "repair" and e.get("status") == "ok":
                ev.setdefault("repairs", {})[e["id"]] = {"budget": e["budget"], "start_walking": e["start_walking"],
                                                          "train_walking": e["train_walking"], "train_fitness": e["train_fitness"]}
        return ev

    def _paths(self, ev: dict) -> list[str]:
        out: dict = {}
        _flat(ev, "", out)
        return [p[1:] for p in out]

    # -------------------------------------------------------------------------------------------- user message
    def _doc_lines(self, obs: dict) -> list[str]:
        lines = []
        keys = [k for k, v in (obs.get("median") or {}).items() if _num(v)]
        for k in keys:
            lines.append(f"  {k} = {_r(obs['median'][k])} : {PROBE_DOCS.get(k, '')}")
        for k, v in (obs.get("pre_fall_median") or {}).items():
            if _num(v):
                lines.append(f"  pre_fall.{k} = {_r(v)} : {PROBE_DOCS.get('pre_fall.' + k, '')}")
        return lines

    def _experiment_lines(self) -> list[str]:
        out = []
        for e in self.experiments:
            if e["kind"] == "observe":
                out.append(f"{e['id']} [step {e['step']}] re-observation of design {e['design_index']} (cost {e['cost']})")
            elif e["kind"] == "counterfactual":
                head = f"{e['id']} [step {e['step']}] counterfactual {e['change']} on design {e['design_index']}; purpose: {e['purpose']}; cost {e['cost']}"
                if e.get("status") != "ok":
                    out.append(head + f"; REFUSED: {e.get('refused')}")
                    continue
                o = e["outcome"]
                out.append(head + f"; n_walking {o['n_walking_base']} -> {o['n_walking']}, n_fell {o['n_fell_base']} -> {o['n_fell']}")
                moved = [f"{q}: {_r(x['base'])} -> {_r(x['new'])}" for q, x in o["quantities"].items()
                         if x["delta"] is not None and abs(x["delta"]) > x["tolerance"] and q not in ("n_walking", "n_fell")]
                out.append("    quantities that changed beyond tolerance: " + ("; ".join(moved[:30]) if moved else "none"))
                for p in e["scoring"]:
                    st = p["status"]
                    out.append(f"    prediction ({p['hypothesis']}) {p['quantity']} {p['predicted']}: observed "
                               f"{p['observed'] if st != 'unscored' else 'undefined'} -> {st.upper()}")
            else:
                head = (f"{e['id']} [step {e['step']}] repair {e['tool']} budget {e.get('budget')} for {e['hypothesis']}; predicted "
                        f"n_walking after repair {e['predicted_n_walking']}")
                if e.get("status") != "ok":
                    out.append(head + f"; REFUSED: {e.get('refused')}")
                else:
                    out.append(head + f"; result: train walking {e['start_walking']} -> {e['train_walking']} of {e['n_train']}, "
                                      f"train fitness {_r(e['train_fitness'])}, rollouts used {e['rollouts_used']}, "
                                      f"{'became the current best design' if e['is_current_best'] else 'did not beat the current best'}")
        return out

    def _user(self, step: int, ctx: dict, task: str) -> str:
        bench = ctx["bench"]
        lines = [f"STEP {step} of at most {self.max_steps}. Model requests used so far: {len(self.calls)} of {self.max_requests}.",
                 f"Rollout budget: {ctx['remaining']} remaining of {ctx['total']}; n_obs = {bench.n_obs}, n_train = {bench.n_train}.",
                 f"Current best design: index {ctx['best']['index']} (source {ctx['best']['source']}); observed: "
                 f"{'yes' if ctx['best_observed'] else 'no'}.", "", "ROBOT:"]
        ev = self._ev_static
        lines.append("  body parameters: " + ", ".join(f"{k}={_r(v)}" for k, v in ev["robot"]["body"].items()))
        if "controller" in ev["robot"]:
            lines.append("  controller parameters: " + ", ".join(f"{k}={_r(v)}" for k, v in ev["robot"]["controller"].items()))
        lines.append("  dimensionless features of this body: " + ", ".join(f"{k}={_r(v)}" for k, v in ev["robot"]["features"].items()))
        lines.append("  the REFERENCE body (a healthy design it can be compared with): " +
                     ", ".join(f"{k}={_r(v)}" for k, v in ev["reference"]["features"].items()))
        lines += ["", f"INITIAL OBSERVATION ({INITIAL_OBS}; median over the {bench.n_obs} observation seeds; n_walking="
                      f"{self._obs0.get('n_walking')}, n_fell={self._obs0.get('n_fell')}):", *self._doc_lines(self._obs0)]
        lines += ["", "YOUR HYPOTHESES:"]
        if not self.ledger_h:
            lines.append("  (none yet)")
        for h in self.ledger_h.values():
            lines.append(f"  {h['id']} [{h['status']}, confidence {h['confidence']}] category {h['category']}: {h['mechanism']} | chain: "
                         f"{h['causal_chain']} | cites {', '.join(h['evidence'])}")
        lines += ["", "YOUR EXPERIMENTS AND REPAIRS (predictions were registered before each ran):"]
        el = self._experiment_lines()
        lines += (["  " + x for x in el] if el else ["  (none yet)"])
        ps = self.prediction_summary()
        if ps["n_scored"]:
            lines.append(f"  prediction record so far: {ps['n_correct']} of {ps['n_scored']} scored predictions correct")
        if self.memory_items:
            lines += ["", "RETRIEVED MEMORY ITEMS (hearsay from other robots):"]
            for m in self.memory_items:
                a = self.memory_assessments.get(m["id"])
                lines.append(f"  {m['id']} [{m.get('kind', 'item')}]: {m['text']}" +
                             (f"  (your assessment: {a['verdict']}: {a['reason']})" if a else ""))
        lines += ["", "COSTS NOW:"]
        lines.append(f"  counterfactual: {ctx['cf_cost']} rollouts each; available now: "
                     f"{', '.join(ctx['cf_available']) if ctx['cf_available'] else 'none'}")
        lines.append("  repair minimum budgets (rollouts): " + ", ".join(f"{t}={b}" for t, b in ctx["tool_min"].items()))
        lines += ["", task]
        return "\n".join(lines)

    # -------------------------------------------------------------------------------------------- model call (+ one repair)
    def _ask_step(self, kind: str, step: int, messages: list, schema: dict, name: str, validate) -> dict:
        dec = {"kind": kind, "round": step, "calls": [], "parsed": None, "first_attempt_errors": [], "validation_errors": [],
               "repaired": False, "status": "ok", "returned": []}

        def assess(call: ModelCall):
            try:
                reply = parse_reply(call.content)
            except ValueError as e:
                return None, [str(e)]
            reply, warn = _drop_placeholders(reply)
            if warn:
                dec.setdefault("warnings", []).extend(warn)
            return reply, validate(reply)

        call, idx = self._send(messages, schema, name, f"scientist_{kind}")
        dec["calls"].append(idx)
        if not call.ok:
            dec.update(status="model_failed", validation_errors=[self._clean(call.error or "no content")])
            return dec
        reply, errs = assess(call)
        dec["parsed"] = reply
        attempts = 0
        while errs and attempts < self.repair_calls:
            attempts += 1
            if attempts == 1:
                dec["first_attempt_errors"] = [self._clean(e) for e in errs]
            dec["repaired"] = True
            call2, idx2 = self._send(self._repair_messages(messages, call, errs), schema, name, "scientist_repair")
            dec["calls"].append(idx2)
            if not call2.ok:
                dec.update(status="repair_failed", validation_errors=dec["first_attempt_errors"] + [self._clean(call2.error or "no content")])
                return dec
            call = call2
            reply, errs = assess(call2)
            dec["parsed"] = reply
        if errs:
            dec.update(status="invalid_after_repair" if dec["repaired"] else "invalid", validation_errors=[self._clean(e) for e in errs])
            return dec
        dec["reply"] = reply
        return dec

    # -------------------------------------------------------------------------------------------- ledger updates
    def _apply_hypotheses(self, step: int, new: list, updates: list) -> list[dict]:
        trans = []
        for h in new:
            self.ledger_h[h["id"]] = {"id": h["id"], "mechanism": h["mechanism"], "causal_chain": h["causal_chain"],
                                      "category": h["category"], "evidence": list(h["evidence"]), "status": "open",
                                      "confidence": float(h["confidence"]), "created_step": step,
                                      "history": [{"step": step, "status": "open", "confidence": float(h["confidence"]), "reason": "created",
                                                   "experiments": []}]}
            trans.append({"id": h["id"], "from": None, "to": "open", "reason": "created", "experiments": []})
        for u in updates:
            h = self.ledger_h[u["id"]]
            acc = self._prediction_support(u["id"], u["experiments"])
            trans.append({"id": u["id"], "from": h["status"], "to": u["status"], "reason": u["reason"],
                          "experiments": list(u["experiments"]), "cited_predictions": acc})
            h["history"].append({"step": step, "status": u["status"], "confidence": float(u["confidence"]), "reason": u["reason"],
                                 "experiments": list(u["experiments"]), "cited_predictions": acc})
            h["status"], h["confidence"] = u["status"], float(u["confidence"])
        return trans

    def _prediction_support(self, hyp: str, exp_ids: list) -> dict:
        """How the hypothesis' own scored predictions fared in the cited experiments (descriptive; never used to decide)."""
        n = c = 0
        for e in self.experiments:
            if e["id"] in exp_ids and e["kind"] == "counterfactual":
                for p in e.get("scoring", []):
                    if p["hypothesis"] == hyp and p["status"] != "unscored":
                        n += 1
                        c += p["status"] == "correct"
        return {"n_scored": n, "n_correct": c}

    def _apply_memory(self, step: int, items: list) -> None:
        for m in items:
            rec = {"item": m["item"], "verdict": m["verdict"], "reason": m["reason"], "step": step}
            self.memory_assessments[m["item"]] = rec
            self.memory_log.append(dict(rec))

    def prediction_summary(self) -> dict:
        n = c = 0
        by_dir: dict = {}
        obs_dirs: dict = {}
        by_q: dict = {}
        for e in self.experiments:
            for p in e.get("scoring", []) if e["kind"] == "counterfactual" else []:
                if p["status"] == "unscored":
                    continue
                n += 1
                c += p["status"] == "correct"
                d = by_dir.setdefault(p["predicted"], {"n": 0, "correct": 0})
                d["n"] += 1
                d["correct"] += p["status"] == "correct"
                obs_dirs[p["observed"]] = obs_dirs.get(p["observed"], 0) + 1
                q = by_q.setdefault(p["quantity"], {"n": 0, "correct": 0})
                q["n"] += 1
                q["correct"] += p["status"] == "correct"
        majority = max(obs_dirs.values()) / n if n else None
        n_rep = [e for e in self.experiments if e["kind"] == "repair" and e.get("status") == "ok"]
        rep_hits = sum(1 for e in n_rep if abs(e["predicted_n_walking"] - e["train_walking"]) <= 1)
        return {"n_scored": n, "n_correct": c, "accuracy": (c / n) if n else None, "chance_three_way": 1 / 3,
                "majority_observed_baseline": majority, "by_predicted_direction": by_dir, "observed_directions": obs_dirs,
                "by_quantity": by_q, "tolerance": TOLERANCE_DOCS,
                "repair_predictions": {"n": len(n_rep), "within_one": rep_hits,
                                       "abs_errors": [abs(e["predicted_n_walking"] - e["train_walking"]) for e in n_rep]}}

    # -------------------------------------------------------------------------------------------- bench actions
    def _available_cfs(self, bench, best: dict) -> list[str]:
        out = []
        done = {e["change"] for e in self.experiments if e["kind"] == "counterfactual" and e.get("design_index") == best["index"]
                and e.get("status") == "ok"}
        for cid, ch in eng_tools.COUNTERFACTUALS.items():
            if cid in done:
                continue
            try:
                fb.apply_changes(best["body"], best["vector"], ch)
            except fb.InvalidInstance:
                continue
            out.append(cid)
        return out

    def _tool_mins(self, bench) -> dict:
        out = {}
        for t in dr._order(list(fb.TOOLS), self.order_seed):
            try:
                out[t] = int(self._min_budget(t, bench.n_train))
            except Exception:       # noqa: BLE001 - a tool without search room is simply not offered
                continue
        return out

    def _do_counterfactual(self, bench, step: int, c: dict, best: dict) -> dict:
        eid = f"E{1 + sum(1 for e in self.experiments if e['kind'] == 'counterfactual')}"
        preds = [dict(p) for p in c["predictions"]]
        reg = self._event("prediction_registered", step, experiment=eid, change=c["change"], predictions=copy.deepcopy(preds))
        before = bench.remaining
        ent = {"id": eid, "kind": "counterfactual", "step": step, "change": c["change"], "purpose": c["purpose"],
               "design_index": best["index"], "predictions": preds, "registered_seq": reg["seq"], "scoring": []}
        if best["index"] not in self._obs:           # observe the current design first (its own ledger line, same total cost)
            oid = f"O{1 + sum(1 for e in self.experiments if e['kind'] == 'observe')}"
            self._event("bench_call", step, call="observe", experiment=oid)
            r = bench.observe()
            if r.get("ok"):
                self._obs[best["index"]] = r["observation"]
                self.experiments.append({"id": oid, "kind": "observe", "step": step, "design_index": best["index"],
                                         "cost": before - bench.remaining})
            else:
                ent.update(status="refused", refused=r.get("refused"), cost=before - bench.remaining, executed_seq=self._seq)
                self.experiments.append(ent)
                return ent
        before_cf = bench.remaining
        ex = self._event("bench_call", step, call="counterfactual", experiment=eid, change=c["change"])
        ent["executed_seq"] = ex["seq"]
        res = bench.counterfactual(c["change"])
        ent["cost"] = (before - bench.remaining)
        if not res.get("ok"):
            ent.update(status="refused", refused=res.get("refused"))
            self.experiments.append(ent)
            return ent
        base, new = self._obs[best["index"]], res["observation"]
        self._obs[res["design_index"]] = new
        quants, scoring = {}, []
        for q in QUANTITIES:
            b, n = quantity_value(base, q), quantity_value(new, q)
            if b is not None and n is not None:
                quants[q] = {"base": b, "new": n, "delta": n - b, "tolerance": tolerance(q, b)}
            else:
                quants[q] = {"base": b, "new": n, "delta": None, "tolerance": None}
        for p in preds:
            s = score_direction(p["quantity"], p["direction"], quantity_value(base, p["quantity"]), quantity_value(new, p["quantity"]))
            s["hypothesis"] = p["hypothesis"]
            scoring.append(s)
        ent.update(status="ok", result_design_index=res["design_index"], changes=res.get("changes"), scoring=scoring,
                   outcome={"n_walking_base": base.get("n_walking"), "n_walking": new.get("n_walking"), "n_fell_base": base.get("n_fell"),
                            "n_fell": new.get("n_fell"), "quantities": quants, "bench_deltas": res.get("deltas_vs_current"),
                            "cost_of_counterfactual_only": before_cf - bench.remaining})
        self.experiments.append(ent)
        return ent

    def _do_repair(self, bench, step: int, r: dict) -> dict:
        return self._do_repair_budget(bench, step, r, repair_budget(r["budget_share"], bench.remaining))

    # -------------------------------------------------------------------------------------------- investigate
    def investigate(self, bench, robot_view: dict, *, memory=None) -> dict:
        """Run the investigation on `bench` (an `eng_tools.Workbench`-compatible object: observe, counterfactual, repair, best_design,
        ledger, remaining, n_obs, n_train, total budget via ledger()) for `robot_view` ({"robot": {"body","vector"}, optional "features"})
        and return the record (JSON-safe; no API key). Raises if called twice."""
        if self._used:
            raise RuntimeError("a Scientist runs one investigation; create a new one")
        self._used = True
        total = int(bench.ledger()["total"])
        before_obs = bench.remaining
        self._ev_static = self._static_evidence(bench, robot_view)
        self._event("bench_call", 0, call="observe", experiment=INITIAL_OBS)
        r0 = bench.observe()
        if not r0.get("ok"):
            self.final = {"diagnosis_category": None, "ended_by": "initial_observation_refused", "detail": r0.get("refused")}
            return self._finish(bench, total)
        self._obs0 = r0["observation"]
        self._obs[r0["design_index"]] = self._obs0
        self.initial_observation_cost = before_obs - bench.remaining
        if memory is not None:
            try:
                got = memory.retrieve(self._obs_evidence(self._obs0), self._ev_static["robot"]["features"])
            except Exception as e:      # noqa: BLE001 - recorded; the arm then runs without items
                got = []
                self.memory_error = self._clean(f"{type(e).__name__}: {e}")
            self.memory_items = [{"id": str(m["id"]), "kind": str(m.get("kind", "item")), "text": str(m["text"])} for m in got]
        with_mem = bool(self.memory_items)
        self.system = build_system_prompt(self.sci_mode, self.order_seed, max_steps=self.max_steps, with_memory=with_mem)
        if self.sci_mode == "one_shot":
            self._one_shot(bench, total)
        else:
            self._loop(bench, total)
        return self._finish(bench, total)

    # ---- iterative loop
    def _ctx(self, bench, step: int) -> dict:
        best = bench.best_design()
        remaining = bench.remaining
        cfs = self._available_cfs(bench, best)
        observed = best["index"] in self._obs
        cost = bench.n_obs * (1 if observed else 2)
        cfs_aff = [c for c in cfs if remaining >= cost]
        mins = self._tool_mins(bench)
        tools_aff = {t: b for t, b in mins.items() if b <= remaining}
        repaired = any(e["kind"] == "repair" for e in self.experiments)
        # Workflow rule (2026-10-17, after the live smoke where the model concluded with a diagnosis at step 1): the deliverable is a
        # repaired design, so `conclude` is offered only once a repair has been attempted, or when no repair is affordable any more.
        # This does not force experiments: a first-step repair is allowed.
        conclude_ok = repaired or not tools_aff or not self.require_repair_before_conclude
        actions = [a for a, ok in (("counterfactual", bool(cfs_aff)), ("repair", bool(tools_aff)), ("conclude", conclude_ok)) if ok]
        if not actions:
            actions = ["conclude"]
        nreq_left = self.max_requests - len(self.calls)
        if step >= self.max_steps or nreq_left <= 2:       # the last step may only conclude (keeps a request for its repair call)
            actions = ["conclude"]
        return {"bench": bench, "best": best, "remaining": remaining, "total": int(bench.ledger()["total"]), "best_observed": observed,
                "cf_available": cfs_aff, "cf_cost": cost, "cf_cost_next": bench.n_obs, "tool_min": mins, "tools": list(mins), "actions": actions,
                "n_train": bench.n_train}

    def _loop(self, bench, total: int) -> None:
        fails = 0
        for step in range(1, self.max_steps + 1):
            if len(self.calls) >= self.max_requests:
                self.final = {"diagnosis_category": None, "ended_by": "request_cap"}
                return
            ctx = self._ctx(bench, step)
            ev = self._evidence()
            paths = self._paths(ev)
            exp_ids = [INITIAL_OBS] + [e["id"] for e in self.experiments if e["kind"] != "observe" and e.get("status") == "ok"]
            n_prev = max([int(h[1:]) for h in self.ledger_h] or [0])
            new_ids = [f"H{n_prev + i}" for i in range(1, MAX_NEW_HYPOTHESES + 1)]
            existing = list(self.ledger_h)
            all_hyp = [h for h in existing if self.ledger_h[h]["status"] != "refuted"] + new_ids
            mem_ids = [m["id"] for m in self.memory_items] if self.memory_items else None
            ctx.update(new_ids=new_ids, hypotheses={h: d["status"] for h, d in self.ledger_h.items()}, exp_ids=exp_ids, paths=set(paths),
                       mem_ids=mem_ids, first_step=(step == 1))
            schema = step_schema(paths=paths, new_ids=new_ids, existing=[h for h in existing if self.ledger_h[h]["status"] != "refuted"],
                                 all_hyp=all_hyp, exp_ids=exp_ids, cf_ids=ctx["cf_available"], tools=ctx["tools"],
                                 quantities=dr._order(QUANTITIES, self.order_seed), actions=ctx["actions"], mem_ids=mem_ids)
            task = ("TASK: choose exactly ONE action: " + ", ".join(ctx["actions"]) + ". Fill only the list of the action you choose "
                    "(one element), leave the other action lists empty, and add new_hypotheses / status_updates as needed.")
            if len(ctx["actions"]) == 1:
                task += " This is the last step: you must conclude."
            if step == 1 and mem_ids:
                task += " Also assess every retrieved memory item in memory_assessments."
            msgs = [{"role": "system", "content": self.system}, {"role": "user", "content": self._user(step, ctx, task)}]
            self._event("model_call", step)
            dec = self._ask_step("step", step, msgs, schema, SCHEMA_STEP, lambda r, c=ctx: validate_step(r, c))
            srec = {"step": step, "user_message": msgs[1]["content"], "status": dec["status"], "calls": dec["calls"],
                    "parsed": copy.deepcopy(dec["parsed"]), "first_attempt_errors": dec["first_attempt_errors"],
                    "validation_errors": dec["validation_errors"], "repaired": dec["repaired"], "allowed_actions": ctx["actions"],
                    "remaining_before": ctx["remaining"]}
            self.steps.append(srec)
            if dec["status"] != "ok":
                fails += 1
                srec["action"] = None
                if fails >= 2:
                    self.final = {"diagnosis_category": None, "ended_by": "consecutive_invalid",
                                  "detail": "two consecutive steps failed; the bench's best design is submitted, nothing substituted"}
                    return
                continue
            fails = 0
            reply = dec["reply"]
            srec["action"] = reply["action"]
            srec["hypothesis_transitions"] = self._apply_hypotheses(step, reply["new_hypotheses"], reply["status_updates"])
            if mem_ids is not None:
                self._apply_memory(step, reply["memory_assessments"])
                srec["memory_assessments"] = copy.deepcopy(reply["memory_assessments"])
            if reply["action"] == "counterfactual":
                ents = [self._do_counterfactual(bench, step, c, ctx["best"]) for c in reply["counterfactual"]]
                srec["experiment"] = ents[-1]["id"]
                srec["experiments"] = [e["id"] for e in ents]
            elif reply["action"] == "repair":
                rem0 = bench.remaining      # both shares are fractions of the rollouts remaining at this step
                ents = []
                for r in reply["repair"]:
                    ents.append(self._do_repair_budget(bench, step, r, repair_budget(r["budget_share"], rem0)))
                srec["experiment"] = ents[-1]["id"]
                srec["experiments"] = [e["id"] for e in ents]
            else:
                c = reply["conclude"][0]
                self.final = {"diagnosis_category": c["diagnosis_category"], "explanation": c["explanation"],
                              "confidence": float(c["confidence"]), "submit": c["submit"], "ended_by": "concluded", "step": step}
                srec["remaining_after"] = bench.remaining
                return
            srec["remaining_after"] = bench.remaining
        self.final = {"diagnosis_category": None, "ended_by": "max_steps"}

    # ---- one-shot
    def _one_shot(self, bench, total: int) -> None:
        ev = self._evidence()
        paths = self._paths(ev)
        new_ids = [f"H{i}" for i in range(1, 5)]
        mins = self._tool_mins(bench)
        mem_ids = [m["id"] for m in self.memory_items] if self.memory_items else None
        ctx = {"new_ids": new_ids, "paths": set(paths), "tools": list(mins), "tool_min": mins, "remaining": bench.remaining,
               "n_train": bench.n_train, "mem_ids": mem_ids}
        schema = one_shot_schema(paths=paths, new_ids=new_ids, tools=list(mins), mem_ids=mem_ids)
        best = bench.best_design()
        uctx = {"bench": bench, "best": best, "remaining": bench.remaining, "total": total, "best_observed": True, "cf_available": [],
                "cf_cost": bench.n_obs, "tool_min": mins}
        task = ("TASK: the single reply. Give `hypotheses` (up to 4, ids H1..H4), `repairs` (1-2, run in order from the current best "
                "design; budget shares are fractions of the remaining rollouts and sum to at most 1), `diagnosis_category`, "
                "`explanation` and `confidence`. No experiments are possible in this session.")
        if mem_ids:
            task += " Also assess every retrieved memory item in memory_assessments."
        user = self._user(1, uctx, task).replace("COSTS NOW:\n  counterfactual: ", "COSTS NOW (counterfactuals are NOT available in this session):\n  counterfactual: ", 1)
        msgs = [{"role": "system", "content": self.system}, {"role": "user", "content": user}]
        self._event("model_call", 1)
        dec = self._ask_step("one_shot", 1, msgs, schema, SCHEMA_ONE_SHOT, lambda r: validate_one_shot(r, ctx))
        srec = {"step": 1, "user_message": user, "status": dec["status"], "calls": dec["calls"], "parsed": copy.deepcopy(dec["parsed"]),
                "first_attempt_errors": dec["first_attempt_errors"], "validation_errors": dec["validation_errors"],
                "repaired": dec["repaired"], "remaining_before": bench.remaining}
        self.steps.append(srec)
        if dec["status"] != "ok":
            self.final = {"diagnosis_category": None, "ended_by": "invalid_reply",
                          "detail": "the single reply was invalid; the bench's best design (the unrepaired robot) is submitted"}
            return
        reply = dec["reply"]
        srec["hypothesis_transitions"] = self._apply_hypotheses(1, reply["hypotheses"], [])
        if mem_ids is not None:
            self._apply_memory(1, reply["memory_assessments"])
            srec["memory_assessments"] = copy.deepcopy(reply["memory_assessments"])
        remaining0 = bench.remaining
        execs = []
        for r in reply["repairs"]:
            # shares are fractions of the rollouts remaining at the decision; refunds can only make more available
            budget = min(repair_budget(r["budget_share"], remaining0), bench.remaining)
            ent = self._do_repair_budget(bench, 1, r, budget)
            execs.append(ent["id"])
        srec["experiments"] = execs
        srec["remaining_after"] = bench.remaining
        self.final = {"diagnosis_category": reply["diagnosis_category"], "explanation": reply["explanation"],
                      "confidence": float(reply["confidence"]), "submit": "best", "ended_by": "one_shot", "step": 1}

    def _do_repair_budget(self, bench, step: int, r: dict, budget: int) -> dict:
        eid = f"R{1 + sum(1 for e in self.experiments if e['kind'] == 'repair')}"
        before = bench.remaining
        ent = {"id": eid, "kind": "repair", "step": step, "tool": r["tool"], "budget_share": float(r["budget_share"]), "budget": budget,
               "hypothesis": r["hypothesis"], "predicted_n_walking": int(r["predicted_n_walking"]), "n_train": bench.n_train}
        reg = self._event("prediction_registered", step, experiment=eid, tool=r["tool"], predicted_n_walking=ent["predicted_n_walking"])
        ent["registered_seq"] = reg["seq"]
        ex = self._event("bench_call", step, call="repair", experiment=eid, tool=r["tool"], budget=budget)
        ent["executed_seq"] = ex["seq"]
        res = bench.repair(r["tool"], budget)
        ent["cost"] = before - bench.remaining
        if not res.get("ok"):
            ent.update(status="refused", refused=res.get("refused"))
        else:
            ent.update(status="ok", rollouts_used=res["rollouts_used"], start_walking=(res.get("start") or {}).get("walking_count"),
                       train_walking=res["best"]["train_walking"], train_fitness=res["best"]["train_fitness"],
                       is_current_best=bool(res.get("is_current_best")), result_design_index=res["design_index"])
            ent["prediction_error"] = ent["train_walking"] - ent["predicted_n_walking"]
        self.experiments.append(ent)
        return ent

    # -------------------------------------------------------------------------------------------- record
    def _finish(self, bench, total: int) -> dict:
        self.submitted = bench.best_design()
        return self.record()

    def record(self) -> dict:
        rec = super().record()
        rec.update({
            "version": VERSION, "director_version": rec.get("version"), "scientist_mode": self.sci_mode,
            "method": f"SCIENTIST-{self.sci_mode}", "max_steps": self.max_steps, "order_seed": self.order_seed,
            "show_controller": self.show_controller, "system_prompt": self.system,
            "quantities": list(QUANTITIES), "tolerance": TOLERANCE_DOCS,
            "initial_observation": None if not hasattr(self, "_obs0") else self._obs_evidence(self._obs0),
            "initial_observation_cost": getattr(self, "initial_observation_cost", None),
            "steps": copy.deepcopy(self.steps), "events": copy.deepcopy(self.events),
            "hypotheses": copy.deepcopy(self.ledger_h), "experiments": copy.deepcopy(self.experiments),
            "memory": {"items": copy.deepcopy(self.memory_items), "assessments": copy.deepcopy(self.memory_assessments),
                       "log": copy.deepcopy(self.memory_log), "error": getattr(self, "memory_error", None)},
            "prediction_summary": self.prediction_summary(), "final": copy.deepcopy(self.final),
            "submitted_design": copy.deepcopy(self.submitted),
            "n_model_calls": len(self.calls),
            "latency_s": sum(float(c.get("latency_s") or 0.0) for c in self.calls),
        })
        import json
        text = json.dumps(rec)
        if self.api_key and self.api_key in text:
            raise RuntimeError("API key found in the scientist record; refusing to return it")
        return json.loads(text)
