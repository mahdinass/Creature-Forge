"""Physics Investigator: simulation evidence -> falsifiable hypothesis -> bounded intervention -> MuJoCo verification.

Trust boundaries (see docs/memory/DECISIONS.md):
  * Evidence and verification are produced ONLY by MuJoCo + deterministic code.
  * The model supplies ONLY a hypothesis, a prediction and one proposed parameter change, all of which
    are validated locally (unknown fields, types, finite numbers, bounds) before anything is simulated.
  * The verdict is computed by `verify`; the model never judges its own result.
  * Every trial, successful or not, is stored as one JSON record (`Trial`) for later evaluation.
"""
from __future__ import annotations

import json
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .controller import GaitParams
from .experiment import compare_designs, evaluate_design
from .failures import detect_failures
from .morphology import BOUNDS, BipedParams
from .nebius import BudgetExceeded, NebiusClient, NebiusError
from .simulate import Push, run_rollout

SCHEMA_VERSION = 1
PREDICTION_METRICS = ("fall_rate", "mean_min_torso_height")
PREDICTION_DIRECTIONS = ("decrease", "increase")
MIN_HEIGHT_GAIN_M = 0.02  # tie-break: equal fall rate counts as improved only if mean min torso height rises this much
INVESTIGATIONS_DIR = Path("artifacts") / "investigations"


class InvalidModelOutput(ValueError):
    """The model's reply failed local validation; the message says why."""


# --------------------------------------------------------------------------- evidence (observed only)

def build_evidence(body: BipedParams, gait: GaitParams, push: Push | None, *, seeds=(0, 1, 2),
                   duration: float = 5.0) -> dict:
    """Deterministic observations from MuJoCo. Contains no hypotheses and no causal claims."""
    matched = evaluate_design(body, gait, seeds, duration, push)
    tel = run_rollout(body, gait, seed=seeds[0], duration=duration, push=push)
    events = detect_failures(tel, body)
    demand = np.abs(tel["ctrl_demand"])
    return {
        "scenario": {"push": None if push is None else {"time_s": push.time, "force_N": push.force,
                                                         "duration_s": push.duration},
                     "duration_s": duration, "seeds": list(seeds)},
        "body": body.as_dict(),
        "controller": gait.as_dict(),
        "matched_seed_results": {
            "fall_rate": matched["fall_rate"],
            "mean_min_torso_height_m": matched["mean_min_torso_height"],
            "mean_max_abs_pitch_rad": matched["mean_max_abs_pitch"],
            "per_seed": [{"seed": r["seed"], "fell": r["fell"], "min_torso_height_m": r["min_torso_height"],
                          "max_abs_pitch_rad": r["max_abs_pitch"], "events": r["events"]}
                         for r in matched["runs"]]},
        "detailed_run": {
            "seed": seeds[0],
            "events": [e.as_dict() for e in events],
            "peak_torque_demand_over_limit": float(demand.max() / body.torque_limit),
            "peak_foot_slip_speed_mps": float(tel["foot_slip_speed"].max()),
            "initial_torso_height_m": float(tel["torso_pos"][0, 1]),
        },
    }


def resolve_path(evidence: dict, path: str):
    """Look up a dotted path such as 'detailed_run.events.0.time'. Raises KeyError if absent."""
    cur = evidence
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur[part]
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            raise KeyError(path)
    return cur


# --------------------------------------------------------------------------- hypothesis schema

@dataclass(frozen=True)
class Hypothesis:
    claim: str
    cited_evidence: tuple[str, ...]
    prediction_metric: str
    prediction_direction: str
    confidence: float
    parameter: str
    value: float

    def as_dict(self) -> dict:
        return {"claim": self.claim, "cited_evidence": list(self.cited_evidence),
                "prediction": {"metric": self.prediction_metric, "direction": self.prediction_direction},
                "confidence": self.confidence,
                "intervention": {"parameter": self.parameter, "value": self.value}}


def _exact_keys(obj, keys: set[str], where: str) -> dict:
    if not isinstance(obj, dict):
        raise InvalidModelOutput(f"{where} must be an object")
    extra, missing = set(obj) - keys, keys - set(obj)
    if extra:
        raise InvalidModelOutput(f"{where}: unknown field(s) {sorted(extra)}")
    if missing:
        raise InvalidModelOutput(f"{where}: missing field(s) {sorted(missing)}")
    return obj


def _number(v, where: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise InvalidModelOutput(f"{where} must be a finite number")
    return float(v)


def extract_json(text: str | None) -> dict:
    """Accept raw JSON or one fenced block; anything else is invalid (no heuristics, no repair)."""
    if text is None or not text.strip():
        raise InvalidModelOutput("model returned no content")
    s = text.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, re.DOTALL)
    if m:
        s = m.group(1)
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise InvalidModelOutput(f"reply is not valid JSON ({e.msg})") from None


