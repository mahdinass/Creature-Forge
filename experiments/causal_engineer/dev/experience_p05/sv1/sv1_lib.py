"""P05-SV1 library (proposal CF-V2-P05-SV1, docs/plans/EXPERIENCE_P05_SV1_PROPOSAL.md): synthetic datasets, ground truths,
interval methods and the coverage / admission arithmetic.

Synthetic only. The learner is the exact P0 pipeline (creature_forge.experience_p0, unchanged); resampling uses the
SV0-validated sv0_lib (unchanged). Estimands (section 2):
    theta_hat(D)   LOBO estimate, mean over rows of v(interv) - v(obs_morph) with the realised Y   (interval centre)
    theta_cond(D)  the same LOBO picks scored with the true Q                                        (secondary truth)
    theta_G        E_D[theta_cond(D)], estimated from independent truth datasets                    (PRIMARY truth)
    theta_new(D)   policy fitted on all G bases, applied to fresh bases, scored with Q              (secondary truth)
"""
from __future__ import annotations

import hashlib
import math
import statistics

import numpy as np

from creature_forge import experience_p0 as p0
import p05_design_calc as calc
import sv0_lib as L
import sv1_fast as F

SV1_ROOT = 2026102390                 # disjoint from SV0 (2026102370 + <= 31) and calc section E (20261023 + 7 / + 11)
PHASES = {"selftest": 9, "bench": 8, "pilot": 1, "confirm": 2}
PURPOSES = {"data": 1, "truth": 2, "boot": 3, "half": 4, "new": 5, "eval": 6, "eval_boot": 7, "eval_half": 8,
            "eval_new": 9, "truth_new": 10, "bench": 11}
SCEN = {"null": "null (no feature-predictable tool heterogeneity)", "info": "interventions add information",
        "obs": "observation sufficient"}
CELLS = {"A-null": (28, "null"), "A-info": (28, "info"), "A-obs": (28, "obs"), "B-null": (12, "null"), "B-info": (12, "info")}
CELL_CODE = {c: i + 1 for i, c in enumerate(CELLS)}
M_INST = 3
NOMINAL = 0.90
TOL = 1e-12                           # closed intervals; theta_hat lies on the 1/(G m) lattice
METHODS = ("M1", "M2", "M3", "M4", "M5", "C0", "C1", "C2")


# ------------------------------------------------------------------------------------------------ seeds and data
def rng_for(phase: str, cell: str, purpose: str, s: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([SV1_ROOT, PHASES[phase], CELL_CODE[cell], PURPOSES[purpose], int(s)]))


def fixed_params(scenario: str) -> dict:
    """Population parameters exactly as calc.learning_inflation: default_rng(calc.SEED + 7)."""
    sc = calc.SCENARIOS[SCEN[scenario]]
    frng = np.random.default_rng(calc.SEED + 7)
    return {"E_o": frng.normal(size=(9, 8)), "E_c": frng.normal(size=(9, 27)),
            "theta": frng.normal(0.0, sc["theta"], (9, calc.TOOLS)), "alpha": frng.normal(-1.5, 0.7, calc.TOOLS),
            "noise_o": sc["noise_o"], "noise_c": sc["noise_c"]}


def dataset(fixed: dict, G: int, rng: np.random.Generator):
    return calc._synth(rng, fixed, G, M_INST)                     # X (3G x 42), Q (3G x 10), Y, base


