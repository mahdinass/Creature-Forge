"""Request guard for the local Studio: Host allow-list (DNS rebinding), Origin check (cross-site writes), body size cap.

Studio is a localhost tool. A hostile web page could (a) rebind its own DNS name to 127.0.0.1 and talk to the API with a
foreign Host header, or (b) fire a cross-site POST at 127.0.0.1. So:

* the `Host` header must be `127.0.0.1`, `localhost` or `[::1]` (any port), plus the comma-separated names in env
  `CF_ALLOWED_HOSTS` (or `create_app(allowed_hosts=...)`); `testserver` (Starlette's TestClient) is allowed only while env
  `CF_ALLOW_TESTSERVER=1`. Both env vars are read per request, so a test module sets the variable once at its top and no app
  wiring changes;
* a POST/PUT/PATCH/DELETE under `/api/` that carries an `Origin` header must be same-origin: the Origin's host:port equals the
  `Host` header (already allow-listed). No Origin (curl, scripts, tests) is allowed;
* request bodies over `CF_MAX_BODY_BYTES` (default 4 MB) are refused with 413.
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlsplit

MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
DEFAULT_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})
MAX_BODY_BYTES = 4 * 1024 * 1024


def _hostname(netloc: str) -> str:
    """`host[:port]` -> lower-case host (IPv6 literals keep their brackets)."""
    netloc = (netloc or "").strip().lower()
    if netloc.startswith("["):
        end = netloc.find("]")
        return netloc[: end + 1] if end != -1 else netloc
    return netloc.rsplit(":", 1)[0] if ":" in netloc else netloc


def allowed_hostnames(extra=()) -> frozenset:
    names = set(DEFAULT_HOSTS) | {h.strip().lower() for h in extra if h and h.strip()}
    names |= {h.strip().lower() for h in os.environ.get("CF_ALLOWED_HOSTS", "").split(",") if h.strip()}
    if os.environ.get("CF_ALLOW_TESTSERVER") == "1":
        names.add("testserver")
    return frozenset(names)


def max_body_bytes() -> int:
    try:
        return int(os.environ.get("CF_MAX_BODY_BYTES") or MAX_BODY_BYTES)
    except ValueError:
        return MAX_BODY_BYTES


class _TooLarge(Exception):
    pass


class RequestGuard:
    """Pure ASGI middleware (no body buffering for normal requests)."""

    def __init__(self, app, allowed_hosts=()):
        self.app, self.extra = app, tuple(allowed_hosts)

    async def _reply(self, send, status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        host = headers.get("host", "")
        if _hostname(host) not in allowed_hostnames(self.extra):
            return await self._reply(send, 403, "Host header not allowed (Studio only answers on localhost)")
        method, path = scope["method"], scope.get("path", "")
        if method in MUTATING and path.startswith("/api/") and "origin" in headers:
            origin = urlsplit(headers["origin"])
            if origin.scheme not in ("http", "https") or origin.netloc.lower() != host.strip().lower():
                return await self._reply(send, 403, "cross-site request refused (Origin does not match this server)")
        limit = max_body_bytes()
        declared = headers.get("content-length")
        if declared is not None:
            try:
                too_big = int(declared) > limit
            except ValueError:
                too_big = True
            if too_big:
                return await self._reply(send, 413, f"request body too large (limit {limit} bytes)")
        seen = 0
        started = overflow = False

        async def counting_receive():
            nonlocal seen, overflow
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > limit:
                    overflow = True
                    raise _TooLarge()
            return msg

        async def tracking_send(msg):
            # The framework may turn the aborted read into its own 400 response; once the limit was crossed, that response is replaced.
            nonlocal started
            if overflow:
                if not started:
                    started = True
                    await self._reply(send, 413, f"request body too large (limit {limit} bytes)")
                return
            if msg["type"] == "http.response.start":
                started = True
            await send(msg)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                started = True
                await self._reply(send, 413, f"request body too large (limit {limit} bytes)")
