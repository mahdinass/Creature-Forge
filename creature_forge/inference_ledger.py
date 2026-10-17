"""Persistent, cross-process inference ledger with hard caps (contracts section 5.4).

One append-only JSON-lines file shared by every process that spends model credit (Studio server, calibration script, tests).
Line format, shared with the calibration script:
    {ts, request_id, model, prompt_tokens, completion_tokens, cost_usd, purpose, investigation_id}
Lines written here add `reservation_id` and `status`. A request is first RESERVED (a `{"kind": "reserve", ...}` line carrying the worst-case
cost) and then SETTLED with the real usage; both happen under an exclusive file lock together with the cap check, so concurrent processes
cannot jointly overshoot. A reservation that is never settled (crash) keeps counting at its worst case.

Caps (default; raised 2026-10-17 by the owner from 1,500 / USD 15): 8,000 requests (2026-10-17 evening, for the held-out run) and USD 30.00 in total; per investigation 4 requests and 80,000 tokens. `reserve` raises
`BudgetExceeded` BEFORE any network call. An unknown model price refuses (fail closed). Unparseable lines are skipped and counted in
`status()["skipped_lines"]`; they never grant headroom to anyone but they are not guessed at either.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .nebius import BudgetExceeded

ENV_VAR = "CF_INFERENCE_LEDGER"
# USD per token (prompt, completion). Source: Nebius Token Factory `GET /v1/models`, fetched 2026-10-14. Prices change; re-verify before relying on them.
PRICES_DATE = "2026-10-14"
PRICES_SOURCE = "GET /v1/models"
PRICES: dict[str, tuple[float, float]] = {
    "nvidia/nemotron-3-super-120b-a12b": (3e-7, 9e-7),
    "nvidia/Nemotron-3-Ultra-550b-a55b": (1e-6, 3e-6),
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (6e-8, 2.4e-7),
    "nvidia/Nemotron-3_5-Lightning": (6e-8, 2.4e-7),
}


class UnknownPrice(BudgetExceeded):
    """No verified price for the model: refuse rather than guess."""


class LedgerLockTimeout(BudgetExceeded):
    """The ledger lock could not be taken: fail closed (no network call)."""


@dataclass(frozen=True)
class Caps:
    max_requests: int = 8000
    max_usd: float = 30.0
    inv_max_requests: int = 4
    inv_max_tokens: int = 80_000


@dataclass(frozen=True)
class Reservation:
    id: str
    model: str
    est_prompt_tokens: int
    max_tokens: int
    investigation_id: str
    purpose: str
    worst_case_usd: float


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@contextmanager
def _flock(lock_path: Path, timeout_s: float):
    """Exclusive cross-process lock on `lock_path` (fcntl.flock on POSIX, msvcrt.locking on Windows). The OS releases it if the holder dies,
    so there are no stale locks to clean up."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "a+b")
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LedgerLockTimeout(f"could not lock the inference ledger within {timeout_s:g}s") from None
                time.sleep(0.02)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()


