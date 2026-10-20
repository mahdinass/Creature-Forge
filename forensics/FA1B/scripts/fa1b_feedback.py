"""FA-1B Investigation D: repair-feedback decision reachability (read-only; stored records + archived Nemotron prompts).

Per assimilation event (assimilated_check / assimilation_skipped, belief_engine.py:455-493) it records the action context, the
deterministic re-screen condition (belief_engine.py:952-960: inside robust_repair, after the twin warm-start check, only if that
check's assimilation changed the leader, tool_order None, no `prefer`, twin remaining >= 250, and the design was not accepted at
L950), later Nemotron turns, whether the update was SHOWN in a later prompt (string search of archived user messages), and the
next decision. D2: exactness test of FA-1's count-bound replay (fa1_f2b.py) on events where seed-level mismatches are fixed by
counts (observed or every predicted count in {0, n}): there |pred - obs| equals the per-seed mismatch count exactly.
Outputs feedback_reachability.csv."""
import collections
import csv
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L

FB = {(r["instance_id"], r["arm"], r["design"]): r for r in csv.DictReader(open(os.path.join(L.FA1, "feedback_events.csv"), encoding="utf-8"))}
RP = {(r["instance_id"], r["arm"], r["design"]): r for r in csv.DictReader(open(os.path.join(L.FA1, "feedback_replay.csv"), encoding="utf-8"))}
# belief_engine.loglik for one walking-only seed (FEATURES walking sd 0.35, NU 3, SEED_OUTLIER 0.1, OUTLIER_FEATURE_LOGP -3)
_t = lambda r: -0.5 * 4.0 * math.log1p(r * r / 3.0)  # noqa: E731
def _lse(a, b):
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))
SEED_MATCH = _lse(math.log(0.9) + _t(0.0), math.log(0.1) - 3.0)
SEED_MISS = _lse(math.log(0.9) + _t(1 / 0.35), math.log(0.1) - 3.0)
K_RAW = SEED_MATCH - SEED_MISS
TEMP = 6.0
MINW = 0.01   # 4-decimal rounding of the recorded weights (belief_engine.py:489-490) makes log-ratios of smaller weights unreliable
CUE = ("belief_update", "belief update", "folded", "assimilat", "leader_changed", "the belief predicted", "predicted walking")


def st(s):
    return "+".join(f"{a}:{b}" for a, b in sorted(tuple(x) for x in s))


def prompts(r):
    out = []
    for c in ((r.get("nemotron") or {}).get("calls") or []):
        out.append("\n".join(m.get("content", "") for m in (c.get("messages") or []) if m.get("role") == "user" and isinstance(m.get("content"), str)))
    return out


