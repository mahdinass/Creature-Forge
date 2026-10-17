"""Export trimmed, display-ready causal-engineer investigation records for the Studio "Causal engineer" page.

  python scripts/ce_export_records.py --results a.jsonl b.jsonl --policy scientist_think \
      --instance-ids "tiny-feet:posture_lean:0.5" ... --out experiments/causal_engineer/demo_records
  python scripts/ce_export_records.py --results a.jsonl --policy scientist_think --first 3 --out <dir>

Reads `scripts/ce_eval.py` episode records (JSON lines) and writes one `<record_id>.json` per episode plus `index.json`.
The record id is opaque (a hash), never the instance id. Trimming: per-call `messages`, `raw_response` and the `system_prompt` are
dropped (the prompt keeps its SHA-256); each step keeps its `user_message` only as SHA-256 + length. The full text stays in the source
file, whose path and line number are recorded for provenance. The ground truth (injected fault, severity, matching tool, diagnosis
match) sits under `evaluation_only`: the AI never saw it. The initial robot is rebuilt deterministically from the committed base
robot and the injected fault (`fault_bench.inject`) and checked against the robot text the model was shown. Output is scanned for
API-key-like strings and the export refuses to write if one is found.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCHEMA = "causal_record_v1"
NON_AI = ("exhaustive", "expert", "random", "blind")
EVAL_NOTE = ("Ground truth added by the evaluation runner after the AI finished. The AI never saw it: its prompt contained only "
             "the faulty robot, its own measurements and (optionally) retrieved memory items.")
SECRET_RES = (re.compile(r"Bearer\s"), re.compile(r"v1\.[A-Za-z0-9_\-.]{40,}"))
_DROP_EXPERIMENT_OUTCOME = {"quantities", "bench_deltas"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_id(instance_id: str, policy: str) -> str:
    return "c-" + sha(f"ce-demo-v1:{policy}:{instance_id}")[:12]


def assert_no_secret(text: str) -> None:
    for rx in SECRET_RES:
        m = rx.search(text)
        if m:
            raise ValueError(f"refusing to write: API-key-like string found ({rx.pattern!r} at offset {m.start()})")


def read_results(paths: list[str]) -> list[tuple[str, int, dict]]:
    out = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                if line.strip():
                    out.append((p, n, json.loads(line)))
    return out


def initial_robot(instance_id: str, bases: list[dict]) -> dict:
    """Faulty robot of an instance id `base:fault:severity`, rebuilt exactly as the benchmark built it."""
    from creature_forge import fault_bench as fb
    base_id, fault, sev = instance_id.rsplit(":", 2)
    base = next((b for b in bases if b["base_id"] == base_id), None)
    if base is None:
        raise ValueError(f"base robot {base_id!r} not found among the committed dev bases")
    inj = fb.inject(base, fault, float(sev))
    if not inj["valid"]:
        raise ValueError(f"instance {instance_id} does not rebuild: {inj['reason']}")
    return {"body": inj["body"], "vector": [float(x) for x in inj["vector"]]}


def check_against_prompt(robot: dict, first_user_message: str | None) -> bool | None:
    """True if every body parameter printed in the model's first message matches the rebuilt robot (4 significant digits)."""
    if not first_user_message:
        return None
    m = re.search(r"body parameters: ([^\n]+)", first_user_message)
    if not m:
        return None
    for kv in m.group(1).split(", "):
        k, _, v = kv.partition("=")
        if k in robot["body"] and isinstance(robot["body"][k], (int, float)):
            want = float(v)
            have = float(robot["body"][k])
            if abs(want - have) > 1e-3 * max(1.0, abs(want)) + 1e-9:
                return False
    return True


def trim_step(step: dict, calls: list[dict]) -> dict:
    out = {k: v for k, v in step.items() if k not in ("user_message", "calls")}
    um = step.get("user_message")
    if um is not None:
        out["user_message"] = {"sha256": sha(um), "length": len(um)}
    out["calls"] = [{"index": i, **{k: calls[i].get(k) for k in ("cost_usd", "latency_s", "finish_reason", "schema_name", "reasoning_present")},
                     "usage": calls[i].get("usage")} for i in step.get("calls", []) if 0 <= i < len(calls)]
    return out


def trim_experiment(e: dict) -> dict:
    out = dict(e)
    if isinstance(out.get("outcome"), dict):
        out["outcome"] = {k: v for k, v in out["outcome"].items() if k not in _DROP_EXPERIMENT_OUTCOME}
    return out


