"""FA-1 F4: Nemotron decision-authority funnel (A3v5, A4x) against the engine default, from the agent traces."""
from __future__ import annotations

import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L  # noqa: E402

TWIN_CAP, RESERVE, STEP = 2800, 1750, 250        # belief_engine v6 budget guard: stop when twin remaining < 1750 + 250
CONF, DIAG_PLANT, MAX_EXP = 0.9, 120, 6


def engine_would_stop(post, plant_used, twin_used, n_exp):
    sp = [w for s, w in (post or []) if L.st_key(s) != L.st_key(L.UNM)]
    return bool((sp and sp[0] >= CONF) or plant_used >= DIAG_PLANT or TWIN_CAP - twin_used < RESERVE + STEP or n_exp >= MAX_EXP)


def episode(r):
    tr = r["agent"]["trace"]
    post, pu, tu, n_exp = None, 0, 0, 0
    out = collections.Counter()
    first_override_twin = None
    for t in tr:
        a = t["action"].get("action")
        if t["actor"] == "engine":
            post = t["result"].get("posterior")
            pu, tu = t["plant_used"], t["twin_used"]
            continue
        actor = t["actor"]
        out[f"{actor}:{a}"] += 1
        stop_before = engine_would_stop(post, pu, tu, n_exp)
        res = t["result"]
        if actor == "nemotron":
            if t["action"].get("hypotheses"):
                out["turns_with_hypotheses"] += 1
            if a == "experiment":
                ok = res.get("ok", False)
                out["exp_ok" if ok else "exp_refused"] += 1
                if ok:
                    if res.get("eig") is not None and res.get("best_eig") is not None and abs(res["eig"] - res["best_eig"]) < 1e-3:
                        out["exp_engine_top"] += 1
                    else:
                        out["exp_not_engine_top"] += 1
                    if stop_before:
                        out["exp_after_engine_stop"] += 1
                        out["plant_after_stop"] += t["plant_cost"]
                        out["twin_after_stop"] += t["twin_cost"]
                        if first_override_twin is None:
                            first_override_twin = tu
                    if t["action"].get("prediction"):
                        out["exp_with_registered_prediction"] += 1
                    n_exp += 1
            if a == "delegate_diagnosis":
                out["dd_ran_exps"] += len(res.get("ran") or [])
                n_exp += len(res.get("ran") or [])
            if a in ("delegate_repair", "repair", "conclude") and not stop_before:
                out["repair_before_engine_stop"] += 1
            if a == "delegate_repair":
                if t["action"].get("tool_order"):
                    out["dr_tool_order"] += 1
                if t["action"].get("start_edits"):
                    out["dr_start_edits"] += 1
                if not t["action"].get("tool_order") and not t["action"].get("start_edits"):
                    out["dr_plain"] += 1
            if a == "repair":
                out["direct_repair_ok" if res.get("ok") else "direct_repair_refused"] += 1
            if a == "conclude":
                out["conclude"] += 1
                if (r["agent"].get("conclusion") or {}).get("design") == 0:
                    out["conclude_faulty_design0"] += 1
            if res.get("proposals"):
                added = res["proposals"].get("added") or []
                out["hyp_added"] += len(added)
                out["hyp_rank1"] += sum(1 for x in added if x.get("rank") == 1)
        if actor == "nemotron" or actor == "fallback":
            post = res.get("posterior") or (res.get("proposals") or {}).get("posterior") or post
        pu, tu = t["plant_used"], t["twin_used"]
    # outcome-level material changes
    ev = r["engine"]["events"]
    lead = r["engine"]["particles"][0] if r["engine"]["particles"] else {}
    out["final_leader_from_nemotron"] = int(str(lead.get("source", "")).startswith(("nemotron", "dossier", "learned")))
    out["screen_unavailable"] = int(any(e["kind"] == "tool_screen_unavailable" for e in ev))
    out["warm_start_missing"] = int(not any(s["step"] == "twin" for s in ((L.repair_of(r) or {}).get("log") or [])))
    out["twin_exhausted_update"] = int(any(e["kind"] == "twin_budget_exhausted" and e.get("where") == "update" for e in ev))
    return out, first_override_twin


