"""FA-1: tool-screen rankings for selected families (read-only)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L
fams = sys.argv[1].split(",")
for arm, rows in sorted(L.load_eval().items()):
    for p, i, r in rows:
        if not any(f in r["family"] for f in fams):
            continue
        ev = r["engine"]["events"]
        probe = [e for e in ev if e["kind"] == "tool_screen"]
        cma = [e for e in ev if e["kind"] == "tool_screen_cma"]
        pr = probe[-1]["ranking"] if probe else []
        ff = next(((k, round(x["score"], 2)) for k, x in enumerate(pr) if x["tool"] == "foot_friction"), None)
        rep = L.repair_of(r) or {}
        print(f"{arm:5s} {r['instance_id']:55s} dx={L.st_str(r['map_structure'])}({r['map_mass']:.2f}) inj={L.st_str(r['injected_structure'])} "
              f"FULL={r['verification']['status'][:4]} val={r['verification']['walking_frac']:.2f}")
        print(f"      probe top5 {[(x['tool'], round(x['score'], 2)) for x in pr[:5]]}  foot_friction rank/score {ff}")
        if cma:
            print(f"      cma {[(x['tool'], x.get('cma_walking'), round(x.get('cma_fitness') or 0, 1)) for x in cma[-1]['ranking'][:5]]}")
        print(f"      run {[(s['step'], s.get('tool'), s.get('twin_walking'), s.get('check'), s.get('check16'), (s.get('evidence') or {}).get('disp_median_m'), round((s.get('evidence') or {}).get('p_full') or 0, 2)) for s in rep.get('log', [])]}")
