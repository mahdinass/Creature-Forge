"""FA-1B Investigation C: posterior consistency after twin-budget exhaustion (read-only, from stored twin ledgers).

belief_engine._register (L631-636) appends experiment E, then updates the alive particles in dict order; _update_particle
(L543-553) recomputes loglik over ALL experiments from the per-experiment cache `seen`, so at registration each alive particle
is charged exactly one twin_observe tagged "<pid>|E" (L512-513). A refused call is ledgered "refused:twin_observe" with the same
tag (hdb_workbench.py:198-203) and _register stops (`break`) without rolling back. Hence the REGISTRATION BLOCK of E is the run
of consecutive successful "<pid>|E" lines ending at the refusal: those particles now include E; the refused particle and any
later ones in dict order do not. A particle in the final record without any successful "<pid>|E" charge never included E.
Each seed's log-density term is at most log(1 - SEED_OUTLIER) = -0.105 (L207-215): a particle missing E is never penalised for E,
so the bias always favours stale particles, by -(their E term)/T >= 0.105 * n_seeds / T nats (T = 6 in DS-1).
Outputs partial_update_cases.csv (one row per experiment whose registration hit a refusal)."""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L

EPI = {(r["instance_id"], r["arm"]): r for r in csv.DictReader(open(os.path.join(L.FA1, "episode_index.csv"), encoding="utf-8"))}
SRC = ("belief_engine.py:631-636 _register (no rollback); 543-553 _update_particle; 502-518 _predict (cache per id); "
       "623-628 prune; 349-366 posterior; hdb_workbench.py:198-212 refusal")


def tag_of(ln):
    t = (ln.get("detail") or {}).get("tag") or ""
    return t.rsplit("|", 1) if "|" in t else (None, None)


