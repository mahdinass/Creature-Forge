#!/usr/bin/env python
"""Launch Creature Forge Studio (FastAPI + built frontend) at http://127.0.0.1:8000

Prereqs: `uv pip install --python .venv\\Scripts\\python.exe -e ".[studio]"` and `npm --prefix studio install && npm --prefix studio run build`.
For frontend development use `npm --prefix studio run dev` (http://127.0.0.1:5173, proxies /api to this server).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    if not (ROOT / "studio" / "dist" / "index.html").exists():
        print("WARNING: studio/dist not built; only the API will be served. Run: npm --prefix studio run build")
    uvicorn.run("creature_forge.studio.app:app", host="127.0.0.1", port=int(os.environ.get("CREATURE_FORGE_PORT", "8000")), log_level="info")
