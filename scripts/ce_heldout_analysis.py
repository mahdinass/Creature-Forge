"""The single analysis of the registered held-out evaluation (experiments/causal_engineer/heldout/PROTOCOL.md).

    python scripts/ce_heldout_analysis.py --results <result jsonl ...> --instances <heldout instance jsonl ...> \
        --protocol experiments/causal_engineer/heldout/protocol.json --memory-probe <dev probe jsonl> \
        [--memory-episodes <dev episode jsonl,...>] --learned-model <level_c json> --out summary.json --report REPORT_DRAFT.md

Primary: FULL_RECOVERY per instance; one-sided exact McNemar per hypothesis (C2-C5b); C1 = exact sign test of per-episode prediction
accuracy against the majority-direction baseline; Holm-Bonferroni over the six. Secondary and descriptive measures as registered.
Written to be run ONCE on complete results. Episodes outside the registered instance list are ignored and counted.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ce_analysis import repair_tools  # noqa: E402

FULL = "FULL_RECOVERY"
REPAIR_OK = 0.75
HYPOTHESES = (("C2", "scientist_think", "scientist_1shot_think"), ("C3", "scientist_think", "exhaustive"),
              ("C4", "scientist_think_mem", "scientist_think"), ("C5a", "learned", "exhaustive"),
              ("C5b", "scientist_think_mem_learned", "scientist_think_mem"))
CATEGORY_TOOL = {"posture_bias": "posture", "cadence_too_fast": "timing", "weak_balance_feedback": "feedback",
                 "poor_foot_placement": "placement", "short_support_base": "foot_length", "heavy_upper_body": "torso_mass",
                 "low_torque_authority": "torque_limit", "low_traction": "foot_friction", "leg_geometry_mismatch": "leg_length",
                 "low_joint_impedance": "feedback"}


def binom_upper(k: int, n: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 0.5)."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def mcnemar(a: dict, b: dict, ids: list) -> dict:
    """One-sided exact McNemar: A recovers more than B."""
    ab = sum(1 for i in ids if a.get(i) == FULL and b.get(i) != FULL)
    ba = sum(1 for i in ids if b.get(i) == FULL and a.get(i) != FULL)
    return {"a_only": ab, "b_only": ba, "a_full": sum(1 for i in ids if a.get(i) == FULL),
            "b_full": sum(1 for i in ids if b.get(i) == FULL), "n": len(ids), "p_one_sided": binom_upper(ab, ab + ba)}


def holm(ps: dict, alpha: float = 0.05) -> dict:
    order = sorted(ps, key=lambda k: ps[k])
    out, stop = {}, False
    for j, k in enumerate(order):
        thr = alpha / (len(order) - j)
        rej = (not stop) and ps[k] <= thr
        stop = stop or not rej
        out[k] = {"p": ps[k], "holm_threshold": thr, "reject_null": rej}
    return out


def wilcoxon(x: list, y: list) -> dict:
    """Two-sided Wilcoxon signed-rank, normal approximation with tie correction (secondary measure)."""
    d = [a - b for a, b in zip(x, y) if a is not None and b is not None and abs(a - b) > 1e-12]
    n = len(d)
    if n == 0:
        return {"n": 0, "p_two_sided": 1.0}
    ab = sorted((abs(v), i) for i, v in enumerate(d))
    ranks = [0.0] * n
    i = 0
    ties = 0.0
    while i < n:
        j = i
        while j + 1 < n and ab[j + 1][0] == ab[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[ab[k][1]] = r
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    w = sum(r for r, v in zip(ranks, d) if v > 0)
    mu = n * (n + 1) / 4
    sd = math.sqrt(n * (n + 1) * (2 * n + 1) / 24 - ties / 48)
    z = (w - mu) / sd if sd > 0 else 0.0
    return {"n": n, "w_plus": w, "z": z, "p_two_sided": math.erfc(abs(z) / math.sqrt(2))}


def load(paths):
    return [json.loads(l) for p in paths for l in open(p, encoding="utf-8") if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--instances", nargs="+", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--memory-probe")
    ap.add_argument("--memory-episodes")
    ap.add_argument("--learned-model")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()
    proto = json.load(open(a.protocol, encoding="utf-8"))
    ids = list(proto["instance_ids"])
    inst = {r["instance_id"]: r for r in load(a.instances) if r.get("kept")}
    recs = load(a.results)
    outside = sum(1 for r in recs if r["instance_id"] not in set(ids))
    by = defaultdict(dict)
    for r in recs:
        if r["instance_id"] in set(ids):
            by[r["policy"]][r["instance_id"]] = r
    status = {p: {i: ((r.get("verification") or {}).get("status") or "ERROR") for i, r in d.items()} for p, d in by.items()}
    arms = {}
    for p, d in sorted(by.items()):
        st = list(status[p].values())
        missing = [i for i in ids if i not in d]
        good_any = first_ok = n_dec = 0
        diag_inj = diag_cons = n_diag = 0
        strata = defaultdict(lambda: [0, 0])
        for i, r in d.items():
            m = (inst.get(i) or {}).get("repair_matrix") or {}
            good = {t for t, v in m.items() if isinstance(v, (int, float)) and v >= REPAIR_OK}
            tools = repair_tools(r)
            if m:
                n_dec += 1
                good_any += bool(set(tools) & good)
                first_ok += bool(tools and tools[0] in good)
            dg = r.get("diagnosis")
            if isinstance(dg, dict) and dg.get("category"):
                n_diag += 1
                diag_inj += bool(dg.get("match"))
                ok = CATEGORY_TOOL.get(dg["category"]) in good
                diag_cons += ok
                s = "specific" if len(good) <= 2 else "over_determined"
                strata[s][0] += ok
                strata[s][1] += 1
        pr = [r.get("prediction_accuracy") or {} for r in d.values()]
        steps = [st_ for r in d.values() for st_ in ((r.get("policy_record") or {}).get("steps") or [])]
        arms[p] = {"n": len(d), "missing": len(missing), "full": st.count(FULL), "partial": st.count("PARTIAL_IMPROVEMENT"),
                   "not": st.count("NOT_RECOVERED"), "error": sum(1 for x in st if x not in (FULL, "PARTIAL_IMPROVEMENT", "NOT_RECOVERED")),
                   "mean_walking": sum((r.get("walking_frac") or 0.0) for r in d.values()) / max(1, len(d)),
                   "mean_rollouts": sum((r.get("rollouts_used") or 0) for r in d.values()) / max(1, len(d)),
                   "chose_repairing_tool": [good_any, n_dec], "first_repair_repairs": [first_ok, n_dec],
                   "diagnosis_injected_match": [diag_inj, n_diag], "diagnosis_repair_consistent": [diag_cons, n_diag],
                   "repair_consistent_by_stratum": dict(strata),
                   "predictions_scored": sum(x.get("n_scored") or 0 for x in pr), "predictions_correct": sum(x.get("n_correct") or 0 for x in pr),
                   "status_updates": sum(len((s.get("parsed") or {}).get("status_updates") or []) for s in steps if s.get("status") == "ok"),
                   "llm_usd": sum(((r.get("llm") or {}).get("cost_usd") or 0.0) for r in d.values()),
                   "wall_s_mean": sum((r.get("wall_s") or 0.0) for r in d.values()) / max(1, len(d))}
    tests = {}
    for hid, A, B in HYPOTHESES:
        if A in status and B in status:
            tests[hid] = {"a": A, "b": B, **mcnemar(status[A], status[B], ids)}
    # C1: per-episode prediction accuracy vs majority-direction baseline (scientist_think)
    up = down = 0
    for r in by.get("scientist_think", {}).values():
        ps = r.get("prediction_accuracy") or {}
        if (ps.get("n_scored") or 0) >= 5 and ps.get("accuracy") is not None and ps.get("majority_observed_baseline") is not None:
            if ps["accuracy"] > ps["majority_observed_baseline"] + 1e-12:
                up += 1
            elif ps["accuracy"] < ps["majority_observed_baseline"] - 1e-12:
                down += 1
    tests["C1"] = {"a": "scientist_think accuracy", "b": "majority-direction baseline", "above": up, "below": down,
                   "p_one_sided": binom_upper(up, up + down)}
    family = holm({k: v["p_one_sided"] for k, v in tests.items()})
    for k in tests:
        tests[k].update(family[k])
    secondary = {}
    for hid, A, B in HYPOTHESES:
        if A in by and B in by:
            common = [i for i in ids if i in by[A] and i in by[B]]
            secondary[hid + "_walking"] = wilcoxon([by[A][i].get("walking_frac") for i in common], [by[B][i].get("walking_frac") for i in common])
    # memory verdicts and negative transfer
    mem = {}
    bank = None
    if a.memory_probe:
        from creature_forge import ce_memory
        rows = load(a.memory_probe.split(","))
        eps = load([p for p in (a.memory_episodes or "").split(",") if p])
        bank = ce_memory.build_bank(rows, eps)
    for p in ("scientist_think_mem", "scientist_think_mem_learned"):
        verdicts = Counter()
        neg = pos = 0
        for i, r in by.get(p, {}).items():
            prc = r.get("policy_record") or {}
            items = {m["id"]: m for m in (prc.get("memory") or {}).get("items", [])}
            ass = (prc.get("memory") or {}).get("assessments", {})
            for mid, v in ass.items():
                verdicts[(items.get(mid, {}).get("kind", "?"), v.get("verdict"))] += 1
            tools = repair_tools(r)
            m = (inst.get(i) or {}).get("repair_matrix") or {}
            good = {t for t, v in m.items() if isinstance(v, (int, float)) and v >= REPAIR_OK}
            if not tools or bank is None:
                continue
            for mid, v in ass.items():
                if v.get("verdict") != "applies" or not mid.startswith("EP-"):
                    continue
                try:
                    rm = bank.item_provenance(mid)["record"].get("repair_matrix") or {}
                except KeyError:
                    continue
                if not rm:
                    continue
                best = max(sorted(rm), key=lambda t: rm[t])
                if tools[0] == best:
                    if best in good:
                        pos += 1
                    elif good:
                        neg += 1
        mem[p] = {"verdicts": {f"{k}:{v}": n for (k, v), n in sorted(verdicts.items(), key=str)}, "negative_transfer": neg,
                  "memory_followed_and_correct": pos}
    # Level C advice: does the advised top-1 tool repair; how often is it followed (first repair)
    adv = {"n": 0, "top1_repairs": 0, "followed": 0, "followed_and_repairs": 0}
    for i, r in by.get("scientist_think_mem_learned", {}).items():
        items = ((r.get("policy_record") or {}).get("memory") or {}).get("items", [])
        txt = next((m["text"] for m in items if m.get("kind") == "learned_advice"), None)
        if not txt or "P(repair) " not in txt:
            continue
        top1 = txt.split("P(repair) ", 1)[1].split()[0]
        m = (inst.get(i) or {}).get("repair_matrix") or {}
        good = {t for t, v in m.items() if isinstance(v, (int, float)) and v >= REPAIR_OK}
        tools = repair_tools(r)
        adv["n"] += 1
        adv["top1_repairs"] += top1 in good
        adv["followed"] += bool(tools and tools[0] == top1)
        adv["followed_and_repairs"] += bool(tools and tools[0] == top1 and top1 in good)
    mem["level_c_advice"] = adv
    out = {"protocol": proto.get("id"), "n_registered": len(ids), "results_outside_registry": outside, "arms": arms,
           "tests": tests, "secondary": secondary, "memory": mem}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    lines = ["# Held-out evaluation: analysis output (generated, single run)", "",
             f"Registered instances: {len(ids)}; result rows outside the registry ignored: {outside}.", "",
             "| arm | FULL | PARTIAL | NOT | ERROR | mean walking | rollouts | chose repairing tool | first repair repairs | diag (injected) | diag (repair-consistent) | LLM $ |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for p, v in arms.items():
        lines.append(f"| {p} | {v['full']} | {v['partial']} | {v['not']} | {v['error']} | {v['mean_walking']:.2f} | {v['mean_rollouts']:.0f} | "
                     f"{v['chose_repairing_tool'][0]}/{v['chose_repairing_tool'][1]} | {v['first_repair_repairs'][0]}/{v['first_repair_repairs'][1]} | "
                     f"{v['diagnosis_injected_match'][0]}/{v['diagnosis_injected_match'][1]} | {v['diagnosis_repair_consistent'][0]}/{v['diagnosis_repair_consistent'][1]} | "
                     f"{v['llm_usd']:.2f} |")
    lines += ["", "| test | A | B | A only / B only (or above / below) | p (one-sided) | Holm threshold | null rejected |", "|---|---|---|---|---|---|---|"]
    for k in ("C1", "C2", "C3", "C4", "C5a", "C5b"):
        if k in tests:
            t = tests[k]
            cnt = f"{t.get('a_only', t.get('above'))} / {t.get('b_only', t.get('below'))}"
            lines.append(f"| {k} | {t['a']} | {t['b']} | {cnt} | {t['p_one_sided']:.4f} | {t['holm_threshold']:.4f} | {t['reject_null']} |")
    with open(a.report, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
