"""Studio "Recover walking": the equal-budget walking-recovery pipeline on one creature version, as a background job.

Flow (research modules reused unchanged): diagnostics -> a director chooses probes and plans (`walk_pipelines.run_pipeline`) ->
CMA-ES fits -> screening selects ONE candidate -> `recovery.assess` (`full_recovery_v1`: validation seeds under the arena's variation
preset, then a 20 s confirmation on further disjoint seeds). The record is saved at `<forge_dir>/recoveries/<rid>.json`.

Directors
  * "ai" + mode "live"      `director.NemotronDirector` (prompt v2), provenance LIVE. Needs CREATURE_FORGE_ENABLE_LIVE=1, an API key and
                            ledger headroom (same gate as investigations); refused under CF_INVESTIGATION_SCALE=smoke.
  * "ai" + mode "scripted"  `ScriptedRecoveryDirector`: the deterministic FIX decisions wearing the AI record shape, provenance
                            SCRIPTED_MOCK, model "scripted-fixture". It is NOT a model and never becomes LIVE.
  * "fix"                   `walk_pipelines.FixedDirector`, the fixed engineering rule; provenance NON_AI.

Rules
  * Accept: a recovery may become a new creature version ONLY with assessment status FULL_RECOVERY (stricter than the investigation's
    VERIFIED_IMPROVEMENT); PARTIAL_IMPROVEMENT, NOT_RECOVERED, INCONCLUSIVE_ERROR and failed runs are never acceptable.
  * Seeds: product namespace, `creatures.seed_block(cid, n, <recovery index>, "rec_<role>", k)`, roles diag/train/screen/validate/confirm
    pairwise disjoint and disjoint from `arena._forbidden_seeds()`, all in [100_000, 1_000_000), never the research namespace (>= 10_000_000).
    The recovery index is persisted per (cid, n) so a repeated recovery gets fresh blocks; a clash bumps it.
  * Scale: full = diag 4 / train 8 / screen 12 (top 3) / validate 24 / confirm 24, probe budget 10 % of the budget, 2 rounds (the S2 protocol).
    Smoke (CF_INVESTIGATION_SCALE=smoke, CI browser flows only): budget 400, probe 40, screen_n 2, diag 2 / train 2 / validate 4 / confirm 4,
    1 round. The scale is recorded.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import threading
from pathlib import Path
from typing import Callable

from . import investigation as inv
from .creatures import FULL_RECOVERY, atomic_write_json, now_iso, seed_block
from .jobs import JobCancelled, QueueFull, jsonable, public_error  # noqa: F401 - QueueFull re-exported for callers

log = logging.getLogger(__name__)

VERSION = "recoveries_v1"
RECOVERY_ID_RE = re.compile(r"r-[0-9a-f]{12}")   # always used with fullmatch
DIRECTORS = ("ai", "fix")
MODES = ("live", "scripted")
PROVENANCE = {"live": "LIVE", "scripted": "SCRIPTED_MOCK", "fix": "NON_AI"}
SCRIPTED_MODEL = inv.SCRIPTED_MODEL
FAMILY = 17
MIN_BUDGET, MAX_BUDGET, DEFAULT_BUDGET = 400, 4000, 2000
ROLES = ("diag", "train", "screen", "validate", "confirm")
FULL_SIZES = {"diag": 4, "train": 8, "screen": 12, "validate": 24, "confirm": 24}
SMOKE_SIZES = {"diag": 2, "train": 2, "screen": 2, "validate": 4, "confirm": 4}
FULL_SETTINGS = {"probe_budget_frac": 0.1, "rounds": 2, "screen_top_k": 3, "screen_n": 12}
SMOKE_SETTINGS = {"probe_budget": 40, "rounds": 1, "screen_top_k": 3, "screen_n": 2, "budget": 400}
FIX_PROBES = ("opt_placement", "opt_body", "opt_posture")   # the S2 protocol's FIX rule for family 17
SEED_LOW, SEED_HIGH = 100_000, 1_000_000
RESEARCH_NAMESPACE_START = 10_000_000
PHASES = ("diagnostics", "probes", "plans", "screening", "validation", "confirmation", "done")
PROGRESS_MIN_INTERVAL_S = 0.5
_counter_lock = threading.Lock()


class RecoveryRefused(ValueError):
    """The recovery cannot be accepted; the message is the reason (HTTP 409)."""


# ------------------------------------------------------------------------------------------------------------------ store
def new_recovery_id() -> str:
    return "r-" + secrets.token_hex(6)


def recovery_path(forge_dir: Path, rid: str) -> Path:
    if not isinstance(rid, str) or not RECOVERY_ID_RE.fullmatch(rid):
        raise KeyError(rid)
    return Path(forge_dir) / "recoveries" / f"{rid}.json"


def load_recovery(forge_dir: Path, rid: str) -> dict:
    try:
        return json.loads(recovery_path(forge_dir, rid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise KeyError(rid) from None


def save_recovery(forge_dir: Path, rec: dict) -> None:
    atomic_write_json(recovery_path(forge_dir, rec["id"]), jsonable(rec))


def summarize(rec: dict) -> dict:
    cand = rec.get("candidate") or {}
    b = rec.get("budget") or {}
    return {"id": rec["id"], "created": rec["created"], "creature": rec["creature"], "director": rec["director"], "mode": rec.get("mode"),
            "provenance": rec["provenance"], "model": rec.get("model"), "status": rec["status"], "error": rec.get("error"),
            "scale": rec.get("scale"), "budget": {"total": b.get("total"), "used": b.get("used")},
            "n_edits": len(cand.get("edits") or []), "walking_frac": (((rec.get("assessment") or {}).get("validation") or {}).get("walking_frac"))}


def list_recoveries(forge_dir: Path, cid: str | None = None) -> list[dict]:
    d = Path(forge_dir) / "recoveries"
    out = []
    for p in sorted(d.glob("r-*.json")) if d.is_dir() else []:
        if not RECOVERY_ID_RE.fullmatch(p.stem):
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            if cid is None or rec["creature"]["cid"] == cid:
                out.append(summarize(rec))
        except (OSError, ValueError, KeyError):
            continue
    out.sort(key=lambda s: (s["created"], s["id"]), reverse=True)
    return out


# ------------------------------------------------------------------------------------------------------------------ seeds
def _next_index(forge_dir: Path, cid: str, n: int) -> int:
    path = Path(forge_dir) / "recoveries" / "_counters.json"
    with _counter_lock:
        try:
            counters = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            counters = {}
        key = f"{cid}:{n}"
        k = int(counters.get(key, 0))
        counters[key] = k + 1
        atomic_write_json(path, counters)
        return k


def recovery_seeds(cid: str, n: int, index: int, sizes: dict, *, max_bumps: int = 64) -> dict:
    """Role blocks of one recovery. Asserts they are pairwise disjoint, disjoint from every consumed research seed set and inside the
    product namespace; a clash bumps the recovery index. Returns {"index": used_index, "seeds": {role: [ints]}}."""
    from .arena import _forbidden_seeds
    forbidden = set().union(*(set(v) for v in _forbidden_seeds().values()))
    for k in range(index, index + max_bumps):
        blocks = {role: list(seed_block(cid, n, k, "rec_" + role, int(sizes[role]))) for role in ROLES}
        seen: set = set()
        clash = False
        for role in ROLES:
            s = set(blocks[role])
            if s & seen or s & forbidden:
                clash = True
                break
            seen |= s
        if not clash:
            assert all(SEED_LOW <= x < RESEARCH_NAMESPACE_START for b in blocks.values() for x in b)
            return {"index": k, "seeds": blocks}
    raise RuntimeError(f"no disjoint seed blocks found within {max_bumps} bumps for {cid} v{n}")


# ------------------------------------------------------------------------------------------------------------------ scale / vector
def scale_settings(scale: str, budget: int) -> tuple[int, dict, dict]:
    """(effective total budget, sizes, run_pipeline settings) for a scale."""
    if scale == "smoke":
        s = dict(SMOKE_SETTINGS)
        return s.pop("budget"), dict(SMOKE_SIZES), s
    probe = int(round(FULL_SETTINGS["probe_budget_frac"] * budget))
    return budget, dict(FULL_SIZES), {"probe_budget": probe, "rounds": FULL_SETTINGS["rounds"],
                                      "screen_top_k": FULL_SETTINGS["screen_top_k"], "screen_n": FULL_SETTINGS["screen_n"]}


def original_vector(version: dict) -> list[float]:
    """The version's walking vector as the 15-D start of the pipeline (no walking controller -> the frozen R2 winner).
    A 17-D controller with non-zero foot-placement gains cannot be the pipeline's start and is refused."""
    from . import creature_walk as cw
    w = (version.get("controllers") or {}).get("walk")
    vec = w.get("vector") if isinstance(w, dict) else w
    if vec is None:
        return [float(x) for x in cw.R2_WINNER]
    vec = [float(x) for x in vec]
    if len(vec) == 17:
        if any(abs(x) > 1e-12 for x in vec[15:]):
            raise ValueError("this version already has foot-placement gains (a 17-parameter walking controller); recovery starts from a "
                             "15-parameter controller")
        vec = vec[:15]
    if len(vec) != 15:
        raise ValueError(f"the walking vector must have 15 numbers, got {len(vec)}")
    return vec


