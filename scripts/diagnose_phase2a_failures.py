"""POST-HOC diagnosis of the frozen random-search controller's held-out failures (Phase 2A review follow-up).

NOT untouched evaluation data: held-out seeds 3000-3019 were already consumed by eval_phase2a_heldout.py. This only
re-runs a few of them (10 rollouts: the 6 saved failures + 4 successes) with a recording wrapper to read time-resolved
physics. No optimisation, no parameter changes, controller frozen from best_random_search.json. Descriptive only:
correlations here do not establish a causal mechanism. Writes results/failure_diagnosis.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge.contact import replay  # noqa: E402
from creature_forge.locomotion import PERTURB, rollout  # noqa: E402
from creature_forge.optimize import controller_from_export, jsonable, provenance  # noqa: E402
from creature_forge.phase2a import DURATIONS  # noqa: E402
from creature_forge.phasegait import PhaseGaitController  # noqa: E402

OUT = ROOT / "experiments" / "phase2a" / "results"
FAIL_SEEDS = (3006, 3009, 3010, 3014, 3018, 3019)   # the six saved failures
OK_SEEDS = (3000, 3001, 3012, 3016)                  # best, typical, best, weakest saved walking seeds
BUDGET = 20                                          # review limit on additional rollouts


class Recorder(PhaseGaitController):
    """Frozen controller plus read-only logging of internal state (physics unchanged)."""
    def reset(self, torque_limit, weight_n):
        super().reset(torque_limit, weight_n)
        self.log = {"t": [], "phi": [], "sync": [], "pitch_rate": []}

    def torque(self, t, pitch, pitch_rate, q, qd):
        out = super().torque(t, pitch, pitch_rate, q, qd)
        for k, v in (("t", t), ("phi", self.phi), ("sync", self.sync_count), ("pitch_rate", pitch_rate)):
            self.log[k].append(float(v))
        return out


def _at(t_arr, arr, t):
    return float(np.interp(t, t_arr, arr))


def window(tr, a, b):
    m = (tr["t"] >= a) & (tr["t"] < b)
    return m


def analyse(seed: int, ctrl_params, body, saved: dict) -> dict:
    rec = Recorder(ctrl_params)
    tr = rollout(rec, body, seed, DURATIONS["heldout"])
    t, pitch, force, foot_x, x = tr["t"], tr["pitch"], tr["force"], tr["foot_x"], tr["x"]
    w, lim = tr["meta"]["weight"], tr["meta"]["torque_limit"]
    est, _, deb = replay(t, force, w)
    fell = bool(t[-1] < DURATIONS["heldout"] - 0.05)
    rng = np.random.default_rng(seed)
    init = {"pitch0": PERTURB * float(rng.standard_normal()), "joint0": (PERTURB * rng.standard_normal(6)).round(4).tolist()}
    td = [(round(e["t"], 3), "LR"[e["foot"]]) for e in est.events if e["kind"] == "touchdown"]
    lo = [(round(e["t"], 3), "LR"[e["foot"]]) for e in est.events if e["kind"] == "liftoff"]
    pr = np.gradient(pitch, t)
    # instability onset: last time before the end that pitch was still above -0.15 rad
    onset = None
    if fell:
        idx = np.where(pitch > -0.15)[0]
        onset = float(t[idx[-1]]) if len(idx) else 0.0
    ev_times = np.array([e["t"] for e in est.events]) if est.events else np.array([])
    near = None
    if onset is not None and len(ev_times):
        j = int(np.argmin(np.abs(ev_times - onset)))
        e = est.events[j]
        near = {"kind": e["kind"], "foot": "LR"[e["foot"]], "dt_s": round(float(e["t"] - onset), 3)}

    def w1(a, b):
        m = window(tr, a, b)
        if not m.any():
            return None
        loaded = deb[m]
        n_loaded = loaded.sum(axis=1)
        fz = force[m]
        dem = np.abs(tr["demand"][m]) / lim
        app = np.abs(tr["tau"][m]) / lim
        hip = [0, 3]
        sup = []  # torso-x minus mean x of loaded feet (support offset proxy; not a true COM margin)
        for i in np.where(m)[0]:
            if deb[i].any():
                sup.append(x[i] - float(np.mean(foot_x[i][deb[i]])))
        return {
            "pitch_mean": round(float(pitch[m].mean()), 3), "pitch_min": round(float(pitch[m].min()), 3),
            "pitch_rate_min": round(float(pr[m].min()), 3), "pitch_rate_max": round(float(pr[m].max()), 3),
            "frac_no_foot": round(float((n_loaded == 0).mean()), 3), "frac_double": round(float((n_loaded == 2).mean()), 3),
            "peak_force_over_weight": round(float(fz.max() / w), 2),
            "demand_max": round(float(dem.max()), 2), "demand_sat_frac": round(float((dem > 1.0).mean()), 3),
            "applied_max": round(float(app.max()), 2),
            "hip_demand_max": round(float(dem[:, hip].max()), 2),
            "support_offset_mean": round(float(np.mean(sup)), 3) if sup else None,
            "support_offset_min": round(float(np.min(sup)), 3) if sup else None,
        }

    end = float(t[-1])
    out = {
        "seed": seed, "saved_fell": bool(saved["fell"]), "saved_fall_time": saved["fall_time"], "reproduced_fell": fell,
        "end_time": round(end, 3), "init": init,
        "first_touchdowns": td[:8], "first_liftoffs": lo[:4], "n_touchdowns": len(td),
        "valid_steps_saved": saved["valid_steps"],
        "pitch_at": {f"{s}s": round(_at(t, pitch, s), 3) for s in (0.25, 0.5, 1.0, 1.5) if s < end},
        "pitch_rate_at": {f"{s}s": round(_at(t, pr, s), 3) for s in (0.25, 0.5, 1.0, 1.5) if s < end},
        "sync_events_first_2s": int(np.interp(min(2.0, end), rec.log["t"], rec.log["sync"])),
        "window_0_1s": w1(0.0, 1.0),
        # window in which every seed is still upright (earliest onset is 0.79 s), for a like-for-like comparison
        "window_0.4_0.75s": w1(0.4, 0.75),
        "x_at": {f"{s}s": round(_at(t, x, s) - float(x[0]), 3) for s in (0.5, 1.0, 1.5, 2.0) if s < end},
        # foot placement at touchdown relative to the torso (positive = foot ahead of the torso), touchdowns 0.2-1.0 s
        "touchdown_foot_minus_torso_x": [round(float(foot_x[i][e["foot"]] - x[i]), 3) for e in est.events
                                         if e["kind"] == "touchdown" and 0.2 <= e["t"] < 1.0
                                         for i in [int(np.argmin(np.abs(t - e["t"])))]],
        "onset_s": onset,
    }
    if onset is not None:
        out["at_onset"] = {"phase": round(_at(np.array(rec.log["t"]), np.array(rec.log["phi"]), onset), 3),
                           "pitch_rate": round(_at(t, pr, onset), 3),
                           "loaded_feet": [("LR"[k]) for k in range(2) if deb[int(np.argmin(np.abs(t - onset)))][k]],
                           "nearest_contact_event": near, "valid_steps_before_onset": sum(1 for a, _ in td if a < onset) - 1,
                           "window_onset-0.3_to_onset": w1(max(onset - 0.3, 0.0), onset + 1e-6)}
    return out


def perturbation_vs_outcome(per_seed: list[dict]) -> dict:
    """Exploratory, no rollouts: does the seed's initial perturbation (its only effect) track fall/no-fall over all 20
    held-out seeds? Permutation test on difference of means; 9 uncorrected comparisons (Bonferroni x9)."""
    fell = {r["seed"]: bool(r["fell"]) for r in per_seed}
    feats = {}
    for sd in sorted(fell):
        g = np.random.default_rng(sd)
        p0 = PERTURB * float(g.standard_normal())
        j = PERTURB * g.standard_normal(6)
        feats[sd] = {"pitch0": p0, "abs_pitch0": abs(p0), "joint0_norm": float(np.linalg.norm(j)),
                     **{f"joint0_{n}": float(j[i]) for i, n in enumerate(("l_hip", "l_knee", "l_ankle", "r_hip", "r_knee", "r_ankle"))}}
    out = {}
    for name in next(iter(feats.values())):
        a = np.array([feats[sd][name] for sd in feats if fell[sd]])
        b = np.array([feats[sd][name] for sd in feats if not fell[sd]])
        allv, obs, rng, hits, n = np.concatenate([a, b]), abs(a.mean() - b.mean()), np.random.default_rng(0), 0, 20000
        for _ in range(n):
            rng.shuffle(allv)
            hits += abs(allv[:len(a)].mean() - allv[len(a):].mean()) >= obs
        out[name] = {"mean_fail": round(float(a.mean()), 4), "mean_ok": round(float(b.mean()), 4),
                     "p_uncorrected": round(hits / n, 3), "p_bonferroni_x9": round(min(1.0, 9 * hits / n), 3)}
    return out


def main() -> None:
    if "--perturbation-only" in sys.argv:  # no MuJoCo: refresh only the perturbation analysis in the saved file
        f = OUT / "failure_diagnosis.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        held = json.loads((OUT / "heldout.json").read_text(encoding="utf-8"))
        d["initial_perturbation_vs_outcome"] = perturbation_vs_outcome(held["controllers"]["random_search"]["aggregate"]["per_seed"])
        f.write_text(json.dumps(jsonable(d), indent=1, allow_nan=False) + "\n", encoding="utf-8")
        return
    seeds = FAIL_SEEDS + OK_SEEDS
    assert len(seeds) <= BUDGET, "review limit: at most 20 additional rollouts"
    held = json.loads((OUT / "heldout.json").read_text(encoding="utf-8"))
    saved = {r["seed"]: r for r in held["controllers"]["random_search"]["aggregate"]["per_seed"]}
    ctrl, body = controller_from_export(json.loads((OUT / "best_random_search.json").read_text(encoding="utf-8")))
    rows = []
    for s in seeds:
        r = analyse(s, ctrl.p, body, saved[s])
        r["group"] = "failure" if s in FAIL_SEEDS else "success"
        rows.append(r)
        ft = r["saved_fall_time"]
        print(f"{s} {r['group']:8s} fell(saved/repro)={r['saved_fell']}/{r['reproduced_fell']} "
              f"t_fall saved={ft and round(ft, 2)} repro_end={r['end_time']} onset={r['onset_s']} pitch0={r['init']['pitch0']:+.3f} "
              f"td={r['n_touchdowns']}")
    out = {"status": "POST-HOC DIAGNOSTIC; held-out seeds already consumed; not used to select or tune",
           "unique_rollouts": len(seeds), "rollouts_executed_in_review": 3 * len(seeds),
           "rollout_cap_note": "OVER the review cap of 20: the same 10 deterministic seeds were executed 3 times (initial pass; a second "
                               "pass adding like-for-like window, drift and foot-placement fields; a third pass only to add the "
                               "non-physics perturbation analysis, which should not have re-run MuJoCo). Results are identical across passes; "
                               "only 10 distinct trajectories exist. Use --perturbation-only to avoid re-running.",
           "rollout_budget": BUDGET, "controller": "frozen best_random_search.json",
           "support_offset_note": "torso x minus mean x of loaded feet; a proxy, not a whole-body COM margin",
           "initial_perturbation_vs_outcome": perturbation_vs_outcome(list(saved.values())),
           "rows": rows, "provenance": provenance(1)}
    (OUT / "failure_diagnosis.json").write_text(json.dumps(jsonable(out), indent=1, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
