"""Build or inspect the engineering-memory bank (creature_forge.memory).

  python scripts/forge_memory.py --build experiments/forge_loop/scoreboard/results/records experiments/forge_loop/dev_live_records --out lessons.jsonl
  python scripts/forge_memory.py --show --out lessons.jsonl

Only LIVE investigations with status `done` yield lessons; measured facts only. The default bank path is artifacts/forge/memory/lessons.jsonl
(the studio's forge_dir).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creature_forge.memory import MemoryBank  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", nargs="+", metavar="RECORDS_DIR", help="directories of archived investigation records (i-*.json)")
    ap.add_argument("--out", help="bank file (default artifacts/forge/memory/lessons.jsonl)")
    ap.add_argument("--show", action="store_true", help="print a summary of the bank")
    a = ap.parse_args(argv)
    path = Path(a.out) if a.out else ROOT / "artifacts" / "forge" / "memory" / "lessons.jsonl"
    bank = MemoryBank(path)
    if a.build:
        added = sum(bank.build_from(d) for d in a.build)
        print(f"added {added} lesson(s); bank {path} now has {len(bank)}")
    if a.show or not a.build:
        for s in bank.summaries():
            print(json.dumps(s, sort_keys=True))
        print(f"{len(bank)} lesson(s) in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
