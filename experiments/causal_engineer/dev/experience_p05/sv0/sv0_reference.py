"""P05-SV0 independent reference (proposal CF-V2-P05-SV0 revision 4, section 5).

A pure-Python re-implementation of the P0 LOBO kNN decision pipeline, written from the specification (P0 docstrings and
revision 2 section 6): lists and math.fsum only; it imports neither numpy nor creature_forge. It also holds a brute-force H4
enumerator over all joint derangements. Honest limit: same author as the code it checks, so it guards against plumbing,
vectorisation and indexing errors, not a shared misreading of the specification (the hand fixtures cover that).
"""
from __future__ import annotations

import itertools
import math
from fractions import Fraction

K_GRID = (1, 3, 5, 9, 15, 25)
EPS = 1e-4                 # log-loss clip
SD_FLOOR = 1e-9            # sd <= floor (or not finite) -> 1
TIE_W = 1e-9               # pick = argmax(P + TIE_W * prior)
IMPROVE = 1e-12            # a larger k must improve the inner loss strictly by this much


# ------------------------------------------------------------------------------------------------ kNN pipeline
def _moments(values: list[float]) -> tuple[float, float]:
    """Population mean and sd of the non-missing values; all missing -> (0, 1); sd <= SD_FLOOR -> 1."""
    v = [x for x in values if not math.isnan(x)]
    if not v:
        return 0.0, 1.0
    mu = math.fsum(v) / len(v)
    sd = math.sqrt(math.fsum((x - mu) ** 2 for x in v) / len(v))
    return (mu if math.isfinite(mu) else 0.0), (sd if math.isfinite(sd) and sd > SD_FLOOR else 1.0)


def dist(X: list[list[float]], tr: list[int], te: list[int], blocks: dict, use) -> list[list[float]]:
    """Fold-standardised block distance: per block the mean squared z-difference, blocks summed in `use` order.
    Moments come from the training rows only; a missing value sits at z = 0."""
    cols = sorted({c for b in use for c in blocks[b]})
    st = {c: _moments([X[i][c] for i in tr]) for c in cols}

    def z(i):
        return {c: (0.0 if math.isnan(X[i][c]) else (X[i][c] - st[c][0]) / st[c][1]) for c in cols}
    ztr = [z(j) for j in tr]
    out = []
    for i in te:
        zi = z(i)
        row = []
        for zj in ztr:
            d = 0.0
            for b in use:
                cs = blocks[b]
                d += math.fsum((zi[c] - zj[c]) ** 2 for c in cs) / len(cs)
            row.append(d)
        out.append(row)
    return out


def prior(Y: list[list[float]], rows: list[int]) -> list[float]:
    T = len(Y[0])
    return [math.fsum(Y[i][t] for i in rows) / len(rows) for t in range(T)]


def knn(drow: list[float], Y: list[list[float]], tr: list[int], k: int, pri: list[float]) -> tuple[list[float], list[int]]:
    """Laplace-shrunk neighbour rates (sum_N Y + prior) / (k + 1); ties broken by training row order (stable sort).
    k is clamped to the number of training rows. Returns (P row, positions of the neighbours within tr)."""
    k = min(k, len(drow))
    nb = sorted(range(len(drow)), key=drow.__getitem__)[:k]
    return [(math.fsum(Y[tr[j]][t] for j in nb) + pri[t]) / (k + 1.0) for t in range(len(pri))], nb


def _log_loss_total(P: list[list[float]], Yrows: list[list[float]]) -> float:
    """Mean binary log loss over all (row, tool) cells with p clipped to [EPS, 1 - EPS]."""
    terms = []
    for p_row, y_row in zip(P, Yrows):
        for p, y in zip(p_row, y_row):
            p = min(max(p, EPS), 1 - EPS)
            terms.append(y * math.log(p) + (1 - y) * math.log(1 - p))
    return -math.fsum(terms) / len(terms)


def choose_k(X, Y, tr: list[int], groups: list, blocks: dict, use, check=None) -> tuple[int, dict]:
    """Inner leave-one-group-out over the training rows: for each k the fold-size-weighted mean log loss; the first k
    reaching the minimum wins unless a later k improves it by more than IMPROVE. Returns (k, {k: loss})."""
    labels = sorted({groups[i] for i in tr})
    inner = []
    for g in labels:
        a = [i for i in tr if groups[i] != g]
        b = [i for i in tr if groups[i] == g]
        inner.append((a, b, dist(X, a, b, blocks, use), prior(Y, a)))
        if check:
            check()
    best, best_ll, losses = K_GRID[0], math.inf, {}
    for k in K_GRID:
        parts = []
        for a, b, D, pri in inner:
            P = [knn(drow, Y, a, k, pri)[0] for drow in D]
            parts.append(_log_loss_total(P, [Y[i] for i in b]) * len(b))
        m = math.fsum(parts) / len(tr)
        losses[k] = m
        if m < best_ll - IMPROVE:
            best, best_ll = k, m
    return best, losses


