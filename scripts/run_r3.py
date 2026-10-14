"""Staged R3 runner. Every stage requires the committed, unmodified, code-consistent R3 protocol.

Physics stages run on the Nebius VM (free-memory floor); the model stage runs where NEBIUS_API_KEY lives (the key is never copied to the VM).

    python scripts/run_r3.py estimate      # offline: token ceiling for the 30 prompts built from contexts.json (needs the freeze) or a sizing sample
    python scripts/run_r3.py pilot         # <= 100 rollouts: physics path + throughput + memory (pilot seeds 9500-9515)
    python scripts/run_r3.py evidence      # theta0 on the 180 evidence-pool seeds (once)
    python scripts/run_r3.py screenpool    # theta0 on the 64 screen-pool seeds (once)
    python scripts/run_r3.py freeze        # 0 rollouts: contexts.json (15 contexts + prompts + hashes) and the 16 screening seeds -> COMMIT
    python scripts/run_r3.py live --confirm-live        # 30 model requests (approved caps); writes requests.jsonl
    python scripts/run_r3.py candidates    # 0 rollouts: candidates.json (model + matched random + heuristic) -> COMMIT before any simulation
    python scripts/run_r3.py screen        # simulate all candidates on the 16 screening seeds
    python scripts/run_r3.py validate      # top-3 per arm + theta0 on the 64 validation seeds
    python scripts/run_r3.py analyze       # prespecified analysis -> analysis.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from creature_forge import r1, r2, r3  # noqa: E402
from creature_forge.nebius import Limits, NebiusClient  # noqa: E402
from creature_forge.optimize import Executor, provenance  # noqa: E402

RES = r3.RESULTS
STORE = r3.SEED_FIELDS + ("walking",)


def load(name):
    return json.loads((RES / name).read_text(encoding="utf-8"))


def slim(m: dict) -> dict:
    return {k: m.get(k) for k in STORE} | {"fitness_total": m["fitness"]["total"]}


def workers_for(args) -> int:
    p = RES / "pilot.json"
    if not p.exists():
        raise SystemExit("run the pilot first")
    d = load("pilot.json")
    if not d["passed"]:
        raise SystemExit("the pilot failed its resource checks; stopping")
    return min(args.workers, r3.MAX_WORKERS, d["recommended_workers"])


def stage_pilot(args, ledger):
    theta = r2.incumbent_theta()
    w = min(args.workers, r3.MAX_WORKERS)
    free_before = r1.free_memory_gb()
    if free_before < r3.MIN_FREE_GB:
        raise SystemExit(f"free memory {free_before:.2f} GB is below the {r3.MIN_FREE_GB} GB floor: not starting")
    edits = [*r3.HEURISTIC_EDITS[:3], tuple(r3.matched_random_edits("M", 0, 0, [0.1, 0.05]))]
    vecs = [theta] + [r3.apply_edits(theta, e) for e in edits] + [r3.apply_edits(theta, r3.matched_random_edits("N", 1, 2, [0.12]))]
    t0 = time.perf_counter()
    with Executor(w, timeout_s=900, fn=r2.r2_job) as ex:
        outs = r3.run_batch(ex, ledger, "pilot", vecs, r3.PILOT_SEEDS, "pilot: theta0 + 3 heuristic edits + 2 matched-random edits")
    wall = time.perf_counter() - t0
    n = len(vecs) * len(r3.PILOT_SEEDS)
    peak = max(o["peak_rss_mb"] for o in outs)
    rate = n / wall
    plan = r3.planned_rollouts()
    rec_workers = max((k for k in range(1, w + 1) if k * peak / 1024 <= 0.5 * free_before), default=0)
    checks = {"no_job_errors": all(o["ok"] for o in outs), "free_memory_after_ok": r1.free_memory_gb() >= r3.MIN_FREE_GB,
              "projected_wall_within_80pct_of_limit": (plan["total_max"] - 96) / rate <= 0.8 * r3.WALL_LIMIT_S,
              "memory_headroom_for_some_worker_count": rec_workers >= 1, "rollouts_within_pilot_cap": n <= r3.PILOT_CAP,
              "planned_maximum_within_cap": plan["total_max"] <= r3.BUDGET_CAP}
    res = {"rollouts": n, "pilot_seeds": [min(r3.PILOT_SEEDS), max(r3.PILOT_SEEDS)], "workers_used": w, "wall_s": wall, "throughput_rollouts_per_s": rate,
           "peak_worker_rss_mb": peak, "free_memory_gb_before": free_before, "recommended_workers": rec_workers, "planned": plan,
           "projected_wall_s_at_this_rate": (plan["total_max"] - 96) / rate, "checks": checks, "passed": all(checks.values()), "provenance": provenance(w),
           "use": "implementation and resource checks only"}
    r3.write_json(RES / "pilot.json", res)
    print(json.dumps({k: v for k, v in res.items() if k != "provenance"}, indent=1))
    if not res["passed"]:
        raise SystemExit("PILOT FAILED its resource checks")


def stage_pool(args, ledger, name, seeds, out):
    w = workers_for(args)
    if (RES / out).exists():
        raise SystemExit(f"{out} exists: theta0 is run once on this pool")
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        res = r3.run_batch(ex, ledger, name, [r2.incumbent_theta()], seeds, f"theta0 on the {name} seeds (once)")[0]
    if not res["ok"]:
        raise SystemExit("theta0 pool run failed: " + res["error"])
    per = res["result"]["per_seed"]
    r3.write_json(RES / out, {"seeds": list(seeds), "walking": int(sum(m["walking"] for m in per)), "per_seed": [slim(m) for m in per]})
    print(f"{name}: theta0 walking {sum(m['walking'] for m in per)}/{len(per)}")


def stage_freeze(args, ledger):
    if r3.CONTEXTS.exists():
        raise SystemExit("contexts.json exists: frozen")
    theta = r2.incumbent_theta()
    ev, sp = load("evidence_pool.json"), load("screen_pool.json")
    ctx = r3.build_contexts(theta, ev["per_seed"])
    scr = r3.select_screening_seeds(sp["per_seed"])
    out = {**ctx, "screening": scr}
    if not scr["stop"]:
        by = {m["seed"]: m for m in sp["per_seed"]}
        out["theta0_on_screening_seeds"] = {"derived_from_screen_pool_no_new_rollouts": True, "walking_count": sum(bool(by[s]["walking"]) for s in scr["seeds"]),
                                            "survival_count": sum(not by[s]["fell"] for s in scr["seeds"])}
    if not ctx["stop"]:
        msgs = [r3.build_messages(c[a]["context"]) for c in ctx["contexts"] for a in r3.ARMS_MODEL]
        est = r3.estimate_tokens(msgs)
        out["token_estimate"] = est
        if est["total_tokens_ceiling"] > r3.MAX_TOTAL_TOKENS:
            out.update({"stop": True, "reason": f"token ceiling {est['total_tokens_ceiling']} exceeds the approved {r3.MAX_TOTAL_TOKENS}; registered STOP"})
        same = all(c["M"]["context"]["controller"] == c["N"]["context"]["controller"] for c in ctx["contexts"])
        out["control_identity_check"] = {"controller_block_identical_in_M_and_N": same}
        if not same:
            out.update({"stop": True, "reason": "controller block differs between arms"})
    if scr["stop"]:
        out["stop"] = True
        out["reason"] = (out.get("reason", "") + " " + scr["reason"]).strip()
    r3.write_json(r3.CONTEXTS, out)
    print(json.dumps({k: out.get(k) for k in ("stop", "reason", "n_pool", "n_failing", "n_walking", "token_estimate", "control_identity_check", "theta0_on_screening_seeds")}, indent=1))
    if not out["stop"]:
        print("contexts.json written; COMMIT it before any model request")


def stage_live(args):
    r3.require_preregistration(need_contexts=True)
    if not args.confirm_live:
        raise SystemExit("refused: pass --confirm-live (approved caps: 30 requests, 130000 tokens)")
    ctx = load("contexts.json")
    if ctx["stop"]:
        raise SystemExit("contexts.json records a registered STOP: " + ctx.get("reason", ""))
    if r3.REQUESTS.exists():
        raise SystemExit("requests.jsonl exists: the live batch is run once")
    client = NebiusClient(model=r3.MODEL, limits=Limits(max_requests=r3.MAX_REQUESTS, max_total_tokens=r3.MAX_TOTAL_TOKENS,
                                                       max_tokens_per_request=r3.MAX_TOKENS, timeout_s=180.0))
    r3.RESULTS.mkdir(parents=True, exist_ok=True)
    sent, stopped = 0, None
    for b in range(r3.BLOCKS):
        for arm in r3.ARMS_MODEL:                                   # interleaved M0, N0, M1, N1, ...
            c = ctx["contexts"][b][arm]
            rec = r3.request_block(client, arm, b, c["context"])
            assert rec.prompt_sha256 == c["prompt_sha256"], "prompt differs from the frozen prompt"
            with open(r3.REQUESTS, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec.as_dict(), allow_nan=False) + "\n")
            sent += 1
            print(f"{arm}{b}: {rec.status} valid_slots={sum(s['proposal'] is not None for s in rec.slots)} tokens_used={client.tokens_used}", flush=True)
            if rec.status in ("model_error", "budget_exceeded"):
                stopped = f"{arm}{b}: {rec.status}: {rec.reason}"
                break
        if stopped:
            break
    tok = client.tokens_used
    summary = {"requests_sent": sent, "requests_counted_by_client": client.requests_made, "tokens_used": tok, "complete": stopped is None and sent == r3.MAX_REQUESTS,
               "stopped_reason": stopped, "model": r3.MODEL,
               "estimated_inference_cost_usd_at_assumed_price_per_million_tokens": {str(p): round(tok * p / 1e6, 4) for p in r3.PRICE_ASSUMPTIONS_USD_PER_M_TOKENS},
               "models_reported": sorted({(c.get("model") or "") for c in client.calls if c.get("ok")})}
    r3.write_json(RES / "live_summary.json", summary)
    print(json.dumps(summary, indent=1))


def stage_candidates(args):
    r3.require_preregistration(need_contexts=True)
    if r3.CANDIDATES.exists():
        raise SystemExit("candidates.json exists: frozen")
    recs = [json.loads(x) for x in r3.REQUESTS.read_text(encoding="utf-8").splitlines()]
    summ = load("live_summary.json")
    ctx = load("contexts.json")
    out = r3.build_candidates(r2.incumbent_theta(), recs, ctx["pool_failing_for_heuristic"])
    out["live_complete"] = summ["complete"]
    out["matching_audit"] = r3.matching_audit(out["candidates"])
    out["request_status_counts"] = {s: sum(r["status"] == s for r in recs) for s in ("ok", "invalid_response", "model_error", "budget_exceeded")}
    out["valid_model_slots"] = {a: sum(1 for c in out["candidates"] if c["arm"] == a) for a in r3.ARMS_MODEL}
    r3.write_json(r3.CANDIDATES, out)
    print(json.dumps({k: out[k] for k in ("n_candidates", "live_complete", "request_status_counts", "valid_model_slots", "matching_audit")}, indent=1))
    print("candidates.json written; COMMIT it before any simulation")


def stage_screen(args, ledger):
    r3.require_preregistration(need_contexts=True, need_candidates=True)
    if (RES / "screening.json").exists():
        raise SystemExit("screening.json exists")
    w = workers_for(args)
    ctx, cand = load("contexts.json"), load("candidates.json")
    seeds = tuple(ctx["screening"]["seeds"])
    base = ctx["theta0_on_screening_seeds"]["walking_count"]
    cs = cand["candidates"]
    results = {}
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        for lo in range(0, len(cs), 20):
            chunk = cs[lo:lo + 20]
            outs = r3.run_batch(ex, ledger, "screen", [c["vector"] for c in chunk], seeds, f"screening candidates {lo}-{lo + len(chunk) - 1}")
            for c, o in zip(chunk, outs):
                if not o["ok"]:
                    raise SystemExit(f"candidate {c['id']} failed: {o['error']}")
                per = o["result"]["per_seed"]
                wk = int(sum(m["walking"] for m in per))
                results[c["id"]] = {"walking_count": wk, "survival_count": int(sum(not m["fell"] for m in per)), **r3.outcome(base, wk, c.get("predicted_min_gain_seeds"))}
    r3.write_json(RES / "screening.json", {"theta0_walking_count": base, "seeds": list(seeds), "outcomes": results})
    print(f"screened {len(results)} candidates; improved {sum(v['improved'] for v in results.values())}; ledger {ledger.total_rollouts()}")


def stage_validate(args, ledger):
    r3.require_preregistration(need_contexts=True, need_candidates=True)
    if (RES / "validation.json").exists():
        raise SystemExit("validation.json exists")
    w = workers_for(args)
    cand, scr = load("candidates.json"), load("screening.json")
    byid = {c["id"]: c for c in cand["candidates"]}
    chosen = {}
    for arm in r3.ARM_ORDER:
        rows = [c for c in cand["candidates"] if c["arm"] == arm]
        rows.sort(key=lambda c: (-scr["outcomes"][c["id"]]["gain_seeds"], c["block"] if c["block"] is not None else -1, c["slot"]))
        chosen[arm] = [c["id"] for c in rows[:r3.TOP_K_VALIDATE]]
    ids = [i for a in r3.ARM_ORDER for i in chosen[a]]
    vecs = [r2.incumbent_theta()] + [byid[i]["vector"] for i in ids]
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        outs = r3.run_batch(ex, ledger, "validate", vecs, r3.VALIDATION_SEEDS, "theta0 (once) + top-3 per arm")
    wk = [int(sum(m["walking"] for m in o["result"]["per_seed"])) for o in outs]
    base = wk[0]
    res = {"theta0_walking_count": base, "chosen": chosen,
           "results": {i: {"walking_count": w_, "gain_seeds": w_ - base, "validated_improvement": bool(w_ - base >= r3.VALIDATED_MIN_GAIN)} for i, w_ in zip(ids, wk[1:])}}
    r3.write_json(RES / "validation.json", res)
    print(f"theta0 {base}/64; validated improvements: {[i for i, v in res['results'].items() if v['validated_improvement']]}")


def stage_analyze(args):
    r3.require_preregistration(need_contexts=True, need_candidates=True)
    cand, scr, live = load("candidates.json"), load("screening.json"), load("live_summary.json")
    out = {"live_complete": live["complete"], "tokens_used": live["tokens_used"], "estimated_cost": live["estimated_inference_cost_usd_at_assumed_price_per_million_tokens"],
           "matching_audit": cand["matching_audit"], "request_status_counts": cand["request_status_counts"]}
    if live["complete"] and cand["request_status_counts"]["model_error"] == 0 and cand["request_status_counts"]["budget_exceeded"] == 0:
        out.update(r3.primary_analysis(scr["outcomes"]))
    else:
        out["primary"] = {"not_run": "the experiment is incomplete (hard limit or transport error); confirmatory test not run per protocol"}
    pred = [(c["predicted_min_gain_seeds"], c["confidence"], scr["outcomes"][c["id"]]) for c in cand["candidates"] if c["arm"] in r3.ARMS_MODEL]
    if pred:
        out["prediction_hit_rate"] = {"n": len(pred), "met": sum(o["prediction_met"] for _, _, o in pred), "mean_confidence": float(np.mean([c for _, c, _ in pred]))}
    out["heuristic"] = [{"id": c["id"], "edits": c["edits"], **scr["outcomes"][c["id"]]} for c in cand["candidates"] if c["arm"] == "H"]
    if (RES / "validation.json").exists():
        out["validation"] = load("validation.json")
    r3.write_json(RES / "analysis.json", out)
    print(json.dumps({k: out[k] for k in ("primary", "exploratory") if k in out}, indent=1)[:3000])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["pilot", "evidence", "screenpool", "freeze", "live", "candidates", "screen", "validate", "analyze"])
    ap.add_argument("--workers", type=int, default=r3.MAX_WORKERS)
    ap.add_argument("--confirm-live", action="store_true")
    args = ap.parse_args()
    r3.require_preregistration()
    ledger = r3.Ledger()
    ledger.verify()
    RES.mkdir(parents=True, exist_ok=True)
    physics = args.stage in ("pilot", "evidence", "screenpool", "screen", "validate")
    if physics:
        ledger.session_begin(args.stage)
    try:
        if args.stage == "pilot":
            return stage_pilot(args, ledger)
        if args.stage == "evidence":
            return stage_pool(args, ledger, "evidence_pool", r3.EVIDENCE_POOL_SEEDS, "evidence_pool.json")
        if args.stage == "screenpool":
            return stage_pool(args, ledger, "screen_pool", r3.SCREEN_POOL_SEEDS, "screen_pool.json")
        if args.stage == "freeze":
            return stage_freeze(args, ledger)
        if args.stage == "live":
            return stage_live(args)
        if args.stage == "candidates":
            return stage_candidates(args)
        if args.stage == "screen":
            return stage_screen(args, ledger)
        if args.stage == "validate":
            return stage_validate(args, ledger)
        if args.stage == "analyze":
            return stage_analyze(args)
    finally:
        if physics:
            ledger.session_end()


if __name__ == "__main__":
    main()
