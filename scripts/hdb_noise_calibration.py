"""Likelihood noise calibration (phase 3, dev only): how far does the plant deviate from the twin that knows the TRUE deviation?

For dev v2 instances, the plant (true deviation + hidden reality gap) and the twin with the true deviation (no gap) walk the same
designs on the same obs seeds: the nominal design and a few generic counterfactual designs. The per-feature residuals are the
model-mismatch noise the belief engine's likelihood must tolerate. Output: robust scale per feature (1.4826 x MAD), the
95th-percentile |residual|, and the walking-label disagreement rate; belief_engine.FEATURES is set from this before freezing.

Usage (VM): python scripts/hdb_noise_calibration.py --thresholds artifacts/hdb/thresholds_olddev.json --split olddev \
                --workers 24 --out artifacts/hdb/noise_cal.jsonl
            python scripts/hdb_noise_calibration.py --analyse artifacts/hdb/noise_cal.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                                # noqa: E402

from creature_forge import belief_engine as be                    # noqa: E402
from creature_forge import fault_bench as fb                      # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge import hidden_plant as hp                     # noqa: E402
from creature_forge.forge_pool import ForgePool                   # noqa: E402

CFS = ("pitch_ref@+0.1R", "foot_length@x1.5", "freq@x0.85")


def job(args) -> dict:
    base, fam, sev, th = args
    inst = hb.make_instance_v2(base, fam, sev, th)
    if inst is None:
        return {"skipped": True}
    from creature_forge.eng_tools import parse_counterfactual
    designs = [("nominal", inst["robot"])]
    for cid in CFS:
        try:
            b, v = fb.apply_changes(inst["robot"]["body"], inst["robot"]["vector"], parse_counterfactual(cid))
            designs.append((cid, {"body": b, "vector": v}))
        except Exception:   # noqa: BLE001
            pass
    seeds = inst["seeds"]["obs"][:4]
    rows = []
    for name, d in designs:
        po = be.obs_features(hp.observe(d["body"], d["vector"], seeds, plant=inst["plant"]))
        to = be.obs_features(hp.observe(d["body"], d["vector"], seeds, plant={"deviation": inst["plant"]["deviation"]}))
        for s in seeds:
            if s in po and s in to:
                rows.append({"design": name, "plant": po[s], "twin": to[s]})
    return {"instance_id": inst["instance_id"], "family": fam, "rows": rows}


def analyse(path: str) -> dict:
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    res = {k: [] for k in be.FEATURES}
    miss = {k: [0, 0] for k in be.FEATURES}
    for r in recs:
        for row in r.get("rows", []):
            for k in be.FEATURES:
                a, b = row["plant"].get(k), row["twin"].get(k)
                if a is None and b is None:
                    continue
                miss[k][1] += 1
                if a is None or b is None:
                    miss[k][0] += 1
                    continue
                res[k].append(a - b)
    out = {}
    for k, v in res.items():
        v = np.asarray(v, float)
        if not len(v):
            continue
        out[k] = {"n": int(len(v)), "robust_scale": float(1.4826 * np.median(np.abs(v - np.median(v)))),
                  "p95_abs": float(np.percentile(np.abs(v), 95)), "current_sigma": be.FEATURES[k],
                  "one_missing_rate": round(miss[k][0] / max(1, miss[k][1]), 4)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thresholds")
    ap.add_argument("--split", default="olddev")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out")
    ap.add_argument("--analyse")
    a = ap.parse_args()
    if a.analyse:
        print(json.dumps(analyse(a.analyse), indent=1))
        return
    th = json.load(open(a.thresholds, encoding="utf-8"))
    jobs = [(b, f, s, th) for b in hb.load_bases(a.split) for f in hb.FAMILY_SPECS for s in range(len(hb.v2_severities(f)))]
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "w", encoding="utf-8") as out:
        for _, r in pool.imap(job, jobs):
            if isinstance(r, tuple) or r.get("skipped"):
                continue
            out.write(json.dumps(r) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
