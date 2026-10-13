"""Investigation Laboratory backend: read-only access to saved trials plus deterministic MuJoCo replay.

Nothing here calls a model, writes a record or invents a number. Trial JSON is immutable history; this module
only (a) lists/loads it, (b) reshapes it for display (`lab_view`, built on `trial_view`), and (c) RE-RUNS the
authoritative MuJoCo engine from the parameters saved in the record (`build_replay`) and checks the fresh
numbers against the saved ones with the cross-platform tolerance policy (`reproducibility.compare_evidence`).

Two trial sources: the user's local `artifacts/investigations` (git-ignored, written by scripts) and the
bundled, hash-checked demonstration records in `experiments/demo_trials` (real, unedited copies).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

import mujoco

from .controller import GaitParams
from .evaluation import Protocol, evaluate_design_protocol
from .investigator import INVESTIGATIONS_DIR
from .morphology import BipedParams
from .render_export import build_run_payload
from .reproducibility import RTOL, ATOL, compare_evidence
from .simulate import Push
from .trial_view import trial_view

DEMO_DIR = Path(__file__).resolve().parents[1] / "experiments" / "demo_trials"
ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
RAW_REPLY_LIMIT = 4000

# What each kind of statement in the UI is, so the frontend cannot blur them.
PROVENANCE = {
    "observed": "Measured by MuJoCo before the model saw anything (authoritative).",
    "hypothesis": "Written by the language model. Untrusted: a guess, never a proven cause.",
    "confidence": "Number the model reported about itself. Not calibrated; never used by the verifier.",
    "measured": "Re-measured by MuJoCo after applying the model's proposed change (authoritative).",
}


class LabError(Exception):
    """A record cannot be shown (missing, unreadable or malformed). Message is safe to display."""


# --------------------------------------------------------------------------- listing / loading

def _manifest(demo_dir: Path) -> dict:
    try:
        return json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8")).get("trials", {})
    except (OSError, ValueError):
        return {}


def _source_dirs(local_dir: Path, demo_dir: Path):
    return (("local", local_dir), ("bundled-demo", demo_dir))


def _summary(trial: dict, source: str) -> dict:
    hyp, out = trial.get("hypothesis") or {}, trial.get("measured_outcome") or {}
    proto = (out.get("protocol") or {}).get("verdict") or {}
    obs = out.get("observed") or {}
    iv = hyp.get("intervention") or {}
    return {"trial_id": trial.get("trial_id"), "status": trial.get("status"), "mode": trial.get("mode"),
            "created_utc": trial.get("created_utc"), "source": source,
            "label": (trial.get("config") or {}).get("label"),
            "variant": (trial.get("config") or {}).get("variant", "legacy"),
            "claim": hyp.get("claim"), "parameter": iv.get("parameter"), "value": iv.get("value"),
            "confidence": hyp.get("confidence"), "tier": proto.get("tier"),
            "fall_rate": {k: (obs.get("fall_rate") or {}).get(k) for k in ("baseline", "candidate")} if obs else None,
            "reason": trial.get("rejection_reason"), "readable": True}


def list_lab_trials(local_dir: Path = INVESTIGATIONS_DIR, demo_dir: Path = DEMO_DIR) -> list[dict]:
    """Newest first. Unreadable files are listed (not hidden) with readable=False so nothing silently vanishes."""
    out, seen = [], {}
    for source, root in _source_dirs(local_dir, demo_dir):
        for p in sorted(root.glob("2*.json")) if root.is_dir() else []:
            tid = p.stem
            try:
                t = json.loads(p.read_text(encoding="utf-8"))
                if not isinstance(t, dict) or t.get("trial_id") != tid:
                    raise ValueError("trial_id does not match file name")
                row = _summary(t, source)
            except (OSError, ValueError) as exc:
                row = {"trial_id": tid, "status": "unreadable", "source": source, "readable": False,
                       "error": f"{type(exc).__name__}: {str(exc)[:120]}", "created_utc": None}
            if tid in seen:  # same record in both places: list once, local copy wins
                seen[tid]["also_bundled"] = True
                continue
            seen[tid] = row
            out.append(row)
    return sorted(out, key=lambda r: r["trial_id"], reverse=True)


def load_lab_trial(trial_id: str, local_dir: Path = INVESTIGATIONS_DIR,
                   demo_dir: Path = DEMO_DIR) -> tuple[dict, str]:
    if not ID_RE.fullmatch(trial_id or ""):
        raise LabError("invalid trial id")
    for source, root in _source_dirs(local_dir, demo_dir):
        p = root / f"{trial_id}.json"
        if p.is_file():
            try:
                t = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise LabError(f"record exists but cannot be read ({type(exc).__name__})") from None
            if not isinstance(t, dict) or t.get("trial_id") != trial_id:
                raise LabError("record is malformed (trial_id mismatch)")
            return t, source
    raise KeyError(trial_id)


def demo_integrity(trial_id: str, demo_dir: Path = DEMO_DIR) -> dict | None:
    """sha256 of the bundled file vs the manifest; None when this id is not a bundled record."""
    entry = _manifest(demo_dir).get(trial_id)
    p = demo_dir / f"{trial_id}.json"
    if entry is None or not p.is_file():
        return None
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"verified": actual == entry["sha256"], "sha256": entry["sha256"], "note": entry.get("note")}


# --------------------------------------------------------------------------- display model

def replay_seeds(trial: dict) -> list[int]:
    ev = trial.get("observed_evidence") or {}
    seeds = set((ev.get("scenario") or {}).get("seeds") or [])
    seeds |= set((trial.get("measured_outcome") or {}).get("seeds") or [])
    return sorted(int(s) for s in seeds)


def _seed_roles(trial: dict) -> dict:
    """Seed sets exactly as saved: the ones the model saw evidence from vs. the ones the verifier screened on."""
    cfg, ev, out = trial.get("config") or {}, trial.get("observed_evidence") or {}, trial.get("measured_outcome") or {}
    evidence = cfg.get("evidence_seeds") or (ev.get("scenario") or {}).get("seeds")
    screening = out.get("seeds") or cfg.get("verify_seeds")
    return {"evidence": sorted(evidence) if evidence else None, "screening": sorted(screening) if screening else None}


def lab_view(trial: dict, source: str, demo_dir: Path = DEMO_DIR) -> dict:
    """trial_view plus availability flags, provenance labels and graceful degradation."""
    missing: list[str] = []
    try:
        view = trial_view(trial)
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        view = {"trial_id": trial.get("trial_id"), "mode": trial.get("mode"),
                "label": (trial.get("config") or {}).get("label"),
                "variant": (trial.get("config") or {}).get("variant", "legacy"), "observed": None,
                "rationale": None, "design_change": None, "predicted_vs_measured": None,
                "outcome": {"status": trial.get("status"), "reason": trial.get("rejection_reason"), "tier": None},
                "model_call": trial.get("model_call"), "degraded": f"record is incomplete ({type(exc).__name__})"}
        missing.append("display model could not be built from this record")
    ev = trial.get("observed_evidence")
    if not ev:
        missing.append("no observed evidence was saved")
    elif not (ev.get("forensics") or {}).get("detailed"):
        missing.append("no forensic timeline (this trial used the compact legacy evidence)")
    if not trial.get("hypothesis"):
        missing.append("no valid hypothesis (the model response was not accepted)")
    elif not trial.get("measured_outcome"):
        missing.append("no verifier outcome was saved")
    can_replay = bool(ev and ev.get("body") and ev.get("controller") and (ev.get("scenario") or {}).get("push"))
    raw = trial.get("raw_model_reply")
    view |= {
        "source": source, "provenance": PROVENANCE, "missing": missing, "created_utc": trial.get("created_utc"),
        "integrity": demo_integrity(view["trial_id"], demo_dir) if source == "bundled-demo" else None,
        "sections": {"observe": bool(ev), "hypothesis": bool(view.get("rationale")),
                     "intervene": bool(view.get("design_change")), "verify": bool(view.get("predicted_vs_measured")),
                     "compare": can_replay and bool(view.get("design_change"))},
        "raw_model_reply": None if raw is None else {"text": raw[:RAW_REPLY_LIMIT], "truncated": len(raw) > RAW_REPLY_LIMIT,
                                                     "note": "Untrusted model text, shown verbatim as plain text."},
        "replay": {"available": can_replay, "seeds": replay_seeds(trial) if can_replay else [],
                   "has_candidate": bool(view.get("design_change"))},
        "protocol_config": (trial.get("config") or {}).get("protocol"),
        "verdict": ((trial.get("measured_outcome") or {}).get("protocol") or {}).get("verdict"),
        "screening": ({k: trial["measured_outcome"].get(k) for k in ("prediction_held", "improved", "accepted", "seeds")}
                      if trial.get("measured_outcome") else None),
        "seeds": _seed_roles(trial),
        "protocol_simulations": ((trial.get("measured_outcome") or {}).get("protocol") or {}).get("simulations"),
    }
    return view


# --------------------------------------------------------------------------- deterministic replay

def _scenario(trial: dict):
    ev = trial["observed_evidence"]
    sc = ev["scenario"]
    gait = GaitParams(**ev["controller"]).validate()
    p = sc["push"]
    return (BipedParams(**ev["body"]).validate(), gait, Push(time=p["time_s"], force=p["force_N"], duration=p["duration_s"]),
            float(sc["duration_s"]))


def _saved_stats(trial: dict, arm: str, seed: int) -> dict | None:
    """Per-seed numbers saved at evaluation time, normalised to {fell, min_torso_height, max_abs_pitch, events}."""
    out = trial.get("measured_outcome") or {}
    for r in (out.get("per_seed") or {}).get(arm, []):
        if r.get("seed") == seed:
            return {k: r[k] for k in ("fell", "min_torso_height", "max_abs_pitch", "events")}
    if arm == "baseline":  # evidence-phase record of the same rollouts
        for r in ((trial.get("observed_evidence") or {}).get("matched_seed_results") or {}).get("per_seed", []):
            if r.get("seed") == seed:
                return {"fell": r["fell"], "min_torso_height": r["min_torso_height_m"],
                        "max_abs_pitch": r["max_abs_pitch_rad"], "events": r["events"]}
    return None


def _consistency(run: dict, saved: dict | None) -> dict:
    if saved is None:
        return {"checked": False, "reason": "no saved per-seed statistics for this seed"}
    fresh = {"fell": run["metrics"]["fell"], "min_torso_height": run["metrics"]["min_torso_height"],
             "max_abs_pitch": run["metrics"]["max_abs_pitch"], "events": sorted({e["kind"] for e in run["events"]})}
    ref = {**saved, "events": sorted(set(saved["events"]))}
    cmp = compare_evidence(ref, fresh)
    return {"checked": True, "matches_saved_record": cmp.ok, "max_rel_diff": cmp.max_rel(),
            "tolerance": {"rtol": RTOL, "atol": ATOL}, "saved": saved,
            "fresh": {k: fresh[k] for k in ("fell", "min_torso_height", "max_abs_pitch")},
            "failures": cmp.failures()}


def build_replay(trial: dict, seed: int) -> dict:
    """Re-run MuJoCo from the parameters saved in the record. No model call. Raises LabError if impossible."""
    if not trial.get("observed_evidence"):
        raise LabError("this record has no saved scenario to replay")
    allowed = replay_seeds(trial)
    if seed not in allowed:
        raise LabError(f"seed {seed} was not part of this investigation (saved seeds: {allowed})")
    try:
        body, gait, push, duration = _scenario(trial)
    except (KeyError, TypeError, ValueError) as exc:
        raise LabError(f"saved scenario is incomplete or invalid ({type(exc).__name__}: {exc})") from None
    baseline = build_run_payload(body, gait, seed=seed, duration=duration, push=push)
    result = {"seed": seed, "baseline": baseline, "candidate": None,
              "engine": {"mujoco": mujoco.__version__, "model_calls": 0,
                         "source": "parameters saved in the trial record, re-simulated now (deterministic)"},
              "consistency": {"baseline": _consistency(baseline, _saved_stats(trial, "baseline", seed))}}
    cand = (trial.get("measured_outcome") or {}).get("candidate_body")
    if cand:
        try:
            cbody = BipedParams(**cand).validate()
        except (TypeError, ValueError) as exc:
            raise LabError(f"saved candidate body is invalid ({exc})") from None
        run = build_run_payload(cbody, gait, seed=seed, duration=duration, push=push)
        result["candidate"] = run
        result["consistency"]["candidate"] = _consistency(run, _saved_stats(trial, "candidate", seed))
    return result


def reverify_protocol(trial: dict, push_levels: list[float] | None = None) -> dict:
    """Recompute the saved held-out protocol aggregates (slow: len(levels) x 10 sims per arm) and compare them."""
    out = trial.get("measured_outcome") or {}
    saved = out.get("protocol")
    cfg = (trial.get("config") or {}).get("protocol")
    if not saved or not cfg or not trial.get("observed_evidence"):
        raise LabError("this record has no held-out protocol to re-verify")
    body, gait, _, _ = _scenario(trial)
    proto = Protocol(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in cfg.items()})
    if push_levels is not None:
        proto = replace(proto, push_levels_N=tuple(float(x) for x in push_levels))
    report = {}
    for arm, b in (("baseline", body), ("candidate", BipedParams(**out["candidate_body"]).validate())):
        fresh = evaluate_design_protocol(b, gait, proto)["by_push"]
        report[arm] = {}
        for k, v in fresh.items():
            ref = saved[arm]["by_push"][str(float(k))] if str(float(k)) in saved[arm]["by_push"] else saved[arm]["by_push"][str(k)]
            cmp = compare_evidence(ref, v)
            report[arm][str(k)] = {"matches": cmp.ok, "max_rel_diff": cmp.max_rel(), "failures": cmp.failures()}
    return {"ok": all(x["matches"] for arm in report.values() for x in arm.values()), "arms": report,
            "tolerance": {"rtol": RTOL, "atol": ATOL}}
