"""Matched-budget controller optimizers: uniform random search and bounded differential evolution.

Both optimise the `PhaseGaitParams` vector on one fixed morphology with the same training seeds, episode
length and total MuJoCo rollout budget; every rollout (including failed candidates) is counted and every
candidate is recorded. No scipy: DE is implemented here so no polishing step can spend unbudgeted rollouts.

Parallelism is over candidates (one job = all training seeds of one candidate). A job is a pure function of its
arguments, so results do not depend on the worker count. Workers use the "spawn" start method (Windows-safe).
A job that raises is returned as an error record (worst fitness, rollouts still counted); a pool-level timeout
raises - jobs are never silently dropped.
"""
from __future__ import annotations

import math
import multiprocessing as mp
import os
import platform
import subprocess
import time
from dataclasses import dataclass, asdict, field

import mujoco
import numpy as np

from .locomotion import DEFAULT_CRITERIA, WalkingCriteria, aggregate, compute_metrics, fitness_components, rollout
from .morphology import BipedParams
from .phasegait import LOWER, UPPER, PhaseGaitController, PhaseGaitParams

ERROR_FITNESS = -10.0


@dataclass(frozen=True)
class OptimizerConfig:
    rollout_budget: int = 600
    train_seeds: tuple = (1000, 1001, 1002)
    duration: float = 6.0
    rng_seed: int = 0
    body: dict = field(default_factory=lambda: BipedParams().as_dict())
    batch_size: int = 20      # random search batch (= DE population, so both evaluate in equal-size waves)
    de_pop: int = 20
    de_f: float = 0.6
    de_cr: float = 0.8

    @property
    def n_candidates(self) -> int:
        return self.rollout_budget // len(self.train_seeds)


# --------------------------------------------------------------------------------------------------------
# evaluation jobs
# --------------------------------------------------------------------------------------------------------
def evaluate_vector(vector, body: dict, seeds, duration: float, crit: dict | None = None) -> dict:
    crit_obj = WalkingCriteria(**crit) if crit else DEFAULT_CRITERIA
    params = PhaseGaitParams.from_vector(vector)
    ctrl = PhaseGaitController(params)
    b = BipedParams(**body)
    per = []
    for s in seeds:
        m = compute_metrics(rollout(ctrl, b, s, duration), crit_obj)
        m["fitness"] = fitness_components(m, crit_obj)
        per.append(m)
    return aggregate(per)


def _eval_job(job: dict) -> dict:
    t0 = time.perf_counter()
    try:
        res = evaluate_vector(job["vector"], job["body"], job["seeds"], job["duration"], job.get("criteria"))
        return {"ok": True, "result": res, "wall_s": time.perf_counter() - t0}
    except Exception as e:  # recorded, never swallowed
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "wall_s": time.perf_counter() - t0}


class Executor:
    """workers=1 runs inline (used by tests); otherwise a spawn-context process pool."""

    def __init__(self, workers: int, timeout_s: float = 1800.0, fn=None):
        self.workers, self.timeout_s = workers, timeout_s
        self.fn = fn or _eval_job  # must be a picklable module-level function when workers > 1
        self.pool = mp.get_context("spawn").Pool(workers) if workers > 1 else None

    def map(self, jobs: list[dict]) -> list[dict]:
        if self.pool is None:
            out = [self.fn(j) for j in jobs]
        else:
            out = self.pool.map_async(self.fn, jobs, chunksize=1).get(self.timeout_s)
        if len(out) != len(jobs):
            raise RuntimeError(f"lost jobs: submitted {len(jobs)}, received {len(out)}")
        return out

    def close(self) -> None:
        if self.pool is not None:
            self.pool.close()
            self.pool.join()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def default_workers() -> int:
    return max(1, min(8, os.cpu_count() or 1))


