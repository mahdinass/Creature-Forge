"""FA-1C Phase 1B follow-up (read-only, no physics): candidate reconstruction, stop-map v2 decomposition and audit."""
import collections, csv, json, math, os, sys
sys.stdout.reconfigure(encoding="utf-8")
H = r"C:\Users\<user>\.vscode"
B1 = os.path.join(H, "creature_forge_runs", "fa1c_phase1b_2026-10-20", "ta1_phase1b.jsonl")
A1 = os.path.join(H, "creature_forge_runs", "fa1c_phase1a_2026-10-20", "rv1_phase1a.jsonl")
MAP = os.path.join(H, "cf-ta1-harness", "experiments", "causal_engineer", "dev", "hdb", "ds1", "stopmap_dev_v2.json")
STOP = [os.path.join(H, "Creature-Forge", "artifacts", "vm", "ds1", f) for f in ("ds1_stopdata.jsonl", "ds1_stopdata_b.jsonl")]
RD = os.path.join(H, "creature_forge_forensics_2026-10-20", "repair_decisions.csv")
sys.path.insert(0, os.path.join(H, "cf-ta1-harness"))
from creature_forge import walk_opt as wo          # names only (no physics)
M = json.load(open(MAP, encoding="utf-8"))
W = M["w"]
NAMES = ["bias", "robust16_logit", "stress4_logit", "disp_pass", "disp_median_clipped"]

def feats(r16, s4, dp, med):
    lo, hi = M["disp_clip"]
    return [1.0, math.log((r16 + .5) / (16 - r16 + .5)), math.log((s4 + .5) / (4 - s4 + .5)), 1.0 if dp else 0.0, min(hi, max(lo, med))]
def p(x): z = sum(a * b for a, b in zip(W, x)); return z, 1 / (1 + math.exp(-z))

R = [json.loads(l) for l in open(B1, encoding="utf-8") if l.strip()]
print("## 1. Candidates (stop map logistic_v2, w =", [round(w, 4) for w in W], ")")
for r in R:
    arm = r["harness"]["ta1_arm"]
    meta = {d["index"]: d for d in r["engine"]["ledger"]["designs"]}
    log = {s["design"]: s for s in r["repair"]["log"]}
    pmap = r["repair"]["p_full"]
    f0 = r["designs"][0]["body"]["foot_friction"]
    for d in r["designs"]:
        i = d["index"]; m_ = meta[i]; par = m_.get("parent")
        ch = []
        if par is not None:
            pb, pv = r["designs"][par]["body"], r["designs"][par]["vector"]
            ch += [f"{k} {pb[k]:.4g}->{d['body'][k]:.4g}" for k in d["body"] if k != "pose" and pb.get(k) != d["body"][k]]
            ch += [f"{wo.ALL_NAMES[j]} {pv[j]:+.4g}->{d['vector'][j]:+.4g}" for j in range(len(pv)) if abs(pv[j] - d["vector"][j]) > 1e-12]
        s = log.get(i)
        line = f"  {arm:9s} d{i} parent {par} {m_['source']:30s} fric x{d['body']['foot_friction']/f0:.3f}"
        if s:
            ev = s.get("evidence") or {}
            line += f" | r8 {s.get('check')} r16 {s.get('check16')} stress4 {ev.get('stress4')} disp {ev.get('disp_status')} med {ev.get('disp_median_m')}"
            if ev.get("robust16") is not None and ev.get("stress4") is not None and ev.get("disp_pass") is not None:
                x = feats(ev["robust16"], ev["stress4"], ev["disp_pass"], ev["disp_median_m"]); z, pp = p(x)
                terms = {n: round(a * b, 3) for n, a, b in zip(NAMES, W, x)}
                line += f" | z {z:.3f} P {pp:.4f} (recorded {ev.get('p_full'):.4f}) terms {terms}"
            line += f" | eligible {str(i) in pmap}"
        print(line)
        if ch:
            print("      changes vs parent:", "; ".join(ch))
    print(f"  {arm}: selected design {r['submitted']} (rule: max mapped P, then walking fraction, then index; tau 0.75 never reached)")
