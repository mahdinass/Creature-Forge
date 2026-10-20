"""Repair learning (phase 3, DS-1; docs/DS1_PROTOCOL.md §2): the R-head, P(verified FULL | tool, situation).

The engine's twin screen ranks repair tools by short simulator optimisations under the belief; in Stage 2 it tied on about a
quarter of instances and the tool decided the outcome. The R-head learns from VERIFIED outcomes of past repairs which tools
work under which beliefs, as a correction of the engine's own evidence (never a replacement): its features are
  * the engine's structure posterior aggregated by deviation kind (agent-visible), its entropy and leading mass,
  * the engine's tool-screen evidence for the tool (probe score and rank, ensemble twin-CMA walking and rank, or missing),
  * the procedure that produced the outcome row (engine final / older engine / A0 / diverse); "engine_final" at decision time.
Injected mechanisms and families are never features (they score the model offline only).

Model: L2-logistic (lambda fixed a priori). Baselines: B1 (engine evidence + procedure only), B2 (tool rates). The same
`situation_features` / `tool_evidence` functions serve offline rows and live episodes, so training and use cannot drift.
"""
from __future__ import annotations

import json
import math

import numpy as np

VERSION = "repair_learning_v1"
TOOLS = ("posture", "timing", "feedback", "stride", "placement", "foot_length", "torso_mass", "torque_limit", "foot_friction",
         "leg_length")
KINDS = ("segment_length", "actuator_strength", "joint_damping", "torso_mass", "payload", "contact_friction", "gain_scale",
         "sensor_delay", "sensor_bias", "clock_scale")
PROCEDURES = ("engine_final", "engine_old", "a0", "diverse")
LAMBDA = 1.0


def situation_features(structures: list) -> dict:
    """structures: [(structure, weight)] with structure = [(kind, target), ...] (v6's 'unmodelled' reserve is ignored)."""
    kw = {k: 0.0 for k in KINDS}
    ws = []
    for st, w in structures:
        st = [tuple(x) for x in st]
        if not st or st[0][0] == "unmodelled":
            continue
        ws.append(float(w))
        for kind, _ in st:
            if kind in kw:
                kw[kind] += float(w)
    tot = sum(ws) or 1.0
    ent = -sum((w / tot) * math.log(w / tot) for w in ws if w > 0)
    return {"kind_w": [kw[k] / tot for k in KINDS], "entropy": ent, "lead": (max(ws) / tot) if ws else 0.0}


def tool_evidence(probe_ranking: list | None, cma_ranking: list | None) -> dict:
    """Per-tool engine evidence from the twin screens: {tool: [has_probe, probe_score, probe_rank_frac, has_cma, cma_walk/4,
    cma_rank_frac]}."""
    out = {t: [0.0, 0.0, 1.0, 0.0, 0.0, 1.0] for t in TOOLS}
    pr = [r for r in (probe_ranking or []) if r.get("tool") in out]
    for i, r in enumerate(pr):
        out[r["tool"]][0:3] = [1.0, float(r.get("score") or 0.0), i / max(1, len(pr) - 1)]
    cr = [r for r in (cma_ranking or []) if r.get("tool") in out and r.get("cma_walking") is not None]
    for i, r in enumerate(cr):
        out[r["tool"]][3:6] = [1.0, float(r["cma_walking"]) / 4.0, i / max(1, len(cr) - 1)]
    return out


def featurize(sit: dict, ev: list, tool: str, procedure: str, kind: str = "full") -> np.ndarray:
    """kind: full (R-head) | b1 (engine evidence + procedure) | b2 (tool one-hot + procedure)."""
    t = np.zeros(len(TOOLS))
    t[TOOLS.index(tool)] = 1.0
    proc = np.zeros(len(PROCEDURES))
    proc[PROCEDURES.index(procedure)] = 1.0
    parts = [np.ones(1)]
    if kind in ("full", "b2"):
        parts.append(t)
    if kind in ("full", "b1"):
        parts.append(np.asarray(ev, dtype=float))
    if kind == "full":
        parts.append(np.outer(np.asarray(sit["kind_w"]), t).ravel())
        parts.append(np.array([sit["entropy"], sit["lead"]]))
    parts.append(proc)
    return np.concatenate(parts)


