"""Shared configuration loading. A repo-root `.env` fills in variables that are NOT already set.

Real environment variables always win (`override=False`). Values are never printed or logged here.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"


def load_env(path: Path | str | None = None) -> bool:
    """Load `.env` (default: repository root) without overriding existing variables.

    Returns True if a file was found and parsed, False if it does not exist.
    """
    p = Path(path) if path is not None else DEFAULT_ENV_FILE
    if not p.is_file():
        return False
    load_dotenv(p, override=False)
    return True


def nebius_base_url(default: str) -> str:
    """NEBIUS_BASE_URL from the (already loaded) environment; empty/unset falls back to `default`."""
    return (os.environ.get("NEBIUS_BASE_URL") or default).strip().rstrip("/")


def nebius_api_key() -> str | None:
    """NEBIUS_API_KEY from the (already loaded) environment; empty counts as unset."""
    return os.environ.get("NEBIUS_API_KEY") or None