def parse_hypothesis(text: str | None, evidence: dict, body: BipedParams) -> Hypothesis:
    obj = _exact_keys(extract_json(text), {"claim", "cited_evidence", "prediction", "confidence",
                                          "intervention"}, "response")
    claim = obj["claim"]
    if not isinstance(claim, str) or not (10 <= len(claim) <= 600):
        raise InvalidModelOutput("claim must be a string of 10-600 characters")
    cited = obj["cited_evidence"]
    if not isinstance(cited, list) or not (1 <= len(cited) <= 8) or not all(isinstance(c, str) for c in cited):
        raise InvalidModelOutput("cited_evidence must be a list of 1-8 evidence paths")
    for c in cited:
        try:
            resolve_path(evidence, c)
        except (KeyError, IndexError, ValueError):
            raise InvalidModelOutput(f"cited evidence path does not exist: {c!r}") from None
    pred = _exact_keys(obj["prediction"], {"metric", "direction"}, "prediction")
    if pred["metric"] not in PREDICTION_METRICS:
        raise InvalidModelOutput(f"prediction.metric must be one of {PREDICTION_METRICS}")
    if pred["direction"] not in PREDICTION_DIRECTIONS:
        raise InvalidModelOutput(f"prediction.direction must be one of {PREDICTION_DIRECTIONS}")
    conf = _number(obj["confidence"], "confidence")
    if not 0.0 <= conf <= 1.0:
        raise InvalidModelOutput("confidence must be within [0, 1]")
    iv = _exact_keys(obj["intervention"], {"parameter", "value"}, "intervention")
    if iv["parameter"] not in BOUNDS:
        raise InvalidModelOutput(f"unsupported intervention parameter {iv['parameter']!r}; allowed: {sorted(BOUNDS)}")
    value = _number(iv["value"], "intervention.value")
    lo, hi = BOUNDS[iv["parameter"]]
    if not lo <= value <= hi:
        raise InvalidModelOutput(f"{iv['parameter']}={value} outside bounds [{lo}, {hi}]")  # rejected, never clipped
    if value == getattr(body, iv["parameter"]):
        raise InvalidModelOutput("intervention does not change the parameter")
    return Hypothesis(claim, tuple(cited), pred["metric"], pred["direction"], conf, iv["parameter"], value)


# --------------------------------------------------------------------------- verification (deterministic)

def verify(hyp: Hypothesis, body: BipedParams, gait: GaitParams, push: Push | None, *, seeds, duration: float) -> dict:
    """Re-run MuJoCo for baseline vs. candidate on matched seeds and judge the prediction numerically."""
    candidate = body.replace(**{hyp.parameter: hyp.value})
    res = compare_designs(body, candidate, gait, seeds=seeds, duration=duration, push=push)
    b, c = res["baseline"], res["candidate"]
    observed = {m: {"baseline": b[m], "candidate": c[m], "delta": c[m] - b[m]} for m in
                ("fall_rate", "mean_min_torso_height", "mean_max_abs_pitch")}
    delta = observed[hyp.prediction_metric]["delta"]
    prediction_held = delta < 0 if hyp.prediction_direction == "decrease" else delta > 0
    d_fall = observed["fall_rate"]["delta"]
    d_h = observed["mean_min_torso_height"]["delta"]
    improved = d_fall < 0 or (d_fall == 0 and d_h > MIN_HEIGHT_GAIN_M)
    return {"candidate_body": candidate.as_dict(), "seeds": list(seeds), "duration_s": duration,
            "observed": observed, "per_seed": {"baseline": b["runs"], "candidate": c["runs"]},
            "prediction_held": bool(prediction_held), "improved": bool(improved),
            "accepted": bool(prediction_held and improved)}


# --------------------------------------------------------------------------- prompt

SYSTEM_PROMPT = """You are the Physics Investigator for a MuJoCo robot-design tool. You receive OBSERVED simulation evidence \
about a planar biped that fails a disturbance test. Propose ONE falsifiable hypothesis about why it fails and ONE \
bounded design change that tests it. A deterministic MuJoCo experiment will judge you; your opinion is never the verdict.
Rules: cite only evidence paths that exist; do not invent measurements; change exactly one body parameter within its bounds.
Reply with ONLY a JSON object, no prose, exactly this shape:
{"claim": str (10-600 chars), "cited_evidence": [dotted paths into the evidence, e.g. "matched_seed_results.fall_rate"],
 "prediction": {"metric": "fall_rate"|"mean_min_torso_height", "direction": "decrease"|"increase"},
 "confidence": number 0..1, "intervention": {"parameter": <one of the body parameters>, "value": number}}"""


