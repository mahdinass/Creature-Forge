"""M1 controller-recoverability study driver (walking-recovery research; development data only, never confirmatory).

A protocol JSON (committed BEFORE the run; its sha256 is recorded in every result line) lists the creatures, the conditions
and the replicates. For every (creature, condition, replicate) unit the driver
  1. builds the start controller: the frozen R2 winner ("r2") or its dynamic-similarity transfer ("similarity");
  2. runs `walk_opt.cma_search` with the condition's search space and rollout budget on the creature's TRAIN seeds under the
     validation-variation preset (budget 0 = no search: the start point itself is the candidate);
  3. assesses the best-so-far candidate at every checkpoint with `recovery.assess` (24 validation + 24 confirmation seeds,
     the same blocks for every condition of a creature, so conditions are paired);
  4. appends ONE JSON line to the results file (append-only; a unit is written only when complete).
Seeds come from `creature_gen.walkrec_seed_block(campaign, role, creature)`; every role block is disjoint from the others and
from every earlier experiment. A rollout cap is checked before each unit against its worst case (budget + assessments).
Units are deterministic, so an interrupted unit (which leaves no line) reproduces exactly when run again; `--resume` skips
completed units.

    python scripts/walk_oracle.py --protocol experiments/walk_recovery/oracle/protocol_m1a.json \
        --out experiments/walk_recovery/oracle/results/m1a.jsonl [--resume] [--workers 4] [--only CREATURE]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import creature_gen as cg  # noqa: E402
from creature_forge import creature_walk as cw  # noqa: E402
from creature_forge import recovery as rc  # noqa: E402
from creature_forge import walk_opt as wo  # noqa: E402
from creature_forge.arena import VARIATION_PRESET  # noqa: E402
from creature_forge.forge_pool import ForgePool  # noqa: E402
from creature_forge.optimize import jsonable  # noqa: E402

ASSESS_ROLLOUT_EQUIV = rc.VALIDATE_N * 2 + rc.CONFIRM_N * rc.CONFIRM_DURATION / rc.TRAIN_DURATION   # worst case per assessment


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        c = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
        return c + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("CF_SNAPSHOT", "unknown")


def load_creatures(proto: dict) -> dict[str, dict]:
    named = cg.dev_named_bodies()
    out: dict[str, dict] = {}
    for c in proto["creatures"]:
        if c.get("generated"):
            g = c["generated"]
            panel = cg.generate_panel(g["campaign"], int(g["n"]), min_dist=float(g.get("min_dist", 0.15)),
                                      max_draws=int(g.get("max_draws", 2000)))
            for a in panel["accepted"]:
                out[a["id"]] = a["body"]
        else:
            out[c["name"]] = named[c["name"]]
    return out


def start_vector(init: str, body: dict) -> tuple[list[float], dict | None]:
    base = list(cw.R2_WINNER)
    if init == "r2":
        return base, None
    if init == "similarity":
        v, rep = wo.similarity_init(body, base)
        return list(v), rep
    raise ValueError(f"unknown init {init!r}")


def space_of(cond: dict) -> "wo.SearchSpace":
    s = cond["space"]
    ctrl = s.get("ctrl", "all")
    body = tuple(s.get("body", ()))
    if ctrl == "all":
        return wo.SearchSpace.full_ctrl(body_params=body)
    if ctrl == "none":
        return wo.SearchSpace(ctrl_params=(), body_params=body)
    return wo.SearchSpace.from_subspaces(tuple(ctrl), body_params=body)


def run_unit(proto: dict, name: str, body: dict, cond: dict, noise_seed: int, pool) -> dict:
    campaign = proto["campaign"]
    seeds = {r: list(cg.walkrec_seed_block(campaign, r, name, int(proto["seeds"][r]))) for r in ("train", "validate", "confirm")}
    t0 = time.perf_counter()
    init_vec, sim_report = start_vector(cond["init"], body)
    budget = int(cond["budget"])
    variation = VARIATION_PRESET if cond.get("train_variation", "preset") == "preset" else None
    train = seeds["train"][: int(cond.get("n_train", len(seeds["train"])))]
    if budget > 0:
        search = wo.cma_search(body, init_vec, space_of(cond), budget=budget, train_seeds=train, noise_seed=noise_seed,
                               pool=pool, variation=variation, checkpoints=tuple(cond.get("checkpoints", (budget,))))
        cps = {int(k): v for k, v in search["checkpoints"].items()}
    else:
        search = None
        cps = {0: {"body": body, "vector": init_vec, "edits": [], "score": None, "found_at_rollouts": 0}}
    original = {"body": body, "vector": list(cw.R2_WINNER)}
    assessed: dict[int, dict] = {}
    cache: dict[str, dict] = {}
    for c in sorted(cps):
        cand = {"body": cps[c]["body"], "vector": cps[c]["vector"]}
        key = hashlib.sha256(json.dumps(jsonable(cand), sort_keys=True).encode()).hexdigest()
        if key not in cache:
            cache[key] = rc.assess(original, cand, seeds["validate"], seeds["confirm"], pool=pool)
        a = cache[key]
        assessed[c] = {"candidate_key": key, "status": a["status"], "reasons": a["reasons"], "assessment": a,
                       "edits": cps[c].get("edits"), "train_score": cps[c].get("score"),
                       "found_at_rollouts": cps[c].get("found_at_rollouts")}
    assess_rollouts = sum(v["rollouts"]["validation"] + v["rollouts"]["confirmation"] for v in cache.values())
    return jsonable({
        "unit": f"{name}|{cond['id']}|{noise_seed}", "creature": name, "body": body, "features": cg.features(body),
        "region": cg.region_of(cg.features(body)), "condition": cond, "noise_seed": noise_seed,
        "seeds": seeds, "train_seeds_used": train, "init": {"kind": cond["init"], "vector": init_vec, "similarity": sim_report},
        "search": search, "checkpoints": assessed,
        "rollouts": {"search": (search or {}).get("rollouts_used", 0), "assessment": assess_rollouts},
        "wall_s": time.perf_counter() - t0})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only")
    a = ap.parse_args()
    ppath = Path(a.protocol)
    proto = json.loads(ppath.read_text(encoding="utf-8"))
    psha = sha256_file(ppath)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    used = 0.0
    if out.exists():
        if not a.resume:
            raise SystemExit(f"{out} exists; use --resume to continue (completed units are skipped, never rerun)")
        for line in out.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["protocol_sha256"] != psha:
                raise SystemExit("results file was produced under a different protocol; refusing to mix")
            done.add(r["unit"])
            used += r["rollouts"]["search"] + r["rollouts"]["assessment"]
    cap = float(proto["rollout_cap"])
    creatures = load_creatures(proto)
    commit = git_commit()
    with ForgePool(max_workers=a.workers) as pool:
        for name, body in creatures.items():
            if a.only and name != a.only:
                continue
            for cond in proto["conditions"]:
                for ns in proto["replicates"]:
                    unit = f"{name}|{cond['id']}|{ns}"
                    if unit in done:
                        continue
                    n_cp = len(cond.get("checkpoints", (cond["budget"],))) if cond["budget"] else 1
                    worst = int(cond["budget"]) + n_cp * ASSESS_ROLLOUT_EQUIV
                    if used + worst > cap:
                        print(json.dumps({"stop": "rollout cap", "used": used, "next_worst": worst, "cap": cap}), flush=True)
                        return 2
                    rec = run_unit(proto, name, body, cond, int(ns), pool)
                    rec.update({"protocol_id": proto["id"], "protocol_sha256": psha, "code_commit": commit,
                                "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                    with out.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(rec, separators=(",", ":")) + "\n")
                    used += rec["rollouts"]["search"] + rec["rollouts"]["assessment"]
                    summ = {c: v["status"] for c, v in rec["checkpoints"].items()}
                    print(json.dumps({"unit": unit, "statuses": summ, "rollouts": rec["rollouts"], "used_total": used,
                                      "wall_s": round(rec["wall_s"], 1)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
