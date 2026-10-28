"""Preregistered, read-only analysis of the W3 (DO1-L4-rep) and W4 (DO1-X) outputs of scripts/do1_repair_ablation.py.

Written and committed BEFORE any W3/W4 episode ran (docs/DO1_REPLICATION_PROTOCOL.md). No physics, no randomness. Every
line of every input file is accounted for: episodes, the sentinel and infrastructure-error lines.

W3, primary (intention to treat over the pairs r1-r5): FULL_RECOVERY count per arm k/n with exact Clopper-Pearson 95%
intervals; the exact one-sided McNemar (sign) test on discordant pairs. Secondary: status counts, paired validation walking
difference k/24 with an exact one-sided sign test (ties dropped), verdicts and median paired displacement, confirmation,
resources, stop-map acceptance, DO-1 binding gates and convergence, and the per-protocol analysis (pairs whose do1 episode
was NOT_EXPOSED excluded), always next to ITT. The sentinel is reported only as a reproduction check.
W4: descriptive per instance and arm; which recovery gates changed between arms. No test, no pooling.

Usage: python scripts/do1_replication_analysis.py --w3 <DO1-L4-rep.jsonl> [--w4 <DO1-X.jsonl>] [--pilot <DO1-L4-r0.jsonl>]
       [--json <summary.json>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics as st
import sys
from math import comb

FULL, PARTIAL = "FULL_RECOVERY", "PARTIAL_IMPROVEMENT"
NULL_WORDING = ("No verified recovery was found under the tested intervention, optimizer configuration and computational "
                "budget.")


# ------------------------------------------------------------------------------------------------------------ statistics
def binom_cdf(k: int, n: int, p: float) -> float:
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided (1 - alpha) interval for a binomial proportion, by bisection on the exact CDF."""
    if n <= 0:
        return (0.0, 1.0)

    def solve(f, lo=0.0, hi=1.0):
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) >= alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) <= alpha / 2)
    return (lower, upper)


def sign_test_one_sided(n_for: int, n_against: int) -> float | None:
    """P(X >= n_for) for X ~ Bin(n_for + n_against, 1/2); None when there is no informative pair."""
    n = n_for + n_against
    if n == 0:
        return None
    return sum(comb(n, k) for k in range(n_for, n + 1)) / 2 ** n


# ------------------------------------------------------------------------------------------------------------ records
def sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def episode(rec: dict) -> dict:
    """The analysed fields of one episode record (every number read from the record)."""
    h = rec["harness"]
    s = rec["verification"]["summary"]
    full = rec["verification"].get("full") or {}
    val = full.get("validation") or {}
    v = val.get("verdict") or {}
    conf = full.get("confirmation") or {}
    res = h.get("resources") or {}
    arm = h["do1"]["arm"]
    out = {
        "case": h.get("case"), "instance_id": rec["instance_id"], "arm": arm, "replicate": h["replicate"],
        "role": h.get("role"), "noise_seed": h.get("noise_seed"), "status": s["status"],
        "walking_k": round(s["walking_frac"] * 24), "reasons": s.get("reasons") or [],
        "aggregate": val.get("aggregate"), "verdict": v.get("status"), "wins": v.get("wins"), "losses": v.get("losses"),
        "ties": v.get("ties"), "median_diff_m": v.get("median_diff"), "p_better": v.get("p_one_sided"),
        "confirmation_run": conf.get("run"), "confirmation_passed": conf.get("passed"),
        "confirmation_checks": {k: (c.get("value"), c.get("passed")) for k, c in (conf.get("checks") or {}).items()},
        "plant_used": (res.get("plant") or {}).get("used"), "twin_used": (res.get("twin") or {}).get("used"),
        "rollout_equivalents": res.get("total_rollout_equivalents"),
        "stop_map_accepted": (rec.get("repair") or {}).get("accepted"), "submitted": rec.get("submitted"),
        "valid": (h.get("arm_checks") or {}).get("valid"), "exposed": (h.get("arm_checks") or {}).get("exposed"),
        "arm_problems": (h.get("arm_checks") or {}).get("problems"),
        "reproduction_exact": (h.get("reproduction") or {}).get("exact"),
        "stored_prefix_match": (h.get("stored_prefix") or {}).get("match"),
        "paired_prehook_equal": (h.get("paired_prehook") or {}).get("equal"),
        "rescreen": (h.get("rescreen") or {}).get("classification"), "wall_s": rec.get("wall_s"),
    }
    if arm == "do1":
        reps = [r for r in h["do1"].get("repairs") or [] if r.get("refused") is None]
        out["do1_repairs"] = [{
            "tool": r["tool"], "design_index": r["design_index"], "n_candidates": r.get("n_candidates", len(r["candidates"])),
            "selected_log_index": r["selected_log_index"],
            "selected_is_last": r["selected_log_index"] == len(r["candidates"]) - 1,
            "selected_walking": r["selected"].get("walking_count"), "selected_margin": r["selected"].get("margin"),
            "selected_median_gain_m": r["selected"].get("median_diff_m"),
            "binding_gates": [p.get("binding_gate") for p in r["selected"].get("per_seed") or []],
        } for r in reps]
        out["do1_refused"] = [r.get("refused") for r in h["do1"].get("repairs") or [] if r.get("refused") is not None]
    return out


