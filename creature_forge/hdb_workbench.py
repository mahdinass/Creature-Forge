"""Budgeted lab bench for one Hidden-Damage Bench robot (phase 3): `eng_tools.Workbench` on the hidden plant, plus a twin.

Plant instruments (charged to ONE plant budget, in 10 s rollout-equivalents; refusals are 0-cost ledger lines, never clipped):
  observe, counterfactual, stress_test    inherited from eng_tools.Workbench, running on the plant
  floor_test(mult)      walk the current best design on a test surface with friction x mult (obs seeds)       n_obs
  weigh_test()          static scale + balance board: total mass and centre-of-mass offset, measurement noise    1
  robustness_check(n)   walk the current best design on n fresh policy-visible "robust" seeds (n in 8, 16)        n
  repair(tool, budget, n_train, init_vector=?, init_body=?)
                        CMA-ES on the plant over the tool's subspace; body tools search x0.25-4 (guided bounds)
Twin (the nominal-design simulator with a hypothesised deviation; charged to a SEPARATE twin budget, 2,800 by default):
  twin_observe(deviation, design, role, n, ...)  twin_walk(...)  twin_cma(...)  twin_weigh(deviation, design)
The twin may use only the policy-visible seed roles (train/obs/robust/twin), never check/validate/confirm.

The plant is held privately (`_plant`); policies receive the bench and `hdb_bench.policy_view` only.
"""
from __future__ import annotations

import copy
import functools
import hashlib

import mujoco
import numpy as np

from . import hidden_plant as hp
from .eng_tools import MIN_GENERATIONS, Workbench, population
from .walk_pipelines import Budget

VERSION = "hdb_workbench_v1"
BODY_RATIO = (0.25, 4.0)
TWIN_BUDGET = 2800
WEIGH_NOISE = {"mass_frac": 0.01, "com_m": 0.005}
TWIN_ROLES = ("train", "obs", "robust", "twin")


def tool_space(tool: str):
    """The tool's search space with the wide HDB body ratio (fault_bench tools, x0.25-4 for body parameters)."""
    from . import fault_bench as fb
    from .walk_pipelines import _FPSpace
    from . import walk_opt as wo
    if tool not in fb.TOOLS:
        raise ValueError(f"unknown tool {tool!r}; known: {list(fb.TOOLS)}")
    t = fb.TOOLS[tool]
    chosen = {p for n in t["subspaces"] for p in wo.SUBSPACES[n]}
    ctrl = tuple(p for p in wo.ALL_NAMES if p in chosen)
    return _FPSpace(ctrl, tuple(t["body"]), body_ratio=BODY_RATIO)


def min_budget(tool: str, n_train: int) -> int:
    return n_train * (1 + MIN_GENERATIONS * population(tool_space(tool)))


def static_mass_com(plant, body: dict, *, design_only: bool = False) -> dict:
    """Total mass (kg) and the whole-body centre of mass x relative to the torso origin (m), neutral pose, from the compiled
    plant model (or the design when design_only)."""
    from .creature_walk import _body
    from .morphology import build_model
    prims = [] if design_only else hp._prims(plant)
    b = _body(hp.plant_body(_body(body).as_dict(), prims))
    model = build_model(b)
    data = mujoco.MjData(model)
    if hp.apply_model(model, prims):
        mujoco.mj_setConst(model, data)
    mujoco.mj_forward(model, data)
    torso = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
    return {"mass_kg": float(model.body_mass.sum()), "com_x_m": float(data.subtree_com[0][0] - data.xpos[torso][0])}


