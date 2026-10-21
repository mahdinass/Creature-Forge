"""Read-only analysis of the Amendment A1 paired L4 pilot output (no physics)."""
import json, math, sys, statistics as st, collections, hashlib, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\<user>\.vscode\cf-ta1-harness")
from creature_forge import walk_opt as wo, verdict as vd            # names and the frozen verdict statistic (pure functions)
M = json.load(open(r"C:\Users\<user>\.vscode\cf-ta1-harness\experiments\causal_engineer\dev\hdb\ds1\stopmap_dev_v2.json", encoding="utf-8"))
R = [json.loads(l) for l in open("ta1_a1_l4.jsonl", encoding="utf-8") if l.strip()]
def dh(d): return hashlib.sha256(json.dumps({"b": d["body"], "v": d["vector"]}, sort_keys=True).encode()).hexdigest()[:10]
for r in R:
    h = r["harness"]; s = r["verification"]["summary"]; f = r["verification"]["full"]; v = f["validation"]["verdict"]; hc = h["hook_calls"][0]
    print(f"\n=== {h['ta1_arm'].upper()} r{h['replicate']} wall {r['wall_s']:.0f}s submitted d{r['submitted']} {dh(r['designs'][r['submitted']])}")
    print(f"  {s['status']} | walking {round(s['walking_frac']*24)}/24 aggregate {f['validation']['aggregate']} | verdict {v['status']} W/L/T {v['wins']}/{v['losses']}/{v['ties']} "
          f"median {v['median_diff']:+.3f} m p_better {v['p_one_sided']:.4g} | confirmation run={f['confirmation'].get('run')} passed={f['confirmation'].get('passed')}")
    if f["confirmation"].get("run"):
        print("  confirmation checks:", {k: (c.get("value"), c.get("passed")) for k, c in f["confirmation"]["checks"].items()})
    print(f"  reasons: {s['reasons']}")
    o = [x["score"] for x in f["validation"]["original"]]; c = [x["score"] for x in f["validation"]["candidate"]]
    print(f"  validation distances: faulty median {st.median(o):.2f} m, submitted median {st.median(c):.2f} m; candidate labels "
          f"{dict(collections.Counter(x['label'] for x in f['validation']['candidate']))}")
    print(f"  hook: ranking {hc['ranking_tools']} | plan {hc['plan']} | fingerprint {hc['prehook_fingerprint'][:16]} | prehook plant {hc['prehook_plant_used']} twin {hc['prehook_twin_used']}")
    meta = {d["index"]: d for d in r["engine"]["ledger"]["designs"]}
    log = {x["design"]: x for x in r["repair"]["log"]}
    rob = h["robust_checks"]; base = rob["baseline"]; f0 = r["designs"][0]["body"]["foot_friction"]
    for d in r["designs"]:
        i = d["index"]; m = meta[i]; par = m.get("parent")
        if i == 0 or str(i) not in (rob["by_design"] or {}) and i not in log: continue
        ch = []
        if par is not None:
            pb, pv = r["designs"][par]["body"], r["designs"][par]["vector"]
            ch += [f"{k} {pb[k]:.4g}->{d['body'][k]:.4g}" for k in d["body"] if k != "pose" and pb.get(k) != d["body"][k]]
            ch += [f"{wo.ALL_NAMES[j]} {pv[j]:+.4g}->{d['vector'][j]:+.4g}" for j in range(17) if abs(pv[j] - d["vector"][j]) > 1e-12]
        x = log.get(i) or {}; ev = x.get("evidence") or {}
        line = f"  d{i} <- d{par} {m['source']:26s} fric x{d['body']['foot_friction']/f0:.3f} | r8 {x.get('check')} r16 {x.get('check16')} stress4 {ev.get('stress4')} disp {ev.get('disp_status')} {ev.get('disp_median_m')} P {ev.get('p_full')}"
        sc = (rob["by_design"] or {}).get(str(i))
        if sc and sc["n"] == 16 and base:
            out = vd.verdict("walk", base["scores"][:16], sc["scores"], original_pass=base["pass"][:16], candidate_pass=sc["pass"])
            line += f" | robust W/L/T {out['wins']}/{out['losses']}/{out['ties']} med {out['median_diff']:+.3f} -> {out['status']} (recomputed) | robust dist median {st.median(sc['scores']):.2f} vs faulty {st.median(base['scores']):.2f}"
        print(line)
        if ch: print("      changes:", "; ".join(ch))
    print(f"  selection pmap {r['repair']['p_full']} -> d{r['submitted']} | resources plant {h['resources']['plant']} twin {h['resources']['twin']} total {h['resources']['total_rollout_equivalents']}")
    print(f"  rescreen {h['rescreen']['classification']} | complete {h['verification_complete']}")
    if "reproduction" in h: print(f"  CONTROL reproduction exact {h['reproduction']['exact']} ({sum(h['reproduction']['checks'].values())}/{len(h['reproduction']['checks'])}) failing {[k for k,v in h['reproduction']['checks'].items() if not v]}")
    if "stored_prefix" in h: print(f"  TREATMENT stored-prefix {h['stored_prefix']['match']} {h['stored_prefix']['checks']}")
    if "paired_prehook" in h: print(f"  PAIRED {h['paired_prehook']}")
c, t = R
fc, ft = c["harness"]["hook_calls"][0]["prehook_component_fingerprints"], t["harness"]["hook_calls"][0]["prehook_component_fingerprints"]
print("\ncomponent fingerprints equal:", all(fc[k] == ft[k] for k in fc), sorted(fc))
print("same submitted design in both arms:", dh(c["designs"][c["submitted"]]) == dh(t["designs"][t["submitted"]]))
m = json.load(open("ta1_a1_l4.jsonl.manifest.json", encoding="utf-8"))
print("manifest:", {k: m.get(k) for k in ("git_commit", "git_dirty", "harness_commit_approved", "harness_version", "python", "numpy", "mujoco", "platform", "created_utc")}, "amendment", m["amendment"]["id"])