def split_lines(recs: list[dict]) -> tuple[list[dict], list[dict]]:
    errors = [r for r in recs if r.get("infrastructure_error")]
    eps = [episode(r) for r in recs if not r.get("infrastructure_error")]
    return eps, errors


# ------------------------------------------------------------------------------------------------------------ W3
def w3_analysis(eps: list[dict], errors: list[dict], planned_replicates=range(1, 6)) -> dict:
    sentinel = [e for e in eps if e["role"] == "sentinel"]
    prim = {(e["replicate"], e["arm"]): e for e in eps if e["role"] == "primary"}
    pairs, incomplete = [], []
    for r in planned_replicates:
        f, d = prim.get((r, "frozen")), prim.get((r, "do1"))
        if f is None or d is None:
            incomplete.append({"replicate": r, "frozen": f is not None, "do1": d is not None,
                               "infrastructure_error": [x for x in errors if x.get("replicate") == r]})
            continue
        pairs.append({"replicate": r, "noise_seed": f["noise_seed"], "frozen": f, "do1": d,
                      "full_frozen": f["status"] == FULL, "full_do1": d["status"] == FULL,
                      "walking_diff": d["walking_k"] - f["walking_k"], "do1_exposed": bool(d["exposed"])})

    def primary(ps):
        n = len(ps)
        kf, kd = sum(p["full_frozen"] for p in ps), sum(p["full_do1"] for p in ps)
        dis_for = sum(p["full_do1"] and not p["full_frozen"] for p in ps)
        dis_against = sum(p["full_frozen"] and not p["full_do1"] for p in ps)
        w_for = sum(p["walking_diff"] > 0 for p in ps)
        w_against = sum(p["walking_diff"] < 0 for p in ps)
        p_mc = sign_test_one_sided(dis_for, dis_against)
        if dis_for + dis_against == 0:
            reading = "no discordant pair: descriptive only"
        elif dis_against == 0 and p_mc is not None and p_mc <= 0.05:
            reading = "every discordant pair favours do1, p <= 0.05 (instance-specific; technical replicates)"
        elif dis_against == 0:
            reading = "every discordant pair favours do1 but p > 0.05: suggestive, inconclusive"
        elif dis_for == 0:
            reading = "no discordant pair favours do1: no evidence of improvement on this instance at this budget"
        else:
            reading = "mixed discordant pairs: inconclusive at this budget"
        return {"n_pairs": n, "full_frozen": kf, "full_do1": kd,
                "cp95_frozen": clopper_pearson(kf, n), "cp95_do1": clopper_pearson(kd, n),
                "discordant_for_do1": dis_for, "discordant_against_do1": dis_against, "mcnemar_one_sided_p": p_mc,
                "reading": reading,
                "status_counts": {arm: {s: sum(p[arm]["status"] == s for p in ps)
                                        for s in (FULL, PARTIAL, "NOT_RECOVERED", "WORSE")} for arm in ("frozen", "do1")},
                "walking_diff": [p["walking_diff"] for p in ps], "walking_sign_for": w_for, "walking_sign_against": w_against,
                "walking_sign_test_p": sign_test_one_sided(w_for, w_against),
                "median_walking_diff": st.median([p["walking_diff"] for p in ps]) if ps else None}
    pp = [p for p in pairs if p["do1_exposed"]]
    return {"sentinel": sentinel, "pairs": pairs, "incomplete_pairs": incomplete, "infrastructure_errors": errors,
            "itt": primary(pairs), "per_protocol": primary(pp),
            "per_protocol_excluded": [{"replicate": p["replicate"], "reason": p["do1"]["arm_problems"]}
                                      for p in pairs if not p["do1_exposed"]]}


