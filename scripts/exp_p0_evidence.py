"""Experience-learning P0 evidence export (read-only; no new experimental data).

Re-derives, from the same stored records and the same code, the row-level provenance behind the committed P0 outputs:
  * every outcome row with source file, line, file SHA-256, procedure, budget and verifier fields;
  * every exclusion (record- and file-level) with its reason;
  * the level-S / level-P comparable rows;
  * the DS-1 `cases_init.json` cohort rebuilt row by row (DS-1 offline construction) and mapped to the P0 corpus;
  * per-case fold assignments and predictions of every P0 analysis, with shuffle and hard-negative details.
It FAILS CLOSED unless the re-derived rows equal the committed `outcomes.csv` and every aggregate equals the committed
`analysis.json`. It never simulates, never calls a model and never opens a file the audit excluded.

Usage: python scripts/exp_p0_evidence.py [--vm-root ../Creature-Forge/artifacts/vm]
Writes experiments/causal_engineer/dev/experience_p0/evidence/.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from creature_forge import experience_audit as ea          # noqa: E402
from creature_forge import experience_p0 as p0             # noqa: E402
from creature_forge import has_cases as hc                 # noqa: E402
from creature_forge import repair_learning as rl           # noqa: E402

OUT = "experiments/causal_engineer/dev/experience_p0"
EV = os.path.join(OUT, "evidence")
CASES_INIT = "experiments/causal_engineer/dev/hdb/ds1/cases_init.json"
_spec = importlib.util.spec_from_file_location("exp_p0_audit", os.path.join(os.path.dirname(__file__), "exp_p0_audit.py"))
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


class Mismatch(RuntimeError):
    pass


def check(cond: bool, what: str) -> None:
    if not cond:
        raise Mismatch(what)


def jhash(x) -> str | None:
    return None if not x else hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()[:16]


def write_csv(name: str, rows: list[dict]) -> None:
    os.makedirs(EV, exist_ok=True)
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(EV, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


# ------------------------------------------------------------------------------------------------ row-level evidence
def evidence_fields(rec: dict) -> dict:
    """Procedure, budget and verifier fields of one stored episode record, wherever its schema keeps them."""
    eng = ea.engine_of(rec)
    led = eng.get("ledger") or rec.get("ledger") or {}
    v = rec.get("verification")
    vs = v["summary"] if isinstance(v, dict) and isinstance(v.get("summary"), dict) else (v if isinstance(v, dict) else {})
    ro = vs.get("rollouts") or {}
    h = rec.get("harness") or {}
    return {"provenance": rec.get("provenance"), "engine_settings_sha16": jhash(eng.get("settings")),
            "v6_settings_sha16": jhash(rec.get("v6_settings") or eng.get("v6")), "stop_rule": json.dumps(rec.get("stop_rule"))
            if rec.get("stop_rule") is not None else None, "policy": json.dumps(rec.get("policy"))[:120] if rec.get("policy") else None,
            "plant_total": led.get("total"), "plant_used": led.get("used"), "twin_total": (led.get("twin") or {}).get("total"),
            "twin_used": (led.get("twin") or {}).get("used"), "verifier": "full_recovery_v1 (stored status)",
            "walking_frac": vs.get("walking_frac", rec.get("walking_frac")), "validation_rollouts": ro.get("validation"),
            "confirmation_rollouts": ro.get("confirmation"), "reasons": "; ".join(vs.get("reasons") or [])[:200] or None,
            "submitted_index": rec.get("submitted", (rec.get("repair") or {}).get("design")),
            "harness_arm": h.get("ta1_arm"), "do1_arm": (h.get("do1") or {}).get("arm"), "replicate": h.get("replicate"),
            "noise_seed": h.get("noise_seed")}


def derive_rows(roots: dict, split: dict) -> tuple[list[dict], list[dict], dict]:
    """The audit's outcome rows again, now with (file, line, sha256) and evidence fields; plus every exclusion."""
    allowed = ea.dev_bases(split)
    man = ea.manifest(roots)
    sha = {(m["root"], m["path"]): m["sha256"] for m in man}
    rows, excl, bench_of_origin = [], [], {}
    for m in man:
        if m["kind"] == "superseded" and m["path"].endswith("mkv2_partial.jsonl"):
            first = ea.rows_of(os.path.join(roots[m["root"]], m["path"]))[:1]
            bench_of_origin["mkv2_partial.jsonl"] = (first[0].get("bench") or "hdb_v1") if first else None
        if m["kind"] not in ("episode", "harness"):
            if m["kind"] in ("superseded", "mirror", "ce_instances", "stopdata"):
                excl.append({"level": "file", "path": m["path"], "sha256": m["sha256"], "records": m["lines"],
                             "reason": {"superseded": "superseded partial / older version of a registered file",
                                        "mirror": "mirror copy; canonical copy used ("
                                                  + ("identical" if m.get("identical_to_canonical") else "DIFFERS") + ")",
                                        "ce_instances": "fault-bench instance builds; the probe set carries the same matrices",
                                        "stopdata": "re-measured evidence; labels are copies of recorded statuses"}[m["kind"]]})
            continue
        for ln, r in enumerate(ea.rows_of(os.path.join(roots[m["root"]], m["path"])), start=1):
            base = ea.base_of(r.get("instance_id", ""))
            src = {"path": m["path"], "corpus": m["corpus"], "kind": m["kind"]}
            if base not in allowed:
                excl.append({"level": "record", "path": m["path"], "line": ln, "iid": r.get("instance_id"),
                             "reason": "base outside the 48 development bases"})
                continue
            bench_of_origin[os.path.basename(m["path"])] = r.get("bench") or "hdb_v1"
            row = ea.outcome_row(r, src)
            if row is None:
                excl.append({"level": "record", "path": m["path"], "line": ln, "iid": r["instance_id"], "arm": r.get("arm") or r.get("condition"),
                             "reason": "plant not eligible (physics eligibility false)" if r.get("eligible") is False else "no verification status"})
                continue
            rows.append({"file": m["path"], "root": m["root"], "line": ln, "file_sha256": sha[(m["root"], m["path"])],
                         **{k: row[k] for k in ("corpus", "kind", "arm", "bench", "iid", "base", "family", "engine", "procedure",
                                                "oracle", "tool", "status", "full")}, **evidence_fields(r)})
    for alias, target in ea.ORIGIN_ALIAS.items():
        bench_of_origin.setdefault(alias, bench_of_origin.get(target))
    for m in man:
        if m["kind"] != "stopcal":
            continue
        for ln, r in enumerate(ea.rows_of(os.path.join(roots[m["root"]], m["path"])), start=1):
            if r["base_id"] not in allowed:
                excl.append({"level": "record", "path": m["path"], "line": ln, "iid": r["instance_id"], "reason": "base outside the 48 development bases"})
                continue
            row = ea.stopcal_rows([r], {"path": m["path"], "corpus": m["corpus"]}, bench_of_origin)[0]
            rows.append({"file": m["path"], "root": m["root"], "line": ln, "file_sha256": m["sha256"],
                         **{k: row[k] for k in ("corpus", "kind", "arm", "bench", "iid", "base", "family", "engine", "procedure",
                                                "oracle", "tool", "status", "full")},
                         "verifier": "full_recovery_v1 via hdb_bench.verify (stop calibration build)", "origin": r.get("origin"),
                         "design_source": r.get("source"), "condition": r.get("condition"),
                         "plant_total": None, "plant_used": None, "twin_used": None})
    for p, why in ea.EXCLUDED:
        excl.append({"level": "file (never opened)", "path": p, "reason": why})
    return rows, excl, bench_of_origin


