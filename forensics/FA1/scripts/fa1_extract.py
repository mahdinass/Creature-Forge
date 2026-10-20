"""FA-1 extraction: episode_index.csv, repair_decisions.csv, feedback_events.csv from the DS-1 dev-eval-2 records.
Read-only; writes only into the forensic output directory."""
from __future__ import annotations

import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def nemotron_summary(r):
    tr = r["agent"]["trace"]
    acts = [t for t in tr if t["actor"] == "nemotron"]
    kinds = {}
    for t in acts:
        a = t["action"].get("action")
        kinds[a] = kinds.get(a, 0) + 1
    tool_orders = [t["action"].get("tool_order") for t in acts if t["action"].get("tool_order")]
    start_edits = [t["action"].get("start_edits") for t in acts if t["action"].get("start_edits")]
    deviated = any(t["action"].get("action") in ("repair", "conclude") or t["action"].get("tool_order")
                   or t["action"].get("start_edits") for t in acts)          # has_cases.agent_decision definition
    ps = [t["action"].get("p_success") for t in acts if t["action"].get("action") in ("delegate_repair", "conclude", "repair")
          and isinstance(t["action"].get("p_success"), (int, float))]
    refused = sum(1 for t in acts if t["result"].get("ok") is False or (t["result"].get("refused")))
    hyps = sum(len(t["action"].get("hypotheses") or []) for t in acts)
    return {"n_nemotron_actions": len(acts), "action_counts": json.dumps(kinds, sort_keys=True),
            "n_fallback": sum(1 for t in tr if t["actor"] == "fallback"), "deviated_hascases": deviated if acts else None,
            "tool_order": json.dumps(tool_orders[-1]) if tool_orders else "", "start_edits": json.dumps(start_edits) if start_edits else "",
            "n_direct_repair": kinds.get("repair", 0), "n_conclude": kinds.get("conclude", 0),
            "n_nemo_experiments": kinds.get("experiment", 0), "n_delegate_diagnosis": kinds.get("delegate_diagnosis", 0),
            "n_hypotheses_proposed": hyps, "n_refused": refused, "p_success": ps[-1] if ps else None}


def phase_costs(r):
    """Plant/twin spent before the repair phase vs in it, from the agent trace."""
    diag_p = diag_t = rep_p = rep_t = 0
    in_rep = False
    for t in r["agent"]["trace"]:
        a = t["action"].get("action")
        if a in ("delegate_repair", "repair", "check", "conclude", "screen_tools"):
            in_rep = True
        if in_rep:
            rep_p += t["plant_cost"]
            rep_t += t["twin_cost"]
        else:
            diag_p += t["plant_cost"]
            diag_t += t["twin_cost"]
    return diag_p, diag_t, rep_p, rep_t


