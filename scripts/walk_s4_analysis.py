"""S4a analysis (pre-declared in protocol_s4a.json "analysis"; descriptive; run ONCE after every unit completed).

    python scripts/walk_s4_analysis.py <shard*.jsonl ...> [--out summary.json]

Reports: FULL/PARTIAL/NOT per arm (24 creatures); per-creature table; G4 (ai_iter >= max(fix15, generic, randmech) + 3);
capability 1 (ai_iter vs ai_1shot paired; revision metric: share of revised mechanisms whose probe improved on the mechanism
they revise vs share of new proposals that improved over the start); mechanism analysis (targets, legs, signals, swing-hip
d/v laws, near-zero fitted gains, validity); budget use; AI cost.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

FULL = "FULL_RECOVERY"
NON_AI = ("fix15", "generic", "randmech")


def load(paths):
    return [json.loads(l) for p in paths for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def mech_probes(rec):
    """The pipeline's mechanism-probe records (key probe_id; revises at top level; feedback fields delta_*, all_gains_near_zero)."""
    return [{**mp, "id": mp.get("probe_id")} for mp in (rec.get("pipeline", {}).get("mechanism_probes") or [])]


def improved(mp, base=(0, 0.0)):
    return (mp.get("delta_walking") or 0, mp.get("delta_mean_fitness") or 0.0) > base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    recs = load(a.files)
    creatures = sorted({r["creature"] for r in recs})
    methods = list(dict.fromkeys(r["method"] for r in recs))
    by = {(r["creature"], r["method"]): r for r in recs}
    errs = [r["unit"] for r in recs if r.get("status") == "UNIT_ERROR"]
    acct = [r["unit"] for r in recs if r.get("pipeline") and (r["pipeline"]["used"] != sum(l["n"] for l in r["pipeline"]["budget_lines"])
                                                              or r["pipeline"]["used"] > r["budget"])]
    print(f"{len(recs)} units, {len(creatures)} creatures, methods {methods}; unit errors {errs}; accounting violations {acct}")
    full = {}
    print("\n| method | FULL | PARTIAL | NOT | other | mean validation walking | mean budget used |")
    print("|---|---|---|---|---|---|---|")
    for m in methods:
        sts = [by[(c, m)]["status"] if (c, m) in by else "MISSING" for c in creatures]
        full[m] = sts.count(FULL)
        ws = [by[(c, m)]["assessment"]["validation"]["walking_frac"] for c in creatures if (c, m) in by and by[(c, m)].get("assessment")]
        us = [by[(c, m)]["pipeline"]["used"] / by[(c, m)]["budget"] for c in creatures if (c, m) in by and by[(c, m)].get("pipeline")]
        print(f"| {m} | {full[m]} | {sts.count('PARTIAL_IMPROVEMENT')} | {sts.count('NOT_RECOVERED')} | "
              f"{len(sts) - full[m] - sts.count('PARTIAL_IMPROVEMENT') - sts.count('NOT_RECOVERED')} | "
              f"{sum(ws) / max(1, len(ws)):.2f} | {sum(us) / max(1, len(us)):.2f} |")
    print("\n| creature | " + " | ".join(methods) + " |")
    print("|---|" + "---|" * len(methods))
    for c in creatures:
        cells = []
        for m in methods:
            r = by.get((c, m))
            cells.append("-" if not r else (f"{r['status'][:4]} {r['assessment']['validation']['walking_frac']:.2f}" if r.get("assessment") else r["status"][:6]))
        print(f"| {c[-4:]} | " + " | ".join(cells) + " |")
    best_non_ai = max(full.get(m, 0) for m in NON_AI)
    g4 = full.get("ai_iter", 0) >= best_non_ai + 3
    print(f"\nG4: ai_iter {full.get('ai_iter')} vs best non-AI structure arm {best_non_ai} "
          f"({ {m: full.get(m) for m in NON_AI} }) -> {'PASS' if g4 else 'FAIL'} (needs +3); expert reference {full.get('expert')}")
    # capability 1
    if "ai_iter" in methods and "ai_1shot" in methods:
        it_only = sum(1 for c in creatures if by.get((c, "ai_iter"), {}).get("status") == FULL and by.get((c, "ai_1shot"), {}).get("status") != FULL)
        os_only = sum(1 for c in creatures if by.get((c, "ai_1shot"), {}).get("status") == FULL and by.get((c, "ai_iter"), {}).get("status") != FULL)
        print(f"capability 1, paired: ai_iter-only {it_only}, ai_1shot-only {os_only}")
    for m in ("ai_iter", "ai_1shot"):
        new_imp = new_n = rev_imp = rev_n = 0
        rounds_used = []
        stopped = 0
        for c in creatures:
            r = by.get((c, m))
            if not r or not r.get("pipeline"):
                continue
            probes = {p.get("id"): p for p in mech_probes(r)}
            rounds_used.append(len(r["pipeline"].get("rounds", [])))
            stopped += r["pipeline"].get("stopped_by") == "director_stop"
            for pid, p in probes.items():
                if p.get("status") != "ok":
                    continue
                rv = p.get("revises")
                if rv and rv in probes and probes[rv].get("status") == "ok":
                    rev_n += 1
                    rev_imp += (p.get("delta_walking") or 0, p.get("delta_mean_fitness") or 0.0) > \
                               (probes[rv].get("delta_walking") or 0, probes[rv].get("delta_mean_fitness") or 0.0)
                else:
                    new_n += 1
                    new_imp += improved(p)
        print(f"{m}: mechanism probes ok: new {new_n} (improved over start {new_imp}), revisions {rev_n} (improved over the revised "
              f"one {rev_imp}); mean rounds {sum(rounds_used) / max(1, len(rounds_used)):.2f}; pipelines with a stop decision {stopped}")
    # mechanism analysis for AI arms
    for m in ("ai_iter", "ai_1shot", "randmech"):
        tg, lg, sig, fp_like, near0, n = Counter(), Counter(), Counter(), 0, 0, 0
        for c in creatures:
            r = by.get((c, m))
            if not r:
                continue
            for p in mech_probes(r):
                mech = p.get("mechanism") or {}
                if not mech:
                    continue
                n += 1
                tg[mech.get("target")] += 1
                lg[mech.get("leg")] += 1
                names = set(re.findall(r"[A-Za-z_]+", " ".join(mech.get("terms", []))))
                for s in ("d", "v", "pitch", "pitch_rate", "phase", "h", "loaded", "swing", "stance", "hip", "knee", "ankle", "t"):
                    if s in names:
                        sig[s] += 1
                fp_like += (mech.get("target") == "hip" and mech.get("leg") in ("swing", "both") and bool({"d", "v"} & names))
                near0 += bool(p.get("all_gains_near_zero"))
        if n:
            print(f"{m}: {n} mechanisms probed; targets {dict(tg)}; legs {dict(lg)}; signals {dict(sig)}; "
                  f"swing/both-hip laws on d or v {fp_like}; all gains near zero {near0}")
    ai = [by[(c, m)] for c in creatures for m in ("ai_iter", "ai_1shot") if (c, m) in by and by[(c, m)].get("director_record")]
    if ai:
        cost = sum(r["director_record"].get("cost_usd") or 0 for r in ai)
        st = Counter(d["status"] for r in ai for d in r["director_record"]["decisions"])
        print(f"AI decisions {dict(st)}; cost ${cost:.3f}; calls {sum(len(r['director_record']['calls']) for r in ai)}")
    if a.out:
        Path(a.out).write_text(json.dumps({"full": full, "g4": g4, "best_non_ai": best_non_ai, "unit_errors": errs,
                                           "accounting_violations": acct}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
