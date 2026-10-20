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
    sha256 fingerprint of the pre-hook state (plant and twin ledgers, engine events, history, experiments, state, ranking),
    resource accounting split at the hook, re-screen events (recorded, never used to discard an outcome) and a provenance
    manifest.
  * Nothing runs physics unless `--execute`, an approved `--phase`, `--approved-by` and a sufficient `--max-rollouts` are
    given. The default is a dry run that only prints the plan.

Randomness (FA-1C randomisation audit): replicate r changes only the bench noise seed, i.e. the plant-CMA streams
(hdb_workbench.py:155, seed = noise + 7919 * repair index). DS-1 used int.from_bytes(instance_id[:4]) % 2**31, which is the
same value for every hdb-v1 instance (1751409197); replicate r uses that value + 10007 * r, so r = 0 is the DS-1 seed. Twin
CMA seeds (0, 11), physical seeds, conditions and the instance are fixed: replicates are technical replicates of plant-CMA
stochasticity, not new robots and not validation-seed generalisation.

Usage:
  python scripts/ta1_tool_access.py --phase 1B                       # dry run (default): plan, caps, input hashes
  python scripts/ta1_tool_access.py --phase 1B --execute --approved-by "<owner, date>" --max-rollouts 7208 \\
      --artifacts-root <dir with thresholds_dev.json, walkers_all.jsonl> --out <path outside the repository>.jsonl
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from creature_forge import belief_engine as be      # noqa: E402
from creature_forge import has_agent as ha          # noqa: E402
from creature_forge import hdb_bench as hb          # noqa: E402
from creature_forge.optimize import jsonable        # noqa: E402

HARNESS_VERSION = "ta1_harness_v1"
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

# preregistered cases (FA-1C section D); stored = the DS-1 A1e6 record used as reference
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


def prehook_snapshot(bench, ep, state: dict, ranking: list) -> dict:
    """Everything that determines the episode up to the hook (deep copies: later mutation cannot change it)."""
    return copy.deepcopy(jsonable({
        "plant_lines": bench.budget.lines, "plant_used": bench.budget.used,
        "twin_lines": bench.twin.lines, "twin_used": bench.twin.used,
        "events": ep.events, "history": ep.history,
        "experiments": [{k: v for k, v in e.items() if k != "design"} for e in ep.experiments],
        "state": state, "ranking": ranking,
    }))


