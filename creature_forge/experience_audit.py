"""Experience-learning P0 audit (docs/plans/EXPERIENCE_LEARNING_PLAN.md rev. 2, §3-4): what the development archives contain.

Offline only. It reads stored JSONL records, hashes them and normalises every verified repair outcome into one row. It then
classifies how comparable the outcomes on one instance are. Nothing here simulates: no MuJoCo, no network, no model calls.

Outcome hierarchy (plan §3):
  FULL_VERIFIED           full_recovery_v1 on the instance's validation/confirmation seeds;
  STANDARDIZED_DEV_PROXY  every tool run by the same assigned procedure, scored on fixed seeds (not the verifier);
  NON_COMPARABLE          in-episode checks, other bench versions, oracle-informed conditions, other verifiers.
Comparability of two outcomes on one plant (plan §3):
  S  the tool was ASSIGNED (forced / randomised / exhaustive) under one procedure and budget;
  P  same engine version, caps and verifier, but the tool was CHOSEN by different policies (missing not at random);
  X  anything else (A0 vs engine, other engine versions, stop-calibration "diverse" designs).

Trust boundary. The fault family, injected structure and severity of a record are kept ONLY as split/scoring labels
(`family`, `structure`); `FEATURE_WHITELIST` / `assert_whitelisted` keep them, ids, seeds and outcomes out of every feature.
Records on a base outside the declared development bases are dropped before any field is read beyond `instance_id`.
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
import os

import numpy as np

VERSION = "experience_audit_v1"
TIERS = ("FULL_VERIFIED", "STANDARDIZED_DEV_PROXY", "NON_COMPARABLE")
FULL = "FULL_RECOVERY"
HAND_BASES = ("stilts-drawn", "tiny-feet", "top-heavy", "weak-slippery")
ORACLE_CONDITIONS = ("K1", "K2", "K3", "K4")       # MKV: structure / exact deviation / symptom-twin / other assigned knowledge
ENGINE_ARMS = ("A1", "A1c", "A1f", "A1c5", "A1e", "A1e6", "A2", "A3", "A3v5", "A4", "A4x", "A4bad", "A4lfo",
               "A4x-noscientist", "K0n")
SPLIT_FILE = "experiments/causal_engineer/dev/hdb/stage2_split.json"
# stop-calibration designs name their episode file; mkv2.jsonl was pulled only as its partial copy (same run, engine v2)
ORIGIN_ALIAS = {"mkv2.jsonl": "mkv2_partial.jsonl"}

# ------------------------------------------------------------------------------------------------ source registry
# (glob relative to its root, root, kind, corpus, note). Roots: "vm" = the git-ignored VM pull (Creature-Forge/artifacts/vm),
# "repo" = this checkout. Kinds: episode (verified HDB episodes) | harness (controlled TA-1/DO-1 episodes) | stopcal
# (re-verified designs) | stopdata (re-measured evidence; labels are recorded statuses) | ident (standardised panel) |
# ce_probe (standardised proxy matrix + fixed catalogue) | ce_instances (fault-bench builds) | superseded | mirror.
SOURCES = [
    ("hdb/artifacts/hdb/vs_a1.jsonl", "vm", "episode", "stage1", "engine v1, HDB v1 bench"),
    ("hdb/artifacts/hdb/vs2_a1.jsonl", "vm", "episode", "stage1", "engine v2"),
    ("hdb/artifacts/hdb/vs4_A0.jsonl", "vm", "episode", "stage1", "A0 generic exhaustive"),
    ("hdb/artifacts/hdb/vs4_A1c.jsonl", "vm", "episode", "stage1", "engine v4, calibrated stop"),
    ("hdb/artifacts/hdb/vs4_A1f.jsonl", "vm", "episode", "stage1", "engine v4, spend all"),
    ("hdb/artifacts/hdb/vs4_a1.jsonl", "vm", "episode", "stage1", "engine v4, provisional stop"),
    ("hdb/artifacts/hdb/vs5_A1c.jsonl", "vm", "episode", "stage1", "engine v5, calibrated stop"),
    ("hdb/artifacts/hdb/fresh_A0.jsonl", "vm", "episode", "stage1", "A0 on fresh dev bases"),
    ("hdb/artifacts/hdb/fresh_A1c5.jsonl", "vm", "episode", "stage1", "engine v5 on fresh dev bases"),
    ("hdb/artifacts/hdb/mkv_dev_v1.jsonl", "vm", "episode", "mkv", "MKV conditions, HDB v1 bench"),
    ("hdb/artifacts/hdb/mkv4.jsonl", "vm", "episode", "mkv", "MKV conditions, engine v4"),
    ("hdb/artifacts/hdb/mkv5.jsonl", "vm", "episode", "mkv", "MKV conditions, engine v5"),
    ("hdb/artifacts/hdb/s2_equiv_A1e.jsonl", "vm", "episode", "stage2", "A1e = A1c5 equivalence"),
    ("hdb/artifacts/hdb/s2_pilot_A1e.jsonl", "vm", "episode", "stage2", "pilot"),
    ("hdb/artifacts/hdb/s2_pilot[123]_A*.jsonl", "vm", "episode", "stage2", "Nemotron pilots (init bases)"),
    ("hdb/artifacts/hdb/s2_smoke_A3.jsonl", "vm", "episode", "stage2", "smoke"),
    ("hdb/artifacts/hdb/smoke_a3_live.jsonl", "vm", "episode", "stage2", "live smoke"),
    ("hdb/artifacts/hdb/s2T_A1e.jsonl", "vm", "episode", "stage2", "transfer, engine"),
    ("hdb/artifacts/hdb/s2T_A2.jsonl", "vm", "episode", "stage2", "transfer, engine + amortized posterior"),
    ("hdb/artifacts/hdb/s2TDC_A1e.jsonl", "vm", "episode", "stage2", "transfer compositions, engine"),
    ("hdb/artifacts/hdb/s2DC_exp_A1e.jsonl", "vm", "episode", "stage2", "experience compositions, engine"),
    ("hdb/artifacts/hdb/s2DC_exp_A3.jsonl", "vm", "episode", "stage2", "experience compositions, Nemotron"),
    ("hdb/artifacts/hdb/stage2_final/s2_transfer_*.jsonl", "vm", "episode", "stage2", "transfer, Nemotron arms"),
    ("hdb/artifacts/hdb/ds1_equiv_A1e.jsonl", "vm", "episode", "ds1", "equivalence"),
    ("hdb/artifacts/hdb/ds1_smoke_A1e6.jsonl", "vm", "episode", "ds1", "smoke"),
    ("ds1/pilot_*.jsonl", "vm", "episode", "ds1", "pilot (init bases)"),
    ("ds1/gm_A1e6.c.jsonl", "vm", "episode", "ds1", "G-m compositions"),
    ("ds1/eval/eval_*.jsonl", "vm", "episode", "ds1", "dev-eval-2"),
    ("hdb/artifacts/hdb/ds1/stream/*.jsonl", "vm", "episode", "ds1", "learning stream"),
    ("experiments/ta1/phase1b_2026-10-20/ta1_phase1b.jsonl", "repo", "harness", "ta1", "forced tool order, L1"),
    ("experiments/ta1/a1_l4_pilot_2026-10-21/ta1_a1_l4.jsonl", "repo", "harness", "ta1", "forced tool order, L4"),
    ("experiments/do1/l4_r0/do1_l4_r0.jsonl", "repo", "harness", "do1", "objective change, L4 r0"),
    ("experiments/do1/w3w4_2026-10-21/do1_l4_rep.jsonl", "repo", "harness", "do1", "objective change, L4 r1-r5 + sentinel"),
    ("experiments/do1/w3w4_2026-10-21/do1_x.jsonl", "repo", "harness", "do1", "objective change, B1/C1"),
    ("hdb/artifacts/hdb/stopcal.jsonl", "vm", "stopcal", "stage1", "stop calibration: designs re-verified by full_recovery_v1"),
    ("ds1/ds1_stopdata.jsonl", "vm", "stopdata", "ds1", "stop-map v2 evidence, shard a"),
    ("ds1/ds1_stopdata_b.jsonl", "vm", "stopdata", "ds1", "stop-map v2 evidence, shard b"),
    ("hdb/artifacts/hdb/ident_v2_all.jsonl", "vm", "ident", "stage1", "identifiability panel, every instrument on every instance"),
    ("ce3/ce/probe_dev.jsonl", "vm", "ce_probe", "ce", "fault bench: fixed counterfactual catalogue + complete 10-tool matrix"),
    ("ce/ce/dev*_shard*.jsonl", "vm", "ce_instances", "ce", "fault-bench dev instance builds"),
    ("hdb/artifacts/hdb/vs4_a1_partial.jsonl", "vm", "superseded", "stage1", "partial pull of vs4_a1"),
    ("hdb/artifacts/hdb/vs5_A1c_partial.jsonl", "vm", "superseded", "stage1", "partial pull of vs5_A1c"),
    ("hdb/artifacts/hdb/mkv2_partial.jsonl", "vm", "superseded", "mkv", "partial MKV v2 (engine v2)"),
    ("hdb/artifacts/hdb/stopcal_partial.jsonl", "vm", "superseded", "stage1", "partial stopcal"),
    ("hdb/artifacts/hdb/ident.jsonl", "vm", "superseded", "stage1", "identifiability v1"),
    ("hdb/artifacts/hdb/ident_v1_partial.jsonl", "vm", "superseded", "stage1", "identifiability v1 partial"),
    ("hdb/artifacts/hdb/ds1_stopdata.jsonl", "vm", "mirror", "ds1", "copy of ds1/ds1_stopdata.jsonl"),
    ("hdb/artifacts/hdb/ds1/*.jsonl", "vm", "mirror", "ds1", "copies of ds1/ (canonical root used by the TA-1 harness)"),
]
# Never opened by the audit (only listed). Reason in the second field.
EXCLUDED = [
    ("hdb/artifacts/hdb/walkers_all.jsonl", "contains test-split walker designs (sealed split); not used"),
    ("cehb/**/*.jsonl", "causal-engineer held-out evaluation shards (registered evaluation set); not used"),
    ("experiments/causal_engineer/heldout/**", "causal-engineer held-out evaluation (registered evaluation set); not used"),
    ("hdb/artifacts/hdb/stage2_final/inference_ledger_*.jsonl", "inference ledger; no outcomes"),
    ("hdb/artifacts/hdb/noise_cal.jsonl", "noise calibration of the twin; no repair outcomes"),
    ("ce2/**, ce3/ce/pilot*, ce3/ce/demo_src.jsonl", "causal-engineer scientist episodes (adaptive LLM runs, older bench); "
     "the standardised probe set covers this bench"),
]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows_of(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def resolve(roots: dict, glob_rel: str, root: str) -> list[str]:
    return sorted(glob.glob(os.path.join(roots[root], glob_rel)))


def manifest(roots: dict) -> list[dict]:
    """Every registered file: path (relative to its root), kind, corpus, SHA-256, line count. Mirrors are hash-compared with
    their canonical copy under ds1/ (same basename)."""
    out = []
    for rel, root, kind, corpus, note in SOURCES:
        for p in resolve(roots, rel, root):
            with open(p, encoding="utf-8") as fh:
                n = sum(1 for line in fh if line.strip())
            ent = {"path": os.path.relpath(p, roots[root]).replace("\\", "/"), "root": root, "kind": kind, "corpus": corpus,
                   "note": note, "sha256": sha256_file(p), "lines": n, "bytes": os.path.getsize(p)}
            if kind == "mirror":
                base = os.path.basename(p)
                canon = [c for c in (os.path.join(roots["vm"], "ds1", base), os.path.join(roots["vm"], "ds1", "eval", base))
                         if os.path.exists(c)]
                ent["canonical"] = os.path.relpath(canon[0], roots["vm"]).replace("\\", "/") if canon else None
                ent["identical_to_canonical"] = (sha256_file(canon[0]) == ent["sha256"]) if canon else None
            out.append(ent)
    return out


# ------------------------------------------------------------------------------------------------ bases and groups
def dev_bases(split: dict) -> set[str]:
    return set(split["experience_bases"]) | set(split["transfer_bases"])


def base_of(iid: str) -> str:
    return iid.split(":")[0]


def generator_group(base: str) -> str:
    """Robot family by construction: hand-designed old dev, walk-recovery m1 generator, or the HDB v1 S3 generator."""
    if base in HAND_BASES:
        return "hand"
    if base.startswith("walkrec-dev-m1-gen"):
        return "walkrec-m1"
    if base.startswith("hdb-v1-gen"):
        return "hdb-v1"
    return "other"


MORPH_KEYS = ("L", "foot_to_leg", "torso_mass", "leg_density", "foot_friction", "tau_proxy", "leg_asym")


def morphology(body: dict) -> dict:
    """Nominal-design morphology from body parameters alone (no model compile, so no MuJoCo): leg length, foot/leg, torso
    mass, leg density, friction, torque limit / (torso weight x leg length), left-right leg asymmetry."""
    tl = [float(body["thigh_length"]), float(body.get("thigh_length_r", body["thigh_length"]))]
    sl = [float(body["shank_length"]), float(body.get("shank_length_r", body["shank_length"]))]
    fl = [float(body["foot_length"]), float(body.get("foot_length_r", body["foot_length"]))]
    legs = [tl[i] + sl[i] for i in range(2)]
    L = float(np.mean(legs))
    tm = float(body["torso_mass"])
    return {"L": L, "foot_to_leg": float(np.mean(fl)) / L, "torso_mass": tm, "leg_density": float(body["leg_density"]),
            "foot_friction": float(body["foot_friction"]), "tau_proxy": float(body["torque_limit"]) / (tm * 9.81 * L),
            "leg_asym": abs(legs[0] - legs[1]) / L}


def body_hash(body: dict) -> str:
    keys = sorted(k for k in body if k != "pose")
    return hashlib.sha256(json.dumps({k: round(float(body[k]), 9) for k in keys}, sort_keys=True).encode()).hexdigest()[:16]


def near_duplicate_groups(morph: dict, thr: float = 0.5) -> list[list[str]]:
    """Bases whose standardised morphology vectors lie within `thr` (Euclidean, z units over MORPH_KEYS) of each other,
    single linkage. Returns only components with more than one base."""
    bases = sorted(morph)
    if len(bases) < 2:
        return []
    X = np.array([[morph[b][k] for k in MORPH_KEYS] for b in bases])
    sd = X.std(0)
    Z = (X - X.mean(0)) / np.where(sd > 1e-12, sd, 1.0)
    parent = list(range(len(bases)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(bases)):
        for j in range(i + 1, len(bases)):
            if np.linalg.norm(Z[i] - Z[j]) < thr:
                parent[find(i)] = find(j)
    comp = collections.defaultdict(list)
    for i, b in enumerate(bases):
        comp[find(i)].append(b)
    return sorted((sorted(c) for c in comp.values() if len(c) > 1), key=lambda c: c[0])


def kish_neff(sizes) -> float:
    """Kish effective number of groups for unequal cluster sizes: (sum n)^2 / sum n^2."""
    s = [int(x) for x in sizes if x]
    return (sum(s) ** 2 / sum(x * x for x in s)) if s else 0.0


# ------------------------------------------------------------------------------------------------ record normalisation
def _final_tool(rec: dict) -> str | None:
    from .has_cases import final_tool       # lazy: has_cases pulls in the belief engine's constants
    return final_tool(rec)


def _status(rec: dict) -> str | None:
    v = rec.get("verification")
    if isinstance(v, dict):
        if isinstance(v.get("summary"), dict):
            return v["summary"].get("status")
        return v.get("status")
    return rec.get("status")


def engine_of(rec: dict) -> dict:
    return rec.get("engine") or ((rec.get("info") or {}).get("engine")) or {}


def procedure_of(rec: dict, kind: str) -> tuple[str, bool]:
    """(procedure class, oracle information assigned?)"""
    arm = rec.get("arm") or rec.get("condition") or ""
    if kind == "harness":
        h = rec.get("harness") or {}
        do1 = (h.get("do1") or {}).get("arm")
        return (f"ta1:{h.get('ta1_arm')}" if do1 is None else f"do1:{do1}"), False
    if arm in ("A0", "K0"):
        return "a0_generic", False
    if arm in ORACLE_CONDITIONS:
        return f"mkv_oracle:{arm}", True
    if arm in ENGINE_ARMS:
        return ("nemotron" if arm.startswith(("A3", "A4")) and arm != "A4x-noscientist" else "engine"), False
    return f"other:{arm}", False


def outcome_row(rec: dict, src: dict) -> dict | None:
    """One verified outcome of a submitted repair, or None (ineligible plant, no verification)."""
    if rec.get("eligible") is False:
        return None
    status = _status(rec)
    if status is None:
        return None
    eng = engine_of(rec)
    proc, oracle = procedure_of(rec, src["kind"])
    led = eng.get("ledger") or {}
    exps = eng.get("experiments") or []
    h = rec.get("harness") or {}
    bench = rec.get("bench") or "hdb_v1"
    return {"source": src["path"], "corpus": src["corpus"], "kind": src["kind"], "arm": rec.get("arm") or rec.get("condition"),
            "bench": bench, "iid": rec["instance_id"], "base": base_of(rec["instance_id"]),
            "family": rec.get("family"), "structure": rec.get("injected_structure"),
            "engine": eng.get("version"), "procedure": proc, "oracle": oracle, "tool": _final_tool(rec), "status": status,
            "full": status == FULL, "tier": "FULL_VERIFIED", "plant_total": led.get("total"), "plant_used": led.get("used"),
            "twin_used": (led.get("twin") or {}).get("used"),
            "repair_steps": [(e.get("step"), e.get("tool"), e.get("budget")) for e in (rec.get("repair") or {}).get("log") or []],
            "experiment_kinds": [e.get("kind") for e in exps], "x0": _x0_hash(exps),
            "replicate": h.get("replicate"), "noise_seed": h.get("noise_seed"),
            "has_settings": bool(eng.get("settings")), "has_v6_settings": bool(rec.get("v6_settings") or eng.get("v6")),
            "has_stop_rule": bool(rec.get("stop_rule")), "has_commit": any(k in rec for k in ("commit", "git_commit", "source_rev")),
            "per_seed_validation": bool(isinstance(rec.get("verification"), dict) and rec["verification"].get("full"))}


def _x0_hash(exps: list[dict]) -> str | None:
    """Hash of the first experiment if it is the standard observe (kind, seeds, per-seed features), so records of one plant
    can be checked for identical pre-intervention observations."""
    if not exps or exps[0].get("kind") != "observe":
        return None
    e = exps[0]
    feats = {str(s): {k: (round(v, 6) if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in f.items()}
             for s, f in (e.get("features") or {}).items()}
    return hashlib.sha256(json.dumps({"seeds": e.get("seeds"), "f": feats}, sort_keys=True).encode()).hexdigest()[:16]


def stopcal_rows(recs: list[dict], src: dict, bench_of_origin: dict) -> list[dict]:
    """Stop-calibration designs re-verified by `hb.verify` (full_recovery_v1). Their tool is the design's source suffix."""
    from .has_cases import PROBE_TOOL
    from .repair_learning import TOOLS
    out = []
    for r in recs:
        s = r.get("source") or ""
        t = s.split(":")[-1]
        tool = t if t in TOOLS else PROBE_TOOL.get(t)
        cond = r.get("condition")
        out.append({"source": src["path"], "corpus": src["corpus"], "kind": "stopcal", "arm": f"stopcal:{s.split(':')[0]}",
                    "bench": bench_of_origin.get(r.get("origin"), "unknown"), "iid": r["instance_id"], "base": r["base_id"],
                    "family": r.get("family"), "structure": None, "engine": None,
                    "procedure": f"diverse:{s.split(':')[0]}", "oracle": cond in ORACLE_CONDITIONS,
                    "tool": tool if s != "initial" else None, "status": r["status"], "full": r["status"] == FULL,
                    "tier": "FULL_VERIFIED", "origin": r.get("origin")})
    return out