# ------------------------------------------------------------------------------------------------------------------ directors
class ScriptedRecoveryDirector:
    """SCRIPTED_MOCK stand-in for the AI director: the fixed engineering rule's decisions in the AI record shape. No model, no network."""
    provenance = "SCRIPTED_MOCK"
    model = SCRIPTED_MODEL

    def __init__(self, investigation_id: str):
        from . import walk_pipelines as wp
        self.inner = wp.FixedDirector(probes=FIX_PROBES)
        self.investigation_id = investigation_id
        self.decisions: list[dict] = []

    def choose_probes(self, state):
        out = self.inner.choose_probes(state)
        self.decisions.append({"kind": "probes", "round": state["round"], "status": "ok", "returned": list(out), "calls": []})
        return out

    def choose_plans(self, state):
        out = self.inner.choose_plans(state)
        self.decisions.append({"kind": "plans", "round": state["round"], "status": "ok", "returned": jsonable(out), "calls": [],
                               "diagnosis": "Scripted mock: the fixed engineering rule's choice, not a model's reasoning."})
        return out

    def record(self) -> dict:
        return jsonable({"version": "scripted_recovery_director_v1", "provenance": self.provenance, "model": self.model, "profile": "scripted",
                         "investigation_id": self.investigation_id, "prompt_version": "v2", "calls": [], "decisions": self.decisions,
                         "hypotheses": {}, "cost_usd": 0.0, "tokens": {"prompt": 0, "completion": 0},
                         "note": "SCRIPTED_MOCK: deterministic fixed-rule decisions; no model was called."})