def classify_record(path, line, r, rows):
    tr = L.trace(r)
    hist = r["engine"]["history"]
    conc = ((r.get("agent") or {}).get("conclusion") or {})
    rep = conc.get("repair") or {}
    rlog = rep.get("log") or []
    prefer = bool(L.events(r, "preferred_tools"))
    rescreens = L.events(r, "rescreen_after_assimilation")
    P = prompts(r)
    designs = r["designs"]
    for e in L.events(r):
        if e["kind"] not in ("assimilated_check", "assimilation_skipped"):
            continue
        d = int(e["design"])
        lab = next((h for h in hist if h["label"].endswith(f":check@{d}")), None) if e["kind"] == "assimilated_check" else None
        eid = lab["label"][len("after_"):] if lab else None
        step = next((s for s in rlog if s.get("design") == d), None)
        if lab:
            t = next((x for x in tr if x["plant_used"] >= lab["plant_used"]), None)
        else:
            t = None
        if step is not None and (t is None or t["action"]["action"] == "delegate_repair"):
            ctx = f"robust_repair:{step['step']}"
            t = t or next((x for x in tr if x["action"]["action"] == "delegate_repair"), None)
        elif t is not None:
            ctx = f"{t['actor']}:{t['action']['action']}" + (f"/{t['action'].get('mode', 'twin')}" if t["action"]["action"] == "repair" else "")
        else:
            src = next((x for x in tr if (x.get("result") or {}).get("design") == d and x["action"]["action"] in ("repair", "check")), None)
            t = src
            ctx = f"{src['actor']}:{src['action']['action']}" if src else "unknown"
        accepted_here = bool(rep.get("accepted")) and rep.get("design") == d
        twin_after = (r["engine"]["ledger"]["twin"]["total"] - lab["twin_used"]) if lab else None
        plant_after = (r["engine"]["ledger"]["total"] - lab["plant_used"]) if lab and "total" in r["engine"]["ledger"] else None
        det_possible = (ctx == "robust_repair:twin" and not prefer and not accepted_here and twin_after is not None and twin_after >= 250)
        later = [x for x in tr if t is not None and x["seq"] > t["seq"] and x["actor"] in ("nemotron", "fallback")]
        later_nemo = [x for x in later if x["actor"] == "nemotron"]
        exposed = bool(eid) and any(f"{eid}:" in p for p in P[1:]) and bool(later_nemo)
        nxt = later_nemo[0] if later_nemo else None
        nxt_txt = " ".join(str(nxt["action"].get(k) or "") for k in ("understanding", "uncertainty", "why")).lower() if nxt else ""
        cites = bool(nxt) and (any(c in nxt_txt for c in CUE) or (f"design {d}" in nxt_txt and "predict" in nxt_txt))
        fb = FB.get((r["instance_id"], r["arm"], str(d)), {})
        rp = RP.get((r["instance_id"], r["arm"], str(d)), {})
        pred = e.get("predicted_walking") or {}
        vals = list(pred.values())
        spread = (max(vals) - min(vals)) if len(vals) >= 2 else None
        tv8 = float(fb["tv_top8"]) if fb.get("tv_top8") not in (None, "") else None
        lc = bool(e.get("leader_changed"))
        if e["kind"] == "assimilation_skipped":
            info = "skipped (twin budget): no update"
        elif spread is None or spread == 0:
            info = "no count-level disagreement among predicted structures"
        elif lc or (tv8 is not None and tv8 >= 0.05):
            info = "belief changed (leader change or TV8 >= 0.05)"
        else:
            info = "informative counts, limited posterior effect (TV8 < 0.05, leader kept)"
        if det_possible:
            reach = "deterministic re-screen structurally possible"
        elif later_nemo:
            reach = "later Nemotron decision(s) possible"
        else:
            reach = "no later decision point"
        if e["kind"] == "assimilation_skipped":
            group = "0 skipped"
        elif reach == "later Nemotron decision(s) possible" and exposed:
            group = "4 might influence Nemotron (shown in a later prompt)"
        elif info.startswith("belief changed"):
            group = "3 belief changed, no deterministic path, no later Nemotron turn" if reach == "no later decision point" else \
                    "3b belief changed, deterministic re-screen possible but not triggered"
        elif info.startswith("informative"):
            group = "2 informative counts, limited posterior effect"
        else:
            group = "1 no count-level information"
        rows.append({
            "instance_id": r["instance_id"], "arm": r["arm"], "robot_base": L.base_of(r["instance_id"]), "kind": e["kind"],
            "design": d, "design_source": designs[d]["source"] if d < len(designs) else None, "experiment_id": eid,
            "context": ctx, "robust_repair_step": step.get("step") if step else None, "nemotron_prefer_in_repair": prefer,
            "accepted_at_this_design": accepted_here, "twin_remaining_after": twin_after, "plant_remaining_after": plant_after,
            "deterministic_rescreen_possible": det_possible, "fa1_decision_reachable": fb.get("decision_reachable"),
            "rescreen_followed": bool(rescreens), "observed_walking": e.get("observed_walking"), "n_seeds": e.get("n"),
            "predicted_walking": json.dumps(pred, sort_keys=True), "count_spread": spread,
            "leader_before": st(e["before"][0][0]) if e.get("before") else None,
            "leader_before_w": e["before"][0][1] if e.get("before") else None, "leader_changed": lc, "tv_top8": tv8,
            "massweighted_disagreement": rp.get("massweighted_disagreement_seeds"),
            "later_nemotron_turns": len(later_nemo), "update_shown_in_later_prompt": exposed,
            "next_nemotron_action": (nxt["action"]["action"] + (":" + str(nxt["action"].get("tool") or nxt["action"].get("tool_order") or nxt["action"].get("experiment") or ""))) if nxt else None,
            "next_turn_text_references_update": cites,
            "final_submission_after": conc.get("design"), "episode_full": (r.get("verification") or {}).get("status") == L.FULL,
            "information_class": info, "action_reach": reach, "group": group, "raw_record": f"{path}#L{line + 1}"})


def replay_exact(rows, recs):
    """Count-bound replay vs realised shift, split by whether count-level mismatch equals seed-level mismatch."""
    byk = {(x["instance_id"], x["arm"], x["design"]): x for x in rows}
    res = []
    for path, line, r in recs:
        for e in L.events(r, "assimilated_check"):
            pred, obs, n = e["predicted_walking"], e["observed_walking"], e["n"]
            before = {st(s): w for s, w in e["before"]}
            after = {st(s): w for s, w in e["after"]}
            mods = [s for s in before if s != "unmodelled:any" and s in pred]
            if len(mods) < 2:
                continue
            exact = obs in (0, n) or all(pred[s] in (0, n) for s in mods)
            tot = sum(before[s] for s in mods)
            if tot <= 0:
                continue
            pb = {s: before[s] / tot for s in mods}
            ll = {s: -K_RAW / TEMP * abs(pred[s] - obs) for s in mods}
            m = max(ll.values())
            z = sum(pb[s] * math.exp(ll[s] - m) for s in mods)
            pa = {s: pb[s] * math.exp(ll[s] - m) / z for s in mods}
            tota = sum(after.get(s, 0.0) for s in mods)
            if tota <= 0:
                continue
            ra = {s: after.get(s, 0.0) / tota for s in mods}
            # log-odds shift of each modelled structure vs the leader (exact comparison where weights are > 0 in both)
            lead = mods[0]
            for s in mods[1:]:
                if min(before[s], before[lead], after.get(s, 0.0), after.get(lead, 0.0)) >= MINW:
                    exp_shift = math.log(pa[s] / pa[lead]) - math.log(pb[s] / pb[lead])
                    real_shift = math.log(ra[s] / ra[lead]) - math.log(pb[s] / pb[lead])
                    res.append((exact, exp_shift, real_shift, pred[s] == pred[lead], r["arm"], r["instance_id"], e["design"], s))
    return res


