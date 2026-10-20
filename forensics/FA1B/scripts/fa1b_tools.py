"""FA-1B Investigation B: repair-tool screening coverage vs. executability (read-only; stored records + copied bounds).

Per episode and tool it separates (belief_engine.py:804-831, 833-854, 862-996; has_agent.py:329-433):
  probe_invalid      all fixed probes of the tool violate guided bounds -> tool absent from the probe ranking
  not_executable     the CMA search interval of the body tool is empty (walk_opt._log_interval) -> no repair possible
  screened_poorly    present in the probe ranking but outside the CMA re-rank top 5, or ranked >= 3rd after it
  budget_cut         ranked 1st/2nd but never optimised (no plant step for it)
  tried              optimised on twin or plant through any path (engine warm start / plant step / Nemotron repair /
                     Nemotron tool preference / fallback order)
Outputs tool_availability.csv (aggregate rows) and prints the per-instance evidence used in the report."""
import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L

EPI = {(r["instance_id"], r["arm"]): r for r in csv.DictReader(open(os.path.join(L.FA1, "episode_index.csv"), encoding="utf-8"))}
TOOLS = list(L.TOOL_PROBES)


def screens(r):
    """Probe screens of one record: [{"seq", "complete", "tools": [...ordered], "cma": [...] or None, "via"}]."""
    out, ev = [], L.events(r)
    for i, e in enumerate(ev):
        if e["kind"] == "tool_screen":
            nxt = ev[i + 1] if i + 1 < len(ev) else None
            cma = [x["tool"] for x in nxt["ranking"]] if nxt and nxt["kind"] == "tool_screen_cma" else None
            out.append({"seq": e["seq"], "complete": True, "tools": [x["tool"] for x in e["ranking"]], "cma": cma,
                        "scores": {x["tool"]: x["score"] for x in e["ranking"]}})
        elif e["kind"] == "tool_screen_cma" and not (i and ev[i - 1]["kind"] == "tool_screen"):
            # screen_tools returned early (twin_walk refused, belief_engine.py:821-822): no tool_screen event, partial list
            out.append({"seq": e["seq"], "complete": False, "tools": [x["tool"] for x in e["ranking"]], "cma": None,
                        "scores": {}})
        elif e["kind"] == "preferred_tools" and not (i and ev[i - 1]["kind"] in ("tool_screen",)):
            out.append({"seq": e["seq"], "complete": False, "tools": list(e["engine_order"]), "cma": None, "scores": {}})
    return out


def tried(r):
    """{tool: set(paths)} optimised through any path."""
    t = collections.defaultdict(set)
    conc = ((r.get("agent") or {}).get("conclusion") or {})
    for s in ((conc.get("repair") or {}).get("log") or []):
        if s.get("tool") and not s.get("refused"):
            t[s["tool"]].add("engine_" + s.get("step", "?"))
    for x in L.trace(r):
        a = x["action"]
        if x["actor"] == "nemotron" and a.get("action") == "repair" and (x["result"] or {}).get("ok"):
            t[a.get("tool")].add("nemotron_repair_" + a.get("mode", "twin"))
    for e in L.events(r, "preferred_tools"):
        for tool in e["prefer"]:
            t[tool].add("nemotron_prefer")
    if L.events(r, "tool_screen_unavailable"):
        t["__fallback__"].add("fallback")
    return t


def requested(r):
    """Tools Nemotron named in repair / delegate_repair (even if refused)."""
    out = set()
    for x in L.trace(r):
        a = x["action"]
        if x["actor"] != "nemotron":
            continue
        if a.get("action") == "repair" and a.get("tool"):
            out.add(a["tool"])
        if a.get("action") == "delegate_repair":
            out |= set(a.get("tool_order") or [])
    return out