# ------------------------------------------------------------------------------------------------------------ W4
def gate_changes(f: dict, d: dict) -> dict:
    return {"status": (f["status"], d["status"]), "walking_k": (f["walking_k"], d["walking_k"]),
            "aggregate": (f["aggregate"], d["aggregate"]), "verdict": (f["verdict"], d["verdict"]),
            "median_diff_m": (f["median_diff_m"], d["median_diff_m"]),
            "confirmation": ((f["confirmation_run"], f["confirmation_passed"]), (d["confirmation_run"], d["confirmation_passed"])),
            "reasons_frozen_only": [x for x in f["reasons"] if x not in d["reasons"]],
            "reasons_do1_only": [x for x in d["reasons"] if x not in f["reasons"]]}


def w4_analysis(eps: list[dict], errors: list[dict]) -> dict:
    out = {}
    for case in sorted({e["case"] for e in eps} | {x["case"] for x in errors if x.get("case")}):
        f = next((e for e in eps if e["case"] == case and e["arm"] == "frozen"), None)
        d = next((e for e in eps if e["case"] == case and e["arm"] == "do1"), None)
        if f is None or d is None:
            direction = "incomplete"
        else:
            rank = {FULL: 3, PARTIAL: 2, "NOT_RECOVERED": 1, "WORSE": 0}
            a, b = rank.get(f["status"], -1), rank.get(d["status"], -1)
            direction = ("do1 better status" if b > a else "do1 worse status" if b < a else
                         f"same status; walking {d['walking_k'] - f['walking_k']:+d}/24")
        out[case] = {"frozen": f, "do1": d, "direction": direction,
                     "gates": gate_changes(f, d) if f and d else None,
                     "infrastructure_errors": [x for x in errors if x.get("case") == case]}
    return out


# ------------------------------------------------------------------------------------------------------------ report
def fmt_ep(e: dict) -> str:
    conf = "-" if not e["confirmation_run"] else ("pass" if e["confirmation_passed"] else "FAIL")
    md = e["median_diff_m"]
    return (f"{e['status']:<20} {e['walking_k']:>2}/24  {str(e['verdict']):<22} med {md:+.3f} m  conf {conf:<4} "
            f"plant {e['plant_used']} twin {e['twin_used']} acc {e['stop_map_accepted']}  valid {e['valid']} "
            f"exposed {e['exposed']}" if md is not None else f"{e['status']} {e['walking_k']}/24")


