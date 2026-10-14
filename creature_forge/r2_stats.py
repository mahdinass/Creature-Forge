"""Paired-proportion risk-difference statistics for R2 (no scipy).

Seeds are paired: the same final seeds and conditions are used for the selected winner ("new") and the frozen incumbent
("old"). With n pairs, b = new-only successes, c = old-only successes, theta = p_new - p_old.

* Non-inferiority with a NONZERO margin uses Tango's (1998) score test / score confidence interval for the paired
  risk difference (Stat. Med. 17:891-908), which is the standard replacement for McNemar when the null difference is
  not zero. H0: theta <= -margin  vs  H1: theta > -margin. The restricted maximum-likelihood estimate of the discordant
  probability under theta = theta0 has a closed form (derived in `restricted_q`); the score statistic is
  Z(theta0) = (theta_hat - theta0) / sqrt((2 q - theta0 - theta0^2) / n)   [q = restricted MLE of p_new-only].
  At theta0 = 0 it reduces to the McNemar statistic (b - c)/sqrt(b + c) (tested).
* Superiority keeps the exact two-sided McNemar test (`r1_stats.exact_mcnemar`).
* Hierarchical (fixed-sequence) decision: see `hierarchical_decision`.

Everything is cross-checked in tests/test_r2_stats.py by an independent numerical maximiser of the restricted
likelihood, the theta0 = 0 identity, and exact enumeration of the test's size at the margin.
"""
from __future__ import annotations

import math

from .r1_stats import exact_mcnemar

Z975 = 1.959963984540054


def restricted_q(b: int, c: int, n: int, theta0: float) -> float:
    """Restricted MLE of p_new-only given p_new-only - p_old-only = theta0 (concordant cells only enter via their total).
    Maximises b ln q + c ln(q - theta0) + m ln(1 - 2q + theta0), m = n - b - c: the stationarity condition is the
    quadratic 2 n q^2 - S q + b theta0 (1 + theta0) = 0, S = b (1 + 3 theta0) + c (1 + theta0) + 2 m theta0."""
    m = n - b - c
    S = b * (1 + 3 * theta0) + c * (1 + theta0) + 2 * m * theta0
    disc = max(0.0, S * S - 8 * n * b * theta0 * (1 + theta0))
    lo, hi = max(0.0, theta0), (1 + theta0) / 2
    roots = [(S + s * math.sqrt(disc)) / (4 * n) for s in (1, -1)]
    inside = [q for q in roots if lo - 1e-12 <= q <= hi + 1e-12]
    if not inside:
        raise ValueError(f"no admissible root for b={b}, c={c}, n={n}, theta0={theta0}: {roots}")
    return min(max(inside[0], lo), hi)


def tango_z(b: int, c: int, n: int, theta0: float) -> float:
    """Tango score statistic for H0: theta = theta0 (positive when the observed difference exceeds theta0)."""
    q = restricted_q(b, c, n, theta0)
    var = (2 * q - theta0 - theta0 * theta0) / n
    if var <= 0:
        return math.inf if (b - c) / n > theta0 else (-math.inf if (b - c) / n < theta0 else 0.0)
    return ((b - c) / n - theta0) / math.sqrt(var)


def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def tango_ci(b: int, c: int, n: int, z: float = Z975) -> tuple[float, float, float]:
    """Tango score interval for theta (default two-sided 95%): (theta_hat, lower, upper), by bisection on Z(theta0) = +-z."""
    th = (b - c) / n

    def solve(side: int) -> float:                      # side=-1: lower bound, +1: upper bound
        lo, hi = (-1.0 + 1e-9, th) if side < 0 else (th, 1.0 - 1e-9)
        f = (lambda t: tango_z(b, c, n, t) - z) if side < 0 else (lambda t: tango_z(b, c, n, t) + z)
        flo, fhi = f(lo), f(hi)
        if side < 0:
            if flo <= 0:                                # even theta0 ~ -1 is not rejected
                return -1.0
            if fhi >= 0:
                return th
        else:
            if fhi >= 0:
                return 1.0
            if flo <= 0:
                return th
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if f(mid) > 0:                              # f(lo) > 0 > f(hi) on both sides
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-13:
                break
        return 0.5 * (lo + hi)

    return th, solve(-1), solve(+1)


def noninferiority(b: int, c: int, n: int, margin: float = 0.05, alpha_one_sided: float = 0.025) -> dict:
    """Prespecified non-inferiority decision: non-inferior iff the one-sided Tango score test of H0: theta <= -margin
    rejects at `alpha_one_sided` (equivalently the lower bound of the two-sided 95% Tango interval exceeds -margin)."""
    z_crit = 1.959963984540054 if abs(alpha_one_sided - 0.025) < 1e-12 else _inv_norm_sf(alpha_one_sided)
    z = tango_z(b, c, n, -margin)
    th, lo, hi = tango_ci(b, c, n, z_crit)
    p = _norm_sf(z) if math.isfinite(z) else (0.0 if z > 0 else 1.0)
    return {"margin": margin, "alpha_one_sided": alpha_one_sided, "theta_hat": th, "tango_z_at_margin": z,
            "p_one_sided": p, "tango_ci": [lo, hi], "ci_level": 1 - 2 * alpha_one_sided,
            "non_inferior": bool(z > z_crit), "rule": f"non-inferior iff Tango lower bound ({1 - 2 * alpha_one_sided:.0%} two-sided) > -{margin}"}


def _inv_norm_sf(p: float) -> float:
    lo, hi = 0.0, 10.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _norm_sf(mid) > p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def hierarchical_decision(b: int, c: int, n: int, margin: float = 0.05, alpha_ni: float = 0.025, alpha_sup: float = 0.05) -> dict:
    """Fixed-sequence (closed) testing, each step at its full level, so the familywise error rate is not inflated:
    step 1 non-inferiority (preservation); step 2 superiority (exact two-sided McNemar at alpha_sup AND b > c) is tested
    only if step 1 succeeds. If step 1 fails, superiority is not tested (reported descriptively, never as confirmatory)."""
    ni = noninferiority(b, c, n, margin, alpha_ni)
    out = {"step1_noninferiority": ni, "step2_superiority": None,
           "claims": {"preservation_confirmed": ni["non_inferior"], "improvement_confirmed": False}}
    p = exact_mcnemar(b, c)
    if ni["non_inferior"]:
        sup = {"tested": True, "mcnemar_exact_two_sided_p": p, "alpha": alpha_sup, "b_gt_c": b > c}
        sup["superior"] = bool(p < alpha_sup and b > c)
        out["step2_superiority"] = sup
        out["claims"]["improvement_confirmed"] = sup["superior"]
    else:
        out["step2_superiority"] = {"tested": False, "descriptive_mcnemar_exact_two_sided_p": p,
                                    "note": "not tested confirmatorily because non-inferiority was not established"}
    return out
