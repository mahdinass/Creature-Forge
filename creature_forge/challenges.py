"""Challenges for user-drawn creatures: stand, push and walk (contracts section 3).

Every number here comes from a MuJoCo rollout; nothing is estimated or model-written. A challenge runs one deterministic
job per seed (`run_seed`, a pure function of its arguments) and aggregates the per-seed results.

  stand  the Phase 0 PD controller (`GaitParams` defaults) holds the creature for `duration`; score = survival time (s).
  push   the same controller; per seed and per direction the critical push force is found by bisection (5 steps in
         [0, max_force]); score = min(forward, backward) critical force (N).
  walk   a 15-D walking controller (default: the R2 winner, "r2-transfer") on `creature_walk.rollout` with
         body-scaled criteria; score = forward distance (m) while upright, 0 unless gait-valid.

The drawn pose is only the start configuration; the controller never targets it. Failure rules ignore `t < settle_s`
because drawings may lean by up to 1.5 rad (the stock detector would call that a fall at t = 0).
"""
from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from typing import Literal, Sequence

import numpy as np

from . import creature_walk as cw
from .contact import replay as contact_replay
from .controller import GaitParams
from .failures import SAMPLE_DT, FailureEvent, _first_sustained, detect_failures
from .forensics import build_forensics
from .forge_pool import InlinePool, is_error
from .locomotion import PERTURB as WALK_PERTURB
from .locomotion import compute_metrics
from .optimize import jsonable
from .phasegait_init import controller_from_vector
from .render_export import export_scene, mj_to_three_pos, mj_to_three_quat, payload_from_telemetry
from .sandbox import SandboxBody
from .simulate import Push, run_rollout
from .morphology import build_model

KINDS = ("stand", "push", "walk")
OUTCOMES = ("PASS", "POOR", "FAIL", "ERROR")
DEFAULT_DURATION = {"stand": 8.0, "push": 5.0, "walk": 10.0}
STAND_POOR_PITCH = 0.5           # rad
STAND_POOR_HEIGHT = 0.7          # fraction of the starting torso height
PUSH_POOR_FRACTION = 0.6
PUSH_BISECTION_STEPS = 5
PUSH_JITTER_S = 0.1
FALL_PITCH = 1.0                 # same numbers as failures.detect_failures
FALL_HEIGHT_FRAC = 0.5
FALL_SUSTAIN_S = 0.1
NAN_OK = ("support_x_min", "support_x_max", "cop_x")    # NaN means "no foot loaded"


class ChallengeError(ValueError):
    """The challenge cannot be run; the message says why."""


