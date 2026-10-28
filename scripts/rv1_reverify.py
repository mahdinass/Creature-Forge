"""RV-1 (FA-1C Phase 1A): deterministic re-verification of 8 stored DS-1 submitted designs with full per-seed output.

Each preregistered design is read from its stored DS-1 record (path, line, design index; its 10-digit design hash must match),
its instance is rebuilt exactly as scripts/hdb_agent_run.py builds it (ta1_tool_access.build_instance), and the UNCHANGED
`hdb_bench.verify` (full_recovery_v1) is run. All newly generated per-seed results (original and candidate validation rows,
verdict statistics, confirmation rows) are kept.

What the gate can establish: DS-1 did not retain per-seed verification trajectories, so Phase 1A tests EXACT REPRODUCTION OF
THE AVAILABLE STORED REFERENCE FIELDS, not complete physical identity:
  per instance (7)  eligibility-check labels, walking count, seed count and rollouts; fault strength and multiple
  per design (8)    verification status, validation walking fraction, verdict_v1 status, reasons, rollout accounting
Fail-closed: the run stops at the first instance or design that does not reproduce (or whose new record is incomplete),
writes that row, keeps the output and manifest, prints PAUSE with the discrepancies and exits nonzero. PASS is printed only
after all 7 instance checks and all 8 designs reproduce. This script never decides what follows.

Usage:
  python scripts/rv1_reverify.py --artifacts-root <dir> --records-root <dir>       # dry run: list, caps, hashes, preflight
  python scripts/rv1_reverify.py --execute --phase 1A --approved-by "<owner, date>" --harness-commit <40-hex HEAD> \\
      --max-rollouts 824 --artifacts-root <dir> --records-root <dir> --out <fresh path outside every worktree>.jsonl
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta1_tool_access as ta1                        # noqa: E402

VERSION = "rv1_reverify_v2"
# preregistered designs (FA-1C section E, Phase 1A): id, instance, stored record (file, 1-based line), arm, design index, hash,
# and the stored outcome that must be reproduced exactly (status, validation walking k/24, verdict_v1 status)
DESIGNS = [
    ("R1", "hdb-v1-gen-0073:low_ground_friction:2", "eval_A1e6_s1.jsonl", 1, "A1e6", 4, "bbf27921db", "NOT_RECOVERED", 23, "WORSE"),
    ("R2", "hdb-v1-gen-0073:low_ground_friction:0", "eval_A1e6_s3.jsonl", 1, "A1e6", 1, "21f93b68fe", "NOT_RECOVERED", 23, "WORSE"),
    ("R3", "hdb-v1-gen-0126:low_ground_friction:0", "eval_A1e6_s2.jsonl", 2, "A1e6", 2, "ed99eefe37", "NOT_RECOVERED", 20, "NOT_VERIFIED"),
    ("R4", "hdb-v1-gen-0137:low_ground_friction:0", "eval_A1e6_s3.jsonl", 4, "A1e6", 4, "66053dae8e", "PARTIAL_IMPROVEMENT", 19,
     "VERIFIED_IMPROVEMENT"),
    ("R5", "hdb-v1-gen-0096:low_ground_friction:2", "eval_A1e6_s4.jsonl", 3, "A1e6", 4, "1d51937757", "NOT_RECOVERED", 6, "NOT_VERIFIED"),
    ("R6", "hdb-v1-gen-0073:heavy_torso:0", "eval_A1e6_s5.jsonl", 2, "A1e6", 4, "1277dab8f7", "NOT_RECOVERED", 23, "WORSE"),
    ("R7", "hdb-v1-gen-0073:heavy_torso:0", "eval_A3v5_s5.jsonl", 2, "A3v5", 4, "dfb185d771", "FULL_RECOVERY", 23,
     "VERIFIED_IMPROVEMENT"),
    ("R8", "hdb-v1-gen-0143:pitch_sensor_bias:3", "eval_A1e6_s2.jsonl", 5, "A1e6", 2, "e3c48a6799", "FULL_RECOVERY", 24,
     "VERIFIED_IMPROVEMENT"),
]
PER_DESIGN_CAP = ta1.VERIFY_CAP
N_INSTANCES = len({e[1] for e in DESIGNS})          # R6 and R7 share one instance: 7
PHASE_CAP = len(DESIGNS) * PER_DESIGN_CAP + N_INSTANCES * ta1.ELIGIBILITY_ROLLOUTS
RECORD_FILES = sorted({e[2] for e in DESIGNS})
SCOPE = "exact reproduction of the available stored reference fields (not proof of complete physical identity)"


def resolve(records_root: str, entry: tuple) -> dict:
    """Read one preregistered design from the stored records and check that it is the preregistered one (no physics)."""
    rid, iid, fname, line, arm, idx, h, status, walk_k, verdict = entry
    rec = ta1.load_stored(records_root, fname, line)
    problems = []
    if rec["instance_id"] != iid:
        problems.append(f"instance {rec['instance_id']} != {iid}")
    if rec["arm"] != arm:
        problems.append(f"arm {rec['arm']} != {arm}")
    if rec["submitted"] != idx:
        problems.append(f"submitted design {rec['submitted']} != {idx}")
    d = rec["designs"][idx]
    if ta1.design_hash(d) != h:
        problems.append(f"design hash {ta1.design_hash(d)} != {h}")
    v = rec["verification"]
    if v["status"] != status or round(v["walking_frac"] * 24) != walk_k or ta1.stored_verdict(v) != verdict:
        problems.append(f"stored outcome {v['status']}/{round(v['walking_frac'] * 24)}/{ta1.stored_verdict(v)} != "
                        f"{status}/{walk_k}/{verdict}")
    return {"id": rid, "record": rec, "design": {"body": d["body"], "vector": d["vector"]}, "problems": problems}


def instance_checks(inst: dict, stored_records: list) -> dict:
    """The rebuilt instance against EVERY stored record of that instance (eligibility check and fault parameters)."""
    checks = {}
    for k, rec in enumerate(stored_records):
        for name, ok in {**ta1.eligibility_checks(inst["check"], rec["check"]),
                         "strength": inst.get("strength") == rec.get("strength"),
                         "mult": inst.get("mult") == rec.get("mult"),
                         "severity": inst.get("severity") == rec.get("severity"),
                         "family": inst.get("family") == rec.get("family")}.items():
            checks[f"{name}[{rec['arm']}#{k}]"] = ok
    return {"exact": bool(checks) and all(checks.values()), "checks": checks, "scope": SCOPE}


def reproduction_checks(stored: dict, summary: dict) -> dict:
    """The new verification summary against the stored DS-1 summary of the same design."""
    checks = ta1.summary_checks(summary, stored["verification"])
    return {"exact": all(checks.values()), "checks": checks, "scope": SCOPE}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--phase", choices=["1A"])
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--approved-by", default="")
    ap.add_argument("--harness-commit", default=None, help="the approved harness revision; must equal HEAD")
    ap.add_argument("--max-rollouts", type=int, default=0)
    ap.add_argument("--artifacts-root", default=os.path.join(ta1.ROOT, "artifacts", "hdb"))
    ap.add_argument("--records-root", default=os.path.join(ta1.ROOT, "artifacts", "vm", "ds1", "eval"))
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    inputs = ta1.config_inputs(ta1.ROOT, a.artifacts_root)
    print(f"{VERSION}: {len(DESIGNS)} designs on {N_INSTANCES} instances; cap {PHASE_CAP} rollout-equivalents "
          f"({PER_DESIGN_CAP} per design + {ta1.ELIGIBILITY_ROLLOUTS} per instance eligibility check); no twin rollouts")
    print(f"  gate: {SCOPE}")
    for e in DESIGNS:
        print(f"  {e[0]} {e[1]} {e[2]}#L{e[3]} {e[4]} design {e[5]} {e[6]} must reproduce {e[7]} {e[8]}/24 {e[9]}")
    for name, p in inputs.items():
        print(f"  input {name}: {p} sha256={ta1.sha256_file(p) or 'MISSING'}")
    pre = ta1.preflight_refusals(ta1.ROOT, inputs, a.records_root, RECORD_FILES, a.harness_commit)
    if not a.execute:
        print("  preflight: " + ("ok" if not pre else "would refuse: " + "; ".join(pre)))
        print("Dry run: nothing was simulated. Pass --execute only with the owner's approval for Phase 1A.")
        return 0
    refusals = list(pre)
    if a.phase != "1A":
        refusals.append("--phase 1A is required with --execute")
    if not a.approved_by.strip():
        refusals.append("--approved-by is required with --execute")
    if a.max_rollouts < PHASE_CAP:
        refusals.append(f"--max-rollouts {a.max_rollouts} is below the phase cap {PHASE_CAP}")
    refusals += ta1.output_refusals(a.out, ta1.ROOT)
    missing = [n for n, p in inputs.items() if ta1.sha256_file(p) is None]
    if missing:
        refusals.append(f"missing inputs: {missing}")
    resolved = []
    if not os.path.isdir(a.records_root):
        refusals.append(f"records root {a.records_root} not found")
    else:
        resolved = [resolve(a.records_root, e) for e in DESIGNS]
        refusals += [f"{r['id']}: {p}" for r in resolved for p in r["problems"]]
    if refusals:
        for r in refusals:
            print("REFUSED:", r)
        return 2
    return _execute(a, inputs, resolved)


def _execute(a, inputs, resolved, *, build_fn=None, verify_fn=None, pool_cm=None) -> int:
    """Fail-closed Phase 1A execution. `build_fn`, `verify_fn` and `pool_cm` are injectable for no-physics tests."""
    if build_fn is None:
        build_fn = ta1.build_instance
    if verify_fn is None:
        from creature_forge import hdb_bench as hb
        verify_fn = hb.verify
    if pool_cm is None:
        from creature_forge.forge_pool import ForgePool, InlinePool
        pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    records = {f: ta1.sha256_file(os.path.join(a.records_root, f)) for f in RECORD_FILES}
    manifest = ta1.provenance_manifest(ta1.ROOT, inputs, {"phase": "1A", "approved_by": a.approved_by, "cap": PHASE_CAP,
                                                          "designs": DESIGNS, "stored_records_sha256": records,
                                                          "records_root": os.path.abspath(a.records_root),
                                                          "harness_commit_approved": a.harness_commit, "rv1_version": VERSION,
                                                          "gate_scope": SCOPE})
    with open(ta1.manifest_path(a.out), "x", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    stored_by_instance = {}
    for r in resolved:
        stored_by_instance.setdefault(r["record"]["instance_id"], []).append(r["record"])
    instances, n_inst_ok, n_design_ok = {}, 0, 0
    with pool_cm as pool, open(a.out, "x", encoding="utf-8") as out:
        for r in resolved:
            t0 = time.perf_counter()
            stored = r["record"]
            iid = stored["instance_id"]
            if iid not in instances:
                inst = build_fn(iid, inputs, pool=pool)
                ic = instance_checks(inst, stored_by_instance[iid])
                out.write(json.dumps(ta1.jsonable({"version": VERSION, "kind": "instance_check", "instance_id": iid,
                                                   "check": inst["check"], "strength": inst.get("strength"),
                                                   "mult": inst.get("mult"), "instance_reproduction": ic})) + "\n")
                out.flush()
                if not ic["exact"]:
                    return ta1._pause(f"instance {iid} does not reproduce the stored eligibility/fault fields",
                                      [k for k, v in ic["checks"].items() if not v])
                instances[iid] = inst
                n_inst_ok += 1
            ver = verify_fn(instances[iid], r["design"], pool=pool)
            sv = ta1.serialize_verification(ver)
            rep = reproduction_checks(stored, sv["summary"])
            problems = ta1.verification_complete(sv["full"])
            row = {"version": VERSION, "kind": "design", "id": r["id"], "instance_id": iid, "stored_arm": stored["arm"],
                   "design_index": stored["submitted"], "design_hash": ta1.design_hash(r["design"]),
                   "verification": sv, "verification_problems": problems, "reproduction": rep,
                   "stored_verification": stored["verification"], "wall_s": time.perf_counter() - t0}
            out.write(json.dumps(ta1.jsonable(row)) + "\n")
            out.flush()
            print(r["id"], iid, sv["summary"]["status"], round(sv["summary"]["walking_frac"] * 24),
                  "exact" if rep["exact"] and not problems else "MISMATCH", f"{row['wall_s']:.0f}s", flush=True)
            if not rep["exact"] or problems:
                return ta1._pause(f"{r['id']} does not reproduce the stored reference fields or its record is incomplete",
                                  [k for k, v in rep["checks"].items() if not v] + problems)
            n_design_ok += 1
    if n_inst_ok == N_INSTANCES and n_design_ok == len(DESIGNS):
        print(f"GATE PASS: {n_inst_ok}/{N_INSTANCES} instance checks and {n_design_ok}/{len(DESIGNS)} designs - {SCOPE}")
        return 0
    return ta1._pause("not every preregistered instance and design was checked",
                      [f"instances {n_inst_ok}/{N_INSTANCES}, designs {n_design_ok}/{len(DESIGNS)}"])


if __name__ == "__main__":
    sys.exit(main())
