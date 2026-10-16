"""Budget-exact, deterministic CMA-ES for the 15-parameter walking controller (and, optionally, a few body parameters).

This is the strong NON-AI optimiser of the Forge Loop: the fair classical baseline an AI director is compared against, and the
numeric engine an AI director can call with a chosen search space. It is new code; `creature_walk.adapt_controller` (the small
(1+8)-ES used by the recorded experiments) is untouched. numpy and existing project code only.

Search space (`SearchSpace`)
  * control dims: any subset of `r3.PARAM_NAMES`; `SUBSPACES` groups them (timing / posture / feedback / stride) and partitions
    the 15 names exactly. Control dims that are not searched keep the value of the base vector.
  * body dims (at most 4 of `BODY_PARAMS`): a leg parameter sets BOTH legs (`x` and `x_r`; legs stay symmetric), by the same ratio.
  * Encoding in [0, 1]^n. Control: u = (x - lo) / (hi - lo) over `phasegait_init.LOWER15/UPPER15` (r2's encoding). Body: z over the
    log-ratio interval [max(ln r_lo, ln(lo/old)), min(ln r_hi, ln(hi/old))] where (lo, hi) are the bounds of the search mode
    (guided: `morphology.BOUNDS`, experimental: `sandbox.SANDBOX_BOUNDS`), `old` is the base body's value and (r_lo, r_hi) =
    `body_ratio` (default 0.5..1.5, the interventions ratio rule). The interval is shrunk by 1e-9 so that float rounding can never
    place a decoded value outside a bound. Every decoded candidate therefore passes `interventions.validate_edits`
    (`body_edits` gives the equivalent scale edits, target "both").
  * Boundary handling: CMA samples outside [0, 1] are folded back with `r2.reflect`. This is the optimiser's own bookkeeping to
    stay inside the legal region (the folded point is both evaluated and used in the update); it is not a model edit.

`similarity_init`: dynamic-similarity transfer of a vector tuned on a reference body (default `SandboxBody()`, 0.6 m legs, the body
R2 was tuned on) to another body. L = mean leg length (thigh + shank), M = total mass: freq *= sqrt(L0/L); ramp_s *= sqrt(L/L0);
kp, balance_gain, pitch_kp *= (M L)/(M0 L0); kd *= (M L)/(M0 L0) sqrt(L/L0); angles, duty, knee_shift, sync_gain, start_lean are
unchanged. A component that would leave LOWER15/UPPER15 is set to the bound and listed in `report["at_bound"]` with the unbounded
value (explicit, never silent). For the reference body the result equals the input exactly.

`cma_search`: (mu/mu_w, lambda)-CMA-ES with the default parameters of Hansen's 2016 tutorial (lambda = 4 + floor(3 ln n), log
weights, cs, damps, cc, c1, cmu, eigendecomposition every generation) in the [0, 1] encoding, mean starting at encode(init).
  * Determinism: all randomness comes from `Generator(PCG64(SeedSequence([noise_seed, 0xC3A])))`; same inputs, same history.
  * Evaluation: ONE pool job per (candidate, seed), `creature_walk.eval_job`, under the conditions of `arena._condition`
    (perturbation) and `arena._body_with_friction` (friction) with `spec = challenges.default_spec("walk", [seed])`, i.e. exactly
    the held-out validation conditions; `variation=None` means nominal conditions. Candidate objective = mean per-seed `fitness`;
    walking_count and survival_count are kept. A failed job scores `r2.ERROR_FITNESS` for that seed and is recorded in
    `result["errors"]`; nothing is raised or dropped. `eval_fn` (tests only) replaces the whole batch evaluation.
  * Ranking inside CMA uses the scalar mean fitness; best-so-far (and the returned best) uses the lexicographic tuple
    (walking_count, survival_count, mean_fitness), like `r2.score_of`.
  * Budget: the initial point is evaluated first (len(train_seeds) rollouts, counted); a generation costs lambda * len(train_seeds)
    and is never started if it would exceed `budget`, so `rollouts_used <= budget` and equals the sum of all logged evaluations.
    Candidate j of a generation counts as completed at (rollouts before the generation) + (j + 1) * len(train_seeds), in index
    order, whatever the real completion order of the pool. A restart whose doubled population no longer fits ends the search.
  * IPOP (optional): restart from encode(init) with lambda doubled and sigma reset when sigma < 1e-3, or the run's best generation
    score has not improved for 10 + ceil(30 n / lambda) generations, or the covariance condition number exceeds 1e14, or the state
    becomes non-finite. Each restart is recorded.
  * Anytime checkpoints: for each c in `checkpoints` with c <= budget, the best-so-far candidate among evaluations completed with
    cumulative rollouts <= c, with its body, vector, edits, score and `found_at_rollouts`.

Training seeds select; they never validate. Held-out validation must use seeds that were not passed here (docs: physics-integrity).
"""
from __future__ import annotations

