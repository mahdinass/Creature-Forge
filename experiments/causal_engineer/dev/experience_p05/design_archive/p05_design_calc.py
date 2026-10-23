"""P0.5 design revision 2.1: read-only design-stage arithmetic. Replaces p05_precision.py (rev. 1) and p05_design_calc_rev2.py.

Nothing here reads Creature Forge records or runs a simulator. Every number is either closed-form arithmetic under stated
assumptions or a property of a SYNTHETIC statistical model (numpy random draws). None is a measured property of Creature
Forge. The learning-inflation section imports the exact P0 kNN functions (creature_forge.experience_p0, pure numpy) and runs
them on synthetic data only; MuJoCo is blocked by a tripwire.

    python -I p05_design_calc.py --worktree <cf-experience> [--quick] [--out p05_design_calc_output.md]

Sections: A constraints | B quantiles | C precision and power | D few-cluster coverage (synthetic, calibrated ICC) |
E learning inflation (synthetic, exact P0 learner; read from cache, G = 46 NOT COMPUTED) | F headroom estimands |
G noise and negative transfer | H cost formulas | I tool budgets and feasible sets | J achieved ICC of the cluster generator |
K discordance bound | L benefit vs equivalence capability | M headroom confidence bounds (simultaneous).
"""
from __future__ import annotations

import argparse
import functools
import math
import sys
import time
from statistics import NormalDist

sys.modules["mujoco"] = None          # tripwire: any MuJoCo import fails

import numpy as np

SEED = 20261023
TOOLS = 10


# ============================================================================================== A. parameter constraints
def check_dq(q: float, delta: float) -> float:
    """d in {-1, 0, 1}, q = P(d != 0), delta = E[d]. Requires 0 < q <= 1 and |delta| <= q. Returns Var(d) = q - delta^2."""
    if not (0.0 < q <= 1.0):
        raise ValueError(f"q must lie in (0, 1], got {q}")
    if abs(delta) > q + 1e-12:
        raise ValueError(f"impossible combination: |delta| = {abs(delta)} > q = {q} (d in {{-1,0,1}} forces |E d| <= P(d != 0))")
    return q - delta * delta


def check_marginals(p_a: float, p_b: float, q: float) -> None:
    """Paired binary outcomes with marginal success rates p_a, p_b: q = P(Y_a != Y_b) must satisfy
    |p_a - p_b| <= q <= min(p_a + p_b, 2 - p_a - p_b)."""
    for p in (p_a, p_b):
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"marginal {p} outside [0, 1]")
    lo, hi = abs(p_a - p_b), min(p_a + p_b, 2.0 - p_a - p_b)
    if not (lo - 1e-12 <= q <= hi + 1e-12):
        raise ValueError(f"q = {q} infeasible for marginals ({p_a}, {p_b}); feasible range [{lo:.3f}, {hi:.3f}]")


def check_design(G: int, m: int, rho: float, infl: float = 1.0) -> None:
    if int(G) != G or G < 2:
        raise ValueError(f"G must be an integer >= 2, got {G}")
    if int(m) != m or m < 1:
        raise ValueError(f"m must be an integer >= 1, got {m}")
    if not 0.0 <= rho <= 1.0:
        raise ValueError(f"rho must lie in [0, 1], got {rho}")
    if infl < 1.0:
        raise ValueError(f"learning inflation must be >= 1, got {infl}")


# ============================================================================================== B. quantiles (no scipy)
def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularised incomplete beta (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for mm in range(1, 400):
        m2 = 2 * mm
        aa = mm * (b - mm) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + mm) * (qab + mm) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-14:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def t_cdf(x: float, df: float) -> float:
    tail = 0.5 * betainc(df / 2.0, 0.5, df / (df + x * x))
    return 1.0 - tail if x >= 0 else tail


@functools.lru_cache(maxsize=None)
def t_ppf(p: float, df: float) -> float:
    if not 0.0 < p < 1.0:
        raise ValueError(p)
    lo, hi = -200.0, 200.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def z_ppf(p: float) -> float:
    return NormalDist().inv_cdf(p)


def crit(p: float, G: int, method: str) -> float:
    """method 'z': normal approximation; 't': Student t with G-1 df (few-cluster small-sample correction)."""
    return z_ppf(p) if method == "z" else t_ppf(p, G - 1)


# ============================================================================================== C. precision and power
def var_mean_diff(q: float, delta: float, G: int, m: int, rho: float, infl: float = 1.0) -> float:
    """Approximate variance of the mean paired difference over G bases x m instances with base ICC rho and learning-variance
    inflation infl (>= 1; 1 = fixed, pre-specified policies). Design-stage approximation only."""
    v = check_dq(q, delta)
    check_design(G, m, rho, infl)
    return v * (1.0 + (m - 1) * rho) * infl / (G * m)


def halfwidth(q, delta, G, m, rho, infl=1.0, level=0.90, method="t") -> float:
    return crit(0.5 + level / 2.0, G, method) * math.sqrt(var_mean_diff(q, delta, G, m, rho, infl))


def mde(q, G, m, rho, infl=1.0, alpha=0.05, power=0.80, method="t") -> float | None:
    """Smallest delta detectable by a one-sided level-alpha test with the given power, solving
    delta = K sqrt((q - delta^2) D / n) in closed form: delta = K sqrt(q / (n_eff + K^2)), n_eff = G m / (D infl).
    Returns None when that delta exceeds q (no valid delta in {-1,0,1}-difference space is detectable)."""
    check_dq(q, 0.0)
    check_design(G, m, rho, infl)
    K = crit(1.0 - alpha, G, method) + crit(power, G, method)
    n_eff = G * m / ((1.0 + (m - 1) * rho) * infl)
    d = K * math.sqrt(q / (n_eff + K * K))
    return None if d > q + 1e-12 else d


