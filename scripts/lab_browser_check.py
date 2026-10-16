#!/usr/bin/env python
"""Real-browser check of the Investigation Lab. Exit 0 = pass.

Starts the real Studio server on a free port against ONLY the bundled demo records (an empty local records
directory, like a fresh clone), then runs studio/e2e/investigation-flow.mjs (playwright-core + system Chrome/Edge):
select experiment -> inspect evidence -> load the real MuJoCo simulation -> compare outcomes, plus the invalid
-response and error paths. Needs `npm --prefix studio install && npm --prefix studio run build`.
Makes no model call. Set SHOT_DIR to keep screenshots.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creature_forge.studio.app import create_app  # noqa: E402


def main() -> int:
    # Browser flows run SCRIPTED investigations only; smoke scale keeps them inside CI time (refused for live mode, recorded).
    os.environ.setdefault("CF_INVESTIGATION_SCALE", "smoke")
    if not (ROOT / "studio" / "dist" / "index.html").exists():
        print("FAIL studio/dist missing: run `npm --prefix studio run build`")
        return 1
    node = shutil.which("node")
    if not node or not (ROOT / "studio" / "node_modules" / "playwright-core").exists():
        print("FAIL node or studio/node_modules/playwright-core missing: run `npm --prefix studio install`")
        return 1
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with tempfile.TemporaryDirectory() as empty_local:
        server = uvicorn.Server(uvicorn.Config(create_app(investigations_dir=Path(empty_local) / "none",
                                                          forge_dir=Path(empty_local) / "forge"),
                                               host="127.0.0.1", port=port, log_level="warning"))
        threading.Thread(target=server.run, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        for _ in range(200):
            try:
                urllib.request.urlopen(base + "/api/schema", timeout=5)
                break
            except OSError:
                time.sleep(0.25)
        else:
            print("FAIL server did not start")
            return 1
        rc = 0
        for flow in ("e2e/tabs-smoke.mjs", "e2e/investigation-flow.mjs", "e2e/locomotion-flow.mjs", "e2e/demo-flow.mjs", "e2e/overview-flow.mjs", "e2e/sketch-flow.mjs", "e2e/freehand-flow.mjs", "e2e/forge-flow.mjs", "e2e/forge-recovery-flow.mjs"):
            rc |= subprocess.run([node, flow], cwd=ROOT / "studio", env={**os.environ, "BASE_URL": base},
                                 timeout=1500).returncode
        server.should_exit = True
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