import math
import time
from typing import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from . import arena, challenges, creature_walk as cw, r2, r3
from . import interventions as iv
from .forge_pool import InlinePool, is_error
from .morphology import build_model
from .optimize import jsonable
from .phasegait_init import LOWER15, UPPER15
from .sandbox import SandboxBody

VERSION = "walk_opt_v1"
SUBSPACES = {
    "timing": ("freq", "duty", "knee_shift"),
    "posture": ("hip_bias", "pitch_ref", "stance_knee", "start_lean"),
    "feedback": ("kp", "kd", "balance_gain", "pitch_kp", "sync_gain"),
    "stride": ("hip_amp", "knee_amp", "ramp_s"),
}
BODY_PARAMS = ("torso_mass", "thigh_length", "shank_length", "foot_length", "leg_density", "foot_friction", "torque_limit")
MAX_BODY_PARAMS = 4
_LEG = ("thigh_length", "shank_length", "foot_length")
_MARGIN = 1e-9                  # log-interval shrink: decoded values stay strictly inside the bounds despite float rounding
DEFAULT_CHECKPOINTS = (250, 1000, 4000, 8000)
SIGMA_RESTART = 1e-3
COND_RESTART = 1e14


# ----------------------------------------------------------------------------------------------------------
# search space and encoding
# ----------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class SearchSpace:
    ctrl_params: tuple
    body_params: tuple = ()
    body_ratio: tuple = (0.5, 1.5)
    mode: str = "guided"

    def __post_init__(self):
        object.__setattr__(self, "ctrl_params", tuple(self.ctrl_params))
        object.__setattr__(self, "body_params", tuple(self.body_params))
        object.__setattr__(self, "body_ratio", tuple(float(x) for x in self.body_ratio))
        bad = [p for p in self.ctrl_params if p not in r3.PARAM_NAMES]
        if bad:
            raise ValueError(f"unknown control parameter(s) {bad}; known: {list(r3.PARAM_NAMES)}")
        bad = [p for p in self.body_params if p not in BODY_PARAMS]
        if bad:
            raise ValueError(f"unknown body parameter(s) {bad}; known: {list(BODY_PARAMS)}")
        if len(set(self.ctrl_params)) != len(self.ctrl_params):
            raise ValueError("duplicate control parameters")
        if len(set(self.body_params)) != len(self.body_params):
            raise ValueError("duplicate body parameters")
        if len(self.body_params) > MAX_BODY_PARAMS:
            raise ValueError(f"at most {MAX_BODY_PARAMS} body parameters (got {len(self.body_params)})")
        if not self.ctrl_params and not self.body_params:
            raise ValueError("the search space needs at least one dimension")
        if self.mode not in iv.MODES:
            raise ValueError(f"mode must be one of {iv.MODES}, got {self.mode!r}")
        if len(self.body_ratio) != 2 or not (0.0 < self.body_ratio[0] <= 1.0 <= self.body_ratio[1]) \
                or not all(math.isfinite(x) for x in self.body_ratio):
            raise ValueError(f"body_ratio must be (r_lo, r_hi) with 0 < r_lo <= 1 <= r_hi, got {self.body_ratio}")

    @property
    def dim(self) -> int:
        return len(self.ctrl_params) + len(self.body_params)

    @staticmethod
    def full_ctrl(body_params=(), **kw) -> "SearchSpace":
        return SearchSpace(tuple(r3.PARAM_NAMES), tuple(body_params), **kw)

    @staticmethod
    def from_subspaces(names: Sequence[str], body_params=(), **kw) -> "SearchSpace":
        unknown = [n for n in names if n not in SUBSPACES]
        if unknown:
            raise ValueError(f"unknown subspace(s) {unknown}; known: {list(SUBSPACES)}")
        if len(set(names)) != len(names):
            raise ValueError("duplicate subspaces")
        chosen = {p for n in names for p in SUBSPACES[n]}
        return SearchSpace(tuple(p for p in r3.PARAM_NAMES if p in chosen), tuple(body_params), **kw)

    def to_dict(self) -> dict:
        return {"ctrl_params": list(self.ctrl_params), "body_params": list(self.body_params),
                "body_ratio": list(self.body_ratio), "mode": self.mode, "dim": self.dim}


