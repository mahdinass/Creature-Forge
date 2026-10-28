"""Nemotron director v3 for the closed-loop mechanism investigation (`nemotron_mech_director_v1`).

`MechDirector` implements the `mech_pipelines` director interface (`investigate(state) -> dict`, `final_plan(state) -> list[plan]`).
Nemotron proposes the STRUCTURE of control-law mechanisms (target, leg, DSL terms, gain bound) and chooses diagnostic probes; a numeric
optimiser fits the signed gains and MuJoCo measures. The model never sets a numeric parameter value and never sees a verdict, a
screening result or a validation seed.

Modes
  * "iterative": up to `max_rounds` investigate calls. After each round the next state carries the measured feedback of the mechanism
    probes (see `mech_pipelines`): the model may revise a mechanism (`revises`), switch hypotheses or stop (`stop: true`), then makes the
    final plan call.
  * "one_shot": exactly one investigate call (mechanisms + probes, no feedback loop), then the final plan call (which sees the results
    of that one round, otherwise it could not name a probed mechanism).

Everything else follows `director.NemotronDirector` (v2): LIVE gate and ledger with a per-pipeline investigation id (pass a fresh one per
method), strict JSON schemas whose citation fields are enums of the evidence paths of that call, ONE repair call carrying the validator's
error list for an unparseable / schema-invalid reply (a failed call is never repaired), listing order shuffled per pipeline with a recorded
seed, SCRIPTED_MOCK for fixtures / injected transports, `.record()` JSON-safe without an API key. A reply that is still invalid after the
repair, or a failed call, yields `{}` / `[]` (nothing substituted; intention to treat) and the reason is recorded.

Trust boundary: the reply is validated here (ids, enums, citations that must be evidence leaf paths, `mechanisms.validate_mechanism`,
revision rules, probe availability, `mech_pipelines.validate_final_plan`, share sum) and rejected WITH reasons; nothing is clipped. The
pipeline validates again.

Evidence paths (flattened scalars, every path citable): creature.*, baseline.*, start.*, budget.*, probes.<id>.* (non-mechanism probes),
mechanisms.<id>.* (mechanism probes: status, rollouts, delta_*, improved, best_*, gain<i>_value / _fraction_of_bound / _at_bound /
_near_zero, all_gains_near_zero, any_gain_at_bound, post.<k>, change.<k>), plans.<id>.* (final plans).
"""
from __future__ import annotations

import copy
import json
import math
from typing import Sequence

from . import director as dr
from . import gait_features as gf
from . import mech_pipelines as mp
from . import r3
from . import walk_opt as wo
from . import walk_pipelines as wp
from .evidence import leaf_paths
from .forge_ai import ModelCall, parse_reply
from .inference_ledger import InferenceLedger
from .investigation import new_investigation_id
from .nebius import contains_secret

VERSION = "nemotron_mech_director_v1"
MODES = ("iterative", "one_shot")
SCHEMA_INVESTIGATE = "mech_director_investigate"
SCHEMA_FINAL = "mech_director_final"
MAX_HYPOTHESES = dr.MAX_HYPOTHESES_PER_CALL
MAX_MECH_CITATIONS = 4
DEFAULT_TARGETS = ("hip", "knee", "ankle", "torque_hip", "torque_knee", "torque_ankle")
DEFAULT_LEGS = ("swing", "stance", "both")
DEFAULT_OPERATIONS = "+, -, *, / (division by an expression is safe-guarded by the evaluator), tanh, clip, abs, min, max, sin, cos"
NO_REVISION = "none"
POST_KEYS = ("fall_time_s", "forward_fall_frac", "froude", "speed_trend_mps2", "pitch_mean_rad", "pitch_drift_radps", "pitch_at_end_rad",
             "step_freq_hz", "step_length_over_leg", "touchdown_foot_ahead_over_leg_mean", "capture_margin_over_leg_mean",
             "capture_margin_over_leg_min", "capture_margin_over_leg_last", "saturation_frac")
BANNED_WORDS = ("foot placement", "foot-placement", "raibert", "capture point", "capture-point", "placement")
_NEUTRAL_REPLACEMENTS = (("the capture point", "the point x + xdot/w"), ("capture point", "the point x + xdot/w"))

_MECH_EVIDENCE_DOCS = {
    "mechanisms.<id>.status": "ok or error (an errored mechanism probe keeps its charge and has no result).",
    "mechanisms.<id>.rollouts": "Rollouts the gain search of the mechanism probe used (training seeds).",
    "mechanisms.<id>.diag_rollouts": "Rollouts spent on the post-probe gait diagnostics (diagnostic seeds).",
    "mechanisms.<id>.best_walking_count": "Training seeds walked by the best gains found.",
    "mechanisms.<id>.best_survival_count": "Training seeds survived by the best gains found.",
    "mechanisms.<id>.best_mean_fitness": "Mean training fitness of the best gains found.",
    "mechanisms.<id>.delta_walking": "best_walking_count minus start.walking_count.",
    "mechanisms.<id>.delta_mean_fitness": "best_mean_fitness minus start.mean_fitness.",
    "mechanisms.<id>.improved": "True if (delta_walking, delta_mean_fitness) > (0, 0) lexicographically.",
    "mechanisms.<id>.gain<i>_value": "Fitted gain of term i (signed; 0-based, in the order of the terms you wrote).",
    "mechanisms.<id>.gain<i>_fraction_of_bound": "gain<i>_value divided by the mechanism's gain_bound (between -1 and 1).",
    "mechanisms.<id>.gain<i>_at_bound": "True if |gain| >= 0.98 of the bound (the optimiser wanted more than allowed).",
    "mechanisms.<id>.gain<i>_near_zero": "True if |gain| <= 0.05 of the bound (the optimiser did not use the term).",
    "mechanisms.<id>.all_gains_near_zero": "True if every gain stayed near zero: the mechanism had no use for the optimiser.",
    "mechanisms.<id>.any_gain_at_bound": "True if some gain hit its bound.",
    "mechanisms.<id>.post.<k>": "Median over the diagnostic seeds of gait feature k for the creature WITH the fitted mechanism (same "
                                "definition as baseline.<k>, which is the unchanged creature).",
    "mechanisms.<id>.change.<k>": "post.<k> minus baseline.<k> (what the mechanism changed in the gait).",
    "plans.<id>.status": "ok or error (final plans only).",
    "plans.<id>.best_walking_count": "Training seeds walked by the plan's best candidate.",
    "plans.<id>.best_mean_fitness": "Mean training fitness of the plan's best candidate.",
    "plans.<id>.delta_walking": "best_walking_count minus start.walking_count.",
    "plans.<id>.delta_mean_fitness": "best_mean_fitness minus start.mean_fitness.",
}