def fit_logistic(X: np.ndarray, y: np.ndarray, lam: float = LAMBDA, iters: int = 60) -> np.ndarray:
    """L2-penalised logistic regression by Newton steps (bias unpenalised)."""
    w = np.zeros(X.shape[1])
    pen = np.full(X.shape[1], lam)
    pen[0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(X @ w)))
        g = X.T @ (p - y) + pen * w
        H = (X * (p * (1 - p))[:, None]).T @ X + np.diag(pen + 1e-9)
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


def predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(X @ w)))


class RHead:
    """A fitted R-head (or baseline) usable as the engine's tool ranker (belief_engine.Episode.robust_repair(ranker=...))."""

    def __init__(self, w, kind: str = "full", meta: dict | None = None):
        self.w, self.kind, self.meta = np.asarray(w, dtype=float), kind, dict(meta or {})
        self.last: list[dict] = []

    @classmethod
    def fit(cls, rows: list[dict], kind: str = "full", lam: float = LAMBDA, meta: dict | None = None) -> "RHead":
        X = np.array([featurize(r["sit"], r["ev"], r["tool"], r["procedure"], kind) for r in rows])
        y = np.array([float(r["full"]) for r in rows])
        return cls(fit_logistic(X, y, lam), kind, {**(meta or {}), "n_rows": len(rows), "lambda": lam})

    def p(self, sit: dict, evid: dict, tool: str, procedure: str = "engine_final") -> float:
        return float(predict(self.w, featurize(sit, evid[tool], tool, procedure, self.kind)[None, :])[0])

    def save(self, path: str) -> None:
        json.dump({"version": VERSION, "kind": self.kind, "w": self.w.tolist(), "meta": self.meta,
                   "tools": TOOLS, "kinds": KINDS, "procedures": PROCEDURES}, open(path, "w", encoding="utf-8"), indent=1)

    @classmethod
    def load(cls, path: str) -> "RHead":
        d = json.load(open(path, encoding="utf-8"))
        if tuple(d["tools"]) != TOOLS or tuple(d["kinds"]) != KINDS or tuple(d["procedures"]) != PROCEDURES:
            raise ValueError("R-head file was fitted with a different feature layout")
        return cls(d["w"], d["kind"], d.get("meta"))

    def scores(self, structures: list, probe_ranking: list | None, cma_ranking: list | None) -> dict:
        sit = situation_features(structures)
        evid = tool_evidence(probe_ranking, cma_ranking)
        return {t: self.p(sit, evid, t) for t in TOOLS}

    def __call__(self, ep, hyps, ranking: list[dict]) -> list[dict]:
        """Engine ranker hook: reorder the screened tools by predicted P(FULL) (ties keep the engine's order)."""
        probe = next((e["ranking"] for e in reversed(ep.events) if e["kind"] == "tool_screen"), None)
        cma = [r for r in ranking if r.get("cma_walking") is not None] or None
        sc = self.scores(ep.structure_posterior(), probe, cma)
        order = sorted(range(len(ranking)), key=lambda i: (-sc.get(ranking[i]["tool"], 0.0), i))
        out = [dict(ranking[i], rhead_p=round(sc.get(ranking[i]["tool"], 0.0), 4)) for i in order]
        self.last = [{"tool": r["tool"], "p": r["rhead_p"]} for r in out]
        ep._event("rhead_order", engine_order=[r["tool"] for r in ranking], rhead_order=[r["tool"] for r in out],
                  p={r["tool"]: r["rhead_p"] for r in out})
        return out
