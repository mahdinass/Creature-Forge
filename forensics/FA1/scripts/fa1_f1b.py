"""FA-1 F1b: instance-level recoverability profile, near-miss structure, warm-start displacement, best evidence per episode."""
import collections, csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = lambda x: x in (True, "True")
E = list(csv.DictReader(open(os.path.join(OUT, "episode_index.csv"), encoding="utf-8")))
R = list(csv.DictReader(open(os.path.join(OUT, "repair_decisions.csv"), encoding="utf-8")))
data = L.load_eval()
faulty = {}
for arm, rows in data.items():
    for p, i, r in rows:
        faulty[r["instance_id"]] = (r["check"]["walking"], r["check"]["n"], r["severity"], r["mult"], round(r["strength"], 3))
arms = ["A1e", "A1e6", "A3v5", "A4x"]
by = collections.defaultdict(dict)
for e in E: by[e["instance_id"]][e["arm"]] = e
best_p = collections.defaultdict(float); best16 = collections.defaultdict(lambda: -1)
for x in R:
    k = (x["instance_id"], x["arm"])
    try: best_p[k] = max(best_p[k], float(x["p_full_map"]))
    except ValueError: pass
    try: best16[k] = max(best16[k], int(x["plant_check16"]))
    except ValueError: pass
print("## instance profile: #FULL arms | family sev mult strength | faulty walking/8 | max val walking | best robust16 (v6 arms) | best mappedP | categories")
groups = collections.defaultdict(list)
for iid, d in sorted(by.items(), key=lambda t: (t[1]['A1e']['kind'], -sum(B(t[1][a]['full']) for a in arms))):
    k = sum(B(d[a]["full"]) for a in arms)
    fw = faulty[iid]
    mv = max(float(d[a]["val_walking_frac"]) for a in arms)
    b16 = max(best16[(iid, a)] for a in arms if a != "A1e")
    bp = max(best_p[(iid, a)] for a in arms if a != "A1e")
    cats = collections.Counter(d[a]["verification_category"] for a in arms)
    groups[(d['A1e']['kind'], 'all' if k == 4 else 'none' if k == 0 else 'mixed')].append((fw[0], mv, b16, bp, d['A1e']['failure_family'], fw[2], fw[3]))
    print(f"  {k} {iid:62s} sev{fw[2]} m{fw[3]} s{fw[4]} faulty {fw[0]}/{fw[1]} maxval {mv:.2f} best16 {b16} bestP {bp:.2f} {dict(cats)}")
print("\n## group summaries (kind, outcome group): n, faulty walking>0 count, median maxval, best16>=15 count, bestP>=0.5 count, families, severities, mults")
import numpy as np
for g, lst in sorted(groups.items()):
    print(f"  {g}: n {len(lst)}; faulty walks>0 {sum(x[0] > 0 for x in lst)}; median maxval {np.median([x[1] for x in lst]):.2f}; "
          f"best16>=15 {sum(x[2] >= 15 for x in lst)}; bestP>=0.5 {sum(x[3] >= 0.5 for x in lst)}; fams {dict(collections.Counter(x[4] for x in lst))}; "
          f"sev {dict(collections.Counter(x[5] for x in lst))}; mult {dict(collections.Counter(x[6] for x in lst))}")
print("\n## near-miss validation walking: counts of validation walking seeds (of 24) among non-FULL, by category")
for cat in sorted({e['verification_category'] for e in E}):
    v = [round(float(e['val_walking_frac']) * 24) for e in E if e['verification_category'] == cat]
    print(f"  {cat}: n {len(v)} hist {dict(sorted(collections.Counter(v).items()))}")
print("\n## displacement-only failures: faulty robot walking/8 on robust check, verdict")
for e in E:
    if e['verification_category'] == 'displacement only (walks >=80%)':
        print(f"  {e['arm']:5s} {e['instance_id']:50s} faulty {faulty[e['instance_id']][0]}/8 verdict {e['verdict']} val {e['val_walking_frac']} sub {e['submitted_source']}")
print("\n## faulty-walks>0 vs FULL (all episodes)")
t = collections.Counter((faulty[e['instance_id']][0] > 0, B(e['full'])) for e in E); print(" ", dict(t))
t = collections.Counter((faulty[e['instance_id']][0] > 0, e['verification_category']) for e in E); print(" ", dict(t))
print("\n## FULL by severity and mult (singles, all arms)")
t = collections.defaultdict(lambda: [0, 0])
for e in E:
    if e['kind'] == 'single':
        fw = faulty[e['instance_id']]; t[(fw[2], fw[3])][0] += B(e['full']); t[(fw[2], fw[3])][1] += 1
print(" ", {k: f"{a}/{b}" for k, (a, b) in sorted(t.items())})
print("\n## FULL by family (singles, all arms; episodes)")
t = collections.defaultdict(lambda: [0, 0])
for e in E:
    if e['kind'] == 'single': t[e['failure_family']][0] += B(e['full']); t[e['failure_family']][1] += 1
print(" ", {k: f"{a}/{b}" for k, (a, b) in sorted(t.items())})
print("\n## warm start (twin step) ran vs FULL, LLM arms")
for a in ('A3v5', 'A4x', 'A1e6'):
    t = collections.Counter((B(e['warm_start_ran']), B(e['full'])) for e in E if e['arm'] == a); print(f"  {a}: {dict(t)}")
print("\n## episodes reaching any checked design with mapped P(FULL) >= 0.5 / >= 0.75 (v6 arms), and FULL among them")
for a in ('A1e6', 'A3v5', 'A4x'):
    for kind in ('single', 'composition'):
        ks = [e for e in E if e['arm'] == a and e['kind'] == kind]
        h5 = [e for e in ks if best_p[(e['instance_id'], a)] >= 0.5]; h75 = [e for e in ks if best_p[(e['instance_id'], a)] >= 0.75]
        print(f"  {a} {kind}: P>=0.5 {len(h5)}/{len(ks)} (FULL {sum(B(e['full']) for e in h5)}), P>=0.75 {len(h75)} (FULL {sum(B(e['full']) for e in h75)}), FULL without P>=0.5: {sum(B(e['full']) for e in ks if best_p[(e['instance_id'], a)] < 0.5)}")
print("\n## repair tool (submitted design) success rates per arm (episodes)")
t = collections.defaultdict(lambda: [0, 0])
for e in E:
    k = e['final_repair_tool'] or e['submitted_source']; t[k][0] += B(e['full']); t[k][1] += 1
print(" ", {k: f"{a}/{b}" for k, (a, b) in sorted(t.items(), key=lambda kv: -kv[1][1])})
print("\n## submitted design origin: twin warm start vs plant optimisation vs other, and FULL")
t = collections.defaultdict(lambda: [0, 0])
for e in E:
    s = e['submitted_source']; k = 'twin warm start' if s.startswith('twin:') else 'plant CMA (1st tool)' if s.startswith('repair:') and e['tool_sequence'].split('>').index(f"plant:{s.split(':')[1]}") == ([x.startswith('plant') for x in e['tool_sequence'].split('>')].index(True)) else 'plant CMA (2nd tool)' if s.startswith('repair:') else s
    t[(e['arm'], k)][0] += B(e['full']); t[(e['arm'], k)][1] += 1
for k, (a, b) in sorted(t.items()): print(f"  {k}: FULL {a}/{b}")
