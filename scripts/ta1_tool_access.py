"""TA-1 harness (FA-1C Phase 0): post-screen repair-tool priority on the pinned engine, non-LLM A1e6 configuration.

Experiment (FA-1C section D, preregistered; development data only, never sealed tests):
  control    the unchanged A1e6 episode. `robust_repair` receives an `engineer` hook that returns {} (no override).
  treatment  identical, except that the hook returns {"tool_order": ["foot_friction"]}.
The hook is called by `belief_engine.Episode.robust_repair` after the unchanged probe screen and CMA re-rank (belief_engine.py
L880-896), so both arms share every computation before it. The treatment is a REPAIR-POLICY change: it also changes the twin
warm-start tool, the second plant tool (`tools[:2]`), the search trajectories and the budget flow after the hook. A success
shows that this policy can recover an instance; it does not show that fixing the screen's probes alone would.

What this file adds and what it leaves untouched:
  * `ToolAccessSession` overrides only `LabSession.delegate_repair`, and only by wrapping `ep.robust_repair` for the
    duration of the original method so that `engineer=` is added. The engine, the agent session, the stop map, the budgets,
    the verifier and every seed are the pinned code paths (no copy of their logic).
  * Per episode it records the full `hb.verify` output (per-seed validation and confirmation rows, verdict statistics), a
    component-wise sha256 fingerprint of the pre-hook state (see PRE-HOOK FINGERPRINT), resource accounting split at the
    hook, re-screen events (recorded, never used to discard an outcome) and a provenance manifest.

Execution is fail-closed (FA-1C Phase 0 audit corrections):
  * physics runs only with `--execute`, an approved `--phase`, `--approved-by`, `--harness-commit` equal to HEAD, a
    sufficient `--max-rollouts` and a FRESH `--out` (neither the file nor its manifest may exist; no resume/append);
  * the output and manifest must lie outside every worktree of this repository (original working directory included),
    compared on resolved paths;
  * preflight validates provenance against the frozen REFERENCE below (implementation commit ea9e729 is an ancestor of HEAD
    and the engine/runner/inputs are unchanged since it; clean worktree; git blob ids of tracked inputs; sha256 of the
    artifact inputs and of the stored DS-1 records). A mismatch refuses execution; the actual values go to the manifest;
  * the run stops with a nonzero exit at the first invalid result: an incomplete verification record, a control r0 that does
    not reproduce the available stored DS-1 fields, a treatment r0 whose pre-hook ledger/event prefix differs from the stored
    record, an arm pair whose pre-hook fingerprints differ, or a hook not called exactly once. Re-screens never stop a run.

PRE-HOOK FINGERPRINT (Phase 1B readiness note). Components, hashed separately and together: plant and twin ledgers; engine
events and history; experiments (with design hashes); every particle in engine dict order (pid, source, deviation, logw,
loglik and its full prediction cache `seen`); engine flags (assimilated designs, composite rounds, temperature, v6 settings,
settings); bench designs (index, source, body+vector hash, metadata), selected design, best score, robust-check scores,
displacement baseline, repair counter, noise seed, weigh calls, observation-cache keys; the agent session (phase, experiment
count, evidence, trace, tool ranking); the state handed to the hook; the screened ranking. It does NOT prove complete
internal equivalence: worker-process state, compiled MuJoCo models, Python object identity and any attribute not listed are
outside it. Equal fingerprints plus a control that reproduces the stored record are the Phase 1B evidence; the fingerprint
alone is not.

Randomness (FA-1C randomisation audit): replicate r changes only the bench noise seed, i.e. the plant-CMA streams
(hdb_workbench.py:155, seed = noise + 7919 * repair index). DS-1 used int.from_bytes(instance_id[:4]) % 2**31, which is the
same value for every hdb-v1 instance (1751409197); replicate r uses that value + 10007 * r, so r = 0 is the DS-1 seed. Twin
CMA seeds (0, 11), physical seeds, conditions and the instance are fixed: replicates are technical replicates of plant-CMA
stochasticity, not new robots and not validation-seed generalisation.

Usage:
  python scripts/ta1_tool_access.py --phase 1B --artifacts-root <dir> --records-root <dir>     # dry run (default)
  python scripts/ta1_tool_access.py --phase 1B --execute --approved-by "<owner, date>" --harness-commit <40-hex HEAD> \\
      --max-rollouts 7208 --artifacts-root <dir> --records-root <dir> --out <fresh path outside every worktree>.jsonl
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from creature_forge import belief_engine as be      # noqa: E402
from creature_forge import has_agent as ha          # noqa: E402
from creature_forge import hdb_bench as hb          # noqa: E402
from creature_forge.optimize import jsonable        # noqa: E402

HARNESS_VERSION = "ta1_harness_v2"
TREATMENT_TOOL = "foot_friction"
REPLICATE_STRIDE = 10007

# A1e6 configuration of DS-1 (scripts/ds1_launch.sh variables B and C; scripts/hdb_agent_run.py defaults)
DS1_DIR = "experiments/causal_engineer/dev/hdb/ds1"
A1E6 = {
    "arm": "A1e6", "v6": f"{DS1_DIR}/engine_v6_settings.json", "stop_model": f"{DS1_DIR}/stopmap_dev_v2.json",
    "split_file": "experiments/causal_engineer/dev/hdb/stage2_split.json", "which": "transfer",
    "eval_instances": f"{DS1_DIR}/ds1_eval_instances.json", "thresholds": "thresholds_dev.json", "walkers": "walkers_all.jsonl",
    "mults": (1.0, 1.3, 1.7), "tau": 0.75, "budget": 700, "twin_budget": 2800, "max_alive": 12, "use_generic": True,
    "max_turns": ha.MAX_TURNS,
}
ELIGIBILITY_ROLLOUTS = hb.CHECK_N   # check_eligibility: the faulty design on the 8 check seeds
VERIFY_CAP = 48 + 48            # 24 + 24 validation rollouts, plus 24 x 20 s confirmation = 48 rollout-equivalents
PER_EPISODE_CAP = {"plant": A1E6["budget"] + ELIGIBILITY_ROLLOUTS + VERIFY_CAP, "twin": A1E6["twin_budget"]}

# FROZEN REFERENCE MANIFEST (approved with this harness revision; never regenerated at execution time). Tracked inputs are
# pinned by git blob id at the implementation commit (line-ending independent); untracked inputs by raw sha256 of the copies
# pulled from the DS-1 VMs.
IMPLEMENTATION_COMMIT = "ea9e7291e8b718f1936120fcd844bd236175a16d"
PROTECTED_SOURCE_PATHS = ("creature_forge", "scripts/hdb_agent_run.py", "scripts/ds1_launch.sh", "experiments")
REFERENCE = {
    "implementation_commit": IMPLEMENTATION_COMMIT,
    "tracked_inputs_git_blob": {
        "v6_settings": "805c72ce0218a23d414c1ca05975f52356292b18",
        "stop_model": "99590dc7d362dc9f5abc0f448bf058529ebe70b5",
        "split_file": "c357bed7ca762fe38dde2323b86b32613d82deb6",
        "eval_instances": "08d94f3c14bd367b0f552f55c57d224f04341fef",
    },
    "artifact_inputs_sha256": {
        "thresholds": "12ca21cbf85d054f9aa4aa08beb184b0f497b52e205184c264609aeedfc37d89",
        "walkers": "151801a5187aabf8ad1dade4e41c47ea07c57007c590ffdb235df83f19aaf1fd",
    },
    "stored_records_sha256": {
        "eval_A1e6_s1.jsonl": "75a0498ba228cf2a9591dcd903a8a8eb11a119e34608b7634aa162c52e44829d",
        "eval_A1e6_s2.jsonl": "2e841477918c68700094adfdbbc373e38f145acffb4b5ff1fac020d67976f48d",
        "eval_A1e6_s3.jsonl": "f4a2ca64124f14837236f822ef9cc3ee3bee189775cb6fc1ed1be9d9d2896f27",
        "eval_A1e6_s4.jsonl": "7015d7d7c378f56d5febbe586b9339426a1e7d1adf1df3001cb50ad38d258102",
        "eval_A1e6_s5.jsonl": "5064356c4474e83aa4f0ee9cf2015ccd20d67eb9a3701268656d0d302b262e97",
        "eval_A3v5_s5.jsonl": "701ba810b30c94256ddd935a93d2751fd97c2b414c2ace87bf8490acd1f47cb0",
    },
}
TRACKED_INPUTS = {"v6_settings": "v6", "stop_model": "stop_model", "split_file": "split_file", "eval_instances": "eval_instances"}

# preregistered cases (FA-1C section D); stored = the DS-1 A1e6 record used as reference (file, 1-based line, design, hash)
CASES = {
    "L1": {"instance_id": "hdb-v1-gen-0073:low_ground_friction:2", "stored": ("eval_A1e6_s1.jsonl", 1, 4, "bbf27921db")},
    "L2": {"instance_id": "hdb-v1-gen-0073:low_ground_friction:0", "stored": ("eval_A1e6_s3.jsonl", 1, 1, "21f93b68fe")},
    "L3": {"instance_id": "hdb-v1-gen-0126:low_ground_friction:0", "stored": ("eval_A1e6_s2.jsonl", 2, 2, "ed99eefe37")},
    "L4": {"instance_id": "hdb-v1-gen-0137:low_ground_friction:0", "stored": ("eval_A1e6_s3.jsonl", 4, 4, "66053dae8e")},
    "L5": {"instance_id": "hdb-v1-gen-0096:low_ground_friction:2", "stored": ("eval_A1e6_s4.jsonl", 3, 4, "1d51937757")},
}
# preregistered phase run lists: (case, arm, replicate). Each phase needs its own owner approval.
PHASES = {
    "1B": [("L1", "control", 0), ("L1", "treatment", 0)],
    "2a": [(c, "treatment", 0) for c in ("L2", "L3", "L4", "L5")],
    "2a-contingency": [(c, "control", 0) for c in ("L2", "L3", "L4", "L5")],   # only for cases named with --cases
    "2b": [(c, arm, r) for c in ("L1", "L2", "L3", "L4") for arm in ("control", "treatment") for r in (1, 2)],
}
PAUSE_EXIT = 3


# ------------------------------------------------------------------------------------------------------------ seeds
def ds1_noise_seed(instance_id: str) -> int:
    """The bench noise seed of scripts/hdb_agent_run.py:83 (DS-1)."""
    return int.from_bytes(instance_id.encode()[:4], "big") % (2 ** 31)


def replicate_noise_seed(instance_id: str, replicate: int) -> int:
    if isinstance(replicate, bool) or not isinstance(replicate, int) or replicate < 0:
        raise ValueError(f"replicate must be a non-negative integer, got {replicate!r}")
    return ds1_noise_seed(instance_id) + REPLICATE_STRIDE * replicate


# ------------------------------------------------------------------------------------------------------------ arms
def control_plan(state: dict, ranking: list) -> dict:
    """No override: robust_repair keeps the engine's screened order."""
    return {}


