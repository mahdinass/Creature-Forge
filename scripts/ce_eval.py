"""Causal-engineer episode runner: every (instance, policy) pair on the same Workbench, budget and seeds, then independent verification.

  python scripts/ce_eval.py --instances inst.jsonl --policies scientist,scientist_1shot,exhaustive,expert,random,blind \
      --budget 700 --out results.jsonl [--shard 0/4] [--resume] [--workers 2] [--source live|scripted --fixture replies.json]

Reads the `kept` instances of a `scripts/fault_bench_build.py` file. A policy only ever receives `fault_bench.policy_view(instance)` (an opaque
id, the faulty robot, train/obs seeds). The runner adds the ground truth (fault, severity, matching tool) to the record AFTER the policy
finished, verifies the submitted design with `fault_bench.verify` (full_recovery_v1, uncharged, hidden seeds) and maps the scientist's
diagnosis category to the injected mechanism with HIDDEN_MAPPING, which lives only here. Append-only JSONL; run on the VM (MuJoCo).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creature_forge import ce_policies as cp  # noqa: E402
from creature_forge import fault_bench as fb  # noqa: E402

VERSION = "ce_eval_v1"
# scientist_think (dev 2026-10-17): the iterative scientist with the model's thinking ENABLED (same model, schema and budget).
# *_mem arms: the same scientist with retrieved experience (Levels A/B, `creature_forge.ce_memory`); needs --memory-probe.
SCIENTIST_ARMS = {"scientist": ("iterative", False, False), "scientist_1shot": ("one_shot", False, False),
                  "scientist_think": ("iterative", True, False), "scientist_1shot_think": ("one_shot", True, False),
                  "scientist_think_mem": ("iterative", True, True), "scientist_1shot_think_mem": ("one_shot", True, True)}
POLICIES = tuple(SCIENTIST_ARMS) + ("exhaustive", "expert", "random", "blind")


def thinking_config():
    from creature_forge.investigation import load_model_config
    import dataclasses
    cfg = load_model_config("default")
    return dataclasses.replace(cfg, max_tokens=16000, extra_body={"chat_template_kwargs": {"enable_thinking": True}},
                               timeout_s=300.0).validate()

# Ground-truth mapping from the injected benchmark mechanism to the scientist's neutral diagnosis taxonomy. EVALUATION ONLY: the scientist
# module never imports or sees this table. The taxonomy's decoys (low_joint_impedance, leg_geometry_mismatch, gait_initiation_failure,
# unresolved) match no fault.
HIDDEN_MAPPING = {
    "posture_lean": "posture_bias",
    "cadence_fast": "cadence_too_fast",
    "feedback_loss": "weak_balance_feedback",
    "placement_loss": "poor_foot_placement",
    "short_feet": "short_support_base",
    "heavy_torso": "heavy_upper_body",
    "weak_motors": "low_torque_authority",
    "slippery": "low_traction",
}
FORBIDDEN_VIEW_KEYS = {"fault", "severity", "repair_matrix", "matching_tool", "ranking", "check", "validate", "confirm", "changes"}


def _h(*parts) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:4], "big") % (2 ** 31)


def load_instances(path: str, kept_only: bool = True) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rec = json.loads(line)
                if rec.get("kept") or not kept_only:
                    out.append(rec)
    return out


def done_pairs(path: str) -> set:
    if not os.path.exists(path):
        return set()
    out = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                out.add((r["instance_id"], r["policy"]))
    return out


def _assert_blind_view(view: dict) -> None:
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in FORBIDDEN_VIEW_KEYS:
                    raise AssertionError(f"policy view leaks {path}{k}")
                walk(v, path + k + ".")
    walk(view)


def default_bench(view: dict, *, budget: int, n_train: int, n_obs: int, pool, noise_seed: int):
    return cp.UnionWorkbench(view["robot"], total_budget=budget, seeds=view["seeds"], pool=pool, n_train=n_train, n_obs=n_obs,
                             noise_seed=noise_seed)


def default_features(body: dict) -> dict:
    from creature_forge import creature_gen as cg
    try:
        return {k: v for k, v in cg.features(body).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    except Exception:       # noqa: BLE001 - descriptive context only
        return {}


def _llm(rec: dict | None) -> dict:
    if not rec:
        return {"calls": 0, "cost_usd": 0.0, "latency_s": 0.0, "tokens": {"prompt": 0, "completion": 0}}
    return {"calls": rec.get("n_model_calls", len(rec.get("calls", []))), "cost_usd": rec.get("cost_usd", 0.0),
            "latency_s": rec.get("latency_s", 0.0), "tokens": rec.get("tokens"), "provenance": rec.get("provenance"),
            "model": rec.get("model")}


def evaluate(instance: dict, policy: str, *, budget: int = 700, n_train: int = 4, n_obs: int = 4, pool=None, bench_factory=None,
             verify_fn=None, scientist_factory=None, features_fn=None, source: str = "live", fixture=None, max_steps: int = 12,
             memory=None, memory_exclude_own_base: bool = True) -> dict:
    """One (instance, policy) episode -> record (JSON-safe)."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}; known: {list(POLICIES)}")
    t0 = time.time()
    view = fb.policy_view(instance)
    view = {**view, "features": (features_fn or default_features)(view["robot"]["body"])}
    _assert_blind_view(view)
    noise = _h(instance["instance_id"], "bench")
    bench = (bench_factory or default_bench)(view, budget=budget, n_train=n_train, n_obs=n_obs, pool=pool, noise_seed=noise)
    rec = {"version": VERSION, "policy": policy, "instance_id": instance["instance_id"], "split": instance.get("split"),
           "base_id": instance["base_id"], "region": instance.get("region"), "budget": budget, "n_train": n_train, "n_obs": n_obs,
           "bench_noise_seed": noise}
    prec = None
    llm_rec = None
    try:
        if policy in SCIENTIST_ARMS:
            mode, think, use_mem = SCIENTIST_ARMS[policy]
            order_seed = _h(instance["instance_id"], "order")
            if scientist_factory is not None:
                sci = scientist_factory(mode=mode, order_seed=order_seed)
            else:
                from creature_forge.scientist import Scientist
                sci = Scientist(mode, source=source, fixture=fixture, order_seed=order_seed, max_steps=max_steps,
                                config=thinking_config() if (think and source == "live") else None)
            mem = None
            if use_mem:
                if memory is None:
                    raise ValueError(f"policy {policy} needs a memory bank (--memory-probe)")
                from creature_forge import ce_memory
                mem = ce_memory.adapter_for(memory, exclude_base=instance["base_id"] if memory_exclude_own_base else None)
            prec = sci.investigate(bench, view, memory=mem)
            if mem is not None:
                prec["memory_meta"] = {"bank_episodes": len(mem.bank.episodes), "cards": len(mem.cards),
                                       "excluded_own_base": bool(memory_exclude_own_base)}
            llm_rec = prec
        else:
            pol = cp.make_policy(policy, seed=_h(instance["instance_id"], "random"))
            prec = pol.run(bench, view)
        design = bench.best_design()
        ledger = bench.ledger()
        rec["error"] = None
    except Exception as e:      # noqa: BLE001 - ERROR is distinct from FAIL; recorded, not verified
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["verification"] = None
        rec["verified"] = None
        rec["ledger"] = bench.ledger()
        rec["wall_s"] = time.time() - t0
        _truth(rec, instance)
        return rec
    ver = (verify_fn or fb.verify)(instance, {"body": design["body"], "vector": design["vector"]}, pool)
    status = ver.get("status")
    wf = (ver.get("validation") or {}).get("walking_frac")
    rec.update(verification={"status": status, "walking_frac": wf, "reasons": ver.get("reasons"), "rollouts": ver.get("rollouts")},
               verified=(status == "FULL_RECOVERY"), walking_frac=wf, ledger=ledger, rollouts_used=ledger["used"],
               n_counterfactuals=sum(1 for l in ledger["lines"] if l["item"] == "counterfactual" and l["n"] > 0),
               n_repairs=sum(1 for l in ledger["lines"] if l["item"] == "repair" and l["n"] > 0),
               n_experiments=sum(1 for l in ledger["lines"] if l["item"] in ("counterfactual", "observe") and l["n"] > 0),
               submitted_design={"index": design["index"], "source": design["source"]}, llm=_llm(llm_rec),
               policy_record=prec, wall_s=time.time() - t0)
    _truth(rec, instance)
    if policy in SCIENTIST_ARMS:
        fin = prec.get("final") or {}
        cat = fin.get("diagnosis_category")
        rec["diagnosis"] = {"category": cat, "ended_by": fin.get("ended_by"), "confidence": fin.get("confidence"),
                            "injected_category": HIDDEN_MAPPING[instance["fault"]],
                            "match": (cat == HIDDEN_MAPPING[instance["fault"]]) if cat else False}
        rec["prediction_accuracy"] = prec.get("prediction_summary")
        rec["provenance"] = prec.get("provenance")
    return rec


