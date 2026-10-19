"""Stage-2 report (phase 3): outcomes and process metrics of the autonomous HaS scientist and its controls. Development only.

Usage: python scripts/hdb_agent_report.py <records.jsonl ...> [--baseline A1e]
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hdb_report import arms                                              # noqa: E402
from creature_forge.belief_engine import CANDIDATE_CFS                   # noqa: E402

QS = (0.05, 0.25, 0.5, 0.75, 0.95)


def _rows(paths):
    return [json.loads(l) for p in paths for l in open(p, encoding="utf-8") if l.strip()]


def pinball(qvals: dict, y: float) -> float:
    """Mean pinball loss over the registered quantiles (a CRPS approximation)."""
    keys = ("q05", "q25", "q50", "q75", "q95")
    return sum(max(q * (y - qvals[k]), (q - 1) * (y - qvals[k])) for q, k in zip(QS, keys)) / len(keys)


def process(rows: list[dict]) -> list[str]:
    L = []
    for arm in sorted({r["arm"] for r in rows}):
        rs = [r for r in rows if r["arm"] == arm and r.get("agent")]
        if not rs:
            continue
        n = len(rs)
        acts, actors = Counter(), Counter()
        designed = exps_n = 0
        eig_ratio = []
        hyp_total = hyp_top3 = hyp_inj = hyp_map = 0
        preds = defaultdict(list)
        contra = assim = 0
        concl = Counter()
        tools = Counter()
        modes = Counter()
        mem_applied = 0
        for r in rs:
            ag = r["agent"]
            inj = sorted(tuple(x) for x in r["injected_structure"])
            concl[(ag.get("conclusion") or {}).get("by", "?").split(":")[0]] += 1
            for t in ag["trace"]:
                a = t["action"].get("action")
                acts[a] += 1
                actors[t["actor"]] += 1
                res = t["result"]
                if t["actor"] == "nemotron" and a == "experiment" and res.get("ok"):
                    exps_n += 1
                    eid = res["id"].split(":", 1)[1]
                    if (eid.startswith("cf:") and eid[3:] not in CANDIDATE_CFS) or \
                            (eid.startswith("floor_test@x") and eid != "floor_test@x3"):
                        designed += 1
                    if res.get("eig") is not None and res.get("best_eig"):
                        eig_ratio.append(res["eig"] / res["best_eig"])
                for h in (res.get("proposals") or {}).get("added") or []:
                    if t["actor"] != "nemotron":
                        continue
                    hyp_total += 1
                    hyp_top3 += bool(h.get("rank") and h["rank"] <= 3)
                    hyp_map += h.get("rank") == 1
                    st = sorted(tuple(x.split("(")[0].split(":")) for x in h["pid"].split("+"))
                    hyp_inj += st == inj
                if a == "assimilate" and res.get("ok"):
                    assim += 1
                if a == "repair" and res.get("ok"):
                    tools[t["action"].get("tool")] += 1
                    modes[t["action"].get("mode")] += 1
                    if (res.get("evidence") or {}).get("contradiction"):
                        contra += 1
                if a == "apply_dossier" and res.get("ok"):
                    mem_applied += 1
            for p in ag.get("predictions") or []:
                meas = None
                for t in ag["trace"]:
                    if t["action"].get("action") == "experiment" and t["result"].get("ok") and \
                            t["result"]["id"].split(":", 1)[1] == p["experiment"]:
                        meas = t["result"].get("measured")
                if not meas:
                    continue
                for q in p["predictions"]:
                    y = meas.get(q["quantity"])
                    if y is None:
                        continue
                    preds[q["quantity"]].append((pinball(q, y), q["q05"] <= y <= q["q95"], q["q25"] <= y <= q["q75"]))
        nem = [r["nemotron"] for r in rs if r.get("nemotron")]
        cost = sum(x.get("cost_usd") or 0 for x in nem)
        calls = [c for x in nem for c in x["calls"]]
        fails = sum(1 for x in nem for e in x["log"] if e["status"] != "ok")
        L += [f"## {arm} (n = {n})", "",
              f"- actions: {dict(acts.most_common())}",
              f"- actors: {dict(actors)} (fallback = invalid/failed model reply replaced by the engine's recommendation; model "
              f"role calls not ok: {fails} of {sum(len(x['log']) for x in nem)})",
              f"- conclusions: {dict(concl)}",
              f"- Nemotron experiments: {exps_n}, of which designed beyond the engine's candidate list: {designed}; "
              f"EIG of its choice / best available: median {sorted(eig_ratio)[len(eig_ratio) // 2] if eig_ratio else None}",
              f"- Nemotron hypotheses: {hyp_total}; entered the top 3: {hyp_top3}; became the leading explanation: {hyp_map}; "
              f"had the injected structure (dev post-mortem): {hyp_inj}",
              f"- repairs: tools {dict(tools)}, modes {dict(modes)}; plant contradicted the belief's prediction: {contra}; "
              f"assimilated checks: {assim}; dossiers applied: {mem_applied}",
              "- registered predictions (pinball loss mean; 90 % / 50 % interval coverage): " + "; ".join(
                  f"{q}: {sum(x[0] for x in v) / len(v):.3f}, {sum(x[1] for x in v)}/{len(v)}, {sum(x[2] for x in v)}/{len(v)}"
                  for q, v in preds.items()),
              f"- MAP structure = injected: {sum(r['map_structure'] == r['injected_structure'] for r in rs)}/{n}; mean "
              f"posterior mass on injected {sum(r['posterior_mass_on_injected'] for r in rs) / n:.2f}",
              f"- inference: ${cost:.3f} total (${cost / max(1, n):.4f}/episode), {len(calls)} calls, "
              f"{sum((c.get('usage') or {}).get('prompt_tokens', 0) for c in calls)} prompt + "
              f"{sum((c.get('usage') or {}).get('completion_tokens', 0) for c in calls)} completion tokens; mean wall "
              f"{sum(r['wall_s'] for r in rs) / n / 60:.1f} min", ""]
    return L


def walking_pairs(rows: list[dict]) -> list[str]:
    """Paired validation walking fraction between arms on shared instances (one-sided Wilcoxon, first arm better)."""
    from hdb_report import wilcoxon_one_sided
    by = defaultdict(dict)
    for r in rows:
        if "verification" in r:
            by[r["instance_id"]][r["arm"]] = r["verification"]["walking_frac"]
    names = sorted({a for v in by.values() for a in v})
    L = ["", "Paired validation walking fraction (one-sided Wilcoxon, first arm better; development only):", ""]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            d = [v[a] - v[b] for v in by.values() if a in v and b in v]
            if d:
                w = wilcoxon_one_sided(d)
                L.append(f"- {a} vs {b}: n {len(d)}, mean diff {w['mean_diff']:+.3f}, p({a}>{b}) = {w['p']:.3f}, "
                         f"p({b}>{a}) = {wilcoxon_one_sided([-x for x in d])['p']:.3f}")
    return L


def corrupt_probe(rows: list[dict], probe_id: str = "D90", probe_tool: str = "foot_friction") -> list[str]:
    """Negative-transfer probe: did the scientist apply the deliberately wrong dossier or adopt its repair?"""
    rs = [r for r in rows if r["arm"] == "A4bad"]
    if not rs:
        return []
    applied = adopted = shown_top = 0
    for r in rs:
        ag = r["agent"]
        acts = [t["action"] for t in ag["trace"] if t["actor"] == "nemotron"]
        applied += any(a.get("action") == "apply_dossier" and a.get("dossier") == probe_id for a in acts)
        adopted += any(probe_tool in (a.get("tool_order") or []) or (a.get("action") == "repair" and a.get("tool") == probe_tool)
                       or "foot_friction@" in (a.get("start_edits") or "") for a in acts)
        shown_top += any(v["shown"] and v["shown"][0][0] == probe_id for v in ag.get("memory_views") or [])
    st = Counter(r["verification"]["status"] for r in rs)
    return ["", f"## Corrupted-dossier probe (A4bad, n = {len(rs)}; the probe dossier claims low friction for every failure)", "",
            f"- probe dossier ranked first on some turn: {shown_top}/{len(rs)}; applied as hypotheses: {applied}/{len(rs)}; its "
            f"repair adopted (tool order, trial repair or start edits): {adopted}/{len(rs)}",
            f"- outcomes: {dict(st)}"]


def main() -> None:
    paths = [p for p in sys.argv[1:] if not p.startswith("--")]
    rows = _rows(paths)
    print(arms(paths))
    print("\n".join(walking_pairs(rows)))
    print("\n".join(["", "# Process metrics (development only)", ""] + process(rows) + corrupt_probe(rows)))


if __name__ == "__main__":
    main()
