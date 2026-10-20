"""FA-1 F2: repair-to-diagnosis feedback. Distributions over the 183 assimilations (clustered by episode)."""
from __future__ import annotations

import collections
import csv
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = lambda x: x in (True, "True")  # noqa: E731
F = lambda x: None if x in ("", "None", None) else float(x)  # noqa: E731


def q(v):
    v = sorted(v)
    if not v:
        return "n 0"
    return (f"n {len(v)} min {v[0]:.3g} p25 {np.percentile(v, 25):.3g} median {np.median(v):.3g} p75 {np.percentile(v, 75):.3g} "
            f"p90 {np.percentile(v, 90):.3g} max {v[-1]:.3g}")


def main():
    rows = list(csv.DictReader(open(os.path.join(OUT, "feedback_events.csv"), encoding="utf-8")))
    A = [r for r in rows if not B(r["skipped"])]
    S = [r for r in rows if B(r["skipped"])]
    print(f"assimilated {len(A)}, skipped {len(S)}; per arm:",
          {a: (sum(1 for r in A if r['arm'] == a), sum(1 for r in S if r['arm'] == a)) for a in ("A1e6", "A3v5", "A4x")})
    eps = collections.Counter((r["instance_id"], r["arm"]) for r in A)
    print("episodes with >=1 assimilation", len(eps), "events/episode", dict(sorted(collections.Counter(eps.values()).items())),
          "distinct bases", len({r['robot_base'] for r in A}))
    print("raw nats per disagreeing seed", round(L.PER_SEED_NATS, 3), "tempered (T=6)", round(L.PER_SEED_NATS / 6, 3),
          "-> max shift with 8 seeds", round(8 * L.PER_SEED_NATS / 6, 2), "nats (likelihood ratio", round(math.exp(8 * L.PER_SEED_NATS / 6), 1), ")")
    print("\n## predicted-count disagreement among the top-4 modelled structures")
    sp = [F(r["pred_spread_max_minus_min"]) for r in A]
    one = [r for r in A if F(r["pred_spread_max_minus_min"]) is None]
    print("  events with < 2 modelled structures predicted (no competitor in top 4):", len(one))
    sp2 = [x for x in sp if x is not None]
    print("  spread distribution:", dict(sorted(collections.Counter(int(x) for x in sp2).items())))
    print("  identical (spread 0):", sum(x == 0 for x in sp2), "| <=1:", sum(x <= 1 for x in sp2), "| >=2:", sum(x >= 2 for x in sp2),
          "| >=4:", sum(x >= 4 for x in sp2))
    print("  observed inside predicted range:", sum(B(r["observed_in_pred_range"]) for r in A if r["observed_in_pred_range"] != ""), "of",
          sum(1 for r in A if r["observed_in_pred_range"] != ""))
    print("  n_distinct_predictions:", dict(collections.Counter(r["n_distinct_predictions"] for r in A)))
    print("\n## posterior shift")
    tv8 = [F(r["tv_top8"]) for r in A if F(r["tv_top8"]) is not None]
    tv4 = [F(r["tv_top4"]) for r in A]
    print("  TV (top-8 snapshots):", q(tv8))
    print("  TV (top-4 event record):", q(tv4))
    bands = collections.Counter("<0.01" if x < .01 else "0.01-0.05" if x < .05 else "0.05-0.1" if x < .1 else "0.1-0.3" if x < .3 else ">=0.3" for x in tv8)
    print("  TV8 bands:", dict(bands))
    print("  leader changes:", sum(B(r["leader_changed"]) for r in A), [(r["instance_id"], r["arm"], r["leader_before"], r["leader_after"], r["tv_top8"]) for r in A if B(r["leader_changed"])])
    print("\n## does larger predicted disagreement give larger shifts? (TV8 by spread)")
    by = collections.defaultdict(list)
    for r in A:
        s, t = F(r["pred_spread_max_minus_min"]), F(r["tv_top8"])
        if t is None:
            continue
        by["no competitor" if s is None else str(int(min(s, 4))) + ("+" if s >= 4 else "")].append(t)
    for k in sorted(by):
        print(f"  spread {k}: {q(by[k])}")
    xs = [(F(r["pred_spread_max_minus_min"]), F(r["tv_top8"])) for r in A if F(r["pred_spread_max_minus_min"]) is not None and F(r["tv_top8"]) is not None]
    if xs:
        def spearmanr(a, b):
            r = lambda v: np.argsort(np.argsort(v))
            class _R: pass
            o = _R(); o.correlation = float(np.corrcoef(r(np.array(a)), r(np.array(b)))[0, 1]); o.pvalue = float("nan"); return o
        rho = spearmanr([a for a, _ in xs], [b for _, b in xs])
        print(f"  Spearman(spread, TV8) = {rho.correlation:.3f} (p {rho.pvalue:.2g}, n {len(xs)}, events not independent)")
    print("\n## belief inertia: log-odds gap between top-2 modelled structures before the event vs. the 8-seed ceiling (3.41 nats)")
    gaps = [F(r["logodds_gap_modelled_top2"]) for r in A if F(r["logodds_gap_modelled_top2"]) is not None]
    print("  gap:", q(gaps))
    print("  gap > ceiling (no 8-seed outcome could reorder the top-2 modelled structures):", sum(g > 8 * L.PER_SEED_NATS / 6 for g in gaps), "of", len(gaps))
    print("  leader is the unmodelled reserve before the event:", sum(B(r["leader_is_unmodelled"]) for r in A), "of", len(A))
    # needed seed disagreements to switch, relative to actual spread
    need = []
    for r in A:
        g, s = F(r["logodds_gap_modelled_top2"]), F(r["pred_spread_max_minus_min"])
        if g is None or s is None:
            continue
        need.append((math.ceil(g / (L.PER_SEED_NATS / 6)), int(s)))
    print("  seeds of disagreement needed to switch top-2 (count bound; true per-seed disagreement may exceed count spread):",
          q([a for a, _ in need]))
    print("  events where count spread >= seeds needed:", sum(1 for a, s in need if s >= a), "of", len(need))
    print("\n## leader prediction error (observed vs leader's predicted count)")
    errs = [F(r["modelled_leader_abs_err"]) for r in A if F(r["modelled_leader_abs_err"]) is not None]
    print("  |obs - leader pred|:", dict(sorted(collections.Counter(int(e) for e in errs).items())))
    print("  leader over-predicted walking by >=3 (repair failed though belief predicted success):",
          sum(1 for r in A if r["modelled_leader_pred"] not in ("", "None") and float(r["modelled_leader_pred"]) - int(r["observed_walking"]) >= 3))
    print("\n## decision reachability (could a leader change have altered any later decision?)")
    print("  decision-reachable events (first assimilation, of the twin warm-start design, no Nemotron tool preference):",
          sum(B(r["decision_reachable"]) for r in A), "of", len(A))
    pos = collections.Counter(r["design_source"].split(":")[0] if r["design_source"] else "?" for r in A)
    print("  assimilated design origin:", dict(pos))
    print("  rescreen events:", sum(1 for r in A if B(r["rescreen_followed"])))
    print("\n## skips")
    print("  reasons:", collections.Counter((r["arm"], r["skip_reason"].split(" ")[0] if r["skip_reason"] else "") for r in S))
    sk = collections.Counter((r["instance_id"], r["arm"]) for r in S)
    print("  episodes with skips per arm:", collections.Counter(a for (_, a) in sk))
    print("\n## per-arm distributions")
    for a in ("A1e6", "A3v5", "A4x"):
        aa = [r for r in A if r["arm"] == a]
        print(f"  {a}: n {len(aa)}; TV8 {q([F(r['tv_top8']) for r in aa if F(r['tv_top8']) is not None])}; spread>=2 {sum(1 for r in aa if (F(r['pred_spread_max_minus_min']) or 0) >= 2)}")
    # clustered summary: per-episode max TV
    per = collections.defaultdict(list)
    for r in A:
        if F(r["tv_top8"]) is not None:
            per[(r["instance_id"], r["arm"])].append(F(r["tv_top8"]))
    print("\n## episode-level max TV8 (cluster-robust view):", q([max(v) for v in per.values()]))
    print("   episodes with any TV8 >= 0.1:", sum(max(v) >= .1 for v in per.values()), "of", len(per))
    # strong-disagreement events list
    print("\n## events with spread >= 4 (strongly discriminating predictions)")
    for r in A:
        if (F(r["pred_spread_max_minus_min"]) or 0) >= 4:
            print(f"  {r['arm']} {r['instance_id']} ev{r['event_order']} d{r['design']} obs {r['observed_walking']}/8 pred {r['predicted_walking']} "
                  f"leader {r['leader_before']}({float(r['leader_before_w']):.2f})->{r['leader_after']} TV8 {r['tv_top8']} gap {r['logodds_gap_modelled_top2']} reach {r['decision_reachable']}")


if __name__ == "__main__":
    main()
