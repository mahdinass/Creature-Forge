"""Persistent creature / version store with lineage (Forge Loop contracts section 4).

One JSON file per creature at `<data_root>/creatures/<cid>.json`, written atomically (temp file + `os.replace`)
under a lock. Nothing touches the filesystem at import or construction; the directory is created on first write.
A version is immutable: accepting a verified change appends a child version, reverting only moves `current`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from .controller import GaitParams
from .morphology import BOUNDS
from .sandbox import SandboxBody

log = logging.getLogger(__name__)

MODES = ("guided", "experimental")
ORIGINS = ("user", "ai_accepted")
CID_RE = re.compile(r"^c-[0-9a-f]{8}$")
WALK_VECTOR_LEN = 15  # r3.PARAM_NAMES order (contracts section 2)
VERIFIED = "VERIFIED_IMPROVEMENT"
_LEG_KEYS = ("thigh_length", "shank_length", "foot_length")
_SCALAR_FIELDS = ("torso_mass", "thigh_length", "shank_length", "foot_length", "foot_friction", "torque_limit",
                  "leg_density")
_BODY_FIELDS = frozenset(SandboxBody.__dataclass_fields__)
_MAX_NAME = 80
_MAX_DRAWING_BYTES = 2_000_000


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json(obj) -> str:
    """Canonical JSON: sorted keys, no whitespace, floats as Python repr; NaN/inf are rejected."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def content_hash(body: dict, controllers: dict) -> str:
    return hashlib.sha256(canonical_json({"body": body, "controllers": controllers}).encode("utf-8")).hexdigest()


def seed_block(creature_id: str, n: int, round: int, role: str, k: int) -> tuple[int, ...]:
    """Contracts section 7: `k` consecutive seeds in a deterministic block >= 100_000 (below 1_000_000)."""
    h = hashlib.sha256(f"{creature_id}:{n}:{round}:{role}".encode("utf-8")).hexdigest()
    base = 100_000 + int(h[:8], 16) % 800_000
    return tuple(range(base, base + int(k)))


def default_controllers() -> dict:
    return {"stand": GaitParams().as_dict(), "walk": None}


def _finite(name: str, v) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number, got {v!r}")
    return float(v)


