"""FA-1 F5: experience. (a) G-a comparable-support reconstruction from the stored init case store (no model refit);
(b) the 20 paired updating/frozen stream episodes; (c) the experience text Nemotron was shown; (d) A4x vs A3v5 deviation."""
from __future__ import annotations

import collections
import csv
import glob
import json
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CASES = os.path.join(L.REPO, "experiments", "causal_engineer", "dev", "hdb", "ds1", "cases_init.json")


def ga():
    d = json.load(open(CASES, encoding="utf-8"))
    rows = d["cases"]
    print("## F5a  G-a data (cases_init.json):", len(rows), "rows,", len({r["iid"] for r in rows}), "instances,",
          len({r["base"] for r in rows}), "bases")
    by_proc = collections.defaultdict(list)
    for r in rows:
        by_proc[r["procedure"]].append(r["full"])
    print("   FULL rate by procedure:", {k: f"{sum(v)}/{len(v)} = {np.mean(v):.2f}" for k, v in by_proc.items()})
    inst = collections.defaultdict(list)
    for r in rows:
        inst[r["iid"]].append(r)
    comp, eng, rnd, orc, worst = 0, 0.0, 0.0, 0.0, 0.0
    n_disagree, eng_best, eng_tool_only_engine_proc = 0, 0, 0
    proc_of_alt = collections.Counter()
    alt_full_by_proc = collections.defaultdict(list)
    eng_full = []
    per_base = collections.defaultdict(lambda: [0.0, 0.0])
    for iid, rr in inst.items():
        e = [r for r in rr if r["procedure"] == "engine_final"]
        known = collections.defaultdict(list)
        for r in rr:
            known[r["tool"]].append(float(r["full"]))
        if not e or len(known) < 2:
            continue
        comp += 1
        out = {t: float(np.mean(v)) for t, v in known.items()}
        et = e[0]["tool"]
        eng += out[et]
        rnd += float(np.mean(list(out.values())))
        orc += max(out.values())
        worst += min(out.values())
        per_base[e[0]["base"]][0] += out[et]
        per_base[e[0]["base"]][1] += max(out.values())
        if max(out.values()) != min(out.values()):
            n_disagree += 1
        if out[et] == max(out.values()):
            eng_best += 1
        eng_full.append(e[0]["full"])
        for r in rr:
            if r["tool"] != et:
                proc_of_alt[r["procedure"]] += 1
                alt_full_by_proc[r["procedure"]].append(r["full"])
    print(f"   comparable-support instances: {comp} (OFFLINE.md: 194)")
    print(f"   expected FULL: engine {eng:.1f} (OFFLINE.md 89.3) | random among known {rnd:.1f} (70.6) | best known tool (oracle among "
          f"observed, not a ceiling) {orc:.1f} | worst {worst:.1f}")
    print(f"   instances where known tools disagree in outcome: {n_disagree}/{comp}; engine's tool is (one of) the best known: {eng_best}/{comp}")
    print(f"   engine_final FULL on these: {sum(eng_full)}/{len(eng_full)}; alternatives' FULL by procedure: "
          + ", ".join(f"{k} {sum(v)}/{len(v)} = {np.mean(v):.2f}" for k, v in alt_full_by_proc.items()))
    print("   -> the maximum any chooser could gain over the engine on this support is", round(orc - eng, 1),
          "expected FULL; R-head got", round(85.66 - eng, 1))
    print("   bases:", len(per_base), "| instances per base: median", np.median([sum(1 for i in inst if inst[i][0]['base'] == b) for b in per_base]))
    return {"n": comp, "engine": eng, "random": rnd, "oracle_known": orc, "disagree": n_disagree, "eng_best": eng_best}