# ---------------------------------------------------------------------------------------------------------
# spec
# ---------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ChallengeSpec:
    kind: Literal["stand", "push", "walk"]
    seeds: tuple[int, ...]
    duration: float
    perturb: float = 0.02
    target_force: float = 10.0          # N; backward pushes are the weak direction of this planar model (pilot: default robot 32.5 N fwd, 10 N bwd)
    push_time: float = 1.0
    push_duration: float = 0.15
    max_force: float = 80.0
    start: Literal["drawn", "neutral"] = "drawn"
    settle_s: float = 0.3
    bisection_steps: int = PUSH_BISECTION_STEPS   # push: resolution = max_force / 2**steps (5 -> 2.5 N, 7 -> 0.625 N)

    def __post_init__(self):
        object.__setattr__(self, "seeds", tuple(self.seeds))
        self.validate()

    def validate(self) -> "ChallengeSpec":
        def num(name, v, lo, hi):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not (lo <= v <= hi):
                raise ValueError(f"{name}={v!r} must be a finite number in [{lo:g}, {hi:g}]")
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {self.kind!r}")
        if not self.seeds:
            raise ValueError("seeds must not be empty")
        for s in self.seeds:
            if isinstance(s, bool) or not isinstance(s, (int, np.integer)) or s < 0:
                raise ValueError(f"seeds must be non-negative integers, got {s!r}")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be distinct")
        num("duration", self.duration, 1.0, 60.0)
        num("perturb", self.perturb, 0.0, 0.2)
        num("target_force", self.target_force, 0.1, 500.0)
        num("push_time", self.push_time, 0.0, 30.0)
        num("push_duration", self.push_duration, 0.01, 2.0)
        num("max_force", self.max_force, 0.1, 500.0)
        num("settle_s", self.settle_s, 0.0, 5.0)
        if isinstance(self.bisection_steps, bool) or not isinstance(self.bisection_steps, (int, np.integer)) or not 3 <= self.bisection_steps <= 9:
            raise ValueError(f"bisection_steps={self.bisection_steps!r} must be an integer in [3, 9]")
        if self.start not in ("drawn", "neutral"):
            raise ValueError(f"start must be 'drawn' or 'neutral', got {self.start!r}")
        if self.settle_s >= self.duration:
            raise ValueError("settle_s must be shorter than duration")
        if self.kind == "push":
            if self.max_force < self.target_force:
                raise ValueError("max_force must be at least target_force")
            if self.push_time + PUSH_JITTER_S + self.push_duration + 0.5 > self.duration:
                raise ValueError("the push must end at least 0.5 s before the episode does")
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d["seeds"] = [int(s) for s in self.seeds]
        return d

    @staticmethod
    def from_dict(d: dict) -> "ChallengeSpec":
        if not isinstance(d, dict):
            raise ValueError("a challenge spec must be an object")
        allowed = {"kind", "seeds", "duration", "perturb", "target_force", "push_time", "push_duration", "max_force",
                   "start", "settle_s", "bisection_steps"}
        extra = sorted(set(d) - allowed)
        if extra:
            raise ValueError(f"unknown challenge field(s): {', '.join(extra)}")
        if "kind" not in d or "seeds" not in d:
            raise ValueError("a challenge spec needs 'kind' and 'seeds'")
        base = default_spec(d["kind"], list(d["seeds"])) if d["kind"] in KINDS else None
        if base is None:
            raise ValueError(f"kind must be one of {KINDS}, got {d['kind']!r}")
        return ChallengeSpec(**{**base.to_dict(), **{k: v for k, v in d.items()}})


def default_spec(kind: str, seeds: Sequence[int]) -> ChallengeSpec:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    if kind == "walk":
        return ChallengeSpec(kind="walk", seeds=tuple(seeds), duration=DEFAULT_DURATION["walk"], perturb=WALK_PERTURB,
                             start="neutral")
    return ChallengeSpec(kind=kind, seeds=tuple(seeds), duration=DEFAULT_DURATION[kind])


# ---------------------------------------------------------------------------------------------------------
# result records
# ---------------------------------------------------------------------------------------------------------
@dataclass
class SeedResult:
    seed: int
    outcome: Literal["PASS", "POOR", "FAIL", "ERROR"]
    score: float
    metrics: dict
    events: list[dict]
    rollouts: int
    error: str | None = None
    forensics: dict | None = None      # only for the seeds that failed; run_challenge keeps the worst seed's in the result

    def as_dict(self) -> dict:
        return jsonable(asdict(self))

    @staticmethod
    def from_dict(d: dict) -> "SeedResult":
        return SeedResult(**{k: d.get(k) for k in ("seed", "outcome", "score", "metrics", "events", "rollouts", "error", "forensics")})


@dataclass
class ChallengeResult:
    spec: dict
    body: dict
    controller: dict
    per_seed: list[SeedResult]
    outcome: str
    summary: dict
    forensics: dict
    rollouts: int
    wall_s: float

    def as_dict(self) -> dict:
        d = asdict(self)
        d["per_seed"] = [s.as_dict() for s in self.per_seed]
        return jsonable(d)


# ---------------------------------------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------------------------------------
def _as_body(body) -> SandboxBody:
    if isinstance(body, SandboxBody):
        return body.validate()
    if isinstance(body, dict):
        d = dict(body)
        if "pose" in d:
            d["pose"] = tuple(d["pose"])
        return SandboxBody(**d).validate()
    if hasattr(body, "as_dict"):          # a plain BipedParams
        return SandboxBody(**body.as_dict()).validate()
    raise ChallengeError(f"body must be a SandboxBody or a dict, got {type(body).__name__}")


