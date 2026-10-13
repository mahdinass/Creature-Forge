"""Write experiments/phase2a/protocol.json (seed roles, budgets, gates, success criteria, selection rule).

Run once, commit the file, and only then run `run_phase2a.py` and `eval_phase2a_heldout.py`.
Refuses to overwrite a protocol that is already tracked by git.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge.phase2a import PROTOCOL, build_protocol, protocol_sha256  # noqa: E402


def main() -> None:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", PROTOCOL.relative_to(ROOT).as_posix()],
                             cwd=ROOT, capture_output=True).returncode == 0
    if tracked:
        sys.exit(f"{PROTOCOL} is already committed; a new registration needs a new protocol id and a new file")
    PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
    PROTOCOL.write_text(json.dumps(build_protocol(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {PROTOCOL}\nsha256 {protocol_sha256()}\nnow: git add + commit this file BEFORE running experiments")


if __name__ == "__main__":
    main()
