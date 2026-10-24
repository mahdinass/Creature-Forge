"""RL-1 repair memory (docs/RL1_PLAN.md §4): learn which repair tool works for a diagnosed failure from verified successes
AND failures, and decide when a past repair applies.

Inputs are policy-visible only:
- the engine's diagnosis record (posterior over structures, the observation of the faulty robot);
- the twin evidence per tool (probe score, short twin-CMA walking and fitness);
- the nominal design's morphology and actuator constraints.
Outcomes come from the dev repair response matrix (every tool tried on every training instance, so there are no
missing-not-at-random rows). Mechanism or family labels are never features.

Model (numpy only, deterministic):
- memory evidence: kernel-weighted Beta-Binomial success rate of each tool among past instances in a standardised physics
  context space, with its effective support n_eff and the nearest-case distance;
- calibrator: per-row logistic regression (instance x tool) on [twin evidence, memory logit, log n_eff, tool prior];
- decision: rank tools by calibrated P(success). Abstain to the engine's own order when the memory has no support; hedge
  (one slot to each source's top tool) when memory and twin disagree and the memory is not confident.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "repair_memory_v1"
TOOLS = ("posture", "timing", "feedback", "stride", "placement", "foot_length", "torso_mass", "torque_limit",
         "foot_friction", "leg_length")
OBS_SCALES = {"walking": 0.35, "time_upright": 1.5, "fall_direction": 0.7, "pitch_mean": 0.04, "com_vx_mean": 0.08,
              "step_freq_hz": 0.4, "step_length_over_L": 0.03, "slip_fraction": 0.03, "double_support_fraction": 0.05,
              "capture_margin_over_L_mean": 0.02, "saturation_frac_hip": 0.05, "saturation_frac_knee": 0.05,
              "saturation_frac_ankle": 0.1, "friction_utilisation_p95": 0.12}      # = belief_engine.FEATURES
KINDS = ("segment_length", "actuator_strength", "joint_damping", "torso_mass", "payload", "contact_friction", "gain_scale",
         "sensor_delay", "sensor_bias", "clock_scale")
MORPH = ("thigh_length", "shank_length", "foot_length", "torso_mass", "torque_limit", "leg_density", "foot_friction")


# ------------------------------------------------------------------------------------------------------------ features
def _nanmean(xs):
    v = [x for x in xs if x is not None and isinstance(x, (int, float)) and math.isfinite(x)]
    return sum(v) / len(v) if v else 0.0


def context(rec: dict, nominal_body: dict) -> dict:
    """Policy-visible context of one episode (an A1-style engine record + the nominal design)."""
    eng = rec["engine"]
    obs = next(x for x in eng["experiments"] if x["kind"] == "observe")["features"]
    o = {k: _nanmean([s.get(k) for s in obs.values()]) / sc for k, sc in OBS_SCALES.items()}
    top = eng["history"][-1]["top"]
    parts = {p["pid"]: p for p in eng["particles"]}
    kinds = {k: 0.0 for k in KINDS}
    for t in top:
        p = parts.get(t["pid"])
        for kind, _target in (p["structure"] if p else []):
            if kind in kinds:
                kinds[kind] += float(t["w"])
    w = [float(t["w"]) for t in top if t["w"] > 0]
    ent = -sum(x * math.log(x) for x in w) if w else 0.0
    m = {k: math.log(max(float(nominal_body[k]), 1e-6)) for k in MORPH}
    return {"obs": o, "kinds": kinds, "entropy": ent, "map_mass": float(top[0]["w"]) if top else 0.0, "morph": m}


def twin_evidence(rec: dict) -> dict:
    """tool -> {probe, cma_walking, cma_fitness, screened, rank} from the engine's tool screens (rank: the order the engine
    would repair in)."""
    ev = {t: {"probe": None, "cma_walking": None, "cma_fitness": None, "screened": 0.0, "rank": len(TOOLS)} for t in TOOLS}
    screen = next((e for e in rec["engine"]["events"] if e["kind"] == "tool_screen"), None)
    cma = next((e for e in rec["engine"]["events"] if e["kind"] == "tool_screen_cma"), None)
    order = [r["tool"] for r in (cma or screen or {"ranking": []})["ranking"]]
    if cma and screen:
        order += [r["tool"] for r in screen["ranking"] if r["tool"] not in order]
    for r in (screen or {"ranking": []})["ranking"]:
        ev[r["tool"]]["probe"] = float(r["score"])
    for r in (cma or {"ranking": []})["ranking"]:
        ev[r["tool"]].update(cma_walking=float(r["cma_walking"]), cma_fitness=float(r["cma_fitness"]), screened=1.0)
    for i, t in enumerate(order):
        ev[t]["rank"] = i
    return ev


def engine_order(rec: dict) -> list[str]:
    ev = twin_evidence(rec)
    return sorted(TOOLS, key=lambda t: (ev[t]["rank"], TOOLS.index(t)))


def ctx_vector(c: dict) -> np.ndarray:
    return np.array([c["obs"][k] for k in OBS_SCALES] + [c["kinds"][k] for k in KINDS] + [c["entropy"], c["map_mass"]]
                    + [c["morph"][k] for k in MORPH], dtype=float)


# ------------------------------------------------------------------------------------------------------------ memory
class Memory:
    """Kernel-weighted per-tool outcome memory over standardised contexts. `y[i, t]` = 1 if tool t verified on case i."""

    def __init__(self, X: np.ndarray, Y: np.ndarray, *, bandwidth: float = 1.0, prior_strength: float = 2.0):
        self.mu = X.mean(axis=0)
        sd = X.std(axis=0)
        self.sd = np.where(sd > 1e-9, sd, 1.0)
        self.Z = (X - self.mu) / self.sd
        self.Y = Y.astype(float)
        self.h = float(bandwidth)
        self.base = (self.Y.sum(axis=0) + 0.5) / (len(self.Y) + 1.0)      # population rate per tool (Jeffreys-like)
        self.a = float(prior_strength)

    def query(self, x: np.ndarray) -> dict:
        z = (x - self.mu) / self.sd
        d = np.sqrt(((self.Z - z) ** 2).mean(axis=1))                      # RMS standardised distance
        w = np.exp(-0.5 * (d / self.h) ** 2)
        n_eff = float(w.sum())
        rate = (w @ self.Y + self.a * self.base) / (n_eff + self.a)
        return {"rate": rate, "n_eff": n_eff, "d_min": float(d.min()), "d_med": float(np.median(d))}


def simple_memory_order(mem_X: np.ndarray, mem_Y: np.ndarray, x: np.ndarray, eng: list[str], k: int = 5) -> list[str]:
    """P-mem0: the tools that most often verified on the k nearest past cases (raw standardised context), engine order breaks
    ties."""
    mu, sd = mem_X.mean(axis=0), mem_X.std(axis=0)
    sd = np.where(sd > 1e-9, sd, 1.0)
    d = np.sqrt((((mem_X - mu) / sd - (x - mu) / sd) ** 2).mean(axis=1))
    nn = np.argsort(d, kind="stable")[:k]
    cnt = mem_Y[nn].sum(axis=0)
    return sorted(TOOLS, key=lambda t: (-cnt[TOOLS.index(t)], eng.index(t)))


# ------------------------------------------------------------------------------------------------------------ calibrator
def _logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def row_features(tev: dict, q: dict, t: str) -> list[float]:
    e = tev[t]
    i = TOOLS.index(t)
    return [1.0,
            (e["probe"] if e["probe"] is not None else 0.0), 1.0 if e["probe"] is None else 0.0,
            (e["cma_walking"] / 4.0 if e["cma_walking"] is not None else 0.0), e["screened"],
            1.0 / (1.0 + e["rank"]),
            _logit(float(q["rate"][i])), math.log1p(q["n_eff"]), q["d_min"]]


def fit_logistic(F: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 200) -> np.ndarray:
    """L2-regularised logistic regression by Newton steps (intercept unpenalised). Deterministic."""
    w = np.zeros(F.shape[1])
    R = np.eye(F.shape[1]) * l2
    R[0, 0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(F @ w)))
        g = F.T @ (p - y) + R @ w
        H = F.T @ (F * (p * (1 - p))[:, None]) + R + 1e-9 * np.eye(F.shape[1])
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def predict(w: np.ndarray, f: list[float]) -> float:
    return float(1 / (1 + math.exp(-float(np.dot(w, f)))))


# ------------------------------------------------------------------------------------------------------------ decision
def decide(P: dict, eng: list[str], n_eff: float, *, n_min: float, hedge_delta: float) -> dict:
    """Tool order from calibrated P(success) per tool.
    - abstain (engine order) when the memory has too little support (n_eff < n_min);
    - commit to the P ranking when its top tool clearly beats the engine's top tool (P gap >= hedge_delta) or agrees;
    - otherwise hedge: slot 1 = the P top tool, slot 2 = the engine's top tool (two independent sources of evidence)."""
    ranked = sorted(TOOLS, key=lambda t: (-P[t], eng.index(t)))
    if n_eff < n_min:
        return {"order": list(eng), "mode": "abstain"}
    top, etop = ranked[0], eng[0]
    if top == etop or P[top] - P[etop] >= hedge_delta:
        return {"order": ranked, "mode": "commit"}
    order = [top, etop] + [t for t in ranked if t not in (top, etop)]
    return {"order": order, "mode": "hedge"}