def _base_dict(body) -> dict:
    """Full body dict (every *_r explicit, list pose) from a dict, SandboxBody or version-like body."""
    d = body.as_dict() if isinstance(body, SandboxBody) else dict(body)
    return iv.full_body({"body": d})


def _fields(param: str) -> tuple:
    return (param, param + "_r") if param in _LEG else (param,)


def _log_interval(space: SearchSpace, base: dict, param: str) -> tuple[float, float]:
    lo_b, hi_b = iv.mode_bounds(space.mode)[param]
    lo = math.log(space.body_ratio[0])
    hi = math.log(space.body_ratio[1])
    for f in _fields(param):
        old = float(base[f])
        if not old > 0:
            raise ValueError(f"base body {f}={old!r} must be positive")
        lo = max(lo, math.log(lo_b / old))
        hi = min(hi, math.log(hi_b / old))
    lo, hi = lo + _MARGIN, hi - _MARGIN
    if not hi > lo:
        raise ValueError(f"base body {param} leaves no room to search inside the {space.mode} bounds [{lo_b:g}, {hi_b:g}]")
    return lo, hi


def _base_vector(v) -> np.ndarray:
    a = np.asarray(v, dtype=float)
    if a.shape != (15,) or not np.all(np.isfinite(a)):
        raise ValueError("vector must be 15 finite numbers")
    bad = [i for i in range(15) if not (LOWER15[i] <= a[i] <= UPPER15[i])]
    if bad:
        raise ValueError(f"vector entries {bad} are outside the controller bounds (not clipped)")
    return a


def encode(space: SearchSpace, base_body, base_vector, body, vector) -> np.ndarray:
    """[0,1]^n point of (body, vector). Dims not searched are ignored. Raises ValueError if a body value is outside its interval."""
    base, body = _base_dict(base_body), _base_dict(body)
    vec = np.asarray(vector, dtype=float)
    x = []
    for p in space.ctrl_params:
        i = r3.PARAM_NAMES.index(p)
        x.append((vec[i] - LOWER15[i]) / (UPPER15[i] - LOWER15[i]))
    for p in space.body_params:
        lo, hi = _log_interval(space, base, p)
        z = (math.log(float(body[p]) / float(base[p])) - lo) / (hi - lo)
        if not (-1e-9 <= z <= 1 + 1e-9):
            raise ValueError(f"body {p}={body[p]!r} is outside the searched interval for base {base[p]!r}")
        x.append(min(1.0, max(0.0, z)))
    return np.asarray(x, dtype=float)


