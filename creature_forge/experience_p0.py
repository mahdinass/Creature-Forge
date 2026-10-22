"""Experience-learning P0, Phase 3 (docs/plans/EXPERIENCE_LEARNING_PLAN.md rev. 2, §4): offline signal analyses.

Two analyses, each only where the inventory found adequate support:
  * DECISION (proxy tier, the causal-engineer probe set: fixed counterfactual catalogue + complete 10-tool repair matrix).
    Q_proxy(x, a) is identified there because every tool was run by the same assigned procedure. Retrieval methods estimate
    P(repairs | x, tool) from other robots; the decision is the top tool; its value is read off the measured matrix.
  * DIAGNOSTIC PRECONDITION (HDB identifiability panel: every instrument on every instance). Fault-family prediction only;
    never reported as a decision or recovery result.
Everything is fitted inside the outer fold: standardisation, k (inner leave-one-group-out), the frequency prior pi0.
Pure numpy; no simulation.
"""
from __future__ import annotations

import math
import warnings

import numpy as np

from .experience_audit import MORPH_KEYS, assert_whitelisted, morphology
from .experience_bank import FEATURE_KEYS, OBS_KEYS, compute_signature

K_GRID = (1, 3, 5, 9, 15, 25)
COVERAGES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
N_BOOT = 2000
N_SHUFFLE = 20
SEED = 20261022
EPS = 1e-4


# ------------------------------------------------------------------------------------------------ feature space
class Space:
    """A feature matrix with named column blocks. Distances average squared z-differences within a block and sum blocks, so
    every block weighs the same regardless of its width (fixed a priori, never tuned). Missing values (NaN) sit at z = 0."""

    def __init__(self, X: np.ndarray, blocks: dict[str, list[int]], names: list[str] | None = None):
        self.X, self.blocks, self.names = np.asarray(X, float), blocks, list(names or [])

    def dist(self, tr: np.ndarray, te: np.ndarray, use: tuple[str, ...]) -> np.ndarray:
        Xtr, Xte = self.X[tr], self.X[te]
        with warnings.catch_warnings():            # all-missing training columns are expected (z = 0 below)
            warnings.simplefilter("ignore", RuntimeWarning)
            mu = np.nanmean(Xtr, 0)
            sd = np.nanstd(Xtr, 0)
        mu = np.where(np.isfinite(mu), mu, 0.0)
        sd = np.where(np.isfinite(sd) & (sd > 1e-9), sd, 1.0)
        Ztr = np.nan_to_num((Xtr - mu) / sd)
        Zte = np.nan_to_num((Xte - mu) / sd)
        D = np.zeros((len(te), len(tr)))
        for b in use:
            c = self.blocks[b]
            diff = Zte[:, None, c] - Ztr[None, :, c]
            D += np.mean(diff ** 2, axis=2)
        return D


def knn_rates(D: np.ndarray, Ytr: np.ndarray, k: int, prior: np.ndarray) -> np.ndarray:
    """Per query: neighbour-average of each column of Ytr over the k nearest, shrunk to `prior` with weight 1 (Laplace-like)."""
    k = min(k, D.shape[1])
    idx = np.argsort(D, axis=1, kind="stable")[:, :k]
    return (Ytr[idx].sum(1) + prior[None, :]) / (k + 1.0)


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def calibration(p: np.ndarray, y: np.ndarray) -> dict:
    """Logistic recalibration y ~ a + b * logit(p): intercept a (0 ideal) and slope b (1 ideal); 5-bin reliability."""
    p = np.clip(np.asarray(p, float).ravel(), EPS, 1 - EPS)
    y = np.asarray(y, float).ravel()
    X = np.column_stack([np.ones_like(p), np.log(p / (1 - p))])
    w = np.array([0.0, 1.0])
    for _ in range(50):
        q = 1 / (1 + np.exp(-X @ w))
        H = (X * (q * (1 - q))[:, None]).T @ X + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, X.T @ (q - y))
        w -= step
        if np.abs(step).max() < 1e-10:
            break
    bins = np.minimum((p * 5).astype(int), 4)
    rel = [[round(float(p[bins == b].mean()), 3), round(float(y[bins == b].mean()), 3), int((bins == b).sum())]
           for b in range(5) if (bins == b).any()]
    return {"intercept": round(float(w[0]), 3), "slope": round(float(w[1]), 3), "reliability": rel}


