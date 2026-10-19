"""Learned amortised posterior (phase 3, Stage 2): simulate training failures on EXPERIENCE dev bases, train, cross-validate.

Training data: random deviations of the development mechanism structures (amortized_posterior.CLASSES; held-out primitives
excluded), with magnitudes drawn log-uniformly over broad physical ranges. Nothing is fitted to a bench instance. Each draw adds
a generic tolerance nuisance (belief_engine.tolerance_draws, independent of the sealed reality-gap generator). Each robot uses
its own policy-visible seed block (key "amortized"), and the nominal design is simulated on the same seeds.

Usage (VM):
  python scripts/hdb_amortized.py gen --split-file experiments/causal_engineer/dev/hdb/stage2_split.json --per-class 12 \
      --workers 7 --shard 0/1 --out artifacts/hdb/amort.jsonl
  python scripts/hdb_amortized.py train --data artifacts/hdb/amort.jsonl --out artifacts/hdb/amortized_v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                                # noqa: E402

from creature_forge import amortized_posterior as ap              # noqa: E402
from creature_forge import belief_engine as be                    # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge import hidden_plant as hp                     # noqa: E402
from creature_forge.forge_pool import ForgePool                   # noqa: E402
from creature_forge.hdb_workbench import WEIGH_NOISE, static_mass_com   # noqa: E402

N_SEEDS = 4


def _h(*parts) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def draw(kind: str, target: str, rng, dm: float) -> dict:
    """Broad physical magnitude ranges (declared a priori; wider than the bench's threshold-relative severities)."""
    u = lambda a, b: float(rng.uniform(a, b))         # noqa: E731
    if kind == "sensor_bias":
        params = {"rad": round(float(rng.choice([-1, 1])) * math.exp(u(math.log(0.01), math.log(0.4))), 6)}
    elif kind == "payload":
        params = {"mass_kg": round(min(15.0, math.exp(u(math.log(0.02), math.log(0.5))) * dm), 6), "x_m": round(u(-0.2, 0.2), 6)}
    elif kind == "contact_friction":
        params = {"factor": round(math.exp(-u(0.1, 3.9)), 6)}
    elif kind == "segment_length":
        params = {"factor": round(math.exp(-u(0.05, 1.2)), 6)}
    elif kind == "gain_scale":
        params = {"factor": round(math.exp(-u(0.1, 3.9)), 6)}
    elif kind == "actuator_strength":
        params = {"factor": round(math.exp(-u(0.05, 3.0)), 6)}
    elif kind == "clock_scale":
        params = {"factor": round(math.exp(float(rng.choice([-1, 1])) * u(0.05, 0.9)), 6)}
    elif kind == "torso_mass":
        params = {"factor": round(math.exp(u(0.05, 1.35)), 6)}
    else:
        raise ValueError(kind)
    return hp.validate_deviation([{"kind": kind, "target": target, "params": params}])[0]


def _weigh(plant, body, key) -> dict:
    t = static_mass_com(plant, body)
    rng = np.random.default_rng(_h("weigh", key))
    return {"mass_kg": t["mass_kg"] * (1.0 + WEIGH_NOISE["mass_frac"] * float(rng.standard_normal())),
            "com_x_m": t["com_x_m"] + WEIGH_NOISE["com_m"] * float(rng.standard_normal())}


def job(args) -> dict:
    base, j, cls = args
    seeds = hb.instance_seeds(base["base_id"], "amortized", 0)["obs"][:N_SEEDS]
    body, vec = base["body"], base["vector"]
    if cls is None:                         # nominal reference on the same seeds
        o = hp.observe(body, vec, seeds, plant=None)
        f = hp.observe(body, vec, seeds, plant=None, friction_mult=3.0)
        return {"base_id": base["base_id"], "nominal": True, "obs": ap.panel(be.obs_features(o)),
                "floor": ap.panel(be.obs_features(f)), "weigh": static_mass_com({"deviation": []}, body)}
    kind, target = ap.CLASSES[cls]
    rng = np.random.default_rng(_h(base["base_id"], j, cls))
    dm = hb.design_mass(body)
    prim = draw(kind, target, rng, dm)
    gap = be.tolerance_draws(1, seed=_h("tol", base["base_id"], j, cls) % (2 ** 31))[0]
    plant = {"deviation": [prim], "gap": gap}
    o = hp.observe(body, vec, seeds, plant=plant)
    f = hp.observe(body, vec, seeds, plant=plant, friction_mult=3.0)
    return {"base_id": base["base_id"], "j": j, "cls": cls, "prim": prim, "design_mass": dm,
            "obs": ap.panel(be.obs_features(o)), "floor": ap.panel(be.obs_features(f)),
            "weigh": _weigh(plant, body, f"{base['base_id']}:{j}:{cls}")}


def gen(a) -> None:
    split = json.load(open(a.split_file, encoding="utf-8"))
    want = set(split["experience_bases"])
    bases = [b for b in hb.load_bases("dev") if b["base_id"] in want]
    assert len(bases) == len(want), (len(bases), len(want))
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out, encoding="utf-8"):
            r = json.loads(l)
            done.add((r["base_id"], r.get("j"), r.get("cls")))
    jobs = []
    for b in bases:
        if (b["base_id"], None, None) not in done:
            jobs.append((b, None, None))
        for c in range(len(ap.CLASSES)):
            for j in range(a.per_class):
                if (b["base_id"], j, c) not in done:
                    jobs.append((b, j, c))
    k, n = (int(x) for x in a.shard.split("/"))
    jobs = jobs[k::n]
    print(f"{len(jobs)} jobs", flush=True)
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "a", encoding="utf-8") as out:
        for i, (_, rec) in enumerate(pool.imap(job, jobs)):
            if isinstance(rec, tuple):
                print("ERROR", rec, flush=True)
                continue
            out.write(json.dumps(rec) + "\n")
            if i % 50 == 0:
                out.flush()
                print(i, flush=True)


def rows_from(path: str) -> list[dict]:
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    nom = {r["base_id"]: r for r in recs if r.get("nominal")}
    rows = []
    for r in recs:
        if r.get("nominal") or r["base_id"] not in nom:
            continue
        n = nom[r["base_id"]]
        rows.append({"base_id": r["base_id"], "cls": r["cls"],
                     "x_obs": ap.vectorize(r["obs"], n["obs"], full=False).tolist(),
                     "x_full": ap.vectorize(r["obs"], n["obs"], r["floor"], n["floor"], r["weigh"], n["weigh"], full=True).tolist(),
                     "y": ap.encode_params(r["prim"], r["design_mass"])})
    return rows


def train(a) -> None:
    rows = rows_from(a.data)
    report = {w: ap.cross_validate(rows, full=(w == "full")) for w in ("obs", "full")}
    models = {w: ap.train(rows, full=(w == "full")) for w in ("obs", "full")}
    models["cv"] = report
    json.dump(models, open(a.out, "w", encoding="utf-8"))
    print(json.dumps(report, indent=1))


def main() -> None:
    ap_ = argparse.ArgumentParser()
    sp = ap_.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("gen")
    g.add_argument("--split-file", required=True)
    g.add_argument("--per-class", type=int, default=12)
    g.add_argument("--workers", type=int, default=7)
    g.add_argument("--shard", default="0/1")
    g.add_argument("--out", required=True)
    t = sp.add_parser("train")
    t.add_argument("--data", required=True)
    t.add_argument("--out", required=True)
    a = ap_.parse_args()
    {"gen": gen, "train": train}[a.cmd](a)


if __name__ == "__main__":
    main()