def build_director(director: str, mode: str | None, *, rid: str, ledger, profile: str, model_config_path, order_seed: int):
    """(director object, provenance, model name or None). Live construction raises LiveRefused when the gate is closed."""
    from . import walk_pipelines as wp
    if director == "fix":
        return wp.FixedDirector(probes=FIX_PROBES), PROVENANCE["fix"], None
    iid = "i-" + rid[2:]
    if mode == "scripted":
        d = ScriptedRecoveryDirector(iid)
        return d, d.provenance, d.model
    from . import director as dr
    cfg = inv.load_model_config(profile, model_config_path)
    d = dr.NemotronDirector(mode="live", profile=profile, ledger=ledger, investigation_id=iid, prompt_version="v2", order_seed=order_seed,
                            config=cfg)
    return d, d.provenance, d.cfg.model


# ------------------------------------------------------------------------------------------------------------------ progress
class _CountingPool:
    """Wraps the pool: counts finished jobs, derives the phase from the seed of a `recovery.run_walk_seeds` job, throttles progress."""

    def __init__(self, inner, tracker):
        self.inner, self.t = inner, tracker
        self.max_workers = getattr(inner, "max_workers", 1)

    def imap(self, fn, jobs):
        jobs = list(jobs)
        for i, res in self.inner.imap(fn, jobs):
            self.t.done(jobs[i] if i < len(jobs) else None)
            yield i, res

    def map(self, fn, jobs):
        out = [None] * len(list(jobs))
        jobs = list(jobs)
        for i, res in self.imap(fn, jobs):
            out[i] = res
        return out

    def close(self) -> None:   # the shared pool belongs to the job manager
        pass


