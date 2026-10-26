"""H3 research only: bounded antisymmetric stance residual on the existing FP gait.

No production registry changes. Importing this module performs no physics or I/O.
The legacy plant bridge is serial and scoped; native equivalence is a future gate.
"""
from contextlib import contextmanager
from copy import deepcopy
import math
import threading

import numpy as np

CAP = 0.15


def split_vector(vector):
    v = np.asarray(vector, dtype=float)
    if v.ndim != 1 or len(v) not in (17, 19) or not np.all(np.isfinite(v)):
        raise ValueError("H3 expects a finite 17-D or 19-D vector")
    if len(v) == 19 and np.any(np.abs(v[17:]) > 1):
        raise ValueError("residual gains must be in [-1, 1]")
    return v[:17].tolist(), tuple(v[17:]) if len(v) == 19 else None


class StanceResidual:
    """Adds signed hip/ankle demand; native actuator clipping remains authoritative.

    Same reset/sense/torque contract as PhaseGaitFPController. The base controller
    computes phase and all existing feedback first. Neither hidden fault nor
    verifier output is an input. This is conventional parameter adaptation, not RL.
    """
    name = "h3_stance_residual_v1"

    def __init__(self, base, gains=(0., 0.), *, log=False):
        gains = tuple(float(x) for x in gains)
        if len(gains) != 2 or not all(math.isfinite(x) and abs(x) <= 1 for x in gains):
            raise ValueError("two finite residual gains in [-1,1] required")
        self.base, self.gains, self.log = base, gains, log
        self.p = base.p  # legacy rich-trace gain metadata only
        self.samples = []

    def reset(self, torque_limit, weight_n):
        if not math.isfinite(torque_limit) or torque_limit <= 0:
            raise ValueError("positive finite torque limit required")
        self.base.reset(torque_limit, weight_n)
        self.limit = float(torque_limit)
        self.samples = []

    def sense(self, t, force):
        return self.base.sense(t, force)

    def torque(self, t, pitch, pitch_rate, q, qd):
        tau = self.base.torque(t, pitch, pitch_rate, q, qd)
        residual = np.zeros(6)
        if self.gains != (0., 0.):
            u = min(1., max(0., t / self.base._ramp_s))
            ramp = u * u * (3 - 2 * u)
            for leg, sign in ((0, 1), (1, -1)):
                phase = (self.base.phi + .5 * leg) % 1.
                if self.base.est.deb[leg] and phase < self.p.duty:
                    bump = math.sin(math.pi * phase / self.p.duty) ** 2
                    for joint, gain in zip((0, 2), self.gains):
                        residual[3 * leg + joint] = sign * gain * CAP * self.limit * ramp * bump
        if self.log:
            self.samples.append({"t_pre_step": float(t), "phase": float(self.base.phi),
                "loaded": list(map(bool, self.base.est.deb)), "base_demand": list(map(float, tau)),
                "residual": residual.tolist()})
        # Identity includes object/dtype preservation; no numerical +0 perturbation.
        return tau if self.gains == (0., 0.) else tau + residual


_bridge_lock = threading.Lock()


@contextmanager
def controller_scope(gains, *, log=False):
    """Temporarily inject a factory into the unchanged hidden-plant local import.

    For dedicated single-thread research worker processes only. Reject nesting
    and concurrent threads rather than leaking an experimental factory. Always
    restore on exceptions. This bridge is deliberately absent from release APIs.
    """
    from . import phasegait_init as factory
    if threading.current_thread() is not threading.main_thread() or threading.active_count() != 1:
        raise RuntimeError("H3 bridge requires a dedicated single-thread process")
    if not _bridge_lock.acquire(blocking=False):
        raise RuntimeError("nested H3 bridge")
    original = factory.controller_from_vector
    made = []
    try:
        def create(vector, body=None):
            base = original(vector, body=body)
            ctrl = StanceResidual(base, gains, log=log)
            made.append(ctrl)
            return ctrl
        factory.controller_from_vector = create
        yield made
    finally:
        factory.controller_from_vector = original
        _bridge_lock.release()


def walk_job(job):
    from . import hidden_plant as hp
    base, gains = split_vector(job["vector"])
    if gains is None:
        return hp.walk_job(job)
    with controller_scope(gains):
        return hp.walk_job({**job, "vector": base})


def seed_job(job, plant=None):
    from . import hidden_plant as hp
    base, gains = split_vector(job["controllers"]["walk"]["vector"])
    if gains is None:
        return hp.seed_job(job, plant=plant)
    clean = deepcopy(job)
    clean["controllers"]["walk"]["vector"] = base
    with controller_scope(gains):
        return hp.seed_job(clean, plant=plant)