print("\n## 2. Counterfactual decomposition, treatment d3 vs d4")
x3, x4 = feats(16, 2, False, 0.0071), feats(16, 4, False, -2.7306)
for lab, x in (("d3 actual", x3), ("d3 with stress4=4", feats(16, 4, False, 0.0071)), ("d3 with median=-2.73", feats(16, 2, False, -2.7306)), ("d4 actual", x4),
               ("d4 with median=0.0071", feats(16, 4, False, 0.0071)), ("any design, disp_pass True, r16 16, s4 4, median +0.5", feats(16, 4, True, 0.5))):
    z, pp = p(x); print(f"  {lab:55s} z {z:+.3f} P {pp:.4f}")
dz = [a * (b - c) for a, b, c in zip(W, x4, x3)]
print("  z(d4)-z(d3) by term:", {n: round(v, 3) for n, v in zip(NAMES, dz)}, "total", round(sum(dz), 3))
print("\n## 3. Faulty robot on L1 validation seeds (Phase 1A R1, per-seed, verified)")
for r in (json.loads(l) for l in open(A1, encoding="utf-8")):
    if r.get("id") == "R1":
        v = r["verification"]["full"]["validation"]
        o = sorted(x["score"] for x in v["original"]); c = sorted(x["score"] for x in v["candidate"])
        print("  faulty scores (m): min %.2f median %.2f max %.2f; labels %s" % (o[0], o[12], o[-1], dict(collections.Counter(x["label"] for x in v["original"]))))
        print("  control submitted design scores (m): min %.2f median %.2f max %.2f" % (c[0], c[12], c[-1]))
print("\n## 4. Stop-map training data (ds1_stopdata*, 678 init-base designs): FULL by displacement evidence")
S = [d for f in STOP for rec in (json.loads(l) for l in open(f, encoding="utf-8") if l.strip()) for d in rec["designs"]]
g = collections.defaultdict(lambda: [0, 0])
for d in S:
    if d.get("disp_median_m") is None: continue
    med = d["disp_median_m"]; b = "<= -1.5" if med <= -1.5 else "(-1.5,-0.5]" if med <= -.5 else "(-0.5,0.5)" if med < .5 else "[0.5,1.5)" if med < 1.5 else ">= 1.5"
    k = (bool(d["disp_pass"]), d.get("disp_status"), b); g[k][0] += d["status"] == "FULL_RECOVERY"; g[k][1] += 1
for k in sorted(g, key=str): print(f"  pass={k[0]!s:5s} {k[1]:20s} median {k[2]:12s}: FULL {g[k][0]}/{g[k][1]}")
fail = [d for d in S if d.get("disp_pass") is False]
print(f"  all disp_pass=False designs: FULL {sum(d['status']=='FULL_RECOVERY' for d in fail)}/{len(fail)}")
print("\n## 5. DS-1 dev-eval (FA-1 repair_decisions.csv): submitted design vs a checked alternative with a better displacement status")
rank = {"VERIFIED_IMPROVEMENT": 3, "NOT_VERIFIED": 2, "INCONCLUSIVE": 2, "WORSE": 0}
rows = list(csv.DictReader(open(RD, encoding="utf-8")))
ep = collections.defaultdict(list)
for x in rows:
    ep[(x["instance_id"], x["arm"])].append(x)
cnt = collections.Counter(); ex = []
for k, xs in ep.items():
    sub = [x for x in xs if x["is_submitted"] == "True"]
    if not sub or k[1] == "A1e": continue
    s = sub[0]; sd = s.get("disp_pass")
    alts = [x for x in xs if x["is_submitted"] != "True" and x.get("p_full_map") not in ("", None)]
    cnt["episodes with mapped alternatives"] += bool(alts)
    for a in alts:
        def st(v): return "VERIFIED_IMPROVEMENT" if v.get("disp_pass") == "True" else None
        if a["disp_pass"] == "True" and s["disp_pass"] != "True":
            cnt["alternative disp-PASS but submitted disp-fail"] += 1; ex.append((k, "pass-alt", a["design"], a["p_full_map"], a["stress4"], s["design"], s["p_full_map"], s["stress4"], s["episode_full"]))
        elif a["disp_pass"] != "True" and s["disp_pass"] != "True" and a["disp_median_m"] and s["disp_median_m"] and float(a["disp_median_m"]) > float(s["disp_median_m"]) + 0.5:
            cnt["both fail, alternative median >0.5 m higher"] += 1; ex.append((k, "higher-median-alt", a["design"], a["p_full_map"], a["stress4"], s["design"], s["p_full_map"], s["stress4"], s["episode_full"]))
print(" ", dict(cnt))
for e in ex[:14]: print("   ", e)
