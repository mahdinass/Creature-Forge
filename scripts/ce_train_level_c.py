"""Train the runtime Level C repair-effect predictor on TRAINING robots (the dev probe dataset) and save it.

    python scripts/ce_train_level_c.py --probe artifacts/vm/ce3/ce/probe_dev.jsonl --lobo experiments/causal_engineer/dev/level_c_lobo.json \
        --model logistic --out experiments/causal_engineer/dev/level_c_logistic.json

Features use the body of the robot under investigation (`ce_memory.robot_features`). The saved model carries its leave-one-base-out
top-1 / top-3 hit rates (from `scripts/ce_learn_eval.py`) so the advice text can state its measured held-out accuracy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from creature_forge import repair_learner as rl  # noqa: E402
from creature_forge.ce_memory import robot_features  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--lobo", required=True, help="ce_learn_eval output JSON (for the held-out accuracy shown in the advice)")
    ap.add_argument("--model", default="logistic", choices=sorted(rl.MODEL_FACTORIES))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.probe, encoding="utf-8") if l.strip()]
    for r in rows:
        r["features"] = robot_features(r)
    pred = rl.RepairPredictor(a.model).fit(rows)
    lobo = json.load(open(a.lobo, encoding="utf-8"))

    def stat(setting, key):
        v = lobo["settings"][setting]["models"][a.model][key]
        return round(float(v["value"]), 3)

    pred.heldout = {st: {k: stat(st, k) for k in ("top1", "top3")} for st in rl.SETTINGS}
    pred.heldout["top1"] = pred.heldout["obs"]["top1"]          # advice_text default: the observation-only setting
    pred.heldout["setting"] = "obs"
    pred.save(a.out)
    print(json.dumps({"n_train": pred.n_train, "n_bases": pred.n_bases, "heldout": pred.heldout}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