def build_messages(evidence: dict, body: BipedParams) -> list[dict]:
    user = {"observed_evidence": evidence,
            "allowed_body_parameters": {k: {"min": lo, "max": hi, "current": getattr(body, k)}
                                        for k, (lo, hi) in BOUNDS.items()}}
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user, separators=(",", ":"))}]


# --------------------------------------------------------------------------- trial record + orchestration

@dataclass
class Trial:
    """One investigation, successful or not. Sections are kept strictly separate."""
    trial_id: str
    status: str = "started"  # accepted | rejected_by_verifier | invalid_model_output | model_error | budget_exceeded
    created_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: int = SCHEMA_VERSION
    mode: str = "fake"  # "fake" | "live": whether the proposer was a real Nebius call
    config: dict = field(default_factory=dict)
    observed_evidence: dict | None = None  # MuJoCo only
    model_call: dict | None = None  # redacted call metadata (no credentials)
    raw_model_reply: str | None = None  # model text as received (untrusted)
    rejection_reason: str | None = None
    hypothesis: dict | None = None  # validated model output: claim, prediction, intervention
    measured_outcome: dict | None = None  # MuJoCo verification only
    elapsed_s: float | None = None

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def save_trial(trial: Trial, root: Path = INVESTIGATIONS_DIR) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{trial.trial_id}.json"
    path.write_text(json.dumps(trial.as_dict(), indent=2))
    return path


def load_trial(trial_id: str, root: Path = INVESTIGATIONS_DIR) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", trial_id):
        raise KeyError(trial_id)
    return json.loads((root / f"{trial_id}.json").read_text())


def list_trials(root: Path = INVESTIGATIONS_DIR) -> list[dict]:
    out = []
    for p in sorted(root.glob("*.json"), reverse=True) if root.is_dir() else []:
        t = json.loads(p.read_text())
        out.append({k: t.get(k) for k in ("trial_id", "status", "mode", "created_utc")} |
                   {"hypothesis_claim": (t.get("hypothesis") or {}).get("claim")})
    return out


def investigate(client: NebiusClient, body: BipedParams, gait: GaitParams, push: Push | None, *,
                evidence_seeds=(0, 1, 2), verify_seeds=(0, 1, 2, 3, 4), duration: float = 5.0,
                reasoning_effort: str | None = None, max_tokens: int = 4096, max_seconds: float = 180.0,
                mode: str = "fake", save_to: Path | None = INVESTIGATIONS_DIR) -> Trial:
    """Run one investigation with at most ONE model request. Always returns (and saves) a Trial."""
    t0 = time.perf_counter()
    trial = Trial(trial_id=f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}", mode=mode,
                  config={"model": client.model, "reasoning_effort": reasoning_effort, "max_tokens": max_tokens,
                          "max_seconds": max_seconds, "evidence_seeds": list(evidence_seeds),
                          "verify_seeds": list(verify_seeds), "duration_s": duration,
                          "limits": {"max_requests": client.limits.max_requests,
                                     "max_total_tokens": client.limits.max_total_tokens,
                                     "timeout_s": client.limits.timeout_s}})

    def finish(status: str, reason: str | None = None) -> Trial:
        trial.status, trial.rejection_reason = status, reason
        trial.elapsed_s = round(time.perf_counter() - t0, 3)
        if save_to is not None:
            save_trial(trial, save_to)
        return trial

    evidence = build_evidence(body, gait, push, seeds=evidence_seeds, duration=duration)
    trial.observed_evidence = evidence
    try:
        result = client.chat(build_messages(evidence, body), max_tokens=max_tokens,
                             reasoning_effort=reasoning_effort)
    except BudgetExceeded as e:
        return finish("budget_exceeded", str(e))
    except NebiusError as e:
        trial.model_call = client.calls[-1] if client.calls else None
        return finish("model_error", str(e)[:300])
    trial.model_call = result.record()
    trial.raw_model_reply = result.content
    try:
        hyp = parse_hypothesis(result.content, evidence, body)
    except InvalidModelOutput as e:
        why = str(e)
        if result.finish_reason == "length":
            why += " (finish_reason=length: max_tokens may have been consumed by reasoning)"
        return finish("invalid_model_output", why)
    trial.hypothesis = hyp.as_dict()
    if time.perf_counter() - t0 > max_seconds:
        return finish("budget_exceeded", f"time limit {max_seconds}s exceeded before verification")
    trial.measured_outcome = verify(hyp, body, gait, push, seeds=verify_seeds, duration=duration)
    return finish("accepted" if trial.measured_outcome["accepted"] else "rejected_by_verifier")