def report(w3: dict | None, w4: dict | None, pilot: list[dict] | None, files: dict) -> str:
    L = ["Input files (sha256):"] + [f"  {k}: {p} {h}" for k, (p, h) in files.items()]
    if w3:
        L.append("\n=== W3 DO1-L4-rep (L4 hdb-v1-gen-0137:low_ground_friction:0) ===")
        for s in w3["sentinel"]:
            L.append(f"SENTINEL frozen r0 (reproduction check only, not analysed): reproduction_exact={s['reproduction_exact']} "
                     f"| {fmt_ep(s)}")
        L.append("Pairs (r, noise seed): frozen | do1 | walking diff")
        for p in w3["pairs"]:
            L.append(f"  r{p['replicate']} {p['noise_seed']}:")
            L.append(f"     frozen {fmt_ep(p['frozen'])}")
            L.append(f"     do1    {fmt_ep(p['do1'])}  diff {p['walking_diff']:+d}/24")
            for rr in p["do1"].get("do1_repairs") or []:
                L.append(f"       do1 repair {rr['tool']}: {rr['n_candidates']} candidates, selected #{rr['selected_log_index']} "
                         f"(last {rr['selected_is_last']}), W {rr['selected_walking']} margin {rr['selected_margin']} "
                         f"gain {rr['selected_median_gain_m']} gates {rr['binding_gates']}")
        for x in w3["incomplete_pairs"]:
            L.append(f"  INCOMPLETE pair r{x['replicate']}: {x}")
        for name in ("itt", "per_protocol"):
            a = w3[name]
            L.append(f"{name.upper()}: n={a['n_pairs']} FULL frozen {a['full_frozen']}/{a['n_pairs']} "
                     f"CP95 [{a['cp95_frozen'][0]:.3f}, {a['cp95_frozen'][1]:.3f}] | FULL do1 {a['full_do1']}/{a['n_pairs']} "
                     f"CP95 [{a['cp95_do1'][0]:.3f}, {a['cp95_do1'][1]:.3f}] | discordant for/against do1 "
                     f"{a['discordant_for_do1']}/{a['discordant_against_do1']} McNemar one-sided p {a['mcnemar_one_sided_p']} "
                     f"-> {a['reading']}")
            L.append(f"   status counts {a['status_counts']}; walking diffs {a['walking_diff']} (sign {a['walking_sign_for']}+/"
                     f"{a['walking_sign_against']}-, one-sided p {a['walking_sign_test_p']}, median {a['median_walking_diff']})")
        L.append(f"Per-protocol exclusions: {w3['per_protocol_excluded'] or 'none'}")
        L.append(f"Infrastructure errors: {len(w3['infrastructure_errors'])}")
    if w4:
        L.append("\n=== W4 DO1-X (exploratory, descriptive only) ===")
        for case, c in w4.items():
            L.append(f"{case} {(c['frozen'] or c['do1'] or {}).get('instance_id')}: {c['direction']}")
            for arm in ("frozen", "do1"):
                if c[arm]:
                    L.append(f"   {arm:<6} {fmt_ep(c[arm])} repro {c[arm]['reproduction_exact']} prefix {c[arm]['stored_prefix_match']}")
            if c["gates"]:
                L.append(f"   gates: {json.dumps(c['gates'])}")
    if pilot:
        L.append("\n=== Reference only (not pooled): exploratory DO1-L4-r0 pilot ===")
        for e in pilot:
            L.append(f"   {e['arm']:<6} r0 {fmt_ep(e)}")
    L.append(f"\nNull wording where applicable: {NULL_WORDING}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--w3")
    ap.add_argument("--w4")
    ap.add_argument("--pilot")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    files, w3, w4, pilot = {}, None, None, None
    if a.w3:
        files["w3"] = (a.w3, sha256(a.w3))
        w3 = w3_analysis(*split_lines(load(a.w3)))
    if a.w4:
        files["w4"] = (a.w4, sha256(a.w4))
        w4 = w4_analysis(*split_lines(load(a.w4)))
    if a.pilot:
        files["pilot"] = (a.pilot, sha256(a.pilot))
        pilot = split_lines(load(a.pilot))[0]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report(w3, w4, pilot, files))
    if a.json:
        with open(a.json, "x", encoding="utf-8") as fh:
            json.dump({"files": files, "w3": w3, "w4": w4, "pilot": pilot}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
