"""RL-1 EXPLORATORY analyses (post hoc; written after gate G-RL1 failed; no claim). Dev data only.
1. Headroom: where the engine's top-2 misses but some tool verifies, and top-k success of the engine and probe orders.
2. Twin-free engineer: does repair memory added to A0's plant-probe ranking help (LOFO, fixed hyper-parameters, no tuning)?
Usage: python scripts/rl1_explore.py --a1 ... --a0 ... --matrix ... --out <file.json>
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creature_forge import repair_memory as rm                    # noqa: E402
import rl1_offline as o                                           # noqa: E402


def probe_feats(d, q, t):
    r = d["probe"].index(t)
    return [1.0, 1.0 / (1 + r), 1.0 if r < 2 else 0.0, rm._logit(float(q["rate"][rm.TOOLS.index(t)])), np.log1p(q["n_eff"]),
            q["d_min"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a1", required=True)
    ap.add_argument("--a0", required=True)
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    D = o.build(a.a1, a.a0, a.matrix)
    idx = lambda ts: [rm.TOOLS.index(t) for t in ts]                           # noqa: E731
    miss = [d for d in D if d["y"][idx(d["eng"][:2])].max() == 0 and d["y"].max() == 1]
    out = {"note": "EXPLORATORY, post hoc after G-RL1 failed; no claim", "n": len(D),
           "headroom_instances": len(miss),
           "rank_of_first_working_tool_in_engine_order": sorted(collections.Counter(
               min(d["eng"].index(t) for t in rm.TOOLS if d["y"][rm.TOOLS.index(t)]) for d in miss).items()),
           "engine_topk": {k: float(np.mean([d["y"][idx(d["eng"][:k])].max() for d in D])) for k in (1, 2, 3, 4, 10)},
           "probe_topk": {k: float(np.mean([d["y"][idx(d["probe"][:k])].max() for d in D])) for k in (1, 2, 3, 4, 10)},
           "working_tools_per_instance": sorted(collections.Counter(int(d["y"].sum()) for d in D).items()),
           "per_tool_success": {t: float(np.mean([d["y"][rm.TOOLS.index(t)] for d in D])) for t in rm.TOOLS}}
    vals, fam = collections.defaultdict(list), collections.defaultdict(lambda: collections.defaultdict(list))
    for g in sorted({d["family"] for d in D}):
        tr, te = [d for d in D if d["family"] != g], [d for d in D if d["family"] == g]
        X, Y = np.stack([d["x"] for d in tr]), np.stack([d["y"] for d in tr])
        qtr = rm.crossfit_queries(X, Y, [d["family"] for d in tr], 1.0)
        w = rm.fit_logistic(np.array([probe_feats(d, q, t) for d, q in zip(tr, qtr) for t in rm.TOOLS]),
                            np.array([d["y"][rm.TOOLS.index(t)] for d in tr for t in rm.TOOLS]))
        mem = rm.Memory(X, Y, bandwidth=1.0)
        for d in te:
            q = mem.query(d["x"])
            P = {t: rm.predict(w, probe_feats(d, q, t)) for t in rm.TOOLS}
            order = sorted(rm.TOOLS, key=lambda t: (-P[t], d["probe"].index(t)))
            for name, ordr in (("probe", d["probe"]), ("probe+memory", order), ("engine", d["eng"])):
                v = o.value(ordr, d)[0]
                vals[name].append(v)
                fam[g][name].append(v)
    diff = np.array(vals["probe+memory"]) - np.array(vals["probe"])
    out["twin_free_lofo"] = {"top2": {k: float(np.mean(v)) for k, v in vals.items()},
                             "probe+memory_minus_probe": float(diff.mean()), "wins": int((diff > 0).sum()),
                             "losses": int((diff < 0).sum()),
                             "per_family": {g: {k: float(np.mean(v)) for k, v in vv.items()} for g, vv in fam.items()}}
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: out[k] for k in ("headroom_instances", "engine_topk", "probe_topk")}), out["twin_free_lofo"]["top2"])


if __name__ == "__main__":
    main()
