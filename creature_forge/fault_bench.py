"""Fault benchmark for the causal engineer (`fault_bench_v1`).

Healthy, verified walking designs (FULL_RECOVERY in the committed research records, read-only) get ONE injected single fault
from a family of mechanisms with similar symptoms (the robot falls). Every fault has a matching low-dimensional repair tool;
per instance the benchmark MEASURES a counterfactual-repair matrix (every tool run at the same small budget from the faulty
design, walking fraction on disjoint check seeds). The matrix, the fault label and the severity are ground truth for evaluation
and training targets; they are never shown to a policy (`policy_view` is the only thing a policy gets).

Rules (docs: physics-integrity)
  * Faults are deterministic transformations. A value outside the guided body bounds (`morphology.BOUNDS`) or the controller
    bounds (`phasegait_fp.LOWER17/UPPER17`) makes the instance INVALID with a named reason; nothing is ever clipped.
  * Severity s in [0, 1] maps linearly from the first (mild) to the second (severe) end of the documented range.
  * Seeds come from `creature_gen.walkrec_seed_block(campaign, role, f"{base_id}:{fault}:{severity}", k)`. Benchmark role names
    map to the existing, disjoint seed-namespace roles: check -> "screen", train -> "train", obs -> "probe",
    validate -> "validate", confirm -> "confirm".
  * Final verification (`verify`) is `recovery.assess` (full_recovery_v1) on validate/confirm seeds that the policy never sees and
    that are asserted disjoint from check/train/obs.
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
from typing import Callable, Sequence

import numpy as np

from . import creature_gen as cg
from .arena import VARIATION_PRESET
from .morphology import BOUNDS as GUIDED_BOUNDS
from .phasegait_fp import LOWER17, UPPER17
from .walk_opt import ALL_NAMES, SUBSPACES

VERSION = "fault_bench_v1"
CHECK_N = 8
TRAIN_N = 8                 # block size; a bench uses the first n_train
OBS_N = 8
VALIDATE_N = 24
CONFIRM_N = 24
FAIL_MAX_WALKING = 2        # the faulty robot must walk on <= 2 of the 8 check seeds
REPAIR_MIN_WALKING = 6      # the matching tool must restore walking on >= 6 of the 8 check seeds
DEFAULT_BUDGET = 160        # protocol parameter B: rollouts of every tool in the repair matrix
DEFAULT_TRAIN = 4
SEED_ROLES = {"check": "screen", "train": "train", "obs": "probe", "validate": "validate", "confirm": "confirm"}
SEED_COUNTS = {"check": CHECK_N, "train": TRAIN_N, "obs": OBS_N, "validate": VALIDATE_N, "confirm": CONFIRM_N}

DEV_PATTERNS = ("experiments/walk_recovery/dev_pilot/results/shard*.jsonl",
                "experiments/walk_recovery/dev_pilot/results_s2b/*.jsonl")
HELDOUT_PATTERNS = ("experiments/walk_recovery/confirmatory/results/shard*.jsonl",)
SPLITS = {"dev": DEV_PATTERNS, "heldout": HELDOUT_PATTERNS}
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_LEG = ("thigh_length", "shank_length", "foot_length")


class InvalidInstance(ValueError):
    """A fault / counterfactual would leave the guided or controller bounds (never clipped)."""


# ------------------------------------------------------------------------------------------------------------------ bases
def load_bases(split: str, root: str | None = None) -> list[dict]:
    """One verified-walking base per creature, read-only from the committed research records.

    Candidates are records with status FULL_RECOVERY; per creature the lexicographically first method (then first unit) wins.
    -> [{base_id, creature, source_unit, body, vector (17), features, region}] sorted by creature."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {sorted(SPLITS)}")
    root = root or _REPO
    best: dict[str, tuple] = {}
    for pat in SPLITS[split]:
        for path in sorted(glob.glob(os.path.join(root, pat))):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("status") != "FULL_RECOVERY":
                        continue
                    fin = rec["pipeline"]["final"]
                    vec = [float(x) for x in fin["vector"]]
                    if len(vec) != 17:
                        continue
                    key = (str(rec["method"]), str(rec["unit"]))
                    cur = best.get(rec["creature"])
                    if cur is None or key < cur[0]:
                        best[rec["creature"]] = (key, rec, fin, vec)
    out = []
    for creature in sorted(best):
        key, rec, fin, vec = best[creature]
        out.append({"base_id": creature, "creature": creature, "source_unit": rec["unit"], "body": dict(fin["body"]),
                    "vector": vec, "features": dict(rec["features"]), "region": rec["region"]})
    return out


