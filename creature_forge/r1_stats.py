"""Exact / closed-form statistics for the R1 paired comparison (no scipy).

Everything here is deterministic and unit-tested against hand-computed values. Seeds are paired: the same 30 final
seeds and simulation conditions are used for the R1 winner ("new") and the Phase 2A incumbent ("old").
"""
from __future__ import annotations

import math

import numpy as np


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k), X ~ Binomial(n, p)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return float(sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1)))


def exact_mcnemar(b: int, c: int) -> float:
    """Two-sided exact McNemar p (b, c = the two discordant counts): 2 * P(X <= min(b, c)), X ~ Bin(b + c, 1/2), capped at 1."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2.0 * binom_cdf(min(b, c), n, 0.5))


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided binomial interval by bisection on the tail probabilities."""
    def bisect(too_high):
        """Smallest-gap p in [0, 1] where `too_high(p)` flips from False to True (monotone)."""
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if too_high(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    # lower: P(X >= k | p) = alpha/2, increasing in p; upper: P(X <= k | p) = alpha/2, decreasing in p
    lower = 0.0 if k == 0 else bisect(lambda p: 1.0 - binom_cdf(k - 1, n, p) > alpha / 2)
    upper = 1.0 if k == n else bisect(lambda p: binom_cdf(k, n, p) <= alpha / 2)
    return (lower, upper)


def paired_table(new_success, old_success) -> dict:
    new = np.asarray(new_success, dtype=bool)
    old = np.asarray(old_success, dtype=bool)
    if new.shape != old.shape:
        raise ValueError("paired outcomes must have the same length")
    return {"both": int((new & old).sum()), "new_only": int((new & ~old).sum()),
            "old_only": int((~new & old).sum()), "neither": int((~new & ~old).sum()), "n": int(new.size)}


def newcombe_paired_diff(a: int, b: int, c: int, d: int, alpha_z: float = 1.959963984540054) -> tuple[float, float, float]:
    """Newcombe (1998) method 10 score interval for p_new - p_old from paired counts (a both, b new only, c old only,
    d neither). Returns (diff, lower, upper)."""
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n, alpha_z)
    l2, u2 = wilson(a + c, n, alpha_z)
    A = (a + b) * (c + d) * (a + c) * (b + d)
    if A == 0:
        phi = 0.0
    else:
        B = a * d - b * c
        C = B - n / 2 if B > n / 2 else (0.0 if B >= 0 else B + n / 2)
        phi = C / math.sqrt(A)
    diff = p1 - p2
    lo = diff - math.sqrt(max(0.0, (p1 - l1) ** 2 + (u2 - p2) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2)))
    hi = diff + math.sqrt(max(0.0, (u1 - p1) ** 2 + (p2 - l2) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2)))
    return diff, max(-1.0, lo), min(1.0, hi)


def paired_comparison(new_success, old_success, alpha: float = 0.05) -> dict:
    """Full prespecified paired analysis: 2x2 table, discordant counts, exact two-sided McNemar p, paired difference
    with a Newcombe interval, per-arm Wilson and exact intervals, and the conditional odds ratio (discordant ratio)
    with an exact interval."""
    t = paired_table(new_success, old_success)
    a, b, c, d, n = t["both"], t["new_only"], t["old_only"], t["neither"], t["n"]
    p = exact_mcnemar(b, c)
    diff, lo, hi = newcombe_paired_diff(a, b, c, d)
    k_new, k_old = a + b, a + c
    out = {"table": t, "discordant": {"new_only": b, "old_only": c, "total": b + c},
           "mcnemar_exact_two_sided_p": p, "alpha": alpha,
           "paired_difference": {"estimate": diff, "newcombe_95ci": [lo, hi]},
           "new": {"successes": k_new, "n": n, "rate": k_new / n, "wilson_95ci": list(wilson(k_new, n)),
                   "exact_95ci": list(clopper_pearson(k_new, n))},
           "old": {"successes": k_old, "n": n, "rate": k_old / n, "wilson_95ci": list(wilson(k_old, n)),
                   "exact_95ci": list(clopper_pearson(k_old, n))},
           "superior": bool(p < alpha and diff > 0)}
    if b + c > 0:
        L, U = clopper_pearson(b, b + c)
        odds = lambda q: (q / (1 - q)) if q < 1 else None  # noqa: E731
        out["conditional_odds_ratio"] = {"estimate": (b / c) if c else None, "exact_95ci": [odds(L), odds(U)],
                                         "note": "new-only / old-only among discordant pairs; null = 1"}
    else:
        out["conditional_odds_ratio"] = {"estimate": None, "exact_95ci": [None, None], "note": "no discordant pairs"}
    return out
