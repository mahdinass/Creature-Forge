"""`/api/causal/*` router: recorded causal-engineer investigations (read-only, no model calls).

Serves the trimmed records written by `scripts/ce_export_records.py` (`experiments/causal_engineer/demo_records`): the index, one record,
and a fresh deterministic MuJoCo replay of the initial or the submitted design of a record. A replay uses the per-seed conditions of the
independent verification (`arena.VARIATION_PRESET`: 2x perturbation, push-time jitter, +-10 % friction; 10 s walk), built the same way
`recovery.run_walk_seeds` builds them. Record ids are validated against the index before any file is opened, so a request can never name
a path. The replayer is injectable (tests use a fake); the default imports MuJoCo code lazily inside the function.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Literal

from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger(__name__)

RECORDS_DIR = Path(__file__).resolve().parents[2] / "experiments" / "causal_engineer" / "demo_records"
ID_RE = re.compile(r"c-[0-9a-f]{12}")      # always used with fullmatch
REPLAY_SEEDS = (1, 2, 3, 4)                # offered by the UI; any seed in [0, 2**31) is accepted
MAX_SEED = 2 ** 31 - 1
REPLAY_DURATION_S = 10.0
MAX_CONCURRENT_REPLAYS = 2
REPLAY_CACHE_SIZE = 16


def default_replayer(body: dict, vector: list[float], seed: int) -> dict:
    """Replay payload (the viewer's RunPayload) of a body + 17-D walking vector on one seed under the verification variation preset."""
    from ..arena import VARIATION_PRESET, _body_with_friction, _condition
    from ..challenges import ChallengeSpec, default_spec, replay_payload
    base = ChallengeSpec.from_dict({**default_spec("walk", [seed]).to_dict(), "duration": REPLAY_DURATION_S})
    c = _condition(seed, base, VARIATION_PRESET)
    b, used = _body_with_friction(body, c["friction_factor"])
    spec = ChallengeSpec.from_dict({**base.to_dict(), "seeds": [seed], "perturb": c["perturb"], "push_time": c["push_time"]})
    controllers = {"stand": None, "walk": {"vector": [float(x) for x in vector], "provenance": {"kind": "custom"}}}
    payload = replay_payload(b, controllers, spec, seed)
    payload["condition"] = {"variation": dict(VARIATION_PRESET), "perturb": c["perturb"], "push_time": c["push_time"], "friction_used": used}
    return payload


def create_causal_router(records_dir: str | Path | None = None, replayer: Callable[[dict, list, int], dict] | None = None) -> APIRouter:
    """Router for `/api/causal`. Nothing is read or imported until first use."""
    root = Path(records_dir) if records_dir is not None else RECORDS_DIR
    run = replayer or default_replayer
    router = APIRouter(prefix="/api/causal")
    cache: OrderedDict = OrderedDict()
    lock = threading.Lock()
    slots = threading.Semaphore(MAX_CONCURRENT_REPLAYS)

    def index() -> dict:
        p = root / "index.json"
        if not p.is_file():
            return {"schema": "causal_record_v1", "records": []}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.exception("causal index unreadable")
            raise HTTPException(500, "the record index could not be read") from exc

    def load(rid: str) -> dict:
        if not ID_RE.fullmatch(rid) or rid not in {r.get("id") for r in index()["records"]}:
            raise HTTPException(404, f"No such causal record: {rid[:40]}")
        p = root / f"{rid}.json"
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HTTPException(404, f"No such causal record: {rid}") from None
        except (OSError, ValueError) as exc:
            log.exception("causal record %s unreadable", rid)
            raise HTTPException(500, "the record could not be read") from exc

    @router.get("/records")
    def records():
        return {**index(), "replay": {"seeds": list(REPLAY_SEEDS), "duration_s": REPLAY_DURATION_S, "designs": ["initial", "submitted"],
                                      "note": "Fresh MuJoCo rollouts on seeds that are not the hidden verification seeds; no model call."}}

    @router.get("/records/{rid}")
    def record(rid: str):
        return load(rid)

    @router.get("/records/{rid}/replay")
    def replay(rid: str, design: Literal["initial", "submitted"] = "initial", seed: int = Query(default=REPLAY_SEEDS[0], ge=0, le=MAX_SEED)):
        rec = load(rid)
        d = (rec.get("robot") or {}).get(design) or {}
        body, vec = d.get("body"), d.get("vector")
        if not isinstance(body, dict) or not isinstance(vec, list) or len(vec) != 17:
            raise HTTPException(404, f"Record {rid} has no replayable {design} design")
        key = (rid, design, seed)
        with lock:
            if key in cache:
                cache.move_to_end(key)
                return cache[key]
        if not slots.acquire(blocking=False):
            raise HTTPException(429, "too many replays are running; try again in a moment")
        try:
            payload = run(body, vec, seed)
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, f"replay failed: {str(exc)[:300]}") from exc
        except Exception as exc:  # noqa: BLE001
            log.exception("causal replay %s %s seed %s failed", rid, design, seed)
            raise HTTPException(500, f"replay failed: {type(exc).__name__}") from exc
        finally:
            slots.release()
        with lock:
            cache[key] = payload
            while len(cache) > REPLAY_CACHE_SIZE:
                cache.popitem(last=False)
        return payload

    return router
