"""R3 - Nemotron-guided physical investigation of a locomotion controller (DESIGN + OFFLINE MACHINERY; no live model calls).

A model never gets credit for text. It proposes bounded edits to a frozen controller's normalised parameters; MuJoCo
decides (creature_forge.r2 job/ledger machinery); matched random, heuristic and no-evidence baselines are scored the same
way. See docs/R3_DESIGN.md. Nothing here performs a network call: the Nebius client is injected and tests use a scripted
transport. An "accepted" status exists only for a proposal whose measured MuJoCo outcome met the registered criterion.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

import numpy as np

from . import r2
from .investigator import InvalidModelOutput, extract_json, resolve_path
from .nebius import BudgetExceeded, NebiusClient, NebiusError, estimate_prompt_tokens
from .phasegait_init import LOWER15, UPPER15

PARAM_NAMES = ("freq", "duty", "hip_amp", "knee_amp", "knee_shift", "stance_knee", "hip_bias", "kp", "kd", "balance_gain",
               "pitch_kp", "pitch_ref", "sync_gain", "ramp_s", "start_lean")
PARAM_DESCRIPTIONS = {
    "freq": "gait frequency (Hz)", "duty": "stance duty fraction", "hip_amp": "hip swing amplitude (rad)",
    "knee_amp": "knee flexion amplitude (rad)", "knee_shift": "knee phase shift (rad)", "stance_knee": "stance-leg knee bias (rad)",
    "hip_bias": "hip bias (rad)", "kp": "joint position gain", "kd": "joint damping gain",
    "balance_gain": "ankle balance feedback gain", "pitch_kp": "stance torso-pitch feedback gain", "pitch_ref": "torso pitch reference (rad)",
    "sync_gain": "contact-informed phase sync gain", "ramp_s": "start-up amplitude ramp duration (s)",
    "start_lean": "extra forward pitch reference at start, decays over 1 s (rad)"}
MAX_EDITS = 4
MAX_ABS_DELTA_U = 0.15
PROPOSALS_PER_REQUEST = 4
MIN_CITATIONS = 2
MIN_GAIN_RANGE = (1, 8)
PREDICTION_METRIC = "walking_seeds_screen"
R3_RNG_BASE = 20261016


# ----------------------------------------------------------------------------------------------------------
# proposal schema (strict; no repair, no heuristics)
# ----------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Proposal:
    claim: str
    cited_evidence: tuple[str, ...]
    edits: tuple[tuple[str, float], ...]          # (parameter, delta in normalised units)
    min_gain_seeds: int
    confidence: float

    def as_dict(self) -> dict:
        return {"claim": self.claim, "cited_evidence": list(self.cited_evidence),
                "edits": [{"parameter": p, "delta_u": d} for p, d in self.edits],
                "prediction": {"metric": PREDICTION_METRIC, "direction": "increase", "min_gain_seeds": self.min_gain_seeds},
                "confidence": self.confidence}


def _exact(obj, keys: set, where: str) -> dict:
    if not isinstance(obj, dict):
        raise InvalidModelOutput(f"{where} must be an object")
    extra, missing = set(obj) - keys, keys - set(obj)
    if extra:
        raise InvalidModelOutput(f"{where}: unknown field(s) {sorted(extra)}")
    if missing:
        raise InvalidModelOutput(f"{where}: missing field(s) {sorted(missing)}")
    return obj


def _num(v, where):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise InvalidModelOutput(f"{where} must be a finite number")
    return float(v)


def parse_proposal(obj, evidence: dict | None) -> Proposal:
    """Validate ONE proposal. `evidence` None = the no-evidence ablation: citations must then be an empty list."""
    o = _exact(obj, {"claim", "cited_evidence", "edits", "prediction", "confidence"}, "proposal")
    claim = o["claim"]
    if not isinstance(claim, str) or not (10 <= len(claim.strip()) <= 400):
        raise InvalidModelOutput("claim must be a string of 10..400 characters")
    cites = o["cited_evidence"]
    if not isinstance(cites, list) or not all(isinstance(c, str) for c in cites):
        raise InvalidModelOutput("cited_evidence must be a list of strings")
    if evidence is None:
        if cites:
            raise InvalidModelOutput("no evidence was provided; cited_evidence must be []")
    else:
        if len(set(cites)) < MIN_CITATIONS:
            raise InvalidModelOutput(f"at least {MIN_CITATIONS} distinct evidence paths must be cited")
        for c in cites:
            try:
                leaf = resolve_path(evidence, c)
            except (KeyError, IndexError, ValueError, TypeError):
                raise InvalidModelOutput(f"cited evidence path does not resolve: {c!r}") from None
            if isinstance(leaf, (dict, list)):
                raise InvalidModelOutput(f"cited evidence path must point to a value, not a container: {c!r}")
    edits = o["edits"]
    if not isinstance(edits, list) or not (1 <= len(edits) <= MAX_EDITS):
        raise InvalidModelOutput(f"edits must be a list of 1..{MAX_EDITS} items")
    seen, parsed = set(), []
    for i, e in enumerate(edits):
        e = _exact(e, {"parameter", "delta_u"}, f"edits[{i}]")
        p = e["parameter"]
        if p not in PARAM_NAMES:
            raise InvalidModelOutput(f"edits[{i}]: unknown parameter {p!r}")
        if p in seen:
            raise InvalidModelOutput(f"edits[{i}]: parameter {p!r} edited twice")
        seen.add(p)
        d = _num(e["delta_u"], f"edits[{i}].delta_u")
        if d == 0.0 or abs(d) > MAX_ABS_DELTA_U:
            raise InvalidModelOutput(f"edits[{i}].delta_u must be nonzero with |delta| <= {MAX_ABS_DELTA_U}")
        parsed.append((p, d))
    pr = _exact(o["prediction"], {"metric", "direction", "min_gain_seeds"}, "prediction")
    if pr["metric"] != PREDICTION_METRIC or pr["direction"] != "increase":
        raise InvalidModelOutput(f"prediction must be metric {PREDICTION_METRIC!r}, direction 'increase'")
    g = pr["min_gain_seeds"]
    if isinstance(g, bool) or not isinstance(g, int) or not (MIN_GAIN_RANGE[0] <= g <= MIN_GAIN_RANGE[1]):
        raise InvalidModelOutput(f"prediction.min_gain_seeds must be an integer in {MIN_GAIN_RANGE}")
    conf = _num(o["confidence"], "confidence")
    if not (0.0 <= conf <= 1.0):
        raise InvalidModelOutput("confidence must be within [0, 1]")
    return Proposal(claim.strip(), tuple(cites), tuple(parsed), int(g), conf)


def parse_response(text: str | None, evidence: dict | None) -> tuple[list[Proposal], list[dict]]:
    """Returns (valid proposals, invalid proposal records). A malformed envelope raises InvalidModelOutput (whole request invalid)."""
    data = extract_json(text)
    o = _exact(data, {"proposals"}, "reply")
    items = o["proposals"]
    if not isinstance(items, list) or not (1 <= len(items) <= PROPOSALS_PER_REQUEST):
        raise InvalidModelOutput(f"proposals must be a list of 1..{PROPOSALS_PER_REQUEST} items")
    ok, bad = [], []
    for i, it in enumerate(items):
        try:
            ok.append(parse_proposal(it, evidence))
        except InvalidModelOutput as e:
            bad.append({"slot": i, "reason": str(e)})
    return ok, bad


# ----------------------------------------------------------------------------------------------------------
# applying a proposal; baselines
# ----------------------------------------------------------------------------------------------------------
def apply_edits(theta0, edits) -> list[float]:
    u = r2.to_u(theta0).copy()
    for p, d in edits:
        u[PARAM_NAMES.index(p)] += d
    return r2.from_u(r2.reflect(u)).tolist()


def proposal_vector(theta0, prop: Proposal) -> list[float]:
    return apply_edits(theta0, prop.edits)


def matched_random_edits(model_edits, seed_parts: list[int]) -> list[tuple[str, float]]:
    """Same number of edits and the same multiset of |delta_u| as the model's proposal; random distinct parameters, random signs.
    Matches size, not content, so any difference in outcomes is about WHICH parameters/directions were chosen."""
    rng = np.random.default_rng(np.random.SeedSequence([R3_RNG_BASE, *seed_parts]))
    params = rng.choice(len(PARAM_NAMES), size=len(model_edits), replace=False)
    signs = rng.choice([-1.0, 1.0], size=len(model_edits))
    return [(PARAM_NAMES[int(j)], float(s * abs(d))) for j, s, (_, d) in zip(params, signs, model_edits)]


HEURISTIC_RULE = ("Derived from docs/PHASE2A_FAILURE_DIAGNOSIS.md (pre-R2): the failures are start-up failures to establish forward "
                  "stepping with backward lean, so (i) lean forward at start, (ii) lengthen the start-up ramp, (iii) raise the pitch "
                  "reference. Fires only if at least half of the failing evidence seeds have <= 1 valid step. Written by the authors "
                  "knowing the R2 outcome: a knowledgeable baseline, not a blind one.")
HEURISTIC_EDITS = (
    (("start_lean", 0.10),), (("start_lean", 0.15),), (("ramp_s", 0.10),), (("start_lean", 0.10), ("ramp_s", 0.10)),
)


def heuristic_proposals(evidence: dict) -> list[tuple[tuple[str, float], ...]]:
    fails = evidence.get("failing_seeds", [])
    if not fails or sum(f["valid_steps"] <= 1 for f in fails) * 2 < len(fails):
        return []                                                     # abstains
    return [tuple(e) for e in HEURISTIC_EDITS]


# ----------------------------------------------------------------------------------------------------------
# evidence (observed MuJoCo facts only) and prompts
# ----------------------------------------------------------------------------------------------------------
SEED_FIELDS = ("seed", "label", "fell", "fall_time", "fall_pitch", "valid_steps", "backward_steps", "touchdowns", "speed_upright",
               "forward_disp_upright", "max_abs_pitch", "mean_pitch", "min_torso_height", "single_support_frac", "mean_stance_s",
               "mean_swing_s", "raw_touchdown_rate", "violations")


def _r(x):
    return round(x, 4) if isinstance(x, float) and math.isfinite(x) else x


def build_evidence(theta, per_seed: list[dict], n_fail: int = 6, n_walk: int = 3) -> dict:
    """Observed evidence for a controller from its per-seed locomotion metrics (compute_metrics output). Seeds are ordered by
    seed number, never by outcome, within each class; each seed carries the initial perturbation that the seed induces."""
    from .r1 import initial_perturbation
    u = r2.to_u(theta)
    controller = {n: {"value": _r(float(theta[i])), "lower": float(LOWER15[i]), "upper": float(UPPER15[i]), "u": _r(float(u[i])),
                      "meaning": PARAM_DESCRIPTIONS[n]} for i, n in enumerate(PARAM_NAMES)}

    def row(m):
        d = {k: _r(m.get(k)) for k in SEED_FIELDS}
        d["initial_perturbation_rad"] = {k: _r(v) for k, v in initial_perturbation(m["seed"]).items()}
        return d

    ordered = sorted(per_seed, key=lambda m: m["seed"])
    fails = [m for m in ordered if not m["walking"]]
    walks = [m for m in ordered if m["walking"]]
    labels: dict[str, int] = {}
    for m in ordered:
        labels[m["label"]] = labels.get(m["label"], 0) + 1
    return {"controller": controller,
            "episode": {"duration_s": r2.DURATION, "initial_state": "torso pitch and 6 joint angles ~ N(0, 0.03 rad) set by the seed"},
            "summary": {"n_seeds": len(ordered), "walking_seeds": len(walks), "fell_seeds": sum(bool(m["fell"]) for m in ordered), "labels": labels},
            "failing_seeds": [row(m) for m in fails[:n_fail]], "walking_seeds": [row(m) for m in walks[:n_walk]]}


SYSTEM_PROMPT = (
    "You are the Physics Investigator for a MuJoCo planar-biped locomotion tool. A frozen phase-based walking controller fails to "
    "walk (every walking gate) on some random initial conditions. You propose bounded edits to its 15 normalised parameters that you "
    "predict will make it walk on MORE seeds. A deterministic MuJoCo experiment on unseen seeds judges you; your opinion is never "
    "the verdict, and you are scored against random and rule-based baselines. Reply with ONE JSON object and nothing else: "
    '{"proposals": [ ... up to 4 items ... ]}. Each item has exactly: "claim" (10-400 chars: the mechanism you suspect), '
    '"cited_evidence" (list of at least 2 DISTINCT dotted paths into the OBSERVED EVIDENCE, each pointing to a single number or '
    'string, e.g. "failing_seeds.0.fall_time" or "controller.pitch_ref.u"), "edits" (1-4 items {"parameter": one of the 15 names, '
    '"delta_u": a nonzero number with |delta_u| <= 0.15, a change in normalised units where u=(value-lower)/(upper-lower)}, each '
    'parameter at most once), "prediction" ({"metric": "walking_seeds_screen", "direction": "increase", "min_gain_seeds": integer '
    '1-8}) and "confidence" (0-1). Propose different edits for different items. Do not claim certainty you cannot have.')
SYSTEM_PROMPT_NO_EVIDENCE = (
    SYSTEM_PROMPT.replace("some random initial conditions.", "some random initial conditions; you are given NO measurements, only the parameter table.")
    .replace('"cited_evidence" (list of at least 2 DISTINCT dotted paths into the OBSERVED EVIDENCE, each pointing to a single number or '
             'string, e.g. "failing_seeds.0.fall_time" or "controller.pitch_ref.u")', '"cited_evidence" (must be the empty list [])'))


def parameter_table() -> dict:
    return {n: {"lower": float(LOWER15[i]), "upper": float(UPPER15[i]), "meaning": PARAM_DESCRIPTIONS[n]} for i, n in enumerate(PARAM_NAMES)}


def build_messages(evidence: dict | None, theta=None) -> list[dict]:
    if evidence is None:
        user = "PARAMETER TABLE (no measurements are provided):\n" + json.dumps(parameter_table(), sort_keys=True, separators=(",", ":"))
        return [{"role": "system", "content": SYSTEM_PROMPT_NO_EVIDENCE}, {"role": "user", "content": user}]
    user = "OBSERVED EVIDENCE (MuJoCo measurements):\n" + json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def prompt_sha256(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def estimate_tokens(messages: list[dict], max_tokens: int, n_requests: int) -> dict:
    """Pre-registered request/token ceiling (no network). Cost needs the per-million-token prices, which are NOT verified."""
    per_req = estimate_prompt_tokens(messages) + max_tokens
    return {"requests": n_requests, "prompt_tokens_estimate_each": estimate_prompt_tokens(messages), "max_completion_tokens_each": max_tokens,
            "total_tokens_ceiling": per_req * n_requests,
            "cost_usd_at_assumed_price_per_million_tokens": {str(p): round(per_req * n_requests * p / 1e6, 4) for p in (0.25, 1.0, 5.0)},
            "note": "token prices for this model were not verifiable from the public docs; the three figures bracket plausible list prices"}


# ----------------------------------------------------------------------------------------------------------
# one counted model request -> an honest record (never fabricates; invalid output stays invalid)
# ----------------------------------------------------------------------------------------------------------
@dataclass
class RequestRecord:
    arm: str                                    # "M" evidence, "N" no-evidence ablation
    request_index: int
    status: str                                 # ok | invalid_response | model_error | budget_exceeded
    prompt_sha256: str
    call: dict | None = None                    # redacted metadata (no credentials)
    raw_reply: str | None = None                # untrusted model text
    reason: str | None = None
    proposals: list = field(default_factory=list)       # validated Proposal dicts
    invalid_proposals: list = field(default_factory=list)
    slots_requested: int = PROPOSALS_PER_REQUEST

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def request_proposals(client: NebiusClient, arm: str, request_index: int, evidence: dict | None, *, max_tokens: int = 2048,
                      temperature: float = 0.7, reasoning_effort: str | None = None) -> RequestRecord:
    """Exactly one chat request (the client never retries). `temperature` > 0 so repeated requests can differ; the value is recorded."""
    messages = build_messages(evidence)
    rec = RequestRecord(arm, request_index, "ok", prompt_sha256(messages))
    try:
        res = client.chat(messages, max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort)
    except BudgetExceeded as e:
        rec.status, rec.reason = "budget_exceeded", str(e)
        return rec
    except NebiusError as e:
        rec.status, rec.reason = "model_error", str(e)[:300]
        rec.call = client.calls[-1] if client.calls else None
        return rec
    rec.call, rec.raw_reply = res.record(), res.content
    try:
        ok, bad = parse_response(res.content, evidence)
    except InvalidModelOutput as e:
        rec.status = "invalid_response"
        rec.reason = str(e) + (" (finish_reason=length)" if res.finish_reason == "length" else "")
        return rec
    rec.proposals = [p.as_dict() for p in ok]
    rec.invalid_proposals = bad
    return rec


# ----------------------------------------------------------------------------------------------------------
# scripted transport (tests, dry-run): an OpenAI-compatible response without any network
# ----------------------------------------------------------------------------------------------------------
def scripted_transport(replies: list, usage=(900, 400)):
    """`replies`: strings (message content), None (null content) or Exception instances (raised). Cycles are NOT used: running out is an error."""
    it = iter(replies)

    def transport(url, headers, body, timeout):
        try:
            r = next(it)
        except StopIteration:
            raise NebiusError("scripted transport exhausted") from None
        if isinstance(r, Exception):
            raise r
        pt, ct = usage
        return 200, {"x-request-id": "scripted"}, {"model": "scripted-model", "choices": [{"finish_reason": "stop", "message": {"content": r}}],
                                                    "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct}}
    return transport


# ----------------------------------------------------------------------------------------------------------
# outcome bookkeeping (physics decides)
# ----------------------------------------------------------------------------------------------------------
IMPROVE_MIN_GAIN = 2          # screening: >= 2 more walking seeds (of 16) than the base controller
VALIDATED_MIN_GAIN = 5        # validation: >= 5 more of 64 (the R2 gate size)


def outcome(base_walking: int, cand_walking: int, predicted_min_gain: int | None = None) -> dict:
    gain = cand_walking - base_walking
    out = {"gain_seeds": gain, "improved": bool(gain >= IMPROVE_MIN_GAIN)}
    if predicted_min_gain is not None:
        out["prediction_met"] = bool(gain >= predicted_min_gain)
    return out


def wilson_ci(k: int, n: int):
    from .r1_stats import wilson
    return wilson(k, n)