def decode(space: SearchSpace, base_body, base_vector, x) -> tuple[dict, list]:
    """(body_dict, vector_list) of a [0,1]^n point (folded with r2.reflect first). Non-searched parts come from the base."""
    base = _base_dict(base_body)
    vec = _base_vector(base_vector).copy()
    u = r2.reflect(np.asarray(x, dtype=float))
    if u.shape != (space.dim,):
        raise ValueError(f"x must have {space.dim} entries")
    k = len(space.ctrl_params)
    for j, p in enumerate(space.ctrl_params):
        i = r3.PARAM_NAMES.index(p)
        vec[i] = min(UPPER15[i], max(LOWER15[i], LOWER15[i] + (UPPER15[i] - LOWER15[i]) * u[j]))
    body = dict(base)
    for j, p in enumerate(space.body_params):
        lo, hi = _log_interval(space, base, p)
        ratio = math.exp(lo + float(u[k + j]) * (hi - lo))
        for f in _fields(p):
            body[f] = float(base[f]) * ratio
    return body, [float(v) for v in vec]


def body_edits(base_body, body) -> list[dict]:
    """Scale edits (target "both") turning base_body into body; parameters that did not change are omitted."""
    base, body = _base_dict(base_body), _base_dict(body)
    out = []
    for p in BODY_PARAMS:
        ratio = float(body[p]) / float(base[p])
        if abs(ratio - 1.0) > 1e-12:
            out.append({"param": p, "op": "scale", "value": ratio, "target": "both"})
    return out


# ----------------------------------------------------------------------------------------------------------
# dynamic-similarity initialisation
# ----------------------------------------------------------------------------------------------------------
def _size(body) -> tuple[float, float]:
    b = cw._body(_base_dict(body) if not isinstance(body, SandboxBody) else body)
    return float(cw._leg_lengths(b)[0] + cw._leg_lengths(b)[1]) / 2.0, float(build_model(b).body_mass.sum())


def similarity_init(body, vector, ref_body=None) -> tuple[list, dict]:
    """Transfer `vector` (tuned on ref_body, default SandboxBody()) to `body` by dynamic similarity. -> (vector, report)."""
    vec = _base_vector(vector)
    ref = SandboxBody() if ref_body is None else ref_body
    L, M = _size(body)
    L0, M0 = _size(ref)
    gain = (M * L) / (M0 * L0)
    f = {"freq": math.sqrt(L0 / L), "ramp_s": math.sqrt(L / L0), "kp": gain, "balance_gain": gain, "pitch_kp": gain,
         "kd": gain * math.sqrt(L / L0)}
    out, at_bound = vec.copy(), []
    for name, fac in f.items():
        i = r3.PARAM_NAMES.index(name)
        raw = float(vec[i] * fac)
        lo, hi = float(LOWER15[i]), float(UPPER15[i])
        if raw < lo or raw > hi:
            bound = lo if raw < lo else hi
            at_bound.append({"param": name, "unbounded": raw, "bound": bound})
            raw = bound
        out[i] = raw
    report = {"L": L, "L0": L0, "M": M, "M0": M0, "factors": f, "at_bound": at_bound}
    return [float(v) for v in out], jsonable(report)


