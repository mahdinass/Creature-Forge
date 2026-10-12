#!/usr/bin/env python
"""Nebius Token Factory readiness check. Never prints the key. Does NOT call the API unless --live."""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1")  # verify against current docs


def main() -> int:
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        print("BLOCKED: NEBIUS_API_KEY is not set. No API call made. See docs/NEBIUS_SETUP.md.")
        return 2
    print(f"NEBIUS_API_KEY present (length {len(key)}); base URL {BASE}")
    if "--live" not in sys.argv:
        print("Dry run. Re-run with --live to list models (read-only GET /models).")
        return 0
    req = urllib.request.Request(f"{BASE}/models", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ids = sorted(m["id"] for m in json.load(r).get("data", []))
    nemo = [i for i in ids if "nemotron" in i.lower()]
    print(f"{len(ids)} models listed; Nemotron candidates: {nemo or 'none'}")
    return 0 if nemo else 1


if __name__ == "__main__":
    raise SystemExit(main())
