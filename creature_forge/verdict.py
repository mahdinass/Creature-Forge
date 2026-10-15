"""Deterministic verdict rule `verdict_v1` (contracts section 6.3): paired sign test on held-out validation seeds.

Pure statistics, no physics and no model input. Model confidence is never an argument. The same function judges AI,
random-baseline and heuristic arms.

  diff_i = candidate_i - original_i on the same seed. A pair is a TIE when |diff_i| <= `resolution` (the score resolution
  of the challenge: the push bisection step, the sampling step of survival time, ...). Ties carry no sign information
  and are excluded from the test. With fewer than `MIN_NON_TIED` non-tied pairs the verdict is INCONCLUSIVE.

  VERIFIED_IMPROVEMENT  one-sided exact sign test p < ALPHA for "candidate better" AND median paired diff >= required
                        minimum effect AND the optional guard passed.
  WORSE                 the mirrored test: p < ALPHA for "candidate worse" AND median paired diff <= -required minimum effect.
  NOT_VERIFIED          enough non-tied pairs but neither of the above.
  INCONCLUSIVE          fewer than MIN_NON_TIED non-tied pairs, or a seed could not be scored (a None score = ERROR).

The thresholds are DRAFT until the null pilot (experiments/forge_loop/null_pilot) is read; keep them only in `MIN_EFFECT`.
"""
from __future__ import annotations

import math
from typing import Sequence

VERDICT_RULE_VERSION = "verdict_v1"
ALPHA = 0.05
MIN_NON_TIED = 6
# Minimum paired median effect (score units: stand seconds, push newtons, walk metres). push: BOTH the absolute and the
# relative (fraction of the ORIGINAL median) bound must be met; when the original median is 0 only the absolute bound counts.
# Frozen 2026-10-15 after the null pilot. Push: with 2.5 N bisection ties the 3 N bar is effectively two steps (5 N).
# Stand: 0.5 s (1.0 s was out of reach for weak creatures that fall within ~1 s).
MIN_EFFECT = {"push": {"abs": 3.0, "rel": 0.10}, "stand": {"abs": 0.5}, "walk": {"abs": 0.5}}
# Score resolution used for ties when the caller does not know better. Push: max_force / 2**5 = 2.5 N (bisection step).
DEFAULT_RESOLUTION = {"push": 2.5, "stand": 0.05, "walk": 0.05}
STATUSES = ("VERIFIED_IMPROVEMENT", "NOT_VERIFIED", "WORSE", "INCONCLUSIVE")
_EPS = 1e-9


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def sign_counts(diffs: Sequence[float], tol: float = 0.0) -> dict:
    """wins (diff > tol), losses (diff < -tol), ties (|diff| <= tol)."""
    wins = sum(1 for d in diffs if d > tol + _EPS)
    losses = sum(1 for d in diffs if d < -tol - _EPS)
    return {"wins": wins, "losses": losses, "ties": len(diffs) - wins - losses}


