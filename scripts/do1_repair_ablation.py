"""DO-1 ablation runner: frozen plant-repair objective vs the DO-1 recovery-aware objective (scripts/do1_objective.py).

Design (prepared 2026-10-21; development data only, never validation-tuned, confirmation-tuned or sealed):
  frozen   the unchanged A1e6 episode on the frozen EvidenceWorkbench (identical to the TA-1 control).
  do1      identical, except that the bench is `Do1Workbench`: its plant `repair` ranks CMA candidates by the DO-1 objective.
Both arms keep the engine's ORIGINAL tool order (TA-1 control hook, returns {}), the same instance, seeds, bounds, twin warm
start, posterior, probe/CMA screens, stop map v2, tau, budgets (plant 700, twin 2,800) and verifier `full_recovery_v1`.
Replicate r changes only the bench noise seed (plant-CMA streams), identically in both arms; arms are seed-matched, not
trajectory-paired. The only differences after the hook: the CMA ranking scalar and the 4-rollout DO-1 train baseline, which is
charged inside the plant budget (the frozen arm spends those 4 rollouts on CMA candidates instead).

Phases (each needs its own owner execution approval; nothing here authorises a run):
  DO1-L4   L4 (hdb-v1-gen-0137:low_ground_friction:0), replicates 0-4, frozen and do1 interleaved: 10 episodes. Primary.
  DO1-L1   L1 (hdb-v1-gen-0073:low_ground_friction:2), replicate 0, frozen and do1: 2 episodes. Complementary, descriptive.

Validity gates (fail closed, stop at the first invalid result; outcomes are never interpreted here):
  * complete verification record; the hook called exactly once;
  * frozen r0 reproduces the stored A1e6 record exactly (TA-1 gate 1); do1 r0's pre-hook prefix equals the stored record's;
  * each (case, replicate) pair has equal pre-hook fingerprints;
  * do1: the train baseline charged exactly once (4 rollouts), plant used <= 700, every completed repair's reported best found
    in the candidate log; frozen: no DO-1 ledger lines.
Re-screens are recorded, never invalidating.

Usage:
  python scripts/do1_repair_ablation.py --phase DO1-L4 --artifacts-root <dir> --records-root <dir>      # dry run (default)
  python scripts/do1_repair_ablation.py --phase DO1-L4 --execute --approved-by "<owner, date>" --harness-commit <40-hex> \\
      --max-rollouts 36040 --workers 6 --artifacts-root <dir> --records-root <dir> --out <fresh path outside every worktree>
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

import ta1_tool_access as ta1      # noqa: E402  (puts the repository root on sys.path)
import do1_objective as do1        # noqa: E402

RUNNER_VERSION = "do1_ablation_v1"
ARMS = ("frozen", "do1")
L4_REPLICATES = 5
PHASES = {
    "DO1-L4": [("L4", arm, r) for r in range(L4_REPLICATES) for arm in ARMS],
    "DO1-L1": [("L1", arm, 0) for arm in ARMS],
}
PREREGISTRATION = {
    "hypothesis": "On L4 the frozen objective saturates (4/4 train walking, validity 1 inside the gates) and rewards speed up "
                  "to 0.4 m/s, so the submitted designs sit near the walking gates (15/16 robust, 19/24 validation). Ranking "
                  "candidates by walking, then the paired-displacement constraint against the faulty robot, then the "
                  "walking-gate margin raises validation walking to >= 20/24 while keeping verified displacement.",
    "primary_case": "L4 (original tool order)", "complementary_case": "L1 (descriptive only)",
    "primary_outcome": "FULL_RECOVERY under the unchanged full_recovery_v1, per episode",
    "primary_test": "one-sided Fisher exact test, do1 vs frozen FULL counts over replicates 0-4 on L4, alpha 0.05",
    "success": "p <= 0.05 (e.g. do1 >= 4/5 FULL with frozen 0/5, or 5/5 with frozen <= 1/5)",
    "falsified": "do1 FULL count <= frozen FULL count on L4",
    "otherwise": "inconclusive at this budget; reported, no follow-up run without approval",
    "secondary": ["paired validation walking k/24 (do1 - frozen) per replicate, sign of the 5 differences",
                  "validation verdict and median paired displacement (do1 must stay VERIFIED_IMPROVEMENT)",
                  "train-seed margin, median paired diff and feasibility of each submitted and checked design",
                  "robust16 and robust displacement of each checked design; mapped P(FULL); plant/twin rollouts"],
    "interpretation_limits": "technical replicates of plant-CMA stochasticity on one instance; not a rate over robots",
    "null_wording": "No verified recovery was found under the tested intervention, optimizer configuration and "
                    "computational budget.",
    "no_outcome_based_stopping": True,
}


def bench_factory(arm: str, holder: dict):
    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}, got {arm!r}")
    from creature_forge.hdb_evidence import EvidenceWorkbench
    cls = do1.Do1Workbench if arm == "do1" else EvidenceWorkbench

    def make(*a, **kw):
        holder["bench"] = cls(*a, **kw)
        return holder["bench"]
    return make


def run_do1_episode(inst: dict, arm: str, replicate: int, inputs: dict, pool=None, run_fn=None) -> dict:
    """One A1e6 episode with the engine's original tool order on the arm's bench. PHYSICS."""
    run_fn = run_fn or ta1.run_episode
    holder: dict = {}
    rec = run_fn(inst, "control", replicate, inputs, pool=pool, bench_cls=bench_factory(arm, holder))
    bench = holder.get("bench")
    if bench is None:
        raise RuntimeError("the episode did not construct its bench through the arm's factory")
    rec["harness"]["do1"] = {"runner_version": RUNNER_VERSION, "arm": arm, "bench_class": type(bench).__name__,
                             **(bench.do1_record() if arm == "do1" else {"version": None})}
    return ta1.jsonable(rec)


def arm_checks(rec: dict) -> list[str]:
    """Arm-specific validity problems (empty = valid)."""
    d = rec["harness"]["do1"]
    lines = rec["engine"]["ledger"]["lines"]
    base_lines = [ln for ln in lines if ln["item"] == "do1_train_baseline"]
    obj_lines = [ln for ln in lines if (ln.get("detail") or {}).get("objective") == do1.VERSION]
    problems = []
    if d["arm"] == "frozen":
        if d["bench_class"] != "EvidenceWorkbench" or obj_lines:
            problems.append("frozen arm used a DO-1 bench or charged DO-1 ledger lines")
        return problems
    if d["bench_class"] != "Do1Workbench" or d.get("version") != do1.VERSION:
        problems.append(f"do1 arm ran on {d['bench_class']} / {d.get('version')}")
    if [ln["n"] for ln in base_lines] not in ([4], []):
        problems.append(f"DO-1 train baseline charged {[ln['n'] for ln in base_lines]} (expected one line of 4)")
    if any(r.get("refused") is None and r.get("selected_log_index") is None for r in d.get("repairs") or []):
        problems.append("a DO-1 repair's reported best is not in its candidate log")
    if rec["engine"]["ledger"]["used"] > ta1.A1E6["budget"]:
        problems.append(f"plant used {rec['engine']['ledger']['used']} > {ta1.A1E6['budget']}")
    return problems


def planned_runs(phase: str) -> list[tuple]:
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {sorted(PHASES)}, got {phase!r}")
    return list(PHASES[phase])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--phase", choices=sorted(PHASES))
    ap.add_argument("--execute", action="store_true", help="run physics (fail-closed preflight; separate owner approval)")
    ap.add_argument("--approved-by", default="")
    ap.add_argument("--harness-commit", default=None, help="the approved harness revision; must equal HEAD")
    ap.add_argument("--max-rollouts", type=int, default=0, help="hard cap in 10 s rollout-equivalents (>= the phase cap)")
    ap.add_argument("--max-wall-s", type=float, default=0.0, help="stop before starting an episode once exceeded (0 = none)")
    ap.add_argument("--artifacts-root", default=os.path.join(ta1.ROOT, "artifacts", "hdb"))
    ap.add_argument("--records-root", default=os.path.join(ta1.ROOT, "artifacts", "vm", "ds1", "eval"))
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", default=None, help="fresh JSONL output outside every worktree of this repository")
    a = ap.parse_args(argv)
    inputs = ta1.config_inputs(ta1.ROOT, a.artifacts_root)
    if not a.phase:
        print(f"{RUNNER_VERSION} ({do1.VERSION}): dry run. Phases: " + ", ".join(f"{p} ({len(r)} episodes)" for p, r in PHASES.items()))
        print("Nothing was simulated. Choose --phase to see its plan; --execute requires separate owner approval.")
        return 0
    runs = planned_runs(a.phase)
    cap = ta1.phase_cap(runs)
    print(f"{RUNNER_VERSION} ({do1.VERSION}): phase {a.phase}: {cap['episodes']} episodes; caps plant {cap['plant']}, "
          f"twin {cap['twin']}, total {cap['total']} rollout-equivalents")
    print(f"  objective: {json.dumps(do1.OBJECTIVE_SPEC)}")
    for c, arm, r in runs:
        iid = ta1.CASES[c]["instance_id"]
        print(f"  {c} {iid} arm={arm} replicate={r} noise_seed={ta1.replicate_noise_seed(iid, r)}")
    for name, p in inputs.items():
        print(f"  input {name}: {p} sha256={ta1.sha256_file(p) or 'MISSING'}")
    pre = ta1.preflight_refusals(ta1.ROOT, inputs, a.records_root, ta1.stored_record_files(runs), a.harness_commit)
    if not a.execute:
        print("  preflight: " + ("ok" if not pre else "would refuse: " + "; ".join(pre)))
        print("Dry run: nothing was simulated. Pass --execute only with the owner's approval for this phase.")
        return 0
    refusals = list(pre)
    if not a.approved_by.strip():
        refusals.append("--approved-by is required with --execute")
    if a.max_rollouts < cap["total"]:
        refusals.append(f"--max-rollouts {a.max_rollouts} is below the phase cap {cap['total']}")
    refusals += ta1.output_refusals(a.out, ta1.ROOT)
    missing = [n for n, p in inputs.items() if ta1.sha256_file(p) is None]
    if missing:
        refusals.append(f"missing inputs: {missing}")
    if refusals:
        for r in refusals:
            print("REFUSED:", r)
        return 2
    return _execute(a, runs, inputs, cap)


def _execute(a, runs, inputs, cap, *, build_fn=None, run_fn=None, pool_cm=None) -> int:
    """Fail-closed execution of an approved phase. `build_fn`, `run_fn` and `pool_cm` are injectable for no-physics tests."""
    build_fn = build_fn or ta1.build_instance
    run_fn = run_fn or run_do1_episode
    if pool_cm is None:
        from creature_forge.forge_pool import ForgePool, InlinePool
        pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    manifest = ta1.provenance_manifest(ta1.ROOT, inputs, {
        "runner_version": RUNNER_VERSION, "objective": do1.OBJECTIVE_SPEC, "preregistration": PREREGISTRATION,
        "phase": a.phase, "approved_by": a.approved_by, "runs": runs, "cap": cap, "max_rollouts": a.max_rollouts,
        "max_wall_s": a.max_wall_s, "harness_commit_approved": a.harness_commit, "records_root": os.path.abspath(a.records_root)})
    with open(ta1.manifest_path(a.out), "x", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    spent, t0, by_unit = 0.0, time.perf_counter(), {}
    with pool_cm as pool, open(a.out, "x", encoding="utf-8") as out:
        instances = {}
        for c, arm, r in runs:
            iid = ta1.CASES[c]["instance_id"]
            if a.max_wall_s and time.perf_counter() - t0 > a.max_wall_s:
                print("STOP: wall-clock cap reached before", c, arm, r)
                return ta1.PAUSE_EXIT
            if spent + ta1.PER_EPISODE_CAP["plant"] + ta1.PER_EPISODE_CAP["twin"] > a.max_rollouts:
                print("STOP: the rollout cap would be exceeded by", c, arm, r)
                return ta1.PAUSE_EXIT
            if iid not in instances:
                instances[iid] = build_fn(iid, inputs, pool=pool)
            rec = run_fn(instances[iid], arm, r, inputs, pool=pool)
            rec["harness"]["case"] = c
            problems = []
            if not rec["harness"].get("verification_complete"):
                problems.append(f"incomplete verification record: {rec['harness'].get('verification_problems')}")
            if len(rec["harness"]["hook_calls"]) != 1:
                problems.append(f"engineer hook called {len(rec['harness']['hook_calls'])} times (expected once)")
            problems += arm_checks(rec)
            if r == 0:
                f, line, _, _ = ta1.CASES[c]["stored"]
                stored = ta1.load_stored(a.records_root, f, line)
                if arm == "frozen":
                    rep = ta1.compare_to_stored(rec, stored)
                    rec["harness"]["reproduction"] = rep
                    if not rep["exact"]:
                        problems.append(f"frozen r0 does not reproduce the stored A1e6 fields: "
                                        f"{[k for k, v in rep['checks'].items() if not v]}")
                else:
                    pm = ta1.prehook_prefix_matches(rec, stored)
                    rec["harness"]["stored_prefix"] = pm
                    if not pm["match"]:
                        problems.append(f"do1 r0 pre-hook prefix differs from the stored record: "
                                        f"{[k for k, v in pm.get('checks', {}).items() if not v] or pm.get('reason')}")
            other = by_unit.get((c, r))
            if other is not None and other["harness"]["do1"]["arm"] != arm:
                pair = ta1.paired_prehook_equal(*sorted([other, rec], key=lambda x: ARMS.index(x["harness"]["do1"]["arm"])))
                rec["harness"]["paired_prehook"] = pair
                if not pair["equal"]:
                    problems.append(f"arm pair pre-hook fingerprints differ: {pair['differing_components']}")
            by_unit[(c, r)] = rec
            out.write(json.dumps(rec) + "\n")
            out.flush()
            spent += rec["harness"]["resources"]["total_rollout_equivalents"]
            s = rec["verification"]["summary"]
            print(c, iid, arm, r, s["status"], round(s["walking_frac"] * 24), "rescreen:",
                  rec["harness"]["rescreen"]["classification"], "spent", round(spent), flush=True)
            if problems:
                return ta1._pause(f"{c} {arm} r{r} is invalid for the matched comparison", problems)
    print("DONE: every run passed its validity checks (outcomes are not interpreted here).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
