"""DO-1 ablation runner: frozen plant-repair objective vs the DO-1 recovery-aware objective (scripts/do1_objective.py).

Design (prepared 2026-10-21; development data only, never validation-tuned, confirmation-tuned or sealed):
  frozen   the unchanged A1e6 episode on the frozen EvidenceWorkbench (identical to the TA-1 control).
  do1      identical, except that the bench is `Do1Workbench`: its plant `repair` ranks CMA candidates by the DO-1 objective.
Both arms keep the engine's ORIGINAL tool order (TA-1 control hook, returns {}), the same instance, seeds, bounds, twin warm
start, posterior, probe/CMA screens, stop map v2, tau, budgets (plant 700, twin 2,800) and verifier `full_recovery_v1`.
Replicate r changes only the bench noise seed (plant-CMA streams), identically in both arms; arms are seed-matched, not
trajectory-paired. The only differences after the hook: the CMA ranking scalar and the 4-rollout DO-1 train baseline, which is
charged inside the plant budget (the frozen arm spends those 4 rollouts on CMA candidates instead).

Phases (each needs its own owner execution approval; nothing here authorises a run, and no phase starts another):
  DO1-L4-r0  EXPLORATORY pilot: L4 replicate 0, frozen then do1 (2 episodes, cap 7,208). Descriptive only, no hypothesis test;
             it checks the end-to-end behaviour (gates, logs, budget) and shows the direction on one pair.
  DO1-L4     L4 (hdb-v1-gen-0137:low_ground_friction:0), replicates 0-4, frozen and do1 interleaved: 10 episodes. Retained as
             defined; never run automatically. Its r0 pair is re-executed (deterministic, expected identical to the pilot)
             and the pilot is not pooled into it unless the owner approves that explicitly.
  DO1-L1     L1 (hdb-v1-gen-0073:low_ground_friction:2), replicate 0, frozen and do1: 2 episodes. Complementary, descriptive.
  DO1-L4-rep W3 replication (preregistered 2026-10-21, docs/DO1_REPLICATION_PROTOCOL.md): a frozen r0 SENTINEL first (an
             environment-reproduction check against the stored A1e6 record, excluded from every analysis), then fresh
             replicates r1-r5, frozen and do1 interleaved: 11 episodes, cap 39,644. The DO1-L4-r0 pilot is not pooled.
  DO1-X      W4 exploratory cross-family pilot: B1 (hdb-v1-gen-0142:payload_offset:5) and C1
             (hdb-v1-gen-0070:feedback_gain_loss:2), replicate 0, frozen then do1: 4 episodes, cap 14,416. Descriptive only.
  In DO1-L4-rep and DO1-X a NOT_EXPOSED do1 episode is recorded, verified, kept and the phase CONTINUES (intention to
  treat); only validity defects pause. An exception inside an episode is written to the output as an infrastructure-
  error line and the phase pauses. DO1-L4-rep replicates r >= 1 must also match the stored record's pre-hook prefix (the
  bench noise seed enters only the plant repair, which no stored L4 trace reaches before the hook).

Statistics (PAIRED design): replicate r of both arms shares the bench noise seed, so the unit is the (replicate) pair. The
primary DO1-L4 analysis is the exact one-sided McNemar (sign) test on discordant pairs (FULL in one arm only): with 5 pairs
p = 0.5 ** n_discordant when every discordant pair favours do1, so p <= 0.05 requires all 5 pairs discordant for do1
(p = 0.031); 4 discordant for do1 and 0 against gives p = 0.0625 (not significant). The pairs are technical replicates of
plant-CMA stochasticity on ONE robot instance, not independent robots: any result is instance-specific.

Validity gates (fail closed, stop at the first invalid result; outcomes are never interpreted here):
  * complete verification record; the hook called exactly once;
  * frozen r0 reproduces the stored A1e6 record exactly (TA-1 gate 1); do1 r0's pre-hook prefix equals the stored record's;
  * each (case, replicate) pair has equal pre-hook fingerprints;
  * do1: exactly one train-baseline line of 4 rollouts, plant used <= 700, at least one completed DO-1 repair (otherwise the
    episode is NOT_EXPOSED and invalid, never a null result), and every completed repair's selected candidate equal to its
    logged candidate and to the design it registered; frozen: no DO-1 ledger lines.
Re-screens are recorded, never invalidating.

Usage:
  python scripts/do1_repair_ablation.py --phase DO1-L4-r0 --artifacts-root <dir> --records-root <dir>   # dry run (default)
  python scripts/do1_repair_ablation.py --phase DO1-L4-r0 --execute --approved-by "<owner, date>" --harness-commit <40-hex> \\
      --max-rollouts 7208 --workers 6 --artifacts-root <dir> --records-root <dir> --out <fresh path outside every worktree>
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

RUNNER_VERSION = "do1_ablation_v2"   # v2: W3/W4 phases (DO1-L4-rep, DO1-X); the v1 phases behave as before
ARMS = ("frozen", "do1")
L4_REPLICATES = 5
# W4 cases (pre-declared eligibility rule, plan of record 2026-10-21 section 6). They live here rather than in ta1.CASES,
# so the TA-1 preregistered case list stays unchanged. stored = (file, 1-based line, submitted design, design hash prefix).
X_CASES = {
    "B1": {"instance_id": "hdb-v1-gen-0142:payload_offset:5", "stored": ("eval_A1e6_s3.jsonl", 5, 2, "73146bcf6e")},
    "C1": {"instance_id": "hdb-v1-gen-0070:feedback_gain_loss:2", "stored": ("eval_A1e6_s5.jsonl", 1, 4, "9823aeddda")},
}
CASES = {**ta1.CASES, **X_CASES}
PHASES = {
    "DO1-L4-r0": [("L4", arm, 0) for arm in ARMS],
    "DO1-L4": [("L4", arm, r) for r in range(L4_REPLICATES) for arm in ARMS],
    "DO1-L1": [("L1", arm, 0) for arm in ARMS],
    "DO1-L4-rep": [("L4", "frozen", 0)] + [("L4", arm, r) for r in range(1, L4_REPLICATES + 1) for arm in ARMS],
    "DO1-X": [(c, arm, 0) for c in ("B1", "C1") for arm in ARMS],
}
CONTINUE_NOT_EXPOSED = frozenset({"DO1-L4-rep", "DO1-X"})   # ITT: a NOT_EXPOSED do1 episode is kept and the phase goes on
STORED_PREFIX_ALL_REPLICATES = frozenset({"DO1-L4-rep"})   # r >= 1 must also match the stored pre-hook prefix
PREREGISTRATION = {
    "hypothesis": "On L4 the frozen objective saturates (4/4 train walking, validity 1 inside the gates) and rewards speed up "
                  "to 0.4 m/s, so the submitted designs sit near the walking gates (15/16 robust, 19/24 validation). Ranking "
                  "candidates by walking, then the paired-displacement constraint against the faulty robot, then the "
                  "walking-gate margin raises validation walking to >= 20/24 while keeping verified displacement.",
    "primary_case": "L4 (original tool order)", "complementary_case": "L1 (descriptive only)",
    "primary_outcome": "FULL_RECOVERY under the unchanged full_recovery_v1, per episode",
    "unit": "replicate pair (shared bench noise seed): technical replicates of plant-CMA stochasticity on one robot instance",
    "primary_test": "DO1-L4: exact one-sided McNemar (sign) test on discordant pairs, do1 FULL vs frozen FULL, alpha 0.05",
    "success": "p <= 0.05, which with 5 pairs requires all 5 pairs discordant in favour of do1 (p = 0.031); an "
               "instance-specific finding about this robot and budget, not a rate over robots",
    "suggestive": "every discordant pair favours do1 but p > 0.05 (e.g. 4 for, 0 against: p = 0.0625): reported as "
                  "suggestive and inconclusive, never as a demonstrated improvement",
    "no_improvement_observed": "no discordant pair favours do1: no evidence of improvement on this instance at this budget; "
                               "with 5 technical replicates this is NOT a falsification of the objective",
    "otherwise": "inconclusive at this budget (mixed discordant pairs); reported, no follow-up run without approval",
    "pilot_DO1-L4-r0": "exploratory, one pair, no hypothesis test: FULL status, validation k/24, verdict and median paired "
                       "displacement per arm, submitted and checked designs, per-candidate DO-1 components, budget split",
    "secondary": ["paired validation walking k/24 (do1 - frozen) per replicate, sign of the 5 differences",
                  "validation verdict and median paired displacement (do1 must stay VERIFIED_IMPROVEMENT)",
                  "train-seed margin, median paired diff and feasibility of each submitted and checked design",
                  "robust16 and robust displacement of each checked design; mapped P(FULL); plant/twin rollouts"],
    "interpretation_limits": "technical replicates of plant-CMA stochasticity on one instance; not a rate over robots",
    "null_wording": "No verified recovery was found under the tested intervention, optimizer configuration and "
                    "computational budget.",
    "no_outcome_based_stopping": True,
}
PHASE_PREREGISTRATION = {
    "DO1-L4-rep": {
        "study": "W3: replication of DO1-L4-r0 on fresh optimizer randomness, one development instance (L4)",
        "runs": "frozen r0 sentinel (role sentinel, excluded from every analysis), then r1-r5 x (frozen, do1) interleaved",
        "varies": "only the bench noise seed (plant-CMA streams): replicate_noise_seed(L4, r) = 1751409197 + 10007 r, and "
                  "+ 7919 k for the k-th plant repair; identical in both arms of a replicate",
        "fixed": "instance, physical seeds, twin-CMA seeds (11 and 0), train/robust/validation/confirmation seeds, verifier "
                 "full_recovery_v1, stop map v2, tau 0.75, budgets plant 700 / twin 2,800, objective do1_objective_v2",
        "hypothesis": "do1 reaches FULL_RECOVERY on more L4 replicates than the frozen objective under matched randomness",
        "primary_outcome": "FULL_RECOVERY per episode (unchanged full_recovery_v1)",
        "primary_analysis": "intention to treat over the 5 pairs r1-r5: FULL count per arm k/5 with exact Clopper-Pearson "
                            "95% intervals; exact one-sided McNemar (sign) test on discordant pairs, alpha 0.05 (5/0 -> "
                            "p = 0.031; 4/0 -> 0.0625, inconclusive; fewer discordant pairs -> descriptive only)",
        "secondary": ["PARTIAL_IMPROVEMENT and NOT_RECOVERED counts per arm",
                      "paired validation walking difference k/24 (do1 - frozen) per replicate; exact sign test",
                      "validation verdict and median paired displacement per episode",
                      "20 s confirmation run/passed and its checks",
                      "plant and twin rollouts; stop-map acceptance; binding gates; selected = last candidate evaluated",
                      "per-protocol analysis excluding NOT_EXPOSED pairs, shown next to ITT with counts and reasons"],
        "stopping": "no outcome-based stopping, no extra replicates; a validity defect (sentinel mismatch, unequal pre-hook "
                    "fingerprints, stored-prefix mismatch, incomplete verification, hook calls != 1, inconsistent DO-1 "
                    "selection, an infrastructure error) pauses fail-closed; completed pairs are reported with the defect "
                    "and nothing is re-run without owner approval; NOT_EXPOSED continues",
        "limits": "technical replicates of optimizer randomness on ONE physical instance, evaluated on the same, already "
                  "studied L4 validation seeds: no claim about unseen robots, fault families or validation conditions; the "
                  "r0 pilot is exploratory and is never pooled",
        "null_wording": PREREGISTRATION["null_wording"],
    },
    "DO1-X": {
        "study": "W4: exploratory cross-family pilot, two development instances chosen by the pre-declared rule "
                 "(stored A1e6 PARTIAL with walking-only failure, at least one stored plant repair, one body/mass and "
                 "one controller family, highest stored walking count, ties by lowest base id)",
        "runs": "B1 r0 frozen, B1 r0 do1, C1 r0 frozen, C1 r0 do1",
        "gates": "frozen r0 reproduces the stored A1e6 record exactly; do1 r0 matches the stored pre-hook prefix; equal "
                 "pre-hook fingerprints; hook once; verification complete; do1 exposure recorded (NOT_EXPOSED continues)",
        "analysis": "descriptive per instance and arm: status, validation k/24, verdict and median paired displacement, "
                    "confirmation, plant/twin use, which recovery gates changed. No hypothesis test, no pooling with L4, "
                    "no family- or population-level claim; cases were selected on the baseline's partial failure, so "
                    "regression to the mean is possible",
        "null_wording": PREREGISTRATION["null_wording"],
    },
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


def selection_problems(rec: dict, rep: dict) -> list[str]:
    """A completed DO-1 repair is consistent when its selected candidate is the logged candidate at `selected_log_index`
    (same components) and that candidate's vector is the design the repair registered."""
    k = rep.get("selected_log_index")
    cands = rep.get("candidates") or []
    tag = f"DO-1 repair {rep.get('repair_index')} ({rep.get('tool')})"
    if not isinstance(k, int) or isinstance(k, bool) or not 0 <= k < len(cands):
        return [f"{tag}: reported best is not in its candidate log (selected_log_index {k!r}, {len(cands)} candidates)"]
    logged = cands[k]
    sel = rep.get("selected")
    if not isinstance(sel, dict) or sel != {key: v for key, v in logged.items() if key != "vector"}:
        return [f"{tag}: selected components differ from logged candidate {k}"]
    designs = rec.get("designs") or []
    j = rep.get("design_index")
    if not isinstance(j, int) or not 0 <= j < len(designs):
        return [f"{tag}: registered design {j!r} is missing from the record"]
    if designs[j].get("vector") != logged.get("vector") or designs[j].get("source") != f"repair:{rep.get('tool')}":
        return [f"{tag}: registered design {j} is not logged candidate {k}"]
    return []


