"""Experience learning for walking recovery (stage L2 pilot): can optimisation runs on OTHER creatures improve the first decision
(a warm start) on an unfamiliar creature, beyond retrieval? numpy only; every function is pure and deterministic.

Design space (FIXED, 21-D, all in [0, 1])
  * d[0:17]  controller: u = (x - LOWER17) / (UPPER17 - LOWER17) in `walk_opt.ALL_NAMES` order (the 17-D family).
  * d[17:21] body log-ratios of (`foot_length`, `thigh_length`, `shank_length`, `torso_mass`): z = (ln(new/old) - ln 0.5) / (ln 1.5 - ln 0.5),
    i.e. the interventions ratio box [0.5, 1.5] of the creature's OWN base body mapped to [0, 1] (no change: z = ln 2 / ln 3 = 0.631).
    A leg parameter scales both legs by the same ratio. The design is RELATIVE to a base body, so it transfers across creatures.
  * NOT clipped by the creature's bounds. `from_design` raises `OutOfBounds` when the scaled body would leave the guided bounds;
    callers discard that point, take the next one, and record the discard (reject-not-clip).

Morphology input `morph_features` (6, dimensionless, from `creature_gen.features`):
  ln L, ln foot_to_leg, torso_frac, ln tau_ratio, friction, ln mass_total. They are z-scored with TRAINING statistics inside the models.

Learned model: `SurrogateEnsemble` predicts y = walking_count / n_train_seeds (a fraction in [0, 1]) of a (morphology, design) pair.
Warm-start decision: `propose_warm_starts`; non-learning baselines: `r2_start`, `knn_warm_start`, `mean_best_start`.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from . import interventions as iv
from . import walk_opt as wo
from .phasegait_fp import LOWER17, UPPER17

VERSION = "experience_v1"
BODY_DIMS = ("foot_length", "thigh_length", "shank_length", "torso_mass")
CTRL_DIM, DESIGN_DIM, MORPH_DIM = 17, 21, 6
MORPH_NAMES = ("ln_L", "ln_foot_to_leg", "torso_frac", "ln_tau_ratio", "friction", "ln_mass_total")
_LO_R, _HI_R = math.log(0.5), math.log(1.5)
_LEG = ("thigh_length", "shank_length", "foot_length")
STD_FLOOR = 0.01            # floor of the reference ensemble std (probability scale) in the applicability ratio
DEFAULT_BETA = 1.0          # warm-start rank = mean - beta * std (mildly risk-averse; one ensemble std of pessimism)
APPLICABILITY_LIMIT = 2.0   # ratio > 2 : "experience may not apply"


class OutOfBounds(ValueError):
    """A design point whose body would leave the guided bounds (never clipped)."""


# ------------------------------------------------------------------------------------------------ morphology
def morph_features(body_or_features) -> np.ndarray:
    """(6,) = [ln L, ln foot_to_leg, torso_frac, ln tau_ratio, friction, ln mass_total] of a body dict (compiles the model via
    `creature_gen.features`) or of an already computed features dict (keys L, foot_to_leg, torso_frac, tau_ratio, friction, mass_total)."""
    f = body_or_features
    if not (isinstance(f, dict) and "foot_to_leg" in f and "mass_total" in f):
        from . import creature_gen as cg
        f = cg.features(f)
    return np.array([math.log(f["L"]), math.log(f["foot_to_leg"]), f["torso_frac"], math.log(f["tau_ratio"]),
                     f["friction"], math.log(f["mass_total"])], dtype=float)


# ------------------------------------------------------------------------------------------------ design conversions
def _z_of_ratio(ratio: float) -> float:
    return (math.log(ratio) - _LO_R) / (_HI_R - _LO_R)


def design_of(body, vector, base_body) -> np.ndarray:
    """21-D design of (body, 15/17-D vector) relative to base_body. Raises OutOfBounds if a body ratio is outside [0.5, 1.5]
    (the point is not representable; nothing is clipped)."""
    base, b = wo._base_dict(base_body), wo._base_dict(body)
    v = np.asarray(wo.pad_to_17(vector), dtype=float)
    d = np.empty(DESIGN_DIM)
    d[:CTRL_DIM] = (v - LOWER17) / (UPPER17 - LOWER17)
    for j, p in enumerate(BODY_DIMS):
        z = _z_of_ratio(float(b[p]) / float(base[p]))
        if not -1e-9 <= z <= 1 + 1e-9:
            raise OutOfBounds(f"{p} ratio {float(b[p]) / float(base[p]):.4f} is outside [0.5, 1.5]")
        d[CTRL_DIM + j] = min(1.0, max(0.0, z))
    return d


def to_design(space_names: Sequence[str], x, base_body) -> np.ndarray:
    """21-D design of a `cma_search` candidate: `x` is the encoded point in the order of `space_names` (result["space_names"]),
    base_body the body the search ran on. The space must contain all 17 controller names; body names missing from it mean ratio 1."""
    names, x = list(space_names), np.asarray(x, dtype=float)
    if x.shape != (len(names),):
        raise ValueError("x and space_names differ in length")
    missing = [n for n in wo.ALL_NAMES if n not in names]
    if missing:
        raise ValueError(f"space lacks controller names {missing}; the design space needs all 17")
    ctrl = [n for n in names if n in wo.ALL_NAMES]
    body_p = tuple(n for n in names if n in wo.BODY_PARAMS)
    extra = [n for n in body_p if n not in BODY_DIMS]
    if extra:
        raise ValueError(f"body names {extra} are not in the design space {BODY_DIMS}")
    base = wo._base_dict(base_body)
    space = wo.SearchSpace(tuple(ctrl), body_p)
    d = np.empty(DESIGN_DIM)
    for n in wo.ALL_NAMES:
        d[wo.ALL_NAMES.index(n)] = x[names.index(n)]
    for j, p in enumerate(BODY_DIMS):
        if p in body_p:
            lo, hi = wo._log_interval(space, base, p)
            lr = lo + float(x[names.index(p)]) * (hi - lo)
            d[CTRL_DIM + j] = (lr - _LO_R) / (_HI_R - _LO_R)
        else:
            d[CTRL_DIM + j] = _z_of_ratio(1.0)
    return d


def from_design(d, base_body) -> tuple[dict, list]:
    """(body dict, 17-D vector) of a design point on base_body. Raises OutOfBounds (never clips) when any scaled body value is
    outside the guided bounds."""
    d = np.asarray(d, dtype=float)
    if d.shape != (DESIGN_DIM,) or not np.all(np.isfinite(d)) or d.min() < 0 or d.max() > 1:
        raise ValueError("design must be 21 finite numbers in [0, 1]")
    base = wo._base_dict(base_body)
    body = dict(base)
    bounds = iv.mode_bounds("guided")
    for j, p in enumerate(BODY_DIMS):
        ratio = math.exp(_LO_R + float(d[CTRL_DIM + j]) * (_HI_R - _LO_R))
        lo, hi = bounds[p]
        for f in ((p, p + "_r") if p in _LEG else (p,)):
            val = float(base[f]) * ratio
            if not lo <= val <= hi:
                raise OutOfBounds(f"{f}={val:.5g} outside guided bounds [{lo:g}, {hi:g}] (ratio {ratio:.3f})")
            body[f] = val
    vec = LOWER17 + (UPPER17 - LOWER17) * d[:CTRL_DIM]
    return body, [float(v) for v in vec]


def r2_design() -> np.ndarray:
    """Design of R2 with zero body change (the frozen R2 winner, padded with fp_kd = fp_kv = 0)."""
    from . import creature_walk as cw
    v = (np.asarray(wo.pad_to_17(list(cw.R2_WINNER))) - LOWER17) / (UPPER17 - LOWER17)
    return np.concatenate([v, np.full(len(BODY_DIMS), _z_of_ratio(1.0))])


# ------------------------------------------------------------------------------------------------ records and dataset
def _rank_key(c: dict) -> tuple:
    return (c["walking_count"], c["survival_count"], c["mean_fitness"])


def record_designs(rec: dict) -> np.ndarray:
    """(n_cand, 21) designs of every logged candidate of a campaign record (record["search"] needs candidates + space_names)."""
    s = rec["search"]
    return np.array([to_design(s["space_names"], c["x"], rec["body"]) for c in s["candidates"]])


def record_best(rec: dict) -> tuple[np.ndarray, dict]:
    """(design, candidate) of the record's best logged candidate: lexicographic (walking, survival, fitness); earliest on a tie."""
    cands = rec["search"]["candidates"]
    i = max(range(len(cands)), key=lambda j: (_rank_key(cands[j]), -j))
    return to_design(rec["search"]["space_names"], cands[i]["x"], rec["body"]), cands[i]


