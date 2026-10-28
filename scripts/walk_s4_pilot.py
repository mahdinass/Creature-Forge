"""S4a development pilot: closed-loop control-law (mechanism) invention vs compute-matched non-AI structure.

For every (creature, method) unit of the protocol: `mech_pipelines.run_mech_pipeline` with that method's director at the
same TOTAL rollout budget (everything charged), then `mech_pipelines.assess_final` (full_recovery_v1, not charged, identical
for every method). Start = the 15-D R2 controller (no foot placement). Seeds per creature shared by all methods (paired).
One JSON line per completed unit (append-only); --resume skips completed units, never reruns.

Methods: fix15, generic, randmech, expert (DSL foot-placement reference), ai_1shot, ai_iter (MechDirector, LIVE).

    python scripts/walk_s4_pilot.py --protocol experiments/walk_recovery/mech_pilot/protocol_s4a.json \
        --panel <panel.json> --out artifacts/walk_recovery/s4a/shard0.jsonl --shard 0/12 --workers 3 [--methods ...] [--resume]
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
from creature_forge import mech_pipelines as mp  # noqa: E402
from creature_forge.forge_pool import ForgePool  # noqa: E402
from creature_forge.optimize import jsonable  # noqa: E402
from walk_oracle import git_commit, load_creatures, sha256_file  # noqa: E402


def _h(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def make_director(method: str, *, creature: str, noise_seed: int, ledger_path: str | None):
    if method == "fix15":
        return mp.Fix15Director()
    if method == "generic":
        return mp.GenericDirector()
    if method == "randmech":
        return mp.RandMechDirector(seed=_h(f"randmech:{creature}:{noise_seed}"))
    if method == "expert":
        return mp.ExpertDirector()
    if method in ("ai_1shot", "ai_iter"):
        from creature_forge import director as dr
        from creature_forge import mech_director as md
        from creature_forge.inference_ledger import Caps, InferenceLedger
        led = InferenceLedger(ledger_path, caps=Caps(inv_max_requests=12, inv_max_tokens=260_000)) if ledger_path else \
            InferenceLedger(caps=Caps(inv_max_requests=12, inv_max_tokens=260_000))
        return md.MechDirector("one_shot" if method == "ai_1shot" else "iterative", source="live", ledger=led,
                               investigation_id=f"m4-{hashlib.sha256(f'{method}:{creature}:{noise_seed}'.encode()).hexdigest()[:10]}",
                               order_seed=_h(f"order:{method}:{creature}:{noise_seed}"), reference=dr.reference_features(),
                               method=method)
    raise ValueError(f"unknown method {method!r}")


def run_unit(proto, name, body, method, noise_seed, pool, ledger_path) -> dict:
    campaign = proto["campaign"]
    k = proto["seeds"]
    ns_role = {"diag": "probe", "train": "train", "screen": "screen", "validate": "validate", "confirm": "confirm"}
    seeds = {r: list(cg.walkrec_seed_block(campaign, ns_role[r], name, int(k[r]))) for r in ns_role}
    st = proto["settings"]
    budget = int(proto["budget"])
    t0 = time.perf_counter()
    director = make_director(method, creature=name, noise_seed=noise_seed, ledger_path=ledger_path)
    mode = "one_shot" if method == "ai_1shot" else "iterative"
    rec = mp.run_mech_pipeline(body, director, total_budget=budget,
                               seeds={"diag": seeds["diag"], "train": seeds["train"], "screen": seeds["screen"]},
                               noise_seed=noise_seed, pool=pool, probe_budget=int(round(float(st["probe_budget_frac"]) * budget)),
                               max_rounds=int(st["max_rounds"]), screen_top_k=int(st["screen_top_k"]), screen_n=int(st["screen_n"]),
                               mode=mode, director_name=method)
    final = rec["final"]
    original = {"body": body, "vector": list(cw.R2_WINNER), "mechanisms": []}
    cand = {"body": final["body"], "vector": final["vector"], "mechanisms": final.get("mechanisms") or []}
    assessment = mp.assess_final(original, cand, seeds["validate"], seeds["confirm"], pool=pool)
    return jsonable({"unit": f"{name}|{method}|{budget}|{noise_seed}", "creature": name, "method": method, "budget": budget,
                     "noise_seed": noise_seed, "body": body, "features": cg.features(body), "region": cg.region_of(cg.features(body)),
                     "seeds": seeds, "pipeline": rec, "director_record": director.record() if hasattr(director, "record") else None,
                     "status": assessment["status"], "assessment": assessment,
                     "rollouts": {"method": rec["used"], "assessment": assessment["rollouts"]["validation"] + assessment["rollouts"]["confirmation"]},
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
    ap.add_argument("--ledger")
    a = ap.parse_args()
    ppath = Path(a.protocol)
    proto = json.loads(ppath.read_text(encoding="utf-8"))
    psha = sha256_file(ppath)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done, used = set(), 0.0
    if out.exists():
        if not a.resume:
            raise SystemExit(f"{out} exists; use --resume")
        for line in out.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["protocol_sha256"] != psha:
                raise SystemExit("results file was produced under a different protocol")
            done.add(r["unit"])
            used += r["rollouts"]["method"] + r["rollouts"]["assessment"]
    creatures, panel_sha = load_creatures(proto, Path(a.panel))
    methods = a.methods.split(",") if a.methods else list(proto["methods"])
    shard = tuple(int(x) for x in a.shard.split("/")) if a.shard else None
    cap = float(proto["rollout_cap"])
    if shard:
        mine = sum(1 for i in range(len(creatures)) if i % shard[1] == shard[0])
        cap = cap * mine / max(1, len(creatures))
    commit = git_commit()
    budget = int(proto["budget"])
    with ForgePool(max_workers=a.workers) as pool:
        for idx, (name, body) in enumerate(creatures.items()):
            if shard and idx % shard[1] != shard[0]:
                continue
            for m in proto["methods"]:
                if m not in methods:
                    continue
                for ns in proto["replicates"]:
                    unit = f"{name}|{m}|{budget}|{ns}"
                    if unit in done:
                        continue
                    if used + budget + 200 > cap:
                        print(json.dumps({"stop": "rollout cap", "used": used, "cap": cap}), flush=True)
                        return 2
                    try:
                        rec = run_unit(proto, name, body, m, int(ns), pool, a.ledger)
                    except Exception as exc:  # noqa: BLE001 - recorded, never silently dropped
                        rec = {"unit": unit, "creature": name, "method": m, "budget": budget, "noise_seed": int(ns), "status": "UNIT_ERROR",
                               "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:],
                               "rollouts": {"method": 0, "assessment": 0}}
                    rec.update({"protocol_id": proto["id"], "protocol_sha256": psha, "code_commit": commit, "panel_sha256": panel_sha,
                                "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                    with out.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(jsonable(rec), separators=(",", ":")) + "\n")
                    used += rec["rollouts"]["method"] + rec["rollouts"]["assessment"]
                    print(json.dumps({"unit": unit, "status": rec.get("status"), "rollouts": rec["rollouts"], "used_total": used,
                                      "wall_s": round(rec.get("wall_s", 0.0), 1)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