def _body_dict(body) -> dict:
    if isinstance(body, SandboxBody):
        return body.as_dict()
    return dict(body) if isinstance(body, dict) else {"unreadable": repr(body)}


def stand_gait(controllers: dict | None) -> GaitParams:
    c = (controllers or {}).get("stand") or {}
    if "params" in c and isinstance(c["params"], dict):
        c = c["params"]
    return GaitParams(**c).validate()


def walk_vector(controllers: dict | None) -> list[float]:
    w = (controllers or {}).get("walk")
    if w is None:
        return list(cw.R2_WINNER)
    if isinstance(w, dict):
        w = w.get("vector")
        if w is None:
            return list(cw.R2_WINNER)
    vec = [float(x) for x in w]
    if len(vec) != cw.N_PARAMS:
        raise ChallengeError(f"the walking controller needs {cw.N_PARAMS} numbers, got {len(vec)}")
    return vec


def controller_provenance(controllers: dict | None, kind: str) -> dict:
    """Provenance record of contracts section 4.3 for the controllers a challenge used."""
    gait = stand_gait(controllers)
    prov: dict = {"stand": {"kind": "stand-pd", "params": gait.as_dict(), "edited": gait != GaitParams()}}
    w = (controllers or {}).get("walk")
    if kind != "walk" and w is None:
        prov["walk"] = {"kind": "none", "vector": None, "adaptation": None}
        return prov
    vec = walk_vector(controllers)
    adaptation = None
    if isinstance(w, dict):
        adaptation = w.get("adaptation") or (w.get("provenance") or {}).get("adaptation")
    if w is None or (vec == list(cw.R2_WINNER) and not adaptation):
        wk = "r2-transfer"
    else:
        wk = "adapted" if adaptation else "custom"
    prov["walk"] = {"kind": wk, "vector": vec, "adaptation": adaptation}
    return prov


# ---------------------------------------------------------------------------------------------------------
# settled failure rules and telemetry helpers
# ---------------------------------------------------------------------------------------------------------
def settled_events(tel: dict, body: SandboxBody, settle_s: float) -> list[FailureEvent]:
    """`failures.detect_failures` with the fall rule restricted to t >= settle_s (same thresholds, reference height = start).

    Saturation and slip events are the stock detector's, unchanged."""
    t = tel["t"]
    z = tel["torso_pos"][:, 1]
    low = (z < FALL_HEIGHT_FRAC * z[0]) | (np.abs(tel["torso_pitch"]) > FALL_PITCH)
    i = _first_sustained(low & (t >= settle_s), max(1, int(round(FALL_SUSTAIN_S / SAMPLE_DT))))
    others = [e for e in detect_failures(tel, body) if e.kind != "fall"]
    events = others
    if i is not None:
        events = [FailureEvent("fall", float(t[i]), {
            "torso_height": float(z[i]), "initial_torso_height": float(z[0]),
            "torso_pitch": float(tel["torso_pitch"][i]), "min_torso_height": float(z.min()),
            "settle_s": settle_s}), *others]
    return sorted(events, key=lambda e: e.time)


def _check_finite(tel: dict) -> None:
    for k, v in tel.items():
        if k in NAN_OK:
            continue
        if not np.all(np.isfinite(v)):
            raise ChallengeError(f"the simulation became numerically unstable (non-finite {k})")


def _simulate(body: SandboxBody, gait: GaitParams, seed: int, spec: ChallengeSpec, push: Push | None = None,
              record_poses: bool = False) -> dict:
    tel = run_rollout(body, gait, seed=seed, duration=spec.duration, perturb=spec.perturb, push=push,
                      record_poses=record_poses)
    _check_finite(tel)
    return tel


def _fall(events: list[FailureEvent]) -> FailureEvent | None:
    return next((e for e in events if e.kind == "fall"), None)


