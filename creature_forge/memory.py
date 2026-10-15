"""Engineering memory: measured lessons from past LIVE investigations, retrieved as hypotheses for a new creature's investigation.

A lesson is a flat record of MEASURED facts about one finished investigation (creature features, original outcome, failure signature, probe
results, and for every arm that reached validation: its edits, source, MuJoCo verdict status and paired median difference). It never contains
model prose (no diagnosis, mechanism, summary or tradeoff text). Only provenance LIVE records with status `done` yield a lesson; scripted or
failed records give None.

Retrieval is deterministic and independent of the bank: same challenge kind only, similarity = exp(-d) where d is a weighted Euclidean distance
over features each divided by a FIXED physical scale (not data-dependent), ties broken by lesson_id. A lesson of the same creature id is never
returned (it would leak the creature's own past).

Feature weights (FEATURES: name -> (weight, scale)); d^2 = sum_f w_f * ((a_f - b_f) / s_f)^2 over features present in BOTH, plus MODE_PENALTY^2
when the creature modes differ:
  leg_length_rear 1.0/0.4 m, leg_length_front 1.0/0.4 m, foot_to_leg 1.0/0.3, torque_to_weight 1.0/1.0, heel_behind_ankle 0.5/0.08 m,
  toe_ahead_of_ankle 0.5/0.15 m, mass_total 0.5/10 kg, foot_friction 0.5/0.5, torque_limit 0.5/60 N m.
Lessons are stored as JSON lines in `<forge_dir>/memory/lessons.jsonl` (append-only, cross-process file lock).
"""
from __future__ import annotations

import json
import math
import os
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from . import probes as pb

LESSON_VERSION = 1
MODE_PENALTY = 1.0
FEATURES: dict[str, tuple[float, float]] = {
    "leg_length_rear": (1.0, 0.4), "leg_length_front": (1.0, 0.4), "foot_to_leg": (1.0, 0.3), "torque_to_weight": (1.0, 1.0),
    "heel_behind_ankle": (0.5, 0.08), "toe_ahead_of_ankle": (0.5, 0.15), "mass_total": (0.5, 10.0), "foot_friction": (0.5, 0.5),
    "torque_limit": (0.5, 60.0)}


def _num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def _mean(*xs):
    v = [x for x in map(_num, xs) if x is not None]
    return round(sum(v) / len(v), 4) if v else None


def features_from_evidence(evidence: dict) -> dict:
    """Creature features (numbers + `mode`) read from `evidence.creature`; absent values are left out."""
    c = (evidence or {}).get("creature") or {}
    d, b = c.get("derived") or {}, c.get("body") or {}
    f = {"mode": c.get("mode"), "leg_length_rear": d.get("leg_length_rear"), "leg_length_front": d.get("leg_length_front"),
         "foot_to_leg": d.get("foot_to_leg"), "torque_to_weight": d.get("torque_to_weight"), "mass_total": d.get("mass_total"),
         "heel_behind_ankle_rear_m": d.get("heel_behind_ankle_rear_m"), "heel_behind_ankle_front_m": d.get("heel_behind_ankle_front_m"),
         "toe_ahead_of_ankle_rear_m": d.get("toe_ahead_of_ankle_rear_m"), "toe_ahead_of_ankle_front_m": d.get("toe_ahead_of_ankle_front_m"),
         "foot_friction": b.get("foot_friction"), "torque_limit": b.get("torque_limit")}
    return {k: v for k, v in f.items() if v is not None}


def _vector(f: dict) -> dict:
    v = {k: _num(f.get(k)) for k in ("leg_length_rear", "leg_length_front", "foot_to_leg", "torque_to_weight", "mass_total",
                                       "foot_friction", "torque_limit")}
    v["heel_behind_ankle"] = _mean(f.get("heel_behind_ankle_rear_m"), f.get("heel_behind_ankle_front_m"))
    v["toe_ahead_of_ankle"] = _mean(f.get("toe_ahead_of_ankle_rear_m"), f.get("toe_ahead_of_ankle_front_m"))
    return v


