"""P05-SV0 library (proposal CF-V2-P05-SV0 revision 4, sections 3 and 5): base resampling and refit wrapper, H4
non-degeneracy calculator (amendment 2.2 section 1, erratum 2.2a E2), interval helpers.

Pure numpy plus the exact P0 learner (creature_forge.experience_p0), called unchanged. No simulation, no file or network I/O.
SV0 verifies that this code computes what the protocol specifies; it establishes no coverage or inference validity.
"""
from __future__ import annotations

import math
from fractions import Fraction

import numpy as np

from creature_forge import experience_p0 as p0

BLOCKS = {"morph": list(range(0, 7)), "obs": list(range(7, 15)), "cf": list(range(15, 42))}     # calc section E layout
POLICIES = {"interv": ("obs", "morph", "cf"), "obs_morph": ("obs", "morph")}


class DegenerateReplicate(Exception):
    """A replicate with G* <= 2 distinct bases: outer LOBO (G* = 1) or inner LOBO (G* = 2) has an empty training set."""


# ------------------------------------------------------------------------------------------------ resampling (section 3.1)
def resample(X: np.ndarray, Y: np.ndarray, base: np.ndarray, idx) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Rows of one base-bootstrap replicate in the canonical layout: original base order, the c_b copies of a base adjacent.
    Every row keeps its ORIGINAL base id as group label. Returns (X*, Y*, groups*, c) with c_b the multiplicity of base b.
    Bases must be labelled 0..G-1 and idx must hold G draws from that range."""
    X, Y, base = np.asarray(X, float), np.asarray(Y, float), np.asarray(base)
    idx = np.asarray(idx, dtype=np.int64)
    G = len(idx)
    if not np.array_equal(np.unique(base), np.arange(G)):
        raise ValueError("bases must be labelled 0..G-1 with G = len(idx)")
    if idx.ndim != 1 or idx.min() < 0 or idx.max() >= G:
        raise ValueError("idx must be G draws from 0..G-1")
    c = np.bincount(idx, minlength=G)
    rows = np.concatenate([np.tile(np.flatnonzero(base == b), int(c[b])) for b in range(G) if c[b]])
    return X[rows], Y[rows], base[rows], c


def copy_index(groups: np.ndarray, m: int) -> np.ndarray:
    """Copy number of each row within its base (canonical layout: copy j occupies rows j*m .. j*m+m-1 of that base)."""
    out = np.zeros(len(groups), dtype=np.int64)
    for g in np.unique(groups):
        pos = np.flatnonzero(groups == g)
        out[pos] = np.arange(len(pos)) // m
    return out


# ------------------------------------------------------------------------------------------------ refit entry points
def refit_eval(space: p0.Space, Y: np.ndarray, groups: np.ndarray, use) -> tuple[dict, dict]:
    """Exact P0 pipeline on the given rows: LOBO outer folds and inner-LOBO k choice by `groups`. No G* check."""
    pred = p0.predict(space, use, Y, groups, groups)
    return pred, p0.decision_eval(pred, Y)


def refit_eval_fixed_k(space: p0.Space, Y: np.ndarray, groups: np.ndarray, use, k_fixed: dict) -> tuple[dict, dict]:
    """FIXTURE entry point: as refit_eval but with k supplied per outer fold, so no inner CV runs and G* >= 2 suffices.
    k_fixed must name exactly the distinct groups with positive integer k (P0 silently falls back to choose_k otherwise)."""
    names = {str(g) for g in np.unique(groups).tolist()}
    if len(names) < 2:
        raise ValueError("refit_eval_fixed_k needs G* >= 2: at G* = 1 the outer LOBO training set is empty")
    if set(k_fixed) != names:
        raise ValueError(f"k_fixed keys {sorted(k_fixed)} != groups {sorted(names)}")
    if any(isinstance(k, bool) or not isinstance(k, int) or k < 1 for k in k_fixed.values()):
        raise ValueError("k_fixed values must be positive integers")
    pred = p0.predict(space, use, Y, groups, groups, k_fixed=dict(k_fixed))
    return pred, p0.decision_eval(pred, Y)


def replicate(X: np.ndarray, Y: np.ndarray, base: np.ndarray, idx, uses: dict | None = None,
              blocks: dict | None = None) -> dict:
    """PRODUCTION entry point (the only one SV1 may call): resample, reject G* <= 2, then refit every policy in `uses`
    (default: interv and obs_morph) with inner-CV k on the replicate."""
    uses = POLICIES if uses is None else uses
    Xs, Ys, gs, c = resample(X, Y, base, idx)
    g_star = int((c > 0).sum())
    if g_star <= 2:
        raise DegenerateReplicate(f"G* = {g_star}")
    space = p0.Space(Xs, BLOCKS if blocks is None else blocks)
    pred, ev = {}, {}
    for name, use in uses.items():
        pred[name], ev[name] = refit_eval(space, Ys, gs, use)
    return {"X": Xs, "Y": Ys, "groups": gs, "c": c, "G_star": g_star, "space": space, "pred": pred, "eval": ev}


def theta(ev: dict, a: str = "interv", b: str = "obs_morph") -> float:
    """theta-hat* = mean over all G*m replicate rows of d = v(a) - v(b); copies enter with their multiplicity."""
    return float(np.mean(ev[a]["v_mem"] - ev[b]["v_mem"]))


def leak_check(space: p0.Space, groups: np.ndarray, use) -> np.ndarray:
    """Flag every test row that has a training row at block distance exactly 0 in its outer LOBO fold."""
    groups = np.asarray(groups)
    flagged = np.zeros(len(groups), bool)
    for tr, te, _ in p0.folds(groups):
        if len(tr):
            flagged[te] |= (space.dist(tr, te, use) == 0.0).any(1)
    return flagged


def g_star_draws(G: int, n: int, rng: np.random.Generator) -> np.ndarray:
    """Number of distinct bases in each of n base-bootstrap index draws (no fitting)."""
    idx = np.sort(rng.integers(0, G, size=(n, G)), axis=1)
    return 1 + (np.diff(idx, axis=1) != 0).sum(1)


def expected_g_star(G: int) -> float:
    return G * (1.0 - (1.0 - 1.0 / G) ** G)


# ------------------------------------------------------------------------------------------------ H4 calculator (E2)
H4_CONTROLS = {
    # control: (grouping, value permuted); groups are within one LOBO training fold
    "S-base": ("base", "row"),
    "S-family-free": ("base_bin", "row"),
    "S-cf-conditional": ("base", "cf"),
    "S-global": ("all", "row"),
}


def subfactorial(n: int) -> int:
    """!n by the integer recurrence !n = (n - 1)(!(n - 1) + !(n - 2)), !0 = 1, !1 = 0 (exact for any n)."""
    a, b = 1, 0
    if n == 0:
        return a
    for i in range(2, n + 1):
        a, b = b, (i - 1) * (a + b)
    return b


def h4_groups(table: list[dict], control: str) -> list[list[int]]:
    grouping = H4_CONTROLS[control][0]
    key = {"base": lambda r: r["base"], "base_bin": lambda r: (r["base"], r["bin"]), "all": lambda _r: 0}[grouping]
    by: dict = {}
    for i, r in enumerate(table):
        by.setdefault(key(r), []).append(i)
    return [by[k] for k in sorted(by)]


def h4_calc(table: list[dict], control: str) -> dict:
    """Erratum E2 for one training fold. Records are dicts with 'base', 'bin', 'row' and 'cf'.
    D = prod over groups with |g| >= 2 of !|g| (None if no such group: the control is the identity, Lemma 5).
    F (N1) = expected fraction of ALL records whose assigned value comes from another record and differs from their own,
    under a uniform derangement of each group (the source of a record's value is uniform over the other |g| - 1 records).
    N3 = fraction of bases with a record in a group of size >= 2. Valid iff F >= 1/2 and N3 >= 1/2; the regime is only
    considered for a valid control."""
    value = H4_CONTROLS[control][1]
    groups = h4_groups(table, control)
    big = [g for g in groups if len(g) >= 2]
    F = Fraction(0)
    for g in big:
        for i in g:
            F += Fraction(sum(table[j][value] != table[i][value] for j in g if j != i), len(g) - 1)
    F /= len(table)
    bases = sorted({r["base"] for r in table})
    covered = {table[i]["base"] for g in big for i in g}
    N3 = Fraction(len(covered), len(bases))
    D = math.prod(subfactorial(len(g)) for g in big) if big else None
    valid = F >= Fraction(1, 2) and N3 >= Fraction(1, 2)
    regime = None
    if valid and D is not None:
        regime = ("single deterministic contrast" if D == 1 else "limited exact set" if D < 20
                  else "genuine permutation distribution")
    return {"D": D, "regime": regime, "F": F, "N3": N3, "valid": valid, "n_groups_ge2": len(big)}


def derange_within(keys: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Permutation of positions: a uniform derangement inside every group of equal keys with >= 2 members (rejection
    sampling); singletons stay fixed."""
    keys = np.asarray(keys)
    perm = np.arange(len(keys))
    for k in np.unique(keys):
        pos = np.flatnonzero(keys == k)
        if len(pos) < 2:
            continue
        while True:
            p = rng.permutation(len(pos))
            if not (p == np.arange(len(pos))).any():
                break
        perm[pos] = pos[p]
    return perm


# ------------------------------------------------------------------------------------------------ interval helpers
def cr1_se(d, base) -> float:
    """Base-cluster CR1 standard error of mean(d), the calc section E formula: sqrt(G/(G-1) sum_b (T_b - n_b e)^2) / n."""
    d = np.asarray(d, float)
    _, inv = np.unique(np.asarray(base), return_inverse=True)
    G = int(inv.max()) + 1
    e = d.mean()
    tot = np.bincount(inv, weights=d, minlength=G)
    cnt = np.bincount(inv, minlength=G)
    return math.sqrt(G / (G - 1.0) * ((tot - cnt * e) ** 2).sum()) / len(d)


def percentile_ci(values, lo: float = 5.0, hi: float = 95.0) -> tuple[float, float]:
    a, b = np.percentile(np.asarray(values, float), [lo, hi])          # numpy default: linear interpolation
    return float(a), float(b)


def wilson_lower(k: int, n: int, z: float) -> float:
    """Wilson score lower bound; z is a parameter (one- vs two-sided is an SV1 decision, B10)."""
    p, z2 = k / n, z * z
    return (p + z2 / (2 * n) - z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / (1 + z2 / n)


def half_splits(G: int, n_splits: int, rng: np.random.Generator) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """n_splits distinct splits of bases 0..G-1 into two disjoint halves of G/2 (a split and its mirror are the same)."""
    if G % 2 or n_splits > math.comb(G, G // 2) // 2:
        raise ValueError("G must be even and n_splits at most C(G, G/2)/2")
    seen, out = set(), []
    while len(out) < n_splits:
        perm = rng.permutation(G)
        a = tuple(sorted(int(i) for i in perm[:G // 2]))
        b = tuple(sorted(int(i) for i in perm[G // 2:]))
        key = a if 0 in a else b
        if key in seen:
            continue
        seen.add(key)
        out.append((a, b))
    return out
