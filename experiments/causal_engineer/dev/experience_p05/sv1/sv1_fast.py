"""P05-SV1 optional fast path (proposal section 8): the exact P0 predict / choose_k logic with the inner-fold distance matrix
computed once per inner fold instead of once per k.

Every numerical step is the unchanged P0 function (Space.dist, knn_rates, log_loss, folds, decide via decision_eval), in
P0's order; only the repeated, identical Space.dist(a, b, use) calls are reused. Space.dist is a deterministic function of
(X[a], X[b], use), so the cached matrix is bit-identical to the recomputed one. It may be used ONLY if sv1_selftest's
bit-identity gate (against p0.predict and sv0_lib.replicate) passes in the same fingerprint; otherwise the P0 path is used.
"""
from __future__ import annotations

import math

import numpy as np

from creature_forge import experience_p0 as p0
import sv0_lib as L


def choose_k(space: p0.Space, use, Y: np.ndarray, tr: np.ndarray, inner_groups: np.ndarray) -> int:
    """As p0.choose_k; the per-inner-fold distance and prior are computed once and reused for every k."""
    if not use:
        return 0
    best, best_ll = p0.K_GRID[0], math.inf
    inner = []
    for itr, ite, _ in p0.folds(inner_groups[tr]):
        a, b = tr[itr], tr[ite]
        inner.append((a, b, space.dist(a, b, use), Y[a].mean(0)))
    for k in p0.K_GRID:
        ll = []
        for a, b, D, prior in inner:
            P = p0.knn_rates(D, Y[a], k, prior)
            ll.append(p0.log_loss(P, Y[b]) * len(b))
        m = sum(ll) / len(tr)
        if m < best_ll - 1e-12:
            best, best_ll = k, m
    return best


def predict(space: p0.Space, use, Y: np.ndarray, groups: np.ndarray, outer_groups: np.ndarray) -> dict:
    """As p0.predict without shuffle_rng / k_fixed (SV1 never uses them)."""
    n, T = Y.shape
    P = np.zeros((n, T))
    prior_oof = np.zeros((n, T))
    gate_sim = np.zeros(n)
    ks: dict[str, int] = {}
    for tr, te, name in p0.folds(outer_groups):
        prior = Y[tr].mean(0)
        prior_oof[te] = prior
        if not use:
            P[te] = prior
            continue
        k = choose_k(space, use, Y, tr, groups)
        ks[name] = k
        D = space.dist(tr, te, use)
        P[te] = p0.knn_rates(D, Y[tr], k, prior)
        gate_sim[te] = -np.sort(D, axis=1)[:, :min(k, D.shape[1])].mean(1)
    return {"P": P, "prior": prior_oof, "gate_sim": gate_sim, "k": ks}


def replicate(X: np.ndarray, Y: np.ndarray, base: np.ndarray, idx, uses: dict | None = None) -> dict:
    """As sv0_lib.replicate (canonical layout, original labels, G* <= 2 rejected) with the fast predict."""
    uses = L.POLICIES if uses is None else uses
    Xs, Ys, gs, c = L.resample(X, Y, base, idx)
    g_star = int((c > 0).sum())
    if g_star <= 2:
        raise L.DegenerateReplicate(f"G* = {g_star}")
    space = p0.Space(Xs, L.BLOCKS)
    pred, ev = {}, {}
    for name, use in uses.items():
        pred[name] = predict(space, use, Ys, gs, gs)
        ev[name] = p0.decision_eval(pred[name], Ys)
    return {"X": Xs, "Y": Ys, "groups": gs, "c": c, "G_star": g_star, "space": space, "pred": pred, "eval": ev}
