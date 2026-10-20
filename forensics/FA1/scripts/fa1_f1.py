"""FA-1 F1 (diagnosis -> recovery), F4 (Nemotron decision funnel) and budget tables from episode_index / repair_decisions."""
from __future__ import annotations

import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = lambda x: x in (True, "True")  # noqa: E731


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(k, n):
    lo, hi = L.wilson(k, n)
    return f"{k}/{n} ({lo:.2f}-{hi:.2f})"


def main():
    E = load("episode_index.csv")
    R = load("repair_decisions.csv")
    arms = ["A1e", "A1e6", "A3v5", "A4x"]
    print("## F1.1 diagnosis x FULL (Wilson 95% CI; episodes, not independent bases)")
    for kind in ("single", "composition"):
        for arm in arms:
            rows = [e for e in E if e["arm"] == arm and e["kind"] == kind]
            for lab, f in (("exact", "true_structure_match"), ("primitive", "true_primitive_overlap"), ("kind", "true_kind_overlap")):
                c = [e for e in rows if B(e[f])]
                w = [e for e in rows if not B(e[f])]
                print(f"  {kind:11s} {arm:5s} {lab:9s} correct: FULL {pct(sum(B(e['full']) for e in c), len(c))} | "
                      f"wrong: FULL {pct(sum(B(e['full']) for e in w), len(w))}")
    print("\n## pooled singles (4 arms x 30, clustered by instance)")
    rows = [e for e in E if e["kind"] == "single"]
    for f in ("true_structure_match", "true_primitive_overlap"):
        c = [e for e in rows if B(e[f])]
        w = [e for e in rows if not B(e[f])]
        print(f"  {f}: correct {pct(sum(B(e['full']) for e in c), len(c))}; wrong {pct(sum(B(e['full']) for e in w), len(w))}")

    print("\n## F1.3 failure categories (non-FULL) per arm and kind")
    for kind in ("single", "composition"):
        for arm in arms:
            c = collections.Counter(e["verification_category"] for e in E if e["arm"] == arm and e["kind"] == kind)
            print(f"  {kind:11s} {arm:5s} {dict(c)}")
    c = collections.Counter(e["verification_category"] for e in E)
    print("  ALL", dict(c))
    c = collections.Counter((e["verification_category"], B(e["true_structure_match"])) for e in E if e["kind"] == "single")
    print("  singles category x exact-correct", dict(c))
    print("  verdicts among non-FULL:", collections.Counter(e["verdict"] for e in E if not B(e["full"])))
    # validation walking distribution among walking-robustness failures
    vw = sorted(float(e["val_walking_frac"]) for e in E if e["verification_category"].startswith("walking robustness"))
    print("  val walking frac among walking-robustness failures: n", len(vw), "quartiles",
          [round(vw[int(q * (len(vw) - 1))], 3) for q in (0, .25, .5, .75, 1)], "n>=0.6:", sum(v >= 0.6 for v in vw),
          "n<0.2:", sum(v < 0.2 for v in vw))

    print("\n## F1.4 per-instance outcome pattern across the 4 arms")
    by_inst = collections.defaultdict(dict)
    for e in E:
        by_inst[e["instance_id"]][e["arm"]] = e
    pat = collections.Counter()
    for iid, d in by_inst.items():
        k = sum(B(d[a]["full"]) for a in arms)
        pat[(d["A1e"]["kind"], k)] += 1
    print("  (kind, #arms FULL) ->", sorted(pat.items()))
    # instances with at least one FULL: list
    print("\n  instances with mixed outcomes:")
    mixed = []
    for iid, d in sorted(by_inst.items()):
        k = sum(B(d[a]["full"]) for a in arms)
        if 0 < k < 4:
            mixed.append(iid)
            s = " | ".join(f"{a}:{'F' if B(d[a]['full']) else '-'} {d[a]['final_repair_tool'] or d[a]['submitted_source']} "
                           f"[{d[a]['tool_sequence']}] dx={'Y' if B(d[a]['true_structure_match']) else 'n'}"
                           for a in arms)
            print(f"   {iid}: {s}")
    # same-tool comparisons on the same instance
    print("\n## F1.6/7 same instance, same submitted-design tool, different outcome")
    same, diff = 0, 0
    examples = []
    for iid, d in by_inst.items():
        tools = collections.defaultdict(list)
        for a in arms:
            tools[d[a]["final_repair_tool"]].append((a, B(d[a]["full"])))
        for t, lst in tools.items():
            if not t or len(lst) < 2:
                continue
            outs = {f for _, f in lst}
            if len(outs) > 1:
                diff += 1
                examples.append((iid, t, lst))
            else:
                same += 1
    print(f"  (instance, tool) groups with >=2 arms: consistent outcome {same}, conflicting outcome {diff}")
    for x in examples:
        print("   ", x)
    # first plant tool comparison
    print("\n## first plant-optimisation tool agreement vs A1e6 (same instance)")
    def first_plant(e):
        for s in e["tool_sequence"].split(">"):
            if s.startswith("plant:"):
                return s.split(":")[1]
        return ""
    def first_tool(e):
        s = e["tool_sequence"].split(">")[0]
        return s.split(":")[1] if ":" in s else ""
    for a in ("A1e", "A3v5", "A4x"):
        agree = collections.Counter()
        for iid, d in by_inst.items():
            x, y = d[a], d["A1e6"]
            same_t = first_tool(x) == first_tool(y) and first_tool(x) != ""
            agree[(same_t, B(x["full"]), B(y["full"]))] += 1
        print(f"  {a} vs A1e6: (same first tool, {a} FULL, A1e6 FULL) -> {dict(sorted(agree.items()))}")

    print("\n## F1.5 discordant pairs vs A1e6 with the decisions that differed")
    for a in ("A1e", "A3v5", "A4x"):
        for iid, d in sorted(by_inst.items()):
            x, y = d[a], d["A1e6"]
            if B(x["full"]) != B(y["full"]):
                print(f"  {a} vs A1e6 {iid} [{x['kind']}]: {a} {'FULL' if B(x['full']) else x['verification_category']} "
                      f"seq={x['tool_sequence']} sub={x['submitted_source']} dx={x['leading_diagnosis']} plant={x['plant_used']} twin={x['twin_used']} "
                      f"|| A1e6 {'FULL' if B(y['full']) else y['verification_category']} seq={y['tool_sequence']} sub={y['submitted_source']} "
                      f"dx={y['leading_diagnosis']} plant={y['plant_used']}")

    print("\n## exact McNemar (two-sided and one-sided) on paired FULL")
    for kind in ("single", "composition", "all"):
        for a, b in (("A1e6", "A1e"), ("A3v5", "A1e6"), ("A4x", "A1e6"), ("A4x", "A3v5"), ("A3v5", "A1e"), ("A4x", "A1e")):
            bb = cc = n = 0
            for iid, d in by_inst.items():
                if kind != "all" and d[a]["kind"] != kind:
                    continue
                n += 1
                fa, fb = B(d[a]["full"]), B(d[b]["full"])
                bb += fa and not fb
                cc += fb and not fa
            print(f"  {kind:11s} {a} vs {b}: n {n}, {a}-only {bb}, {b}-only {cc}, p1({a}>{b}) {L.mcnemar_one_sided(bb, cc):.3f}, "
                  f"p2 {L.mcnemar_two_sided(bb, cc):.3f}, diff {(bb - cc) / n:+.3f}")

    print("\n## independent bases")
    for kind in ("single", "composition"):
        bases = collections.Counter(e["robot_base"] for e in E if e["arm"] == "A1e6" and e["kind"] == kind)
        fams = collections.Counter(e["failure_family"] for e in E if e["arm"] == "A1e6" and e["kind"] == kind)
        print(f"  {kind}: {len(bases)} bases {dict(bases)}; families {dict(fams)}")
    allb = {e["robot_base"] for e in E}
    print("  total distinct bases", len(allb))
    # base-grouped FULL per arm
    print("\n## base-level FULL rates (singles), per arm: bases with any FULL / bases")
    for a in arms:
        per = collections.defaultdict(list)
        for e in E:
            if e["arm"] == a and e["kind"] == "single":
                per[e["robot_base"]].append(B(e["full"]))
        print(f"  {a}: bases with >=1 FULL {sum(any(v) for v in per.values())}/{len(per)}; per-base {{{', '.join(f'{k[-4:]}:{sum(v)}/{len(v)}' for k, v in sorted(per.items()))}}}")

    print("\n## budgets (median [IQR]) per arm and kind")
    import numpy as np
    for kind in ("single", "composition"):
        for a in arms:
            rows = [e for e in E if e["arm"] == a and e["kind"] == kind]
            def q(f):
                v = np.array([float(e[f]) for e in rows])
                return f"{np.median(v):.0f} [{np.percentile(v, 25):.0f}-{np.percentile(v, 75):.0f}]"
            tw = collections.Counter()
            pl = collections.Counter()
            for e in rows:
                tw.update(json.loads(e["twin_breakdown"]))
                pl.update(json.loads(e["plant_breakdown"]))
            n = len(rows)
            print(f"  {kind:11s} {a:5s} plant {q('plant_used')} twin {q('twin_used')} plant_diag {q('plant_diag')} twin_diag {q('twin_diag')} "
                  f"twin_remaining {q('twin_remaining')} plant_remaining {q('plant_remaining')} diag_exps {q('n_diag_experiments')}")
            print(f"      twin mean/episode by op: {{{', '.join(f'{k}: {v / n:.0f}' for k, v in sorted(tw.items(), key=lambda t: -t[1]))}}}")
            print(f"      plant mean/episode by op: {{{', '.join(f'{k}: {v / n:.0f}' for k, v in sorted(pl.items(), key=lambda t: -t[1]))}}}")
            print(f"      warm start ran {sum(B(e['warm_start_ran']) for e in rows)}/{n}; screen unavailable {sum(int(e['tool_screen_unavailable']) > 0 for e in rows)}; "
                  f"twin-exhausted(update) episodes {sum(int(e['n_twin_exhausted_update']) > 0 for e in rows)}; "
                  f"termination {dict(collections.Counter(e['termination'] for e in rows))}")

    print("\n## F1.8 / H5: submitted vs best non-submitted checked design (plant evidence only)")
    by_ep = collections.defaultdict(list)
    for x in R:
        by_ep[(x["instance_id"], x["arm"])].append(x)
    alt_better = []
    for (iid, a), steps in by_ep.items():
        sub = [s for s in steps if B(s["is_submitted"])]
        oth = [s for s in steps if not B(s["is_submitted"]) and s["plant_check16"] not in ("", "None")]
        if not sub or not oth:
            continue
        s16 = sub[0]["plant_check16"]
        s16 = int(s16) if s16 not in ("", "None") else -1
        for o in oth:
            if int(o["plant_check16"]) > s16:
                alt_better.append((iid, a, sub[0]["tool"], s16, sub[0]["p_full_map"], o["tool"], o["plant_check16"], o["p_full_map"], sub[0]["episode_full"]))
    print("  episodes where a non-submitted design had more robust16 walking than the submitted one:", len(alt_better))
    for x in alt_better:
        print("   ", x)
    # robust16 of submitted design vs FULL
    print("\n## submitted-design plant evidence vs FULL (v6 arms, singles+comps)")
    tab = collections.defaultdict(lambda: [0, 0])
    for x in R:
        if B(x["is_submitted"]) and x["plant_check16"] not in ("", "None") and x["arm"] != "A1e":
            k = int(x["plant_check16"])
            band = "16" if k == 16 else "15" if k == 15 else "13-14" if k >= 13 else "8-12" if k >= 8 else "<8"
            tab[band][0] += B(x["episode_full"])
            tab[band][1] += 1
    for k in ("16", "15", "13-14", "8-12", "<8"):
        if k in tab:
            print(f"  robust16 {k}: FULL {tab[k][0]}/{tab[k][1]}")
    tab = collections.defaultdict(lambda: collections.Counter())
    for x in R:
        if B(x["is_submitted"]) and x["arm"] != "A1e" and x["p_full_map"] not in ("", "None"):
            p = float(x["p_full_map"])
            band = ">=0.75" if p >= .75 else "0.5-0.75" if p >= .5 else "0.25-0.5" if p >= .25 else "<0.25"
            tab[band][x["episode_category"]] += 1
    print("  mapped P(FULL) band of the submitted design -> verification category")
    for k in (">=0.75", "0.5-0.75", "0.25-0.5", "<0.25"):
        print("   ", k, dict(tab[k]))


if __name__ == "__main__":
    main()