def episode_rows(recs, scope):
    rows = []
    for path, line, r in recs:
        iid, arm = r["instance_id"], r["arm"]
        body0 = r["designs"][0]["body"]
        scr = screens(r)
        complete = [s for s in scr if s["complete"]]
        first = complete[0] if complete else (scr[0] if scr else None)
        tr, req = tried(r), requested(r)
        e = EPI.get((iid, arm), {})
        for tool in TOOLS:
            pv = [L.body_probe_valid(body0, c) for c in L.TOOL_PROBES[tool]]
            recon_invalid = (all(v is False for v in pv)) if all(v is not None for v in pv) else None
            iv = L.cma_interval(body0, tool) if tool in L.BODY_TOOLS else ("ctrl",)
            in_probe = (tool in first["tools"]) if first else None
            pr = first["tools"].index(tool) + 1 if first and tool in first["tools"] else None
            cr = (first["cma"].index(tool) + 1) if first and first["cma"] and tool in first["cma"] else None
            if not first:
                mech = "no_screen_record"
            elif not first["complete"]:
                mech = "screen_truncated_by_twin_budget"
            elif not in_probe:
                mech = "probe_invalid" if recon_invalid in (True, None) else "absent_unexplained"
            elif first["cma"] is not None and cr is None:
                mech = "screened_not_cma_reranked(rank>5)"
            elif (cr or pr) > 2:
                mech = "screened_ranked_below_2"
            else:
                mech = "ranked_top2"
            used = sorted(tr.get(tool, set()))
            rows.append({
                "scope": scope, "instance_id": iid, "robot_base": L.base_of(iid), "arm": arm, "family": r["family"],
                "tool": tool, "base_param": {t: body0.get(L.BODY_TOOLS[t][0]) for t in L.BODY_TOOLS}.get(tool),
                "probe_valid_reconstructed": "/".join("na" if v is None else str(v)[0] for v in pv),
                "all_probes_invalid_reconstructed": recon_invalid,
                "cma_interval": None if iv is None else ("ctrl" if iv == ("ctrl",) else f"x{iv[0]}-x{iv[1]}"),
                "cma_executable": iv is not None, "first_screen_complete": first["complete"] if first else None,
                "n_screens": len(scr), "in_first_probe_ranking": in_probe, "probe_rank": pr, "cma_rank": cr,
                "mechanism_first_screen": mech, "optimised_via": ";".join(used), "nemotron_requested": tool in req,
                "fallback_used": bool(tr.get("__fallback__")), "leader_pre_repair": e.get("leader_pre_repair"),
                "final_repair_tool": e.get("final_repair_tool"), "full": e.get("full") == "True" if e else
                ((r.get("verification") or {}).get("status") == L.FULL),
                "category": e.get("verification_category"), "raw_record": f"{path}#L{line + 1}"})
    return rows


def aggregate(rows, scope, tools=None, by_family=False):
    out = []
    keyf = (lambda x: (x["tool"], x["leader_pre_repair"] or "?")) if by_family else (lambda x: (x["tool"], "all"))
    g = collections.defaultdict(list)
    for x in rows:
        if tools is None or x["tool"] in tools:
            g[keyf(x)].append(x)
    for (tool, fam), xs in sorted(g.items()):
        scr = [x for x in xs if x["mechanism_first_screen"] not in ("no_screen_record",)]
        comp = [x for x in scr if x["first_screen_complete"]]
        absent = [x for x in comp if x["mechanism_first_screen"] in ("probe_invalid", "absent_unexplained")]
        exe_abs = [x for x in absent if x["cma_executable"]]
        opt_abs = [x for x in absent if x["optimised_via"]]
        req_abs = [x for x in absent if x["nemotron_requested"]]
        pres = [x for x in comp if x not in absent]
        out.append({
            "scope": scope, "row_type": "tool_x_leading_diagnosis" if by_family else "tool", "tool": tool,
            "leading_diagnosis_pre_repair": fam, "arm_episodes": len(xs), "arm_episodes_with_screen": len(scr),
            "with_complete_probe_screen": len(comp), "truncated_screen(twin_budget)": len(scr) - len(comp),
            "absent_all_probes_invalid": len(absent),
            "absent_unique_instances": len({x["instance_id"] for x in absent}),
            "absent_unique_bases": len({x["robot_base"] for x in absent}),
            "absent_but_cma_executable": len(exe_abs),
            "absent_cma_max_up_factor_range": (lambda v: f"{min(v):.2f}-{max(v):.2f}" if v else "")(
                [float(x["cma_interval"].split("-x")[1]) for x in exe_abs if x["cma_interval"] not in (None, "ctrl")]),
            "absent_yet_optimised_other_path": len(opt_abs),
            "absent_paths": ";".join(sorted({p for x in opt_abs for p in x["optimised_via"].split(";")})),
            "absent_nemotron_requested": len(req_abs),
            "absent_full": sum(x["full"] for x in absent), "absent_not_full": sum(not x["full"] for x in absent),
            "present_episodes": len(pres), "present_ranked_top2": sum(x["mechanism_first_screen"] == "ranked_top2" for x in pres),
            "present_optimised": sum(bool(x["optimised_via"]) for x in pres),
            "present_full": sum(x["full"] for x in pres), "present_not_full": sum(not x["full"] for x in pres),
            "reconstruction_mismatch": sum(1 for x in comp if x["all_probes_invalid_reconstructed"] is not None and
                                           x["all_probes_invalid_reconstructed"] != (x in absent))})
    return out