def base_families(bases: Sequence[dict]) -> dict:
    """creature_gen region of every base: {base_id: region} (for held-out-family evaluation)."""
    return {b["base_id"]: b["region"] for b in bases}


# ------------------------------------------------------------------------------------------------------------------ changes
def full_body(body: dict) -> dict:
    d = dict(body)
    for k in _LEG:
        if d.get(k + "_r") is None:
            d[k + "_r"] = d[k]
    d["pose"] = list(d.get("pose") or [0.0] * 7)
    return d


def _body_fields(param: str) -> tuple:
    if param == "leg_length":
        return ("thigh_length", "thigh_length_r", "shank_length", "shank_length_r")
    return (param, param + "_r") if param in _LEG else (param,)


BODY_CHANGE_PARAMS = ("torso_mass", "foot_length", "torque_limit", "foot_friction", "leg_length", "thigh_length",
                      "shank_length", "leg_density")


def apply_changes(body: dict, vector: Sequence[float], changes: Sequence[dict]) -> tuple[dict, list]:
    """Apply atomic changes {"param", "op": scale|add|set, "value"} to (body, 17-D vector). Raises InvalidInstance if any
    result leaves the guided body bounds or the controller bounds. Inputs are not modified; nothing is clipped."""
    b = full_body(body)
    v = [float(x) for x in vector]
    if len(v) != 17:
        raise ValueError("vector must be 17-D")
    for ch in changes:
        p, op, val = ch["param"], ch["op"], float(ch["value"])
        if op not in ("scale", "add", "set"):
            raise ValueError(f"unknown op {op!r}")
        if p in ALL_NAMES:
            i = ALL_NAMES.index(p)
            v[i] = v[i] * val if op == "scale" else v[i] + val if op == "add" else val
        elif p in BODY_CHANGE_PARAMS:
            for f in _body_fields(p):
                b[f] = float(b[f]) * val if op == "scale" else float(b[f]) + val if op == "add" else val
        else:
            raise ValueError(f"unknown parameter {p!r}")
    for i, name in enumerate(ALL_NAMES):
        if not (math.isfinite(v[i]) and LOWER17[i] <= v[i] <= UPPER17[i]):
            raise InvalidInstance(f"{name}={v[i]:.6g} outside controller bounds [{LOWER17[i]:g}, {UPPER17[i]:g}]")
    for k, (lo, hi) in GUIDED_BOUNDS.items():
        for f in (k, k + "_r") if k in _LEG else (k,):
            if f in b and b[f] is not None and not (math.isfinite(float(b[f])) and lo <= float(b[f]) <= hi):
                raise InvalidInstance(f"{f}={float(b[f]):.6g} outside guided bounds [{lo:g}, {hi:g}]")
    return b, v


# ------------------------------------------------------------------------------------------------------------------ faults
# severity s in [0,1]: value = mild + s * (severe - mild)
FAULTS = {
    "posture_lean": {"ranges": {"pitch_ref_add": (0.05, 0.20)}, "tool": "posture"},
    "cadence_fast": {"ranges": {"freq_scale": (1.2, 1.6)}, "tool": "timing"},
    "feedback_loss": {"ranges": {"gain_scale": (0.4, 0.1)}, "tool": "feedback"},
    "placement_loss": {"ranges": {}, "tool": "placement"},
    "short_feet": {"ranges": {"foot_length_scale": (0.75, 0.55)}, "tool": "foot_length"},
    "heavy_torso": {"ranges": {"torso_mass_scale": (1.4, 2.0)}, "tool": "torso_mass"},
    "weak_motors": {"ranges": {"torque_limit_scale": (0.5, 0.25)}, "tool": "torque_limit"},
    "slippery": {"ranges": {"foot_friction_scale": (0.25, 0.08)}, "tool": "foot_friction"},
}
MATCHING_TOOL = {f: d["tool"] for f, d in FAULTS.items()}
PLACEMENT_MIN_USE = 0.05     # placement_loss is meaningful only if max(|fp_kd|, |fp_kv|) > 0.05

