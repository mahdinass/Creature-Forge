"""Write the immutable R3 v2 pre-registration (experiments/phase2a_r3/protocol_v2.json). Refuses to overwrite.

Commit it BEFORE any new model request or R3 v2 rollout; v1 files are hashed into it and must not change.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r2, r3v2  # noqa: E402


def main() -> None:
    if r3v2.PROTOCOL_V2.exists():
        raise SystemExit(f"{r3v2.PROTOCOL_V2} already exists; protocols are immutable")
    r3v2.PROTOCOL_V2.write_text(json.dumps(r3v2.build_protocol_v2(), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {r3v2.PROTOCOL_V2}; sha256(LF) {r2.sha256_lf(r3v2.PROTOCOL_V2)}")


if __name__ == "__main__":
    main()
