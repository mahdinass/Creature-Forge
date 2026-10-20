"""FA-1B side finding: Nemotron delegate_repair carrying `design: 0` (optional schema field, has_agent.py:777) makes
LabSession.delegate_repair select the faulty design 0 before robust_repair (has_agent.py:419-420), discarding any better design
the session had produced. Counts how often that happened while a non-zero design with plant evidence existed."""
import collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L
c = collections.Counter()
rows = []
for scope, recs in (("dev-eval-2", L.load_eval()), ("stream", L.load_stream())):
    for p, i, r in recs:
        if r["arm"] not in ("A3v5", "A4x"):
            continue
        ev = (r.get("agent") or {}).get("evidence") or {}
        for t in L.trace(r):
            a = t["action"]
            if t["actor"] != "nemotron" or a.get("action") != "delegate_repair":
                continue
            c[(scope, "delegate_repair")] += 1
            if a.get("design") == 0:
                c[(scope, "design=0")] += 1
                better = {k: v for k, v in ev.items() if k != "0" and (v.get("robust16") or v.get("robust8"))}
                if better:
                    c[(scope, "design=0 while a checked non-zero design existed")] += 1
                    rows.append((scope, r["instance_id"], r["arm"], {k: (v.get("robust16"), v.get("robust8"), v.get("p_full")) for k, v in better.items()},
                                 r["submitted"], r["verification"]["status"]))
print(dict(c))
for x in rows:
    print(" ", x)
