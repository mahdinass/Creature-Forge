"""FA-1 finalize: add comparator columns to episode_index.csv and repair_decisions.csv (observed comparators only), and write
FA1_MANIFEST.json (hashes, record counts, provenance). Read-only with respect to the repository."""
from __future__ import annotations

import collections
import csv
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_f4 as F4  # noqa: E402
import fa1_load as L  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = lambda x: x in (True, "True")  # noqa: E731


def rw(name, rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main():
    E = list(csv.DictReader(open(os.path.join(OUT, "episode_index.csv"), encoding="utf-8")))
    R = list(csv.DictReader(open(os.path.join(OUT, "repair_decisions.csv"), encoding="utf-8")))
    data = L.load_eval()
    after_stop = {}
    for arm in ("A3v5", "A4x"):
        for _, _, r in data[arm]:
            c, _ = F4.episode(r)
            after_stop[(r["instance_id"], arm)] = (c["exp_after_engine_stop"], c["exp_not_engine_top"], c["exp_engine_top"], c["hyp_added"])
    by = collections.defaultdict(dict)
    for e in E:
        by[e["instance_id"]][e["arm"]] = e
    for e in E:
        ref = by[e["instance_id"]]["A1e6"]
        e["repair_seq_differs_from_A1e6"] = "" if e["arm"] == "A1e6" else e["tool_sequence"] != ref["tool_sequence"]
        e["first_tool_differs_from_A1e6"] = "" if e["arm"] == "A1e6" else (e["tool_sequence"].split(">")[0] != ref["tool_sequence"].split(">")[0])
        e["full_A1e6_same_instance"] = ref["full"]
        e["arms_full_on_instance"] = sum(B(by[e["instance_id"]][a]["full"]) for a in ("A1e", "A1e6", "A3v5", "A4x"))
        s = after_stop.get((e["instance_id"], e["arm"]))
        e["nemo_exps_after_engine_stop"] = s[0] if s else ""
        e["nemo_exps_not_engine_top"] = s[1] if s else ""
        e["nemo_exps_engine_top"] = s[2] if s else ""
        e["nemo_hypotheses_added"] = s[3] if s else ""
    rw("episode_index.csv", E)
    # repair rows: observed comparators on the same instance (never inferred)
    sub_by = collections.defaultdict(list)
    for e in E:
        sub_by[e["instance_id"]].append((e["arm"], e["final_repair_tool"], B(e["full"])))
    for x in R:
        comps = [f"{a}:{'FULL' if f else 'fail'}" for a, t, f in sub_by[x["instance_id"]] if a != x["arm"] and t == x["tool"]]
        x["other_arms_submitting_same_tool"] = ";".join(comps)
        x["comparator_procedure_equivalent"] = "no (different diagnosis/budget trajectory; outcome observed, not counterfactual)" if comps else "no comparator"
    rw("repair_decisions.csv", R)

    # ---------------- manifest
    def sha(p):
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()

    def git(*a):
        return subprocess.run(["git", "-C", L.REPO, *a], capture_output=True, text=True).stdout.strip()

    src = ["creature_forge/belief_engine.py", "creature_forge/has_agent.py", "creature_forge/has_cases.py", "creature_forge/has_memory.py",
           "creature_forge/repair_learning.py", "creature_forge/hdb_workbench.py", "creature_forge/hdb_evidence.py",
           "creature_forge/hidden_plant.py", "creature_forge/hdb_bench.py", "creature_forge/recovery.py", "creature_forge/verdict.py",
           "creature_forge/fault_bench.py", "creature_forge/morphology.py", "creature_forge/sandbox.py",
           "scripts/hdb_agent_run.py", "scripts/ds1_report.py", "scripts/ds1_stream.py", "scripts/ds1_pilot.py", "scripts/ds1_offline.py",
           "scripts/ds1_instances.py", "scripts/stage2_failure_analysis.py",
           "docs/DS1_REPORT.md", "docs/DS1_PROTOCOL.md", "docs/STAGE2_REPORT.md", "docs/PROJECT_STATE.md",
           "experiments/causal_engineer/dev/hdb/DS1_RESULTS.md", "experiments/causal_engineer/dev/hdb/STAGE2_FAILURE_ANALYSIS.md",
           "experiments/causal_engineer/dev/hdb/ds1/OFFLINE.md", "experiments/causal_engineer/dev/hdb/ds1/PILOT.md",
           "experiments/causal_engineer/dev/hdb/ds1/engine_v6_settings.json", "experiments/causal_engineer/dev/hdb/ds1/ds1_eval_instances.json",
           "experiments/causal_engineer/dev/hdb/ds1/ds1_stream_instances.json", "experiments/causal_engineer/dev/hdb/ds1/cases_init.json",
           "experiments/causal_engineer/dev/hdb/ds1/offline_report.json"]
    raw = sorted(glob.glob(os.path.join(L.EVAL_DIR, "*.jsonl"))) + [os.path.join(L.DS1_DIR, n) for n in
           ("gm_A1e6.c.jsonl", "pilot_A1e.c.jsonl", "pilot_A1e6.c.jsonl")] + [os.path.join(L.HDB_DIR, "s2DC_exp_A1e.jsonl")] + \
          sorted(glob.glob(os.path.join(L.STREAM_DIR, "r*_*.jsonl"))) + sorted(glob.glob(os.path.join(L.STREAM_DIR, "cases_upd_r*.json"))) + \
          [os.path.join(L.STREAM_DIR, "order.json"), os.path.join(L.HDB_DIR, "ds1_all.tgz")]
    # archive vs extracted copies of the LLM-arm eval files
    dup = {}
    for f in glob.glob(os.path.join(L.HDB_DIR, "ds1", "eval_*.jsonl")):
        g = os.path.join(L.EVAL_DIR, os.path.basename(f))
        dup[os.path.basename(f)] = os.path.exists(g) and sha(f) == sha(g)
    counts = {a: len(v) for a, v in data.items()}
    man = {
        "investigation": "FA-1 failure mechanism localization (read-only)", "date": "2026-10-20",
        "repository": "mahdinass/Creature-Forge", "branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"),
        "expected_commit": "ea9e729", "worktree_porcelain_at_end": git("status", "--porcelain"),
        "source_blob_hashes_at_HEAD": {p: git("rev-parse", f"HEAD:{p}") for p in src},
        "raw_records": {os.path.relpath(p, L.REPO).replace("\\", "/"): {"sha256": sha(p), "bytes": os.path.getsize(p)} for p in raw if os.path.exists(p)},
        "raw_provenance": {
            "dev_eval_2": "artifacts/vm/ds1/eval/eval_{A1e,A1e6,A3v5,A4x}_{s0..s5,c}.jsonl; A1e/A1e6 from the batch VM (pulled to artifacts/vm/ds1), "
                          "A3v5/A4x also inside ds1_all.tgz (extracted copy at artifacts/vm/hdb/artifacts/hdb/ds1/); byte-identity checked",
            "G-m": "v6 side artifacts/vm/ds1/gm_A1e6.c.jsonl (12) + pilot_A1e6.c.jsonl (1); v5 side artifacts/vm/hdb/artifacts/hdb/s2DC_exp_A1e.jsonl (12, Stage-2 init-base compositions) + artifacts/vm/ds1/pilot_A1e.c.jsonl (1); pairing as scripts/ds1_pilot.py",
            "stream": "artifacts/vm/hdb/artifacts/hdb/ds1/stream/r{0..3}_{upd,frz}_*.jsonl, cases_upd_r{0..4}.json, order.json (extracted from ds1_all.tgz)",
            "G-a": "experiments/causal_engineer/dev/hdb/ds1/cases_init.json (947 rows) and offline_report.json; no model was refitted"},
        "archive_copy_identity_eval_files": dup,
        "records_loaded": {"dev_eval_2_per_arm": counts, "dev_eval_unique_instances": len({r['instance_id'] for v in data.values() for _, _, r in v}),
                           "G-m_pairs": 13, "stream_pairs": 20, "assimilation_events": 183, "assimilation_skips": 98},
        "dedup_exclusion_checks": "36 records per arm, 36 unique instance ids per arm, no duplicates; every stream jsonl holds exactly one record; "
                                  "eval files in ds1_all.tgz are byte-identical to the batch-pulled copies (see archive_copy_identity_eval_files)",
        "derived_tables": {"episode_index.csv": "fa1_extract.py + fa1_finalize.py <- dev-eval-2 records",
                           "repair_decisions.csv": "fa1_extract.py + fa1_finalize.py <- repair logs and Nemotron direct repairs",
                           "feedback_events.csv": "fa1_extract.py <- engine events assimilated_check / assimilation_skipped + history snapshots",
                           "feedback_replay.csv": "fa1_f2b.py <- feedback_events.csv (count-bound replay of each update)",
                           "compound_cases.csv": "fa1_f3.py <- G-m and dev-eval composition records",
                           "stream_pairs.csv": "fa1_f5.py <- stream records (incl. the CASE EVIDENCE text Nemotron was shown)"},
        "scripts": sorted(os.path.basename(p) for p in glob.glob(os.path.join(OUT, "scripts", "*"))),
        "analysis_outputs": sorted(os.path.basename(p) for p in glob.glob(os.path.join(OUT, "out_*.txt"))),
        "python": {"executable": sys.executable, "version": platform.python_version(), "packages_used": ["numpy"], "flags": "-I, PYTHONDONTWRITEBYTECODE=1"},
        "commands": ["python -I scripts/survey.py artifacts/vm/ds1/eval", "python -I scripts/fa1_extract.py", "python -I scripts/fa1_f1.py",
                     "python -I scripts/fa1_f1b.py", "python -I scripts/fa1_tools.py low_ground_friction", "python -I scripts/fa1_f2.py",
                     "python -I scripts/fa1_f2b.py", "python -I scripts/fa1_f3.py", "python -I scripts/fa1_f4.py", "python -I scripts/fa1_f5.py",
                     "python -I scripts/fa1_misc.py", "python -I scripts/fa1_trace.py <record> <line>", "python -I scripts/fa1_finalize.py",
                     "plus inline read-only python -c inspections recorded in the session (tool absence, foot_friction bounds, partial updates)"],
        "simulations_run": False, "network_calls": False, "paid_resources": False, "repository_modified": False,
        "sealed_or_heldout_accessed": False,
        "limitations": [
            "Per-seed twin predictions of assimilated checks are not stored (only per-structure counts of each structure's best particle), so prediction disagreement is a count lower bound.",
            "Posterior before/after of assimilations is stored for the top 4 (event) and top 8 (snapshot) structures only.",
            "Only the submitted design of each episode was verified; outcomes of non-submitted candidates and untried tools are unobserved.",
            "No intermediate candidate list for compositions beyond the enumerated pairs and the 12 generic-screen survivors.",
            "Validation per-seed scores are not in the episode records (only status, walking fraction and reasons).",
            "Stage-2 per-episode records were not re-analysed; Stage-2 figures are taken from STAGE2_FAILURE_ANALYSIS.md (secondary).",
            "G-a R-head fold choices were not recomputed (no refit); engine/random/oracle baselines were recomputed from cases_init.json."]}
    json.dump(man, open(os.path.join(OUT, "FA1_MANIFEST.json"), "w", encoding="utf-8"), indent=1)
    print("manifest written; eval archive identity:", dup)


if __name__ == "__main__":
    main()
