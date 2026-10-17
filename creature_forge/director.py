"""AI director for the walking-recovery study (`nemotron_director_v1`).

`NemotronDirector` implements the `walk_pipelines` director interface (`choose_probes(state)`, `choose_plans(state)`). NVIDIA Nemotron
makes the engineering DECISIONS: which diagnostic experiments to run and which subsystems of the creature to change with what share of the
remaining rollout budget. A numeric optimiser (CMA-ES in `walk_pipelines`) does the fitting and MuJoCo measures. The model never sets a
numeric parameter value, never sees a verdict, and receives exactly the information the non-AI directors receive (the pipeline `state`)
at the same total rollout budget.

Calls per round: one probe call, one plan call. Each may get ONE repair call that carries the validator's error list (as in `forge_ai`);
nothing else is retried. A call that failed (HTTP error, timeout, empty content, `finish_reason=length`, ledger refusal) is never repaired.
If a reply is still invalid after the repair, or the call failed, the director returns `[]` (no probes / no plans). It never substitutes a
default or a non-AI decision (intention to treat); the reason is recorded.

Trust boundary: the reply is parsed (`forge_ai.parse_reply`), validated here (ids, enums, citations that must be leaf paths of the
evidence pack, probe availability, `walk_pipelines.validate_plan`, the share sum) and rejected WITH reasons; nothing is clipped or repaired
by code. The pipeline validates again when it receives the decisions.

Evidence (flattened scalars, every path citable and a strict enum in the JSON schema, like `forge_ai.build_reply_schema`):
  creature.<body field>, creature.features.<k>, baseline.<k>, start.<k>, budget.<k>, budget.probe_cost.<probe_id>,
  probes.<id>.<k> (measured probes), plans.<id>.<k> (previous plans; scalars only).

Provenance: mode "live" with the real transport -> LIVE (an injected transport is always labelled SCRIPTED_MOCK; needs CREATURE_FORGE_ENABLE_LIVE=1, NEBIUS_API_KEY, ledger headroom; same gate as
`investigation.live_refusal`); mode "scripted" -> SCRIPTED_MOCK (replies come from `fixture`, a scratch ledger or the one passed in, model
name `scripted-fixture`), never promoted to LIVE. `.record()` is JSON-safe and holds no API key.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import math
import re
import tempfile
from pathlib import Path
from typing import Sequence

from . import gait_features as gf
from . import r3
from . import interventions as iv
from . import walk_opt as wo
from . import walk_pipelines as wp
from .evidence import leaf_items, leaf_paths
from .forge_ai import ModelCall, ModelConfig, call_model, make_client, parse_reply
from .inference_ledger import Caps, InferenceLedger
from .investigation import (PROVENANCE, SCRIPTED_MODEL, LiveRefused, live_refusal, load_model_config, new_investigation_id)
from .nebius import estimate_prompt_tokens, redact_secret

VERSION = "nemotron_director_v1"
PROMPT_VERSIONS = ("v1", "v2")
# v2 (2026-10-17, development tuning after S2 - experiments/walk_recovery/dev_pilot/REPORT_S2.md): (a) the body is presented as a
# subsystem on a par with the control subspaces, (b) budget left after the last round is stated to be wasted, (c) the order in
# which probes and subspaces are listed (prompt text and schema enums) is shuffled per pipeline with a recorded seed, removing a
# fixed list-position bias (v1 listed opt_timing first and the model chose it in 22/24 pipelines), (d) the reference body's
# features (the body the transferred controller was tuned for) are part of the evidence. No statement about which subsystem
# usually works is added.
MAX_HYPOTHESES_PER_CALL = 3
MAX_CITATIONS = 6
MAX_PLAN_CITATIONS = 4
MAX_PROBES = wp.MAX_PROBES_PER_ROUND
MAX_PLANS = wp.MAX_PLANS_PER_ROUND
EXPECTS = ("improves", "no_change")
TEXT_MAX = 1500   # was 500; raised by S3 amendment 1 (2026-10-17, before any confirmatory data): a 500-char diagnosis cap rejected otherwise valid final plans
PROMPT_TARGET_BYTES = 6000
SCHEMA_PROBES = "director_probes"
SCHEMA_PLANS = "director_plans"
REPAIR_ECHO_MAX = 4000
REPAIR_ERRORS_MAX = 12
SHARE_EPS = 1e-9
NO_HYPOTHESIS = "none"
_SAFE = re.compile(r"[^A-Za-z0-9_]+")


# ------------------------------------------------------------------------------------------------------------------ system prompt
_PROBE_TEXT = {
    "subspace": "runs a short CMA-ES search (its cost is in budget.probe_cost) over ONLY the {subspace} parameters, starting from the unchanged creature",
    "body": "runs a short CMA-ES search over the four body parameters {bp} with the controller fixed",
    "morphology": "evaluates the unchanged controller once on the training seeds on a counterfactual body: {description}; unavailable if the edit would leave the guided bounds",
    "similarity": "evaluates once on the training seeds the controller transferred by dynamic similarity (frequency, gains and ramp rescaled by leg length and mass)",
}
_BODY_DOC = {
    "foot_length": "foot length (m), mostly forward of the ankle; both feet change together by one ratio",
    "thigh_length": "thigh length, hip to knee (m); both legs change together by one ratio",
    "shank_length": "shank length, knee to ankle (m); both legs change together by one ratio",
    "torso_mass": "torso mass parameter (kg), sets the torso box density",
}
_PLACEMENT_DOC = ("fp_kd: gain of swing-foot placement feedback on the torso-ahead-of-stance-foot distance; fp_kv: the same on the torso "
                  "velocity; both distances and velocities are normalised by leg length (family 17 only; both are 0 at the start, which behaves "
                  "exactly like family 15)")
_STATIC_DOCS = {
    "creature.<body field>": "Body parameter of the creature (SI units; *_r = right leg; the legs may differ).",
    "creature.features.L": "Mean leg length, thigh + shank (m).",
    "creature.features.foot_to_leg": "Mean foot length divided by L.",
    "creature.features.mass_total": "Total mass of the compiled MuJoCo model (kg).",
    "creature.features.torso_frac": "Torso mass parameter divided by total mass.",
    "creature.features.tau_ratio": "torque_limit / (total mass * g * L): torque authority relative to weight at one leg length.",
    "creature.features.friction": "Foot-floor friction coefficient.",
    "creature.features.leg_density": "Leg segment density (kg/m^3).",
    "baseline.outcome_<X>": "Number of diagnostic seeds of the UNCHANGED creature (R2 transfer controller, 10 s, not charged) with outcome X (PASS = walking).",
    "baseline.label_<x>": "Number of those seeds whose gait label is x.",
    "start.walking_count": "Training seeds (of n_train) on which the unchanged creature walks, under perturbation and friction variation.",
    "start.survival_count": "Training seeds on which it stays up (not necessarily walking).",
    "start.mean_fitness": "Mean fitness over the training seeds (higher is better).",
    "budget.total": "Total rollout budget of this study run (everything is charged to it).",
    "budget.reserved_for_screening": "Rollouts already reserved for the final screening of candidates; not spendable.",
    "budget.remaining": "Rollouts you can still spend on probes and plans.",
    "budget.n_train": "Training seeds; one candidate evaluation costs n_train rollouts.",
    "budget.round": "Current round (1-based).",
    "budget.rounds_total": "Number of rounds.",
    "budget.probe_cost.<probe_id>": "Rollouts the probe would cost (available probes only).",
    "probes.<id>.status": "ok or error (an errored probe keeps its charge and has no result).",
    "probes.<id>.rollouts": "Rollouts the probe actually used.",
    "probes.<id>.best_walking_count": "Training seeds walked by the probe's best candidate.",
    "probes.<id>.best_survival_count": "Training seeds survived by the probe's best candidate.",
    "probes.<id>.best_mean_fitness": "Mean training fitness of the probe's best candidate.",
    "probes.<id>.delta_walking": "best_walking_count minus start.walking_count.",
    "probes.<id>.delta_mean_fitness": "best_mean_fitness minus start.mean_fitness.",
    "probes.<id>.improved": "True if (delta_walking, delta_mean_fitness) > (0, 0) lexicographically.",
    "plans.<id>.status": "ok or error (an errored plan keeps its charge).",
    "plans.<id>.budget": "Rollouts reserved for the plan.",
    "plans.<id>.rollouts_used": "Rollouts the plan used.",
    "plans.<id>.best_walking_count": "Training seeds walked by the plan's best candidate.",
    "plans.<id>.best_survival_count": "Training seeds survived by the plan's best candidate.",
    "plans.<id>.best_mean_fitness": "Mean training fitness of the plan's best candidate.",
    "plans.<id>.delta_walking": "best_walking_count minus start.walking_count.",
    "plans.<id>.delta_mean_fitness": "best_mean_fitness minus start.mean_fitness.",
}


def _guided_bounds(p: str) -> str:
    lo, hi = iv.mode_bounds("guided")[p]
    return f"guided bounds [{lo:g}, {hi:g}]"


def _order(items, seed):
    items = list(items)
    if seed is None:
        return items
    import numpy as np
    perm = np.random.default_rng(np.random.SeedSequence([int(seed), 0x0D1E])).permutation(len(items))
    return [items[i] for i in perm]


def build_system_prompt(prompt_version: str = "v1", order_seed: int | None = None) -> str:
    """The director's system prompt (deterministic for (version, order_seed); generated from the live probe catalogue, subspaces and
    parameter descriptions). v1 is the S2 prompt, byte-identical; v2 adds the statements listed at PROMPT_VERSIONS and lists probes and
    subspaces in an order shuffled by `order_seed`."""
    v2 = prompt_version == "v2"
    probes = []
    for pid, spec in (_order(wp.PROBES.items(), order_seed) if v2 else wp.PROBES.items()):
        txt = _PROBE_TEXT[spec["kind"]].format(subspace=spec.get("subspace", ""),
                                               bp=", ".join(spec.get("body_params", ())), description=spec.get("description", ""))
        probes.append(f"- {pid}: {txt}." + (" Family 17 only." if pid == "opt_placement" else ""))
    subs = []
    for name, params in (_order(wo.SUBSPACES.items(), order_seed) if v2 else wo.SUBSPACES.items()):
        if name == "placement":
            subs.append(f"- placement (family 17 only): {_PLACEMENT_DOC}.")
        else:
            subs.append(f"- {name}: " + "; ".join(f"{p} = {r3.PARAM_DESCRIPTIONS[p]}" for p in params) + ".")
    bodies = [f"- {p}: {_BODY_DOC[p]}; ratio 0.5-1.5 of the current value, inside the {_guided_bounds(p)}." for p in wp.FIX_BODY_PARAMS]
    docs = [f"- {k}: {v}" for k, v in _STATIC_DOCS.items()]
    docs.append("- baseline.<k>: median over the diagnostic seeds of gait feature k (listed below); None values are omitted.")
    docs += [f"  - baseline.{k}: {v}" for k, v in gf.SUMMARY_DOCS.items()]
    if v2:
        docs.append("- creature.reference.features.<k>: the same feature for the REFERENCE body, the body for which the transferred "
                    "start controller was tuned (it walks there); compare with creature.features.<k>.")
    if v2:
        return "\n".join(_v2_sections(probes, subs, bodies, docs))
    return "\n".join([
        "You are the engineering director of a walking-recovery study. A planar (side-view, 2-D) two-legged creature with a phase-based "
        "gait controller (15 parameters; 17 in family 17) does not walk. You decide WHICH diagnostic experiments to run and WHICH subsystem "
        "of the creature to change, with what share of the remaining budget. A numeric optimiser (CMA-ES) then fits the parameters and MuJoCo "
        "measures the result. You never choose numeric parameter values and you never decide whether the creature has recovered.",
        "",
        "GOAL: the creature must genuinely walk: >= 80% of 24 held-out seeds under perturbation and friction variation, confirmed for 20 s. "
        "Small distance gains do not count. A final screening and a held-out validation, both outside your control, decide.",
        "",
        "BUDGET: one total rollout budget pays for everything: the start evaluation, every probe, every plan (also a failed or discarded one) "
        "and the final screening. A probe or plan is charged in full before it runs and unused rollouts are refunded. One candidate "
        "evaluation costs n_train rollouts (one per training seed). Plans must not exceed the remaining budget; a plan whose budget cannot "
        "pay one evaluation is rejected, and a rejected plan forfeits its share. Methods without a model get the same budget and the same "
        "information as you.",
        "",
        "ROUNDS: each round has a probe step and a plan step. Probes of a round run before its plans. budget_share is a fraction of the "
        "rollouts remaining when plans are decided (after that round's probes); shares of one round sum to at most 1; budget you do not spend "
        "stays available for later rounds. At most 3 probes and 2 plans per round, no repeated probe.",
        "",
        "PROBES (diagnostic experiments; the measured delta is relative to the unchanged creature on the training seeds):",
        *probes,
        "",
        "CONTROL SUBSPACES (a plan's ctrl_subspaces; the optimiser searches only these dimensions and keeps the others at the init's values):",
        *subs,
        "",
        "BODY PARAMETERS (a plan's body_params, at most 4; the leg ones change both legs by one ratio):",
        *bodies,
        "",
        "SEARCH SPACE TRADE-OFF: a smaller, well-chosen search space converges faster for the same budget but excludes everything outside it; "
        "a larger one includes more but needs more rollouts for the same progress. A plan's init is \"start\", or the id of a probe or plan "
        "that already ran with status ok; the search starts from that run's best candidate (its body and controller).",
        "",
        "HYPOTHESES: state hypotheses about WHY the creature does not walk. Ground each in evidence by citing evidence paths (copied exactly "
        "from the EVIDENCE lines) and give at least one competing explanation. A probe is a test of a hypothesis with an expected outcome: "
        "\"improves\" (best candidate beats the start) or \"no_change\". After the measurements, list in `refuted` the hypotheses the "
        "measurements contradict; a refuted hypothesis must not be pursued again without new evidence. Measurements, not hypotheses, count.",
        "",
        "PROCEDURE: you are called twice per round. Probe call: reply with `hypotheses` (1-3; ids as listed) and `probes` (0-3, each tied to a "
        "hypothesis with an expected outcome). Plan call: reply with `refuted`, a short updated `diagnosis` and `plans` (1-2: init, "
        "ctrl_subspaces, body_params, budget_share, hypothesis, prediction, evidence). A plan's hypothesis is a hypothesis that is not "
        "refuted, or \"none\" with its own evidence. Reply with ONE JSON object in the required format and nothing else.",
        "",
        "EVIDENCE: the user message lists `path = value` lines. Citations must be copied exactly from them. Documentation of the paths:",
        *docs,
    ])


def _v2_sections(probes, subs, bodies, docs) -> list[str]:
    return [
        "You are the engineering director of a walking-recovery study. A planar (side-view, 2-D) two-legged creature with a phase-based "
        "gait controller (15 parameters; 17 in family 17) does not walk. You decide WHICH diagnostic experiments to run and WHICH subsystems "
        "of the creature to change, with what share of the remaining budget. The creature has two kinds of changeable subsystems: its "
        "CONTROLLER (the control subspaces below) and its BODY (the body parameters below); a plan may search any control subspaces, any "
        "body parameters, or both together. A numeric optimiser (CMA-ES) then fits the chosen parameters jointly and MuJoCo measures the "
        "result. You never choose numeric parameter values and you never decide whether the creature has recovered.",
        "",
        "GOAL: the creature must genuinely walk: >= 80% of 24 held-out seeds under perturbation and friction variation, confirmed for 20 s. "
        "Small distance gains do not count. A final screening and a held-out validation, both outside your control, decide.",
        "",
        "BUDGET: one total rollout budget pays for everything: the start evaluation, every probe, every plan (also a failed or discarded one) "
        "and the final screening. A probe or plan is charged in full before it runs and unused rollouts are refunded. One candidate "
        "evaluation costs n_train rollouts (one per training seed). Plans must not exceed the remaining budget; a plan whose budget cannot "
        "pay one evaluation is rejected, and a rejected plan forfeits its share. Rollouts still unspent after the plans of the LAST round "
        "are wasted: they are not used for anything. Methods without a model get the same budget and the same information as you.",
        "",
        "ROUNDS: each round has a probe step and a plan step. Probes of a round run before its plans. budget_share is a fraction of the "
        "rollouts remaining when plans are decided (after that round's probes); shares of one round sum to at most 1; budget you do not spend "
        "in an earlier round stays available for later rounds. At most 3 probes and 2 plans per round, no repeated probe. The lists below "
        "are in no particular order.",
        "",
        "PROBES (diagnostic experiments; the measured delta is relative to the unchanged creature on the training seeds):",
        *probes,
        "",
        "CONTROL SUBSPACES (a plan's ctrl_subspaces; the optimiser searches only these dimensions and keeps the others at the init's values):",
        *subs,
        "",
        "BODY PARAMETERS (a plan's body_params, at most 4; the leg ones change both legs by one ratio; searched jointly with the plan's "
        "control subspaces):",
        *bodies,
        "",
        "SEARCH SPACE TRADE-OFF: a smaller, well-chosen search space converges faster for the same budget but excludes everything outside it; "
        "a larger one includes more but needs more rollouts for the same progress. A plan's init is \"start\", or the id of a probe or plan "
        "that already ran with status ok; the search starts from that run's best candidate (its body and controller).",
        "",
        "HYPOTHESES: state hypotheses about WHY the creature does not walk. Ground each in evidence by citing evidence paths (copied exactly "
        "from the EVIDENCE lines) and give at least one competing explanation. A probe is a test of a hypothesis with an expected outcome: "
        "\"improves\" (best candidate beats the start) or \"no_change\". After the measurements, list in `refuted` the hypotheses the "
        "measurements contradict; a refuted hypothesis must not be pursued again without new evidence. Measurements, not hypotheses, count.",
        "",
        "PROCEDURE: you are called twice per round. Probe call: reply with `hypotheses` (1-3; ids as listed) and `probes` (0-3, each tied to a "
        "hypothesis with an expected outcome). Plan call: reply with `refuted`, a short updated `diagnosis` and `plans` (1-2: init, "
        "ctrl_subspaces, body_params, budget_share, hypothesis, prediction, evidence). A plan's hypothesis is a hypothesis that is not "
        "refuted, or \"none\" with its own evidence. Reply with ONE JSON object in the required format and nothing else.",
        "",
        "EVIDENCE: the user message lists `path = value` lines. Citations must be copied exactly from them. Documentation of the paths:",
        *docs,
    ]


_REFERENCE_FEATURES: dict | None = None


def reference_features() -> dict:
    """creature_gen.features of the default SandboxBody (the body the R2 start controller was tuned on); cached."""
    global _REFERENCE_FEATURES
    if _REFERENCE_FEATURES is None:
        from . import creature_gen as cg
        from .sandbox import SandboxBody
        b = SandboxBody().as_dict()
        b["pose"] = list(b["pose"])
        _REFERENCE_FEATURES = _scalars(cg.features(b))
    return dict(_REFERENCE_FEATURES)


# ------------------------------------------------------------------------------------------------------------------ evidence
def _r(v):
    if isinstance(v, bool) or isinstance(v, int):
        return v
    if isinstance(v, float) and math.isfinite(v):
        return float(f"{v:.4g}")
    return v


def _scalar(v) -> bool:
    return isinstance(v, (bool, int, float, str)) and not (isinstance(v, float) and not math.isfinite(v))


def _scalars(d: dict, skip: Sequence[str] = ()) -> dict:
    return {k: _r(v) for k, v in d.items() if k not in skip and isinstance(k, str) and _scalar(v)}


EVIDENCE_MODES = ("full", "no_gait")


def build_evidence(state: dict) -> dict:
    """Flattened scalar evidence pack from a pipeline state (see module docstring for the layout)."""
    body = state["creature"]["body"]
    ev: dict = {"creature": {**_scalars(body), "features": _scalars(state["creature"].get("features") or {})}}
    base = _scalars((state["baseline"].get("gait") or {}))
    for field, pre in (("outcome", "outcome_"), ("label", "label_")):
        counts: dict[str, int] = {}
        for row in state["baseline"].get("outcomes") or []:
            v = row.get(field)
            if v is not None:
                k = pre + _SAFE.sub("_", str(v)).strip("_")
                counts[k] = counts.get(k, 0) + 1
        base.update(counts)
    ev["baseline"] = base
    ev["start"] = _scalars(state["start_score"])
    b = state["budget"]
    ev["budget"] = {"total": b["total"], "reserved_for_screening": b["reserved_for_screening"], "remaining": b["remaining"],
                    "n_train": state["n_train"], "round": state["round"], "rounds_total": state["rounds_total"],
                    "probe_cost": {p: state["probe_costs"][p] for p in state["available_probes"]}}
    probes = {}
    for p in state["probes_run"]:
        d = {"status": p["status"], "rollouts": p["rollouts"]}
        if p["status"] == "ok":
            bs = p["best_score"]
            d.update(best_walking_count=bs["walking_count"], best_survival_count=bs["survival_count"],
                     best_mean_fitness=_r(bs["mean_fitness"]), delta_walking=p["delta_walking"],
                     delta_mean_fitness=_r(p["delta_mean_fitness"]), improved=_improved(p))
        probes[p["probe_id"]] = d
    plans = {}
    for p in state["plans_run"]:
        d = {"status": p["status"], "budget": p["budget"]}
        if p["status"] == "ok":
            bs = p["best_score"]
            d.update(rollouts_used=p["rollouts_used"], best_walking_count=bs["walking_count"],
                     best_survival_count=bs["survival_count"], best_mean_fitness=_r(bs["mean_fitness"]),
                     delta_walking=p["improvement"]["delta_walking"], delta_mean_fitness=_r(p["improvement"]["delta_mean_fitness"]))
        plans[p["plan_id"]] = d
    if probes:
        ev["probes"] = probes
    if plans:
        ev["plans"] = plans
    return ev


def _improved(p: dict) -> bool:
    return (p["delta_walking"], p["delta_mean_fitness"]) > (0, 0.0)


def _fmt(v) -> str:
    return "true" if v is True else "false" if v is False else str(v)


def evidence_lines(evidence: dict) -> list[str]:
    return [f"{p} = {_fmt(v)}" for p, v in leaf_items(evidence, limit=10_000)]


# ------------------------------------------------------------------------------------------------------------------ schemas
def _str() -> dict:
    return {"type": "string"}


def _citations(paths: list[str]) -> dict:
    return {"type": "array", "items": {"type": "string", "enum": list(paths)}}


def probe_schema(paths: list[str], hyp_ids: list[str], all_hyp_ids: list[str], probe_ids: list[str]) -> dict:
    hyp = {"type": "object", "additionalProperties": False, "required": ["id", "mechanism", "evidence", "competing"],
           "properties": {"id": {"type": "string", "enum": list(hyp_ids)}, "mechanism": _str(), "evidence": _citations(paths),
                          "competing": {"type": "array", "items": _str()}}}
    probe = {"type": "object", "additionalProperties": False, "required": ["probe_id", "hypothesis", "expect"],
             "properties": {"probe_id": {"type": "string", "enum": list(probe_ids)},
                            "hypothesis": {"type": "string", "enum": list(all_hyp_ids)},
                            "expect": {"type": "string", "enum": list(EXPECTS)}}}
    return {"type": "object", "additionalProperties": False, "required": ["hypotheses", "probes"],
            "properties": {"hypotheses": {"type": "array", "items": hyp}, "probes": {"type": "array", "items": probe}}}


def plan_schema(paths: list[str], hyp_ids: list[str], refutable: list[str], inits: list[str], subspaces: list[str]) -> dict:
    plan = {"type": "object", "additionalProperties": False,
            "required": ["init", "ctrl_subspaces", "body_params", "budget_share", "hypothesis", "prediction", "evidence"],
            "properties": {"init": {"type": "string", "enum": list(inits)},
                           "ctrl_subspaces": {"type": "array", "items": {"type": "string", "enum": list(subspaces)}},
                           "body_params": {"type": "array", "items": {"type": "string", "enum": list(wp.FIX_BODY_PARAMS)}},
                           "budget_share": {"type": "number"},
                           "hypothesis": {"type": "string", "enum": list(hyp_ids) + [NO_HYPOTHESIS]},
                           "prediction": _str(), "evidence": _citations(paths)}}
    return {"type": "object", "additionalProperties": False, "required": ["refuted", "diagnosis", "plans"],
            "properties": {"refuted": {"type": "array", "items": {"type": "string", "enum": list(refutable) or ["(none open)"]}},
                           "diagnosis": _str(), "plans": {"type": "array", "items": plan}}}


# ------------------------------------------------------------------------------------------------------------------ validators
def _exact(obj, required: set, where: str, errs: list) -> bool:
    if not isinstance(obj, dict):
        errs.append(f"{where}: must be an object")
        return False
    extra, missing = sorted(set(obj) - required), sorted(required - set(obj))
    if extra:
        errs.append(f"{where}: unknown field(s) {extra}")
    if missing:
        errs.append(f"{where}: missing field(s) {missing}")
    return not extra and not missing


def _text(v, where: str, errs: list, required: bool = True) -> None:
    if not isinstance(v, str) or (required and not v.strip()):
        errs.append(f"{where}: must be a non-empty string")
    elif len(v) > TEXT_MAX:
        errs.append(f"{where}: longer than {TEXT_MAX} characters")


def _cites(v, where: str, paths: set, limit: int, errs: list) -> None:
    if not isinstance(v, list) or not v:
        errs.append(f"{where}: needs 1-{limit} evidence paths")
        return
    if len(v) > limit:
        errs.append(f"{where}: at most {limit} citations (got {len(v)})")
    for c in v:
        if not isinstance(c, str) or c not in paths:
            errs.append(f"{where}: citation {c!r} is not an evidence path (copy a path exactly from the EVIDENCE lines)")
    if len({c for c in v if isinstance(c, str)}) != len(v):
        errs.append(f"{where}: duplicate citations")


def validate_probe_reply(reply, *, paths: set, new_ids: list[str], live_ids: list[str], available: list[str]) -> tuple[list[str], list[dict]]:
    """(errors, probe ids requested in order). Empty errors = valid."""
    errs: list[str] = []
    if not _exact(reply, {"hypotheses", "probes"}, "reply", errs):
        return errs, []
    hyps, probes = reply["hypotheses"], reply["probes"]
    if not isinstance(hyps, list) or not isinstance(probes, list):
        return errs + ["reply: hypotheses and probes must be lists"], []
    lo = 0 if live_ids else 1
    if not lo <= len(hyps) <= MAX_HYPOTHESES_PER_CALL:
        errs.append(f"hypotheses: need {lo}-{MAX_HYPOTHESES_PER_CALL} hypotheses (got {len(hyps)})")
    seen: set = set()
    for i, h in enumerate(hyps):
        w = f"hypotheses[{i}]"
        if not _exact(h, {"id", "mechanism", "evidence", "competing"}, w, errs):
            continue
        if h["id"] not in new_ids:
            errs.append(f"{w}: id {h['id']!r} must be one of {new_ids}")
        elif h["id"] in seen:
            errs.append(f"{w}: duplicate id {h['id']!r}")
        seen.add(h["id"])
        _text(h["mechanism"], f"{w}.mechanism", errs)
        _cites(h["evidence"], f"{w}.evidence", paths, MAX_CITATIONS, errs)
        if not isinstance(h["competing"], list) or not h["competing"]:
            errs.append(f"{w}.competing: give at least one competing explanation")
        else:
            for j, c in enumerate(h["competing"]):
                _text(c, f"{w}.competing[{j}]", errs)
    known = set(live_ids) | seen
    if len(probes) > MAX_PROBES:
        errs.append(f"probes: at most {MAX_PROBES} (got {len(probes)})")
    ids = []
    for i, p in enumerate(probes):
        w = f"probes[{i}]"
        if not _exact(p, {"probe_id", "hypothesis", "expect"}, w, errs):
            continue
        if not isinstance(p["probe_id"], str) or p["probe_id"] not in wp.PROBES:
            errs.append(f"{w}: unknown probe {p['probe_id']!r}")
        elif p["probe_id"] not in available:
            errs.append(f"{w}: probe {p['probe_id']!r} is not available now (available: {available})")
        elif p["probe_id"] in ids:
            errs.append(f"{w}: probe {p['probe_id']!r} requested twice")
        else:
            ids.append(p["probe_id"])
        if p["hypothesis"] not in known:
            errs.append(f"{w}: hypothesis {p['hypothesis']!r} does not exist (known: {sorted(known)})")
        if p["expect"] not in EXPECTS:
            errs.append(f"{w}: expect must be one of {list(EXPECTS)}")
    return errs, ids


def validate_plan_reply(reply, *, paths: set, live_ids: list[str], refutable: list[str], family: int, runs: dict) -> list[str]:
    errs: list[str] = []
    if not _exact(reply, {"refuted", "diagnosis", "plans"}, "reply", errs):
        return errs
    ref, plans = reply["refuted"], reply["plans"]
    if not isinstance(ref, list) or not isinstance(plans, list):
        return errs + ["reply: refuted and plans must be lists"]
    _text(reply["diagnosis"], "diagnosis", errs)
    for i, r in enumerate(ref):
        if not isinstance(r, str) or r not in refutable:
            errs.append(f"refuted[{i}]: {r!r} is not an existing hypothesis that is still open (open: {refutable})")
    if len(set(map(str, ref))) != len(ref):
        errs.append("refuted: duplicate ids")
    if not 1 <= len(plans) <= MAX_PLANS:
        errs.append(f"plans: need 1-{MAX_PLANS} plans (got {len(plans)})")
    cum = 0.0
    for i, p in enumerate(plans):
        w = f"plans[{i}]"
        if not _exact(p, {"init", "ctrl_subspaces", "body_params", "budget_share", "hypothesis", "prediction", "evidence"}, w, errs):
            continue
        core = {k: p[k] for k in wp.PLAN_KEYS}
        errs += [f"{w}: {e}" for e in wp.validate_plan(core, family=family, runs=runs)]
        if isinstance(p["body_params"], list):
            off = [b for b in p["body_params"] if isinstance(b, str) and b not in wp.FIX_BODY_PARAMS]
            if off:
                errs.append(f"{w}: body parameter(s) {off} are not allowed here; allowed: {list(wp.FIX_BODY_PARAMS)}")
        h = p["hypothesis"]
        if h != NO_HYPOTHESIS and h not in live_ids:
            errs.append(f"{w}: hypothesis {h!r} is not an open hypothesis (open: {live_ids}; use {NO_HYPOTHESIS!r} with evidence)")
        if h in ref:
            errs.append(f"{w}: hypothesis {h!r} is listed in refuted; a refuted hypothesis must not be pursued")
        _text(p["prediction"], f"{w}.prediction", errs)
        _cites(p["evidence"], f"{w}.evidence", paths, MAX_PLAN_CITATIONS, errs)
        sh = p["budget_share"]
        if isinstance(sh, (int, float)) and not isinstance(sh, bool) and math.isfinite(float(sh)):
            cum += float(sh)
    if cum > 1.0 + SHARE_EPS:
        errs.append(f"plans: budget shares sum to {cum:.4g} > 1")
    return errs


# ------------------------------------------------------------------------------------------------------------------ scripted transport
class FixtureTransport:
    """Answers each request with the next fixture reply (a dict -> JSON text, or a str -> raw text). Nothing here is a model."""

    def __init__(self, fixture: Sequence):
        self.fixture = list(fixture)
        self.requests = 0

    def __call__(self, url, headers, body, timeout):
        from .nebius import NebiusError
        i = self.requests
        self.requests += 1
        if i >= len(self.fixture):
            raise NebiusError("scripted fixture exhausted")
        item = self.fixture[i]
        content = item if isinstance(item, str) else json.dumps(item)
        pt = estimate_prompt_tokens(body.get("messages", []))
        ct = max(1, len(content) // 3)
        raw = {"model": SCRIPTED_MODEL, "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
               "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct}}
        return 200, {"x-request-id": f"scripted-{i + 1}"}, raw


def scripted_ledger(path: Path | str | None = None) -> InferenceLedger:
    """Free scratch ledger for scripted runs (separate from the real one)."""
    p = Path(path) if path else Path(tempfile.mkdtemp(prefix="cf_director_")) / "scripted_inference_ledger.jsonl"
    return InferenceLedger(p, prices={SCRIPTED_MODEL: (0.0, 0.0)})


# ------------------------------------------------------------------------------------------------------------------ director
class NemotronDirector:
    """See module docstring. `ledger`: live default is `InferenceLedger()` at env CF_INFERENCE_LEDGER with per-investigation caps equal to
    max_requests / max_total_tokens (global caps unchanged); scripted default is a free scratch ledger."""

    def __init__(self, mode: str = "live", profile: str = "default", ledger: InferenceLedger | None = None,
                 investigation_id: str | None = None, transport=None, fixture: Sequence | None = None, max_requests: int = 8,
                 max_total_tokens: int = 160_000, config: ModelConfig | None = None, evidence_mode: str = "full",
                 prompt_version: str = "v1", order_seed: int | None = None):
        if prompt_version not in PROMPT_VERSIONS:
            raise ValueError(f"prompt_version must be one of {PROMPT_VERSIONS}, got {prompt_version!r}")
        self.prompt_version = prompt_version
        self.order_seed = order_seed if prompt_version == "v2" else None
        if evidence_mode not in EVIDENCE_MODES:
            raise ValueError(f"evidence_mode must be one of {EVIDENCE_MODES}, got {evidence_mode!r}")
        self.evidence_mode = evidence_mode
        if mode not in PROVENANCE:
            raise ValueError(f"mode must be one of {list(PROVENANCE)}, got {mode!r}")
        self.mode, self.profile = mode, profile
        # LIVE only if a real request can leave the machine; an injected transport (tests) is always labelled SCRIPTED_MOCK.
        self.provenance = PROVENANCE[mode] if mode == "scripted" or transport is None else PROVENANCE["scripted"]
        self.investigation_id = investigation_id or new_investigation_id()
        cfg = config or load_model_config(profile)
        self.api_key: str | None = None
        if mode == "scripted":
            cfg = dataclasses.replace(cfg, model=SCRIPTED_MODEL)
            if transport is None:
                if fixture is None:
                    raise ValueError("scripted mode needs a fixture (list of reply dicts) or a transport")
                transport = FixtureTransport(fixture)
            self.ledger = ledger or scripted_ledger()
            self.client = make_client(cfg, transport=transport, api_key="scripted-no-key", base_url="http://scripted.invalid",
                                      max_requests=max_requests, max_total_tokens=max_total_tokens)
        else:
            if ledger is None:
                ledger = InferenceLedger(caps=Caps(inv_max_requests=max_requests, inv_max_tokens=max_total_tokens))
            reason = live_refusal(ledger, cfg)
            if reason:
                raise LiveRefused(reason)
            self.ledger = ledger
            self.client = make_client(cfg, transport=transport, max_requests=max_requests, max_total_tokens=max_total_tokens)
            self.api_key = self.client.api_key
        self.cfg = cfg
        self.max_requests, self.max_total_tokens = max_requests, max_total_tokens
        self.fixture_used = isinstance(transport, FixtureTransport)
        self._transport = transport
        self.system = build_system_prompt(prompt_version, self.order_seed)
        self.calls: list[dict] = []
        self.decisions: list[dict] = []
        self.hypotheses: dict[str, dict] = {}
        self.expectations: dict[str, dict] = {}
        self.plan_meta: dict[str, dict] = {}
        self.refuted_by_round: dict[str, list[str]] = {}

    # ---------------------------------------------------------------------------------------------- shared machinery
    def _evidence(self, state: dict) -> dict:
        """The evidence pack; evidence_mode "no_gait" (an information ablation, H6) removes the baseline gait-feature
        summary and keeps only the baseline outcome / label counts."""
        ev = build_evidence(state)
        if self.prompt_version == "v2":
            ev["creature"]["reference"] = {"features": reference_features()}
            pc = ev["budget"]["probe_cost"]
            ev["budget"]["probe_cost"] = {k: pc[k] for k in _order(list(pc), self.order_seed)}
        if self.evidence_mode == "no_gait":
            ev["baseline"] = {k: v for k, v in ev["baseline"].items() if k.startswith(("outcome_", "label_"))}
        return ev

    def _clean(self, text) -> str:
        return redact_secret(str(text), self.api_key)

    def _live_ids(self) -> list[str]:
        return [h for h, d in self.hypotheses.items() if not d["refuted"]]

    def _user(self, state: dict, evidence: dict, task: str) -> str:
        b = state["budget"]
        head = [f"ROUND {state['round']} of {state['rounds_total']}. FAMILY {state['family']}: "
                + ("the controller has 17 parameters; the placement subspace (fp_kd, fp_kv) is allowed."
                   if state["family"] == 17 else "the controller has 15 parameters; the placement subspace is NOT available."),
                f"Remaining budget {b['remaining']} of {b['total']} rollouts ({b['reserved_for_screening']} reserved for screening); "
                f"n_train = {state['n_train']}.",
                "", "EVIDENCE:", *evidence_lines(evidence)]
        if self.hypotheses:
            head += ["", "YOUR HYPOTHESES SO FAR:"]
            for h, d in self.hypotheses.items():
                head.append(f"{h} [round {d['round']}, {'REFUTED in round ' + str(d['refuted_round']) if d['refuted'] else 'open'}]: "
                            f"{d['mechanism']} (cites {', '.join(d['evidence'])}; competing: {'; '.join(d['competing'])})")
        if state["round"] > 1 or task == "plans":
            ran = []
            for pid, e in self.expectations.items():
                ran.append(f"probe {pid}: you expected {e['expect']} (for {e['hypothesis']})")
            for pid, m in self.plan_meta.items():
                ran.append(f"plan {pid}: init {m['init']}, subspaces {m['ctrl_subspaces'] or '-'}, body {m['body_params'] or '-'}, "
                           f"share {m['budget_share']}, for {m['hypothesis']}; predicted: {m['prediction']}")
            if ran:
                head += ["", "WHAT YOU DECIDED EARLIER:", *ran]
        head += ["", {"probes": "TASK: probe call. Reply with `hypotheses` and `probes` (ids and options are in the response schema).",
                      "plans": "TASK: plan call. Reply with `refuted`, `diagnosis` and `plans`."}[task]]
        return "\n".join(head)

    def _repair_messages(self, messages: list, first: ModelCall, errors: list[str]) -> list:
        shown = [self._clean(e)[:300] for e in errors[:REPAIR_ERRORS_MAX]]
        more = f"\n(+{len(errors) - len(shown)} more)" if len(errors) > len(shown) else ""
        prompt = ("Your previous reply was rejected by the validator:\n- " + "\n- ".join(shown) + more +
                  "\nReturn ONE corrected JSON object in the same format, following every rule (ids and values exactly as in the response "
                  "schema, citations copied exactly from the EVIDENCE lines). No prose.")
        return messages + [{"role": "assistant", "content": (first.content or "")[:REPAIR_ECHO_MAX]}, {"role": "user", "content": prompt}]

    def _send(self, messages: list, schema: dict, name: str, purpose: str) -> tuple[ModelCall, int]:
        cfg = self.cfg
        call = None
        try:
            call = call_model(self.client, cfg, messages, self.ledger, investigation_id=self.investigation_id, purpose=purpose,
                              response_schema=schema)
        except Exception as e:      # noqa: BLE001 - recorded as a failed call, never raised into the pipeline
            call = ModelCall(cfg.model, {"purpose": purpose, "investigation_id": self.investigation_id}, "", messages)
            call.error = self._clean(f"{type(e).__name__}: {e}")[:400]
        rec = call.as_dict()
        rec["error"] = None if rec["error"] is None else self._clean(rec["error"])
        rec["schema_name"] = name
        self.calls.append(rec)
        return call, len(self.calls) - 1

    def _ask(self, kind: str, rnd: int, messages: list, schema: dict, validate) -> dict:
        """One call plus at most one repair. `validate(reply) -> (errors, extra)`. Returns the decision record (with `ok`, `reply`, `extra`)."""
        dec = {"kind": kind, "round": rnd, "calls": [], "parsed": None, "first_attempt_errors": [], "validation_errors": [],
               "repaired": False, "status": "ok", "returned": []}
        name = SCHEMA_PROBES if kind == "probes" else SCHEMA_PLANS

        def assess(call: ModelCall):
            try:
                reply = parse_reply(call.content)
            except ValueError as e:
                return None, [str(e)], None
            errs, extra = validate(reply)
            return reply, errs, extra

        call, idx = self._send(messages, schema, name, f"director_{kind}")
        dec["calls"].append(idx)
        if not call.ok:
            dec.update(status="model_failed", validation_errors=[self._clean(call.error or "no content")])
            return dec
        reply, errs, extra = assess(call)
        dec["parsed"] = reply
        if errs:
            dec["first_attempt_errors"] = [self._clean(e) for e in errs]
            dec["repaired"] = True
            call2, idx2 = self._send(self._repair_messages(messages, call, errs), schema, name, "director_repair")
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

    def _finish(self, dec: dict, returned: list) -> list:
        dec.pop("reply", None)
        dec.pop("extra", None)
        dec["returned"] = copy.deepcopy(returned)
        self.decisions.append(dec)
        return returned

    # ---------------------------------------------------------------------------------------------- the director interface
    def choose_probes(self, state: dict) -> list:
        rnd = state["round"]
        try:
            return self._choose_probes(state, rnd)
        except Exception as e:      # noqa: BLE001 - a bug here must not crash the pipeline; recorded, no decision substituted
            return self._finish({"kind": "probes", "round": rnd, "calls": [], "parsed": None, "first_attempt_errors": [], "repaired": False,
                                 "status": "director_error", "validation_errors": [self._clean(f"{type(e).__name__}: {e}")]}, [])

    def _choose_probes(self, state: dict, rnd: int) -> list:
        evidence = self._evidence(state)
        paths = leaf_paths(evidence, limit=10_000)
        n = max([int(h[1:]) for h in self.hypotheses] or [0])
        new_ids = [f"H{n + i}" for i in range(1, MAX_HYPOTHESES_PER_CALL + 1)]
        live = self._live_ids()
        avail = list(state["available_probes"])
        if self.prompt_version == "v2":
            avail = _order(avail, self.order_seed)
        schema = probe_schema(paths, new_ids, live + new_ids, avail or ["(none available)"])
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": self._user(state, evidence, "probes")}]
        pset = set(paths)
        dec = self._ask("probes", rnd, messages, schema,
                        lambda r: validate_probe_reply(r, paths=pset, new_ids=new_ids, live_ids=live, available=avail))
        if dec["status"] != "ok":
            return self._finish(dec, [])
        reply, ids = dec["reply"], dec["extra"]
        for h in reply["hypotheses"]:
            self.hypotheses[h["id"]] = {"round": rnd, "mechanism": h["mechanism"], "evidence": list(h["evidence"]),
                                        "competing": list(h["competing"]), "refuted": False, "refuted_round": None}
        for p in reply["probes"]:
            self.expectations[p["probe_id"]] = {"hypothesis": p["hypothesis"], "expect": p["expect"], "round": rnd}
        return self._finish(dec, list(ids))

    def choose_plans(self, state: dict) -> list:
        rnd = state["round"]
        try:
            return self._choose_plans(state, rnd)
        except Exception as e:      # noqa: BLE001
            return self._finish({"kind": "plans", "round": rnd, "calls": [], "parsed": None, "first_attempt_errors": [], "repaired": False,
                                 "status": "director_error", "validation_errors": [self._clean(f"{type(e).__name__}: {e}")]}, [])

    def _choose_plans(self, state: dict, rnd: int) -> list:
        evidence = self._evidence(state)
        paths = leaf_paths(evidence, limit=10_000)
        live = self._live_ids()
        runs = {p["probe_id"]: 1 for p in state["probes_run"] if p["status"] == "ok"}
        runs.update({p["plan_id"]: 1 for p in state["plans_run"] if p["status"] == "ok"})
        subs = [s for s in wo.SUBSPACES if s != "placement" or state["family"] == 17]
        if self.prompt_version == "v2":
            subs = _order(subs, self.order_seed)
        schema = plan_schema(paths, live, live, ["start"] + sorted(runs), subs)
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": self._user(state, evidence, "plans")}]
        pset = set(paths)
        dec = self._ask("plans", rnd, messages, schema,
                        lambda r: (validate_plan_reply(r, paths=pset, live_ids=live, refutable=live, family=state["family"], runs=runs), None))
        if dec["status"] != "ok":
            return self._finish(dec, [])
        reply = dec["reply"]
        out = []
        for i, p in enumerate(reply["plans"]):
            out.append({"init": p["init"], "ctrl_subspaces": list(p["ctrl_subspaces"]), "body_params": list(p["body_params"]),
                        "budget_share": p["budget_share"], "rationale": f"{p['hypothesis']}: {p['prediction']}"})
            self.plan_meta[f"r{rnd}p{i}"] = {"init": p["init"], "ctrl_subspaces": list(p["ctrl_subspaces"]),
                                             "body_params": list(p["body_params"]), "budget_share": p["budget_share"],
                                             "hypothesis": p["hypothesis"], "prediction": p["prediction"], "evidence": list(p["evidence"])}
        for h in reply["refuted"]:
            self.hypotheses[h]["refuted"], self.hypotheses[h]["refuted_round"] = True, rnd
        self.refuted_by_round[str(rnd)] = list(reply["refuted"])
        dec["diagnosis"] = reply["diagnosis"]
        return self._finish(dec, out)

    # ---------------------------------------------------------------------------------------------- record
    def record(self) -> dict:
        tok = {"prompt": 0, "completion": 0}
        for c in self.calls:
            u = c.get("usage") or {}
            tok["prompt"] += int(u.get("prompt_tokens") or 0)
            tok["completion"] += int(u.get("completion_tokens") or 0)
        rec = {"version": VERSION, "provenance": self.provenance, "model": self.cfg.model, "profile": self.profile,
               "investigation_id": self.investigation_id, "evidence_mode": self.evidence_mode,
               "prompt_version": self.prompt_version, "order_seed": self.order_seed,
               "settings": {"temperature": self.cfg.temperature, "max_tokens": self.cfg.max_tokens,
                            "reasoning_effort": self.cfg.reasoning_effort, "json_schema": self.cfg.json_schema,
                            "extra_body": copy.deepcopy(self.cfg.extra_body), "timeout_s": self.cfg.timeout_s,
                            "max_requests": self.max_requests, "max_total_tokens": self.max_total_tokens},
               "system_prompt": self.system, "calls": copy.deepcopy(self.calls), "decisions": copy.deepcopy(self.decisions),
               "hypotheses": copy.deepcopy(self.hypotheses), "plan_meta": copy.deepcopy(self.plan_meta),
               "expectations": copy.deepcopy(self.expectations), "refuted_by_round": copy.deepcopy(self.refuted_by_round),
               "cost_usd": sum(float(c.get("cost_usd") or 0.0) for c in self.calls), "tokens": tok}
        text = json.dumps(rec)      # must be JSON-safe
        if self.api_key and self.api_key in text:
            raise RuntimeError("API key found in the director record; refusing to return it")
        return json.loads(text)