# ----------------------------------------------------------------------------------------------------------
# CMA-ES core (Hansen 2016 tutorial defaults)
# ----------------------------------------------------------------------------------------------------------
class _CMA:
    def __init__(self, n: int, lam: int, mean: np.ndarray, sigma: float):
        self.n, self.lam = n, lam
        self.mu = lam // 2
        w = math.log((lam + 1) / 2.0) - np.log(np.arange(1, self.mu + 1))
        self.w = w / w.sum()
        self.mueff = 1.0 / float((self.w ** 2).sum())
        me = self.mueff
        self.cc = (4 + me / n) / (n + 4 + 2 * me / n)
        self.cs = (me + 2) / (n + me + 5)
        self.c1 = 2 / ((n + 1.3) ** 2 + me)
        self.cmu = min(1 - self.c1, 2 * (me - 2 + 1 / me) / ((n + 2) ** 2 + me))
        self.damps = 1 + 2 * max(0.0, math.sqrt((me - 1) / (n + 1)) - 1) + self.cs
        self.chi_n = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))
        self.m = mean.copy()
        self.sigma = float(sigma)
        self.C = np.eye(n)
        self.B = np.eye(n)
        self.D = np.ones(n)
        self.ps = np.zeros(n)
        self.pc = np.zeros(n)
        self.gen = 0
        self.cond = 1.0

    def sample(self, rng) -> np.ndarray:
        """lam folded points in [0,1]^n (the folded points are what is evaluated and what the update uses)."""
        z = rng.standard_normal((self.lam, self.n))
        y = (z * self.D) @ self.B.T
        return r2.reflect(self.m + self.sigma * y)

    def update(self, x: np.ndarray, fitness: np.ndarray) -> None:
        order = np.argsort(-fitness, kind="stable")[: self.mu]
        y_all = (x - self.m) / self.sigma
        y_sel = y_all[order]
        y_w = self.w @ y_sel
        m_old = self.m
        self.m = np.clip(m_old + self.sigma * y_w, 0.0, 1.0)
        y_w = (self.m - m_old) / self.sigma
        inv_sqrt_c_y = self.B @ ((self.B.T @ y_w) / self.D)
        self.ps = (1 - self.cs) * self.ps + math.sqrt(self.cs * (2 - self.cs) * self.mueff) * inv_sqrt_c_y
        self.gen += 1
        hsig = (np.linalg.norm(self.ps) / math.sqrt(1 - (1 - self.cs) ** (2 * self.gen)) / self.chi_n
                < 1.4 + 2 / (self.n + 1))
        self.pc = (1 - self.cc) * self.pc + (math.sqrt(self.cc * (2 - self.cc) * self.mueff) * y_w if hsig else 0.0)
        rank_mu = (y_sel.T * self.w) @ y_sel
        self.C = ((1 - self.c1 - self.cmu) * self.C
                  + self.c1 * (np.outer(self.pc, self.pc) + (0.0 if hsig else self.cc * (2 - self.cc)) * self.C)
                  + self.cmu * rank_mu)
        self.sigma *= math.exp(min(1.0, (self.cs / self.damps) * (np.linalg.norm(self.ps) / self.chi_n - 1)))
        self.C = (self.C + self.C.T) / 2.0
        eig, B = np.linalg.eigh(self.C)
        if not np.all(np.isfinite(eig)) or not math.isfinite(self.sigma):
            self.cond = math.inf
            return
        eig = np.maximum(eig, 1e-30)
        self.B, self.D = B, np.sqrt(eig)
        self.cond = float(eig.max() / eig.min())


def _score(rec: dict) -> tuple:
    return (rec["walking_count"], rec["survival_count"], rec["mean_fitness"])


def _check_int(name: str, v, minimum: int = 0) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(v)


