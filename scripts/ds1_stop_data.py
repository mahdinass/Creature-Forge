"""DS-1 stop map v2 data (docs/DS1_PROTOCOL.md §1.4): re-measure submitted development designs on the plant with the
displacement-aware evidence (EvidenceWorkbench: robust16 + walk scores, 20 s stress test, the faulty design's baseline on the
same robust seeds). Labels are the designs' recorded `full_recovery_v1` statuses. Init experience bases only; policy-visible
seed roles only (robust, obs) - never validation or confirmation seeds.

Usage (VM): python scripts/ds1_stop_data.py --records artifacts/hdb/fresh_A1c5.jsonl ... --thresholds artifacts/hdb/thresholds_dev.json
            --out artifacts/hdb/ds1_stopdata.jsonl [--workers 7] [--shard 0/1]
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import has_cases as hc                       # noqa: E402
from creature_forge import hdb_bench as hb                       # noqa: E402
from creature_forge.forge_pool import ForgePool, InlinePool      # noqa: E402
from creature_forge.hdb_evidence import EvidenceWorkbench        # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", nargs="+", required=True)
    ap.add_argument("--split-file", default="experiments/causal_engineer/dev/hdb/stage2_split.json")
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    split = json.load(open(a.split_file, encoding="utf-8"))
    init = set(hc.ds1_init_bases(split))
    th = json.load(open(a.thresholds, encoding="utf-8"))
    bases = {b["base_id"]: b for b in hb.load_bases("dev")}
    designs = collections.defaultdict(list)          # instance id -> [(source file, status, body, vector)]
    for path in a.records:
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            if r.get("eligible") is False or "verification" not in r or hc.base_of(r["instance_id"]) not in init:
                continue
            sub = r.get("submitted", (r.get("repair") or {}).get("design"))
            d = next((x for x in r.get("designs") or [] if x.get("index") == sub), None)
            if d is None:
                continue
            designs[r["instance_id"]].append((os.path.basename(path), r["verification"]["status"], d["body"], d["vector"],
                                              r.get("family")))
    k, n = (int(x) for x in a.shard.split("/"))
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["instance_id"] for l in open(a.out, encoding="utf-8") if l.strip()}
    pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    with pool_cm as pool, open(a.out, "a", encoding="utf-8") as out:
        for i, iid in enumerate(sorted(designs)):
            if i % n != k or iid in done:
                continue
            fam = designs[iid][0][4]
            if fam and fam.startswith("devcomp"):
                from creature_forge import hdb_devcomp
                inst = None
                for p in hdb_devcomp.candidate_pairs():
                    cand = hdb_devcomp.make_instance(bases[hc.base_of(iid)], p, th)
                    if cand is not None and cand["instance_id"] == iid:
                        inst = cand
                        break
            else:
                base_id, f, sev = iid.rsplit(":", 2)
                inst = hb.make_instance_v2(bases[base_id], f, int(sev), th)
            if inst is None:
                continue
            bench = EvidenceWorkbench(hb.policy_view(inst), inst["plant"], total_budget=100000, pool=pool)
            rows = []
            for src, status, body, vec, _ in designs[iid]:
                idx = bench.add_twin_design(body, vec, source=f"record:{src}")
                bench.select(idx)
                c = bench.robustness_check(16)
                bench.select(idx)
                st = bench.stress_test()
                disp = bench.displacement(idx)
                rows.append({"source": src, "status": status, "robust16": c["walking"],
                             "stress4": st["observation"]["n_walking"] if st.get("ok") else None,
                             "disp_pass": None if disp is None else disp["pass"],
                             "disp_median_m": None if disp is None else disp["median_diff_m"],
                             "disp_status": None if disp is None else disp["status"]})
            out.write(json.dumps({"instance_id": iid, "base": hc.base_of(iid), "family": fam, "designs": rows}) + "\n")
            out.flush()
            print(iid, len(rows), flush=True)


if __name__ == "__main__":
    main()
