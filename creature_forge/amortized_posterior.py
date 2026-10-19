"""Learned amortised posterior over hidden deviations (phase 3, Stage 2; arm A2, and a tool of the agent).

Trained on SIMULATED failures of development robots (`scripts/hdb_amortized.py`): random deviations of the development
mechanism structures (held-out primitives excluded), plus a generic tolerance nuisance (`belief_engine.TOLERANCE`, independent of
the bench's sealed reality-gap generator), measured with the policy-visible instruments. Inputs are differences from the nominal
design simulated on the SAME seeds:
- observe, 4 trials;
- optional floor test x3 and weigh test.
Differencing makes them comparable across morphologies.

Model (numpy only, deterministic):
- multinomial logistic regression over structures;
- per-structure ridge regression of the log-magnitude parameters;
- a Mahalanobis out-of-distribution score, so an unfamiliar failure is flagged instead of being forced into a known class.

At use time it proposes hypotheses (particles) to the belief engine. The data still decide their weight.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import belief_engine as be
from . import hidden_plant as hp

VERSION = "amortized_posterior_v1"
OBS_FEATURES = tuple(be.FEATURES)
# the development mechanism structures (hdb_bench.FAMILY_SPECS); held-out primitives (sensor_delay, joint_damping, shank length)
# are deliberately absent
CLASSES = (("sensor_bias", "pitch"), ("payload", "torso"), ("contact_friction", "feet"), ("segment_length", "feet"),
           ("gain_scale", "balance_feedback"), ("actuator_strength", "all"), ("actuator_strength", "left"),
           ("actuator_strength", "right"), ("clock_scale", "clock"), ("torso_mass", "torso"))


def _med(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    return v[len(v) // 2] if len(v) % 2 else 0.5 * (v[len(v) // 2 - 1] + v[len(v) // 2])


def panel(features_by_seed: dict) -> dict:
    """Median of each feature over seeds + walking fraction."""
    out = {k: _med([f.get(k) for f in features_by_seed.values()]) for k in OBS_FEATURES}
    out["walking"] = sum(1 for f in features_by_seed.values() if f.get("walking")) / max(1, len(features_by_seed))
    return out


def vectorize(obs: dict, nom: dict, floor: dict | None = None, nom_floor: dict | None = None, weigh: dict | None = None,
              nom_weigh: dict | None = None, *, full: bool) -> np.ndarray:
    """Feature vector: (plant - nominal) per panel feature, with undefined -> 0 plus an 'undefined' indicator."""
    def block(a, b):
        x = []
        for k in OBS_FEATURES:
            va, vb = a.get(k), b.get(k)
            if va is None or vb is None:
                x += [0.0, 1.0]
            else:
                x += [float(va) - float(vb), 0.0]
        return x
    x = block(obs, nom)
    if full:
        x += block(floor or {}, nom_floor or {})
        if weigh and nom_weigh:
            x += [weigh["mass_kg"] / nom_weigh["mass_kg"] - 1.0, weigh["com_x_m"] - nom_weigh["com_x_m"]]
        else:
            x += [0.0, 0.0]
    return np.asarray(x, float)


def class_params(kind: str) -> tuple[str, ...]:
    return ("mass_kg", "x_m") if kind == "payload" else tuple(hp.PRIMITIVES[kind]["params"])


def encode_params(prim: dict, design_mass: float) -> list[float]:
    """Regression targets: log factor / signed magnitude, payload as (mass fraction log, x)."""
    k, p = prim["kind"], prim["params"]
    if k == "payload":
        return [math.log(max(1e-4, p["mass_kg"] / design_mass)), p["x_m"]]
    if k == "sensor_bias":
        return [p["rad"]]
    (v,) = p.values()
    return [math.log(max(1e-6, v))]


def decode_params(kind: str, target: str, y: list[float], design_mass: float) -> dict | None:
    if kind == "payload":
        prim = {"kind": kind, "target": target, "params": {"mass_kg": float(min(15.0, max(0.0, math.exp(y[0]) * design_mass))),
                                                         "x_m": float(min(0.3, max(-0.3, y[1])))}}
    elif kind == "sensor_bias":
        prim = {"kind": kind, "target": target, "params": {"rad": float(y[0])}}
    else:
        (name,) = hp.PRIMITIVES[kind]["params"]
        prim = {"kind": kind, "target": target, "params": {name: float(math.exp(y[0]))}}
    try:
        return hp.validate_deviation([prim])[0]
    except hp.DeviationError:
        return None


# ---------------------------------------------------------------------------------------------------------- training
def fit_softmax(X: np.ndarray, y: np.ndarray, k: int, l2: float = 1e-2, iters: int = 3000, lr: float = 0.5) -> np.ndarray:
    """Multinomial logistic regression by full-batch gradient descent (deterministic)."""
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    W = np.zeros((d + 1, k))
    Y = np.eye(k)[y]
    for _ in range(iters):
        Z = Xb @ W
        Z -= Z.max(1, keepdims=True)
        P = np.exp(Z)
        P /= P.sum(1, keepdims=True)
        G = Xb.T @ (P - Y) / n + l2 * np.vstack([W[:-1], np.zeros((1, k))])
        W -= lr * G
    return W


def softmax_proba(W: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    Z = Xb @ W
    Z -= Z.max(1, keepdims=True)
    P = np.exp(Z)
    return P / P.sum(1, keepdims=True)


def fit_ridge(X: np.ndarray, Y: np.ndarray, l2: float = 1.0) -> np.ndarray:
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    reg = l2 * np.eye(Xb.shape[1])
    reg[-1, -1] = 0.0
    return np.linalg.solve(Xb.T @ Xb + reg, Xb.T @ Y)


def train(rows: list[dict], *, full: bool) -> dict:
    """rows: {x_obs, x_full, cls, y, base_id}. Returns a JSON-able model."""
    key = "x_full" if full else "x_obs"
    X = np.asarray([r[key] for r in rows], float)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    y = np.asarray([r["cls"] for r in rows], int)
    W = fit_softmax(Z, y, len(CLASSES))
    reg = {}
    for c in range(len(CLASSES)):
        m = y == c
        if m.sum() >= 5:
            reg[str(c)] = fit_ridge(Z[m], np.asarray([rows[i]["y"] for i in np.flatnonzero(m)], float)).tolist()
    cov = np.cov(Z.T) + 1e-3 * np.eye(Z.shape[1])
    icov = np.linalg.inv(cov)
    d2 = np.einsum("ij,jk,ik->i", Z, icov, Z)
    return {"version": VERSION, "full": full, "classes": [list(c) for c in CLASSES], "mu": mu.tolist(), "sd": sd.tolist(),
            "W": W.tolist(), "reg": reg, "icov": icov.tolist(), "ood_q99": float(np.quantile(d2, 0.99)),
            "n_train": len(rows), "bases": sorted({r["base_id"] for r in rows})}


def cross_validate(rows: list[dict], *, full: bool, folds: int = 5) -> dict:
    """Leave-bases-out cross-validation: structure top-1/top-3 accuracy, log loss, parameter error."""
    bases = sorted({r["base_id"] for r in rows})
    top1 = top3 = 0
    ll = 0.0
    n = 0
    for f in range(folds):
        test_b = set(bases[f::folds])
        tr = [r for r in rows if r["base_id"] not in test_b]
        te = [r for r in rows if r["base_id"] in test_b]
        if not tr or not te:
            continue
        m = train(tr, full=full)
        P = predict_proba(m, np.asarray([r["x_full" if full else "x_obs"] for r in te], float))
        for r, p in zip(te, P):
            order = np.argsort(-p)
            top1 += order[0] == r["cls"]
            top3 += r["cls"] in order[:3]
            ll -= math.log(max(1e-9, p[r["cls"]]))
            n += 1
    return {"n": n, "top1": round(top1 / n, 3), "top3": round(top3 / n, 3), "log_loss": round(ll / n, 3),
            "chance_log_loss": round(math.log(len(CLASSES)), 3)}


def predict_proba(model: dict, X: np.ndarray) -> np.ndarray:
    Z = (X - np.asarray(model["mu"])) / np.asarray(model["sd"])
    return softmax_proba(np.asarray(model["W"]), Z)


# ---------------------------------------------------------------------------------------------------------- use
class LearnedPosterior:
    def __init__(self, models: dict):
        self.models = models          # {"obs": model, "full": model}

    @classmethod
    def load(cls, path: str | Path) -> "LearnedPosterior":
        return cls(json.loads(Path(path).read_text("utf-8")))

    def _inputs(self, ep: be.Episode):
        """Plant panels from the episode's experiments and nominal-twin panels on the same seeds (twin-charged)."""
        b = ep.b
        design = {"body": ep.design0["body"], "vector": ep.design0["vector"]}
        exp0 = ep.experiments[0]
        nom = b.twin_observe([], design, role="obs", n=len(exp0["features"]), tag="learned:nominal")
        if nom is None:
            return None
        obs, nomp = panel(exp0["features"]), panel(be.obs_features(nom))
        floor = next((e for e in ep.experiments if e["kind"] == "floor" and abs(e.get("friction_mult", 0) - 3.0) < 1e-9), None)
        weigh = next((e for e in ep.experiments if e["kind"] == "weigh"), None)
        if floor is not None and weigh is not None:
            nf = b.twin_observe([], design, role="obs", n=len(floor["features"]), friction_mult=3.0, tag="learned:nominal_floor")
            if nf is not None:
                nw = b.twin_weigh([], design)
                return vectorize(obs, nomp, panel(floor["features"]), panel(be.obs_features(nf)), weigh["measured"], nw,
                                 full=True), "full"
        return vectorize(obs, nomp, full=False), "obs"

    def posterior(self, ep: be.Episode) -> dict | None:
        got = self._inputs(ep)
        if got is None:
            return None
        x, which = got
        m = self.models[which]
        Z = (x - np.asarray(m["mu"])) / np.asarray(m["sd"])
        p = softmax_proba(np.asarray(m["W"]), Z[None, :])[0]
        d2 = float(Z @ np.asarray(m["icov"]) @ Z)
        return {"model": which, "proba": p.tolist(), "z": Z, "ood": d2 > m["ood_q99"], "d2": d2, "q99": m["ood_q99"]}

    def suggest(self, ep: be.Episode, k: int = 3) -> list[tuple[list[dict], float]]:
        """Top-k structures with regressed magnitudes (each at the estimate and x0.6 / x1.6 around it)."""
        post = self.posterior(ep)
        if post is None:
            return []
        m = self.models[post["model"]]
        out = []
        for c in np.argsort(-np.asarray(post["proba"]))[:k]:
            kind, target = CLASSES[int(c)]
            W = m["reg"].get(str(int(c)))
            if W is None:
                continue
            y = (np.append(post["z"], 1.0) @ np.asarray(W)).tolist()
            y = y if isinstance(y, list) else [y]
            for shift in (0.0, math.log(0.6), math.log(1.6)):
                yy = list(y)
                if kind == "sensor_bias":
                    yy[0] = y[0] * math.exp(shift)
                else:
                    yy[0] = y[0] + shift
                prim = decode_params(kind, target, yy, ep.design_mass)
                if prim is not None:
                    out.append(([prim], float(post["proba"][int(c)])))
        self.last = {k_: v for k_, v in post.items() if k_ != "z"}
        return out
