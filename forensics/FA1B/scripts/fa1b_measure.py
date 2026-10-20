"""FA-1B Investigation A3: what existing records establish about verification losses (read-only, no simulation).

Final per-seed validation/confirmation rows are NOT retained: scripts/hdb_agent_run.py:126-127 keeps only status, walking_frac,
reasons and rollouts of recovery.assess's output (which holds per-seed `validation.original/candidate` rows and the verdict
statistics, recovery.py:168-174). What survives per submitted design: robust-seed walking counts (robust8/16), robust-seed
displacement evidence (verdict_v1 on 16 paired robust seeds vs the faulty design: status, median diff; per-seed scores are not
serialised, hdb_evidence.py:51,83), the final status/walking fraction/verdict status, the faulty robot's eligibility labels on
8 check seeds, and the submitted design's body. Also ds1_stopdata*.jsonl: fresh robust re-measurements of earlier submitted
designs on init bases paired with their final status (scripts/ds1_stop_data.py)."""
import collections
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L

E = {(r["instance_id"], r["arm"]): r for r in csv.DictReader(open(os.path.join(L.FA1, "episode_index.csv"), encoding="utf-8"))}
RD = list(csv.DictReader(open(os.path.join(L.FA1, "repair_decisions.csv"), encoding="utf-8")))


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def sub_evidence(r):
    """Evidence of the submitted design from the engine repair log or the Nemotron trace."""
    sub = r["submitted"]
    conc = ((r.get("agent") or {}).get("conclusion") or {})
    for s in ((conc.get("repair") or {}).get("log") or []):
        if s.get("design") == sub and s.get("evidence"):
            return s["evidence"], s.get("tool"), s.get("step")
    ev = ((r.get("agent") or {}).get("evidence") or {}).get(str(sub))
    if ev:
        return ev, None, "nemotron"
    for s in ((conc.get("repair") or {}).get("log") or []):
        if s.get("design") == sub:
            return {"robust8": s.get("check"), "robust16": s.get("check16")}, s.get("tool"), s.get("step")
    return {}, None, None


def leg(b):
    return (float(b["thigh_length"]) + float(b["shank_length"]))


