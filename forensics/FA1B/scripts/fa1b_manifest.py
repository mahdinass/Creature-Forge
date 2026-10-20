"""FA-1B manifest: input/output checksums, source blob hashes at the pinned commit, record counts, environment, git state.
Read-only: git is queried with rev-parse / status / cat-file only."""
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L

SOURCES = ["creature_forge/belief_engine.py", "creature_forge/hdb_workbench.py", "creature_forge/hdb_evidence.py",
           "creature_forge/hidden_plant.py", "creature_forge/morphology.py", "creature_forge/eng_tools.py",
           "creature_forge/fault_bench.py", "creature_forge/walk_opt.py", "creature_forge/locomotion.py",
           "creature_forge/challenges.py", "creature_forge/recovery.py", "creature_forge/verdict.py", "creature_forge/arena.py",
           "creature_forge/has_agent.py", "creature_forge/hdb_bench.py", "creature_forge/creature_walk.py",
           "creature_forge/sandbox.py", "creature_forge/interventions.py", "scripts/hdb_agent_run.py", "scripts/ds1_stop_data.py"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git(*a, cwd=L.REPO):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True).stdout.strip()


def rel(p, base):
    return os.path.relpath(p, base).replace("\\", "/")


def main():
    inputs = sorted(glob.glob(os.path.join(L.EVAL_DIR, "eval_*.jsonl"))) + sorted(glob.glob(os.path.join(L.STREAM_DIR, "r*_*.jsonl"))) + \
        [os.path.join(L.REPO, "artifacts/vm/hdb/artifacts/hdb/thresholds_dev.json"), os.path.join(L.DS1_DIR, "ds1_stopdata.jsonl"),
         os.path.join(L.DS1_DIR, "ds1_stopdata_b.jsonl")]
    fa1 = [os.path.join(L.FA1, f) for f in ("episode_index.csv", "feedback_events.csv", "feedback_replay.csv", "repair_decisions.csv")]
    outs = ["FA1B_REPORT.md", "FA1B_SELECTED_EVIDENCE.md", "claim_audit.md", "measurement_findings.md", "metric_path_matrix.csv",
            "tool_availability.csv", "partial_update_cases.csv", "feedback_reachability.csv", "scripts/_friction_feasibility.json"]
    scripts = sorted(glob.glob(os.path.join(L.HERE, "fa1b_*.py")))
    logs = sorted(glob.glob(os.path.join(L.OUT, "logs", "out_*.txt")))
    ev, st = L.load_eval(), L.load_stream()
    man = {
        "investigation": "FA-1B read-only implementation and metric correctness audit", "date": "2026-10-20",
        "source_repository": L.REPO.replace("\\", "/"), "source_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "source_commit": git("rev-parse", "HEAD"), "forensic_base_commit": git("rev-parse", "16f174d"),
        "forensic_base_local_dir": L.FA1.replace("\\", "/"),
        "git_status_porcelain_before": "", "git_status_porcelain_after": git("status", "--porcelain"),
        "git_status_note": "before: verified empty at session start (git status --porcelain, HEAD ea9e729); after: recorded by this script",
        "python": sys.version.split()[0], "platform": platform.platform(), "numpy": __import__("numpy").__version__,
        "python_flags": "-I (isolated); no creature_forge import; no MuJoCo",
        "source_blobs_at_commit": {s: git("rev-parse", f"HEAD:{s}") for s in SOURCES},
        "inputs": {rel(p, L.REPO): sha(p) for p in inputs},
        "fa1_inputs": {os.path.basename(p): sha(p) for p in fa1},
        "archive_read_only": {"artifacts/vm/hdb/artifacts/hdb/ds1_all.tgz": sha(os.path.join(L.REPO, "artifacts/vm/hdb/artifacts/hdb/ds1_all.tgz")),
                              "use": "member listing (tar -tzf) and stream scan to stdout (tar -xzOf | grep); never extracted to disk"},
        "other_sources_read": ["Notion page 3ff5d357b5ad8169bd73df21f6263673 (context only)",
                               "Basic Memory project creature-forge, text search 'FA-1 forensic' (no results)",
                               "artifacts/vm/hdb/artifacts/hdb/logs/FINALIZE.log and stream *.log (summary lines only)"],
        "record_counts": {"dev_eval_2_records": len(ev), "dev_eval_2_per_arm": {a: sum(1 for _, _, r in ev if r["arm"] == a) for a in ("A1e", "A1e6", "A3v5", "A4x")},
                          "stream_records": len(st), "assimilated_checks_dev": 183, "assimilation_skips_dev": 98,
                          "twin_budget_exhausted_events_dev": {"update": 8, "add_particles": 27},
                          "stopdata_designs": 678, "tool_screen_rows_dev": 1440, "tool_screen_rows_stream": 400},
        "exclusions": ["pilot, G-m and Stage-2 records not needed for the five questions (not opened)",
                       "sealed-test / held-out-family / Stage-3 data: not accessed",
                       "D2 replay test: pairs with any recorded weight < 0.01 excluded (4-decimal rounding)",
                       "C: refusals inside add_particles (new particles) are not registration refusals and are excluded from partial_update_cases"],
        "scripts_executed": {rel(p, L.OUT): sha(p) for p in scripts},
        "script_stdout_logs": {rel(p, L.OUT): sha(p) for p in logs},
        "outputs": {o: sha(os.path.join(L.OUT, o)) for o in outs if os.path.exists(os.path.join(L.OUT, o))},
        "resources": {"paid_inference": False, "cloud_or_vm_operations": False, "mujoco_rollouts": 0, "network": "Notion read (MCP) only",
                      "package_installs": False, "repository_writes": False, "git_commits_or_pushes": False,
                      "sealed_test_access": False}}
    with open(os.path.join(L.OUT, "FA1B_MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    print("manifest written; git status after:", repr(man["git_status_porcelain_after"]), "HEAD", man["source_commit"])


if __name__ == "__main__":
    main()
