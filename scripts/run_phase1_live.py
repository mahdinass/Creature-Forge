#!/usr/bin/env python
"""Run the PRE-REGISTERED Phase 1 live batch: at most 3 Nemotron requests, 18,000 tokens in total.

Refuses to run unless (1) experiments/phase1/protocol.json is committed and unmodified in Git, (2) the prompts
rebuilt now from MuJoCo hash-match the registered prompts, (3) --confirm-live is given. No retries, no prompt edits.
Every outcome (valid, invalid, rejected, error) is saved to artifacts/investigations/ and summarised in
experiments/phase1/results/live_summary.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from creature_forge.controller import GaitParams
from creature_forge.evaluation import Protocol
from creature_forge.experiment import PHASE0_BASELINE, PHASE0_DURATION, PHASE0_PUSH
from creature_forge.investigator import build_evidence, build_forensic_evidence, build_messages, investigate, prompt_hash
from creature_forge.nebius import Limits, NebiusClient

REG = Path("experiments") / "phase1" / "protocol.json"
OUT = Path("experiments") / "phase1" / "results" / "live_summary.json"
EVIDENCE_SEEDS, VERIFY_SEEDS = (0, 1, 2), (0, 1, 2, 3, 4)


def registered_and_committed() -> str | None:
    """Return None if OK, else the reason the pre-registration is not usable."""
    p = str(REG)
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", p], capture_output=True, text=True)
    if tracked.returncode:
        return "protocol.json is not tracked by git"
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", p]).returncode:
        return "protocol.json has uncommitted changes"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-live", action="store_true", help="actually send the registered requests")
    ap.add_argument("--only", help="run only this call id (default: all, in order)")
    a = ap.parse_args()
    why = registered_and_committed()
    if why:
        print(f"REFUSED: {why}")
        return 2
    reg = json.loads(REG.read_text(encoding="utf-8"))
    lim = reg["live_limits"]
    body, gait = PHASE0_BASELINE, GaitParams()
    built = {"legacy": build_messages(build_evidence(body, gait, PHASE0_PUSH, seeds=EVIDENCE_SEEDS,
                                                     duration=PHASE0_DURATION), body, "legacy"),
             "forensic": build_messages(build_forensic_evidence(body, gait, PHASE0_PUSH, seeds=EVIDENCE_SEEDS,
                                                                duration=PHASE0_DURATION), body, "forensic")}
    for v, msgs in built.items():
        if prompt_hash(msgs) != reg["prompts"][v]["sha256"]:
            print(f"REFUSED: rebuilt {v} prompt does not match the registered hash")
            return 2
    if not a.confirm_live:
        print("dry run OK: registration committed, prompts match registered hashes. Re-run with --confirm-live.")
        return 0

    client = NebiusClient(limits=Limits(max_requests=lim["max_live_requests"], max_total_tokens=lim["max_total_tokens"],
                                        max_tokens_per_request=lim["max_completion_tokens_per_request"],
                                        timeout_s=lim["request_timeout_s"]))
    proto = Protocol()
    summary = {"registered_prompt_sha256": {v: reg["prompts"][v]["sha256"] for v in built}, "calls": [], "stopped": None}
    for call in reg["call_plan"]:
        if a.only and call["id"] != a.only:
            continue
        est_prompt = sum(len(m["content"]) for m in built[call["variant"]]) // 3 + 1
        if client.requests_made >= lim["max_live_requests"]:
            summary["stopped"] = "request limit reached"
            break
        if client.tokens_used >= lim["max_total_tokens"] or \
                client.tokens_used + est_prompt + lim["max_completion_tokens_per_request"] > lim["max_total_tokens"]:
            summary["stopped"] = (f"token budget: used {client.tokens_used} + est prompt {est_prompt} + "
                                  f"max completion {lim['max_completion_tokens_per_request']} > {lim['max_total_tokens']}")
            break
        t = investigate(client, body, gait, PHASE0_PUSH, evidence_seeds=EVIDENCE_SEEDS, verify_seeds=VERIFY_SEEDS,
                        duration=PHASE0_DURATION, max_tokens=lim["max_completion_tokens_per_request"],
                        mode="live", variant=call["variant"], temperature=call["temperature"], protocol=proto,
                        workers=8, label=call["id"])
        po = (t.measured_outcome or {}).get("protocol")
        summary["calls"].append({
            "id": call["id"], "trial_id": t.trial_id, "status": t.status, "reason": t.rejection_reason,
            "prompt_sha256": t.config.get("prompt_sha256"), "model_call": t.model_call,
            "hypothesis": t.hypothesis,
            "screening_prediction_held": (t.measured_outcome or {}).get("prediction_held"),
            "heldout_prediction_held": po and po["prediction_held_heldout_primary"],
            "tier": po and po["verdict"]["tier"], "falls_by_push_baseline_vs_candidate": po and po["verdict"]["falls_by_push"],
            "levels_worse": po and po["verdict"]["levels_where_candidate_worse"],
            "heldout_simulations": po and po["simulations"]})
        print(json.dumps(summary["calls"][-1], indent=1), flush=True)
    summary["totals"] = {"requests": client.requests_made, "tokens": client.tokens_used}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({"stopped": summary["stopped"], "totals": summary["totals"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