def _mirror(tel: dict) -> dict:
    """The telemetry as seen with +x = push direction when the push was backward (forensics' convention)."""
    m = dict(tel)
    tp = np.array(tel["torso_pos"], copy=True)
    tp[:, 0] *= -1.0
    tp[:, 2] *= -1.0
    m["torso_pos"] = tp
    for k in ("torso_pitch", "torso_angvel", "cop_x"):
        m[k] = -np.asarray(tel[k])
    lv = np.array(tel["torso_linvel"], copy=True)
    lv[:, 0] *= -1.0
    m["torso_linvel"] = lv
    for k in ("com_pos", "com_vel"):
        a = np.array(tel[k], copy=True)
        a[:, 0] *= -1.0
        m[k] = a
    m["support_x_min"] = -np.asarray(tel["support_x_max"])
    m["support_x_max"] = -np.asarray(tel["support_x_min"])
    return m


def _forensics(tel: dict, body: SandboxBody, push: Push, events: list[FailureEvent], mirrored: bool) -> dict:
    try:
        if mirrored:
            tel = _mirror(tel)
            push = Push(push.time, abs(push.force), push.duration)
        with np.errstate(all="ignore"):
            return build_forensics(tel, body, push, events)
    except Exception as exc:  # noqa: BLE001 - evidence is best-effort, the verdict never depends on it
        return {"unavailable": f"{type(exc).__name__}: {exc}"}


def _stand_metrics(tel: dict, body: SandboxBody, events: list[FailureEvent], spec: ChallengeSpec) -> dict:
    t = tel["t"]
    z = tel["torso_pos"][:, 1]
    after = t >= spec.settle_s
    fall = _fall(events)
    demand = np.abs(tel["ctrl_demand"])
    loaded = tel["foot_contact"] > 0.5
    slipping = ((tel["foot_slip_speed"] > 0.15) & loaded).any(axis=1)
    return {
        "survival_s": float(fall.time if fall else spec.duration), "fell": fall is not None,
        "fall_time": None if fall is None else float(fall.time),
        "max_abs_pitch_after_settle": float(np.abs(tel["torso_pitch"][after]).max()),
        "min_height_ratio": float(z[after].min() / z[0]),
        "saturation_frac": float((demand > body.torque_limit * 0.999).any(axis=1).mean()),
        "slip_frac": float(slipping.mean()),
        "settle_s": spec.settle_s, "z_ref": float(z[0]), "initial_pitch": float(tel["torso_pitch"][0]),
        "final_pitch": float(tel["torso_pitch"][-1]), "final_height_ratio": float(z[-1] / z[0]),
    }


# ---------------------------------------------------------------------------------------------------------
# per-seed runners
# ---------------------------------------------------------------------------------------------------------
def _run_stand(body, controllers, spec, seed) -> SeedResult:
    gait = stand_gait(controllers)
    tel = _simulate(body, gait, seed, spec)
    events = settled_events(tel, body, spec.settle_s)
    m = _stand_metrics(tel, body, events, spec)
    if m["fell"]:
        outcome = "FAIL"
    elif m["max_abs_pitch_after_settle"] > STAND_POOR_PITCH or m["min_height_ratio"] < STAND_POOR_HEIGHT:
        outcome = "POOR"
    else:
        outcome = "PASS"
    forensics = None
    if outcome != "PASS":
        forensics = _forensics(tel, body, Push(spec.settle_s, 0.0, 0.0), events, False)
        forensics["no_push"] = True
    return SeedResult(seed, outcome, m["survival_s"], m, [e.as_dict() for e in events], 1, forensics=forensics)


