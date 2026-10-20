"""FA-1B shared loaders (read-only). Reads stored JSON records only: no creature_forge import, no simulation, no network.
Bounds/probe constants are COPIED from the pinned source (ea9e729) with their file:line so the reconstruction is auditable."""
from __future__ import annotations

import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(OUT, "..", "Creature-Forge"))
FA1 = os.path.abspath(os.path.join(OUT, "..", "creature_forge_forensics_2026-10-20"))
EVAL_DIR = os.path.join(REPO, "artifacts", "vm", "ds1", "eval")
DS1_DIR = os.path.join(REPO, "artifacts", "vm", "ds1")
STREAM_DIR = os.path.join(REPO, "artifacts", "vm", "hdb", "artifacts", "hdb", "ds1", "stream")
FULL = "FULL_RECOVERY"

# creature_forge/morphology.py:9-17 (guided bounds; fault_bench.apply_changes imports them as GUIDED_BOUNDS, fault_bench.py:32)
GUIDED = {"torso_mass": (1.0, 15.0), "thigh_length": (0.15, 0.6), "shank_length": (0.15, 0.6), "foot_length": (0.06, 0.30),
          "foot_friction": (0.05, 2.0), "torque_limit": (2.0, 200.0), "leg_density": (200.0, 3000.0)}
# creature_forge/belief_engine.py:71-80
TOOL_PROBES = {"posture": ("pitch_ref@+0.1R", "pitch_ref@-0.1R", "hip_bias@+0.1R", "hip_bias@-0.1R"),
               "timing": ("freq@x0.85", "freq@x0.7", "duty@+0.1R"),
               "feedback": ("balance_gain@x2", "balance_gain@x0.5", "pitch_kp@x2", "pitch_kp@x0.5"),
               "stride": ("hip_amp@x0.7", "hip_amp@x1.2"),
               "placement": ("fp_kd@+0.2R", "fp_kv@+0.2R"),
               "foot_length": ("foot_length@x1.5", "foot_length@x2"),
               "torso_mass": ("torso_mass@x0.7", "torso_mass@x0.5"),
               "torque_limit": ("torque_limit@x2", "torque_limit@x3"),
               "foot_friction": ("foot_friction@x2", "foot_friction@x3"),
               "leg_length": ("leg_length@x0.85", "leg_length@x1.2")}
BODY_TOOLS = {"foot_length": ("foot_length",), "torso_mass": ("torso_mass",), "torque_limit": ("torque_limit",),
              "foot_friction": ("foot_friction",), "leg_length": ("thigh_length", "shank_length")}   # fault_bench.py:241-242
BODY_RATIO = (0.25, 4.0)   # hdb_workbench.py:30 (CMA body search ratio; walk_opt._log_interval clips to guided bounds)
_LEG = ("thigh_length", "shank_length", "foot_length")


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def load_eval():
    """[(relpath, line0, record)] of the DS-1 dev-eval-2 records (4 arms x 36)."""
    out = []
    for f in sorted(glob.glob(os.path.join(EVAL_DIR, "eval_*.jsonl"))):
        for i, r in enumerate(read_jsonl(f)):
            out.append((os.path.relpath(f, REPO).replace("\\", "/"), i, r))
    return out


def load_stream():
    out = []
    for f in sorted(glob.glob(os.path.join(STREAM_DIR, "r*_*.jsonl"))):
        for i, r in enumerate(read_jsonl(f)):
            out.append((os.path.relpath(f, REPO).replace("\\", "/"), i, r))
    return out


def base_of(iid: str) -> str:
    return iid.split(":")[0]


def full_body(b: dict) -> dict:
    d = dict(b)
    for k in _LEG:
        if d.get(k + "_r") is None:
            d[k + "_r"] = d.get(k)
    return d


def _fields(p):
    if p == "leg_length":
        return ("thigh_length", "thigh_length_r", "shank_length", "shank_length_r")
    return (p, p + "_r") if p in _LEG else (p,)


def body_probe_valid(body: dict, cid: str):
    """True/False for a BODY-parameter scale probe (exact apply_changes semantics: every guided-bounds field of the RESULT is
    checked, fault_bench.py:123-151); None for control probes (need the controller bounds LOWER17/UPPER17: not reconstructed)."""
    p, lvl = cid.split("@")
    if p not in ("torso_mass", "foot_length", "torque_limit", "foot_friction", "leg_length"):
        return None
    fac = float(lvl[1:])
    b = full_body(body)
    for f in _fields(p):
        b[f] = float(b[f]) * fac
    for k, (lo, hi) in GUIDED.items():
        for f in ((k, k + "_r") if k in _LEG else (k,)):
            if f in b and b[f] is not None and not (lo <= float(b[f]) <= hi):
                return False
    return True


def cma_interval(body: dict, tool: str):
    """(lo_factor, hi_factor) of the plant/twin CMA search for a body tool (walk_opt._log_interval, walk_opt.py:191-204),
    or None if the interval is empty (tool not executable)."""
    import math
    b = full_body(body)
    lo, hi = math.log(BODY_RATIO[0]), math.log(BODY_RATIO[1])
    for p in BODY_TOOLS[tool]:
        lo_b, hi_b = GUIDED[p]
        for f in ((p, p + "_r") if p in _LEG else (p,)):
            old = float(b[f])
            lo = max(lo, math.log(lo_b / old))
            hi = min(hi, math.log(hi_b / old))
    if not hi > lo:
        return None
    return round(math.exp(lo), 4), round(math.exp(hi), 4)


def events(r, kind=None):
    ev = (r.get("engine") or {}).get("events") or []
    return [e for e in ev if kind is None or e["kind"] == kind]


def trace(r):
    return ((r.get("agent") or {}).get("trace")) or []