def treatment_plan(state: dict, ranking: list) -> dict:
    """Post-screen priority for the treatment tool; robust_repair prepends it and keeps the rest of the ranking."""
    return {"tool_order": [TREATMENT_TOOL]}


ARM_PLANS = {"control": control_plan, "treatment": treatment_plan}


def canonical(o) -> str:
    return json.dumps(jsonable(o), sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(snapshot: dict) -> str:
    return hashlib.sha256(canonical(snapshot).encode()).hexdigest()


def design_hash(design: dict) -> str:
    """The 10-hex-digit design identifier used in FA-1C (body + vector)."""
    return hashlib.sha256(json.dumps({"b": design["body"], "v": design["vector"]}, sort_keys=True).encode()).hexdigest()[:10]


def _particles(ep) -> list:
    out = []
    for p in (getattr(ep, "particles", None) or {}).values():
        out.append({"pid": p.pid, "source": p.source, "deviation": p.deviation, "logw": p.logw, "loglik": p.loglik,
                    "seen_keys": sorted(p.seen), "seen_sha256": fingerprint(p.seen)})
    return out


def _bench_state(bench) -> dict:
    designs = []
    for d in getattr(bench, "designs", []) or []:
        meta = {k: v for k, v in d.items() if k not in ("body", "vector")}
        designs.append({**meta, "design_hash": design_hash(d) if "body" in d and "vector" in d else None})
    obs = getattr(bench, "_obs_cache", None)
    return {"designs": designs, "selected": getattr(bench, "_best", None), "best_score": getattr(bench, "_best_score", None),
            "robust_scores": getattr(bench, "scores", None), "baseline": getattr(bench, "_baseline", None),
            "n_repairs": getattr(bench, "_n_repairs", None), "noise_seed": getattr(bench, "_noise", None),
            "weigh_calls": getattr(bench, "_weigh_calls", None),
            "obs_cache_keys": sorted(str(k) for k in obs) if isinstance(obs, dict) else None}


def _session_state(session) -> dict | None:
    if session is None:
        return None
    return {"phase": session.phase, "n_experiments": session.n_experiments, "evidence": session.evidence,
            "trace": session.trace, "tool_ranking": session.tool_ranking, "done": session.done}


def prehook_snapshot(bench, ep, state: dict, ranking: list, session=None) -> dict:
    """Everything listed in PRE-HOOK FINGERPRINT, as deep-copied JSON (later mutation cannot change it)."""
    exps = []
    for e in getattr(ep, "experiments", []) or []:
        x = {k: v for k, v in e.items() if k != "design"}
        if isinstance(e.get("design"), dict) and "body" in e["design"]:
            x["design_hash"] = design_hash(e["design"])
        exps.append(x)
    return copy.deepcopy(jsonable({
        "ledgers": {"plant_lines": bench.budget.lines, "plant_used": bench.budget.used,
                    "twin_lines": bench.twin.lines, "twin_used": bench.twin.used},
        "engine_trace": {"events": ep.events, "history": ep.history},
        "experiments": exps,
        "particles": _particles(ep),
        "engine_flags": {"assimilated": sorted(getattr(ep, "_assimilated", None) or []),
                         "composite_rounds": getattr(ep, "_composite_rounds", None), "temperature": getattr(ep, "T", None),
                         "v6": getattr(ep, "v6", None), "settings": getattr(ep, "settings", None)},
        "bench": _bench_state(bench),
        "session": _session_state(session),
        "state": state, "ranking": ranking,
    }))


class HookRecorder:
    """The `engineer(state, ranking)` callback: fingerprints the pre-hook state, then returns the arm's plan.
    Set `.session` to the LabSession so its state is part of the fingerprint."""

    def __init__(self, arm: str, bench, ep, session=None):
        if arm not in ARM_PLANS:
            raise ValueError(f"arm must be one of {sorted(ARM_PLANS)}, got {arm!r}")
        self.arm, self.b, self.ep, self.session = arm, bench, ep, session
        self.calls: list[dict] = []

    def __call__(self, state: dict, ranking: list) -> dict:
        snap = prehook_snapshot(self.b, self.ep, state, ranking, self.session)
        tools = [r.get("tool") for r in ranking]
        plan = ARM_PLANS[self.arm](state, ranking)
        led = snap["ledgers"]
        self.calls.append({
            "arm": self.arm, "plan": copy.deepcopy(plan), "ranking_tools": tools,
            "treatment_tool_in_ranking": TREATMENT_TOOL in tools,
            "treatment_tool_rank": (tools.index(TREATMENT_TOOL) + 1) if TREATMENT_TOOL in tools else None,
            "prehook_fingerprint": fingerprint(snap),
            "prehook_component_fingerprints": {k: fingerprint(v) for k, v in snap.items()},
            "prehook_plant_used": led["plant_used"], "prehook_twin_used": led["twin_used"],
            "prehook_n_plant_lines": len(led["plant_lines"]), "prehook_n_twin_lines": len(led["twin_lines"]),
            "prehook_n_events": len(snap["engine_trace"]["events"]), "prehook_n_history": len(snap["engine_trace"]["history"]),
            "prehook_n_particles": len(snap["particles"]), "session_included": snap["session"] is not None,
        })
        return plan


class ToolAccessSession(ha.LabSession):
    """LabSession whose delegated repair passes `engineer` to Episode.robust_repair. The original delegate_repair runs
    unchanged; only its call to `self.ep.robust_repair` is wrapped (keyword arguments, as the pinned code calls it)."""

    def __init__(self, *args, engineer, **kwargs):
        super().__init__(*args, **kwargs)
        self._engineer = engineer

    def delegate_repair(self, *args, **kwargs):
        original = self.ep.robust_repair
        engineer = self._engineer

        def robust_repair(**kw):
            if kw.get("engineer") is not None:
                raise RuntimeError("the pinned delegate_repair already passes an engineer; the harness would override it")
            return original(**kw, engineer=engineer)

        self.ep.robust_repair = robust_repair
        try:
            return super().delegate_repair(*args, **kwargs)
        finally:
            del self.ep.robust_repair          # restore the class method


# ------------------------------------------------------------------------------------------------------------ records
RESCREEN_KIND = "rescreen_after_assimilation"


def rescreen_summary(events: list, treatment_tool: str = TREATMENT_TOOL) -> dict:
    """Re-screens after a leader change (belief_engine.py L952-960) are a natural downstream effect of the policy: recorded,
    kept in the primary (intention-to-treat) analysis, and flagged for the preregistered sensitivity analysis."""
    rs = [e for e in events if e.get("kind") == RESCREEN_KIND]
    out = [{"seq": e.get("seq"), "old_order": e.get("old_order"), "new_order": e.get("new_order"),
            "treatment_tool_in_new_order": treatment_tool in (e.get("new_order") or [])} for e in rs]
    if not rs:
        cls = "no re-screen"
    elif any(not x["treatment_tool_in_new_order"] for x in out):
        cls = "re-screen; treatment tool absent from the new order"
    else:
        cls = "re-screen; treatment tool kept"
    return {"n": len(rs), "events": out, "classification": cls, "sensitivity_exclude": bool(rs)}


VALIDATION_ROW_FIELDS = ("seed", "outcome", "score", "walking", "label", "forward_disp_upright", "fell", "fall_time",
                         "valid_steps", "speed_upright", "body_contact_frac", "perturb", "friction_used")
VERDICT_FIELDS = ("status", "n", "wins", "losses", "ties", "median_diff", "p_one_sided", "p_worse", "min_effect", "reasons")


def verification_summary(ver: dict) -> dict:
    """The fields scripts/hdb_agent_run.py:126-127 keeps (for like-for-like comparison with DS-1 records)."""
    return {"status": ver["status"], "walking_frac": ver["validation"]["walking_frac"], "reasons": ver["reasons"],
            "rollouts": ver["rollouts"]}


def serialize_verification(ver: dict) -> dict:
    return {"summary": verification_summary(ver), "full": jsonable(copy.deepcopy(ver))}


def verification_complete(full: dict) -> list[str]:
    """Problems that would make the per-seed record incomplete (empty list = complete)."""
    errs = []
    val = full.get("validation") or {}
    nseeds = len((full.get("seeds") or {}).get("validate") or [])
    for side in ("original", "candidate"):
        rows = val.get(side)
        if not isinstance(rows, list) or len(rows) != nseeds or nseeds == 0:
            errs.append(f"validation.{side}: {0 if not isinstance(rows, list) else len(rows)} rows for {nseeds} seeds")
            continue
        for r in rows:
            miss = [k for k in VALIDATION_ROW_FIELDS if k not in r]
            if miss:
                errs.append(f"validation.{side} seed {r.get('seed')}: missing {miss}")
                break
    vd = val.get("verdict") or {}
    miss = [k for k in VERDICT_FIELDS if k not in vd]
    if miss:
        errs.append(f"verdict: missing {miss}")
    conf = full.get("confirmation") or {}
    if conf.get("run"):
        ncs = len((full.get("seeds") or {}).get("confirm") or [])
        if len(conf.get("per_seed") or []) != ncs:
            errs.append(f"confirmation.per_seed: {len(conf.get('per_seed') or [])} rows for {ncs} seeds")
        if "checks" not in conf:
            errs.append("confirmation: missing checks")
    return errs


def resource_accounting(ledger: dict, hook_calls: list, ver: dict | None) -> dict:
    """Plant and twin rollouts split at the hook, plus eligibility and verification rollouts (10 s-equivalents)."""
    pre = hook_calls[0] if hook_calls else None
    plant_used, twin_used = int(ledger["used"]), int(ledger["twin"]["used"])
    r = (ver or {}).get("rollouts") or {}
    val, conf = int(r.get("validation") or 0), float(r.get("confirmation_rollout_equivalents") or 0.0)
    return {
        "plant": {"used": plant_used, "budget": int(ledger["total"]),
                  "prehook": pre["prehook_plant_used"] if pre else None,
                  "posthook": (plant_used - pre["prehook_plant_used"]) if pre else None},
        "twin": {"used": twin_used, "budget": int(ledger["twin"]["total"]),
                 "prehook": pre["prehook_twin_used"] if pre else None,
                 "posthook": (twin_used - pre["prehook_twin_used"]) if pre else None},
        "eligibility_rollouts": ELIGIBILITY_ROLLOUTS, "verification_rollouts": val,
        "confirmation_rollout_equivalents": conf,
        "total_rollout_equivalents": plant_used + twin_used + ELIGIBILITY_ROLLOUTS + val + conf,
    }


def stored_verdict(verification: dict) -> str:
    """verdict_v1 status of a stored DS-1 summary (FULL/PARTIAL imply VERIFIED_IMPROVEMENT)."""
    for reason in verification.get("reasons") or []:
        if reason.startswith("verdict_v1 is "):
            return reason[len("verdict_v1 is "):].split(",")[0].strip()
    if verification.get("status") in ("FULL_RECOVERY", "PARTIAL_IMPROVEMENT"):
        return "VERIFIED_IMPROVEMENT"
    return "UNKNOWN"


def _strip_hook_events(events: list) -> list:
    return [{k: v for k, v in e.items() if k != "seq"} for e in events if e.get("kind") != "engineer_plan"]


def summary_checks(new_summary: dict, stored_summary: dict) -> dict:
    """Exact comparisons of the stored DS-1 verification summary fields (the only ones DS-1 retained)."""
    return {"status": new_summary["status"] == stored_summary["status"],
            "walking_frac": new_summary["walking_frac"] == stored_summary["walking_frac"],
            "verdict": stored_verdict(new_summary) == stored_verdict(stored_summary),
            "reasons": list(new_summary.get("reasons") or []) == list(stored_summary.get("reasons") or []),
            "rollouts": canonical(new_summary.get("rollouts")) == canonical(stored_summary.get("rollouts"))}


def eligibility_checks(new_check: dict, stored_check: dict) -> dict:
    return {"eligibility_labels": new_check.get("labels") == stored_check.get("labels"),
            "eligibility_walking": new_check.get("walking") == stored_check.get("walking"),
            "eligibility_n": new_check.get("n") == stored_check.get("n"),
            "eligibility_rollouts": new_check.get("rollouts") == stored_check.get("rollouts")}


def compare_to_stored(new: dict, stored: dict) -> dict:
    """Exact reproduction of the AVAILABLE stored reference fields of a DS-1 A1e6 record by a harness control record (Phase 1B
    gate 1). DS-1 did not retain per-seed verification rows, so this is not proof of complete physical identity. The only
    expected difference is the harness's own `engineer_plan` event."""
    nd, sd = new["designs"][new["submitted"]], stored["designs"][stored["submitted"]]
    ne, se = new["engine"], stored["engine"]
    nv = new["verification"]["summary"] if "summary" in new["verification"] else new["verification"]
    checks = {
        "submitted_index": new["submitted"] == stored["submitted"],
        "submitted_design_hash": design_hash(nd) == design_hash(sd),
        "all_design_hashes": [design_hash(d) for d in new["designs"]] == [design_hash(d) for d in stored["designs"]],
        **summary_checks(nv, stored["verification"]),
        "plant_used": ne["ledger"]["used"] == se["ledger"]["used"],
        "twin_used": ne["ledger"]["twin"]["used"] == se["ledger"]["twin"]["used"],
        "plant_lines": canonical(ne["ledger"]["lines"]) == canonical(se["ledger"]["lines"]),
        "twin_lines": canonical(ne["ledger"]["twin"]["lines"]) == canonical(se["ledger"]["twin"]["lines"]),
        "events_except_engineer_plan": canonical(_strip_hook_events(ne["events"])) == canonical(_strip_hook_events(se["events"])),
        "history": canonical(ne["history"]) == canonical(se["history"]),
        "final_particles": canonical(ne.get("particles")) == canonical(se.get("particles")),
        **eligibility_checks(new["check"], stored["check"]),
        "strength": new.get("strength") == stored.get("strength"),
        "mult": new.get("mult") == stored.get("mult"),
    }
    return {"exact": all(checks.values()), "checks": checks,
            "scope": "exact reproduction of the available stored reference fields (not proof of complete physical identity)"}


def prehook_prefix_matches(new: dict, stored: dict) -> dict:
    """Phase 2a check: the new record's pre-hook segment (ledger lines and events before the hook) equals the stored record's
    corresponding prefix, so the stored record can serve as that instance's r0 control."""
    calls = new["harness"]["hook_calls"]
    if len(calls) != 1:
        return {"match": False, "reason": f"expected one hook call, got {len(calls)}"}
    c = calls[0]
    ne, se = new["engine"], stored["engine"]
    checks = {
        "plant_lines": canonical(ne["ledger"]["lines"][:c["prehook_n_plant_lines"]]) == canonical(se["ledger"]["lines"][:c["prehook_n_plant_lines"]]),
        "twin_lines": canonical(ne["ledger"]["twin"]["lines"][:c["prehook_n_twin_lines"]]) == canonical(se["ledger"]["twin"]["lines"][:c["prehook_n_twin_lines"]]),
        "events": canonical(ne["events"][:c["prehook_n_events"]]) == canonical(se["events"][:c["prehook_n_events"]]),
        "history": canonical(ne["history"][:c["prehook_n_history"]]) == canonical(se["history"][:c["prehook_n_history"]]),
        **eligibility_checks(new["check"], stored["check"]),
    }
    return {"match": all(checks.values()), "checks": checks}


def paired_prehook_equal(control: dict, treatment: dict) -> dict:
    """Phase 1B gate 2: both arms reached the hook in the identical recorded state (same instance and replicate)."""
    a, b = control["harness"], treatment["harness"]
    same_unit = (control["instance_id"], a["replicate"], a["noise_seed"]) == (treatment["instance_id"], b["replicate"], b["noise_seed"])
    ca, cb = a["hook_calls"], b["hook_calls"]
    equal = same_unit and len(ca) == len(cb) == 1 and ca[0]["prehook_fingerprint"] == cb[0]["prehook_fingerprint"]
    diff = []
    if len(ca) == len(cb) == 1:
        fa, fb = ca[0].get("prehook_component_fingerprints") or {}, cb[0].get("prehook_component_fingerprints") or {}
        diff = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
    return {"equal": bool(equal), "same_unit": same_unit, "n_calls": (len(ca), len(cb)), "differing_components": diff}


# ------------------------------------------------------------------------------------------------------------ provenance
def _git(root: str, *args) -> str | None:
    """stdout of a read-only git command, or None if git failed."""
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def sha256_file(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def provenance_manifest(repo_root: str, inputs: dict, extra: dict | None = None) -> dict:
    """Git state, ACTUAL input checksums and git blob ids, the frozen reference, software versions (no physics)."""
    try:
        import mujoco
        mj = mujoco.__version__
    except Exception:  # noqa: BLE001
        mj = None
    import numpy as np
    status = _git(repo_root, "status", "--porcelain")
    blobs = {name: _git(repo_root, "rev-parse", f"HEAD:{A1E6[key]}") for name, key in TRACKED_INPUTS.items()}
    return {
        "harness_version": HARNESS_VERSION, "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git(repo_root, "rev-parse", "HEAD"), "git_branch": _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": None if status is None else bool(status), "git_status_porcelain": status,
        "inputs": {name: {"path": os.path.abspath(p), "sha256": sha256_file(p), "git_blob_at_head": blobs.get(name)}
                   for name, p in inputs.items()},
        "reference": REFERENCE,
        "python": sys.version.split()[0], "numpy": np.__version__, "mujoco": mj, "platform": platform.platform(),
        "engine_version": be.VERSION_V6, "agent_version": getattr(ha, "VERSION", None), "argv": list(sys.argv),
        **(extra or {}),
    }


def config_inputs(repo_root: str, artifacts_root: str) -> dict:
    return {"v6_settings": os.path.join(repo_root, A1E6["v6"]), "stop_model": os.path.join(repo_root, A1E6["stop_model"]),
            "split_file": os.path.join(repo_root, A1E6["split_file"]),
            "eval_instances": os.path.join(repo_root, A1E6["eval_instances"]),
            "thresholds": os.path.join(artifacts_root, A1E6["thresholds"]),
            "walkers": os.path.join(artifacts_root, A1E6["walkers"])}


def preflight_refusals(repo_root: str, inputs: dict, records_root: str | None, record_files: list,
                       harness_commit: str | None) -> list[str]:
    """Provenance validation against the frozen REFERENCE (empty list = may execute). Read-only git and file hashing."""
    ref, out = REFERENCE, []
    head = _git(repo_root, "rev-parse", "HEAD")
    if not harness_commit:
        out.append("--harness-commit (the approved 40-hex harness revision) is required")
    elif not re.fullmatch(r"[0-9a-f]{40}", harness_commit):
        out.append(f"--harness-commit must be a full 40-hex commit id, got {harness_commit!r}")
    elif head != harness_commit:
        out.append(f"harness revision HEAD {head} is not the approved {harness_commit}")
    status = _git(repo_root, "status", "--porcelain")
    if status is None:
        out.append("git status unavailable: cannot verify a clean worktree")
    elif status:
        out.append("the harness worktree is not clean (commit or remove every change before execution)")
    if _git(repo_root, "merge-base", "--is-ancestor", ref["implementation_commit"], "HEAD") is None:
        out.append(f"implementation commit {ref['implementation_commit']} is not an ancestor of HEAD")
    changed = _git(repo_root, "diff", "--name-only", ref["implementation_commit"], "HEAD", "--", *PROTECTED_SOURCE_PATHS)
    if changed is None:
        out.append("cannot diff the protected source paths against the implementation commit")
    elif changed:
        out.append(f"protected sources differ from {ref['implementation_commit'][:7]}: {changed.splitlines()}")
    for name, key in TRACKED_INPUTS.items():
        blob = _git(repo_root, "rev-parse", f"HEAD:{A1E6[key]}")
        if blob != ref["tracked_inputs_git_blob"][name]:
            out.append(f"input {name}: git blob {blob} != reference {ref['tracked_inputs_git_blob'][name]}")
    for name, want in ref["artifact_inputs_sha256"].items():
        got = sha256_file(inputs[name])
        if got != want:
            out.append(f"input {name}: sha256 {got} != reference {want} ({inputs[name]})")
    for fname in sorted(set(record_files)):
        want = ref["stored_records_sha256"].get(fname)
        got = sha256_file(os.path.join(records_root, fname)) if records_root else None
        if want is None:
            out.append(f"stored record {fname} has no frozen reference hash")
        elif got != want:
            out.append(f"stored record {fname}: sha256 {got} != reference {want}")
    return out


def protected_roots(repo_root: str) -> list[str] | None:
    """Resolved roots of every worktree of this repository (the original working directory included), or None if git
    cannot list them (callers must then refuse)."""
    listing = _git(repo_root, "worktree", "list", "--porcelain")
    common = _git(repo_root, "rev-parse", "--git-common-dir")
    if listing is None or common is None:
        return None
    roots = {os.path.realpath(repo_root)}
    for line in listing.splitlines():
        if line.startswith("worktree "):
            roots.add(os.path.realpath(line[len("worktree "):].strip()))
    common_abs = common if os.path.isabs(common) else os.path.join(repo_root, common)
    roots.add(os.path.realpath(os.path.dirname(os.path.realpath(common_abs))))
    return sorted(roots)


def inside(path: str, root: str) -> bool:
    p, r = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(root))
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def manifest_path(out: str) -> str:
    return out + ".manifest.json"


def output_refusals(out: str | None, repo_root: str) -> list[str]:
    """The output and its manifest must be fresh and outside every worktree of this repository."""
    if not out:
        return ["--out is required with --execute"]
    roots = protected_roots(repo_root)
    if roots is None:
        return ["cannot list this repository's worktrees with git: refusing to choose an output location"]
    refusals = []
    for p in (out, manifest_path(out)):
        hit = [r for r in roots if inside(p, r)]
        if hit:
            refusals.append(f"{p} is inside repository worktree {hit[0]} (outputs must stay outside every worktree)")
        if os.path.lexists(p):
            refusals.append(f"{p} already exists (a fresh output path is required; nothing is appended or resumed)")
    return refusals


def load_stored(records_root: str, fname: str, line: int) -> dict:
    with open(os.path.join(records_root, fname), encoding="utf-8") as fh:
        for i, text in enumerate(fh, 1):
            if i == line:
                return json.loads(text)
    raise ValueError(f"{fname} has no line {line}")


# ------------------------------------------------------------------------------------------------------------ physics
def parse_instance_id(instance_id: str) -> tuple[str, str, int]:
    parts = instance_id.split(":")
    if len(parts) != 3 or parts[1].startswith("devcomp"):
        raise ValueError(f"single-family instance id base:family:severity expected, got {instance_id!r}")
    return parts[0], parts[1], int(parts[2])


def build_instance(instance_id: str, inputs: dict, pool=None) -> dict:
    """The instance exactly as scripts/hdb_agent_run.py builds it (instances(), main()): make_instance_v2 on the dev base with
    the DS-1 thresholds, then check_eligibility. PHYSICS: check_eligibility runs 8 plant rollouts."""
    base_id, family, severity = parse_instance_id(instance_id)
    with open(inputs["split_file"], encoding="utf-8") as fh:
        split = json.load(fh)
    if base_id not in set(split[f"{A1E6['which']}_bases"]):
        raise ValueError(f"{base_id} is not a {A1E6['which']} base of the DS-1 split")
    if instance_id in set(split.get("excluded_from_transfer_eval") or []):
        raise ValueError(f"{instance_id} is excluded from transfer evaluation")
    variant, mult = hb.v2_severities(family)[severity]
    if float(mult) not in A1E6["mults"]:
        raise ValueError(f"{instance_id}: mult {mult} not in the DS-1 mults {A1E6['mults']}")
    bases = {b["base_id"]: b for b in hb.load_bases("dev", walkers_glob=inputs["walkers"])}
    with open(inputs["thresholds"], encoding="utf-8") as fh:
        th = json.load(fh)
    raw = hb.make_instance_v2(bases[base_id], family, severity, th)
    if raw is None:
        raise ValueError(f"{instance_id}: no instance (threshold missing or strength above the maximum)")
    inst = hb.check_eligibility(raw, pool=pool)
    if not inst["eligible"]:
        raise ValueError(f"{instance_id}: not eligible ({inst['reason']})")
    return inst


def run_episode(inst: dict, arm: str, replicate: int, inputs: dict, pool=None) -> dict:
    """One A1e6 episode (scripts/hdb_agent_run.run_one with arm A1e6) plus the engineer hook. PHYSICS."""
    from creature_forge.hdb_evidence import EvidenceWorkbench
    t0 = time.perf_counter()
    view = hb.policy_view(inst)
    noise = replicate_noise_seed(inst["instance_id"], replicate)
    bench = EvidenceWorkbench(view, inst["plant"], total_budget=A1E6["budget"], twin_budget=A1E6["twin_budget"], pool=pool,
                              noise_seed=noise)
    with open(inputs["stop_model"], encoding="utf-8") as fh:
        stop_model = json.load(fh)
    with open(inputs["v6_settings"], encoding="utf-8") as fh:
        v6 = json.load(fh)
    ep = be.Episode(bench, proposer=None, use_generic=A1E6["use_generic"], max_alive=A1E6["max_alive"], v6=v6)
    hook = HookRecorder(arm, bench, ep)
    session = ToolAccessSession(bench, ep, stop_model=stop_model, tau=A1E6["tau"], memory=None, learned=None, v5=False,
                                cases=None, engineer=hook)
    hook.session = session
    rec_agent = ha.run_agent(session, None, max_turns=A1E6["max_turns"], auto_learned=False)
    design = bench.best_design()
    ver = hb.verify(inst, {"body": design["body"], "vector": design["vector"]}, pool=pool)
    sp = ep.structure_posterior()
    inj = [list(x) for x in hb.mechanism_signature(inst)]
    engine = ep.record()
    rec = {
        "version": "hdb_agent_v1", "instance_id": inst["instance_id"], "family": inst["family"], "pair": inst["pair"],
        "severity": inst["severity"], "bench": inst["version"], "strength": inst.get("strength"), "mult": inst.get("mult"),
        "provenance": "NO_AI", "arm": A1E6["arm"], "check": inst["check"], "nemotron": None, "agent": rec_agent,
        "injected_structure": inj, "map_structure": [list(x) for x in sp[0][0]] if sp else None,
        "map_mass": sp[0][1] if sp else 0.0, "posterior_mass_on_injected": sum(w for s, w in sp if [list(x) for x in s] == inj),
        "repair": (rec_agent.get("conclusion") or {}).get("repair"), "submitted": design["index"],
        "verification": serialize_verification(ver),
        "stop_rule": {"model": A1E6["stop_model"], "tau": A1E6["tau"]}, "v6_settings": A1E6["v6"],
        "engine": engine, "designs": [{k: d[k] for k in ("index", "source", "body", "vector")} for d in bench.designs],
        "wall_s": time.perf_counter() - t0,
        "harness": {"version": HARNESS_VERSION, "ta1_arm": arm, "replicate": replicate, "noise_seed": noise,
                    "treatment_tool": TREATMENT_TOOL, "hook_calls": hook.calls,
                    "rescreen": rescreen_summary(engine["events"]),
                    "resources": resource_accounting(engine["ledger"], hook.calls, ver)},
    }
    rec = jsonable(rec)
    problems = verification_complete(rec["verification"]["full"])
    rec["harness"]["verification_complete"] = not problems
    rec["harness"]["verification_problems"] = problems
    return rec


# ------------------------------------------------------------------------------------------------------------ CLI
def planned_runs(phase: str, cases: list[str] | None = None) -> list[tuple]:
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {sorted(PHASES)}, got {phase!r}")
    runs = PHASES[phase]
    if phase == "2a-contingency":
        if not cases:
            raise ValueError("phase 2a-contingency runs only the cases named with --cases (after a pre-hook mismatch)")
        runs = [r for r in runs if r[0] in set(cases)]
    elif cases:
        raise ValueError("--cases is only used with phase 2a-contingency")
    return list(runs)


def phase_cap(runs: list) -> dict:
    n = len(runs)
    return {"episodes": n, "plant": n * PER_EPISODE_CAP["plant"], "twin": n * PER_EPISODE_CAP["twin"],
            "total": n * (PER_EPISODE_CAP["plant"] + PER_EPISODE_CAP["twin"])}


def stored_record_files(runs: list) -> list[str]:
    return sorted({CASES[c]["stored"][0] for c, _, _ in runs})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--phase", choices=sorted(PHASES))
    ap.add_argument("--cases", default=None, help="comma list of case ids (phase 2a-contingency only)")
    ap.add_argument("--execute", action="store_true", help="run physics (fail-closed preflight; separate owner approval)")
    ap.add_argument("--approved-by", default="", help="owner approval reference for this phase (recorded in the manifest)")
    ap.add_argument("--harness-commit", default=None, help="the approved harness revision; must equal HEAD")
    ap.add_argument("--max-rollouts", type=int, default=0, help="hard cap in 10 s rollout-equivalents (>= the phase cap)")
    ap.add_argument("--max-wall-s", type=float, default=0.0, help="stop before starting an episode once exceeded (0 = none)")
    ap.add_argument("--artifacts-root", default=os.path.join(ROOT, "artifacts", "hdb"),
                    help="directory holding thresholds_dev.json and walkers_all.jsonl")
    ap.add_argument("--records-root", default=os.path.join(ROOT, "artifacts", "vm", "ds1", "eval"),
                    help="directory holding the stored DS-1 eval_*.jsonl records")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", default=None, help="fresh JSONL output outside every worktree of this repository")
    a = ap.parse_args(argv)
    cases = [c for c in (a.cases or "").split(",") if c] or None
    inputs = config_inputs(ROOT, a.artifacts_root)
    if not a.phase:
        print(f"{HARNESS_VERSION}: dry run. Phases: " + ", ".join(f"{p} ({len(r)} episodes)" for p, r in PHASES.items()))
        print("Nothing was simulated. Choose --phase to see its plan; --execute requires separate owner approval.")
        return 0
    runs = planned_runs(a.phase, cases)
    cap = phase_cap(runs)
    print(f"{HARNESS_VERSION}: phase {a.phase}: {cap['episodes']} episodes; caps plant {cap['plant']}, twin {cap['twin']}, "
          f"total {cap['total']} rollout-equivalents")
    for c, arm, r in runs:
        iid = CASES[c]["instance_id"]
        print(f"  {c} {iid} arm={arm} replicate={r} noise_seed={replicate_noise_seed(iid, r)}")
    for name, p in inputs.items():
        print(f"  input {name}: {p} sha256={sha256_file(p) or 'MISSING'}")
    pre = preflight_refusals(ROOT, inputs, a.records_root, stored_record_files(runs), a.harness_commit)
    if not a.execute:
        print("  preflight: " + ("ok" if not pre else "would refuse: " + "; ".join(pre)))
        print("Dry run: nothing was simulated. Pass --execute only with the owner's approval for this phase.")
        return 0
    refusals = list(pre)
    if not a.approved_by.strip():
        refusals.append("--approved-by is required with --execute")
    if a.max_rollouts < cap["total"]:
        refusals.append(f"--max-rollouts {a.max_rollouts} is below the phase cap {cap['total']}")
    refusals += output_refusals(a.out, ROOT)
    missing = [n for n, p in inputs.items() if sha256_file(p) is None]
    if missing:
        refusals.append(f"missing inputs: {missing}")
    if refusals:
        for r in refusals:
            print("REFUSED:", r)
        return 2
    return _execute(a, runs, inputs, cap)


def _pause(msg: str, problems) -> int:
    print("PAUSE:", msg)
    for p in problems:
        print("   ", p)
    print("Output and manifest are preserved. Investigate before anything else runs.")
    return PAUSE_EXIT


def _execute(a, runs, inputs, cap, *, build_fn=None, run_fn=None, pool_cm=None) -> int:
    """Fail-closed execution of an approved phase. `build_fn`, `run_fn` and `pool_cm` are injectable for no-physics tests."""
    import contextlib
    build_fn = build_fn or build_instance
    run_fn = run_fn or run_episode
    if pool_cm is None:
        from creature_forge.forge_pool import ForgePool, InlinePool
        pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    manifest = provenance_manifest(ROOT, inputs, {"phase": a.phase, "approved_by": a.approved_by, "runs": runs, "cap": cap,
                                                  "max_rollouts": a.max_rollouts, "max_wall_s": a.max_wall_s,
                                                  "harness_commit_approved": a.harness_commit,
                                                  "records_root": os.path.abspath(a.records_root)})
    with open(manifest_path(a.out), "x", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    spent, t0, by_unit = 0.0, time.perf_counter(), {}
    with pool_cm as pool, open(a.out, "x", encoding="utf-8") as out:
        instances = {}
        for c, arm, r in runs:
            iid = CASES[c]["instance_id"]
            if a.max_wall_s and time.perf_counter() - t0 > a.max_wall_s:
                print("STOP: wall-clock cap reached before", c, arm, r)
                return PAUSE_EXIT
            if spent + PER_EPISODE_CAP["plant"] + PER_EPISODE_CAP["twin"] > a.max_rollouts:
                print("STOP: the rollout cap would be exceeded by", c, arm, r)
                return PAUSE_EXIT
            if iid not in instances:
                instances[iid] = build_fn(iid, inputs, pool=pool)
            rec = run_fn(instances[iid], arm, r, inputs, pool=pool)
            rec["harness"]["case"] = c
            problems = []
            if not rec["harness"].get("verification_complete"):
                problems += [f"incomplete verification record: {rec['harness'].get('verification_problems')}"]
            if len(rec["harness"]["hook_calls"]) != 1:
                problems.append(f"engineer hook called {len(rec['harness']['hook_calls'])} times (expected once)")
            if r == 0:
                f, line, _, _ = CASES[c]["stored"]
                stored = load_stored(a.records_root, f, line)
                if arm == "control":
                    rep = compare_to_stored(rec, stored)
                    rec["harness"]["reproduction"] = rep
                    if not rep["exact"]:
                        problems.append(f"control r0 does not reproduce the stored A1e6 fields: "
                                        f"{[k for k, v in rep['checks'].items() if not v]}")
                else:
                    pm = prehook_prefix_matches(rec, stored)
                    rec["harness"]["stored_prefix"] = pm
                    if not pm["match"]:
                        problems.append(f"treatment r0 pre-hook prefix differs from the stored record: "
                                        f"{[k for k, v in pm.get('checks', {}).items() if not v] or pm.get('reason')}")
            other = by_unit.get((c, r))
            if other is not None and other["harness"]["ta1_arm"] != arm:
                pair = paired_prehook_equal(*(sorted([other, rec], key=lambda x: x["harness"]["ta1_arm"])))
                rec["harness"]["paired_prehook"] = pair
                if not pair["equal"]:
                    problems.append(f"arm pair pre-hook fingerprints differ: {pair['differing_components']}")
            by_unit[(c, r)] = rec
            out.write(json.dumps(rec) + "\n")
            out.flush()
            spent += rec["harness"]["resources"]["total_rollout_equivalents"]
            s = rec["verification"]["summary"]
            print(c, iid, arm, r, s["status"], round(s["walking_frac"] * 24), "rescreen:", rec["harness"]["rescreen"]["classification"],
                  "spent", round(spent), flush=True)
            if problems:
                return _pause(f"{c} {arm} r{r} is invalid for the matched comparison", problems)
    print("DONE: every run passed its validity checks (outcomes are not interpreted here).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