def normalize_body(body, mode: str) -> dict:
    """Validate `body` for `mode` and return it with every per-leg `*_r` explicit and all numbers as floats."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {list(MODES)}, got {mode!r}")
    if not isinstance(body, dict):
        raise ValueError("body must be an object")
    unknown = set(body) - _BODY_FIELDS
    if unknown:
        raise ValueError(f"unknown body field(s): {sorted(unknown)}")
    missing = [k for k in _SCALAR_FIELDS if body.get(k) is None]
    if missing:
        raise ValueError(f"body is missing required field(s): {missing}")
    vals: dict = {k: _finite(k, body[k]) for k in _SCALAR_FIELDS}
    for k in _LEG_KEYS:  # explicit per-leg values: the right leg copies the left when absent
        r = body.get(k + "_r")
        vals[k + "_r"] = vals[k] if r is None else _finite(k + "_r", r)
    pose = body.get("pose", (0.0,) * 7)
    if not isinstance(pose, (list, tuple)):
        raise ValueError("pose must be a list of 7 numbers")
    vals["pose"] = tuple(_finite(f"pose[{i}]", v) for i, v in enumerate(pose))
    sb = SandboxBody(**vals).validate()  # sandbox ranges, pose ranges, finite numbers
    if mode == "guided":
        for k, (lo, hi) in BOUNDS.items():
            names = (k, k + "_r") if k in _LEG_KEYS else (k,)
            for nm in names:
                v = getattr(sb, nm)
                if not (lo <= v <= hi):
                    raise ValueError(f"{nm}={v:g} is outside the guided range [{lo:g}, {hi:g}] "
                                     "(use experimental mode for wider values)")
        for k in _LEG_KEYS:
            a, b = getattr(sb, k), getattr(sb, k + "_r")
            if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(f"guided mode needs symmetric legs: {k} is {a:g} (rear) vs {b:g} (front); "
                                 "use experimental mode for different legs")
    return sb.as_dict()


def normalize_controllers(controllers) -> dict:
    """Validate a controllers record; fills the default stand gait and `walk: null` when absent."""
    if controllers is None:
        return default_controllers()
    if not isinstance(controllers, dict):
        raise ValueError("controllers must be an object")
    extra = set(controllers) - {"stand", "walk"}
    if extra:
        raise ValueError(f"unknown controller key(s): {sorted(extra)}")
    stand_in = controllers.get("stand")
    stand = GaitParams().as_dict()
    if stand_in is not None:
        if not isinstance(stand_in, dict):
            raise ValueError("controllers.stand must be an object of gait parameters")
        unknown = set(stand_in) - set(stand)
        if unknown:
            raise ValueError(f"unknown stand parameter(s): {sorted(unknown)}")
        stand.update({k: _finite(f"stand.{k}", v) for k, v in stand_in.items()})
    try:
        GaitParams(**stand).validate()
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid stand controller: {exc}") from exc
    walk = controllers.get("walk")
    if walk is not None:
        if not isinstance(walk, dict) or set(walk) - {"vector", "provenance"}:
            raise ValueError("controllers.walk must be null or {vector, provenance}")
        vec = walk.get("vector")
        if not isinstance(vec, (list, tuple)) or len(vec) != WALK_VECTOR_LEN:
            raise ValueError(f"controllers.walk.vector must have {WALK_VECTOR_LEN} numbers")
        prov = walk.get("provenance")
        if prov is not None and not isinstance(prov, dict):
            raise ValueError("controllers.walk.provenance must be an object or null")
        walk = {"vector": [_finite(f"walk.vector[{i}]", v) for i, v in enumerate(vec)], "provenance": prov}
    return {"stand": stand, "walk": walk}


def atomic_write_json(path: Path, obj) -> None:
    """Write JSON next to `path` and `os.replace` it in, so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1, allow_nan=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class CreatureStore:
    """`root` is the forge data root; creatures live in `<root>/creatures/<cid>.json`."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.dir = self.root / "creatures"
        self._lock = threading.RLock()

    # ---- file helpers
    def _path(self, cid: str) -> Path:
        if not isinstance(cid, str) or not CID_RE.match(cid):
            raise KeyError(cid)
        return self.dir / f"{cid}.json"

    def _read(self, cid: str) -> dict:
        path = self._path(cid)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(cid) from None

    def _write(self, rec: dict) -> None:
        atomic_write_json(self._path(rec["id"]), rec)

    @staticmethod
    def _version(n: int, parent, mode, body, controllers, origin, drawing, change) -> dict:
        return {"n": n, "parent": parent, "created": now_iso(), "content_hash": content_hash(body, controllers),
                "mode": mode, "body": body, "controllers": controllers, "origin": origin,
                "drawing": drawing, "change": change}

    # ---- public API
    def create(self, *, name, body: dict, mode: str, drawing: dict | None = None) -> dict:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > _MAX_NAME:
            raise ValueError(f"name must be 1 to {_MAX_NAME} characters")
        norm = normalize_body(body, mode)
        if drawing is None:
            drawing = {}
        if not isinstance(drawing, dict):
            raise ValueError("drawing must be an object")
        drawing = {"strokes": [], "interpretation": None, "approximation": None, **drawing}
        try:
            if len(canonical_json(drawing)) > _MAX_DRAWING_BYTES:
                raise ValueError("drawing is too large")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"drawing must be plain JSON: {exc}") from exc
        controllers = default_controllers()
        with self._lock:
            while True:
                cid = "c-" + secrets.token_hex(4)
                if not self._path(cid).exists():
                    break
            rec = {"id": cid, "name": name.strip(), "created": now_iso(), "current": 1,
                   "versions": [self._version(1, None, mode, norm, controllers, "user", drawing, None)]}
            self._write(rec)
            return rec

    def list(self) -> list[dict]:
        out = []
        with self._lock:
            files = sorted(self.dir.glob("c-*.json")) if self.dir.is_dir() else []
            for p in files:
                try:
                    r = json.loads(p.read_text(encoding="utf-8"))
                    out.append({"id": r["id"], "name": r["name"], "current": r["current"],
                                "n_versions": len(r["versions"]), "created": r["created"]})
                except (OSError, ValueError, KeyError) as exc:
                    log.warning("skipping unreadable creature file %s: %s", p.name, exc)
        out.sort(key=lambda s: (s["created"], s["id"]), reverse=True)
        return out

    def get(self, cid: str) -> dict:
        with self._lock:
            return self._read(cid)

    def version(self, cid: str, n: int) -> dict:
        rec = self.get(cid)
        for v in rec["versions"]:
            if v["n"] == n:
                return v
        raise KeyError(f"{cid} has no version {n}")

    def accept(self, cid: str, *, parent_n: int, body: dict, controllers: dict, change: dict) -> dict:
        """Append a child version of `parent_n`. Refuses unless the change carries a VERIFIED_IMPROVEMENT verdict."""
        verdict = change.get("verdict") if isinstance(change, dict) else None
        status = verdict.get("status") if isinstance(verdict, dict) else None
        if status != VERIFIED:
            raise ValueError(f"only a {VERIFIED} can be accepted (verdict status: {status!r})")
        with self._lock:
            rec = self._read(cid)
            parent = next((v for v in rec["versions"] if v["n"] == parent_n), None)
            if parent is None:
                raise KeyError(f"{cid} has no version {parent_n}")
            mode = parent["mode"]
            norm_body = normalize_body(body, mode)
            norm_ctrl = normalize_controllers(controllers)
            n = max(v["n"] for v in rec["versions"]) + 1
            rec["versions"].append(self._version(n, parent_n, mode, norm_body, norm_ctrl, "ai_accepted", None, change))
            rec["current"] = n
            self._write(rec)
            return rec

    def set_current(self, cid: str, n: int) -> dict:
        """Revert or move forward to an existing version. Never deletes anything."""
        if isinstance(n, bool) or not isinstance(n, int):
            raise ValueError("n must be an integer")
        with self._lock:
            rec = self._read(cid)
            if not any(v["n"] == n for v in rec["versions"]):
                raise KeyError(f"{cid} has no version {n}")
            rec["current"] = n
            self._write(rec)
            return rec