def folds(groups: np.ndarray) -> list[tuple[np.ndarray, np.ndarray, str]]:
    return [(np.where(groups != g)[0], np.where(groups == g)[0], str(g)) for g in sorted(set(groups.tolist()))]


def choose_k(space: Space, use, Y: np.ndarray, tr: np.ndarray, inner_groups: np.ndarray) -> int:
    """k by inner leave-one-group-out log loss on the training fold only (standardisation refitted per inner fold)."""
    if not use:
        return 0
    best, best_ll = K_GRID[0], math.inf
    inner = folds(inner_groups[tr])
    for k in K_GRID:
        ll = []
        for itr, ite, _ in inner:
            a, b = tr[itr], tr[ite]
            prior = Y[a].mean(0)
            P = knn_rates(space.dist(a, b, use), Y[a], k, prior)
            ll.append(log_loss(P, Y[b]) * len(b))
        m = sum(ll) / len(tr)
        if m < best_ll - 1e-12:
            best, best_ll = k, m
    return best


def predict(space: Space, use, Y: np.ndarray, groups: np.ndarray, outer_groups: np.ndarray, *,
            shuffle_rng: np.random.Generator | None = None, k_fixed: dict | None = None) -> dict:
    """Out-of-fold P(column | x) for every case (outer folds by `outer_groups`; inner k selection by `groups`).
    shuffle_rng: permute the training store's outcome rows (signature -> outcome link broken) - the shuffled-memory control."""
    n, T = Y.shape
    P = np.zeros((n, T))
    prior_oof = np.zeros((n, T))
    gate_sim = np.zeros(n)
    ks: dict[str, int] = {}
    for tr, te, name in folds(outer_groups):
        prior = Y[tr].mean(0)
        prior_oof[te] = prior
        if not use:
            P[te] = prior
            continue
        k = (k_fixed or {}).get(name) or choose_k(space, use, Y, tr, groups)
        ks[name] = k
        Ytr = Y[tr]
        if shuffle_rng is not None:
            Ytr = Ytr[shuffle_rng.permutation(len(tr))]
        D = space.dist(tr, te, use)
        P[te] = knn_rates(D, Ytr, k, prior)
        gate_sim[te] = -np.sort(D, axis=1)[:, :min(k, D.shape[1])].mean(1)
    return {"P": P, "prior": prior_oof, "gate_sim": gate_sim, "k": ks}


# ------------------------------------------------------------------------------------------------ decision analysis
def decide(P: np.ndarray, prior: np.ndarray) -> np.ndarray:
    """Top tool; ties broken by the training-fold frequency order (pi0's ranking)."""
    return np.argmax(P + 1e-9 * prior, axis=1)


def decision_eval(pred: dict, Y: np.ndarray) -> dict:
    """Per-case decision outcomes against pi0 = the training-fold most frequent repairing tool (the no-memory default)."""
    n = len(Y)
    pick = decide(pred["P"], pred["prior"])
    pi0 = np.argmax(pred["prior"], axis=1)
    v_m = Y[np.arange(n), pick]
    v_0 = Y[np.arange(n), pi0]
    best = Y.max(1)
    benefit_gate = pred["P"][np.arange(n), pick] - pred["P"][np.arange(n), pi0]
    return {"pick": pick, "pi0": pi0, "v_mem": v_m, "v_pi0": v_0, "best": best, "gate_benefit": benefit_gate,
            "gate_sim": pred["gate_sim"]}


def summarize_decision(d: dict, mask: np.ndarray | None = None) -> dict:
    m = np.ones(len(d["v_mem"]), bool) if mask is None else mask
    vm, v0, b = d["v_mem"][m], d["v_pi0"][m], d["best"][m]
    return {"n": int(m.sum()), "value_mem": round(float(vm.mean()), 4), "value_pi0": round(float(v0.mean()), 4),
            "oracle_best": round(float(b.mean()), 4), "regret_mem": round(float((b - vm).mean()), 4),
            "delta_vs_pi0": round(float((vm - v0).mean()), 4),
            "p_plus": round(float(((vm == 1) & (v0 == 0)).mean()), 4), "p_minus": round(float(((vm == 0) & (v0 == 1)).mean()), 4)}