class HookRecorder:
    """The `engineer(state, ranking)` callback: fingerprints the pre-hook state, then returns the arm's plan."""

    def __init__(self, arm: str, bench, ep):
        if arm not in ARM_PLANS:
            raise ValueError(f"arm must be one of {sorted(ARM_PLANS)}, got {arm!r}")
        self.arm, self.b, self.ep = arm, bench, ep
        self.calls: list[dict] = []

    def __call__(self, state: dict, ranking: list) -> dict:
        snap = prehook_snapshot(self.b, self.ep, state, ranking)
        tools = [r.get("tool") for r in ranking]
        plan = ARM_PLANS[self.arm](state, ranking)
        self.calls.append({
            "arm": self.arm, "plan": copy.deepcopy(plan), "ranking_tools": tools,
            "treatment_tool_in_ranking": TREATMENT_TOOL in tools,
            "treatment_tool_rank": (tools.index(TREATMENT_TOOL) + 1) if TREATMENT_TOOL in tools else None,
            "prehook_fingerprint": fingerprint(snap), "prehook_plant_used": snap["plant_used"],
            "prehook_twin_used": snap["twin_used"], "prehook_n_plant_lines": len(snap["plant_lines"]),
            "prehook_n_twin_lines": len(snap["twin_lines"]), "prehook_n_events": len(snap["events"]),
            "prehook_n_history": len(snap["history"]),
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


def design_hash(design: dict) -> str:
    """The 10-hex-digit design identifier used in FA-1C (body + vector)."""
    return hashlib.sha256(json.dumps({"b": design["body"], "v": design["vector"]}, sort_keys=True).encode()).hexdigest()[:10]


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


def compare_to_stored(new: dict, stored: dict) -> dict:
    """Exact-reproduction checks of a harness control record against the stored DS-1 A1e6 record (Phase 1B gate 1).
    The only expected difference is the harness's own `engineer_plan` event."""
    nd, sd = new["designs"][new["submitted"]], stored["designs"][stored["submitted"]]
    ne, se = new["engine"], stored["engine"]
    nv = new["verification"]["summary"] if "summary" in new["verification"] else new["verification"]
    checks = {
        "submitted_index": new["submitted"] == stored["submitted"],
        "submitted_design_hash": design_hash(nd) == design_hash(sd),
        "all_design_hashes": [design_hash(d) for d in new["designs"]] == [design_hash(d) for d in stored["designs"]],
        "status": nv["status"] == stored["verification"]["status"],
        "walking_frac": nv["walking_frac"] == stored["verification"]["walking_frac"],
        "verdict": stored_verdict(nv) == stored_verdict(stored["verification"]),
        "plant_used": ne["ledger"]["used"] == se["ledger"]["used"],
        "twin_used": ne["ledger"]["twin"]["used"] == se["ledger"]["twin"]["used"],
        "plant_lines": canonical(ne["ledger"]["lines"]) == canonical(se["ledger"]["lines"]),
        "twin_lines": canonical(ne["ledger"]["twin"]["lines"]) == canonical(se["ledger"]["twin"]["lines"]),
        "events_except_engineer_plan": canonical(_strip_hook_events(ne["events"])) == canonical(_strip_hook_events(se["events"])),
        "history": canonical(ne["history"]) == canonical(se["history"]),
        "eligibility_labels": new["check"]["labels"] == stored["check"]["labels"],
    }
    return {"exact": all(checks.values()), "checks": checks}


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
    }
    return {"match": all(checks.values()), "checks": checks}


def paired_prehook_equal(control: dict, treatment: dict) -> dict:
    """Phase 1B gate 2: both arms reached the hook in the identical state (same instance and replicate)."""
    a, b = control["harness"], treatment["harness"]
    same_unit = (control["instance_id"], a["replicate"], a["noise_seed"]) == (treatment["instance_id"], b["replicate"], b["noise_seed"])
    ca, cb = a["hook_calls"], b["hook_calls"]
    equal = same_unit and len(ca) == len(cb) == 1 and ca[0]["prehook_fingerprint"] == cb[0]["prehook_fingerprint"]
    return {"equal": bool(equal), "same_unit": same_unit, "n_calls": (len(ca), len(cb))}


# ------------------------------------------------------------------------------------------------------------ provenance
def _git(root: str, *args) -> str | None:
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
    """Git state, input checksums and software versions (no physics; mujoco is only imported for its version)."""
    try:
        import mujoco
        mj = mujoco.__version__
    except Exception:  # noqa: BLE001
        mj = None
    import numpy as np
    status = _git(repo_root, "status", "--porcelain")
    return {
        "harness_version": HARNESS_VERSION, "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git(repo_root, "rev-parse", "HEAD"), "git_branch": _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": None if status is None else bool(status), "git_status_porcelain": status,
        "inputs": {name: {"path": os.path.abspath(p), "sha256": sha256_file(p)} for name, p in inputs.items()},
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
    split = json.load(open(inputs["split_file"], encoding="utf-8"))
    if base_id not in set(split[f"{A1E6['which']}_bases"]):
        raise ValueError(f"{base_id} is not a {A1E6['which']} base of the DS-1 split")
    if instance_id in set(split.get("excluded_from_transfer_eval") or []):
        raise ValueError(f"{instance_id} is excluded from transfer evaluation")
    variant, mult = hb.v2_severities(family)[severity]
    if float(mult) not in A1E6["mults"]:
        raise ValueError(f"{instance_id}: mult {mult} not in the DS-1 mults {A1E6['mults']}")
    bases = {b["base_id"]: b for b in hb.load_bases("dev", walkers_glob=inputs["walkers"])}
    th = json.load(open(inputs["thresholds"], encoding="utf-8"))
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
    stop_model = json.load(open(inputs["stop_model"], encoding="utf-8"))
    ep = be.Episode(bench, proposer=None, use_generic=A1E6["use_generic"], max_alive=A1E6["max_alive"],
                    v6=json.load(open(inputs["v6_settings"], encoding="utf-8")))
    hook = HookRecorder(arm, bench, ep)
    session = ToolAccessSession(bench, ep, stop_model=stop_model, tau=A1E6["tau"], memory=None, learned=None, v5=False,
                                cases=None, engineer=hook)
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


def inside(path: str, root: str) -> bool:
    p, r = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    return p == r or p.startswith(r + os.sep)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--phase", choices=sorted(PHASES))
    ap.add_argument("--cases", default=None, help="comma list of case ids (phase 2a-contingency only)")
    ap.add_argument("--execute", action="store_true", help="run physics (needs --phase, --approved-by, --max-rollouts, --out)")
    ap.add_argument("--approved-by", default="", help="owner approval reference for this phase (recorded in the manifest)")
    ap.add_argument("--max-rollouts", type=int, default=0, help="hard cap in 10 s rollout-equivalents (>= the phase cap)")
    ap.add_argument("--max-wall-s", type=float, default=0.0, help="stop before starting an episode once exceeded (0 = none)")
    ap.add_argument("--artifacts-root", default=os.path.join(ROOT, "artifacts", "hdb"),
                    help="directory holding thresholds_dev.json and walkers_all.jsonl")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", default=None, help="JSONL output; must be outside the repository")
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
    if not a.execute:
        print("Dry run: nothing was simulated. Pass --execute only with the owner's approval for this phase.")
        return 0
    refusals = []
    if not a.approved_by.strip():
        refusals.append("--approved-by is required with --execute")
    if a.max_rollouts < cap["total"]:
        refusals.append(f"--max-rollouts {a.max_rollouts} is below the phase cap {cap['total']}")
    if not a.out:
        refusals.append("--out is required with --execute")
    elif inside(a.out, ROOT):
        refusals.append("--out must be outside the repository (records stay out of git until publication is approved)")
    missing = [n for n, p in inputs.items() if sha256_file(p) is None]
    if missing:
        refusals.append(f"missing inputs: {missing}")
    if refusals:
        for r in refusals:
            print("REFUSED:", r)
        return 2
    return _execute(a, runs, inputs, cap)


def _execute(a, runs, inputs, cap) -> int:          # pragma: no cover - physics; Phase 1B+ only, with owner approval
    import contextlib
    from creature_forge.forge_pool import ForgePool, InlinePool
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    manifest = provenance_manifest(ROOT, inputs, {"phase": a.phase, "approved_by": a.approved_by, "runs": runs, "cap": cap,
                                                  "max_rollouts": a.max_rollouts, "max_wall_s": a.max_wall_s})
    with open(a.out + ".manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    done = set()
    if os.path.exists(a.out):
        for line in open(a.out, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                done.add((r["instance_id"], r["harness"]["ta1_arm"], r["harness"]["replicate"]))
    spent, t0 = 0.0, time.perf_counter()
    pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    with pool_cm as pool, open(a.out, "a", encoding="utf-8") as out:
        instances = {}
        for c, arm, r in runs:
            iid = CASES[c]["instance_id"]
            if (iid, arm, r) in done:
                continue
            if a.max_wall_s and time.perf_counter() - t0 > a.max_wall_s:
                print("STOP: wall-clock cap reached before", c, arm, r)
                break
            if spent + PER_EPISODE_CAP["plant"] + PER_EPISODE_CAP["twin"] > a.max_rollouts:
                print("STOP: the rollout cap would be exceeded by", c, arm, r)
                break
            if iid not in instances:
                instances[iid] = build_instance(iid, inputs, pool=pool)
            rec = run_episode(instances[iid], arm, r, inputs, pool=pool)
            rec["harness"]["case"] = c
            out.write(json.dumps(rec) + "\n")
            out.flush()
            spent += rec["harness"]["resources"]["total_rollout_equivalents"]
            s = rec["verification"]["summary"]
            print(c, iid, arm, r, s["status"], round(s["walking_frac"] * 24), "rescreen:", rec["harness"]["rescreen"]["classification"],
                  "spent", round(spent), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
