"""Leave-one-base-out evaluation of the Level C repair-effect predictor against non-learned baselines (numpy only).

Purpose. For each of the bases in the probe dataset: train on the other bases, rank the 10 repair tools for the held-out base's instances,
and score the ranking against the MEASURED repair matrix (target: walked on >= 6/8 check seeds). Standardisation, lambda selection and
all fitting use the training fold only. Fault labels (joined from the dev instance files by instance_id) are used ONLY for the
per-fault breakdown of the report, never as an input.

Trust boundary. Reads local git-ignored JSONL; writes one JSON and one Markdown report; no network, no MuJoCo. Verdict text is generated
from the numbers (a learned model "beats" the strongest simple baseline only if the paired bootstrap 95% CI excludes 0).
"""
from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):    # tiny matrices: BLAS threading is 70x slower here
    os.environ.setdefault(_v, "1")

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from creature_forge import ce_policies as cp                     # noqa: E402
from creature_forge import repair_learner as rl                  # noqa: E402

SEED = 20261017
N_BOOT = 1000
CHANCE_SEEDS = 20
N_SHUFFLE = 3
CURVE_SIZES = (3, 6, 9, 11)
CURVE_REPS = 5
PROB_MODELS = ("prior", "knn", "logistic", "mlp_ensemble")
RANK_ONLY = ("expert_rules", "cf_heuristic", "random")
METRICS = ("top1", "top3", "mrr", "brier")


def load_rows(path: str) -> list[dict]:
    """Probe rows with `features` REPLACED by the body features of the robot under investigation (`ce_memory.robot_features`), which
    is what a policy computes at runtime; the stored field describes the creature before its earlier recovery (fixed 2026-10-17)."""
    from creature_forge.ce_memory import robot_features
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in rows:
        r["features_stored"] = r.get("features")
        r["features"] = robot_features(r)
    return rows


def load_faults(pattern: str) -> dict:
    out = {}
    for f in sorted(glob.glob(pattern)):
        for l in Path(f).read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                if "instance_id" in d and "fault" in d:
                    out[d["instance_id"]] = d["fault"]
    return out


# ------------------------------------------------------------------------------------------------ baselines
def expert_matrix(rows) -> np.ndarray:
    pos = {t: i for i, t in enumerate(cp.FALLBACK_ORDER)}
    S = np.zeros((len(rows), len(rl.TOOLS)))
    for i, r in enumerate(rows):
        sc, _ = cp.expert_scores(r["observation"], (r.get("robot") or {}).get("body") or {})
        S[i] = [sc.get(t, 0.0) - 1e-3 * pos.get(t, 99) for t in rl.TOOLS]
    return S


def cf_matrix(rows) -> np.ndarray:
    """Exhaustive policy's order: available counterfactuals by (more walking, fewer falls, more time upright), catalogue order ties;
    tools without an available counterfactual (stride, refused) follow in FALLBACK_ORDER."""
    pos = {t: i for i, t in enumerate(cp.FALLBACK_ORDER)}
    order = {c: i for i, c in enumerate(rl.CF_IDS)}
    S = np.zeros((len(rows), len(rl.TOOLS)))
    for i, r in enumerate(rows):
        cfs = []
        for cid, res in (r.get("counterfactuals") or {}).items():
            if isinstance(res, dict) and "deltas" in res:
                cfs.append((cid, cp._cf_score({"deltas_vs_current": res["deltas"]})))
        cfs.sort(key=lambda c: (tuple(-x for x in c[1]), order[c[0]]))
        score = {t: -1.0 - 1e-3 * pos.get(t, 99) for t in rl.TOOLS}
        for k, (cid, _) in enumerate(cfs):
            score[cp.CF_TO_TOOL[cid]] = 100.0 - k
        S[i] = [score[t] for t in rl.TOOLS]
    return S


