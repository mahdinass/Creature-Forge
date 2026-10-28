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


def validate_base_url(url: str) -> str:
    """The API key is sent to this URL, so it must be `https://`. The only exception is the explicit scripted placeholder
    host (`*.invalid`, never resolvable), used by the offline scripted mode. Raises ValueError otherwise."""
    from urllib.parse import urlsplit
    u = (url or "").strip().rstrip("/")
    parts = urlsplit(u)
    host = (parts.hostname or "")
    if parts.scheme == "https" and host:
        return u
    if parts.scheme == "http" and host.endswith(".invalid"):
        return u
    raise ValueError("the Nebius base URL must start with https:// (got a non-https or malformed URL)")


def nebius_base_url(default: str) -> str:
    """NEBIUS_BASE_URL from the (already loaded) environment; empty/unset falls back to `default`. Must be https."""
    return validate_base_url(os.environ.get("NEBIUS_BASE_URL") or default)


def nebius_api_key() -> str | None:
    """NEBIUS_API_KEY from the (already loaded) environment, stripped of surrounding whitespace (a CRLF .env sourced by a shell
    leaves a trailing CR, incident 2026-10-17); empty counts as unset."""
    return (os.environ.get("NEBIUS_API_KEY") or "").strip() or None
