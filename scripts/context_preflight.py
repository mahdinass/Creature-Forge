#!/usr/bin/env python3
"""Read-only Creature Forge session preflight.

Run at agent start and before making setup assumptions. Never creates an environment,
installs dependencies, reads secrets, or contacts an external service.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENVS = (".venv", "venv", "env", "backend/.venv", "engine/.venv")
MANIFESTS = (
    "pyproject.toml", "uv.lock", "requirements.txt", "requirements-dev.txt",
    "Pipfile", "poetry.lock", "backend/pyproject.toml",
    "package.json", "frontend/package.json", "pnpm-lock.yaml",
    "docs/PROJECT_SPEC.md", "docs/PROJECT_STATE.md",
)

def exists(rel: str) -> str:
    p = ROOT / rel
    return "directory" if p.is_dir() else "file" if p.is_file() else "missing"

def git_summary() -> str:
    try:
        branch = subprocess.run(
            ["git", "-C", str(ROOT), "branch", "--show-current"],
            capture_output=True, text=True, timeout=3, check=False
        )
        changes = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--short"],
            capture_output=True, text=True, timeout=3, check=False
        )
        return "branch=" + (branch.stdout.strip() or "unknown") + (
            "; worktree=clean" if not changes.stdout.strip() else
            "; worktree has uncommitted changes (inspect git status)"
        )
    except (OSError, subprocess.TimeoutExpired):
        return "Git unavailable; inspect manually"

def main() -> int:
    print("[Creature Forge session preflight — read-only]")
    print("repo:", ROOT)
    print("git:", git_summary())
    print("python executable:", sys.executable)
    print("python version:", sys.version.split()[0])
    # Avoid printing VIRTUAL_ENV contents if it might contain user-specific paths.
    print("VIRTUAL_ENV active:", bool(os.environ.get("VIRTUAL_ENV")))
    found = False
    for rel in VENVS:
        p = ROOT / rel
        if p.is_dir():
            found = True
            interpreters = [p / "Scripts" / "python.exe", p / "bin" / "python"]
            usable = any(x.is_file() for x in interpreters)
            print("existing environment:", rel, "; Python executable:", "present" if usable else "unverified")
    if not found:
        print("known venv folders: none found (do not infer no alternative environment exists)")
    print("project files:", ", ".join(f"{name}={exists(name)}" for name in MANIFESTS))
    print("Next: read docs/PROJECT_STATE.md, inspect dependencies, then check relevant")
    print("docs/memory notes and Basic Memory MCP if connected. Never recreate a")
    print("venv or service from assumption. Verify with exact local commands first.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