class _Abort(BaseException):
    """Cancellation signal that the pipeline's `except Exception` handlers (which record a failed plan and carry on) cannot swallow."""


class _Tracker:
    def __init__(self, emit, progress, seeds: dict, screen_n: int, total: int, n_validate: int, n_confirm: int, clock=None,
                 cancelled: Callable[[], bool] | None = None):
        import time
        self.emit, self.progress, self.clock = emit, progress, clock or time.monotonic
        self.cancelled = cancelled or (lambda: False)
        self.role = {s: r for r in ("diag", "screen", "validate", "confirm") for s in (seeds[r][:screen_n] if r == "screen" else seeds[r])}
        self.total = total
        self.phase = None
        self.pipeline_used = 0
        self.counts = {"validation": 0, "confirmation": 0}
        self.totals = {"validation": 2 * n_validate, "confirmation": n_confirm}
        self._last = 0.0

    def set_phase(self, phase: str, **extra) -> None:
        if phase != self.phase:
            self.phase = phase
            self.emit("phase", {"phase": phase, **extra})
            self._report(force=True)

    def done(self, job) -> None:
        if self.cancelled():
            raise _Abort()
        seed = job.get("seed") if isinstance(job, dict) else None
        role = self.role.get(seed) if seed is not None else None
        if role == "diag":
            self.set_phase("diagnostics")
        elif role == "screen":
            self.set_phase("screening")
            self.pipeline_used += 1
        elif role == "validate":
            self.set_phase("validation")
            self.counts["validation"] += 1
        elif role == "confirm":
            self.set_phase("confirmation")
            self.counts["confirmation"] += 1
        else:
            self.pipeline_used += 1
        self._report()

    def _report(self, force: bool = False) -> None:
        now = self.clock()
        if not force and now - self._last < PROGRESS_MIN_INTERVAL_S:
            return
        self._last = now
        try:
            if self.phase in self.counts:
                self.progress(min(self.counts[self.phase], self.totals[self.phase]), self.totals[self.phase], self.phase)
            else:
                self.progress(min(self.pipeline_used, self.total), self.total, self.phase)
        except JobCancelled:
            raise _Abort() from None

    def log(self, msg: str) -> None:   # run_pipeline's `log`: "round r: probe X" / "round r: plan X budget B"
        if ": probe " in msg:
            self.set_phase("probes", detail=msg)
        elif ": plan " in msg:
            self.set_phase("plans", detail=msg)


