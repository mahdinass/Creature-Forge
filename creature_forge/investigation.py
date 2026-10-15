"""Forge Loop orchestration: one investigation round and the bounded loop (contracts sections 6-8).

evidence -> model (`forge_ai.investigate_once`, <= 2 calls) -> arms (accepted AI proposals + one matched-random twin per
proposal + one heuristic + the original) -> Counterfactual Arena (injected) -> verdicts -> investigation record.

Integrity rules kept here:
* MuJoCo decides. This module never computes a verdict, metric or replay; it only forwards the arena's records. If the arena
  errors, the record says so (`status: failed`, `error`); nothing is filled in.
* Provenance: mode `live` -> `LIVE` (needs CREATURE_FORGE_ENABLE_LIVE=1, an API key and ledger headroom, else `LiveRefused`);
  mode `scripted` -> `SCRIPTED_MOCK` (fixture transport, scratch ledger, model name `scripted-fixture`). Every record, arm and
  event carries it; a scripted record can never be labelled LIVE and an accepted scripted arm is attributed `scripted_mock`.
* The loop never accepts anything. Rounds 2+ evaluate the *proposed* body of the previous round's best verified AI arm as a
  hypothetical parent (clearly recorded); such an arm can be accepted only after its hypothetical parent exists as a version.

The arena (S3) and baselines are injected; the defaults import `creature_forge.arena` / `creature_forge.baselines` lazily.
"""
from __future__ import annotations

import dataclasses
import json
import os
import random
import re
import secrets
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from . import interventions as iv
from .creatures import atomic_write_json, content_hash, now_iso, seed_block
from .evidence import build_evidence, leaf_items, leaf_paths
from .forge_ai import ModelConfig, accepted_proposals, investigate_once, make_client
from .inference_ledger import InferenceLedger
from .jobs import JobCancelled, jsonable
from .nebius import estimate_prompt_tokens

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = REPO_ROOT / "experiments" / "forge_loop" / "model_config.json"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "forge_scripted"
PROFILES = ("default", "deep")
MODES = ("live", "scripted")
PROVENANCE = {"live": "LIVE", "scripted": "SCRIPTED_MOCK"}
SCRIPTED_MODEL = "scripted-fixture"
INVESTIGATION_ID_RE = re.compile(r"^i-[0-9a-f]{6,16}$")
DEFAULT_SIZES = {"train": 3, "screen": 12, "validate": 24}
# Null pilot (experiments/forge_loop/null_pilot): stand needs 16 validation seeds to leave INCONCLUSIVE; push is near-deterministic
# per seed, 12 suffice; walk varies most. Validation conditions are varied for push/walk (arena.VARIATION_PRESET).
SIZES_BY_KIND = {"push": {"train": 3, "screen": 6, "validate": 12}, "stand": {"train": 3, "screen": 8, "validate": 16},
                 "walk": {"train": 3, "screen": 12, "validate": 24}}
VARY_VALIDATION = ("push", "walk")
ARENA_PUSH_BISECTION_STEPS = 7   # first live loop (2026-10-15): a real +2.5 N effect was one 2.5 N step and counted as a tie
DEFAULT_RETUNE_BUDGET = 48  # zoo pilot: K=48 (2 ES generations x 8 x 3 train seeds); only used when an AI walk proposal asks for retuning; applied to EVERY arm
RECORD_KEYS = ("id", "created", "mode", "provenance", "creature", "challenge_run_id", "spec", "evidence", "model_calls", "reply",
               "validation", "arms", "seeds", "screening", "selection", "validation_results", "verdicts", "budget", "code",
               "status", "error")
STATUSES = ("done", "model_failed", "no_valid_proposals", "cancelled", "failed")
VERIFIED = "VERIFIED_IMPROVEMENT"
LIVE_PROMPT_TOKENS_ESTIMATE = 6000  # headroom check only; the ledger's own reserve() is the hard gate


class LiveRefused(RuntimeError):
    """Live mode is not allowed right now; the message is the human-readable reason (HTTP 503)."""


class AcceptRefused(ValueError):
    """The requested arm cannot be accepted; the message is the reason (HTTP 409)."""


# ------------------------------------------------------------------------------------------------------------------ config / gates
def new_investigation_id() -> str:
    return "i-" + secrets.token_hex(6)


def load_model_config(profile: str = "default", path: Path | str | None = None) -> ModelConfig:
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of {list(PROFILES)}, got {profile!r}")
    raw = json.loads(Path(path or MODEL_CONFIG_PATH).read_text(encoding="utf-8"))[profile]
    return ModelConfig(model=raw["model"], max_tokens=int(raw["max_tokens"]), temperature=float(raw["temperature"]),
                       reasoning_effort=raw.get("reasoning_effort"), extra_body=raw.get("extra_body"),
                       json_schema=bool(raw.get("json_schema", True)), timeout_s=float(raw.get("timeout_s", 180))).validate()