def main():
    ev_rows = episode_rows(L.load_eval(), "dev-eval-2")
    st_rows = episode_rows(L.load_stream(), "stream")
    agg = aggregate(ev_rows, "dev-eval-2") + aggregate(st_rows, "stream") + \
        aggregate(ev_rows, "dev-eval-2", tools=("foot_friction", "torque_limit", "foot_length"), by_family=True)
    with open(os.path.join(L.OUT, "tool_availability.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(agg[0]))
        w.writeheader()
        w.writerows(agg)
    print("episode rows", len(ev_rows), "stream rows", len(st_rows))
    print("mechanism counts (dev-eval-2):", collections.Counter((x["tool"], x["mechanism_first_screen"]) for x in ev_rows
                                                                if x["tool"] in ("foot_friction", "torque_limit", "foot_length")))
    print("truncated/missing screens:", sorted({(x["instance_id"], x["arm"], x["mechanism_first_screen"]) for x in ev_rows + st_rows
                                               if x["mechanism_first_screen"] in ("screen_truncated_by_twin_budget", "no_screen_record")}))
    print("absent_unexplained:", sorted({(x["instance_id"], x["arm"], x["tool"]) for x in ev_rows + st_rows
                                        if x["mechanism_first_screen"] == "absent_unexplained"}))
    for scope, rows in (("dev", ev_rows), ("stream", st_rows)):
        print(f"\n## {scope}: low_ground_friction family episodes, foot_friction")
        for x in rows:
            if "low_ground_friction" in x["family"] and x["tool"] == "foot_friction":
                print(" ", x["instance_id"], x["arm"], "f=", round(x["base_param"], 3), x["mechanism_first_screen"], "cma", x["cma_interval"],
                      "probe_rank", x["probe_rank"], "cma_rank", x["cma_rank"], "via", x["optimised_via"] or "-",
                      "req", x["nemotron_requested"], "lead", x["leader_pre_repair"], "full", x["full"], x["category"])
    print("\n## Nemotron-requested tools absent from the first probe ranking (any tool)")
    for x in ev_rows + st_rows:
        if x["nemotron_requested"] and x["in_first_probe_ranking"] is False:
            print(" ", x["scope"], x["instance_id"], x["arm"], x["tool"], "via", x["optimised_via"], "full", x["full"])
    print("\n## tools optimised that were NOT in the first probe ranking")
    for x in ev_rows + st_rows:
        if x["optimised_via"] and x["in_first_probe_ranking"] is False:
            print(" ", x["scope"], x["instance_id"], x["arm"], x["tool"], x["optimised_via"], "full", x["full"])


if __name__ == "__main__":
    main()