def record_morph(rec: dict) -> np.ndarray:
    return morph_features(rec["features"] if rec.get("features") else rec["body"])


def build_dataset(records: Sequence[dict]) -> dict:
    """Arrays from campaign records (one creature's `cma_search(log_candidates=True)` each; fields creature, region, body,
    features, search{candidates, space_names, train_seeds}). X = [morph(6) raw, design(21)]; y = walking_count / n_train;
    also survival (fraction), fitness, groups (creature id), regions, n_train."""
    X, y, sv, fit, groups, regions = [], [], [], [], [], []
    for rec in records:
        s = rec["search"]
        n = len(s["train_seeds"])
        m = record_morph(rec)
        D = record_designs(rec)
        for c, d in zip(s["candidates"], D):
            X.append(np.concatenate([m, d]))
            y.append(c["walking_count"] / n)
            sv.append(c["survival_count"] / n)
            fit.append(c["mean_fitness"])
            groups.append(rec["creature"])
            regions.append(rec["region"])
    return {"X": np.array(X).reshape(-1, MORPH_DIM + DESIGN_DIM), "y": np.array(y), "survival": np.array(sv),
            "fitness": np.array(fit), "groups": np.array(groups), "regions": np.array(regions)}


def leakage_check(train_ids, test_ids, train_regions, test_regions) -> None:
    """Raises ValueError if any creature id or any morphology region is shared by the training and test sets."""
    ids = set(train_ids) & set(test_ids)
    regs = set(train_regions) & set(test_regions)
    if ids or regs:
        raise ValueError(f"train/test leakage: shared creatures {sorted(ids)}, shared regions {sorted(regs)}")