def model_summary(path: Path | str | None = None) -> dict | None:
    """For GET /status: the selected model settings (no secrets). None if the file cannot be read."""
    try:
        raw = json.loads(Path(path or MODEL_CONFIG_PATH).read_text(encoding="utf-8"))
        return {"model": raw["default"]["model"], "selected": raw.get("selected"),
                "profiles": {p: {k: raw[p].get(k) for k in ("model", "max_tokens", "temperature", "reasoning_effort", "json_schema")}
                             for p in PROFILES if p in raw}}
    except (OSError, ValueError, KeyError):
        return None


def api_key_present() -> bool:
    from .config import load_env, nebius_api_key
    load_env()
    return bool(nebius_api_key())


def live_refusal(ledger: InferenceLedger | None, cfg: ModelConfig) -> str | None:
    """None if a live call may be attempted, else the reason. Checks the env flag, an API key and ledger headroom for one worst-case request."""
    if os.environ.get("CREATURE_FORGE_ENABLE_LIVE") != "1":
        return "live mode is disabled: set CREATURE_FORGE_ENABLE_LIVE=1 to allow real model calls"
    if not api_key_present():
        return "live mode needs an API key (NEBIUS_API_KEY is not set)"
    if ledger is None:
        return "live mode needs an inference ledger"
    try:
        st = ledger.status()
        pp, pc = ledger.price_for(cfg.model)
    except Exception as exc:  # noqa: BLE001 - fail closed with the reason
        return f"inference ledger unavailable: {type(exc).__name__}: {exc}"
    caps = st["caps"]
    if st["requests"] + 1 > caps["requests"]:
        return f"ledger request cap {caps['requests']} reached"
    worst = LIVE_PROMPT_TOKENS_ESTIMATE * pp + cfg.max_tokens * pc
    if st["usd"] + worst > caps["usd"] + 1e-12:
        return f"ledger spend cap ${caps['usd']:.2f} has no headroom for one more request (${st['usd']:.4f} used)"
    return None


def scripted_ledger(forge_dir: Path) -> InferenceLedger:
    """Scratch ledger for scripted runs: free, separate from the real one so mocks never count as spend or LIVE requests."""
    return InferenceLedger(Path(forge_dir) / "scripted_inference_ledger.jsonl", prices={SCRIPTED_MODEL: (0.0, 0.0)})


# ------------------------------------------------------------------------------------------------------------------ scripted transport
class ScriptedTransport:
    """Fixture transport: answers every request with a stored reply template adapted to THIS evidence's real citable paths and to edits
    that validate for THIS creature. Nothing here is a model. If no candidate edit validates, the first one is kept and the normal
    validator rejects it with its reason."""

    def __init__(self, evidence: dict, version: dict, kind: str, fixture_dir: Path | str | None = None):
        self.evidence, self.version, self.kind = evidence, version, kind
        self.template = json.loads((Path(fixture_dir or FIXTURE_DIR) / f"{kind}.json").read_text(encoding="utf-8"))
        self.requests = 0

    def _cite(self, hints: list[str]) -> list[str]:
        paths = leaf_paths(self.evidence)
        have = set(paths)
        out: list[str] = []
        for h in hints:
            if h in have:
                out.append(h)
                continue
            tail = h.split(".")[-1]
            match = [p for p in paths if p.split(".")[-1] == tail]
            if match:
                out.append(match[0])
        out = list(dict.fromkeys(out))[:6]
        if not out:
            out = [p for p, v in leaf_items(self.evidence) if isinstance(v, (int, float)) and not isinstance(v, bool)][:2]
        return out

    def _edits(self, candidates: list) -> list[dict]:
        for cand in candidates:
            ok, why = iv.validate_edits(self.version, self.kind, cand)
            if ok and not why:
                return cand
        return candidates[0]

    def reply(self) -> dict:
        t = self.template
        hyps = [{"id": h["id"], "mechanism": h["mechanism"], "evidence": self._cite(h.get("evidence_hints", [])),
                 "competing": list(h.get("competing", []))} for h in t["hypotheses"]]
        props = []
        for p in t["proposals"]:
            edits = self._edits(p["edits_candidates"])
            try:
                cat = iv.category([iv.Edit.from_dict(e) for e in edits])
            except (ValueError, KeyError):
                cat = p.get("category", "morphology")
            props.append({"id": p["id"], "hypothesis": p["hypothesis"], "category": cat, "edits": edits,
                          "retune_controller": bool(p.get("retune_controller", False)), "prediction": dict(p["prediction"]),
                          "tradeoffs": p.get("tradeoffs", ""), "confidence": float(p.get("confidence", 0.5)),
                          "verification": p.get("verification", "")})
        return {"diagnosis": {"summary": t["summary"], "hypotheses": hyps}, "proposals": props}

    def __call__(self, url, headers, body, timeout):
        self.requests += 1
        content = json.dumps(self.reply())
        pt = estimate_prompt_tokens(body.get("messages", []))
        ct = max(1, len(content) // 3)
        raw = {"model": SCRIPTED_MODEL, "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
               "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct}}
        return 200, {"x-request-id": f"scripted-{self.requests}"}, raw


def default_client_factory(cfg: ModelConfig, *, mode: str, max_requests: int = 2, evidence: dict | None = None,
                           version: dict | None = None, challenge_kind: str | None = None, fixture_dir=None, **_ignored):
    """Client for one investigation round. Live: the real Nebius client (limits sized for cfg.max_tokens). Scripted: fixture transport."""
    if mode == "scripted":
        tr = ScriptedTransport(evidence or {}, version or {}, challenge_kind or "push", fixture_dir)
        return make_client(cfg, transport=tr, api_key="scripted-no-key", base_url="http://scripted.invalid", max_requests=max_requests)
    return make_client(cfg, max_requests=max_requests)


# ------------------------------------------------------------------------------------------------------------------ small helpers
def _edit_dicts(edits) -> list[dict]:
    return [e.to_dict() if hasattr(e, "to_dict") else dict(e) for e in (edits or [])]


def _edit_objs(dicts: list[dict]) -> list:
    return [iv.Edit.from_dict(d) for d in dicts]


def default_code_info() -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=20).stdout.strip())
        return {"commit": commit or None, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}


