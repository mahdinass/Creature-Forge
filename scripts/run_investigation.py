#!/usr/bin/env python
"""Run ONE Physics Investigator trial on the Phase 0 failure (8 cm foot, 25 N push).

  --estimate          build the evidence + prompt, print its size, make NO model call
  --live              ONE real Nebius request (needs NEBIUS_API_KEY); saved to artifacts/investigations/
Options: --reasoning {none,low,medium,high} (omit = model default), --max-tokens N (default 4096)
No retries. Never prints credentials.
"""
from __future__ import annotations

import argparse
import json
import sys

from creature_forge.controller import GaitParams
from creature_forge.experiment import PHASE0_BASELINE, PHASE0_DURATION, PHASE0_PUSH
from creature_forge.investigator import build_evidence, build_messages, investigate
from creature_forge.nebius import Limits, NebiusClient


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--reasoning", choices=("none", "low", "medium", "high"))
    ap.add_argument("--max-tokens", type=int, default=4096)
    a = ap.parse_args()
    if a.estimate == a.live:
        ap.error("choose exactly one of --estimate / --live")
    body, gait = PHASE0_BASELINE, GaitParams()
    if a.estimate:
        msgs = build_messages(build_evidence(body, gait, PHASE0_PUSH, duration=PHASE0_DURATION), body)
        chars = sum(len(m["content"]) for m in msgs)
        print(json.dumps({"prompt_chars": chars, "approx_prompt_tokens(chars/3)": chars // 3,
                          "max_completion_tokens": a.max_tokens}))
        return 0
    client = NebiusClient(limits=Limits(max_requests=1, max_total_tokens=a.max_tokens + 4000, timeout_s=90))
    trial = investigate(client, body, gait, PHASE0_PUSH, duration=PHASE0_DURATION, reasoning_effort=a.reasoning,
                        max_tokens=a.max_tokens, mode="live")
    print(json.dumps({"trial_id": trial.trial_id, "status": trial.status, "reason": trial.rejection_reason,
                      "model_call": trial.model_call, "hypothesis": trial.hypothesis,
                      "outcome": trial.measured_outcome and {k: trial.measured_outcome[k] for k in
                                                              ("observed", "prediction_held", "improved", "accepted")}},
                     indent=2))
    return 0 if trial.status in ("accepted", "rejected_by_verifier") else 1


if __name__ == "__main__":
    sys.exit(main())
