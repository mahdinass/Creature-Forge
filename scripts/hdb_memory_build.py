"""Build the HaS experience memory (phase 3, Stage 2) from DEVELOPMENT investigations on the experience bases only.

Steps:
1. episode summaries (deterministic facts) from hdb_vs_run / hdb_agent_run records;
2. Nemotron writes dossiers from an evidence digest;
3. the code computes each dossier's support;
4. Nemotron revises / retires dossiers against that support;
5. the code recomputes support;
6. the memory is saved frozen.
`--exclude-families` builds a leave-family-out memory (to measure transfer to unfamiliar mechanisms and negative transfer).

Usage (VM): python scripts/hdb_memory_build.py --records artifacts/hdb/vs5_A1c.jsonl artifacts/hdb/fresh_A1c5.jsonl
            --split-file experiments/causal_engineer/dev/hdb/stage2_split.json --out artifacts/hdb/memory_v1.json
            [--exclude-families clock_fault,short_feet] [--source scripted --fixture f.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from creature_forge import has_memory as hm                       # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", nargs="+", required=True)
    ap.add_argument("--split-file", required=True)
    ap.add_argument("--exclude-families", default="")
    ap.add_argument("--thresholds", required=True, help="to reconstruct each dev instance's true deviation (post-mortem)")
    ap.add_argument("--rounds", type=int, default=2, help="revision rounds")
    ap.add_argument("--source", choices=["live", "scripted"], default="live")
    ap.add_argument("--fixture", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    split = json.load(open(a.split_file, encoding="utf-8"))
    exp_bases = set(split["experience_bases"])
    excl = {f for f in a.exclude_families.split(",") if f}
    th = json.load(open(a.thresholds, encoding="utf-8"))
    bases = {b["base_id"]: b for b in hb.load_bases("dev")}
    summaries, skipped = [], {"not_experience_base": 0, "excluded_family": 0, "no_engine": 0}
    for path in a.records:
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            if "engine" not in r or "verification" not in r:
                skipped["no_engine"] += 1
                continue
            if r["instance_id"].rsplit(":", 2)[0] not in exp_bases:
                skipped["not_experience_base"] += 1
                continue
            if r.get("family") in excl:
                skipped["excluded_family"] += 1
                continue
            s = hm.episode_summary(r)
            base_id, fam, sev = r["instance_id"].rsplit(":", 2)
            inst = hb.make_instance_v2(bases[base_id], fam, int(sev), th, gap=False)
            s["true_deviation"] = inst["plant"]["deviation"] if inst else None
            summaries.append(s)
    cfg = None
    if a.source == "live":
        from ce_eval import thinking_config
        cfg = thinking_config()
    fixture = json.load(open(a.fixture, encoding="utf-8")) if a.fixture else None
    con = hm.Consolidator(source=a.source, config=cfg, fixture=fixture, investigation_id="memory-build")
    mem = hm.Memory([], frozen=False)
    w = con.write(summaries, mem)
    mem.refresh_support(summaries)
    support_after_write = {d["id"]: dict(d["support"]) for d in mem.dossiers.values()}
    r = []
    for _ in range(a.rounds):
        r.append(con.revise(summaries, mem))
        mem.refresh_support(summaries)
    meta = {"records": a.records, "n_summaries": len(summaries), "skipped": skipped, "excluded_families": sorted(excl),
            "experience_bases": len(exp_bases), "write": w, "revise": r, "support_after_write": support_after_write,
            "consolidator": con.record()}
    mem.frozen = True
    mem.save(a.out, meta)
    print(json.dumps({"summaries": len(summaries), "skipped": skipped, "write": w, "revise": r,
                      "dossiers": {d["id"]: [d["title"], d["status"], d["support"]["precision"], d["support"]["recall"],
                                             d["support"]["recommended_repair"], d["support"]["other_repairs"]]
                                   for d in mem.dossiers.values()},
                      "cost_usd": meta["consolidator"]["cost_usd"]}, indent=1))


if __name__ == "__main__":
    main()