def compare_to_committed(rows: list[dict]) -> None:
    with open(os.path.join(OUT, "outcomes.csv"), encoding="utf-8") as fh:
        committed = collections.Counter((r["source"], r["arm"], r["iid"], r["tool"], r["status"]) for r in csv.DictReader(fh))
    mine = collections.Counter((r["file"], str(r["arm"]) if r["arm"] is not None else "", r["iid"], r["tool"] or "", r["status"])
                               for r in rows)
    check(sum(committed.values()) == len(rows) == 2587, f"row count {len(rows)} vs committed {sum(committed.values())}")
    check(committed == mine, "re-derived outcome rows differ from the committed outcomes.csv")


def comparable_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    comp = ea.comparability([{"bench": r["bench"], "iid": r["iid"], "tool": r["tool"], "full": r["full"], "engine": r["engine"],
                              "procedure": r["procedure"], "oracle": r["oracle"], "noise_seed": r.get("noise_seed")} for r in rows])
    inst, out = [], []
    for (bench, iid), lv in sorted(comp.items()):
        for level in ("S", "P"):
            tools = lv[level]
            if len(tools) < 2:
                continue
            eng = lv["P_engine"]
            inst.append({"level": level, "bench": bench, "iid": iid, "base": ea.base_of(iid), "engine": eng if level == "P" else "harness",
                         "tools": json.dumps({t: [int(x) for x in v] for t, v in sorted(tools.items())}), "informative": ea.informative(tools)})
            for r in rows:
                if r["bench"] != bench or r["iid"] != iid or not r["tool"]:
                    continue
                if level == "S" and not r["procedure"].startswith("ta1:"):
                    continue
                if level == "P" and not (r["engine"] == eng and r["procedure"] in ("engine", "nemotron") and not r["oracle"]):
                    continue
                out.append({"level": level, **r})
    return inst, out