def main():
    data = L.load_eval()
    ep_rows, rep_rows, fb_rows = [], [], []
    for arm in sorted(data):
        for path, line, r in data[arm]:
            iid = r["instance_id"]
            eng = r["engine"]
            led = eng["ledger"]
            fl = L.verification_flags(r["verification"])
            rep = L.repair_of(r) or {}
            log = rep.get("log") or []
            conc = r["agent"].get("conclusion") or {}
            sub = r["submitted"]
            sub_src = L.design_source(r, sub)
            pre = L.pre_repair_snapshot(r) or {}
            pre_st = pre.get("structures") or []
            fin = L.snapshots(r)[-1]["structures"] if L.snapshots(r) else []
            ev = eng["events"]
            ekinds = {}
            for e in ev:
                ekinds[e["kind"]] = ekinds.get(e["kind"], 0) + 1
            cma = next((e["ranking"] for e in ev if e["kind"] == "tool_screen_cma"), None)
            probe = next((e["ranking"] for e in ev if e["kind"] == "tool_screen"), None)
            pref = next((e for e in ev if e["kind"] == "preferred_tools"), None)
            tools_run = [s.get("tool") for s in log]
            twin_b, plant_b = L.twin_breakdown(led), L.plant_breakdown(led)
            dp, dt, rp, rt = phase_costs(r)
            nm = nemotron_summary(r) if r.get("nemotron") else {}
            inj = r["injected_structure"]
            # material change of the repair procedure by Nemotron (FA-1 operational definition, see report section C/F4)
            material = None
            if r.get("nemotron"):
                material = bool(nm["n_direct_repair"] or nm["n_conclude"] or nm["start_edits"] or nm["tool_order"]
                                or ekinds.get("tool_screen_unavailable"))
            sub_tool = sub_src.split(":")[-1] if sub_src and (sub_src.startswith("repair:") or sub_src.startswith("twin:")) else ""
            ep_rows.append({
                "instance_id": iid, "robot_base": L.base_of(iid), "failure_family": r["family"],
                "kind": "composition" if L.is_comp(r) else "single", "severity": r["severity"], "mult": r["mult"], "arm": arm,
                "injected": L.st_str(inj), "leading_diagnosis": L.st_str(r["map_structure"]), "leading_mass": round(r["map_mass"], 4),
                "p_on_injected": round(r["posterior_mass_on_injected"], 4),
                "leader_incl_unmodelled_final": L.st_str(fin[0]["structure"]) if fin else "",
                "unmodelled_mass_final": eng.get("unmodelled_mass", 0.0),
                "leader_pre_repair": L.st_str(pre_st[0]["structure"]) if pre_st else "",
                "leader_pre_repair_mass": round(pre_st[0]["w"], 4) if pre_st else None,
                "true_structure_match": L.st_key(r["map_structure"]) == L.st_key(inj),
                "true_primitive_overlap": L.shares_primitive(r["map_structure"], inj),
                "true_kind_overlap": L.shares_kind(r["map_structure"], inj),
                "full": fl["full"], "status": fl["status"], "val_walking_frac": fl["walking_frac"],
                "verification_category": L.fail_category(fl), "verdict": fl["verdict"],
                "fail_walk": fl["fail_walk_robustness"], "fail_disp": fl["fail_displacement"], "fail_confirm": fl["fail_confirmation"],
                "submitted_design": sub, "submitted_source": sub_src, "final_repair_tool": sub_tool,
                "tool_sequence": ">".join(f"{s['step']}:{s.get('tool')}" for s in log),
                "engine_cma_order": ">".join(x["tool"] for x in cma[:5]) if cma else "",
                "engine_probe_order": ">".join(x["tool"] for x in probe[:5]) if probe else "",
                "preferred_tools": ">".join(pref["prefer"]) if pref else "",
                "repair_accepted_early": rep.get("accepted"), "concluded_by": conc.get("by"),
                "termination": ("no repair (concluded by Nemotron)" if conc.get("by") == "nemotron" and not log else
                                ("accepted by stop map" if rep.get("accepted") else "budget spent, best mapped design")) if rep or conc.get("by") == "nemotron" else "?",
                "n_diag_experiments": sum(1 for x in eng["experiments"] if x["kind"] in ("counterfactual", "floor", "weigh")),
                "plant_used": led["used"], "plant_remaining": led["remaining"],
                "twin_used": led["twin"]["used"], "twin_remaining": led["twin"]["remaining"],
                "plant_diag": dp, "twin_diag": dt, "plant_repair": rp, "twin_repair": rt,
                "plant_breakdown": json.dumps(plant_b, sort_keys=True), "twin_breakdown": json.dumps(twin_b, sort_keys=True),
                "n_assimilated": ekinds.get("assimilated_check", 0), "n_assim_skipped": ekinds.get("assimilation_skipped", 0),
                "n_composite_expansion": ekinds.get("composite_expansion", 0), "n_composite_skipped": ekinds.get("composite_skipped", 0),
                "n_twin_exhausted_update": sum(1 for e in ev if e["kind"] == "twin_budget_exhausted" and e.get("where") == "update"),
                "n_twin_exhausted_add": sum(1 for e in ev if e["kind"] == "twin_budget_exhausted" and e.get("where") == "add_particles"),
                "tool_screen_unavailable": ekinds.get("tool_screen_unavailable", 0),
                "warm_start_ran": any(s["step"] == "twin" for s in log),
                "nemotron_materially_changed_repair": material,
                **{k: nm.get(k) for k in ("n_nemotron_actions", "action_counts", "n_fallback", "deviated_hascases", "tool_order",
                                          "start_edits", "n_direct_repair", "n_conclude", "n_nemo_experiments",
                                          "n_delegate_diagnosis", "n_hypotheses_proposed", "n_refused", "p_success")},
                "raw_record": f"{path}#L{line + 1}"})
            # ---------------- repair steps
            pmap = rep.get("p_full") or {}
            for k, s in enumerate(log):
                evd = s.get("evidence") or {}
                rep_rows.append({
                    "instance_id": iid, "arm": arm, "kind": "composition" if L.is_comp(r) else "single", "step_no": k,
                    "step": s["step"], "tool": s.get("tool"), "plant_budget": s.get("budget"), "design": s.get("design"),
                    "twin_walking_of8": s.get("twin_walking"), "plant_check8": s.get("check"), "plant_check16": s.get("check16"),
                    "train_walking_of4": s.get("train_walking"), "stress4": evd.get("stress4"), "disp_pass": evd.get("disp_pass"),
                    "disp_median_m": evd.get("disp_median_m"), "p_full_map": evd.get("p_full"), "refused": s.get("refused"),
                    "is_submitted": s.get("design") == sub, "episode_full": fl["full"], "episode_category": L.fail_category(fl),
                    "engine_cma_rank_of_tool": next((i for i, x in enumerate(cma or []) if x["tool"] == s.get("tool")), None),
                    "engine_cma_walking_of_tool": next((x.get("cma_walking") for x in (cma or []) if x["tool"] == s.get("tool")), None),
                    "outcome_observed": "verified (submitted design)" if s.get("design") == sub else "not verified (plant robustness evidence only)",
                    "raw_record": f"{path}#L{line + 1}"})
            # Nemotron direct repairs (outside robust_repair)
            for t in r["agent"]["trace"]:
                if t["actor"] == "nemotron" and t["action"].get("action") == "repair":
                    res, a = t["result"], t["action"]
                    e2 = res.get("evidence") or {}
                    rep_rows.append({
                        "instance_id": iid, "arm": arm, "kind": "composition" if L.is_comp(r) else "single", "step_no": f"nemotron@{t['seq']}",
                        "step": f"nemotron_{a.get('mode', 'twin')}", "tool": a.get("tool"), "plant_budget": res.get("plant_rollouts"),
                        "design": res.get("design"), "twin_walking_of8": res.get("twin_walking"), "plant_check8": e2.get("robust8"),
                        "plant_check16": e2.get("robust16"), "train_walking_of4": e2.get("train"), "stress4": e2.get("stress4"),
                        "disp_pass": e2.get("disp_pass"), "disp_median_m": e2.get("disp_median_m"), "p_full_map": e2.get("p_full"),
                        "refused": res.get("refused"), "is_submitted": res.get("design") == sub, "episode_full": fl["full"],
                        "episode_category": L.fail_category(fl), "engine_cma_rank_of_tool": None, "engine_cma_walking_of_tool": None,
                        "outcome_observed": "verified (submitted design)" if res.get("design") == sub else "not verified",
                        "raw_record": f"{path}#L{line + 1}"})
            # ---------------- assimilation events (engine events carry them for every arm)
            hist = {h["label"]: h for h in L.snapshots(r)}
            order = 0
            assim_list = [e for e in ev if e["kind"] in ("assimilated_check", "assimilation_skipped")]
            first_done = False
            for e in assim_list:
                if e["kind"] == "assimilation_skipped":
                    fb_rows.append({"instance_id": iid, "arm": arm, "robot_base": L.base_of(iid),
                                    "kind": "composition" if L.is_comp(r) else "single", "event_order": order,
                                    "design": e["design"], "skipped": True, "skip_reason": e.get("reason"),
                                    "design_source": L.design_source(r, e["design"]), "raw_record": f"{path}#L{line + 1}",
                                    "episode_full": fl["full"]})
                    order += 1
                    continue
                pred = e["predicted_walking"]
                vals = list(pred.values())
                obs, n = e["observed_walking"], e["n"]
                before, after = e["before"], e["after"]
                bmap = {L.st_str(s): w for s, w in before}
                amap = {L.st_str(s): w for s, w in after}
                keys = set(bmap) | set(amap)
                # top-4 truncated TV (lower bound on true TV when structures leave the top 4)
                tv4 = 0.5 * sum(abs(bmap.get(k, 0.0) - amap.get(k, 0.0)) for k in keys)
                # full structure TV from the engine snapshots (top 8) around this assimilation
                lab = next((h for h in L.snapshots(r) if h["label"].endswith(f":check@{e['design']}")), None)
                idx = L.snapshots(r).index(lab) if lab else None
                tv8 = None
                if idx:
                    b8 = {L.st_str(x["structure"]): x["w"] for x in L.snapshots(r)[idx - 1]["structures"]}
                    a8 = {L.st_str(x["structure"]): x["w"] for x in lab["structures"]}
                    tv8 = 0.5 * sum(abs(b8.get(k, 0.0) - a8.get(k, 0.0)) for k in set(b8) | set(a8))
                lead_b = L.st_str(before[0][0]) if before else ""
                # modelled competitors: log-odds gap leader vs runner-up (modelled only, before)
                mod = [(L.st_str(s), w) for s, w in before if L.st_key(s) != L.st_key(L.UNM)]
                gap = math.log(mod[0][1] / mod[1][1]) if len(mod) >= 2 and mod[1][1] > 0 else None
                spread = (max(vals) - min(vals)) if len(vals) >= 2 else None
                pairs = [abs(a - b) for i, a in enumerate(vals) for b in vals[i + 1:]]
                # leader's predicted count vs observation, and best-competitor
                lead_mod = mod[0][0] if mod else None
                lead_pred = pred.get(lead_mod) if lead_mod else None
                dsrc = L.design_source(r, e["design"])
                step = next((s for s in log if s.get("design") == e["design"]), None)
                reachable = (not first_done) and dsrc is not None and dsrc.startswith("twin:") and not ekinds.get("preferred_tools") \
                    and step is not None and step.get("step") == "twin"
                first_done = True
                fb_rows.append({
                    "instance_id": iid, "arm": arm, "robot_base": L.base_of(iid), "kind": "composition" if L.is_comp(r) else "single",
                    "event_order": order, "design": e["design"], "design_source": dsrc, "skipped": False, "skip_reason": "",
                    "observed_walking": obs, "n_seeds": n, "predicted_walking": json.dumps(pred, sort_keys=True),
                    "n_structures_predicted": len(vals), "n_distinct_predictions": len(set(vals)),
                    "pred_spread_max_minus_min": spread, "pred_pairwise_max": max(pairs) if pairs else None,
                    "pred_pairwise_mean": (sum(pairs) / len(pairs)) if pairs else None,
                    "observed_in_pred_range": (min(vals) <= obs <= max(vals)) if vals else None,
                    "leader_before": lead_b, "leader_before_w": before[0][1] if before else None,
                    "leader_is_unmodelled": lead_b == "unmodelled:any",
                    "modelled_leader_pred": lead_pred, "modelled_leader_abs_err": abs(lead_pred - obs) if lead_pred is not None else None,
                    "logodds_gap_modelled_top2": gap,
                    "max_possible_shift_nats_T6": round(n * L.PER_SEED_NATS / 6.0, 3),
                    "switch_possible_by_count_bound": (gap is not None and gap < n * L.PER_SEED_NATS / 6.0),
                    "posterior_before": json.dumps(before), "posterior_after": json.dumps(after),
                    "tv_top4": round(tv4, 4), "tv_top8": round(tv8, 4) if tv8 is not None else None,
                    "leader_changed": e["leader_changed"], "leader_after": L.st_str(after[0][0]) if after else "",
                    "decision_reachable": reachable,
                    "rescreen_followed": any(x["kind"] == "rescreen_after_assimilation" for x in ev),
                    "episode_full": fl["full"], "raw_record": f"{path}#L{line + 1}"})
                order += 1
    for name, rows in (("episode_index.csv", ep_rows), ("repair_decisions.csv", rep_rows), ("feedback_events.csv", fb_rows)):
        keys = []
        for row in rows:
            for k in row:
                if k not in keys:
                    keys.append(k)
        with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(name, len(rows))
    print("PER_SEED_NATS raw", L.PER_SEED_NATS, "tempered", L.PER_SEED_NATS / 6)


if __name__ == "__main__":
    main()
