"""R0 scoped wrapper around existing forge_cloud operations, never new IAM.

The explicit --ops-root identifies the existing machine-local operational state,
SA-profile metadata and ledgers. Only normal cloud lifecycle operations update
those ignored operational files; Claude's source and scientific work are unused.
Current account credit must be independently verified before `start`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def cloud(ops_root, profile):
    s = importlib.util.spec_from_file_location("r0_forge_cloud", ROOT/"infra/nebius/forge_cloud.py")
    fc = importlib.util.module_from_spec(s)
    s.loader.exec_module(fc)
    fc.HERE = Path(ops_root).resolve()
    fc.VM, fc.CFG = profile, dict(fc.PROFILES[profile])
    fc.HOST = fc.CFG["host"]
    fc.STATE, fc.SPEND = fc.HERE/fc.CFG["state"], fc.HERE/fc.CFG["spend"]
    fc.SA_CFG, fc.AUTH_BLOCKED = fc.HERE/"sa.json", fc.HERE/"AUTH_BLOCKED"
    if not fc.SA_CFG.exists() or time.time() >= fc.sa_config()["key_expires_epoch"]:
        raise ValueError("unattended service-account authentication unavailable")
    # No personal-login fallback: the campaign requires service-account control.
    fc.ctl = fc.nebius_sa
    fc.nebius = fc.nebius_sa  # cmd_start calls this legacy entry point directly
    return fc


def states(fc):
    out = {}
    for profile, config in fc.PROFILES.items():
        d = json.loads((fc.HERE/config["state"]).read_text(encoding="utf-8"))
        obj = json.loads(fc.nebius_sa("compute", "instance", "get", "--id", d["instance_id"], "--format", "json"))
        out[profile] = {"id": d["instance_id"], "state": obj.get("status", {}).get("state"),
                        "resources": obj.get("spec", {}).get("resources")}
    return out


def limits(campaign, current_spend, now):
    if not all(math.isfinite(float(x)) for x in (campaign["first_start_epoch"], campaign["verified_credit_usd"],
                                               campaign["initial_spend_usd"], current_spend, now)):
        raise ValueError("nonfinite campaign resource state")
    elapsed = max(0, now-campaign["first_start_epoch"])
    # Wall-time since first paid start is stricter than summed paid runtime.
    hours = max(0, (10*3600-elapsed-300)/3600)
    money = min(35, campaign["verified_credit_usd"])-max(0, current_spend-campaign["initial_spend_usd"])
    return hours, money


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--ops-root", required=True)
    p.add_argument("--campaign", default="artifacts/r0_ops/campaign.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    start = sub.add_parser("start")
    start.add_argument("--hours", type=float, required=True)
    start.add_argument("--credit-evidence", required=True,
                       help="JSON: available_usd, verified_epoch, source; current console/owner verification")
    sub.add_parser("stop")
    sub.add_parser("prove-selfstop")
    deadline = sub.add_parser("deadline")
    deadline.add_argument("--hours", type=float, required=True)
    a = p.parse_args()
    fc = cloud(a.ops_root, "batch")
    st = states(fc)
    current = fc.spend_all()
    if a.cmd == "status":
        print(json.dumps({"checked_epoch": time.time(), "states": st, "ledger": current,
                          "batch_quoted_rate": fc.costs(), "sa_expiry": fc.sa_config()["key_expires_epoch"]}, indent=2))
        return
    if a.cmd == "stop":
        if st["batch"]["state"] != "STOPPED":
            fc.cmd_stop()
        print(json.dumps(states(fc), indent=2))
        return
    if a.cmd == "prove-selfstop":
        if st["batch"]["state"] != "RUNNING":
            raise ValueError("self-stop test requires the authorized engineering VM start")
        fc.ssh("sudo systemctl is-active --quiet forge-selfstop.timer && "
               "sudo test -x /usr/local/sbin/forge-selfstop && "
               "date +%s | sudo tee /var/lib/forge/deadline >/dev/null && "
               "sudo /usr/local/sbin/forge-selfstop", timeout=90, check=False)
        got = fc.wait_state(st["batch"]["id"], timeout_s=180)
        if got != "STOPPED":
            fc.cmd_stop()
            raise ValueError("VM-side self-stop test failed; external stop applied")
        fc.spend_record("stop", by="r0_vm_side_selfstop_test")
        proof = {"verified_epoch": time.time(), "state": got, "instance_id": st["batch"]["id"]}
        path = Path(a.campaign).parent/"selfstop_proof.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proof, indent=2), encoding="utf-8")
        print(json.dumps(proof))
        return
    cp = Path(a.campaign)
    if not cp.exists():
        if a.cmd != "start":
            raise ValueError("campaign must be initialized by start")
        evidence = json.loads(Path(a.credit_evidence).read_text(encoding="utf-8"))
        if not evidence.get("source") or not 0 <= time.time()-evidence["verified_epoch"] <= 3600 or \
                not math.isfinite(evidence["available_usd"]) or evidence["available_usd"] <= 0:
            raise ValueError("current credit evidence required, <=1 hour old")
        campaign = {"first_start_epoch": time.time(), "verified_credit_usd": evidence["available_usd"],
                    "credit_evidence": evidence, "initial_spend_usd": current["usd"],
                    "additional_cap_usd": 35, "max_hours": 10}
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(campaign, indent=2), encoding="utf-8")
    campaign = json.loads(cp.read_text(encoding="utf-8"))
    hours, dollars = limits(campaign, current["usd"], time.time())
    if not math.isfinite(a.hours) or not 0 < a.hours <= hours or a.hours*fc.costs()["total_usd_per_h"] + .5 > dollars:
        raise ValueError("requested deadline exceeds campaign runtime/credit/spend remainder")
    if st["main"]["state"] != "STOPPED":
        raise ValueError("main VM is not stopped; do not interfere with another workload")
    fc.SPEND_CAP_USD = campaign["initial_spend_usd"] + min(35, campaign["verified_credit_usd"])
    if a.cmd == "start":
        if st["batch"]["state"] != "STOPPED":
            raise ValueError("batch VM already active; no takeover")
        fc.CFG["default_deadline_h"] = a.hours
        fc.cmd_start()
    else:
        proof = json.loads((cp.parent/"selfstop_proof.json").read_text(encoding="utf-8"))
        if proof.get("state") != "STOPPED" or proof.get("instance_id") != st["batch"]["id"] or not \
                campaign["first_start_epoch"] <= proof.get("verified_epoch", 0) <= time.time():
            raise ValueError("no end-to-end API self-stop proof")
        fc.cmd_extend(argparse.Namespace(hours=a.hours))
    print(json.dumps({"states": states(fc), "campaign": campaign, "deadline_epoch": fc.load()["deadline_epoch"]}, indent=2))


if __name__ == "__main__":
    main()