def sha(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ fitting and truths
def fit(X: np.ndarray, Y: np.ndarray, base: np.ndarray, fast: bool) -> dict:
    """LOBO fit of both policies on the given rows; returns {policy: decision_eval dict}."""
    space = p0.Space(X, L.BLOCKS)
    out = {}
    for name, use in L.POLICIES.items():
        pred = F.predict(space, use, Y, base, base) if fast else p0.predict(space, use, Y, base, base)
        out[name] = p0.decision_eval(pred, Y)
    return out


def theta_hat(ev: dict) -> float:
    return float(np.mean(ev["interv"]["v_mem"] - ev["obs_morph"]["v_mem"]))


def theta_cond(ev: dict, Q: np.ndarray) -> float:
    r = np.arange(len(Q))
    return float(np.mean(Q[r, ev["interv"]["pick"]] - Q[r, ev["obs_morph"]["pick"]]))


def deploy(fixed: dict, X: np.ndarray, Y: np.ndarray, base: np.ndarray, rng_new: np.random.Generator, n_new_bases: int,
           fast: bool, uses: dict | None = None) -> tuple[float, float]:
    """theta_new(D): each policy fitted on ALL G bases (k by inner LOBO over all G, P0 primitives, training-row
    standardisation) and applied to n_new_bases fresh bases from the same population, scored with their true Q.
    Returns (value difference, its base-cluster CR1 standard error over the fresh instances)."""
    uses = L.POLICIES if uses is None else uses
    Xn, Qn, _Yn, base_n = calc._synth(rng_new, fixed, n_new_bases, M_INST)
    n = len(Y)
    tr, te = np.arange(n), n + np.arange(len(Xn))
    space = p0.Space(np.vstack([X, Xn]), L.BLOCKS)
    prior = Y.mean(0)
    r = np.arange(len(Qn))
    vals = []
    for name in ("interv", "obs_morph"):
        use = uses[name]
        k = F.choose_k(space, use, Y, tr, base) if fast else p0.choose_k(space, use, Y, tr, base)
        P = p0.knn_rates(space.dist(tr, te, use), Y, k, prior)
        pick = p0.decide(P, np.broadcast_to(prior, P.shape))
        vals.append(Qn[r, pick])
    diff = vals[0] - vals[1]
    return float(diff.mean()), float(L.cr1_se(diff, base_n))


# ------------------------------------------------------------------------------------------------ intervals
def half_variance(diffs) -> float:
    """M4: Var(theta_hat) estimate from R half-sample differences, mean((thA - thB)^2) / 4."""
    return float(np.mean(np.square(np.asarray(diffs, float))) / 4.0)


def cr1_interval(d: np.ndarray, base: np.ndarray, G: int) -> tuple[float, float, float]:
    se = L.cr1_se(d, base)
    t = calc.t_ppf(0.95, G - 1)
    e = float(np.mean(d))
    return e - t * se, e + t * se, float(se)


def coverage_unit(phase: str, cell: str, kind: str, s: int, B: int, R_half: int, n_new_bases: int, fast: bool) -> dict:
    """One coverage dataset (kind 'cov' = admission sample, 'eval' = independent evaluation sample): estimate, truths,
    every interval. Deterministic in (phase, cell, kind, s); contains no timing."""
    G, scen = CELLS[cell]
    pre = "" if kind == "cov" else "eval_"
    fixed = fixed_params(scen)
    X, Q, Y, base = dataset(fixed, G, rng_for(phase, cell, "data" if kind == "cov" else "eval", s))
    ev = fit(X, Y, base, fast)
    d = ev["interv"]["v_mem"] - ev["obs_morph"]["v_mem"]
    th = float(d.mean())
    t_new, t_new_se = deploy(fixed, X, Y, base, rng_for(phase, cell, pre + "new", s), n_new_bases, fast)
    iv: dict = {}
    lo, hi, se1 = cr1_interval(d, base, G)
    iv["M1"] = [lo, hi]
    dfix = Y[:, 0] - Y[:, 1]                                       # C0: fixed (non-learned) contrast
    lo0, hi0, _ = cr1_interval(dfix, base, G)
    iv["C0"] = [lo0, hi0]
    n = len(d)
    se_iid = float(np.std(d, ddof=1) / math.sqrt(n))
    t_iid = calc.t_ppf(0.95, n - 1)
    iv["C1"] = [th - t_iid * se_iid, th + t_iid * se_iid]
    # refit bootstrap (M2, M3) and the non-refit cluster bootstrap of the fixed d (C2) share the base draws
    rng_b = rng_for(phase, cell, pre + "boot", s)
    tot_b = np.bincount(base, weights=d, minlength=G)
    stars, fixed_stars, gstars, degenerate = [], [], [], 0
    for _ in range(B):
        idx = rng_b.integers(0, G, G)
        while len(np.unique(idx)) <= 2:                            # U10: redraw from the same stream, counted
            degenerate += 1
            idx = rng_b.integers(0, G, G)
        rep = F.replicate(X, Y, base, idx) if fast else L.replicate(X, Y, base, idx)
        stars.append(L.theta(rep["eval"]))
        c = np.bincount(idx, minlength=G)
        fixed_stars.append(float((c * tot_b).sum() / (G * M_INST)))
        gstars.append(rep["G_star"])
    if B:
        q05, q95 = L.percentile_ci(stars)
        iv["M2"] = [q05, q95]
        iv["M3"] = [2 * th - q95, 2 * th - q05]
        iv["C2"] = list(L.percentile_ci(fixed_stars))
        w1, w2 = iv["M1"][1] - iv["M1"][0], q95 - q05
        iv["M5"] = iv["M2"] if w2 > 1.25 * w1 else iv["M1"]       # protocol composite (frozen section 5)
    # half-sampling (M4): LOBO within each half; V = mean((thA - thB)^2) / 4; t with G/2 - 1 df
    diffs, V = [], None
    if R_half:
        for A, Bh in L.half_splits(G, R_half, rng_for(phase, cell, pre + "half", s)):
            ests = []
            for half in (A, Bh):
                rows = np.flatnonzero(np.isin(base, half))
                ests.append(theta_hat(fit(X[rows], Y[rows], base[rows], fast)))
            diffs.append(ests[0] - ests[1])
        V = half_variance(diffs)
        th4 = calc.t_ppf(0.95, G // 2 - 1) * math.sqrt(V)
        iv["M4"] = [th - th4, th + th4]
    return {"phase": phase, "cell": cell, "kind": kind, "s": int(s), "G": G, "m": M_INST, "B": B, "R_half": R_half,
            "fast": bool(fast), "sha_X": sha(X), "sha_Y": sha(Y), "sha_base": sha(base),
            "theta_hat": th, "theta_cond": theta_cond(ev, Q), "theta_new": t_new, "theta_new_se": t_new_se,
            "theta_fix_hat": float(dfix.mean()), "se_cr1": se1, "se_iid": se_iid,
            "intervals": iv, "boot": {"mean": float(np.mean(stars)) if B else None, "sd": float(np.std(stars, ddof=1)) if B > 1 else None,
                                      "n_degenerate_redrawn": degenerate, "gstar_min": int(min(gstars)) if B else None,
                                      "gstar_mean": float(np.mean(gstars)) if B else None},
            "half": {"R": R_half, "V": V}, "n_new": int(n_new_bases)}


def truth_unit(phase: str, cell: str, t: int, n_new_bases: int, fast: bool) -> dict:
    """One truth dataset: theta_cond (exact Q), theta_hat (for the bias check), the fixed-contrast truth and theta_new."""
    G, scen = CELLS[cell]
    fixed = fixed_params(scen)
    X, Q, Y, base = dataset(fixed, G, rng_for(phase, cell, "truth", t))
    ev = fit(X, Y, base, fast)
    t_new, t_new_se = deploy(fixed, X, Y, base, rng_for(phase, cell, "truth_new", t), n_new_bases, fast)
    return {"phase": phase, "cell": cell, "kind": "truth", "s": int(t), "G": G, "fast": bool(fast), "sha_X": sha(X),
            "theta_cond": theta_cond(ev, Q), "theta_hat": theta_hat(ev), "theta_fix": float(np.mean(Q[:, 0] - Q[:, 1])),
            "theta_new": t_new, "theta_new_se": t_new_se, "n_new": int(n_new_bases)}


# ------------------------------------------------------------------------------------------------ coverage arithmetic
def covered(iv, truth: float) -> bool:
    return iv[0] - TOL <= truth <= iv[1] + TOL


def wilson(k: int, n: int, z: float) -> tuple[float, float]:
    """Two-sided Wilson interval at the given z (z = 1.645 -> 90 %)."""
    if n == 0:
        return (0.0, 1.0)
    return L.wilson_lower(k, n, z), 1.0 - L.wilson_lower(n - k, n, z)


def binom_sf(k_min: int, n: int, p: float) -> float:
    """P(X >= k_min), X ~ Binomial(n, p), exact."""
    return float(sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(max(k_min, 0), n + 1)))


def admit_k_min(n: int, z: float, cov_min: float = 0.85, wil_min: float = 0.75) -> int | None:
    """Smallest k with k/n >= cov_min and Wilson lower(k, n, z) >= wil_min (the frozen admission rule)."""
    for k in range(n + 1):
        if k / n >= cov_min - 1e-12 and L.wilson_lower(k, n, z) >= wil_min:
            return k
    return None


def p_admit(n: int, c: float, z: float, cells: int) -> float:
    """Exact P(admit in every one of `cells` independent cells) at true coverage c."""
    k = admit_k_min(n, z)
    return 0.0 if k is None else binom_sf(k, n, c) ** cells


def partition(iv, m: float = 0.10) -> str:
    """Frozen protocol section 4 outcome partition of an interval [L, U] with margin m."""
    lo, hi = iv
    if hi < 0:
        return "supported harm"
    if lo > 0 and hi >= m:
        return "supported benefit"
    if 0 <= hi < m:
        return "no meaningful gain"
    return "inconclusive"


def verdict(k: int, n: int, z: float, admitted: bool) -> str:
    """Section 6B: separate 'not validated' (insufficient evidence) from demonstrated undercoverage; 'conservative' when the
    Wilson lower bound exceeds the nominal level (reported in addition, see verdict_conservative)."""
    lo, hi = wilson(k, n, z)
    if admitted:
        return "validated"
    if hi < 0.85:
        return "evidence of material undercoverage"
    if hi < NOMINAL:
        return "evidence of undercoverage"
    return "not validated"


def verdict_conservative(k: int, n: int, z: float) -> bool:
    return wilson(k, n, z)[0] > NOMINAL


def work_units(cfg: dict, phase: str, override: dict | None = None) -> list:
    """The ordered, complete list of (cell, kind, s, params) of a phase. Used by sv1_run (round-robin sharding, resume)
    and by sv1_aggregate (exact completeness and per-record parameter checks)."""
    fx, dec, pil = cfg["fixed"], cfg["decisions"], {**cfg["pilot"], **(override or {})}
    units = []
    if phase == "pilot":
        for c in CELLS:
            n_cov = pil["S_per_A_cell"] if c.startswith("A") else pil["S_per_B_cell"]
            par = {"B": pil["B"], "R": pil.get("R_half", fx["R_half"]), "new": pil.get("n_new_bases", fx["n_new_bases"])}
            units += [(c, "cov", s, par) for s in range(n_cov)]
            units += [(c, "truth", t, {"new": par["new"]}) for t in range(pil["T"])]
    elif phase == "confirm":
        pending = [k for k, v in dec.items() if v == "PENDING"]
        if pending or cfg["engineering"]["fast_path"] not in (True, False):
            raise SystemExit(f"confirm refused: owner decisions pending {pending} or fast_path not decided")
        for c in list(dec["admission_cells"]) + list(fx["diagnostic_cells"]):
            adm = c in dec["admission_cells"]
            par = {"B": dec["B"], "R": fx["R_half"], "new": fx["n_new_bases"]}
            units += [(c, "cov", s, par) for s in range(dec["S_adm"] if adm else fx["S_diagnostic_cells"])]
            if adm:
                units += [(c, "eval", s, par) for s in range(dec["S_eval"])]
            units += [(c, "truth", t, {"new": fx["n_new_bases"]})
                      for t in range(fx["T_admission_cells"] if adm else fx["T_diagnostic_cells"])]
    return units


def record_problems(rec: dict, phase: str, par: dict, fast: bool) -> list:
    """Per-record check that a record was produced by this phase with the frozen parameters."""
    bad = []
    G = CELLS[rec["cell"]][0]
    if rec.get("phase") != phase:
        bad.append("phase")
    if rec.get("G") != G or rec.get("fast") != fast:
        bad.append("G/fast")
    if rec["kind"] != "truth" and (rec.get("B") != par["B"] or rec.get("R_half") != par["R"] or rec.get("m") != M_INST):
        bad.append("B/R_half/m")
    if rec.get("n_new") != par["new"]:
        bad.append("n_new")
    return bad

# ------------------------------------------------------------------------------------------------ aggregation (used by sv1_aggregate,
# kept here so sv1_selftest can test the admission / selection arithmetic on constructed cases)
def _mean_se(xs) -> tuple[float, float]:
    xs = list(xs)
    m = statistics.fmean(xs)
    return m, (statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else float("nan"))


def _rate(flags: list, z: float) -> dict:
    k, n = int(sum(flags)), len(flags)
    lo, hi = wilson(k, n, z)
    return {"k": k, "n": n, "rate": k / n if n else None, "wilson": [lo, hi]}


def truths(recs: dict, cell: str) -> dict:
    tr = [r for (c, kind, _), r in recs.items() if c == cell and kind == "truth"]
    if not tr:
        return {}
    tg, tg_se = _mean_se(r["theta_cond"] for r in tr)
    tf, tf_se = _mean_se(r["theta_fix"] for r in tr)
    tn, tn_se = _mean_se(r["theta_new"] for r in tr)
    bias, bias_se = _mean_se(r["theta_hat"] - r["theta_cond"] for r in tr)
    return {"T": len(tr), "theta_G": tg, "theta_G_mcse": tg_se, "theta_fix_G": tf, "theta_fix_mcse": tf_se,
            "theta_new_G": tn, "theta_new_mcse": tn_se, "bias_hat_minus_cond": bias, "bias_mcse": bias_se,
            "sd_theta_cond": statistics.stdev(r["theta_cond"] for r in tr) if len(tr) > 1 else None}


def method_metrics(cov: list, tru: dict, method: str, z: float, m: float) -> dict:
    """All section-5 metrics of one method on one cell's datasets."""
    rows = [r for r in cov if method in r["intervals"]]
    if not rows:
        return {}
    tG = tru["theta_fix_G"] if method == "C0" else tru["theta_G"]
    se_t = tru["theta_fix_mcse"] if method == "C0" else tru["theta_G_mcse"]
    iv = [r["intervals"][method] for r in rows]
    th = [r["theta_fix_hat"] if method == "C0" else r["theta_hat"] for r in rows]
    width = [b - a for a, b in iv]
    out = {"n": len(rows),
           "coverage_theta_G": _rate([covered(x, tG) for x in iv], z),
           "coverage_theta_G_minus_2se": _rate([covered(x, tG - 2 * se_t) for x in iv], z),
           "coverage_theta_G_plus_2se": _rate([covered(x, tG + 2 * se_t) for x in iv], z),
           "lower_miss": _rate([tG < x[0] - TOL for x in iv], z),
           "lower_miss_minus_2se": _rate([tG - 2 * se_t < x[0] - TOL for x in iv], z),
           "lower_miss_plus_2se": _rate([tG + 2 * se_t < x[0] - TOL for x in iv], z),
           "upper_miss": _rate([tG > x[1] + TOL for x in iv], z),
           "zero_width": sum(w <= TOL for w in width),
           "width_mean": statistics.fmean(width), "width_median": statistics.median(width)}
    out["conservative"] = verdict_conservative(out["coverage_theta_G"]["k"], out["n"], z)
    out["evidence_excess_lower_tail"] = out["lower_miss"]["wilson"][0] > (1 - NOMINAL) / 2
    if method != "C0":
        out["coverage_theta_cond"] = _rate([covered(x, r["theta_cond"]) for x, r in zip(iv, rows)], z)
        out["coverage_theta_new_D"] = _rate([covered(x, r["theta_new"]) for x, r in zip(iv, rows)], z)
        out["coverage_theta_new_G"] = _rate([covered(x, tru["theta_new_G"]) for x in iv], z)
        out["decision_rates"] = {k: sum(partition(x, m) == k for x in iv) / len(iv)
                                 for k in ("supported benefit", "no meaningful gain", "supported harm", "inconclusive")}
    sd = statistics.stdev(th) if len(th) > 1 else float("nan")
    out.update({"bias_theta_hat_vs_theta_G": statistics.fmean(th) - tG, "sd_theta_hat": sd,
                "rmse": math.sqrt(statistics.fmean((x - tG) ** 2 for x in th)),
                "width_over_sd": statistics.fmean(width) / sd if sd and sd == sd else None})
    return out


def admission(per_cell: dict, cand: str, dec: dict, fx: dict) -> dict:
    """Frozen admission rule over the admission cells (plus D-4 if adopted); truth-sensitive verdicts are not admitted."""
    z, ok_all, detail = dec["wilson_z"], True, {}
    for cell in dec["admission_cells"]:
        mm = per_cell[cell]["methods"].get(cand)
        if not mm:
            ok_all, detail[cell] = False, "no data"
            continue
        def rule(cv):
            return cv["rate"] >= fx["admission_coverage_min"] - 1e-12 and cv["wilson"][0] >= fx["admission_wilson_lower_min"]
        def lt(miss):
            return dec["lower_tail_max"] is None or miss["rate"] <= dec["lower_tail_max"] + 1e-12
        base_ok, lt_ok = rule(mm["coverage_theta_G"]), lt(mm["lower_miss"])
        # truth-sensitivity (section 2A item 3): ANY admission outcome flipping inside theta_G +- 2 MC-SE
        outcomes = {(rule(mm[f"coverage_theta_G{sfx}"]), lt(mm[f"lower_miss{sfx}"])) for sfx in ("", "_minus_2se", "_plus_2se")}
        cell_ok = base_ok and lt_ok and len(outcomes) == 1
        detail[cell] = {"coverage_rule": base_ok, "lower_tail_rule": lt_ok, "truth_sensitive": len(outcomes) > 1,
                        "admitted_in_cell": cell_ok, "conservative": mm["conservative"],
                        "evidence_excess_lower_tail": mm["evidence_excess_lower_tail"],
                        "verdict": verdict(mm["coverage_theta_G"]["k"], mm["coverage_theta_G"]["n"], z, cell_ok)}
        ok_all &= cell_ok
    return {"admitted": ok_all, "cells": detail}


def widest(rec: dict, methods: list):
    ivs = [rec["intervals"][mt] for mt in methods if mt in rec["intervals"]]
    return max(ivs, key=lambda x: (x[1] - x[0], -x[0])) if ivs else None


# ------------------------------------------------------------------------------------------------ C0 harness gate (amendment A-SV1-1)
def _binom_lpmf(k: int, n: int, p: float) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) + (n - k) * math.log1p(-p)