# For humans and the benchmark only. NEVER shown to the AI.
FAULT_DOCS = {
    "posture_lean": "Torso reference pitched forward by 0.05-0.20 rad: the centre of mass sits ahead of the feet, the robot tips "
                    "forward (symptom: forward fall). Fixed by re-trimming posture (hip_bias, pitch_ref, stance_knee, start_lean).",
    "cadence_fast": "Stride frequency x1.2-1.6: the swing leg cannot reach the ground placement and the stance has no time to "
                    "recover (symptom: forward fall / stumbling). Fixed by timing (freq, duty, knee_shift).",
    "feedback_loss": "Balance and pitch feedback gains x0.1-0.4: disturbances are no longer rejected (symptom: fall after a push, "
                     "drift of the torso angle). Fixed by feedback gains (kp, kd, balance_gain, pitch_kp, sync_gain).",
    "placement_loss": "Swing-foot placement gains (Raibert/SIMBICON capture-step feedback) removed: the foot lands under the hip "
                      "instead of ahead of the falling COM (symptom: forward fall at speed). Only meaningful when the base uses "
                      "them. Fixed by placement (fp_kd, fp_kv).",
    "short_feet": "Both feet shortened to 55-75 % of their length: the support polygon shrinks, the COP runs off the toe "
                  "(symptom: forward fall, small stability margin). Fixed by foot length (body).",
    "heavy_torso": "Torso mass x1.4-2.0: higher inertia and gravity load at the same torque (symptom: sagging knees, forward "
                   "fall, torque saturation). Fixed by torso mass (body).",
    "weak_motors": "Joint torque limit x0.25-0.5: actuation saturates (symptom: collapse under load, slow tracking, saturation). "
                   "Fixed by torque limit (body).",
    "slippery": "Foot friction x0.08-0.25 (guided floor 0.05): feet slip at push-off and touchdown (symptom: sliding, fall). "
                "Fixed by foot friction (body).",
}


def _lerp(rng: tuple, s: float) -> float:
    return rng[0] + s * (rng[1] - rng[0])


def fault_changes(fault: str, severity: float) -> list[dict]:
    if fault not in FAULTS:
        raise ValueError(f"unknown fault {fault!r}; known: {list(FAULTS)}")
    if isinstance(severity, bool) or not isinstance(severity, (int, float)) or not 0.0 <= severity <= 1.0:
        raise ValueError("severity must be a number in [0, 1]")
    r = FAULTS[fault]["ranges"]
    s = float(severity)
    if fault == "posture_lean":
        return [{"param": "pitch_ref", "op": "add", "value": _lerp(r["pitch_ref_add"], s)}]
    if fault == "cadence_fast":
        return [{"param": "freq", "op": "scale", "value": _lerp(r["freq_scale"], s)}]
    if fault == "feedback_loss":
        f = _lerp(r["gain_scale"], s)
        return [{"param": "balance_gain", "op": "scale", "value": f}, {"param": "pitch_kp", "op": "scale", "value": f}]
    if fault == "placement_loss":
        return [{"param": "fp_kd", "op": "set", "value": 0.0}, {"param": "fp_kv", "op": "set", "value": 0.0}]
    if fault == "short_feet":
        return [{"param": "foot_length", "op": "scale", "value": _lerp(r["foot_length_scale"], s)}]
    if fault == "heavy_torso":
        return [{"param": "torso_mass", "op": "scale", "value": _lerp(r["torso_mass_scale"], s)}]
    if fault == "weak_motors":
        return [{"param": "torque_limit", "op": "scale", "value": _lerp(r["torque_limit_scale"], s)}]
    return [{"param": "foot_friction", "op": "scale", "value": _lerp(r["foot_friction_scale"], s)}]


def inject(base: dict, fault: str, severity: float) -> dict:
    """-> {"valid": bool, "reason": str|None, "body", "vector", "changes"}. Invalid instances carry the reason (never clipped)."""
    changes = fault_changes(fault, severity)
    out = {"valid": False, "reason": None, "body": None, "vector": None, "changes": changes}
    if fault == "placement_loss":
        vec = base["vector"]
        use = max(abs(vec[ALL_NAMES.index("fp_kd")]), abs(vec[ALL_NAMES.index("fp_kv")]))
        if not use > PLACEMENT_MIN_USE:
            out["reason"] = f"base does not use foot placement (max |fp| = {use:.4g} <= {PLACEMENT_MIN_USE})"
            return out
    try:
        body, vector = apply_changes(base["body"], base["vector"], changes)
    except InvalidInstance as exc:
        out["reason"] = f"out of bounds: {exc}"
        return out
    out.update(valid=True, body=body, vector=vector)
    return out


