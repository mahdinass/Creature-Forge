#!/usr/bin/env python
"""Engineering memory evaluation: a small PRE-REGISTERED paired comparison of investigations WITH and WITHOUT memory on new creatures.

    python scripts/forge_memory_eval.py --register      # freeze the bank + write protocol.json (refuses if it exists); COMMIT before running
    python scripts/forge_memory_eval.py --run           # needs the committed protocol + bank unchanged; server WITHOUT CF_MEMORY (bank frozen)
    python scripts/forge_memory_eval.py --analyze       # pre-declared analysis -> results/summary.json

Pairing: each test creature/replicate gets ONE fresh challenge run and TWO live investigations on that same run (memory on / off,
order alternating by replicate). Both investigations of a pair evaluate the same creature version and round, so the arena validates
them on identical held-out seeds. The bank is built only from archived LIVE records and never contains the test creatures.
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
OUT = ROOT / "experiments" / "forge_loop" / "memory_eval"
PROTOCOL, BANK, RESULTS = OUT / "protocol.json", OUT / "bank.jsonl", OUT / "results"
BANK_SOURCES = ["experiments/forge_loop/scoreboard/results/records", "experiments/forge_loop/dev_live_records"]
# New shapes (studio starter geometry with different proportions/materials); none of these bodies is in the bank.
CREATURES = {
    "short-legs": ({"thigh": 0.22, "shank": 0.22, "foot": 0.12}, None),
    "long-legs": ({"thigh": 0.38, "shank": 0.38, "foot": 0.14}, None),
    "big-torso": ({"torsoW": 0.2, "torsoH": 0.45, "foot": 0.14}, None),
    "small-feet": ({"foot": 0.10}, None),
    "heavy-legs": ({}, {"leg_density": 2500.0}),
    "soft-motors": ({}, {"torque_limit": 25.0}),
}
REPLICATES, CHALLENGE = 2, "push"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def committed_unchanged(path: Path) -> bool:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    try:
        blob = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{rel}"], capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        return False
    return hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest() == sha(path)


def protocol(bank_sha: str, bank_size: int) -> dict:
    return {
        "id": "forge-memory-eval-v1",
        "question": "Does engineering memory (measured lessons from OTHER creatures) increase how often the AI's selected redesign is verified?",
        "creatures": {k: {"figure": f, "materials": m} for k, (f, m) in CREATURES.items()}, "challenge": CHALLENGE,
        "replicates": REPLICATES, "n_pairs": len(CREATURES) * REPLICATES,
        "pairing": "one fresh challenge run per creature/replicate; two live investigations on it: memory on and memory off; order "
                   "memory-first on replicate 1, no-memory-first on replicate 2; identical arena seeds within a pair",
        "investigation": {"mode": "live", "profile": "default", "probes": True, "loop": False, "memory_k": 3},
        "bank": {"path": "experiments/forge_loop/memory_eval/bank.jsonl", "sha256_lf": bank_sha, "lessons": bank_size,
                 "sources": BANK_SOURCES, "frozen": "the evaluation server runs WITHOUT CF_MEMORY, so no lesson is added during the run"},
        "primary_outcome": "per investigation: the arena's selected AI arm has verdict VERIFIED_IMPROVEMENT (no AI arm counts as not verified)",
        "primary_analysis": ("exact one-sided McNemar on discordant pairs (H1: memory-only > no-memory-only), alpha 0.05. Claim 'memory "
                             "increased verified redesigns on these creatures' ONLY if p < 0.05; otherwise 'no evidence of a benefit'."),
        "power_note": "12 pairs: low power; a null result is the expected outcome unless the effect is large. Stated before running.",
        "secondary": ["AI verified rate per arm (Wilson 95% CI)", "paired median diff of the AI arm (memory - no memory)",
                      "memory cited in hypotheses", "matched-twin verdicts", "calls, tokens, USD, rollouts"],
        "caps": {"model_requests": 3 * 2 * len(CREATURES) * REPLICATES, "usd": 1.0, "wall_hours": 2.5},
        "no_retries": "a failed investigation is recorded as not verified, never rerun",
        "registered_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def strokes_for(name: str):
    from tests.test_freehand_starters import figure
    f, m = CREATURES[name]
    return figure(**f), m


def register() -> None:
    if PROTOCOL.exists():
        raise SystemExit("protocol.json already exists; a registered protocol is never rewritten")
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "forge_memory.py"), "--build", *[str(ROOT / s) for s in BANK_SOURCES],
                    "--out", str(BANK)], check=True)
    n = sum(1 for line in BANK.read_text(encoding="utf-8").splitlines() if line.strip())
    PROTOCOL.write_text(json.dumps(protocol(sha(BANK), n), indent=1) + "\n", encoding="utf-8")
    print("registered", PROTOCOL, "bank lessons", n)


def run(base: str, forge_dir: Path, resume: bool = False) -> None:
    """`resume=True` continues an interrupted run: registered pairs already in runs.jsonl are skipped; a pair whose creature
    (`mem-<name>-<rep>`) already exists on the server WITHOUT a recorded row was interrupted mid-pair, so it is recorded as
    `interrupted` and EXCLUDED - never rerun (no investigation is repeated)."""
    from scripts.forge_acceptance import call, wait_job
    if not (committed_unchanged(PROTOCOL) and committed_unchanged(BANK)):
        raise SystemExit("protocol.json and bank.jsonl must be committed unchanged before any run")
    p = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if sha(BANK) != p["bank"]["sha256_lf"]:
        raise SystemExit("bank does not match the registered hash")
    live_bank = forge_dir / "memory" / "lessons.jsonl"
    live_bank.parent.mkdir(parents=True, exist_ok=True)
    live_bank.write_bytes(BANK.read_bytes())          # the server reads the frozen bank; CF_MEMORY must be unset (no auto-add)
    RESULTS.mkdir(parents=True, exist_ok=True)
    log = RESULTS / "runs.jsonl"
    done = {(r["creature"], r["replicate"]) for r in (json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip())} \
        if log.exists() else set()
    if done and not resume:
        raise SystemExit("runs already recorded; use --resume to continue the remaining registered pairs (no reruns)")
    existing = set()
    if resume:
        # A pair counts as interrupted only if its creature already has at least one investigation (then it is excluded, never
        # rerun). A creature created just before the stop with NO investigation started no investigation: the pair runs normally
        # with a fresh creature, which repeats nothing.
        _, creatures = call(base, "GET", "/api/forge/creatures")
        for c in creatures or []:
            if str(c.get("name", "")).startswith("mem-"):
                _, invs = call(base, "GET", f"/api/forge/investigations?cid={c['id']}")
                if invs:
                    existing.add(c.get("name"))
    t0 = time.time()
    for rep in range(1, p["replicates"] + 1):
        for name in p["creatures"]:
            if (name, rep) in done:
                continue
            if resume and f"mem-{name}-{rep}" in existing:
                _append(log, {"creature": name, "replicate": rep, "interrupted": True,
                              "error": "interrupted mid-pair in an earlier session; excluded, not rerun"})
                continue
            if time.time() - t0 > p["caps"]["wall_hours"] * 3600:
                raise SystemExit("wall-clock cap reached")
            strokes, materials = strokes_for(name)
            _, interp = call(base, "POST", "/api/freehand/interpret", {"strokes": strokes, "guided": False, "materials": materials or {}})
            row = {"creature": name, "replicate": rep, "interpret_outcome": interp.get("outcome")}
            if not interp.get("body"):
                row["error"] = f"drawing not interpretable: {interp.get('errors')}"
                _append(log, row)
                continue
            _, cr = call(base, "POST", "/api/forge/creatures", {"name": f"mem-{name}-{rep}", "body": interp["body"], "mode": "experimental",
                                                               "drawing": {"strokes": strokes}})
            cid = cr["id"]
            _, out = call(base, "POST", f"/api/forge/creatures/{cid}/versions/1/challenges", {"kind": p["challenge"], "seeds": 8})
            row.update(cid=cid, run_id=out["run_id"], challenge_job=wait_job(base, out["job_id"])["status"])
            order = [True, False] if rep % 2 == 1 else [False, True]
            for mem in order:
                st, inv = call(base, "POST", f"/api/forge/creatures/{cid}/versions/1/investigations",
                               {"run_id": out["run_id"], "mode": "live", "probes": True, "memory": mem})
                key = "memory" if mem else "no_memory"
                if st != 200:
                    row[key] = {"error": f"refused ({st}): {inv.get('detail')}"}
                else:
                    job = wait_job(base, inv["job_id"], limit_s=1800)
                    row[key] = {"investigation_id": inv["investigation_id"], "job": job["status"]}
            _append(log, row)
            print(json.dumps(row)[:300], flush=True)


def _append(log: Path, row: dict) -> None:
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def wilson(k: int, n: int) -> list:
    if not n:
        return [None, None]
    z, ph = 1.959964, k / n
    d = 1 + z * z / n
    c, h = (ph + z * z / (2 * n)) / d, z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def analyze(records: Path) -> dict:
    rows = [json.loads(l) for l in (RESULTS / "runs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pairs, per, cost = [], [], {"calls": 0, "tokens": 0, "usd": 0.0, "rollouts": 0}

    def outcome(arm: dict | None):
        iid = (arm or {}).get("investigation_id")
        f = records / f"{iid}.json" if iid else None
        if not f or not f.exists():
            return False, None, None
        rec = json.loads(f.read_text(encoding="utf-8"))
        for k in cost:
            cost[k] += (rec.get("budget") or {}).get(k) or 0
        ai = (rec.get("selection") or {}).get("ai")
        v = (rec.get("verdicts") or {}).get(ai) or {}
        cited = any(str(c).startswith("memory") for h in ((rec.get("validation") or {}).get("hypotheses") or []) for c in h.get("evidence", []))
        return v.get("status") == "VERIFIED_IMPROVEMENT", v.get("median_diff"), {"id": rec["id"], "status": rec["status"], "ai": ai,
                                                                                   "verdict": v.get("status"), "memory_cited": cited}
    excluded = []
    for row in rows:
        if row.get("interrupted") or ("memory" not in row and "no_memory" not in row):
            excluded.append({"creature": row["creature"], "replicate": row["replicate"], "reason": row.get("error")})
            continue   # no investigation pair exists: excluded from the paired test and reported (never rerun)
        m_ok, m_d, m_rec = outcome(row.get("memory"))
        n_ok, n_d, n_rec = outcome(row.get("no_memory"))
        pairs.append((m_ok, n_ok))
        per.append({"creature": row["creature"], "replicate": row["replicate"], "memory": m_rec, "no_memory": n_rec,
                    "memory_median_diff": m_d, "no_memory_median_diff": n_d, "error": row.get("error")})
    b = sum(1 for m, n in pairs if m and not n)
    c = sum(1 for m, n in pairs if n and not m)
    nd = b + c
    p = sum(math.comb(nd, i) for i in range(b, nd + 1)) / 2 ** nd if nd else 1.0
    s = {"protocol": "forge-memory-eval-v1", "n_pairs": len(pairs),
         "paired_table": {"memory_only": b, "no_memory_only": c, "both": sum(1 for m, n in pairs if m and n),
                          "neither": sum(1 for m, n in pairs if not m and not n)},
         "mcnemar_one_sided_p": round(p, 6),
         "conclusion": ("memory increased verified redesigns on these creatures (pre-declared test, p < 0.05)" if p < 0.05
                        else "no evidence of a benefit from engineering memory (pre-declared test)"),
         "memory_verified": {"k": sum(m for m, _ in pairs), "n": len(pairs), "wilson95": wilson(sum(m for m, _ in pairs), len(pairs))},
         "no_memory_verified": {"k": sum(n for _, n in pairs), "n": len(pairs), "wilson95": wilson(sum(n for _, n in pairs), len(pairs))},
         "cost": {k: round(v, 4) for k, v in cost.items()}, "excluded": excluded, "per_pair": per}
    (RESULTS / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted run (completed pairs skipped, interrupted pairs excluded)")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--forge-dir", default=str(ROOT / "artifacts" / "forge"))
    ap.add_argument("--records", default=str(ROOT / "artifacts" / "forge" / "investigations"))
    a = ap.parse_args()
    if a.register:
        register()
    elif a.run or a.resume:
        run(a.base, Path(a.forge_dir), resume=a.resume)
    elif a.analyze:
        print(json.dumps({k: v for k, v in analyze(Path(a.records)).items() if k != "per_pair"}, indent=1))


if __name__ == "__main__":
    main()
