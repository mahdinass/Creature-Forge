#!/usr/bin/env python
"""ONE reasoning_effort=none test request to Nebius Token Factory. No retries. Never prints/logs the key.

Writes a redacted record to artifacts/nebius/connectivity_<utc>.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from creature_forge.config import load_env, nebius_api_key, nebius_base_url
from creature_forge.nebius import DEFAULT_BASE_URL

load_env()
BASE = nebius_base_url(DEFAULT_BASE_URL)
MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
MAX_TOKENS = 128


def main() -> int:
    key = nebius_api_key()
    if not key:
        print("BLOCKED: NEBIUS_API_KEY not set")
        return 2
    body = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "temperature": 0, "reasoning_effort": "none",
        "messages": [{"role": "user", "content": "Reply with exactly one word: ready"}],
    }
    req = urllib.request.Request(
        f"{BASE}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    record: dict = {"utc": datetime.now(timezone.utc).isoformat(), "requested_model": MODEL,
                    "max_tokens": MAX_TOKENS, "reasoning_effort": "none", "base_url": BASE}
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = json.load(r)
            record["http_status"] = r.status
            record["request_id"] = r.headers.get("x-request-id") or r.headers.get("request-id")
        record["succeeded"] = True
        choice = (raw.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        record.update(actual_model=raw.get("model"), usage=raw.get("usage"),
                      finish_reason=choice.get("finish_reason"),
                      content=msg.get("content"),
                      has_reasoning_field=any(k.startswith("reasoning") and msg.get(k) for k in msg))
    except urllib.error.HTTPError as e:
        record.update(succeeded=False, http_status=e.code, error=e.read(500).decode("utf-8", "replace"))
    except Exception as e:  # network/timeout
        record.update(succeeded=False, error=f"{type(e).__name__}: {e}")
    record["latency_s"] = round(time.perf_counter() - t0, 3)
    out = Path("artifacts/nebius")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"reasoning_none_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    print(f"saved {path}")
    return 0 if record["succeeded"] else 1


if __name__ == "__main__":
    sys.exit(main())