def arm_checks(rec: dict) -> list[str]:
    """Arm-specific validity problems (empty = valid). A do1 episode is a valid objective ablation only if it was EXPOSED to
    the DO-1 objective: exactly one 4-rollout train-baseline line, at least one completed DO-1 repair, and every completed
    repair's selected candidate consistent with its logged evidence. An unexposed episode is invalid, never a null result."""
    d = rec["harness"]["do1"]
    lines = rec["engine"]["ledger"]["lines"]
    base_lines = [ln for ln in lines if ln["item"] == "do1_train_baseline"]
    obj_lines = [ln for ln in lines if (ln.get("detail") or {}).get("objective") == do1.VERSION]
    problems = []
    if d["arm"] == "frozen":
        if d["bench_class"] != "EvidenceWorkbench" or obj_lines or base_lines:
            problems.append("frozen arm used a DO-1 bench or charged DO-1 ledger lines")
        return problems
    if d["bench_class"] != "Do1Workbench" or d.get("version") != do1.VERSION:
        problems.append(f"do1 arm ran on {d['bench_class']} / {d.get('version')}")
    if len(base_lines) != 1 or base_lines[0]["n"] != 4 or (base_lines[0].get("detail") or {}).get("objective") != do1.VERSION:
        problems.append(f"DO-1 train baseline lines {[ln['n'] for ln in base_lines]} (expected exactly one line of 4)")
    repairs = d.get("repairs") or []
    completed = [r for r in repairs if r.get("refused") is None]
    if not completed:
        problems.append(f"NOT_EXPOSED: no DO-1 repair completed ({len(repairs)} attempted); the episode is invalid as an "
                        f"objective ablation")
    for r in completed:
        problems += selection_problems(rec, r)
    if rec["engine"]["ledger"]["used"] > ta1.A1E6["budget"]:
        problems.append(f"plant used {rec['engine']['ledger']['used']} > {ta1.A1E6['budget']}")
    return problems


