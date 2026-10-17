"""Building the scientist's experience (Levels A and B) from training data, and per-robot memory adapters.

Sources (TRAINING robots only; the caller passes only training-split rows):
  probe rows   `scripts/ce_probe_dataset.py`: the faulty robot's initial observation, its measured responses to the fixed
               counterfactual catalogue and its measured repair matrix -> one "probe" episode per instance (policy "probe").
  episodes     ce_eval records of earlier investigations (any policy, e.g. pilot runs), joined with the instance's observation
               and repair matrix.
Every episode carries `group_key`, an opaque hash of its base robot, so a development run can exclude the robot's own morphology
(`adapter_for(..., exclude_base=...)`): memory then comes only from OTHER robots. Mechanism cards are rebuilt per adapter from the
retained episodes. Nothing here reads fault labels.
"""
from __future__ import annotations

import hashlib

from . import experience_bank as xb
from .scientist import tolerance

VERSION = "ce_memory_v1"


def group_key(base_id: str) -> str:
    return "G-" + hashlib.sha256(("group|" + str(base_id)).encode()).hexdigest()[:8]


def _probe_record(row: dict) -> dict:
    """A ce_eval-shaped record for a probe row (only the fields `episode_from_record` reads)."""
    obs = row["observation"]
    exps = []
    for cid, r in sorted(row.get("counterfactuals", {}).items()):
        if "observation" not in r:
            continue
        base_med, new_med = obs.get("median") or {}, r["observation"].get("median") or {}
        q = {}
        for k, v in new_med.items():
            b = base_med.get(k)
            if isinstance(v, (int, float)) and isinstance(b, (int, float)) and not isinstance(v, bool):
                q[k] = {"delta": v - b, "tolerance": tolerance(k, b)}
        exps.append({"kind": "counterfactual", "status": "ok", "change": cid,
                     "outcome": {"n_walking_base": obs.get("n_walking"), "n_walking": r["observation"].get("n_walking"), "quantities": q}})
    return {"policy": "probe", "instance_id": row["instance_id"], "n_obs": len(obs.get("per_seed") or []) or 4, "n_train": 4,
            "policy_record": {"initial_observation": {"median": obs.get("median")}, "experiments": exps},
            "verification": {"status": None, "walking_frac": None}}


def build_bank(probe_rows: list[dict], episode_records: list[dict] = ()) -> xb.ExperienceBank:
    by_id = {r["instance_id"]: r for r in probe_rows}
    bank = xb.ExperienceBank()
    for row in probe_rows:
        inst = {"features": row.get("features"), "repair_matrix": row.get("repair_matrix"),
                "initial_observation": {"median": (row.get("observation") or {}).get("median")}}
        ep = xb.episode_from_record(_probe_record(row), inst)
        ep["group_key"] = group_key(row["base_id"])
        bank.add(ep)
    for rec in episode_records:
        row = by_id.get(rec.get("instance_id"))
        if row is None:
            continue
        inst = {"features": row.get("features"), "repair_matrix": row.get("repair_matrix"),
                "initial_observation": {"median": (row.get("observation") or {}).get("median")}}
        ep = xb.episode_from_record(rec, inst)
        ep["group_key"] = group_key(row["base_id"])
        bank.add(ep)
    return bank


def adapter_for(bank: xb.ExperienceBank, *, exclude_base: str | None = None, mode: str = "episodes+cards", k_episodes: int = 2,
                k_cards: int = 1) -> xb.MemoryAdapter:
    sub = bank.subset([group_key(exclude_base)] if exclude_base else [])
    cards = xb.build_cards(list(sub.episodes.values()))
    return xb.MemoryAdapter(sub, cards, k_episodes=k_episodes, k_cards=k_cards, mode=mode)