# ------------------------------------------------------------------------------------------------ DS-1 cohort
def rebuild_cases_init(roots: dict, split: dict, rows: list[dict]) -> dict:
    """DS-1 offline row construction (scripts/ds1_offline.py §3), with the source of each row; mapped to the P0 corpus."""
    R = lambda f: os.path.join(roots["vm"], "hdb/artifacts/hdb", f)    # noqa: E731
    stream = set(hc.ds1_stream_bases(split))
    init = set(split["experience_bases"]) - stream
    sit = {}
    for f in ("fresh_A1c5.jsonl", "vs5_A1c.jsonl", "s2DC_exp_A1e.jsonl"):
        for ln, r in enumerate(ea.rows_of(R(f)), start=1):
            if r.get("eligible") is False or "engine" not in r or hc.base_of(r["instance_id"]) not in init:
                continue
            sit.setdefault(r["instance_id"], (f, ln, r))
    built = []

    def add(iid, tool, status, proc, f, ln, extra=None):
        if iid not in sit or tool not in rl.TOOLS:
            return
        built.append({"iid": iid, "base": hc.base_of(iid), "tool": tool, "procedure": proc, "full": status == "FULL_RECOVERY",
                      "src_file": "hdb/artifacts/hdb/" + f, "src_line": ln, **(extra or {})})
    for iid, (f, ln, r) in sit.items():
        add(iid, hc.final_tool(r), r["verification"]["status"], "engine_final", f, ln, {"arm": r.get("arm"), "engine": r["engine"]["version"]})
    for proc, files in (("engine_old", ("vs4_A1c.jsonl", "vs4_a1.jsonl", "vs4_A1f.jsonl", "vs2_a1.jsonl")),
                        ("a0", ("fresh_A0.jsonl", "vs4_A0.jsonl"))):
        for f in files:
            for ln, r in enumerate(ea.rows_of(R(f)), start=1):
                if r.get("eligible") is not False and "verification" in r:
                    add(r["instance_id"], hc.final_tool(r), r["verification"]["status"], proc, f, ln,
                        {"arm": r.get("arm"), "engine": (r.get("engine") or {}).get("version"), "stop_rule": json.dumps(r.get("stop_rule"))})
    n_mkv = 0
    for ln, r in enumerate(ea.rows_of(R("stopcal.jsonl")), start=1):
        if r["source"] == "initial":
            continue
        if r.get("origin", "").startswith("mkv"):
            n_mkv += 1
            continue
        t = r["source"].split(":")[-1]
        add(r["instance_id"], t if t in rl.TOOLS else hc.PROBE_TOOL.get(t), r["status"], "diverse", "stopcal.jsonl", ln,
            {"arm": "stopcal", "origin": r.get("origin"), "design_source": r["source"], "condition": r.get("condition")})
    ci = json.load(open(CASES_INIT, encoding="utf-8"))["cases"]
    check(len(built) == len(ci) == 947, f"rebuilt {len(built)} vs cases_init {len(ci)}")
    check([(b["iid"], b["tool"], b["procedure"], b["full"]) for b in built] == [(c["iid"], c["tool"], c["procedure"], c["full"]) for c in ci],
          "rebuilt DS-1 rows differ from cases_init.json")
    key = {(r["file"], r["line"]): r for r in rows}
    for b in built:
        p = key.get((b["src_file"], b["src_line"]))
        b["in_p0_corpus"] = p is not None
        if p:
            b.update({"p0_procedure": p["procedure"], "p0_engine": p["engine"], "p0_oracle": p["oracle"], "p0_bench": p["bench"],
                      "plant_used": p.get("plant_used"), "twin_used": p.get("twin_used"), "status": p["status"],
                      "confirmation_rollouts": p.get("confirmation_rollouts")})
    # same-procedure-label candidates: one instance, one DS-1 label, >= 2 tools
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for b in built:
        by[(b["iid"], b["procedure"])][b["tool"]].append(b)
    cand = []
    for (iid, label), tools in sorted(by.items()):
        if len(tools) < 2:
            continue
        rates = {t: float(np.mean([x["full"] for x in v])) for t, v in tools.items()}
        procs = sorted({(x.get("arm"), x.get("p0_engine"), x.get("stop_rule"), x.get("design_source", "").split(":")[0] if x.get("design_source") else None)
                        for v in tools.values() for x in v}, key=str)
        engines = {x.get("p0_engine") for v in tools.values() for x in v}
        if label == "diverse":
            why = ("stop-calibration designs generated inside engine-v2 episodes by different steps (twin search, counterfactual probe, "
                   "plant repair); no per-design budget; tool not assigned -> P0 level X")
        else:
            why = (f"one DS-1 label pools {len({p[0] for p in procs})} arm(s) and engine version(s) {sorted(map(str, engines))} with "
                   "different stop rules; tool chosen by each policy, remaining budget endogenous -> not level S")
        cand.append({"iid": iid, "base": hc.base_of(iid), "ds1_label": label, "tools": json.dumps({t: [int(x["full"]) for x in v] for t, v in sorted(tools.items())}),
                     "full_rates_differ": len(set(rates.values())) > 1,
                     "rows": "; ".join(f"{x['tool']}<-{x['src_file'].split('/')[-1]}:{x['src_line']} arm={x.get('arm')} engine={x.get('p0_engine')} "
                                       f"stop={x.get('stop_rule')} src={x.get('design_source')} plant_used={x.get('plant_used')} status={x.get('status')}"
                                       for v in tools.values() for x in v),
                     "why_not_level_S": why})
    inst = sorted({b["iid"] for b in built})
    multi = [i for i in inst if len({b["tool"] for b in built if b["iid"] == i}) >= 2]
    cinst = {c["iid"] for c in cand}
    summary = {"rows": len(built), "instances": len(inst), "bases": len({hc.base_of(i) for i in inst}), "multi_tool_instances": len(multi),
               "same_label_groups": len(cand), "same_label_instances": len(cinst), "same_label_bases": len({hc.base_of(i) for i in cinst}),
               "same_label_instances_with_differing_full": len({c["iid"] for c in cand if c["full_rates_differ"]}),
               "same_label_groups_by_label": dict(collections.Counter(c["ds1_label"] for c in cand)),
               "rows_found_in_p0_corpus": sum(b["in_p0_corpus"] for b in built), "mkv_origin_stopcal_excluded_by_ds1": n_mkv}
    return {"rows": built, "candidates": cand, "summary": summary}


