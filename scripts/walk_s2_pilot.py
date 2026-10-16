"""S2 method dev pilot (walking recovery; development data only, never confirmatory).

For every (creature, method, budget) unit of the protocol: run `walk_pipelines.run_pipeline` with that method's director at
the given TOTAL rollout budget (everything charged), then assess the single final candidate with `recovery.assess`
(full_recovery_v1; 24 validation + 24 confirmation seeds; not charged, identical for every method). Seeds are per creature
and shared by every method and budget (paired). One JSON line per unit, appended only when the unit is complete.

Methods: cma_joint (FullSpaceDirector with 4 body params), cma_ctrl (FullSpaceDirector), fix (FixedDirector), rand
(RandomDirector), ai (NemotronDirector, LIVE; needs CREATURE_FORGE_ENABLE_LIVE=1 and the key in .env), ai_nogait (the same
with the baseline gait features removed from its evidence: an information ablation, H6), census (H6 ground
truth: every subspace probe and the morphology probes, no plans).

    python scripts/walk_s2_pilot.py --protocol experiments/walk_recovery/dev_pilot/protocol_s2.json \
        --panel experiments/walk_recovery/oracle/results/m1/panel.json --out artifacts/walk_recovery/s2/shard0.jsonl \
        --shard 0/12 --workers 3 [--methods cma_joint,fix] [--resume]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from creature_forge import creature_gen as cg  # noqa: E402
from creature_forge import creature_walk as cw  # noqa: E402
from creature_forge import recovery as rc  # noqa: E402
from creature_forge import walk_pipelines as wp  # noqa: E402
from creature_forge.forge_pool import ForgePool  # noqa: E402
from creature_forge.optimize import jsonable  # noqa: E402
from walk_oracle import git_commit, load_creatures, sha256_file  # noqa: E402

BODY4 = ("foot_length", "thigh_length", "shank_length", "torso_mass")


def census_decisions(family: int) -> list[dict]:
    opt = ["opt_timing", "opt_posture", "opt_feedback", "opt_stride", "opt_body"] + (["opt_placement"] if family == 17 else [])
    morph = ["foot_x1_5", "torso_x0_7", "torque_x1_5", "legs_x0_8", "legs_x1_2", "similarity"]
    rounds = [opt[0:3], opt[3:6], morph[0:3], morph[3:6]]
    dec = []
    for i, probes in enumerate(rounds, start=1):
        dec.append({"round": i, "kind": "probes", "returned": probes})
        dec.append({"round": i, "kind": "plans", "returned": []})
    return dec


def make_director(method: str, *, creature: str, budget: int, family: int, ledger_path: str | None, noise_seed: int,
                  evidence_mode: str = "full"):
    if method == "cma_joint":
        return wp.FullSpaceDirector(body_params=BODY4)
    if method == "cma_ctrl":
        return wp.FullSpaceDirector()
    if method == "fix":
        return wp.FixedDirector(probes=("opt_placement", "opt_body", "opt_posture") if family == 17 else ("opt_body", "opt_posture", "opt_timing"))
    if method == "rand":
        return wp.RandomDirector(seed=int(hashlib.sha256(f"{creature}:{budget}:{noise_seed}".encode()).hexdigest()[:8], 16))
    if method == "census":
        return wp.ScriptedDirector(census_decisions(family))
    if method in ("ai", "ai_nogait"):
        evidence_mode = "no_gait" if method == "ai_nogait" else "full"
        from creature_forge import director as dr
        from creature_forge.inference_ledger import Caps, InferenceLedger
        led = InferenceLedger(ledger_path, caps=Caps(inv_max_requests=8, inv_max_tokens=160_000)) if ledger_path else None
        return dr.NemotronDirector(mode="live", ledger=led, evidence_mode=evidence_mode,
                                   investigation_id=f"wr-{hashlib.sha256(f'{creature}:{budget}:{noise_seed}'.encode()).hexdigest()[:10]}")
    raise ValueError(f"unknown method {method!r}")


def run_unit(proto: dict, name: str, body: dict, method: str, budget: int, noise_seed: int, pool, ledger_path) -> dict:
    campaign = proto["campaign"]
    k = proto["seeds"]
    ns_role = {"diag": "probe", "train": "train", "screen": "screen", "validate": "validate", "confirm": "confirm"}  # diag = the "probe" namespace
    seeds = {r: list(cg.walkrec_seed_block(campaign, ns_role[r], name, int(k[r]))) for r in ns_role}
    family = int(proto["family"])
    st = proto["settings"]
    t0 = time.perf_counter()
    director = make_director(method, creature=name, budget=budget, family=family, ledger_path=ledger_path, noise_seed=noise_seed)
    probe_budget = int(round(float(st["probe_budget_frac"]) * budget))
    rounds = 4 if method == "census" else int(st["rounds"])
    rec = wp.run_pipeline(body, director, total_budget=budget, family=family,
                          seeds={"diag": seeds["diag"], "train": seeds["train"], "screen": seeds["screen"]},
                          noise_seed=noise_seed, pool=pool, probe_budget=probe_budget, rounds=rounds,
                          screen_top_k=int(st["screen_top_k"]), screen_n=int(st["screen_n"]), director_name=method)
    ai_record = director.record() if hasattr(director, "record") else None
    final = rec["final"]
    original = {"body": body, "vector": list(cw.R2_WINNER)}
    assessment = None
    if method != "census":
        assessment = rc.assess(original, {"body": final["body"], "vector": final["vector"]}, seeds["validate"], seeds["confirm"],
                               pool=pool)
    return jsonable({"unit": f"{name}|{method}|{budget}|{noise_seed}", "creature": name, "method": method, "budget": budget,
                     "noise_seed": noise_seed, "family": family, "body": body, "features": cg.features(body),
                     "region": cg.region_of(cg.features(body)), "seeds": seeds, "pipeline": rec, "director_record": ai_record,
                     "status": (assessment or {}).get("status"), "assessment": assessment,
                     "rollouts": {"method": rec["used"],
                                  "assessment": 0 if assessment is None else assessment["rollouts"]["validation"] + assessment["rollouts"]["confirmation"]},
                     "wall_s": time.perf_counter() - t0})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--panel", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--methods")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--ledger", help="inference ledger path for the ai method (default: env CF_INFERENCE_LEDGER)")
    a = ap.parse_args()
    ppath = Path(a.protocol)
    proto = json.loads(ppath.read_text(encoding="utf-8"))
    psha = sha256_file(ppath)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done, used = set(), 0.0
    if out.exists():
        if not a.resume:
            raise SystemExit(f"{out} exists; use --resume (completed units are skipped, never rerun)")
        for line in out.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["protocol_sha256"] != psha:
                raise SystemExit("results file was produced under a different protocol")
            done.add(r["unit"])
            used += r["rollouts"]["method"] + r["rollouts"]["assessment"]
    creatures, panel_sha = load_creatures(proto, Path(a.panel))
    methods = a.methods.split(",") if a.methods else [m["id"] for m in proto["methods"]]
    shard = tuple(int(x) for x in a.shard.split("/")) if a.shard else None
    cap = float(proto["rollout_cap"])
    if shard:
        mine = sum(1 for i in range(len(creatures)) if i % shard[1] == shard[0])
        cap = cap * mine / max(1, len(creatures))
    commit = git_commit()
    with ForgePool(max_workers=a.workers) as pool:
        for idx, (name, body) in enumerate(creatures.items()):
            if shard and idx % shard[1] != shard[0]:
                continue
            for m in proto["methods"]:
                if m["id"] not in methods:
                    continue
                for budget in m["budgets"]:
                    for ns in proto["replicates"]:
                        unit = f"{name}|{m['id']}|{budget}|{ns}"
                        if unit in done:
                            continue
                        worst = int(budget) + 2 * rc.VALIDATE_N + rc.CONFIRM_N * 2
                        if used + worst > cap:
                            print(json.dumps({"stop": "rollout cap", "used": used, "cap": cap}), flush=True)
                            return 2
                        try:
                            rec = run_unit(proto, name, body, m["id"], int(budget), int(ns), pool, a.ledger)
                        except Exception as exc:  # noqa: BLE001 - recorded as an error unit (never silently dropped)
                            rec = {"unit": unit, "creature": name, "method": m["id"], "budget": int(budget), "noise_seed": int(ns),
                                   "status": "UNIT_ERROR", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:],
                                   "rollouts": {"method": 0, "assessment": 0}}
                        rec.update({"protocol_id": proto["id"], "protocol_sha256": psha, "code_commit": commit, "panel_sha256": panel_sha,
                                    "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                        with out.open("a", encoding="utf-8") as f:
                            f.write(json.dumps(jsonable(rec), separators=(",", ":")) + "\n")
                        used += rec["rollouts"]["method"] + rec["rollouts"]["assessment"]
                        print(json.dumps({"unit": unit, "status": rec.get("status"), "rollouts": rec["rollouts"],
                                          "used_total": used, "wall_s": round(rec.get("wall_s", 0.0), 1)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
