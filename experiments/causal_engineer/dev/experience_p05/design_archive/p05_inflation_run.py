"""Run one cell of section E (learning inflation, synthetic data, exact P0 learner) and write JSON.
    python -I p05_inflation_run.py <worktree> <G> <scenario index> <sims> <out.json>"""
import json
import os
import sys

sys.modules["mujoco"] = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p05_design_calc as c  # noqa: E402

wt, G, si, sims, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
sys.path.insert(0, wt)
from creature_forge import experience_p0 as p0  # noqa: E402

r = c.learning_inflation(p0, G, 2, list(c.SCENARIOS)[si], sims)
json.dump(r, open(out, "w"), indent=1)
print({k: v for k, v in r.items() if k != 'per_sim'})
