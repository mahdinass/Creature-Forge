"""DS-1 offline stage (docs/DS1_PROTOCOL.md §7.2): temperature T, misfit threshold, R-head leave-one-base-out validation and
gate G-a. Reads development records on the 20 INIT experience bases only (stream and transfer bases, and the sealed split,
are excluded by construction). No simulation; runs locally.

Usage: python scripts/ds1_offline.py [--records artifacts/vm/hdb/artifacts/hdb] [--out experiments/causal_engineer/dev/hdb/ds1]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creature_forge import repair_learning as rl                     # noqa: E402
from creature_forge import has_cases as hc                           # noqa: E402
from creature_forge.has_cases import PROBE_TOOL, base_of, final_tool, screens   # noqa: E402

SPLIT = "experiments/causal_engineer/dev/hdb/stage2_split.json"
T_GRID = (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0)
ENGINE_V5 = ("fresh_A1c5.jsonl", "vs5_A1c.jsonl", "s2DC_exp_A1e.jsonl")          # situation source (engine v5 = A1e)
ENGINE_OLD = ("vs4_A1c.jsonl", "vs4_a1.jsonl", "vs4_A1f.jsonl", "vs2_a1.jsonl")
A0 = ("fresh_A0.jsonl", "vs4_A0.jsonl")


def rows_of(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def structures_at(rec: dict, T: float) -> list:
    return hc.structures_at(rec["engine"]["particles"], T)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default="artifacts/vm/hdb/artifacts/hdb")
    ap.add_argument("--out", default="experiments/causal_engineer/dev/hdb/ds1")
    a = ap.parse_args()
    R = lambda f: os.path.join(a.records, f)    # noqa: E731
    split = json.load(open(SPLIT, encoding="utf-8"))
    stream = set(hc.ds1_stream_bases(split))
    init = set(split["experience_bases"]) - stream
    report: dict = {"init_bases": sorted(init), "stream_bases": sorted(stream)}
    L = ["# DS-1 offline stage (development; init experience bases only)", ""]

    # ---------------------------------------------------------------- situation records (engine v5 on init bases)
    sit_rec = {}
    for f in ENGINE_V5:
        for r in rows_of(R(f)):
            if r.get("eligible") is False or "engine" not in r or base_of(r["instance_id"]) not in init:
                continue
            sit_rec.setdefault(r["instance_id"], r)
    singles = [r for r in sit_rec.values() if not r["family"].startswith("devcomp")]
    comps = [r for r in sit_rec.values() if r["family"].startswith("devcomp")]
    L.append(f"Engine-v5 records on init bases: {len(singles)} single-mechanism, {len(comps)} development compositions.")

    # ---------------------------------------------------------------- 1. temperature (LOBO on mean log P(true structure))
    def logp_truth(r, T):
        tru = sorted(tuple(x) for x in r["injected_structure"])
        for st, w in structures_at(r, T):
            if sorted(tuple(x) for x in st) == tru:
                return math.log(max(w, 1e-4))
        return math.log(1e-4)
    bases = sorted({base_of(r["instance_id"]) for r in singles})
    cv = []
    for b in bases:
        tr = [r for r in singles if base_of(r["instance_id"]) != b]
        te = [r for r in singles if base_of(r["instance_id"]) == b]
        Tb = max(T_GRID, key=lambda T: np.mean([logp_truth(r, T) for r in tr]))
        cv += [(logp_truth(r, Tb), logp_truth(r, 1.0)) for r in te]
    T = max(T_GRID, key=lambda T: np.mean([logp_truth(r, T) for r in singles]))
    conf_wrong = lambda TT: sum(1 for r in singles if (lambda sp: sp[0][1] >= 0.95 and sorted(map(tuple, sp[0][0])) !=   # noqa: E731
                                                       sorted(tuple(x) for x in r["injected_structure"]))(structures_at(r, TT)))
    report["temperature"] = {"T": T, "lobo_mean_logp_truth_at_T": float(np.mean([x for x, _ in cv])),
                             "lobo_mean_logp_truth_at_1": float(np.mean([y for _, y in cv])),
                             "confident_wrong_at_1": conf_wrong(1.0), "confident_wrong_at_T": conf_wrong(T), "n": len(singles)}
    L += ["", "## 1. Temperature", "",
          f"- T = {T} (grid {T_GRID}, chosen on all init singles; LOBO mean log P(truth) {report['temperature']['lobo_mean_logp_truth_at_T']:.3f} "
          f"vs {report['temperature']['lobo_mean_logp_truth_at_1']:.3f} at T = 1)",
          f"- confident-but-wrong (>= 0.95 on a wrong structure): {conf_wrong(1.0)} at T = 1 -> {conf_wrong(T)} at T = {T}, of {len(singles)}"]

    # ---------------------------------------------------------------- 2. misfit threshold
    def stat(r):
        exps = r["engine"]["experiments"]
        if any(e["kind"] not in ("observe", "counterfactual", "floor") for e in exps):
            return None                 # the stored log-likelihood includes a weigh test: not comparable, skipped
        n = sum(len(e.get("features") or {}) for e in exps)
        best = max(r["engine"]["particles"], key=lambda p: p["loglik"])
        return best["loglik"] / n if n else None
    ok_stats = sorted(s for r in singles if r["map_structure"] == r["injected_structure"] and (s := stat(r)) is not None)
    thr = float(np.percentile(ok_stats, 5))
    all_single = [s for r in singles if (s := stat(r)) is not None]
    comp_stats = [s for r in comps if (s := stat(r)) is not None]
    report["misfit"] = {"threshold": thr, "n_calibration": len(ok_stats),
                        "flag_rate_single_all": float(np.mean([s < thr for s in all_single])) if all_single else None,
                        "flag_rate_compositions": float(np.mean([s < thr for s in comp_stats])) if comp_stats else None,
                        "n_compositions": len(comp_stats)}
    L += ["", "## 2. Structural misfit threshold", "",
          f"- threshold = 5th percentile of the leader's log-likelihood per diagnostic seed on {len(ok_stats)} correctly "
          f"diagnosed init singles: {thr:.3f}",
          f"- flag rate: all init singles {report['misfit']['flag_rate_single_all']}; init development compositions "
          f"{report['misfit']['flag_rate_compositions']} (n = {len(comp_stats)})"]

    # ---------------------------------------------------------------- 3. R-head rows
    rows = []
    def add(iid, tool, status, proc):
        r = sit_rec.get(iid)
        if r is None or tool not in rl.TOOLS:
            return
        probe, cma = screens(r)
        rows.append({"iid": iid, "base": base_of(iid), "tool": tool, "procedure": proc,
                     "full": status == "FULL_RECOVERY", "sit": rl.situation_features(structures_at(r, T)),
                     "ev": rl.tool_evidence(probe, cma)[tool]})
    for iid, r in sit_rec.items():
        add(iid, final_tool(r), r["verification"]["status"], "engine_final")
    for f in ENGINE_OLD:
        for r in rows_of(R(f)):
            if r.get("eligible") is not False and "verification" in r:
                add(r["instance_id"], final_tool(r), r["verification"]["status"], "engine_old")
    for f in A0:
        for r in rows_of(R(f)):
            if r.get("eligible") is not False and "verification" in r:
                add(r["instance_id"], final_tool(r), r["verification"]["status"], "a0")
    n_mkv = 0
    for r in rows_of(R("stopcal.jsonl")):
        if r["source"] == "initial":
            continue
        if r.get("origin", "").startswith("mkv"):
            n_mkv += 1          # designs optimised with oracle mechanism knowledge (MKV K1/K2): excluded
            continue
        t = r["source"].split(":")[-1]
        add(r["instance_id"], t if t in rl.TOOLS else PROBE_TOOL.get(t), r["status"], "diverse")
    cnt = collections.Counter(r["procedure"] for r in rows)
    L += ["", "## 3. R-head data", "",
          f"- {len(rows)} verified (situation, tool, outcome) rows on {len({r['iid'] for r in rows})} init instances: {dict(cnt)}; "
          f"FULL rate {np.mean([r['full'] for r in rows]):.2f}. Excluded: {n_mkv} oracle-informed MKV designs.",
          "- Selection bias: outcomes exist only for tools some procedure chose (missing not at random); engine-final tools "
          "had the full pipeline, other rows other budgets. Procedure is a covariate, and decisions are compared only "
          "among tools whose outcome is known on the same instance."]

    # ---------------------------------------------------------------- 4. LOBO validation
    def lobo(kind):
        preds, models = [], {}
        for b in sorted({r["base"] for r in rows}):
            tr = [r for r in rows if r["base"] != b]
            te = [r for r in rows if r["base"] == b]
            if kind == "b0":
                p0 = np.mean([r["full"] for r in tr])
                preds += [(r, float(p0)) for r in te]
                continue
            m = models[b] = rl.RHead.fit(tr, kind)
            preds += [(r, float(rl.predict(m.w, rl.featurize(r["sit"], r["ev"], r["tool"], r["procedure"], kind)[None, :])[0]))
                      for r in te]
        return preds, models

    def case_attention():
        preds = []
        def kfeat(r):
            return np.array(r["sit"]["kind_w"] + [r["sit"]["entropy"], r["sit"]["lead"]])
        for b in sorted({r["base"] for r in rows}):
            tr = [r for r in rows if r["base"] != b]
            te = [r for r in rows if r["base"] == b]
            # temperature by inner leave-one-base-out on the training bases
            def score(tau, trn, tst):
                ll = 0.0
                for q in tst:
                    same = [r for r in trn if r["tool"] == q["tool"]]
                    w = np.array([math.exp(-np.sum((kfeat(q) - kfeat(r)) ** 2) / tau) for r in same])
                    p = (float(np.dot(w, [r["full"] for r in same])) + 1.0) / (float(w.sum()) + 2.0) if same else 0.5
                    ll -= q["full"] * math.log(p) + (1 - q["full"]) * math.log(1 - p)
                return ll
            inner = sorted({r["base"] for r in tr})[:6]
            tau = min((0.05, 0.2, 0.5, 1.0), key=lambda t: sum(score(t, [r for r in tr if r["base"] != ib],
                                                                    [r for r in tr if r["base"] == ib]) for ib in inner))
            for q in te:
                same = [r for r in tr if r["tool"] == q["tool"]]
                w = np.array([math.exp(-np.sum((kfeat(q) - kfeat(r)) ** 2) / tau) for r in same])
                p = (float(np.dot(w, [r["full"] for r in same])) + 1.0) / (float(w.sum()) + 2.0) if same else 0.5
                preds.append((q, p))
        return preds, None

    def metrics(preds):
        y = np.array([r["full"] for r, _ in preds], dtype=float)
        p = np.clip(np.array([p for _, p in preds]), 1e-4, 1 - 1e-4)
        bins = np.minimum((p * 5).astype(int), 4)
        ece = sum(abs(p[bins == k].mean() - y[bins == k].mean()) * (bins == k).sum() for k in range(5) if (bins == k).any()) / len(y)
        rel = [(round(float(p[bins == k].mean()), 3), round(float(y[bins == k].mean()), 3), int((bins == k).sum()))
               for k in range(5) if (bins == k).any()]
        return {"log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), "brier": float(np.mean((p - y) ** 2)),
                "ece": float(ece), "reliability": rel}
    LO = {k: lobo(k) for k in ("b0", "b1", "b2", "full")}
    P = {k: v[0] for k, v in LO.items()}
    P["case_attention"] = case_attention()[0]
    report["lobo"] = {k: metrics(v) for k, v in P.items()}
    L += ["", "## 4. Leave-one-base-out probability quality", "", "| model | log loss | Brier | ECE |", "|---|---|---|---|"]
    for k, m in report["lobo"].items():
        L.append(f"| {k} | {m['log_loss']:.4f} | {m['brier']:.4f} | {m['ece']:.3f} |")
    L.append(f"\nReliability of the R-head (mean predicted, observed, n per bin): {report['lobo']['full']['reliability']}")

    # ---------------------------------------------------------------- 5. decision quality on comparable support
    by_inst = collections.defaultdict(list)
    for kind in ("full", "b1", "case_attention"):
        for r, p in P[kind]:
            by_inst[(kind, r["iid"])].append((r, p))
    dec = {"engine": [], "full": [], "b1": [], "case_attention": [], "random": []}
    per_base = collections.defaultdict(lambda: collections.defaultdict(float))
    n_inst = 0
    for iid in sorted({r["iid"] for r in rows}):
        rr = [r for r in rows if r["iid"] == iid]
        eng = [r for r in rr if r["procedure"] == "engine_final"]
        known = {}
        for r in rr:
            known.setdefault(r["tool"], []).append(float(r["full"]))
        if not eng or len(known) < 2:
            continue
        n_inst += 1
        out = {t: float(np.mean(v)) for t, v in known.items()}
        def choice(kind):
            # each fold model (fitted without this instance's base) scores every known tool at decision time, with the
            # procedure set to "engine_final"; case attention scores a tool by its kernel-weighted outcome rate
            if kind == "case_attention":
                s = {r["tool"]: p for r, p in by_inst[(kind, iid)]}
            else:
                m = LO[kind][1][base_of(iid)]
                s = {t: m.p(rr_t[0]["sit"], {t: rr_t[0]["ev"]}, t, "engine_final")
                     for t, rr_t in ((t, [r for r in rr if r["tool"] == t]) for t in known)}
            return max(out, key=lambda t: (s.get(t, -1.0), t == eng[0]["tool"]))
        picks = {"engine": eng[0]["tool"], "full": choice("full"), "b1": choice("b1"), "case_attention": choice("case_attention")}
        for k, t in picks.items():
            dec[k].append(out[t])
            per_base[base_of(iid)][k] += out[t]
        dec["random"].append(float(np.mean(list(out.values()))))
        per_base[base_of(iid)]["random"] += float(np.mean(list(out.values())))
    rng = np.random.default_rng(20261020)
    bl = sorted(per_base)
    boots = []
    for _ in range(2000):
        s = rng.choice(len(bl), len(bl))
        boots.append(sum(per_base[bl[i]]["full"] - per_base[bl[i]]["engine"] for i in s))
    ci = (float(np.percentile(boots, 5)), float(np.percentile(boots, 95)))
    report["decision"] = {"n_instances": n_inst, **{k: float(sum(v)) for k, v in dec.items()},
                          "rhead_minus_engine_ci90": ci}
    L += ["", "## 5. Decision quality on comparable support", "",
          f"Instances with the engine's own final tool outcome known and >= 1 other known tool: {n_inst}. Expected FULL of each "
          "chooser's pick among the known tools (mean of that tool's known outcomes on the instance):", ""]
    L += [f"- {k}: {float(sum(v)):.1f}" for k, v in dec.items()]
    L.append(f"- R-head minus engine: base-bootstrap 90 % CI [{ci[0]:.1f}, {ci[1]:.1f}]")
    L.append("- Caveat: the engine's choice is scored by its own full-pipeline outcome; alternatives by outcomes from other "
             "procedures (older engines, A0, diverse repairs), which this comparison cannot equalise.")

    # ---------------------------------------------------------------- 6. gate G-a (pre-declared)
    ga = (report["lobo"]["full"]["log_loss"] < report["lobo"]["b1"]["log_loss"]) and (sum(dec["full"]) >= sum(dec["engine"]))
    report["gate_G_a"] = {"passed": bool(ga), "rule": "R-head LOBO log loss < B1 AND comparable-support FULL >= engine"}
    L += ["", "## 6. Gate G-a", "", f"**{'PASSED' if ga else 'NOT PASSED'}** ({report['gate_G_a']['rule']}).", ""]
    os.makedirs(a.out, exist_ok=True)
    # ---------------------------------------------------------------- 7. the initial shared case store (init bases only)
    import glob
    from creature_forge.has_memory import episode_summary
    summ_recs = []
    for f in ENGINE_V5 + ENGINE_OLD:
        summ_recs += [r for r in rows_of(R(f)) if r.get("eligible") is not False and "engine" in r and "verification" in r
                      and base_of(r["instance_id"]) in init]
    pilots = []
    for f in sorted(glob.glob(R("s2_pilot*_A*.jsonl"))) + [R("s2DC_exp_A3.jsonl")]:
        pilots += [r for r in rows_of(f) if base_of(r["instance_id"]) in init and r.get("nemotron")]
    store = hc.CaseStore(rows, [d for r in pilots if (d := hc.agent_decision(r))], T=T,
                         meta={"built": "ds1_offline", "init_bases": sorted(init), "stream_bases_excluded": sorted(stream)},
                         frozen=True)
    store.summaries = [episode_summary(r) for r in summ_recs]
    store.save(os.path.join(a.out, "cases_init.json"))
    L += ["## 7. Initial case store", "",
          f"- {len(store.cases)} verified repair cases, {len(store.summaries)} investigation summaries (dossier support), "
          f"{len(store.decisions)} earlier scientist decisions (Stage-2 pilots on init bases, agent v1-v4)."]
    final = rl.RHead.fit(rows, "full", meta={"T": T, "bases": sorted({r['base'] for r in rows}), "fitted_on": "DS-1 init bases"})
    final.save(os.path.join(a.out, "rhead_init.json"))
    json.dump(report, open(os.path.join(a.out, "offline_report.json"), "w", encoding="utf-8"), indent=1)
    json.dump({"temperature": T, "misfit_threshold": thr}, open(os.path.join(a.out, "engine_v6_settings.json"), "w"), indent=1)
    open(os.path.join(a.out, "OFFLINE.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
