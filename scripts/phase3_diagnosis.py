"""Phase-3 diagnosis: read-only, exploratory analysis of the frozen causal-engineer held-out records (2026-10-18).

Nothing here is a registered test. The analyses motivate the phase-3 design (docs/HAS_SCIENTIST.md) and are labelled
exploratory and post hoc. Inputs (all read-only):
  experiments/causal_engineer/heldout/results_amend1/heldout_amend1_shard*.jsonl   (AI arms, amendment 1)
  experiments/causal_engineer/heldout/results_amend1/nonai_from_registered.jsonl   (non-AI arms, registered run)
  experiments/causal_engineer/heldout/instances/heldout_shard*.jsonl               (instances, repair matrices)
  artifacts/vm/ce3/ce/probe_dev.jsonl                                              (dev probe dataset; optional, git-ignored)
Outputs: experiments/causal_engineer/dev/phase3_diagnosis/{diagnosis.json, DIAGNOSIS.md}

Usage: python scripts/phase3_diagnosis.py [--out DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HELDOUT = ROOT / "experiments" / "causal_engineer" / "heldout"
PROBE = ROOT / "artifacts" / "vm" / "ce3" / "ce" / "probe_dev.jsonl"
REPAIRS_AT = 0.75            # the old bench's "repairing tool" label: walking >= 6/8 check seeds after a 160-rollout repair
STOP_LEFT = 100              # "stopped with budget left": at least this many rollouts unused at the end
ARMS = ["exhaustive", "learned", "scientist_think_mem", "scientist_think", "scientist_think_mem_learned", "random",
        "scientist_1shot_think", "expert"]
CLOSED_LOOP = ("scientist_think", "scientist_think_mem", "scientist_think_mem_learned")


def _jsonl(path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load() -> tuple[list[dict], dict]:
    ai = [r for f in sorted(glob.glob(str(HELDOUT / "results_amend1" / "heldout_amend1_shard*.jsonl"))) for r in _jsonl(f)]
    non = _jsonl(HELDOUT / "results_amend1" / "nonai_from_registered.jsonl")
    inst = {r["instance_id"]: r for f in glob.glob(str(HELDOUT / "instances" / "*.jsonl")) for r in _jsonl(f)}
    return ai + non, inst


def full(rec) -> bool:
    return rec["verification"]["status"] == "FULL_RECOVERY"


def repairing(inst, iid) -> set:
    return {t for t, v in inst[iid]["repair_matrix"].items() if v >= REPAIRS_AT}


def lineage(rec) -> list[dict]:
    """Designs from the initial robot to the submitted design (parent chain)."""
    ds = {d["index"]: d for d in rec["ledger"]["designs"]}
    i, out = rec["submitted_design"]["index"], []
    while i is not None and i in ds:
        out.append(ds[i])
        i = ds[i].get("parent")
    return out[::-1]


def repairs_of(designs) -> list[dict]:
    return [d for d in designs if str(d.get("source", "")).startswith("repair:")]


def decomposition(recs, inst) -> dict:
    out = {}
    for arm in ARMS:
        rs = [r for r in recs if r["policy"] == arm]
        cats = Counter()
        for r in rs:
            if full(r):
                continue
            R = repairing(inst, r["instance_id"])
            reps, lin = repairs_of(r["ledger"]["designs"]), repairs_of(lineage(r))
            if not reps:
                c = "no_repair"
            elif not any(d["tool"] in R for d in reps):
                c = "wrong_tools_only"
            elif not any(d["tool"] in R for d in lin):
                c = "right_tool_not_submitted"
            elif r["ledger"]["remaining"] >= STOP_LEFT:
                c = "right_tool_stopped_with_budget"
            else:
                c = "right_tool_budget_spent"
            cats[c] += 1
        out[arm] = {"n": len(rs), "full": int(sum(map(full, rs))), "non_full": dict(cats),
                    "mean_remaining": round(float(np.mean([r["ledger"]["remaining"] for r in rs])), 1)}
    return out


def lineage_rows(recs, inst) -> list[dict]:
    rows = []
    for r in recs:
        lr = repairs_of(lineage(r))
        if not lr:
            continue
        tools = [d["tool"] for d in lr]
        rows.append({"arm": r["policy"], "iid": r["instance_id"], "full": full(r), "roll": sum(d.get("rollouts", 0) for d in lr),
                     "any_repairing": any(t in repairing(inst, r["instance_id"]) for t in tools),
                     "injected": r["matching_tool"] in tools, "ai": r["policy"].startswith("scientist"),
                     "train_walking": lr[-1].get("train_walking")})
    return rows


def rate(rows) -> dict:
    n = len(rows)
    k = int(sum(x["full"] for x in rows))
    return {"full": k, "n": n, "rate": round(k / n, 3) if n else None}


def budget_curve(rows) -> dict:
    sel = [x for x in rows if x["any_repairing"]]
    bins = [(0, 150), (150, 300), (300, 450), (450, 600), (600, 800)]
    return {f"{lo}-{hi}": rate([x for x in sel if lo <= x["roll"] < hi]) for lo, hi in bins}


def injected_vs_compensating(rows, seed: int = 0) -> dict:
    inj = [x for x in rows if x["injected"]]
    comp = [x for x in rows if x["any_repairing"] and not x["injected"]]
    by = defaultdict(lambda: {"m": [], "c": []})
    for x in inj:
        by[x["iid"]]["m"].append(x["full"])
    for x in comp:
        by[x["iid"]]["c"].append(x["full"])
    d = [float(np.mean(v["m"]) - np.mean(v["c"])) for v in by.values() if v["m"] and v["c"]]
    rng = random.Random(seed)
    boots = sorted(float(np.mean([rng.choice(d) for _ in d])) for _ in range(5000))
    pos, neg = int(sum(x > 0 for x in d)), int(sum(x < 0 for x in d))
    n = pos + neg
    p = sum(math.comb(n, k) for k in range(pos, n + 1)) / 2 ** n if n else None
    return {"pooled": {"injected": rate(inj), "compensating": rate(comp)},
            "within_instance": {"instances": len(d), "mean_diff": round(float(np.mean(d)), 3),
                                "bootstrap95": [round(boots[124], 3), round(boots[4874], 3)],
                                "positive": pos, "negative": neg, "sign_test_one_sided_p": round(p, 4) if p is not None else None},
            "caveat": "exploratory association; arms choose tools from evidence that also predicts difficulty, and the "
                      "matching tool's subspace is the one the bench was screened with"}


def visible_evidence(recs, rows) -> dict:
    tw4 = [x for x in rows if x["train_walking"] == 4]
    stress = defaultdict(lambda: [0, 0])
    for r in recs:
        if not r["policy"].startswith("scientist"):
            continue
        sub = r["submitted_design"]["index"]
        tests = [e for e in r["policy_record"]["experiments"] if e["kind"] == "test" and e["design_index"] == sub]
        if tests:
            k = int(tests[-1]["n_walking"])
            stress[k][0] += int(full(r))
            stress[k][1] += 1
    return {"train_4of4_at_submission": rate(tw4),
            "stress_test_on_submitted": {str(k): {"full": v[0], "n": v[1]} for k, v in sorted(stress.items())}}


def first_repair(recs) -> dict:
    out = {}
    for arm in ARMS:
        rs = [r for r in recs if r["policy"] == arm]
        firsts = [repairs_of(r["ledger"]["designs"])[:1] for r in rs]
        firsts = [(r, f[0]) for r, f in zip(rs, firsts) if f]
        out[arm] = {"injected_first": int(sum(f["tool"] == r["matching_tool"] for r, f in firsts)), "with_repair": len(firsts)}
    return out


def predictions(recs) -> dict:
    c = Counter()
    for r in recs:
        if r["policy"] not in CLOSED_LOOP:
            continue
        for e in r["policy_record"]["experiments"]:
            if e["kind"] != "counterfactual" or not e.get("outcome"):
                continue
            q = e["outcome"]["quantities"]
            for p in e.get("predictions") or []:
                v = q.get(p["quantity"])
                if not v or v.get("delta") is None:
                    continue
                d, t = v["delta"], v["tolerance"]
                obs = "increase" if d > t else "decrease" if d < -t else "no_change"
                if obs == "no_change":
                    c["null_" + ("right" if p["direction"] == "no_change" else "wrong")] += 1
                elif p["direction"] != "no_change":
                    c["real_sign_" + ("right" if p["direction"] == obs else "wrong")] += 1
                else:
                    c["real_said_no_change"] += 1
    return dict(c)


def learnability() -> dict | None:
    """Leave-one-base-out kNN prediction of catalogue counterfactual effects from the initial observation (dev probe set)."""
    if not PROBE.exists():
        return None
    rows = _jsonl(PROBE)
    keys = sorted(k for k, v in rows[0]["observation"]["median"].items() if isinstance(v, (int, float)))
    cfs = ["foot_length_x1.3", "torso_mass_x0.75", "torque_limit_x1.6", "pitch_ref_-0.08", "freq_x0.85",
           "placement_gains_0.5", "leg_length_x0.85"]
    targets = ["time_upright", "capture_margin_over_L_mean", "pitch_mean", "step_freq_hz", "n_walking"]

    def val(o, t):
        return o["n_walking"] if t == "n_walking" else o["median"].get(t)
    X, idx = [], []
    for i, r in enumerate(rows):
        x = [r["observation"]["median"].get(k) for k in keys] + list(r["features"].values())
        if all(v is not None for v in x):
            X.append(x)
            idx.append(i)
    X = np.asarray(X, float)
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    bases = np.array([rows[i]["base_id"] for i in idx])
    out = {"n_instances": len(idx), "n_bases": len(set(bases)), "k": 7, "targets": {}}
    for t in targets:
        m0, mk = [], []
        for c in cfs:
            y = []
            for i in idx:
                o = rows[i]["counterfactuals"].get(c, {}).get("observation")
                a, b = (None if o is None else val(o, t)), val(rows[i]["observation"], t)
                y.append(np.nan if a is None or b is None else a - b)
            y = np.asarray(y, float)
            for b in set(bases):
                te, tr = (bases == b) & ~np.isnan(y), (bases != b) & ~np.isnan(y)
                if not te.any():
                    continue
                dist = ((X[te][:, None, :] - X[tr][None, :, :]) ** 2).sum(-1)
                pk = y[tr][np.argsort(dist, 1)[:, :7]].mean(1)
                m0 += list(np.abs(y[te]))
                mk += list(np.abs(y[te] - pk))
        out["targets"][t] = {"mae_no_change": round(float(np.mean(m0)), 4), "mae_knn_lobo": round(float(np.mean(mk)), 4)}
    return out


def render(res: dict) -> str:
    L = ["# Phase-3 diagnosis of the frozen causal-engineer held-out records",
         "",
         "Exploratory and post hoc (2026-10-18). Generated by `scripts/phase3_diagnosis.py` from frozen records; nothing here is a "
         "registered test. It motivates the phase-3 design in `docs/HAS_SCIENTIST.md`.",
         "",
         "## 1. Why non-FULL episodes failed (\"repairing tool\" = old matrix label, walking >= 6/8 at 160 rollouts)",
         "",
         "| arm | FULL | non-FULL categories | mean rollouts left |",
         "|---|---|---|---|"]
    for arm, d in res["decomposition"].items():
        L.append(f"| {arm} | {d['full']}/{d['n']} | {', '.join(f'{k} {v}' for k, v in sorted(d['non_full'].items()))} | "
                 f"{d['mean_remaining']} |")
    L += ["", "## 2. Optimiser budget vs verification (lineage includes a repairing tool; all arms)", "",
          "| lineage repair rollouts | FULL / n |", "|---|---|"]
    L += [f"| {k} | {v['full']}/{v['n']} ({v['rate']}) |" for k, v in res["budget_curve"].items()]
    ve = res["visible_evidence"]
    L += ["", "## 3. Policy-visible evidence at submission", "",
          f"- 4/4 training seeds walking: {ve['train_4of4_at_submission']['full']}/{ve['train_4of4_at_submission']['n']} FULL.",
          "- Last 20 s stress test on the submitted design (n_walking of 4 -> FULL / n): " +
          ", ".join(f"{k}: {v['full']}/{v['n']}" for k, v in ve["stress_test_on_submitted"].items()) + "."]
    iv = res["injected_vs_compensating"]
    w = iv["within_instance"]
    L += ["", "## 4. Injected-mechanism repairs vs other repairing tools (association only)", "",
          f"- Pooled: injected {iv['pooled']['injected']['full']}/{iv['pooled']['injected']['n']}, "
          f"compensating {iv['pooled']['compensating']['full']}/{iv['pooled']['compensating']['n']}.",
          f"- Within instance ({w['instances']} instances with both): mean difference {w['mean_diff']}, bootstrap 95% "
          f"{w['bootstrap95']}, {w['positive']} vs {w['negative']}, one-sided sign test p = {w['sign_test_one_sided_p']}.",
          f"- Caveat: {iv['caveat']}. A controlled test is designed in docs/HAS_SCIENTIST.md (MKV study)."]
    L += ["", "## 5. First repair targets the injected mechanism", "", "| arm | injected first / episodes with a repair |", "|---|---|"]
    L += [f"| {a} | {v['injected_first']}/{v['with_repair']} |" for a, v in res["first_repair"].items()]
    p = res["predictions"]
    real = p.get("real_sign_right", 0) + p.get("real_sign_wrong", 0)
    null = p.get("null_right", 0) + p.get("null_wrong", 0)
    L += ["", "## 6. Direction predictions of the closed-loop arms", "",
          f"- Real effects (beyond tolerance), model predicted a change: sign right {p.get('real_sign_right', 0)}/{real}.",
          f"- Real effects predicted as no change: {p.get('real_said_no_change', 0)}.",
          f"- Null effects (within tolerance): predicted a change {p.get('null_wrong', 0)}/{null}."]
    lb = res["learnability"]
    if lb:
        L += ["", f"## 7. Learnability of counterfactual effects (dev probe set, {lb['n_instances']} instances, {lb['n_bases']} bases, "
              "leave-one-base-out kNN)", "", "| target | MAE predict no change | MAE kNN |", "|---|---|---|"]
        L += [f"| {t} | {v['mae_no_change']} | {v['mae_knn_lobo']} |" for t, v in lb["targets"].items()]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "experiments" / "causal_engineer" / "dev" / "phase3_diagnosis"))
    a = ap.parse_args()
    recs, inst = load()
    rows = lineage_rows(recs, inst)
    res = {"version": "phase3_diagnosis_v1", "n_records": len(recs), "decomposition": decomposition(recs, inst),
           "budget_curve": budget_curve(rows), "visible_evidence": visible_evidence(recs, rows),
           "injected_vs_compensating": injected_vs_compensating(rows), "first_repair": first_repair(recs),
           "predictions": predictions(recs), "learnability": learnability()}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diagnosis.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    (out / "DIAGNOSIS.md").write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
