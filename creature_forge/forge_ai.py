"""Forge Loop model side: prompt, reply schema, one recorded model call, tolerant parsing, strict validation, one repair attempt.

Trust boundary: the model's reply is untrusted text. It is parsed (`parse_reply`), validated against the schema, the evidence (every citation
must resolve to a scalar via `evidence.resolve`) and the edit rules (`interventions.validate_edits`), and each proposal is accepted or rejected
WITH reasons. Nothing is clipped into range, nothing the model says is a verdict: MuJoCo verifies accepted proposals elsewhere.

Failure policy (earlier runs returned `content=null` when hidden reasoning consumed the completion budget): `content` null/empty,
`finish_reason=length`, HTTP errors, timeouts and budget refusals are RECORDED FAILURES in the returned `ModelCall` and are never retried.
The single exception is one repair call when the reply is unparseable, schema-invalid or leaves no valid proposal; it carries the validator's
errors, is counted in the ledger like any request, and happens at most once.

No network happens here except through the injected client's transport (tests use fakes).
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import dataclass, field

from . import interventions as iv
from . import probes as pb
from .evidence import UnresolvedCitation, build_evidence, leaf_items, leaf_paths, pack_size, resolve
from .inference_ledger import InferenceLedger
from .nebius import (RESERVED_BODY_KEYS, REASONING_EFFORTS, BudgetExceeded, Limits, NebiusClient, NebiusError,
                     estimate_prompt_tokens)

HYPOTHESIS_IDS = ("H1", "H2", "H3")
PROPOSAL_IDS = ("P1", "P2", "P3")
MAX_HYPOTHESES = len(HYPOTHESIS_IDS)
MAX_CITATIONS = 6
SUMMARY_MAX = 400
TEXT_MAX = 600
SHORT_MAX = 300
SCHEMA_NAME = "forge_reply"
REPAIR_ECHO_MAX = 4000
REPAIR_ERRORS_MAX = 12


# ------------------------------------------------------------------------------------------------------------------ schema
def _schema(paths: list[str] | None = None, params: list[str] | None = None, n_proposals: int = 3) -> dict:
    s = {"type": "string"}
    path_item = {"type": "string", "enum": list(paths)} if paths else dict(s)
    param_item = {"type": "string", "enum": list(params)} if params else dict(s)
    edit = {"type": "object", "additionalProperties": False, "required": ["param", "op", "value", "target"],
            "properties": {"param": param_item, "op": {"type": "string", "enum": list(iv.OPS)}, "value": {"type": "number"},
                           "target": {"type": "string", "enum": list(iv.TARGETS)}}}
    hyp = {"type": "object", "additionalProperties": False, "required": ["id", "mechanism", "evidence", "competing"],
           "properties": {"id": {"type": "string", "enum": list(HYPOTHESIS_IDS)}, "mechanism": dict(s),
                          "evidence": {"type": "array", "items": path_item}, "competing": {"type": "array", "items": dict(s)}}}
    prop = {"type": "object", "additionalProperties": False,
            "required": ["id", "hypothesis", "category", "edits", "retune_controller", "prediction", "tradeoffs", "confidence", "verification"],
            "properties": {"id": {"type": "string", "enum": list(PROPOSAL_IDS[:max(1, n_proposals)])},
                           "hypothesis": {"type": "string", "enum": list(HYPOTHESIS_IDS)},
                           "category": {"type": "string", "enum": list(iv.CATEGORIES)},
                           "edits": {"type": "array", "items": edit}, "retune_controller": {"type": "boolean"},
                           "prediction": {"type": "object", "additionalProperties": False, "required": ["metric", "direction", "expected_change"],
                                          "properties": {"metric": {"type": "string", "enum": ["score"]},
                                                         "direction": {"type": "string", "enum": ["increase", "decrease"]},
                                                         "expected_change": dict(s)}},
                           "tradeoffs": dict(s), "confidence": {"type": "number"}, "verification": dict(s)}}
    return {"type": "object", "additionalProperties": False, "required": ["diagnosis", "proposals"],
            "properties": {"diagnosis": {"type": "object", "additionalProperties": False, "required": ["summary", "hypotheses"],
                                         "properties": {"summary": dict(s), "hypotheses": {"type": "array", "items": hyp}}},
                           "proposals": {"type": "array", "items": prop}}}


REPLY_JSON_SCHEMA = _schema()   # generic (contracts 5.3); `build_reply_schema` tightens it per evidence pack


def build_reply_schema(evidence: dict, allowed_params, *, max_proposals: int = 3) -> dict:
    """The reply JSON schema for ONE evidence pack: hypothesis ids and proposal.hypothesis are enums H1..H3, every citation must be one of the
    pack's scalar leaf paths (`evidence.leaf_paths`), and edit params are an enum of the editable parameters of the challenge.
    `allowed_params`: an iterable of parameter ids or the `interventions.editable_params` dict."""
    return _schema(leaf_paths(evidence), list(allowed_params), max_proposals)


def response_format(schema: dict) -> dict:
    return {"type": "json_schema", "json_schema": {"name": SCHEMA_NAME, "schema": schema, "strict": True}}


# ------------------------------------------------------------------------------------------------------------------ prompt
_CHALLENGES = {
    "stand": ("STAND: after a small random initial perturbation the creature must stay upright for {duration:g} s under a fixed standing controller "
              "(joint PD with ankle balance feedback). Score = seconds survived before falling (higher is better, at most {duration:g})."),
    "push": ("PUSH: the creature stands, then a horizontal shove of 0.15 s is applied to the torso. For each seed the largest survivable shove is "
             "searched forwards and backwards (up to a ceiling). Score = the smaller of the two critical forces in newtons (higher is better); "
             "PASS needs score >= challenge.target_force."),
    "walk": ("WALK: the creature must walk forward for {duration:g} s under a phase-based gait controller with 15 parameters. Score = forward distance "
             "in metres travelled while upright with a valid gait (0 if it falls within 1 s). PASS means the walking criteria were met."),
}


def _acceptance_rule(kind: str) -> str:
    """The deterministic verification rule in words (protocol facts from verdict.MIN_EFFECT, not a hint about which change helps)."""
    from .verdict import MIN_EFFECT
    m = MIN_EFFECT[kind]
    if kind == "push":
        need = (f"the median per-seed gain in critical push force must be at least {m['abs']:g} N and at least {m['rel']:.0%} of the "
                "original's median; forces are measured to 0.625 N")
    elif kind == "stand":
        need = f"the median per-seed gain in survival time must be at least {m['abs']:g} s"
    else:
        need = f"the median per-seed gain in valid walking distance must be at least {m['abs']:g} m"
    return (f"verdict_v1): on held-out seeds, paired with the unchanged creature, {need}, and the gains must be consistent across seeds "
            "(one-sided sign test, p < 0.05).")


def build_system_prompt(kind: str, mode: str, allowed: dict, max_proposals: int = 3, duration: float = 0.0) -> str:
    lines = [f"- {p} [{d['kind']}; targets {'|'.join(d['targets'])}] {d['meaning']}" for p, d in allowed.items()]
    guided = mode == "guided"
    control_u = ("control parameters (stand.*, walk.*): the change in u = (value - lo) / (hi - lo) must satisfy |delta u| <= 0.25"
                 " (lo, hi and u are in EDIT BOUNDS)")
    return "\n".join([
        "You are the Physics Investigator of Creature Forge. A person drew a planar (side-view, 2-D) two-legged creature: a torso with a REAR leg "
        "and a FRONT leg, each with thigh, shank, foot and hip, knee, ankle motors. MuJoCo simulates it under gravity 9.81 m/s^2.",
        "",
        "CHALLENGE. " + _CHALLENGES[kind].format(duration=duration),
        "Outcome per seed: PASS, POOR (did it, but with a small margin) or FAIL (fell / cannot do it); ERROR means the run itself failed.",
        "",
        "HOW YOU ARE JUDGED. Your proposals are untrusted. MuJoCo will independently re-run the original creature and each valid proposal on fresh "
        "random seeds, and ALSO a matched-random edit of the same size and a simple rule-based heuristic. A change is adopted only if it beats the "
        "original significantly; your confidence is never used. So diagnose carefully and honestly. If no change is likely to help, say so: "
        "give low confidence (<= 0.2) on your best small proposal instead of guessing.",
        "ACCEPTANCE RULE (" + _acceptance_rule(kind) + " A change smaller than this is recorded as not verified even if it helps a little, "
        "so size each edit to the effect you predict (within the edit rules below).",
        "",
        "EVIDENCE. The user message lists every measurement as one `path=value` line; these paths are the ONLY citable ones. Seeds are ordered "
        "worst to best by score (seeds[0] is the worst). Derived: leg_length = thigh + shank; foot_to_leg = mean foot length / mean leg length; "
        "weight_n = mass_total * 9.81; torque_to_weight = torque_limit / (weight_n * mean leg length); heel_behind_ankle_* and "
        "toe_ahead_of_ankle_* = how far each sole reaches behind / in front of its ankle in the compiled model (both scale with foot_length). "
        "A second section, EDIT BOUNDS, gives each "
        "editable parameter's current value and range.",
        "",
        f"EDITABLE PARAMETERS (mode: {mode}):",
        *lines,
        "",
        "EDIT RULES. Each edit = {param, op, value, target}. op 'scale': new = old * value. op 'set': new = value. At most 4 edits, no two on the same "
        "field. Morphology/actuation: new/old ratio in [0.5, 1.5]; " + control_u + ". The result must stay inside the bounds: out-of-range edits are "
        "REJECTED, never clipped. "
        + ("Guided mode: legs stay symmetric, so target must be 'both'." if guided else
           "target 'rear'/'front' applies to leg lengths only; every other parameter uses 'both'.")
        + " The pose cannot be edited. A proposal's category must equal the kinds of its edits: 'morphology' (morphology and torque_limit), "
        "'control' (stand.* or walk.*) or 'combined'. "
        + ("retune_controller may be true: every arm then gets the same short walking-controller re-adaptation after the edits. "
           if kind == "walk" else "retune_controller must be false. "),
        "",
        "REPLY: ONE JSON object, nothing else (no prose, no code fence):",
        '{"diagnosis":{"summary":"<=400 chars","hypotheses":[{"id":"H1","mechanism":"what physically happens and why",'
        '"evidence":["<path copied from the EVIDENCE lines>"],"competing":["an alternative explanation"]}]},'
        '"proposals":[{"id":"P1","hypothesis":"H1","category":"morphology|control|combined",'
        '"edits":[{"param":"<editable id>","op":"scale|set","value":0.0,"target":"both"}],"retune_controller":false,'
        '"prediction":{"metric":"score","direction":"increase","expected_change":"..."},"tradeoffs":"...","confidence":0.0,"verification":"..."}]}',
        f"Rules: 1-{MAX_HYPOTHESES} hypotheses with ids exactly H1, H2, H3 (upper case); 1-{max_proposals} proposals with ids P1, P2, P3. "
        "proposals[].hypothesis is the hypothesis ID (e.g. \"H1\"), never its text. Each hypothesis cites 1-6 paths copied EXACTLY from the EVIDENCE lines "
        "(the path only, left of '=', no value appended); prefer numeric measurements. confidence is a number in [0, 1]. Keep every text field short.",
    ])


def _bounds_lines(allowed: dict) -> list[str]:
    out = []
    for p, d in allowed.items():
        cur = f"rear={d['rear']:g} front={d['front']:g}" if "rear" in d else f"current={d['current']:g}"
        out.append(f"{p}: {cur} range=[{d['lo']:g}, {d['hi']:g}]" + (f" u={d['u']:g}" if "u" in d else ""))
    return out


def evidence_lines(evidence: dict) -> list[str]:
    """One `path=value` line per citable scalar (JSON-encoded values)."""
    return [f"{p}={json.dumps(v, ensure_ascii=False)}" for p, v in leaf_items(evidence)]


def build_messages(evidence: dict, *, allowed: dict, max_proposals: int = 3) -> list[dict]:
    """[system, user] messages. `allowed` = `interventions.editable_params(version, kind)`. The user message renders the evidence pack as flat
    `path=value` lines (the model copies exact paths; they are the same paths the reply schema enumerates) plus the edit bounds. Contains no
    hint of which change is right."""
    ch, cr = evidence["challenge"], evidence["creature"]
    system = build_system_prompt(ch["kind"], cr["mode"], allowed, max_proposals, float(ch.get("duration", 0.0)))
    user = "EVIDENCE (path=value):\n" + "\n".join(evidence_lines(evidence)) + "\n\nEDIT BOUNDS:\n" + "\n".join(_bounds_lines(allowed))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def prompt_sha256(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------------------ config and call
@dataclass
class ModelConfig:
    model: str
    max_tokens: int = 16000
    temperature: float = 0.6
    reasoning_effort: str | None = "low"
    extra_body: dict | None = None          # e.g. {"chat_template_kwargs": {"enable_thinking": False}}
    json_schema: bool = True                # send response_format json_schema (strict)
    timeout_s: float = 180.0

    def validate(self) -> "ModelConfig":
        if self.reasoning_effort is not None and self.reasoning_effort not in REASONING_EFFORTS:
            raise ValueError(f"reasoning_effort must be one of {REASONING_EFFORTS}")
        if self.extra_body is not None:
            if not isinstance(self.extra_body, dict):
                raise ValueError("extra_body must be a dict")
            clash = sorted(set(self.extra_body) & RESERVED_BODY_KEYS)
            if clash:
                raise ValueError(f"extra_body may not override {clash}")
        if self.max_tokens < 1 or self.timeout_s <= 0:
            raise ValueError("max_tokens must be >= 1 and timeout_s > 0")
        return self


def make_client(cfg: ModelConfig, *, transport=None, api_key: str | None = None, base_url: str | None = None,
                max_requests: int = 4, max_total_tokens: int = 80_000) -> NebiusClient:
    """A NebiusClient whose Limits fit this config (the default Limits allow only 4096 completion tokens)."""
    kw = {} if transport is None else {"transport": transport}
    return NebiusClient(model=cfg.model, api_key=api_key, base_url=base_url, **kw,
                        limits=Limits(max_requests=max_requests, max_total_tokens=max_total_tokens,
                                      max_tokens_per_request=max(cfg.max_tokens, 1), timeout_s=cfg.timeout_s))


@dataclass
class ModelCall:
    """Everything about one model request. Never contains the API key."""
    model: str
    settings: dict
    prompt_sha256: str
    messages: list
    raw_response: dict | None = None
    content: str | None = None
    reasoning_present: bool = False
    request_id: str | None = None
    latency_s: float = 0.0
    usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    finish_reason: str | None = None
    http_status: int | None = None
    error: str | None = None
    budget_refused: bool = False
    sent: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.content and self.content.strip())

    def as_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["ok"] = self.ok
        return d


class _Recorder:
    """Transport wrapper capturing the raw exchange of the call it wraps (the client keeps only a digest)."""

    def __init__(self, inner):
        self.inner, self.calls, self.status, self.headers, self.raw, self.body = inner, 0, None, None, None, None

    def __call__(self, url, headers, body, timeout):
        self.calls += 1
        self.body = body
        status, resp_headers, raw = self.inner(url, headers, body, timeout)
        self.status, self.headers, self.raw = status, resp_headers, raw
        return status, resp_headers, raw


def _http_status(err: str) -> int | None:
    m = re.match(r"HTTP (\d{3})", err or "")
    return int(m.group(1)) if m else None


def call_model(client, cfg: ModelConfig, messages: list[dict], ledger: InferenceLedger, *, investigation_id: str,
               purpose: str = "investigation", response_schema: dict | None = None) -> ModelCall:
    """One request (never retried). Reserves ledger budget first; a refusal is returned as a recorded failure BEFORE any transport call.
    With cfg.json_schema the request carries response_format json_schema strict (`response_schema`, default REPLY_JSON_SCHEMA); cfg.extra_body
    is merged into the body by the client. Also sets client.model / limits.timeout_s from cfg."""
    cfg.validate()
    schema = response_schema or REPLY_JSON_SCHEMA
    settings = {"temperature": cfg.temperature, "max_tokens": cfg.max_tokens, "reasoning_effort": cfg.reasoning_effort,
                "json_schema": cfg.json_schema, "schema_name": SCHEMA_NAME if cfg.json_schema else None,
                "extra_body": copy.deepcopy(cfg.extra_body), "timeout_s": cfg.timeout_s, "purpose": purpose,
                "investigation_id": investigation_id}
    call = ModelCall(cfg.model, settings, prompt_sha256(messages), messages)
    try:
        res = ledger.reserve(estimate_prompt_tokens(messages), cfg.max_tokens, cfg.model, investigation_id=investigation_id, purpose=purpose)
    except BudgetExceeded as e:
        call.error, call.budget_refused = f"{type(e).__name__}: {e}", True
        return call
    client.model = cfg.model
    if hasattr(client, "limits"):
        client.limits = dataclasses.replace(client.limits, timeout_s=cfg.timeout_s)
    rec = _Recorder(client.transport)
    client.transport = rec.__call__
    try:
        result = client.chat(messages, max_tokens=cfg.max_tokens, temperature=cfg.temperature, reasoning_effort=cfg.reasoning_effort,
                             response_format=response_format(schema) if cfg.json_schema else None, extra_body=cfg.extra_body)
    except NebiusError as e:
        call.error = f"{type(e).__name__}: {str(e)[:400]}"
        call.http_status = _http_status(str(e))
    except BaseException:  # noqa: BLE001 - account for the reservation, then let the caller see the real exception
        client.transport = rec.inner
        try:
            if rec.calls > 0:  # possibly sent: never undercount, settle at the worst case
                ledger.settle(res, request_id=None, prompt_tokens=None, completion_tokens=None, status="error", usage_estimated=True)
            else:
                ledger.release(res)
        except Exception:  # noqa: BLE001 - a ledger failure must not mask the original exception
            pass
        raise
    finally:
        client.transport = rec.inner
    call.sent = rec.calls > 0
    call.raw_response = rec.raw if isinstance(rec.raw, dict) else None
    usage = (call.raw_response or {}).get("usage") or {}
    pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if call.error is None:
        call.content, call.finish_reason, call.reasoning_present = result.content, result.finish_reason, result.reasoning_present
        call.request_id, call.latency_s, call.usage, call.http_status = result.request_id, result.latency_s, dict(result.usage), result.http_status
        pt, ct = result.usage.get("prompt_tokens"), result.usage.get("completion_tokens")
        if result.finish_reason == "length":
            call.error = (f"finish_reason=length: the completion budget ({cfg.max_tokens} tokens) ran out"
                          f"{' while reasoning' if result.reasoning_present else ''}; the reply is not used")
        elif result.content is None:
            call.error = "content_null: the model returned no message content"
        elif not result.content.strip():
            call.error = "content_empty: the model returned blank content"
    if not call.sent:
        ledger.release(res)  # refused locally (client limits): no request happened
    else:
        # Sent but usage unknown (timeout, HTTP error, malformed response): settle at the reservation's worst case, flagged.
        row = ledger.settle(res, request_id=call.request_id, prompt_tokens=pt, completion_tokens=ct, status="ok" if call.error is None else "error",
                            usage_estimated=(pt is None or ct is None))
        call.cost_usd = row["cost_usd"]
        if row.get("usage_estimated"):
            call.usage = {"prompt_tokens": row["prompt_tokens"], "completion_tokens": row["completion_tokens"], "usage_estimated": True}
        elif call.usage == {} and (pt is not None or ct is not None):
            call.usage = {"prompt_tokens": pt, "completion_tokens": ct}
    return call


# ------------------------------------------------------------------------------------------------------------------ parsing
class ReplyParseError(ValueError):
    """The reply text is not one JSON object."""


_THINK_END = "</think>"
_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)\s*```", re.DOTALL)


def parse_reply(text: str | None) -> dict:
    """Extract the single JSON object of a reply. Tolerates a leading `<think>...</think>` block (or a bare trailing `</think>`) and a code
    fence; rejects empty text, unterminated think blocks, top-level lists/non-objects and trailing text after the object."""
    if text is None or not text.strip():
        raise ReplyParseError("reply has no content")
    s = text
    if _THINK_END in s:
        s = s.rsplit(_THINK_END, 1)[1]
    elif "<think>" in s:
        raise ReplyParseError("reply is an unterminated <think> block")
    s = s.strip()
    m = _FENCE.search(s)
    if m and not s.startswith("{"):
        s = m.group(1).strip()
    elif s.startswith("```"):
        s = re.sub(r"^```(?:json|JSON)?\s*|\s*```$", "", s).strip()
    if not s:
        raise ReplyParseError("reply is empty after removing the thinking block")
    if s[0] != "{":
        raise ReplyParseError("reply is not a JSON object (a top-level " + ("list" if s[0] == "[" else "value") + " or prose)")
    try:
        obj, end = json.JSONDecoder().raw_decode(s)
    except json.JSONDecodeError as e:
        raise ReplyParseError(f"reply is not valid JSON ({e.msg} at char {e.pos})") from None
    if s[end:].strip():
        raise ReplyParseError("unexpected text after the JSON object")
    return obj


# ------------------------------------------------------------------------------------------------------------------ validation
def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _exact(obj, required: set, optional: set, where: str, reasons: list) -> bool:
    if not isinstance(obj, dict):
        reasons.append(f"{where}: must be an object")
        return False
    miss, extra = sorted(required - set(obj)), sorted(set(obj) - required - optional)
    if miss:
        reasons.append(f"{where}: missing field(s) {miss}")
    if extra:
        reasons.append(f"{where}: unknown field(s) {extra}")
    return not miss and not extra


def _text(v, where: str, limit: int, reasons: list, warnings: list, required: bool = True) -> str:
    if not isinstance(v, str) or (required and not v.strip()):
        reasons.append(f"{where}: must be a non-empty string")
        return ""
    if len(v) > limit:
        warnings.append(f"{where}: text shortened from {len(v)} to {limit} characters")
        return v[: limit - 1] + "…"
    return v


def _validate_hypothesis(raw, evidence: dict, seen: set, warnings: list) -> dict:
    reasons: list[str] = []
    hid = raw.get("id") if isinstance(raw, dict) else None
    out = {"id": hid if isinstance(hid, str) else "?", "status": "rejected", "reasons": reasons, "mechanism": "", "evidence": [], "competing": [],
           "values": {}}
    w = f"hypothesis {out['id']}"
    if _exact(raw, {"id", "mechanism", "evidence"}, {"competing"}, w, reasons):
        if hid not in HYPOTHESIS_IDS:
            reasons.append(f"{w}: id must be exactly one of {list(HYPOTHESIS_IDS)}")
        elif hid in seen:
            reasons.append(f"{w}: duplicate hypothesis id")
        out["mechanism"] = _text(raw["mechanism"], f"{w} mechanism", TEXT_MAX, reasons, warnings)
        ev = raw["evidence"]
        if not isinstance(ev, list) or not (1 <= len(ev) <= MAX_CITATIONS) or not all(isinstance(x, str) for x in ev):
            reasons.append(f"{w}: evidence must be a list of 1-{MAX_CITATIONS} path strings")
        else:
            for path in ev:
                try:
                    out["values"][path] = resolve(evidence, path)
                except UnresolvedCitation as e:
                    reasons.append(f"{w}: unresolved citation {path!r} ({e})")
            out["evidence"] = list(ev)
        comp = raw.get("competing", [])
        if not isinstance(comp, list) or len(comp) > 3 or not all(isinstance(x, str) for x in comp):
            reasons.append(f"{w}: competing must be a list of up to 3 strings")
        else:
            out["competing"] = [_text(x, f"{w} competing", SHORT_MAX, [], warnings, False) for x in comp]
    if isinstance(hid, str) and hid in HYPOTHESIS_IDS:
        seen.add(hid)
    if not reasons:
        out["status"] = "accepted"
    return out


def _validate_proposal(raw, idx: int, hyps: dict, version: dict, kind: str, seen: set, max_proposals: int, warnings: list) -> dict:
    reasons: list[str] = []
    pid = raw.get("id") if isinstance(raw, dict) else None
    out = {"id": pid if isinstance(pid, str) else f"#{idx + 1}", "status": "rejected", "reasons": reasons}
    w = f"proposal {out['id']}"
    req = {"id", "hypothesis", "category", "edits", "prediction", "confidence"}
    if not _exact(raw, req, {"retune_controller", "tradeoffs", "verification"}, w, reasons):
        return out
    if pid not in PROPOSAL_IDS[:max_proposals]:
        reasons.append(f"{w}: id must be one of {list(PROPOSAL_IDS[:max_proposals])}")
    elif pid in seen:
        reasons.append(f"{w}: duplicate proposal id")
    if isinstance(pid, str):
        seen.add(pid)
    hid = raw["hypothesis"]
    if hid not in HYPOTHESIS_IDS:
        reasons.append(f"{w}: hypothesis must be a hypothesis id {list(HYPOTHESIS_IDS)}, not text (got {str(hid)[:40]!r})")
    elif hid not in hyps:
        reasons.append(f"{w}: unknown hypothesis id {hid!r} (the reply defines {sorted(hyps)})")
    elif hyps[hid]["status"] != "accepted":
        reasons.append(f"{w}: hypothesis {hid} was rejected: " + "; ".join(hyps[hid]["reasons"]))
    cat = raw["category"]
    if cat not in iv.CATEGORIES:
        reasons.append(f"{w}: category must be one of {list(iv.CATEGORIES)}")
    edits, why = iv.validate_edits(version, kind, raw["edits"])
    reasons += [f"{w}: {r}" for r in why]
    if edits and cat in iv.CATEGORIES and iv.category(edits) != cat:
        reasons.append(f"{w}: category mismatch: declared '{cat}' but the edits are '{iv.category(edits)}'")
    rt = raw.get("retune_controller", False)
    if not isinstance(rt, bool):
        reasons.append(f"{w}: retune_controller must be a boolean")
    elif rt and kind != "walk":
        reasons.append(f"{w}: retune_controller is only allowed for walk challenges (challenge is '{kind}')")
    pred = raw["prediction"]
    pr: list[str] = []
    if _exact(pred, {"metric", "direction", "expected_change"}, set(), f"{w} prediction", pr):
        if pred["metric"] != "score":
            pr.append(f"{w} prediction: metric must be 'score'")
        if pred["direction"] not in ("increase", "decrease"):
            pr.append(f"{w} prediction: direction must be 'increase' or 'decrease'")
        _text(pred["expected_change"], f"{w} prediction expected_change", SHORT_MAX, pr, warnings)
    reasons += pr
    conf = raw["confidence"]
    if not _is_num(conf) or not (0.0 <= conf <= 1.0):
        reasons.append(f"{w}: confidence must be a number in [0, 1]")
    trade = _text(raw.get("tradeoffs", ""), f"{w} tradeoffs", TEXT_MAX, reasons, warnings, False)
    verif = _text(raw.get("verification", ""), f"{w} verification", TEXT_MAX, reasons, warnings, False)
    if reasons:
        return out
    h = hyps[hid]
    out.update(status="accepted", hypothesis=hid, category=cat, edits=[e.to_dict() for e in edits], retune_controller=rt,
               prediction=dict(pred), tradeoffs=trade, confidence=float(conf), verification=verif, citations=list(h["evidence"]),
               magnitudes=[round(iv.magnitude(version, e), 6) for e in edits])
    return out


def validate_reply(reply: dict, evidence: dict, version: dict, kind: str, *, max_proposals: int = 3) -> dict:
    """Validate a parsed reply. Returns {"schema_errors": [...], "hypotheses": [...], "proposals": [{id, status, reasons, ...}], "warnings": [...]}.
    `schema_errors` are envelope problems (no usable structure); per-hypothesis/proposal problems are reasons on that item only, so one bad
    proposal (e.g. an unresolved citation) never rejects the others. Accepted proposals carry normalised edits, citations and magnitudes."""
    res = {"schema_errors": [], "hypotheses": [], "proposals": [], "warnings": []}
    errs, warns = res["schema_errors"], res["warnings"]
    if not _exact(reply, {"diagnosis", "proposals"}, set(), "reply", errs):
        return res
    diag = reply["diagnosis"]
    if _exact(diag, {"summary", "hypotheses"}, set(), "diagnosis", errs):
        _text(diag["summary"], "diagnosis summary", SUMMARY_MAX, errs, warns)
        hl = diag["hypotheses"]
        if not isinstance(hl, list) or not hl:
            errs.append("diagnosis: hypotheses must be a non-empty list")
        else:
            seen: set = set()
            for i, h in enumerate(hl):
                hv = _validate_hypothesis(h, evidence, seen, warns)
                if i >= MAX_HYPOTHESES:
                    hv["status"] = "rejected"
                    hv["reasons"].append(f"hypothesis {hv['id']}: at most {MAX_HYPOTHESES} hypotheses allowed")
                res["hypotheses"].append(hv)
            res["summary"] = diag["summary"] if isinstance(diag["summary"], str) else ""
    pl = reply["proposals"]
    if not isinstance(pl, list) or not pl:
        errs.append("proposals must be a non-empty list")
        return res
    hyps = {h["id"]: h for h in res["hypotheses"]}
    seen_p: set = set()
    for i, p in enumerate(pl):
        pv = _validate_proposal(p, i, hyps, version, kind, seen_p, max_proposals, warns)
        if i >= max_proposals:
            pv["status"] = "rejected"
            pv["reasons"].append(f"proposal {pv['id']}: at most {max_proposals} proposals allowed")
        res["proposals"].append(pv)
    return res


# ------------------------------------------------------------------------------------------------------------------ orchestration
def accepted_proposals(validation: dict | None) -> list[dict]:
    return [p for p in (validation or {}).get("proposals", []) if p["status"] == "accepted"]


def validation_errors(validation: dict) -> list[str]:
    out = list(validation.get("schema_errors", []))
    for h in validation.get("hypotheses", []):
        out += h["reasons"] if h["status"] != "accepted" else []
    for p in validation.get("proposals", []):
        out += p["reasons"] if p["status"] != "accepted" else []
    return out


def _repair_messages(messages: list[dict], first: ModelCall, errors: list[str]) -> list[dict]:
    shown = [e[:300] for e in errors[:REPAIR_ERRORS_MAX]]
    more = f"\n(+{len(errors) - len(shown)} more)" if len(errors) > len(shown) else ""
    prompt = ("Your previous reply was rejected by the validator:\n- " + "\n- ".join(shown) + more +
              "\nReturn ONE corrected JSON object in the same format, following every rule (ids H1..H3 / P1..P3, citations copied exactly from "
              "the EVIDENCE lines, edits inside the rules). No prose.")
    return messages + [{"role": "assistant", "content": (first.content or "")[:REPAIR_ECHO_MAX]}, {"role": "user", "content": prompt}]


def _assess(call: ModelCall, evidence: dict, version: dict, kind: str, max_proposals: int) -> dict:
    """{'reply', 'validation', 'errors'}: errors non-empty = the reply needs repair."""
    try:
        reply = parse_reply(call.content)
    except ReplyParseError as e:
        return {"reply": None, "validation": None, "errors": [str(e)]}
    val = validate_reply(reply, evidence, version, kind, max_proposals=max_proposals)
    errors = validation_errors(val) if (val["schema_errors"] or not accepted_proposals(val)) else []
    return {"reply": reply, "validation": val, "errors": errors}


def investigate_once(client, cfg: ModelConfig, version: dict, challenge_result: dict, history: list[dict] | None,
                     ledger: InferenceLedger, *, investigation_id: str | None = None, max_proposals: int = 3) -> dict:
    """Evidence -> prompt -> model -> parse -> validate, with at most ONE repair call (so <= 2 requests).
    Returns {status, investigation_id, evidence, evidence_bytes, calls, reply, validation, accepted, repaired, error, allowed}.
    status: 'ok' (>= 1 accepted proposal) | 'no_valid_proposal' (replies arrived but none valid) | 'model_failed' (the call that was needed failed:
    HTTP/timeout/null content/finish_reason=length/budget refusal). A repair is made only for an unparseable, schema-invalid or all-rejected
    reply, never after a failed call."""
    kind = challenge_result["spec"]["kind"]
    inv = investigation_id or f"i-{uuid.uuid4().hex[:12]}"
    evidence = build_evidence(version, challenge_result, history)
    allowed = iv.editable_params(version, kind)
    messages = build_messages(evidence, allowed=allowed, max_proposals=max_proposals)
    schema = build_reply_schema(evidence, allowed, max_proposals=max_proposals)
    out = {"status": "model_failed", "investigation_id": inv, "evidence": evidence, "evidence_bytes": pack_size(evidence), "calls": [],
           "reply": None, "validation": None, "accepted": [], "repaired": False, "error": None, "allowed": list(allowed)}

    call = call_model(client, cfg, messages, ledger, investigation_id=inv, response_schema=schema)
    out["calls"].append(call.as_dict())
    if not call.ok:
        out["error"] = call.error
        return out
    a = _assess(call, evidence, version, kind, max_proposals)
    out["reply"], out["validation"] = a["reply"], a["validation"]
    if a["errors"]:
        out["repaired"] = True
        call2 = call_model(client, cfg, _repair_messages(messages, call, a["errors"]), ledger, investigation_id=inv,
                           purpose="investigation_repair", response_schema=schema)
        out["calls"].append(call2.as_dict())
        if not call2.ok:
            out["error"] = f"repair call failed: {call2.error}"
            return out
        a = _assess(call2, evidence, version, kind, max_proposals)
        out["reply"], out["validation"] = a["reply"], a["validation"]
    out["accepted"] = accepted_proposals(out["validation"])
    if out["accepted"]:
        out["status"], out["error"] = "ok", None
    else:
        out["status"] = "no_valid_proposal"
        out["error"] = "; ".join(a["errors"])[:600] or "no proposal passed validation"
    return out


# ------------------------------------------------------------------------------------------------------------------ diagnostic probes (two-step)
# Additive: `investigate_once` above is unchanged and stays the default. With probes the model is called in two steps:
#   step A: evidence + probe catalogue -> hypotheses + 1-3 probe requests (no proposals);
#   executor: validate the requests, run the probes in MuJoCo (`probe_runner`), compute expectation outcomes deterministically;
#   step B: the same evidence + `probes.*` measurements + the step-A hypotheses -> the normal proposal reply.
# Calls: A + B = 2, plus AT MOST ONE repair shared by both steps (<= 3 requests, below the ledger's per-investigation cap of 4).
PROBE_STEP_MARK = "PROBE STEP A"
_REPLY_MARK = "\nREPLY: ONE JSON object"


def build_probe_schema(evidence: dict, probe_ids, allowed_params=None) -> dict:
    """Step-A reply schema: the diagnosis exactly as in the proposal schema (citations enumerated) and `probes` with the probe ids enumerated."""
    diag = _schema(leaf_paths(evidence), list(allowed_params) if allowed_params else None)["properties"]["diagnosis"]
    probe = {"type": "object", "additionalProperties": False, "required": ["probe_id", "hypothesis", "expect"],
             "properties": {"probe_id": {"type": "string", "enum": list(probe_ids)},
                            "hypothesis": {"type": "string", "enum": list(HYPOTHESIS_IDS)},
                            "expect": {"type": "string", "enum": list(pb.EXPECTATIONS)}}}
    return {"type": "object", "additionalProperties": False, "required": ["diagnosis", "probes"],
            "properties": {"diagnosis": diag, "probes": {"type": "array", "items": probe}}}


def build_probe_system_prompt(kind: str, mode: str, allowed: dict, probe_ids, *, n_seeds: int, resolution: float, duration: float = 0.0,
                              max_probes: int = pb.MAX_PROBES) -> str:
    head = build_system_prompt(kind, mode, allowed, 3, duration).split(_REPLY_MARK)[0]
    return "\n".join([
        head, "",
        f"{PROBE_STEP_MARK} (diagnosis). Before you propose anything you may run diagnostic probes: counterfactual MuJoCo experiments on the CURRENT "
        "creature. A probe is never a proposal and is never adopted; it only tells you which mechanism matters. Each probe is run on "
        f"{n_seeds} fresh random seeds, paired with the unchanged creature, and you will receive the median per-seed change in score "
        f"(a change smaller than the score resolution {resolution:g} counts as no change).",
        "AVAILABLE PROBES:", *pb.catalogue_lines(probe_ids), "",
        "REPLY: ONE JSON object, nothing else (no prose, no code fence), with NO proposals yet:",
        '{"diagnosis":{"summary":"<=400 chars","hypotheses":[{"id":"H1","mechanism":"what physically happens and why",'
        '"evidence":["<path copied from the EVIDENCE lines>"],"competing":["an alternative explanation"]}]},'
        '"probes":[{"probe_id":"<one of the available probes>","hypothesis":"H1","expect":"increase|decrease|no_change"}]}',
        f"Rules: 1-{MAX_HYPOTHESES} hypotheses with ids exactly H1, H2, H3, each citing 1-{MAX_CITATIONS} paths copied EXACTLY from the EVIDENCE lines. "
        f"1-{max_probes} distinct probes; each names the hypothesis it tests and what you EXPECT the median change in score to be relative to the "
        "unchanged creature (increase, decrease or no_change). Choose probes that would tell your hypotheses apart. Keep every text field short.",
    ])


def build_probe_messages(evidence: dict, *, allowed: dict, probe_ids, n_seeds: int, resolution: float) -> list[dict]:
    ch, cr = evidence["challenge"], evidence["creature"]
    system = build_probe_system_prompt(ch["kind"], cr["mode"], allowed, probe_ids, n_seeds=n_seeds, resolution=resolution,
                                       duration=float(ch.get("duration", 0.0)))
    user = "EVIDENCE (path=value):\n" + "\n".join(evidence_lines(evidence)) + "\n\nEDIT BOUNDS:\n" + "\n".join(_bounds_lines(allowed))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


_STEP_B_NOTE = (
    "PROBE RESULTS. In step A you stated hypotheses and asked for diagnostic probes; MuJoCo has run them. The measurements are in the EVIDENCE as "
    "probes.* (probes.<id>.median_delta = median per-seed change in score of the probed variant versus the unchanged creature; wins/losses/ties "
    "count seeds beyond probes.resolution; probes.no_push.* is a measurement of the unchanged creature without a push). Revise your hypotheses in "
    "light of them: drop or reword one a probe contradicted, and cite probes.* paths where they support one. A probe is a counterfactual "
    "measurement, not a verified improvement: your proposals below are still tested independently on held-out seeds. "
    "METHOD: a refuted expectation is evidence against that mechanism. Do not propose strengthening a factor whose probe showed no change, "
    "or a change in the direction a probe showed to be harmful, unless you cite other evidence that explains why; prefer mechanisms a probe "
    "confirmed, then ones no probe has tested. If every tested mechanism was refuted, say so in the summary and form a new hypothesis.")


def build_step_b_messages(evidence: dict, *, allowed: dict, hypotheses: list[dict], requests: list[dict], max_proposals: int = 3,
                          expectations: list[dict] | None = None) -> list[dict]:
    """[system, user] for step B: the normal proposal prompt (+ a probe note) over the evidence INCLUDING the `probes` section."""
    msgs = build_messages(evidence, allowed=allowed, max_proposals=max_proposals)
    msgs[0]["content"] += "\n\n" + _STEP_B_NOTE
    lines = [f"- {h['id']}: {h.get('mechanism', '')}" for h in hypotheses if h.get("status") == "accepted"]
    outcome = {e.get("probe_id"): e for e in expectations or []}
    for r in requests:
        e = outcome.get(r["probe_id"]) or {}
        verdict = {True: "CONFIRMED", False: "REFUTED"}.get(e.get("confirmed"), "not decidable")
        measured = f"; MuJoCo measured: {e.get('observed')} -> {verdict}" if e else ""
        lines.append(f"- probe {r['probe_id']} tested {r['hypothesis']}; you expected: {r['expect']}{measured}")
    msgs[1]["content"] += "\n\nYOUR STEP A (hypotheses and probes requested):\n" + "\n".join(lines)
    return msgs


def validate_probe_reply(reply, evidence: dict, probe_ids, *, max_probes: int = pb.MAX_PROBES) -> dict:
    """{schema_errors, hypotheses, probes: [{probe_id, hypothesis, expect, status, reasons}], accepted_probes, warnings}. A probe is accepted only
    if its id is in `probe_ids` (the available catalogue), it is not a duplicate, its hypothesis is an ACCEPTED hypothesis of this reply and
    `expect` is valid; at most `max_probes` are accepted."""
    res = {"schema_errors": [], "hypotheses": [], "probes": [], "accepted_probes": [], "warnings": []}
    errs, warns = res["schema_errors"], res["warnings"]
    if not _exact(reply, {"diagnosis", "probes"}, set(), "reply", errs):
        return res
    diag = reply["diagnosis"]
    if _exact(diag, {"summary", "hypotheses"}, set(), "diagnosis", errs):
        _text(diag["summary"], "diagnosis summary", SUMMARY_MAX, errs, warns)
        hl = diag["hypotheses"]
        if not isinstance(hl, list) or not hl:
            errs.append("diagnosis: hypotheses must be a non-empty list")
        else:
            seen: set = set()
            for i, h in enumerate(hl):
                hv = _validate_hypothesis(h, evidence, seen, warns)
                if i >= MAX_HYPOTHESES:
                    hv["status"] = "rejected"
                    hv["reasons"].append(f"hypothesis {hv['id']}: at most {MAX_HYPOTHESES} hypotheses allowed")
                res["hypotheses"].append(hv)
            res["summary"] = diag["summary"] if isinstance(diag["summary"], str) else ""
    pl = reply["probes"]
    if not isinstance(pl, list) or not pl:
        errs.append("probes must be a non-empty list")
        return res
    hyps = {h["id"]: h for h in res["hypotheses"]}
    seen_p: set = set()
    for i, p in enumerate(pl):
        reasons: list[str] = []
        pid = p.get("probe_id") if isinstance(p, dict) else None
        out = {"probe_id": pid if isinstance(pid, str) else f"#{i + 1}", "hypothesis": None, "expect": None, "status": "rejected", "reasons": reasons}
        w = f"probe {out['probe_id']}"
        if _exact(p, {"probe_id", "hypothesis", "expect"}, set(), w, reasons):
            if pid not in probe_ids:
                reasons.append(f"{w}: probe_id must be one of {list(probe_ids)}")
            elif pid in seen_p:
                reasons.append(f"{w}: duplicate probe")
            seen_p.add(pid)
            hid = p["hypothesis"]
            if hid not in HYPOTHESIS_IDS:
                reasons.append(f"{w}: hypothesis must be a hypothesis id {list(HYPOTHESIS_IDS)}")
            elif hid not in hyps or hyps[hid]["status"] != "accepted":
                reasons.append(f"{w}: hypothesis {hid} is not an accepted hypothesis of this reply")
            if p["expect"] not in pb.EXPECTATIONS:
                reasons.append(f"{w}: expect must be one of {list(pb.EXPECTATIONS)}")
            out.update(hypothesis=hid if isinstance(hid, str) else None, expect=p["expect"] if isinstance(p["expect"], str) else None)
        if not reasons and len(res["accepted_probes"]) >= max_probes:
            reasons.append(f"{w}: at most {max_probes} probes allowed")
        if not reasons:
            out["status"] = "accepted"
            res["accepted_probes"].append({"probe_id": pid, "hypothesis": out["hypothesis"], "expect": out["expect"]})
        res["probes"].append(out)
    return res


def _probe_errors(val: dict) -> list[str]:
    out = list(val["schema_errors"])
    for h in val["hypotheses"]:
        out += h["reasons"] if h["status"] != "accepted" else []
    for p in val["probes"]:
        out += p["reasons"] if p["status"] != "accepted" else []
    return out


def _assess_probe_plan(call: ModelCall, evidence: dict, probe_ids) -> dict:
    try:
        reply = parse_reply(call.content)
    except ReplyParseError as e:
        return {"reply": None, "validation": None, "errors": [str(e)]}
    val = validate_probe_reply(reply, evidence, probe_ids)
    errors = _probe_errors(val) if (val["schema_errors"] or not val["accepted_probes"]) else []
    return {"reply": reply, "validation": val, "errors": errors}


def investigate_with_probes(client, cfg: ModelConfig, version: dict, challenge_result: dict, history: list[dict] | None,
                            ledger: InferenceLedger, *, probe_runner, investigation_id: str | None = None, max_proposals: int = 3,
                            n_probe_seeds: int = pb.MAX_PROBE_SEEDS, probe_spec: dict | None = None) -> dict:
    """Two-step investigation with diagnostic probes. `probe_runner(requests, probe_ids) -> run_probes() dict` runs the MuJoCo probes (it never
    sees the model). Returns what `investigate_once` returns (evidence = the step-B pack incl. `probes`; calls = every request) plus
    `probes`: {requested, step_a_reply, step_a_validation, results, original, expectations, seeds, rollouts, resolution, available}.
    Requests: step A, step B, and at most ONE repair in total (shared). A failed/invalid step A ends the run without running probes
    (`model_failed` / `no_valid_proposal`). If no probe is available for this challenge, falls back to `investigate_once`."""
    kind = challenge_result["spec"]["kind"]
    inv = investigation_id or f"i-{uuid.uuid4().hex[:12]}"
    pspec = probe_spec or challenge_result["spec"]   # the spec the probes will run with (push: finer bisection than the stored run)
    avail = pb.available_probes(version, kind, pspec)
    if not avail:
        out = investigate_once(client, cfg, version, challenge_result, history, ledger, investigation_id=inv, max_proposals=max_proposals)
        out["probes"] = {"requested": [], "skipped": "no probe is available for this creature and challenge", "available": []}
        return out
    evidence = build_evidence(version, challenge_result, history)
    allowed = iv.editable_params(version, kind)
    res_tol = pb.resolution_for(kind, pspec)
    out = {"status": "model_failed", "investigation_id": inv, "evidence": evidence, "evidence_bytes": pack_size(evidence), "calls": [],
           "reply": None, "validation": None, "accepted": [], "repaired": False, "error": None, "allowed": list(allowed),
           "probes": {"requested": [], "available": avail, "step_a_reply": None, "step_a_validation": None}}
    msgs_a = build_probe_messages(evidence, allowed=allowed, probe_ids=avail, n_seeds=n_probe_seeds, resolution=res_tol)
    schema_a = build_probe_schema(evidence, avail, allowed)
    call = call_model(client, cfg, msgs_a, ledger, investigation_id=inv, purpose="investigation_probe_plan", response_schema=schema_a)
    out["calls"].append(call.as_dict())
    if not call.ok:
        out["error"] = call.error
        return out
    a = _assess_probe_plan(call, evidence, avail)
    repairs = 1
    if a["errors"]:
        repairs, out["repaired"] = 0, True
        call2 = call_model(client, cfg, _repair_messages(msgs_a, call, a["errors"]), ledger, investigation_id=inv,
                           purpose="investigation_repair", response_schema=schema_a)
        out["calls"].append(call2.as_dict())
        if not call2.ok:
            out["error"] = f"repair call failed: {call2.error}"
            return out
        a = _assess_probe_plan(call2, evidence, avail)
    out["probes"]["step_a_reply"], out["probes"]["step_a_validation"] = a["reply"], a["validation"]
    if a["errors"]:
        out["status"] = "no_valid_proposal"
        out["error"] = "step A (probe plan): " + "; ".join(a["errors"])[:560]
        return out
    val_a = a["validation"]
    requests = list(val_a["accepted_probes"])
    out["probes"]["requested"] = requests
    ran = probe_runner(requests, [r["probe_id"] for r in requests])
    expectations = pb.evaluate_expectations(requests, ran)
    out["probes"].update(results=ran["results"], original=ran.get("original"), expectations=expectations, seeds=ran["seeds"],
                         rollouts=ran["rollouts"], resolution=ran["resolution"], bisection_steps=ran.get("bisection_steps"))
    evidence_b = {**evidence, "probes": pb.evidence_block(ran)}
    out["evidence"], out["evidence_bytes"] = evidence_b, pack_size(evidence_b)
    msgs_b = build_step_b_messages(evidence_b, allowed=allowed, hypotheses=val_a["hypotheses"], requests=requests, max_proposals=max_proposals,
                                   expectations=expectations)
    schema_b = build_reply_schema(evidence_b, allowed, max_proposals=max_proposals)
    callb = call_model(client, cfg, msgs_b, ledger, investigation_id=inv, purpose="investigation", response_schema=schema_b)
    out["calls"].append(callb.as_dict())
    if not callb.ok:
        out["error"] = f"step B failed: {callb.error}"
        return out
    b = _assess(callb, evidence_b, version, kind, max_proposals)
    out["reply"], out["validation"] = b["reply"], b["validation"]
    if b["errors"] and repairs:
        out["repaired"] = True
        callr = call_model(client, cfg, _repair_messages(msgs_b, callb, b["errors"]), ledger, investigation_id=inv,
                           purpose="investigation_repair", response_schema=schema_b)
        out["calls"].append(callr.as_dict())
        if not callr.ok:
            out["error"] = f"repair call failed: {callr.error}"
            return out
        b = _assess(callr, evidence_b, version, kind, max_proposals)
        out["reply"], out["validation"] = b["reply"], b["validation"]
    out["accepted"] = accepted_proposals(out["validation"])
    if out["accepted"]:
        out["status"], out["error"] = "ok", None
    else:
        out["status"] = "no_valid_proposal"
        out["error"] = "; ".join(b["errors"])[:600] or "no proposal passed validation"
    return out