def _default_baselines() -> dict:
    from . import baselines  # lazy: owned by another module
    from .arena import seed_sets
    return {"matched_random": baselines.matched_random, "heuristic": baselines.heuristic, "seed_sets": seed_sets,
            "make_rng": baselines.make_rng}


def _default_arena():
    from .arena import ArenaConfig, run_arena  # lazy: owned by another module
    return run_arena, ArenaConfig


def _arena_config(arena_cls, seeds: dict, retune_budget: int, kind: str | None = None):
    kw = {"screen_seeds": tuple(seeds["screen"]), "validate_seeds": tuple(seeds["validate"]), "train_seeds": tuple(seeds["train"]),
          "retune_budget": retune_budget}
    if arena_cls is not None and kind in VARY_VALIDATION:
        from .arena import VARIATION_PRESET
        kw["validation_variation"] = dict(VARIATION_PRESET)
    return arena_cls(**kw) if arena_cls is not None else SimpleNamespace(**kw)


def _load_run(forge_dir: Path, run_id: str) -> dict:
    return json.loads((Path(forge_dir) / "runs" / f"{run_id}.json").read_text(encoding="utf-8"))


def investigation_path(forge_dir: Path, iid: str) -> Path:
    if not INVESTIGATION_ID_RE.match(iid or ""):
        raise KeyError(iid)
    return Path(forge_dir) / "investigations" / f"{iid}.json"


