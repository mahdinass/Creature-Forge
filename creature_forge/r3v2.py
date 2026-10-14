"""R3 v2 - calibrated generation settings, then the same corrected experiment (protocol id phase2a-r3-protocol-v2).

v1 (`protocol.json`, commit 7def51f) stays immutable; its three empty-response requests, the aborted-attempt report, the frozen contexts
and the shared hash-chained physics ledger are carried forward. v2 adds (a) a preregistered, sequential calibration of the generation
settings on NON-experimental pilot contexts and (b) the 30 experimental requests with the selected setting. Everything else (contexts,
prompts, schema, matched-random streams, comparators, primary analysis) is r3's. Combined caps across v1 and v2: 41 requests,
300,000 tokens, 6,000 physics rollouts (the existing 340 count), additional spend < $2.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import phase2a, r2, r3
from .nebius import Limits, NebiusClient, NebiusError, BudgetExceeded

EXP_DIR = r3.EXP_DIR
RES1 = r3.RESULTS
RES2 = EXP_DIR / "results_v2"
PROTOCOL_V2 = EXP_DIR / "protocol_v2.json"
PROTOCOL_ID_V2 = "phase2a-r3-protocol-v2"
CAL_POOL = RES2 / "calibration_pool.json"
CAL_CONTEXT = RES2 / "calibration_context.json"
CAL_REQUESTS = RES2 / "calibration.jsonl"
CAL_RESULT = RES2 / "calibration_result.json"
CONFIG = RES2 / "generation_config.json"
REQUESTS2 = RES2 / "requests.jsonl"
LIVE_SUMMARY2 = RES2 / "live_summary.json"
CANDIDATES2 = RES2 / "candidates.json"

# combined caps across v1 and v2
TOTAL_REQUESTS_CAP = 41
TOTAL_TOKENS_CAP = 300_000
CAL_MAX_REQUESTS = 8
EXP_REQUESTS = 30
PER_REQUEST_MAX_TOKENS = 5000
SPEND_CAP_USD = 2.0
ASSUMED_PRICE_USD_PER_M = 5.0
VM_USD_BOUND = 0.30

# exactly these four settings, in this order (sequential: stop at the first passing setting)
SETTINGS = (
    {"name": "A", "reasoning_effort": "none", "max_tokens": 3500},
    {"name": "B", "reasoning_effort": "low", "max_tokens": 3500},
    {"name": "C", "reasoning_effort": "low", "max_tokens": 5000},
    {"name": "D", "reasoning_effort": "medium", "max_tokens": 5000},
)
CAL_MIN_VALID_PROPOSALS = 2
CAL_ARMS = ("M", "N")                                  # measured evidence first, then the control; same treatment difference as the experiment
ABORT_AFTER_EMPTY_FIRST_REQUESTS = 4                   # experimental batch: abort if the first 4 requests all have null visible content
N_FAIL_CAL, N_WALK_CAL = 4, 2

V1_FILES = {"protocol": "protocol.json", "contexts": "results/contexts.json", "requests": "results/requests.jsonl",
            "live_summary": "results/live_summary.json", "aborted_report": "ATTEMPT1_ABORTED.md",
            "evidence_pool": "results/evidence_pool.json", "screen_pool": "results/screen_pool.json", "pilot": "results/pilot.json"}


# ----------------------------------------------------------------------------------------------------------
# usage accounting across v1 + v2
# ----------------------------------------------------------------------------------------------------------
def _records(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def usage_from(records: list[dict]) -> tuple[int, int]:
    """(requests sent, tokens used) from stored request records. Every record is one counted request, including failed ones."""
    toks = sum(int(((r.get("call") or {}).get("usage") or {}).get("total_tokens") or 0) for r in records)
    return len(records), toks


def prior_usage() -> dict:
    v1 = usage_from(_records(RES1 / "requests.jsonl"))
    cal = usage_from(_records(CAL_REQUESTS))
    exp = usage_from(_records(REQUESTS2))
    return {"v1": {"requests": v1[0], "tokens": v1[1]}, "calibration": {"requests": cal[0], "tokens": cal[1]},
            "experiment": {"requests": exp[0], "tokens": exp[1]},
            "requests": v1[0] + cal[0] + exp[0], "tokens": v1[1] + cal[1] + exp[1]}


def make_client(**overrides) -> NebiusClient:
    """Client whose request/token counters start from everything already spent in v1 and v2, with the COMBINED caps."""
    u = prior_usage()
    c = NebiusClient(model=r3.MODEL, limits=Limits(max_requests=TOTAL_REQUESTS_CAP, max_total_tokens=TOTAL_TOKENS_CAP,
                                                  max_tokens_per_request=PER_REQUEST_MAX_TOKENS, timeout_s=240.0), **overrides)
    c.requests_made, c.tokens_used = u["requests"], u["tokens"]
    return c


# ----------------------------------------------------------------------------------------------------------
# calibration contexts (derived from pilot seeds only)
# ----------------------------------------------------------------------------------------------------------
def build_calibration_context(theta, pool_per_seed: list[dict]) -> dict:
    """From theta0's results on the 16 pilot seeds: the first 4 failing and first 2 walking seeds in ascending seed order (STOP if short).
    Uses no R3 screening/validation outcome and no R2 final outcome."""
    ordered = sorted(pool_per_seed, key=lambda m: m["seed"])
    fails = [m for m in ordered if not m["walking"]]
    walks = [m for m in ordered if m["walking"]]
    out = {"n_pool": len(ordered), "n_failing": len(fails), "n_walking": len(walks)}
    if len(fails) < N_FAIL_CAL or len(walks) < N_WALK_CAL:
        out.update({"stop": True, "reason": f"pilot pool has {len(fails)} failing (< {N_FAIL_CAL}) or {len(walks)} walking (< {N_WALK_CAL}) seeds; calibration cannot run"})
        return out
    sel = fails[:N_FAIL_CAL] + walks[:N_WALK_CAL]
    m_ctx, n_ctx = r3.build_context(theta, sel), r3.build_context(theta, None)
    out.update({"stop": False, "seeds": sorted(m["seed"] for m in sel),
                "M": {"context": m_ctx, "prompt_sha256": r3.prompt_sha256(r3.build_messages(m_ctx))},
                "N": {"context": n_ctx, "prompt_sha256": r3.prompt_sha256(r3.build_messages(n_ctx))},
                "controller_block_identical": json.dumps(m_ctx["controller"], sort_keys=True) == json.dumps(n_ctx["controller"], sort_keys=True)})
    return out


# ----------------------------------------------------------------------------------------------------------
# one request under a setting
# ----------------------------------------------------------------------------------------------------------
def request_with_setting(client: NebiusClient, arm: str, block: int, context: dict, setting: dict) -> dict:
    """Exactly one chat request with the given reasoning_effort/max_tokens (and the experiment's temperature). Returns an r3.RequestRecord dict
    plus the requested generation parameters and the observed reasoning-token count (to check whether the setting was honoured)."""
    messages = r3.build_messages(context)
    rec = r3.RequestRecord(arm, block, "ok", r3.prompt_sha256(messages), slots=[{"proposal": None, "reason": "not requested"}] * r3.SLOTS,
                           max_tokens=setting["max_tokens"])
    try:
        res = client.chat(messages, max_tokens=setting["max_tokens"], temperature=r3.TEMPERATURE, reasoning_effort=setting["reasoning_effort"])
    except BudgetExceeded as e:
        rec.status, rec.reason = "budget_exceeded", str(e)
    except NebiusError as e:
        rec.status, rec.reason = "model_error", str(e)[:300]
        rec.call = client.calls[-1] if client.calls else None
    else:
        rec.call, rec.raw_reply = res.record(), res.content
        slots, reasons, err = r3.parse_slots(res.content, context)
        if err is not None:
            rec.status = "invalid_response"
            rec.reason = err + (" (finish_reason=length)" if res.finish_reason == "length" else "")
        rec.slots = [{"proposal": None if p is None else p.as_dict(), "reason": r} for p, r in zip(slots, reasons)]
    d = rec.as_dict()
    d["generation"] = {"reasoning_effort_requested": setting["reasoning_effort"], "max_tokens_requested": setting["max_tokens"],
                       "temperature": r3.TEMPERATURE, "setting": setting.get("name"),
                       "reasoning_tokens_reported": ((rec.call or {}).get("usage") or {}).get("reasoning_tokens")}
    return d


def valid_proposals(rec: dict) -> int:
    return sum(1 for s in rec["slots"] if s["proposal"] is not None)


def setting_passes(recs: list[dict]) -> dict:
    """A setting passes iff BOTH responses (evidence, no-evidence) have non-null visible content, a valid JSON envelope and at least
    CAL_MIN_VALID_PROPOSALS schema-valid proposals. Proposal quality, physics and plausibility play no part."""
    checks = []
    for r in recs:
        content = r.get("raw_reply")
        envelope_ok = r["status"] == "ok"
        n = valid_proposals(r) if envelope_ok else 0
        checks.append({"arm": r["arm"], "status": r["status"], "visible_content": bool(content and content.strip()), "envelope_valid": envelope_ok,
                       "valid_proposals": n, "failure_reasons": [s["reason"] for s in r["slots"] if s["proposal"] is None] if envelope_ok else [r.get("reason")],
                       "finish_reason": (r.get("call") or {}).get("finish_reason"),
                       "usage": (r.get("call") or {}).get("usage"),
                       "ok": bool(content and content.strip()) and envelope_ok and n >= CAL_MIN_VALID_PROPOSALS})
    return {"passes": len(checks) == len(CAL_ARMS) and all(c["ok"] for c in checks), "checks": checks}


def run_calibration(client: NebiusClient, cal_context: dict, record_sink) -> dict:
    """Sequential: settings A, B, C, D in order, M then N for each; stops at the first passing setting. No retries, <= CAL_MAX_REQUESTS calls.
    `record_sink(rec)` persists each request record immediately."""
    results, chosen, sent = [], None, 0
    for st in SETTINGS:
        recs = []
        for arm in CAL_ARMS:
            if sent >= CAL_MAX_REQUESTS:
                break
            rec = request_with_setting(client, arm, -1, cal_context[arm]["context"], st)
            sent += 1
            record_sink(rec)
            recs.append(rec)
            if rec["status"] in ("model_error", "budget_exceeded"):
                results.append({"setting": st, **setting_passes(recs), "stopped": rec["status"]})
                return {"chosen": None, "results": results, "requests_sent": sent, "stopped": f"{st['name']}-{arm}: {rec['status']}: {rec['reason']}"}
        verdict = {"setting": st, **setting_passes(recs)}
        results.append(verdict)
        if verdict["passes"]:
            chosen = st
            break
    return {"chosen": chosen, "results": results, "requests_sent": sent, "stopped": None,
            "not_tested": [s["name"] for s in SETTINGS if s["name"] not in {r["setting"]["name"] for r in results}]}


# ----------------------------------------------------------------------------------------------------------
# protocol v2
# ----------------------------------------------------------------------------------------------------------
def v1_hashes() -> dict:
    return {k: r2.sha256_lf(EXP_DIR / p) for k, p in V1_FILES.items()}


def spend_bound() -> dict:
    infer = TOTAL_TOKENS_CAP * ASSUMED_PRICE_USD_PER_M / 1e6
    return {"inference_worst_case_usd_at_assumed_5_per_million": round(infer, 3), "vm_usd_bound": VM_USD_BOUND,
            "total_bound_usd": round(infer + VM_USD_BOUND, 3), "cap_usd": SPEND_CAP_USD, "within_cap": infer + VM_USD_BOUND < SPEND_CAP_USD,
            "note": "the Nemotron token price was not verifiable from public docs; 5 USD per million tokens is a deliberately high assumed bound and the v1 tokens are included"}


def build_protocol_v2() -> dict:
    r3.check_disjoint()
    return {
        "id": PROTOCOL_ID_V2,
        "supersedes": {"id": r3.PROTOCOL_ID, "commit": "7def51f", "status": "immutable and preserved; aborted after 3 of 30 requests (empty replies)",
                       "preserved_files_sha256_lf": v1_hashes()},
        "status": "immutable once committed; changes require a new protocol id",
        "reason": ("v1's generation settings (default reasoning, max_tokens 2200) produced HTTP 200 / finish_reason=length / null visible content on 3 of 3 "
                   "requests (hidden reasoning exhausted the completion budget). v2 calibrates the generation settings on non-experimental pilot contexts, then runs "
                   "the unchanged corrected experiment."),
        "generation_diagnosis": {
            "source": "Nebius Token Factory docs (create-chat-completion, structured output), read 2026-10-14",
            "documented": ["reasoning_effort accepts none|minimal|low|medium|high|xhigh|max (no per-model behaviour is documented)",
                           "max_completion_tokens is documented as including visible and reasoning tokens; max_tokens is the generic limit",
                           "usage.completion_tokens_details.reasoning_tokens may be reported (nullable)",
                           "response_format json_object / json_schema exist; support is model dependent ('test and compare')",
                           "enable_thinking and chat_template_kwargs are not documented"],
            "consequences": ["accepted parameters are NOT assumed to be honoured: every call records the requested effort/max_tokens, finish_reason, completion tokens, reasoning_present and reported reasoning_tokens",
                             "structured-output modes are not part of the four preregistered settings and are not used"]},
        "model": {"id": r3.MODEL, "endpoint": "Nebius Token Factory", "temperature": r3.TEMPERATURE, "response_format": "none (prompted JSON)"},
        "limits": {"combined_requests_v1_and_v2": TOTAL_REQUESTS_CAP, "combined_tokens_v1_and_v2": TOTAL_TOKENS_CAP,
                   "calibration_requests_max": CAL_MAX_REQUESTS, "experimental_requests": EXP_REQUESTS, "historical_v1_requests_included": 3,
                   "historical_v1_tokens_included": 13114, "max_tokens_per_request_hard": PER_REQUEST_MAX_TOKENS,
                   "physics_rollouts_total_cap": r3.BUDGET_CAP, "physics_existing_rollouts_counted": 340, "physics_ledger": "experiments/phase2a_r3/results/ledger.jsonl (continued, not reset)",
                   "spend": spend_bound(), "no_retries": True, "no_automatic_extension": True, "no_gpu": True},
        "calibration": {
            "contexts": ("derived from the designated pilot seeds 9500-9515: theta0 is run on those 16 seeds (a counted batch labelled calibration-context; the v1 pilot ran "
                         "the same rollouts but did not store per-seed results); context = first 4 failing + first 2 walking seeds in ascending seed order; "
                         "STOP if the pool has fewer; two prompts per setting: M (measured evidence) and N (control, byte-identical controller block and system prompt)"),
            "no_outcome_leakage": "no R3 screening/validation outcome and no R2 final outcome is used; screening/validation seeds are not touched",
            "settings_in_order": [dict(s) for s in SETTINGS], "temperature": r3.TEMPERATURE,
            "procedure": "sequential: for each setting in order make exactly one M and one N request (<= 8 requests in total); stop at the first passing setting; later settings are then not tested",
            "pass_rule": ("a setting passes iff BOTH responses have non-null visible content, a valid JSON envelope and at least "
                          f"{CAL_MIN_VALID_PROPOSALS} schema-valid proposals each (r3.parse_proposal against the context shown)"),
            "selection": "the FIRST passing setting in the prespecified order; proposal quality, physics, or how convincing an edit sounds play no part",
            "if_none_passes": "the statistical experiment is not run; the generation blocker is reported as the R3 result",
            "recorded_per_request": ["requested reasoning_effort and max_tokens", "temperature", "finish_reason", "usage incl. reasoning_tokens if reported", "reasoning_present",
                                     "raw reply as received", "per-slot validation outcome and reason", "prompt SHA-256", "request id", "model id reported by the API"],
            "freeze": "generation_config.json (the selected setting + the observed calibration metadata) is committed before the first experimental request"},
        "experiment": {
            "same_as_v1": ["15 frozen evidence contexts and prompt SHA-256 (contexts.json, commit 196de48)", "screening seeds and theta0's derived screening baseline",
                           "4 slots per request, all-slot ITT endpoint, invalid/empty = failure", "matched-random streams (SeedSequence([rng_base, 11|12, block, slot])) and fallback magnitudes",
                           "heuristic comparator", "paired request-block exact sign-flip test (two-sided, alpha 0.05)", "comparators frozen in candidates.json before any simulation",
                           "validation of the top-3 candidates per arm (descriptive)"],
            "generation": "the SAME selected setting for the evidence and the no-evidence arm (reasoning_effort and max_tokens from generation_config.json); temperature 0.7",
            "requests": EXP_REQUESTS, "request_order": "interleaved M0, N0, M1, N1, ... M14, N14",
            "early_abort": f"if the first {ABORT_AFTER_EMPTY_FIRST_REQUESTS} experimental requests all return null visible content, stop and report a generation failure (protects the budget)",
            "carryover": ("v1 pilot (96), evidence pool (180) and screen pool (64) rollouts are carried forward and NOT rerun; v1's three request records stay in results/requests.jsonl "
                          "and count toward the combined caps; no v1 file is modified"),
            "completeness_rule": ("the primary test is run only if all 30 experimental requests were sent, none ended in a transport/HTTP error or budget refusal, the combined "
                                  "caps were respected and every frozen hash verified; otherwise the experiment is reported as incomplete"),
            "no_adaptation": "no model physics outcome is inspected to change a prompt, a generation setting, a comparator or the analysis"},
        "physics_budget": {"remaining_planned": {"calibration_context": 16, "screening_candidates_max": r3.planned_rollouts()["screening_candidates_max"],
                                                 "validation": r3.planned_rollouts()["validation_theta0"] + r3.planned_rollouts()["validation_top_k"]},
                           "planned_total_including_existing": 340 + 16 + r3.planned_rollouts()["screening_candidates_max"] + r3.planned_rollouts()["validation_theta0"] + r3.planned_rollouts()["validation_top_k"],
                           "cap": r3.BUDGET_CAP},
        "reporting": "no result is described as an AI success unless MuJoCo independently verifies the measured intervention; scripted replies are never saved as results",
    }


def require_preregistration_v2(need_cal_context: bool = False, need_config: bool = False, need_candidates: bool = False) -> dict:
    commits = {"protocol_v1": phase2a.committed_unmodified(r3.PROTOCOL), "protocol_v2": phase2a.committed_unmodified(PROTOCOL_V2),
               "contexts": phase2a.committed_unmodified(r3.CONTEXTS)}
    if json.loads(PROTOCOL_V2.read_text(encoding="utf-8")) != json.loads(json.dumps(build_protocol_v2())):
        raise RuntimeError("protocol_v2.json no longer matches the code that defines it or the preserved v1 files; re-registration required")
    if need_cal_context:
        commits["calibration_context"] = phase2a.committed_unmodified(CAL_CONTEXT)
    if need_config:
        commits["generation_config"] = phase2a.committed_unmodified(CONFIG)
    if need_candidates:
        commits["candidates"] = phase2a.committed_unmodified(CANDIDATES2)
    return commits