# ------------------------------------------------------------------------------------------------ metrics
def rank_metrics(S: np.ndarray, Y: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Per instance [top1, top3, mrr] (NaN if no repairing tool among measured tools)."""
    out = np.full((len(S), 3), np.nan)
    for i in range(len(S)):
        s = np.where(M[i] > 0, S[i], -np.inf)
        order = np.argsort(-s, kind="stable")
        ok = [Y[i, j] > 0 and M[i, j] > 0 for j in order]
        if any(ok):
            r = ok.index(True) + 1
            out[i] = [r == 1, r <= 3, 1.0 / r]
    return out


def random_metrics(Y, M) -> np.ndarray:
    acc = np.zeros((len(Y), 3))
    for s in range(CHANCE_SEEDS):
        rng = np.random.default_rng(SEED + s)
        acc += np.nan_to_num(rank_metrics(rng.random(Y.shape), Y, M))
    elig = np.nan_to_num(rank_metrics(np.zeros(Y.shape), Y, M)[:, 0], nan=-1) >= 0
    out = acc / CHANCE_SEEDS
    out[~elig] = np.nan
    return out


def prob_stats(P, Y, M):
    Pc = np.clip(P, 1e-4, 1 - 1e-4)
    se = (((P - Y) ** 2) * M).sum(1)
    ll = ((-(Y * np.log(Pc) + (1 - Y) * np.log(1 - Pc))) * M).sum(1)
    return se, ll, M.sum(1)


def auroc(score, positive) -> float | None:
    score, positive = np.asarray(score, float), np.asarray(positive, bool)
    npos, nneg = positive.sum(), (~positive).sum()
    if npos == 0 or nneg == 0:
        return None
    order = np.argsort(score, kind="stable")
    ranks = np.empty(len(score))
    sorted_s = score[order]
    i = 0
    while i < len(score):
        j = i
        while j + 1 < len(score) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[positive].sum() - npos * (npos + 1) / 2) / (npos * nneg))


class Result:
    """Out-of-fold per-instance results of one model."""

    def __init__(self, rm, P=None, spread=None, Y=None, M=None):
        self.rm, self.P, self.spread = rm, P, spread
        if P is not None:
            self.se, self.ll, self.npairs = prob_stats(P, Y, M)


def per_base_sums(res: Result, bases: np.ndarray, ubases: list):
    """(nb, 4, 2) numerators/denominators for top1, top3, mrr, brier per base."""
    A = np.zeros((len(ubases), 4, 2))
    for k, b in enumerate(ubases):
        idx = bases == b
        for m in range(3):
            v = res.rm[idx, m]
            A[k, m] = [np.nansum(v), np.sum(~np.isnan(v))]
        if res.P is not None:
            A[k, 3] = [res.se[idx].sum(), res.npairs[idx].sum()]
    return A


def boot_idx(nb: int) -> np.ndarray:
    return np.random.default_rng(SEED).integers(0, nb, size=(N_BOOT, nb))


def ci(vals) -> list:
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def stat_from(A, idx, m):
    num, den = A[idx, m, 0].sum(1), A[idx, m, 1].sum(1)
    return num / np.maximum(den, 1e-12)


# ------------------------------------------------------------------------------------------------ fitting
def make_model(name, seed=0, fixed_lam=False):
    if name == "logistic":
        return rl.LogisticModel(lam=rl.LogisticModel.DEFAULT_LAMBDA if fixed_lam else None)
    if name == "mlp_ensemble":
        return rl.MLPModel(seed=seed)
    return rl.MODEL_FACTORIES[name]()


def fit_predict(name, Xtr, Ytr, Mtr, gtr, Xte, seed=0, fixed_lam=False):
    m = make_model(name, seed, fixed_lam).fit(Xtr, Ytr, Mtr, groups=gtr)
    return m.predict_proba(Xte)


def run_setting(setting, rows, Y, M, bases, expert, cf, log):
    n = len(rows)
    Xraw = np.stack([rl.build_features(r, setting)[0] for r in rows])
    preds = {k: np.zeros((n, len(rl.TOOLS))) for k in PROB_MODELS}
    spread = np.zeros((n, len(rl.TOOLS)))
    shuf = {(k, s): np.zeros((n, len(rl.TOOLS))) for k in ("logistic", "mlp_ensemble") for s in range(N_SHUFFLE)}
    lams = {}
    for fold, (tr, te, b) in enumerate(rl.lobo_splits(bases)):
        assert not set(bases[tr]) & set(bases[te])
        prep = rl.Preprocessor().fit(Xraw[tr])
        Xtr, Xte = prep.transform(Xraw[tr]), prep.transform(Xraw[te])
        for k in PROB_MODELS:
            m = make_model(k, seed=SEED % 997).fit(Xtr, Y[tr], M[tr], groups=bases[tr])
            P, S = m.predict_proba(Xte)
            preds[k][te] = P
            if S is not None:
                spread[te] = S
            if k == "logistic":
                lams[str(b)] = m.lam_
        for s in range(N_SHUFFLE):
            perm = np.random.default_rng(SEED + 100 * fold + s).permutation(len(tr))
            for k in ("logistic", "mlp_ensemble"):
                shuf[(k, s)][te] = fit_predict(k, Xtr, Y[tr][perm], M[tr][perm], bases[tr][perm], Xte, seed=s, fixed_lam=True)[0]
        log(f"  [{setting}] fold {fold + 1}/{len(set(bases))} done")
    res = {k: Result(rank_metrics(preds[k], Y, M), preds[k], spread if k == "mlp_ensemble" else None, Y, M) for k in PROB_MODELS}
    res["expert_rules"] = Result(rank_metrics(expert, Y, M))
    if setting == "obs+cf":
        res["cf_heuristic"] = Result(rank_metrics(cf, Y, M))
    res["random"] = Result(random_metrics(Y, M))
    shuf_res = {k: [Result(rank_metrics(shuf[(k, s)], Y, M), shuf[(k, s)], None, Y, M) for s in range(N_SHUFFLE)]
                for k in ("logistic", "mlp_ensemble")}
    return res, shuf_res, preds, spread, lams


def learning_curve(setting, rows, Y, M, bases, expert, log):
    Xraw = np.stack([rl.build_features(r, setting)[0] for r in rows])
    ub = sorted(set(bases.tolist()))
    out = {}
    for size in CURVE_SIZES:
        acc = {k: [] for k in ("prior", "knn", "logistic", "mlp_ensemble")}
        for ti, b in enumerate(ub):
            te = np.flatnonzero(bases == b)
            others = [x for x in ub if x != b]
            reps = 1 if size >= len(others) else CURVE_REPS
            for rep in range(reps):
                rng = np.random.default_rng(SEED + 1000 * size + 17 * ti + rep)
                chosen = rng.choice(others, size=min(size, len(others)), replace=False)
                tr = np.flatnonzero(np.isin(bases, chosen))
                prep = rl.Preprocessor().fit(Xraw[tr])
                Xtr, Xte = prep.transform(Xraw[tr]), prep.transform(Xraw[te])
                for k in acc:
                    P = fit_predict(k, Xtr, Y[tr], M[tr], bases[tr], Xte, seed=rep, fixed_lam=True)[0]
                    acc[k].append(rank_metrics(P, Y[te], M[te])[:, 0])
        out[size] = {k: float(np.nanmean(np.concatenate(v))) for k, v in acc.items()}
        log(f"  [{setting}] curve size {size}: {out[size]}")
    return out


# ------------------------------------------------------------------------------------------------ summary
def summarise(setting, rows, Y, M, bases, res, shuf_res, preds, spread, faults):
    ub = sorted(set(bases.tolist()))
    idx = boot_idx(len(ub))
    sums = {k: per_base_sums(v, bases, ub) for k, v in res.items()}
    out = {"models": {}, "paired": {}, "uncertainty": {}, "overconfidence": {}, "reliability": {}, "per_fault": {}}
    for k, A in sums.items():
        m = {}
        for j, name in enumerate(METRICS):
            if A[:, j, 1].sum() == 0:
                continue
            point = float(A[:, j, 0].sum() / A[:, j, 1].sum())
            m[name] = {"value": point, "ci95": ci(stat_from(A, idx, j))}
        if res[k].P is not None:
            m["logloss"] = float(res[k].ll.sum() / res[k].npairs.sum())
        out["models"][k] = m
    # shuffled controls: mean over repeats
    for k, lst in shuf_res.items():
        vals = {"top1": [], "top3": [], "mrr": [], "brier": [], "logloss": []}
        for r in lst:
            A = per_base_sums(r, bases, ub)
            for j, name in enumerate(METRICS):
                vals[name].append(A[:, j, 0].sum() / A[:, j, 1].sum())
            vals["logloss"].append(r.ll.sum() / r.npairs.sum())
        out["models"][f"{k}_shuffled"] = {n: {"value": float(np.mean(v)), "range": [float(min(v)), float(max(v))]} if n != "logloss"
                                          else float(np.mean(v)) for n, v in vals.items()}
    # strongest simple baseline by top-1 point estimate
    simple = [k for k in ("prior", "knn", "expert_rules", "cf_heuristic", "random") if k in res]
    best_simple = max(simple, key=lambda k: out["models"][k]["top1"]["value"])
    out["best_simple_baseline"] = best_simple
    learned = ("logistic", "mlp_ensemble")
    refs = sorted(set(["knn", "expert_rules", "prior", best_simple] + (["cf_heuristic"] if "cf_heuristic" in res else [])))
    for a in learned + ("knn",):
        for b in refs:
            if a == b:
                continue
            for j, name in ((0, "top1"), (1, "top3"), (2, "mrr")):
                d = stat_from(sums[a], idx, j) - stat_from(sums[b], idx, j)
                pt = sums[a][:, j, 0].sum() / sums[a][:, j, 1].sum() - sums[b][:, j, 0].sum() / sums[b][:, j, 1].sum()
                out["paired"].setdefault(f"{a} - {b}", {})[name] = {"value": float(pt), "ci95": ci(d)}
    # reliability, overconfidence, uncertainty
    elig = ~np.isnan(res["prior"].rm[:, 0])
    for k in PROB_MODELS:
        P = preds[k]
        bins = np.minimum((P * 5).astype(int), 4)
        rel = []
        for q in range(5):
            sel = (bins == q) & (M > 0)
            rel.append({"bin": f"{q / 5:.1f}-{(q + 1) / 5:.1f}", "n": int(sel.sum()), "mean_pred": float(P[sel].mean()) if sel.any() else None,
                        "observed": float(Y[sel].mean()) if sel.any() else None})
        out["reliability"][k] = rel
        top = np.argmax(np.where(M > 0, P, -1), axis=1)
        ptop = P[np.arange(len(P)), top]
        hit = Y[np.arange(len(P)), top] > 0
        conf = ptop >= 0.7
        u = {"n_conf_picks": int(conf.sum()), "n_conf_wrong": int((conf & ~hit).sum()),
             "n_instances": int(len(P)), "n_instances_with_a_repair": int(elig.sum()),
             "auroc_low_prob_flags_miss": auroc(1 - ptop, ~hit), "mean_ptop_hit": float(ptop[hit].mean()) if hit.any() else None,
             "mean_ptop_miss": float(ptop[~hit].mean()) if (~hit).any() else None}
        if k == "mlp_ensemble":
            sp = spread[np.arange(len(P)), top]
            u.update({"mean_spread_hit": float(sp[hit].mean()) if hit.any() else None,
                      "mean_spread_miss": float(sp[~hit].mean()) if (~hit).any() else None, "auroc_high_spread_flags_miss": auroc(sp, ~hit)})
        out["overconfidence"][k] = {x: u[x] for x in ("n_conf_picks", "n_conf_wrong")}
        out["uncertainty"][k] = u
    # per-fault top-1 (labels for reporting only)
    fl = np.array([faults.get(r["instance_id"], "unknown") for r in rows])
    for f in sorted(set(fl.tolist())):
        sel = (fl == f)
        d = {"n_instances": int(sel.sum()), "n_with_repair": int((sel & elig).sum())}
        for k in res:
            v = res[k].rm[sel, 0]
            d[k] = float(np.nanmean(v)) if np.sum(~np.isnan(v)) else None
        out["per_fault"][f] = d
    return out


def fmt(m, key):
    if key not in m:
        return "n/a"
    v = m[key]
    if "ci95" in v:
        return f"{v['value']:.3f} [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]"
    return f"{v['value']:.3f} (range {v['range'][0]:.3f}-{v['range'][1]:.3f})"


def write_report(path, summary, meta):
    L = [f"# Level C leave-one-base-out evaluation", "",
         f"Data: {meta['n_instances']} instances, {meta['n_bases']} bases, {meta['n_tools']} tools; target = measured repair (walking fraction >= 0.75). "
         f"Base-clustered bootstrap ({N_BOOT} reps, seed {SEED}) 95% CIs in brackets. Test = an unseen base; standardisation, k, lambda "
         f"(logistic inner leave-one-base-out CV over {list(rl.LogisticModel.LAMBDAS)}) fitted on training bases only. Instances with no repairing tool "
         f"({meta['n_no_repair']}) are excluded from top-k/MRR but counted in Brier/log-loss. Mean fraction of tools that repair: {meta['base_rate']:.3f}.", ""]
    for s, S in summary["settings"].items():
        cost = "4 rollouts (initial observation)" if s == "obs" else "36 rollouts (observation + 9 counterfactuals)"
        L += [f"## Setting `{s}` (information cost {cost})", "", "| model | top-1 | top-3 | MRR | Brier | log-loss |", "|---|---|---|---|---|---|"]
        for k, m in S["models"].items():
            ll = f"{m['logloss']:.3f}" if "logloss" in m else "n/a"
            L.append(f"| {k} | {fmt(m, 'top1')} | {fmt(m, 'top3')} | {fmt(m, 'mrr')} | {fmt(m, 'brier')} | {ll} |")
        L += ["", f"Strongest simple baseline by top-1: **{S['best_simple_baseline']}**.", "", "Paired differences in top-1 (model A - B; base-clustered 95% CI):", "",
              "| A - B | top-1 diff | top-3 diff | MRR diff |", "|---|---|---|---|"]
        for k, d in S["paired"].items():
            L.append(f"| {k} | " + " | ".join(f"{d[n]['value']:+.3f} [{d[n]['ci95'][0]:+.3f}, {d[n]['ci95'][1]:+.3f}]" for n in ("top1", "top3", "mrr")) + " |")
        L += ["", "Verdict (generated from the CIs):", ""]
        b0 = S["best_simple_baseline"]
        for b in dict.fromkeys([b0] + (["cf_heuristic"] if "cf_heuristic" in S["models"] else []) + ["expert_rules"]):
            for a in ("logistic", "mlp_ensemble", "knn"):
                key = f"{a} - {b}"
                if a != b and key in S["paired"]:
                    d = S["paired"][key]["top1"]
                    word = "BEATS" if d["ci95"][0] > 0 else ("is WORSE than" if d["ci95"][1] < 0 else "is NOT distinguishable from")
                    L.append(f"- {a} {word} {b}{' (strongest simple baseline)' if b == b0 else ''} on top-1 "
                             f"({d['value']:+.3f}, CI [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]).")
        L += ["", "Overconfidence (top-1 probability >= 0.7 while that tool does not repair) and uncertainty:", "",
              "| model | confident picks | confident & wrong | AUROC(low p flags miss) | mean p hit / miss |", "|---|---|---|---|---|"]
        for k, u in S["uncertainty"].items():
            au = "n/a" if u["auroc_low_prob_flags_miss"] is None else f"{u['auroc_low_prob_flags_miss']:.3f}"
            mh = "n/a" if u["mean_ptop_hit"] is None or u["mean_ptop_miss"] is None else f"{u['mean_ptop_hit']:.3f} / {u['mean_ptop_miss']:.3f}"
            L.append(f"| {k} | {u['n_conf_picks']} | {u['n_conf_wrong']} | {au} | {mh} |")
        u = S["uncertainty"]["mlp_ensemble"]
        if u.get("mean_spread_hit") is not None and u.get("mean_spread_miss") is not None:
            sa = "n/a" if u["auroc_high_spread_flags_miss"] is None else f"{u['auroc_high_spread_flags_miss']:.3f}"
            L += ["", f"MLP ensemble spread of the top-1 tool: mean {u['mean_spread_hit']:.3f} for hits vs {u['mean_spread_miss']:.3f} for misses; "
                      f"AUROC(high spread flags a miss) = {sa} (0.5 = no information)."]
        L += ["", "Reliability (pooled over tools; 5 bins):", ""]
        for k in ("logistic", "mlp_ensemble", "knn", "prior"):
            L.append(f"- {k}: " + "; ".join(f"{r['bin']}: n={r['n']}, pred {r['mean_pred']:.2f}, obs {r['observed']:.2f}" for r in S["reliability"][k]
                                            if r["n"]))
        L += ["", "Learning curve (top-1 vs number of training bases; mean over random base subsets):", "", "| bases | prior | knn | logistic (fixed lambda) | mlp_ensemble |",
              "|---|---|---|---|---|"]
        for size, v in S["learning_curve"].items():
            L.append(f"| {size} | " + " | ".join(f"{v[k]:.3f}" for k in ("prior", "knn", "logistic", "mlp_ensemble")) + " |")
        L += ["", "Per-fault top-1 (fault labels used for this breakdown only):", ""]
        ks = [k for k in ("prior", "knn", "logistic", "mlp_ensemble", "expert_rules", "cf_heuristic", "random") if k in S["models"]]
        L += ["| fault | n (with repair) | " + " | ".join(ks) + " |", "|---|---|" + "---|" * len(ks)]
        for f, d in S["per_fault"].items():
            L.append(f"| {f} | {d['n_instances']} ({d['n_with_repair']}) | " + " | ".join("n/a" if d[k] is None else f"{d[k]:.2f}" for k in ks) + " |")
        L.append("")
    L += ["## Notes", "", "- Shuffled controls permute the training targets within the training fold (3 repeats, logistic with fixed lambda 10); they keep the per-tool base rates, so their natural chance level is the `prior` row (not `random`); any lift above prior would indicate a leak.",
          "- The MLP ensemble members differ only by initialisation and agree closely, so their spread is tiny and carries no signal; the predicted probability itself is the usable confidence (AUROC column).",
          "- Bases are strongly unequal in size (5 to 20 instances) and instances within a base share a body, so the effective sample size is the number of bases (12); CIs are wide.",
          "- The cf_heuristic ranks only tools with an available counterfactual (stride has none) and puts the rest after them.", ""]
    Path(path).write_text("\n".join(L), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--probe", required=True)
    ap.add_argument("--instances", default=None, help="glob of dev instance files (fault labels, report breakdown only)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--skip-curve", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:6.1f}s] {s}", flush=True)
    rows = load_rows(a.probe)
    faults = load_faults(a.instances) if a.instances else {}
    YM = [rl.targets(r["repair_matrix"]) for r in rows]
    Y, M = np.stack([y for y, _ in YM]), np.stack([m for _, m in YM])
    bases = np.array([r["base_id"] for r in rows])
    expert, cf = expert_matrix(rows), cf_matrix(rows)
    meta = {"n_instances": len(rows), "n_bases": len(set(bases.tolist())), "n_tools": len(rl.TOOLS),
            "n_no_repair": int(((Y * M).sum(1) == 0).sum()), "base_rate": float((Y * M).sum() / M.sum()),
            "n_fault_labels_joined": int(sum(r["instance_id"] in faults for r in rows)), "seed": SEED}
    summary = {"meta": meta, "settings": {}}
    for s in rl.SETTINGS:
        res, shuf_res, preds, spread, lams = run_setting(s, rows, Y, M, bases, expert, cf, log)
        S = summarise(s, rows, Y, M, bases, res, shuf_res, preds, spread, faults)
        S["logistic_lambda_by_heldout_base"] = lams
        S["learning_curve"] = {} if a.skip_curve else learning_curve(s, rows, Y, M, bases, expert, log)
        summary["settings"][s] = S
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(summary, indent=1), encoding="utf-8")
    write_report(a.report, summary, meta)
    log(f"wrote {a.out} and {a.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