def binom_cdf_exact(k: int, n: int, p: float) -> float:
    return math.fsum(math.exp(_binom_lpmf(j, n, p)) for j in range(0, k + 1))


def binom_sf_exact(k: int, n: int, p: float) -> float:
    return math.fsum(math.exp(_binom_lpmf(j, n, p)) for j in range(max(k, 0), n + 1))


def c0_gate(counts: dict, band=(0.85, 0.95), alpha: float = 0.01) -> dict:
    """Amendment A-SV1-1 (pre-registered before any confirmatory coverage was observed): the C0 fixed-contrast harness check.
    For each cell and for all cells pooled, with k covered of n: REJECT iff P_{band lo}(X <= k) < alpha (exact one-sided
    test that the coverage is below the band; equivalent to the one-sided Clopper-Pearson upper bound < lo) or
    P_{band hi}(X >= k) < alpha (above the band; CP lower bound > hi). Exact false-rejection with a correct harness
    (S = 200 x 3 cells, 100 x 2, pooled 800): <= 0.048 at the band edges, <= 0.010 for true coverage in [0.88, 0.94]."""
    lo, hi = band
    def test(k, n):
        p_below, p_above = binom_cdf_exact(k, n, lo), binom_sf_exact(k, n, hi)
        return {"k": k, "n": n, "rate": k / n, "p_below": p_below, "p_above": p_above,
                "reject": p_below < alpha or p_above < alpha, "point_in_band": lo - 1e-12 <= k / n <= hi + 1e-12}
    cells = {c: test(k, n) for c, (k, n) in sorted(counts.items())}
    K, N = sum(k for k, _ in counts.values()), sum(n for _, n in counts.values())
    pooled = test(K, N) if N else None
    return {"band": list(band), "alpha_per_side": alpha, "cells": cells, "pooled": pooled,
            "ok": bool(cells) and not any(v["reject"] for v in cells.values()) and not (pooled and pooled["reject"])}
