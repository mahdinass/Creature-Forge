#!/usr/bin/env python3
"""Claude Code PreToolUse guard: reject duplicate venv creation.

The agent still must inspect and verify environment usability. This protects one
easy-to-make repeated setup mistake; it does not prove MCP retrieval occurred.
No writes, network access or secrets. Exit code 2 blocks a matching tool call.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_DIRS = (".venv", "venv", "env", "backend/.venv", "engine/.venv")
# Only match a real command at start or after a shell control operator.
# Do not block harmless prose/grep commands containing the word 'venv'.
COMMAND = re.compile(
    r"(?:^|[;&|]\s*)"
    r"(?:(?:python(?:\d+(?:\.\d+)?)?|py(?:\s+-\d+(?:\.\d+)?)?)\s+-m\s+venv"
    r"|uv\s+venv|virtualenv)(?:\s|$)",
    flags=re.IGNORECASE,
)

def existing_envs() -> list[str]:
    return [name for name in VENV_DIRS if (ROOT / name).is_dir()]

def should_block(command: str) -> bool:
    return bool(COMMAND.search(command) and existing_envs())

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        # No tool payload: fail open, to avoid breaking all shell commands.
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command", "")
    if not isinstance(command, str):
        return 0
    if should_block(command):
        sys.stderr.write(
            "Creature Forge guard: existing virtual environment folder(s): "
            + ", ".join(existing_envs())
            + ". Inspect and reuse/repair the current environment rather than "
              "creating a second one. If a separate environment is truly required, "
              "document the decision and request explicit approval.\n"
        )
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