def _neutral(text: str) -> str:
    for a, b in _NEUTRAL_REPLACEMENTS:
        text = text.replace(a, b)
    return text


def _static_docs() -> list[str]:
    skip = ("plans.",)
    docs = [f"- {k}: {v}" for k, v in dr._STATIC_DOCS.items() if not k.startswith(skip)]
    docs.append("- baseline.<k>: median over the diagnostic seeds of gait feature k (listed below); None values are omitted.")
    docs += [f"  - baseline.{k}: {_neutral(v)}" for k, v in gf.SUMMARY_DOCS.items()]
    docs.append("- creature.reference.features.<k>: the same feature for the REFERENCE body, the body for which the transferred start "
                "controller was tuned (it walks there); compare with creature.features.<k>.")
    docs.append("- budget.mechanism_probe_cost: rollouts a mechanism probe costs (gain search + diagnostic rollouts); budget.n_diag: the "
                "diagnostic rollouts of it.")
    docs += [f"- {k}: {v}" for k, v in _MECH_EVIDENCE_DOCS.items()]
    return docs


MECH_TEXT_MAX = 1500   # free-text fields (2026-10-17, after the S4 smoke: a 500-character diagnosis cap discarded a whole final plan)


def _mtext(v, where: str, errs: list, required: bool = True) -> None:
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            errs.append(f"{where}: required text is empty")
        return
    if not isinstance(v, str):
        errs.append(f"{where}: must be a string")
    elif len(v) > MECH_TEXT_MAX:
        errs.append(f"{where}: longer than {MECH_TEXT_MAX} characters")


