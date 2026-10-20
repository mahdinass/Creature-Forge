"""FA-1B C/D side finding: experiments that the leading particle never scored are shown to Nemotron as "fits".

Episode.state() builds residuals from `best.seen.get(exp_id) or {}` (belief_engine.py:791); an unscored experiment gives an
empty residual dict, which notebook() renders as "<id>: fits" (has_agent.py:592). This script searches the archived Nemotron
user prompts (record field nemotron.calls[*].messages) of every A3v5/A4x episode for MODEL CHECK lines of experiments that the
final leading particle never scored (no successful "<leader pid>|<exp id>" twin charge in the ledger)."""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L


def main():
    tot = collections.Counter()
    for scope, recs in (("dev-eval-2", L.load_eval()), ("stream", L.load_stream())):
        for path, line, r in recs:
            if not r.get("nemotron"):
                continue
            lines = r["engine"]["ledger"]["twin"]["lines"]
            ok = collections.defaultdict(set)
            for ln in lines:
                tag = (ln.get("detail") or {}).get("tag") or ""
                if "|" in tag and not str(ln["item"]).startswith("refused"):
                    pid, eid = tag.rsplit("|", 1)
                    ok[eid].add(pid)
            exps = [e["id"] for e in r["engine"]["experiments"] if e["kind"] != "weigh"]
            hits = collections.Counter()
            for c in r["nemotron"]["calls"]:
                txt = "\n".join(m.get("content", "") for m in (c.get("messages") or []) if m.get("role") == "user" and isinstance(m.get("content"), str))
                if "MODEL CHECK" not in txt:
                    continue
                sec = txt.split("MODEL CHECK", 1)[1].split("\n\n", 1)[0]
                bel = txt.split("BELIEF", 1)[1].splitlines()[1].split() if "BELIEF" in txt else []
                lead = bel[1] if len(bel) > 1 else None
                for ln in sec.splitlines():
                    s = ln.strip()
                    for eid in exps:
                        if s == f"{eid}: fits" and lead and lead not in ok.get(eid, set()):
                            hits[eid] += 1
            if hits:
                tot[(scope, r["arm"])] += 1
                print(f"{scope} {r['instance_id']} {r['arm']} {path}#L{line + 1}: unscored-by-leader experiments shown as 'fits':",
                      dict(hits))
    print("episodes affected:", dict(tot))


if __name__ == "__main__":
    main()
