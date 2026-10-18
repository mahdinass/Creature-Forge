"""Deterministic replay attribution for HaS episodes (phase 3, docs/HAS_SCIENTIST.md §7.3).

Re-runs the belief engine's inference on the RECORDED plant measurements of an episode (same experiments, same order, same
seeds), with a chosen set of proposal sources, and returns the posterior trajectory. Contrasts on identical evidence:
  generic + nemotron   vs   generic only      -> what Nemotron's hypotheses add to the physical belief
  nemotron only        vs   generic only      -> how good Nemotron's hypotheses are on their own
No plant rollout is run (the plant data are read from the record); twin rollouts are run and reported (twin ledger).
"""
from __future__ import annotations

from . import belief_engine as be
from . import hdb_bench as hb
from .hdb_workbench import HDBWorkbench
from .scientist_has import HasNemotron


def nemotron_proposals(rec: dict) -> list[list[list[dict]]]:
    """Per proposer call, the validated deviations Nemotron proposed (in call order)."""
    out = []
    for e in (rec.get("nemotron") or {}).get("log", []):
        if e["role"] != "propose" or e["status"] != "ok":
            continue
        devs = []
        for h in (e.get("parsed") or {}).get("hypotheses", []):
            try:
                devs.append(HasNemotron.to_deviation(h))
            except Exception:   # noqa: BLE001 - invalid ones were rejected live too
                continue
        out.append(devs)
    return out


def replay(rec: dict, *, use_generic: bool = True, use_nemotron: bool = True, pool=None, twin_budget: int = 2800) -> dict:
    """Posterior trajectory of the recorded episode under the chosen proposal sources."""
    base_id, fam, sev = rec["instance_id"].rsplit(":", 2)
    seeds = hb.instance_seeds(base_id, fam, int(sev))
    initial = next(d for d in rec["designs"] if d["index"] == 0)
    view = {"robot_id": "replay", "robot": {"body": initial["body"], "vector": initial["vector"]},
            "seeds": {r: seeds[r] for r in hb.POLICY_ROLES}}
    bench = HDBWorkbench(view, {}, twin_budget=twin_budget, pool=pool)      # plant instruments are never called
    calls = nemotron_proposals(rec) if use_nemotron else []
    ep = be.Episode(bench, use_generic=use_generic)
    exps = [e for e in rec["engine"]["experiments"]]
    traj = []
    inj = [tuple(x) for x in (rec.get("injected_structure") or [])]

    def snap(label):
        sp = ep.structure_posterior()
        traj.append({"after": label, "map": [list(x) for x in sp[0][0]] if sp else None, "map_mass": sp[0][1] if sp else 0.0,
                     "mass_on_injected": sum(w for s, w in sp if list(s) == inj), "twin_used": bench.twin.used,
                     "n_particles": len(ep.particles)})
    for i, e in enumerate(exps):
        exp = dict(e)
        if e["kind"] == "counterfactual":
            from .eng_tools import parse_counterfactual
            from .fault_bench import apply_changes
            cid = e["id"].split(":", 2)[-1]
            body, vec = apply_changes(initial["body"], initial["vector"], parse_counterfactual(cid))
            exp["design"] = {"body": body, "vector": vec}
        else:
            exp["design"] = {"body": initial["body"], "vector": initial["vector"]}
        if "features" in exp:
            exp["features"] = {int(s): f for s, f in exp["features"].items()}
        ep._register(exp)
        if i == 0 and use_generic:
            ep._screen_generic()
        if i < len(calls):
            ep.add_particles(calls[i], "proposer")
        ep.refine()
        ep.prune()
        snap(e["id"])
    return {"instance_id": rec["instance_id"], "use_generic": use_generic, "use_nemotron": use_nemotron,
            "injected": [list(x) for x in inj], "trajectory": traj, "twin_used": bench.twin.used}
