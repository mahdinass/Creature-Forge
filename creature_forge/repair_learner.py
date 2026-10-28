"""Level C of the causal engineer: a learned repair-effect predictor, P(tool repairs | observation, body features[, counterfactuals]).

Purpose. Trained on the MEASURED repair matrices of training instances (walking fraction on independent check seeds after a CMA-ES
repair with each tool), it predicts for a new robot which tools will repair it, so the scientist can be shown "learned advice" and a
"predict then repair" policy can be built. Pure Python + numpy (no sklearn/torch): deterministic given the seeds.

Trust boundary (physics-integrity).
- NO LABEL LEAKAGE. `build_features` reads ONLY `row["observation"]`, `row["features"]` and `row["counterfactuals"]`. It never touches
  `instance_id`, `base_id`, the fault name, severity, region or the repair matrix (unit-tested by perturbing those fields).
- Target: y[tool] = 1 iff the measured walking fraction >= REPAIR_THRESHOLD (6 of 8 check seeds); a tool absent from the matrix is
  MASKED (M = 0), never a negative. The target is a verified repair outcome, not a proxy.
- Outputs are statistical predictions from a few training robots, not measurements; `advice_text` says so. Callers must fit only on
  training instances (the evaluation script does leave-one-base-out).
- The signature computation is reused from `experience_bank.compute_signature` / `SIGNATURE_KEYS` (not replicated).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from .experience_bank import SIGNATURE_KEYS, compute_signature, _num

VERSION = "repair_learner_v1"
REPAIR_THRESHOLD = 0.75
TOOLS = ("feedback", "foot_friction", "foot_length", "leg_length", "placement", "posture", "stride", "timing", "torque_limit",
         "torso_mass")
CF_IDS = ("foot_length_x1.3", "torso_mass_x0.75", "torque_limit_x1.6", "foot_friction_x2.5", "pitch_ref_-0.08", "freq_x0.85",
          "feedback_gains_x2", "placement_gains_0.5", "leg_length_x0.85")      # == eng_tools.COUNTERFACTUALS order
CF_DELTA_KEYS = ("n_walking", "time_upright", "capture_margin_over_L_end", "pitch_end", "com_vx_end")
EXTRA_BODY = ("L", "mass_total", "leg_density")
SETTINGS = ("obs", "obs+cf")
_EPS = 1e-6


# ------------------------------------------------------------------------------------------------------------ features
def feature_names(setting: str) -> list[str]:
    names = list(SIGNATURE_KEYS) + list(EXTRA_BODY) + ["n_walking", "n_fell"]
    if setting == "obs+cf":
        for cid in CF_IDS:
            names += [f"cf:{cid}:{k}" for k in CF_DELTA_KEYS] + [f"cf:{cid}:refused"]
    elif setting != "obs":
        raise ValueError(f"unknown setting {setting!r}")
    return names


def build_features(row: dict, setting: str) -> tuple[np.ndarray, list[str]]:
    """Raw feature vector (NaN = missing) and the list of missing feature names. Uses only observation, features, counterfactuals."""
    obs = row.get("observation") or {}
    feats = row.get("features") or {}
    sig = compute_signature(obs.get("median"), feats) or {k: None for k in SIGNATURE_KEYS}
    vals: list = [sig.get(k) for k in SIGNATURE_KEYS] + [feats.get(k) for k in EXTRA_BODY] + [obs.get("n_walking"), obs.get("n_fell")]
    if setting == "obs+cf":
        cfs = row.get("counterfactuals") or {}
        for cid in CF_IDS:
            res = cfs.get(cid)
            if not isinstance(res, dict) or "deltas" not in res:
                vals += [None] * len(CF_DELTA_KEYS) + [1.0 if isinstance(res, dict) and "refused" in res else None]
            else:
                d = res.get("deltas") or {}
                vals += [d.get(k) for k in CF_DELTA_KEYS] + [0.0]
    elif setting != "obs":
        raise ValueError(f"unknown setting {setting!r}")
    x = np.array([np.nan if _num(v) is None else float(_num(v)) for v in vals], dtype=float)
    names = feature_names(setting)
    return x, [names[i] for i in np.flatnonzero(np.isnan(x))]


def targets(repair_matrix: dict, tools: tuple[str, ...] = TOOLS) -> tuple[np.ndarray, np.ndarray]:
    """(y, mask): y = 1 if the measured walking fraction >= threshold; mask = 0 for a tool absent from the matrix."""
    y, m = np.zeros(len(tools)), np.zeros(len(tools))
    for i, t in enumerate(tools):
        v = _num((repair_matrix or {}).get(t))
        if v is not None:
            m[i], y[i] = 1.0, float(v >= REPAIR_THRESHOLD)
    return y, m


class Preprocessor:
    """NaN-aware standardiser fitted on the training fold only; missing -> 0 after standardising, plus a flag per column that had any
    missing value in the training fold."""

    def fit(self, X: np.ndarray) -> "Preprocessor":
        self.mean, self.std = np.zeros(X.shape[1]), np.ones(X.shape[1])
        for j in range(X.shape[1]):
            v = X[~np.isnan(X[:, j]), j]
            if len(v):
                self.mean[j] = v.mean()
                sd = v.std() if len(v) > 1 else 0.0
                self.std[j] = sd if sd > 1e-9 else 1.0
        self.flag_cols = [int(j) for j in np.flatnonzero(np.isnan(X).any(axis=0))]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(X)
        Z = np.nan_to_num((X - self.mean) / self.std, nan=0.0)
        Z = np.clip(Z, -6.0, 6.0)
        if self.flag_cols:
            Z = np.hstack([Z, np.isnan(X[:, self.flag_cols]).astype(float)])
        return Z

    def to_dict(self) -> dict:
        return {"mean": self.mean.tolist(), "std": self.std.tolist(), "flag_cols": self.flag_cols}

    @classmethod
    def from_dict(cls, d: dict) -> "Preprocessor":
        p = cls()
        p.mean, p.std, p.flag_cols = np.array(d["mean"]), np.array(d["std"]), list(d["flag_cols"])
        return p


def lobo_splits(groups) -> list[tuple[np.ndarray, np.ndarray, object]]:
    """Leave-one-group-out: [(train_idx, test_idx, held_out_group)], groups sorted; a group is never in both parts."""
    g = np.asarray(groups)
    return [(np.flatnonzero(g != b), np.flatnonzero(g == b), b) for b in sorted(set(g.tolist()))]


# ------------------------------------------------------------------------------------------------------------ models
def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def _logit(p):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return np.log(p / (1 - p))


def _prior(Y, M):
    return (Y * M).sum(0) + 0.5, M.sum(0) + 1.0


class PriorModel:
    """Per-tool repair rate on the training fold (Laplace-smoothed)."""
    name = "prior"

    def fit(self, X, Y, M, groups=None):
        a, b = _prior(Y, M)
        self.p = a / b
        return self

    def predict_proba(self, X):
        return np.tile(self.p, (len(X), 1)), None

    def to_dict(self):
        return {"kind": "prior", "p": self.p.tolist()}


class KNNModel:
    """Distance-weighted mean target vector of the k nearest training instances (Euclidean on the standardised features)."""
    name = "knn"

    def __init__(self, k: int = 5):
        self.k = k

    def fit(self, X, Y, M, groups=None):
        self.X, self.Y, self.M = np.array(X, float), np.array(Y, float), np.array(M, float)
        a, b = _prior(Y, M)
        self.p = a / b
        return self

    def predict_proba(self, X):
        out = np.zeros((len(X), self.Y.shape[1]))
        for i, x in enumerate(X):
            d = np.sqrt(((self.X - x) ** 2).sum(1))
            idx = np.argsort(d, kind="stable")[: self.k]
            w = 1.0 / (d[idx] + 1e-3)
            num = (w[:, None] * self.M[idx] * self.Y[idx]).sum(0)
            den = (w[:, None] * self.M[idx]).sum(0)
            out[i] = np.where(den > 0, num / np.maximum(den, 1e-12), self.p)
        return out, None

    def to_dict(self):
        return {"kind": "knn", "k": self.k, "X": self.X.tolist(), "Y": self.Y.tolist(), "M": self.M.tolist(), "p": self.p.tolist()}


def _fit_logistic(X, y, lam, iters=30):
    """L2-regularised logistic regression by damped Newton; intercept unpenalised. Returns (w, b)."""
    n, d = X.shape
    A = np.hstack([X, np.ones((n, 1))])
    pen = np.full(d + 1, lam)
    pen[-1] = 1e-6
    w = np.zeros(d + 1)
    for _ in range(iters):
        p = _sigmoid(A @ w)
        g = A.T @ (p - y) + pen * w
        H = (A * (p * (1 - p))[:, None]).T @ A + np.diag(pen)
        step = np.linalg.solve(H + 1e-9 * np.eye(d + 1), g)
        w -= step
        if np.abs(step).max() < 1e-7:
            break
    return w[:-1], w[-1]


class LogisticModel:
    """One L2 logistic regression per tool. lambda is chosen by inner leave-one-base-out CV over LAMBDAS when `groups` is given
    (shared across tools, minimising masked log-loss); otherwise DEFAULT_LAMBDA."""
    name = "logistic"
    LAMBDAS = (1.0, 3.0, 10.0, 30.0, 100.0)
    DEFAULT_LAMBDA = 10.0

    def __init__(self, lam: float | None = None):
        self.lam = lam

    def _fit_all(self, X, Y, M, lam):
        d = X.shape[1]
        W, b, const = np.zeros((d, Y.shape[1])), np.zeros(Y.shape[1]), np.zeros(Y.shape[1], bool)
        for t in range(Y.shape[1]):
            m = M[:, t] > 0
            yt = Y[m, t]
            if m.sum() < 4 or yt.min() == yt.max():
                a, bb = _prior(Y[:, [t]], M[:, [t]])
                b[t], const[t] = float(_logit(a / bb)[0]), True
            else:
                W[:, t], b[t] = _fit_logistic(X[m], yt, lam)
        return W, b

    def fit(self, X, Y, M, groups=None):
        X, Y, M = np.asarray(X, float), np.asarray(Y, float), np.asarray(M, float)
        lam = self.lam
        if lam is None and groups is not None and len(set(np.asarray(groups).tolist())) >= 3:
            g = np.asarray(groups)
            best = None
            for L in self.LAMBDAS:
                loss = 0.0
                for b_ in sorted(set(g.tolist())):
                    tr, te = g != b_, g == b_
                    W, b = self._fit_all(X[tr], Y[tr], M[tr], L)
                    P = np.clip(_sigmoid(X[te] @ W + b), 1e-4, 1 - 1e-4)
                    loss += float((-(Y[te] * np.log(P) + (1 - Y[te]) * np.log(1 - P)) * M[te]).sum())
                if best is None or loss < best[0] - 1e-9:
                    best = (loss, L)
            lam = best[1]
        self.lam_ = float(lam if lam is not None else self.DEFAULT_LAMBDA)
        self.W, self.b = self._fit_all(X, Y, M, self.lam_)
        return self

    def predict_proba(self, X):
        return _sigmoid(np.atleast_2d(X) @ self.W + self.b), None

    def to_dict(self):
        return {"kind": "logistic", "lam": self.lam_, "W": self.W.tolist(), "b": self.b.tolist()}


class MLPModel:
    """Multi-task MLP: input -> hidden (ReLU) -> one sigmoid per tool, masked BCE, L2 weight decay, Adam full batch; an ensemble of
    `n_members` seeds whose std is the uncertainty. Sizes are deliberately tiny (hidden 16, ~150 training rows): ~1k weights."""
    name = "mlp_ensemble"

    def __init__(self, hidden: int = 16, epochs: int = 300, lr: float = 0.01, wd: float = 0.02, n_members: int = 5, seed: int = 0):
        self.hidden, self.epochs, self.lr, self.wd, self.n_members, self.seed = hidden, epochs, lr, wd, n_members, seed
        self.members: list[list[np.ndarray]] = []

    def _fit_one(self, X, Y, M, seed):
        rng = np.random.default_rng(seed)
        d, T, h = X.shape[1], Y.shape[1], self.hidden
        a, b = _prior(Y, M)
        P = [rng.normal(0, 1 / math.sqrt(d), (d, h)), np.zeros(h), rng.normal(0, 1 / math.sqrt(h), (h, T)), _logit(a / b)]
        m_ = [np.zeros_like(p) for p in P]
        v_ = [np.zeros_like(p) for p in P]
        denom = max(M.sum(), 1.0)
        for t in range(1, self.epochs + 1):
            W1, b1, W2, b2 = P
            H = np.maximum(X @ W1 + b1, 0)
            Pr = _sigmoid(H @ W2 + b2)
            dz = (Pr - Y) * M / denom
            gW2 = H.T @ dz + self.wd * W2
            gb2 = dz.sum(0)
            dH = (dz @ W2.T) * (H > 0)
            gW1 = X.T @ dH + self.wd * W1
            gb1 = dH.sum(0)
            for i, g in enumerate((gW1, gb1, gW2, gb2)):
                m_[i] = 0.9 * m_[i] + 0.1 * g
                v_[i] = 0.999 * v_[i] + 0.001 * g * g
                P[i] = P[i] - self.lr * (m_[i] / (1 - 0.9 ** t)) / (np.sqrt(v_[i] / (1 - 0.999 ** t)) + 1e-8)
        return P

    def fit(self, X, Y, M, groups=None):
        X, Y, M = np.asarray(X, float), np.asarray(Y, float), np.asarray(M, float)
        self.members = [self._fit_one(X, Y, M, self.seed + 1000 * i + 7) for i in range(self.n_members)]
        return self

    def predict_proba(self, X):
        X = np.atleast_2d(X)
        outs = np.stack([_sigmoid(np.maximum(X @ W1 + b1, 0) @ W2 + b2) for W1, b1, W2, b2 in self.members])
        return outs.mean(0), outs.std(0)

    def to_dict(self):
        return {"kind": "mlp", "members": [[p.tolist() for p in m] for m in self.members]}


def model_from_dict(d: dict):
    k = d["kind"]
    if k == "prior":
        m = PriorModel()
        m.p = np.array(d["p"])
    elif k == "knn":
        m = KNNModel(d["k"])
        m.X, m.Y, m.M, m.p = (np.array(d[q]) for q in ("X", "Y", "M", "p"))
    elif k == "logistic":
        m = LogisticModel()
        m.lam_, m.W, m.b = d["lam"], np.array(d["W"]), np.array(d["b"])
    elif k == "mlp":
        m = MLPModel()
        m.members = [[np.array(p) for p in mem] for mem in d["members"]]
    else:
        raise ValueError(f"unknown model kind {k!r}")
    return m


MODEL_FACTORIES = {"prior": PriorModel, "knn": KNNModel, "logistic": LogisticModel, "mlp_ensemble": MLPModel}


# ------------------------------------------------------------------------------------------------------------ runtime predictor
class RepairPredictor:
    """Trained on rows of the probe dataset (all of them, for runtime use); one model per setting. `advise` ranks the tools."""

    def __init__(self, model: str = "mlp_ensemble", tools: tuple[str, ...] = TOOLS, seed: int = 0):
        self.model_name, self.tools, self.seed = model, tuple(tools), seed
        self.prep: dict = {}
        self.models: dict = {}
        self.n_train = 0
        self.n_bases = 0
        self.heldout: dict = {}     # optional {"top1": .., "top3": .., "setting": ..}, set by the caller from a LOBO evaluation

    def fit(self, rows: list[dict], settings=SETTINGS) -> "RepairPredictor":
        Y, M = map(np.array, zip(*(targets(r["repair_matrix"], self.tools) for r in rows)))
        groups = [r.get("base_id", "") for r in rows]       # base ids are used ONLY to group the inner CV, never as features
        self.n_train, self.n_bases = len(rows), len(set(groups))
        for s in settings:
            Xraw = np.stack([build_features(r, s)[0] for r in rows])
            self.prep[s] = Preprocessor().fit(Xraw)
            kw = {"seed": self.seed} if self.model_name == "mlp_ensemble" else {}
            self.models[s] = MODEL_FACTORIES[self.model_name](**kw).fit(self.prep[s].transform(Xraw), Y, M, groups=groups)
        return self

    def advise(self, observation: dict, features: dict, cf_results: dict | None = None) -> list[dict]:
        setting = "obs+cf" if (cf_results and "obs+cf" in self.models) else "obs"
        row = {"observation": observation, "features": features, "counterfactuals": cf_results or {}}
        x, _ = build_features(row, setting)
        P, S = self.models[setting].predict_proba(self.prep[setting].transform(x))
        p, sp = P[0], (S[0] if S is not None else None)
        order = sorted(range(len(self.tools)), key=lambda i: (-p[i], self.tools[i]))
        return [{"tool": self.tools[i], "p_repair": round(float(p[i]), 3),
                 "uncertainty": None if sp is None else round(float(sp[i]), 3), "rank": r + 1, "setting": setting}
                for r, i in enumerate(order)]

    def advice_text(self, observation: dict, features: dict, cf_results: dict | None = None, heldout: dict | None = None,
                    top: int = 4) -> str:
        adv = self.advise(observation, features, cf_results)[:top]
        items = ", ".join(f"{a['tool']} {a['p_repair']:.2f}" + (f"+-{a['uncertainty']:.2f}" if a["uncertainty"] is not None else "")
                          for a in adv)
        ho = heldout or self.heldout
        acc = f" Held-out top-1 hit rate {ho['top1']:.2f} (leave-one-base-out)." if ho and ho.get("top1") is not None else ""
        text = (f"Learned advice (statistical prediction from {self.n_train} training instances of {self.n_bases} robots, "
                f"not a measurement): P(repair) {items}.{acc}")
        return text if len(text) <= 400 else text[:397] + "..."

    def save(self, path) -> None:
        d = {"version": VERSION, "model": self.model_name, "tools": list(self.tools), "seed": self.seed, "n_train": self.n_train,
             "n_bases": self.n_bases, "heldout": self.heldout,
             "prep": {s: p.to_dict() for s, p in self.prep.items()}, "models": {s: m.to_dict() for s, m in self.models.items()}}
        Path(path).write_text(json.dumps(d, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path) -> "RepairPredictor":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        p = cls(d["model"], tuple(d["tools"]), d["seed"])
        p.n_train, p.n_bases, p.heldout = d["n_train"], d["n_bases"], d.get("heldout", {})
        p.prep = {s: Preprocessor.from_dict(v) for s, v in d["prep"].items()}
        p.models = {s: model_from_dict(v) for s, v in d["models"].items()}
        return p