def load_investigation(forge_dir: Path, iid: str) -> dict:
    try:
        return json.loads(investigation_path(forge_dir, iid).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise KeyError(iid) from None


def summarize(rec: dict) -> dict:
    verdicts = rec.get("verdicts") or {}
    return {"id": rec["id"], "created": rec["created"], "mode": rec["mode"], "provenance": rec["provenance"], "creature": rec["creature"],
            "challenge_run_id": rec["challenge_run_id"], "status": rec["status"], "error": rec.get("error"),
            "n_arms": len(rec.get("arms") or []),
            "verdicts": {a: (v or {}).get("status") for a, v in verdicts.items()}, "budget": rec.get("budget")}


def list_investigations(forge_dir: Path, cid: str | None = None) -> list[dict]:
    d = Path(forge_dir) / "investigations"
    out = []
    for p in sorted(d.glob("i-*.json")) if d.is_dir() else []:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            if cid is None or rec["creature"]["cid"] == cid:
                out.append(summarize(rec))
        except (OSError, ValueError, KeyError):
            continue
    out.sort(key=lambda s: (s["created"], s["id"]), reverse=True)
    return out


def materialize_arm(version: dict, arm: dict) -> tuple[dict, dict]:
    """(body, controllers) of an arm: the arena's stored materials if present, else the edits re-applied to the parent version."""
    if isinstance(arm.get("body"), dict) and isinstance(arm.get("controllers"), dict):
        return arm["body"], arm["controllers"]
    body, ctrl = iv.apply_edits(version, _edit_objs(arm.get("edits") or []))
    return body, ctrl


def _arm_summary(arm: dict) -> str:
    return "; ".join(f"{e['param']} {e['op']} {e['value']:g} ({e.get('target', 'both')})" for e in arm.get("edits") or []) or "no edits"


def best_verified_ai_arm(rec: dict) -> dict | None:
    """The AI arm with a VERIFIED_IMPROVEMENT verdict and the largest median paired difference (None if there is none)."""
    best, best_d = None, None
    for arm in rec.get("arms") or []:
        v = (rec.get("verdicts") or {}).get(arm.get("arm_id")) or {}
        if arm.get("source") not in ("nemotron", "scripted_mock") or v.get("status") != VERIFIED:
            continue
        d = v.get("median_diff")
        d = float(d) if isinstance(d, (int, float)) else 0.0
        if best is None or d > best_d:
            best, best_d = arm, d
    return best


def history_entry(round_: int, arm: dict, verdict: dict | None) -> dict:
    v = verdict or {}
    return {"round": round_, "proposal": f"{arm.get('arm_id')}: {_arm_summary(arm)}", "verdict": v.get("status"),
            "effect": v.get("median_diff")}


# ------------------------------------------------------------------------------------------------------------------ one investigation
def _build_arms(version: dict, kind: str, iid: str, accepted: list[dict], challenge_result: dict, fns: dict,
                ai_source: str = "nemotron") -> list[dict]:
    retune = any(p.get("retune_controller") for p in accepted)
    arms = [{"arm_id": "original", "source": "original", "proposal_id": None, "edits": [], "retune": retune}]
    for p in accepted:
        arms.append({"arm_id": f"ai:{p['id']}", "source": ai_source, "proposal_id": p["id"], "edits": list(p["edits"]), "retune": retune,
                     "hypothesis": p.get("hypothesis"), "category": p.get("category")})
    for p in accepted:
        arm = {"arm_id": f"random:{p['id']}", "source": "random_baseline", "proposal_id": p["id"], "edits": [], "retune": retune}
        rng = fns["make_rng"](iid, p["id"]) if "make_rng" in fns else random.Random(f"{iid}:{p['id']}")
        try:
            edits = fns["matched_random"](version, kind, _edit_objs(p["edits"]), rng)
        except Exception as exc:  # noqa: BLE001 - recorded, never hidden
            edits, arm["unavailable"] = None, f"matched_random failed: {type(exc).__name__}: {exc}"
        if edits:
            arm["edits"] = _edit_dicts(edits)
            arm["category"] = iv.category(_edit_objs(arm["edits"]))
        else:
            arm.setdefault("unavailable", "no matched-random twin could be drawn within the bounds")
        arms.append(arm)
    harm = {"arm_id": "heuristic", "source": "heuristic", "proposal_id": None, "edits": [], "retune": retune}
    try:
        edits = fns["heuristic"](version, kind, challenge_result)
    except Exception as exc:  # noqa: BLE001
        edits, harm["unavailable"] = None, f"heuristic failed: {type(exc).__name__}: {exc}"
    if edits:
        harm["edits"] = _edit_dicts(edits)
        harm["category"] = iv.category(_edit_objs(harm["edits"]))
    else:
        harm.setdefault("unavailable", "the heuristic rule table has no rule for this evidence")
    arms.append(harm)
    return arms


def _disjoint_seed_sets(fn: Callable, cid: str, n: int, round_: int, sizes: dict, avoid: set) -> tuple[dict, int]:
    for salt in range(10):
        used = round_ + 1000 * salt
        out = fn(cid, n, used, sizes)
        blocks = out["seeds"] if isinstance(out, dict) and "seeds" in out else out
        sets = {k: tuple(v) for k, v in blocks.items()}
        flat = [s for v in sets.values() for s in v]
        if len(set(flat)) == len(flat) and not (set(flat) & avoid):
            return sets, used
    raise RuntimeError("could not find train/screen/validate seed blocks disjoint from each other and from the challenge seeds")


def run_investigation(store, cid: str, n: int, run_id: str, *, mode: str, forge_dir, client_factory: Callable | None = None,
                      ledger: InferenceLedger | None = None, cfg: ModelConfig | None = None, pool=None, emit: Callable | None = None,
                      progress: Callable | None = None, cancelled: Callable[[], bool] | None = None, arena_runner: Callable | None = None,
                      baseline_fns: dict | None = None, history: list | None = None, round: int = 1,  # noqa: A002 - contract name
                      investigation_id: str | None = None, profile: str = "default", model_config_path=None, sizes: dict | None = None,
                      parent: dict | None = None, loop_id: str | None = None, code_fn: Callable | None = None,
                      max_requests: int = 2, fixture_dir=None, retune_budget: int = DEFAULT_RETUNE_BUDGET) -> dict:
    """One investigation round on stored creature version (cid, n) and stored challenge run `run_id`. Returns the saved record.

    `parent` (rounds 2+ of the loop): {"version": <hypothetical parent version dict>, "from": {"investigation_id", "arm_id"}}; the run
    `run_id` must then be a challenge run of THAT body. `arena_runner(version, kind, arms, cfg, *, pool, progress, emit, spec_overrides)`
    defaults to `arena.run_arena`; `baseline_fns` = {"matched_random", "heuristic", "seed_sets"} defaults to S3's functions.
    `client_factory(cfg, *, mode, max_requests, evidence, version, challenge_kind)` defaults to `default_client_factory`.
    Raises LiveRefused (nothing written, no transport call) when live mode is not allowed."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {list(MODES)}, got {mode!r}")
    forge_dir = Path(forge_dir)
    provenance = PROVENANCE[mode]
    iid = investigation_id or new_investigation_id()
    cfg = cfg or load_model_config(profile, model_config_path)
    if mode == "live":
        reason = live_refusal(ledger, cfg)
        if reason:
            raise LiveRefused(reason)
        use_ledger = ledger
    else:
        cfg = dataclasses.replace(cfg, model=SCRIPTED_MODEL)
        use_ledger = scripted_ledger(forge_dir)
    t0 = time.monotonic()
    seen: set = set()

    def ev(type_: str, data: dict | None = None) -> None:
        seen.add(type_)
        if emit:
            emit(type_, {**(data or {}), "provenance": provenance, "investigation_id": iid})

    def prog(done=0, total=0, *_a) -> None:
        if progress:
            progress(done, total, "arena")

    def check() -> None:
        if cancelled and cancelled():
            raise JobCancelled()

    version = (parent or {}).get("version") or store.version(cid, n)
    run = _load_run(forge_dir, run_id)
    spec = run["spec"]
    kind = spec["kind"]
    rec = {"id": iid, "created": now_iso(), "mode": mode, "provenance": provenance,
           "creature": {"cid": cid, "n": n, "content_hash": version["content_hash"], "round": round,
                        "hypothetical_parent": (parent or {}).get("from"), "loop_id": loop_id},
           "challenge_run_id": run_id, "spec": spec, "evidence": None, "model_calls": [], "reply": None, "validation": None, "arms": [],
           "seeds": {}, "screening": None, "selection": None, "validation_results": None, "verdicts": {},
           "budget": {"rollouts": 0, "wall_s": 0.0, "calls": 0, "tokens": 0, "usd": 0.0}, "code": (code_fn or default_code_info)(),
           "status": "failed", "error": None}
    fns = baseline_fns
    try:
        ev("phase", {"phase": "evidence", "kind": kind, "round": round})
        check()
        evidence = build_evidence(version, run, history)
        factory = client_factory or default_client_factory
        client = factory(cfg, mode=mode, max_requests=max_requests, evidence=evidence, version=version, challenge_kind=kind,
                         **({"fixture_dir": fixture_dir} if (client_factory is None and fixture_dir) else {}))
        ev("model_request", {"model": cfg.model, "max_tokens": cfg.max_tokens, "temperature": cfg.temperature, "profile": profile,
                             "evidence_bytes": len(json.dumps(evidence, separators=(",", ":")))})
        out = investigate_once(client, cfg, version, run, history, use_ledger, investigation_id=iid)
        rec.update(evidence=out["evidence"], model_calls=out["calls"], reply=out["reply"], validation=out["validation"])
        for c in out["calls"]:
            ev("model_response", {"request_id": c.get("request_id"), "ok": c.get("ok"), "finish_reason": c.get("finish_reason"),
                                  "latency_s": c.get("latency_s"), "usage": c.get("usage"), "cost_usd": c.get("cost_usd"),
                                  "error": c.get("error"), "model": c.get("model")})
        accepted = accepted_proposals(out["validation"])
        ev("validation", {"status": out["status"], "repaired": out["repaired"], "error": out["error"],
                          "proposals": [{"id": p["id"], "status": p["status"], "reasons": p["reasons"]}
                                        for p in ((out["validation"] or {}).get("proposals") or [])]})
        model_status = {"ok": "done", "no_valid_proposal": "no_valid_proposals", "model_failed": "model_failed"}[out["status"]]
        rec["status"], rec["error"] = model_status, out["error"]
        check()

        ev("phase", {"phase": "arms", "ai_arms": len(accepted)})
        fns = fns or _default_baselines()
        arms = _build_arms(version, kind, iid, accepted, run, fns, "nemotron" if mode == "live" else "scripted_mock")
        rec["arms"] = [{**a, "provenance": provenance} for a in arms]
        runnable = [a for a in arms if not a.get("unavailable")]
        if len(runnable) <= 1:  # only the original: nothing to compare
            rec["error"] = (rec["error"] + "; " if rec["error"] else "") + "no comparable arm could be built; the arena was not run"
            return _finish(rec, forge_dir, t0)
        avoid = set(spec.get("seeds") or [])
        sets, used_round = _disjoint_seed_sets(fns["seed_sets"], cid, n, round, sizes or SIZES_BY_KIND.get(kind, DEFAULT_SIZES), avoid)
        rec["seeds"] = {**{k: list(v) for k, v in sets.items()}, "round_used": used_round}
        rb = retune_budget if any(a["retune"] for a in arms) else 0
        if arena_runner is None:
            arena_runner, arena_cls = _default_arena()
        else:
            arena_cls = None
        acfg = _arena_config(arena_cls, sets, rb, kind)
        overrides = {k: v for k, v in spec.items() if k not in ("kind", "seeds")}
        if kind == "push":   # finer, identical measurement for every arm: 0.625 N steps so a +2.5 N effect is not a tie
            overrides["bisection_steps"] = ARENA_PUSH_BISECTION_STEPS
        ev("phase", {"phase": "arena", "arms": [a["arm_id"] for a in runnable], "retune_budget": rb})
        check()
        arena_arms = [{k: a.get(k) for k in ("arm_id", "source", "proposal_id", "edits", "retune")} for a in runnable]
        try:
            res = arena_runner(version, kind, arena_arms, acfg, pool=pool, progress=prog, emit=ev, spec_overrides=overrides)
        except JobCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - the record states it; nothing is substituted
            rec["status"] = "failed"
            rec["error"] = f"arena failed: {type(exc).__name__}: {exc}"
            return _finish(rec, forge_dir, t0)
        _merge_arena(rec, res, provenance)
        for arm in rec["arms"]:
            if "arm_result" not in seen and not arm.get("unavailable"):
                ev("arm_result", {"arm_id": arm["arm_id"], "source": arm["source"], "edits": arm["edits"]})
        for arm_id, v in rec["verdicts"].items():
            if "verdict" not in seen:
                ev("verdict", {"arm_id": arm_id, "status": (v or {}).get("status")})
        return _finish(rec, forge_dir, t0)
    except JobCancelled:
        rec["status"], rec["error"] = "cancelled", "cancelled by the user"
        _finish(rec, forge_dir, t0)
        return rec
    except Exception as exc:  # noqa: BLE001
        rec["status"], rec["error"] = "failed", f"{type(exc).__name__}: {exc}"
        ev("error", {"message": rec["error"]})
        _finish(rec, forge_dir, t0)
        return rec


def _merge_arena(rec: dict, res: dict, provenance: str) -> None:
    by_id = {a.get("arm_id"): a for a in (res.get("arms") or []) if isinstance(a, dict)}
    rec["arms"] = [a if a.get("unavailable") else {**a, **by_id.get(a["arm_id"], {}), "provenance": provenance} for a in rec["arms"]]
    rec["screening"], rec["selection"], rec["validation_results"] = res.get("screening"), res.get("selection"), res.get("validation")
    src = {a["arm_id"]: a["source"] for a in rec["arms"]}
    rec["verdicts"] = {k: {**(v or {}), "source": src.get(k), "provenance": provenance} for k, v in (res.get("verdicts") or {}).items()}
    r = res.get("rollouts") or 0   # arena: {"per_arm": {...}, "total": int}; fakes may give an int
    rec["budget"]["rollouts"] = int(r.get("total", 0) if isinstance(r, dict) else r)


def _finish(rec: dict, forge_dir: Path, t0: float) -> dict:
    calls = rec.get("model_calls") or []
    tokens = sum(int((c.get("usage") or {}).get("total_tokens") or ((c.get("usage") or {}).get("prompt_tokens") or 0)
                     + ((c.get("usage") or {}).get("completion_tokens") or 0)) for c in calls)
    rec["budget"].update(wall_s=round(time.monotonic() - t0, 3), calls=sum(1 for c in calls if c.get("sent")), tokens=tokens,
                         usd=round(sum(float(c.get("cost_usd") or 0) for c in calls), 6))
    missing = [k for k in RECORD_KEYS if k not in rec]
    assert not missing, missing
    atomic_write_json(investigation_path(forge_dir, rec["id"]), jsonable({k: rec[k] for k in RECORD_KEYS}))
    return rec


# ------------------------------------------------------------------------------------------------------------------ accept
def build_accept(store, cid: str, rec: dict, arm_id: str) -> tuple[int, dict, dict, dict]:
    """(parent_n, body, controllers, change) for accepting `arm_id` of investigation `rec`. Raises AcceptRefused (409) with the reason
    unless the arm's verdict is VERIFIED_IMPROVEMENT. Random/heuristic arms are accepted but attributed to what they are."""
    if rec["creature"]["cid"] != cid:
        raise AcceptRefused(f"investigation {rec['id']} belongs to creature {rec['creature']['cid']}, not {cid}")
    arm = next((a for a in rec.get("arms") or [] if a.get("arm_id") == arm_id), None)
    if arm is None or arm.get("unavailable"):
        raise AcceptRefused(f"no such arm in this investigation: {arm_id}" if arm is None else f"arm {arm_id} was not run: {arm['unavailable']}")
    verdict = (rec.get("verdicts") or {}).get(arm_id)
    status = (verdict or {}).get("status")
    if status != VERIFIED:
        raise AcceptRefused(f"arm {arm_id} is not accepted: its verdict is {status or 'missing'}, only {VERIFIED} can be accepted")
    created = store.get(cid)
    if rec["creature"].get("hypothetical_parent"):
        parent = next((v for v in created["versions"] if v["content_hash"] == rec["creature"]["content_hash"]), None)
        if parent is None:
            raise AcceptRefused("this arm was verified against a hypothetical parent (an earlier round's unaccepted proposal); accept that "
                                "earlier arm first, then this one, or run a new investigation on the resulting version")
    else:
        parent = next((v for v in created["versions"] if v["n"] == rec["creature"]["n"]), None)
        if parent is None or parent["content_hash"] != rec["creature"]["content_hash"]:
            raise AcceptRefused("the creature version this investigation evaluated no longer matches the stored version")
    body, controllers = materialize_arm(parent, arm)
    scripted = rec["provenance"] != "LIVE"
    source = arm["source"]
    if source in ("nemotron", "scripted_mock"):
        mech = next((h.get("mechanism") for h in (rec.get("validation") or {}).get("hypotheses", []) if h.get("id") == arm.get("hypothesis")), None)
        rationale = mech or "model hypothesis text unavailable"
        source = "scripted_mock" if scripted else "nemotron"
        model = (rec.get("model_calls") or [{}])[0].get("model")
    elif source == "random_baseline":
        rationale = f"Matched-random baseline edit (no model reasoning), twin of {arm.get('proposal_id')}."
        model = None
    else:
        rationale = "Heuristic rule-table edit (no model reasoning)."
        model = None
    edits = list(arm.get("edits") or [])
    change = {"edits": edits, "category": iv.category(_edit_objs(edits)), "rationale": rationale, "source": source, "model": model,
              "investigation_id": rec["id"], "arm_id": arm_id, "verdict": verdict, "provenance": rec["provenance"],
              "round": rec["creature"].get("round", 1)}
    return parent["n"], body, controllers, change


# ------------------------------------------------------------------------------------------------------------------ bounded loop
@dataclasses.dataclass(frozen=True)
class LoopLimits:
    max_rounds: int = 3
    max_rollouts: int = 3000
    max_calls: int = 4
    wall_s: float = 600.0
    patience: int = 2   # stop after this many CONSECUTIVE rounds without a verified AI arm (failures feed the next round)


def default_challenge_runner(pool=None) -> Callable:
    """challenge_runner(body, controllers, spec_dict, progress) -> ChallengeResult dict (lazy import of challenges)."""
    def run(body: dict, controllers: dict, spec_dict: dict, progress) -> dict:
        from . import challenges
        from .studio.forge_api import _sandbox_body
        res = challenges.run_challenge(_sandbox_body(body), controllers, challenges.ChallengeSpec.from_dict(spec_dict), pool=pool,
                                       progress=progress)
        return dataclasses.asdict(res) if dataclasses.is_dataclass(res) else res
    return run


def run_loop(store, cid: str, n: int, run_id: str, *, mode: str, forge_dir, limits: LoopLimits | None = None,
             challenge_runner: Callable | None = None, investigation_id: str | None = None, clock: Callable[[], float] = time.monotonic,
             emit: Callable | None = None, progress: Callable | None = None, cancelled: Callable[[], bool] | None = None, pool=None,
             **kw) -> dict:
    """Up to `limits.max_rounds` investigations with the earlier rounds as evidence history. After a round with a verified AI arm, round
    k+1 evaluates that PROPOSED body as a hypothetical parent. After a round without one, the falsified AI proposals and their measured
    verdicts are added to the history and the same design is investigated again, until `limits.patience` consecutive rounds failed.
    Also stops on the rollout / model-call / wall-clock limits, a round that did not finish `done`, or cancellation. NEVER accepts
    anything: the user accepts explicitly."""
    lim = limits or LoopLimits()
    forge_dir = Path(forge_dir)
    loop_id = "l-" + secrets.token_hex(4)
    provenance = PROVENANCE[mode]
    t0 = clock()
    rounds: list[dict] = []
    history: list[dict] = []
    totals = {"rollouts": 0, "calls": 0}
    cur_run, parent, stop, misses = run_id, None, None, 0
    for r in range(1, lim.max_rounds + 1):
        if cancelled and cancelled():
            stop = "cancelled"
        elif r > 1 and totals["rollouts"] >= lim.max_rollouts:
            stop = "max_rollouts"
        elif totals["calls"] >= lim.max_calls:
            stop = "max_model_calls"
        elif clock() - t0 >= lim.wall_s:
            stop = "wall_clock"
        if stop:
            break
        rec = run_investigation(store, cid, n, cur_run, mode=mode, forge_dir=forge_dir, emit=emit, progress=progress, cancelled=cancelled,
                                pool=pool, history=list(history) or None, round=r, parent=parent, loop_id=loop_id,
                                investigation_id=investigation_id if r == 1 else None,
                                max_requests=min(2, lim.max_calls - totals["calls"]), **kw)
        totals["rollouts"] += rec["budget"]["rollouts"]
        totals["calls"] += rec["budget"]["calls"]
        best = best_verified_ai_arm(rec)
        rounds.append({"round": r, "investigation_id": rec["id"], "status": rec["status"], "run_id": cur_run,
                       "hypothetical_parent": rec["creature"]["hypothetical_parent"],
                       "best_verified_arm": best["arm_id"] if best else None,
                       "best_verdict": (rec["verdicts"].get(best["arm_id"]) if best else None)})
        if rec["status"] == "cancelled":
            stop = "cancelled"
        elif rec["status"] != "done":
            stop = f"round_status:{rec['status']}"
        elif best is None:
            misses += 1
            if misses >= lim.patience:
                stop = "no_verified_arm"
        elif r == lim.max_rounds:
            stop = "max_rounds"
        if not stop and r == lim.max_rounds:
            stop = "max_rounds"
        if stop:
            break
        if best is None:
            # Learn from the falsified proposals: same design, same challenge run, fresh arena seeds (round-salted) next round.
            for arm in rec["arms"]:
                if arm.get("source") in ("nemotron", "scripted_mock") and not arm.get("unavailable"):
                    history.append(history_entry(r, arm, rec["verdicts"].get(arm["arm_id"])))
            continue
        misses = 0
        history.append(history_entry(r, best, rec["verdicts"].get(best["arm_id"])))
        base = (parent or {}).get("version") or store.version(cid, n)
        body, ctrl = materialize_arm(base, best)
        hyp = {**base, "body": body, "controllers": ctrl, "content_hash": content_hash(body, ctrl)}
        # Fresh challenge run of the hypothetical body (re-simulated; evidence for the next round).
        runner = challenge_runner or default_challenge_runner(pool)
        k = len(run_from(forge_dir, cur_run)["spec"]["seeds"])
        seeds = seed_block(cid, n, 100 + r, "challenge", k)
        new_spec = {**run_from(forge_dir, cur_run)["spec"], "seeds": list(seeds)}
        try:
            result = runner(body, ctrl, new_spec, lambda d=0, t=0, *_: progress(d, t, "challenge") if progress else None)
        except JobCancelled:
            stop = "cancelled"
            break
        cur_run = "r-" + secrets.token_hex(4)
        totals["rollouts"] += int(result.get("rollouts") or 0)
        atomic_write_json(forge_dir / "runs" / f"{cur_run}.json", jsonable({
            **result, "run_id": cur_run, "created": now_iso(), "controllers": ctrl, "body": body, "spec": result.get("spec") or new_spec,
            "creature": {"cid": cid, "n": n, "content_hash": hyp["content_hash"], "hypothetical": True,
                         "from": {"investigation_id": rec["id"], "arm_id": best["arm_id"]}}}))
        parent = {"version": hyp, "from": {"investigation_id": rec["id"], "arm_id": best["arm_id"]}}
    if cancelled and cancelled() and stop is None:
        stop = "cancelled"
    verified = [x for x in rounds if x["best_verified_arm"]]
    return {"loop_id": loop_id, "mode": mode, "provenance": provenance, "rounds": rounds, "stop_reason": stop or "max_rounds",
            "best": verified[-1] if verified else None, "budget": {**totals, "wall_s": round(clock() - t0, 3)},
            "auto_accepted": False,
            "note": "The loop never accepts a design. Rounds after the first evaluate a proposed, not yet accepted, body as a hypothetical parent."}


def run_from(forge_dir: Path, run_id: str) -> dict:
    return _load_run(forge_dir, run_id)

