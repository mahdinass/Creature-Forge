"""Prepare, execute, validate and analyse the development-only R0 study.

No walker glob or test-side loader is used. Only the already-audited dev response
matrix, explicitly named dev A1 records and dev thresholds may prepare inputs.
Run commands require a protocol with pinned sources and case bytes. Each completed
unit is an atomic independent checkpoint; resume validates rather than trusts it.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import importlib.metadata
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import random
import re
import subprocess
import sys
import tarfile
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
VERSION = "r0_experiment_v1"
EXPERIMENT = ROOT / "experiments/causal_engineer/dev/repair_strategy_r0"
CODE = ("scripts/r0_experiment.py", "creature_forge/r0_repair.py", "scripts/do1_objective.py",
        "scripts/r0_integrity.py", "scripts/r0_campaign.sh", "scripts/r0_nebius.py",
        "creature_forge/walk_opt.py", "creature_forge/hidden_plant.py", "creature_forge/hdb_bench.py",
        "creature_forge/hdb_workbench.py", "creature_forge/recovery.py", "creature_forge/verdict.py",
        "creature_forge/arena.py", "creature_forge/locomotion.py", "creature_forge/creature_walk.py",
        "creature_forge/fault_bench.py", "creature_forge/phasegait_fp.py", "creature_forge/eng_tools.py",
        "creature_forge/walk_pipelines.py", "creature_forge/r2.py", "creature_forge/morphology.py",
        "creature_forge/sandbox.py")
MATRIX = "experiments/causal_engineer/dev/rl1/rl1_matrix.tgz"
MATRIX_SHA = "9b740a946231d7bf98967d28a641de320831e346048a59da5eaff89434c96b2a"
A1_SHA = "3bde2b77676fd3d46592bb9ad50250ecfc8614376d6676b87d59f2a97d2149cb"
TH_SHA = "12ca21cbf85d054f9aa4aa08beb184b0f497b52e205184c264609aeedfc37d89"
FULL = "FULL_RECOVERY"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(obj) + b"\n"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"refusing to replace existing evidence: {path}")
        return
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with tmp.open("xb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        if os.name == "nt":
            os.rename(tmp, path)  # Windows rename is atomic and refuses overwrite
        else:
            os.link(tmp, path)  # POSIX link is atomic and refuses overwrite
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError(f"concurrent checkpoint disagrees: {path}")
    finally:
        tmp.unlink(missing_ok=True)


def code_hashes():
    # Code only: LF normalization allows the same Git source on Windows/Linux.
    paths = set(CODE) | {str(p.relative_to(ROOT)).replace("\\", "/")
                         for p in (ROOT / "creature_forge").rglob("*.py")}
    return {p: sha((ROOT / p).read_bytes().replace(b"\r\n", b"\n")) for p in sorted(paths)}


def fingerprint():
    return {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
            "cpu_count": os.cpu_count(), "executable": sys.executable,
            "mujoco": importlib.metadata.version("mujoco"), "numpy": importlib.metadata.version("numpy"),
            "blas_threads": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}}


def fresh_seeds(iid):
    counts = {"train": 4, "select": 8, "validate": 24, "confirm": 24}
    out = {r: [int(sha(f"r0-dev-v1:{iid}:{r}:{i}".encode())[:8], 16) for i in range(n)]
           for r, n in counts.items()}
    flat = [s for ss in out.values() for s in ss]
    if len(set(flat)) != len(flat):
        raise ValueError("seed collision")
    return out


def balanced_pick(candidates, n, excluded=()):
    """Family-count-balanced, SHA tie-break, at most one case per base."""
    used, counts, out = set(excluded), collections.Counter(), []
    while len(out) < n:
        eligible = [c for c in candidates if c["base_id"] not in used]
        if not eligible:
            raise ValueError("sampling quota cannot be filled without changing base caps")
        c = min(eligible, key=lambda x: (counts[x["family"]], sha(("r0-sample-v1:" + x["instance_id"]).encode())))
        out.append(c)
        used.add(c["base_id"])
        counts[c["family"]] += 1
    return out


def prepare(a):
    from creature_forge import hdb_bench as hb
    from creature_forge import r0_repair as rp
    for path, expected in ((ROOT / MATRIX, MATRIX_SHA), (Path(a.a1), A1_SHA), (Path(a.thresholds), TH_SHA)):
        if sha(path.read_bytes()) != expected:
            raise ValueError(f"source checksum mismatch: {path}")
    with tarfile.open(ROOT / MATRIX) as t:
        matrix = [json.loads(l) for l in t.extractfile("matrix.jsonl")]
    cells = {}
    for r in matrix:
        key = (r["instance_id"], r["tool"])
        if key in cells or r.get("error") or not r.get("ok"):
            raise ValueError("invalid historical matrix cell")
        cells[key] = r
    records = [json.loads(l) for l in Path(a.a1).open(encoding="utf-8")]
    records = [r for r in records if r.get("verification")]
    if len(records) != 211 or len(cells) != 2110:
        raise ValueError("unexpected dev population")
    candidates, bases = [], {}
    for r in records:
        iid = r["instance_id"]
        bid, fam, sev = iid.rsplit(":", 2)
        if fam not in hb.FAMILY_SPECS or hb.FAMILY_SPECS[fam]["split"] != "dev":
            raise ValueError("non-development input")
        d = {k: copy.deepcopy(r["designs"][0][k]) for k in ("body", "vector")}
        if bid in bases and bases[bid] != d:
            raise ValueError("inconsistent nominal morphology")
        bases[bid] = d
        full_tools = [t for t in rp.TOOLS if cells[iid, t]["status"] == FULL]
        candidates.append({"instance_id": iid, "base_id": bid, "family": fam, "severity": int(sev),
                           "historical_full_tools": full_tools, "historical_check": r["check"]})
    failed = balanced_pick([c for c in candidates if not c["historical_full_tools"]], 12)
    controls = balanced_pick([c for c in candidates if c["historical_full_tools"]], 6,
                             excluded=[c["base_id"] for c in failed])
    selected = [{**c, "cohort": "failed"} for c in failed] + [{**c, "cohort": "control"} for c in controls]
    thresholds = read(a.thresholds)

    def make(c):
        base = {"base_id": c["base_id"], **bases[c["base_id"]]}
        inst = hb.make_instance_v2(base, c["family"], c["severity"], thresholds)
        if inst is None or inst["split"] != "dev" or inst["instance_id"] != c["instance_id"]:
            raise ValueError("cannot reconstruct declared development case")
        seeds = fresh_seeds(c["instance_id"])
        if set(s for ss in seeds.values() for s in ss) & set(s for ss in inst["seeds"].values() for s in ss):
            raise ValueError("new/old seed collision")
        return {**c, "plant": inst["plant"], "robot": inst["robot"], "seeds": seeds,
                "policy_id": sha(("r0-view:" + c["instance_id"]).encode())[:16]}
    out = Path(a.out)
    write_new(out / "cases.json", [make(c) for c in selected])
    selected_ids = {c["instance_id"] for c in selected}
    smoke = sorted((c for c in candidates if c["instance_id"] not in selected_ids),
                   key=lambda c: sha(("r0-smoke-v1:" + c["instance_id"]).encode()))[:1]
    write_new(out / "smoke_cases.json", [make(c) for c in smoke])
    protocol = {"version": VERSION, "study": "R0 development capability pilot", "created_date": "2026-10-25",
                "base_commit": "0828cbd0ea556fb31630e275b444b0197671185e",
                "cases_sha256": sha((out / "cases.json").read_bytes()),
                "smoke_cases_sha256": sha((out / "smoke_cases.json").read_bytes()),
                "code_sha256_lf": code_hashes(), "actions": list(rp.ACTIONS), "objectives": list(rp.OBJECTIVES),
                "pairs": [list(p) for p in rp.PAIRS], "replicates": [0, 1, 2], "budget": 3000,
                "n_cases": 18, "n_failed": 12, "n_controls": 6, "n_units": 324,
                "smoke_budget": 2000,
                "seed_namespace": "r0-dev-v1", "selection_seeds": 8, "selection_candidates": 2,
                "body_ratio_original": [0.25, 4.0], "recovery_rule": "full_recovery_v1",
                "sources": {MATRIX: MATRIX_SHA, "fresh_A1c5.jsonl": A1_SHA, "thresholds_dev.json": TH_SHA},
                "gate": {"joint_do1_full_at_least": 2, "best_restricted_do1_full_at_most": 1,
                         "rescue_bases_at_least": 3, "rescue_families_at_least": 2,
                         "net_failed_full_gain_at_least": 3, "material_control_regressions_at_most": 0,
                         "material_regression": "joint_do1 <=1/3 and either restricted_do1 >=2/3",
                         "require_complete_error_free": True},
                "analysis": {"primary_descriptive": "joint-do1 minus sequential-do1 on failed cohort",
                             "cluster": "base", "bootstrap": 10000, "bootstrap_seed": 2026102507,
                             "ci": 0.95, "confirmatory": False},
                "recovery": "Atomic successful units are never rerun. Missing checkpoints may resume identically. "
                            "Errors are retained and stop the run; no automatic scientific/algorithm error retry.",
                "resource_authority": {"additional_infra_usd": 35, "paid_runtime_hours": 10, "inference": False}}
    write_new(out / "protocol.json", protocol)
    print(json.dumps({"protocol_sha256": sha((out / "protocol.json").read_bytes()),
                      "cases": [{k: c[k] for k in ("instance_id", "cohort", "family")} for c in selected]}, indent=2))


def load_study(directory, smoke=False):
    directory = Path(directory)
    p = read(directory / "protocol.json")
    name = "smoke_cases.json" if smoke else "cases.json"
    if sha((directory / name).read_bytes()) != p["smoke_cases_sha256" if smoke else "cases_sha256"]:
        raise ValueError("case checksum mismatch")
    if code_hashes() != p["code_sha256_lf"]:
        raise ValueError("source differs from frozen protocol")
    from creature_forge import r0_repair as rp
    if p["pairs"] != [list(pair) for pair in rp.PAIRS] or p["actions"] != list(rp.ACTIONS) or p["objectives"] != list(rp.OBJECTIVES):
        raise ValueError("protocol/implementation condition mismatch")
    cases = read(directory / name)
    if smoke:
        # The frozen excluded-case blob predates this reporting-only label.
        # Keep its bytes/seeds/robot/plant unchanged; never expose it to policy.
        cases = [{**c, "cohort": "engineering"} for c in cases]
    elif any(c.get("cohort") not in ("failed", "control") for c in cases):
        raise ValueError("missing or invalid study cohort metadata")
    if len({c["base_id"] for c in cases}) != len(cases) and not smoke:
        raise ValueError("base cap violated")
    return p, cases


def units(p, cases):
    return [{"case": c, "action": ac, "objective": ob, "replicate": r, "budget": p["budget"]}
            for c in cases for ac in p["actions"] for ob in p["objectives"] for r in p["replicates"]]


def unit_id(job):
    return sha(canonical([job["case"]["instance_id"], job["action"], job["objective"], job["replicate"]]))[:24]


class PlantEvaluator:
    """Trusted measurement layer; all physical paths are serial within a unit."""
    def __init__(self, case, objective):
        self.case, self.objective, self.baselines = case, objective, {}

    def __call__(self, candidates, role):
        import numpy as np
        import do1_objective as do1
        from creature_forge import hidden_plant as hp
        from creature_forge import r2
        from creature_forge.hdb_evidence import walk_score
        if role.endswith("_baseline"):
            actual = role.split("_")[0]
            d = candidates[0]
            rows = hp.walk_seeds(self.case["plant"], d["body"], d["vector"], self.case["seeds"][actual])
            if any(not r.get("ok") for r in rows):
                raise RuntimeError("baseline physics error")
            self.baselines[actual] = [0.0 if walk_score(r) is None else walk_score(r) for r in rows]
            return []
        seeds = self.case["seeds"][role]
        if self.objective == "do1":
            fn = do1.make_do1_eval_fn(self.case["plant"], seeds, self.baselines[role])
        else:
            fn = hp.make_eval_fn(self.case["plant"], seeds)
        return fn([(c["body"], c["vector"]) for c in candidates])


def run_unit(job):
    from creature_forge import hidden_plant as hp
    from creature_forge import r0_repair as rp
    t0 = time.perf_counter()
    c = job["case"]
    required = ("instance_id", "base_id", "family", "cohort", "policy_id", "robot", "plant", "seeds")
    missing = [k for k in required if k not in c]
    if missing:
        raise ValueError(f"missing case metadata before physics: {missing}")
    view = {"robot_id": c["policy_id"], "robot": copy.deepcopy(c["robot"]),
            "seeds": {r: c["seeds"][r] for r in ("train", "select")}}
    result = rp.solve(view, job["action"], job["objective"], job["replicate"],
                      PlantEvaluator(c, job["objective"]), budget=job["budget"])
    # Final verification cannot influence any candidate or selection decision.
    ver = hp.verify(c["plant"], c["robot"], result["design"], c["seeds"]["validate"], c["seeds"]["confirm"])
    return {"version": VERSION, "unit_id": unit_id(job), "instance_id": c["instance_id"],
            "base_id": c["base_id"], "family": c["family"], "cohort": c["cohort"],
            "action": job["action"], "objective": job["objective"], "replicate": job["replicate"],
            "seeds": c["seeds"], "provenance": job["provenance"], "result": result,
            "verification": ver, "wall_s": time.perf_counter() - t0,
            "verification_rollout_equivalents": ver["rollouts"]["validation"] +
                                                ver["rollouts"]["confirmation_rollout_equivalents"]}


def validate_record(row, job, provenance):
    if row.get("version") != VERSION or row.get("unit_id") != unit_id(job) or row.get("provenance") != provenance:
        raise ValueError("record identity/provenance mismatch")
    for key in ("action", "objective", "replicate"):
        if row.get(key) != job[key]:
            raise ValueError("record condition mismatch")
    if any(row.get(k) != job["case"][k] for k in ("instance_id", "base_id", "family", "cohort", "seeds")):
        raise ValueError("record case mismatch")
    result = row.get("result", {})
    ledger = result.get("ledger", {})
    lines = ledger.get("lines", [])
    cum = 0
    for ln in lines:
        if type(ln.get("n")) is not int or ln["n"] <= 0 or ln["n"] % 4:
            raise ValueError("invalid rollout charge")
        cum += ln["n"]
        if ln["cumulative"] != cum or not 0 <= cum <= job["budget"]:
            raise ValueError("invalid ledger")
    if cum != job["budget"] or ledger.get("used") != cum or ledger.get("total") != cum:
        raise ValueError("missing or incomplete ledger")
    from creature_forge.r0_repair import assert_bounds
    assert_bounds(job["case"]["robot"], result["design"])
    ver = row.get("verification", {})
    if ver.get("rule") != "full_recovery_v1" or ver.get("status") not in (
            FULL, "PARTIAL_IMPROVEMENT", "NOT_RECOVERED", "INCONCLUSIVE_ERROR"):
        raise ValueError("invalid verification")
    vs, cs = ver.get("seeds", {}).get("validate"), ver.get("seeds", {}).get("confirm")
    if vs != job["case"]["seeds"]["validate"] or cs != job["case"]["seeds"]["confirm"]:
        raise ValueError("verification seeds mismatch")
    validation = ver.get("validation", {})
    for arm in ("original", "candidate"):
        records = validation.get(arm, [])
        if [r.get("seed") for r in records] != vs or any(
                r.get("outcome") not in ("PASS", "POOR", "FAIL", "ERROR") for r in records):
            raise ValueError("missing or invalid per-seed validation")
    walking = sum(r["outcome"] == "PASS" for r in validation["candidate"])/24
    if validation.get("walking_frac") != walking:
        raise ValueError("validation aggregate disagrees with per-seed evidence")
    confirmation = ver.get("confirmation", {})
    conf_n = 24 if confirmation.get("run") else 0
    if conf_n and ([r.get("seed") for r in confirmation.get("per_seed", [])] != cs or any(
            r.get("outcome") not in ("PASS", "POOR", "FAIL", "ERROR")
            for r in confirmation.get("per_seed", []))):
        raise ValueError("missing per-seed confirmation")
    if ver.get("rollouts") != {"validation": 48, "confirmation": conf_n,
                               "confirmation_rollout_equivalents": 2*conf_n} or \
            row.get("verification_rollout_equivalents") != 48 + 2*conf_n:
        raise ValueError("verification rollout accounting mismatch")
    if ver["status"] == FULL:
        if not (ver.get("confirmation", {}).get("passed") and
                len(ver["confirmation"].get("per_seed", [])) == 24 and
                ver["validation"].get("aggregate") == "PASS" and
                ver["validation"].get("verdict", {}).get("status") == "VERIFIED_IMPROVEMENT"):
            raise ValueError("false FULL record")
    if not math.isfinite(row.get("wall_s", float("nan"))) or row["wall_s"] < 0:
        raise ValueError("invalid timing")


def execution_provenance(directory, fingerprint_value):
    return {"protocol_sha256": sha((Path(directory) / "protocol.json").read_bytes()),
            "code_sha256_lf": code_hashes(), "environment": fingerprint_value,
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()}


def validate_provenance(provenance, directory):
    if provenance.get("protocol_sha256") != sha((Path(directory)/"protocol.json").read_bytes()) or \
            provenance.get("code_sha256_lf") != code_hashes():
        raise ValueError("execution provenance does not match frozen study")
    if not re.fullmatch(r"[0-9a-f]{40}", provenance.get("source_commit", "")):
        raise ValueError("missing source commit")
    env = provenance.get("environment", {})
    if env.get("mujoco") != "3.15.0" or not all(env.get(k) for k in ("numpy", "python", "platform", "executable")):
        raise ValueError("missing or unsupported environment fingerprint")


def execute(a):
    p, cases = load_study(a.study, a.smoke)
    jobs = units(p, cases)
    if a.smoke:
        # Excluded engineering sample, all action/objective combinations, r0.
        jobs = [j for j in jobs if j["replicate"] == 0]
        for j in jobs:
            j["budget"] = p["smoke_budget"]
    k, n = map(int, a.shard.split("/"))
    if not 0 <= k < n or not 1 <= a.workers <= 6:
        raise ValueError("invalid shard/worker count")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    provenance = execution_provenance(a.study, fingerprint())
    validate_provenance(provenance, a.study)
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT).decode().strip()
    if dirty:
        raise ValueError("execution requires a clean committed research tree")
    write_new(out / "execution.json", provenance)
    todo = []
    for job in jobs[k::n]:
        job["provenance"] = provenance
        path = out / "units" / (unit_id(job) + ".json")
        if path.exists():
            validate_record(read(path), job, provenance)
        else:
            todo.append(job)
    print(json.dumps({"todo": len(todo), "shard": a.shard, "workers": a.workers}), flush=True)
    executor = None
    try:
        if a.workers == 1:
            completed = ((j, run_unit(j)) for j in todo)
        else:
            executor = ProcessPoolExecutor(max_workers=a.workers, mp_context=mp.get_context("spawn"))
            fs = {executor.submit(run_unit, j): j for j in todo}
            completed = ((fs[f], f.result()) for f in as_completed(fs))
        for job, row in completed:
            validate_record(row, job, provenance)
            write_new(out / "units" / (unit_id(job) + ".json"), row)
            print(json.dumps({"unit_id": row["unit_id"], "condition": row["action"] + "/" + row["objective"],
                              "status": row["verification"]["status"], "wall_s": round(row["wall_s"], 2)}), flush=True)
    except Exception:
        write_new(out / "errors" / f"shard{k}_{time.time_ns()}.json", {"error": traceback.format_exc(), "shard": a.shard})
        raise
    finally:
        if executor:
            executor.shutdown(wait=True, cancel_futures=True)


def analyze(a):
    p, cases = load_study(a.study, a.smoke)
    jobs = units(p, cases)
    if a.smoke:
        jobs = [j for j in jobs if j["replicate"] == 0]
        for j in jobs:
            j["budget"] = p["smoke_budget"]
    out = Path(a.out)
    provenance = read(out / "execution.json")
    validate_provenance(provenance, a.study)
    expected = {unit_id(j): j for j in jobs}
    paths = list((out / "units").glob("*.json"))
    if {f.stem for f in paths} != set(expected):
        raise ValueError(f"incomplete/unexpected units: {len(paths)}/{len(expected)}")
    rows = []
    for path in sorted(paths):
        row = read(path)
        validate_record(row, expected[path.stem], provenance)
        rows.append(row)
    if a.smoke:
        summary = {"complete": True, "n": len(rows), "max_wall_s": max(r["wall_s"] for r in rows),
                   "sum_worker_hours": sum(r["wall_s"] for r in rows) / 3600,
                   "statuses": dict(collections.Counter(r["verification"]["status"] for r in rows))}
        write_new(out / "smoke_summary.json", summary)
        print(json.dumps(summary, indent=2))
        return
    by = collections.defaultdict(dict)
    for c in cases:
        for ac in p["actions"]:
            for ob in p["objectives"]:
                rs = [r for r in rows if r["instance_id"] == c["instance_id"] and r["action"] == ac and r["objective"] == ob]
                by[c["instance_id"]][f"{ac}/{ob}"] = sum(r["verification"]["status"] == FULL for r in rs)
    conditions = {}
    for ac in p["actions"]:
        for ob in p["objectives"]:
            rs = [r for r in rows if r["action"] == ac and r["objective"] == ob]
            conditions[f"{ac}/{ob}"] = {
                "full": sum(r["verification"]["status"] == FULL for r in rs), "n": len(rs),
                "failed_full": sum(r["verification"]["status"] == FULL for r in rs if r["cohort"] == "failed"),
                "control_full": sum(r["verification"]["status"] == FULL for r in rs if r["cohort"] == "control"),
                "statuses": dict(collections.Counter(r["verification"]["status"] for r in rs)),
                "mean_validation_walking": sum(r["verification"]["validation"]["walking_frac"] for r in rs) / len(rs),
                "mean_worker_s": sum(r["wall_s"] for r in rs) / len(rs),
                "policy_rollouts": sorted({r["result"]["ledger"]["used"] for r in rs})}
    failed = [c for c in cases if c["cohort"] == "failed"]
    controls = [c for c in cases if c["cohort"] == "control"]
    rescue = [c for c in failed if by[c["instance_id"]]["joint/do1"] >= 2 and
              max(by[c["instance_id"]]["single/do1"], by[c["instance_id"]]["sequential/do1"]) <= 1]
    regress = [c for c in controls if by[c["instance_id"]]["joint/do1"] <= 1 and
               max(by[c["instance_id"]]["single/do1"], by[c["instance_id"]]["sequential/do1"]) >= 2]
    net = sum(by[c["instance_id"]]["joint/do1"] -
              max(by[c["instance_id"]]["single/do1"], by[c["instance_id"]]["sequential/do1"]) for c in failed)
    errors = sum(r["verification"]["status"] == "INCONCLUSIVE_ERROR" for r in rows)
    gate = {"rescue_bases": len({c["base_id"] for c in rescue}), "rescue_families": len({c["family"] for c in rescue}),
            "net_failed_full_gain": net, "material_control_regressions": len(regress), "errors": errors,
            "rescue_ids": [c["instance_id"] for c in rescue], "regression_ids": [c["instance_id"] for c in regress]}
    gate["PASS"] = gate["rescue_bases"] >= 3 and gate["rescue_families"] >= 2 and net >= 3 and not regress and not errors
    contrasts = {}
    comparisons = [("joint/do1", "sequential/do1"), ("joint/do1", "single/do1"),
                   ("joint/frozen", "sequential/frozen"), ("joint/frozen", "single/frozen")]
    comparisons += [(f"{ac}/do1", f"{ac}/frozen") for ac in p["actions"]]
    for left, right in comparisons:
        delta = [(by[c["instance_id"]][left] - by[c["instance_id"]][right]) / 3 for c in failed]
        rng = random.Random(p["analysis"]["bootstrap_seed"])
        boot = sorted(sum(rng.choice(delta) for _ in delta) / len(delta) for _ in range(p["analysis"]["bootstrap"]))
        nz = [d for d in delta if d]
        observed = abs(sum(nz))
        pv = sum(abs(sum(d * (1 if bits >> i & 1 else -1) for i, d in enumerate(nz))) >= observed - 1e-12
                 for bits in range(2**len(nz))) / 2**len(nz)
        contrasts[f"{left} - {right}"] = {"mean_base_difference": sum(delta) / len(delta),
            "descriptive_cluster_bootstrap95": [boot[249], boot[9749]], "exploratory_two_sided_base_signflip_p": pv,
            "n_bases": len(delta)}
    summary = {"version": VERSION, "complete": True, "n": len(rows), "conditions": conditions,
               "gate": gate, "contrasts_failed_cohort": contrasts, "per_case_full_counts": dict(by),
               "sum_worker_hours": sum(r["wall_s"] for r in rows) / 3600,
               "total_policy_rollouts": sum(r["result"]["ledger"]["used"] for r in rows),
               "total_verification_equivalents": sum(r["verification_rollout_equivalents"] for r in rows),
               "record_hashes": {str(f.relative_to(out)): sha(f.read_bytes()) for f in sorted(paths)},
               "note": "Development pilot; descriptive intervals and exploratory tests, no confirmatory claim."}
    write_new(out / "analysis.json", summary)
    print(json.dumps({"conditions": conditions, "gate": gate, "contrasts": contrasts}, indent=2))


def main():
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--a1", required=True)
    prep.add_argument("--thresholds", required=True)
    prep.add_argument("--out", default=str(EXPERIMENT))
    for cmd in ("run", "analyze"):
        q = sub.add_parser(cmd)
        q.add_argument("--study", default=str(EXPERIMENT))
        q.add_argument("--out", required=True)
        q.add_argument("--smoke", action="store_true")
        if cmd == "run":
            q.add_argument("--workers", type=int, default=6)
            q.add_argument("--shard", default="0/1")
    a = parser.parse_args()
    {"prepare": prepare, "run": execute, "analyze": analyze}[a.command](a)


if __name__ == "__main__":
    main()
