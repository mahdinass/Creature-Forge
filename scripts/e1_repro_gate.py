"""E-1 gate G-R (docs/E1_PROTOCOL.md §5): the frozen arm code at the registration commit must reproduce stored fresh-dev records
exactly (dev data only; the sealed side is not touched). Picks the first --n eligible instances of the stored A1c5 file in
sha256(instance id) order, rebuilds them from the dev bases and dev thresholds, re-checks eligibility, runs A0 and A1 with
e1_run, and compares with the stored records: eligibility check rows, verification status, validation walking fraction,
submitted design (body and vector), plant and twin ledger use. Also runs K0n on the same instances (smoke; no reference).

Usage (VM): python scripts/e1_repro_gate.py --records-dir artifacts/hdb --thresholds artifacts/hdb/thresholds_dev.json
            --stop-model experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json --n 4 --arm A1 --workers 7 --out <dir>
            (one process per arm: --arm A0 | A1 | K0n; then --compare)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge.forge_pool import ForgePool                   # noqa: E402
import e1_run                                                     # noqa: E402

STORED = {"A0": "fresh_A0.jsonl", "A1": "fresh_A1c5.jsonl"}


def pick(records_dir: str, n: int) -> list[str]:
    rows = [json.loads(l) for l in open(os.path.join(records_dir, STORED["A1"]), encoding="utf-8") if l.strip()]
    ids = [r["instance_id"] for r in rows if r.get("verification")]
    return sorted(ids, key=lambda i: hashlib.sha256(i.encode()).hexdigest())[:n]


def rebuild(ids: list[str], thresholds: dict, pool) -> list[dict]:
    bases = {b["base_id"]: b for b in hb.load_bases("dev")}
    out = []
    for iid in ids:
        base_id, fam, sev = iid.rsplit(":", 2)
        inst = hb.make_instance_v2(bases[base_id], fam, int(sev), thresholds)
        out.append(hb.check_eligibility(inst, pool=pool))
    return out


def summary(rec: dict) -> dict:
    led = rec.get("ledger") or (rec.get("engine") or {}).get("ledger") or {}
    designs = [{"body": d["body"], "vector": d["vector"]} for d in rec["designs"]]   # every design the arm created, in order
    return {"status": rec["verification"]["status"], "walking_frac": rec["verification"]["walking_frac"],
            "check": rec["check"], "plant_used": led.get("used"), "twin_used": (led.get("twin") or {}).get("used"),
            "n_designs": len(designs), "submitted": rec.get("submitted"),
            "designs_sha": hashlib.sha256(json.dumps(designs, sort_keys=True).encode()).hexdigest()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records-dir", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--stop-model", required=True)
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--arm", choices=e1_run.ARMS)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ids = pick(a.records_dir, a.n)
    if a.compare:
        report = {"ids": ids, "arms": {}}
        ok = True
        for arm, fname in STORED.items():
            stored = {r["instance_id"]: r for r in map(json.loads, open(os.path.join(a.records_dir, fname), encoding="utf-8"))
                      if r.get("verification")}
            new = {r["instance_id"]: r for r in map(json.loads, open(os.path.join(a.out, f"{arm}.jsonl"), encoding="utf-8"))}
            rows = []
            for i in ids:
                s_old, s_new = summary(stored[i]), summary(new[i])
                same = s_old == s_new
                ok &= same
                rows.append({"instance_id": i, "match": same, "stored": s_old, "rerun": s_new})
            report["arms"][arm] = rows
        k0n = os.path.join(a.out, "K0n.jsonl")
        if os.path.exists(k0n):
            report["K0n_smoke"] = [{"instance_id": r["instance_id"], "status": r["verification"]["status"]}
                                   for r in map(json.loads, open(k0n, encoding="utf-8"))]
        report["gate_G_R"] = "PASS" if ok else "FAIL"
        json.dump(report, open(os.path.join(a.out, "gate_G_R.json"), "w", encoding="utf-8"), indent=1, sort_keys=True)
        print(report["gate_G_R"], json.dumps({arm: [r["match"] for r in rows] for arm, rows in report["arms"].items()}))
        return
    th = json.load(open(a.thresholds, encoding="utf-8"))
    st = e1_run.settings(a.arm, a.stop_model)
    with ForgePool(max_workers=a.workers) as pool, open(os.path.join(a.out, f"{a.arm}.jsonl"), "w", encoding="utf-8") as fh:
        for inst in rebuild(ids, th, pool):
            if not inst["eligible"]:
                raise SystemExit(f"{inst['instance_id']} is no longer eligible: {inst['reason']}")
            rec = e1_run.run_arm(a.arm, inst, pool, st)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(a.arm, inst["instance_id"], rec["verification"]["status"], round(rec["wall_s"]), flush=True)


if __name__ == "__main__":
    main()
