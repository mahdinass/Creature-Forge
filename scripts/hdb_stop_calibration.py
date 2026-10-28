"""Stopping-rule calibration (phase 3, dev only): map policy-visible robustness evidence to P(full_recovery_v1).

Build: for candidate designs taken from dev episode records (VS / MKV runs: initial, counterfactual, twin and repair designs)
measure on the hidden plant everything a policy could see before concluding, and the hidden truth:
  train4 / train8     walking on the first 4 / 8 train seeds (10 s)
  robust8 / robust16  walking on the first 8 / 16 robust seeds (10 s)
  stress4             walking on 4 obs seeds for 20 s
  twin8               twin walking under the episode's MAP hypothesis on 8 twin seeds (gap-free; the engine's own forecast)
  label               full_recovery_v1 == FULL_RECOVERY (hidden verification on validate/confirm seeds)
Analyse: base-clustered cross-validated logistic mapping vs the naive Beta reading of the robustness check
(P[p >= 0.8 | Beta(1 + k, 1 + n - k)]); Brier, log loss, ECE (10 bins), AUROC. Test data are never used.

Usage (VM): python scripts/hdb_stop_calibration.py build --episodes artifacts/hdb/vs_a1.jsonl,artifacts/hdb/mkv_dev.jsonl
                --workers 6 --out artifacts/hdb/stopcal.jsonl
            python scripts/hdb_stop_calibration.py analyse artifacts/hdb/stopcal.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                                # noqa: E402

from creature_forge import fault_bench as fb                      # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge import hidden_plant as hp                     # noqa: E402
from creature_forge.forge_pool import ForgePool                   # noqa: E402

FEATURES = ("train4", "train8", "robust8", "robust16", "stress4", "twin8")
PASS = 0.8


def _walk(plant, design, seeds, duration=10.0) -> int:
    rows = hp.walk_seeds(plant, design["body"], design["vector"], seeds, duration=duration)
    return int(sum(1 for r in rows if r.get("ok") and r["walking"]))


def measure(job) -> dict:
    inst, design, map_dev, meta = job
    s = inst["seeds"]
    ev = {"train4": _walk(inst["plant"], design, s["train"][:4]), "train8": _walk(inst["plant"], design, s["train"][:8]),
          "robust16": None, "stress4": _walk(inst["plant"], design, s["obs"][:4], duration=20.0)}
    rows = hp.walk_seeds(inst["plant"], design["body"], design["vector"], s["robust"][:16])
    w = [1 if r.get("ok") and r["walking"] else 0 for r in rows]
    ev["robust8"], ev["robust16"] = int(sum(w[:8])), int(sum(w))
    # forward progress on the same robust seeds, candidate and faulty nominal design (verdict_v1 compares displacement)
    base = hp.walk_seeds(inst["plant"], inst["robot"]["body"], inst["robot"]["vector"], s["robust"][:16])
    disp = lambda rr: [float(r.get("forward_disp_upright") or 0.0) if r.get("ok") else 0.0 for r in rr]  # noqa: E731
    ev["disp16_median"] = float(np.median(disp(rows)))
    ev["disp16_faulty_median"] = float(np.median(disp(base)))
    ev["disp16_paired_gain_median"] = float(np.median(np.array(disp(rows)) - np.array(disp(base))))
    ev["twin8"] = _walk({"deviation": map_dev}, design, s["twin"][:8]) if map_dev is not None else None
    ver = hb.verify(inst, design)
    return {**meta, **ev, "status": ver["status"], "label": int(ver["status"] == "FULL_RECOVERY")}


def build(a) -> None:
    bases = {b["base_id"]: b for b in hb.load_bases("dev")}
    th = json.load(open(a.thresholds, encoding="utf-8")) if a.thresholds else None
    jobs, seen = [], set()
    for path in a.episodes.split(","):
        for line in open(path, encoding="utf-8"):
            rec = json.loads(line)
            if not rec.get("designs"):
                continue
            base_id, fam, sev = rec["instance_id"].rsplit(":", 2)
            inst = (hb.make_instance_v2(bases[base_id], fam, int(sev), th) if rec.get("bench") == "hdb_v2"
                    else hb.make_instance(bases[base_id], fam, int(sev)))
            if inst is None:
                continue
            parts = ((rec.get("engine") or {}).get("particles")) or (((rec.get("info") or {}).get("engine") or {}).get("particles")) or []
            map_dev = parts[0]["deviation"] if parts else None
            cf_kept = 0
            for d in rec["designs"]:
                src = d["source"]
                if src.startswith("counterfactual:"):
                    cf_kept += 1
                    if cf_kept > 2:
                        continue
                key = (rec["instance_id"], json.dumps([d["body"], d["vector"]], sort_keys=True))
                if key in seen:
                    continue
                seen.add(key)
                meta = {"instance_id": rec["instance_id"], "base_id": base_id, "family": fam, "severity": int(sev),
                        "source": src, "origin": os.path.basename(path), "condition": rec.get("condition")}
                jobs.append((inst, {"body": d["body"], "vector": d["vector"]}, map_dev, meta))
    done = set()
    if os.path.exists(a.out):
        done = {(r["instance_id"], r["source"], r.get("condition")) for r in map(json.loads, open(a.out, encoding="utf-8"))}
    jobs = [j for j in jobs if (j[3]["instance_id"], j[3]["source"], j[3]["condition"]) not in done]
    print(f"{len(jobs)} designs to measure", flush=True)
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "a", encoding="utf-8") as out:
        for _, r in pool.imap(measure, jobs):
            if isinstance(r, tuple):
                print("ERROR", r, flush=True)
                continue
            out.write(json.dumps(r) + "\n")
            out.flush()


# ------------------------------------------------------------------ analysis
def beta_pass(k: int, n: int, thr: float = PASS, grid: int = 2000) -> float:
    x = (np.arange(grid) + 0.5) / grid
    logp = k * np.log(x) + (n - k) * np.log1p(-x)
    p = np.exp(logp - logp.max())
    return float(p[x >= thr].sum() / p.sum())


def design_matrix(rows, feats) -> np.ndarray:
    cols = []
    for f in feats:
        n = {"train4": 4, "train8": 8, "robust8": 8, "robust16": 16, "stress4": 4, "twin8": 8}[f]
        v = np.array([(r[f] if r.get(f) is not None else np.nan) for r in rows], float)
        frac = np.where(np.isnan(v), 0.5, v / n)
        cols.append(np.log((frac * n + 0.5) / ((1 - frac) * n + 0.5)))      # empirical logit
        if f == "twin8":
            cols.append(np.isnan(v).astype(float))
    return np.column_stack([np.ones(len(rows))] + cols)


def fit_logistic(X, y, lam=1.0, iters=200) -> np.ndarray:
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        g = X.T @ (p - y) + lam * np.r_[0, w[1:]]
        H = X.T @ (X * (p * (1 - p))[:, None]) + lam * np.diag(np.r_[0, np.ones(len(w) - 1)])
        step = np.linalg.solve(H + 1e-9 * np.eye(len(w)), g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def metrics(p, y) -> dict:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, float)
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(abs(p[bins == b].mean() - y[bins == b].mean()) * (bins == b).mean() for b in range(10) if (bins == b).any())
    pos, neg = p[y == 1], p[y == 0]
    auroc = float(np.mean([(a > b) + 0.5 * (a == b) for a in pos for b in neg])) if len(pos) and len(neg) else None
    return {"n": int(len(y)), "base_rate": round(float(y.mean()), 4), "brier": round(float(np.mean((p - y) ** 2)), 4),
            "log_loss": round(float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), 4), "ece": round(float(ece), 4),
            "auroc": None if auroc is None else round(auroc, 4)}


def analyse(path: str) -> dict:
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    y = np.array([r["label"] for r in rows], float)
    bases = np.array([r["base_id"] for r in rows])
    out = {"n": len(rows), "positives": int(y.sum())}
    out["naive_beta_robust16"] = metrics([beta_pass(r["robust16"], 16) for r in rows], y)
    out["naive_beta_robust8"] = metrics([beta_pass(r["robust8"], 8) for r in rows], y)
    out["constant"] = metrics(np.full(len(y), y.mean()), y)
    for name, feats in {"robust16": ("robust16",), "robust16+stress": ("robust16", "stress4"),
                        "all_visible": FEATURES}.items():
        X = design_matrix(rows, feats)
        p = np.zeros(len(y))
        for b in sorted(set(bases)):
            te = bases == b
            if y[~te].min() == y[~te].max():
                p[te] = y[~te].mean()
                continue
            p[te] = 1 / (1 + np.exp(-X[te] @ fit_logistic(X[~te], y[~te])))
        out[f"logistic_lobo[{name}]"] = metrics(p, y)
    out["full_fit_all_visible"] = fit_logistic(design_matrix(rows, FEATURES), y).round(4).tolist()
    return out


def isotonic_counts(k: np.ndarray, y: np.ndarray, n: int) -> list[float]:
    """Pool-adjacent-violators fit of P(label | count k in 0..n), non-decreasing in k; empty cells borrow neighbours."""
    blocks = []                       # [sum_y, count, lo_k, hi_k]
    for v in range(n + 1):
        m = k == v
        if m.any():
            blocks.append([float(y[m].sum()), int(m.sum()), v, v])
            while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
                b = blocks.pop()
                blocks[-1][0] += b[0]
                blocks[-1][1] += b[1]
                blocks[-1][3] = b[3]
    p = [None] * (n + 1)
    for s_, c, lo, hi in blocks:
        for v in range(lo, hi + 1):
            p[v] = s_ / c
    last = 0.0
    for v in range(n + 1):
        last = p[v] if p[v] is not None else last
        p[v] = last
    return p


def fit(path: str, out: str) -> dict:
    """Isotonic map robust16 -> P(FULL), with leave-one-base-out predictions for honest metrics."""
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    k = np.array([r["robust16"] for r in rows])
    y = np.array([r["label"] for r in rows], float)
    bases = np.array([r["base_id"] for r in rows])
    lobo = np.zeros(len(y))
    for b in sorted(set(bases)):
        te = bases == b
        table = isotonic_counts(k[~te], y[~te], 16)
        lobo[te] = [table[v] for v in k[te]]
    model = {"kind": "isotonic_robust16", "fitted_on": os.path.basename(path), "n": int(len(y)),
             "p": [round(v, 6) for v in isotonic_counts(k, y, 16)], "lobo_metrics": metrics(lobo, y),
             "naive_beta_metrics": metrics([beta_pass(int(v), 16) for v in k], y)}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(model, fh, indent=1)
    return model


def fit_logistic_rs(path: str, out: str) -> dict:
    """Logistic map (robust16, stress4) -> P(FULL) with leave-one-base-out metrics (dev only)."""
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    y = np.array([r["label"] for r in rows], float)
    bases = np.array([r["base_id"] for r in rows])
    feats = ("robust16", "stress4")
    X = design_matrix(rows, feats)
    lobo = np.zeros(len(y))
    for b in sorted(set(bases)):
        te = bases == b
        lobo[te] = 1 / (1 + np.exp(-X[te] @ fit_logistic(X[~te], y[~te])))
    w = fit_logistic(X, y)
    model = {"kind": "logistic_robust16_stress4", "features": list(feats), "n_by_feature": {"robust16": 16, "stress4": 4},
             "w": [round(float(v), 6) for v in w], "fitted_on": os.path.basename(path), "n": int(len(y)),
             "lobo_metrics": metrics(lobo, y), "naive_beta_metrics": metrics([beta_pass(int(r["robust16"]), 16) for r in rows], y)}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(model, fh, indent=1)
    return model


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--episodes", required=True)
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--out", required=True)
    b.add_argument("--thresholds", default=None)
    an = sub.add_parser("analyse")
    an.add_argument("path")
    ft = sub.add_parser("fit")
    ft.add_argument("path")
    ft.add_argument("--out", required=True)
    ft.add_argument("--kind", choices=["logistic", "isotonic"], default="logistic")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a)
    elif a.cmd == "fit":
        print(json.dumps(fit_logistic_rs(a.path, a.out) if a.kind == "logistic" else fit(a.path, a.out), indent=1))
    else:
        print(json.dumps(analyse(a.path), indent=1))


if __name__ == "__main__":
    main()