def _run_push(body, controllers, spec, seed) -> SeedResult:
    gait = stand_gait(controllers)
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0x9055]))
    t_push = float(spec.push_time + rng.uniform(-PUSH_JITTER_S, PUSH_JITTER_S))
    rollouts = 0
    trace: list[list] = []
    first_fallen: dict[int, tuple] = {}     # direction -> (force, tel, events) at the lowest force that fell
    z_ref: list[float] = []

    def survives(force: float, direction: int) -> bool:
        nonlocal rollouts
        push = Push(t_push, direction * force, spec.push_duration)
        tel = _simulate(body, gait, seed, spec, push)
        rollouts += 1
        if not z_ref:
            z_ref.append(float(tel["torso_pos"][0, 1]))
        events = settled_events(tel, body, spec.settle_s)
        ok = _fall(events) is None
        trace.append([float(direction * force), bool(ok)])
        if not ok and (direction not in first_fallen or force < first_fallen[direction][0]):
            first_fallen[direction] = (force, tel, events)
        return ok

    base_ok = survives(0.0, +1)
    crit: dict[int, float] = {}
    censored: dict[int, bool] = {}
    if not base_ok:
        crit = {+1: 0.0, -1: 0.0}
        censored = {+1: False, -1: False}
    else:
        for d in (+1, -1):
            if survives(spec.max_force, d):
                crit[d], censored[d] = spec.max_force, True
                continue
            lo, hi = 0.0, spec.max_force
            for _ in range(spec.bisection_steps):
                mid = 0.5 * (lo + hi)
                if survives(mid, d):
                    lo = mid
                else:
                    hi = mid
            crit[d], censored[d] = lo, False
    fwd, bwd = crit[+1], crit[-1]
    score = min(fwd, bwd)
    weak = +1 if fwd <= bwd else -1
    weak_name = "equal" if fwd == bwd else ("forward" if weak == +1 else "backward")
    if score >= spec.target_force:
        outcome = "PASS"
    elif score >= PUSH_POOR_FRACTION * spec.target_force:
        outcome = "POOR"
    else:
        outcome = "FAIL"
    forensics, events = None, []
    if weak in first_fallen:   # the breaking point of the weak direction is the evidence, PASS or not
        f, tel, ev = first_fallen[weak]
        events = [e.as_dict() for e in ev]
        forensics = _forensics(tel, body, Push(t_push, weak * f, spec.push_duration), ev, weak == -1)
        forensics.update({"direction": "backward" if weak == -1 else "forward", "force_N": float(weak * f),
                          "mirrored": weak == -1, "first_failing_force_N": float(f)})
        if not base_ok:
            forensics["direction"] = "none (falls without a push)"
    metrics = {
        "critical_force_fwd": fwd, "critical_force_bwd": bwd, "weak_direction": weak_name,
        "censored": bool(censored[+1] and censored[-1]), "censored_fwd": censored[+1], "censored_bwd": censored[-1],
        "falls_without_push": not base_ok, "bisection_trace": trace, "push_time_s": t_push,
        "push_duration_s": spec.push_duration, "max_force": spec.max_force, "target_force": spec.target_force,
        "force_resolution_N": spec.max_force / 2 ** spec.bisection_steps, "settle_s": spec.settle_s,
        "z_ref": z_ref[0],
    }
    return SeedResult(seed, outcome, float(score), metrics, events, rollouts, forensics=forensics)


WALK_KEEP = ("label", "walking", "violations", "fell", "fall_time", "fall_pitch", "time_upright", "forward_disp_upright",
             "speed_upright", "valid_steps", "valid_step_rate", "backward_steps", "alternation", "mean_step_advance",
             "mean_stance_s", "mean_swing_s", "flight_frac", "single_support_frac", "double_support_frac",
             "raw_touchdown_rate", "slip_frac", "body_contact_frac", "saturation_frac", "effort", "cot",
             "max_abs_pitch", "min_torso_height")