def predict(X, Y, groups: list, blocks: dict, use, check=None) -> dict:
    """Out-of-fold P for every row; outer and inner folds by `groups`. Also returns per-row neighbour sets (global row
    indices), per-fold k, the inner-loss gap between the chosen k and the runner-up, and the gap between the k-th and
    (k+1)-th nearest distance (diagnostic)."""
    n = len(Y)
    P: list = [None] * n
    pri_oof: list = [None] * n
    neigh: list = [None] * n
    gate_sim = [0.0] * n
    ks, kgap, bgap = {}, {}, {}
    for g in sorted(set(groups)):
        tr = [i for i in range(n) if groups[i] != g]
        te = [i for i in range(n) if groups[i] == g]
        pri = prior(Y, tr)
        k, losses = choose_k(X, Y, tr, groups, blocks, use, check)
        name = str(g)
        ks[name] = k
        others = [abs(v - losses[k]) for kk, v in losses.items() if kk != k]
        kgap[name] = min(others) if others else math.inf
        D = dist(X, tr, te, blocks, use)
        gaps = []
        for r, i in enumerate(te):
            P[i], nb = knn(D[r], Y, tr, k, pri)
            pri_oof[i] = pri
            neigh[i] = tuple(sorted(tr[j] for j in nb))
            srt = sorted(D[r])
            kk = min(k, len(srt))
            gate_sim[i] = -math.fsum(srt[:kk]) / kk
            if kk < len(srt):
                gaps.append(srt[kk] - srt[kk - 1])
        bgap[name] = min(gaps) if gaps else math.inf
        if check:
            check()
    return {"P": P, "prior": pri_oof, "gate_sim": gate_sim, "neighbours": neigh, "k": ks, "kgap": kgap, "boundary_gap": bgap}


def _argmax(v: list[float]) -> int:
    best = 0
    for j in range(1, len(v)):
        if v[j] > v[best]:
            best = j
    return best


def decision(P: list[list[float]], pri: list[list[float]], Y: list[list[float]]) -> dict:
    """pick = first argmax of P + TIE_W * prior; pi0 = first argmax of the training prior; values read off Y.
    margin = top-1 minus top-2 of the pick score (near-tie diagnostic)."""
    pick, pi0, v_mem, v_pi0, margin = [], [], [], [], []
    for p_row, q_row, y_row in zip(P, pri, Y):
        s = [p + TIE_W * q for p, q in zip(p_row, q_row)]
        j, j0 = _argmax(s), _argmax(q_row)
        srt = sorted(s, reverse=True)
        pick.append(j)
        pi0.append(j0)
        v_mem.append(y_row[j])
        v_pi0.append(y_row[j0])
        margin.append(srt[0] - srt[1] if len(srt) > 1 else math.inf)
    return {"pick": pick, "pi0": pi0, "v_mem": v_mem, "v_pi0": v_pi0, "margin": margin}


# ------------------------------------------------------------------------------------------------ H4 brute force
_CONTROLS = {"S-base": ("base", "row"), "S-family-free": ("base_bin", "row"), "S-cf-conditional": ("base", "cf"),
             "S-global": ("all", "row")}


def derangements(m: int) -> list[tuple[int, ...]]:
    return [p for p in itertools.permutations(range(m)) if all(p[i] != i for i in range(m))]


def subfactorial_sum(n: int) -> int:
    """!n = n! sum_{k=0..n} (-1)^k / k!, evaluated exactly with fractions (independent of any recurrence)."""
    s = Fraction(0)
    for k in range(n + 1):
        s += Fraction((-1) ** k, math.factorial(k))
    v = s * math.factorial(n)
    if v.denominator != 1:
        raise ArithmeticError(n)
    return int(v)


def brute_h4(table: list[dict], control: str) -> dict:
    """Enumerate every joint derangement of the groups with >= 2 records; D_enum = their number (1 = identity only, when
    no such group exists); F = exact mean over them of the moved-and-different fraction of ALL records; N3 as in E2."""
    grouping, value = _CONTROLS[control]
    by: dict = {}
    for i, r in enumerate(table):
        k = r["base"] if grouping == "base" else (r["base"], r["bin"]) if grouping == "base_bin" else 0
        by.setdefault(k, []).append(i)
    big = [by[k] for k in sorted(by) if len(by[k]) >= 2]
    n = len(table)
    count, total = 0, Fraction(0)
    for combo in itertools.product(*[derangements(len(g)) for g in big]):
        moved = 0
        for g, p in zip(big, combo):
            for pos, src in enumerate(p):
                moved += table[g[src]][value] != table[g[pos]][value]
        total += Fraction(moved, n)
        count += 1
    bases = {r["base"] for r in table}
    covered = {table[i]["base"] for g in big for i in g}
    return {"D_enum": count, "n_groups_ge2": len(big), "F": total / count, "N3": Fraction(len(covered), len(bases))}