class InferenceLedger:
    """`path`: explicit ledger file, else env CF_INFERENCE_LEDGER, else `default_path` (e.g. <data_root>/inference_ledger.jsonl)."""

    def __init__(self, path: str | Path | None = None, *, default_path: str | Path | None = None,
                 prices: dict[str, tuple[float, float]] | None = None, caps: Caps | None = None, lock_timeout_s: float = 10.0):
        chosen = path or os.environ.get(ENV_VAR) or default_path
        if not chosen:
            raise ValueError(f"no ledger path: pass path/default_path or set {ENV_VAR}")
        self.path = Path(chosen)
        self.prices = dict(PRICES if prices is None else prices)
        self.caps = caps or Caps()
        self.lock_timeout_s = lock_timeout_s
        self._tlock = threading.Lock()

    # ---------------------------------------------------------------- internals
    @contextmanager
    def _locked(self):
        with self._tlock, _flock(self.path.with_name(self.path.name + ".lock"), self.lock_timeout_s):
            yield

    def _read(self) -> tuple[list[dict], int]:
        rows, skipped = [], 0
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                if isinstance(d, dict):
                    rows.append(d)
                else:
                    skipped += 1
        return rows, skipped

    def _append(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lead = ""
        if self.path.exists() and self.path.stat().st_size:
            with open(self.path, "rb") as f:
                f.seek(-1, os.SEEK_END)
                lead = "" if f.read(1) == b"\n" else "\n"  # never glue onto a partial line
        with open(self.path, "ab") as f:
            f.write((lead + json.dumps(row, separators=(",", ":")) + "\n").encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _num(x) -> float:
        return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0

    def _tally(self, rows: list[dict], investigation_id: str | None = None) -> dict:
        """Requests, USD and tokens (settled usage, or worst case for unsettled reservations). Calibration lines (no reservation) count as one
        request each."""
        settled = {r["reservation_id"] for r in rows if r.get("kind") != "reserve" and r.get("reservation_id")}
        unsent = {r["reservation_id"] for r in rows if r.get("kind") != "reserve" and r.get("status") == "not_sent" and r.get("reservation_id")}
        req, usd, tok = 0, 0.0, 0
        for r in rows:
            if investigation_id is not None and r.get("investigation_id") != investigation_id:
                continue
            if r.get("reservation_id") in unsent:
                continue  # released before any network call: neither a request nor a cost
            if r.get("kind") == "reserve":
                req += 1
                if r.get("reservation_id") not in settled:
                    usd += self._num(r.get("worst_case_usd"))
                    tok += int(self._num(r.get("est_prompt_tokens")) + self._num(r.get("max_tokens")))
            else:
                if not r.get("reservation_id"):
                    req += 1
                usd += self._num(r.get("cost_usd"))
                tok += int(self._num(r.get("prompt_tokens")) + self._num(r.get("completion_tokens")))
        return {"requests": req, "usd": usd, "tokens": tok}

    def price_for(self, model: str) -> tuple[float, float]:
        p = self.prices.get(model)
        if (not isinstance(p, (tuple, list)) or len(p) != 2 or not all(isinstance(x, (int, float)) and x >= 0 for x in p)):
            raise UnknownPrice(f"no verified price for model {model!r}; refusing to spend")
        return float(p[0]), float(p[1])

    # ---------------------------------------------------------------- public API
    def reserve(self, est_prompt_tokens: int, max_tokens: int, model: str, *, investigation_id: str,
                purpose: str = "investigation") -> Reservation:
        """Check every cap against the worst case of this request and, if it fits, persist the reservation. Raises BudgetExceeded (or its
        subclasses) otherwise. Call before the network request; pair with `settle`."""
        if not investigation_id or not isinstance(investigation_id, str):
            raise ValueError("investigation_id is required")
        if est_prompt_tokens < 0 or max_tokens < 1:
            raise ValueError("est_prompt_tokens must be >= 0 and max_tokens >= 1")
        pp, pc = self.price_for(model)
        worst = est_prompt_tokens * pp + max_tokens * pc
        c = self.caps
        with self._locked():
            rows, _ = self._read()
            tot = self._tally(rows)
            inv = self._tally(rows, investigation_id)
            if tot["requests"] + 1 > c.max_requests:
                raise BudgetExceeded(f"ledger request cap {c.max_requests} reached ({tot['requests']} used)")
            if tot["usd"] + worst > c.max_usd + 1e-12:
                raise BudgetExceeded(f"ledger spend cap ${c.max_usd:.2f} would be exceeded (${tot['usd']:.4f} used + ${worst:.4f} worst case)")
            if inv["requests"] + 1 > c.inv_max_requests:
                raise BudgetExceeded(f"investigation {investigation_id}: request cap {c.inv_max_requests} reached")
            need = est_prompt_tokens + max_tokens
            if inv["tokens"] + need > c.inv_max_tokens:
                raise BudgetExceeded(f"investigation {investigation_id}: token cap {c.inv_max_tokens} would be exceeded "
                                     f"({inv['tokens']} used + {need} worst case)")
            rid = uuid.uuid4().hex
            self._append({"kind": "reserve", "ts": _now(), "reservation_id": rid, "model": model, "est_prompt_tokens": int(est_prompt_tokens),
                          "max_tokens": int(max_tokens), "worst_case_usd": worst, "purpose": purpose, "investigation_id": investigation_id})
        return Reservation(rid, model, int(est_prompt_tokens), int(max_tokens), investigation_id, purpose, worst)

    def settle(self, res: Reservation, *, request_id: str | None, prompt_tokens: int | None, completion_tokens: int | None,
               status: str = "ok", usage_estimated: bool = False) -> dict:
        """Record the real usage of a reserved request. With `usage_estimated` (the request was sent but its usage is unknown) the line is
        settled at the reservation's worst case (prompt estimate + max_tokens at the model prices) and flagged; never an undercount.
        Returns the ledger line, including `cost_usd`."""
        pp, pc = self.price_for(res.model)
        if usage_estimated:
            pt, ct = int(res.est_prompt_tokens), int(res.max_tokens)
        else:
            pt, ct = int(prompt_tokens or 0), int(completion_tokens or 0)
        row = {"ts": _now(), "request_id": request_id, "model": res.model, "prompt_tokens": pt, "completion_tokens": ct,
               "cost_usd": pt * pp + ct * pc, "purpose": res.purpose, "investigation_id": res.investigation_id,
               "reservation_id": res.id, "status": status}
        if usage_estimated:
            row["usage_estimated"] = True
        with self._locked():
            self._append(row)
        return row

    def release(self, res: Reservation) -> dict:
        """The request was never sent (refused locally before the transport): give the reservation back."""
        row = {"ts": _now(), "request_id": None, "model": res.model, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0,
               "purpose": res.purpose, "investigation_id": res.investigation_id, "reservation_id": res.id, "status": "not_sent"}
        with self._locked():
            self._append(row)
        return row

    def status(self) -> dict:
        with self._locked():
            rows, skipped = self._read()
        t = self._tally(rows)
        c = self.caps
        return {"requests": t["requests"], "usd": round(t["usd"], 6), "tokens": t["tokens"], "skipped_lines": skipped,
                "caps": {"requests": c.max_requests, "usd": c.max_usd, "investigation_requests": c.inv_max_requests,
                         "investigation_tokens": c.inv_max_tokens},
                "prices": {"date": PRICES_DATE, "source": PRICES_SOURCE}}

    def investigation_status(self, investigation_id: str) -> dict:
        with self._locked():
            rows, _ = self._read()
        return self._tally(rows, investigation_id)