def _run_walk(body, controllers, spec, seed) -> SeedResult:
    vec = walk_vector(controllers)
    crit = cw.creature_criteria(body)
    ctrl = controller_from_vector(vec)
    tr = cw.rollout(ctrl, body, seed, spec.duration, start=spec.start, perturb=spec.perturb, settle_s=spec.settle_s)
    for k in ("x", "z", "pitch", "tau"):
        if not np.all(np.isfinite(tr[k])):
            raise ChallengeError(f"the simulation became numerically unstable (non-finite {k})")
    m = compute_metrics(tr, crit)
    fell_early = bool(m["fell"]) and (m["fall_time"] or 0.0) < 1.0
    gait_valid = m["valid_steps"] >= 1
    score = 0.0 if (fell_early or not gait_valid) else max(0.0, float(m["forward_disp_upright"]))
    if m["walking"]:
        outcome = "PASS"
    elif m["fell"]:
        outcome = "FAIL"
    else:
        outcome = "POOR"
    metrics = {k: m[k] for k in WALK_KEEP}
    metrics.update({"score_rule": "forward displacement while upright; 0 if fallen before 1 s or no valid step",
                    "criteria_scale": cw.length_scale(body), "min_speed": crit.min_speed,
                    "min_step_advance": crit.min_step_advance, "start": spec.start, "settle_s": spec.settle_s})
    forensics = None
    if outcome != "PASS":
        forensics = {k: m[k] for k in ("label", "violations", "fell", "fall_time", "fall_pitch", "time_upright",
                                       "speed_upright", "valid_steps", "valid_step_rate", "flight_frac", "slip_frac",
                                       "saturation_frac", "max_abs_pitch", "min_torso_height", "mean_stance_s",
                                       "mean_swing_s", "body_contact_frac")}
        forensics["kind"] = "walk"
    events = []
    if m["fell"]:
        events.append(FailureEvent("fall", float(m["fall_time"]), {"torso_pitch": m["fall_pitch"],
                                                                    "min_torso_height": m["min_torso_height"]}).as_dict())
    return SeedResult(seed, outcome, score, metrics, events, 1, forensics=forensics)


def run_seed(body, controllers: dict | None, spec: ChallengeSpec, seed: int) -> SeedResult:
    """One seed of a challenge. Deterministic for (body, controllers, spec, seed); never raises: a run that cannot execute
    is an `ERROR` result carrying the message."""
    try:
        b = _as_body(body)
        runner = {"stand": _run_stand, "push": _run_push, "walk": _run_walk}[spec.kind]
        res = runner(b, controllers, spec, int(seed))
        return SeedResult.from_dict(jsonable(asdict(res)))
    except Exception as exc:  # noqa: BLE001 - reported as ERROR with its message
        msg = f"{type(exc).__name__}: {exc}"
        return SeedResult(int(seed), "ERROR", 0.0, {"error": msg}, [], 0, error=msg)


def seed_job(job: dict) -> dict:
    """Pool job: {body, controllers, spec, seed} -> SeedResult dict. Module-level so it pickles under 'spawn'."""
    spec = ChallengeSpec.from_dict(job["spec"])
    return run_seed(job["body"], job["controllers"], spec, job["seed"]).as_dict()


# ---------------------------------------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------------------------------------
def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def aggregate_outcome(outcomes: Sequence[str]) -> str:
    """PASS if >= 80 % of seeds PASS, FAIL if >= 50 % FAIL, else POOR; ERROR if any seed errored."""
    n = len(outcomes)
    if n == 0 or "ERROR" in outcomes:
        return "ERROR"
    if sum(o == "PASS" for o in outcomes) >= 0.8 * n:
        return "PASS"
    if sum(o == "FAIL" for o in outcomes) >= 0.5 * n:
        return "FAIL"
    return "POOR"


def summarize(per_seed: Sequence[SeedResult]) -> dict:
    n = len(per_seed)
    counts = {o: sum(s.outcome == o for s in per_seed) for o in OUTCOMES}
    scores = np.array([s.score for s in per_seed if s.outcome != "ERROR"], dtype=float)
    stats = ({"median": float(np.median(scores)), "mean": float(scores.mean()), "min": float(scores.min()),
              "max": float(scores.max()), "q25": float(np.percentile(scores, 25)), "q75": float(np.percentile(scores, 75))}
             if len(scores) else {"median": None, "mean": None, "min": None, "max": None, "q25": None, "q75": None})
    lo, hi = wilson_interval(counts["PASS"], n)
    return {"n": n, "counts": counts, "score": stats,
            "pass_rate": {"rate": counts["PASS"] / n if n else 0.0, "ci95": [lo, hi], "method": "wilson"}}


_RANK = {"FAIL": 0, "POOR": 1, "PASS": 2, "ERROR": 3}


