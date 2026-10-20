"""FA-1 F3: compound diagnosis. The 13 G-m init-base compositions (v5 vs v6) and the 6 dev-eval compositions x 4 arms, kept
separate. For each episode: was the true pair enumerable (both true primitives among the top-4 distinct singles at expansion),
enumerated, added within budget, fitted, retained at the end; final mass on truth; leader; unmodelled reserve; FULL."""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def prims_of_pid(pid: str) -> set:
    out = set()
    for part in pid.split("+"):
        head = part.split("(")[0]
        k, t = head.split(":")
        out.add((k, t))
    return out


def analyse(r, cohort, src):
    inj = set(L.st_key(r["injected_structure"]))
    eng = r["engine"]
    ev = eng["events"]
    exps = [e for e in ev if e["kind"] == "composite_expansion"]
    skips = [e for e in ev if e["kind"] == "composite_skipped"]
    enumerated = any(prims_of_pid(p) == inj for e in exps for p in e.get("pairs", []))
    added = any(prims_of_pid(p) == inj for e in exps for p in e.get("added", []))
    fitted = any(prims_of_pid(p) == inj for e in exps for p in e.get("fitted", []))
    # both true primitives present among single-primitive particles kept after the generic screen / at the end
    gen = next((e for e in ev if e["kind"] == "generic_screen"), None)
    kept_singles = {next(iter(prims_of_pid(p))) for p in (gen or {}).get("kept", []) if "+" not in p and p != "nominal"}
    final_structs = {L.st_key(p["structure"]) for p in eng["particles"]}
    retained = tuple(sorted(inj)) in final_structs
    snaps = eng["history"]
    # best rank/mass of the true pair over all snapshots (top-8 structures recorded)
    best_mass, best_rank = 0.0, None
    for h in snaps:
        for i, s in enumerate(h["structures"]):
            if L.st_key(s["structure"]) == tuple(sorted(inj)):
                if s["w"] > best_mass:
                    best_mass, best_rank = s["w"], i + 1
    fin = snaps[-1]["structures"] if snaps else []
    unm_lead = bool(fin) and L.st_key(fin[0]["structure"]) == L.st_key(L.UNM)
    v = L.verification_flags(r["verification"])
    true_single_in_screen = sorted(f"{k}:{t}" for k, t in inj if (k, t) in kept_singles)
    # misfit statistic at each expansion event
    stats = [e.get("stat") for e in exps + skips]
    return {"cohort": cohort, "instance_id": r["instance_id"], "robot_base": L.base_of(r["instance_id"]), "arm": r["arm"],
            "engine": eng.get("version"), "injected": L.st_str(r["injected_structure"]),
            "leading_modelled": L.st_str(r["map_structure"]), "leading_mass": round(r["map_mass"], 4),
            "leader_incl_unmodelled": L.st_str(fin[0]["structure"]) if fin else "", "unmodelled_leads": unm_lead,
            "unmodelled_mass": eng.get("unmodelled_mass", 0.0),
            "p_on_injected_final": round(r["posterior_mass_on_injected"], 4),
            "exact_pair_leads": L.st_key(r["map_structure"]) == tuple(sorted(inj)),
            "shares_primitive": L.shares_primitive(r["map_structure"], r["injected_structure"]),
            "shares_kind": L.shares_kind(r["map_structure"], r["injected_structure"]),
            "true_singles_kept_by_generic_screen": "+".join(true_single_in_screen),
            "n_true_singles_kept": len(true_single_in_screen),
            "misfit_stats": json.dumps(stats), "n_expansions": len(exps), "n_expansion_skipped_budget": len(skips),
            "pairs_enumerated": json.dumps([p for e in exps for p in e.get("pairs", [])]),
            "true_pair_enumerated": enumerated, "true_pair_added": added, "true_pair_fitted": fitted,
            "true_pair_retained_final": retained, "true_pair_best_mass_any_snapshot": round(best_mass, 4),
            "true_pair_best_rank_any_snapshot": best_rank,
            "composite_twin_cost": sum(e.get("twin_cost", 0) for e in exps),
            "plant_used": eng["ledger"]["used"], "twin_used": eng["ledger"]["twin"]["used"],
            "full": v["full"], "verification_category": L.fail_category(v), "val_walking_frac": v["walking_frac"],
            "source": src}


