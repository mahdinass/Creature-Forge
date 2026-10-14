"""R3 tooling. Offline only until the R3 protocol, request cap and cost estimate are approved.

    python scripts/run_r3.py estimate    # token/request ceiling for the planned live batch (no network, no physics)
    python scripts/run_r3.py dry-run     # SCRIPTED stand-in for the model through the real parser/applier/baselines (no network, no physics)
    python scripts/run_r3.py live        # refused: live calls need an approved, committed R3 protocol

The dry-run replies are written by this script, not by a model; they exist to exercise validation, matching and bookkeeping.
No dry-run output is ever a result, and nothing is written under experiments/.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creature_forge import r2, r3  # noqa: E402
from creature_forge.nebius import Limits, NebiusClient  # noqa: E402

REQUESTS_PER_MODEL_ARM = 15            # x 4 proposal slots = 60 slots per model arm (planned; see docs/R3_DESIGN.md)
MAX_TOKENS = 2048


def screen_evidence() -> dict:
    """Evidence built from the R2 screen of theta0 (compact fields only): good enough to size the prompt, NOT the R3 evidence run."""
    screen = json.loads((r2.RESULTS / "screen.json").read_text(encoding="utf-8"))
    per = [{**m, "walking": m["walking"], "fell": m["fell"], "label": m["label"]} for m in screen["per_seed"]]
    return r3.build_evidence(r2.incumbent_theta(), per)


def cmd_estimate() -> None:
    ev = screen_evidence()
    out = {"M_evidence_arm": r3.estimate_tokens(r3.build_messages(ev), MAX_TOKENS, REQUESTS_PER_MODEL_ARM),
           "N_no_evidence_arm": r3.estimate_tokens(r3.build_messages(None), MAX_TOKENS, REQUESTS_PER_MODEL_ARM)}
    out["total_requests"] = 2 * REQUESTS_PER_MODEL_ARM
    out["total_tokens_ceiling"] = out["M_evidence_arm"]["total_tokens_ceiling"] + out["N_no_evidence_arm"]["total_tokens_ceiling"]
    out["prompt_sha256"] = {"M": r3.prompt_sha256(r3.build_messages(ev)), "N": r3.prompt_sha256(r3.build_messages(None))}
    out["note"] = "evidence sized from the R2 screen of theta0; the registered R3 prompt hash will come from the R3 evidence run"
    print(json.dumps(out, indent=1))


def scripted_reply(i: int) -> str:
    sets = [("start_lean", 0.12), ("ramp_s", 0.10), ("pitch_ref", 0.08), ("kp", -0.06)]
    p, d = sets[i % len(sets)]
    item = {"claim": "Scripted stand-in (not a model): start-up lean/ramp influences forward stepping.",
            "cited_evidence": ["failing_seeds.0.valid_steps", "controller.start_lean.u"],
            "edits": [{"parameter": p, "delta_u": d}],
            "prediction": {"metric": r3.PREDICTION_METRIC, "direction": "increase", "min_gain_seeds": 2}, "confidence": 0.5}
    return json.dumps({"proposals": [item, {**item, "edits": [{"parameter": "not_a_parameter", "delta_u": 0.1}]}]})


def cmd_dry_run() -> None:
    ev = screen_evidence()
    client = NebiusClient(api_key="dry-run", base_url="http://invalid.example", limits=Limits(max_requests=8, max_total_tokens=200_000),
                          transport=r3.scripted_transport([scripted_reply(i) for i in range(4)] + [None, "plain text", RuntimeError("x")]))
    recs = []
    for i in range(7):
        try:
            recs.append(r3.request_proposals(client, "M", i, ev, max_tokens=MAX_TOKENS))
        except RuntimeError:
            break
    valid = [p for r in recs for p in r.proposals]
    matched = [r3.matched_random_edits([(e["parameter"], e["delta_u"]) for e in p["edits"]], [0, k]) for k, p in enumerate(valid)]
    print(json.dumps({"requests": [{"status": r.status, "valid": len(r.proposals), "invalid": len(r.invalid_proposals), "reason": r.reason} for r in recs],
                      "valid_proposals": len(valid), "matched_random_edits_example": matched[:2],
                      "heuristic_edits": [list(map(list, e)) for e in r3.heuristic_proposals(ev)],
                      "vectors_in_bounds": all(r3.LOWER15[j] - 1e-12 <= v <= r3.UPPER15[j] + 1e-12
                                               for p in valid for j, v in enumerate(r3.apply_edits(r2.incumbent_theta(), [(e['parameter'], e['delta_u']) for e in p['edits']]))),
                      "NOT_A_RESULT": "scripted replies; no model, no physics"}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["estimate", "dry-run", "live"])
    a = ap.parse_args()
    if a.mode == "live":
        raise SystemExit("refused: live model requests require an approved, committed R3 protocol with its request cap and cost estimate")
    {"estimate": cmd_estimate, "dry-run": cmd_dry_run}[a.mode]()


if __name__ == "__main__":
    main()
