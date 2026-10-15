#!/usr/bin/env python
"""Run ONE Forge investigation (or the bounded loop) on a stored creature version and a stored challenge run.

    python scripts/forge_investigate.py --cid c-1a2b3c4d --n 1 --run-id r-0a1b2c3d --mode scripted
    python scripts/forge_investigate.py --cid ... --n 1 --run-id ... --mode live --confirm-live [--profile deep] [--loop]

`scripted` uses the fixture transport (provenance SCRIPTED_MOCK, no network, free). `live` makes real Nebius calls and needs
CREATURE_FORGE_ENABLE_LIVE=1, an API key, ledger headroom AND --confirm-live. The record is written to
<forge-dir>/investigations/<id>.json; nothing is ever accepted automatically. Run it on the VM (it uses the process pool).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import investigation as inv  # noqa: E402
from creature_forge.creatures import CreatureStore  # noqa: E402
from creature_forge.inference_ledger import InferenceLedger  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forge-dir", default=str(ROOT / "artifacts" / "forge"))
    ap.add_argument("--cid", required=True)
    ap.add_argument("--n", type=int, required=True, help="creature version number")
    ap.add_argument("--run-id", required=True, help="stored challenge run id (r-xxxxxxxx)")
    ap.add_argument("--mode", choices=inv.MODES, default="scripted")
    ap.add_argument("--profile", choices=inv.PROFILES, default="default")
    ap.add_argument("--confirm-live", action="store_true", help="required for --mode live (real model calls, real spend)")
    ap.add_argument("--loop", action="store_true", help="bounded loop (<= 3 rounds); never accepts anything")
    args = ap.parse_args(argv)
    if args.mode == "live" and not args.confirm_live:
        print("refusing: --mode live needs --confirm-live (real model calls)", file=sys.stderr)
        return 2
    forge_dir = Path(args.forge_dir)
    store = CreatureStore(forge_dir)
    ledger = InferenceLedger(default_path=forge_dir / "inference_ledger.jsonl")

    def emit(type_, data):
        print(json.dumps({"event": type_, **{k: v for k, v in data.items() if k in ("phase", "status", "arm_id", "request_id", "error", "provenance")}}))

    from creature_forge.forge_pool import get_pool  # lazy: the pool is only created when a run needs it
    kw = dict(mode=args.mode, forge_dir=forge_dir, ledger=ledger, emit=emit, profile=args.profile, pool=get_pool())
    try:
        if args.loop:
            out = inv.run_loop(store, args.cid, args.n, args.run_id, **kw)
            print(json.dumps(out, indent=1, default=str))
            return 0
        rec = inv.run_investigation(store, args.cid, args.n, args.run_id, **kw)
    except inv.LiveRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(inv.summarize(rec), indent=1))
    print(f"record: {forge_dir / 'investigations' / (rec['id'] + '.json')}")
    return 0 if rec["status"] in ("done", "model_failed", "no_valid_proposals") else 1


if __name__ == "__main__":
    raise SystemExit(main())
