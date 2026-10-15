#!/usr/bin/env python
"""Forge Loop scoreboard: a small PRE-REGISTERED comparison of Nemotron-selected redesigns against size-matched random edits.

    python scripts/forge_scoreboard.py --register              # write protocol.json (refuses if it exists); commit it BEFORE running
    python scripts/forge_scoreboard.py --run --base URL         # refuses unless protocol.json is committed and unchanged
    python scripts/forge_scoreboard.py --analyze                # pre-declared analysis -> results/summary.json + REPORT section

Every investigation uses a FRESH creature drawn from a Studio starter (exact port of starters.ts), a fresh challenge run, the
production investigation protocol (model_config.json default profile, diagnostic probes on, single round) and the arena's
twin rule: the selected AI arm and its own matched-random twin are validated on the same held-out seeds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "experiments" / "forge_loop" / "scoreboard"
PROTOCOL = OUT / "protocol.json"
RESULTS = OUT / "results"

CELLS = [  # (starter, challenge): push for creatures that stand, stand for creatures that fall without a push (zoo pilot)
    ("balanced", "push"), ("bird-knees", "push"), ("weak-slippery", "push"),
    ("tiny-feet", "stand"), ("top-heavy", "stand"), ("stilts", "stand"),
]
REPLICATES = 2


def protocol() -> dict:
    return {
        "id": "forge-scoreboard-v1",
        "question": "Do Nemotron-selected redesigns of drawn creatures pass the verification rule more often than size-matched random edits?",
        "cells": [{"starter": s, "challenge": k} for s, k in CELLS], "replicates_per_cell": REPLICATES,
        "n_investigations": len(CELLS) * REPLICATES,
        "investigation": {"mode": "live", "profile": "default (experiments/forge_loop/model_config.json)", "probes": True, "loop": False,
                          "challenge_seeds": 8, "creature": "fresh per investigation, experimental mode, starter strokes interpreted by "
                          "/api/freehand/interpret"},
        "unit": "one investigation",
        "primary_outcome": ("paired binary per investigation: AI = the arena's selected AI arm has verdict VERIFIED_IMPROVEMENT; "
                            "TWIN = that arm's own matched-random twin (validated on the same held-out seeds) has VERIFIED_IMPROVEMENT"),
        "primary_analysis": ("exact one-sided McNemar (binomial on discordant pairs, H1: AI-only > twin-only) over investigations in which an AI "
                             "arm and its twin were both validated; alpha 0.05. Claim 'AI-selected edits verified more often than matched "
                             "random edits on this zoo' ONLY if p < 0.05; otherwise report 'no evidence of a difference'."),
        "missing_data": ("investigations with model failure, no valid proposal, or no validated twin are counted and reported separately and "
                         "excluded from the paired test (they count as AI failures in the secondary 'AI verified per attempted "
                         "investigation' rate)"),
        "secondary": ["AI verified rate per attempted investigation (Wilson 95% CI)", "twin verified rate", "heuristic verified rate",
                      "median paired diff AI vs original and twin vs original", "probe confirmation rate", "model calls, tokens, USD, "
                      "rollouts, wall time"],
        "caps": {"model_requests": 3 * len(CELLS) * REPLICATES, "usd": 1.0, "wall_hours": 2.0},
        "no_retries": "a failed investigation is recorded, never rerun",
        "verdict_rule": "verdict_v1 (creature_forge/verdict.py at the registered commit)",
        "registered_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def committed_unchanged() -> bool:
    rel = str(PROTOCOL.relative_to(ROOT)).replace("\\", "/")
    try:
        blob = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{rel}"], capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        return False
    return hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest() == sha(PROTOCOL)


def run(base: str) -> None:
    from scripts.forge_acceptance import STARTERS, call, wait_job
    if not PROTOCOL.exists() or not committed_unchanged():
        raise SystemExit("protocol.json must exist and be committed unchanged before any run")
    p = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    log = RESULTS / "runs.jsonl"
    done = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.exists() else []
    if done:
        raise SystemExit(f"{len(done)} runs already recorded; the scoreboard runs once (no reruns)")
    t0 = time.time()
    for rep in range(1, p["replicates_per_cell"] + 1):
        for cell in p["cells"]:
            if time.time() - t0 > p["caps"]["wall_hours"] * 3600:
                raise SystemExit("wall-clock cap reached")
            strokes, materials = STARTERS[cell["starter"]]
            row = {"starter": cell["starter"], "challenge": cell["challenge"], "replicate": rep, "started": time.time()}
            st, interp = call(base, "POST", "/api/freehand/interpret", {"strokes": strokes, "guided": False, "materials": materials or {}})
            st, cr = call(base, "POST", "/api/forge/creatures", {"name": f"sb-{cell['starter']}-{rep}", "body": interp["body"],
                                                                 "mode": "experimental", "drawing": {"strokes": strokes}})
            cid = cr["id"]
            st, out = call(base, "POST", f"/api/forge/creatures/{cid}/versions/1/challenges", {"kind": cell["challenge"], "seeds": 8})
            job = wait_job(base, out["job_id"])
            row.update(cid=cid, run_id=out["run_id"], challenge_job=job["status"])
            st, inv = call(base, "POST", f"/api/forge/creatures/{cid}/versions/1/investigations",
                           {"run_id": out["run_id"], "mode": "live", "probes": True})
            if st != 200:
                row.update(error=f"investigation refused ({st}): {inv.get('detail')}")
            else:
                job = wait_job(base, inv["job_id"], limit_s=1800)
                row.update(investigation_id=inv["investigation_id"], investigation_job=job["status"])
            row["finished"] = time.time()
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(json.dumps(row)[:300], flush=True)


def wilson(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    z, ph = 1.959964, k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def analyze(records_dir: Path) -> dict:
    rows = [json.loads(l) for l in (RESULTS / "runs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    per, ai_k, tw_k, he_k, pairs, excluded, probes_conf, probes_n = [], 0, 0, 0, [], [], 0, 0
    cost = {"calls": 0, "tokens": 0, "usd": 0.0, "rollouts": 0, "wall_s": 0.0}
    for row in rows:
        iid = row.get("investigation_id")
        rec = json.loads((records_dir / f"{iid}.json").read_text(encoding="utf-8")) if iid and (records_dir / f"{iid}.json").exists() else None
        if rec is None:
            excluded.append({"row": row, "reason": row.get("error") or "no record"})
            continue
        for k in cost:
            cost[k] += (rec.get("budget") or {}).get(k) or 0
        for e in (rec.get("probes") or {}).get("expectations") or []:
            if e.get("confirmed") is not None:
                probes_n += 1
                probes_conf += bool(e["confirmed"])
        sel = rec.get("selection") or {}
        ai, twin = sel.get("ai"), sel.get("matched_twin")
        v = rec.get("verdicts") or {}
        ai_ok = bool(ai and (v.get(ai) or {}).get("status") == "VERIFIED_IMPROVEMENT")
        he_ok = (v.get("heuristic") or {}).get("status") == "VERIFIED_IMPROVEMENT"
        ai_k += ai_ok
        he_k += bool(he_ok)
        entry = {"investigation_id": iid, "starter": row["starter"], "challenge": row["challenge"], "replicate": row["replicate"],
                 "status": rec["status"], "ai_arm": ai, "ai_verdict": (v.get(ai) or {}).get("status") if ai else None,
                 "ai_median_diff": (v.get(ai) or {}).get("median_diff") if ai else None, "twin": twin,
                 "twin_verdict": (v.get(twin) or {}).get("status") if twin else None,
                 "twin_median_diff": (v.get(twin) or {}).get("median_diff") if twin else None,
                 "heuristic_verdict": (v.get("heuristic") or {}).get("status")}
        per.append(entry)
        if ai and twin and twin in v and ai in v:
            tw_ok = (v.get(twin) or {}).get("status") == "VERIFIED_IMPROVEMENT"
            tw_k += tw_ok
            pairs.append((ai_ok, tw_ok))
        else:
            excluded.append({"investigation_id": iid, "reason": f"status {rec['status']}; ai={ai}; twin={twin}"})
    b = sum(1 for a, t in pairs if a and not t)
    c = sum(1 for a, t in pairs if t and not a)
    n_disc = b + c
    p = sum(math.comb(n_disc, i) for i in range(b, n_disc + 1)) / 2 ** n_disc if n_disc else 1.0
    n_att = len(rows)
    summary = {
        "protocol": json.loads(PROTOCOL.read_text(encoding="utf-8"))["id"], "n_attempted": n_att, "n_paired": len(pairs),
        "paired_table": {"ai_only": b, "twin_only": c, "both": sum(1 for a, t in pairs if a and t), "neither": sum(1 for a, t in pairs if not a and not t)},
        "mcnemar_one_sided_p": round(p, 6),
        "conclusion": ("AI-selected edits verified more often than matched random edits on this zoo (pre-declared test, p < 0.05)"
                       if p < 0.05 else "no evidence of a difference between AI-selected and matched random edits (pre-declared test)"),
        "ai_verified_per_attempt": {"k": ai_k, "n": n_att, "wilson95": wilson(ai_k, n_att)},
        "twin_verified_per_pair": {"k": tw_k, "n": len(pairs), "wilson95": wilson(tw_k, len(pairs))},
        "heuristic_verified_per_attempt": {"k": he_k, "n": n_att, "wilson95": wilson(he_k, n_att)},
        "probe_confirmation": {"confirmed": probes_conf, "evaluated": probes_n},
        "cost": {k: round(v, 4) for k, v in cost.items()}, "per_investigation": per, "excluded": excluded,
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--records", default=str(ROOT / "artifacts" / "forge" / "investigations"))
    a = ap.parse_args()
    if a.register:
        if PROTOCOL.exists():
            raise SystemExit("protocol.json already exists; a registered protocol is never rewritten")
        OUT.mkdir(parents=True, exist_ok=True)
        PROTOCOL.write_text(json.dumps(protocol(), indent=1) + "\n", encoding="utf-8")
        print("registered", PROTOCOL, sha(PROTOCOL))
    elif a.run:
        run(a.base)
    elif a.analyze:
        s = analyze(Path(a.records))
        print(json.dumps({k: v for k, v in s.items() if k not in ("per_investigation",)}, indent=1))


if __name__ == "__main__":
    main()