# ------------------------------------------------------------------------------------------------ learned model
def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class SurrogateEnsemble:
    """Ensemble of tanh MLPs (hidden sizes `hidden`, sigmoid output) trained with binary cross-entropy on the soft target y
    (a fraction), Adam, mini-batches. Member i: its own Generator(SeedSequence([seed, i])); a random ~20 % of the training
    CREATURES (`val_frac`) is held out for early stopping (patience epochs on validation BCE, best weights restored); the
    remaining rows are bootstrap-resampled. `fit(X, y, groups)`: X = [morph raw (6), design (21)]. Deterministic for a seed."""

    def __init__(self, n_models: int = 5, hidden=(64, 64), epochs: int = 100, lr: float = 1e-2, weight_decay: float = 1e-4,
                 seed: int = 0, batch_size: int = 128, val_frac: float = 0.2, patience: int = 20):
        self.n_models, self.hidden, self.epochs = int(n_models), tuple(hidden), int(epochs)
        self.lr, self.weight_decay, self.seed = float(lr), float(weight_decay), int(seed)
        self.batch_size, self.val_frac, self.patience = int(batch_size), float(val_frac), int(patience)
        self.members: list = []
        self.info: list = []
        self.mu = self.sd = None
        self.train_median_std = None

    # -- preprocessing
    def _prep(self, X):
        X = np.asarray(X, dtype=float)
        Z = X.copy()
        Z[:, :MORPH_DIM] = (X[:, :MORPH_DIM] - self.mu) / self.sd
        Z[:, MORPH_DIM:] = (X[:, MORPH_DIM:] - 0.5) * 2.0
        return Z

    @staticmethod
    def _forward(W, Z):
        acts = [Z]
        for k, (w, b) in enumerate(W):
            a = acts[-1] @ w + b
            acts.append(_sigmoid(a) if k == len(W) - 1 else np.tanh(a))
        return acts

    @staticmethod
    def _bce(p, y):
        p = np.clip(p, 1e-7, 1 - 1e-7)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    def fit(self, X, y, groups) -> "SurrogateEnsemble":
        X, y, groups = np.asarray(X, dtype=float), np.asarray(y, dtype=float), np.asarray(groups)
        if X.ndim != 2 or X.shape[1] != MORPH_DIM + DESIGN_DIM or len(y) != len(X) or len(groups) != len(X):
            raise ValueError("X must be (m, 27), y and groups length m")
        if not len(X) or y.min() < 0 or y.max() > 1:
            raise ValueError("need rows and y in [0, 1]")
        self.mu = X[:, :MORPH_DIM].mean(0)
        self.sd = np.maximum(X[:, :MORPH_DIM].std(0), 1e-6)
        Z = self._prep(X)
        ug = sorted(set(groups.tolist()))
        sizes = [Z.shape[1], *self.hidden, 1]
        self.members, self.info = [], []
        for i in range(self.n_models):
            rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([self.seed, i])))
            perm = [ug[j] for j in rng.permutation(len(ug))]
            nval = int(round(self.val_frac * len(ug))) if len(ug) >= 3 else 0
            vset = set(perm[:nval])
            isval = np.array([g in vset for g in groups.tolist()])
            tr, va = np.flatnonzero(~isval), np.flatnonzero(isval)
            tr = tr[rng.integers(0, len(tr), len(tr))]                      # bootstrap
            W = [[rng.standard_normal((a, b)) * math.sqrt(1.0 / a) * (1.0 if k < len(sizes) - 2 else 0.5), np.zeros(b)]
                 for k, (a, b) in enumerate(zip(sizes[:-1], sizes[1:]))]
            m = [[np.zeros_like(p) for p in layer] for layer in W]
            v = [[np.zeros_like(p) for p in layer] for layer in W]
            t, best, best_W, best_ep, bad = 0, math.inf, None, 0, 0
            for ep in range(self.epochs):
                order = tr[rng.permutation(len(tr))]
                for s in range(0, len(order), self.batch_size):
                    idx = order[s:s + self.batch_size]
                    acts = self._forward(W, Z[idx])
                    delta = (acts[-1] - y[idx][:, None]) / len(idx)
                    t += 1
                    for k in range(len(W) - 1, -1, -1):
                        gw = acts[k].T @ delta + self.weight_decay * W[k][0]
                        gb = delta.sum(0)
                        if k > 0:
                            delta = (delta @ W[k][0].T) * (1 - acts[k] ** 2)
                        for q, g in ((0, gw), (1, gb)):
                            m[k][q] = 0.9 * m[k][q] + 0.1 * g
                            v[k][q] = 0.999 * v[k][q] + 0.001 * g * g
                            W[k][q] = W[k][q] - self.lr * (m[k][q] / (1 - 0.9 ** t)) / (np.sqrt(v[k][q] / (1 - 0.999 ** t)) + 1e-8)
                if len(va):
                    vl = self._bce(self._forward(W, Z[va])[-1][:, 0], y[va])
                    if vl < best - 1e-6:
                        best, best_W, best_ep, bad = vl, [[p.copy() for p in layer] for layer in W], ep, 0
                    else:
                        bad += 1
                        if bad >= self.patience:
                            break
            if best_W is None:
                best_W, best_ep = W, ep
            self.members.append(best_W)
            self.info.append({"member": i, "val_creatures": sorted(vset), "best_epoch": int(best_ep),
                              "val_bce": None if not len(va) else float(best), "n_train_rows": int(len(tr))})
        sub = np.linspace(0, len(X) - 1, min(len(X), 2000)).astype(int)
        self.train_median_std = float(np.median(self.predict(X[sub])[1]))
        return self

    def predict(self, X) -> tuple[np.ndarray, np.ndarray]:
        """(mean, std) across members of the predicted walking fraction, each (m,)."""
        if not self.members:
            raise RuntimeError("model is not fitted")
        Z = self._prep(np.atleast_2d(X))
        P = np.array([self._forward(W, Z)[-1][:, 0] for W in self.members])
        return P.mean(0), P.std(0)