def build_system_prompt(mode: str = "iterative", order_seed: int | None = None) -> str:
    """The system prompt (deterministic for (mode, order_seed)). Neutral: it describes the language, the economics and the rules, never a
    specific mechanism or which structure tends to work."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    m = mp.mx()
    signals = list(getattr(m, "SIGNALS", ()))
    sdocs = dict(getattr(m, "SIGNAL_DOCS", {}))
    targets = tuple(getattr(m, "TARGETS", DEFAULT_TARGETS))
    legs = tuple(getattr(m, "LEGS", DEFAULT_LEGS))
    sig_lines = [f"- {s}: {_neutral(str(sdocs.get(s, '')))}" for s in dr._order(signals, order_seed)]
    ops = _neutral(str(getattr(m, "DSL_DOCS", DEFAULT_OPERATIONS)))
    probes = []
    for pid in dr._order(mp.MECH_PROBE_IDS, order_seed):
        spec = wp.PROBES[pid]
        txt = dr._PROBE_TEXT[spec["kind"]].format(subspace=spec.get("subspace", ""), bp=", ".join(spec.get("body_params", ())),
                                                  description=spec.get("description", ""))
        probes.append(f"- {pid}: {txt}.")
    subs = []
    for name, params in dr._order([(k, v) for k, v in wo.SUBSPACES.items() if k != "placement"], order_seed):
        subs.append(f"- {name}: " + "; ".join(f"{p} = {r3.PARAM_DESCRIPTIONS[p]}" for p in params) + ".")
    bodies = [f"- {p}: {dr._BODY_DOC[p]}; ratio 0.5-1.5 of the current value, inside the {dr._guided_bounds(p)}." for p in wp.FIX_BODY_PARAMS]
    if mode == "iterative":
        procedure = ("PROCEDURE (iterative): you are called once per investigation round, then once for the final plan. Investigation "
                     "reply: `hypotheses` (new ones, ids as listed; 0-3), `refuted` (hypotheses the measurements contradict), "
                     "`mechanisms` (0-2), `probes` (0-2) and `stop` (true ends the investigation after this reply's items have run). "
                     "You may stop at any time; stopping is not penalised and is not forced. The number of rounds is a limit, not a "
                     "target. After every round you see the measured feedback of everything that ran. Final-plan reply: `refuted`, "
                     "`diagnosis` and `plans` (1-2). Reply with ONE JSON object in the required format and nothing else.")
    else:
        procedure = ("PROCEDURE (one shot): you are called exactly twice. Investigation call (the only one): `hypotheses` (1-3), "
                     "`refuted` (empty), `mechanisms` (0-2), `probes` (0-2) and `stop`. Everything you ask for runs once and there is no "
                     "second investigation round and no revision. Then the final-plan call: `refuted`, `diagnosis` and `plans` (1-2), "
                     "which sees what the investigation measured. Reply with ONE JSON object in the required format and nothing else.")
    return "\n".join([
        "You are the engineering director of a walking-recovery study. A planar (side-view, 2-D) two-legged creature with a phase-based "
        "gait controller (15 parameters) does not walk. You decide WHICH diagnostic experiments to run, WHICH subsystems of the creature "
        "to change, and whether the controller needs a new MECHANISM: an extra control law that you describe in a small expression "
        "language over proprioceptive signals. A numeric optimiser (CMA-ES) fits all numbers (the controller parameters, the body "
        "parameters you select, and the gain of every term of every mechanism) and MuJoCo measures the result. You choose STRUCTURE; you "
        "never choose numeric parameter values and you never decide whether the creature has recovered.",
        "",
        "GOAL: the creature must genuinely walk. The acceptance rule, applied outside your control after your plan has run: >= 80% of 24 "
        "held-out seeds walking under perturbation and friction variation (the walking label of the frozen criteria), AND verdict_v1 "
        "VERIFIED_IMPROVEMENT over the unchanged creature on the same seeds (median paired distance gain >= 0.5 m with a sign test), AND "
        "a 20 s confirmation on 24 further seeds (>= 80% walking, median upright speed above the creature's minimum, little body "
        "contact). Small distance gains do not count. A final screening on separate seeds picks which of your candidates is submitted; "
        "screening and validation seeds never appear in your feedback.",
        "",
        "BUDGET: one total rollout budget pays for everything: the start evaluation, every probe, every mechanism probe, every plan "
        "(also a failed or discarded one), the final screening of the best candidates and of the unchanged creature. A probe or plan is "
        "charged in full before it runs and unused rollouts are refunded. One candidate evaluation costs n_train rollouts (one per "
        "training seed). An optimisation probe costs probe_budget rollouts; a mechanism probe costs probe_budget plus n_diag "
        "diagnostic rollouts (budget.mechanism_probe_cost); a morphology probe costs n_train. Invalid mechanisms, probes and plans are "
        "rejected with a reason, cost nothing and are NOT repaired. A plan whose budget cannot pay one evaluation is rejected and its "
        "share is forfeited. Rollouts still unspent after the final plans are WASTED: they are used for nothing, so spend the remainder "
        "(the shares of the final plans are fractions of what remains when you are asked for the final plan; shares sum to at most 1). "
        "Spending more on investigation leaves less for the final plan. Methods without a model get the same total budget and the same "
        "information as you.",
        "",
        procedure,
        "",
        "MECHANISMS (control laws you may add; at most 2 per investigation reply; at most 2 in a final plan):",
        "A mechanism is {id, target, leg, terms, gain_bound} plus a rationale (and `revises` if it replaces an earlier one).",
        f"- id: a new identifier, letters/digits/underscore, starting with a letter, at most 24 characters, never reused.",
        f"- target: one of {', '.join(targets)}. hip / knee / ankle: an additive offset to the reference angle of that joint; "
        "torque_hip / torque_knee / torque_ankle: an additive torque contribution at that joint (the torque limit still applies).",
        f"- leg: one of {', '.join(legs)}: which leg receives the contribution, decided from the gait phase at every instant "
        "(the swing leg, the stance leg, or both).",
        "- terms: 1-4 expressions over the signals below. The contribution is the sum over terms of gain_i x term_i.",
        f"- operations allowed in an expression: {ops}. Allowed names: the signals listed below and the constant pi. Controller "
        "parameters (for example the gait frequency) are NOT signals; use the phase signal for timing. Any other name, attribute access, "
        "other function calls, loops and imports are rejected.",
        "- gains: ONE signed gain per term, fitted by the optimiser. A gain is bounded to [-gain_bound, +gain_bound] and every gain "
        "STARTS AT 0, so a new mechanism leaves the creature exactly unchanged until the optimiser moves its gains; the optimiser "
        "chooses sign and size. gain_bound is a number in (0, 5]: it is part of the structure (the size of authority the mechanism may "
        "use), not a fitted value.",
        "- rationale: why this structure should act on the failure you measured.",
        "Signals (names usable in terms):",
        *sig_lines,
        "",
        "PROBES (diagnostic experiments; the measured delta is relative to the unchanged creature on the training seeds):",
        *probes,
        "A MECHANISM PROBE runs a short CMA-ES search over ONLY the gains of that mechanism (the rest of the creature stays as it is), on "
        "the training seeds, then measures the gait of the best gains on the diagnostic seeds. Its feedback: delta_walking and "
        "delta_mean_fitness against the unchanged creature, every fitted gain with flags at_bound / near_zero, and the gait summary with "
        "the fitted mechanism next to the baseline gait summary (post.<k>, change.<k>).",
        "",
        "HOW TO USE FEEDBACK: measurements, not hypotheses, count. A mechanism whose fitted gains all stay near zero, or that does not "
        "improve the training score, is evidence AGAINST the hypothesis it tested: the optimiser found no use for that structure. A gain "
        "at its bound says the optimiser wanted more authority than allowed. Compare the post-probe gait with the baseline gait to see "
        "what the mechanism changed and whether that is the change your hypothesis predicted. Revise a mechanism only with a stated "
        "reason that cites the measured feedback of the mechanism you revise (the revision gets a new id and `revises`); otherwise "
        "switch hypothesis or stop. A hypothesis listed in `refuted` must not be pursued again without new evidence.",
        "",
        "CONTROL SUBSPACES (a final plan's ctrl_subspaces; the optimiser searches only these dimensions and keeps the others at the "
        "init's values):",
        *subs,
        "",
        "BODY PARAMETERS (a plan's body_params, at most 4; the leg ones change both legs by one ratio; searched jointly with the plan's "
        "control subspaces and mechanism gains):",
        *bodies,
        "",
        "FINAL PLANS: 1-2 plans {init, ctrl_subspaces, body_params, mechanisms, budget_share}. The optimiser searches the chosen control "
        "subspaces, body parameters and the gains of the chosen mechanisms (ids of mechanisms whose probe ran ok) JOINTLY. init is "
        "\"start\", or the id of a probe or mechanism probe that ran ok; the search starts from that run's best candidate, and a plan "
        "must include every mechanism its init carries. A smaller, well-chosen search space converges faster for the same budget but "
        "excludes everything outside it; a larger one includes more but needs more rollouts for the same progress. The lists in this "
        "message are in no particular order.",
        "",
        "HYPOTHESES: state hypotheses about WHY the creature does not walk; the `mechanism` field of a hypothesis describes the physical "
        "cause in words (not an id). Ground each in evidence by citing evidence paths (copied "
        "exactly from the EVIDENCE lines) and give at least one competing explanation. Every mechanism and probe tests a hypothesis "
        "(`hypothesis` field) with an expected outcome \"improves\" (best candidate beats the start on the training seeds) or "
        "\"no_change\", and every mechanism cites 1-4 evidence paths.",
        "",
        "EVIDENCE: the user message lists `path = value` lines. Citations must be copied exactly from them. Documentation of the paths:",
        *_static_docs(),
    ])


def check_prompt_neutral(text: str) -> list[str]:
    """Banned words found in a prompt (empty = neutral)."""
    low = text.lower()
    return [w for w in BANNED_WORDS if w in low]


# ------------------------------------------------------------------------------------------------------------------ evidence
def _r(v):
    return dr._r(v)


def build_evidence(state: dict, reference: dict | None = None, order_seed: int | None = None) -> dict:
    """Flattened scalar evidence pack of a pipeline state (see module docstring)."""
    st = dict(state)
    ev = dr.build_evidence(st)
    if reference:
        ev["creature"]["reference"] = {"features": dr._scalars(reference)}
    pc = ev["budget"]["probe_cost"]
    ev["budget"]["probe_cost"] = {k: pc[k] for k in dr._order(list(pc), order_seed)}
    ev["budget"]["mechanism_probe_cost"] = state["mechanism_probe_cost"]
    ev["budget"]["n_diag"] = state["n_diag"]
    mechs = {}
    for p in state["mechanism_probes"]:
        d = {"status": p["status"], "rollouts": p["rollouts"], "diag_rollouts": p.get("diag_rollouts", 0)}
        if p["status"] == "ok":
            bs = p["best_score"]
            d.update(best_walking_count=bs["walking_count"], best_survival_count=bs["survival_count"],
                     best_mean_fitness=_r(bs["mean_fitness"]), delta_walking=p["delta_walking"],
                     delta_mean_fitness=_r(p["delta_mean_fitness"]), improved=bool(p["improved"]),
                     all_gains_near_zero=bool(p["all_gains_near_zero"]), any_gain_at_bound=bool(p["any_gain_at_bound"]))
            for g in p["gains"]:
                i = g["term_index"]
                d[f"gain{i}_value"] = _r(g["value"])
                d[f"gain{i}_fraction_of_bound"] = _r(g["fraction_of_bound"])
                d[f"gain{i}_at_bound"] = bool(g["at_bound"])
                d[f"gain{i}_near_zero"] = bool(g["near_zero"])
            post = {k: _r(v) for k, v in (p.get("post_gait") or {}).items() if k in POST_KEYS and dr._scalar(v)}
            chg = {k: _r(v) for k, v in (p.get("gait_change") or {}).items() if k in POST_KEYS and dr._scalar(v)}
            if post:
                d["post"] = post
            if chg:
                d["change"] = chg
        mechs[p["probe_id"]] = d
    if mechs:
        ev["mechanisms"] = mechs
    return ev


# ------------------------------------------------------------------------------------------------------------------ schemas
def _mech_schema(paths, all_hyp_ids, targets, legs, revisable):
    cites = {"type": "array", "items": {"type": "string", "enum": list(paths)}}
    return {"type": "object", "additionalProperties": False,
            "required": ["id", "hypothesis", "expect", "target", "leg", "terms", "gain_bound", "rationale", "revises", "evidence"],
            "properties": {"id": {"type": "string"}, "hypothesis": {"type": "string", "enum": list(all_hyp_ids)},
                           "expect": {"type": "string", "enum": list(dr.EXPECTS)},
                           "target": {"type": "string", "enum": list(targets)}, "leg": {"type": "string", "enum": list(legs)},
                           "terms": {"type": "array", "items": {"type": "string"}}, "gain_bound": {"type": "number"},
                           "rationale": {"type": "string"},
                           "revises": {"type": "string", "enum": [NO_REVISION] + list(revisable)}, "evidence": cites}}


def investigate_schema(paths, new_ids, all_hyp_ids, probe_ids, revisable, refutable, targets, legs) -> dict:
    hyp = {"type": "object", "additionalProperties": False, "required": ["id", "mechanism", "evidence", "competing"],
           "properties": {"id": {"type": "string", "enum": list(new_ids)}, "mechanism": {"type": "string"},
                          "evidence": {"type": "array", "items": {"type": "string", "enum": list(paths)}},
                          "competing": {"type": "array", "items": {"type": "string"}}}}
    probe = {"type": "object", "additionalProperties": False, "required": ["probe_id", "hypothesis", "expect"],
             "properties": {"probe_id": {"type": "string", "enum": list(probe_ids)},
                            "hypothesis": {"type": "string", "enum": list(all_hyp_ids)},
                            "expect": {"type": "string", "enum": list(dr.EXPECTS)}}}
    return {"type": "object", "additionalProperties": False, "required": ["hypotheses", "refuted", "mechanisms", "probes", "stop"],
            "properties": {"hypotheses": {"type": "array", "items": hyp},
                           "refuted": {"type": "array", "items": {"type": "string", "enum": list(refutable) or ["(none open)"]}},
                           "mechanisms": {"type": "array", "items": _mech_schema(paths, all_hyp_ids, targets, legs, revisable)},
                           "probes": {"type": "array", "items": probe}, "stop": {"type": "boolean"}}}


def final_schema(paths, hyp_ids, refutable, inits, subspaces, mech_ids) -> dict:
    plan = {"type": "object", "additionalProperties": False,
            "required": ["init", "ctrl_subspaces", "body_params", "mechanisms", "budget_share", "hypothesis", "prediction", "evidence"],
            "properties": {"init": {"type": "string", "enum": list(inits)},
                           "ctrl_subspaces": {"type": "array", "items": {"type": "string", "enum": list(subspaces)}},
                           "body_params": {"type": "array", "items": {"type": "string", "enum": list(wp.FIX_BODY_PARAMS)}},
                           "mechanisms": {"type": "array", "items": {"type": "string", "enum": list(mech_ids) or ["(none probed)"]}},
                           "budget_share": {"type": "number"},
                           "hypothesis": {"type": "string", "enum": list(hyp_ids) + [dr.NO_HYPOTHESIS]},
                           "prediction": {"type": "string"},
                           "evidence": {"type": "array", "items": {"type": "string", "enum": list(paths)}}}}
    return {"type": "object", "additionalProperties": False, "required": ["refuted", "diagnosis", "plans"],
            "properties": {"refuted": {"type": "array", "items": {"type": "string", "enum": list(refutable) or ["(none open)"]}},
                           "diagnosis": {"type": "string"}, "plans": {"type": "array", "items": plan}}}


# ------------------------------------------------------------------------------------------------------------------ validators
def validate_investigate_reply(reply, *, paths: set, new_ids: list[str], live_ids: list[str], refutable: list[str],
                               available: list[str], revisable: set, used_mech_ids: set, structures: dict,
                               mech_affordable: bool = True, mode: str = "iterative") -> tuple[list[str], dict | None]:
    """(errors, normalised decision). Empty errors = valid."""
    errs: list[str] = []
    if not dr._exact(reply, {"hypotheses", "refuted", "mechanisms", "probes", "stop"}, "reply", errs):
        return errs, None
    hyps, ref, mechs, probes, stop = (reply[k] for k in ("hypotheses", "refuted", "mechanisms", "probes", "stop"))
    if not all(isinstance(x, list) for x in (hyps, ref, mechs, probes)):
        return errs + ["reply: hypotheses, refuted, mechanisms and probes must be lists"], None
    if not isinstance(stop, bool):
        errs.append("stop must be a boolean")
    if not len(hyps) <= MAX_HYPOTHESES:
        errs.append(f"hypotheses: at most {MAX_HYPOTHESES} (got {len(hyps)})")
    seen: set = set()
    for i, h in enumerate(hyps):
        w = f"hypotheses[{i}]"
        if not dr._exact(h, {"id", "mechanism", "evidence", "competing"}, w, errs):
            continue
        if h["id"] not in new_ids:
            errs.append(f"{w}: id {h['id']!r} must be one of {new_ids}")
        elif h["id"] in seen:
            errs.append(f"{w}: duplicate id {h['id']!r}")
        seen.add(h["id"])
        _mtext(h["mechanism"], f"{w}.mechanism", errs)
        dr._cites(h["evidence"], f"{w}.evidence", paths, dr.MAX_CITATIONS, errs)
        if not isinstance(h["competing"], list) or not h["competing"]:
            errs.append(f"{w}.competing: give at least one competing explanation")
        else:
            for j, c in enumerate(h["competing"]):
                _mtext(c, f"{w}.competing[{j}]", errs)
    for i, r in enumerate(ref):
        if not isinstance(r, str) or r not in refutable:
            errs.append(f"refuted[{i}]: {r!r} is not an existing hypothesis that is still open (open: {refutable})")
    if len(set(map(str, ref))) != len(ref):
        errs.append("refuted: duplicate ids")
    known = (set(live_ids) | seen) - set(map(str, ref))
    if mode == "one_shot" and ref:
        errs.append("refuted: nothing can be refuted in a one-shot investigation")
    if (mechs or probes) and not known:
        errs.append("mechanisms / probes need at least one hypothesis (new or open) to test")
    if len(mechs) > mp.MAX_MECH_PER_ROUND:
        errs.append(f"mechanisms: at most {mp.MAX_MECH_PER_ROUND} (got {len(mechs)})")
    if mechs and not mech_affordable:
        errs.append("mechanisms: a mechanism probe is not affordable with the remaining budget")
    out_m, mids = [], []
    structures = dict(structures)               # structures of earlier probes + of the mechanisms accepted so far in this reply
    for i, m in enumerate(mechs):
        w = f"mechanisms[{i}]"
        if not dr._exact(m, {"id", "hypothesis", "expect", "target", "leg", "terms", "gain_bound", "rationale", "revises", "evidence"},
                         w, errs):
            continue
        if m["hypothesis"] not in known:
            errs.append(f"{w}: hypothesis {m['hypothesis']!r} does not exist or is refuted (usable: {sorted(known)})")
        if m["expect"] not in dr.EXPECTS:
            errs.append(f"{w}: expect must be one of {list(dr.EXPECTS)}")
        if not isinstance(m["terms"], list) or not all(isinstance(t, str) for t in m["terms"]):
            errs.append(f"{w}.terms: must be a list of strings")
            continue
        if isinstance(m["gain_bound"], bool) or not isinstance(m["gain_bound"], (int, float)) or not math.isfinite(float(m["gain_bound"])):
            errs.append(f"{w}.gain_bound: must be a finite number")
            continue
        _mtext(m["rationale"], f"{w}.rationale", errs)
        dr._cites(m["evidence"], f"{w}.evidence", paths, MAX_MECH_CITATIONS, errs)
        rev = m["revises"]
        core = {"id": m["id"], "target": m["target"], "leg": m["leg"], "terms": list(m["terms"]),
                "gain_bound": float(m["gain_bound"]), "rationale": m["rationale"]}
        if rev != NO_REVISION:
            core["revises"] = rev
            if not isinstance(rev, str) or rev not in revisable:
                errs.append(f"{w}: revises {rev!r} is not a mechanism probed in an earlier round (probed: {sorted(revisable)})")
            elif isinstance(m["evidence"], list) and not any(isinstance(c, str) and c.startswith(f"mechanisms.{rev}.") for c in m["evidence"]):
                errs.append(f"{w}: a revision must cite the measured feedback of {rev!r} (an evidence path starting with mechanisms.{rev}.)")
        if m["id"] in mids:
            errs.append(f"{w}: id {m['id']!r} used twice in this reply")
        mids.append(m["id"])
        errs += [f"{w}: {e}" for e in mp.validate_decision_mechanism(core, used_ids=set(used_mech_ids), probed_before=set(revisable),
                                                                     structures=structures)]
        structures.setdefault(mp._structure_key(core), core["id"])
        out_m.append(core)
    if len(probes) > mp.MAX_PROBES_PER_ROUND:
        errs.append(f"probes: at most {mp.MAX_PROBES_PER_ROUND} (got {len(probes)})")
    ids = []
    for i, p in enumerate(probes):
        w = f"probes[{i}]"
        if not dr._exact(p, {"probe_id", "hypothesis", "expect"}, w, errs):
            continue
        if not isinstance(p["probe_id"], str) or p["probe_id"] not in mp.MECH_PROBE_IDS:
            errs.append(f"{w}: unknown probe {p['probe_id']!r}")
        elif p["probe_id"] not in available:
            errs.append(f"{w}: probe {p['probe_id']!r} is not available now (available: {available})")
        elif p["probe_id"] in ids:
            errs.append(f"{w}: probe {p['probe_id']!r} requested twice")
        else:
            ids.append(p["probe_id"])
        if p["hypothesis"] not in known:
            errs.append(f"{w}: hypothesis {p['hypothesis']!r} does not exist or is refuted (usable: {sorted(known)})")
        if p["expect"] not in dr.EXPECTS:
            errs.append(f"{w}: expect must be one of {list(dr.EXPECTS)}")
    return errs, {"mechanisms": out_m, "probes": ids, "stop": bool(stop) if isinstance(stop, bool) else False}


def validate_final_reply(reply, *, paths: set, live_ids: list[str], refutable: list[str], runs: dict, mech_ids: set) -> list[str]:
    errs: list[str] = []
    if not dr._exact(reply, {"refuted", "diagnosis", "plans"}, "reply", errs):
        return errs
    ref, plans = reply["refuted"], reply["plans"]
    if not isinstance(ref, list) or not isinstance(plans, list):
        return errs + ["reply: refuted and plans must be lists"]
    _mtext(reply["diagnosis"], "diagnosis", errs)
    for i, r in enumerate(ref):
        if not isinstance(r, str) or r not in refutable:
            errs.append(f"refuted[{i}]: {r!r} is not an existing hypothesis that is still open (open: {refutable})")
    if len(set(map(str, ref))) != len(ref):
        errs.append("refuted: duplicate ids")
    if not 1 <= len(plans) <= mp.MAX_FINAL_PLANS:
        errs.append(f"plans: need 1-{mp.MAX_FINAL_PLANS} plans (got {len(plans)})")
    cum = 0.0
    for i, p in enumerate(plans):
        w = f"plans[{i}]"
        if not dr._exact(p, {"init", "ctrl_subspaces", "body_params", "mechanisms", "budget_share", "hypothesis", "prediction", "evidence"},
                         w, errs):
            continue
        core = {k: p[k] for k in mp.FINAL_PLAN_KEYS}
        errs += [f"{w}: {e}" for e in mp.validate_final_plan(core, runs=runs, mech_ids=mech_ids)]
        if isinstance(p["body_params"], list):
            off = [b for b in p["body_params"] if isinstance(b, str) and b not in wp.FIX_BODY_PARAMS]
            if off:
                errs.append(f"{w}: body parameter(s) {off} are not allowed here; allowed: {list(wp.FIX_BODY_PARAMS)}")
        h = p["hypothesis"]
        if h != dr.NO_HYPOTHESIS and h not in live_ids:
            errs.append(f"{w}: hypothesis {h!r} is not an open hypothesis (open: {live_ids}; use {dr.NO_HYPOTHESIS!r} with evidence)")
        if h in ref:
            errs.append(f"{w}: hypothesis {h!r} is listed in refuted; a refuted hypothesis must not be pursued")
        _mtext(p["prediction"], f"{w}.prediction", errs)
        dr._cites(p["evidence"], f"{w}.evidence", paths, dr.MAX_PLAN_CITATIONS, errs)
        sh = p["budget_share"]
        if isinstance(sh, (int, float)) and not isinstance(sh, bool) and math.isfinite(float(sh)):
            cum += float(sh)
    if cum > 1.0 + dr.SHARE_EPS:
        errs.append(f"plans: budget shares sum to {cum:.4g} > 1")
    return errs


# ------------------------------------------------------------------------------------------------------------------ director
class MechDirector(dr.NemotronDirector):
    """See module docstring. `mode` is the investigation mode ("iterative" | "one_shot"). `source` is "live" or "scripted" (default:
    scripted iff `fixture` is given); an injected transport is always labelled SCRIPTED_MOCK (as in `NemotronDirector`)."""

    def __init__(self, mode: str = "iterative", *, source: str | None = None, profile: str = "default",
                 ledger: InferenceLedger | None = None, investigation_id: str | None = None, transport=None,
                 fixture: Sequence | None = None, max_requests: int = 12, max_total_tokens: int = 260_000, config=None,
                 order_seed: int | None = None, reference: dict | None = None, method: str | None = None):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        src = source or ("scripted" if fixture is not None else "live")
        super().__init__(mode=src, profile=profile, ledger=ledger, investigation_id=investigation_id or new_investigation_id(),
                         transport=transport, fixture=fixture, max_requests=max_requests, max_total_tokens=max_total_tokens,
                         config=config, evidence_mode="full", prompt_version="v2", order_seed=order_seed)
        self.mech_mode = mode
        self.method = method or f"AI-MECH-{mode}"
        self.reference = dict(reference) if reference else {}
        self.system = build_system_prompt(mode, order_seed)
        bad = check_prompt_neutral(self.system)
        if bad:
            raise ValueError(f"system prompt contains banned word(s) {bad}: the mechanisms module's docs must be neutral")
        self.mech_meta: dict[str, dict] = {}

    # ---------------------------------------------------------------------------------------------- machinery
    def _evidence(self, state: dict) -> dict:
        return build_evidence(state, self.reference, self.order_seed)

    def _ask(self, kind: str, rnd: int, messages: list, schema: dict, validate) -> dict:
        dec = {"kind": kind, "round": rnd, "calls": [], "parsed": None, "first_attempt_errors": [], "validation_errors": [],
               "repaired": False, "status": "ok", "returned": []}
        name = SCHEMA_INVESTIGATE if kind == "investigate" else SCHEMA_FINAL

        def assess(call: ModelCall):
            try:
                reply = parse_reply(call.content)
            except ValueError as e:
                return None, [str(e)], None
            errs, extra = validate(reply)
            return reply, errs, extra

        call, idx = self._send(messages, schema, name, f"mech_director_{kind}")
        dec["calls"].append(idx)
        if not call.ok:
            dec.update(status="model_failed", validation_errors=[self._clean(call.error or "no content")])
            return dec
        reply, errs, extra = assess(call)
        dec["parsed"] = reply
        if errs:
            dec["first_attempt_errors"] = [self._clean(e) for e in errs]
            dec["repaired"] = True
            call2, idx2 = self._send(self._repair_messages(messages, call, errs), schema, name, "mech_director_repair")
            dec["calls"].append(idx2)
            if not call2.ok:
                dec.update(status="repair_failed", validation_errors=dec["first_attempt_errors"] + [self._clean(call2.error or "no content")])
                return dec
            reply, errs, extra = assess(call2)
            dec["parsed"] = reply
        if errs:
            dec.update(status="invalid_after_repair" if dec["repaired"] else "invalid", validation_errors=[self._clean(e) for e in errs])
            return dec
        dec["reply"], dec["extra"] = reply, extra
        return dec

    def _user(self, state: dict, evidence: dict, task: str) -> str:
        b = state["budget"]
        head = [f"ROUND {state['round']} of {state['rounds_total']} (mode {self.mech_mode}). STAGE: "
                + ("investigation" if task == "investigate" else "FINAL PLAN") + ". The controller has 15 parameters (family 15).",
                f"Remaining budget {b['remaining']} of {b['total']} rollouts ({b['reserved_for_screening']} reserved for screening); "
                f"n_train = {state['n_train']}, n_diag = {state['n_diag']}; mechanism probe cost {state['mechanism_probe_cost']}.",
                "", "EVIDENCE:", *dr.evidence_lines(evidence)]
        if self.hypotheses:
            head += ["", "YOUR HYPOTHESES SO FAR:"]
            for h, d in self.hypotheses.items():
                head.append(f"{h} [round {d['round']}, {'REFUTED in round ' + str(d['refuted_round']) if d['refuted'] else 'open'}]: "
                            f"{d['mechanism']} (cites {', '.join(d['evidence'])}; competing: {'; '.join(d['competing'])})")
        ran = []
        for mid, m in self.mech_meta.items():
            ran.append(f"mechanism {mid} [round {m['round']}, tests {m['hypothesis']}, expected {m['expect']}"
                       + (f", revises {m['revises']}" if m.get("revises") else "") + f"]: target {m['target']}, leg {m['leg']}, "
                       f"gain_bound {m['gain_bound']}, terms {json.dumps(m['terms'])}; why: {m['rationale']}")
        for pid, e in self.expectations.items():
            ran.append(f"probe {pid}: you expected {e['expect']} (for {e['hypothesis']})")
        for pid, m in self.plan_meta.items():
            ran.append(f"plan {pid}: init {m['init']}, subspaces {m['ctrl_subspaces'] or '-'}, body {m['body_params'] or '-'}, "
                       f"mechanisms {m.get('mechanisms') or '-'}, share {m['budget_share']}, for {m['hypothesis']}; predicted: {m['prediction']}")
        if ran:
            head += ["", "WHAT YOU DECIDED EARLIER:", *ran]
        rej = state.get("rejected_last_round") or []
        if rej:
            head += ["", "REJECTED IN YOUR LAST DECISION (cost 0, not repaired):"]
            for r in rej:
                head.append(f"{r.get('kind')} {r.get('id')}: " + "; ".join(map(str, r.get("reasons", []))))
        if task == "investigate":
            if self.mech_mode == "one_shot":
                head += ["", "TASK: the single investigation call. Reply with `hypotheses`, `refuted` (empty), `mechanisms`, `probes` and "
                             "`stop` (ids and options are in the response schema)."]
            else:
                head += ["", "TASK: investigation call. Reply with `hypotheses` (new), `refuted`, `mechanisms`, `probes` and `stop` "
                             "(ids and options are in the response schema). Set stop to true when more investigation is not worth its "
                             "cost."]
        else:
            head += ["", f"TASK: final plan call. {b['remaining']} rollouts remain; whatever the plans leave unspent is wasted. Reply with "
                         "`refuted`, `diagnosis` and `plans`."]
        return "\n".join(head)

    def _finish(self, dec: dict, returned) -> object:
        dec.pop("reply", None)
        dec.pop("extra", None)
        dec["returned"] = copy.deepcopy(returned)
        self.decisions.append(dec)
        return returned

    def _error_dec(self, kind: str, rnd: int, e: Exception) -> dict:
        return {"kind": kind, "round": rnd, "calls": [], "parsed": None, "first_attempt_errors": [], "repaired": False,
                "status": "director_error", "validation_errors": [self._clean(f"{type(e).__name__}: {e}")]}

    # ---------------------------------------------------------------------------------------------- the director interface
    def investigate(self, state: dict) -> dict:
        rnd = state["round"]
        if self.mech_mode == "one_shot" and rnd > 1:
            return self._finish({"kind": "investigate", "round": rnd, "calls": [], "parsed": None, "first_attempt_errors": [],
                                 "repaired": False, "status": "one_shot_no_call", "validation_errors": []}, {"stop": True})
        try:
            return self._investigate(state, rnd)
        except Exception as e:      # noqa: BLE001 - recorded; nothing substituted
            return self._finish(self._error_dec("investigate", rnd, e), {})

    def _investigate(self, state: dict, rnd: int) -> dict:
        evidence = self._evidence(state)
        paths = leaf_paths(evidence, limit=10_000)
        n = max([int(h[1:]) for h in self.hypotheses] or [0])
        new_ids = [f"H{n + i}" for i in range(1, MAX_HYPOTHESES + 1)]
        live = self._live_ids()
        avail = dr._order(list(state["available_probes"]), self.order_seed)
        revisable = sorted(p["probe_id"] for p in state["mechanism_probes"])
        used = set(state["mechanisms_registry"])
        structures = {mp._structure_key(m["mechanism"]): k for k, m in
                      ((p["probe_id"], p) for p in state["mechanism_probes"])}
        mx = mp.mx()
        targets = tuple(getattr(mx, "TARGETS", DEFAULT_TARGETS))
        legs = tuple(getattr(mx, "LEGS", DEFAULT_LEGS))
        schema = investigate_schema(paths, new_ids, live + new_ids, avail or ["(none available)"], revisable, live, targets, legs)
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": self._user(state, evidence, "investigate")}]
        pset = set(paths)
        dec = self._ask("investigate", rnd, messages, schema, lambda r: validate_investigate_reply(
            r, paths=pset, new_ids=new_ids, live_ids=live, refutable=live, available=avail, revisable=set(revisable),
            used_mech_ids=used, structures=structures, mech_affordable=bool(state.get("mechanism_probe_affordable", True)),
            mode=self.mech_mode))
        if dec["status"] != "ok":
            return self._finish(dec, {})
        reply, extra = dec["reply"], dec["extra"]
        for h in reply["hypotheses"]:
            self.hypotheses[h["id"]] = {"round": rnd, "mechanism": h["mechanism"], "evidence": list(h["evidence"]),
                                        "competing": list(h["competing"]), "refuted": False, "refuted_round": None}
        for h in reply["refuted"]:
            self.hypotheses[h]["refuted"], self.hypotheses[h]["refuted_round"] = True, rnd
        self.refuted_by_round[str(rnd)] = list(reply["refuted"])
        for p in reply["probes"]:
            self.expectations[p["probe_id"]] = {"hypothesis": p["hypothesis"], "expect": p["expect"], "round": rnd}
        for m in reply["mechanisms"]:
            self.mech_meta[m["id"]] = {"round": rnd, "hypothesis": m["hypothesis"], "expect": m["expect"], "target": m["target"],
                                       "leg": m["leg"], "terms": list(m["terms"]), "gain_bound": m["gain_bound"],
                                       "rationale": m["rationale"], "evidence": list(m["evidence"]),
                                       "revises": None if m["revises"] == NO_REVISION else m["revises"]}
        return self._finish(dec, extra)

    def final_plan(self, state: dict) -> list:
        rnd = state["round"]
        try:
            return self._final_plan(state, rnd)
        except Exception as e:      # noqa: BLE001
            return self._finish(self._error_dec("final_plan", rnd, e), [])

    def _final_plan(self, state: dict, rnd: int) -> list:
        evidence = self._evidence(state)
        paths = leaf_paths(evidence, limit=10_000)
        live = self._live_ids()
        runs = {p["probe_id"]: [] for p in state["probes_run"] if p["status"] == "ok"}
        runs.update({p["probe_id"]: [p["probe_id"]] for p in state["mechanism_probes"] if p["status"] == "ok"})
        mech_ids = sorted(k for k, v in runs.items() if v)
        subs = dr._order(list(mp.SUBSPACES15), self.order_seed)
        schema = final_schema(paths, live, live, ["start"] + sorted(runs), subs, mech_ids)
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": self._user(state, evidence, "final")}]
        pset = set(paths)
        dec = self._ask("final_plan", rnd, messages, schema, lambda r: (validate_final_reply(
            r, paths=pset, live_ids=live, refutable=live, runs=runs, mech_ids=set(mech_ids)), None))
        if dec["status"] != "ok":
            return self._finish(dec, [])
        reply = dec["reply"]
        out = []
        for i, p in enumerate(reply["plans"]):
            out.append({"init": p["init"], "ctrl_subspaces": list(p["ctrl_subspaces"]), "body_params": list(p["body_params"]),
                        "mechanisms": list(p["mechanisms"]), "budget_share": p["budget_share"],
                        "rationale": f"{p['hypothesis']}: {p['prediction']}"})
            self.plan_meta[f"f{i}"] = {"init": p["init"], "ctrl_subspaces": list(p["ctrl_subspaces"]),
                                       "body_params": list(p["body_params"]), "mechanisms": list(p["mechanisms"]),
                                       "budget_share": p["budget_share"], "hypothesis": p["hypothesis"],
                                       "prediction": p["prediction"], "evidence": list(p["evidence"])}
        for h in reply["refuted"]:
            self.hypotheses[h]["refuted"], self.hypotheses[h]["refuted_round"] = True, rnd
        self.refuted_by_round["final"] = list(reply["refuted"])
        dec["diagnosis"] = reply["diagnosis"]
        return self._finish(dec, out)

    # ---------------------------------------------------------------------------------------------- record
    def record(self) -> dict:
        rec = super().record()
        rec.update(version=VERSION, method=self.method, mech_mode=self.mech_mode, mech_meta=copy.deepcopy(self.mech_meta),
                   reference_features=copy.deepcopy(self.reference))
        text = json.dumps(rec)
        if contains_secret(text, self.api_key):
            raise RuntimeError("API key found in the director record; refusing to return it")
        return json.loads(text)
