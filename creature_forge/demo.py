"""Investigation demo: observed MuJoCo failure -> Nemotron proposal -> bounded edit -> simulator verification -> replay -> measured verdict.

Honesty rules enforced here (each has a test):
 * provenance is one of LIVE (a Nebius call made in this run), RECORDED_LIVE (a stored record of an earlier real call, hash-verified) or
   SCRIPTED_MOCK (text written by this repository, never a model). A mock run can never be stored as, or labelled, live;
 * the model's reply is stored exactly as received; invalid or empty replies are shown as such and nothing is substituted;
 * every valid proposal is verified (no cherry-picking); the shown "primary" one is simply the first valid slot;
 * each proposal is compared with a matched-random edit of the same size on the same verification seeds;
 * the verdict comes only from the MuJoCo measurements; a single instance is never a statistical claim;
 * the classical-optimiser improvement of R2 is never attributed to the model (see LIMITS).
Live calls draw on the same combined Nebius request/token caps as R3 (41 requests / 300,000 tokens) via r3v2.prior_usage().
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import r1, r2, r3, r3v2
from .morphology import BipedParams
from .nebius import BudgetExceeded, NebiusClient, NebiusError
from .optimize import Executor

ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = ROOT / "experiments" / "phase2a_r3" / "demo_records"        # committed, hash-verified recordings of real live runs
LOCAL_RUNS_DIR = ROOT / "artifacts" / "demo_runs"                            # git-ignored runs made on this machine
MANIFEST = RECORDS_DIR / "manifest.json"
DEMO_REQUESTS = r3v2.DEMO_REQUESTS

FAILING_SEED, WALKING_SEED = 9101, 9100                                       # R3 evidence-pool seeds (observation only; disclosed)
VERIFY_SEEDS = tuple(range(9600, 9632))                                       # demo-only verification seeds, disjoint from every other role
SLOTS_REQUESTED = 2
SETTING = {"name": "demo", "reasoning_effort": "low", "max_tokens": 8000}     # calibration saw 3.4-5k completion tokens at 'low'
MAX_LIVE_REQUESTS_PER_PROCESS = 10
IMPROVE_MIN_GAIN = 2
KINDS = ("LIVE", "RECORDED_LIVE", "SCRIPTED_MOCK")
LIMITS = [
    "One instance on one planar biped: a demonstration of the propose -> simulate -> verify loop, not evidence that the model reasons correctly about physics.",
    "A matched-random edit of the same size is shown beside every proposal; random local edits of the frozen controller often help too (R2), so a single success proves little.",
    "The registered statistical comparison (R3) was not run: no generation setting passed calibration (experiments/phase2a_r3/REPORT_V2.md).",
    "The R2 controller that walks 150/150 seeds was found by a classical optimiser; none of that is attributed to Nemotron.",
]
MOCK_REPLY = json.dumps({"proposals": [
    {"claim": "SCRIPTED MOCK, not a model: a larger forward pitch reference may help establish the first forward step.",
     "cited_evidence": ["controller.pitch_ref.u", "failing_seeds.0.valid_steps"],
     "edits": [{"parameter": "pitch_ref", "delta_u": 0.10}],
     "prediction": {"metric": "walking_seeds_screen", "direction": "increase", "min_gain_seeds": 2}, "confidence": 0.5},
    {"claim": "SCRIPTED MOCK, not a model: lean forward at start-up.",
     "cited_evidence": ["controller.start_lean.u", "failing_seeds.0.fall_time"],
     "edits": [{"parameter": "start_lean", "delta_u": 0.12}],
     "prediction": {"metric": "walking_seeds_screen", "direction": "increase", "min_gain_seeds": 2}, "confidence": 0.5}]})

PATH_NOTE = (" Path format: list entries are addressed by index (for example failing_seeds.0.fall_time, never failing_seeds.fell); "
             "a path that ends at a list or an object is invalid.")
# demo prompt v2 (after live run 001 cited list-level paths and was correctly rejected): the R3 prompt with the item count and a path-format note
DEMO_SYSTEM_PROMPT = r3.SYSTEM_PROMPT.replace("exactly 4 items", f"exactly {SLOTS_REQUESTED} items") + PATH_NOTE
assert DEMO_SYSTEM_PROMPT != r3.SYSTEM_PROMPT


def check_demo_seeds() -> None:
    mine = set(VERIFY_SEEDS)
    for name, seeds in r3.consumed_seed_sets().items():
        if mine & set(seeds):
            raise ValueError(f"demo verification seeds overlap {name}")
    for name, seeds in (("r3_evidence_pool", r3.EVIDENCE_POOL_SEEDS), ("r3_screen_pool", r3.SCREEN_POOL_SEEDS), ("r3_validation", r3.VALIDATION_SEEDS),
                        ("r3_pilot", r3.PILOT_SEEDS)):
        if mine & set(seeds):
            raise ValueError(f"demo verification seeds overlap {name}")


def demo_messages(context: dict) -> list[dict]:
    return [{"role": "system", "content": DEMO_SYSTEM_PROMPT},
            {"role": "user", "content": "CONTEXT:\n" + json.dumps(context, sort_keys=True, separators=(",", ":"))}]


def live_enabled() -> bool:
    if os.environ.get("CREATURE_FORGE_ENABLE_LIVE") != "1":
        return False
    from .config import load_env, nebius_api_key
    load_env()
    return bool(nebius_api_key())


def demo_usage() -> dict:
    return r3v2.usage_from(r3v2._records(DEMO_REQUESTS))


# ----------------------------------------------------------------------------------------------------------
# verification (MuJoCo decides)
# ----------------------------------------------------------------------------------------------------------
def _summ(out: dict) -> dict:
    per = out["result"]["per_seed"]
    return {"walking_count": int(sum(m["walking"] for m in per)), "survival_count": int(sum(not m["fell"] for m in per)),
            "walking_by_seed": [bool(m["walking"]) for m in per], "n": len(per),
            "labels": {l: sum(m["label"] == l for m in per) for l in sorted({m["label"] for m in per})}}


def verdict_for(base_walking: int, walking: int, predicted_min_gain: int | None) -> dict:
    gain = walking - base_walking
    kind = "improved" if gain >= IMPROVE_MIN_GAIN else ("worse" if gain <= -IMPROVE_MIN_GAIN else "no_clear_change")
    v = {"gain_seeds": gain, "kind": kind}
    if predicted_min_gain is not None:
        v["prediction_met"] = bool(gain >= predicted_min_gain)
    return v


def evaluate_vectors(vectors: list, seeds, executor: Executor) -> list[dict]:
    outs = executor.map(r2.make_jobs(vectors, seeds))
    for o in outs:
        if not o["ok"]:
            raise RuntimeError("simulation failed: " + o["error"])
    return outs


# ----------------------------------------------------------------------------------------------------------
# one investigation
# ----------------------------------------------------------------------------------------------------------
def observe(theta, executor: Executor) -> dict:
    """Run the frozen controller on the failing and the walking seed; the model's context is built from exactly these measurements."""
    outs = evaluate_vectors([theta], (WALKING_SEED, FAILING_SEED), executor)[0]["result"]["per_seed"]
    by = {m["seed"]: m for m in outs}
    return {"failing_seed": FAILING_SEED, "walking_seed": WALKING_SEED, "metrics": {str(s): {k: m.get(k) for k in r3.SEED_FIELDS + ("walking",)} for s, m in by.items()},
            "failing_seed_walked": bool(by[FAILING_SEED]["walking"])}, [by[WALKING_SEED], by[FAILING_SEED]]