# ------------------------------------------------------------------------------------------------ pool and decisions
def build_pool(train_records: Sequence[dict], per_creature: int = 20, include_r2: bool = True) -> list[dict]:
    """Candidate warm-start designs: each training creature's `per_creature` best logged candidates (lexicographic (walking,
    survival, fitness), earliest first on ties) plus the R2 start (zero body change). Exact duplicates are dropped."""
    pool, seen = [], set()

    def add(d, source, rank):
        key = tuple(np.round(d, 9))
        if key not in seen:
            seen.add(key)
            pool.append({"design": np.asarray(d, dtype=float), "source": source, "rank_in_source": rank})

    if include_r2:
        add(r2_design(), "r2", 0)
    for rec in train_records:
        cands = rec["search"]["candidates"]
        order = sorted(range(len(cands)), key=lambda j: (tuple(-a for a in _rank_key(cands[j])), j))[:per_creature]
        for r, j in enumerate(order):
            add(to_design(rec["search"]["space_names"], cands[j]["x"], rec["body"]), rec["creature"], r)
    return pool


def _try_realise(d, body, source, rank, discarded):
    try:
        b, v = from_design(d, body)
        return {"body": b, "vector": v}
    except OutOfBounds as e:
        discarded.append({"source": source, "rank": rank, "reason": str(e)})
        return None