def risk_coverage(d: dict, gate: str) -> list[dict]:
    """Memory's pick is used on the top-c fraction of cases by the gate score, pi0's elsewhere. Rank-based thresholds give
    matched coverage across methods."""
    n = len(d["v_mem"])
    g = d[gate]
    order = np.argsort(-g, kind="stable")
    out = []
    for c in COVERAGES:
        use = np.zeros(n, bool)
        use[order[:int(round(c * n))]] = True
        v = np.where(use, d["v_mem"], d["v_pi0"])
        neg = use & (d["v_mem"] == 0) & (d["v_pi0"] == 1)
        pos = use & (d["v_mem"] == 1) & (d["v_pi0"] == 0)
        out.append({"coverage": c, "value": round(float(v.mean()), 4), "delta_vs_pi0": round(float((v - d["v_pi0"]).mean()), 4),
                    "negative_transfer": round(float(neg.mean()), 4), "positive_transfer": round(float(pos.mean()), 4)})
    return out


def cluster_bootstrap(values: dict[str, np.ndarray], groups: np.ndarray, stat, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Percentile CI of stat(values) resampling GROUPS (robot bases) with replacement."""
    rng = np.random.default_rng(seed)
    gs = sorted(set(groups.tolist()))
    idx = {g: np.where(groups == g)[0] for g in gs}
    boots = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(gs), len(gs))
        ii = np.concatenate([idx[gs[i]] for i in pick])
        boots.append(stat({k: v[ii] for k, v in values.items()}))
    b = np.array(boots)
    return {"est": round(float(stat(values)), 4), "ci90": [round(float(np.percentile(b, 5)), 4), round(float(np.percentile(b, 95)), 4)],
            "ci95": [round(float(np.percentile(b, 2.5)), 4), round(float(np.percentile(b, 97.5)), 4)], "n_groups": len(gs)}


def hard_negative_separation(space: Space, Y: np.ndarray, groups: np.ndarray, select_use, score_uses: dict,
                             details: list | None = None) -> dict:
    """For each query with at least one repairing and one failing tool, find in the OTHER bases the nearest case (in the
    `select_use` space) whose own best tool repairs the query (hard positive) and the nearest whose best tool fails on it
    (hard negative). Each score space then 'separates' the pair if it puts the positive closer. The query's outcomes are used
    only to construct this control, never as a feature. Returns per-space separation rates (0.5 = no information)."""
    out = {s: [] for s in score_uses}
    qgroups = []
    for tr, te, _ in folds(groups):
        rates = Y[tr].mean(0)
        own_best = np.argmax(Y[tr] + 1e-9 * rates, axis=1)
        Dsel = space.dist(tr, te, select_use)
        Ds = {s: space.dist(tr, te, u) for s, u in score_uses.items()}
        for qi, q in enumerate(te):
            if Y[q].max() == 0 or Y[q].min() == 1:
                continue
            ok = Y[q, own_best] == 1
            if ok.all() or (~ok).all():
                continue
            order = np.argsort(Dsel[qi], kind="stable")
            hp = next(j for j in order if ok[j])
            hn = next(j for j in order if not ok[j])
            for s in score_uses:
                d = Ds[s][qi]
                out[s].append(1.0 if d[hp] < d[hn] else (0.5 if d[hp] == d[hn] else 0.0))
            qgroups.append(groups[q])
            if details is not None:          # per-query record for the evidence export (does not change the result)
                details.append({"query": int(q), "hard_positive": int(tr[hp]), "hard_negative": int(tr[hn]),
                                **{f"separated:{s}": out[s][-1] for s in score_uses}})
    g = np.array(qgroups)
    res: dict = {"n_queries": len(g)}
    for s, v in out.items():
        res[s] = cluster_bootstrap({"x": np.array(v)}, g, lambda d: d["x"].mean()) if len(v) else None
    if len(score_uses) >= 2 and len(g):
        a, b = list(score_uses)[:2]
        res[f"{a}_minus_{b}"] = cluster_bootstrap({"a": np.array(out[a]), "b": np.array(out[b])}, g,
                                                  lambda d: d["a"].mean() - d["b"].mean())
    return res


# ------------------------------------------------------------------------------------------------ diagnostic analysis
def class_metrics(P: np.ndarray, y: np.ndarray) -> dict:
    """Multi-class log loss, Brier, top-1 accuracy, ECE of the top probability (10 bins), selective accuracy by coverage."""
    n, C = P.shape
    P = np.clip(P, EPS, 1.0)
    P = P / P.sum(1, keepdims=True)
    onehot = np.zeros_like(P)
    onehot[np.arange(n), y] = 1
    top = P.argmax(1)
    conf = P.max(1)
    acc = (top == y).astype(float)
    bins = np.minimum((conf * 10).astype(int), 9)
    ece = sum(abs(conf[bins == b].mean() - acc[bins == b].mean()) * (bins == b).mean() for b in range(10) if (bins == b).any())
    order = np.argsort(-conf, kind="stable")
    sel = {str(c): round(float(acc[order[:max(1, int(round(c * n)))]].mean()), 4) for c in (0.25, 0.5, 0.75, 1.0)}
    return {"n": n, "log_loss": round(float(-np.mean(np.log(P[np.arange(n), y]))), 4),
            "brier": round(float(np.mean(np.sum((P - onehot) ** 2, 1))), 4), "top1": round(float(acc.mean()), 4),
            "ece": round(float(ece), 4), "selective_acc": sel}


def class_predict(space: Space, use, y: np.ndarray, C: int, groups: np.ndarray, outer_groups: np.ndarray, **kw) -> dict:
    """Out-of-fold kNN class probabilities (one-hot rates shrunk to the training class frequencies); kw as in `predict`."""
    Y = np.zeros((len(y), C))
    Y[np.arange(len(y)), y] = 1
    return predict(space, use, Y, groups, outer_groups, **kw)


def per_case_logp(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    P = np.clip(P, EPS, 1.0)
    P = P / P.sum(1, keepdims=True)
    return np.log(P[np.arange(len(y)), y])


# ------------------------------------------------------------------------------------------------ datasets
CE_TOOLS = ("feedback", "foot_friction", "foot_length", "leg_length", "placement", "posture", "stride", "timing",
            "torque_limit", "torso_mass")
CE_REPAIRS = 0.75                 # a tool repairs the robot if it walks on >= 75 % of the 8 check seeds (fault_bench)
CE_OBS_KEYS = tuple(k for k in OBS_KEYS if k not in FEATURE_KEYS)
CE_CF_KEYS = ("time_upright", "fall_direction", "pitch_end", "com_vx_end", "step_length_over_L", "slip_fraction",
              "capture_margin_over_L_end")
IDENT_KEYS = ("walking", "time_upright", "fall_direction", "pitch_mean", "com_vx_mean", "step_freq_hz", "step_length_over_L",
              "slip_fraction", "double_support_fraction", "capture_margin_over_L_mean", "saturation_frac_hip",
              "saturation_frac_knee", "saturation_frac_ankle", "friction_utilisation_p95")
IDENT_CF_KEYS = ("walking", "time_upright", "fall_direction", "pitch_mean", "com_vx_mean")
HDB_FAMILIES = ("pitch_sensor_bias", "payload_offset", "low_ground_friction", "short_feet", "feedback_gain_loss",
                "actuator_weakness", "one_side_weakness", "clock_fault", "heavy_torso")


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else np.nan


def _assemble(cols: dict[str, list[str]], rows: list[dict]) -> Space:
    names: list[str] = []
    blocks = {}
    for b, cs in cols.items():
        blocks[b] = list(range(len(names), len(names) + len(cs)))
        names += cs
    assert_whitelisted(names)
    return Space(np.array([[r.get(c, np.nan) for c in names] for r in rows], float), blocks, names)


def ce_dataset(probe_rows: list[dict], nominal_morph: dict) -> dict:
    """Causal-engineer probe set -> blocks morph (the NOMINAL base design), obs (pre-intervention observation signature),
    cf (responses to the fixed 9-counterfactual catalogue, as change from the observation) and faulty (the faulty robot's own
    body: a leakage probe only, because on this older bench the fault is visible in the body). Targets: repairs per tool and
    walking fraction. Fault labels are returned for splitting and scoring only."""
    cf_names = sorted({c for r in probe_rows for c in r["counterfactuals"]})
    cols = {"morph": [f"m:{k}" for k in MORPH_KEYS], "obs": [f"o:{k}" for k in CE_OBS_KEYS],
            "cf": [f"c:{c}:{k}" for c in cf_names for k in CE_CF_KEYS + ("n_walking",)],
            "faulty": [f"b:{k}" for k in MORPH_KEYS]}
    feats, Y, W, base, fault, missing_morph = [], [], [], [], [], 0
    for r in probe_rows:
        f = {}
        nm = nominal_morph.get(r["base_id"])
        missing_morph += nm is None
        fb = morphology(r["robot"]["body"])
        for k in MORPH_KEYS:
            f[f"m:{k}"] = nm[k] if nm else np.nan
            f[f"b:{k}"] = fb[k]
        s0 = compute_signature(r["observation"]["median"], {}) or {}
        for k in CE_OBS_KEYS:
            f[f"o:{k}"] = _num(s0.get(k))
        n0 = r["observation"].get("n_walking")
        for c in cf_names:
            o = (r["counterfactuals"].get(c) or {}).get("observation") or {}
            s1 = compute_signature(o.get("median") or {}, {}) or {}
            for k in CE_CF_KEYS:
                f[f"c:{c}:{k}"] = _num(s1.get(k)) - _num(s0.get(k))
            f[f"c:{c}:n_walking"] = (_num(o.get("n_walking")) - _num(n0)) / 4.0
        feats.append(f)
        m = r["repair_matrix"]
        Y.append([1.0 if (m.get(t) is not None and m[t] >= CE_REPAIRS) else 0.0 for t in CE_TOOLS])
        W.append([float(m.get(t, 0.0)) for t in CE_TOOLS])
        base.append(r["base_id"])
        fault.append(r["instance_id"].split(":")[1])
    return {"space": _assemble(cols, feats), "Y": np.array(Y), "W": np.array(W), "base": np.array(base),
            "fault": np.array(fault), "tools": CE_TOOLS, "cf_names": cf_names, "missing_nominal_morph": int(missing_morph)}


def _median_panel(by_seed, keys) -> dict:
    out = {}
    for k in keys:
        v = sorted(x for x in (_num((f or {}).get(k)) for f in (by_seed or {}).values()) if np.isfinite(x))
        out[k] = float(np.median(v)) if v else np.nan
    return out


def ident_dataset(ident_rows: list[dict], nominal_morph: dict) -> dict:
    """HDB identifiability panel (eligible instances) -> blocks morph (nominal), obs (observe), cond (floor test + weigh test),
    cf (each catalogue counterfactual as change from observe; NaN where the design's bounds excluded it), belief (the stored
    model-based twin posterior over families with all instruments). Label: the injected family (scoring/splitting only)."""
    rows = [r for r in ident_rows if not r.get("skipped") and r.get("eligible") and r["family"] in HDB_FAMILIES]
    cf_names = sorted({c for r in rows for c in r["panel"] if c.startswith("cf:")})
    cols = {"morph": [f"m:{k}" for k in MORPH_KEYS], "obs": [f"o:{k}" for k in IDENT_KEYS],
            "cond": [f"fl:{k}" for k in IDENT_KEYS] + ["w:mass_kg", "w:com_x_m"],
            "cf": [f"{c}:{k}" for c in cf_names for k in IDENT_CF_KEYS],
            "belief": [f"q:{i}" for i in range(len(HDB_FAMILIES))]}
    feats, y, base = [], [], []
    post: dict[str, list] = {"obs": [], "obs+conditions": [], "all": []}
    for r in rows:
        f = {}
        nm = nominal_morph.get(r["base_id"]) or {}
        for k in MORPH_KEYS:
            f[f"m:{k}"] = nm.get(k, np.nan)
        o = _median_panel(r["panel"].get("observe"), IDENT_KEYS)
        fl = _median_panel(r["panel"].get("floor_test@x3"), IDENT_KEYS)
        for k in IDENT_KEYS:
            f[f"o:{k}"] = o[k]
            f[f"fl:{k}"] = fl[k]
        w = r["panel"].get("weigh_test") or {}
        f["w:mass_kg"], f["w:com_x_m"] = _num(w.get("mass_kg")), _num(w.get("com_x_m"))
        for c in cf_names:
            cm = _median_panel(r["panel"][c], IDENT_CF_KEYS) if c in r["panel"] else {k: np.nan for k in IDENT_CF_KEYS}
            for k in IDENT_CF_KEYS:
                f[f"{c}:{k}"] = cm[k] - o[k]
        for name in post:
            q = np.nan_to_num(np.array([_num(r["posterior"][name].get(fm, 0.0)) for fm in HDB_FAMILIES]))
            post[name].append(q / q.sum() if q.sum() > 0 else np.full(len(q), 1 / len(q)))
        for i in range(len(HDB_FAMILIES)):
            f[f"q:{i}"] = post["all"][-1][i]
        feats.append(f)
        y.append(HDB_FAMILIES.index(r["family"]))
        base.append(r["base_id"])
    return {"space": _assemble(cols, feats), "y": np.array(y), "base": np.array(base),
            "posterior": {k: np.array(v) for k, v in post.items()}, "cf_names": cf_names, "n_rows": len(rows)}