def _binom_upper(k: int, n: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 1/2), exact."""
    if n <= 0:
        return 1.0
    if k <= 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def paired_sign_test(diffs: Sequence[float], tol: float = 0.0, alternative: str = "greater") -> float:
    """One-sided exact binomial sign test p-value on the non-tied pairs (ties: |diff| <= tol).

    alternative "greater": H1 = candidate better (small p when wins dominate); "less": the mirror. All pairs tied -> 1.0."""
    if alternative not in ("greater", "less"):
        raise ValueError("alternative must be 'greater' or 'less'")
    c = sign_counts(diffs, tol)
    n = c["wins"] + c["losses"]
    return _binom_upper(c["wins"] if alternative == "greater" else c["losses"], n)


def median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    return float(s[n // 2]) if n % 2 else float(0.5 * (s[n // 2 - 1] + s[n // 2]))


def required_effect(kind: str, original_median: float) -> dict:
    """The minimum effect that applies for this challenge and original median: {abs, rel, required}."""
    if kind not in MIN_EFFECT:
        raise ValueError(f"kind must be one of {sorted(MIN_EFFECT)}, got {kind!r}")
    spec = MIN_EFFECT[kind]
    absolute = float(spec["abs"])
    rel = spec.get("rel")
    required = absolute
    if rel is not None and original_median > 0:
        required = max(absolute, float(rel) * float(original_median))
    return {"abs": absolute, "rel": None if rel is None else float(rel), "required": required}


def _pass_rate(orig_pass: Sequence[bool] | None, cand_pass: Sequence[bool] | None) -> dict | None:
    if orig_pass is None or cand_pass is None:
        return None
    out = {}
    for name, flags in (("original", orig_pass), ("candidate", cand_pass)):
        k, n = int(sum(bool(f) for f in flags)), len(flags)
        lo, hi = wilson_interval(k, n)
        out[name] = {"k": k, "n": n, "rate": (k / n if n else 0.0), "ci95": [lo, hi], "method": "wilson"}
    return out


def verdict(kind: str, original_scores: Sequence, candidate_scores: Sequence, *, resolution: float | None = None,
            guard: dict | None = None, original_pass: Sequence[bool] | None = None,
            candidate_pass: Sequence[bool] | None = None) -> dict:
    """`verdict_v1` for one candidate against the original, paired by position (same seed order). Scores higher = better.

    `resolution`: tie tolerance in score units (default `DEFAULT_RESOLUTION[kind]`). `guard`: optional dict with a boolean
    `passed` (and a free-text `reason`); a failed guard downgrades VERIFIED_IMPROVEMENT to NOT_VERIFIED. `original_pass` /
    `candidate_pass`: optional per-seed PASS flags for the Wilson pass-rate block. A `None` score (a seed that errored) makes
    the verdict INCONCLUSIVE, never a silent drop."""
    if kind not in MIN_EFFECT:
        raise ValueError(f"kind must be one of {sorted(MIN_EFFECT)}, got {kind!r}")
    if len(original_scores) != len(candidate_scores):
        raise ValueError("original and candidate scores must be paired (same length, same seed order)")
    tol = DEFAULT_RESOLUTION[kind] if resolution is None else float(resolution)
    if tol < 0 or not math.isfinite(tol):
        raise ValueError("resolution must be a finite non-negative number")
    n = len(original_scores)
    base = {"rule": VERDICT_RULE_VERSION, "kind": kind, "n": n, "resolution": tol, "alpha": ALPHA, "min_non_tied": MIN_NON_TIED,
            "pass_rate": _pass_rate(original_pass, candidate_pass)}
    errors = [i for i in range(n) if original_scores[i] is None or candidate_scores[i] is None]
    if errors:
        return {**base, "status": "INCONCLUSIVE", "wins": None, "losses": None, "ties": None, "median_diff": None,
                "p_one_sided": None, "p_worse": None, "min_effect": None, "errors": errors,
                "reasons": [f"{len(errors)} of {n} paired seeds could not be scored (pair indices {errors}); no statistic is computed"]}
    for x in list(original_scores) + list(candidate_scores):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
            raise ValueError(f"scores must be finite numbers or None, got {x!r}")
    diffs = [float(c) - float(o) for o, c in zip(original_scores, candidate_scores)]
    cnt = sign_counts(diffs, tol)
    non_tied = cnt["wins"] + cnt["losses"]
    med = median(diffs)
    p_better = paired_sign_test(diffs, tol, "greater")
    p_worse = paired_sign_test(diffs, tol, "less")
    eff = required_effect(kind, median(list(map(float, original_scores))) if n else 0.0)
    out = {**base, **cnt, "median_diff": med, "p_one_sided": p_better, "p_worse": p_worse, "min_effect": eff, "errors": [],
           "non_tied": non_tied}
    reasons: list[str] = [f"{cnt['wins']} wins, {cnt['losses']} losses, {cnt['ties']} ties (|diff| <= {tol:g}) of {n} paired seeds",
                          f"median paired diff {med:+.4g}"]
    if non_tied < MIN_NON_TIED:
        reasons.append(f"only {non_tied} non-tied pairs; at least {MIN_NON_TIED} are needed for a verdict")
        return {**out, "status": "INCONCLUSIVE", "reasons": reasons}
    guard_ok = guard is None or bool(guard.get("passed", False))
    if p_better < ALPHA and med >= eff["required"] - _EPS:
        if guard_ok:
            reasons.append(f"sign test p={p_better:.4f} < {ALPHA} and median diff >= required minimum effect {eff['required']:.4g}")
            return {**out, "status": "VERIFIED_IMPROVEMENT", "reasons": reasons}
        reasons.append(f"guard failed: {(guard or {}).get('reason', 'no reason given')}; improvement not credited")
        return {**out, "status": "NOT_VERIFIED", "reasons": reasons}
    if p_worse < ALPHA and med <= -eff["required"] + _EPS:
        reasons.append(f"mirrored sign test p={p_worse:.4f} < {ALPHA} and median diff <= -{eff['required']:.4g}: candidate is worse")
        return {**out, "status": "WORSE", "reasons": reasons}
    if p_better < ALPHA:
        reasons.append(f"sign test significant (p={p_better:.4f}) but median diff {med:+.4g} below the minimum effect {eff['required']:.4g}")
    elif p_worse < ALPHA:
        reasons.append(f"mirrored sign test significant (p={p_worse:.4f}) but median diff {med:+.4g} not beyond -{eff['required']:.4g}")
    else:
        reasons.append(f"sign test not significant (p={p_better:.4f})")
    return {**out, "status": "NOT_VERIFIED", "reasons": reasons}
