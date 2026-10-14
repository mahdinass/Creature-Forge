"""Windows-side controller for the Creature Forge Nebius CPU VM. Stdlib only; secrets never pass through it.

The official Nebius CLI has no Windows build, so it runs inside WSL Ubuntu (profile 'creature-forge', federation login
stored by the CLI itself, not by this repo). The VM is reached over SSH with a dedicated key (~/.ssh/creature_forge_nebius,
not the user's other keys). State (instance id, IP, deadline) lives in the git-ignored infra/nebius/state.json.

    python infra/nebius/forge_cloud.py plan | create | status | ssh-config | bootstrap | check | exec "<cmd>" |
        run-stage <stage> [--rep N] | monitor | sync-down | extend --hours H | stop | start | delete --yes | watchdog
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = HERE / "state.json"
SSH_KEY = Path.home() / ".ssh" / "creature_forge_nebius"
HOST = "creature-forge-nebius"
REGISTERED_COMMIT = "f33d429c7aaf4a01e5cb960c384350c80a6f50bf"   # R1 pre-registration commit
CFG = {
    "project_id": "project-e01jjnn2pa00wm820bree9", "region": "eu-west1", "subnet_id": "vpcsubnet-e01bb10pt7n200dkqh",
    "name": "creature-forge-r1-cpu", "platform": "cpu-d3", "preset": "8vcpu-32gb", "image_family": "ubuntu24.04-driverless",
    "disk_type": "network_ssd", "disk_gib": 50, "default_deadline_h": 6.0,
    # rates quoted on docs.nebius.com/compute/resources/pricing (from 2026-10-01); verify with `plan` before creating
    "usd_per_vcpu_h": 0.015, "usd_per_gib_ram_h": 0.0045, "usd_per_gib_disk_month": 0.071, "max_usd_per_h": 0.30,
}
WSL = ["wsl.exe", "-d", "Ubuntu", "-u", "mahdi", "--", "bash", "-s"]


def nebius(*args: str, check: bool = True) -> str:
    cmd = "~/.nebius/bin/nebius " + " ".join(shlex.quote(a) for a in args) + "\n"
    r = subprocess.run(WSL, input=cmd.encode(), capture_output=True)
    out = r.stdout.decode(errors="replace").replace("\0", "")
    if check and r.returncode != 0:
        raise SystemExit(f"nebius {' '.join(args[:3])} failed:\n{r.stderr.decode(errors='replace').replace(chr(0), '')[-1500:]}")
    return out


def load() -> dict:
    return json.loads(STATE.read_text("utf-8")) if STATE.exists() else {}


def save(st: dict) -> None:
    STATE.write_text(json.dumps(st, indent=1), "utf-8")


def costs() -> dict:
    c = CFG
    vcpu, ram = (int(c["preset"].split("vcpu")[0]), int(c["preset"].split("-")[1].rstrip("gb")))
    compute = vcpu * c["usd_per_vcpu_h"] + ram * c["usd_per_gib_ram_h"]
    disk_h = c["disk_gib"] * c["usd_per_gib_disk_month"] / 730
    return {"compute_usd_per_h": round(compute, 4), "disk_usd_per_h": round(disk_h, 5), "total_usd_per_h": round(compute + disk_h, 4),
            "run_90min_usd": round(1.5 * (compute + disk_h), 2), "deadline_cap_usd": round(c["default_deadline_h"] * (compute + disk_h), 2),
            "disk_usd_per_day_when_stopped": round(disk_h * 24, 3)}


def ssh(cmd: str, timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["ssh", "-F", str(Path.home() / ".ssh" / "config"), HOST, cmd], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise SystemExit(f"ssh failed ({r.returncode}):\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r


def instance() -> dict:
    st = load()
    if "instance_id" not in st:
        raise SystemExit("no instance recorded; run `create`")
    return json.loads(nebius("compute", "instance", "get", "--id", st["instance_id"], "--format", "json"))


def cmd_plan(_a=None) -> None:
    c = costs()
    print(json.dumps({"config": CFG, "cost": c}, indent=1))
    ok = c["total_usd_per_h"] <= CFG["max_usd_per_h"]
    print("WITHIN the $0.30/h ceiling" if ok else "EXCEEDS the $0.30/h ceiling - will not create")
    if not ok:
        raise SystemExit(1)


def cmd_create(a) -> None:
    c = costs()
    if c["total_usd_per_h"] > CFG["max_usd_per_h"]:
        raise SystemExit("quoted rate exceeds ceiling")
    if load().get("instance_id"):
        raise SystemExit("an instance is already recorded in state.json; refusing to create a second one")
    pub = SSH_KEY.with_suffix(".pub").read_text().strip()
    ci = (HERE / "cloud-init.yaml.tmpl").read_text("utf-8").replace("@@SSH_PUBKEY@@", pub)
    ci = ci.replace("@@DEADLINE_S@@", str(int(CFG["default_deadline_h"] * 3600)))
    ud = shlex.quote(ci)
    nic = json.dumps([{"name": "eth0", "ip_address": {}, "public_ip_address": {}, "subnet_id": CFG["subnet_id"]}])
    script = ("~/.nebius/bin/nebius compute instance create --format json --name %s --resources-platform %s --resources-preset %s "
              "--boot-disk-managed-disk-name %s-boot --boot-disk-managed-disk-type %s --boot-disk-managed-disk-size-gibibytes %d "
              "--boot-disk-managed-disk-source-image-family-image-family %s --boot-disk-attach-mode READ_WRITE "
              "--network-interfaces %s --cloud-init-user-data %s\n") % (
        CFG["name"], CFG["platform"], CFG["preset"], CFG["name"], CFG["disk_type"], CFG["disk_gib"], CFG["image_family"],
        shlex.quote(nic), ud)
    r = subprocess.run(WSL, input=script.encode(), capture_output=True)
    out = r.stdout.decode(errors="replace").replace("\0", "")
    if r.returncode != 0:
        raise SystemExit("create failed:\n" + r.stderr.decode(errors="replace").replace("\0", "")[-1500:])
    obj = json.loads(out)
    iid = (obj.get("resource_id") or obj.get("metadata", {}).get("id") or obj.get("resource", {}).get("metadata", {}).get("id"))
    if not iid:
        raise SystemExit("created, but could not find instance id in output; inspect `nebius compute instance list` NOW to avoid orphaned billing")
    save({"instance_id": iid, "created_epoch": int(time.time()), "deadline_epoch": int(time.time() + CFG["default_deadline_h"] * 3600)})
    print("created", iid, "- run `status` until RUNNING, then `ssh-config`")


def cmd_status(_a=None) -> dict:
    st = load()
    if not st.get("instance_id"):
        print("no instance")
        return {}
    i = instance()
    ip = ((i.get("status", {}).get("network_interfaces") or [{}])[0].get("public_ip_address") or {}).get("address", "").split("/")[0]
    state = i.get("status", {}).get("state")
    if ip:
        st["ip"] = ip
        save(st)
    left = (st.get("deadline_epoch", 0) - time.time()) / 3600
    print(json.dumps({"id": st["instance_id"], "state": state, "ip": ip, "deadline_in_h": round(left, 2),
                      "est_spend_usd_if_running_since_create": round(max(0, (time.time() - st["created_epoch"]) / 3600) * costs()["total_usd_per_h"], 2)}))
    return {"state": state, "ip": ip}


def cmd_ssh_config(_a=None) -> None:
    ip = load().get("ip") or cmd_status().get("ip")
    if not ip:
        raise SystemExit("no public IP yet")
    cfg = Path.home() / ".ssh" / "config"
    text = cfg.read_text() if cfg.exists() else ""
    block = (f"# >>> {HOST} (managed by infra/nebius/forge_cloud.py)\nHost {HOST}\n  HostName {ip}\n  User forge\n  IdentityFile {SSH_KEY}\n"
             f"  IdentitiesOnly yes\n  StrictHostKeyChecking accept-new\n  ServerAliveInterval 30\n  ServerAliveCountMax 6\n# <<< {HOST}\n")
    a, b = f"# >>> {HOST}", f"# <<< {HOST}\n"
    if a in text:
        text = text[: text.index(a)] + text[text.index(b) + len(b):]
    cfg.write_text(text.rstrip("\n") + "\n\n" + block)
    print(f"ssh {HOST}   (HostName {ip})")


def cmd_bootstrap(_a=None) -> None:
    branch = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    bundle = HERE / "repo.bundle"
    subprocess.check_call(["git", "-C", str(ROOT), "bundle", "create", str(bundle), branch], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sc = ["scp", "-F", str(Path.home() / ".ssh" / "config")]
    subprocess.check_call(sc + [str(bundle), f"{HOST}:repo.bundle"])
    subprocess.check_call(sc + [str(HERE / "remote" / "bootstrap.sh"), str(HERE / "remote" / "run_stage.sh"), str(HERE / "remote" / "status.sh"), str(HERE / "remote" / "run_script.sh"),
                                str(HERE / "remote" / "check_env.py"), str(HERE / "reference_windows.json"), f"{HOST}:"])
    bundle.unlink()
    r = ssh(f"chmod +x ~/*.sh && ~/bootstrap.sh ~/repo.bundle {shlex.quote(branch)} {REGISTERED_COMMIT}", timeout=1800)
    print(r.stdout[-2000:])


def cmd_check(_a=None) -> None:
    r = ssh("cd ~/creature-forge && ~/venvs/creature-forge/bin/python ~/creature-forge/infra/nebius/remote/check_env.py "
            "--reference ~/creature-forge/infra/nebius/reference_windows.json --out ~/logs/check_env.json", timeout=1200, check=False)
    print(r.stdout[-3000:], r.stderr[-500:])
    sys.exit(r.returncode)


def cmd_exec(a) -> None:
    r = ssh(a.command, timeout=a.timeout, check=False)
    print(r.stdout, end="")
    print(r.stderr, end="", file=sys.stderr)
    sys.exit(r.returncode)


def cmd_run_stage(a) -> None:
    cmd_verify_deadline()
    print(ssh(f"~/run_stage.sh {shlex.quote(a.stage)} --rep {a.rep}").stdout)


def cmd_run(a) -> None:
    """Launch scripts/<script> <args...> detached on the VM (refuses unless local and VM deadlines are in sync)."""
    cmd_verify_deadline()
    print(ssh("~/run_script.sh " + " ".join(shlex.quote(x) for x in [a.script, *a.args])).stdout)


def cmd_wait(a) -> None:
    """Block until no experiment stage is running on the VM, then print the tail of the newest log."""
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        r = ssh("pgrep -f '[s]cripts/run_r[0-9].py' >/dev/null && echo busy || echo done", timeout=60, check=False)
        if "done" in r.stdout:
            print(ssh("tail -n 25 $(ls -t ~/logs/run_r*.log | head -1)", timeout=60).stdout)
            return
        time.sleep(10)
    raise SystemExit(f"still running after {a.timeout}s")


def cmd_monitor(_a=None) -> None:
    print(ssh("~/status.sh", timeout=60).stdout)


def cmd_sync_down(_a=None) -> Path:
    dest = ROOT / "artifacts" / "nebius_r1" / time.strftime("%Y%m%dT%H%M%S")
    dest.mkdir(parents=True)
    ssh("cd ~ && mkdir -p logs creature-forge/experiments/phase2a_r1/results creature-forge/experiments/phase2a_r2/results creature-forge/experiments/phase2a_r3/results && tar czf /tmp/forge_results.tgz logs creature-forge/experiments/phase2a_r1/results creature-forge/experiments/phase2a_r2/results creature-forge/experiments/phase2a_r3/results && sha256sum /tmp/forge_results.tgz > /tmp/forge_results.sha")
    sc = ["scp", "-F", str(Path.home() / ".ssh" / "config")]
    subprocess.check_call(sc + [f"{HOST}:/tmp/forge_results.tgz", f"{HOST}:/tmp/forge_results.sha", str(dest)])
    import hashlib
    got = hashlib.sha256((dest / "forge_results.tgz").read_bytes()).hexdigest()
    want = (dest / "forge_results.sha").read_text().split()[0]
    if got != want:
        raise SystemExit("checksum mismatch on retrieved results")
    subprocess.check_call(["tar", "xzf", str(dest / "forge_results.tgz"), "-C", str(dest)])
    st = load()
    st["last_sync"] = {"dir": str(dest), "sha256": got, "epoch": int(time.time())}
    save(st)
    print("results verified and extracted to", dest)
    return dest


def cmd_extend(a) -> None:
    dl = set_deadline(a.hours)
    print(f"deadline now {a.hours} h from now ({dl}), local and VM verified equal (est. cap ${a.hours * costs()['total_usd_per_h']:.2f})")


def cmd_stop(_a=None) -> None:
    nebius("compute", "instance", "stop", "--id", load()["instance_id"])
    print("stop requested (compute billing ends when STOPPED; the boot disk keeps billing ~$%s/day)" % costs()["disk_usd_per_day_when_stopped"])


def remote_deadline() -> int:
    return int(ssh("cat /var/lib/forge/deadline", timeout=60).stdout.strip())


def set_deadline(hours: float) -> int:
    """Set the local AND VM-side deadline to the same epoch, then read the VM value back and require equality."""
    st = load()
    dl = int(time.time() + hours * 3600)
    ssh(f"echo {dl} | sudo tee /var/lib/forge/deadline >/dev/null", timeout=60)
    got = remote_deadline()
    if got != dl:
        raise SystemExit(f"deadline sync failed: local {dl} vs VM {got}; the VM would run unguarded - stop it")
    st["deadline_epoch"] = dl
    save(st)
    return dl


def cmd_start(_a=None) -> None:
    nebius("compute", "instance", "start", "--id", load()["instance_id"])
    for _ in range(30):
        time.sleep(10)
        s = cmd_status()
        if s.get("state") == "RUNNING" and s.get("ip"):
            break
    else:
        raise SystemExit("VM did not reach RUNNING; check `status`")
    cmd_ssh_config()
    for _ in range(30):
        if ssh("true", timeout=30, check=False).returncode == 0:
            break
        time.sleep(10)
    else:
        raise SystemExit("SSH not reachable after start")
    dl = set_deadline(CFG["default_deadline_h"])
    print(f"started; local and VM-side deadline verified equal ({dl}, {CFG['default_deadline_h']} h from now)")


def cmd_verify_deadline(_a=None) -> None:
    local, vm = load().get("deadline_epoch", 0), remote_deadline()
    left = (vm - time.time()) / 3600
    ok = local == vm and left > 0
    print(json.dumps({"local": local, "vm": vm, "hours_left": round(left, 2), "in_sync": local == vm}))
    if not ok:
        raise SystemExit("deadline mismatch or expired: refusing to proceed")


def cmd_delete(a) -> None:
    st = load()
    if not a.yes:
        raise SystemExit("refusing: pass --yes. Results must be synced first (this command syncs and verifies automatically).")
    if not a.skip_sync:
        cmd_sync_down()
    iid = st["instance_id"]
    nebius("compute", "instance", "delete", "--id", iid)
    left = json.loads(nebius("compute", "disk", "list", "--format", "json")).get("items", [])
    names = [d["metadata"]["name"] for d in left]
    print("instance deleted; remaining disks (must be empty to stop billing):", names)
    for d in left:
        if d["metadata"]["name"].startswith(CFG["name"]):
            nebius("compute", "disk", "delete", "--id", d["metadata"]["id"])
            print("deleted orphan disk", d["metadata"]["name"])
    st.pop("instance_id", None)
    st["deleted_epoch"] = int(time.time())
    save(st)


def cmd_watchdog(_a=None) -> None:
    """Run from Task Scheduler every 15 min: stops the VM if its deadline passed (independent of any Claude/Codex session)."""
    st = load()
    if not st.get("instance_id"):
        return
    log = HERE / "watchdog.log"
    try:
        state = instance().get("status", {}).get("state")
        if time.time() > st.get("deadline_epoch", 0) and state in ("RUNNING", "STARTING"):
            nebius("compute", "instance", "stop", "--id", st["instance_id"])
            msg = "deadline passed: stop requested"
        else:
            msg = f"ok state={state}"
    except SystemExit as e:
        msg = f"error {e}"
    with log.open("a") as f:
        f.write(f"{time.strftime('%FT%T')} {msg}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for n in ("plan", "create", "status", "ssh-config", "bootstrap", "check", "monitor", "sync-down", "stop", "start", "watchdog", "verify-deadline"):
        sp.add_parser(n)
    e = sp.add_parser("exec"); e.add_argument("command"); e.add_argument("--timeout", type=int, default=600)
    r = sp.add_parser("run-stage"); r.add_argument("stage", choices=["pilot", "train", "validate", "gate", "select"]); r.add_argument("--rep", type=int, default=1)
    w = sp.add_parser("wait"); w.add_argument("--timeout", type=int, default=3300)
    ru = sp.add_parser("run"); ru.add_argument("script"); ru.add_argument("args", nargs=argparse.REMAINDER)
    x = sp.add_parser("extend"); x.add_argument("--hours", type=float, required=True)
    d = sp.add_parser("delete"); d.add_argument("--yes", action="store_true"); d.add_argument("--skip-sync", action="store_true")
    a = ap.parse_args()
    {"plan": cmd_plan, "create": cmd_create, "status": cmd_status, "ssh-config": cmd_ssh_config, "bootstrap": cmd_bootstrap,
     "check": cmd_check, "exec": cmd_exec, "run-stage": cmd_run_stage, "monitor": cmd_monitor, "sync-down": cmd_sync_down,
     "extend": cmd_extend, "stop": cmd_stop, "start": cmd_start, "verify-deadline": cmd_verify_deadline, "run": cmd_run, "wait": cmd_wait, "delete": cmd_delete, "watchdog": cmd_watchdog}[a.cmd](a)


if __name__ == "__main__":
    main()
