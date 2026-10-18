"""Identifiability study (phase 3, before any comparative run): can the available instruments tell symptom-twin mechanisms apart?

For every dev instance (base x family x severity, with its reality gap) the plant runs the full instrument panel: observe, the
high-friction floor test, the weigh test and every generic candidate counterfactual (belief_engine.CANDIDATE_CFS). Then:
  (a) model-based separability: within the instance's twin pair, the posterior over the two families (uniform prior, marginal
      over each family's own severity grid, paired-seed twin likelihood from belief_engine) for instrument subsets
      obs | obs+conditions | obs+conditions+counterfactuals. This is a best case: the family set and grids are known.
  (b) model-free check: leave-one-base-out 1-NN on the standardised plant panel features.
Eligibility is recorded but nothing is filtered here; ineligible instances are reported separately.

Usage (VM): python scripts/hdb_identifiability.py --bases 6 --workers 8 --out artifacts/hdb/ident.jsonl
            python scripts/hdb_identifiability.py --analyse artifacts/hdb/ident.jsonl > experiments/.../IDENTIFIABILITY.md
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                                # noqa: E402

from creature_forge import belief_engine as be                    # noqa: E402
from creature_forge import fault_bench as fb                      # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge import hidden_plant as hp                     # noqa: E402
from creature_forge.forge_pool import ForgePool                   # noqa: E402
from creature_forge.hdb_workbench import static_mass_com          # noqa: E402

TWIN_SEEDS = 2


def _experiments(robot: dict) -> list[dict]:
    from creature_forge.eng_tools import parse_counterfactual
    out = [{"id": "observe", "group": "obs", "design": robot},
           {"id": "floor_test@x3", "group": "conditions", "design": robot, "friction_mult": 3.0},
           {"id": "weigh_test", "group": "conditions", "design": robot, "weigh": True}]
    for cid in be.CANDIDATE_CFS:
        try:
            body, vec = fb.apply_changes(robot["body"], robot["vector"], parse_counterfactual(cid))
        except Exception:   # noqa: BLE001
            continue
        out.append({"id": "cf:" + cid, "group": "counterfactuals", "design": {"body": body, "vector": vec}})
    return out


def _measure(plant, exp, seeds, design_mass=None) -> dict:
    if exp.get("weigh"):
        return static_mass_com(plant, exp["design"]["body"])
    obs = hp.observe(exp["design"]["body"], exp["design"]["vector"], seeds, plant=plant,
                     friction_mult=exp.get("friction_mult", 1.0))
    return be.obs_features(obs)


def _grid(base, family, th):
    """Hypothesis grid of a family on this base: v1 fixed grid, or v2 threshold multiples of every variant."""
    if th is None:
        return [hb.deviation_for(base, family, s) for s in range(hb.severity_count(family))]
    out = []
    for s in range(len(hb.v2_severities(family))):
        inst = hb.make_instance_v2(base, family, s, th, gap=False)
        if inst is not None:
            out.append(inst["plant"]["deviation"])
    return out


def study_instance(args) -> dict:
    base, family, sev, th = args
    t0 = time.perf_counter()
    raw = hb.make_instance_v2(base, family, sev, th) if th is not None else hb.make_instance(base, family, sev)
    if raw is None:
        return {"instance_id": hb.instance_key(base["base_id"], family, sev), "skipped": "no threshold / above max"}
    inst = hb.check_eligibility(raw)
    seeds = inst["seeds"]["obs"][:4]
    exps = _experiments(inst["robot"])
    plant_panel = {e["id"]: _measure(inst["plant"], e, seeds) for e in exps}
    dm = hb.design_mass(inst["robot"]["body"])
    specs = hb.FAMILY_SPECS if th is not None else hb.FAMILIES
    pair = specs[family]["pair"]
    rivals = [f for f, s in specs.items() if s["pair"] == pair]
    grids = {f: _grid(base, f, th) for f in rivals}
    # twin predictions for every (family, grid point) on TWIN_SEEDS seeds; gap-free
    ll = {}
    for f in rivals:
        for s, dev in enumerate(grids[f]):
            for e in exps:
                pred = _measure({"deviation": dev}, e, seeds[:TWIN_SEEDS])
                obs = plant_panel[e["id"]]
                if e.get("weigh"):
                    v = be.weigh_loglik(obs, pred, dm)
                else:
                    v = be.loglik({k: obs[k] for k in list(obs)[:TWIN_SEEDS]}, pred)
                ll[(f, s, e["id"])] = v
    groups = {"obs": ["obs"], "obs+conditions": ["obs", "conditions"], "all": ["obs", "conditions", "counterfactuals"]}
    post = {}
    for gname, gs in groups.items():
        ids = [e["id"] for e in exps if e["group"] in gs]
        fam_lml = {}
        for f in rivals:
            vals = [sum(ll[(f, s, i)] for i in ids) for s in range(len(grids[f]))]
            if not vals:
                fam_lml[f] = -1e300
                continue
            m = max(vals)
            fam_lml[f] = m + math.log(sum(math.exp(v - m) for v in vals) / len(vals))
        m = max(fam_lml.values())
        z = sum(math.exp(v - m) for v in fam_lml.values())
        post[gname] = {f: math.exp(v - m) / z for f, v in fam_lml.items()}
    return {"instance_id": inst["instance_id"], "base_id": base["base_id"], "family": family, "pair": pair, "severity": sev,
            "eligible": inst["eligible"], "check": inst["check"]["walking"], "panel": plant_panel, "posterior": post,
            "wall_s": time.perf_counter() - t0}


def analyse(path: str) -> str:
    rows = [r for r in (json.loads(l) for l in open(path, encoding="utf-8") if l.strip()) if not r.get("skipped")]
    L = ["# Identifiability study (dev, model-based twin-pair separability + model-free check)", "",
         f"Instances: {len(rows)}; eligible (plant fails): {sum(r['eligible'] for r in rows)}. Results below use eligible instances; "
         "the posterior is over the two families of the instance's twin pair (uniform prior, marginal over each family's grid).", ""]
    el = [r for r in rows if r["eligible"]]
    for pair in sorted({r["pair"] for r in el}):
        pr = [r for r in el if r["pair"] == pair]
        L += [f"## {pair}", "", "| family | n | MAP correct: obs | obs+conditions | all | mean P(correct) all |", "|---|---|---|---|---|---|"]
        for fam in sorted({r["family"] for r in pr}):
            fr = [r for r in pr if r["family"] == fam]
            acc = {g: sum(max(r["posterior"][g], key=r["posterior"][g].get) == fam for r in fr) for g in ("obs", "obs+conditions", "all")}
            mp = np.mean([r["posterior"]["all"][fam] for r in fr])
            L.append(f"| {fam} | {len(fr)} | {acc['obs']} | {acc['obs+conditions']} | {acc['all']} | {mp:.3f} |")
        # model-free LOBO 1-NN on the plant panel
        feats, labels, bases = [], [], []
        keys = sorted({(e, s, k) for r in pr for e, v in r["panel"].items() if e != "weigh_test"
                       for s, d in v.items() for k in d})
        for r in pr:
            vec = []
            for e, s, k in keys:
                v = (r["panel"].get(e) or {}).get(s, {}).get(k)
                vec.append(np.nan if v is None else v)
            w = r["panel"].get("weigh_test") or {}
            vec += [w.get("mass_kg", np.nan), w.get("com_x_m", np.nan)]
            feats.append(vec)
            labels.append(r["family"])
            bases.append(r["base_id"])
        X = np.asarray(feats, float)
        X = np.where(np.isnan(X), np.nanmean(X, 0), X)
        X = (X - X.mean(0)) / (X.std(0) + 1e-9)
        ok = 0
        for i in range(len(X)):
            m = np.array([b != bases[i] for b in bases])
            if not m.any():
                continue
            d = ((X[m] - X[i]) ** 2).sum(1)
            ok += np.array(labels)[m][int(np.argmin(d))] == labels[i]
        L += ["", f"Model-free leave-one-base-out 1-NN on the plant panel: {ok}/{len(X)} correct.", ""]
    inel = [r for r in rows if not r["eligible"]]
    if inel:
        L += ["## Not eligible (plant still walks; reported, not studied)", ""]
        L += [f"- {r['instance_id']}: check walking {r['check']}/8" for r in inel]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", type=int, default=6)
    ap.add_argument("--base-offset", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="artifacts/hdb/ident.jsonl")
    ap.add_argument("--analyse", default=None)
    ap.add_argument("--thresholds", default=None)
    a = ap.parse_args()
    if a.analyse:
        print(analyse(a.analyse))
        return
    bases = hb.load_bases("dev")[a.base_offset:a.base_offset + a.bases]
    th = json.load(open(a.thresholds, encoding="utf-8")) if a.thresholds else None
    fams = hb.FAMILY_SPECS if th is not None else hb.FAMILIES
    nsev = (lambda f: len(hb.v2_severities(f))) if th is not None else hb.severity_count
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["instance_id"] for l in open(a.out, encoding="utf-8") if l.strip()}
    jobs = [(b, f, s, th) for b in bases for f in fams for s in range(nsev(f))
            if hb.instance_key(b["base_id"], f, s) not in done]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "a", encoding="utf-8") as out:
        for _, rec in pool.imap(study_instance, jobs):
            if isinstance(rec, tuple):
                print("ERROR", rec, flush=True)
                continue
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(rec["instance_id"], rec["eligible"], {g: round(max(p.values()), 3) for g, p in rec["posterior"].items()},
                  round(rec["wall_s"]), flush=True)


if __name__ == "__main__":
    main()
