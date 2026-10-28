"""Read-only analysis of the DO1-L4-r0 exploratory pilot output (no physics)."""
import collections
import hashlib
import json
import statistics as st
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\<user>\.vscode\cf-ta1-harness")
from creature_forge import walk_opt as wo, verdict as vd            # names and the frozen verdict statistic (pure functions)

R = [json.loads(line) for line in open("do1_l4_r0.jsonl", encoding="utf-8") if line.strip()]


def dh(d):
    return hashlib.sha256(json.dumps({"b": d["body"], "v": d["vector"]}, sort_keys=True).encode()).hexdigest()[:10]


for r in R:
    h = r["harness"]
    s = r["verification"]["summary"]
    f = r["verification"]["full"]
    v = f["validation"]["verdict"]
    hc = h["hook_calls"][0]
    arm = h["do1"]["arm"]
    print(f"\n=== {arm.upper()} r{h['replicate']} wall {r['wall_s']:.0f}s submitted d{r['submitted']} {dh(r['designs'][r['submitted']])}")
    print(f"  {s['status']} | walking {round(s['walking_frac'] * 24)}/24 aggregate {f['validation']['aggregate']} | verdict {v['status']} "
          f"W/L/T {v['wins']}/{v['losses']}/{v['ties']} median {v['median_diff']:+.3f} m p_better {v['p_one_sided']:.4g} | "
          f"confirmation run={f['confirmation'].get('run')} passed={f['confirmation'].get('passed')}")
    if f["confirmation"].get("run"):
        print("  confirmation checks:", {k: (c.get("value"), c.get("passed")) for k, c in f["confirmation"]["checks"].items()})
    print(f"  reasons: {s['reasons']}")
    o = [x["score"] for x in f["validation"]["original"]]
    c = [x["score"] for x in f["validation"]["candidate"]]
    print(f"  validation distances: faulty median {st.median(o):.2f} m, submitted median {st.median(c):.2f} m; candidate labels "
          f"{dict(collections.Counter(x['label'] for x in f['validation']['candidate']))}")
    print(f"  hook: ranking {hc['ranking_tools']} | plan {hc['plan']} | fingerprint {hc['prehook_fingerprint'][:16]} | "
          f"prehook plant {hc['prehook_plant_used']} twin {hc['prehook_twin_used']}")
    meta = {d["index"]: d for d in r["engine"]["ledger"]["designs"]}
    log = {x["design"]: x for x in r["repair"]["log"]}
    rob = h["robust_checks"]
    base = rob["baseline"]
    f0 = r["designs"][0]["body"]["foot_friction"]
    for d in r["designs"]:
        i = d["index"]
        m = meta[i]
        par = m.get("parent")
        if i == 0 or str(i) not in (rob["by_design"] or {}) and i not in log:
            continue
        ch = []
        if par is not None:
            pb, pv = r["designs"][par]["body"], r["designs"][par]["vector"]
            ch += [f"{k} {pb[k]:.4g}->{d['body'][k]:.4g}" for k in d["body"] if k != "pose" and pb.get(k) != d["body"][k]]
            ch += [f"{wo.ALL_NAMES[j]} {pv[j]:+.4g}->{d['vector'][j]:+.4g}" for j in range(17) if abs(pv[j] - d["vector"][j]) > 1e-12]
        x = log.get(i) or {}
        ev = x.get("evidence") or {}
        line = (f"  d{i} <- d{par} {m['source']:26s} fric x{d['body']['foot_friction'] / f0:.3f} | r8 {x.get('check')} "
                f"r16 {x.get('check16')} stress4 {ev.get('stress4')} disp {ev.get('disp_status')} {ev.get('disp_median_m')} P {ev.get('p_full')}")
        sc = (rob["by_design"] or {}).get(str(i))
        if sc and sc["n"] == 16 and base:
            out = vd.verdict("walk", base["scores"][:16], sc["scores"], original_pass=base["pass"][:16], candidate_pass=sc["pass"])
            line += (f" | robust W/L/T {out['wins']}/{out['losses']}/{out['ties']} med {out['median_diff']:+.3f} -> {out['status']} "
                     f"| robust dist median {st.median(sc['scores']):.2f} vs faulty {st.median(base['scores']):.2f}")
        print(line)
        if ch:
            print("      changes:", "; ".join(ch))
    print(f"  accepted {r['repair'].get('accepted')} selection pmap {r['repair'].get('p_full')} -> d{r['submitted']} | resources plant {h['resources']['plant']} "
          f"twin {h['resources']['twin']} total {h['resources']['total_rollout_equivalents']}")
    print(f"  rescreen {h['rescreen']['classification']} | complete {h['verification_complete']} | arm_checks {h.get('arm_checks')}")
    if "reproduction" in h:
        rc = h["reproduction"]["checks"]
        print(f"  FROZEN reproduction exact {h['reproduction']['exact']} ({sum(rc.values())}/{len(rc)}) failing {[k for k, ok in rc.items() if not ok]}")
    if "stored_prefix" in h:
        print(f"  DO1 stored-prefix {h['stored_prefix']['match']} {h['stored_prefix']['checks']}")
    if "paired_prehook" in h:
        print(f"  PAIRED {h['paired_prehook']}")
    if arm == "do1":
        d1 = h["do1"]
        tb = d1["train_baseline"]
        print(f"  DO-1 train baseline (faulty, train seeds {tb['seeds']}): scores {[round(x, 3) for x in tb['scores']]} pass {tb['pass']}")
        for rep in d1["repairs"]:
            if rep.get("refused") is not None:
                print(f"  DO-1 repair {rep['tool']}: REFUSED {rep['refused']}")
                continue
            cands = rep["candidates"]
            sel = rep["selected"]
            feas = [c_ for c_ in cands if c_["feasible"]]
            w4 = [c_ for c_ in cands if c_["walking_count"] == 4]
            print(f"  DO-1 repair #{rep['repair_index']} {rep['tool']}: budget {rep['budget']} (baseline {rep['train_baseline_rollouts']}, "
                  f"cma {rep['cma_budget']}, used {rep['rollouts_used']}) -> d{rep['design_index']} | {rep['n_candidates']} candidates, "
                  f"{len(w4)} walk 4/4, {len(feas)} feasible | restarts {len(rep['cma']['restarts'] or [])} errors {len(rep['cma']['errors'] or [])}")
            print(f"      init: W {cands[0]['walking_count']} S {cands[0]['survival_count']} feasible {cands[0]['feasible']} "
                  f"med gain {cands[0]['median_diff_m']:+.3f} m margin {cands[0]['margin']:+.3f} fit_v1 {cands[0]['mean_fitness_v1']:.3f} J {cands[0]['J']:.3f}")
            print(f"      selected (log #{rep['selected_log_index']}): W {sel['walking_count']} S {sel['survival_count']} feasible {sel['feasible']} "
                  f"med gain {sel['median_diff_m']:+.3f} m (wins {sel['wins']} losses {sel['losses']}) margin {sel['margin']:+.3f} "
                  f"fit_v1 {sel['mean_fitness_v1']:.3f} J {sel['J']:.3f}")
            print("      selected per seed: " + "; ".join(
                f"s{p['seed']} {p['label']} gain {p['diff_m']:+.2f} margin {p['margin']:+.3f} ({p['binding_gate']})" for p in sel["per_seed"]))
            if feas:
                print(f"      feasible margins: max {max(c_['margin'] for c_ in feas):+.3f} median {st.median(c_['margin'] for c_ in feas):+.3f}; "
                      f"binding gates of selected: {collections.Counter(p['binding_gate'] for p in sel['per_seed'])}")
            print(f"      median gain over all candidates: median {st.median(c_['median_diff_m'] for c_ in cands):+.3f} "
                  f"max {max(c_['median_diff_m'] for c_ in cands):+.3f}")
c, t = R
fc, ft = c["harness"]["hook_calls"][0]["prehook_component_fingerprints"], t["harness"]["hook_calls"][0]["prehook_component_fingerprints"]
print("\ncomponent fingerprints equal:", all(fc[k] == ft[k] for k in fc), sorted(fc))
print("same submitted design in both arms:", dh(c["designs"][c["submitted"]]) == dh(t["designs"][t["submitted"]]))
m = json.load(open("do1_l4_r0.jsonl.manifest.json", encoding="utf-8"))
print("manifest:", {k: m.get(k) for k in ("git_commit", "git_dirty", "harness_commit_approved", "runner_version", "python", "numpy",
                                          "mujoco", "platform", "created_utc", "phase")}, "objective", m["objective"]["version"])
