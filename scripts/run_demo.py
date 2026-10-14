"""Investigation demo runner (observed failure -> Nemotron proposal -> bounded edit -> MuJoCo verification).

    python scripts/run_demo.py mock                       # scripted stand-in (labelled SCRIPTED_MOCK); no network
    python scripts/run_demo.py live --confirm-live        # ONE real Nebius call (draws on the shared 41-request / 300k-token caps)
    python scripts/run_demo.py record <run_id> [--name N] # promote a real LIVE local run to a committed, hash-verified RECORDED_LIVE record
    python scripts/run_demo.py list

Runs are written to artifacts/demo_runs/ (git-ignored). Live calls are appended to the shared usage file so the combined caps stay honest.
Mock runs can never be recorded or counted as live.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import demo, r1, r2, r3v2  # noqa: E402
from creature_forge.nebius import Limits  # noqa: E402
from creature_forge.optimize import Executor  # noqa: E402


def summarize(rec: dict) -> None:
    mr = rec["model_reply"]
    print(f"run {rec['run_id']}  kind={rec['provenance']['kind']}  model_status={mr['status']}  elapsed={rec['elapsed_s']} s")
    if mr["call"]:
        print("  call:", {k: mr["call"].get(k) for k in ("model", "finish_reason", "usage", "latency_s", "request_id", "reasoning_present", "content_is_null")})
    if mr["reason"]:
        print("  reason:", mr["reason"])
    for iv in rec["interventions"]:
        k = f"slot{iv['slot']}"
        v, r = rec["verification"]["results"][k], rec["verification"]["results"][k + "_random"]
        t0 = rec["verification"]["results"]["theta0"]
        print(f"  slot {iv['slot']}: edits {[(e['parameter'], e['delta_u']) for e in iv['proposal']['edits']]} | theta0 {t0['walking_count']}/32 -> edit {v['walking_count']}/32 "
              f"({v['verdict']['kind']}, prediction_met={v['verdict'].get('prediction_met')}) | matched random {r['walking_count']}/32 ({r['verdict']['kind']})")
    if not rec["interventions"]:
        print("  no valid proposal; nothing was simulated or substituted")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["mock", "live", "record", "list"])
    ap.add_argument("run_id", nargs="?")
    ap.add_argument("--confirm-live", action="store_true")
    ap.add_argument("--name")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.cmd == "list":
        print(json.dumps(demo.list_runs(), indent=1))
        return
    if a.cmd == "record":
        rec = demo.load_run(a.run_id)
        p = demo.promote_to_recording(rec, a.name)
        print("recorded", p)
        return
    if r1.free_memory_gb() < 0.8:
        raise SystemExit("not enough free memory for the 4-worker verification pool")
    client = None
    if a.cmd == "live":
        if not a.confirm_live:
            raise SystemExit("refused: pass --confirm-live (spends Nebius inference budget)")
        client = r3v2.make_client()
        client.limits = Limits(max_requests=client.limits.max_requests, max_total_tokens=client.limits.max_total_tokens,
                               max_tokens_per_request=demo.SETTING["max_tokens"], timeout_s=client.limits.timeout_s)
    with Executor(a.workers, timeout_s=900, fn=r2.r2_job) as ex:
        rec = demo.run_investigation(a.cmd, ex, client)
    if a.cmd == "live":
        demo.record_live_request(rec)
    p = demo.save_local(rec)
    summarize(rec)
    print("saved", p)
    if a.cmd == "live":
        u = r3v2.prior_usage()
        print(f"combined usage now: {u['requests']} requests / {u['tokens']} tokens (caps {r3v2.TOTAL_REQUESTS_CAP} / {r3v2.TOTAL_TOKENS_CAP})")


if __name__ == "__main__":
    main()
