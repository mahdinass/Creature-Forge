"""DS-1 stop map v2 (docs/DS1_PROTOCOL.md §1.4): logistic P(FULL | robust16, stress4, displacement evidence) fitted on the
re-measured init-base designs (scripts/ds1_stop_data.py), compared with stop map v1 by leave-one-base-out Brier and AUROC on
the same designs. Pre-declared rule: v2 replaces v1 in engine v6 only if its LOBO Brier is lower.

Usage: python scripts/ds1_stop_map.py --data artifacts/vm/hdb/artifacts/hdb/ds1_stopdata.jsonl
       [--v1 experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json] [--out experiments/causal_engineer/dev/hdb/ds1]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creature_forge import belief_engine as be                          # noqa: E402
from creature_forge.repair_learning import fit_logistic, predict         # noqa: E402

N_BY = {"robust16": 16, "stress4": 4}
FEATURES = ["robust16", "stress4", "disp_pass", "disp_median_m"]


def auroc(y, p):
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return float(np.mean([(a > b) + 0.5 * (a == b) for a in pos for b in neg]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--v1", default="experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json")
    ap.add_argument("--out", default="experiments/causal_engineer/dev/hdb/ds1")
    a = ap.parse_args()
    v1 = json.load(open(a.v1, encoding="utf-8"))
    model0 = {"kind": "logistic_v2", "features": FEATURES, "n_by_feature": N_BY, "disp_clip": [-1.5, 1.5], "w": [0.0] * 5}
    rows = []
    for line in open(a.data, encoding="utf-8"):
        r = json.loads(line)
        for d in r["designs"]:
            x = be.v2_features(d, model0)
            if x is None:
                continue
            rows.append({"base": r["base"], "x": x, "y": float(d["status"] == "FULL_RECOVERY"), "ev": d})
    X = np.array([r["x"] for r in rows])
    y = np.array([r["y"] for r in rows])
    bases = sorted({r["base"] for r in rows})
    p2 = np.zeros(len(rows))
    for b in bases:
        tr = np.array([r["base"] != b for r in rows])
        w = fit_logistic(X[tr], y[tr], lam=0.1)
        p2[~tr] = predict(w, X[~tr])
    p1 = np.array([be.mapped_p_full(v1, r["ev"]) for r in rows], dtype=float)
    res = {"n_designs": len(rows), "n_bases": len(bases), "full_rate": float(y.mean()),
           "v1": {"brier": float(np.mean((p1 - y) ** 2)), "auroc": auroc(y, p1)},
           "v2_lobo": {"brier": float(np.mean((p2 - y) ** 2)), "auroc": auroc(y, p2)},
           "disp_pass_rate_full": float(np.mean([r["ev"]["disp_pass"] for r in rows if r["y"] == 1])),
           "disp_pass_rate_not_full": float(np.mean([r["ev"]["disp_pass"] for r in rows if r["y"] == 0])),
           "accepted_v1_at_tau": int(np.sum(p1 >= 0.75)), "verified_of_accepted_v1": float(y[p1 >= 0.75].mean()) if np.any(p1 >= 0.75) else None,
           "accepted_v2_at_tau": int(np.sum(p2 >= 0.75)), "verified_of_accepted_v2": float(y[p2 >= 0.75].mean()) if np.any(p2 >= 0.75) else None}
    res["use_v2"] = res["v2_lobo"]["brier"] < res["v1"]["brier"]
    w = fit_logistic(X, y, lam=0.1)
    model = {**model0, "w": [float(v) for v in w], "fitted_on": "DS-1 init experience bases (scripts/ds1_stop_map.py)",
             "lobo": res}
    os.makedirs(a.out, exist_ok=True)
    json.dump(model, open(os.path.join(a.out, "stopmap_dev_v2.json"), "w", encoding="utf-8"), indent=1)
    json.dump(res, open(os.path.join(a.out, "stopmap_v2_report.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
