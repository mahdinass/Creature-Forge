"""R1 one-shot final evaluation of the frozen R1 winner against the frozen Phase 2A incumbent on seeds 6000-6029.

    .venv\\Scripts\\python scripts\\eval_r1_final.py [--workers 4]

Refuses to run unless the protocol and results/selection.json are committed unmodified (and the protocol still matches
the code), refuses to run twice, and counts its rollouts in the ledger. Reports two separate conclusions: the
engineering criterion and statistical superiority (exact two-sided McNemar on the paired seeds). Nothing here selects,
tunes or stops anything. No Nebius calls.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r1, r1_stats  # noqa: E402
from creature_forge.optimize import Executor, jsonable, provenance  # noqa: E402

RES = r1.RESULTS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    out_path = RES / "final.json"
    if out_path.exists():
        raise SystemExit("final.json exists: the final evaluation is run once")
    commits = r1.require_preregistration(need_selection=True)
    ledger = r1.Ledger()
    ledger.verify()
    pilot = json.loads((RES / "pilot.json").read_text(encoding="utf-8"))
    workers = max(1, min(a.workers, r1.MAX_WORKERS, pilot["recommended_workers"]))
    sel = json.loads(r1.SELECTION.read_text(encoding="utf-8"))
    vecs = [sel["winner"]["vector"], r1.incumbent_vector(15 if len(sel["winner"]["vector"]) == 15 else 13)]
    names = ["r1_winner", "phase2a_incumbent"]
    with Executor(workers, timeout_s=1800, fn=r1.r1_job) as ex:
        outs = r1.run_batch(ex, ledger, "final", vecs, r1.FINAL_SEEDS, "R1 winner vs frozen incumbent, identical seeds")
    if not all(o["ok"] for o in outs):
        raise SystemExit("a final-evaluation job failed: " + "; ".join(o.get("error", "") for o in outs if not o["ok"]))
    per = {n: o["result"]["per_seed"] for n, o in zip(names, outs)}
    ok = {n: [m["walking"] for m in per[n]] for n in names}
    out = {"protocol_commit": commits["protocol"], "selection_commit": commits["selection"], "seeds": list(r1.FINAL_SEEDS),
           "duration": r1.DURATION, "winner_source": sel["winner"]["arm"] + str(sel["winner"]["replicate"]) + f"#{sel['winner']['index']}",
           "engineering": {n: r1.engineering_verdict(per[n]) for n in names},
           "superiority": r1_stats.paired_comparison(ok["r1_winner"], ok["phase2a_incumbent"], alpha=r1.ALPHA),
           "secondary_exploratory_right_knee": {n: r1.knee_hypothesis_test(r1.FINAL_SEEDS, ok[n]) for n in names},
           "per_seed": {n: [r1._compact_seed(m) for m in per[n]] for n in names},
           "ledger_rollouts_total": ledger.total_rollouts(), "provenance": provenance(workers)}
    out_path.write_text(json.dumps(jsonable(out), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    for n in names:
        e = out["engineering"][n]
        print(f"{n:18s} walking {e['walking_seeds']}/{e['n_seeds']}  median v {e['median_speed_upright']:+.2f}  "
              f"engineering criterion met: {e['meets_engineering_criterion']}")
    s = out["superiority"]
    print(f"paired table {s['table']}  McNemar exact p = {s['mcnemar_exact_two_sided_p']:.4f}  "
          f"diff {s['paired_difference']['estimate']:+.3f} {s['paired_difference']['newcombe_95ci']}  superior: {s['superior']}")


if __name__ == "__main__":
    main()