# ------------------------------------------------------------------------------------------------------------------ tools
# Repair tools: control subspaces (walk_opt.SUBSPACES) and body parameters. Body repairs search the edit-rule ratio box
# [0.5, 1.5] relative to the body the repair starts from, inside the guided bounds (walk_opt.SearchSpace, mode "guided").
CONTROL_TOOLS = ("posture", "timing", "feedback", "stride", "placement")
BODY_TOOLS = {"foot_length": ("foot_length",), "torso_mass": ("torso_mass",), "torque_limit": ("torque_limit",),
              "foot_friction": ("foot_friction",), "leg_length": ("thigh_length", "shank_length")}
TOOLS = {**{t: {"kind": "control", "subspaces": (t,), "ctrl": SUBSPACES[t], "body": ()} for t in CONTROL_TOOLS},
         **{t: {"kind": "body", "subspaces": (), "ctrl": (), "body": b} for t, b in BODY_TOOLS.items()}}


def tool_dims(tool: str) -> dict:
    if tool not in TOOLS:
        raise ValueError(f"unknown tool {tool!r}; known: {list(TOOLS)}")
    t = TOOLS[tool]
    return {"ctrl_params": list(t["ctrl"]), "body_params": list(t["body"]), "dim": len(t["ctrl"]) + len(t["body"])}


# ------------------------------------------------------------------------------------------------------------------ seeds
def instance_key(base_id: str, fault: str, severity: float) -> str:
    return f"{base_id}:{fault}:{float(severity)}"


def instance_seeds(campaign: str, base_id: str, fault: str, severity: float) -> dict:
    key = instance_key(base_id, fault, severity)
    return {name: list(cg.walkrec_seed_block(campaign, SEED_ROLES[name], key, SEED_COUNTS[name])) for name in SEED_ROLES}


def assert_disjoint_roles(seeds: dict, verification_roles=("validate", "confirm"), other_roles=("check", "train", "obs")) -> None:
    ver = {s for r in verification_roles for s in seeds[r]}
    oth = {s for r in other_roles for s in seeds[r]}
    if ver & oth:
        raise ValueError(f"verification seeds overlap check/train/obs seeds: {sorted(ver & oth)[:5]}")
    if set(seeds["validate"]) & set(seeds["confirm"]):
        raise ValueError("validate and confirm seeds overlap")


def policy_view(instance: dict) -> dict:
    """Everything a policy may see about an instance: an opaque id, the faulty robot and its train/obs seeds. Not the fault,
    severity, tool matrix, check/validate/confirm seeds."""
    oid = hashlib.sha256(("view:" + instance["instance_id"]).encode()).hexdigest()[:12]
    return {"robot_id": oid, "robot": {"body": instance["robot"]["body"], "vector": instance["robot"]["vector"]},
            "seeds": {"train": list(instance["seeds"]["train"]), "obs": list(instance["seeds"]["obs"])}}


# ------------------------------------------------------------------------------------------------------------------ evaluation
def verify(instance: dict, design: dict, pool=None, *, assess_fn: Callable | None = None) -> dict:
    """Independent final verification: recovery.assess(original=faulty robot, candidate=design, validate seeds, confirm seeds).
    Uncharged; the seeds are never visible to a policy. design = {"body", "vector"}."""
    seeds = instance["seeds"]
    assert_disjoint_roles(seeds)
    if assess_fn is None:
        from .recovery import assess as assess_fn
    return assess_fn(original=instance["robot"], candidate={"body": design["body"], "vector": list(design["vector"])},
                     validate_seeds=seeds["validate"], confirm_seeds=seeds["confirm"], pool=pool)


def _walk_check(body, vector, seeds, pool, walk_fn) -> dict:
    if walk_fn is None:
        from .recovery import run_walk_seeds as walk_fn
    rows = walk_fn(body, vector, seeds, duration=10.0, variation=VARIATION_PRESET, pool=pool)
    errs = [r for r in rows if r.get("outcome") == "ERROR"]
    walking = sum(1 for r in rows if r.get("walking"))
    return {"walking": walking, "n": len(rows), "frac": walking / len(rows) if rows else 0.0, "errors": len(errs),
            "error_messages": [str(r.get("error")) for r in errs][:3]}