def worst_seed(per_seed: Sequence[SeedResult]) -> SeedResult | None:
    ok = [s for s in per_seed if s.outcome != "ERROR"]
    return min(ok, key=lambda s: (_RANK[s.outcome], s.score, s.seed)) if ok else None


def run_challenge(body, controllers: dict | None, spec: ChallengeSpec, pool=None, progress=None) -> ChallengeResult:
    """Run `spec` on every seed (over `pool.imap` if given) and aggregate. `progress(done, total)` counts seeds."""
    t0 = time.perf_counter()
    pool = pool or InlinePool()
    body_raw = body.as_dict() if isinstance(body, SandboxBody) else body
    ctrl = {"stand": (controllers or {}).get("stand"), "walk": (controllers or {}).get("walk")}
    jobs = [{"body": body_raw, "controllers": ctrl, "spec": spec.to_dict(), "seed": int(s)} for s in spec.seeds]
    results: list[SeedResult | None] = [None] * len(jobs)
    done = 0
    for i, out in pool.imap(seed_job, jobs):
        if isinstance(out, tuple) and is_error(out):
            results[i] = SeedResult(int(spec.seeds[i]), "ERROR", 0.0, {"error": out[1]}, [], 0, error=out[1])
        else:
            results[i] = SeedResult.from_dict(out)
        done += 1
        if progress is not None:
            progress(done, len(jobs))
    per = [r for r in results if r is not None]
    worst = worst_seed(per)
    forensics = {}
    if worst is not None and worst.forensics:
        forensics = {**worst.forensics, "seed": worst.seed, "seed_outcome": worst.outcome, "seed_score": worst.score}
    for s in per:
        s.forensics = None
    try:
        body_dict = _as_body(body).as_dict()
    except Exception:  # noqa: BLE001 - the invalid body is echoed as given; every seed reports why
        body_dict = jsonable(_body_dict(body))
    return ChallengeResult(
        spec=spec.to_dict(), body=body_dict, controller=controller_provenance(controllers, spec.kind), per_seed=per,
        outcome=aggregate_outcome([s.outcome for s in per]), summary=summarize(per), forensics=jsonable(forensics),
        rollouts=int(sum(s.rollouts for s in per)), wall_s=time.perf_counter() - t0)


# ---------------------------------------------------------------------------------------------------------
# replay for the viewer
# ---------------------------------------------------------------------------------------------------------
def _decimate(tel: dict, max_hz: int) -> dict:
    n = len(tel["t"])
    k = max(1, int(math.ceil(1.0 / SAMPLE_DT / max(1, max_hz))))
    idx = np.arange(0, n, k)
    if idx[-1] != n - 1:
        idx = np.append(idx, n - 1)
    return {key: (val[idx] if isinstance(val, np.ndarray) and len(val) == n else val) for key, val in tel.items()}


def replay_payload(body, controllers: dict | None, spec: ChallengeSpec, seed: int, *, force: float | None = None,
                   direction: int = +1, max_hz: int = 50) -> dict:
    """A `RunPayload` (the existing 3D viewer's format) for one seed, decimated to <= `max_hz` Hz.

    Fresh MuJoCo rollout; `force` (push only) defaults to the spec's target force and `direction` is +1 forward / -1 backward.
    Events use the same settle window as the challenge."""
    b = _as_body(body)
    if direction not in (+1, -1):
        raise ChallengeError("direction must be +1 (forward) or -1 (backward)")
    if spec.kind == "walk":
        return _walk_payload(b, controllers, spec, int(seed), max_hz)
    gait = stand_gait(controllers)
    push = None
    if spec.kind == "push":
        f = spec.target_force if force is None else float(force)
        if not math.isfinite(f) or f < 0:
            raise ChallengeError("force must be a finite, non-negative number of newtons")
        rng = np.random.default_rng(np.random.SeedSequence([int(seed), 0x9055]))
        t_push = float(spec.push_time + rng.uniform(-PUSH_JITTER_S, PUSH_JITTER_S))
        push = Push(t_push, direction * f, spec.push_duration)
    tel = _simulate(b, gait, int(seed), spec, push, record_poses=True)
    events = settled_events(tel, b, spec.settle_s)
    payload = payload_from_telemetry(b, gait, _decimate(tel, max_hz), seed=int(seed), duration=spec.duration, push=push)
    payload["events"] = [e.as_dict() for e in events]
    payload["metrics"]["fell"] = _fall(events) is not None
    payload["sandbox"] = True
    stride = max(1, int(math.ceil(1.0 / SAMPLE_DT / max(1, max_hz))))
    payload["challenge"] = {"kind": spec.kind, "seed": int(seed), "settle_s": spec.settle_s, "direction": direction,
                            "force": None if push is None else float(push.force), "sample_hz": 1.0 / (SAMPLE_DT * stride)}
    return jsonable(payload)