def bases_needed(delta, q, m, rho, infl=1.0, alpha=0.05, power=0.80, method="t", g_max=2000) -> int | None:
    """Smallest G whose MDE <= delta (MDE is non-increasing in G); binary search. None if not reached by g_max."""
    check_dq(q, delta)

    def ok(G):
        d = mde(q, G, m, rho, infl, alpha, power, method)
        return d is not None and d <= delta
    if not ok(g_max):
        return None
    lo, hi = 2, g_max
    while lo < hi:
        mid = (lo + hi) // 2
        if ok(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


# ============================================================================================== D. few-cluster coverage
def _cluster_d(rng, G, m, q, delta, sigma, reps):
    """Synthetic paired differences with a base random effect on E[d]: delta_b = clip(delta + u_b, -q, q), u_b ~ N(0, sigma^2);
    d ~ {+1 w.p. (q+delta_b)/2, -1 w.p. (q-delta_b)/2, 0 otherwise}. The ACHIEVED ICC of d is achieved_icc(q, delta, sigma)
    (section J); calibrate_sigma hits a target. rev. 2 used sigma^2 = rho (q - delta^2), which under-achieves rho."""
    db = np.clip(delta + rng.normal(0.0, sigma, size=(reps, G)), -q, q)
    u = rng.random((reps, G, m))
    pp, pm = (q + db) / 2.0, (q - db) / 2.0
    d = np.where(u < pp[..., None], 1.0, np.where(u < (pp + pm)[..., None], -1.0, 0.0))
    return d


def coverage_sim(G, m, q, delta, rho_target, reps=2000, n_boot=999, level=0.90, seed=SEED, sigma=None):
    """Coverage of three intervals for the population mean of d (synthetic): z with CR0 cluster SE, t_{G-1} with CR1 SE,
    and the percentile base-cluster bootstrap. The generator is calibrated so the ACHIEVED ICC equals rho_target (or, if
    sigma is given, it is used and the achieved ICC is reported). Truth = the analytic mean of the clipped effect."""
    rng = np.random.default_rng(seed)
    check_dq(q, delta)
    if sigma is None:
        sigma = calibrate_sigma(q, delta, rho_target)
    truth, _ = clipped_normal_moments(delta, sigma, -q, q)
    if delta == 0.0:
        truth = 0.0        # exact by symmetry; a float residue (rev. 2 used a 1e6-draw MC mean) is scored as a miss on discrete data
    TOL = 1e-12        # closed intervals; estimates and bootstrap quantiles of discrete data sit exactly on lattice points
    rho_ach = achieved_icc(q, delta, sigma)
    d = _cluster_d(rng, G, m, q, delta, sigma, reps)
    tot = d.sum(2)                                     # base totals (reps, G)
    est = tot.sum(1) / (G * m)
    resid = tot - m * est[:, None]
    se0 = np.sqrt((resid ** 2).sum(1)) / (G * m)
    se1 = se0 * math.sqrt(G / (G - 1.0))
    zc, tc = z_ppf(0.5 + level / 2), t_ppf(0.5 + level / 2, G - 1)
    cov_z = np.mean(np.abs(est - truth) <= zc * se0 + TOL)
    cov_t = np.mean(np.abs(est - truth) <= tc * se1 + TOL)
    W = rng.multinomial(G, np.full(G, 1.0 / G), size=n_boot).astype(float)     # (B, G) resampling counts
    bs = (tot @ W.T) / (G * m)                                                  # (reps, B)
    lo, hi = np.quantile(bs, [0.5 - level / 2, 0.5 + level / 2], axis=1)
    cov_b = np.mean((lo - TOL <= truth) & (truth <= hi + TOL))
    deg = np.mean(se0 == 0)
    return {"G": G, "m": m, "q": q, "delta": delta, "rho_achieved": round(rho_ach, 4), "sigma": round(sigma, 4),
            "truth": round(truth, 4), "cov_z_CR0": round(float(cov_z), 3),
            "cov_t_CR1": round(float(cov_t), 3), "cov_boot_pct": round(float(cov_b), 3), "zero_se_frac": round(float(deg), 3),
            "mc_se": round(math.sqrt(level * (1 - level) / reps), 3)}


# ============================================================================================== E. learning inflation (exact P0 learner)
SCENARIOS = {
    # tool x family effect sd, observation noise sd, catalogue-response noise sd (smaller = more informative)
    "null (no feature-predictable tool heterogeneity)": {"theta": 0.0, "noise_o": 1.0, "noise_c": 1.0},
    "observation sufficient": {"theta": 1.5, "noise_o": 0.5, "noise_c": 3.0},
    "interventions add information": {"theta": 1.5, "noise_o": 3.0, "noise_c": 0.5},
}


def _synth(rng, fixed, G, m):
    n = G * m
    base = np.repeat(np.arange(G), m)
    fam = rng.integers(0, 9, size=n)
    morph = rng.normal(size=(G, 7))[base]
    obs = fixed["E_o"][fam] + rng.normal(scale=fixed["noise_o"], size=(n, fixed["E_o"].shape[1]))
    cf = fixed["E_c"][fam] + rng.normal(scale=fixed["noise_c"], size=(n, fixed["E_c"].shape[1]))
    logit = (fixed["alpha"][None, :] + fixed["theta"][fam] + rng.normal(0.0, 0.5, G)[base][:, None]
             + rng.normal(0.0, 0.5, (G, TOOLS))[base])
    Q = 1.0 / (1.0 + np.exp(-logit))
    Y = (rng.random(Q.shape) < Q).astype(float)
    return np.hstack([morph, obs, cf]), Q, Y, base


def learning_inflation(p0, G, m, scenario, sims, seed=SEED):
    """Monte Carlo of the exact P0 decision pipeline (LOBO outer folds, inner LOBO k choice, Laplace kNN, argmax) on
    synthetic data. Returns the sampling variance of the estimated interv - obs_morph decision-value difference relative to the
    mean squared naive (fixed-policy) CR1 standard error, and the naive t-interval's coverage of the procedure estimand."""
    sc = SCENARIOS[scenario]
    frng = np.random.default_rng(seed + 7)
    fixed = {"E_o": frng.normal(size=(9, 8)), "E_c": frng.normal(size=(9, 27)), "theta": frng.normal(0.0, sc["theta"], (9, TOOLS)),
             "alpha": frng.normal(-1.5, 0.7, TOOLS), "noise_o": sc["noise_o"], "noise_c": sc["noise_c"]}
    blocks = {"morph": list(range(0, 7)), "obs": list(range(7, 15)), "cf": list(range(15, 42))}
    rng = np.random.default_rng(seed + 11)
    est, dq, se = [], [], []
    for _ in range(sims):
        X, Q, Y, base = _synth(rng, fixed, G, m)
        sp = p0.Space(X, blocks)
        picks = {}
        vals = {}
        for name, use in (("interv", ("obs", "morph", "cf")), ("obs_morph", ("obs", "morph"))):
            de = p0.decision_eval(p0.predict(sp, use, Y, base, base), Y)
            picks[name], vals[name] = de["pick"], de["v_mem"]
        d = vals["interv"] - vals["obs_morph"]
        n = len(d)
        e = d.mean()
        tot = np.bincount(base, weights=d, minlength=G)
        cnt = np.bincount(base, minlength=G)
        se1 = math.sqrt(G / (G - 1.0) * ((tot - cnt * e) ** 2).sum()) / n
        est.append(e)
        se.append(se1)
        dq.append(float((Q[np.arange(n), picks["interv"]] - Q[np.arange(n), picks["obs_morph"]]).mean()))
    est, se, dq = np.array(est), np.array(se), np.array(dq)
    truth = dq.mean()
    tc = t_ppf(0.95, G - 1)
    var_ratio = est.var(ddof=1) / np.mean(se ** 2)
    # MC uncertainty of the ratio (delta method on the variance, ignoring se^2 noise): relative sd ~ sqrt(2/(sims-1))
    nz = se > 0
    covered = np.abs(est - truth) <= tc * se
    return {"G": G, "m": m, "scenario": scenario, "sims": sims, "procedure_estimand": round(float(truth), 4),
            "procedure_estimand_mc_se": round(float(dq.std(ddof=1) / math.sqrt(sims)), 4),
            "sd_estimate": round(float(est.std(ddof=1)), 4), "rms_naive_se": round(float(np.sqrt(np.mean(se ** 2))), 4),
            "inflation_var_ratio": round(float(var_ratio), 2), "ratio_mc_rel_sd": round(math.sqrt(2.0 / (sims - 1)), 2),
            "naive_t90_coverage": round(float(np.mean(covered)), 3),
            "zero_se_fraction": round(float(np.mean(~nz)), 3),
            "naive_t90_coverage_nondegenerate": round(float(np.mean(covered[nz])), 3) if nz.any() else None,
            "sd_policy_learning_component": round(float(dq.std(ddof=1)), 4),
            "per_sim": {"est": est.round(6).tolist(), "se": se.round(6).tolist(), "dq": np.round(dq, 6).tolist()}}


# ============================================================================================== F. headroom estimands
def binom_pmf(R: int, p: float) -> np.ndarray:
    k = np.arange(R + 1)
    return np.array([math.comb(R, int(j)) for j in k]) * p ** k * (1 - p) ** (R - k)


def selector_value(Q: np.ndarray, R: int) -> float:
    """Exact E[Q(argmax_a Ybar_R(a))] for independent Binomial(R, Q_a) counts, ties broken uniformly at random."""
    T = len(Q)
    pmf = [binom_pmf(R, float(p)) for p in Q]
    cdf = [np.cumsum(f) for f in pmf]
    val = 0.0
    for a in range(T):
        for k in range(R + 1):
            poly = np.array([1.0])
            for b in range(T):
                if b == a:
                    continue
                below = cdf[b][k - 1] if k > 0 else 0.0
                poly = np.convolve(poly, [below, pmf[b][k]])
            val += Q[a] * pmf[a][k] * float(np.sum(poly / (np.arange(len(poly)) + 1.0)))
    return val


def naive_max(Q: np.ndarray, R: int) -> float:
    """Exact E[max_a Ybar_R(a)] for independent Binomial(R, Q_a) counts: >= max_a Q_a (Jensen)."""
    cdf = np.array([np.cumsum(binom_pmf(R, float(p))) for p in Q])     # (T, R+1)
    return float(sum(1.0 - np.prod(cdf[:, k - 1]) for k in range(1, R + 1)) / R)


HEADROOM_SCENARIOS = {
    # name: (generator, description)
    "S0 equal tools, p~Beta(1.5,3.5)": "every tool has the same Q(x)=p(x); zero true tool headroom",
    "S1 graded, logit sd 0.75": "logit Q = mu_x + eta_xa, eta ~ N(0, 0.75^2)",
    "S2 graded, logit sd 1.5": "logit Q = mu_x + eta_xa, eta ~ N(0, 1.5^2)",
    "S3 sparse best tool": "one tool Q~Beta(4,2), others Q~Beta(1,9)",
}


def headroom_instances(rng, name, n):
    if name.startswith("S0"):
        p = rng.beta(1.5, 3.5, n)
        Q = np.repeat(p[:, None], TOOLS, 1)
    elif name.startswith("S1") or name.startswith("S2"):
        sd = 0.75 if name.startswith("S1") else 1.5
        mu = rng.normal(-1.2, 1.0, n)
        Q = 1.0 / (1.0 + np.exp(-(mu[:, None] + rng.normal(0, sd, (n, TOOLS)))))
    else:
        Q = rng.beta(1, 9, (n, TOOLS))
        Q[np.arange(n), rng.integers(0, TOOLS, n)] = rng.beta(4, 2, n)
    # pi0 is a fixed tool (the population best-on-average tool is exchangeable here): tool 0
    return Q


def headroom_table(R_list=(1, 2, 3, 4), n=1500, seed=SEED):
    rng = np.random.default_rng(seed + 3)
    out = []
    for name in HEADROOM_SCENARIOS:
        Q = headroom_instances(rng, name, n)
        q0 = Q[:, 0]
        true = float(np.mean(Q.max(1) - q0))
        vb = headroom_var_bound(float(Q.var(1, ddof=1).mean()), float(np.mean(Q.mean(1) - q0)))
        row = {"scenario": name, "Gamma_true": round(true, 3), "var_bound": round(vb, 3)}
        for R in R_list:
            sel = np.array([selector_value(Q[i], R) for i in range(n)])
            nav = np.array([naive_max(Q[i], R) for i in range(n)])
            row[f"sel_R{R}"] = round(float(np.mean(sel - q0)), 3)
            row[f"naive_R{R}"] = round(float(np.mean(nav - q0)), 3)
        out.append(row)
    return out


def headroom_estimator_sd(name, R, n=4000, seed=SEED):
    """Per-instance SDs of (i) the selector estimator: select on R replicates, evaluate the selected tool and pi0 on one fresh
    draw each; (ii) the naive estimator max_a Ybar_R(a) - Ybar_R(pi0). Synthetic draws."""
    rng = np.random.default_rng(seed + 5)
    Q = headroom_instances(rng, name, n)
    K = rng.binomial(R, Q)
    noise = rng.random(K.shape) * 1e-6
    sel = np.argmax(K + noise, 1)
    fresh_sel = (rng.random(n) < Q[np.arange(n), sel]).astype(float)
    fresh_0 = (rng.random(n) < Q[:, 0]).astype(float)
    e_sel = fresh_sel - fresh_0
    e_nav = K.max(1) / R - K[:, 0] / R
    return float(e_sel.std()), float(e_nav.std())


def tool_variance_component(Y: np.ndarray) -> np.ndarray:
    """Per-instance unbiased estimate of V_Q(x) = sample variance over tools of Q(x, a), from Y of shape (n, T, R >= 2):
    S^2 over tools of Ybar_R minus mean_a s_a^2 / R, because E[S^2] = V_Q + mean_a Q(1-Q)/R and E[s_a^2] = Q(1-Q)."""
    R = Y.shape[2]
    if R < 2:
        raise ValueError("needs >= 2 replicates per cell")
    Yb = Y.mean(2)
    return Yb.var(1, ddof=1) - Y.var(2, ddof=1).mean(1) / R


def headroom_var_bound(mean_V: float, mean_gap: float, T: int = TOOLS) -> float:
    """Valid upper bound on Gamma_true = E[max_a Q - Q(pi0)] from E[V_Q] and E[Qbar - Q(pi0)]:
    max_a Q - Qbar <= (T-1) sqrt(V_Q / T) (deviations sum to zero), then Jensen: E sqrt(V) <= sqrt(E V)."""
    return (T - 1) / math.sqrt(T) * math.sqrt(max(mean_V, 0.0)) + mean_gap


def instances_for_halfwidth(sd, h, rho, m, level=0.90):
    deff = 1.0 + (m - 1) * rho
    return math.ceil((z_ppf(0.5 + level / 2) * sd) ** 2 * deff / h ** 2)


# ============================================================================================== G. noise and negative transfer
def equal_tool_noise(p: float, K: int = TOOLS) -> dict:
    """Two tools with the same expected success p and independent optimizer noise: discordance, realised adverse outcome
    (memory fails where pi0 succeeds), expected harm, and the chance that K equally effective tools look 'informative'."""
    return {"p": p, "q_discordance": 2 * p * (1 - p), "realised_p_minus": p * (1 - p), "expected_harm": 0.0,
            f"P_informative_K{K}": 1 - p ** K - (1 - p) ** K}


def harm_bounds(mu: float, var_tau: float) -> tuple[float, float]:
    """Bounds on the expected harm E[(Q0 - QM)+] = E[tau_-] given mean mu = E[tau] and Var(tau) (tau = QM - Q0):
    max(0, -mu) <= E[tau_-] <= (sqrt(var + mu^2) - mu) / 2 (since E|tau| <= sqrt(E tau^2))."""
    if var_tau < 0:
        raise ValueError("variance must be >= 0")
    return max(0.0, -mu), (math.sqrt(var_tau + mu * mu) - mu) / 2.0


# ============================================================================================== H. cost formulas
ROLLOUT_EQ_CONFIRM = 2.0          # recovery.CONFIRM_DURATION / TRAIN_DURATION = 20 / 10 [code-derived]
VALIDATE_N, CONFIRM_N = 24, 24    # hdb_bench.SEED_COUNTS [code-derived]
SENTINEL_RE = 615 + 2519          # one stored A1e6 episode: plant + twin rollouts [HIST, report 8.4]
THRESH_VARIANTS = 13              # hdb_bench.FAMILY_SPECS variant count over the 9 dev families [code-derived]
THRESH_EVALS = 1 + 6              # s_max check + BISECT_STEPS [code-derived]
CHECK_N = 8                       # hdb_bench.CHECK_N [code-derived]
OBS_N, CAT_N = 4, 9               # P0 interv: n_obs = 4 (ce_probe_dataset.N_OBS), 9 catalogue entries (eng_tools.COUNTERFACTUALS)

COST_SETS = {
    # all [ASSUMP] unless the comment says otherwise; prices are unverified until billed. n_train = repair train seeds. Every
    # set keeps all ten tools budget-feasible at B (section I), so the +36 / +40 cost-matched budgets never change the action set.
    "low": {"B_plant": 160, "n_train": 4, "twin_prefix": 0, "p_pass": 0.15, "throughput_h": 31_200 * 1.5, "price_h": 0.269, "overhead_h": 0.25,
            "sessions": 2, "idle_frac": 0.10, "cache_original": True},
    "mid": {"B_plant": 300, "n_train": 8, "twin_prefix": 40, "p_pass": 0.30, "throughput_h": 31_200, "price_h": 0.269, "overhead_h": 0.5,
            "sessions": 3, "idle_frac": 0.20, "cache_original": False},
    "high": {"B_plant": 700, "n_train": 8, "twin_prefix": 40, "p_pass": 0.50, "throughput_h": 31_200 * 0.5, "price_h": 0.60, "overhead_h": 1.0,
             "sessions": 5, "idle_frac": 0.35, "cache_original": False},
}


def verify_re(p_pass: float, cache_original: bool) -> float:
    """full_recovery_v1 per verified design: original + candidate on the validation seeds, plus confirmation (20 s seeds) only
    when validation passes. cache_original: the original's 24 validation rollouts are identical for all cells of an instance
    and computed once (an implementation choice that must be shown bit-identical)."""
    return (0 if cache_original else VALIDATE_N) + VALIDATE_N + p_pass * CONFIRM_N * ROLLOUT_EQ_CONFIRM


def prefix_re(c: dict) -> float:
    """Diagnosis per instance: observe (4 plant) + 9-entry catalogue (36 plant) + optional nominal-twin replay (twin_prefix)."""
    return OBS_N + CAT_N * OBS_N + c["twin_prefix"]


def stage_e_re(n_bases: int, candidates_per_base: int) -> float:
    """Physics-only eligibility for bases lacking a verified threshold file: thresholds (13 variants x 7 evaluations x 8 check
    seeds) + one 8-seed eligibility check per candidate instance."""
    return n_bases * (THRESH_VARIANTS * THRESH_EVALS * CHECK_N + candidates_per_base * CHECK_N)


AUG_EXTRA = {"obs_morph pick at B + catalogue": CAT_N * OBS_N, "pi0 pick at B + observe + catalogue": OBS_N + CAT_N * OBS_N}


def design_re(c: dict, n_inst: int, tools: float, R: float, aug_per_inst: int, n_confirm_cells: int, n_sentinel: int) -> dict:
    """Rollout-equivalents of one design. Matrix: n_inst x tools x R cells at plant budget B. Cost-matched (phase-2) cells:
    up to aug_per_inst per instance, each the comparator's cross-fitted pick at B plus the plant cost of the diagnosis it
    did not pay for (AUG_EXTRA). Selector-confirmation: fresh draws of the replicate-selected tool and of pi0."""
    v = verify_re(c["p_pass"], c["cache_original"])
    orig_once = VALIDATE_N if c["cache_original"] else 0
    cell = c["B_plant"] + v
    extras = list(AUG_EXTRA.values())[:aug_per_inst]
    parts = {
        "prefix": n_inst * prefix_re(c),
        "matrix cells": n_inst * tools * R * cell + n_inst * orig_once,
        "cost-matched cells": n_inst * sum(c["B_plant"] + e + v for e in extras),
        "selector-confirmation cells": n_confirm_cells * cell,
        "sentinel": n_sentinel * SENTINEL_RE,
    }
    parts["total"] = sum(parts.values())
    return parts


def dollars(c: dict, rollout_eq: float) -> float:
    hours = rollout_eq / c["throughput_h"] * (1.0 + c["idle_frac"]) + c["sessions"] * c["overhead_h"]
    return hours * c["price_h"]


# ============================================================================================== I. tool budgets and feasible sets
# eng_tools.tool_space(t).dim at e3caf81, enumerated from the published code with physics entry points trapped
# (p05_min_budget_check.py). population / min_repair_budget restate eng_tools.population / eng_tools.min_repair_budget.
TOOL_DIMS = {"posture": 4, "timing": 3, "feedback": 5, "stride": 3, "placement": 2, "foot_length": 1, "torso_mass": 1,
             "torque_limit": 1, "foot_friction": 1, "leg_length": 2}
MIN_GENERATIONS = 3


def population(dim: int) -> int:
    return max(2, 4 + int(math.floor(3 * math.log(dim))))


def min_repair_budget(tool: str, n_train: int) -> int:
    return n_train * (1 + MIN_GENERATIONS * population(TOOL_DIMS[tool]))


def budget_feasible(B: int, n_train: int) -> list:
    """Tools that eng_tools.run_repair would NOT refuse for budget (bounds-feasibility is per robot and separate)."""
    return sorted(t for t in TOOL_DIMS if min_repair_budget(t, n_train) <= B)


def check_all_tools_feasible(c: dict) -> None:
    short = [t for t in TOOL_DIMS if min_repair_budget(t, c["n_train"]) > c["B_plant"]]
    if short:
        raise ValueError(f"B={c['B_plant']} with n_train={c['n_train']} refuses {short}; the action set would depend on budget")


# ============================================================================================== J. achieved ICC of the generator
def _phi(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def _Phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def clipped_normal_moments(mu: float, sigma: float, lo: float, hi: float):
    """Exact mean and variance of clip(X, lo, hi), X ~ N(mu, sigma^2); sigma = 0 gives the clipped constant."""
    if sigma <= 0:
        c = min(max(mu, lo), hi)
        return c, 0.0
    a, b = (lo - mu) / sigma, (hi - mu) / sigma
    Pa, Pb, pa, pb = _Phi(a), _Phi(b), _phi(a), _phi(b)
    mid = Pb - Pa
    e1 = lo * Pa + hi * (1 - Pb) + mu * mid + sigma * (pa - pb)
    e2_mid = mu * mu * mid + 2 * mu * sigma * (pa - pb) + sigma * sigma * (mid + a * pa - b * pb)
    e2 = lo * lo * Pa + hi * hi * (1 - Pb) + e2_mid
    return e1, max(e2 - e1 * e1, 0.0)


def achieved_icc(q: float, delta: float, sigma: float) -> float:
    """ICC of d under the section-D generator. P(d != 0 | base) = q for every base, so Var(d) = q - mu^2 with mu = E[delta_b];
    the between-base variance is Var(delta_b) = Var(clip(delta + u, -q, q))."""
    check_dq(q, delta)
    mu, v = clipped_normal_moments(delta, sigma, -q, q)
    return v / (q - mu * mu)


def icc_supremum(q: float) -> float:
    """Upper limit of achieved_icc for this generator: a variable in [-q, q] with mean mu has variance <= q^2 - mu^2, and
    (q^2 - mu^2) / (q - mu^2) <= q for q <= 1. Targets >= q are unattainable with a constant per-base discordance."""
    return q


def calibrate_sigma(q: float, delta: float, rho_target: float, tol: float = 1e-12) -> float:
    """sigma with achieved_icc(q, delta, sigma) = rho_target (bisection; achieved_icc increases with sigma).
    Raises ValueError when the target is not attainable by this generator."""
    if rho_target <= 0:
        return 0.0
    if rho_target >= icc_supremum(q):
        raise ValueError(f"ICC {rho_target} unattainable for q={q} (supremum {icc_supremum(q)} for this generator)")
    hi = 1.0
    while achieved_icc(q, delta, hi) < rho_target:
        hi *= 2.0
        if hi > 1e6:
            raise ValueError(f"ICC {rho_target} unattainable for q={q}, delta={delta}")
    lo = 0.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if achieved_icc(q, delta, mid) < rho_target:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def rev2_nominal_sigma(q: float, delta: float, rho_nominal: float) -> float:
    """The rev. 2 (uncalibrated) choice sigma^2 = rho_nominal (q - delta^2)."""
    return math.sqrt(rho_nominal * check_dq(q, delta))


# ============================================================================================== K. discordance bound
def discordance_upper(v_a: float, v_b: float) -> float:
    """For two binary outcomes with success rates v_a, v_b: q = P(Y_a != Y_b) <= min(1, v_a + v_b, 2 - v_a - v_b)."""
    return min(1.0, v_a + v_b, 2.0 - v_a - v_b)


def discordance_upper_any_policies(emax_ucb: float, emin_lcb: float = 0.0) -> float:
    """Valid for ANY two tool-choice policies: each value lies in [E min_a Q, E max_a Q], so
    q <= min(1, 2 E max_a Q, 2 - 2 E min_a Q). E max_a Q <= E max_a Ybar_R (unbiasedly estimable: use its upper confidence
    bound); E min_a Q >= E min_a Ybar_R (use its lower confidence bound)."""
    return min(1.0, 2.0 * emax_ucb, 2.0 - 2.0 * emin_lcb)


# ============================================================================================== L. benefit vs equivalence capability
def se_at(q, G, m, rho, infl, delta=0.0):
    return math.sqrt(var_mean_diff(q, delta, G, m, rho, infl))


def equivalence_margin_demonstrable(q, G, m, rho, infl, power=0.80, level=0.90, two_sided=False) -> float:
    """Smallest margin M such that, if the true effect is 0, the analysis shows 'no meaningful gain' (U < M, U = upper end of
    the two-sided `level` interval) with probability `power`. two_sided: TOST-style (L > -M as well; power split)."""
    se = se_at(q, G, m, rho, infl)
    hi = crit(0.5 + level / 2.0, G, "t")
    pw = crit(power, G, "t") if not two_sided else crit(0.5 + power / 2.0, G, "t")
    return (hi + pw) * se


def benefit_detectable(delta_large, q, G, m, rho, infl) -> bool:
    d = mde(q, G, m, rho, infl)
    return d is not None and d <= delta_large


# ============================================================================================== M. headroom confidence bounds
SEL_RANGE = (-1.0, 1.0)            # per-instance selector estimate Y_fresh(sel) - Y_fresh(pi0)
NAIVE_RANGE = (-1.0, 1.0)          # max_a Ybar_R - Ybar_R(pi0)
GAP_RANGE = (-1.0, 1.0)            # mean over tools of Ybar_R - Ybar_R(pi0)


def vhat_range(T: int = TOOLS, R: int = 2):
    """Range of S^2_a(Ybar_R) - mean_a s_a^2 / R for binary draws: S^2 over T values in [0, 1] is at most T / (4 (T - 1));
    the sample variance of R binary draws is at most R / (4 (R - 1)), so the subtracted term is at most 1 / (4 (R - 1))."""
    return -1.0 / (4.0 * (R - 1)), T / (4.0 * (T - 1))


def ucb(base_means, alpha: float, method: str, rng_) -> float:
    x = np.asarray(base_means, float)
    G = len(x)
    if method == "t":
        return float(x.mean()) + t_ppf(1 - alpha, G - 1) * float(x.std(ddof=1)) / math.sqrt(G)
    if method == "hoeffding":                  # finite sample; bases independent (I9); base means inside rng_
        return float(x.mean()) + (rng_[1] - rng_[0]) * math.sqrt(math.log(1.0 / alpha) / (2.0 * G))
    raise ValueError(method)


def lcb(base_means, alpha, method, rng_) -> float:
    return -ucb(-np.asarray(base_means, float), alpha, method, (-rng_[1], -rng_[0]))


def headroom_interval(sel, naive, vhat, gap, alpha=0.10, method="hoeffding", T=TOOLS, R=2) -> dict:
    """Simultaneous (1 - alpha) region for Gamma from BASE-level means of the four per-instance estimates.
    Bonferroni split: L_sel alpha/3, U_naive alpha/3, and U_var's two components alpha/6 each, so every bound holds jointly with
    probability >= 1 - alpha. U_var = (T-1)/sqrt(T) * sqrt(max(UCB[E V], 0)) + UCB[E gap]: E V >= 0, so truncating a negative
    bound at 0 can only enlarge the coverage event; sqrt is monotone, so no delta method is used at the 0 boundary.
    The joint coverage is GUARANTEED (finite sample, independent bases, bounded estimates) only for method='hoeffding';
    method='t' is a normal-theory approximation."""
    L = lcb(sel, alpha / 3, method, SEL_RANGE)
    Un = ucb(naive, alpha / 3, method, NAIVE_RANGE)
    UV = max(ucb(vhat, alpha / 6, method, vhat_range(T, R)), 0.0)
    Ug = ucb(gap, alpha / 6, method, GAP_RANGE)
    Uv = (T - 1) / math.sqrt(T) * math.sqrt(UV) + Ug
    return {"L_sel": L, "U_naive": Un, "U_var": Uv, "upper": min(Un, Uv), "UCB_EV": UV, "vhat_mean": float(np.mean(vhat))}


def simulate_headroom_estimates(rng, Q, base, R: int = 2):
    """Synthetic per-instance estimates from a Q matrix (pi0 = tool 0), returned as BASE means."""
    n = len(Q)
    K = (rng.random((n, Q.shape[1], R)) < Q[:, :, None]).astype(float)
    Yb = K.mean(2)
    sel = np.argmax(Yb + rng.random(Yb.shape) * 1e-6, 1)
    e_sel = (rng.random(n) < Q[np.arange(n), sel]).astype(float) - (rng.random(n) < Q[:, 0]).astype(float)
    e_nav = Yb.max(1) - Yb[:, 0]
    vh = tool_variance_component(K)
    gap = Yb.mean(1) - Yb[:, 0]
    G = int(base.max()) + 1
    cnt = np.bincount(base, minlength=G)
    bm = lambda v: np.bincount(base, weights=v, minlength=G) / cnt
    return bm(e_sel), bm(e_nav), bm(vh), bm(gap)

# ============================================================================================== report
def fmt(x):
    return "n/a" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default="p05_design_calc_output.md")
    ap.add_argument("--skip-e", action="store_true", help="omit section E (preview only)")
    ap.add_argument("--inflation-dir", default=None, help="read section E from p05_inflation_run.py JSON files G<G>_s<i>.json")
    ap.add_argument("--compute-e", action="store_true", help="recompute section E here (memory/CPU heavy; not used in rev. 2.1)")
    a = ap.parse_args(argv)
    if not (a.skip_e or a.inflation_dir or a.compute_e):
        ap.error("section E is read from --inflation-dir in rev. 2.1 (or pass --skip-e); --compute-e is explicit opt-in")
    sys.path.insert(0, a.worktree)
    from creature_forge import experience_p0 as p0      # pure numpy; tripwire above blocks MuJoCo
    assert sys.modules.get("mujoco") is None
    t0 = time.time()
    L = ["# P0.5 rev. 2.1: design-stage calculations (synthetic / closed form; NOT measured Creature Forge properties)", "",
         f"seed {SEED}; generated by p05_design_calc.py", ""]

    # C. precision
    Gs, ms, rhos, qs = (8, 12, 24, 28, 34, 40, 46), (1, 2, 3), (0.0, 0.2, 0.5), (0.10, 0.15, 0.25, 0.30, 0.42, 0.50)
    L += ["## C1. 90 % half-width at delta = 0, fixed policies (infl = 1): normal approximation z | t with G-1 df", "",
          "| q | rho | " + " | ".join(f"{G}x{m}" for G in Gs for m in ms) + " |", "|---|---|" + "---|" * (len(Gs) * len(ms))]
    for q in qs:
        for rho in rhos:
            cells = [f"{halfwidth(q, 0, G, m, rho, 1, method='z'):.3f} / {halfwidth(q, 0, G, m, rho, 1, method='t'):.3f}"
                     for G in Gs for m in ms]
            L.append(f"| {q} | {rho} | " + " | ".join(cells) + " |")
    L += ["", "## C2. Minimum detectable effect (one-sided alpha 0.05, power 0.80), t-based, infl in {1, 2, 3}", "",
          "| q | rho | infl | " + " | ".join(f"{G}x{m}" for G in Gs for m in (1, 2, 3)) + " |",
          "|---|---|---|" + "---|" * (len(Gs) * 3)]
    for q in qs:
        for rho in (0.0, 0.2, 0.5):
            for infl in (1.0, 2.0, 3.0):
                L.append(f"| {q} | {rho} | {infl} | " + " | ".join(fmt(mde(q, G, m, rho, infl)) for G in Gs for m in (1, 2, 3)) + " |")
    L += ["", "## C3. Bases needed (t-based, power 0.80, one-sided 0.05), m = 2", "",
          "| delta | q | rho | infl=1 | infl=2 | infl=3 |", "|---|---|---|---|---|---|"]
    for delta in (0.05, 0.10, 0.15):
        for q in qs:
            if delta > q:
                L.append(f"| {delta} | {q} | - | impossible: delta > q | | |")
                continue
            for rho in (0.2, 0.5):
                L.append(f"| {delta} | {q} | {rho} | " + " | ".join(fmt(bases_needed(delta, q, 2, rho, i)) for i in (1.0, 2.0, 3.0)) + " |")

    # D. coverage
    reps = 600 if a.quick else 2000
    L += ["", "## J. Achieved ICC of the section-D cluster generator (exact, clipped-normal moments)", "",
          "rev. 2 set sigma^2 = rho_nominal (q - delta^2) and clipped delta_b to [-q, q]; the ICC it achieved is below the label. "
          "For this generator (constant per-base discordance q) the ICC can never reach q: targets >= q are unattainable.", "",
          "| q | delta | rho_nominal (rev. 2 label) | achieved ICC | calibrated sigma for achieved = 0.10 | for achieved = 0.30 |",
          "|---|---|---|---|---|---|"]
    for q in (0.15, 0.30, 0.42, 0.50):
        for delta in (0.0, 0.05):
            if delta > q:
                continue
            ach = achieved_icc(q, delta, rev2_nominal_sigma(q, delta, 0.3))
            s1 = calibrate_sigma(q, delta, 0.10)
            try:
                s3 = f"{calibrate_sigma(q, delta, 0.30):.4f}"
            except ValueError:
                s3 = "unattainable (ICC < q)"
            L.append(f"| {q} | {delta} | 0.3 | {ach:.4f} | {s1:.4f} | {s3} |")
    L += ["", f"## D. Few-cluster coverage of nominal 90 % intervals (synthetic, {reps} reps, m = 2, delta = 0)", "",
          "D1 relabels the rev. 2 runs by their ACHIEVED ICC (same seeds and sigma, so same numbers); D2 reruns with a "
          "calibrated generator at achieved ICC 0.10 and, where attainable, 0.30.", "",
          "| table | G | q | achieved ICC | z, CR0 | t(G-1), CR1 | percentile cluster bootstrap | P(SE = 0) | MC se |",
          "|---|---|---|---|---|---|---|---|---|"]
    for G in (8, 12, 24, 46):
        for q in (0.15, 0.42):
            for rho in (0.0, 0.3):
                r = coverage_sim(G, 2, q, 0.0, None, reps=reps, n_boot=499 if a.quick else 999,
                                 sigma=rev2_nominal_sigma(q, 0.0, rho))
                L.append(f"| D1 (rev. 2 label rho={rho}) | {G} | {q} | {r['rho_achieved']} | {r['cov_z_CR0']} | {r['cov_t_CR1']} | "
                         f"{r['cov_boot_pct']} | {r['zero_se_frac']} | {r['mc_se']} |")
    for G in (8, 12, 24, 46):
        for q in (0.15, 0.42):
            for rho in (0.10, 0.30):
                if rho >= icc_supremum(q):
                    L.append(f"| D2 | {G} | {q} | {rho}: unattainable | | | | | |")
                    continue
                r = coverage_sim(G, 2, q, 0.0, rho, reps=reps, n_boot=499 if a.quick else 999)
                L.append(f"| D2 | {G} | {q} | {r['rho_achieved']} | {r['cov_z_CR0']} | {r['cov_t_CR1']} | "
                         f"{r['cov_boot_pct']} | {r['zero_se_frac']} | {r['mc_se']} |")

    # E. learning inflation
    L += ["", "## E. Learning-variance inflation of the exact P0 decision pipeline (synthetic data, m = 2)", "",
          "| G | scenario | sims | procedure estimand (MC se) | sd of estimate | rms naive CR1 se | inflation (var ratio) | MC rel. sd of ratio | P(naive se = 0) | naive t90 coverage (all / se>0) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for G, sims in () if a.skip_e else ((12, 60 if a.quick else 200), (24, 30 if a.quick else 80), (46, 20 if a.quick else 30)):
        for i, sc in enumerate(SCENARIOS):
            if not a.compute_e:
                import json
                import os
                fp = os.path.join(a.inflation_dir or "infl2", f"G{G}_s{i}.json")
                if not os.path.exists(fp):
                    L.append(f"| {G} | {sc} | - | NOT COMPUTED (run absent: {os.path.basename(fp)}) | | | | | | |")
                    continue
                r = json.load(open(fp))
                sims = r["sims"]
            else:
                r = learning_inflation(p0, G, 2, sc, sims)
            L.append(f"| {G} | {sc} | {sims} | {r['procedure_estimand']} ({r['procedure_estimand_mc_se']}) | {r['sd_estimate']} | "
                     f"{r['rms_naive_se']} | {r['inflation_var_ratio']} | {r['ratio_mc_rel_sd']} | {r['zero_se_fraction']} | "
                     f"{r['naive_t90_coverage']} / {r['naive_t90_coverage_nondegenerate']} |")

    # F. headroom
    L += ["", "## F1. Headroom estimands (exact binomial; synthetic Q distributions; pi0 = a fixed tool)", "",
          "Gamma_true = E[max_a Q - Q(pi0)]; sel_R = selector trained on R replicates (LOWER bound, -> Gamma_true as R grows); "
          "naive_R = E[max_a Ybar_R - Q(pi0)] (UPPER bound, -> Gamma_true as R grows).", "",
          "var_bound = (T-1)/sqrt(T) sqrt(E V_Q) + E[Qbar - Q(pi0)]: a valid UPPER bound needing only R >= 2 (V_Q unbiasedly estimable).", "",
          "| scenario | Gamma_true | var_bound | " + " | ".join(f"sel_R{R} / naive_R{R}" for R in (1, 2, 3, 4)) + " |", "|---|---|---|" + "---|" * 4]
    for row in headroom_table(n=600 if a.quick else 1500):
        L.append(f"| {row['scenario']} | {row['Gamma_true']} | {row['var_bound']} | " + " | ".join(f"{row[f'sel_R{R}']} / {row[f'naive_R{R}']}" for R in (1, 2, 3, 4)) + " |")
    L += ["", "## F2. Instances needed for a 90 % half-width h on each bracket end (rho = 0.2, m = 2)", "",
          "| scenario | R | sd sel. estimator | sd naive estimator | n for h=0.10 (sel / naive) | n for h=0.05 (sel / naive) |",
          "|---|---|---|---|---|---|"]
    for name in HEADROOM_SCENARIOS:
        for R in (1, 2, 3):
            s1, s2 = headroom_estimator_sd(name, R)
            L.append(f"| {name} | {R} | {s1:.3f} | {s2:.3f} | {instances_for_halfwidth(s1, 0.10, 0.2, 2)} / {instances_for_halfwidth(s2, 0.10, 0.2, 2)} | "
                     f"{instances_for_halfwidth(s1, 0.05, 0.2, 2)} / {instances_for_halfwidth(s2, 0.05, 0.2, 2)} |")

    L += ["", "## F3. Variance-component estimator (R = 2): per-instance sd of Vhat and instances for a 90 % half-width on E[V]", "",
          "| scenario | E[V_Q] | sd(Vhat) | n for half-width 0.005 | n for 0.01 | implied var_bound change per +0.01 in E[V] near E[V] |", "|---|---|---|---|---|---|"]
    rng = np.random.default_rng(SEED + 9)
    for name in HEADROOM_SCENARIOS:
        Q = headroom_instances(rng, name, 4000)
        Y = (rng.random((4000, TOOLS, 2)) < Q[:, :, None]).astype(float)
        vh = tool_variance_component(Y)
        ev = float(Q.var(1, ddof=1).mean())
        slope = (TOOLS - 1) / math.sqrt(TOOLS) * (math.sqrt(ev + 0.01) - math.sqrt(ev))
        L.append(f"| {name} | {ev:.4f} | {vh.std():.4f} | {instances_for_halfwidth(vh.std(), 0.005, 0.2, 2)} | "
                 f"{instances_for_halfwidth(vh.std(), 0.01, 0.2, 2)} | {slope:.3f} |")

    # G. noise
    L += ["", "## G. Equally effective stochastic tools (no tool effect at all)", "",
          "| p | discordance q | realised p_minus | expected harm | P(informative), K=4 | K=10 |", "|---|---|---|---|---|---|"]
    for p in (0.1, 0.2, 0.3, 0.5):
        r4, r10 = equal_tool_noise(p, 4), equal_tool_noise(p, 10)
        L.append(f"| {p} | {r4['q_discordance']:.2f} | {r4['realised_p_minus']:.2f} | 0 | {r4['P_informative_K4']:.2f} | {r10['P_informative_K10']:.2f} |")
    L += ["", "Harm bounds E[(Q0-QM)+] from (mean, Var tau): " + "; ".join(
        f"mu={mu}, var={v}: [{harm_bounds(mu, v)[0]:.3f}, {harm_bounds(mu, v)[1]:.3f}]" for mu, v in ((0.0, 0.01), (0.05, 0.02), (0.05, 0.05)))]

    # H. cost
    L += ["", "## I. Minimum repair budgets and budget-feasible tool sets (eng_tools.min_repair_budget, published code)", "",
          "| tool | dim | population | min budget, 4 train seeds | min budget, 8 train seeds |", "|---|---|---|---|---|"]
    for t in sorted(TOOL_DIMS, key=lambda t: (min_repair_budget(t, 8), t)):
        L.append(f"| {t} | {TOOL_DIMS[t]} | {population(TOOL_DIMS[t])} | {min_repair_budget(t, 4)} | {min_repair_budget(t, 8)} |")
    L += ["", "| B | n_train | feasible at B | at B + 36 | at B + 40 |", "|---|---|---|---|---|"]
    for B, nt in ((160, 8), (160, 4), (200, 8), (300, 8), (700, 8)):
        L.append(f"| {B} | {nt} | {len(budget_feasible(B, nt))} | {len(budget_feasible(B + 36, nt))} | {len(budget_feasible(B + 40, nt))} |")
    L += ["", "## K. Discordance bound for ANY two tool-choice policies: q <= min(1, 2 E max_a Q, 2 - 2 E min_a Q)", "",
          "| scenario | E max_a Q | E min_a Q | bound on q | pure-noise q of two equal tools at E Q |", "|---|---|---|---|---|"]
    rngk = np.random.default_rng(SEED + 13)
    for name in HEADROOM_SCENARIOS:
        Q = headroom_instances(rngk, name, 4000)
        emax, emin, em = float(Q.max(1).mean()), float(Q.min(1).mean()), float(Q.mean())
        L.append(f"| {name} | {emax:.3f} | {emin:.3f} | {discordance_upper_any_policies(emax, emin):.3f} | {2 * em * (1 - em):.3f} |")
    L += ["", "## L. Benefit detection vs equivalence demonstration (t-based; SE at delta = 0; m_inst = instances per base)", "",
          "MDE: one-sided 0.05, power 0.80. M_nmg: smallest margin with P(U < M | delta = 0) = 0.80 (U = upper 90 % bound). "
          "M_tost: two-sided equivalence (L > -M and U < M) with power 0.80.", "",
          "| G | m_inst | q | rho | infl | MDE | M_nmg | M_tost | no-gain shown at M=0.05 / 0.10 / 0.15 |", "|---|---|---|---|---|---|---|---|---|"]
    for G in (12, 18, 22, 28, 34, 40):
        for mi in (2, 3):
            for q in (0.15, 0.30, 0.42, 0.50):
                for rho in (0.1, 0.3):
                    for infl in (1.0, 2.25, 2.7):
                        nmg = equivalence_margin_demonstrable(q, G, mi, rho, infl)
                        tost = equivalence_margin_demonstrable(q, G, mi, rho, infl, two_sided=True)
                        ok = " / ".join("yes" if nmg <= M else "no" for M in (0.05, 0.10, 0.15))
                        L.append(f"| {G} | {mi} | {q} | {rho} | {infl} | {fmt(mde(q, G, mi, rho, infl))} | {nmg:.3f} | {tost:.3f} | {ok} |")
    L += ["", "## M. Simultaneous 90 % headroom region (Bonferroni over three bounds; synthetic, one dataset per row, R = 2, m = 2)", "",
          "| scenario | G | true Gamma | method | L_sel | U_naive | U_var | reported upper | UCB of E[V] (truncated at 0) |", "|---|---|---|---|---|---|---|---|---|"]
    for name in HEADROOM_SCENARIOS:
        for G in (12, 34):
            rngm = np.random.default_rng(SEED + 17 + G)
            Q = headroom_instances(rngm, name, 2 * G)
            base = np.repeat(np.arange(G), 2)
            est = simulate_headroom_estimates(rngm, Q, base)
            true = float(np.mean(Q.max(1) - Q[:, 0]))
            for meth in ("t", "hoeffding"):
                h = headroom_interval(*est, method=meth)
                L.append(f"| {name} | {G} | {true:.3f} | {meth} | {h['L_sel']:.3f} | {h['U_naive']:.3f} | {h['U_var']:.3f} | "
                         f"{h['upper']:.3f} | {h['UCB_EV']:.4f} |")

    L += ["", "## H. Rollout-equivalents and dollars (all inputs [ASSUMP] unless code-derived; prices unverified)", "",
          "Every cost set keeps all ten tools budget-feasible at B (low: B = 160 with 4 train seeds, as P0's matrix; mid/high: "
          "8 train seeds with B >= 200), so the +36 / +40 cost-matched budgets never enlarge the action set.", ""]
    for c in COST_SETS.values():
        check_all_tools_feasible(c)
    designs = {
        "Stage 0 (local; $0 cloud)": dict(n_inst=1, tools=10, R=2, aug_per_inst=2, n_confirm_cells=2, n_sentinel=1),
        "Pilot: 6 bases x 2 inst, R=2, full matrix": dict(n_inst=12, tools=10, R=2, aug_per_inst=2, n_confirm_cells=24, n_sentinel=3),
        "Campaign 28 bases x 2, 25 % R=2": dict(n_inst=56, tools=10, R=1.25, aug_per_inst=2, n_confirm_cells=2 * 14, n_sentinel=3),
        "Campaign 36 bases x 2, 25 % R=2": dict(n_inst=72, tools=10, R=1.25, aug_per_inst=2, n_confirm_cells=2 * 18, n_sentinel=3),
        "Campaign 36 bases x 3, 25 % R=2": dict(n_inst=108, tools=10, R=1.25, aug_per_inst=2, n_confirm_cells=2 * 27, n_sentinel=3),
    }
    L += ["| design | set | prefix | matrix | cost-matched | sel.-confirm | sentinel | total rollout-eq | VM h | $ |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for dn, d in designs.items():
        for sn, c in COST_SETS.items():
            parts = design_re(c, **d)
            hours = parts["total"] / c["throughput_h"] * (1 + c["idle_frac"]) + c["sessions"] * c["overhead_h"]
            usd = 0.0 if dn.startswith("Stage 0") else dollars(c, parts["total"])
            L.append(f"| {dn} | {sn} | " + " | ".join(f"{parts[k]:,.0f}" for k in ("prefix", "matrix cells", "cost-matched cells",
                     "selector-confirmation cells", "sentinel", "total")) + f" | {hours:.1f} | {usd:.2f} |")
    L += ["", "Stage E (physics-only thresholds + eligibility checks, one-time, for bases without a verified threshold file; "
          "39 candidate instances per base = 13 variants x 3 multiples):", "", "| bases needing Stage E | rollout-eq | $ low | $ mid | $ high |",
          "|---|---|---|---|---|"]
    for nb in (0, 6, 18, 48):
        re_ = stage_e_re(nb, 39)
        L.append(f"| {nb} | {re_:,.0f} | " + " | ".join(f"{dollars(c, re_) if nb else 0:.2f}" for c in COST_SETS.values()) + " |")
    L += ["", f"runtime {time.time() - t0:.0f} s"]
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
