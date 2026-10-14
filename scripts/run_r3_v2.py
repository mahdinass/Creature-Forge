"""Staged R3 v2 runner (protocol phase2a-r3-protocol-v2). v1 files are never modified; v2 artifacts live in experiments/phase2a_r3/results_v2/.

Physics stages run on the Nebius VM; model stages run where NEBIUS_API_KEY lives (the key is never copied to the VM).

    python scripts/run_r3_v2.py calibration-context   # VM, 16 rollouts: theta0 on the pilot seeds (counted; the v1 pilot's per-seed data was not stored)
    python scripts/run_r3_v2.py calibration-freeze    # pure: calibration_context.json (M and N prompts + hashes) -> COMMIT before any calibration request
    python scripts/run_r3_v2.py calibrate --confirm-live   # <= 8 requests, sequential settings A..D, stops at the first pass
    python scripts/run_r3_v2.py config                # pure: generation_config.json from the calibration outcome -> COMMIT before any experimental request
    python scripts/run_r3_v2.py live --confirm-live   # 30 experimental requests with the frozen setting
    python scripts/run_r3_v2.py candidates            # pure: candidates.json (model + matched random + heuristic) -> COMMIT before any simulation
    python scripts/run_r3_v2.py screen | validate     # VM physics, shared ledger
    python scripts/run_r3_v2.py analyze               # prespecified analysis -> analysis.json
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

from creature_forge import r1, r2, r3, r3v2  # noqa: E402
from creature_forge.optimize import Executor  # noqa: E402

R2D = r3v2.RES2
STORE = r3.SEED_FIELDS + ("walking",)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def workers_for(args) -> int:
    d = load(r3.RESULTS / "pilot.json")
    if not d["passed"]:
        raise SystemExit("the v1 pilot did not pass")
    return min(args.workers, r3.MAX_WORKERS, d["recommended_workers"])


def append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, allow_nan=False) + "\n")


def stage_calibration_context(args, ledger):
    if r3v2.CAL_POOL.exists():
        raise SystemExit("calibration_pool.json exists: theta0 is run once on the pilot seeds for calibration")
    w = workers_for(args)
    with Executor(w, timeout_s=900, fn=r2.r2_job) as ex:
        res = r3.run_batch(ex, ledger, "calibration-context", [r2.incumbent_theta()], r3.PILOT_SEEDS, "theta0 on the pilot seeds for the calibration contexts")[0]
    if not res["ok"]:
        raise SystemExit("run failed: " + res["error"])
    per = res["result"]["per_seed"]
    r3.write_json(r3v2.CAL_POOL, {"seeds": list(r3.PILOT_SEEDS), "walking": int(sum(m["walking"] for m in per)),
                                 "per_seed": [{k: m.get(k) for k in STORE} | {"fitness_total": m["fitness"]["total"]} for m in per]})
    print(f"calibration pool: theta0 walking {sum(m['walking'] for m in per)}/16")


def stage_calibration_freeze(args):
    r3v2.require_preregistration_v2()
    if r3v2.CAL_CONTEXT.exists():
        raise SystemExit("calibration_context.json exists: frozen")
    pool = load(r3v2.CAL_POOL)
    out = r3v2.build_calibration_context(r2.incumbent_theta(), pool["per_seed"])
    r3.write_json(r3v2.CAL_CONTEXT, out)
    print(json.dumps({k: out.get(k) for k in ("stop", "reason", "n_failing", "n_walking", "seeds", "controller_block_identical")}, indent=1))
    if not out["stop"]:
        print("M", out["M"]["prompt_sha256"], "N", out["N"]["prompt_sha256"], "\ncalibration_context.json written; COMMIT it before any calibration request")


def stage_calibrate(args):
    r3v2.require_preregistration_v2(need_cal_context=True)
    if not args.confirm_live:
        raise SystemExit("refused: pass --confirm-live (calibration: <= 8 requests under the combined caps)")
    if r3v2.CAL_REQUESTS.exists() or r3v2.CAL_RESULT.exists():
        raise SystemExit("calibration already ran; it is run once")
    ctx = load(r3v2.CAL_CONTEXT)
    if ctx["stop"]:
        raise SystemExit("calibration context records a registered STOP: " + ctx["reason"])
    client = r3v2.make_client()
    before = r3v2.prior_usage()
    out = r3v2.run_calibration(client, ctx, lambda rec: append(r3v2.CAL_REQUESTS, rec))
    after = r3v2.prior_usage()
    out["usage_before"], out["usage_after"] = before, after
    out["combined_caps"] = {"requests": r3v2.TOTAL_REQUESTS_CAP, "tokens": r3v2.TOTAL_TOKENS_CAP}
    r3.write_json(r3v2.CAL_RESULT, out)
    for v in out["results"]:
        print(v["setting"]["name"], v["setting"]["reasoning_effort"], v["setting"]["max_tokens"], "PASS" if v["passes"] else "fail",
              [(c["arm"], c["status"], c["valid_proposals"], c["finish_reason"], (c["usage"] or {}).get("completion_tokens"), (c["usage"] or {}).get("reasoning_tokens")) for c in v["checks"]])
    print("chosen:", out["chosen"], "| requests sent", out["requests_sent"], "| usage after", after["requests"], "requests,", after["tokens"], "tokens")


def stage_config(args):
    r3v2.require_preregistration_v2(need_cal_context=True)
    if r3v2.CONFIG.exists():
        raise SystemExit("generation_config.json exists: frozen")
    res = load(r3v2.CAL_RESULT)
    if res["chosen"] is None:
        raise SystemExit("no calibration setting passed: the statistical experiment is not run; report the generation blocker")
    ctx = load(r3.CONTEXTS)
    ok = all(r3.prompt_sha256(r3.build_messages(c[a]["context"])) == c[a]["prompt_sha256"] for c in ctx["contexts"] for a in r3.ARMS_MODEL)
    if not ok:
        raise SystemExit("a frozen experimental prompt hash no longer verifies")
    passing = next(v for v in res["results"] if v["setting"]["name"] == res["chosen"]["name"])
    cfg = {"setting": res["chosen"], "temperature": r3.TEMPERATURE, "same_for_both_arms": True, "frozen_prompt_hashes_verified": True,
           "n_contexts": len(ctx["contexts"]), "calibration_observed": passing["checks"], "usage_after_calibration": res["usage_after"],
           "selection_rule": "first passing setting in the prespecified order A, B, C, D"}
    r3.write_json(r3v2.CONFIG, cfg)
    print(json.dumps({"setting": cfg["setting"], "verified": ok}, indent=1), "\ngeneration_config.json written; COMMIT it before any experimental request")


def stage_live(args):
    r3v2.require_preregistration_v2(need_cal_context=True, need_config=True)
    if not args.confirm_live:
        raise SystemExit("refused: pass --confirm-live (30 experimental requests under the combined caps)")
    if r3v2.REQUESTS2.exists():
        raise SystemExit("v2 requests.jsonl exists: the experimental batch is run once")
    cfg = load(r3v2.CONFIG)
    setting = cfg["setting"]
    ctx = load(r3.CONTEXTS)
    client = r3v2.make_client()
    sent, stopped, empty_first = 0, None, []
    for b in range(r3.BLOCKS):
        for arm in r3.ARMS_MODEL:
            c = ctx["contexts"][b][arm]
            rec = r3v2.request_with_setting(client, arm, b, c["context"], setting)
            assert rec["prompt_sha256"] == c["prompt_sha256"], "prompt differs from the frozen prompt"
            append(r3v2.REQUESTS2, rec)
            sent += 1
            if sent <= r3v2.ABORT_AFTER_EMPTY_FIRST_REQUESTS:
                empty_first.append(not (rec.get("raw_reply") or "").strip())
            print(f"{arm}{b}: {rec['status']} valid_slots={r3v2.valid_proposals(rec)} tokens_total={client.tokens_used}", flush=True)
            if rec["status"] in ("model_error", "budget_exceeded"):
                stopped = f"{arm}{b}: {rec['status']}: {rec['reason']}"
                break
            if sent == r3v2.ABORT_AFTER_EMPTY_FIRST_REQUESTS and all(empty_first):
                stopped = "early abort: the first 4 experimental requests all returned null visible content (generation failure)"
                break
        if stopped:
            break
    u = r3v2.prior_usage()
    summary = {"requests_sent": sent, "complete": stopped is None and sent == r3v2.EXP_REQUESTS, "stopped_reason": stopped, "setting": setting,
               "usage_combined": {"requests": u["requests"], "tokens": u["tokens"], "caps": [r3v2.TOTAL_REQUESTS_CAP, r3v2.TOTAL_TOKENS_CAP]},
               "usage_experiment": u["experiment"], "model": r3.MODEL,
               "models_reported": sorted({(c.get("model") or "") for c in client.calls if c.get("ok")}),
               "estimated_inference_cost_usd_at_assumed_price_per_million_tokens": {str(p): round(u["tokens"] * p / 1e6, 4) for p in r3.PRICE_ASSUMPTIONS_USD_PER_M_TOKENS}}
    r3.write_json(r3v2.LIVE_SUMMARY2, summary)
    print(json.dumps(summary, indent=1))


def stage_candidates(args):
    r3v2.require_preregistration_v2(need_cal_context=True, need_config=True)
    if r3v2.CANDIDATES2.exists():
        raise SystemExit("candidates.json exists: frozen")
    recs = [json.loads(x) for x in r3v2.REQUESTS2.read_text(encoding="utf-8").splitlines()]
    summ = load(r3v2.LIVE_SUMMARY2)
    ctx = load(r3.CONTEXTS)
    out = r3.build_candidates(r2.incumbent_theta(), recs, ctx["pool_failing_for_heuristic"])
    out["live_complete"] = summ["complete"]
    out["matching_audit"] = r3.matching_audit(out["candidates"])
    out["request_status_counts"] = {s: sum(r["status"] == s for r in recs) for s in ("ok", "invalid_response", "model_error", "budget_exceeded")}
    out["valid_model_slots"] = {a: sum(1 for c in out["candidates"] if c["arm"] == a) for a in r3.ARMS_MODEL}
    r3.write_json(r3v2.CANDIDATES2, out)
    print(json.dumps({k: out[k] for k in ("n_candidates", "live_complete", "request_status_counts", "valid_model_slots", "matching_audit")}, indent=1))
    print("candidates.json written; COMMIT it before any simulation")


def stage_screen(args, ledger):
    r3v2.require_preregistration_v2(need_cal_context=True, need_config=True, need_candidates=True)
    if (R2D / "screening.json").exists():
        raise SystemExit("screening.json exists")
    w = workers_for(args)
    ctx, cand = load(r3.CONTEXTS), load(r3v2.CANDIDATES2)
    seeds = tuple(ctx["screening"]["seeds"])
    base = ctx["theta0_on_screening_seeds"]["walking_count"]
    cs, results = cand["candidates"], {}
    with Executor(w, timeout_s=1800, fn=r2.r2_job) as ex:
        for lo in range(0, len(cs), 20):
            chunk = cs[lo:lo + 20]
            outs = r3.run_batch(ex, ledger, "screen", [c["vector"] for c in chunk], seeds, f"v2 screening candidates {lo}-{lo + len(chunk) - 1}")
            for c, o in zip(chunk, outs):
                if not o["ok"]:
                    raise SystemExit(f"candidate {c['id']} failed: {o['error']}")
                per = o["result"]["per_seed"]
                wk = int(sum(m["walking"] for m in per))
                results[c["id"]] = {"walking_count": wk, "survival_count": int(sum(not m["fell"] for m in per)), **r3.outcome(base, wk, c.get("predicted_min_gain_seeds"))}
    r3.write_json(R2D / "screening.json", {"theta0_walking_count": base, "seeds": list(seeds), "outcomes": results})
    print(f"screened {len(results)}; improved {sum(v['improved'] for v in results.values())}; ledger {ledger.total_rollouts()}")


def stage_validate(args, ledger):
    r3v2.require_preregistration_v2(need_cal_context=True, need_config=True, need_candidates=True)
    if (R2D / "validation.json").exists():
        raise SystemExit("validation.json exists")
    w = workers_for(args)
    cand, scr = load(r3v2.CANDIDATES2), load(R2D / "screening.json")
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
           "results": {i: {"walking_count": v, "gain_seeds": v - base, "validated_improvement": bool(v - base >= r3.VALIDATED_MIN_GAIN)} for i, v in zip(ids, wk[1:])}}
    r3.write_json(R2D / "validation.json", res)
    print(f"theta0 {base}/64; validated improvements: {[i for i, v in res['results'].items() if v['validated_improvement']]}")


def stage_analyze(args):
    r3v2.require_preregistration_v2(need_cal_context=True, need_config=True, need_candidates=True)
    cand, scr, live = load(r3v2.CANDIDATES2), load(R2D / "screening.json"), load(r3v2.LIVE_SUMMARY2)
    out = {"protocol": r3v2.PROTOCOL_ID_V2, "live_complete": live["complete"], "setting": live["setting"], "usage_combined": live["usage_combined"],
           "estimated_cost": live["estimated_inference_cost_usd_at_assumed_price_per_million_tokens"], "matching_audit": cand["matching_audit"],
           "request_status_counts": cand["request_status_counts"], "valid_model_slots": cand["valid_model_slots"],
           "calibration": load(r3v2.CAL_RESULT)}
    counts = cand["request_status_counts"]
    if live["complete"] and counts["model_error"] == 0 and counts["budget_exceeded"] == 0:
        out.update(r3.primary_analysis(scr["outcomes"]))
    else:
        out["primary"] = {"not_run": "completeness requirements not met; confirmatory test not run per protocol v2"}
    pred = [(c["predicted_min_gain_seeds"], c["confidence"], scr["outcomes"][c["id"]]) for c in cand["candidates"] if c["arm"] in r3.ARMS_MODEL]
    if pred:
        out["prediction_hit_rate"] = {"n": len(pred), "met": sum(o["prediction_met"] for _, _, o in pred), "mean_confidence": float(np.mean([c for _, c, _ in pred]))}
    out["heuristic"] = [{"id": c["id"], "edits": c["edits"], **scr["outcomes"][c["id"]]} for c in cand["candidates"] if c["arm"] == "H"]
    if (R2D / "validation.json").exists():
        out["validation"] = load(R2D / "validation.json")
    r3.write_json(R2D / "analysis.json", out)
    print(json.dumps({k: out[k] for k in ("primary", "exploratory") if k in out}, indent=1)[:3500])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["calibration-context", "calibration-freeze", "calibrate", "config", "live", "candidates", "screen", "validate", "analyze"])
    ap.add_argument("--workers", type=int, default=r3.MAX_WORKERS)
    ap.add_argument("--confirm-live", action="store_true")
    args = ap.parse_args()
    r3v2.require_preregistration_v2()
    physics = args.stage in ("calibration-context", "screen", "validate")
    ledger = r3.Ledger()
    ledger.verify()
    R2D.mkdir(parents=True, exist_ok=True)
    if physics:
        ledger.session_begin("v2-" + args.stage)
    try:
        if args.stage == "calibration-context":
            return stage_calibration_context(args, ledger)
        if args.stage == "calibration-freeze":
            return stage_calibration_freeze(args)
        if args.stage == "calibrate":
            return stage_calibrate(args)
        if args.stage == "config":
            return stage_config(args)
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
