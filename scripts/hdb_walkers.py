"""Fresh verified walkers for the Hidden-Damage Bench (phase 3): new healthy bases, never used by any earlier stage.

1. `creature_gen.generate_panel(campaign="hdb-v1-gen", n)`: genuinely failing guided bodies (the S3 rule, unchanged).
2. Morphology split BEFORE any pipeline runs: each creature's region (creature_gen.region_of) is assigned to dev or test by a
   hash of the region name (`split_of`), so test robots are morphologically separated from dev robots and the split cannot
   depend on any outcome.
3. Per creature: walk_pipelines.run_pipeline with the FIX director at 2,000 rollouts and the S3 settings, then
   recovery.assess (full_recovery_v1). FULL_RECOVERY designs become HDB bases (nominal designs); the others are kept in the
   output as non-bases (reported, never used).

Usage (VM): python scripts/hdb_walkers.py panel --n 250 --workers 32 --out artifacts/hdb/walkers_panel.json
            python scripts/hdb_walkers.py run --panel artifacts/hdb/walkers_panel.json --shard k/K --workers 3 \
                --out artifacts/hdb/walkers_sK.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from creature_forge import creature_gen as cg                   # noqa: E402
from creature_forge import creature_walk as cw                  # noqa: E402
from creature_forge import recovery as rc                       # noqa: E402
from creature_forge import walk_pipelines as wp                 # noqa: E402
from creature_forge.forge_pool import ForgePool                 # noqa: E402
from creature_forge.optimize import jsonable                    # noqa: E402

CAMPAIGN = "hdb-v1-walkers"
GEN_CAMPAIGN = "hdb-v1-gen"
TEST_FRACTION = 0.6
S3 = json.loads((ROOT / "experiments" / "walk_recovery" / "confirmatory" / "protocol.json").read_text(encoding="utf-8"))


def split_of(region: str) -> str:
    h = int(hashlib.sha256(f"hdb-v1-split:{region}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "test" if h < TEST_FRACTION else "dev"


def panel(a) -> None:
    with ForgePool(max_workers=a.workers) as pool:
        p = cg.generate_panel(GEN_CAMPAIGN, a.n, pool=pool)
    for c in p["accepted"]:
        c["hdb_split"] = split_of(c["region"])
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(jsonable(p)), encoding="utf-8")
    acc = p["accepted"]
    print(f"accepted {len(acc)}; dev {sum(c['hdb_split'] == 'dev' for c in acc)}, test {sum(c['hdb_split'] == 'test' for c in acc)}")


def run(a) -> None:
    p = json.loads(Path(a.panel).read_text(encoding="utf-8"))
    k, n = (int(x) for x in a.shard.split("/"))
    todo = p["accepted"][k::n]
    st, ks, family, budget = S3["settings"], S3["seeds"], 17, 2000
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["creature"] for l in open(a.out, encoding="utf-8") if l.strip()}
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "a", encoding="utf-8") as out:
        for c in todo:
            name = c["id"]
            if name in done:
                continue
            t0 = time.perf_counter()
            ns_role = {"diag": "probe", "train": "train", "screen": "screen", "validate": "validate", "confirm": "confirm"}
            seeds = {r: list(cg.walkrec_seed_block(CAMPAIGN, ns_role[r], name, int(ks[r]))) for r in ns_role}
            noise = int(hashlib.sha256(f"{CAMPAIGN}:{name}".encode()).hexdigest()[:8], 16)
            director = wp.FixedDirector(probes=("opt_placement", "opt_body", "opt_posture"))
            rec = wp.run_pipeline(c["body"], director, total_budget=budget, family=family,
                                  seeds={"diag": seeds["diag"], "train": seeds["train"], "screen": seeds["screen"]},
                                  noise_seed=noise, pool=pool, probe_budget=int(round(float(st["probe_budget_frac"]) * budget)),
                                  rounds=int(st["rounds"]), screen_top_k=int(st["screen_top_k"]), screen_n=int(st["screen_n"]),
                                  director_name="fix", selection=st.get("selection", "v1"))
            fin = rec["final"]
            ass = rc.assess({"body": c["body"], "vector": list(cw.R2_WINNER)}, {"body": fin["body"], "vector": fin["vector"]},
                            seeds["validate"], seeds["confirm"], pool=pool)
            out.write(json.dumps(jsonable({
                "creature": name, "hdb_split": c["hdb_split"], "region": c["region"], "features": c.get("features"),
                "body": c["body"], "method": "fix", "budget": budget, "noise_seed": noise, "seeds": seeds,
                "pipeline": {"final": fin, "used": rec["used"]}, "status": ass["status"],
                "assessment": {"status": ass["status"], "walking_frac": ass["validation"]["walking_frac"], "reasons": ass["reasons"]},
                "wall_s": time.perf_counter() - t0})) + "\n")
            out.flush()
            print(name, c["hdb_split"], ass["status"], flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("panel")
    p.add_argument("--n", type=int, default=250)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--out", required=True)
    r = sub.add_parser("run")
    r.add_argument("--panel", required=True)
    r.add_argument("--shard", default="0/1")
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--out", required=True)
    a = ap.parse_args()
    {"panel": panel, "run": run}[a.cmd](a)


if __name__ == "__main__":
    main()