# ------------------------------------------------------------------------------------------------ comparability
def comparability(rows: list[dict]) -> dict:
    """Per plant (bench, instance): the distinct tools with a FULL_VERIFIED outcome at each comparability level.
    S = assigned tool (TA-1 forced order within one replicate); P = same engine version, engine/Nemotron procedure, no oracle;
    X = all non-oracle procedures pooled (A0, other engine versions, stop-calibration designs)."""
    by = collections.defaultdict(list)
    for r in rows:
        if r.get("tool"):
            by[(r["bench"], r["iid"])].append(r)
    out = {}
    for key, rr in by.items():
        lv = {}
        s_groups = collections.defaultdict(dict)
        for r in rr:
            if r["procedure"].startswith("ta1:"):
                s_groups[r.get("noise_seed")].setdefault(r["tool"], []).append(r["full"])
        lv["S"] = max((g for g in s_groups.values()), key=len, default={})
        p_groups = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in rr:
            if not r["oracle"] and r["procedure"] in ("engine", "nemotron") and r["engine"]:
                p_groups[r["engine"]][r["tool"]].append(r["full"])
        lv["P"] = max(p_groups.values(), key=len, default={})
        lv["P_engine"] = max(p_groups, key=lambda e: len(p_groups[e]), default=None)
        x = collections.defaultdict(list)
        for r in rr:
            if not r["oracle"]:
                x[r["tool"]].append(r["full"])
        lv["X"] = dict(x)
        out[key] = lv
    return out