def cma_search(body, init_vector, space: SearchSpace, *, budget: int, train_seeds, noise_seed: int, pool=None,
               variation=arena.VARIATION_PRESET, popsize: int | None = None, sigma0: float = 0.2, ipop: bool = True,
               checkpoints: Sequence[int] = DEFAULT_CHECKPOINTS, duration: float = 10.0, progress: Callable | None = None,
               eval_fn: Callable | None = None) -> dict:
    """CMA-ES over `space` for `body` starting at `init_vector`; budget counted in rollouts (one per candidate and seed)."""
    t0 = time.perf_counter()
    seeds = [int(s) for s in train_seeds]
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("train_seeds must be non-empty and distinct")
    budget = _check_int("budget", budget)
    noise_seed = _check_int("noise_seed", noise_seed)
    if not (isinstance(sigma0, (int, float)) and 0 < sigma0 <= 1):
        raise ValueError("sigma0 must be in (0, 1]")
    if popsize is not None:
        popsize = _check_int("popsize", popsize, 2)
    if not isinstance(space, SearchSpace):
        raise ValueError("space must be a SearchSpace")
    var = None if variation is None else arena._check_variation(dict(variation))
    base = _base_dict(body)
    vec0 = _base_vector(init_vector)
    S, n = len(seeds), space.dim
    if budget < S:
        raise ValueError(f"budget {budget} cannot pay for the initial evaluation ({S} rollouts)")
    pool = pool or InlinePool()
    x0 = encode(space, base, vec0, base, vec0)
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([noise_seed, 0xC3A])))

    conds = []
    for s in seeds:
        spec = challenges.default_spec("walk", [s])
        if var is None:
            conds.append({"perturb": spec.perturb, "friction_factor": None, "start": spec.start})
        else:
            c = arena._condition(s, spec, var)
            conds.append({"perturb": c["perturb"], "friction_factor": c["friction_factor"], "start": spec.start})

    errors: list[dict] = []
    done = 0

    def evaluate(cands: list, cum_before: int) -> list[dict]:
        nonlocal done
        if eval_fn is not None:
            raw = eval_fn([(b, list(v)) for b, v in cands])
            if len(raw) != len(cands):
                raise ValueError("eval_fn must return one record per candidate")
            recs = []
            for r in raw:
                mf = float(r["mean_fitness"])
                err = r.get("error")
                recs.append({"walking_count": int(r["walking_count"]), "survival_count": int(r["survival_count"]),
                             "mean_fitness": mf if math.isfinite(mf) else r2.ERROR_FITNESS, "error": err})
            done += S * len(cands)
            if progress is not None:
                progress(done, budget)
        else:
            jobs, index = [], []
            for ci, (b, v) in enumerate(cands):
                for si, s in enumerate(seeds):
                    cd = conds[si]
                    jb = b if cd["friction_factor"] is None else arena._body_with_friction(b, cd["friction_factor"])[0]
                    jobs.append({"vector": [float(a) for a in v], "body": jb, "seeds": [s], "duration": duration,
                                 "start": cd["start"], "perturb": cd["perturb"]})
                    index.append((ci, si))
            per = [[None] * S for _ in cands]
            for i, out in pool.imap(cw.eval_job, jobs):
                ci, si = index[i]
                if isinstance(out, tuple) and is_error(out):
                    per[ci][si] = {"error": out[1]}
                elif not out.get("ok"):
                    per[ci][si] = {"error": out.get("error", "unknown error")}
                else:
                    p = out["per_seed"][0]
                    per[ci][si] = {"walking": bool(p["walking"]), "fell": bool(p["fell"]), "fitness": float(p["fitness"])}
                done += 1
                if progress is not None:
                    progress(done, budget)
            recs = []
            for row in per:
                fits = [r2.ERROR_FITNESS if "error" in r or not math.isfinite(r["fitness"]) else r["fitness"] for r in row]
                errs = [f"seed {seeds[k]}: {r['error']}" for k, r in enumerate(row) if "error" in r]
                recs.append({"walking_count": sum(1 for r in row if "error" not in r and r["walking"]),
                             "survival_count": sum(1 for r in row if "error" not in r and not r["fell"]),
                             "mean_fitness": float(np.mean(fits)), "error": "; ".join(errs) if errs else None})
        for j, r in enumerate(recs):
            if r["error"]:
                errors.append({"rollouts_cumulative": cum_before + (j + 1) * S, "error": str(r["error"])})
        return recs

    used = 0
    improvements: list[dict] = []          # strictly improving best-so-far candidates, in completion order
    best: dict | None = None

    def consider(rec: dict, b: dict, v: list, cum: int) -> None:
        nonlocal best
        if best is None or _score(rec) > _score(best):
            best = {"body": b, "vector": v, "walking_count": rec["walking_count"], "survival_count": rec["survival_count"],
                    "mean_fitness": rec["mean_fitness"], "found_at_rollouts": cum}
            improvements.append(best)

    init_rec = evaluate([(base, [float(a) for a in vec0])], 0)[0]
    used = S
    consider(init_rec, dict(base), [float(a) for a in vec0], used)
    init_info = {"body": dict(base), "vector": [float(a) for a in vec0], "walking_count": init_rec["walking_count"],
                 "survival_count": init_rec["survival_count"], "mean_fitness": init_rec["mean_fitness"],
                 "error": init_rec["error"], "rollouts": S}

    lam0 = popsize if popsize is not None else 4 + int(math.floor(3 * math.log(n)))
    lam0 = max(2, lam0)
    lam, restart_idx = lam0, 0
    restarts: list[dict] = []
    history: list[dict] = []
    cma = _CMA(n, lam, x0, sigma0)
    run_best, since_improve, gens_in_run = -math.inf, 0, 0
    while used + cma.lam * S <= budget:
        sigma_used = cma.sigma
        x = cma.sample(rng)
        decoded = [decode(space, base, vec0, xi) for xi in x]
        recs = evaluate(decoded, used)
        fit = np.array([r["mean_fitness"] for r in recs], dtype=float)
        gen_best = max(range(len(recs)), key=lambda j: (_score(recs[j]), -j))
        for j, r in enumerate(recs):
            consider(r, decoded[j][0], decoded[j][1], used + (j + 1) * S)
        used += cma.lam * S
        gens_in_run += 1
        history.append({"restart": restart_idx, "lambda": cma.lam, "sigma": float(sigma_used),
                        "best_score": [best["walking_count"], best["survival_count"], best["mean_fitness"]],
                        "gen_best_score": float(fit.max()), "rollouts_cumulative": used})
        if fit.max() > run_best:
            run_best, since_improve = float(fit.max()), 0
        else:
            since_improve += 1
        cma.update(x, fit)
        reason = None
        if not math.isfinite(cma.cond) or not np.all(np.isfinite(cma.m)):
            reason = "non_finite"
        elif cma.sigma < SIGMA_RESTART:
            reason = "sigma_below_1e-3"
        elif since_improve >= 10 + math.ceil(30 * n / cma.lam):
            reason = "stagnation"
        elif cma.cond > COND_RESTART:
            reason = "condition_number_above_1e14"
        if reason and ipop:
            lam *= 2
            restart_idx += 1
            restarts.append({"index": restart_idx, "after_generation": len(history), "rollouts_cumulative": used,
                             "reason": reason, "new_lambda": lam, "generations_in_previous_run": gens_in_run})
            cma = _CMA(n, lam, x0, sigma0)
            run_best, since_improve, gens_in_run = -math.inf, 0, 0
        elif reason == "non_finite":
            break

    def pack(b: dict | None) -> dict | None:
        if b is None:
            return None
        return {"body": b["body"], "vector": b["vector"], "edits": body_edits(base, b["body"]),
                "score": [b["walking_count"], b["survival_count"], b["mean_fitness"]],
                "walking_count": b["walking_count"], "survival_count": b["survival_count"],
                "mean_fitness": b["mean_fitness"], "found_at_rollouts": b["found_at_rollouts"]}

    cps = {}
    for c in checkpoints:
        c = int(c)
        if c <= budget:
            eligible = [b for b in improvements if b["found_at_rollouts"] <= c]
            cps[str(c)] = pack(eligible[-1]) if eligible else None
    return jsonable({
        "version": VERSION, "best": pack(best), "checkpoints": cps, "history": history, "rollouts_used": used,
        "budget": budget, "space": space.to_dict(), "noise_seed": noise_seed, "train_seeds": seeds, "variation": var,
        "restarts": restarts, "errors": errors,
        "init": init_info, "popsize": lam0, "sigma0": float(sigma0), "ipop": bool(ipop), "duration": float(duration),
        "wall_s": time.perf_counter() - t0})