# ------------------------------------------------------------------------------------------------------------------ start / run
def start_recovery(jobs, store, forge_dir: Path, cid: str, n: int, *, director: str, mode: str | None = None,
                   budget: int = DEFAULT_BUDGET, ledger=None, profile: str = "default", model_config_path=None, options: dict | None = None,
                   submit_kw: dict | None = None) -> tuple[str, str]:
    """Validate, fix the seeds and submit the job. Returns (job_id, recovery_id).
    KeyError: no such creature/version. ValueError: bad input. `inv.LiveRefused`: live not allowed (nothing submitted).
    QueueFull / RuntimeError come from the job manager."""
    if director not in DIRECTORS:
        raise ValueError(f"director must be one of {list(DIRECTORS)}, got {director!r}")
    if director == "ai":
        if mode not in MODES:
            raise ValueError(f"mode must be one of {list(MODES)} for the ai director, got {mode!r}")
    elif mode is not None:
        raise ValueError("mode applies to the ai director only (the fix rule is not an AI)")
    if isinstance(budget, bool) or not isinstance(budget, int) or not MIN_BUDGET <= budget <= MAX_BUDGET:
        raise ValueError(f"budget must be an integer in [{MIN_BUDGET}, {MAX_BUDGET}] rollouts")
    version = store.version(cid, n)   # KeyError -> 404
    original_vector(version)           # validates the start controller now (422) instead of failing in the job
    scale = inv.investigation_scale()
    if mode == "live":
        if scale == "smoke":
            raise inv.LiveRefused("live recoveries always run at full scale; unset CF_INVESTIGATION_SCALE=smoke on this server")
        cfg = inv.load_model_config(profile, model_config_path)
        reason = inv.live_refusal(ledger, cfg)
        if reason:
            raise inv.LiveRefused(reason)
    total, sizes, settings = scale_settings(scale, budget)
    forge_dir = Path(forge_dir)
    rid = new_recovery_id()
    plan = recovery_seeds(cid, n, _next_index(forge_dir, cid, n), sizes)
    job_id = jobs.submit("recovery", _recovery_job, store=store, forge_dir=forge_dir, rid=rid, cid=cid, n=n, director=director, mode=mode,
                         requested_budget=budget, total=total, settings=settings, scale=scale, plan=plan, ledger=ledger, profile=profile,
                         model_config_path=model_config_path, options=dict(options or {}), **(submit_kw or {}))
    return job_id, rid


def _recovery_job(ctx, **kw) -> dict:
    rec = run_recovery(emit=ctx.emit, progress=ctx.progress, cancelled=ctx.cancelled, pool=ctx.pool, **kw)
    if rec["status"] == "cancelled":
        raise JobCancelled()
    if rec["status"] == "failed":
        raise RuntimeError(rec["error"] or "recovery failed")
    return {"recovery_id": rec["id"], "status": rec["status"], "provenance": rec["provenance"]}