def analyse(scope, path, line, r):
    lines = r["engine"]["ledger"]["twin"]["lines"]
    exps = [e["id"] for e in r["engine"]["experiments"]]
    nseeds = {e["id"]: len(e.get("seeds") or e.get("features") or []) for e in r["engine"]["experiments"]}
    final = r["engine"]["particles"]
    charged = collections.defaultdict(set)              # experiment id -> pids with a successful charge
    for ln in lines:
        pid, eid = tag_of(ln)
        if eid and not str(ln["item"]).startswith("refused"):
            charged[eid].add(pid)
    rows = []
    done = set()
    for k, ln in enumerate(lines):
        if not str(ln["item"]).startswith("refused:twin_observe"):
            continue
        pid, eid = tag_of(ln)
        if eid not in exps or eid in done:
            continue
        # registration block: consecutive successful "<x>|eid" lines right before the refusal, distinct pids
        block, j = [], k - 1
        while j >= 0:
            p2, e2 = tag_of(lines[j])
            if e2 != eid or str(lines[j]["item"]).startswith("refused") or p2 in block:
                break
            block.append(p2)
            j -= 1
        # a refusal inside add_particles shows the earlier experiments of a NEW particle charged just before it; a registration
        # refusal is preceded by other particles' charges for the same eid (or by a non-eid line when nobody got through)
        prev_tags = [tag_of(lines[x]) for x in range(max(0, k - 3), k)]
        if any(p2 == pid and e2 != eid for p2, e2 in prev_tags):
            continue   # new particle (add_particles): not a registration
        if eid != exps[-1] and exps.index(eid) == 0:
            continue
        done.add(eid)
        cum = ln.get("cumulative") or 0
        tr = L.trace(r)
        turn = next((t for t in tr if t["twin_used"] >= cum), None)
        later = [t for t in tr if turn and t["seq"] > turn["seq"]]
        with_e = charged[eid]
        f_with = [p["pid"] for p in final if p["pid"] in with_e]
        f_without = [p["pid"] for p in final if p["pid"] not in with_e]
        # posterior snapshots after the refusal: mass (top-10 pids) on particles with vs without E
        hist = r["engine"]["history"]
        idx = next((i for i, h in enumerate(hist) if h["twin_used"] >= cum), None)
        snaps = []
        for h in (hist[idx:] if idx is not None else []):
            mw = sum(x["w"] for x in h["top"] if x["pid"] in with_e)
            mo = sum(x["w"] for x in h["top"] if x["pid"] not in with_e)
            lead = h["top"][0]["pid"] if h["top"] else None
            snaps.append(f"{h['label']}: with_E {mw:.3f} / without_E {mo:.3f}; leader {'has' if lead in with_e else 'LACKS'} E")
        stale_mass = [float(s.split("without_E ")[1].split(";")[0]) for s in snaps]
        if not block:
            cat = "benign/consistent: E registered but no particle scored it (plant data discarded by inference)"
        elif f_with and f_without:
            cat = "confirmed posterior inconsistency persisting to the final record"
        elif any(m > 0.0 for m in stale_mass if True) and any("without_E 0.000" not in s for s in snaps):
            cat = "confirmed transient inconsistency (stale particles carried posterior mass in a snapshot)"
        else:
            cat = "partial update, stale particles pruned before any snapshot (reachable defect, no recorded effect)"
        e = EPI.get((r["instance_id"], r["arm"]), {})
        rows.append({
            "scope": scope, "instance_id": r["instance_id"], "arm": r["arm"], "family": r["family"],
            "experiment": eid, "experiment_seeds": nseeds.get(eid), "experiment_index": exps.index(eid),
            "n_experiments_total": len(exps), "refused_pid": pid, "twin_remaining_at_refusal": r["engine"]["ledger"]["twin"]["total"] - cum,
            "updated_at_registration": len(block), "alive_at_registration_lower_bound": len(block) + 1,
            "stale_bias_lower_bound_nats_T6": round(0.105 * (nseeds.get(eid) or 0) / 6.0, 3),
            "final_particles": len(final), "final_with_E": len(f_with), "final_without_E": len(f_without),
            "final_leader_has_E": (final[0]["pid"] in with_e) if final else None, "final_leader": final[0]["pid"] if final else None,
            "max_stale_mass_in_later_snapshots": round(max(stale_mass), 4) if stale_mass else None,
            "snapshots_after": " | ".join(snaps),
            "actor_action_at_refusal": f"{turn['actor']}:{turn['action']['action']}" if turn else None,
            "turn_at_refusal": turn["turn"] if turn else None,
            "later_actions": ";".join(f"{t['actor']}:{t['action']['action']}" for t in later),
            "later_nemotron_turns": sum(1 for t in later if t["actor"] == "nemotron"),
            "twin_screen_after": "unavailable/truncated" if (L.events(r, "tool_screen_unavailable") or not L.events(r, "tool_screen")) else "ran",
            "termination": e.get("termination"), "final_tool": e.get("final_repair_tool"), "full": e.get("full"),
            "outcome_category": e.get("verification_category"), "leading_final": e.get("leading_diagnosis"),
            "leading_final_mass": e.get("leading_mass"), "true_structure_match": e.get("true_structure_match"),
            "classification": cat, "source_locations": SRC, "raw_record": f"{path}#L{line + 1}"})
    return rows


def main():
    rows, n_with = [], collections.Counter()
    for scope, recs in (("dev-eval-2", L.load_eval()), ("stream", L.load_stream())):
        for path, line, r in recs:
            for ev in L.events(r, "twin_budget_exhausted"):
                n_with[(scope, r["arm"], ev["where"])] += 1
            rows += analyse(scope, path, line, r)
    with open(os.path.join(L.OUT, "partial_update_cases.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("twin_budget_exhausted events:", dict(n_with))
    print("episodes with a registration refusal:", len({(x["instance_id"], x["arm"]) for x in rows}), "| rows:", len(rows))
    for x in rows:
        print("\n", x["instance_id"], x["arm"], x["experiment"], "| updated", x["updated_at_registration"], "| final with/without E",
              x["final_with_E"], x["final_without_E"], "| leader has E", x["final_leader_has_E"], "| max stale mass",
              x["max_stale_mass_in_later_snapshots"], "|", x["actor_action_at_refusal"], "->", x["later_actions"], "| full", x["full"],
              "| lead", x["leading_final"], x["leading_final_mass"], "| match", x["true_structure_match"])
        print("   ", x["classification"])
        print("   ", x["snapshots_after"][:600])


if __name__ == "__main__":
    main()
