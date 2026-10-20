"""RV-1 (FA-1C Phase 1A): deterministic re-verification of 8 stored DS-1 submitted designs with full per-seed output.

Each preregistered design is read from its stored DS-1 record (path, line, design index; its 10-digit design hash must match),
its instance is rebuilt exactly as scripts/hdb_agent_run.py builds it (ta1_tool_access.build_instance), and the UNCHANGED
`hdb_bench.verify` (full_recovery_v1) is run. The full output (per-seed original and candidate validation rows, verdict
statistics, confirmation rows) is kept, together with exact-reproduction checks against the stored record:
  status, validation walking fraction, verdict_v1 status, eligibility-check labels, fault strength and multiple.
Gate (FA-1C): ALL designs and ALL eligibility checks must reproduce exactly; any discrepancy pauses the study for
investigation. This script reports the gate; it never decides what follows.

Usage:
  python scripts/rv1_reverify.py                                   # dry run: the preregistered list, caps, input hashes
  python scripts/rv1_reverify.py --execute --phase 1A --approved-by "<owner, date>" --max-rollouts 824 \\
      --artifacts-root <dir> --records-root <dir with eval_*.jsonl> --out <path outside the repository>.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta1_tool_access as ta1                        # noqa: E402

VERSION = "rv1_reverify_v1"
# preregistered designs (FA-1C section E, Phase 1A): id -> stored record (file, 1-based line), arm, design index, hash, and the
# stored outcome that must be reproduced exactly (status, validation walking k/24, verdict_v1 status)
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


def load_stored(records_root: str, fname: str, line: int) -> dict:
    with open(os.path.join(records_root, fname), encoding="utf-8") as fh:
        for i, text in enumerate(fh, 1):
            if i == line:
                return json.loads(text)
    raise ValueError(f"{fname} has no line {line}")


def resolve(records_root: str, entry: tuple) -> dict:
    """Read one preregistered design from the stored records and check that it is the preregistered one (no physics)."""
    rid, iid, fname, line, arm, idx, h, status, walk_k, verdict = entry
    rec = load_stored(records_root, fname, line)
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


def reproduction_checks(stored: dict, inst: dict, summary: dict) -> dict:
    """Exact comparisons of a re-verification against its stored record (Phase 1A gate)."""
    sv = stored["verification"]
    checks = {
        "status": summary["status"] == sv["status"],
        "walking_frac": summary["walking_frac"] == sv["walking_frac"],
        "verdict": ta1.stored_verdict(summary) == ta1.stored_verdict(sv),
        "eligibility_labels": inst["check"]["labels"] == stored["check"]["labels"],
        "strength": inst.get("strength") == stored.get("strength"),
        "mult": inst.get("mult") == stored.get("mult"),
    }
    return {"exact": all(checks.values()), "checks": checks}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--phase", choices=["1A"])
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--approved-by", default="")
    ap.add_argument("--max-rollouts", type=int, default=0)
    ap.add_argument("--artifacts-root", default=os.path.join(ta1.ROOT, "artifacts", "hdb"))
    ap.add_argument("--records-root", default=os.path.join(ta1.ROOT, "artifacts", "vm", "ds1", "eval"))
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    inputs = ta1.config_inputs(ta1.ROOT, a.artifacts_root)
    print(f"{VERSION}: {len(DESIGNS)} designs on {N_INSTANCES} instances; cap {PHASE_CAP} rollout-equivalents "
          f"({PER_DESIGN_CAP} per design + {ta1.ELIGIBILITY_ROLLOUTS} per instance eligibility check); no twin rollouts")
    for e in DESIGNS:
        print(f"  {e[0]} {e[1]} {e[2]}#L{e[3]} {e[4]} design {e[5]} {e[6]} must reproduce {e[7]} {e[8]}/24 {e[9]}")
    for name, p in inputs.items():
        print(f"  input {name}: {p} sha256={ta1.sha256_file(p) or 'MISSING'}")
    if not a.execute:
        print("Dry run: nothing was simulated. Pass --execute only with the owner's approval for Phase 1A.")
        return 0
    refusals = []
    if a.phase != "1A":
        refusals.append("--phase 1A is required with --execute")
    if not a.approved_by.strip():
        refusals.append("--approved-by is required with --execute")
    if a.max_rollouts < PHASE_CAP:
        refusals.append(f"--max-rollouts {a.max_rollouts} is below the phase cap {PHASE_CAP}")
    if not a.out:
        refusals.append("--out is required with --execute")
    elif ta1.inside(a.out, ta1.ROOT):
        refusals.append("--out must be outside the repository")
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


def _execute(a, inputs, resolved) -> int:        # pragma: no cover - physics; Phase 1A only, with owner approval
    import contextlib
    from creature_forge import hdb_bench as hb
    from creature_forge.forge_pool import ForgePool, InlinePool
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    records = {e[0]: (e[2], ta1.sha256_file(os.path.join(a.records_root, e[2]))) for e in DESIGNS}
    manifest = ta1.provenance_manifest(ta1.ROOT, inputs, {"phase": "1A", "approved_by": a.approved_by, "cap": PHASE_CAP,
                                                          "designs": DESIGNS, "stored_records": records, "rv1_version": VERSION})
    with open(a.out + ".manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    gate, instances = [], {}
    pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    with pool_cm as pool, open(a.out, "a", encoding="utf-8") as out:
        for r in resolved:
            t0 = time.perf_counter()
            stored = r["record"]
            iid = stored["instance_id"]
            if iid not in instances:
                instances[iid] = ta1.build_instance(iid, inputs, pool=pool)
            inst = instances[iid]
            ver = hb.verify(inst, r["design"], pool=pool)
            sv = ta1.serialize_verification(ver)
            rep = reproduction_checks(stored, inst, sv["summary"])
            row = {"version": VERSION, "id": r["id"], "instance_id": iid, "stored_arm": stored["arm"],
                   "design_index": stored["submitted"], "design_hash": ta1.design_hash(r["design"]),
                   "verification": sv, "verification_problems": ta1.verification_complete(sv["full"]),
                   "reproduction": rep, "stored_verification": stored["verification"], "check": inst["check"],
                   "wall_s": time.perf_counter() - t0}
            out.write(json.dumps(ta1.jsonable(row)) + "\n")
            out.flush()
            gate.append(rep["exact"] and not row["verification_problems"])
            print(r["id"], iid, sv["summary"]["status"], round(sv["summary"]["walking_frac"] * 24), "exact" if rep["exact"]
                  else f"MISMATCH {[k for k, v in rep['checks'].items() if not v]}", f"{row['wall_s']:.0f}s", flush=True)
    print("GATE (all exact):", "PASS" if gate and all(gate) else "PAUSE - investigate every discrepancy before any comparison")
    return 0 if gate and all(gate) else 3


if __name__ == "__main__":
    sys.exit(main())
