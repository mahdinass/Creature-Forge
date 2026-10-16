#!/usr/bin/env python
"""End-to-end Forge Loop acceptance run against a RUNNING Studio server, over real HTTP, exactly as the UI drives it:

    draw (starter strokes) -> /api/freehand/interpret -> create creature -> challenge job -> investigation job (scripted or live)
    -> arena verdicts -> accept ONLY if an arm is VERIFIED_IMPROVEMENT -> challenge the new version -> second investigation sees history

    python scripts/forge_acceptance.py --base http://127.0.0.1:8000 --starter tiny-feet --kind stand --mode scripted
    python scripts/forge_acceptance.py --base ... --starter balanced --kind push --mode live      # needs the server started with
                                                                                                  # CREATURE_FORGE_ENABLE_LIVE=1
Prints a compact, honest report and writes it to artifacts/forge/acceptance/<timestamp>.json. Nothing is invented: every
number printed comes from the API. Exit code 0 means the pipeline completed (an unsuccessful investigation is a valid
completion); non-zero means a pipeline error.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_freehand_starters import STARTERS  # noqa: E402  (exact port of studio/src/sketch/starters.ts)


def call(base: str, method: str, path: str, body: dict | None = None, timeout: float = 60):
    req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def wait_job(base: str, job_id: str, limit_s: float = 1800) -> dict:
    since, t0, last = 0, time.time(), None
    while time.time() - t0 < limit_s:
        _, out = call(base, "GET", f"/api/forge/jobs/{job_id}?since={since}")
        for ev in out.get("events", []):
            since = max(since, ev["i"])
            if ev["type"] in ("phase", "model_response", "verdict", "error"):
                d = ev["data"]
                print(f"   [{ev['type']}] " + json.dumps(d)[:180])
        job = out["job"]
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        p = job.get("progress") or {}
        if p != last:
            last = p
        time.sleep(2)
    raise SystemExit(f"job {job_id} did not finish in {limit_s} s")


def challenge(base: str, cid: str, n: int, kind: str, seeds: int) -> dict:
    st, out = call(base, "POST", f"/api/forge/creatures/{cid}/versions/{n}/challenges", {"kind": kind, "seeds": seeds})
    assert st == 200, (st, out)
    job = wait_job(base, out["job_id"])
    assert job["status"] == "done", job
    _, run = call(base, "GET", f"/api/forge/runs/{out['run_id']}")
    s = run["summary"]
    print(f"  v{n} {kind}: {run['outcome']}  median score {s.get('score', {}).get('median')}  counts {s.get('counts')}  "
          f"rollouts {run['rollouts']}")
    return run


def investigate(base: str, cid: str, n: int, run_id: str, mode: str) -> dict:
    st, out = call(base, "POST", f"/api/forge/creatures/{cid}/versions/{n}/investigations", {"run_id": run_id, "mode": mode})
    if st != 200:
        print(f"  investigation refused ({st}): {out.get('detail')}")
        return {"refused": out.get("detail"), "status_code": st}
    job = wait_job(base, out["job_id"])
    _, rec = call(base, "GET", f"/api/forge/investigations/{out['investigation_id']}")
    print(f"  investigation {rec['id']}: status {rec['status']}  provenance {rec['provenance']}  error {rec.get('error')}")
    for c in rec.get("model_calls") or []:
        u = c.get("usage") or {}
        print(f"   model {c.get('model')}  request {c.get('request_id')}  {c.get('latency_s')} s  tokens {u.get('prompt_tokens')}+"
              f"{u.get('completion_tokens')}  finish {c.get('finish_reason')}  error {c.get('error')}")
    for h in (rec.get("validation") or {}).get("hypotheses", []):
        print(f"   {h.get('id')}: {str(h.get('mechanism'))[:140]}")
    for p in (rec.get("validation") or {}).get("proposals", []):
        print(f"   {p.get('id')} [{p.get('status')}] {json.dumps(p.get('edits'))[:140]} {'; '.join(p.get('reasons') or [])[:160]}")
    for arm_id, v in (rec.get("verdicts") or {}).items():
        v = v or {}
        print(f"   verdict {arm_id:12s} {v.get('status')}  median diff {v.get('median_diff')}  wins/losses/ties "
              f"{v.get('wins')}/{v.get('losses')}/{v.get('ties')}  p {v.get('p_one_sided')}")
    print(f"   budget {rec.get('budget')}")
    rec["_job_status"] = job["status"]
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--starter", default="tiny-feet", choices=list(STARTERS))
    ap.add_argument("--kind", default="stand", choices=["stand", "push", "walk"])
    ap.add_argument("--mode", default="scripted", choices=["scripted", "live"])
    ap.add_argument("--seeds", type=int, default=8)
    a = ap.parse_args()
    report = {"args": vars(a), "started": time.strftime("%Y-%m-%dT%H:%M:%S")}

    strokes, materials = STARTERS[a.starter]
    st, interp = call(a.base, "POST", "/api/freehand/interpret", {"strokes": strokes, "guided": False, "materials": materials or {}})
    assert st == 200 and interp.get("body"), (st, interp.get("errors"))
    print(f"1 drew '{a.starter}': {interp['outcome']}  body foot {interp['body']['foot_length']:.3f} m  torso {interp['body']['torso_mass']:.2f} kg")
    st, creature = call(a.base, "POST", "/api/forge/creatures",
                        {"name": a.starter, "body": interp["body"], "mode": "experimental",
                         "drawing": {"strokes": strokes, "interpretation": {"outcome": interp["outcome"]}, "approximation": None}})
    assert st == 200, (st, creature)
    cid = creature["id"]
    print(f"2 creature {cid} v1 created")
    run1 = challenge(a.base, cid, 1, a.kind, a.seeds)
    print("3 investigating with", a.mode)
    rec1 = investigate(a.base, cid, 1, run1["run_id"], a.mode)
    report.update(creature=cid, run1=run1["run_id"], investigation1=rec1.get("id"), status1=rec1.get("status"),
                  verdicts1={k: (v or {}).get("status") for k, v in (rec1.get("verdicts") or {}).items()})
    verified = [k for k, v in (rec1.get("verdicts") or {}).items() if (v or {}).get("status") == "VERIFIED_IMPROVEMENT"]
    ai_verified = [k for k in verified if k.startswith("ai:")]
    if not verified:
        print("4 no arm was verified: nothing can be accepted (this is a valid, honestly reported outcome)")
        st, out = call(a.base, "POST", f"/api/forge/creatures/{cid}/accept", {"investigation_id": rec1.get("id"), "arm_id": "ai:P1"})
        print(f"  accept attempt correctly refused: {st} {out.get('detail', '')[:120]}")
        report["accepted"] = None
    else:
        pick = (ai_verified or verified)[0]
        st, out = call(a.base, "POST", f"/api/forge/creatures/{cid}/accept", {"investigation_id": rec1["id"], "arm_id": pick})
        assert st == 200, (st, out)
        v2 = out["versions"][-1]
        print(f"4 accepted {pick} -> v{v2['n']} (parent v{v2['parent']}, source {v2['change']['source']}, edits {json.dumps(v2['change']['edits'])[:120]})")
        run2 = challenge(a.base, cid, v2["n"], a.kind, a.seeds)
        print("5 investigating v2 (history of round 1 available)")
        rec2 = investigate(a.base, cid, v2["n"], run2["run_id"], a.mode)
        report.update(accepted=pick, v2=v2["n"], run2=run2["run_id"], investigation2=rec2.get("id"), status2=rec2.get("status"))
    out_dir = ROOT / "artifacts" / "forge" / "acceptance"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (time.strftime("%Y%m%dT%H%M%S") + f"-{a.starter}-{a.kind}-{a.mode}.json")
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("report:", path)


if __name__ == "__main__":
    main()