def _truth(rec: dict, instance: dict) -> None:
    """Ground truth, added by the runner after the policy finished."""
    rec["fault"] = instance["fault"]
    rec["severity"] = instance["severity"]
    rec["matching_tool"] = instance.get("matching_tool")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", required=True)
    ap.add_argument("--policies", default=",".join(POLICIES))
    ap.add_argument("--budget", type=int, default=700)
    ap.add_argument("--n-train", type=int, default=4)
    ap.add_argument("--n-obs", type=int, default=4)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--source", choices=("live", "scripted"), default="live")
    ap.add_argument("--fixture", help="JSON list of scripted scientist replies (with --source scripted)")
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="stop after this many (instance, policy) pairs")
    ap.add_argument("--memory-probe", help="probe-dataset jsonl(s) (comma-separated) of TRAINING robots for the *_mem arms")
    ap.add_argument("--memory-episodes", help="comma-separated ce_eval result files of TRAINING robots added to the bank")
    ap.add_argument("--memory-keep-own-base", action="store_true",
                    help="do not exclude the robot's own base from memory (default: excluded, for development transfer tests)")
    ap.add_argument("--instance-ids", nargs="*", help="restrict to these instance ids (development)")
    a = ap.parse_args(argv)
    pols = [p for p in a.policies.split(",") if p]
    bad = [p for p in pols if p not in POLICIES]
    if bad:
        ap.error(f"unknown policies {bad}; known: {list(POLICIES)}")
    memory = None
    if a.memory_probe:
        from creature_forge import ce_memory
        rows = [json.loads(l) for path in a.memory_probe.split(",") for l in open(path, encoding="utf-8") if l.strip()]
        eps = [json.loads(l) for path in (a.memory_episodes or "").split(",") if path for l in open(path, encoding="utf-8") if l.strip()]
        memory = ce_memory.build_bank(rows, eps)
        print(f"memory bank: {len(memory.episodes)} episodes from {len(rows)} probe rows and {len(eps)} episode records", flush=True)
    if any(SCIENTIST_ARMS.get(p, (0, 0, False))[2] for p in pols) and memory is None:
        ap.error("*_mem policies need --memory-probe")
    i, k = (int(x) for x in a.shard.split("/"))
    if not 0 <= i < k:
        ap.error("--shard must be i/k with 0 <= i < k")
    fixture = None
    if a.source == "scripted":
        if not a.fixture:
            ap.error("--source scripted needs --fixture")
        with open(a.fixture, encoding="utf-8") as fh:
            fixture = json.load(fh)
    insts = [r for path in a.instances.split(",") for r in load_instances(path)]
    if a.instance_ids:
        insts = [r for r in insts if r["instance_id"] in set(a.instance_ids)]
    pairs = [(inst, p) for inst in insts for p in pols]
    pairs = [x for n, x in enumerate(pairs) if n % k == i]
    if a.resume:
        seen = done_pairs(a.out)
        pairs = [(inst, p) for inst, p in pairs if (inst["instance_id"], p) not in seen]
    elif os.path.exists(a.out) and os.path.getsize(a.out):
        ap.error(f"{a.out} exists; use --resume (the file is append-only)")
    if a.limit:
        pairs = pairs[: a.limit]
    print(f"{len(pairs)} episode(s)", flush=True)
    from creature_forge.forge_pool import ForgePool
    with ForgePool(max_workers=a.workers) as pool, open(a.out, "a", encoding="utf-8") as out:
        for n, (inst, p) in enumerate(pairs):
            r = evaluate(inst, p, budget=a.budget, n_train=a.n_train, n_obs=a.n_obs, pool=pool, source=a.source,
                         fixture=json.loads(json.dumps(fixture)) if fixture is not None else None, max_steps=a.max_steps,
                         memory=memory, memory_exclude_own_base=not a.memory_keep_own_base)
            out.write(json.dumps(r, sort_keys=True) + "\n")
            out.flush()
            print(f"[{n + 1}/{len(pairs)}] {inst['instance_id']} {p} status={(r.get('verification') or {}).get('status')} "
                  f"used={r.get('rollouts_used')} err={r.get('error')} t={r['wall_s']:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