# --------------------------------------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------------------------------------
def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def provenance(workers: int | None = None) -> dict:
    def git(*a):
        try:
            return subprocess.run(["git", *a], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return {"git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
            "mujoco": mujoco.__version__, "numpy": np.__version__, "python": platform.python_version(),
            "platform": platform.platform(), "cpu_count": os.cpu_count(), "workers": workers}


def _record(method: str, gen: int, idx: int, vector, job_out: dict, rollouts_before: int, n_seeds: int,
            seeds, extra: dict | None = None) -> dict:
    params = PhaseGaitParams.from_vector(np.clip(vector, LOWER, UPPER)).as_dict()
    rec = {"method": method, "generation": gen, "index": idx, "vector": [float(x) for x in vector],
           "params": params, "seeds": list(seeds), "rollouts_before": rollouts_before,
           "rollouts_after": rollouts_before + n_seeds, "wall_s": job_out["wall_s"]}
    if job_out["ok"]:
        r = job_out["result"]
        rec.update({"error": None, "fitness": r["fitness"], "fitness_worst": r["fitness_worst"],
                    "fitness_components": r["fitness_components"], "feasible": r["feasible"],
                    "walking_fraction": r["walking_fraction"], "label": r["label"], "labels": r["labels"],
                    "median_speed": r["median_speed"], "per_seed": r["per_seed"]})
    else:
        rec.update({"error": job_out["error"], "fitness": ERROR_FITNESS, "fitness_worst": ERROR_FITNESS,
                    "fitness_components": None, "feasible": False, "walking_fraction": 0.0, "label": "error",
                    "labels": ["error"] * n_seeds, "median_speed": None, "per_seed": []})
    if extra:
        rec.update(extra)
    return jsonable(rec)


def _jobs(vectors, cfg: OptimizerConfig, crit: dict | None) -> list[dict]:
    return [{"vector": [float(x) for x in v], "body": cfg.body, "seeds": list(cfg.train_seeds),
             "duration": cfg.duration, "criteria": crit} for v in vectors]


def _summarise(method: str, cfg: OptimizerConfig, history: list[dict], wall_s: float, hyper: dict,
               workers: int) -> dict:
    rollouts = sum(len(cfg.train_seeds) for _ in history)
    best = max(history, key=lambda r: (r["fitness"], -r["rollouts_before"]))
    feas = [r for r in history if r["feasible"]]
    curve, top = [], -1e9
    for r in history:
        top = max(top, r["fitness"])
        curve.append(top)
    labels: dict[str, int] = {}
    for r in history:
        labels[r["label"]] = labels.get(r["label"], 0) + 1
    return {"method": method, "config": jsonable(asdict(cfg)), "hyperparameters": hyper,
            "rollouts": rollouts, "candidates": len(history), "errors": sum(r["error"] is not None for r in history),
            "wall_s": wall_s, "best_index": history.index(best), "best_fitness": best["fitness"],
            "best_feasible": bool(feas), "n_feasible": len(feas),
            "best_feasible_index": history.index(max(feas, key=lambda r: r["fitness"])) if feas else None,
            "best_so_far": curve, "label_counts": labels, "provenance": provenance(workers)}


# --------------------------------------------------------------------------------------------------------
# optimizers
# --------------------------------------------------------------------------------------------------------
def random_search(cfg: OptimizerConfig, ex: Executor, crit: dict | None = None) -> tuple[list[dict], dict]:
    rng = np.random.default_rng(cfg.rng_seed)
    t0 = time.perf_counter()
    history: list[dict] = []
    n = cfg.n_candidates
    while len(history) < n:
        k = min(cfg.batch_size, n - len(history))
        vecs = LOWER + (UPPER - LOWER) * rng.random((k, len(LOWER)))
        outs = ex.map(_jobs(vecs, cfg, crit))
        for v, o in zip(vecs, outs):
            history.append(_record("random_search", len(history) // cfg.batch_size, len(history) % cfg.batch_size,
                                   v, o, len(history) * len(cfg.train_seeds), len(cfg.train_seeds), cfg.train_seeds))
    return history, _summarise("random_search", cfg, history, time.perf_counter() - t0,
                               {"sampling": "uniform in bounds", "batch_size": cfg.batch_size}, ex.workers)


def differential_evolution(cfg: OptimizerConfig, ex: Executor, crit: dict | None = None) -> tuple[list[dict], dict]:
    """DE/rand/1/bin, greedy selection (ties go to the trial), bounds by clipping. No polishing."""
    rng = np.random.default_rng(cfg.rng_seed)
    t0 = time.perf_counter()
    npop, dim = cfg.de_pop, len(LOWER)
    history: list[dict] = []
    pop = LOWER + (UPPER - LOWER) * rng.random((npop, dim))  # same RNG stream as random search's first batch
    outs = ex.map(_jobs(pop, cfg, crit))
    fit = np.empty(npop)
    for i, (v, o) in enumerate(zip(pop, outs)):
        history.append(_record("differential_evolution", 0, i, v, o, len(history) * len(cfg.train_seeds),
                               len(cfg.train_seeds), cfg.train_seeds, {"role": "init"}))
        fit[i] = history[-1]["fitness"]
    gen = 1
    while len(history) < cfg.n_candidates:
        k = min(npop, cfg.n_candidates - len(history))
        trials = np.empty((k, dim))
        for i in range(k):
            others = [j for j in range(npop) if j != i]
            a, b, c = rng.choice(others, 3, replace=False)
            mutant = pop[a] + cfg.de_f * (pop[b] - pop[c])
            cross = rng.random(dim) < cfg.de_cr
            cross[rng.integers(dim)] = True
            trials[i] = np.clip(np.where(cross, mutant, pop[i]), LOWER, UPPER)
        outs = ex.map(_jobs(trials, cfg, crit))
        for i, (v, o) in enumerate(zip(trials, outs)):
            history.append(_record("differential_evolution", gen, i, v, o, len(history) * len(cfg.train_seeds),
                                   len(cfg.train_seeds), cfg.train_seeds, {"role": "trial", "target_index": i}))
            if history[-1]["fitness"] >= fit[i]:
                pop[i], fit[i] = v, history[-1]["fitness"]
        gen += 1
    return history, _summarise("differential_evolution", cfg, history, time.perf_counter() - t0,
                               {"population": npop, "F": cfg.de_f, "CR": cfg.de_cr, "strategy": "rand/1/bin",
                                "bounds": "clip", "polish": False, "generations": gen}, ex.workers)


# --------------------------------------------------------------------------------------------------------
# replayable export
# --------------------------------------------------------------------------------------------------------
def candidate_export(rec: dict, body: dict, source: dict) -> dict:
    """Self-contained, replayable description of a candidate (controller + body + evaluation provenance)."""
    return {"controller": "phase_gait", "params": rec["params"], "body": body, "source": source,
            "training": {"seeds": rec["seeds"], "fitness": rec["fitness"], "label": rec["label"],
                         "feasible": rec["feasible"]}}


def controller_from_export(d: dict) -> tuple[PhaseGaitController, BipedParams]:
    if d.get("controller") != "phase_gait":
        raise ValueError(f"unsupported controller {d.get('controller')!r}")
    return PhaseGaitController(PhaseGaitParams(**d["params"]).validate()), BipedParams(**d["body"]).validate()