def propose_warm_starts(model: SurrogateEnsemble, body, candidate_pool: Sequence[dict], k: int = 3, beta: float = DEFAULT_BETA,
                        features: dict | None = None) -> list[dict]:
    """Score every pool point on the NEW creature's morphology, rank by mean - beta * std, and return the top-k FEASIBLE
    points (a point whose body would leave the guided bounds is discarded, never clipped, and the next one is taken; the
    discards are listed in each item's `discarded_before`). Items: design, body, vector, source, mean, std, score, rank,
    applicability (mean std of the returned top-k / max(training-median std, STD_FLOOR); > 2 means experience may not apply)."""
    m = morph_features(features if features is not None else body)
    D = np.array([p["design"] for p in candidate_pool])
    mean, std = model.predict(np.hstack([np.tile(m, (len(D), 1)), D]))
    score = mean - beta * std
    order = sorted(range(len(D)), key=lambda i: (-score[i], i))
    out, discarded = [], []
    for r, i in enumerate(order):
        real = _try_realise(D[i], body, candidate_pool[i]["source"], r, discarded)
        if real is None:
            continue
        out.append({**real, "design": D[i], "source": candidate_pool[i]["source"], "mean": float(mean[i]), "std": float(std[i]),
                    "score": float(score[i]), "rank": r, "beta": float(beta), "discarded_before": list(discarded)})
        if len(out) == k:
            break
    ref = max(model.train_median_std, STD_FLOOR)
    app = float(np.mean([o["std"] for o in out])) / ref if out else math.inf
    for o in out:
        o["applicability"] = app
        o["may_not_apply"] = app > APPLICABILITY_LIMIT
    return out


def r2_start(body) -> dict:
    """Baseline 1: the frozen R2 winner (padded) on the unchanged body. No learning, no morphology use."""
    from . import creature_walk as cw
    return {"body": wo._base_dict(body), "vector": list(wo.pad_to_17(list(cw.R2_WINNER))), "source": "r2", "design": r2_design()}


def knn_warm_start(body, train_records: Sequence[dict], k: int = 1, features: dict | None = None) -> list[dict]:
    """Baseline 2 (retrieval): the best logged solution of the nearest training creature(s) in z-scored morph-feature space
    (Euclidean; z-scoring with the training records' statistics; ties by record order). Its DESIGN (controller + relative body
    ratios) is applied to the new body. Returns the k nearest in order, feasible or not decided by the caller via `realise`."""
    M = np.array([record_morph(r) for r in train_records])
    mu, sd = M.mean(0), np.maximum(M.std(0), 1e-6)
    m = morph_features(features if features is not None else body)
    dist = np.sqrt((((M - mu) / sd - (m - mu) / sd) ** 2).sum(1))
    order = sorted(range(len(M)), key=lambda i: (dist[i], i))[:k]
    return [{"design": record_best(train_records[i])[0], "source": train_records[i]["creature"], "distance": float(dist[i])}
            for i in order]


def mean_best_start(train_records: Sequence[dict]) -> list[dict]:
    """Baseline 3 (one universal answer): the medoid of the training creatures' best designs in the 21-D design space (the best
    solution with the smallest summed Euclidean distance to all other best solutions; ties by record order). Returned as an ordered
    list (medoid first, then by increasing summed distance) so a caller can fall back when the first is out of bounds."""
    B = np.array([record_best(r)[0] for r in train_records])
    tot = np.sqrt(((B[:, None, :] - B[None, :, :]) ** 2).sum(-1)).sum(1)
    order = sorted(range(len(B)), key=lambda i: (tot[i], i))
    return [{"design": B[i], "source": train_records[i]["creature"], "summed_distance": float(tot[i])} for i in order]


def realise(candidates: Sequence[dict], body) -> tuple[dict | None, list[dict]]:
    """First candidate (dict with "design") whose body is inside the guided bounds -> (item with body, vector; discards before it).
    (None, discards) if none is feasible. Never clips."""
    discarded: list = []
    for r, c in enumerate(candidates):
        real = _try_realise(c["design"], body, c.get("source"), r, discarded)
        if real is not None:
            return {**c, **real, "discarded_before": list(discarded)}, discarded
    return None, discarded