def informative(tools: dict) -> bool:
    """At least two tools, and their (mean) verified outcomes differ: only then does the instance carry decision information."""
    if len(tools) < 2:
        return False
    rates = [float(np.mean(v)) for v in tools.values()]
    return max(rates) > min(rates)


def support(comp: dict, level: str, rows: list[dict], bench: str | None = None) -> dict:
    """Counts behind the adequacy criteria for one comparability level."""
    fam = {(r["bench"], r["iid"]): r.get("family") for r in rows}
    keys = [k for k, lv in comp.items() if len(lv[level]) >= 2 and (bench is None or k[0] == bench)]
    inf = [k for k in keys if informative(comp[k][level])]
    per_base = collections.Counter(base_of(k[1]) for k in inf)
    fam_bases = collections.defaultdict(set)
    for k in inf:
        fam_bases[fam.get(k)].add(base_of(k[1]))
    return {"instances_ge2_tools": len(keys), "bases_ge2_tools": len({base_of(k[1]) for k in keys}),
            "informative_instances": len(inf), "informative_bases": len(per_base),
            "fault_families_informative": len(fam_bases), "families_on_ge2_bases": sum(1 for b in fam_bases.values() if len(b) >= 2),
            "generator_groups": sorted({generator_group(b) for b in per_base}), "kish_neff_bases": round(kish_neff(per_base.values()), 2)}