def main():
    rows = []
    v5_path = os.path.join(L.HDB_DIR, "s2DC_exp_A1e.jsonl")
    v5 = {r["instance_id"]: (r, "artifacts/vm/hdb/artifacts/hdb/s2DC_exp_A1e.jsonl#L%d" % (i + 1)) for i, r in enumerate(L.read_jsonl(v5_path))}
    for i, r in enumerate(L.read_jsonl(os.path.join(L.DS1_DIR, "pilot_A1e.c.jsonl"))):
        v5[r["instance_id"]] = (r, "artifacts/vm/ds1/pilot_A1e.c.jsonl#L%d" % (i + 1))
    v6 = {}
    for name in ("gm_A1e6.c.jsonl", "pilot_A1e6.c.jsonl"):
        for i, r in enumerate(L.read_jsonl(os.path.join(L.DS1_DIR, name))):
            if r["arm"] == "A1e6":
                v6[r["instance_id"]] = (r, f"artifacts/vm/ds1/{name}#L{i + 1}")
    paired = sorted(set(v5) & set(v6))
    print("G-m paired compositions:", len(paired), "(v5 records", len(v5), ", v6 records", len(v6), ")")
    for iid in paired:
        rows.append(analyse(v5[iid][0], "G-m (init bases), v5 = Stage-2 A1e", v5[iid][1]))
        rows.append(analyse(v6[iid][0], "G-m (init bases), v6 = A1e6", v6[iid][1]))
    for arm, recs in sorted(L.load_eval().items()):
        for p, i, r in recs:
            if L.is_comp(r):
                rows.append(analyse(r, "dev-eval-2 compositions (transfer bases)", f"{p}#L{i + 1}"))
    keys = list(rows[0])
    with open(os.path.join(OUT, "compound_cases.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    for cohort in sorted({r["cohort"] for r in rows}):
        rs = [r for r in rows if r["cohort"] == cohort]
        print(f"\n## {cohort}: n {len(rs)}")
        for r in rs:
            print(f"  {r['arm']:5s} {r['instance_id'][:62]:62s} inj {r['injected']:45s} lead {r['leading_modelled'][:45]:45s}({r['leading_mass']:.2f}) "
                  f"unm {r['unmodelled_mass']:.2f}{'*' if r['unmodelled_leads'] else ' '} share {int(r['shares_primitive'])}/{int(r['shares_kind'])} "
                  f"trueSingles {r['n_true_singles_kept']} enum {int(r['true_pair_enumerated'])} add {int(r['true_pair_added'])} fit {int(r['true_pair_fitted'])} "
                  f"ret {int(r['true_pair_retained_final'])} bestP {r['true_pair_best_mass_any_snapshot']} pInj {r['p_on_injected_final']} "
                  f"exp {r['n_expansions']}/{r['n_expansion_skipped_budget']} misfit {r['misfit_stats']} FULL {int(r['full'])}")
        for k in ("shares_primitive", "shares_kind", "exact_pair_leads", "unmodelled_leads", "true_pair_enumerated", "true_pair_added",
                  "true_pair_retained_final", "full"):
            by = {}
            for r in rs:
                by.setdefault(r["arm"], []).append(bool(r[k]))
            print(f"   {k}: " + ", ".join(f"{a} {sum(v)}/{len(v)}" for a, v in sorted(by.items())))
        by = {}
        for r in rs:
            by.setdefault(r["arm"], []).append(r["n_true_singles_kept"])
        print("   true singles kept by generic screen (0/1/2): " + ", ".join(f"{a} {[v.count(i) for i in (0, 1, 2)]}" for a, v in sorted(by.items())))


if __name__ == "__main__":
    main()
