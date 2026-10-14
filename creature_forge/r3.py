"""R3 - Nemotron-guided physical investigation of a frozen locomotion controller (protocol id phase2a-r3-protocol-v1).

A model never gets credit for text. It proposes bounded edits to the normalised parameters of the frozen incumbent theta0;
MuJoCo decides (R2's job/Executor machinery with R3's own caps and ledger). Matched-random, heuristic and no-measurement
controls are scored identically. Design: docs/R3_DESIGN.md; immutable protocol: experiments/phase2a_r3/protocol.json.

Methodological controls (each has a test in tests/test_r3.py):
 * the no-measurement control sees exactly the same controller table (values, bounds, meanings, u) and episode description;
   the ONLY difference is the presence of measured MuJoCo evidence;
 * 15 evidence contexts are fixed from theta0's evidence-pool outcomes before any request; prompts are frozen and hashed;
 * the primary endpoint uses all 4 allocated slots per request (invalid/empty = failure) and a paired request-block exact
   sign-flip test over the 15 blocks; each slot's matched-random counterpart is generated from a stream fixed in advance;
 * comparators are generated and frozen BEFORE any candidate is simulated; screening outcomes never feed back into anything;
 * requested AND realised (after boundary reflection) edit magnitudes are recorded for auditing the matching.
No network access happens in this module except through the injected Nebius client.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import phase2a, r1, r2
from .investigator import InvalidModelOutput, extract_json, resolve_path
from .nebius import BudgetExceeded, NebiusClient, NebiusError, estimate_prompt_tokens
from .optimize import Executor, jsonable
from .phasegait_init import LOWER15, UPPER15

ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = ROOT / "experiments" / "phase2a_r3"
RESULTS = EXP_DIR / "results"
PROTOCOL = EXP_DIR / "protocol.json"
LEDGER = RESULTS / "ledger.jsonl"
CONTEXTS = RESULTS / "contexts.json"
CANDIDATES = RESULTS / "candidates.json"
REQUESTS = RESULTS / "requests.jsonl"
PROTOCOL_ID = "phase2a-r3-protocol-v1"
MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

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
SLOTS = 4                           # allocated proposal slots per request (the primary endpoint uses all of them)
BLOCKS = 15                         # evidence contexts = request blocks per model arm
MIN_CITATIONS = 2
MIN_GAIN_RANGE = (1, 8)
PREDICTION_METRIC = "walking_seeds_screen"
FALLBACK_EDIT_MAGNITUDES = (0.10, 0.05)          # matched-random size for a slot whose model proposal is invalid or empty
R3_RNG_BASE = 20261016
TEMPERATURE = 0.7
MAX_TOKENS = 2200
MAX_REQUESTS = 30
MAX_TOTAL_TOKENS = 130_000
PRICE_ASSUMPTIONS_USD_PER_M_TOKENS = (0.25, 1.0, 5.0)

# seeds: disjoint from every consumed range (Phase 2A, R1, R2) and from the infrastructure-only seeds 9000-9001 (disclosed below)
EVIDENCE_POOL_SEEDS = tuple(range(9100, 9280))     # theta0 once; 15 contexts of 4 failing + 2 walking seeds are drawn from it
SCREEN_POOL_SEEDS = tuple(range(9300, 9364))       # theta0 once; the first 8 walking + first 8 failing become the 16 screening seeds
VALIDATION_SEEDS = tuple(range(9400, 9464))
PILOT_SEEDS = tuple(range(9500, 9516))
INFRA_ONLY_SEEDS = (9000, 9001)                    # used by infrastructure compatibility checks (check_env.py), never by any experiment
N_FAIL_PER_CONTEXT, N_WALK_PER_CONTEXT = 4, 2
N_SCREEN_PER_CLASS = 8
IMPROVE_MIN_GAIN = 2                               # screening: >= 2 more walking seeds (of 16) than theta0
VALIDATED_MIN_GAIN = 5                             # validation: >= 5 more of 64
TOP_K_VALIDATE = 3

BUDGET_CAP = 6000
PILOT_CAP = 100
WALL_LIMIT_S = 60 * 60
MIN_FREE_GB = 4.0
MAX_WORKERS = 4
ARMS_MODEL = ("M", "N")
ARMS_RANDOM = {"M": "RM", "N": "RN"}
ARM_ORDER = ("M", "RM", "N", "RN", "H")
ESTIMATED_SPEND_CAP_USD = 2.0


def consumed_seed_sets() -> dict[str, tuple]:
    return {**r2.consumed_seed_sets(), "r2_screen": r2.SCREEN_SEEDS, "r2_validation": r2.VALIDATION_SEEDS, "r2_diagnostic": r2.DIAGNOSTIC_SEEDS,
            "r2_pilot": r2.PILOT_SEEDS, "r2_final": r2.FINAL_SEEDS, "infra_only": INFRA_ONLY_SEEDS}


def check_disjoint() -> None:
    mine = {"evidence_pool": EVIDENCE_POOL_SEEDS, "screen_pool": SCREEN_POOL_SEEDS, "validation": VALIDATION_SEEDS, "pilot": PILOT_SEEDS}
    allsets = {**mine, **consumed_seed_sets()}
    names = list(allsets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if set(allsets[a]) & set(allsets[b]):
                raise ValueError(f"seed sets overlap: {a} & {b}")


# ----------------------------------------------------------------------------------------------------------
# proposal schema (strict; no repair, no heuristics)
# ----------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Proposal:
    claim: str
    cited_evidence: tuple[str, ...]
    edits: tuple[tuple[str, float], ...]          # (parameter, requested delta in normalised units)
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


def parse_proposal(obj, context: dict) -> Proposal:
    """Validate ONE proposal against the context the model was shown. Both arms use the identical schema: at least
    MIN_CITATIONS distinct dotted paths into THAT context, each resolving to a single value."""
    o = _exact(obj, {"claim", "cited_evidence", "edits", "prediction", "confidence"}, "proposal")
    claim = o["claim"]
    if not isinstance(claim, str) or not (10 <= len(claim.strip()) <= 400):
        raise InvalidModelOutput("claim must be a string of 10..400 characters")
    cites = o["cited_evidence"]
    if not isinstance(cites, list) or not all(isinstance(c, str) for c in cites):
        raise InvalidModelOutput("cited_evidence must be a list of strings")
    if len(set(cites)) < MIN_CITATIONS:
        raise InvalidModelOutput(f"at least {MIN_CITATIONS} distinct evidence paths must be cited")
    for c in cites:
        try:
            leaf = resolve_path(context, c)
        except (KeyError, IndexError, ValueError, TypeError):
            raise InvalidModelOutput(f"cited path does not resolve in the provided context: {c!r}") from None
        if isinstance(leaf, (dict, list)):
            raise InvalidModelOutput(f"cited path must point to a value, not a container: {c!r}")
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


def parse_slots(text: str | None, context: dict) -> tuple[list, list, str | None]:
    """Map a reply onto the SLOTS allocated slots. Returns (slots, reasons, request_level_error): slots[i] is a Proposal or None;
    reasons[i] says why a slot is empty ('empty' = the model returned fewer than SLOTS items; no repair, no reordering).
    A malformed envelope leaves every slot empty."""
    slots: list = [None] * SLOTS
    reasons: list = ["empty"] * SLOTS
    try:
        data = extract_json(text)
        o = _exact(data, {"proposals"}, "reply")
        items = o["proposals"]
        if not isinstance(items, list) or not (1 <= len(items) <= SLOTS):
            raise InvalidModelOutput(f"proposals must be a list of 1..{SLOTS} items")
    except InvalidModelOutput as e:
        return slots, [f"request invalid: {e}"] * SLOTS, str(e)
    for i, it in enumerate(items):
        try:
            slots[i] = parse_proposal(it, context)
            reasons[i] = None
        except InvalidModelOutput as e:
            reasons[i] = str(e)
    return slots, reasons, None


# ----------------------------------------------------------------------------------------------------------
# edits: requested vs realised (after boundary reflection)
# ----------------------------------------------------------------------------------------------------------
def apply_edits(theta0, edits) -> list[float]:
    u = r2.to_u(theta0).copy()
    for p, d in edits:
        u[PARAM_NAMES.index(p)] += d
    return r2.from_u(r2.reflect(u)).tolist()


def realised_edits(theta0, edits) -> list[dict]:
    """Per edited parameter: requested delta_u and the delta_u actually realised after reflection at the bounds."""
    u0 = r2.to_u(theta0)
    u1 = r2.to_u(apply_edits(theta0, edits))
    out = []
    for p, d in edits:
        j = PARAM_NAMES.index(p)
        out.append({"parameter": p, "requested_delta_u": d, "realised_delta_u": float(u1[j] - u0[j]), "reflected": bool(abs((u1[j] - u0[j]) - d) > 1e-12)})
    return out


def random_stream(arm: str, block: int, slot: int) -> tuple[list[str], list[float]]:
    """Fixed in advance and independent of any model output: a random permutation of the 15 parameters and 4 signs per (arm, block, slot).
    A counterpart with k edits takes the first k parameters and signs."""
    rng = np.random.default_rng(np.random.SeedSequence([R3_RNG_BASE, 11 if arm == "M" else 12, block, slot]))
    perm = [PARAM_NAMES[int(j)] for j in rng.permutation(len(PARAM_NAMES))]
    signs = [float(s) for s in rng.choice([-1.0, 1.0], size=MAX_EDITS)]
    return perm[:MAX_EDITS], signs


def matched_random_edits(arm: str, block: int, slot: int, magnitudes: list[float] | tuple[float, ...]) -> list[tuple[str, float]]:
    """Counterpart with the requested magnitudes (in the model's edit order) on random parameters and signs. Valid slot: the model's
    |delta_u| list. Invalid/empty slot: FALLBACK_EDIT_MAGNITUDES. The parameter/sign draws do not depend on the magnitudes."""
    perm, signs = random_stream(arm, block, slot)
    return [(perm[i], signs[i] * float(abs(m))) for i, m in enumerate(magnitudes)]


HEURISTIC_RULE = ("Derived from docs/PHASE2A_FAILURE_DIAGNOSIS.md (pre-R2): the failures are start-up failures to establish forward "
                  "stepping with backward lean, so lean forward at start, lengthen the start-up ramp, raise the pitch reference. Fires only "
                  "if at least half of the failing seeds of the evidence pool have <= 1 valid step. Written by the authors knowing the R2 "
                  "outcome: a knowledgeable baseline, not a blind one.")
HEURISTIC_EDITS = ((("start_lean", 0.10),), (("start_lean", 0.15),), (("ramp_s", 0.10),), (("start_lean", 0.10), ("ramp_s", 0.10)))


def heuristic_edits(pool_failing: list[dict]) -> list[tuple]:
    if not pool_failing or sum(f["valid_steps"] <= 1 for f in pool_failing) * 2 < len(pool_failing):
        return []
    return [tuple(e) for e in HEURISTIC_EDITS]


# ----------------------------------------------------------------------------------------------------------
# contexts and prompts (identical controller block in both arms; measurements are the only treatment)
# ----------------------------------------------------------------------------------------------------------
SEED_FIELDS = ("seed", "label", "fell", "fall_time", "fall_pitch", "valid_steps", "backward_steps", "touchdowns", "speed_upright",
               "forward_disp_upright", "max_abs_pitch", "mean_pitch", "min_torso_height", "single_support_frac", "mean_stance_s",
               "mean_swing_s", "raw_touchdown_rate", "violations")


def _r(x):
    return round(x, 4) if isinstance(x, float) and math.isfinite(x) else x


def controller_block(theta) -> dict:
    u = r2.to_u(theta)
    return {n: {"value": _r(float(theta[i])), "lower": float(LOWER15[i]), "upper": float(UPPER15[i]), "u": _r(float(u[i])),
                "meaning": PARAM_DESCRIPTIONS[n]} for i, n in enumerate(PARAM_NAMES)}


def episode_block() -> dict:
    return {"duration_s": r2.DURATION, "initial_state": "torso pitch and 6 joint angles ~ N(0, 0.03 rad) set by the seed"}


def seed_row(m: dict) -> dict:
    d = {k: _r(m.get(k)) for k in SEED_FIELDS}
    d["initial_perturbation_rad"] = {k: _r(v) for k, v in r1.initial_perturbation(m["seed"]).items()}
    return d


def build_context(theta, measured: list[dict] | None = None) -> dict:
    """What the model sees. measured=None: controller table + episode description only (control). With `measured` (per-seed metrics of the
    frozen controller): the same two blocks plus the observed MuJoCo measurements of those seeds (treatment)."""
    ctx = {"controller": controller_block(theta), "episode": episode_block()}
    if measured is not None:
        ordered = sorted(measured, key=lambda m: m["seed"])
        labels: dict[str, int] = {}
        for m in ordered:
            labels[m["label"]] = labels.get(m["label"], 0) + 1
        ctx["summary"] = {"n_seeds": len(ordered), "walking_seeds": sum(bool(m["walking"]) for m in ordered),
                          "fell_seeds": sum(bool(m["fell"]) for m in ordered), "labels": labels}
        ctx["failing_seeds"] = [seed_row(m) for m in ordered if not m["walking"]]
        ctx["walking_seeds"] = [seed_row(m) for m in ordered if m["walking"]]
    return ctx


SYSTEM_PROMPT = (
    "You are the Physics Investigator for a MuJoCo planar-biped locomotion tool. A frozen phase-based walking controller fails to walk "
    "(every walking gate) on some random initial conditions. You are shown its parameter table and possibly measured evidence. Propose "
    "bounded edits to its 15 normalised parameters that you predict will make it walk on MORE seeds. A deterministic MuJoCo experiment on "
    "unseen seeds judges you; your opinion is never the verdict, and you are scored against random and rule-based baselines. Reply with "
    'ONE JSON object and nothing else: {"proposals": [ ... exactly 4 items ... ]}. Each item has exactly: "claim" (10-400 chars: the '
    'mechanism you suspect), "cited_evidence" (list of at least 2 DISTINCT dotted paths into the provided context, each pointing to a '
    'single number or string, e.g. "controller.pitch_ref.u" or "episode.duration_s"), "edits" (1-4 items {"parameter": one of the 15 '
    'names, "delta_u": a nonzero number with |delta_u| <= 0.15, a change in normalised units where u=(value-lower)/(upper-lower)}, each '
    'parameter at most once), "prediction" ({"metric": "walking_seeds_screen", "direction": "increase", "min_gain_seeds": integer 1-8}) '
    'and "confidence" (0-1). The 4 items must propose different edits. Do not claim certainty you cannot have.')


def build_messages(context: dict) -> list[dict]:
    user = "CONTEXT:\n" + json.dumps(context, sort_keys=True, separators=(",", ":"))
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def prompt_sha256(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def estimate_tokens(messages_list: list[list[dict]], max_tokens: int = MAX_TOKENS) -> dict:
    """Ceiling for a set of prompts (no network): sum over requests of (estimated prompt tokens + max completion tokens)."""
    per = [estimate_prompt_tokens(m) + max_tokens for m in messages_list]
    total = int(sum(per))
    return {"requests": len(per), "max_completion_tokens_each": max_tokens, "total_tokens_ceiling": total,
            "cost_usd_at_assumed_price_per_million_tokens": {str(p): round(total * p / 1e6, 3) for p in PRICE_ASSUMPTIONS_USD_PER_M_TOKENS},
            "note": "token prices for this model could not be verified from public docs; the figures bracket plausible list prices"}


# ----------------------------------------------------------------------------------------------------------
# evidence pool -> 15 contexts; screening set
# ----------------------------------------------------------------------------------------------------------
def build_contexts(theta, pool_per_seed: list[dict]) -> dict:
    """Deterministic from theta0's evidence-pool outcomes only: context c takes the failing seeds with ascending-rank 4c..4c+3 and the
    walking seeds with ascending-rank 2c..2c+1. If the pool has fewer than 60 failing or 30 walking seeds the registered outcome is STOP."""
    ordered = sorted(pool_per_seed, key=lambda m: m["seed"])
    fails = [m for m in ordered if not m["walking"]]
    walks = [m for m in ordered if m["walking"]]
    need_f, need_w = BLOCKS * N_FAIL_PER_CONTEXT, BLOCKS * N_WALK_PER_CONTEXT
    out = {"n_pool": len(ordered), "n_failing": len(fails), "n_walking": len(walks), "need_failing": need_f, "need_walking": need_w}
    if len(fails) < need_f or len(walks) < need_w:
        out.update({"stop": True, "reason": f"evidence pool has {len(fails)} failing (< {need_f}) or {len(walks)} walking (< {need_w}) seeds; registered STOP",
                    "contexts": []})
        return out
    ctxs = []
    for c in range(BLOCKS):
        sel = fails[c * N_FAIL_PER_CONTEXT:(c + 1) * N_FAIL_PER_CONTEXT] + walks[c * N_WALK_PER_CONTEXT:(c + 1) * N_WALK_PER_CONTEXT]
        m_ctx, n_ctx = build_context(theta, sel), build_context(theta, None)
        m_msg, n_msg = build_messages(m_ctx), build_messages(n_ctx)
        ctxs.append({"block": c, "seeds": sorted(m["seed"] for m in sel),
                     "M": {"context": m_ctx, "prompt_sha256": prompt_sha256(m_msg)},
                     "N": {"context": n_ctx, "prompt_sha256": prompt_sha256(n_msg)}})
    out.update({"stop": False, "contexts": ctxs, "pool_failing_for_heuristic": [{"seed": m["seed"], "valid_steps": m["valid_steps"]} for m in fails],
                "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()})
    return out


def select_screening_seeds(pool_per_seed: list[dict]) -> dict:
    ordered = sorted(pool_per_seed, key=lambda m: m["seed"])
    w = [m["seed"] for m in ordered if m["walking"]]
    f = [m["seed"] for m in ordered if not m["walking"]]
    out = {"n_pool": len(ordered), "n_walking": len(w), "n_failing": len(f)}
    if len(w) < N_SCREEN_PER_CLASS or len(f) < N_SCREEN_PER_CLASS:
        out.update({"stop": True, "reason": f"fewer than {N_SCREEN_PER_CLASS} seeds in an outcome class; registered STOP", "seeds": []})
    else:
        out.update({"stop": False, "seeds": sorted(w[:N_SCREEN_PER_CLASS] + f[:N_SCREEN_PER_CLASS])})
    return out


# ----------------------------------------------------------------------------------------------------------
# one counted model request -> an honest record (never fabricates; invalid output stays invalid)
# ----------------------------------------------------------------------------------------------------------
@dataclass
class RequestRecord:
    arm: str
    block: int
    status: str                                  # ok | invalid_response | model_error | budget_exceeded
    prompt_sha256: str
    call: dict | None = None                     # redacted metadata: model id, tokens, latency, request id (no credentials)
    raw_reply: str | None = None                 # untrusted model text, stored as received
    reason: str | None = None
    slots: list = field(default_factory=list)    # SLOTS entries: {"proposal": dict | None, "reason": str | None}
    temperature: float = TEMPERATURE
    max_tokens: int = MAX_TOKENS

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def request_block(client: NebiusClient, arm: str, block: int, context: dict, *, reasoning_effort: str | None = None) -> RequestRecord:
    """Exactly one chat request (the client never retries)."""
    messages = build_messages(context)
    rec = RequestRecord(arm, block, "ok", prompt_sha256(messages), slots=[{"proposal": None, "reason": "not requested"}] * SLOTS)
    try:
        res = client.chat(messages, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, reasoning_effort=reasoning_effort)
    except BudgetExceeded as e:
        rec.status, rec.reason = "budget_exceeded", str(e)
        return rec
    except NebiusError as e:
        rec.status, rec.reason = "model_error", str(e)[:300]
        rec.call = client.calls[-1] if client.calls else None
        return rec
    rec.call, rec.raw_reply = res.record(), res.content
    slots, reasons, err = parse_slots(res.content, context)
    if err is not None:
        rec.status = "invalid_response"
        rec.reason = err + (" (finish_reason=length)" if res.finish_reason == "length" else "")
    rec.slots = [{"proposal": None if p is None else p.as_dict(), "reason": r} for p, r in zip(slots, reasons)]
    return rec


def scripted_transport(replies: list, usage=(900, 400)):
    """OpenAI-compatible stand-in for tests: strings, None (null content) or Exceptions (raised). Running out is an error."""
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
# candidate set (generated and frozen BEFORE any candidate is simulated)
# ----------------------------------------------------------------------------------------------------------
def slot_requested_magnitudes(slot: dict | None) -> list[float]:
    if slot is None or slot.get("proposal") is None:
        return list(FALLBACK_EDIT_MAGNITUDES)
    return [abs(e["delta_u"]) for e in slot["proposal"]["edits"]]


def build_candidates(theta, request_records: list[dict], pool_failing: list[dict]) -> dict:
    """request_records: dicts for arms M and N, one per (arm, block). Every one of the 4*15 slots of each arm gets a matched-random
    counterpart, whether or not the model slot is valid (fallback magnitudes for invalid/empty slots). Candidates exist for valid model
    slots only; invalid/empty model slots are failures in the primary endpoint without being simulated."""
    by = {(r["arm"], r["block"]): r for r in request_records}
    cands: list[dict] = []
    for arm in ARMS_MODEL:
        for b in range(BLOCKS):
            rec = by.get((arm, b))
            for s in range(SLOTS):
                slot = rec["slots"][s] if rec and rec["status"] in ("ok", "invalid_response") else None
                valid = slot is not None and slot.get("proposal") is not None
                mags = slot_requested_magnitudes(slot)
                rnd_edits = matched_random_edits(arm, b, s, mags)
                rnd_arm = ARMS_RANDOM[arm]
                cands.append({"id": f"{rnd_arm}-{b}-{s}", "arm": rnd_arm, "block": b, "slot": s, "model_slot_valid": valid, "matched_to": f"{arm}-{b}-{s}",
                              "edits": [{"parameter": p, "delta_u": d} for p, d in rnd_edits],
                              "realised": realised_edits(theta, rnd_edits), "vector": apply_edits(theta, rnd_edits)})
                if valid:
                    edits = [(e["parameter"], e["delta_u"]) for e in slot["proposal"]["edits"]]
                    cands.append({"id": f"{arm}-{b}-{s}", "arm": arm, "block": b, "slot": s, "model_slot_valid": True,
                                  "edits": slot["proposal"]["edits"], "realised": realised_edits(theta, edits), "vector": apply_edits(theta, edits),
                                  "predicted_min_gain_seeds": slot["proposal"]["prediction"]["min_gain_seeds"], "confidence": slot["proposal"]["confidence"]})
    for i, e in enumerate(heuristic_edits(pool_failing)):
        cands.append({"id": f"H-{i}", "arm": "H", "block": None, "slot": i, "model_slot_valid": None, "edits": [{"parameter": p, "delta_u": d} for p, d in e],
                      "realised": realised_edits(theta, e), "vector": apply_edits(theta, e)})
    return {"theta0": [float(x) for x in theta], "n_candidates": len(cands), "candidates": cands}


def matching_audit(cands: list[dict]) -> dict:
    """Requested vs realised magnitudes per arm; the matching is on REQUESTED magnitudes, so reflection differences are reported here."""
    out = {}
    for arm in ARM_ORDER:
        rows = [r for c in cands if c["arm"] == arm for r in c["realised"]]
        if not rows:
            out[arm] = None
            continue
        out[arm] = {"n_edits": len(rows), "mean_requested_abs": float(np.mean([abs(r["requested_delta_u"]) for r in rows])),
                    "mean_realised_abs": float(np.mean([abs(r["realised_delta_u"]) for r in rows])),
                    "reflected_fraction": float(np.mean([r["reflected"] for r in rows]))}
    return out


# ----------------------------------------------------------------------------------------------------------
# statistics: paired request-block exact sign-flip test (prespecified)
# ----------------------------------------------------------------------------------------------------------
def signflip_exact(diffs: list[int], two_sided: bool = True) -> dict:
    """Exact randomisation test for paired block differences d_c = (successes in arm A) - (successes in arm B), c = 1..n blocks. Under H0 the
    sign of each d_c is exchangeable; the statistic is S = sum d_c. The null distribution is enumerated exactly (DP over the nonzero |d_c|).
    Two-sided p = P(|S*| >= |S_obs|)."""
    d = [int(x) for x in diffs]
    mags = [abs(x) for x in d if x != 0]
    total = sum(mags)
    counts = {0: 1}                                       # number of sign assignments giving each signed sum
    for m in mags:
        new: dict[int, int] = {}
        for s, c in counts.items():
            new[s + m] = new.get(s + m, 0) + c
            new[s - m] = new.get(s - m, 0) + c
        counts = new
    n_assign = 2 ** len(mags)
    obs = sum(d)
    ge = sum(c for s, c in counts.items() if abs(s) >= abs(obs))
    p_two = ge / n_assign
    p_ge = sum(c for s, c in counts.items() if s >= obs) / n_assign
    return {"n_blocks": len(d), "n_nonzero_blocks": len(mags), "sum_diff": obs, "mean_diff": obs / len(d) if d else 0.0, "total_abs": total,
            "p_two_sided": min(1.0, p_two), "p_one_sided_greater": p_ge, "n_assignments": n_assign}


def block_bootstrap_ci(diffs: list[int], n_boot: int = 20000, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    d = np.asarray(diffs, float)
    means = rng.choice(d, size=(n_boot, len(d)), replace=True).mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def slot_success(outcomes: dict, arm: str, block: int, slot: int) -> int:
    """1 iff the candidate exists and improved on the screening seeds; a model slot without a candidate (invalid/empty) is a failure."""
    return int(bool(outcomes.get(f"{arm}-{block}-{slot}", {}).get("improved", False)))


def primary_analysis(outcomes: dict) -> dict:
    """outcomes: {candidate_id: {"improved": bool, ...}}. Confirmatory: all 4 slots per request, M vs matched random RM, paired by request block."""
    def per_block(arm):
        return [sum(slot_success(outcomes, arm, b, s) for s in range(SLOTS)) for b in range(BLOCKS)]
    m, rm, n, rn = per_block("M"), per_block("RM"), per_block("N"), per_block("RN")
    d = [a - b for a, b in zip(m, rm)]
    prim = signflip_exact(d)
    prim.update({"endpoint": "successes among the 4 allocated slots per request, invalid/empty model slots = failure; M minus matched-random RM, paired by request block",
                 "per_block_M": m, "per_block_RM": rm, "per_block_diff": d, "bootstrap_ci_95_mean_diff": block_bootstrap_ci(d),
                 "total_M": sum(m), "total_RM": sum(rm), "slots_per_arm": BLOCKS * SLOTS,
                 "claim": "model edits improve more often than matched random edits" if (prim["p_two_sided"] < 0.05 and prim["mean_diff"] > 0) else None})
    exploratory = {"M_vs_N_signflip": signflip_exact([a - b for a, b in zip(m, n)]), "per_block_N": n, "per_block_RN": rn,
                   "N_vs_RN_signflip": signflip_exact([a - b for a, b in zip(n, rn)]), "totals": {"M": sum(m), "RM": sum(rm), "N": sum(n), "RN": sum(rn)}}
    valid_only = {}
    for arm in ARMS_MODEL:
        pairs = [(slot_success(outcomes, arm, b, s), slot_success(outcomes, ARMS_RANDOM[arm], b, s))
                 for b in range(BLOCKS) for s in range(SLOTS) if f"{arm}-{b}-{s}" in outcomes]
        valid_only[arm] = {"n_valid_slots": len(pairs), "model_improved": sum(a for a, _ in pairs), "matched_random_improved": sum(b for _, b in pairs),
                           "note": "slot-level, ignores clustering within requests: descriptive only"}
    return {"primary": prim, "exploratory": exploratory, "valid_only_descriptive": valid_only}


# ----------------------------------------------------------------------------------------------------------
# ledger, resources, batches
# ----------------------------------------------------------------------------------------------------------
class Ledger(r1.Ledger):
    def __init__(self, path: Path = LEDGER):
        super().__init__(path)

    def begin(self, stage: str, rollouts: int, note: str = "") -> int:
        self.verify()
        if self.total_rollouts() + rollouts > BUDGET_CAP:
            raise r1.BudgetExceeded(f"{self.total_rollouts()} + {rollouts} would exceed the hard cap {BUDGET_CAP}")
        if stage == "pilot" and self.stage_rollouts("pilot") + rollouts > PILOT_CAP:
            raise r1.BudgetExceeded(f"pilot is capped at {PILOT_CAP} rollouts")
        bid = sum(e["event"] == "begin" for e in self.entries()) + 1
        self._append({"event": "begin", "id": bid, "stage": stage, "rollouts": int(rollouts), "note": note,
                      "cumulative_after": self.total_rollouts() + int(rollouts)})
        return bid


def check_resources(ledger: Ledger) -> None:
    free = r1.free_memory_gb()
    if free < MIN_FREE_GB:
        raise r1.ResourceAbort(f"free memory {free:.2f} GB is below the {MIN_FREE_GB} GB floor")
    if ledger.total_wall_s() >= WALL_LIMIT_S:
        raise r1.ResourceAbort(f"cumulative active wall time {ledger.total_wall_s():.0f}s reached the {WALL_LIMIT_S}s hard stop")


def run_batch(ex: Executor, ledger: Ledger, stage: str, vectors, seeds, note: str = "") -> list[dict]:
    check_resources(ledger)
    n = len(vectors) * len(seeds)
    bid = ledger.begin(stage, n, note)
    t0 = time.perf_counter()
    outs = ex.map(r2.make_jobs(vectors, seeds))
    errors = sum(not o["ok"] for o in outs)
    peak = max((o.get("peak_rss_mb") or 0.0) for o in outs)
    ledger.end(bid, executed=n, errors=errors, wall_s=time.perf_counter() - t0, peak_rss_mb_=peak, free_gb=r1.free_memory_gb())
    return outs


def outcome(base_walking: int, cand_walking: int, predicted_min_gain: int | None = None) -> dict:
    gain = cand_walking - base_walking
    out = {"gain_seeds": gain, "improved": bool(gain >= IMPROVE_MIN_GAIN)}
    if predicted_min_gain is not None:
        out["prediction_met"] = bool(gain >= predicted_min_gain)
    return out


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(obj), indent=1, allow_nan=False) + "\n", encoding="utf-8")


def planned_rollouts() -> dict:
    n_cand_max = 4 * BLOCKS * SLOTS + len(HEURISTIC_EDITS)          # M, RM, N, RN slots + heuristic
    screen = n_cand_max * 16
    return {"pilot": 96, "evidence_pool": len(EVIDENCE_POOL_SEEDS), "screen_pool": len(SCREEN_POOL_SEEDS), "screening_candidates_max": screen,
            "validation_theta0": len(VALIDATION_SEEDS), "validation_top_k": len(ARM_ORDER) * TOP_K_VALIDATE * len(VALIDATION_SEEDS),
            "total_max": 96 + len(EVIDENCE_POOL_SEEDS) + len(SCREEN_POOL_SEEDS) + screen + len(VALIDATION_SEEDS) + len(ARM_ORDER) * TOP_K_VALIDATE * len(VALIDATION_SEEDS)}


# ----------------------------------------------------------------------------------------------------------
# protocol
# ----------------------------------------------------------------------------------------------------------
def build_protocol() -> dict:
    check_disjoint()
    plan = planned_rollouts()
    return {
        "id": PROTOCOL_ID,
        "status": "immutable once committed; changes require a new protocol id and re-registration",
        "question": ("Do Nemotron-proposed, MuJoCo-grounded, bounded edits to the frozen Phase 2A incumbent raise its walking success more often "
                     "than matched random edits? Secondary: measured evidence vs none; a rule-based heuristic. MuJoCo alone decides."),
        "approved_limits": {"live_requests": MAX_REQUESTS, "combined_tokens": MAX_TOTAL_TOKENS, "physics_rollouts": BUDGET_CAP,
                            "additional_estimated_spend_usd": ESTIMATED_SPEND_CAP_USD, "no_automatic_extension": True, "no_retries": True,
                            "no_gpu": True},
        "model": {"id": MODEL, "endpoint": "Nebius Token Factory (OpenAI-compatible chat completions)", "temperature": TEMPERATURE,
                  "max_tokens_per_request": MAX_TOKENS, "reasoning_effort": "default (not set)", "response_format": "none (prompted JSON)",
                  "one_request_per_block_and_arm": True, "request_order": "interleaved M0, N0, M1, N1, ... M14, N14"},
        "spend_estimate": {"inference_worst_case_usd_at_assumed_5_per_million_tokens": round(MAX_TOTAL_TOKENS * 5 / 1e6, 3),
                           "vm_usd_per_hour": 0.269, "vm_hours_assumed_upper_bound": 1.0, "vm_usd_upper_bound": 0.27,
                           "total_upper_bound_usd": round(MAX_TOTAL_TOKENS * 5 / 1e6 + 0.27, 2),
                           "note": "the token price of this model could not be verified; 5 USD per million tokens is a deliberately high assumed bound"},
        "frozen_inputs": {"incumbent_export": r1.INCUMBENT_FILE.relative_to(ROOT).as_posix(), "incumbent_sha256_lf": r2.sha256_lf(r1.INCUMBENT_FILE),
                          "r2_protocol_sha256_lf": r2.sha256_lf(r2.PROTOCOL), "phase2a_protocol_sha256_lf": r2.sha256_lf(phase2a.PROTOCOL)},
        "base_controller": "frozen Phase 2A incumbent theta0 (15 parameters incl. ramp_s/start_lean at their defaults); R2's winner is not used",
        "morphology": r2.BipedParams().as_dict(),
        "durations_s": {"all": r2.DURATION},
        "seeds": {"evidence_pool": [min(EVIDENCE_POOL_SEEDS), max(EVIDENCE_POOL_SEEDS)], "screen_pool": [min(SCREEN_POOL_SEEDS), max(SCREEN_POOL_SEEDS)],
                  "validation": [min(VALIDATION_SEEDS), max(VALIDATION_SEEDS)], "pilot": [min(PILOT_SEEDS), max(PILOT_SEEDS)],
                  "disclosure": ("Disjoint from every Phase 2A, R1 and R2 seed (including the R2 final seeds 8000-8149, which R3 does not touch) and from "
                                 "the infrastructure-only seeds 9000-9001 (used only by check_env.py compatibility checks; never an experimental role). "
                                 "No R3 seed has been used before registration.")},
        "contexts": {"n": BLOCKS, "rule": (f"theta0 is run once on the {len(EVIDENCE_POOL_SEEDS)} evidence-pool seeds. Context c (c = 0..{BLOCKS - 1}) shows the "
                                           f"failing seeds with ascending rank {N_FAIL_PER_CONTEXT}c..{N_FAIL_PER_CONTEXT}c+{N_FAIL_PER_CONTEXT - 1} and the walking seeds with "
                                           f"ascending rank {N_WALK_PER_CONTEXT}c..{N_WALK_PER_CONTEXT}c+{N_WALK_PER_CONTEXT - 1} (6 seeds, ordered by seed number). STOP if the pool has "
                                           f"fewer than {BLOCKS * N_FAIL_PER_CONTEXT} failing or {BLOCKS * N_WALK_PER_CONTEXT} walking seeds."),
                     "freeze": "contexts.json (15 contexts, both prompts per block, SHA-256 of every prompt) is committed BEFORE any model request",
                     "treatment_difference": "arm M receives controller table + episode + measured evidence; arm N receives byte-identical controller table and episode block and the same system prompt; the only difference is the measured evidence"},
        "screening_set": {"rule": f"theta0 once on the {len(SCREEN_POOL_SEEDS)} screen-pool seeds; screening seeds = first {N_SCREEN_PER_CLASS} walking + first {N_SCREEN_PER_CLASS} failing in ascending seed order; STOP if either class has fewer",
                          "frozen_in": "contexts.json"},
        "arms": {"M": "Nemotron with measured evidence (15 requests x 4 slots)", "N": "Nemotron without measured evidence, identical controller/bounds/descriptions (15 x 4)",
                 "RM": "matched random counterpart of every M slot", "RN": "matched random counterpart of every N slot",
                 "H": f"rule-based heuristic (fixed edits, descriptive only): {HEURISTIC_RULE}"},
        "proposal_contract": {"slots_per_request": SLOTS, "max_edits": MAX_EDITS, "max_abs_delta_u": MAX_ABS_DELTA_U, "min_citations": MIN_CITATIONS,
                              "same_schema_in_both_arms": True,
                              "invalid_handling": "no repair, no retries, no reordering; an invalid item or a missing item (fewer than 4 returned) is an empty slot = failure; a malformed envelope leaves all 4 slots empty"},
        "matched_random": {"streams": "per (arm, block, slot): default_rng(SeedSequence([rng_base, 11 for M | 12 for N, block, slot])) permutation of the 15 parameters and 4 signs, drawn before any request",
                           "rng_base": R3_RNG_BASE,
                           "valid_slot": "k = number of model edits; magnitudes = the model's |delta_u| in the model's edit order; parameters/signs = first k of the stream",
                           "invalid_or_empty_slot": f"fallback: 2 edits with magnitudes {list(FALLBACK_EDIT_MAGNITUDES)}; same stream",
                           "every_slot_has_a_counterpart": True,
                           "audit": "requested and realised (after reflection at the bounds) delta_u are recorded per edit; matching is on requested magnitudes and the realised differences are reported",
                           "freeze": "candidates.json (all candidate vectors with provenance) is committed BEFORE any candidate is simulated; screening outcomes never alter prompts, comparators or selection"},
        "evaluation": {"screening": {"seeds": "the 16 screening seeds (common random numbers for every candidate and theta0)", "improved": f">= {IMPROVE_MIN_GAIN} more walking seeds than theta0 on the same seeds"},
                       "validation": {"seeds": [min(VALIDATION_SEEDS), max(VALIDATION_SEEDS)], "n": len(VALIDATION_SEEDS), "theta0": "once",
                                      "top_k_per_arm": TOP_K_VALIDATE, "ranking": "screening gain, ties by earlier (block, slot)", "validated_improvement": f">= {VALIDATED_MIN_GAIN} more walking seeds than theta0",
                                      "arms_validated": list(ARM_ORDER), "status": "descriptive, no multiplicity claim"}},
        "primary_analysis": {"endpoint": "per request block c: successes among the 4 slots (success = improved on screening seeds; invalid/empty model slot = failure); d_c = successes(M) - successes(RM)",
                             "test": "paired request-block exact sign-flip (randomisation) test over the 15 blocks, statistic sum d_c, null distribution enumerated exactly, two-sided",
                             "alpha": 0.05, "claim_rule": "claim 'model edits improve more often than matched random edits' only if p < 0.05 and mean d_c > 0",
                             "reporting": ["per-block table", "sum and mean of d_c", "exact p (two-sided and one-sided)", "block bootstrap 95% interval of mean d_c (descriptive)", "totals per arm"],
                             "completeness_rule": "the confirmatory test is run only if all 30 requests were sent and none ended in a transport/HTTP error or budget refusal; otherwise the experiment is reported as incomplete"},
        "exploratory_analyses": ["M vs N, paired by block (sign-flip)", "N vs RN", "valid-slot-only comparisons ignoring clustering", "H outcomes", "prediction hit rate vs confidence",
                                 "requested vs realised magnitude audit", "validated improvements per arm"],
        "budget": {"hard_cap_rollouts": BUDGET_CAP, "pilot_cap_rollouts": PILOT_CAP, "planned": plan, "wall_clock_hard_stop_s": WALL_LIMIT_S, "max_workers": MAX_WORKERS,
                   "min_free_memory_gb": MIN_FREE_GB, "ledger": "experiments/phase2a_r3/results/ledger.jsonl (hash-chained, begin entries precede physics, session events feed the wall guard)",
                   "feasibility": f"planned maximum {plan['total_max']} rollouts <= cap {BUDGET_CAP}; verified by tests and by the pilot",
                   "token_limits": {"max_requests": MAX_REQUESTS, "max_total_tokens": MAX_TOTAL_TOKENS, "max_tokens_per_request": MAX_TOKENS}},
        "stopping_rules": ["any hard limit reached (requests, tokens, rollouts, wall time, memory floor) stops the run; no extension, no retry",
                           "a transport/HTTP error or budget refusal on any request makes the experiment incomplete: remaining requests are not sent",
                           "screening-set or evidence-pool STOP outcomes are reported as the result",
                           "no model reply is edited, repaired, selected by hand or re-requested; scripted replies are never saved as results"],
        "provenance": ["prompt SHA-256 per request and arm", "redacted call metadata per request (model id, usage, latency, request id)", "raw reply as received",
                       "per-slot validation outcome and reason", "token totals and estimated spend (assumed price bounds)"],
    }


def require_preregistration(need_contexts: bool = False, need_candidates: bool = False) -> dict:
    commits = {"protocol": phase2a.committed_unmodified(PROTOCOL)}
    if json.loads(PROTOCOL.read_text(encoding="utf-8")) != json.loads(json.dumps(build_protocol())):
        raise RuntimeError("protocol.json no longer matches the code that defines it or its frozen inputs; re-registration required")
    if need_contexts:
        commits["contexts"] = phase2a.committed_unmodified(CONTEXTS)
    if need_candidates:
        commits["candidates"] = phase2a.committed_unmodified(CANDIDATES)
    return commits
