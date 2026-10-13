#!/usr/bin/env python
"""Write the Phase 1 pre-registration (protocol + exact prompts + hashes) BEFORE any live model request.

Output: experiments/phase1/protocol.json (commit it; run_phase1_live.py refuses to run unless this file is
tracked, unmodified and matches the prompts rebuilt from MuJoCo). Makes NO model call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from creature_forge.controller import GaitParams
from creature_forge.evaluation import Protocol
from creature_forge.experiment import PHASE0_BASELINE, PHASE0_DURATION, PHASE0_PUSH
from creature_forge.investigator import (build_evidence, build_forensic_evidence, build_messages,
                                         prompt_hash)
from creature_forge.proposers import HEURISTIC_FACTORS

OUT = Path("experiments") / "phase1" / "protocol.json"
EVIDENCE_SEEDS = (0, 1, 2)
VERIFY_SEEDS = (0, 1, 2, 3, 4)

LIMITS = {"max_live_requests": 3, "max_total_tokens": 18000, "max_completion_tokens_per_request": 4096,
          "request_timeout_s": 90, "retries": 0, "reasoning_effort": "default (parameter omitted)"}

CALL_PLAN = [
    {"id": "control", "variant": "legacy", "temperature": 0.0,
     "purpose": "original compact evidence + original prompt/validation (control)"},
    {"id": "enriched-1", "variant": "forensic", "temperature": 0.0,
     "purpose": "forensic evidence + forensic prompt/validation"},
    {"id": "enriched-2", "variant": "forensic", "temperature": 0.7,
     "purpose": "identical prompt to enriched-1, sampled at temperature 0.7 to expose proposal variability"},
]


def build() -> dict:
    body, gait = PHASE0_BASELINE, GaitParams()
    legacy = build_messages(build_evidence(body, gait, PHASE0_PUSH, seeds=EVIDENCE_SEEDS, duration=PHASE0_DURATION),
                            body, "legacy")
    forensic = build_messages(build_forensic_evidence(body, gait, PHASE0_PUSH, seeds=EVIDENCE_SEEDS,
                                                      duration=PHASE0_DURATION), body, "forensic")
    proto = Protocol()
    return {
        "registered_before_any_phase1_live_request": True,
        "scenario": {"baseline_body": body.as_dict(), "controller": gait.as_dict(),
                     "push": {"time_s": PHASE0_PUSH.time, "force_N": PHASE0_PUSH.force,
                              "duration_s": PHASE0_PUSH.duration},
                     "duration_s": PHASE0_DURATION, "evidence_seeds": list(EVIDENCE_SEEDS),
                     "screening_verify_seeds": list(VERIFY_SEEDS)},
        "intervention_space": "exactly ONE body parameter changed to a value inside morphology.BOUNDS "
                              "(out-of-range is rejected, never clipped); gait/controller parameters are out of scope",
        "live_limits": LIMITS,
        "call_plan": CALL_PLAN,
        "stop_rules": ["stop before a request if requests_made >= 3",
                       "stop before a request if tokens_used + estimated_prompt_tokens + max_tokens > 18000",
                       "stop after any request if tokens_used >= 18000",
                       "no prompt edits and no extra requests after seeing any result"],
        "independent_evaluation": proto.as_dict() | {"tier_rule": {
            "success": "primary-push held-out fall rate <= 0.2 AND candidate fall rate <= baseline at EVERY push level "
                       "AND primary mean survival time >= baseline",
            "partial": "not success, but primary fall rate reduced by >= 0.3",
            "none": "otherwise (a better secondary metric alone never counts)"}},
        "trial_status_mapping": "accepted == tier success; everything else (incl. partial) is rejected_by_verifier; "
                                "invalid replies, errors and budget stops are preserved as their own statuses",
        "baselines": {
            "random": {"n_proposals": 100, "rng_seed": 1000,
                       "description": "uniform parameter, uniform value in bounds; sees no evidence and no results; "
                                      "every proposal judged by the same held-out protocol; reported as per-proposal "
                                      "success rate (matches Nemotron's budget of ONE proposal) plus analytic best-of-k"},
            "heuristic": {"factors": HEURISTIC_FACTORS,
                          "prior_knowledge_disclosure": "author knew longer feet widen the support polygon and that foot "
                                                        "length mattered in Phase 0; the x1.5 factor was fixed before any "
                                                        "candidate was evaluated (x1.5 -> 0.12 m, not the 16 cm answer)"},
        },
        "reference_designs_not_proposers": ["no change (baseline)", "foot_length=0.16 (known Phase 0 answer)"],
        "exploration_disclosure": "seeds 100-105 and pushes 10-40 N were used on 2026-10-13 to characterise the baseline and "
                                  "16 cm frontier (baseline survives 15 N, falls >= 20 N; 16 cm survives <= 30 N, falls "
                                  ">= 35 N). Held-out seeds 200-209 were never used for exploration, evidence or screening.",
        "claims_policy": "no claim that Nemotron outperforms any baseline from <= 3 exploratory trials; report counts, "
                         "budgets (model calls, tokens, simulations) and limitations",
        "prompts": {"legacy": {"sha256": prompt_hash(legacy), "messages": legacy},
                    "forensic": {"sha256": prompt_hash(forensic), "messages": forensic}},
    }


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(json.dumps({"written": str(OUT), "legacy_sha256": doc["prompts"]["legacy"]["sha256"],
                      "forensic_sha256": doc["prompts"]["forensic"]["sha256"],
                      "legacy_chars": sum(len(m["content"]) for m in doc["prompts"]["legacy"]["messages"]),
                      "forensic_chars": sum(len(m["content"]) for m in doc["prompts"]["forensic"]["messages"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