# ------------------------------------------------------------------------------------------------ per-case predictions
def per_case(roots: dict, morph: dict, committed: dict) -> dict:
    probe = ea.rows_of(os.path.join(roots["vm"], "ce3/ce/probe_dev.jsonl"))
    ds = p0.ce_dataset(probe, morph)
    sp, Y, base, fault = ds["space"], ds["Y"], ds["base"], ds["fault"]
    iids = [r["instance_id"] for r in probe]
    gen = np.array([ea.generator_group(b) for b in base])
    schemes = {"LOBO": base, "LOFO (fault family held out)": fault, "LOGO (generator group held out)": gen}
    tools = ds["tools"]
    out, preds = [], {}
    cd = committed["decision_proxy"]
    for sname, og in schemes.items():
        for m, use in audit.CE_METHODS.items():
            pr = p0.predict(sp, use, Y, base, og)
            d = p0.decision_eval(pr, Y)
            preds[(sname, m)] = (pr, d)
            check(p0.summarize_decision(d) == cd[sname][m]["all"], f"decision summary differs: {sname}/{m}")
            check(pr["k"] == cd[sname][m]["k"], f"fold k differs: {sname}/{m}")
            for i in range(len(Y)):
                fold = str(og[i])
                out.append({"scheme": sname, "method": m, "fold_heldout_group": fold, "k": pr["k"].get(fold), "iid": iids[i],
                            "base": base[i], "fault": fault[i], "generator": gen[i], "pick": tools[d["pick"][i]], "pi0": tools[d["pi0"][i]],
                            "v_mem": int(d["v_mem"][i]), "v_pi0": int(d["v_pi0"][i]), "best": int(d["best"][i]),
                            "gate_sim": round(float(d["gate_sim"][i]), 6), "gate_benefit": round(float(d["gate_benefit"][i]), 6),
                            **{f"p:{t}": round(float(pr["P"][i, j]), 6) for j, t in enumerate(tools)},
                            **{f"y:{t}": int(Y[i, j]) for j, t in enumerate(tools)}})
    write_csv("ce_per_case_predictions.csv", out)
    rng = np.random.default_rng(p0.SEED)          # same generator sequence as exp_p0_audit.decision_analysis
    shuf = []
    for m in ("obs_morph", "interv"):
        pr_real, _ = preds[("LOBO", m)]
        vals = []
        for perm in range(p0.N_SHUFFLE):
            pr = p0.predict(sp, audit.CE_METHODS[m], Y, base, base, shuffle_rng=rng, k_fixed=pr_real["k"])
            vals.append(float(p0.decision_eval(pr, Y)["v_mem"].mean()))
            shuf.append({"method": m, "permutation": perm, "decision_value": round(vals[-1], 6)})
        check(round(float(np.mean(vals)), 4) == cd["shuffled_LOBO"][m]["shuffled_mean"], f"shuffle mean differs: {m}")
    write_csv("ce_shuffled_permutations.csv", shuf)
    det: list = []
    hn = p0.hard_negative_separation(sp, Y, base, ("obs", "morph"), {"interv": ("obs", "morph", "cf"), "obs_morph": ("obs", "morph")}, details=det)
    check(hn == cd["hard_negative_LOBO"], "hard-negative aggregate differs")
    write_csv("ce_hard_negative_queries.csv", [{"query": iids[x["query"]], "hard_positive": iids[x["hard_positive"]],
                                                 "hard_negative": iids[x["hard_negative"]],
                                                 **{k: v for k, v in x.items() if k.startswith("separated")}} for x in det])
    # HDB identifiability panel
    ident = ea.rows_of(os.path.join(roots["vm"], "hdb/artifacts/hdb/ident_v2_all.jsonl"))
    kept = [r for r in ident if not r.get("skipped") and r.get("eligible") and r["family"] in p0.HDB_FAMILIES]
    excluded_ident = [{"iid": r["instance_id"], "reason": "skipped record" if r.get("skipped") else
                       ("plant not eligible" if not r.get("eligible") else "family not a dev family")}
                      for r in ident if r not in kept]
    write_csv("ident_exclusions.csv", excluded_ident)
    dsi = p0.ident_dataset(ident, morph)
    spi, y, bi = dsi["space"], dsi["y"], dsi["base"]
    check(len(kept) == len(y), "ident row count")
    geni = np.array([ea.generator_group(b) for b in bi])
    C = len(p0.HDB_FAMILIES)
    rowsi = []
    cdi = committed["diagnostic_hdb"]
    for sname, og in {"LOBO": bi, "LOGO (generator group held out)": geni}.items():
        for m, use in audit.ID_METHODS.items():
            pr = p0.class_predict(spi, use, y, C, bi, og)
            met = p0.class_metrics(pr["P"], y)
            check({k: v for k, v in cdi[sname][m].items() if k != "k"} == met, f"diagnostic metrics differ: {sname}/{m}")
            for i in range(len(y)):
                rowsi.append({"scheme": sname, "method": m, "fold_heldout_group": str(og[i]), "k": pr["k"].get(str(og[i])),
                              "iid": kept[i]["instance_id"], "base": bi[i], "generator": geni[i], "family": p0.HDB_FAMILIES[y[i]],
                              "top": p0.HDB_FAMILIES[int(pr["P"][i].argmax())],
                              **{f"p:{f}": round(float(pr["P"][i, j]), 6) for j, f in enumerate(p0.HDB_FAMILIES)}})
        for name, Q in dsi["posterior"].items():
            check(p0.class_metrics(Q, y) == cdi[sname][f"model_posterior[{name}] (no memory)"], f"posterior metrics differ: {name}")
    write_csv("ident_per_case_predictions.csv", rowsi)
    write_csv("ident_model_posteriors.csv", [{"iid": kept[i]["instance_id"], "base": bi[i], "family": p0.HDB_FAMILIES[y[i]],
                                              **{f"{name}:{f}": round(float(Q[i, j]), 6) for name, Q in dsi["posterior"].items()
                                                 for j, f in enumerate(p0.HDB_FAMILIES)}} for i in range(len(y))])
    return {"ce_cases": len(Y), "ident_cases": len(y), "ident_excluded": len(excluded_ident), "hard_negative_queries": len(det)}