def _tool_noise_seed(instance_id: str, tool: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{instance_id}:{tool}".encode()).digest()[:4], "big") % (2 ** 31)


def build_instance(base: dict, fault: str, severity: float, campaign: str, pool=None, *, budget: int = DEFAULT_BUDGET,
                   n_train: int = DEFAULT_TRAIN, n_check: int = CHECK_N, tools: Sequence[str] | None = None,
                   cma_fn: Callable | None = None, walk_fn: Callable | None = None) -> dict:
    """Inject, require the faulty robot to fail, run every repair tool at budget B and measure walking on the check seeds.

    The record is always returned (invalid / not-failing / not-kept ones carry `valid`, `kept` and `reason`).
    repair_matrix[tool] = walking fraction on the n_check check seeds; kept = the matching tool restores walking on
    >= 6/8 (scaled to n_check) of them."""
    from . import eng_tools
    iid = instance_key(base["base_id"], fault, severity)
    seeds = instance_seeds(campaign, base["base_id"], fault, severity)
    rec = {"version": VERSION, "instance_id": iid, "base_id": base["base_id"], "source_unit": base["source_unit"],
           "region": base["region"], "features": base["features"], "fault": fault, "severity": float(severity),
           "matching_tool": MATCHING_TOOL[fault], "campaign": campaign, "budget": int(budget), "n_train": int(n_train),
           "seeds": seeds, "valid": False, "kept": False, "reason": None, "rollouts": 0}
    inj = inject(base, fault, severity)
    rec["changes"] = inj["changes"]
    if not inj["valid"]:
        rec["reason"] = inj["reason"]
        return rec
    rec["valid"] = True
    robot = {"body": inj["body"], "vector": inj["vector"]}
    rec["robot"] = robot
    check = seeds["check"][:n_check]
    min_ok = math.ceil(REPAIR_MIN_WALKING * len(check) / CHECK_N)
    max_fail = math.floor(FAIL_MAX_WALKING * len(check) / CHECK_N)
    faulty = _walk_check(robot["body"], robot["vector"], check, pool, walk_fn)
    rec["rollouts"] += faulty["n"]
    rec["faulty_check"] = faulty
    if faulty["errors"]:
        rec.update(valid=False, reason=f"error during faulty check: {faulty['error_messages']}")
        return rec
    if faulty["walking"] > max_fail:
        rec.update(reason=f"faulty robot still walks on {faulty['walking']}/{faulty['n']} check seeds (needs <= {max_fail})")
        return rec
    matrix, detail = {}, {}
    for tool in (tools or list(TOOLS)):
        try:
            res = eng_tools.run_repair(robot, tool, budget, seeds["train"][:n_train], _tool_noise_seed(iid, tool), pool,
                                       cma_fn=cma_fn)
        except ValueError as exc:      # tool unavailable for this robot (no room inside the bounds)
            detail[tool] = {"unavailable": str(exc)}
            continue
        best = res["best"]
        chk = _walk_check(best["body"], best["vector"], check, pool, walk_fn)
        rec["rollouts"] += res["rollouts_used"] + chk["n"]
        detail[tool] = {"walking": chk["walking"], "n": chk["n"], "errors": chk["errors"], "rollouts": res["rollouts_used"],
                        "train_walking": best["walking_count"], "train_fitness": best["mean_fitness"]}
        if not chk["errors"]:
            matrix[tool] = chk["frac"]
    rec["repair_matrix"] = matrix
    rec["repair_detail"] = detail
    rec["ranking"] = sorted(matrix, key=lambda t: (-matrix[t], t))
    rec["n_tools_that_repair"] = sum(1 for t, f in matrix.items() if round(f * len(check)) >= min_ok)
    m = MATCHING_TOOL[fault]
    ok = m in matrix and round(matrix[m] * len(check)) >= min_ok
    rec["kept"] = bool(ok)
    if not ok:
        rec["reason"] = f"matching tool {m} restores walking on {detail.get(m, {}).get('walking', 'n/a')}/{len(check)} check seeds (needs >= {min_ok})"
    return rec
