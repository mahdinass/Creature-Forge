"""DS-1 learning stream (docs/DS1_PROTOCOL.md §5): A4x with an UPDATING experience store vs A4x with the FROZEN initial store, on
the same new stream instances, in the same order, in chronological rounds. After each round only the updating store appends
that round's verified outcomes (repair cases, the scientist's decisions, investigation summaries for dossier support) and
refits its repair-outcome model; the frozen store never changes. Any failed episode (e.g. an authentication failure) stops the
stream: no fallbacks.

Usage (VM): python scripts/ds1_stream.py --instances experiments/causal_engineer/dev/hdb/ds1/stream_instances.json
            --cases-init experiments/causal_engineer/dev/hdb/ds1/cases_init.json --memory artifacts/hdb/memory_ds1_init.json
            --v6 experiments/causal_engineer/dev/hdb/ds1/engine_v6_settings.json --stop-model <map> --out-dir artifacts/hdb/ds1_stream
            [--rounds 6 --per-round 5]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creature_forge.has_cases import CaseStore          # noqa: E402

RUN = "scripts/hdb_agent_run.py"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", required=True)
    ap.add_argument("--cases-init", required=True)
    ap.add_argument("--memory", required=True)
    ap.add_argument("--v6", required=True)
    ap.add_argument("--stop-model", required=True)
    ap.add_argument("--thresholds", default="artifacts/hdb/thresholds_dev.json")
    ap.add_argument("--split-file", default="experiments/causal_engineer/dev/hdb/stage2_split.json")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--per-round", type=int, default=5)
    ap.add_argument("--source", default="live")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    inst = json.load(open(a.instances, encoding="utf-8"))
    # fixed interleaving of single-mechanism and composition instances (one composition per round when available)
    single, comp = list(inst["single"]), list(inst["comp"])
    order = []
    while single or comp:
        order += [("comp", comp.pop(0))] if comp else []
        order += [("single", single.pop(0)) for _ in range(a.per_round - 1) if single]
    os.makedirs(a.out_dir, exist_ok=True)
    json.dump(order, open(os.path.join(a.out_dir, "order.json"), "w"), indent=1)
    upd = os.path.join(a.out_dir, "cases_upd_r0.json")
    if not os.path.exists(upd):
        shutil.copy(a.cases_init, upd)
    status = {"rounds": []}
    for r in range(a.rounds):
        todo = order[r * a.per_round:(r + 1) * a.per_round]
        if not todo:
            break
        nxt = os.path.join(a.out_dir, f"cases_upd_r{r + 1}.json")
        if os.path.exists(nxt):
            upd = nxt
            continue                     # resume: this round already finished
        procs = []
        for kind, iid in todo:
            for tag, store in (("upd", upd), ("frz", a.cases_init)):
                out = os.path.join(a.out_dir, f"r{r}_{tag}_{iid.replace(':', '_')}.jsonl")
                if os.path.exists(out) and os.path.getsize(out) > 0:
                    continue
                cmd = [sys.executable, RUN, "--arm", "A4x", "--split-file", a.split_file, "--which", "stream", "--only", iid,
                       "--thresholds", a.thresholds, "--stop-model", a.stop_model, "--v6", a.v6, "--cases", store,
                       "--memory", a.memory, "--source", a.source, "--workers", "1", "--out", out]
                if kind == "comp":
                    cmd.append("--devcomp")
                log = open(out.replace(".jsonl", ".log"), "w")
                procs.append((tag, iid, out, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)))
        for tag, iid, out, p in procs:
            p.wait()
        failed = [(tag, iid) for tag, iid, out, p in procs
                  if p.returncode != 0 or not os.path.exists(out) or os.path.getsize(out) == 0]
        status["rounds"].append({"round": r, "instances": todo, "failed": failed, "t": time.time()})
        json.dump(status, open(os.path.join(a.out_dir, "status.json"), "w"), indent=1)
        if failed:
            raise SystemExit(f"round {r}: episodes failed {failed}; the stream stops (no fallbacks)")
        recs = []
        for kind, iid in todo:
            out = os.path.join(a.out_dir, f"r{r}_upd_{iid.replace(':', '_')}.jsonl")
            recs += [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
        st = CaseStore.load(upd, frozen=False)
        st.append_records(recs)
        st.save(nxt)
        upd = nxt
        print(f"round {r} done: {len(recs)} outcomes appended to the updating store ({len(st.cases)} cases)", flush=True)


if __name__ == "__main__":
    main()