def main():
    rows = []
    for path, line, r in L.load_eval():
        e = E[(r["instance_id"], r["arm"])]
        ev, tool, step = sub_evidence(r)
        d0, ds = r["designs"][0]["body"], r["designs"][r["submitted"]]["body"]
        rows.append({"iid": r["instance_id"], "arm": r["arm"], "family": r["family"], "cat": e["verification_category"],
                     "verdict": e["verdict"], "val_k": round(float(e["val_walking_frac"]) * 24), "status": e["status"],
                     "r16": ev.get("robust16"), "r8": ev.get("robust8"), "disp_status": ev.get("disp_status"),
                     "disp_med": ev.get("disp_median_m"), "pfull": ev.get("p_full"), "step": step,
                     "tool": e["final_repair_tool"], "leg_ratio": round(leg(ds) / leg(d0), 3),
                     "fric_ratio": round(float(ds["foot_friction"]) / float(d0["foot_friction"]), 3),
                     "faulty_labels": collections.Counter(r["check"]["labels"]), "faulty_walk8": r["check"]["walking"],
                     "raw": f"{path}#L{line + 1}"})
    print("## A3.1 robust-seed displacement status (16 paired robust seeds) x final verdict_v1 (24 paired validation seeds), "
          "submitted designs, v6 arms")
    t = collections.Counter((x["disp_status"], x["verdict"] or "VERIFIED(FULL/PARTIAL)") for x in rows if x["arm"] != "A1e")
    for k, v in sorted(t.items(), key=lambda kv: str(kv[0])):
        print("  ", k, v)
    print("\n## A3.2 the 20 displacement-only failures (walks >= 80 % on validation, verdict not VERIFIED)")
    D = [x for x in rows if x["cat"].startswith("displacement only")]
    for x in sorted(D, key=lambda x: (x["iid"], x["arm"])):
        print(f"   {x['iid']:48s} {x['arm']:5s} val {x['val_k']}/24 {x['verdict']:12s} r16 {x['r16']} robust-disp {x['disp_status']} "
              f"{x['disp_med']} | tool {x['tool']} leg x{x['leg_ratio']} fric x{x['fric_ratio']} | faulty check {dict(x['faulty_labels'])}")
    print("   unique instances", len({x["iid"] for x in D}), "| robust-disp status:", collections.Counter(x["disp_status"] for x in D),
          "| verdicts:", collections.Counter(x["verdict"] for x in D))
    lab = collections.Counter()
    for x in D:
        lab.update(x["faulty_labels"])
    print("   faulty-robot eligibility labels pooled over these episodes:", dict(lab))
    lab2 = collections.Counter()
    for x in rows:
        if x["status"] == L.FULL:
            lab2.update(x["faulty_labels"])
    print("   ... and over FULL episodes:", dict(lab2))
    print("\n## A3.3 near-threshold walking failures (validation 17-19/24): robust16 of the submitted design vs validation")
    N = [x for x in rows if 17 <= x["val_k"] <= 19 and x["cat"].startswith("walking robustness")]
    have = [x for x in N if x["r16"] is not None]
    print("   episodes", len(N), "unique instances", len({x["iid"] for x in N}), "| with robust16:", len(have))
    print("   robust16 distribution:", sorted(collections.Counter(x["r16"] for x in have).items()))
    # if the validation walking probability equalled the robust16 rate, how likely is <= observed?
    ps = [binom_cdf(x["val_k"], 24, min(0.999, x["r16"] / 16)) for x in have]
    print("   P(val <= observed | p = robust16/16): median %.3f; < 0.05 in %d of %d" % (sorted(ps)[len(ps) // 2], sum(p < 0.05 for p in ps), len(ps)))
    print("   expected val k under p = r16/16: %.1f, observed mean %.1f" % (sum(24 * x["r16"] / 16 for x in have) / len(have), sum(x["val_k"] for x in have) / len(have)))
    print("\n## A3.4 all submitted designs with robust16: robust rate vs validation rate (selection / winner's-curse check)")
    allr = [x for x in rows if x["r16"] is not None]
    for lo, hi in ((15, 16), (12, 14), (0, 11)):
        xs = [x for x in allr if lo <= x["r16"] <= hi]
        if xs:
            print(f"   robust16 {lo}-{hi}: n {len(xs)}; mean robust rate {sum(x['r16'] for x in xs) / 16 / len(xs):.3f}; mean validation rate "
                  f"{sum(x['val_k'] for x in xs) / 24 / len(xs):.3f}; FULL {sum(x['status'] == L.FULL for x in xs)}")
    print("\n## A3.5 fresh robust re-measurement (ds1_stopdata, init bases): final status by robust16 and displacement status")
    S = []
    for f in ("ds1_stopdata.jsonl", "ds1_stopdata_b.jsonl"):
        for r in L.read_jsonl(os.path.join(L.DS1_DIR, f)):
            for d in r["designs"]:
                S.append(d)
    print("   designs", len(S))
    for lo, hi in ((15, 16), (12, 14), (0, 11)):
        xs = [d for d in S if d.get("robust16") is not None and lo <= d["robust16"] <= hi]
        print(f"   robust16 {lo}-{hi}: n {len(xs)}, FULL {sum(d['status'] == L.FULL for d in xs)}"
              f" | of which disp VERIFIED: n {sum(d.get('disp_status') == 'VERIFIED_IMPROVEMENT' for d in xs)}, FULL "
              f"{sum(d['status'] == L.FULL and d.get('disp_status') == 'VERIFIED_IMPROVEMENT' for d in xs)}"
              f" | disp WORSE: n {sum(d.get('disp_status') == 'WORSE' for d in xs)}, FULL {sum(d['status'] == L.FULL and d.get('disp_status') == 'WORSE' for d in xs)}")
    print("\n## A3.6 submitted-design leg length (thigh + shank) relative to the faulty design, by outcome category")
    band = lambda x: "legs <= x0.85" if x <= 0.85 else ("legs >= x1.15" if x >= 1.15 else "legs ~ x1")  # noqa: E731
    t = collections.Counter((band(x["leg_ratio"]), x["cat"].split(" (")[0]) for x in rows)
    for k, v in sorted(t.items()):
        print("  ", k, v)
    short = [x for x in rows if x["leg_ratio"] <= 0.85]
    print("   legs <= x0.85: designs", len(short), "instances", len({x["iid"] for x in short}), "FULL", sum(x["status"] == L.FULL for x in short))


if __name__ == "__main__":
    main()
