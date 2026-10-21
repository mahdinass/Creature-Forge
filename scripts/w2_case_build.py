"""W2: build the display-ready attribution case for the recorded HaS investigation of hdb-v1-gen-0137:one_side_weakness:4.

  python scripts/w2_case_build.py                       # case.json from the tracked excerpt (no physics, no model call)
  python scripts/w2_case_build.py --full-root <dir>     # also cross_instance.json from the full Stage 2 transfer files
  python scripts/w2_case_build.py --check [--full-root <dir>]   # rebuild in memory and compare with the committed files

Inputs: experiments/w2/gen0137_one_side_weakness/{A3,A1e,A4}.jsonl, byte-exact single lines of the Stage 2 transfer records
(SOURCES.json pins each line's SHA-256 and its source file's SHA-256, which is also pinned in
experiments/causal_engineer/dev/hdb/STAGE2_TRANSFER_agent_v4.md). Every refusal names its reason; nothing is clipped.

What case.json holds, all read from the records (nothing restated by hand):
  * the shared start: the plant observation (4 seeds), the engine's belief after it, the eligibility check;
  * the fork: the notebook exactly as Nemotron saw it on turn 0 (candidate experiments, EIG, per-hypothesis walking
    predictions, the engine's recommendation), parsed from the recorded prompt, Nemotron's reply and the engine's choice;
  * per arm (A3 Nemotron, A1e engine alone, A4 Nemotron + memory + learned posterior): every step, the measured per-seed
    results of the chosen experiment, belief history, proposed hypotheses and their fate, the engine's repair log, the
    designs and their checks, the submitted design, the independent verification, costs and model-call metadata;
  * determinism checks between arms (identical observation; identical X1 features where the same experiment ran).

cross_instance.json (needs --full-root): the 36 paired single-mechanism transfer instances, A1e vs A3 vs A4 (FULL, MAP
correct, first experiment and who chose it), and the inference-ledger check of this episode's request ids.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CASE_DIR = os.path.join(ROOT, "experiments", "w2", "gen0137_one_side_weakness")
INSTANCE_ID = "hdb-v1-gen-0137:one_side_weakness:4"
ARMS = {"A3": "LIVE", "A1e": "NO_AI", "A4": "LIVE"}
ARM_LABEL = {"A3": "Nemotron scientist (A3)", "A1e": "Engine alone (A1e)", "A4": "Nemotron + memory + learned posterior (A4)"}
FULL_FILES = {   # Stage 2 transfer records (git-ignored), SHA-256 as pinned in STAGE2_TRANSFER_agent_v4.md
    "A3": ("stage2_final/s2_transfer_A3.jsonl", "540b9415921b205a80ad62fe6ae9565f5c6d6027bae63e2fb1dee8dca374ea98"),
    "A1e": ("s2T_A1e.jsonl", "2014fa80f8f333b1b2f8d4ba561da024516fb49b0334ef7a696acbfa535cdf56"),
    "A4": ("stage2_final/s2_transfer_A4.jsonl", "cb34a780d76f9325718e53f3d8345672ab642aa005a334cd96bf614dec7ec77a"),
}
LEDGER = ("stage2_final/inference_ledger_main_20261020.jsonl", "729e37ffb0e6e594f0a374a40c4e0194b59d9b79dbb50b78c60b8d7a2e0f4d9a")
FEATURES = ("walking", "time_upright", "fall_direction", "pitch_mean", "com_vx_mean", "step_freq_hz", "step_length_over_L",
            "double_support_fraction", "capture_margin_over_L_mean", "slip_fraction")
CAPTIONS = {
    "playback": "RECORDED LIVE: playback of a stored Nemotron investigation (2026-10-20). No model is called on this page.",
    "scope": "A single instance. Across the 36 paired instances, Nemotron and the engine alone are level on verified "
             "recovery (15 vs 14, discordant 4 vs 3, one-sided p = 0.50); the engine alone won 3 instances Nemotron lost.",
    "repair": "The repair itself was run by the engine's optimiser (delegated); Nemotron chose the experiment.",
    "do1": "Separate result: the DO-1 L4 recovery was a deterministic optimiser-objective change with no Nemotron (NO_AI).",
}


class CaseError(RuntimeError):
    """The excerpt or a source does not match its pins, or a record is not what this case needs."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def design_hash(d: dict) -> str:
    """The 10-hex-digit FA-1C design identifier (scripts/ta1_tool_access.design_hash), inlined to stay import-light."""
    return sha256(json.dumps({"b": d["body"], "v": d["vector"]}, sort_keys=True).encode())[:10]


