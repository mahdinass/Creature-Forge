"""Confirmatory analysis for walkrec-confirm-v1 (frozen with the protocol; run ONCE after every unit completed).

    python scripts/walk_confirm_analysis.py <shard*.jsonl ...> --protocol experiments/walk_recovery/confirmatory/protocol.json [--out summary.json]

Primary: exact one-sided McNemar, ai_v2 vs fix, on FULL_RECOVERY paired by creature (alpha 0.05).
Secondary: ai_v2 vs cma_joint / rand / cma_ctrl, one-sided exact McNemar each, Holm-Bonferroni at 0.05.
Exploratory: two-sided McNemar for fix-cma_joint, rand-fix, cma_joint-cma_ctrl; region-cluster sign test (ai_v2 - fix);
partial rates; mean walking fractions; budget use; AI decision patterns and cost.
Unit errors count as not recovered and are listed. Nothing is rerun or excluded silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from math import comb
from pathlib import Path

FULL = "FULL_RECOVERY"


def binom_upper(k: int, n: int) -> float:
    """P(X >= k) for X ~ Bin(n, 1/2)."""
    return sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0


def mcnemar(a: dict, b: dict, creatures, two_sided: bool = False) -> dict:
    a_only = sum(1 for c in creatures if a.get(c) and not b.get(c))
    b_only = sum(1 for c in creatures if b.get(c) and not a.get(c))
    n = a_only + b_only
    p1 = binom_upper(a_only, n)
    p = min(1.0, 2 * min(p1, binom_upper(b_only, n))) if two_sided else p1
    return {"a_only": a_only, "b_only": b_only, "both": sum(1 for c in creatures if a.get(c) and b.get(c)),
            "neither": sum(1 for c in creatures if not a.get(c) and not b.get(c)), "p": p, "two_sided": two_sided}


def holm(pvals: dict, alpha: float = 0.05) -> dict:
    order = sorted(pvals, key=lambda k: pvals[k])
    out, stop = {}, False
    for i, k in enumerate(order):
        thr = alpha / (len(order) - i)
        rej = (not stop) and pvals[k] <= thr
        stop = stop or not rej
        out[k] = {"p": pvals[k], "threshold": thr, "reject_H0": rej}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    proto_bytes = Path(a.protocol).read_bytes()
    psha = hashlib.sha256(proto_bytes).hexdigest()
    proto = json.loads(proto_bytes)
    recs = [json.loads(l) for p in a.files for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
    bad_proto = [r["unit"] for r in recs if r.get("protocol_sha256") != psha]
    if bad_proto:
        raise SystemExit(f"{len(bad_proto)} units were produced under a different protocol file: {bad_proto[:3]}")
    methods = [m["id"] for m in proto["methods"]]
    creatures = sorted({r["creature"] for r in recs})
    expected = len(creatures) * len(methods)
    print(f"protocol {proto['id']} sha256 {psha[:12]}; {len(recs)} units (expected {expected}); {len(creatures)} creatures; "
          f"panel {sorted({str(r.get('panel_sha256'))[:12] for r in recs})}; commits {sorted({r['code_commit'] for r in recs})}")
    seen = defaultdict(list)
    for r in recs:
        seen[(r["creature"], r["method"])].append(r)
    dup = [k for k, v in seen.items() if len(v) > 1]
    missing = [(c, m) for c in creatures for m in methods if (c, m) not in seen]
    if dup:
        raise SystemExit(f"duplicate units (a unit was run twice): {dup[:5]}")
    print(f"missing units: {missing}")
    errors = [r["unit"] for r in recs if r.get("status") == "UNIT_ERROR"]
    print(f"unit errors (counted as not recovered): {errors}")
    acct = [r["unit"] for r in recs if r.get("pipeline") and (r["pipeline"]["used"] != sum(l["n"] for l in r["pipeline"]["budget_lines"])
                                                              or r["pipeline"]["used"] > r["budget"])]
    print(f"accounting violations: {acct}")
    rec = {m: {c: (seen.get((c, m)) or [{}])[0].get("status") == FULL for c in creatures} for m in methods}
    status = {m: {c: (seen.get((c, m)) or [{}])[0].get("status") for c in creatures} for m in methods}
    print("\n| method | FULL | PARTIAL | NOT | error/missing | mean validation walking | mean budget used |")
    print("|---|---|---|---|---|---|---|")
    for m in methods:
        sts = list(status[m].values())
        ws = [r["assessment"]["validation"]["walking_frac"] for c in creatures for r in seen.get((c, m), []) if r.get("assessment")]
        us = [r["pipeline"]["used"] / r["budget"] for c in creatures for r in seen.get((c, m), []) if r.get("pipeline")]
        print(f"| {m} | {sts.count(FULL)} | {sts.count('PARTIAL_IMPROVEMENT')} | {sts.count('NOT_RECOVERED')} | "
              f"{len(sts) - sts.count(FULL) - sts.count('PARTIAL_IMPROVEMENT') - sts.count('NOT_RECOVERED')} | "
              f"{sum(ws) / max(1, len(ws)):.2f} | {sum(us) / max(1, len(us)):.2f} |")
    prim = mcnemar(rec["ai_v2"], rec["fix"], creatures)
    print(f"\nPRIMARY ai_v2 > fix: ai-only {prim['a_only']}, fix-only {prim['b_only']}, both {prim['both']}, neither {prim['neither']}; "
          f"exact one-sided McNemar p = {prim['p']:.4f} -> {'SUPPORTED' if prim['p'] < 0.05 else 'NOT SUPPORTED'} at alpha 0.05")
    sec = {f"ai_v2 > {b}": mcnemar(rec["ai_v2"], rec[b], creatures) for b in ("cma_joint", "rand", "cma_ctrl")}
    h = holm({k: v["p"] for k, v in sec.items()})
    print("SECONDARY (Holm):")
    for k, v in sec.items():
        print(f"- {k}: {v['a_only']} vs {v['b_only']} discordant, p = {v['p']:.4f}, Holm threshold {h[k]['threshold']:.4f} -> "
              f"{'reject H0' if h[k]['reject_H0'] else 'not rejected'}")
    print("EXPLORATORY (two-sided, no multiplicity claim):")
    expl = {}
    for x, y in (("fix", "cma_joint"), ("rand", "fix"), ("cma_joint", "cma_ctrl")):
        expl[f"{x} vs {y}"] = e = mcnemar(rec[x], rec[y], creatures, two_sided=True)
        print(f"- {x} vs {y}: {e['a_only']} vs {e['b_only']} discordant, two-sided p = {e['p']:.4f}")
    region = {}
    for c in creatures:
        r0 = (seen.get((c, "ai_v2")) or [{}])[0]
        region.setdefault(r0.get("region", "?"), []).append(c)
    diffs = [sum(rec["ai_v2"][c] for c in cs) - sum(rec["fix"][c] for c in cs) for cs in region.values()]
    pos, neg = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    p_reg = binom_upper(pos, pos + neg)
    print(f"region-cluster sign test (ai_v2 - fix): {pos} regions favour ai, {neg} favour fix, {len(diffs) - pos - neg} tied; one-sided p = {p_reg:.4f}")
    ai = [r for c in creatures for r in seen.get((c, "ai_v2"), []) if r.get("director_record")]
    if ai:
        plans = [p for r in ai for d in r["pipeline"]["decisions"] if d["kind"] == "plans" for p in d["returned"]]
        cost = sum(r["director_record"].get("cost_usd") or 0 for r in ai)
        calls = sum(len(r["director_record"].get("calls") or []) for r in ai)
        valid = sum(any(d["kind"] == "plans" and d["status"] == "ok" and d["returned"] for d in r["director_record"]["decisions"]) for r in ai)
        print(f"\nAI: {len(ai)} pipelines, valid plan in {valid}; plans with body co-design {sum(1 for p in plans if p['body_params'])}/{len(plans)}; "
              f"{calls} calls, ${cost:.4f}")
    if a.out:
        Path(a.out).write_text(json.dumps({"protocol_sha256": psha, "n_creatures": len(creatures), "missing": missing, "unit_errors": errors,
                                           "accounting_violations": acct, "full": {m: sum(rec[m].values()) for m in methods},
                                           "primary": prim, "secondary": sec, "holm": h, "exploratory": expl,
                                           "region_sign_test": {"pos": pos, "neg": neg, "p": p_reg}}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
