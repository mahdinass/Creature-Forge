"""Write the immutable R3 pre-registration (experiments/phase2a_r3/protocol.json).

    .venv\\Scripts\\python scripts\\preregister_r3.py

Refuses to overwrite an existing protocol. Commit the file BEFORE any R3 rollout or model request.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r2, r3  # noqa: E402


def main() -> None:
    if r3.PROTOCOL.exists():
        raise SystemExit(f"{r3.PROTOCOL} already exists; protocols are immutable (use a new protocol id to re-register)")
    r3.PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
    r3.PROTOCOL.write_text(json.dumps(r3.build_protocol(), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {r3.PROTOCOL}; sha256(LF) {r2.sha256_lf(r3.PROTOCOL)}")


if __name__ == "__main__":
    main()
