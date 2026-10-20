"""FA-1B B3: arithmetic feasibility bound for foot_friction compensation on low-ground-friction instances (no physics).

Model (stated assumptions, Interpretation-level):
  * plant contact_friction multiplies the foot geom friction (hidden_plant.apply_model, hidden_plant.py:199-202); the floor geom
    has friction 0.05 (morphology.py:83) and MuJoCo combines equal-priority geoms by element-wise max, so effective
    mu = design foot_friction x factor whenever that exceeds 0.05;
  * injected factor = exp(-s), s = mult x s_star (hdb_bench.py:88-90, 168); the stored record field `strength` is s;
  * the base controller walks at strengths in its threshold bisection trace with >= k/8 walking (thresholds_dev.json);
    required multiplier m_req(k) = exp(s - s_k) returns effective friction to the largest such s_k;
  * the CMA ceiling is m_max = 2.0 / base foot_friction (guided bound morphology.py:14; walk_opt._log_interval).
This ignores controller retuning, other simultaneous edits, the reality gap and the displacement clause: it bounds whether
the legal friction range can even reach the base controller's own walking regime, not whether a repair would verify."""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L

TH = json.load(open(os.path.join(L.REPO, "artifacts", "vm", "hdb", "artifacts", "hdb", "thresholds_dev.json"), encoding="utf-8"))


def main():
    seen = {}
    for scope, recs in (("dev-eval-2", L.load_eval()), ("stream", L.load_stream())):
        for path, line, r in recs:
            if r["family"] != "low_ground_friction" or r["instance_id"] in seen:
                continue
            th = TH[f"{L.base_of(r['instance_id'])}|low_ground_friction|"]
            f0 = float(r["designs"][0]["body"]["foot_friction"])
            s = float(r["strength"])
            m_max = 2.0 / f0
            out = {"scope": scope, "instance": r["instance_id"], "mult": r["mult"], "base_foot_friction": round(f0, 3),
                   "strength_s": round(s, 4), "injected_factor": round(math.exp(-s), 4),
                   "effective_mu_faulty": round(f0 * math.exp(-s), 3), "cma_max_up_factor": round(m_max, 3),
                   "effective_mu_ceiling": round(2.0 * math.exp(-s), 3)}
            for k in (5, 6, 7):
                walk = [x for x, w in th["trace"] if w >= k]
                if walk:
                    sk = max(walk)
                    req = math.exp(max(0.0, s - sk))
                    out[f"m_req_walk>={k}/8"] = round(req, 3)
                    out[f"feasible_k{k}"] = req <= m_max
                else:
                    out[f"m_req_walk>={k}/8"] = None
                    out[f"feasible_k{k}"] = None
            out["threshold_trace"] = th["trace"]
            seen[r["instance_id"]] = out
    for v in seen.values():
        print(json.dumps(v))
    json.dump(list(seen.values()), open(os.path.join(L.OUT, "scripts", "_friction_feasibility.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
