"""Read-only: enumerate eng_tools.min_repair_budget for all ten tools from the published code (no physics).

eng_tools imports MuJoCo transitively, so the module is imported, but every physics entry point (mj_step, mj_forward, model
compilation, MjData) is replaced by a trap that raises; the script asserts that no trap fired.
    python -I p05_min_budget_check.py <cf-experience worktree>"""
import sys

wt = sys.argv[1]
sys.path.insert(0, wt)
import mujoco  # noqa: E402

calls = []


def _trap(name):
    def f(*a, **k):
        calls.append(name)
        raise RuntimeError(f"physics call blocked: {name}")
    return f


for n in ("mj_step", "mj_forward", "mj_resetData", "mj_step1", "mj_step2", "mj_kinematics", "MjData"):
    if hasattr(mujoco, n):
        setattr(mujoco, n, _trap(n))


class _NoModel:
    from_xml_string = staticmethod(_trap("MjModel.from_xml_string"))
    from_xml_path = staticmethod(_trap("MjModel.from_xml_path"))
    from_binary_path = staticmethod(_trap("MjModel.from_binary_path"))


mujoco.MjModel = _NoModel
from creature_forge import eng_tools as et  # noqa: E402

print("MIN_GENERATIONS", et.MIN_GENERATIONS)
for n_train in (4, 8):
    for t in et.TOOLS:
        sp = et.tool_space(t)
        print(f"n_train={n_train} {t:14s} dim={sp.dim} pop={et.population(sp)} min_repair_budget={et.min_repair_budget(t, n_train)}")
assert not calls, calls
print("physics entry points called:", calls)