def model_step(mode: str, context: dict, client: NebiusClient | None) -> dict:
    messages = demo_messages(context)
    base = {"prompt_sha256": r3.prompt_sha256(messages), "setting": SETTING, "temperature": r3.TEMPERATURE, "slots_requested": SLOTS_REQUESTED}
    if mode == "mock":
        slots, reasons, err = r3.parse_slots(MOCK_REPLY, context)
        return {**base, "status": "ok" if err is None else "invalid_response", "raw_reply": MOCK_REPLY, "reason": err, "call": None,
                "slots": [{"proposal": None if p is None else p.as_dict(), "reason": r} for p, r in zip(slots, reasons)][:SLOTS_REQUESTED]}
    assert client is not None
    rec = {**base, "status": "ok", "raw_reply": None, "reason": None, "call": None,
           "slots": [{"proposal": None, "reason": "not requested"}] * SLOTS_REQUESTED}
    try:
        res = client.chat(messages, max_tokens=SETTING["max_tokens"], temperature=r3.TEMPERATURE, reasoning_effort=SETTING["reasoning_effort"])
    except BudgetExceeded as e:
        rec.update(status="budget_exceeded", reason=str(e))
        return rec
    except NebiusError as e:
        rec.update(status="model_error", reason=str(e)[:300], call=client.calls[-1] if client.calls else None)
        return rec
    rec["call"], rec["raw_reply"] = res.record(), res.content
    slots, reasons, err = r3.parse_slots(res.content, context)
    if err is not None:
        rec["status"], rec["reason"] = "invalid_response", err + (" (finish_reason=length: hidden reasoning used the whole completion limit)" if res.finish_reason == "length" else "")
    rec["slots"] = [{"proposal": None if p is None else p.as_dict(), "reason": r} for p, r in zip(slots, reasons)][:SLOTS_REQUESTED]
    return rec