class BudgetPool:
    """Serial legacy pool adapter; reserve before each native job, including errors.

    Limits both attempted rollouts and ten-second equivalents. A future outer
    process pool may run independent case commands, each with a frozen local cap.
    """
    def __init__(self, max_rollouts, max_equivalents, *, inner=None, on_reserve=None):
        if max_rollouts <= 0 or not math.isfinite(max_equivalents) or max_equivalents <= 0:
            raise ValueError("positive budgets required")
        self.max_rollouts, self.max_equivalents = max_rollouts, max_equivalents
        self.rollouts = 0
        self.equivalents = 0.
        self.inner, self.on_reserve = inner, on_reserve

    def imap(self, fn, jobs):
        from . import hidden_plant as hp
        target = walk_job if fn is hp.walk_job else fn
        jobs = list(jobs)
        cost = 0.
        for job in jobs:
            duration = job.get("duration", job.get("spec", {}).get("duration"))
            if duration is None or not math.isfinite(duration) or duration <= 0:
                raise ValueError("finite positive job duration required")
            cost += duration / 10.
        if self.rollouts + len(jobs) > self.max_rollouts or self.equivalents + cost > self.max_equivalents + 1e-9:
            raise RuntimeError("H3 physical budget exhausted before dispatch")
        self.rollouts += len(jobs)
        self.equivalents += cost
        if self.on_reserve:
            self.on_reserve(self.rollouts, self.equivalents)
        if self.inner:
            yield from self.inner.imap(target, jobs)
        else:
            for i, job in enumerate(jobs): yield i, target(job)


def search(body, vector, plant, *, expanded, budget, seeds, selection, noise_seed, pool):
    """Matched CMA kernel/population/objective; only two added dimensions differ.

    Budget includes initial candidate, training and 8-seed selection of two
    finalists. No FULL outcomes are inspected here. Uses saved-candidate train
    records; selection chooses the finalist once, before independent verification.
    """
    from . import hidden_plant as hp, walk_opt as wo
    from .phasegait_fp import LOWER17, UPPER17
    base, gains = split_vector(vector)
    if gains is not None or len(seeds) != 4 or len(selection) != 8 or set(seeds) & set(selection):
        raise ValueError("17-D start, 4 train and 8 disjoint selection seeds required")
    if budget < 68 or budget % 4:
        raise ValueError("budget must be a multiple of four >=68")
    lo = np.r_[LOWER17, [-1., -1.]] if expanded else LOWER17
    hi = np.r_[UPPER17, [1., 1.]] if expanded else UPPER17
    initial = np.r_[base, [0., 0.]] if expanded else np.asarray(base)
    mean = (initial-lo)/(hi-lo)
    rng = np.random.default_rng(noise_seed)
    cma = wo._CMA(len(lo), 12, mean, .2)
    evaluate = hp.make_eval_fn(plant, seeds, pool=pool)
    records = []
    train_budget = budget - 16
    used = 0
    def evaluate_points(points):
        nonlocal used
        vectors = [(lo+(hi-lo)*p).tolist() for p in points]
        recs = evaluate([(body, v) for v in vectors])
        used += 4 * len(vectors)
        if any(r.get("error") for r in recs):
            raise RuntimeError("training errors; preserve attempted budget, stop case")
        records.extend({"vector": v, "train": r} for v,r in zip(vectors,recs))
        return recs
    evaluate_points([mean])
    while used + 48 <= train_budget:
        points = cma.sample(rng)
        recs = evaluate_points(points)
        # Ordinal ranks encode exactly the existing lexicographic objective.
        order = sorted(range(12), key=lambda i: wo._score(recs[i]), reverse=True)
        ranks = np.empty(12)
        for rank, i in enumerate(order): ranks[i] = 12-rank
        cma.update(points, ranks)
    remaining = (train_budget-used)//4
    if remaining:
        evaluate_points(cma.sample(rng)[:remaining])
    best = sorted(range(len(records)), key=lambda i: wo._score(records[i]["train"]), reverse=True)
    # Distinct candidate identities, including incumbent as a possible finalist.
    finalists = []
    for i in best:
        if records[i]["vector"] not in [r["vector"] for r in finalists]: finalists.append(records[i])
        if len(finalists) == 2: break
    if len(finalists) != 2: raise RuntimeError("fewer than two distinct finalists")
    selected = hp.make_eval_fn(plant, selection, pool=pool)([(body,r["vector"]) for r in finalists])
    if any(r.get("error") for r in selected): raise RuntimeError("selection error")
    winner = max(range(2), key=lambda i: wo._score(selected[i]))
    return {"candidate": {"body": body, "vector": finalists[winner]["vector"]},
        "training": records, "finalists": finalists, "selection": selected,
        "selected_index": winner, "policy_rollouts": used+16, "noise_seed": noise_seed}