def load_excerpt(case_dir: str = CASE_DIR) -> tuple[dict, dict]:
    with open(os.path.join(case_dir, "SOURCES.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    recs = {}
    for s in man["sources"]:
        with open(os.path.join(case_dir, s["file"]), "rb") as fh:
            raw = fh.read()
        line = raw.rstrip(b"\r\n")
        if raw.count(b"\n") != 1 or sha256(line) != s["line_sha256"]:
            raise CaseError(f"{s['file']}: not the pinned single line (sha256 {sha256(line)} vs {s['line_sha256']})")
        if FULL_FILES[s["arm"]][1] != s["source_sha256"]:
            raise CaseError(f"{s['file']}: source sha256 {s['source_sha256']} is not the Stage 2 pin")
        rec = json.loads(line)
        if rec["instance_id"] != INSTANCE_ID or rec["arm"] != s["arm"] or rec["provenance"] != ARMS[s["arm"]]:
            raise CaseError(f"{s['file']}: {rec['instance_id']} / {rec['arm']} / {rec['provenance']} is not the expected episode")
        if (rec["nemotron"] is None) != (ARMS[s["arm"]] == "NO_AI"):
            raise CaseError(f"{s['file']}: provenance {rec['provenance']} disagrees with the presence of model calls")
        recs[s["arm"]] = rec
    if sorted(recs) != sorted(ARMS):
        raise CaseError(f"expected arms {sorted(ARMS)}, got {sorted(recs)}")
    return man, recs


# ------------------------------------------------------------------------------------------------ notebook parsing
_CAND = re.compile(r"^\s+(\S+): cost (\d+), EIG ([0-9.]+), H1/H2/H3 predict (\d+)/(\d+)/(\d+)\s*$")
_BELIEF = re.compile(r"^\s+([0-9.]+)\s+(\S+)\s+\[(\w+)\]\s*$")


def notebook(prompt: str) -> dict:
    """The turn-0 notebook sections that decide the experiment: belief rows, candidates, recommendation, budgets."""
    lines = prompt.splitlines()
    sec, belief, cands, rec, entropy, n_pred = None, [], [], None, None, None
    for ln in lines:
        if ln.startswith("BELIEF"):
            sec = "belief"
        elif ln.startswith("CANDIDATE EXPERIMENTS"):
            sec = "cand"
            m = re.search(r"out of (\d+) trials", ln)
            n_pred = int(m.group(1)) if m else None
        elif ln.startswith("ENGINE RECOMMENDATION"):
            rec = ln.split(":", 1)[1].strip()
            sec = None
        elif not ln.strip():
            sec = None if sec != "belief" else sec
        elif sec == "belief":
            m = _BELIEF.match(ln)
            if m:
                belief.append({"weight": float(m.group(1)), "hypothesis": m.group(2), "proposed_by": m.group(3)})
            elif (me := re.search(r"entropy ([0-9.]+) nats", ln)):
                entropy = float(me.group(1))
                sec = None
        elif sec == "cand":
            m = _CAND.match(ln)
            if m:
                cands.append({"id": m.group(1), "cost": int(m.group(2)), "eig": float(m.group(3)),
                              "predicted_walking": [int(m.group(i)) for i in (4, 5, 6)]})
    if not cands or rec is None or not belief:
        raise CaseError("the turn-0 notebook could not be parsed (candidates, belief or recommendation missing)")
    return {"belief": belief, "entropy_nats": entropy, "candidates": cands, "predicted_out_of": n_pred,
            "hypotheses": [b["hypothesis"] for b in belief[:3]], "engine_recommendation": rec}


# ------------------------------------------------------------------------------------------------ per-arm extraction
def _per_seed(exp: dict) -> list[dict]:
    return [{"seed": int(s), **{k: f.get(k) for k in FEATURES}} for s, f in exp["features"].items()]


def _posterior(rows) -> list[dict]:
    return [{"structure": s, "w": round(float(w), 6)} for s, w in rows]


def _calls(rec: dict) -> list[dict]:
    out = []
    for c in (rec.get("nemotron") or {}).get("calls", []):
        u = c.get("usage") or {}
        out.append({"request_id": c.get("request_id"), "ok": c.get("ok"), "finish_reason": c.get("finish_reason"),
                    "latency_s": round(float(c["latency_s"]), 2) if c.get("latency_s") is not None else None,
                    "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                    "reasoning_tokens": u.get("reasoning_tokens"), "cost_usd": c.get("cost_usd"),
                    "prompt_sha256": c.get("prompt_sha256"), "schema_name": c.get("schema_name"),
                    "temperature": (c.get("settings") or {}).get("temperature"),
                    "engine_recommendation": _recommendation(c), "model_check": _model_check(c)})
    return out


def _model_check(call: dict) -> list[str]:
    """The notebook's MODEL CHECK section on that turn: its header (with the rule) and one line per experiment."""
    msgs = call.get("messages") or []
    if not msgs:
        return []
    m = re.search(r"(MODEL CHECK[^\n]*)\n(.*?)(?:\n\s*\n|$)", msgs[-1]["content"], re.S)
    return [m.group(1).strip()] + [ln.strip() for ln in m.group(2).splitlines() if ln.strip()] if m else []


def _recommendation(call: dict) -> str | None:
    msgs = call.get("messages") or []
    if not msgs:
        return None
    m = re.search(r"ENGINE RECOMMENDATION[^:]*:\s*(.+)", msgs[-1]["content"])
    return m.group(1).strip() if m else None


def _step(t: dict, notes: dict) -> dict:
    a = dict(t["action"])
    words = None
    if t["actor"] == "nemotron":
        n = notes.get(t.get("turn"))
        words = {k: n[k] for k in ("understanding", "uncertainty", "why")} if n else None
        a = {k: v for k, v in a.items() if k not in ("understanding", "uncertainty", "why")}
    r = t["result"]
    res = {k: r[k] for k in ("ok", "refused", "id", "eig", "best_eig", "accepted", "design") if k in r}
    if "posterior" in r:
        res["posterior"] = _posterior(r["posterior"][:3])
    if "ranking" in r:
        res["ranking"] = [{"tool": x["tool"], "probe": x["probe"], "score": round(float(x["score"]), 4),
                           "cma_walking": x.get("cma_walking")} for x in r["ranking"]]
    if "proposals" in r:
        res["hypotheses"] = [{"pid": h["pid"], "fitted": h.get("fitted"), "weight": h["weight"], "rank": h["rank"],
                              "status": h.get("status"), "loglik_gap": h.get("loglik_gap")} for h in r["proposals"].get("added", [])]
        res["posterior"] = _posterior(r["proposals"]["posterior"][:3])
    return {"seq": t["seq"], "turn": t.get("turn"), "actor": t["actor"], "action": a, "words": words, "result": res,
            "plant_cost": t["plant_cost"], "twin_cost": t["twin_cost"], "plant_used": t["plant_used"], "twin_used": t["twin_used"]}


def arm_view(rec: dict) -> dict:
    ag, eng = rec["agent"], rec["engine"]
    notes = {n["turn"]: n for n in ag.get("notes") or []}
    designs = {d["index"]: d for d in rec["designs"]}
    checked = rec["repair"].get("checked") or {}
    exps = [{"id": e["id"], "kind": e["kind"], "seeds": [int(s) for s in e["seeds"]], "cost": e["cost"],
             "per_seed": _per_seed(e), "n_walking": int(sum(1 for f in e["features"].values() if f.get("walking")))}
            for e in eng["experiments"]]
    v = rec["verification"]
    nem = rec.get("nemotron") or {}
    return {
        "arm": rec["arm"], "label": ARM_LABEL[rec["arm"]], "provenance": rec["provenance"],
        "steps": [_step(t, notes) for t in ag["trace"]],
        "experiments": exps,
        "belief_history": [{"label": h["label"], "plant_used": h["plant_used"], "twin_used": h["twin_used"],
                            "top": _posterior([(s["structure"], s["w"]) for s in h["structures"][:3]])} for h in eng["history"]],
        "designs": [{"index": i, "source": d["source"], "design_hash": design_hash(d),
                     "check": checked.get(str(i))} for i, d in sorted(designs.items())],
        "repair_log": rec["repair"]["log"], "repair_accepted": rec["repair"]["accepted"],
        "submitted": {"index": rec["submitted"], "source": designs[rec["submitted"]]["source"],
                      "design_hash": design_hash(designs[rec["submitted"]])},
        "conclusion": {k: v2 for k, v2 in (ag.get("conclusion") or {}).items() if k != "repair"},
        "verification": {"status": v["status"], "walking_frac": v["walking_frac"], "reasons": v["reasons"],
                         "rollouts": v["rollouts"]},
        "final_belief": {"structure": rec["map_structure"], "mass": rec["map_mass"],
                         "mass_on_truth": rec["posterior_mass_on_injected"],
                         "correct": rec["map_structure"] == rec["injected_structure"]},
        "costs": {"plant_used": eng["ledger"]["used"], "plant_total": eng["ledger"]["total"],
                  "twin_used": eng["ledger"]["twin"]["used"], "twin_total": eng["ledger"]["twin"]["total"],
                  "llm_calls": len(nem.get("calls") or []), "cost_usd": nem.get("cost_usd"), "tokens": nem.get("tokens"),
                  "wall_s": round(float(rec["wall_s"]), 1) if rec.get("wall_s") is not None else None},
        "model": {"name": nem.get("model"), "system_prompt_sha256": sha256((nem.get("system_prompt") or "").encode()),
                  "calls": _calls(rec)} if nem else None,
        "predictions_registered": len(ag.get("predictions") or []),
    }


def _validate_n() -> int:
    from creature_forge import hdb_bench as hb   # seed derivation only; no simulation
    base, fam, sev = INSTANCE_ID.rsplit(":", 2)
    return len(hb.instance_seeds(base, fam, int(sev))["validate"])


def build_case(man: dict, recs: dict, n_validate: int | None = None) -> dict:
    a3, a1, a4 = recs["A3"], recs["A1e"], recs["A4"]
    for k in ("injected_structure", "family", "severity", "mult", "strength", "check", "bench", "version"):
        if not (a3[k] == a1[k] == a4[k]):
            raise CaseError(f"the arms disagree on {k}: not the same instance")
    if not (a3["designs"][0] == a1["designs"][0] == a4["designs"][0]):
        raise CaseError("the arms start from different nominal designs")
    x0 = [r["engine"]["experiments"][0] for r in (a3, a1, a4)]
    h0 = [r["engine"]["history"][0] for r in (a3, a1, a4)]
    if not (x0[0] == x0[1] == x0[2]) or not (h0[0] == h0[1] == h0[2]):
        raise CaseError("the arms' observation or belief after it differ: the fork is not clean")
    nb = notebook(a3["nemotron"]["calls"][0]["messages"][-1]["content"])
    nb4 = notebook(a4["nemotron"]["calls"][0]["messages"][-1]["content"])
    if nb != nb4:
        raise CaseError("A3 and A4 saw different turn-0 notebooks")
    first = {arm: next(t for t in r["agent"]["trace"] if t["action"].get("action") == "experiment") for arm, r in recs.items()}
    reply0 = json.loads(a3["nemotron"]["calls"][0]["content"])
    if reply0.get("action") != "experiment" or reply0.get("experiment") != first["A3"]["action"]["experiment"]:
        raise CaseError("Nemotron's recorded reply does not match the experiment the agent ran")
    if nb["engine_recommendation"] != f"experiment {first['A1e']['action']['experiment']}":
        raise CaseError("the engine recommendation shown to Nemotron is not what the engine alone ran")
    n = n_validate if n_validate is not None else _validate_n()
    views = {arm: arm_view(r) for arm, r in recs.items()}
    for arm, vw in views.items():
        v = vw["verification"]
        k = round(v["walking_frac"] * n)
        if abs(k - v["walking_frac"] * n) > 1e-9 or v["rollouts"]["validation"] != 2 * n:
            raise CaseError(f"{arm}: verification counts are not consistent with {n} validation seeds")
        v["walking"], v["n"] = k, n
    x1 = {arm: r["engine"]["experiments"][1] for arm, r in recs.items()}
    chosen = {arm: first[arm]["action"]["experiment"] for arm in recs}
    cand = {c["id"]: c for c in nb["candidates"]}
    return {
        "schema": "w2_case_v1", "instance_id": INSTANCE_ID, "built_by": "scripts/w2_case_build.py",
        "sources": [{k: s[k] for k in ("arm", "file", "source", "source_line", "source_sha256", "line_sha256")} for s in man["sources"]],
        "captions": CAPTIONS,
        "evaluation_only": {"note": "Ground truth of the hidden plant, added after the investigation; no arm ever saw it.",
                            "injected_structure": a3["injected_structure"], "family": a3["family"],
                            "severity": a3["severity"], "mult": a3["mult"], "strength": a3["strength"]},
        "nominal_design": {"body": a3["designs"][0]["body"], "design_hash": design_hash(a3["designs"][0])},
        "eligibility_check": a3["check"],
        "shared": {"observation": {"id": x0[0]["id"], "seeds": [int(s) for s in x0[0]["seeds"]], "per_seed": _per_seed(x0[0]),
                                   "n_walking": int(sum(1 for f in x0[0]["features"].values() if f.get("walking")))},
                   "belief_after_observation": _posterior([(s["structure"], s["w"]) for s in h0[0]["structures"][:3]]),
                   "identical_in_all_arms": True},
        "fork": {"notebook": nb,
                 "nemotron": {"experiment": chosen["A3"], "eig": first["A3"]["result"].get("eig"),
                              "best_eig": first["A3"]["result"].get("best_eig"),
                              "predicted_walking": cand.get(chosen["A3"], {}).get("predicted_walking"),
                              "words": views["A3"]["steps"][first["A3"]["seq"]]["words"],
                              "registered_prediction": first["A3"]["action"].get("prediction"),
                              "prediction_issue": first["A3"]["action"].get("prediction_issue"),
                              "call": views["A3"]["model"]["calls"][0]},
                 "engine": {"experiment": chosen["A1e"], "eig": first["A1e"]["result"].get("eig"),
                            "best_eig": first["A1e"]["result"].get("best_eig"),
                            "predicted_walking": cand.get(chosen["A1e"], {}).get("predicted_walking"),
                            "why": first["A1e"]["action"].get("why")},
                 "a4_same_choice": chosen["A4"] == chosen["A3"]},
        "arms": views,
        "determinism": {"observation_identical_all_arms": True,
                        "x1_identical_A3_A4": chosen["A3"] == chosen["A4"] and x1["A3"] == x1["A4"],
                        "belief_after_x1_identical_A3_A4": recs["A3"]["engine"]["history"][1] == recs["A4"]["engine"]["history"][1]},
    }


# ------------------------------------------------------------------------------------------------ cross-instance (full files)
def _load_full(full_root: str) -> dict:
    out = {}
    for arm, (rel, want) in FULL_FILES.items():
        p = os.path.join(full_root, rel)
        with open(p, "rb") as fh:
            data = fh.read()
        if sha256(data) != want:
            raise CaseError(f"{rel}: sha256 {sha256(data)} is not the Stage 2 pin {want}")
        out[arm] = {"lines": data.split(b"\n"), "recs": {}}
        for raw in out[arm]["lines"]:
            if raw.strip():
                r = json.loads(raw)
                out[arm]["recs"][r["instance_id"]] = r
    return out


def build_cross(full_root: str, man: dict, recs: dict) -> dict:
    full = _load_full(full_root)
    for s in man["sources"]:
        if sha256(full[s["arm"]]["lines"][s["source_line"] - 1].rstrip(b"\r")) != s["line_sha256"]:
            raise CaseError(f"{s['file']} is not line {s['source_line']} of {s['source']}")
    ids = sorted(full["A3"]["recs"])
    if set(ids) != set(full["A1e"]["recs"]) or set(ids) != set(full["A4"]["recs"]):
        raise CaseError("the arms cover different instances")

    def first_exp(r):
        for t in r["agent"]["trace"]:
            if t["action"].get("action") == "experiment":
                return {"experiment": t["action"].get("experiment"), "actor": t["actor"]}
        return None

    rows = []
    for i in ids:
        row = {"instance_id": i}
        for arm in ("A1e", "A3", "A4"):
            r = full[arm]["recs"][i]
            row[arm] = {"full": r["verification"]["status"] == "FULL_RECOVERY", "status": r["verification"]["status"],
                        "map_correct": r["map_structure"] == r["injected_structure"], "first_experiment": first_exp(r)}
        rows.append(row)

    def count(pred):
        return sum(1 for r in rows if pred(r))
    agg = {"n": len(rows),
           "full": {a: count(lambda r, a=a: r[a]["full"]) for a in ("A1e", "A3", "A4")},
           "map_correct": {a: count(lambda r, a=a: r[a]["map_correct"]) for a in ("A1e", "A3", "A4")},
           "full_discordant_A3_vs_A1e": {"A3_only": count(lambda r: r["A3"]["full"] and not r["A1e"]["full"]),
                                         "A1e_only": count(lambda r: r["A1e"]["full"] and not r["A3"]["full"])},
           "map_discordant_A3_vs_A1e": {"A3_only": count(lambda r: r["A3"]["map_correct"] and not r["A1e"]["map_correct"]),
                                        "A1e_only": count(lambda r: r["A1e"]["map_correct"] and not r["A3"]["map_correct"])},
           "first_experiment_differs": count(lambda r: (r["A3"]["first_experiment"] or {}).get("experiment") !=
                                             (r["A1e"]["first_experiment"] or {}).get("experiment")),
           "map_and_full_both_favour_A3": [r["instance_id"] for r in rows if r["A3"]["map_correct"] and not r["A1e"]["map_correct"]
                                           and r["A3"]["full"] and not r["A1e"]["full"]],
           "A3_full_only": [r["instance_id"] for r in rows if r["A3"]["full"] and not r["A1e"]["full"]],
           "A1e_full_only": [r["instance_id"] for r in rows if r["A1e"]["full"] and not r["A3"]["full"]],
           "A3_map_wrong_A1e_right": [r["instance_id"] for r in rows if r["A1e"]["map_correct"] and not r["A3"]["map_correct"]]}
    d = agg["full_discordant_A3_vs_A1e"]
    k, m = d["A3_only"], d["A3_only"] + d["A1e_only"]
    from math import comb
    agg["mcnemar_one_sided_p_A3_gt_A1e"] = round(sum(comb(m, j) for j in range(k, m + 1)) / 2 ** m, 4) if m else None
    # LIVE check: this episode's request ids in the main VM's inference ledger
    p = os.path.join(full_root, LEDGER[0])
    with open(p, "rb") as fh:
        data = fh.read()
    if sha256(data) != LEDGER[1]:
        raise CaseError(f"{LEDGER[0]}: not the pinned inference ledger")
    ledger = {}
    for raw in data.splitlines():
        if raw.strip():
            e = json.loads(raw)
            ledger.setdefault(e.get("request_id"), []).append(e)
    live = {}
    for arm in ("A3", "A4"):
        ids_ = [c["request_id"] for c in recs[arm]["nemotron"]["calls"]]
        live[arm] = [{"request_id": rid, "in_ledger": len(ledger.get(rid, [])),
                      "ledger_model": (ledger.get(rid) or [{}])[0].get("model"),
                      "ledger_cost_usd": (ledger.get(rid) or [{}])[0].get("cost_usd")} for rid in ids_]
    return {"schema": "w2_cross_instance_v1", "built_by": "scripts/w2_case_build.py --full-root",
            "population": "Stage 2 transfer, 36 single-mechanism dev instances, paired arms (development evidence)",
            "sources": {arm: {"file": FULL_FILES[arm][0], "sha256": FULL_FILES[arm][1]} for arm in FULL_FILES},
            "ledger": {"file": LEDGER[0], "sha256": LEDGER[1], "this_case": live},
            "aggregates": agg, "rows": rows}


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--full-root", help="directory holding the full Stage 2 transfer files (artifacts/vm/hdb/artifacts/hdb)")
    ap.add_argument("--check", action="store_true", help="compare a rebuild with the committed outputs; write nothing")
    a = ap.parse_args(argv)
    man, recs = load_excerpt()
    outs = {"case.json": dumps(build_case(man, recs))}
    if a.full_root:
        outs["cross_instance.json"] = dumps(build_cross(a.full_root, man, recs))
    bad = 0
    for name, text in outs.items():
        p = os.path.join(CASE_DIR, name)
        if a.check:
            with open(p, encoding="utf-8") as fh:
                same = fh.read() == text
            print(f"{name}: {'identical' if same else 'DIFFERS'}")
            bad += not same
        else:
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            print(f"wrote {os.path.relpath(p, ROOT)} ({len(text.encode())} bytes, sha256 {sha256(text.encode())[:12]})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
