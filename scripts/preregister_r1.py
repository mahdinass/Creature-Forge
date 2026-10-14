"""Write the immutable R1 pre-registration (experiments/phase2a_r1/protocol.json).

    .venv\\Scripts\\python scripts\\preregister_r1.py

Refuses to overwrite an existing protocol. Commit the file BEFORE any optimisation; every later stage refuses to run
unless it is committed unmodified and still matches the code that defines it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r1  # noqa: E402


def main() -> None:
    if r1.PROTOCOL.exists():
        raise SystemExit(f"{r1.PROTOCOL} already exists; protocols are immutable (use a new protocol id to re-register)")
    r1.PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
    r1.PROTOCOL.write_text(json.dumps(r1.build_protocol(), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {r1.PROTOCOL}; sha256 {r1.sha256_file(r1.PROTOCOL)}")


if __name__ == "__main__":
    main()