def adequacy(sup: dict, *, assigned: bool, tier: str) -> dict:
    """Pre-declared criteria D1 (exploratory decision-signal test) and D2 (FULL-verified GO), plan §4."""
    d1 = assigned and sup["informative_bases"] >= 10 and sup["informative_instances"] >= 30
    d2 = (assigned and tier == "FULL_VERIFIED" and sup["informative_bases"] >= 20 and sup["informative_instances"] >= 40
          and sup["families_on_ge2_bases"] >= 3)
    return {"D1": bool(d1), "D2": bool(d2), "assigned": assigned, "tier": tier}


# ------------------------------------------------------------------------------------------------ feature whitelist
FORBIDDEN_TOKENS = ("instance", "base_id", "seed", "severity", "strength", "mult", "family", "fault", "injected", "changes",
                    "verification", "status", "label", "full_recovery", "walking_frac", "repair_matrix", "matching_tool",
                    "map_structure", "posterior_mass_on_injected", "region", "source_unit")


def assert_whitelisted(names) -> None:
    """Every feature name must be free of identifier, truth, outcome and seed tokens (plan §4, leakage)."""
    bad = [n for n in names if any(t in str(n).lower() for t in FORBIDDEN_TOKENS)]
    if bad:
        raise ValueError(f"forbidden feature names (leakage): {bad}")