def trim_record(path: str, line: int, ep: dict, bases: list[dict], baselines: list[dict] | None = None) -> dict:
    pr = ep.get("policy_record") or {}
    steps = pr.get("steps") or []
    calls = pr.get("calls") or []
    robot0 = initial_robot(ep["instance_id"], bases)
    first_msg = None
    um = None
    if steps:
        um = steps[0].get("user_message")
    first_msg = um
    prompt_match = check_against_prompt(robot0, first_msg)
    if prompt_match is False:
        raise ValueError(f"{ep['instance_id']}: rebuilt initial robot differs from the robot shown to the model")
    sub = pr.get("submitted_design") or {}
    ledger = ep.get("ledger") or {}
    diag = ep.get("diagnosis") or {}
    rec = {
        "schema": SCHEMA,
        "id": record_id(ep["instance_id"], ep["policy"]),
        "source": {"file": os.path.basename(path), "line": line, "policy": ep["policy"], "runner_version": ep.get("version"),
                   "scientist_version": pr.get("version"), "note": "The full prompts and replies stay in the source file."},
        "config": {"model": pr.get("model"), "prompt_version": pr.get("prompt_version"), "scientist_mode": pr.get("scientist_mode"),
                   "thinking": ep["policy"].endswith("_think") or "_think_" in ep["policy"], "max_steps": pr.get("max_steps"),
                   "budget": ep.get("budget"), "n_train": ep.get("n_train"), "n_obs": ep.get("n_obs"), "tolerance": pr.get("tolerance"),
                   "system_prompt": {"sha256": sha(pr["system_prompt"]), "length": len(pr["system_prompt"])} if pr.get("system_prompt") else None,
                   "provenance": ep.get("provenance")},
        "robot": {"vector_names": __import__("creature_forge.walk_opt", fromlist=["ALL_NAMES"]).ALL_NAMES,
                  "initial": robot0, "initial_matches_prompt": prompt_match,
                  "submitted": {"body": sub.get("body"), "vector": sub.get("vector"), "design_index": sub.get("index"),
                                "source": sub.get("source")},
                  "base_region": ep.get("region")},
        "initial_observation": pr.get("initial_observation"),
        "steps": [trim_step(s, calls) for s in steps],
        "hypotheses": pr.get("hypotheses"),
        "experiments": [trim_experiment(e) for e in (pr.get("experiments") or [])],
        "memory": pr.get("memory") or {"items": [], "assessments": {}, "log": [], "error": None},
        "final": pr.get("final"),
        "prediction_summary": pr.get("prediction_summary"),
        "budget": {"total": ledger.get("total"), "used": ledger.get("used"), "remaining": ledger.get("remaining"),
                   "lines": ledger.get("lines"), "designs": ledger.get("designs")},
        "verification": {**(ep.get("verification") or {}), "independent": True,
                         "note": "Independent verification on hidden seeds the AI never saw (full_recovery_v1, uncharged)."},
        "llm": ep.get("llm"),
        "error": ep.get("error"),
        "evaluation_only": {"note": EVAL_NOTE, "fault": ep.get("fault"), "severity": ep.get("severity"),
                            "matching_tool": ep.get("matching_tool"), "injected_category": diag.get("injected_category"),
                            "diagnosis_category": diag.get("category"), "diagnosis_match": diag.get("match")},
        "no_ai_comparison": baselines or [],
    }
    return rec


def baseline_rows(rows: list[tuple[str, int, dict]], instance_id: str) -> list[dict]:
    out = []
    for _, _, r in rows:
        if r.get("instance_id") == instance_id and r.get("policy") in NON_AI:
            v = r.get("verification") or {}
            out.append({"policy": r["policy"], "status": v.get("status"), "walking_frac": v.get("walking_frac"),
                        "rollouts_used": r.get("rollouts_used"), "error": r.get("error")})
    return sorted(out, key=lambda x: x["policy"])


def index_row(rec: dict) -> dict:
    llm = rec.get("llm") or {}
    ver = rec.get("verification") or {}
    body = rec["robot"]["initial"]["body"]
    return {"id": rec["id"], "policy": rec["source"]["policy"], "status": ver.get("status"), "walking_frac": ver.get("walking_frac"),
            "n_steps": len(rec["steps"]), "n_experiments": len(rec["experiments"]), "cost_usd": llm.get("cost_usd"),
            "llm_calls": llm.get("calls"), "model": llm.get("model"),
            "robot": {"leg_length": round(float(body["thigh_length"]) + float(body["shank_length"]), 3),
                      "torso_mass": body.get("torso_mass"), "foot_length": body.get("foot_length"), "foot_friction": body.get("foot_friction"),
                      "torque_limit": body.get("torque_limit")},
            "final_category": (rec.get("final") or {}).get("diagnosis_category"), "has_memory": bool(rec["memory"].get("items"))}


def select(rows: list[tuple[str, int, dict]], policies: list[str], ids: list[str] | None, first: int | None) -> list[tuple[str, int, dict]]:
    pool = [x for x in rows if x[2].get("policy") in policies and not x[2].get("error") and x[2].get("policy_record")]
    if ids:
        out = []
        for i in ids:
            hit = next((x for x in pool if x[2]["instance_id"] == i), None)
            if hit is None:
                raise SystemExit(f"no usable {policies} record for instance {i!r}")
            out.append(hit)
        return out
    return pool[: first or len(pool)]


def export(rows, picked, bases, out_dir: str) -> list[dict]:
    os.makedirs(out_dir, exist_ok=True)
    recs = []
    for path, line, ep in picked:
        rec = trim_record(path, line, ep, bases, baseline_rows(rows, ep["instance_id"]))
        text = json.dumps(rec, indent=1, sort_keys=True)
        assert_no_secret(text)
        recs.append((rec, text))
    index = [index_row(r) for r, _ in recs]
    idx_text = json.dumps({"schema": SCHEMA, "records": index}, indent=1)
    assert_no_secret(idx_text)
    for r, text in recs:
        with open(os.path.join(out_dir, r["id"] + ".json"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(idx_text + "\n")
    return index


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", nargs="+", required=True, help="ce_eval result files (JSON lines)")
    ap.add_argument("--policy", default="scientist_think", help="comma-separated policies to export")
    ap.add_argument("--instance-ids", nargs="*")
    ap.add_argument("--first", type=int, help="export the first N usable records instead")
    ap.add_argument("--out", default=os.path.join("experiments", "causal_engineer", "demo_records"))
    a = ap.parse_args(argv)
    from creature_forge import fault_bench as fb
    rows = read_results(a.results)
    picked = select(rows, a.policy.split(","), a.instance_ids, a.first)
    index = export(rows, picked, fb.load_bases("dev"), a.out)
    for r in index:
        print(r["id"], r["status"], r["n_steps"], "steps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