def run_investigation(mode: str, executor: Executor, client: NebiusClient | None = None, *, run_id: str | None = None, label: str | None = None) -> dict:
    """mode 'live' needs a client; 'mock' uses the scripted reply. Returns the full record (provenance LIVE or SCRIPTED_MOCK)."""
    if mode not in ("live", "mock"):
        raise ValueError("mode must be 'live' or 'mock'")
    check_demo_seeds()
    theta = r2.incumbent_theta()
    run_id = run_id or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{mode}-{uuid.uuid4().hex[:6]}"
    t0 = time.perf_counter()
    observed, measured_rows = observe(theta, executor)
    context = r3.build_context(theta, measured_rows)
    model = model_step(mode, context, client)
    interventions, vectors = [], [theta]
    for s, slot in enumerate(model["slots"]):
        if slot["proposal"] is None:
            continue
        edits = [(e["parameter"], e["delta_u"]) for e in slot["proposal"]["edits"]]
        rnd = r3.matched_random_edits("M", 900 + len(interventions), s, [abs(d) for _, d in edits])
        iv = {"slot": s, "proposal": slot["proposal"], "realised": r3.realised_edits(theta, edits), "vector": r3.apply_edits(theta, edits),
              "matched_random": {"edits": [{"parameter": p, "delta_u": d} for p, d in rnd], "realised": r3.realised_edits(theta, rnd), "vector": r3.apply_edits(theta, rnd)}}
        interventions.append(iv)
        vectors += [iv["vector"], iv["matched_random"]["vector"]]
    verification = None
    if interventions:
        outs = evaluate_vectors(vectors, VERIFY_SEEDS, executor)
        base = _summ(outs[0])
        res = {"theta0": base}
        for k, iv in enumerate(interventions):
            e, r = _summ(outs[1 + 2 * k]), _summ(outs[2 + 2 * k])
            pm = iv["proposal"]["prediction"]["min_gain_seeds"]
            res[f"slot{iv['slot']}"] = {**e, "verdict": verdict_for(base["walking_count"], e["walking_count"], pm)}
            res[f"slot{iv['slot']}_random"] = {**r, "verdict": verdict_for(base["walking_count"], r["walking_count"], None)}
        verification = {"seeds": list(VERIFY_SEEDS), "results": res, "rollouts": len(vectors) * len(VERIFY_SEEDS),
                        "rule": f"improved = at least {IMPROVE_MIN_GAIN} more walking seeds than the frozen controller on the same {len(VERIFY_SEEDS)} seeds"}
    kind = "LIVE" if mode == "live" else "SCRIPTED_MOCK"
    call = model["call"]
    return {
        "run_id": run_id, "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "label": label, "schema": 1,
        "provenance": {"kind": kind, "model": (call or {}).get("model") if mode == "live" else None, "request_id": (call or {}).get("request_id"),
                       "prompt_sha256": model["prompt_sha256"], "setting": SETTING, "usage": (call or {}).get("usage"),
                       "note": ("A real Nebius Token Factory call made during this run." if mode == "live" else
                                "SCRIPTED MOCK: the 'model reply' below was written by this repository to exercise the pipeline. It is not Nemotron and is not a result.")},
        "controller": {"name": "frozen Phase 2A incumbent", "vector": [float(x) for x in theta], "params": r3.controller_block(theta)},
        "observed": observed, "context": context,
        "prompt": {"system": DEMO_SYSTEM_PROMPT, "user": demo_messages(context)[1]["content"], "sha256": model["prompt_sha256"]},
        "model_reply": {k: model[k] for k in ("status", "reason", "raw_reply", "call", "slots", "setting", "temperature", "slots_requested")},
        "interventions": interventions, "verification": verification, "limits": LIMITS, "elapsed_s": round(time.perf_counter() - t0, 1),
    }


def record_live_request(rec: dict) -> None:
    """Append the redacted request metadata of a real live call to the shared usage file so the combined caps stay honest."""
    if rec["provenance"]["kind"] != "LIVE":
        raise ValueError("only LIVE runs consume the live budget")
    DEMO_REQUESTS.parent.mkdir(parents=True, exist_ok=True)
    with open(DEMO_REQUESTS, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"run_id": rec["run_id"], "call": rec["model_reply"]["call"], "status": rec["model_reply"]["status"],
                            "prompt_sha256": rec["prompt"]["sha256"]}, allow_nan=False) + "\n")