def distance(a: dict, b: dict) -> float:
    """Weighted Euclidean distance between two feature dicts (see module doc). Deterministic, symmetric."""
    va, vb = _vector(a), _vector(b)
    s = 0.0
    for k, (w, scale) in FEATURES.items():
        if va.get(k) is not None and vb.get(k) is not None:
            s += w * ((va[k] - vb[k]) / scale) ** 2
    if a.get("mode") and b.get("mode") and a["mode"] != b["mode"]:
        s += MODE_PENALTY ** 2
    return math.sqrt(s)


def similarity(a: dict, b: dict) -> float:
    return math.exp(-distance(a, b))


# ------------------------------------------------------------------------------------------------------------------ extraction
def _failure_signature(kind: str, rec: dict, ev: dict) -> dict:
    seeds = ev.get("seeds") or []
    sig: dict = {}
    if kind == "push":
        dirs = [(s.get("metrics") or {}).get("weak_direction") for s in seeds]
        dirs = [d for d in dirs if isinstance(d, str)]
        if dirs:
            sig["weak_direction"] = Counter(sorted(dirs)).most_common(1)[0][0]
        np_ = ((rec.get("probes") or {}).get("results") or {}).get("no_push") or {}
        if _num(np_.get("static_fall_frac")) is not None:
            sig["falls_without_push"] = round(float(np_["static_fall_frac"]), 4)
    elif kind == "stand":
        m = [s.get("metrics") or {} for s in seeds]
        sig["fell"] = any(bool(x.get("fell")) for x in m)
        surv = sorted(x for x in (_num(y.get("survival_s")) for y in m) if x is not None)
        if surv:
            sig["median_survival_s"] = round(surv[len(surv) // 2] if len(surv) % 2 else (surv[len(surv) // 2 - 1] + surv[len(surv) // 2]) / 2, 4)
    elif kind == "walk":
        labels = [(s.get("metrics") or {}).get("label") for s in seeds]
        labels = [x for x in labels if isinstance(x, str)]
        if labels:
            sig["dominant_label"] = Counter(sorted(labels)).most_common(1)[0][0]
    return sig


def _probe_items(rec: dict) -> list[dict]:
    p = rec.get("probes") or {}
    res, tol = p.get("results") or {}, _num(p.get("resolution"))
    out = []
    for pid, r in res.items():
        d = _num((r or {}).get("median_delta"))
        obs = pb.observed_direction(d, tol) if (d is not None and tol is not None and (r or {}).get("status") == "ok") else None
        item = {"probe_id": pid, "observed": obs, "median_delta": None if d is None else round(d, 4)}
        out.append(item)
    return out


def _tried(rec: dict) -> list[dict]:
    validated = (rec.get("selection") or {}).get("validated") or []
    arms = {a.get("arm_id"): a for a in rec.get("arms") or []}
    out = []
    for aid in validated:
        a, v = arms.get(aid), (rec.get("verdicts") or {}).get(aid)
        if not a or not v or aid == "original":
            continue
        edits = [{"param": e.get("param"), "op": e.get("op"), "value": e.get("value"), "target": e.get("target")} for e in a.get("edits") or []]
        out.append({"source": a.get("source"), "edits": edits, "category": a.get("category"), "verdict": v.get("status"),
                    "median_diff": _num(v.get("median_diff")), "n": v.get("n")})
    return out


def extract_lesson(rec: dict) -> dict | None:
    """Lesson from a finished investigation record, or None unless provenance is LIVE and status `done`. Measured facts only."""
    if not isinstance(rec, dict) or rec.get("provenance") != "LIVE" or rec.get("status") != "done" or not rec.get("evidence"):
        return None
    ev = rec["evidence"]
    kind = (ev.get("challenge") or {}).get("kind") or (rec.get("spec") or {}).get("kind")
    if not kind or not rec.get("id"):
        return None
    sc = (ev.get("outcome") or {}).get("score") or {}
    return {"version": LESSON_VERSION, "lesson_id": rec["id"], "created": rec.get("created"),
            "creature_id": (rec.get("creature") or {}).get("cid"), "kind": kind, "features": features_from_evidence(ev),
            "original": {"aggregate": (ev.get("outcome") or {}).get("aggregate"), "score_median": sc.get("median"),
                         "score_min": sc.get("min"), "score_max": sc.get("max"), "seeds_n": (ev.get("outcome") or {}).get("seeds_n")},
            "failure": _failure_signature(kind, rec, ev), "probes": _probe_items(rec), "tried": _tried(rec)}


# ------------------------------------------------------------------------------------------------------------------ bank
@contextmanager
def _flock(path: Path, timeout_s: float = 10.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+b")
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
                    raise TimeoutError("could not lock the memory bank") from None
                time.sleep(0.02)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        f.close()


class MemoryBank:
    """Append-only JSONL bank of lessons at `path`."""

    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def for_forge_dir(cls, forge_dir) -> "MemoryBank":
        return cls(Path(forge_dir) / "memory" / "lessons.jsonl")

    def lessons(self) -> list[dict]:
        out, seen = [], set()
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            return []
        for line in text.splitlines():
            try:
                x = json.loads(line)
            except ValueError:
                continue
            if isinstance(x, dict) and x.get("lesson_id") and x["lesson_id"] not in seen:
                seen.add(x["lesson_id"])
                out.append(x)
        return out

    def __len__(self) -> int:
        return len(self.lessons())

    def add(self, lesson: dict | None) -> bool:
        """Append the lesson unless its lesson_id is already present. True if added."""
        if not lesson or not lesson.get("lesson_id"):
            return False
        with _flock(self.path.with_suffix(".lock")):
            if any(x["lesson_id"] == lesson["lesson_id"] for x in self.lessons()):
                return False
            with open(self.path, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(lesson, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        return True

    def add_record(self, rec: dict) -> bool:
        return self.add(extract_lesson(rec))

    def build_from(self, records_dir) -> int:
        """Add the lesson of every eligible investigation record `i-*.json` under `records_dir` (recursive). Returns how many were added."""
        n = 0
        for p in sorted(Path(records_dir).rglob("i-*.json")):
            try:
                n += int(self.add_record(json.loads(p.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                continue
        return n

    def retrieve(self, features: dict, kind: str, k: int = 3, exclude_creature: str | None = None, exclude_lessons=()) -> list[tuple[float, dict]]:
        """The k most similar lessons of the same challenge kind as [(similarity, lesson)], best first (ties by lesson_id). Never a lesson of
        `exclude_creature` or one listed in `exclude_lessons`."""
        skip = set(exclude_lessons or ())
        scored = []
        for les in self.lessons():
            if les.get("kind") != kind or les["lesson_id"] in skip or (exclude_creature and les.get("creature_id") == exclude_creature):
                continue
            scored.append((round(similarity(features, les.get("features") or {}), 6), les))
        scored.sort(key=lambda t: (-t[0], t[1]["lesson_id"]))
        return scored[:max(0, int(k))]

    def summaries(self) -> list[dict]:
        return [{"lesson_id": x["lesson_id"], "created": x.get("created"), "kind": x.get("kind"), "creature_id": x.get("creature_id"),
                 "original": x.get("original"), "failure": x.get("failure"),
                 "verified": sum(1 for t in x.get("tried") or [] if t.get("verdict") == "VERIFIED_IMPROVEMENT"),
                 "n_tried": len(x.get("tried") or [])} for x in self.lessons()]


def memory_enabled() -> bool:
    return os.environ.get("CF_MEMORY") == "1"
