"""Minimal, secure Nebius Token Factory chat client (OpenAI-compatible).

Design rules: key only from the environment and never stored in reprs/logs; explicit request, token
and time limits; NO retries of any kind; the transport is injectable so tests never touch the network.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

from .config import load_env, nebius_api_key, nebius_base_url, validate_base_url

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
REASONING_EFFORTS = ("none", "low", "medium", "high")  # per Nebius docs; model support must be verified
# Request-body keys that `extra_body` may never set: the client owns them (model, messages, max_tokens, temperature) or they
# have a dedicated, validated argument (reasoning_effort, response_format).
RESERVED_BODY_KEYS = frozenset({"model", "messages", "max_tokens", "temperature", "reasoning_effort", "response_format"})


class NebiusError(RuntimeError):
    """Transport, HTTP or protocol failure. Never contains the API key."""


class BudgetExceeded(NebiusError):
    """A request/token limit would be exceeded; raised BEFORE any network call."""


@dataclass(frozen=True)
class Limits:
    max_requests: int = 3
    # Prompt + completion. Enforced BEFORE the call against a conservative worst case (see
    # estimate_prompt_tokens + max_tokens; the prompt part is a heuristic) and again AFTER it against the API-reported usage.
    max_total_tokens: int = 20_000
    max_tokens_per_request: int = 4096
    timeout_s: float = 60.0


@dataclass(frozen=True)
class ChatResult:
    content: str | None  # None when the model returned no message content (e.g. reasoning-only reply)
    finish_reason: str | None
    model: str | None
    usage: dict
    latency_s: float
    request_id: str | None
    reasoning_present: bool
    http_status: int

    def record(self) -> dict:
        """Redacted, loggable metadata (no prompt, no credentials)."""
        return {"model": self.model, "finish_reason": self.finish_reason, "usage": self.usage,
                "latency_s": round(self.latency_s, 3), "request_id": self.request_id,
                "reasoning_present": self.reasoning_present, "http_status": self.http_status,
                "content_is_null": self.content is None}




def estimate_prompt_tokens(messages: list[dict]) -> int:
    """Heuristic prompt-token estimate: ~3 UTF-8 bytes per token of the serialized messages plus chat-template
    slack (same ratio the pre-registered live runner uses). It is deliberately pessimistic for English/JSON
    but is NOT a guaranteed upper bound: unusual text can tokenize denser and the server's template
    overhead is invisible to us. Actual API-reported usage is still added after every call."""
    return len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) // 3 + 64


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would re-send the Authorization header to another host: never follow one (it surfaces as an HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


_BEARER = re.compile(r"(Bearer\s+)[^\s'\"\\]+")


def redact_secret(text: str, secret: str | None) -> str:
    """Remove every occurrence of the API key from provider-supplied text: the key as given, stripped of surrounding whitespace,
    in its escaped repr form (an exception message shows a trailing CR as the two characters backslash-r), and ANY
    "Bearer <token>" (incident 2026-10-17: a key with a trailing CR from a CRLF .env produced an "Invalid header value" error
    whose text the exact-match redaction missed)."""
    text = str(text)
    if secret and len(secret.strip()) >= 4:
        for form in sorted({secret, secret.strip(), repr(secret)[1:-1], repr(secret.strip())[1:-1]}, key=len, reverse=True):
            if len(form) >= 4:
                text = text.replace(form, "[redacted]")
    return _BEARER.sub(r"\1[redacted]", text)


def contains_secret(text: str, secret: str | None) -> bool:
    """True if `text` (e.g. a JSON-serialised record) holds the key in any form redact_secret removes, its JSON-escaped form, or an
    un-redacted "Bearer <token>". Used by record guards, which must fail closed."""
    import json as _json
    text = str(text)
    if secret and len(secret.strip()) >= 4:
        forms = {secret, secret.strip(), repr(secret)[1:-1], repr(secret.strip())[1:-1], _json.dumps(secret)[1:-1],
                 _json.dumps(secret.strip())[1:-1]}
        if any(len(f) >= 4 and f in text for f in forms):
            return True
    return any(m.group(0)[len(m.group(1)):] != "[redacted]" for m in _BEARER.finditer(text))


def _key_from_headers(headers: dict) -> str | None:
    auth = (headers or {}).get("Authorization") or ""
    return auth[7:] if auth.startswith("Bearer ") else (auth or None)


def _urllib_transport(url: str, headers: dict, body: dict, timeout: float):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    key = _key_from_headers(headers)
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), json.load(r)
    except urllib.error.HTTPError as e:
        # provider error text may echo a credential: redact the key before it is stored or raised
        raise NebiusError(redact_secret(f"HTTP {e.code}: {e.read(500).decode('utf-8', 'replace')}", key)) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise NebiusError(redact_secret(f"{type(e).__name__}: {e}", key)) from None


@dataclass
class NebiusClient:
    model: str = DEFAULT_MODEL
    base_url: str | None = None  # None -> NEBIUS_BASE_URL (env or .env) -> DEFAULT_BASE_URL
    limits: Limits = field(default_factory=Limits)
    # transport(url, headers, body, timeout) -> (status, response_headers, parsed_json)
    transport: Callable = _urllib_transport
    api_key: str | None = field(default=None, repr=False)
    requests_made: int = 0
    tokens_used: int = 0
    calls: list = field(default_factory=list)  # redacted records of every attempted request

    def __post_init__(self):
        if self.api_key is None or self.base_url is None:
            load_env()  # repo-root .env; real environment variables take precedence
        if self.api_key is None:
            self.api_key = nebius_api_key()
        self.base_url = validate_base_url(self.base_url) if self.base_url else nebius_base_url(DEFAULT_BASE_URL)

    def chat(self, messages: list[dict], *, max_tokens: int = 1024, temperature: float = 0.0,
             reasoning_effort: str | None = None, response_format: dict | None = None,
             extra_body: dict | None = None) -> ChatResult:
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
            raise ValueError(f"reasoning_effort must be one of {REASONING_EFFORTS}")
        if extra_body is not None:
            # Additive provider-specific fields (e.g. {"chat_template_kwargs": {"enable_thinking": False}}). Validated BEFORE any
            # budget is touched; it can never override what the client itself controls.
            if not isinstance(extra_body, dict):
                raise ValueError("extra_body must be a dict")
            clash = sorted(set(extra_body) & RESERVED_BODY_KEYS)
            if clash:
                raise ValueError(f"extra_body may not override {clash}")
        if not (1 <= max_tokens <= self.limits.max_tokens_per_request):
            raise BudgetExceeded(f"max_tokens={max_tokens} outside 1..{self.limits.max_tokens_per_request}")
        if self.requests_made >= self.limits.max_requests:
            raise BudgetExceeded(f"request limit {self.limits.max_requests} reached")
        # Reserve for this request: estimated prompt tokens (heuristic) + max_tokens completion tokens (hard cap).
        # The actual API-reported usage is added afterwards, so a later call is blocked if the estimate
        # was too low. Hard limit on completion; prompt side is a conservative estimate (documented).
        reserve = estimate_prompt_tokens(messages) + max_tokens
        if self.tokens_used + reserve > self.limits.max_total_tokens:
            raise BudgetExceeded(f"token budget {self.limits.max_total_tokens} would be exceeded "
                                 f"(used {self.tokens_used} + reserve {reserve})")
        if not self.api_key:
            raise NebiusError("NEBIUS_API_KEY is not set")

        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens,
                "temperature": temperature}
        if reasoning_effort is not None:
            body["reasoning_effort"] = reasoning_effort
        if response_format is not None:
            body["response_format"] = response_format
        if extra_body:
            body.update(extra_body)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        self.requests_made += 1  # counted before the call: a failed/timed-out request still costs budget
        t0 = time.perf_counter()
        try:
            status, resp_headers, raw = self.transport(f"{self.base_url}/chat/completions", headers, body,
                                                      self.limits.timeout_s)
        except NebiusError as e:
            if self.api_key and self.api_key in str(e):  # custom transports too: never store or re-raise the key
                e = NebiusError(redact_secret(str(e), self.api_key))
            self.calls.append({"ok": False, "error": str(e)[:300], "latency_s": round(time.perf_counter() - t0, 3),
                               "requested_model": self.model, "reasoning_effort": reasoning_effort})
            raise e from None
        latency = time.perf_counter() - t0
        try:
            choice = raw["choices"][0]
            msg = choice.get("message") or {}
            usage = raw.get("usage") or {}
            result = ChatResult(
                content=msg.get("content"), finish_reason=choice.get("finish_reason"),
                model=raw.get("model"), usage={**{k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
                                               **({"reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")}
                                                  if (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") is not None else {})},
                latency_s=latency,
                request_id=(resp_headers or {}).get("x-request-id") or (resp_headers or {}).get("request-id"),
                reasoning_present=any(k.startswith("reasoning") and msg.get(k) for k in msg),
                http_status=status)
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            self.calls.append({"ok": False, "error": f"malformed response: {type(e).__name__}",
                               "latency_s": round(latency, 3), "requested_model": self.model})
            raise NebiusError("malformed chat completion response") from None
        self.tokens_used += int(result.usage.get("total_tokens") or 0)
        self.calls.append({"ok": True, "requested_model": self.model, "reasoning_effort": reasoning_effort,
                           "max_tokens": max_tokens, **result.record()})
        return result
