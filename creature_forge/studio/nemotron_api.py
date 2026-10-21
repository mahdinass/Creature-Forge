"""`/api/nemotron/*` router: the recorded Nemotron investigation of hdb-v1-gen-0137:one_side_weakness:4 (W2; read-only).

Serves only committed, hash-pinned files in experiments/w2 (scripts/w2_case_build.py; nothing is simulated and no model is
called):
  * case.json            the attribution case: the shared start, the fork at turn 0, and the A3 / A1e / A4 episodes;
  * cross_instance.json  the 36 paired Stage 2 single-mechanism instances (A1e vs A3 vs A4) and the ledger check;
  * studies.json         one row per study of Nemotron's role, each with a source file and a verbatim quote.
experiments/w2/SHA256SUMS lists them; its own SHA-256 is pinned here, and every served file must match it (else 503).

Damaged-plant replays: the viewer payloads of the hidden (damaged) plant are produced only by
scripts/w2_damaged_plant_export.py in the recorded Linux environment, after owner approval. Until that export exists and its
SHA256SUMS is pinned below (`REPLAY_SUMS_SHA256`), `/api/nemotron/case` reports the replays as unavailable and the page shows
no animation of the damaged robot. The generic `/api/scientist` replays show designs on the NOMINAL robot only.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException

ROOT = Path(__file__).resolve().parents[2]
W2_DIR = ROOT / "experiments" / "w2"
SUMS_SHA256 = "1b4538ff12185598847cb37b69a0f59888bab13d2c8d5f4211bcf85176b6ac6c"
REPLAY_DIR = W2_DIR / "gen0137_one_side_weakness" / "plant_replays"
REPLAY_SUMS_SHA256: str | None = None      # set when an approved, fidelity-gated export is committed
FILES = {"case": "gen0137_one_side_weakness/case.json", "cross": "gen0137_one_side_weakness/cross_instance.json",
         "studies": "studies.json"}


class IntegrityError(RuntimeError):
    """A served file does not match its pinned hash."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_nemotron_router(w2_dir: Path = W2_DIR, *, sums_sha256: str = SUMS_SHA256,
                           replay_sums_sha256: str | None = REPLAY_SUMS_SHA256) -> APIRouter:
    """Router for `/api/nemotron`. Nothing is read until first use; integrity failures are reported, never served."""
    router = APIRouter(prefix="/api/nemotron")
    lock = threading.Lock()
    state: dict = {}

    def sums() -> dict[str, str]:
        with lock:
            if "sums" not in state:
                raw = (w2_dir / "SHA256SUMS").read_bytes()
                if _sha(raw) != sums_sha256:
                    raise IntegrityError("experiments/w2/SHA256SUMS is not the pinned one")
                state["sums"] = {rel: h for h, rel in (ln.split(" *", 1) for ln in raw.decode("utf-8").splitlines() if ln)}
            return state["sums"]

    def read_json(rel: str) -> dict:
        want = sums().get(rel)
        if want is None:
            raise IntegrityError(f"{rel} is not listed in the pinned SHA256SUMS")
        data = (w2_dir / rel).read_bytes()
        if _sha(data) != want:
            raise IntegrityError(f"{rel} does not match the pinned SHA256SUMS")
        return json.loads(data)

    def replay_status() -> dict:
        if replay_sums_sha256 is None:
            return {"available": False, "reason": "The damaged-plant replays have not been exported. They need a fidelity-gated "
                                                  "export in the recorded Linux environment (scripts/w2_damaged_plant_export.py), "
                                                  "which awaits owner approval. Nothing on this page animates the damaged robot."}
        return {"available": False, "reason": "replay serving is not implemented in this version"}

    @router.get("/case")
    def case():
        try:
            out = {k: read_json(rel) for k, rel in FILES.items()}
        except IntegrityError as exc:
            raise HTTPException(503, f"Nemotron case data failed its integrity check: {exc}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, "The W2 case files are not present in this checkout") from exc
        cross = out["cross"]
        return {"case": out["case"], "cross": {k: cross[k] for k in ("population", "aggregates", "rows", "ledger", "sources")},
                "studies": out["studies"], "replays": replay_status(), "playback": "RECORDED_LIVE"}

    return router
