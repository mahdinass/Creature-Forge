"""FA-1: compact trace excerpt of one record: python fa1_trace.py <repo-relative path> <line (1-based)>."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L
sys.stdout.reconfigure(encoding="utf-8")
path, line = sys.argv[1], int(sys.argv[2])
r = L.read_jsonl(os.path.join(L.REPO, path))[line - 1]
v = r["verification"]
print(f"== {path}#L{line} | {r['arm']} | {r['instance_id']} | {v['status']} val {v['walking_frac']:.2f} | {' | '.join(v['reasons'])[:200]}")
print(f"   injected {L.st_str(r['injected_structure'])} | leader {L.st_str(r['map_structure'])} ({r['map_mass']:.2f}) | p(inj) {r['posterior_mass_on_injected']:.3f} | unmodelled {r['engine'].get('unmodelled_mass', 0)}")
print(f"   faulty robust check {r['check']['walking']}/{r['check']['n']} | plant {r['engine']['ledger']['used']}/700 twin {r['engine']['ledger']['twin']['used']}/2800 | base foot_friction {r['designs'][0]['body']['foot_friction']:.3f}")
for t in r["agent"]["trace"]:
    a = t["action"]; res = t["result"]
    s = {k: a[k] for k in ("action", "experiment", "tool", "mode", "tool_order", "start_edits", "design", "p_success") if k in a}
    if a.get("hypotheses"): s["hypotheses"] = [str(h)[:80] for h in a["hypotheses"]][:3]
    rr = {k: res[k] for k in ("ok", "eig", "best_eig", "refused", "design", "accepted", "ran", "twin_walking") if k in res}
    if "posterior" in res: rr["post"] = [(L.st_str(x[0]), x[1]) for x in res["posterior"][:3]]
    if "evidence" in res: rr["ev"] = res["evidence"]
    why = (a.get("why") or "")[:220]
    print(f"   [{t['seq']}] {t['actor']}: {json.dumps(s)} -> {json.dumps(rr)[:330]} | plant {t['plant_used']} twin {t['twin_used']}" + (f"\n        why: {why}" if why and t['actor'] == 'nemotron' else ""))
ev = r["engine"]["events"]
for e in ev:
    if e["kind"] in ("tool_screen_cma", "preferred_tools", "tool_screen_unavailable", "composite_expansion", "composite_skipped", "assimilation_skipped", "rescreen_after_assimilation"):
        if e["kind"] == "tool_screen_cma":
            print(f"   {e['kind']}: {[(x['tool'], x.get('cma_walking')) for x in e['ranking'][:5]]}")
        elif e["kind"] == "composite_expansion":
            print(f"   composite_expansion: stat {e['stat']} pairs {e.get('pairs')} fitted {e.get('fitted')} twin {e.get('twin_cost')}")
        else:
            print(f"   {e['kind']}: {json.dumps({k: v for k, v in e.items() if k not in ('seq', 'kind')})[:200]}")
gen = next((e for e in ev if e["kind"] == "generic_screen"), None)
if gen: print(f"   generic screen kept: {gen['kept']}")
rep = L.repair_of(r) or {}
for s in rep.get("log", []):
    e2 = s.get("evidence") or {}
    print(f"   repair {s['step']}:{s.get('tool')} design {s.get('design')} twin {s.get('twin_walking')} check8 {s.get('check')} check16 {s.get('check16')} train {s.get('train_walking')} stress {e2.get('stress4')} disp {e2.get('disp_median_m')} p_full {e2.get('p_full')}")
for a in rep.get("assimilated", []) or []:
    print(f"   assim {a['id']} obs {a['observed_walking']}/{a['n']} pred {a['predicted_walking']} before {[(L.st_str(x[0]), x[1]) for x in a['before']][:3]} after {[(L.st_str(x[0]), x[1]) for x in a['after']][:3]}")
print(f"   submitted {r['submitted']} ({L.design_source(r, r['submitted'])}) concluded by {(r['agent'].get('conclusion') or {}).get('by')}")