def main():
    rows = []
    recs = L.load_eval()
    for path, line, r in recs:
        classify_record(path, line, r, rows)
    with open(os.path.join(L.OUT, "feedback_reachability.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    A = [x for x in rows if x["kind"] == "assimilated_check"]
    print("events: assimilated", len(A), "skipped", len(rows) - len(A))
    print("context:", collections.Counter(x["context"] for x in A))
    print("group:", sorted(collections.Counter(x["group"] for x in A).items()))
    print("info x reach:")
    for k, v in sorted(collections.Counter((x["information_class"], x["action_reach"]) for x in A).items()):
        print("  ", k, v)
    print("deterministic re-screen possible:", sum(x["deterministic_rescreen_possible"] for x in A),
          "| FA-1 'decision_reachable':", sum(x["fa1_decision_reachable"] == "True" for x in A),
          "| disagreements:", [(x["instance_id"], x["arm"], x["design"], x["deterministic_rescreen_possible"], x["fa1_decision_reachable"])
                                for x in A if x["deterministic_rescreen_possible"] != (x["fa1_decision_reachable"] == "True")][:12])
    print("later Nemotron turns > 0:", sum(x["later_nemotron_turns"] > 0 for x in A), "| shown in a later prompt:",
          sum(x["update_shown_in_later_prompt"] for x in A), "| next-turn text references the update:", sum(x["next_turn_text_references_update"] for x in A))
    print("by arm, events with later Nemotron turns:", collections.Counter(x["arm"] for x in A if x["later_nemotron_turns"] > 0))
    print("next Nemotron actions after shown updates:", collections.Counter((x["next_nemotron_action"] or "").split(":")[0] for x in A if x["update_shown_in_later_prompt"]))
    print("leader changes:", [(x["instance_id"], x["arm"], x["design"], x["context"], x["leader_before"], x["later_nemotron_turns"], x["next_nemotron_action"], x["deterministic_rescreen_possible"]) for x in A if x["leader_changed"]])
    print("belief-changed events (leader change or TV8>=0.05) by reach:", collections.Counter(x["action_reach"] for x in A if x["information_class"].startswith("belief changed")))
    print("  of which shown to Nemotron:", sum(1 for x in A if x["information_class"].startswith("belief changed") and x["update_shown_in_later_prompt"]))
    # D2 replay exactness
    res = replay_exact(rows, recs)
    for flag in (True, False):
        sub = [x for x in res if x[0] == flag]
        es, rs = np.array([x[1] for x in sub]), np.array([x[2] for x in sub])
        nz = np.abs(es) > 0.05
        print(f"\nD2 replay, {'EXACT (count = seed mismatch)' if flag else 'NON-exact'} pairs: n {len(sub)}; |expected|>0.05: {nz.sum()}")
        if len(sub):
            print("   median |real - expected| %.3f; p90 %.3f; corr %.3f" % (np.median(np.abs(rs - es)), np.percentile(np.abs(rs - es), 90),
                                                                           np.corrcoef(es, rs)[0, 1] if len(sub) > 2 else float('nan')))
            if nz.sum():
                print("   ratio real/expected where |expected|>0.05: median %.3f, IQR %.3f-%.3f" % (np.median(rs[nz] / es[nz]), np.percentile(rs[nz] / es[nz], 25), np.percentile(rs[nz] / es[nz], 75)))
            same = [x for x in sub if x[3]]
            if same:
                v = np.array([x[2] for x in same])
                print("   pairs with IDENTICAL predicted counts (replay expects 0): n %d, |real shift| median %.3f, p90 %.3f, max %.3f, >0.1 nats: %d" % (
                    len(same), np.median(np.abs(v)), np.percentile(np.abs(v), 90), np.abs(v).max(), int((np.abs(v) > 0.1).sum())))
    print("\nper-seed raw nats K =", round(K_RAW, 4), "tempered", round(K_RAW / TEMP, 4), "8-seed ceiling", round(8 * K_RAW / TEMP, 3))


if __name__ == "__main__":
    main()