def environment() -> dict:
    import platform
    vers: dict = {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__}
    try:
        import mujoco
        vers["mujoco (installed, not called; tripwire-tested)"] = mujoco.__version__
    except ImportError:
        vers["mujoco"] = None
    return vers


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vm-root", default=audit.DEFAULT_VM)
    a = ap.parse_args()
    roots = {"vm": os.path.abspath(a.vm_root), "repo": os.path.abspath(".")}
    split = audit.load_split()
    committed = json.load(open(os.path.join(OUT, "analysis.json"), encoding="utf-8"))
    inv = json.load(open(os.path.join(OUT, "inventory.json"), encoding="utf-8"))
    rows, excl, _ = derive_rows(roots, split)
    compare_to_committed(rows)
    write_csv("p0_outcome_rows.csv", rows)
    write_csv("p0_exclusions.csv", excl)
    write_csv("p0_comparison_exclusions.csv", [{"file": r["file"], "line": r["line"], "iid": r["iid"], "arm": r["arm"],
                                                "reason": "oracle-informed condition" if r["oracle"] else "no resolvable tool"}
                                               for r in rows if r["oracle"] or not r["tool"]])
    inst, comp_rows = comparable_rows(rows)
    check(sum(1 for i in inst if i["level"] == "P") == inv["support"]["P"]["instances_ge2_tools"], "level-P instance count")
    check(sum(1 for i in inst if i["level"] == "P" and i["informative"]) == inv["support"]["P"]["informative_instances"], "level-P informative")
    write_csv("p0_level_SP_instances.csv", inst)
    write_csv("p0_level_SP_rows.csv", comp_rows)
    ds1 = rebuild_cases_init(roots, split, rows)
    write_csv("ds1_cases_init_rows_with_sources.csv", ds1["rows"])
    write_csv("ds1_same_label_candidates.csv", ds1["candidates"])
    pc = per_case(roots, inv["morphology_table"], committed)
    p0_inst = {(r["iid"]) for r in rows}
    ds1_inst = {r["iid"] for r in ds1["rows"]}
    rec = {"ds1_cases_init": ds1["summary"], "ds1_instances_in_p0": len(ds1_inst & p0_inst),
           "p0": {"outcome_rows": len(rows), "plants": len({(r["bench"], r["iid"]) for r in rows}), "bases": len({r["base"] for r in rows}),
                  "record_exclusions": sum(1 for e in excl if e["level"] == "record"),
                  "comparison_exclusions_oracle": sum(1 for r in rows if r["oracle"]),
                  "comparison_exclusions_no_tool": sum(1 for r in rows if not r["tool"] and not r["oracle"]),
                  "level_P_instances": sum(1 for i in inst if i["level"] == "P"),
                  "level_P_informative": sum(1 for i in inst if i["level"] == "P" and i["informative"]),
                  "level_P_informative_bases": len({i["base"] for i in inst if i["level"] == "P" and i["informative"]}),
                  "level_S_instances": sum(1 for i in inst if i["level"] == "S")},
           "ds1_same_label_instances_by_p0_level": dict(collections.Counter(
               "P" if any(i["iid"] == c and i["level"] == "P" for i in inst) else "X"
               for c in sorted({c["iid"] for c in ds1["candidates"]}))),
           "per_case": pc, "environment": environment(), "all_checks_against_committed_outputs": "passed"}
    json.dump(rec, open(os.path.join(EV, "reconciliation_summary.json"), "w", encoding="utf-8"), indent=1, default=str)
    print(json.dumps(rec, indent=1, default=str))


if __name__ == "__main__":
    main()
