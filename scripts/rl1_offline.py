"""RL-1 offline development evaluation on the dev repair response matrix (docs/RL1_PLAN.md §5.1, gate G-RL1). Dev data only.

Each policy picks an ordered top-2 of tools for an instance; its value is 1 if either tool verified in the matrix (plant-only
single-tool repair at the matrix budget). Splits: LOFO (leave one dev family out = unfamiliar mechanism) and LOBO (leave one
base out = unfamiliar morphology). P-RL1 is fully nested: within each outer fold, memory features of training rows are
cross-fitted (inner leave-one-group-out) and hyper-parameters are chosen by inner-fold value; the test fold is never used.

Usage: python scripts/rl1_offline.py --a1 fresh_A1c5.jsonl --a0 fresh_A0.jsonl --matrix matrix.jsonl --out <dir>
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creature_forge import repair_memory as rm                    # noqa: E402

FULL = "FULL_RECOVERY"
GRID = {"h": (0.5, 1.0, 2.0), "n_min": (0.0, 1.0, 3.0), "delta": (0.0, 0.1, 0.25)}
BOOT_N, BOOT_SEED = 10000, 2026102501


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def build(a1_path, a0_path, matrix_path):
    a1 = {r["instance_id"]: r for r in load(a1_path) if r.get("verification")}
    a0 = {r["instance_id"]: r for r in load(a0_path) if r.get("verification")}
    mat = defaultdict(dict)
    for r in load(matrix_path):
        if "error" in r:
            raise SystemExit(f"matrix cell error: {r['instance_id']} {r['tool']}")
        mat[r["instance_id"]][r["tool"]] = r
    ids = sorted(i for i in a1 if i in a0 and len(mat.get(i, {})) == len(rm.TOOLS))
    D = []
    for i in ids:
        nominal = a0[i]["designs"][0]["body"]
        c = rm.context(a1[i], nominal)
        probe = [x["tool"] for x in a0[i]["policy"]["ranking"]]
        eng = rm.engine_order(a1[i])
        D.append({"id": i, "family": a1[i]["family"], "base": i.split(":")[0], "x": rm.ctx_vector(c),
                  "tev": rm.twin_evidence(a1[i]), "eng": eng, "probe": probe + [t for t in eng if t not in probe],
                  "y": np.array([1.0 if mat[i][t].get("status") == FULL else 0.0 for t in rm.TOOLS]),
                  "wf": np.array([mat[i][t].get("walking_frac") or 0.0 for t in rm.TOOLS]),
                  "a1_full": a1[i]["verification"]["status"] == FULL, "a0_full": a0[i]["verification"]["status"] == FULL})
    return D


def value(order, d):
    idx = [rm.TOOLS.index(t) for t in order[:2]]
    return float(max(d["y"][idx[0]], d["y"][idx[1]])), float(d["y"][idx[0]])


def mem_features(train, test_rows, h):
    """Memory query for each test row from a Memory over `train` (never containing the row itself)."""
    X = np.stack([d["x"] for d in train])
    Y = np.stack([d["y"] for d in train])
    mem = rm.Memory(X, Y, bandwidth=h)
    return [mem.query(d["x"]) for d in test_rows]


def crossfit_train_rows(train, group_key, h):
    """Memory features for every training instance, computed without its own group (inner leave-one-group-out)."""
    groups = sorted({d[group_key] for d in train})
    q = {}
    for g in groups:
        inner = [d for d in train if d[group_key] != g]
        rows = [d for d in train if d[group_key] == g]
        for d, qq in zip(rows, mem_features(inner, rows, h)):
            q[d["id"]] = qq
    return q


def fit_calibrator(train, q):
    F, y = [], []
    for d in train:
        for t in rm.TOOLS:
            F.append(rm.row_features(d["tev"], q[d["id"]], t))
            y.append(d["y"][rm.TOOLS.index(t)])
    return rm.fit_logistic(np.array(F), np.array(y))


def rl1_policy(train, test, group_key, h, n_min, delta):
    q_train = crossfit_train_rows(train, group_key, h)
    w = fit_calibrator(train, q_train)
    out = {}
    for d, q in zip(test, mem_features(train, test, h)):
        P = {t: rm.predict(w, rm.row_features(d["tev"], q, t)) for t in rm.TOOLS}
        dec = rm.decide(P, d["eng"], q["n_eff"], n_min=n_min, hedge_delta=delta)
        out[d["id"]] = {**dec, "P": P, "n_eff": q["n_eff"]}
    return out


def select_hyper(train, group_key):
    """Inner leave-one-group-out over the training groups; maximise mean top-2 value."""
    groups = sorted({d[group_key] for d in train})
    best, best_v = None, -1.0
    for h, n_min, delta in itertools.product(GRID["h"], GRID["n_min"], GRID["delta"]):
        vals = []
        for g in groups:
            inner_tr = [d for d in train if d[group_key] != g]
            inner_te = [d for d in train if d[group_key] == g]
            pol = rl1_policy(inner_tr, inner_te, group_key, h, n_min, delta)
            vals += [value(pol[d["id"]]["order"], d)[0] for d in inner_te]
        v = float(np.mean(vals))
        if v > best_v + 1e-12:
            best, best_v = (h, n_min, delta), v
    return best, best_v


def evaluate(D, group_key):
    groups = sorted({d[group_key] for d in D})
    rows = {}
    chosen = {}
    for g in groups:
        train = [d for d in D if d[group_key] != g]
        test = [d for d in D if d[group_key] == g]
        (h, n_min, delta), _ = select_hyper(train, group_key) if group_key == "family" else ((1.0, 1.0, 0.1), None)
        chosen[g] = {"h": h, "n_min": n_min, "delta": delta}
        pol = rl1_policy(train, test, group_key, h, n_min, delta)
        Xtr, Ytr = np.stack([d["x"] for d in train]), np.stack([d["y"] for d in train])
        for d in test:
            mem0 = rm.simple_memory_order(Xtr, Ytr, d["x"], d["eng"])
            oracle = float(d["y"].max())
            rows[d["id"]] = {"family": d["family"], "base": d["base"],
                             "P-eng": value(d["eng"], d), "P-probe": value(d["probe"], d), "P-mem0": value(mem0, d),
                             "P-RL1": value(pol[d["id"]]["order"], d), "mode": pol[d["id"]]["mode"], "oracle": oracle,
                             "A1_full": d["a1_full"], "A0_full": d["a0_full"],
                             "brier_rl1": float(np.mean([(pol[d["id"]]["P"][t] - d["y"][rm.TOOLS.index(t)]) ** 2
                                                         for t in rm.TOOLS]))}
    return rows, chosen


def cluster_boot(rows, a, b, n=BOOT_N, seed=BOOT_SEED):
    by = defaultdict(list)
    for r in rows.values():
        by[r["base"]].append(r[a][0] - r[b][0])
    blocks = list(by.values())
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        s = m = 0
        for _ in range(len(blocks)):
            blk = blocks[rng.randrange(len(blocks))]
            s += sum(blk)
            m += len(blk)
        stats.append(s / m)
    stats.sort()
    return [stats[int(0.05 * n)], stats[int(0.95 * n) - 1]]


def summarise(rows):
    pols = ("P-eng", "P-probe", "P-mem0", "P-RL1")
    out = {"n": len(rows), "top2": {p: float(np.mean([r[p][0] for r in rows.values()])) for p in pols},
           "top1": {p: float(np.mean([r[p][1] for r in rows.values()])) for p in pols},
           "oracle_any_tool": float(np.mean([r["oracle"] for r in rows.values()])),
           "stored_A1_full": float(np.mean([r["A1_full"] for r in rows.values()])),
           "stored_A0_full": float(np.mean([r["A0_full"] for r in rows.values()])),
           "modes": {m: sum(1 for r in rows.values() if r["mode"] == m) for m in ("commit", "hedge", "abstain")},
           "brier_rl1": float(np.mean([r["brier_rl1"] for r in rows.values()]))}
    for p in ("P-probe", "P-mem0", "P-RL1"):
        out[f"{p}_minus_P-eng"] = {"diff": out["top2"][p] - out["top2"]["P-eng"], "boot90": cluster_boot(rows, p, "P-eng")}
    fam = defaultdict(list)
    for r in rows.values():
        fam[r["family"]].append(r)
    out["per_family"] = {f: {"n": len(v), **{p: float(np.mean([r[p][0] for r in v])) for p in pols},
                             "oracle": float(np.mean([r["oracle"] for r in v]))} for f, v in sorted(fam.items())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a1", required=True)
    ap.add_argument("--a0", required=True)
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    D = build(a.a1, a.a0, a.matrix)
    res = {"n_instances": len(D)}
    for key, name in (("family", "LOFO"), ("base", "LOBO")):
        rows, chosen = evaluate(D, key)
        s = summarise(rows)
        res[name] = {**s, "hyper": chosen}
        if name == "LOFO":
            d = s["P-RL1_minus_P-eng"]
            worst = min(v["P-RL1"] - v["P-eng"] for v in s["per_family"].values())
            res["gate_G_RL1"] = {"c1_lower90_gt_0": d["boot90"][0] > 0, "c2_no_family_below_-0.15": worst >= -0.15,
                                 "c3_ge_mem0": s["top2"]["P-RL1"] >= s["top2"]["P-mem0"], "worst_family_diff": worst}
            res["gate_G_RL1"]["PASS"] = all(v for k, v in res["gate_G_RL1"].items() if k.startswith("c"))
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "rl1_offline.json"), "w", encoding="utf-8"), indent=1)
    for name in ("LOFO", "LOBO"):
        s = res[name]
        print(name, "top2", {k: round(v, 3) for k, v in s["top2"].items()}, "oracle", round(s["oracle_any_tool"], 3),
              "modes", s["modes"])
        for p in ("P-probe", "P-mem0", "P-RL1"):
            print("  ", p, "- P-eng", round(s[f"{p}_minus_P-eng"]["diff"], 3), [round(x, 3) for x in s[f"{p}_minus_P-eng"]["boot90"]])
    print("G-RL1", res["gate_G_RL1"])


if __name__ == "__main__":
    main()
