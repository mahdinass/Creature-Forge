"""Real inference spend from the ledger: settled calls that returned a request id (billed), versus worst-case settlements of
failed calls (e.g. HTTP 401, not billed), since a given time. The ledger stays the conservative cap guard. This script
answers "what did we actually spend in this stage" (owner's Stage-2 envelope is real spend).

Usage: python scripts/inference_real_spend.py [--ledger ~/dev/ledger/inference_ledger.jsonl] [--since 2026-10-19T00:00:00]
"""
from __future__ import annotations

import argparse
import json
import os


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=os.path.expanduser("~/dev/ledger/inference_ledger.jsonl"))
    ap.add_argument("--since", default="2026-10-19T00:00:00")
    a = ap.parse_args()
    billed = failed = 0.0
    nb = nf = 0
    for line in open(a.ledger, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") == "reserve" or str(r.get("ts", "")) < a.since:
            continue
        if r.get("request_id"):
            billed += r.get("cost_usd") or 0.0
            nb += 1
        else:
            failed += r.get("cost_usd") or 0.0
            nf += 1
    print(json.dumps({"since": a.since, "billed_calls": nb, "billed_usd": round(billed, 4), "failed_calls": nf,
                      "failed_worst_case_usd_not_billed": round(failed, 4)}))


if __name__ == "__main__":
    main()
