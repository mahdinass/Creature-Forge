#!/usr/bin/env python
"""Forge Loop model calibration (M0): which NVIDIA model + generation settings reliably return a usable, schema-valid
engineering reply for a drawn creature's failure evidence?

Engineering calibration, NOT a scientific claim about model quality. Frozen context: one deliberately poor drawn
creature ("Stubby": 5 cm feet) failing a 25 N push, compact evidence (<= ~6 KB) and the Forge reply schema from
docs/FORGE_LOOP_CONTRACTS.md section 5.3. Pass criteria per request: HTTP 200, finish_reason "stop", non-empty content,
parseable JSON object, schema-valid, every edit whitelisted and within the contract's edit rules, every citation resolves
to a scalar, latency <= 120 s.

    python scripts/forge_calibrate.py --context            # build/freeze the context offline (no network)
    python scripts/forge_calibrate.py --stage A --live     # 4 models x 3 settings x 1 request (12)
    python scripts/forge_calibrate.py --stage B --live --pairs super:A,ultra:B   # 3 reps of chosen pairs (<= 6)
    python scripts/forge_calibrate.py --report             # summarise requests.jsonl -> REPORT.md table (no network)

Hard limits: <= 18 calibration requests in total (counted from requests.jsonl), no retries, ledger cap $15.
Every request/response (raw JSON, request id, usage, latency) is stored in experiments/forge_loop/calibration/.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge.config import load_env, nebius_api_key, nebius_base_url  # noqa: E402

OUT = ROOT / "experiments" / "forge_loop" / "calibration"
CONTEXT = OUT / "context.json"            # evidence is shared by v1 and v2 (frozen at the first request)
VERSION = os.environ.get("CF_CAL_VERSION", "v2")
REQUESTS = OUT / ("requests.jsonl" if VERSION == "v1" else f"requests_{VERSION}.jsonl")
# v1 (12 requests, all HTTP 200/stop/non-null but 0 valid: hypothesis TEXT used as id; invented/mis-prefixed citation
# paths) -> v2 changes ONLY the reply contract: ids "H1".."H3", schema enums for hypothesis ids, citation paths
# (every scalar leaf of the same evidence) and editable params. Same evidence, models, settings and pass criteria.
MAX_CAL_REQUESTS = 30                      # across all versions (v1 used 12)
RULE = os.environ.get("CF_CAL_RULE", "contract")   # see validate(): "strict" or "contract"
LEDGER_CAP_USD = 15.0
BASE_DEFAULT = "https://api.tokenfactory.nebius.com/v1"
MODELS = {  # USD per token, from GET /v1/models on 2026-10-14
    "super": ("nvidia/nemotron-3-super-120b-a12b", 3e-7, 9e-7),
    "ultra": ("nvidia/Nemotron-3-Ultra-550b-a55b", 1e-6, 3e-6),
    "nano": ("nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", 6e-8, 2.4e-7),
    "lightning": ("nvidia/Nemotron-3_5-Lightning", 6e-8, 2.4e-7),
}
SETTINGS = {
    "A": {"label": "reasoning low + json_schema", "max_tokens": 16000, "reasoning_effort": "low", "json_schema": True, "extra": None},
    "B": {"label": "thinking disabled + json_schema", "max_tokens": 8000, "reasoning_effort": None, "json_schema": True,
          "extra": {"chat_template_kwargs": {"enable_thinking": False}}},
    "C": {"label": "default reasoning, prompt-only JSON", "max_tokens": 16000, "reasoning_effort": None, "json_schema": False, "extra": None},
}
TIMEOUT_S = 180
MAX_LATENCY_S = 120

# ---- editable parameters for a push challenge (contracts 5.2); ratio rule for physical, |du| rule for control ----
PHYS = ["torso_mass", "thigh_length", "shank_length", "foot_length", "leg_density", "foot_friction", "torque_limit"]
CTRL = {"stand.kp": (0.0, 500.0), "stand.kd": (0.0, 50.0), "stand.balance_gain": (0.0, 200.0),
        "stand.stand_hip": (-0.3, 0.3), "stand.stand_knee": (-0.8, 0.0)}
MEANING = {
    "torso_mass": "torso mass (kg)", "thigh_length": "upper-leg length (m)", "shank_length": "lower-leg length (m)",
    "foot_length": "foot length (m), support polygon size", "leg_density": "leg material density (kg/m^3)",
    "foot_friction": "foot-ground friction coefficient", "torque_limit": "max motor torque per joint (N m)",
    "stand.kp": "joint PD stiffness", "stand.kd": "joint PD damping", "stand.balance_gain": "ankle torque per rad of torso pitch",
    "stand.stand_hip": "standing hip angle target (rad)", "stand.stand_knee": "standing knee angle target (rad, <= 0)",
}

REPLY_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["diagnosis", "proposals"],
    "properties": {
        "diagnosis": {"type": "object", "additionalProperties": False, "required": ["summary", "hypotheses"], "properties": {
            "summary": {"type": "string"},
            "hypotheses": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
                "type": "object", "additionalProperties": False, "required": ["id", "mechanism", "evidence", "competing"],
                "properties": {"id": {"type": "string"}, "mechanism": {"type": "string"},
                               "evidence": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string"}},
                               "competing": {"type": "array", "items": {"type": "string"}}}}}}},
        "proposals": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "hypothesis", "category", "edits", "retune_controller", "prediction", "tradeoffs", "confidence", "verification"],
            "properties": {
                "id": {"type": "string"}, "hypothesis": {"type": "string"},
                "category": {"type": "string", "enum": ["morphology", "control", "combined"]},
                "edits": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                    "type": "object", "additionalProperties": False, "required": ["param", "op", "value", "target"],
                    "properties": {"param": {"type": "string"}, "op": {"type": "string", "enum": ["scale", "set"]},
                                   "value": {"type": "number"}, "target": {"type": "string", "enum": ["both", "rear", "front"]}}}},
                "retune_controller": {"type": "boolean"},
                "prediction": {"type": "object", "additionalProperties": False, "required": ["metric", "direction", "expected_change"],
                               "properties": {"metric": {"type": "string"}, "direction": {"type": "string", "enum": ["increase", "decrease"]},
                                              "expected_change": {"type": "string"}}},
                "tradeoffs": {"type": "string"}, "confidence": {"type": "number"}, "verification": {"type": "string"}}}},
    },
}

SYSTEM = """You are an engineering investigator for Creature Forge, a physics laboratory where users draw simple robots.
The robot is a PLANAR two-legged walker simulated in MuJoCo: a box torso and two legs (rear and front), each with hip,
knee and ankle joints driven by torque-limited motors, plus a flat foot. A standing controller (joint PD + ankle balance
feedback on torso pitch) keeps it upright.