def _walk_payload(body: SandboxBody, controllers: dict | None, spec: ChallengeSpec, seed: int, max_hz: int,
                  ndigits: int = 5) -> dict:
    vec = walk_vector(controllers)
    ctrl = controller_from_vector(vec)
    tr = cw.rollout(ctrl, body, seed, spec.duration, start=spec.start, perturb=spec.perturb, record_poses=True,
                    settle_s=spec.settle_s)
    m = compute_metrics(tr, cw.creature_criteria(body))
    _, _, deb = contact_replay(tr["t"], tr["force"], tr["meta"]["weight"])
    tr = dict(tr)
    tr["deb"] = deb
    d = _decimate({k: v for k, v in tr.items() if k != "meta"}, max_hz)
    pos = np.round([[mj_to_three_pos(p) for p in f] for f in d["geom_xpos"]], ndigits)
    quat = np.round([[mj_to_three_quat(q) for q in f] for f in d["geom_xquat"]], ndigits)
    cpos = np.round([[mj_to_three_pos(p) for p in f] for f in d["foot_contact_pos"]], ndigits)
    z = d["z"]
    vx = float(np.abs(np.gradient(tr["x"], tr["t"])).max()) if len(tr["t"]) > 1 else 0.0
    keep = ("label", "walking", "violations", "speed_upright", "forward_disp_upright", "valid_steps", "valid_step_rate",
            "backward_steps", "mean_step_advance", "mean_stance_s", "mean_swing_s", "single_support_frac",
            "double_support_frac", "flight_frac", "raw_touchdown_rate", "slip_frac", "saturation_frac", "effort",
            "time_upright", "fell", "fall_time")
    events = []
    if m["fell"]:
        events.append({"kind": "fall", "time": m["fall_time"],
                       "evidence": {"torso_pitch": m["fall_pitch"], "min_torso_height": m["min_torso_height"]}})
    return jsonable({
        "scene": export_scene(build_model(body)), "body": body.as_dict(),
        "gait": {"walk_vector": vec}, "seed": seed, "duration": float(tr["t"][-1]), "push": None, "sandbox": True,
        "time": np.round(d["t"], 4).tolist(),
        "frames": {"pos": pos.tolist(), "quat": quat.tolist(), "contact_pos": cpos.tolist()},
        "series": {"torso_height": np.round(z, 5).tolist(), "torso_pitch": np.round(d["pitch"], 5).tolist(),
                   "torso_x": np.round(d["x"], 5).tolist(), "foot_contact": d["deb"].astype(int).tolist(),
                   "foot_slip_speed": np.round(d["slip"], 4).tolist(),
                   "max_torque_frac": np.round(np.abs(d["tau"]).max(axis=1) / body.torque_limit, 4).tolist()},
        "events": events,
        "metrics": {"initial_torso_height": float(z[0]), "min_torso_height": float(z.min()),
                    "final_torso_height": float(z[-1]), "max_abs_pitch": float(np.abs(d["pitch"]).max()),
                    "peak_torso_vx": vx, "fell": bool(m["fell"])},
        "locomotion": {k: m[k] for k in keep},
        "challenge": {"kind": "walk", "seed": seed, "settle_s": spec.settle_s, "start": spec.start}})
