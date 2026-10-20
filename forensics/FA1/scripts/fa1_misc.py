"""FA-1 misc: twin->plant transfer (H3), train->robust16->validation attrition (H2/H7), early acceptance precision,
base-cluster bootstrap of paired FULL differences (descriptive only; 14 single-mechanism bases)."""
import collections, csv, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = lambda x: x in (True, "True")
def I(x):
    try: return int(float(x))
    except (TypeError, ValueError): return None
E = list(csv.DictReader(open(os.path.join(OUT, "episode_index.csv"), encoding="utf-8")))
R = list(csv.DictReader(open(os.path.join(OUT, "repair_decisions.csv"), encoding="utf-8")))
print("## H3 twin warm start: twin walking (of 8, ensemble) vs plant robust8 of the same design")
t = collections.Counter()
for x in R:
    if x["step"] == "twin" and I(x["twin_walking_of8"]) is not None and I(x["plant_check8"]) is not None:
        tw, pc = I(x["twin_walking_of8"]), I(x["plant_check8"])
        t[("twin>=7" if tw >= 7 else "twin<7", "plant>=7" if pc >= 7 else "plant 4-6" if pc >= 4 else "plant<=3")] += 1
print(" ", dict(sorted(t.items())))
d = [I(x["twin_walking_of8"]) - I(x["plant_check8"]) for x in R if x["step"] == "twin" and I(x["twin_walking_of8"]) is not None and I(x["plant_check8"]) is not None]
print("  twin minus plant walking (of 8): median", np.median(d), "mean", round(np.mean(d), 2), "share >=3:", round(np.mean([v >= 3 for v in d]), 2), "n", len(d))
print("\n## H2/H7 plant CMA: train walking (of 4) -> plant robust16 -> FULL (submitted designs only, all arms)")
t = collections.defaultdict(lambda: [0, 0])
for x in R:
    if x["step"] == "plant" and B(x["is_submitted"]) and I(x["train_walking_of4"]) is not None and I(x["plant_check16"]) is not None:
        k = (f"train {I(x['train_walking_of4'])}/4", "r16>=15" if I(x["plant_check16"]) >= 15 else "r16 12-14" if I(x["plant_check16"]) >= 12 else "r16<12")
        t[k][0] += B(x["episode_full"]); t[k][1] += 1
for k in sorted(t): print(f"  {k}: FULL {t[k][0]}/{t[k][1]}")
tr4 = [x for x in R if x["step"] == "plant" and I(x["train_walking_of4"]) == 4]
print("  plant steps reaching 4/4 on train seeds:", len(tr4), "of", sum(1 for x in R if x["step"] == "plant" and I(x["train_walking_of4"]) is not None),
      "| of those robust16>=15:", sum(1 for x in tr4 if (I(x["plant_check16"]) or 0) >= 15))
print("\n## early acceptance by the stop map (v6 arms): FULL among accepted")
for a in ("A1e", "A1e6", "A3v5", "A4x"):
    acc = [e for e in E if e["arm"] == a and e["termination"] == "accepted by stop map"]
    print(f"  {a}: accepted {len(acc)}, FULL {sum(B(e['full']) for e in acc)}")
print("\n## base-cluster bootstrap of paired FULL differences, singles (descriptive; 14 bases, 1-4 instances each)")
by = collections.defaultdict(dict)
for e in E:
    if e["kind"] == "single": by[e["instance_id"]][e["arm"]] = (e["robot_base"], B(e["full"]))
bases = sorted({v["A1e6"][0] for v in by.values()})
rng = np.random.default_rng(20261020)
for a, b in (("A4x", "A1e6"), ("A3v5", "A1e6"), ("A1e6", "A1e"), ("A4x", "A3v5")):
    per = collections.defaultdict(list)
    for iid, v in by.items(): per[v[a][0]].append(int(v[a][1]) - int(v[b][1]))
    obs = sum(sum(v) for v in per.values())
    boots = []
    for _ in range(5000):
        s = rng.choice(len(bases), len(bases)); boots.append(sum(sum(per[bases[i]]) for i in s))
    print(f"  {a} - {b}: observed {obs:+d} of 30; 90% base-bootstrap [{np.percentile(boots, 5):+.0f}, {np.percentile(boots, 95):+.0f}]; "
          f"bases contributing a non-zero difference: {sum(1 for v in per.values() if sum(v) != 0)}")
print("\n## same instance, all four arms: outcome concordance (singles + comps)")
inst = collections.defaultdict(list)
for e in E: inst[e["instance_id"]].append(B(e["full"]))
print("  instances with identical outcome in all 4 arms:", sum(1 for v in inst.values() if len(set(v)) == 1), "of", len(inst))
# intraclass-style share of FULL variance explained by instance
y = np.array([B(e["full"]) for e in E], float); g = [e["instance_id"] for e in E]
mu = y.mean(); ss_tot = ((y - mu) ** 2).sum()
ss_b = sum(len(v) * (np.mean(v) - mu) ** 2 for v in inst.values())
print(f"  share of FULL variance between instances (eta^2): {ss_b / ss_tot:.2f}")
arms = collections.defaultdict(list)
for e in E: arms[e["arm"]].append(B(e["full"]))
ss_a = sum(len(v) * (np.mean(v) - mu) ** 2 for v in arms.values())
print(f"  share of FULL variance between arms (eta^2): {ss_a / ss_tot:.3f}")