def run_recovery(*, store, forge_dir: Path, rid: str, cid: str, n: int, director: str, mode: str | None, requested_budget: int, total: int,
                 settings: dict, scale: str, plan: dict, ledger=None, profile: str = "default", model_config_path=None,
                 options: dict | None = None, emit: Callable | None = None, progress: Callable | None = None,
                 cancelled: Callable[[], bool] | None = None, pool=None) -> dict:
    """Run one recovery and save its record (also when it failed or was cancelled). Raises `inv.LiveRefused` (nothing written) if live is
    not allowed. `options` (tests): pipeline_fn, assess_fn, code_fn, director_factory."""
    from . import forge_pool
    from . import recovery as rc
    from . import walk_pipelines as wp
    opts = dict(options or {})
    emit = emit or (lambda *_a, **_k: None)
    progress = progress or (lambda *_a, **_k: None)
    cancelled = cancelled or (lambda: False)
    version = store.version(cid, n)
    body = version["body"]
    start_vec = original_vector(version)
    seeds = plan["seeds"]
    order_seed = int(hashlib.sha256(f"order:{rid}".encode()).hexdigest()[:8], 16)
    if scale == "smoke" and mode == "live":
        raise inv.LiveRefused("live recoveries always run at full scale; unset CF_INVESTIGATION_SCALE=smoke on this server")
    factory = opts.get("director_factory") or build_director
    dobj, provenance, model = factory(director, mode, rid=rid, ledger=ledger, profile=profile, model_config_path=model_config_path,
                                      order_seed=order_seed)
    t0 = now_iso()
    rec: dict = {"id": rid, "created": t0, "creature": {"cid": cid, "n": n, "content_hash": version["content_hash"]}, "version": n,
                 "director": director, "mode": mode, "provenance": provenance, "model": model,
                 "budget": {"requested": requested_budget, "total": total, "used": None, **{k: v for k, v in settings.items()}},
                 "seeds": seeds, "seed_index": plan["index"], "family": FAMILY, "scale": scale, "rule": rc.RECOVERY_RULE,
                 "pipeline": None, "director_record": None, "assessment": None, "status": "failed", "candidate": None, "error": None}
    tracker = _Tracker(emit, progress, seeds, settings["screen_n"], total, len(seeds["validate"]), len(seeds["confirm"]),
                       cancelled=cancelled)
    inner = pool or forge_pool.InlinePool()
    cpool = _CountingPool(inner, tracker)
    pipeline_fn = opts.get("pipeline_fn") or wp.run_pipeline
    assess_fn = opts.get("assess_fn") or rc.assess
    try:
        tracker.set_phase("diagnostics", provenance=provenance, director=director)
        out = pipeline_fn(body, dobj, total_budget=total, family=FAMILY,
                          seeds={"diag": seeds["diag"], "train": seeds["train"], "screen": seeds["screen"]},
                          noise_seed=int(hashlib.sha256(rid.encode()).hexdigest()[:8], 16), pool=cpool, probe_budget=settings["probe_budget"],
                          rounds=settings["rounds"], screen_top_k=settings["screen_top_k"], screen_n=settings["screen_n"],
                          director_name=("ai" if director == "ai" else "fix"), log=tracker.log, start_vector=start_vec)
        if cancelled():
            raise JobCancelled()
        final = out["final"]
        rec["pipeline"], rec["budget"]["used"] = out, out["used"]
        rec["director_record"] = dobj.record() if hasattr(dobj, "record") else None
        rec["candidate"] = {"body": final["body"], "vector": final["vector"], "edits": final["edits"], "source": final["source"],
                            "train_score": final["train_score"], "screen": final["screen"]}
        tracker.set_phase("validation")
        assessment = assess_fn({"body": body, "vector": start_vec}, {"body": final["body"], "vector": final["vector"]}, seeds["validate"],
                               seeds["confirm"], pool=cpool)
        rec["assessment"], rec["status"] = assessment, assessment["status"]
        tracker.set_phase("done")
        emit("verdict", {"status": rec["status"], "rule": assessment.get("rule"), "provenance": provenance})
    except (JobCancelled, _Abort):
        rec["status"] = "cancelled"
        rec["director_record"] = rec["director_record"] or (dobj.record() if hasattr(dobj, "record") else None)
    except inv.LiveRefused:
        raise
    except Exception as exc:  # noqa: BLE001 - recorded; the job fails with the public message
        log.warning("recovery %s failed: %s", rid, public_error(exc), exc_info=True)
        rec["status"], rec["error"] = "failed", public_error(exc)
        try:
            rec["director_record"] = rec["director_record"] or (dobj.record() if hasattr(dobj, "record") else None)
        except Exception:  # noqa: BLE001
            pass
    dr = rec.get("director_record") or {}
    ass = rec.get("assessment") or {}
    rec["cost"] = {"usd": round(float(dr.get("cost_usd") or 0.0), 6), "tokens": dr.get("tokens"), "calls": sum(1 for c in dr.get("calls") or []
                                                                                                          if c.get("sent", True)),
                   "pipeline_rollouts": rec["budget"]["used"], "assessment_rollouts": (ass.get("rollouts") or {}) or None}
    rec["code"] = (opts.get("code_fn") or inv.default_code_info)()
    rec["finished"] = now_iso()
    save_recovery(forge_dir, rec)
    return rec