class HDBWorkbench(Workbench):
    def __init__(self, view: dict, plant: dict, *, total_budget: int = 700, twin_budget: int = TWIN_BUDGET, pool=None,
                 n_train: int = 4, n_obs: int = 4, noise_seed: int = 0, variation=None):
        from .arena import VARIATION_PRESET
        variation = VARIATION_PRESET if variation is None else variation
        self._plant = hp.normalize_plant(plant)
        super().__init__(view["robot"], total_budget=total_budget, seeds=view["seeds"], pool=pool, n_train=n_train,
                         n_obs=n_obs, observe_fn=functools.partial(hp.observe, plant=self._plant),
                         cma_fn=functools.partial(hp.plant_cma, plant=self._plant), noise_seed=noise_seed,
                         variation=variation)
        self.view_seeds = {r: [int(s) for s in view["seeds"][r]] for r in TWIN_ROLES}
        self.twin = Budget(int(twin_budget))
        self._weigh_calls = 0
        self._robot_id = view.get("robot_id", "")

    # ------------------------------------------------------------------ ledger
    def ledger(self) -> dict:
        out = super().ledger()
        out["version"] = VERSION
        out["twin"] = {"total": self.twin.total, "used": self.twin.used, "remaining": self.twin.remaining,
                       "lines": copy.deepcopy(self.twin.lines)}
        return out

    # ------------------------------------------------------------------ plant instruments
    def floor_test(self, mult: float = 3.0) -> dict:
        if not (isinstance(mult, (int, float)) and 0.2 <= float(mult) <= 5.0):
            return self._refuse("floor_test", f"friction multiplier must be in [0.2, 5], got {mult!r}")
        if self.remaining < self.n_obs:
            return self._refuse("floor_test", f"needs {self.n_obs} rollouts, {self.remaining} remain")
        idx = self._best
        d = self.designs[idx]
        self._spend(self.n_obs, "floor_test", {"design": idx, "friction_mult": float(mult)})
        out = hp.observe(d["body"], d["vector"], self.obs_seeds, plant=self._plant, variation=self.variation,
                         pool=self.pool, friction_mult=float(mult))
        return {"ok": True, "design_index": idx, "friction_mult": float(mult), "observation": out}

    def weigh_test(self) -> dict:
        if self.remaining < 1:
            return self._refuse("weigh_test", "needs 1 rollout-equivalent")
        idx = self._best
        d = self.designs[idx]
        self._spend(1, "weigh_test", {"design": idx})
        true = static_mass_com(self._plant, d["body"])
        h = int.from_bytes(hashlib.sha256(f"weigh:{self._robot_id}:{self._weigh_calls}".encode()).digest()[:8], "big")
        rng = np.random.default_rng(h)
        self._weigh_calls += 1
        return {"ok": True, "design_index": idx,
                "mass_kg": true["mass_kg"] * (1.0 + WEIGH_NOISE["mass_frac"] * float(rng.standard_normal())),
                "com_x_m": true["com_x_m"] + WEIGH_NOISE["com_m"] * float(rng.standard_normal()),
                "noise_sd": dict(WEIGH_NOISE)}

    def robustness_check(self, n: int = 8) -> dict:
        if n not in (8, 16):
            return self._refuse("robustness_check", f"n must be 8 or 16, got {n!r}")
        if self.remaining < n:
            return self._refuse("robustness_check", f"needs {n} rollouts, {self.remaining} remain")
        idx = self._best
        d = self.designs[idx]
        self._spend(n, "robustness_check", {"design": idx, "n": n})
        rows = hp.walk_seeds(self._plant, d["body"], d["vector"], self.view_seeds["robust"][:n], variation=self.variation,
                             pool=self.pool)
        return {"ok": True, "design_index": idx, "n": n, "walking": int(sum(1 for r in rows if r.get("ok") and r["walking"])),
                "errors": int(sum(1 for r in rows if not r.get("ok"))), "labels": [r.get("label") for r in rows]}

    def repair(self, tool: str, budget: int, *, n_train: int | None = None, init: dict | None = None) -> dict:
        """CMA-ES on the plant over the tool's wide-range subspace from the current best design (or `init`, a design that
        must belong to this bench, e.g. a twin-optimised design registered with `add_twin_design`)."""
        from . import fault_bench as fb
        n_train = self.n_train if n_train is None else int(n_train)
        if tool not in fb.TOOLS:
            return self._refuse("repair", f"unknown tool {tool!r}; known: {list(fb.TOOLS)}")
        if n_train not in (4, 8) or n_train > len(self.view_seeds["train"]):
            return self._refuse("repair", f"n_train must be 4 or 8, got {n_train}", tool=tool)
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            return self._refuse("repair", "budget must be a non-negative integer", tool=tool)
        need = min_budget(tool, n_train)
        if budget < need:
            return self._refuse("repair", f"budget {budget} is below the minimum {need} for tool {tool}", tool=tool)
        if budget > self.remaining:
            return self._refuse("repair", f"budget {budget} exceeds the {self.remaining} rollouts remaining", tool=tool)
        parent = self._best if init is None else int(init["index"])
        d = self.designs[parent]
        seeds = self.view_seeds["train"][:n_train]
        self._spend(budget, "repair", {"tool": tool, "design": parent, "budget": budget, "n_train": n_train})
        try:
            res = hp.plant_cma(d["body"], list(d["vector"]), tool_space(tool), plant=self._plant, budget=budget,
                               train_seeds=seeds, noise_seed=self._noise + 7919 * self._n_repairs, pool=self.pool,
                               variation=self.variation)
        except ValueError as exc:
            self.budget.refund(budget, "repair", {"tool": tool, "reason": str(exc)})
            return {"ok": False, "refused": f"tool {tool} unavailable for this design: {exc}"}
        self._n_repairs += 1
        used = int(res["rollouts_used"])
        if used < budget:
            self.budget.refund(budget - used, "repair", {"tool": tool, "unused": budget - used})
        best = res["best"]
        j = self._add_design(f"repair:{tool}", best["body"], best["vector"], parent=parent, tool=tool, n_train=n_train,
                             train_walking=int(best["walking_count"]), train_fitness=float(best["mean_fitness"]), rollouts=used)
        score = (int(best["walking_count"]) * (4 / n_train), int(best["survival_count"]) * (4 / n_train),
                 float(best["mean_fitness"]))
        if self._best_score is None or score > self._best_score:
            self._best_score, self._best = score, j
        return {"ok": True, "tool": tool, "design_index": j, "rollouts_used": used, "n_train": n_train,
                "best": {"body": copy.deepcopy(best["body"]), "vector": list(best["vector"]),
                         "train_walking": int(best["walking_count"]), "train_n": n_train,
                         "train_fitness": float(best["mean_fitness"])},
                "is_current_best": self._best == j}

    def select(self, index: int) -> dict:
        """Make an existing design the current best (e.g. after a robustness check favours it). Free."""
        if not (isinstance(index, int) and 0 <= index < len(self.designs)):
            return self._refuse("select", f"no design {index!r}")
        self._best = index
        self.budget.charge(0, "select", {"design": index})
        return {"ok": True, "design_index": index}

    def add_twin_design(self, body: dict, vector, *, source: str, parent: int | None = None, **extra) -> int:
        """Register a design produced on the twin (no plant cost) so plant instruments can run on it."""
        return self._add_design(f"twin:{source}", body, vector, parent=self._best if parent is None else parent, **extra)

    # ------------------------------------------------------------------ twin
    def _twin_seeds(self, role: str, n: int) -> list[int]:
        if role not in TWIN_ROLES:
            raise ValueError(f"the twin may use only {TWIN_ROLES}, got {role!r}")
        seeds = self.view_seeds[role]
        if not 1 <= n <= len(seeds):
            raise ValueError(f"role {role} has {len(seeds)} seeds, asked for {n}")
        return seeds[:n]

    def _twin_charge(self, n: int, item: str, detail: dict) -> bool:
        if n > self.twin.remaining:
            self.twin.charge(0, f"refused:{item}", {"reason": f"needs {n}, {self.twin.remaining} remain", **detail})
            return False
        self.twin.charge(n, item, detail)
        return True

    def twin_observe(self, deviation, design: dict, *, role: str = "obs", n: int | None = None, friction_mult: float = 1.0,
                     duration: float = 10.0, tag: str = "") -> dict | None:
        seeds = self._twin_seeds(role, self.n_obs if n is None else n)
        cost = len(seeds) * (2 if duration > 10.0 else 1)
        if not self._twin_charge(cost, "twin_observe", {"role": role, "n": len(seeds), "tag": tag}):
            return None
        return hp.observe(design["body"], design["vector"], seeds, plant={"deviation": deviation}, variation=self.variation,
                          duration=duration, pool=self.pool, friction_mult=friction_mult)

    def twin_walk(self, deviation, design: dict, *, role: str = "twin", n: int = 4, tag: str = "") -> list | None:
        seeds = self._twin_seeds(role, n)
        if not self._twin_charge(len(seeds), "twin_walk", {"role": role, "n": len(seeds), "tag": tag}):
            return None
        return hp.walk_seeds({"deviation": deviation}, design["body"], design["vector"], seeds, variation=self.variation,
                             pool=self.pool)

    def twin_cma(self, deviation, design: dict, tool: str, budget: int, *, role: str = "twin", n_train: int = 4,
                 noise_seed: int = 0, tag: str = "", ensemble: list | None = None) -> dict | None:
        """CMA-ES on the twin. `ensemble` (list of plants) judges every candidate across plausible plants (seed i on plant
        i mod K) instead of the single `deviation`."""
        seeds = self._twin_seeds(role, n_train)
        if budget < min_budget(tool, n_train):
            return None
        if not self._twin_charge(budget, "twin_cma", {"tool": tool, "role": role, "budget": budget, "tag": tag,
                                                      "ensemble": len(ensemble or [])}):
            return None
        res = hp.plant_cma(design["body"], list(design["vector"]), tool_space(tool), plant={"deviation": deviation},
                           budget=budget, train_seeds=seeds, noise_seed=noise_seed, pool=self.pool, variation=self.variation,
                           ensemble=ensemble)
        used = int(res["rollouts_used"])
        if used < budget:
            self.twin.refund(budget - used, "twin_cma", {"tool": tool, "unused": budget - used})
        return res

    def twin_weigh(self, deviation, design: dict) -> dict:
        """Static mass/COM of the twin with a hypothesised deviation: a model computation, no rollout cost."""
        return static_mass_com({"deviation": deviation}, design["body"])