def stream():
    pairs = collections.defaultdict(dict)
    for f in sorted(glob.glob(os.path.join(L.STREAM_DIR, "r*_*.jsonl"))):
        name = os.path.basename(f)
        rnd, tag = int(name.split("_")[0][1:]), name.split("_")[1]
        recs = L.read_jsonl(f)
        if len(recs) != 1:
            print("   !! unexpected record count", name, len(recs))
        r = recs[0]
        pairs[(rnd, r["instance_id"])][tag] = (r, os.path.relpath(f, L.REPO).replace("\\", "/"))
    order = json.load(open(os.path.join(L.STREAM_DIR, "order.json")))
    print("\n## F5b stream: pairs", len(pairs), "complete", sum(1 for v in pairs.values() if len(v) == 2), "| order entries", len(order))

    def case_text(r):
        calls = (r.get("nemotron") or {}).get("calls") or []
        out = []
        for c in calls:
            m = c.get("messages") or []
            if not m:
                continue
            t = m[-1]["content"]
            i, j = t.find("CASE EVIDENCE"), t.find("MEMORY (dossiers")
            out.append(t[i:j if j > i else i + 1500] if i >= 0 else "")
        return out

    def seq(r):
        return [(s["step"], s.get("tool")) for s in ((L.repair_of(r) or {}).get("log") or [])]

    def ps(r):
        v = [t["action"].get("p_success") for t in r["agent"]["trace"] if t["actor"] == "nemotron"
             and t["action"].get("action") in ("delegate_repair", "conclude", "repair") and isinstance(t["action"].get("p_success"), (int, float))]
        return v[-1] if v else None

    def dev(r):
        return any(t["action"].get("action") in ("repair", "conclude") or t["action"].get("tool_order") or t["action"].get("start_edits")
                   for t in r["agent"]["trace"] if t["actor"] == "nemotron")

    out_rows = []
    for (rnd, iid), v in sorted(pairs.items()):
        u, ur = v["upd"]
        f, fr = v["frz"]
        cu, cf = case_text(u), case_text(f)
        # case-evidence text identical at the first turn? (memory-dependent part only)
        first_same = bool(cu and cf and cu[0] == cf[0])
        rh_u = re.findall(r"submitted with (.*)", cu[0])[0] if cu and "submitted with" in cu[0] else ""
        rh_f = re.findall(r"submitted with (.*)", cf[0])[0] if cf and "submitted with" in cf[0] else ""
        tr_u = re.findall(r"(\d+ earlier investigations.*?verified\.)", cu[0])[0] if cu and "earlier investigations" in cu[0] else ""
        tr_f = re.findall(r"(\d+ earlier investigations.*?verified\.)", cf[0])[0] if cf and "earlier investigations" in cf[0] else ""
        row = {"round": rnd, "instance_id": iid, "robot_base": L.base_of(iid), "kind": "composition" if L.is_comp(u) else "single",
               "full_upd": u["verification"]["status"] == L.FULL, "full_frz": f["verification"]["status"] == L.FULL,
               "status_upd": u["verification"]["status"], "status_frz": f["verification"]["status"],
               "logp_truth_upd": round(math.log(max(u["posterior_mass_on_injected"], 1e-4)), 3),
               "logp_truth_frz": round(math.log(max(f["posterior_mass_on_injected"], 1e-4)), 3),
               "leader_upd": L.st_str(u["map_structure"]), "leader_frz": L.st_str(f["map_structure"]),
               "same_leader": L.st_key(u["map_structure"]) == L.st_key(f["map_structure"]),
               "p_success_upd": ps(u), "p_success_frz": ps(f), "deviated_upd": dev(u), "deviated_frz": dev(f),
               "cases_file_upd": u.get("cases"), "cases_file_frz": f.get("cases"),
               "first_turn_case_evidence_identical": first_same,
               "rhead_line_upd": rh_u, "rhead_line_frz": rh_f, "track_record_upd": tr_u, "track_record_frz": tr_f,
               "n_nemotron_turns_upd": sum(1 for t in u["agent"]["trace"] if t["actor"] == "nemotron"),
               "n_nemotron_turns_frz": sum(1 for t in f["agent"]["trace"] if t["actor"] == "nemotron"),
               "tool_seq_upd": ">".join(f"{a}:{b}" for a, b in seq(u)), "tool_seq_frz": ">".join(f"{a}:{b}" for a, b in seq(f)),
               "same_tool_seq": seq(u) == seq(f), "same_first_tool": (seq(u) or [(None, None)])[0][1] == (seq(f) or [(None, None)])[0][1],
               "submitted_upd": L.design_source(u, u["submitted"]), "submitted_frz": L.design_source(f, f["submitted"]),
               "same_final_vector": [d["vector"] for d in u["designs"] if d["index"] == u["submitted"]] == [d["vector"] for d in f["designs"] if d["index"] == f["submitted"]],
               "plant_upd": u["engine"]["ledger"]["used"], "plant_frz": f["engine"]["ledger"]["used"],
               "twin_upd": u["engine"]["ledger"]["twin"]["used"], "twin_frz": f["engine"]["ledger"]["twin"]["used"],
               "record_upd": ur, "record_frz": fr}
        out_rows.append(row)
    with open(os.path.join(OUT, "stream_pairs.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    for rnd in sorted({r["round"] for r in out_rows}):
        rs = [r for r in out_rows if r["round"] == rnd]
        print(f"   round {rnd}: n {len(rs)} FULL upd {sum(r['full_upd'] for r in rs)} frz {sum(r['full_frz'] for r in rs)} | discordant "
              f"{sum(r['full_upd'] != r['full_frz'] for r in rs)} | same leader {sum(r['same_leader'] for r in rs)} | same tool seq "
              f"{sum(r['same_tool_seq'] for r in rs)} | same first tool {sum(r['same_first_tool'] for r in rs)} | same final design "
              f"{sum(r['same_final_vector'] for r in rs)} | first-turn case evidence text identical {sum(r['first_turn_case_evidence_identical'] for r in rs)} "
              f"| deviated upd/frz {sum(r['deviated_upd'] for r in rs)}/{sum(r['deviated_frz'] for r in rs)}")
    r0 = [r for r in out_rows if r["round"] == 0]
    rl = [r for r in out_rows if r["round"] > 0]
    print(f"   round 0 (identical memory) vs rounds 1-3: tool-seq differs {sum(not r['same_tool_seq'] for r in r0)}/{len(r0)} vs "
          f"{sum(not r['same_tool_seq'] for r in rl)}/{len(rl)}; FULL discordant {sum(r['full_upd'] != r['full_frz'] for r in r0)}/{len(r0)} vs "
          f"{sum(r['full_upd'] != r['full_frz'] for r in rl)}/{len(rl)}; leader differs {sum(not r['same_leader'] for r in r0)}/{len(r0)} vs "
          f"{sum(not r['same_leader'] for r in rl)}/{len(rl)}")
    b = sum(r["full_upd"] and not r["full_frz"] for r in out_rows)
    c = sum(r["full_frz"] and not r["full_upd"] for r in out_rows)
    print(f"   whole stream: FULL upd {sum(r['full_upd'] for r in out_rows)} frz {sum(r['full_frz'] for r in out_rows)}; discordant {b}/{c}; "
          f"exact two-sided p {L.mcnemar_two_sided(b, c):.3f}; bases {len({r['robot_base'] for r in out_rows})}")
    print("   sample R-head lines (upd | frz) and track records:")
    for r in out_rows:
        print(f"    r{r['round']} {r['instance_id'][:48]:48s} FULL {int(r['full_upd'])}/{int(r['full_frz'])} seq {r['tool_seq_upd'][:40]:40s} | {r['tool_seq_frz'][:40]:40s}")
        print(f"        RH upd: {r['rhead_line_upd'][:90]}\n        RH frz: {r['rhead_line_frz'][:90]}\n        TR upd: {r['track_record_upd']}\n        TR frz: {r['track_record_frz']}")
    return out_rows


def deviation_contrast():
    data = L.load_eval()
    dv = {}
    cite = collections.Counter()
    for arm in ("A3v5", "A4x"):
        for p, i, r in data[arm]:
            acts = [t for t in r["agent"]["trace"] if t["actor"] == "nemotron"]
            d = any(t["action"].get("action") in ("repair", "conclude") or t["action"].get("tool_order") or t["action"].get("start_edits") for t in acts)
            dv[(arm, r["instance_id"])] = d
            txt = " ".join(str(t["action"].get("why", "")) + " " + str(t["action"].get("understanding", "")) for t in acts).lower()
            if "track record" in txt:
                cite[(arm, "mentions 'track record'")] += 1
            if re.search(r"overr|deviat", txt) and arm == "A4x":
                cite[(arm, "mentions override/deviation")] += 1
            if re.search(r"case evidence|similar past|learned repair|repair-outcome", txt):
                cite[(arm, "mentions case evidence / repair model")] += 1
    iids = sorted({k[1] for k in dv})
    b = sum(dv[("A3v5", i)] and not dv[("A4x", i)] for i in iids)
    c = sum(dv[("A4x", i)] and not dv[("A3v5", i)] for i in iids)
    print(f"\n## F5d deviation (has_cases definition): A3v5 {sum(dv[('A3v5', i)] for i in iids)}/36, A4x {sum(dv[('A4x', i)] for i in iids)}/36; "
          f"paired discordant A3v5-only {b}, A4x-only {c}, exact two-sided p {L.mcnemar_two_sided(b, c):.3f}")
    print("   reasoning text mentions (episodes):", dict(cite))


if __name__ == "__main__":
    ga()
    stream()
    deviation_contrast()
