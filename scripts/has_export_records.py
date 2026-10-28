"""Export display-ready records of the autonomous HaS scientist (Stage 2) for the Studio "AI scientist" page.

  python scripts/has_export_records.py --results artifacts/hdb/s2_A4.jsonl ... --ids <instance_id,...> | --first N
      --out experiments/causal_engineer/dev/scientist_records

Reads `scripts/hdb_agent_run.py` records and writes one `<record_id>.json` per episode plus `index.json` (schema
`scientist_record_v1`). The record id is opaque (a hash), never the instance id.

Trimming: prompts, raw responses and the notebook text are dropped; each model call keeps the SHA-256 of its prompt, plus
usage, cost and latency. The scientist's own words (understanding, open question, reason for each action) and every
instrument result are kept verbatim.

The ground truth (injected mechanism, family, severity, whether the final belief matched) sits under `evaluation_only`:
the scientist never saw it. The output is scanned for API-key-like strings and the export refuses to write if one is found.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCHEMA = "scientist_record_v1"
SECRET_RES = (re.compile(r"Bearer\s"), re.compile(r"v1\.[A-Za-z0-9_\-.]{40,}"))
EVAL_NOTE = ("Ground truth added by the evaluation runner after the investigation ended. The scientist never saw it: it saw "
             "only the nominal design, its own measurements, the engine's outputs and (memory arms) its dossiers.")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_id(instance_id: str, arm: str) -> str:
    return "s-" + sha(f"has-demo-v1:{arm}:{instance_id}")[:12]


def assert_no_secret(text: str) -> None:
    for rx in SECRET_RES:
        m = rx.search(text)
        if m:
            raise ValueError(f"refusing to write: API-key-like string found ({rx.pattern!r} at offset {m.start()})")


def _panel(exp: dict) -> dict:
    if exp["kind"] == "weigh":
        return {"mass_kg": exp["measured"]["mass_kg"], "com_x_m": exp["measured"]["com_x_m"]}
    f = exp.get("features") or {}
    vals = lambda k: sorted(x.get(k) for x in f.values() if x.get(k) is not None)     # noqa: E731
    med = lambda v: None if not v else v[len(v) // 2]                                   # noqa: E731
    return {"n": len(f), "walking": sum(1 for x in f.values() if x.get("walking")),
            **{k: med(vals(k)) for k in ("time_upright", "pitch_mean", "step_freq_hz", "slip_fraction", "fall_direction")}}


def export(rec: dict, source: str, line: int) -> dict:
    ag = rec["agent"]
    nem = rec.get("nemotron") or {}
    notes = {n["turn"]: n for n in ag.get("notes") or []}
    steps = []
    for t in ag["trace"]:
        n = notes.get(t.get("turn")) if t["actor"] == "nemotron" else None
        res = dict(t["result"])
        steps.append({"seq": t["seq"], "turn": t.get("turn"), "actor": t["actor"], "action": t["action"], "result": res,
                      "plant_cost": t["plant_cost"], "twin_cost": t["twin_cost"], "plant_used": t["plant_used"],
                      "twin_used": t["twin_used"],
                      "scientist": {k: n[k] for k in ("understanding", "uncertainty", "why")} if n else None})
    eng = rec["engine"]
    designs = {d["index"]: d for d in rec["designs"]}
    sub = designs[rec["submitted"]]
    calls = nem.get("calls") or []
    out = {
        "schema": SCHEMA, "id": record_id(rec["instance_id"], rec["arm"]), "arm": rec["arm"], "provenance": rec["provenance"],
        "robot": {"initial": {k: designs[0][k] for k in ("body", "vector")}, "submitted": {k: sub[k] for k in ("body", "vector")},
                  "submitted_source": sub["source"]},
        "steps": steps,
        "belief_history": [{"label": h["label"], "plant_used": h["plant_used"], "twin_used": h["twin_used"],
                            "structures": h["structures"][:5]} for h in eng["history"]],
        "experiments": [{"id": e["id"], "kind": e["kind"], "panel": _panel(e)} for e in eng["experiments"] if e["kind"] != "check"],
        "evidence": ag.get("evidence"), "conclusion": {k: v for k, v in (ag.get("conclusion") or {}).items() if k != "repair"},
        "predictions": ag.get("predictions"), "memory_views": (ag.get("memory_views") or [])[-1:],
        "memory_uses": ag.get("memory_uses"),
        "verification": rec["verification"],
        "costs": {"plant_used": eng["ledger"]["used"], "plant_total": eng["ledger"]["total"],
                  "twin_used": eng["ledger"]["twin"]["used"], "twin_total": eng["ledger"]["twin"]["total"],
                  "llm_calls": len(calls), "cost_usd": nem.get("cost_usd"), "tokens": nem.get("tokens"),
                  "wall_s": rec.get("wall_s")},
        "model": {"name": nem.get("model"), "system_prompt_sha256": sha(nem.get("system_prompt") or ""),
                  "calls": [{"purpose": (c.get("settings") or {}).get("purpose"), "prompt_sha256": c.get("prompt_sha256"),
                             "usage": c.get("usage"), "latency_s": c.get("latency_s"), "cost_usd": c.get("cost_usd"),
                             "ok": c.get("ok"), "finish_reason": c.get("finish_reason")} for c in calls]},
        "evaluation_only": {"note": EVAL_NOTE, "injected_structure": rec["injected_structure"], "family": rec["family"],
                            "severity_multiple": rec.get("mult"), "final_belief": rec["map_structure"],
                            "final_belief_mass": rec["map_mass"], "mass_on_injected": rec["posterior_mass_on_injected"],
                            "belief_matched": rec["map_structure"] == rec["injected_structure"]},
        "source": {"file": source, "line": line, "record_version": rec.get("version")},
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--ids", default=None, help="comma list of instance ids")
    ap.add_argument("--arm", default=None)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    want = set(a.ids.split(",")) if a.ids else None
    picked = []
    for p in a.results:
        for n, line in enumerate(open(p, encoding="utf-8"), 1):
            if not line.strip():
                continue
            r = json.loads(line)
            if not r.get("agent") or (a.arm and r["arm"] != a.arm) or (want and r["instance_id"] not in want):
                continue
            picked.append((p, n, r))
    if a.first:
        picked = picked[:a.first]
    os.makedirs(a.out, exist_ok=True)
    idx_path = os.path.join(a.out, "index.json")
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {"schema": SCHEMA, "records": []}
    rows = {r["id"]: r for r in index["records"]}
    for p, n, r in picked:
        out = export(r, os.path.relpath(p).replace(os.sep, "/"), n)
        text = json.dumps(out)
        assert_no_secret(text)
        with open(os.path.join(a.out, f"{out['id']}.json"), "w", encoding="utf-8") as fh:
            fh.write(text)
        rows[out["id"]] = {"id": out["id"], "arm": out["arm"], "provenance": out["provenance"],
                           "status": out["verification"]["status"], "walking_frac": out["verification"]["walking_frac"],
                           "n_steps": len(out["steps"]), "n_experiments": len(out["experiments"]),
                           "llm_calls": out["costs"]["llm_calls"], "cost_usd": out["costs"]["cost_usd"],
                           "robot": out["robot"]["initial"]["body"], "conclusion_by": out["conclusion"].get("by")}
        print(out["id"], r["instance_id"], out["verification"]["status"])
    index["records"] = list(rows.values())
    with open(idx_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1)


if __name__ == "__main__":
    main()
