"""Read-only: reproduce the DS-1 same-label comparability counts from the committed P0 evidence CSVs (e3caf81).
Usage: python -I ds1_comparability_check.py <cf-experience worktree>"""
import collections as C, csv, json, sys

E = sys.argv[1].rstrip("/\\") + "/experiments/causal_engineer/dev/experience_p0/evidence/"
load = lambda f: list(csv.DictReader(open(E + f, encoding="utf-8")))
rows, cand, sp = load("ds1_cases_init_rows_with_sources.csv"), load("ds1_same_label_candidates.csv"), load("p0_level_SP_rows.csv")
out = {}
keys = {(c["iid"], c["ds1_label"]) for c in cand}
cands = {c["iid"] for c in cand}
lab = C.defaultdict(dict)
for c in cand:
    lab[c["iid"]][c["ds1_label"]] = c["full_rates_differ"] == "True"
d21 = {i for i in lab if any(lab[i].values())}
sub = [r for r in rows if (r["iid"], r["procedure"]) in keys]
out["rows/instances/bases"] = [len(rows), len({r["iid"] for r in rows}), len({r["base"] for r in rows})]
out["candidate groups/instances/bases"] = [len(cand), len(cands), len({c["base"] for c in cand})]
out["differing instances"] = len(d21)
out["differing by label"] = {"+".join(k): v for k, v in C.Counter(tuple(sorted(l for l, d in lab[i].items() if d)) for i in d21).items()}


def groups(key, filt):
    g = C.defaultdict(lambda: C.defaultdict(list))
    for r in sub:
        if filt(r):
            g[tuple(r[k] for k in key)][r["tool"]].append(r["full"] == "True")
    multi = [k for k, t in g.items() if len(t) >= 2]
    diff = [k for k in multi if len({sum(v) / len(v) for v in g[k].values()}) > 1]
    return sorted({k[0] for k in multi}), sorted({k[0] for k in diff})


m18, d2 = groups(("iid", "procedure", "engine"), lambda r: r["engine"] != "")
out["two tools under one procedure label and recorded engine version"] = [len(m18), len({i.split(':')[0] for i in m18})]
out["... with differing FULL"] = d2
eng_files = {r["src_file"] for r in rows if r["engine"]}
per_arm = C.Counter((r["iid"], r["src_file"]) for r in rows if r["src_file"] in eng_files)
out["max rows per (instance, engine-arm file)"] = max(per_arm.values())
m_st, d_st = groups(("iid", "src_file"), lambda r: r["src_file"].endswith("stopcal.jsonl"))
out["stopcal.jsonl (one file, engine not recorded): instances with >=2 tools / differing"] = [len(m_st), len(d_st)]
P = C.defaultdict(set)
for r in sp:
    if r["level"] == "P":
        P[r["iid"]].add((r["file"].split("/")[-1], r["arm"], r["engine"]))
ov = sorted(cands & set(P))
out["70 overlapping expanded-corpus level P"] = len(ov)
extra = [i for i in ov if i not in m18]
out["overlap reached only through rows outside DS-1 candidate rows"] = {
    i: sorted({f for f, a, e in P[i] if not f.startswith(("vs4_", "vs2_"))}) for i in extra}
out["21 differing that overlap level P"] = len(d21 & set(P))
eo = sorted(i for i in d21 if lab[i].get("engine_old"))
out["engine_old-differing instances / persisting within one engine version"] = [len(eo), len([i for i in eo if i in d2])]
arms = C.defaultdict(set)
for r in sp:
    if r["level"] == "P":
        arms[(r["bench"], r["iid"], r["engine"])].add(r["arm"])
stop_only = {"A1", "A1c", "A1f", "A1c5", "A1e", "A1e6"}
out["level-P instances: stop-rule variants of one engine arm only / pooling other harnesses or arms"] = [
    sum(a <= stop_only for a in arms.values()), sum(not a <= stop_only for a in arms.values())]
print(json.dumps(out, indent=1))
