"""Stage-2 runner (phase 3): the autonomous HaS scientist (`has_agent`) and its non-LLM controls on Hidden-Damage Bench dev instances.

Arms (identical instruments, plant budget 700, twin cap 2,800, same seeds, same calibrated stopping map):
  A1e   engine only, driven through the agent loop with every decision delegated. It must reproduce A1c5 (equivalence check).
  A2    A1e + the learned amortised posterior's suggestions after the first observation (no LLM)
  A3    Nemotron directs the investigation (no memory, no learned posterior)
  A4    A3 + experience: frozen mechanism dossiers (--memory) and the learned posterior as a tool (--learned)
  A4m   A3 + dossiers only
DS-1 (docs/DS1_PROTOCOL.md; engine v6 settings via --v6, displacement-aware workbench, stop map via --stop-model):
  A1e6  engine v6, every decision delegated (the non-LLM comparator with the same instruments)
  A3v5  Nemotron (agent v5) on engine v6, no experience
  A4x   A3v5 + the shared case store (--cases: case evidence, repair-outcome model, track record) and dual-scored
        dossiers (--memory, rescored on the store's summaries)
Development only: nothing here is a registered comparison.

Usage (VM): python scripts/hdb_agent_run.py --arm A3 --split-file experiments/causal_engineer/dev/hdb/stage2_split.json
            --which transfer --thresholds artifacts/hdb/thresholds_dev.json --stop-model experiments/.../stopmap_dev_v1.json
            --mults 1.3 --limit 12 --workers 3 --shard 0/2 --out artifacts/hdb/s2_A3.jsonl [--source scripted --fixture f.json]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from creature_forge import belief_engine as be                    # noqa: E402
from creature_forge import has_agent as ha                        # noqa: E402
from creature_forge import hdb_bench as hb                        # noqa: E402
from creature_forge.forge_pool import ForgePool, InlinePool       # noqa: E402
from creature_forge.hdb_workbench import HDBWorkbench             # noqa: E402
from creature_forge.optimize import jsonable                      # noqa: E402

ARMS = ("A1e", "A2", "A3", "A4", "A4m", "A4lfo", "A4bad", "A1e6", "A3v5", "A4x")   # A4lfo / A4bad: A4 with the leave-family-out / corrupted memory
V6_ARMS = ("A1e6", "A3v5", "A4x")


def instances(a) -> list[tuple]:
    split = json.load(open(a.split_file, encoding="utf-8"))
    if a.which in ("init", "stream"):          # DS-1 subsets of the experience bases (pre-declared hash rule)
        from creature_forge import has_cases as hc
        want = hc.ds1_init_bases(split) if a.which == "init" else hc.ds1_stream_bases(split)
    else:
        want = split[f"{a.which}_bases"]
    bases = [b for b in hb.load_bases("dev") if b["base_id"] in set(want)]
    if a.devcomp:          # development compositions: (base, pair, None)
        from creature_forge import hdb_devcomp
        out = [(b, p, None) for b in bases for p in hdb_devcomp.candidate_pairs()]
        if a.sample:
            import random
            random.Random(a.sample_seed).shuffle(out)
        return out
    fams = a.families.split(",") if a.families else list(hb.FAMILY_SPECS)
    mults = {float(x) for x in a.mults.split(",")}
    out = []
    for b in bases:
        for f in fams:
            for s, (_, m) in enumerate(hb.v2_severities(f)):
                if m in mults:
                    out.append((b, f, s))
    if a.which == "transfer":
        skip = set(split.get("excluded_from_transfer_eval") or [])
        out = [t for t in out if hb.instance_key(t[0]["base_id"], t[1], t[2]) not in skip]
    if a.sample:
        import random
        random.Random(a.sample_seed).shuffle(out)
    return out


def run_one(inst: dict, pool, a, cases=None) -> dict:
    t0 = time.perf_counter()
    view = hb.policy_view(inst)
    v6 = a.arm in V6_ARMS
    wb = HDBWorkbench
    if v6:
        from creature_forge.hdb_evidence import EvidenceWorkbench as wb
    bench = wb(view, inst["plant"], total_budget=a.budget, twin_budget=a.twin_budget, pool=pool,
               noise_seed=int.from_bytes(inst["instance_id"].encode()[:4], "big") % (2 ** 31))
    stop_model = json.load(open(a.stop_model, encoding="utf-8"))
    ep = be.Episode(bench, proposer=None, use_generic=True, max_alive=12,
                    v6=json.load(open(a.v6, encoding="utf-8")) if v6 else None)
    memory = learned = None
    if a.arm.startswith("A4") and a.arm != "A4x":
        from creature_forge.has_memory import Memory
        memory = Memory.load(a.memory, frozen=True)
    if a.arm == "A4x":
        from creature_forge.has_cases import DualMemory
        if cases is None:
            from creature_forge.has_cases import CaseStore
            cases = CaseStore.load(a.cases, frozen=True)
        memory = DualMemory.load(a.memory, frozen=True)
        memory.rescore(cases.summaries)
    if a.arm in ("A2", "A4", "A4lfo", "A4bad"):
        from creature_forge.amortized_posterior import LearnedPosterior
        learned = LearnedPosterior.load(a.learned)
    session = ha.LabSession(bench, ep, stop_model=stop_model, tau=a.tau, memory=memory, learned=learned,
                            v5=a.arm in ("A3v5", "A4x"), cases=cases if a.arm == "A4x" else None)
    sci = None
    if (a.arm in ("A3", "A3v5") or a.arm.startswith("A4")) and not a.no_scientist:
        cfg = None
        if a.source == "live":
            from ce_eval import thinking_config
            cfg = thinking_config()
        fixture = json.load(open(a.fixture, encoding="utf-8")) if a.fixture else None
        sci = ha.NemotronScientist(source=a.source, config=cfg, design=view["robot"], fixture=fixture,
                                   investigation_id=f"agent-{a.arm}-{view['robot_id']}", v5=a.arm in ("A3v5", "A4x"))
    rec_agent = ha.run_agent(session, sci, max_turns=a.max_turns, auto_learned=(a.arm == "A2"))
    design = bench.best_design()
    ver = hb.verify(inst, {"body": design["body"], "vector": design["vector"]}, pool=pool)
    inj = [list(x) for x in hb.mechanism_signature(inst)]
    sp = ep.structure_posterior()
    return jsonable({
        "version": "hdb_agent_v1", "instance_id": inst["instance_id"], "family": inst["family"], "pair": inst["pair"],
        "severity": inst["severity"], "bench": inst["version"], "strength": inst.get("strength"), "mult": inst.get("mult"),
        "provenance": sci.provenance if sci else "NO_AI", "arm": a.arm + ("-noscientist" if a.no_scientist else ""),
        "check": inst["check"],
        "nemotron": sci.record() if sci else None, "agent": rec_agent,
        "injected_structure": inj, "map_structure": [list(x) for x in sp[0][0]] if sp else None,
        "map_mass": sp[0][1] if sp else 0.0, "posterior_mass_on_injected": sum(w for s, w in sp if [list(x) for x in s] == inj),
        "repair": (rec_agent.get("conclusion") or {}).get("repair"), "submitted": design["index"],
        "verification": {"status": ver["status"], "walking_frac": ver["validation"]["walking_frac"], "reasons": ver["reasons"],
                         "rollouts": ver["rollouts"]},
        "stop_rule": {"model": a.stop_model, "tau": a.tau}, "memory": a.memory if memory else None,
        "cases": a.cases if a.arm == "A4x" else None, "v6_settings": a.v6 if v6 else None,
        "learned": a.learned if learned else None, "learned_last": getattr(learned, "last", None),
        "engine": ep.record(), "designs": [{k: d[k] for k in ("index", "source", "body", "vector")} for d in bench.designs],
        "wall_s": time.perf_counter() - t0})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--split-file", required=True)
    ap.add_argument("--which", choices=["experience", "transfer", "init", "stream"], required=True)
    ap.add_argument("--families", default=None)
    ap.add_argument("--mults", default="1.3")
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--stop-model", required=True)
    ap.add_argument("--tau", type=float, default=0.75)
    ap.add_argument("--budget", type=int, default=700)
    ap.add_argument("--twin-budget", type=int, default=2800)
    ap.add_argument("--max-turns", type=int, default=ha.MAX_TURNS)
    ap.add_argument("--memory", default=None)
    ap.add_argument("--learned", default=None)
    ap.add_argument("--v6", default=None, help="engine v6 settings json (temperature, misfit threshold): DS-1 arms")
    ap.add_argument("--cases", default=None, help="frozen case store (A4x)")
    ap.add_argument("--no-scientist", action="store_true",
                    help="equivalence check: the arm's instruments and experience with every decision delegated")
    ap.add_argument("--exclude-ids", default=None, help="file of instance ids never to run (e.g. all ids in earlier records)")
    ap.add_argument("--source", choices=["live", "scripted"], default="live")
    ap.add_argument("--fixture", default=None)
    ap.add_argument("--sample", action="store_true", help="shuffle the instance list with --sample-seed before --limit")
    ap.add_argument("--sample-seed", type=int, default=20261019)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default=None, help="comma list of instance ids")
    ap.add_argument("--devcomp", action="store_true", help="development compositions (hdb_devcomp) instead of single families")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.arm.startswith("A4") and not a.memory:
        raise SystemExit("A4 arms need --memory")
    if a.arm in V6_ARMS and not a.v6:
        raise SystemExit("DS-1 arms need --v6")
    if a.arm == "A4x" and not a.cases:
        raise SystemExit("A4x needs --cases")
    if a.arm in ("A2", "A4", "A4lfo", "A4bad") and not a.learned:
        raise SystemExit("A2/A4 need --learned")
    th = json.load(open(a.thresholds, encoding="utf-8"))
    todo = instances(a)
    if a.only and not a.devcomp:
        keep = set(a.only.split(","))
        todo = [t for t in todo if hb.instance_key(t[0]["base_id"], t[1], t[2]) in keep]
    if a.exclude_ids:
        bad = {l.strip() for l in open(a.exclude_ids, encoding="utf-8") if l.strip()}
        todo = [t for t in todo if (hb.instance_key(t[0]["base_id"], t[1], t[2]) if not a.devcomp else None) not in bad]
    k, n = (int(x) for x in a.shard.split("/"))
    done = set()
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as fh:
            done = {json.loads(l)["instance_id"] for l in fh if l.strip()}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    pool_cm = ForgePool(max_workers=a.workers) if a.workers else contextlib.nullcontext(InlinePool())
    taken = 0
    with pool_cm as pool, open(a.out, "a", encoding="utf-8") as out:
        for i, (b, f, s) in enumerate(todo):
            if a.devcomp:
                from creature_forge import hdb_devcomp
                raw = hdb_devcomp.make_instance(b, f, th)
                iid = raw["instance_id"] if raw else None
            else:
                iid = hb.instance_key(b["base_id"], f, s)
                raw = hb.make_instance_v2(b, f, s, th)
            if raw is None:
                continue
            if a.exclude_ids and a.devcomp and raw["instance_id"] in bad:
                continue
            if a.only and a.devcomp and raw["instance_id"] not in set(a.only.split(",")):
                continue
            inst = hb.check_eligibility(raw, pool=pool)
            if not inst["eligible"]:
                continue
            taken += 1
            if a.limit and taken > a.limit:
                break
            if (taken - 1) % n != k or iid in done:
                continue
            rec = run_one(inst, pool, a)
            out.write(json.dumps(rec) + "\n")
            out.flush()
            nem = rec.get("nemotron") or {}
            print(iid, rec["arm"], rec["map_structure"], round(rec["posterior_mass_on_injected"], 3),
                  rec["verification"]["status"], f"${nem.get('cost_usd', 0):.4f}", round(rec["wall_s"]), flush=True)


if __name__ == "__main__":
    main()