def legal_at(decision_index: int, experiment_index: int) -> bool:
    """An interventional feature from experiment i may be used at decision point d only if i < d (the experiment occurred)."""
    return experiment_index < decision_index


# ------------------------------------------------------------------------------------------------ inventory
def inventory(roots: dict, split: dict) -> dict:
    """Read every registered source, normalise outcomes, and count support. Returns a JSON-serialisable dict."""
    allowed = dev_bases(split)
    man = manifest(roots)
    rows, dropped = [], collections.Counter()
    bench_of_origin: dict = {}
    morph_bodies = collections.defaultdict(set)
    morph: dict = {}
    exp_stats = collections.Counter()
    first_kind = collections.Counter()
    n_exps = []
    x0_by_plant = collections.defaultdict(set)
    ident_n, ident_bases, ident_fam = 0, set(), collections.Counter()
    ce = {"instances": 0, "bases": set(), "faults": collections.Counter(), "complete": 0, "informative": 0, "tools": set(),
          "fault_bases": collections.defaultdict(set)}
    exps_by_engine = collections.defaultdict(list)
    for ent in man:
        if ent["kind"] == "superseded" and ent["path"].endswith("mkv2_partial.jsonl"):
            first = rows_of(os.path.join(roots[ent["root"]], ent["path"]))[:1]
            bench_of_origin["mkv2_partial.jsonl"] = (first[0].get("bench") or "hdb_v1") if first else None
        if ent["kind"] in ("superseded", "mirror", "ce_instances", "stopdata"):
            continue
        p = os.path.join(roots[ent["root"]], ent["path"])
        recs = rows_of(p)
        if ent["kind"] in ("episode", "harness"):
            bench_of_origin.setdefault(os.path.basename(ent["path"]), None)
            for r in recs:
                if base_of(r.get("instance_id", "")) not in allowed:
                    dropped[ent["path"]] += 1
                    continue
                bench_of_origin[os.path.basename(ent["path"])] = r.get("bench") or "hdb_v1"
                for d in r.get("designs") or []:
                    if d.get("source") == "initial" and d.get("body"):
                        b = base_of(r["instance_id"])
                        morph_bodies[b].add(body_hash(d["body"]))
                        morph.setdefault(b, morphology(d["body"]))
                        break
                row = outcome_row(r, ent)
                if row is None:
                    continue
                rows.append(row)
                if row["experiment_kinds"]:
                    n_exps.append(len(row["experiment_kinds"]))
                    exps_by_engine[str(row["engine"])].append(len(row["experiment_kinds"]))
                    first_kind[row["experiment_kinds"][0]] += 1
                    for k in set(row["experiment_kinds"]):
                        exp_stats[k] += 1
                if row["x0"]:
                    x0_by_plant[(row["bench"], row["iid"])].add(row["x0"])
        elif ent["kind"] == "ident":
            for r in recs:
                if r.get("skipped") or base_of(r["instance_id"]) not in allowed:
                    continue
                ident_n += 1
                ident_bases.add(r["base_id"])
                ident_fam[r["family"]] += 1
        elif ent["kind"] == "ce_probe":
            for r in recs:
                if r["base_id"] not in allowed:
                    dropped[ent["path"]] += 1
                    continue
                m = r.get("repair_matrix") or {}
                ce["instances"] += 1
                ce["bases"].add(r["base_id"])
                ce["tools"] |= set(m)
                ce["faults"][r["instance_id"].split(":")[1]] += 1
                ce["fault_bases"][r["instance_id"].split(":")[1]].add(r["base_id"])
                ce["complete"] += len(m) == 10
                ce["informative"] += len({v >= 0.75 for v in m.values()}) > 1
    for alias, target in ORIGIN_ALIAS.items():
        bench_of_origin.setdefault(alias, bench_of_origin.get(target))
    for ent in man:
        if ent["kind"] == "stopcal":
            recs = [r for r in rows_of(os.path.join(roots[ent["root"]], ent["path"])) if r["base_id"] in allowed]
            rows += stopcal_rows(recs, ent, bench_of_origin)
    comp = comparability(rows)
    stop_rows = [r for r in rows if r["kind"] == "stopcal"]
    sup = {lv: support(comp, lv, rows) for lv in ("S", "P", "X")}
    sup_by_engine = {}
    for eng in sorted({lv["P_engine"] for lv in comp.values() if lv["P_engine"]}):
        sub = {k: v for k, v in comp.items() if v["P_engine"] == eng}
        sup_by_engine[eng] = support(sub, "P", rows)
    ce_sup = {"tier": "STANDARDIZED_DEV_PROXY", "instances": ce["instances"], "bases": len(ce["bases"]),
              "fault_families": len(ce["faults"]), "complete_10_tool_matrices": ce["complete"],
              "informative_instances": ce["informative"], "informative_bases": len(ce["bases"]),
              "families_on_ge2_bases": sum(1 for b in ce["fault_bases"].values() if len(b) >= 2),
              "outcome": "walking fraction on 8 check seeds after each tool at budget 160; repairs = >= 0.75"}
    gates = {
        "HDB FULL_VERIFIED level S (assigned tool)": adequacy(sup["S"], assigned=True, tier="FULL_VERIFIED"),
        "HDB FULL_VERIFIED level P (policy-chosen)": adequacy(sup["P"], assigned=False, tier="FULL_VERIFIED"),
        "HDB FULL_VERIFIED level X (cross-procedure)": adequacy(sup["X"], assigned=False, tier="FULL_VERIFIED"),
        "CE STANDARDIZED_DEV_PROXY (complete matrix)": adequacy({"informative_bases": len(ce["bases"]),
                                                                 "informative_instances": ce["informative"],
                                                                 "families_on_ge2_bases": ce_sup["families_on_ge2_bases"]},
                                                                assigned=True, tier="STANDARDIZED_DEV_PROXY"),
    }
    x0_multi = [v for v in x0_by_plant.values()]
    by_corpus = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        c = by_corpus[r["corpus"] + ("/stopcal" if r["kind"] == "stopcal" else "")]
        c["outcomes"] += 1
        c["full"] += r["full"]
        c["oracle"] += r["oracle"]
        c["with_tool"] += bool(r["tool"])
    plants = collections.defaultdict(set)
    for r in rows:
        plants[r["bench"]].add(r["iid"])
    fields = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["kind"] == "stopcal":
            continue
        f = fields[r["corpus"]]
        f["n"] += 1
        for k in ("has_settings", "has_v6_settings", "has_stop_rule", "has_commit", "per_seed_validation"):
            f[k] += bool(r.get(k))
        f["has_noise_seed"] += r.get("noise_seed") is not None
        f["has_x0_observe"] += bool(r.get("x0"))
        f["has_repair_log"] += bool(r.get("repair_steps"))
    return {
        "version": VERSION, "manifest": man, "excluded_not_opened": EXCLUDED, "dropped_off_split": dict(dropped),
        "outcome_rows": len(rows), "plants_by_bench": {k: len(v) for k, v in plants.items()},
        "bases_with_outcomes": len({r["base"] for r in rows}),
        "outcomes_by_corpus": {k: dict(v) for k, v in by_corpus.items()},
        "procedures": dict(collections.Counter(r["procedure"] for r in rows)),
        "engines": dict(collections.Counter(str(r["engine"]) for r in rows if r["kind"] != "stopcal")),
        "stopcal_by_bench": dict(collections.Counter(r["bench"] for r in stop_rows)),
        "support": sup, "support_level_P_by_engine": sup_by_engine, "ce_proxy": ce_sup, "gates": gates,
        "families": dict(collections.Counter(r["family"] for r in rows if r["kind"] != "stopcal")),
        "generator_groups": dict(collections.Counter(generator_group(r["base"]) for r in rows)),
        "morphology": {"bases": len(morph), "bases_with_inconsistent_nominal_body": sorted(b for b, s in morph_bodies.items() if len(s) > 1),
                       "near_duplicate_groups_z0.5": near_duplicate_groups(morph)},
        "experiments": {"episodes_with_experiments": len(n_exps), "first_kind": dict(first_kind),
                        "kind_present_in_episodes": dict(exp_stats),
                        "n_experiments_median": float(np.median(n_exps)) if n_exps else None,
                        "n_experiments_range": [int(min(n_exps)), int(max(n_exps))] if n_exps else None,
                        "n_experiments_median_by_engine": {k: float(np.median(v)) for k, v in sorted(exps_by_engine.items())}},
        "x0_consistency": {"plants_with_ge2_records": sum(1 for v in x0_multi if v), "plants_inconsistent": sum(1 for v in x0_multi if len(v) > 1)},
        "fields_by_corpus": {k: dict(v) for k, v in fields.items()},
        "ident": {"instances": ident_n, "bases": len(ident_bases), "families": dict(ident_fam)},
        "_rows": rows, "_comp": comp, "_morph": morph,
    }


def json_safe(inv: dict) -> dict:
    return {k: v for k, v in inv.items() if not k.startswith("_")}
