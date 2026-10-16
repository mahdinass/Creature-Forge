#!/usr/bin/env python
"""Launch a bounded investigation loop on an existing creature version + challenge run through the running Studio API and print
every round honestly (model calls, proposals, verdicts, stop reason). The loop never accepts a design.

    python scripts/forge_run_loop.py --cid c-13d00809 --n 1 --run-id r-82936044 --mode live
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.forge_acceptance import call, wait_job  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--cid", required=True)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--mode", default="scripted", choices=["scripted", "live"])
    ap.add_argument("--profile", default="default")
    ap.add_argument("--probes", action="store_true", help="diagnostic probes before proposing (active experimentation)")
    ap.add_argument("--single", action="store_true", help="one investigation instead of the bounded loop")
    a = ap.parse_args()
    _, before = call(a.base, "GET", f"/api/forge/investigations?cid={a.cid}")
    seen_before = {r["id"] for r in before}
    st, out = call(a.base, "POST", f"/api/forge/creatures/{a.cid}/versions/{a.n}/investigations",
                   {"run_id": a.run_id, "mode": a.mode, "profile": a.profile, "loop": not a.single, "probes": a.probes})
    if st != 200:
        raise SystemExit(f"refused ({st}): {out.get('detail')}")
    job = wait_job(a.base, out["job_id"], limit_s=1800)
    print("job", job["status"], job.get("error"))
    _, rows = call(a.base, "GET", f"/api/forge/investigations?cid={a.cid}")
    loop = (job.get("result") or {}) if isinstance(job.get("result"), dict) else {}
    for row in sorted(rows, key=lambda r: r.get("created", "")):
        _, rec = call(a.base, "GET", f"/api/forge/investigations/{row['id']}")
        if rec["id"] in seen_before or (not a.single and not rec.get("creature", {}).get("loop_id")):
            continue
        print(f"\nround {rec['creature'].get('round')}  {rec['id']}  {rec['status']}  {rec['provenance']}  "
              f"history entries {len((rec.get('evidence') or {}).get('history') or [])}")
        for c in rec.get("model_calls") or []:
            u = c.get("usage") or {}
            print(f"  model {c.get('model')} request {c.get('request_id')} {c.get('latency_s', 0):.1f} s tokens "
                  f"{u.get('prompt_tokens')}+{u.get('completion_tokens')} finish {c.get('finish_reason')}")
        pr = rec.get("probes") or {}
        for e in pr.get("expectations") or []:
            print(f"  probe {e.get('probe_id'):18s} for {e.get('hypothesis')}: expected {e.get('expect')}, observed {e.get('observed')} "
                  f"-> {'CONFIRMED' if e.get('confirmed') else ('refuted' if e.get('confirmed') is False else 'n/a')}  "
                  f"(median delta {((pr.get('results') or {}).get(e.get('probe_id')) or {}).get('median_delta')})")
        for h in (rec.get("validation") or {}).get("hypotheses", []):
            print(f"  {h.get('id')}: {str(h.get('mechanism'))[:160]}")
        for p in (rec.get("validation") or {}).get("proposals", []):
            print(f"  {p.get('id')} [{p.get('status')}] {json.dumps(p.get('edits'))[:150]}")
        for arm_id, v in (rec.get("verdicts") or {}).items():
            v = v or {}
            print(f"  verdict {arm_id:12s} {v.get('status')}  median diff {v.get('median_diff')}  "
                  f"W/L/T {v.get('wins')}/{v.get('losses')}/{v.get('ties')}")
    if loop:
        print("\nloop:", json.dumps({k: loop.get(k) for k in ("stop_reason", "budget", "auto_accepted")}))


if __name__ == "__main__":
    main()
