"""`/api/nemotron/*` router: the recorded Nemotron investigation of hdb-v1-gen-0137:one_side_weakness:4 (W2; read-only).

Serves only committed, hash-pinned files in experiments/w2 (scripts/w2_case_build.py; nothing is simulated and no model is
called):
  * case.json            the attribution case: the shared start, the fork at turn 0, and the A3 / A1e / A4 episodes;
  * cross_instance.json  the 36 paired Stage 2 single-mechanism instances (A1e vs A3 vs A4) and the ledger check;
  * studies.json         one row per study of Nemotron's role, each with a source file and a verbatim quote.
experiments/w2/SHA256SUMS lists them; its own SHA-256 is pinned here, and every served file must match it (else 503).

Damaged-plant replays (`/api/nemotron/replay/{name}/{seed}`): viewer payloads of the hidden (damaged) plant, produced only
by scripts/w2_damaged_plant_export.py in the recorded Linux environment after owner approval. They are served only when the
export's SHA256SUMS equals `REPLAY_SUMS_SHA256`, and every file must match it; otherwise `/api/nemotron/case` reports them
as unavailable and the page animates nothing of the damaged robot. The generic `/api/scientist` replays show designs on the NOMINAL robot only.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

ROOT = Path(__file__).resolve().parents[2]
W2_DIR = ROOT / "experiments" / "w2"
SUMS_SHA256 = "1b4538ff12185598847cb37b69a0f59888bab13d2c8d5f4211bcf85176b6ac6c"
REPLAY_DIR = W2_DIR / "gen0137_one_side_weakness" / "plant_replays"
REPLAY_SUMS_SHA256: str | None = "7c05c8de8dff2e7935078e2d833dcf0d6583e0b9c4e29352b28f4b95d7146512"   # W2 export, main VM, 2026-10-21
REPLAY_NAMES = ("observe", "x1_nem", "x1_eng", "nominal", "a3_submitted", "a1e_submitted")
REPLAY_FILE_RE = re.compile(r"payloads/(observe|x1_nem|x1_eng|nominal|a3_submitted|a1e_submitted)_\d{1,10}\.json")
SEED_RE = re.compile(r"\d{1,10}")
FILES = {"case": "gen0137_one_side_weakness/case.json", "cross": "gen0137_one_side_weakness/cross_instance.json",
         "studies": "studies.json"}


class IntegrityError(RuntimeError):
    """A served file does not match its pinned hash."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_nemotron_router(w2_dir: Path = W2_DIR, *, sums_sha256: str = SUMS_SHA256, replay_dir: Path | None = None,
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

    rdir = replay_dir if replay_dir is not None else w2_dir / "gen0137_one_side_weakness" / "plant_replays"

    def replay_sums() -> dict[str, str]:
        with lock:
            if "rsums" not in state:
                raw = (rdir / "SHA256SUMS").read_bytes()
                if replay_sums_sha256 is None or _sha(raw) != replay_sums_sha256:
                    raise IntegrityError("the damaged-plant export's SHA256SUMS is not the pinned one")
                state["rsums"] = {rel: h for h, rel in (ln.split(" *", 1) for ln in raw.decode("utf-8").splitlines() if ln)}
            return state["rsums"]

    def read_replay(rel: str) -> bytes:
        want = replay_sums().get(rel)
        if want is None:
            raise IntegrityError(f"{rel} is not listed in the export's SHA256SUMS")
        data = (rdir / rel).read_bytes()
        if _sha(data) != want:
            raise IntegrityError(f"{rel} does not match the export's SHA256SUMS")
        return data

    @lru_cache(maxsize=1)
    def replay_index() -> dict:
        return json.loads(read_replay("index.json"))

    def replay_status() -> dict:
        if replay_sums_sha256 is None:
            return {"available": False, "reason": "The damaged-plant replays have not been exported. They need a fidelity-gated "
                                                  "export in the recorded Linux environment (scripts/w2_damaged_plant_export.py), "
                                                  "which awaits owner approval. Nothing on this page animates the damaged robot."}
        try:
            idx = replay_index()
        except (IntegrityError, FileNotFoundError) as exc:
            return {"available": False, "reason": f"The damaged-plant export failed its integrity check: {exc}"}
        return {"available": True, "reason": None, **{k: v for k, v in idx.items() if k != "files"}, "available_keys": sorted(idx["files"])}

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

    @router.get("/replay/{name}/{seed}")
    def replay(name: str, seed: str):
        if name not in REPLAY_NAMES or not SEED_RE.fullmatch(seed):
            raise HTTPException(422, "unknown replay or malformed seed")
        try:
            rel = replay_index()["files"].get(f"{name}/{int(seed)}")
            if rel is None or not REPLAY_FILE_RE.fullmatch(rel):
                raise HTTPException(404, f"No verified replay for {name}, seed {seed}")
            return Response(read_replay(rel), media_type="application/json")
        except IntegrityError as exc:
            raise HTTPException(503, f"Damaged-plant replay failed its integrity check: {exc}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, "The damaged-plant export is not present in this checkout") from exc

    return router