# ------------------------------------------------------------------------------------------------------------------ accept
def build_accept(store, cid: str, rec: dict) -> tuple[int, dict, list, dict, str]:
    """(parent_n, body, vector, change, origin) for accepting recovery `rec` into creature `cid`. Raises RecoveryRefused (409) with the reason
    unless the assessment status is FULL_RECOVERY and the evaluated version is unchanged."""
    if rec["creature"]["cid"] != cid:
        raise RecoveryRefused(f"recovery {rec['id']} belongs to creature {rec['creature']['cid']}, not {cid}")
    ass = rec.get("assessment") or {}
    status = ass.get("status") if rec.get("status") == ass.get("status") else None
    if status != FULL_RECOVERY:
        why = "; ".join(ass.get("reasons") or []) or rec.get("error") or ""
        raise RecoveryRefused(f"recovery {rec['id']} is not accepted: its status is {rec.get('status')}. Only {FULL_RECOVERY} can be accepted "
                              f"(stricter than the {inv.VERIFIED} rule for investigations; a partial improvement is not a recovery)"
                              + (f". Reason: {why}" if why else ""))
    cand = rec.get("candidate") or {}
    if not cand.get("body") or not isinstance(cand.get("vector"), list) or len(cand["vector"]) != 17:
        raise RecoveryRefused(f"recovery {rec['id']} has no complete candidate (body and 17-parameter walking vector)")
    parent = next((v for v in store.get(cid)["versions"] if v["n"] == rec["creature"]["n"]), None)
    if parent is None or parent["content_hash"] != rec["creature"]["content_hash"]:
        raise RecoveryRefused("the creature version this recovery evaluated no longer matches the stored version")
    scripted = rec["provenance"] == "SCRIPTED_MOCK"
    if rec["director"] == "fix":
        source, origin, model = "fix_rule", "baseline_accepted", None
        rationale = "Fixed engineering rule (no model reasoning) chose the probes and plans; CMA-ES fitted the controller and body."
    else:
        source, origin, model = ("scripted_mock" if scripted else "nemotron"), "ai_accepted", rec.get("model")
        diag = next((d.get("diagnosis") for d in (rec.get("director_record") or {}).get("decisions") or [] if d.get("diagnosis")), None)
        rationale = str(diag)[:500] if diag else "director diagnosis unavailable"
    change = {"kind": "recovery", "edits": list(cand.get("edits") or []), "category": "walking_recovery", "rationale": rationale,
              "source": source, "model": model, "director": rec["director"], "recovery_id": rec["id"], "status": FULL_RECOVERY,
              "rule": ass.get("rule"), "provenance": rec["provenance"], "verdict": (ass.get("validation") or {}).get("verdict"),
              "budget": (rec.get("budget") or {}).get("total"), "scale": rec.get("scale")}
    return parent["n"], cand["body"], list(cand["vector"]), jsonable(change), origin


# ------------------------------------------------------------------------------------------------------------------ replay
def replay_inputs(rec: dict, version: dict, arm: str, seed: int) -> tuple[dict, dict, dict]:
    """(body, controllers, spec dict) to replay `arm` ("original" | "candidate") on one validation or confirmation seed under the SAME
    per-seed conditions `recovery.run_walk_seeds` used (variation preset: perturbation, push time, friction; 10 s, or 20 s for confirmation)."""
    from .arena import VARIATION_PRESET, _body_with_friction, _condition
    from .challenges import ChallengeSpec, default_spec
    seeds = rec.get("seeds") or {}
    if arm not in ("original", "candidate"):
        raise ValueError("arm must be 'original' or 'candidate'")
    if seed in (seeds.get("validate") or []):
        duration = rc_duration(False)
    elif seed in (seeds.get("confirm") or []) and arm == "candidate" and ((rec.get("assessment") or {}).get("confirmation") or {}).get("run"):
        duration = rc_duration(True)
    else:
        raise KeyError(seed)
    if arm == "original":
        body, vec = version["body"], original_vector(version)
    else:
        cand = rec.get("candidate") or {}
        if not cand.get("body"):
            raise KeyError("no candidate")
        body, vec = cand["body"], cand["vector"]
    base = ChallengeSpec.from_dict({**default_spec("walk", [seed]).to_dict(), "duration": float(duration)})
    c = _condition(seed, base, VARIATION_PRESET)
    b, _used = _body_with_friction(body, c["friction_factor"])
    spec = ChallengeSpec.from_dict({**base.to_dict(), "seeds": [seed], "perturb": c["perturb"], "push_time": c["push_time"]})
    b = b.as_dict() if hasattr(b, "as_dict") else dict(b)
    controllers = {"stand": None, "walk": {"vector": [float(x) for x in vec], "provenance": {"kind": "custom"}}}
    return b, controllers, spec.to_dict()


def rc_duration(confirm: bool) -> float:
    from . import recovery as rc
    return rc.CONFIRM_DURATION if confirm else rc.TRAIN_DURATION
