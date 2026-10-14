"""Write the immutable R2 pre-registration (experiments/phase2a_r2/protocol.json).

    .venv\\Scripts\\python scripts\\preregister_r2.py

Refuses to overwrite an existing protocol. Commit the file BEFORE any R2 rollout; every stage refuses to run unless it is
committed unmodified and still matches the code that defines it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r2  # noqa: E402


def main() -> None:
    if r2.PROTOCOL.exists():
        raise SystemExit(f"{r2.PROTOCOL} already exists; protocols are immutable (use a new protocol id to re-register)")
    r2.PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
    r2.PROTOCOL.write_text(json.dumps(r2.build_protocol(), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {r2.PROTOCOL}; sha256(LF) {r2.sha256_lf(r2.PROTOCOL)}")


if __name__ == "__main__":
    main()
