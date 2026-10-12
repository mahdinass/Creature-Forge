#!/usr/bin/env python
"""End-to-end demo check for Creature Forge Studio. Exit 0 = pass.

Starts the real server on a free port, then verifies: built frontend is served, the Phase 0 experiment comes
from MuJoCo (fall at the right time, same seed/push for both arms), exported poses are physically consistent,
a parameter edit yields a different MuJoCo result, invalid input is rejected, and (if Edge/Chrome is found and
--browser is given) the real React app renders the fall banner from those frames in a headless browser.
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creature_forge.studio.app import create_app  # noqa: E402

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe", "chromium", "google-chrome"]


def check(cond: bool, msg: str) -> None:
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        raise SystemExit(1)


def get(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.status, r.read()


def post(url: str, body: dict):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(200):
        try:
            get(base + "/api/schema")
            break
        except OSError:
            time.sleep(0.25)
    else:
        check(False, "server started")

    st, html = get(base + "/")
    asset = re.search(rb'/assets/[^"]+\.js', html)
    check(st == 200 and asset is not None, "built frontend index served (run `npm --prefix studio run build` if this fails)")
    check(get(base + asset.group(0).decode())[0] == 200, "frontend JS bundle served")

    d = json.loads(get(base + "/api/experiments/phase0")[1])
    b, c = d["baseline"], d["candidate"]
    check(b["push"] == c["push"] and b["seed"] == c["seed"], "both arms use the same seed and disturbance")
    fall = [e for e in b["events"] if e["kind"] == "fall"]
    check(len(fall) == 1 and 1.0 < fall[0]["time"] < 3.0, f"baseline falls after the push (t={fall[0]['time']:.2f} s)")
    check(not c["metrics"]["fell"], "candidate (16 cm foot) does not fall under the same push")
    check(d["matched_seed_summary"]["baseline"]["fall_rate"] == 1.0
          and d["matched_seed_summary"]["candidate"]["fall_rate"] == 0.0, "matched-seed fall rates 100% -> 0%")

    torso = next(i for i, g in enumerate(b["scene"]["geoms"]) if g["part"] == "torso")
    y_end = b["frames"]["pos"][-1][torso][1]
    y_start = b["frames"]["pos"][0][torso][1]
    check(y_start > 0.7 and y_end < 0.2, f"exported torso pose really drops ({y_start:.2f} m -> {y_end:.2f} m)")
    check(len(b["time"]) == len(b["frames"]["pos"]) == len(b["series"]["torso_height"]), "frames align with telemetry")

    st, e = post(base + "/api/simulate", {"body": {"foot_length": 0.30}, "push": {"time": 1.0, "force": 25.0}})
    check(st == 200 and not e["metrics"]["fell"] and e["body"]["foot_length"] == 0.30, "edited morphology re-simulates in MuJoCo")
    st, e = post(base + "/api/simulate", {"body": {"foot_length": 9.0}})
    check(st == 422, "out-of-bounds parameter rejected (not clipped)")

    if "--browser" in sys.argv:
        exe = next((p for p in BROWSERS if shutil.which(p) or Path(p).exists()), None)
        check(exe is not None, "headless browser found")
        with tempfile.TemporaryDirectory() as prof:
            out = subprocess.run(
                [exe, "--headless=new", "--disable-gpu-sandbox", "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
                 f"--user-data-dir={prof}", "--virtual-time-budget=8000", "--dump-dom", f"{base}/?t=2.6"],
                capture_output=True, text=True, timeout=120).stdout
        m = re.search(r"FALL detected at sim t = ([0-9.]+) s", out)
        check(m is not None and abs(float(m.group(1)) - fall[0]["time"]) < 0.01,
              "real browser renders the fall banner at the MuJoCo-detected time")
        check("<canvas" in out and "foot 0.080 m" in out, "WebGL canvas and baseline creature mounted")
    print("STUDIO E2E CHECK PASSED")
    server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