def main():
    data = L.load_eval()
    a1 = {r["instance_id"]: r for _, _, r in data["A1e6"]}
    for arm in ("A3v5", "A4x"):
        tot = collections.Counter()
        per = []
        for p, i, r in data[arm]:
            c, fot = episode(r)
            tot.update(c)
            e1 = a1[r["instance_id"]]
            seq = lambda x: [(s["step"], s.get("tool")) for s in ((L.repair_of(x) or {}).get("log") or [])]  # noqa: E731
            first_tool = lambda x: (seq(x)[0][1] if seq(x) else None)  # noqa: E731
            per.append({"iid": r["instance_id"], "c": c, "full": r["verification"]["status"] == L.FULL,
                        "a1_full": e1["verification"]["status"] == L.FULL,
                        "same_first_tool": first_tool(r) == first_tool(e1),
                        "same_seq": seq(r) == seq(e1), "same_dx": L.st_key(r["map_structure"]) == L.st_key(e1["map_structure"]),
                        "tool_order": next((t["action"].get("tool_order") for t in r["agent"]["trace"] if t["action"].get("tool_order")), None),
                        "engine_top_tool": next((e["ranking"][0]["tool"] for e in r["engine"]["events"] if e["kind"] in ("tool_screen_cma",) and e["ranking"]), None),
                        "pref": next((e for e in r["engine"]["events"] if e["kind"] == "preferred_tools"), None),
                        "p_success": next((t["action"].get("p_success") for t in reversed(r["agent"]["trace"]) if t["action"].get("action") in ("delegate_repair", "conclude", "repair")), None),
                        "plant": r["engine"]["ledger"]["used"], "twin": r["engine"]["ledger"]["twin"]["used"]})
        n = len(per)
        print(f"\n######## {arm}: {n} episodes")
        print("action counts:", {k: v for k, v in sorted(tot.items()) if ":" in k})
        print("experiments: ok", tot["exp_ok"], "refused", tot["exp_refused"], "| engine's top-EIG pick", tot["exp_engine_top"],
              "| other pick", tot["exp_not_engine_top"], "| with registered prediction", tot["exp_with_registered_prediction"])
        print("experiments run after the engine's own stopping rule had fired:", tot["exp_after_engine_stop"],
              f"(plant {tot['plant_after_stop']}, twin {tot['twin_after_stop']}) in",
              sum(1 for x in per if x["c"]["exp_after_engine_stop"]), "episodes")
        print("delegate_diagnosis experiments:", tot["dd_ran_exps"], "| repair started before the engine would stop:", tot["repair_before_engine_stop"])
        print("hypotheses: turns with hypotheses", tot["turns_with_hypotheses"], "added", tot["hyp_added"], "ranked 1 on arrival", tot["hyp_rank1"],
              "| episodes whose final leading particle came from Nemotron/dossier:", sum(x["c"]["final_leader_from_nemotron"] for x in per))
        print("repair: delegate plain", tot["dr_plain"], "with tool_order", tot["dr_tool_order"], "with start_edits", tot["dr_start_edits"],
              "| direct repair ok/refused", tot["direct_repair_ok"], tot["direct_repair_refused"], "| conclude", tot["conclude"],
              "(faulty design 0:", tot["conclude_faulty_design0"], ")")
        print("knock-on: screen unavailable", sum(x["c"]["screen_unavailable"] for x in per), "| warm start missing",
              sum(x["c"]["warm_start_missing"] for x in per), "| twin exhausted during belief update", sum(x["c"]["twin_exhausted_update"] for x in per))
        # tool_order vs engine top
        for x in per:
            if x["tool_order"]:
                print(f"   tool_order {x['tool_order']} engine-probe-order {x['pref']['engine_order'][:3] if x['pref'] else None} FULL {x['full']} (A1e6 {x['a1_full']}) {x['iid']}")
        # funnel
        f1 = n
        f2 = sum(1 for x in per if x["c"]["exp_not_engine_top"] or x["c"]["exp_after_engine_stop"] or x["c"]["hyp_added"]
                 or x["c"]["dr_tool_order"] or x["c"]["dr_start_edits"] or x["c"]["direct_repair_ok"] or x["c"]["conclude"]
                 or x["c"]["nemotron:screen_tools"] or x["c"]["nemotron:check"])
        f3 = sum(1 for x in per if not x["same_seq"])
        f3b = sum(1 for x in per if not x["same_first_tool"])
        f4 = sum(1 for x in per if x["full"] != x["a1_full"])
        print(f"FUNNEL: episodes {f1} -> with >=1 non-default Nemotron action {f2} -> repair tool sequence differs from A1e6 {f3} "
              f"(first tool differs {f3b}) -> FULL differs from A1e6 {f4} (Nemotron arm better {sum(1 for x in per if x['full'] and not x['a1_full'])}, "
              f"worse {sum(1 for x in per if x['a1_full'] and not x['full'])})")
        dev = [x for x in per if x["c"]["dr_tool_order"] or x["c"]["dr_start_edits"] or x["c"]["direct_repair_ok"] or x["c"]["conclude"]]
        print(f"  has_cases 'deviated' (repair-level only): {len(dev)}; among non-deviated, sequence still differs from A1e6 in "
              f"{sum(1 for x in per if x not in dev and not x['same_seq'])} of {n - len(dev)}; FULL differs in {sum(1 for x in per if x not in dev and x['full'] != x['a1_full'])}")
        ov = [x for x in per if x["c"]["exp_after_engine_stop"]]
        nov = [x for x in per if not x["c"]["exp_after_engine_stop"]]
        print(f"  episodes with experiments after engine stop: FULL {sum(x['full'] for x in ov)}/{len(ov)} (A1e6 on same instances {sum(x['a1_full'] for x in ov)}); "
              f"others FULL {sum(x['full'] for x in nov)}/{len(nov)} (A1e6 {sum(x['a1_full'] for x in nov)})")
        wm = [x for x in per if x["c"]["warm_start_missing"]]
        print(f"  warm start missing: FULL {sum(x['full'] for x in wm)}/{len(wm)} (A1e6 same instances {sum(x['a1_full'] for x in wm)})")
        print(f"  same diagnosis as A1e6 (exact leading structure): {sum(x['same_dx'] for x in per)}/{n}")
        ps = [(x["p_success"], x["full"]) for x in per if isinstance(x["p_success"], (int, float))]
        if ps:
            import numpy as np  # noqa: PLC0415
            hi = [f for p, f in ps if p >= .5]
            lo = [f for p, f in ps if p < .5]
            base = np.mean([f for _, f in ps])
            print(f"  P(success): n {len(ps)} mean {np.mean([p for p, _ in ps]):.2f}; FULL when P>=0.5: {sum(hi)}/{len(hi)}, P<0.5: {sum(lo)}/{len(lo)}; "
                  f"Brier {np.mean([(p - f) ** 2 for p, f in ps]):.3f} vs constant {np.mean([(base - f) ** 2 for _, f in ps]):.3f}")


if __name__ == "__main__":
    main()
