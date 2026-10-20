"""FA-1 survey: read-only scan of DS-1 dev-eval records (counts, duplicates, schema vocab)."""
import json, sys, glob, collections, os
root = sys.argv[1]
C = collections.Counter
by_arm = collections.defaultdict(list)
for f in sorted(glob.glob(os.path.join(root, "eval_*.jsonl"))):
    for i, l in enumerate(open(f)):
        r = json.loads(l)
        by_arm[r["arm"]].append((os.path.basename(f), i, r))
ev_kinds, statuses, reasons, actors, actions, steps, conc_by = C(), C(), C(), C(), C(), C(), C()
for arm, rows in by_arm.items():
    ids = [r["instance_id"] for _, _, r in rows]
    print(arm, len(rows), "unique", len(set(ids)), "dups", [k for k, v in C(ids).items() if v > 1])
    for f, i, r in rows:
        for e in r["engine"]["events"]:
            ev_kinds[(arm, e["kind"])] += 1
        statuses[(arm, r["verification"]["status"])] += 1
        for x in r["verification"].get("reasons") or []:
            reasons[x[:60]] += 1
        for t in r["agent"]["trace"]:
            actors[(arm, t["actor"])] += 1
            actions[(arm, t["actor"], t["action"].get("action"))] += 1
        conc_by[(arm, (r["agent"].get("conclusion") or {}).get("by"))] += 1
        rep = r.get("repair") or ((r["agent"].get("conclusion") or {}).get("repair"))
        for s in (rep or {}).get("log", []):
            steps[(arm, s["step"])] += 1
for d, name in [(ev_kinds, "events"), (statuses, "status"), (reasons, "reasons"), (actors, "actors"), (actions, "actions"), (conc_by, "conclusion.by"), (steps, "repair steps")]:
    print("==", name)
    for k, v in sorted(d.items(), key=lambda t: str(t[0])):
        print("  ", k, v)