# ----------------------------------------------------------------------------------------------------------
# storage and replay
# ----------------------------------------------------------------------------------------------------------
def record_sha256(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def save_local(rec: dict) -> Path:
    LOCAL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = LOCAL_RUNS_DIR / f"{rec['run_id']}.json"
    p.write_text(json.dumps(rec, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return p


def promote_to_recording(rec: dict, name: str | None = None) -> Path:
    """Turn a real LIVE run into a committed RECORDED_LIVE record (provenance relabelled, original kind and hash kept). Mocks are refused."""
    if rec["provenance"]["kind"] != "LIVE":
        raise ValueError("only a real LIVE run can be recorded as RECORDED_LIVE; scripted mocks are never promoted")
    out = json.loads(json.dumps(rec))
    out["provenance"]["kind"] = "RECORDED_LIVE"
    out["provenance"]["recorded_from"] = {"original_kind": "LIVE", "original_sha256": record_sha256(rec), "note": "stored copy of a real call made on " + rec["created_utc"]}
    out["provenance"]["note"] = ("RECORDED LIVE: a stored copy of a real Nebius Token Factory call made on " + rec["created_utc"] + ". Nothing is re-sent to the model; "
                                 "the MuJoCo replays below are fresh deterministic rollouts of the stored controller vectors.")
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    path = RECORDS_DIR / f"{name or rec['run_id']}.json"
    path.write_text(json.dumps(out, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"records": {}}
    man["records"][path.name] = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    MANIFEST.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return path


def bundle_mock_example(rec: dict, name: str) -> Path:
    """Store a SCRIPTED_MOCK run as a bundled example. It keeps (and shows) its SCRIPTED_MOCK label; it is never relabelled live."""
    if rec["provenance"]["kind"] != "SCRIPTED_MOCK":
        raise ValueError("only SCRIPTED_MOCK runs are bundled as mock examples")
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    path = RECORDS_DIR / f"{name}.json"
    path.write_text(json.dumps(rec, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"records": {}}
    man["records"][path.name] = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    MANIFEST.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return path


def _inner_id(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))["run_id"]
    except (OSError, ValueError, KeyError):
        return None


def list_runs() -> list[dict]:
    """Bundled recordings first, then local runs. The row id is the file stem (what load_run resolves). A local run that was promoted to a
    bundled recording is listed once, as the recording."""
    rows = []
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["records"] if MANIFEST.exists() else {}
    bundled_inner = {_inner_id(q) for q in RECORDS_DIR.glob("*.json")} if RECORDS_DIR.is_dir() else set()
    for d, src in ((RECORDS_DIR, "bundled-recording"), (LOCAL_RUNS_DIR, "local")):
        for p in sorted(d.glob("*.json")) if d.is_dir() else []:
            if p.name == "manifest.json" or (src == "local" and _inner_id(p) in bundled_inner):
                continue
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
                ver = rec.get("verification")
                first = next((i for i in rec["interventions"]), None)
                key = f"slot{first['slot']}" if first else None
                rows.append({"run_id": p.stem, "source": src, "kind": rec["provenance"]["kind"], "created_utc": rec["created_utc"], "label": rec.get("label"),
                             "status": rec["model_reply"]["status"], "n_valid_proposals": len(rec["interventions"]),
                             "gain_seeds": (ver["results"][key]["verdict"]["gain_seeds"] if ver and key else None),
                             "verdict": (ver["results"][key]["verdict"]["kind"] if ver and key else None),
                             "hash_verified": (hashlib.sha256(p.read_bytes().replace(bytes([13, 10]), bytes([10]))).hexdigest() == man.get(p.name)) if src == "bundled-recording" else None})
            except (OSError, ValueError, KeyError):
                rows.append({"run_id": p.stem, "source": src, "kind": None, "created_utc": None, "readable": False})
    return rows


def load_run(run_id: str) -> dict:
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id or ""):
        raise KeyError(run_id)
    for d in (RECORDS_DIR, LOCAL_RUNS_DIR):
        p = d / f"{run_id}.json"
        if p.is_file() and p.resolve().parent == d.resolve():
            rec = json.loads(p.read_text(encoding="utf-8"))
            if d == RECORDS_DIR and MANIFEST.exists():
                want = json.loads(MANIFEST.read_text(encoding="utf-8"))["records"].get(p.name)
                rec["integrity"] = {"verified": hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == want}
            return rec
    raise KeyError(run_id)


def replay_vector(rec: dict, which: str):
    if which == "baseline":
        return rec["controller"]["vector"]
    for iv in rec["interventions"]:
        if which == f"slot{iv['slot']}":
            return iv["vector"]
        if which == f"slot{iv['slot']}_random":
            return iv["matched_random"]["vector"]
    raise KeyError(which)


def build_replay(rec: dict, which: str, seed: int, duration: float = 10.0) -> dict:
    from .locomotion_view import build_locomotion_payload
    from .phasegait_init import controller_from_vector
    allowed = {FAILING_SEED, WALKING_SEED, *VERIFY_SEEDS}
    if seed not in allowed:
        raise ValueError("replay seed must be the observed failing/walking seed or a verification seed")
    v = replay_vector(rec, which)
    ctrl = controller_from_vector(v)
    payload = build_locomotion_payload(ctrl, BipedParams(), {"vector": v}, seed=seed, duration=duration)
    payload["role"] = "demo"
    return payload