You receive measured evidence from real MuJoCo runs of ONE user-drawn creature attempting ONE challenge. Your job:
1. Diagnose: state 1-3 hypotheses about the physical failure mechanism. Each must cite 1-6 evidence paths that point to
   single numbers in the evidence JSON (dotted keys, list indices like seeds[0].fall_time). Mention competing explanations.
2. Propose 1-3 testable redesigns using ONLY the editable parameters listed. Each edit is {param, op, value, target}:
   op "scale" multiplies the current value (allowed factor 0.5-1.5 for physical parameters); op "set" sets a controller
   value (change at most 25% of that parameter's range). target is "both", "rear" or "front" for leg lengths, "both"
   otherwise. At most 4 edits per proposal. category = morphology (body/motor params only), control (stand.* only) or
   combined. retune_controller must be false for this challenge.
3. Predict the measurable consequence and the trade-offs; give an honest confidence (0-1). It is acceptable to say that
   you expect little improvement.

MuJoCo will test every proposal on new seeds against the unchanged creature, random edits of the same size and a
non-AI heuristic. Your text is not trusted; only the measurements decide. Reply with ONE JSON object only, matching
the schema given by the user. No markdown."""


def creature_body() -> dict:
    return {"torso_mass": 6.0, "thigh_length": 0.30, "shank_length": 0.30, "foot_length": 0.05, "foot_friction": 1.0,
            "torque_limit": 60.0, "leg_density": 1000.0, "thigh_length_r": 0.30, "shank_length_r": 0.30,
            "foot_length_r": 0.05, "pose": [0.0] * 7}


def r(x, nd=3):
    if isinstance(x, (bool, str)) or x is None:
        return x
    if isinstance(x, (int,)):
        return x
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if not math.isfinite(f):
        return None
    return float(f"{f:.{nd}g}")


def compact(obj, depth=0):
    """Round numbers, drop arrays longer than 8, keep evidence small and citeable."""
    if isinstance(obj, dict):
        return {k: compact(v, depth + 1) for k, v in obj.items() if not (isinstance(v, (list, tuple)) and len(v) > 8)}
    if isinstance(obj, (list, tuple)):
        return [compact(v, depth + 1) for v in obj]
    return r(obj)


def build_context() -> dict:
    """Run the frozen calibration creature in MuJoCo (3 seeds, 25 N forward push) and build the compact evidence."""
    from creature_forge.controller import GaitParams
    from creature_forge.failures import detect_failures
    from creature_forge.forensics import build_forensics
    from creature_forge.sandbox import SandboxBody
    from creature_forge.simulate import Push, run_rollout
    body = SandboxBody(**{**creature_body(), "pose": tuple(creature_body()["pose"])}).validate()
    gait = GaitParams()
    push = Push(time=1.0, force=25.0, duration=0.15)
    seeds, worst = [], None
    for s in (100001, 100002, 100003):
        tel = run_rollout(body, gait, seed=s, duration=5.0, push=push)
        ev = detect_failures(tel, body)
        fall = next((e for e in ev if e.kind == "fall"), None)
        z = tel["torso_pos"][:, 1]   # torso height (x, z, pitch layout)
        rec = {"seed": s, "fell": fall is not None, "fall_time_s": None if fall is None else r(fall.time),
               "max_abs_pitch_rad": r(float(abs(tel["torso_pitch"]).max())),
               "events": [{"kind": e.kind, "time_s": r(e.time)} for e in ev][:4]}
        rec["min_height_ratio"] = r(float(z.min() / z[0]))
        seeds.append(rec)
        if worst is None:
            worst = build_forensics(tel, body, push, ev)
    weight = (body.torso_mass + 0.0) * 9.81
    evidence = {
        "creature": {"name": "Stubby (calibration creature)", "mode": "experimental",
                     "body": {k: r(v) for k, v in creature_body().items() if k != "pose"},
                     "derived": {"leg_length_m": 0.6, "foot_to_leg_ratio": r(0.05 / 0.6), "torso_weight_n": r(weight)}},
        "challenge": {"kind": "push", "push_force_n": 25.0, "push_time_s": 1.0, "push_duration_s": 0.15, "duration_s": 5.0,
                      "success": "torso stays upright (no fall) for the whole run"},
        "controller": {"stand": GaitParams().as_dict()},
        "outcome": {"seeds_n": len(seeds), "falls": sum(s["fell"] for s in seeds)},
        "seeds": seeds,
        "forensics_seed0": compact(worst),
    }
    editable = {}
    for p in PHYS:
        editable[p] = {"current": r(creature_body()[p]), "rule": "scale 0.5-1.5", "meaning": MEANING[p]}
    for p, (lo, hi) in CTRL.items():
        editable[p] = {"current": r(GaitParams().as_dict()[p.split(".")[1]]), "range": [lo, hi], "rule": "set, |change| <= 25% of range",
                       "meaning": MEANING[p]}
    return {"evidence": evidence, "editable": editable}


def leaf_paths(obj, prefix: str = "") -> list[str]:
    if isinstance(obj, dict):
        return [p for k, v in obj.items() for p in leaf_paths(v, f"{prefix}.{k}" if prefix else k)]
    if isinstance(obj, list):
        return [p for i, v in enumerate(obj) for p in leaf_paths(v, f"{prefix}[{i}]")]
    return [prefix]


def schema_for(ctx: dict) -> dict:
    if VERSION == "v1":
        return REPLY_SCHEMA
    sch = json.loads(json.dumps(REPLY_SCHEMA))
    hyp = sch["properties"]["diagnosis"]["properties"]["hypotheses"]["items"]["properties"]
    ids = {"type": "string", "enum": ["H1", "H2", "H3"]}
    hyp["id"] = ids
    hyp["evidence"]["items"] = {"type": "string", "enum": leaf_paths(ctx["evidence"])}
    prop = sch["properties"]["proposals"]["items"]["properties"]
    prop["hypothesis"] = ids
    prop["edits"]["items"]["properties"]["param"] = {"type": "string", "enum": list(ctx["editable"])}
    return sch


ID_NOTE = """
Identifiers: hypotheses have ids "H1", "H2", "H3" (in order). Each proposal's "hypothesis" field is the id it tests
(for example "H1"), never a sentence. Each citation in "evidence" is an exact path copied from the allowed list in the
schema (for example "seeds[0].fall_time_s" or "forensics_seed0.support.com_margin_before_push_m"): no values, no
extra prefixes."""


def messages_for(ctx: dict) -> list[dict]:
    user = ("EVIDENCE (measured in MuJoCo):\n" + json.dumps(ctx["evidence"], separators=(",", ":")) +
            "\n\nEDITABLE PARAMETERS:\n" + json.dumps(ctx["editable"], separators=(",", ":")) +
            "\n\nREPLY SCHEMA (JSON Schema):\n" + json.dumps(schema_for(ctx), separators=(",", ":")))
    return [{"role": "system", "content": SYSTEM + ("" if VERSION == "v1" else ID_NOTE)}, {"role": "user", "content": user}]


def resolve(obj, path: str):
    cur = obj
    for tok in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if tok.startswith("["):
            i = int(tok[1:-1])
            if not isinstance(cur, list) or i >= len(cur):
                raise KeyError(path)
            cur = cur[i]
        else:
            if not isinstance(cur, dict) or tok not in cur:
                raise KeyError(path)
            cur = cur[tok]
    if isinstance(cur, (dict, list)):
        raise KeyError(f"{path} is not a single value")
    return cur


def parse(content: str | None):
    if not content or not content.strip():
        raise ValueError("empty content")
    t = re.sub(r"(?s)^\s*<think>.*?</think>", "", content).strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < i:
        raise ValueError("no JSON object")
    obj = json.loads(t[i:j + 1])
    if not isinstance(obj, dict):
        raise ValueError("top level is not an object")
    return obj


def validate(reply: dict, ctx: dict) -> list[str]:
    errs = []
    try:
        hyps = reply["diagnosis"]["hypotheses"]
        props = reply["proposals"]
    except (KeyError, TypeError):
        return ["missing diagnosis.hypotheses or proposals"]
    if not (1 <= len(hyps) <= 3) or not (1 <= len(props) <= 3):
        errs.append("hypothesis/proposal count out of range")
    ids = {h.get("id") for h in hyps}
    for h in hyps:
        for c in h.get("evidence", []):
            try:
                resolve({"evidence": ctx["evidence"], **ctx["evidence"]}, c)
            except KeyError:
                try:
                    resolve(ctx["evidence"], c.removeprefix("evidence."))
                except KeyError:
                    errs.append(f"{h.get('id')}: unresolved citation {c}")
    for p in props:
        pid = p.get("id")
        if p.get("hypothesis") not in ids:
            errs.append(f"{pid}: unknown hypothesis {p.get('hypothesis')}")
        edits = p.get("edits") or []
        if not 1 <= len(edits) <= 4:
            errs.append(f"{pid}: edit count {len(edits)}")
        kinds = set()
        for e in edits:
            prm, op, val = e.get("param"), e.get("op"), e.get("value")
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
                errs.append(f"{pid}: {prm} value not a finite number"); continue
            if prm in PHYS:
                kinds.add("morphology")
                if op != "scale" or not 0.5 <= val <= 1.5 or val == 1.0:
                    errs.append(f"{pid}: {prm} must be scale in [0.5,1.5] and != 1 (got {op} {val})")
                if e.get("target", "both") != "both" and prm not in ("thigh_length", "shank_length", "foot_length"):
                    errs.append(f"{pid}: target only for leg lengths")
            elif prm in CTRL:
                kinds.add("control")
                lo, hi = CTRL[prm]
                cur = ctx["editable"][prm]["current"]
                # rule "strict" (prompt wording, used for v1/v2 Stage A at run time): controller edits must be op "set".
                # rule "contract" (docs/FORGE_LOOP_CONTRACTS.md 5.2, the production validator): scale or set, judged on
                # the resulting value. Both are reported; Stage B is judged by the contract rule.
                new = cur * val if op == "scale" else val
                if (RULE == "strict" and op != "set") or not lo <= new <= hi or abs(new - cur) > 0.25 * (hi - lo) or new == cur:
                    errs.append(f"{pid}: {prm} must stay within bounds with |du|<=0.25 (got {op} {val}, current {cur})")
            else:
                errs.append(f"{pid}: param {prm} not editable")
        cat = "combined" if len(kinds) > 1 else (kinds.pop() if kinds else None)
        if cat and p.get("category") != cat:
            errs.append(f"{pid}: category {p.get('category')} != {cat}")
        if p.get("retune_controller"):
            errs.append(f"{pid}: retune_controller must be false for push")
        c = p.get("confidence")
        if not isinstance(c, (int, float)) or not 0 <= c <= 1:
            errs.append(f"{pid}: confidence not in [0,1]")
    return errs


def ledger_path() -> Path:
    return Path(os.environ.get("CF_INFERENCE_LEDGER") or (ROOT / "artifacts" / "forge" / "inference_ledger.jsonl"))


def ledger_usd() -> float:
    p = ledger_path()
    if not p.exists():
        return 0.0
    return sum(json.loads(line).get("cost_usd", 0.0) for line in p.read_text("utf-8").splitlines() if line.strip())


def n_requests() -> int:
    """Calibration requests across all versions (the cap is global)."""
    return sum(1 for f in OUT.glob("requests*.jsonl") for line in f.read_text("utf-8").splitlines() if line.strip())


def call(model_key: str, setting: str, ctx: dict, stage: str, rep: int) -> dict:
    model, p_in, p_out = MODELS[model_key]
    s = SETTINGS[setting]
    msgs = messages_for(ctx)
    body = {"model": model, "messages": msgs, "max_tokens": s["max_tokens"], "temperature": 0.6}
    if s["reasoning_effort"]:
        body["reasoning_effort"] = s["reasoning_effort"]
    if s["json_schema"]:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "forge_reply", "schema": schema_for(ctx), "strict": True}}
    if s["extra"]:
        body.update(s["extra"])
    url = nebius_base_url(BASE_DEFAULT) + "/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + (nebius_api_key() or ""), "Content-Type": "application/json"})
    t0 = time.perf_counter()
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "version": VERSION, "stage": stage, "rep": rep, "model_key": model_key,
           "model": model, "setting": setting, "setting_detail": {k: v for k, v in s.items()},
           "prompt_sha256": hashlib.sha256(json.dumps(msgs, sort_keys=True).encode()).hexdigest()}
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw = json.loads(resp.read().decode())
            rec["http_status"] = resp.status
    except urllib.error.HTTPError as e:
        raw = None
        rec["http_status"] = e.code
        rec["error"] = e.read().decode(errors="replace")[:2000]
    except Exception as e:  # timeout, network
        raw = None
        rec["http_status"] = None
        rec["error"] = f"{type(e).__name__}: {e}"
    rec["latency_s"] = round(time.perf_counter() - t0, 2)
    rec["raw"] = raw
    usage = (raw or {}).get("usage") or {}
    rec["usage"] = usage
    rec["cost_usd"] = round(usage.get("prompt_tokens", 0) * p_in + usage.get("completion_tokens", 0) * p_out, 6)
    rec["request_id"] = (raw or {}).get("id")
    ch = ((raw or {}).get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = msg.get("content")
    rec["finish_reason"] = ch.get("finish_reason")
    rec["reasoning_present"] = bool(msg.get("reasoning_content") or msg.get("reasoning"))
    checks = {"http_200": rec["http_status"] == 200, "finish_stop": rec["finish_reason"] == "stop",
              "content": bool(content and content.strip()), "latency_ok": rec["latency_s"] <= MAX_LATENCY_S}
    errs = []
    try:
        reply = parse(content)
        checks["json"] = True
        errs = validate(reply, ctx)
        checks["valid"] = not errs
        rec["n_proposals"] = len(reply.get("proposals", []))
        rec["n_hypotheses"] = len(reply.get("diagnosis", {}).get("hypotheses", []))
    except Exception as e:
        checks["json"] = False
        checks["valid"] = False
        errs = [f"parse: {e}"]
    rec["checks"] = checks
    rec["validation_errors"] = errs
    rec["pass"] = all(checks.values())
    return rec


def append(rec: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with REQUESTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    lp = ledger_path()
    lp.parent.mkdir(parents=True, exist_ok=True)
    u = rec.get("usage") or {}
    with lp.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": rec["ts"], "request_id": rec.get("request_id"), "model": rec["model"],
                            "prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0),
                            "cost_usd": rec["cost_usd"], "purpose": "calibration", "investigation_id": None}) + "\n")


def run(plan: list[tuple[str, str, int]], stage: str, ctx: dict) -> None:
    if n_requests() + len(plan) > MAX_CAL_REQUESTS:
        raise SystemExit(f"refusing: {n_requests()} + {len(plan)} > {MAX_CAL_REQUESTS} calibration requests")
    worst = sum(MODELS[m][1] * 4000 + MODELS[m][2] * SETTINGS[s]["max_tokens"] for m, s, _ in plan)
    if ledger_usd() + worst > LEDGER_CAP_USD:
        raise SystemExit("refusing: ledger cap")
    with cf.ThreadPoolExecutor(max_workers=4) as ex:   # one in flight per model at most
        futs = {ex.submit(call, m, s, ctx, stage, rep): (m, s, rep) for m, s, rep in plan}
        for fu in cf.as_completed(futs):
            rec = fu.result()
            append(rec)
            print(f"{rec['model_key']:9s} {rec['setting']} rep{rec['rep']}: pass={rec['pass']} http={rec['http_status']} "
                  f"finish={rec['finish_reason']} lat={rec['latency_s']}s tok={rec['usage'].get('completion_tokens')} "
                  f"${rec['cost_usd']:.4f} errs={rec['validation_errors'][:3]}", flush=True)


def revalidated(x: dict, ctx: dict) -> bool:
    """Re-judge a stored reply under the current RULE (transport checks are kept as recorded)."""
    content = (((x.get("raw") or {}).get("choices") or [{}])[0].get("message") or {}).get("content")
    try:
        ok = not validate(parse(content), ctx)
    except Exception:
        ok = False
    return ok and all(v for k, v in x["checks"].items() if k not in ("json", "valid"))


def report() -> None:
    ctx = json.loads(CONTEXT.read_text("utf-8"))
    rows = [json.loads(line) for line in REQUESTS.read_text("utf-8").splitlines() if line.strip()]
    for x in rows:
        x["pass"] = revalidated(x, ctx)
    print(f"# {VERSION}, judged by rule '{RULE}'")
    lines = ["| stage | model | setting | pass | http | finish | latency s | prompt tok | completion tok | cost $ | failures |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in rows:
        u = x.get("usage") or {}
        fails = [k for k, v in x["checks"].items() if not v] + x["validation_errors"][:2]
        lines.append(f"| {x['stage']}{x['rep']} | {x['model_key']} | {x['setting']} | {'PASS' if x['pass'] else 'fail'} | {x['http_status']} | "
                     f"{x['finish_reason']} | {x['latency_s']} | {u.get('prompt_tokens')} | {u.get('completion_tokens')} | {x['cost_usd']:.4f} | "
                     f"{'; '.join(map(str, fails))[:160]} |")
    total = sum(x["cost_usd"] for x in rows)
    print("\n".join(lines))
    print(f"\n{len(rows)} requests, ${total:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", action="store_true")
    ap.add_argument("--stage", choices=["A", "B"])
    ap.add_argument("--pairs", default="")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    load_env()
    if a.report:
        return report()
    if a.context or not CONTEXT.exists():
        if CONTEXT.exists() and n_requests() > 0 and a.context:
            raise SystemExit("context is frozen (requests already sent); refusing to rebuild")
        ctx = build_context()
        OUT.mkdir(parents=True, exist_ok=True)
        CONTEXT.write_text(json.dumps(ctx, indent=1), "utf-8")
        size = len(json.dumps(ctx["evidence"], separators=(",", ":")))
        prompt = sum(len(m["content"]) for m in messages_for(ctx))
        print(f"context frozen: evidence {size} bytes, prompt {prompt} chars (~{prompt // 3} tokens est.)")
        if not a.stage:
            return
    ctx = json.loads(CONTEXT.read_text("utf-8"))
    if not a.stage:
        return
    if not a.live:
        raise SystemExit("refusing to call the API without --live")
    if not nebius_api_key():
        raise SystemExit("NEBIUS_API_KEY not set")
    if a.stage == "A":
        plan = [(m, s, 1) for m in MODELS for s in SETTINGS]
    else:
        pairs = [p.split(":") for p in a.pairs.split(",") if p]
        if not pairs or any(m not in MODELS or s not in SETTINGS for m, s in pairs):
            raise SystemExit("--pairs model:setting,... required for stage B")
        plan = [(m, s, rep) for m, s in pairs for rep in (2, 3, 4)]
    run(plan, a.stage, ctx)


if __name__ == "__main__":
    main()