def planned_runs(phase: str) -> list[tuple]:
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {sorted(PHASES)}, got {phase!r}")
    return list(PHASES[phase])


def run_role(phase: str, case: str, arm: str, replicate: int) -> str:
    """sentinel (DO1-L4-rep frozen r0: reproduction check only), primary (DO1-L4-rep r >= 1), exploratory otherwise."""
    if phase == "DO1-L4-rep":
        return "sentinel" if replicate == 0 else "primary"
    return "exploratory"


def stored_record_files(runs: list) -> list[str]:
    return sorted({CASES[c]["stored"][0] for c, _, _ in runs})


def pausing_problems(phase: str, problems: list[str]) -> list[str]:
    """The problems that pause the phase: all of them, except NOT_EXPOSED in the phases that keep it (ITT)."""
    if phase in CONTINUE_NOT_EXPOSED:
        return [p for p in problems if not p.startswith("NOT_EXPOSED")]
    return list(problems)


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
        iid = CASES[c]["instance_id"]
        print(f"  {c} {iid} arm={arm} replicate={r} role={run_role(a.phase, c, arm, r)} "
              f"noise_seed={ta1.replicate_noise_seed(iid, r)}")
    for name, p in inputs.items():
        print(f"  input {name}: {p} sha256={ta1.sha256_file(p) or 'MISSING'}")
    pre = ta1.preflight_refusals(ta1.ROOT, inputs, a.records_root, stored_record_files(runs), a.harness_commit)
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
        "phase_preregistration": PHASE_PREREGISTRATION.get(a.phase), "cases": {c: CASES[c] for c in sorted({x[0] for x in runs})},
        "phase": a.phase, "approved_by": a.approved_by, "runs": runs, "cap": cap, "max_rollouts": a.max_rollouts,
        "max_wall_s": a.max_wall_s, "harness_commit_approved": a.harness_commit, "records_root": os.path.abspath(a.records_root)})
    with open(ta1.manifest_path(a.out), "x", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    spent, t0, by_unit = 0.0, time.perf_counter(), {}
    with pool_cm as pool, open(a.out, "x", encoding="utf-8") as out:
        instances = {}
        for c, arm, r in runs:
            iid = CASES[c]["instance_id"]
            if a.max_wall_s and time.perf_counter() - t0 > a.max_wall_s:
                print("STOP: wall-clock cap reached before", c, arm, r)
                return ta1.PAUSE_EXIT
            if spent + ta1.PER_EPISODE_CAP["plant"] + ta1.PER_EPISODE_CAP["twin"] > a.max_rollouts:
                print("STOP: the rollout cap would be exceeded by", c, arm, r)
                return ta1.PAUSE_EXIT
            if iid not in instances:
                instances[iid] = build_fn(iid, inputs, pool=pool)
            try:
                rec = run_fn(instances[iid], arm, r, inputs, pool=pool)
            except Exception as exc:   # recorded, never silently dropped; the phase pauses
                import traceback
                out.write(json.dumps({"infrastructure_error": True, "phase": a.phase, "case": c, "instance_id": iid,
                                      "arm": arm, "replicate": r, "error": f"{type(exc).__name__}: {exc}",
                                      "traceback": traceback.format_exc()}) + "\n")
                out.flush()
                return ta1._pause(f"{c} {arm} r{r} raised an infrastructure error", [f"{type(exc).__name__}: {exc}"])
            rec["harness"]["case"] = c
            rec["harness"]["phase"] = a.phase
            rec["harness"]["role"] = run_role(a.phase, c, arm, r)
            problems = []
            if not rec["harness"].get("verification_complete"):
                problems.append(f"incomplete verification record: {rec['harness'].get('verification_problems')}")
            if len(rec["harness"]["hook_calls"]) != 1:
                problems.append(f"engineer hook called {len(rec['harness']['hook_calls'])} times (expected once)")
            arm_problems = arm_checks(rec)
            rec["harness"]["arm_checks"] = {"valid": not arm_problems, "problems": arm_problems,
                                            "exposed": None if arm == "frozen" else
                                            not any(p.startswith("NOT_EXPOSED") for p in arm_problems)}
            problems += arm_problems
            if r != 0 and a.phase in STORED_PREFIX_ALL_REPLICATES:
                f, line, _, _ = CASES[c]["stored"]
                pm = ta1.prehook_prefix_matches(rec, ta1.load_stored(a.records_root, f, line))
                rec["harness"]["stored_prefix"] = pm
                if not pm["match"]:
                    problems.append(f"{arm} r{r} pre-hook prefix differs from the stored record: "
                                    f"{[k for k, v in pm.get('checks', {}).items() if not v] or pm.get('reason')}")
            if r == 0:
                f, line, _, _ = CASES[c]["stored"]
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
            kept = [p for p in problems if p not in pausing_problems(a.phase, problems)]
            if kept:
                print(f"  {c} {arm} r{r}: recorded and kept (intention to treat): {kept}", flush=True)
            if pausing_problems(a.phase, problems):
                return ta1._pause(f"{c} {arm} r{r} is invalid for the matched comparison", pausing_problems(a.phase, problems))
    print("DONE: every run passed its validity checks, apart from any NOT_EXPOSED episode kept above "
          "(outcomes are not interpreted here).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
