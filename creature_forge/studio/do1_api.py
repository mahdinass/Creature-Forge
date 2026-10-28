"""`/api/do1/*` router: the verified DO-1 L4 recovery replays (read-only, static, no simulation).

Serves only the committed export in experiments/do1/demo (scripts/do1_demo_export.py; 96/96 rows and every frame verified
against the audited DO1-L4-r0 record on the recorded Linux environment). Two pinned SHA-256 values anchor it:
  * the export's SHA256SUMS. Every served file is checked against it before it is returned.
  * the audited record experiments/do1/l4_r0/do1_l4_r0.jsonl. The verifier's verdicts, reasons and confirmation checks
    are read from it, so the page shows recorded evidence rather than restated numbers.
A file that does not match is refused (503). Design, duration and seed are validated, and the file name comes from the
export's own index, never from the request. Nothing is simulated and no model is called.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Response

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "experiments" / "do1" / "demo"
RECORD = ROOT / "experiments" / "do1" / "l4_r0" / "do1_l4_r0.jsonl"
DEMO_SUMS_SHA256 = "73078ae5075c7a0897ef2cbefae0a373817d1816330e8a7ebdcb7585e1782ec4"
RECORD_SHA256 = "00a8db20b9b3ab186b935f2062a9a78d411a4d2a512e289e8aa1e4c39a5e263b"
SEED_RE = re.compile(r"\d{1,10}")
FILE_RE = re.compile(r"payloads/(faulty|frozen|do1)_(10|20)s_\d{1,10}\.json")
VERDICT_KEYS = ("status", "wins", "losses", "ties", "non_tied", "median_diff", "p_one_sided", "pass_rate", "min_effect")


class IntegrityError(RuntimeError):
    """A served file does not match its pinned hash."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verification(arm: dict) -> dict:
    """The verifier's recorded outcome for one arm (full_recovery_v1), without the per-seed rows already in the index."""
    f = arm["verification"]["full"]
    v = f["validation"]["verdict"]
    conf = {k: f["confirmation"][k] for k in ("run", "reason", "passed", "checks", "duration") if k in f["confirmation"]}
    return {"rule": f["rule"], "status": f["status"], "reasons": f["reasons"], "aggregate": f["validation"]["aggregate"],
            "walking_frac": f["validation"]["walking_frac"], "verdict": {k: v[k] for k in VERDICT_KEYS if k in v},
            "verdict_reasons": v.get("reasons", []), "confirmation": conf}


def create_do1_router(demo_dir: Path = DEMO_DIR, record: Path = RECORD, *, sums_sha256: str = DEMO_SUMS_SHA256,
                      record_sha256: str = RECORD_SHA256) -> APIRouter:
    """Router for `/api/do1`. Nothing is read until first use; integrity failures are reported, never served."""
    router = APIRouter(prefix="/api/do1")
    lock = threading.Lock()
    state: dict = {}

    def sums() -> dict[str, str]:
        with lock:
            if "sums" not in state:
                raw = (demo_dir / "SHA256SUMS").read_bytes()
                if _sha(raw) != sums_sha256:
                    raise IntegrityError("the export's SHA256SUMS is not the verified one")
                state["sums"] = {rel: h for h, rel in (ln.split(" *", 1) for ln in raw.decode("utf-8").splitlines() if ln)}
            return state["sums"]

    def read_verified(rel: str) -> bytes:
        want = sums().get(rel)
        if want is None:
            raise IntegrityError(f"{rel} is not listed in the verified SHA256SUMS")
        data = (demo_dir / rel).read_bytes()
        if _sha(data) != want:
            raise IntegrityError(f"{rel} does not match the verified SHA256SUMS")
        return data

    @lru_cache(maxsize=1)
    def index() -> dict:
        idx = json.loads(read_verified("index.json"))
        raw = record.read_bytes()
        if _sha(raw) != record_sha256:
            raise IntegrityError("the DO1-L4-r0 record is not the audited one")
        arms = {r["harness"]["do1"]["arm"]: r for r in map(json.loads, raw.decode("utf-8").splitlines())}
        from ..recovery import PASS_FRAC, RECOVERY_RULE
        idx["verification"] = {"frozen": _verification(arms["frozen"]), "do1": _verification(arms["do1"])}
        idx["criteria"] = {"rule": RECOVERY_RULE, "pass_frac": PASS_FRAC}
        idx["provenance"]["arms_nemotron"] = [arms[a]["nemotron"] for a in ("frozen", "do1")]
        idx["provenance"]["arms_provenance_recorded"] = [arms[a]["provenance"] for a in ("frozen", "do1")]
        return idx

    @lru_cache(maxsize=12)
    def payload_bytes(rel: str) -> bytes:
        return read_verified(rel)

    def guarded(fn):
        try:
            return fn()
        except IntegrityError as exc:
            raise HTTPException(503, f"DO-1 replay data failed its integrity check: {exc}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, "The DO-1 replay export is not present in this checkout") from exc

    @router.get("/index")
    def get_index():
        idx = guarded(index)
        return {k: v for k, v in idx.items() if k != "files"} | {"available": sorted(idx["files"])}

    @router.get("/payload/{design}/{duration}/{seed}")
    def get_payload(design: Literal["faulty", "frozen", "do1"], duration: Literal["10", "20"], seed: str):
        if not SEED_RE.fullmatch(seed):
            raise HTTPException(422, "seed must be a non-negative integer")
        idx = guarded(index)
        rel = idx["files"].get(f"{design}/{duration}/{int(seed)}")
        if rel is None or not FILE_RE.fullmatch(rel):
            raise HTTPException(404, f"No verified replay for {design}, {duration} s, seed {seed}")
        return Response(guarded(lambda: payload_bytes(rel)), media_type="application/json")

    return router
