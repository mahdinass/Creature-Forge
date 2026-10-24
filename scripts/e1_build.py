"""E-1 test-bench build (docs/E1_PROTOCOL.md §4): the ONLY step that opens the sealed test side, run once on the VM after the
registration commit is pushed. Physics only: thresholds, instances, eligibility. No arm, oracle or verification runs here.

Inputs: experiments/e1/protocol.json (strata, quotas, sampling seed, caps). Outputs in --out-dir (resumable):
  thresholds.json        every threshold computed (key base|family|variant)
  evaluated.jsonl        one line per evaluated candidate (instance or None, eligibility)
  instances.jsonl        the accepted sample (hidden instance records, eligible only), registered order
  sample_log.jsonl       the sampler's decision sequence (accept / reject / skip_cap)
  summary.json           per-stratum quota, accepted, examined; rollouts; protocol sha256

Usage (VM): python scripts/e1_build.py --protocol experiments/e1/protocol.json --workers 7 --out-dir <dir>
            [--rehearsal-dev]   (dev bases and dev families only; never the sealed side)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge import hdb_testbench as tb                    # noqa: E402
from creature_forge.forge_pool import ForgePool                   # noqa: E402

def _threshold_job(args):
    base, fam, var = args
    return tb.threshold(base, fam, var)


def _candidate_job(args):
    base, cand, ths = args
    inst = tb.make_instance(base, cand, ths)
    return {"instance": None if inst is None else hb.check_eligibility(inst)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--batch", type=int, default=28)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--rehearsal-dev", action="store_true")
    a = ap.parse_args()
    raw = open(a.protocol, "rb").read()
    proto = json.loads(raw)
    sp = proto["sampling"]
    quotas = dict(sp["quotas"])
    if a.rehearsal_dev:
        quotas = {s: q for s, q in quotas.items() if s in hb.FAMILY_SPECS}
        bases = hb.load_bases("dev")
    else:
        bases = hb.load_bases("test")
    if not bases:
        raise SystemExit("no bases loaded")
    by_id = {b["base_id"]: b for b in bases}
    os.makedirs(a.out_dir, exist_ok=True)
    p_th, p_ev = os.path.join(a.out_dir, "thresholds.json"), os.path.join(a.out_dir, "evaluated.jsonl")
    ths = json.load(open(p_th, encoding="utf-8")) if os.path.exists(p_th) else {}
    ordered = {s: tb.candidates(s, bases, int(sp["seed"])) for s in quotas}
    smp = tb.Sampler(ordered, quotas, per_base=int(sp["per_base"]), per_base_family=int(sp["per_base_stratum"]))
    if os.path.exists(p_ev):
        for line in open(p_ev, encoding="utf-8"):
            r = json.loads(line)
            smp.results[r["cand"]] = {"instance": r["instance"]}
        smp.advance()
    # ForgePool is spawn-based: each job carries its base record
    with ForgePool(max_workers=a.workers) as pool, open(p_ev, "a", encoding="utf-8") as fev:
        while not smp.done:
            need = smp.next_needed(a.batch)
            if not need:
                break
            th_jobs = sorted({(c["base_id"], f, v) for c in need for f, v in tb.needed_thresholds(c)
                              if tb.th_key(c["base_id"], f, v) not in ths})
            for _, r in pool.imap(_threshold_job, [(by_id[b], f, v) for b, f, v in th_jobs]):
                if isinstance(r, tuple):
                    raise SystemExit(f"threshold job failed: {r}")
                ths[tb.th_key(r["base_id"], r["family"], r["variant"])] = r
            with open(p_th + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(ths, fh, sort_keys=True)
            os.replace(p_th + ".tmp", p_th)
            jobs = [(by_id[c["base_id"]], c, {k: ths[k] for k in (tb.th_key(c["base_id"], f, v) for f, v in tb.needed_thresholds(c))}) for c in need]
            for i, r in pool.imap(_candidate_job, jobs):
                if isinstance(r, tuple):
                    raise SystemExit(f"candidate job failed: {r}")
                cid = tb.cand_id(need[i])
                fev.write(json.dumps({"cand": cid, "instance": r["instance"]}, sort_keys=True) + "\n")
                fev.flush()
                smp.results[cid] = r
            smp.advance()
            print(json.dumps({s: v["accepted"] for s, v in smp.summary().items()}), flush=True)
    order = [inst for s in smp.names for inst in smp.accepted[s]]
    with open(os.path.join(a.out_dir, "instances.jsonl"), "w", encoding="utf-8") as fh:
        for inst in order:
            fh.write(json.dumps(inst, sort_keys=True) + "\n")
    with open(os.path.join(a.out_dir, "sample_log.jsonl"), "w", encoding="utf-8") as fh:
        for row in smp.log:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    rollouts = sum(int(t.get("rollouts", 0)) for t in ths.values()) + hb.CHECK_N * len(smp.results)
    summary = {"protocol_sha256": hashlib.sha256(raw).hexdigest(), "rehearsal_dev": a.rehearsal_dev,
               "n_bases": len(bases), "strata": smp.summary(), "n_instances": len(order),
               "n_evaluated": len(smp.results), "n_thresholds": len(ths), "rollouts_approx": rollouts}
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