# ------------------------------------------------------------------------------------------------------------ fit / apply
def crossfit_queries(X: np.ndarray, Y: np.ndarray, groups: list, h: float) -> list[dict]:
    """Memory query for every training case from a Memory without the case's own group (leave-one-group-out), so the
    calibrator learns how much to trust memory evidence on cases the memory has not seen."""
    out: list = [None] * len(X)
    for g in sorted(set(groups)):
        tr = [i for i, gg in enumerate(groups) if gg != g]
        mem = Memory(X[tr], Y[tr], bandwidth=h)
        for i, gg in enumerate(groups):
            if gg == g:
                out[i] = mem.query(X[i])
    return out


def fit(X: np.ndarray, Y: np.ndarray, tevs: list[dict], groups: list, *, h: float, n_min: float, delta: float,
        l2: float = 1.0) -> dict:
    """Train a repair-memory model (JSON-serialisable). `groups`: the grouping used for cross-fitting (dev family)."""
    q = crossfit_queries(X, Y, groups, h)
    F = [row_features(tevs[i], q[i], t) for i in range(len(X)) for t in TOOLS]
    y = [Y[i, TOOLS.index(t)] for i in range(len(X)) for t in TOOLS]
    w = fit_logistic(np.array(F), np.array(y), l2=l2)
    return {"version": VERSION, "X": X.tolist(), "Y": Y.tolist(), "h": h, "n_min": n_min, "delta": delta, "l2": l2,
            "w": w.tolist(), "n_cases": int(len(X))}


def apply(model: dict, rec: dict, nominal_body: dict) -> dict:
    """Decision for one episode at repair time: {"order", "mode", "P", "n_eff", "d_min"}."""
    mem = Memory(np.array(model["X"]), np.array(model["Y"]), bandwidth=model["h"])
    x = ctx_vector(context(rec, nominal_body))
    q = mem.query(x)
    tev = twin_evidence(rec)
    w = np.array(model["w"])
    P = {t: predict(w, row_features(tev, q, t)) for t in TOOLS}
    dec = decide(P, engine_order(rec), q["n_eff"], n_min=model["n_min"], hedge_delta=model["delta"])
    return {**dec, "P": P, "n_eff": q["n_eff"], "d_min": q["d_min"]}


def apply_simple(model: dict, rec: dict, nominal_body: dict, k: int = 5) -> dict:
    """P-mem0 decision (the simple memory baseline) from the same training cases."""
    x = ctx_vector(context(rec, nominal_body))
    order = simple_memory_order(np.array(model["X"]), np.array(model["Y"]), x, engine_order(rec), k=k)
    return {"order": order, "mode": "simple"}
