"""Windows-side controller for the Creature Forge Nebius CPU VM. Stdlib only; secrets never pass through it.

The official Nebius CLI has no Windows build, so it runs inside WSL Ubuntu (profile 'creature-forge', federation login
stored by the CLI itself, not by this repo). The VM is reached over SSH with a dedicated key (~/.ssh/creature_forge_nebius,
not the user's other keys). State (instance id, IP, deadline) lives in the git-ignored infra/nebius/state.json.

    python infra/nebius/forge_cloud.py plan | create | status | ssh-config | bootstrap | check | exec "<cmd>" |
        run-stage <stage> [--rep N] | monitor | sync-down | extend --hours H | stop | start | delete --yes | watchdog | spend
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# Infra cap across ALL VM profiles (combined): $10 (2026-10-14), raised to $20 by the owner on 2026-10-16 for the
# walking-recovery S1 stage (temporary 64-vCPU batch VM), and to $35 on 2026-10-17 for iteration 3 (S4a, S4b, S3, demo). create/start/extend refuse beyond it.
# 2026-10-18: phase-3 Stage 1 approved by the owner (infra envelope $35; real Cloud credit $66 at a ledger of $33.29).
# Cap = ledger 33.29 + envelope 35 + ~3 disk accrual; the credit-supported maximum is ~$94 (ledger + credit - $5 reserve).
# 2026-10-19: Stage 1 ended at a ledger of $75.48 (5.39 h of unplanned batch time past a deadline, CLI login expired).
# Phase-3 Stage 2 approved by the owner: +$20 incremental infra. Cap = ledger at the Stage-2 start $75.48 + $20 + $0.5
# accounting slack (disk accrual rounding). Estimated real credit before Stage 2 is ~$23.8.
SPEND_CAP_USD = 96.0
SSH_KEY = Path.home() / ".ssh" / "creature_forge_nebius"
REGISTERED_COMMIT = "f33d429c7aaf4a01e5cb960c384350c80a6f50bf"   # R1 pre-registration commit
_BASE = {
    "project_id": "project-e01jjnn2pa00wm820bree9", "region": "eu-west1", "subnet_id": "vpcsubnet-e01bb10pt7n200dkqh",
    "platform": "cpu-d3", "image_family": "ubuntu24.04-driverless", "disk_type": "network_ssd", "disk_gib": 50,
    # rates quoted on docs.nebius.com/compute/resources/pricing (from 2026-10-01); verify with `plan` before creating
    "usd_per_vcpu_h": 0.015, "usd_per_gib_ram_h": 0.0045, "usd_per_gib_disk_month": 0.071,
}
# VM profiles, selected with the environment variable CF_VM (default "main"; forge_dev.py inherits it). "main" is the
# long-lived dev VM (paths unchanged); "batch" is a temporary large VM for heavy MuJoCo batches, deleted after use.
PROFILES = {
    "main": {**_BASE, "name": "creature-forge-r1-cpu", "preset": "8vcpu-32gb", "default_deadline_h": 6.0, "max_usd_per_h": 0.30,
             "state": "state.json", "spend": "spend_ledger.jsonl", "host": "creature-forge-nebius"},
    "batch": {**_BASE, "name": "creature-forge-batch", "preset": "64vcpu-256gb", "default_deadline_h": 3.0, "max_usd_per_h": 2.30,
              "state": "state_batch.json", "spend": "spend_ledger_batch.jsonl", "host": "creature-forge-batch"},
}
VM = os.environ.get("CF_VM", "main")
if VM not in PROFILES:
    raise SystemExit(f"CF_VM must be one of {sorted(PROFILES)}, got {VM!r}")
CFG = PROFILES[VM]
STATE = HERE / CFG["state"]                 # git-ignored
SPEND = HERE / CFG["spend"]                 # git-ignored; infra spend ledger of this profile (main: from 2026-10-14)
HOST = CFG["host"]
WSL = ["wsl.exe", "-d", "Ubuntu", "-u", "mahdi", "--", "bash", "-s"]


AUTH_BLOCKED = HERE / "AUTH_BLOCKED"       # git-ignored marker: set on the first auth failure, cleared only by `login`
_AUTH_SIGNS = ("auth.nebius.com", "authentication", "oauth2", "unauthenticated", "token is expired")


def nebius(*args: str, check: bool = True, interactive: bool = False) -> str:
    """Run the Nebius CLI in WSL. Unattended calls never open a browser (--no-browser) and give up on auth after 30 s.
    An auth failure writes AUTH_BLOCKED; every later unattended call then refuses without contacting Nebius (no repeated
    login attempts) until the owner runs `forge_cloud.py login` in a terminal (owner instruction, 2026-10-19)."""
    if not interactive and AUTH_BLOCKED.exists():
        raise SystemExit(f"nebius auth blocked since {AUTH_BLOCKED.read_text('utf-8').strip()}: "
                         "run `python infra/nebius/forge_cloud.py login` in a terminal (opens the browser once)")
    flags = [] if interactive else ["--no-browser", "--auth-timeout", "30s"]
    cmd = "~/.nebius/bin/nebius " + " ".join(shlex.quote(a) for a in [*flags, *args]) + "\n"
    try:
        r = subprocess.run(WSL, input=cmd.encode(), capture_output=True, timeout=None if interactive else 180)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"nebius {' '.join(args[:3])} timed out")
    out = r.stdout.decode(errors="replace").replace("\0", "")
    err = r.stderr.decode(errors="replace").replace("\0", "")
    if r.returncode != 0 and not interactive and any(k in (out + err).lower() for k in _AUTH_SIGNS):
        AUTH_BLOCKED.write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n", "utf-8")
        raise SystemExit("nebius auth failed (login expired): AUTH_BLOCKED written, no further attempts. "
                         "Run `python infra/nebius/forge_cloud.py login` in a terminal.")
    if check and r.returncode != 0:
        raise SystemExit(f"nebius {' '.join(args[:3])} failed:\n{err[-1500:]}")
    return out


def cmd_login(_a=None) -> None:
    """Owner action in a terminal: refresh the CLI login (may open the browser once), then clear AUTH_BLOCKED."""
    nebius("compute", "instance", "list", "--parent-id", CFG["project_id"], "--format", "json", interactive=True)
    AUTH_BLOCKED.unlink(missing_ok=True)
    exp = auth_expiry()
    print("login ok; AUTH_BLOCKED cleared" + (f"; CLI auth valid for {(exp - time.time()) / 3600:.1f} h" if exp else ""))


# Auth horizon (2026-10-24 incident: the federation token is a fixed ~12 h access token with no refresh; once it expires the
# watchdog can no longer stop anything). Rule: no VM may be running when the token expires. `start`/`extend` keep every
# deadline (+ watchdog lag) inside the token lifetime, and the watchdog stops running VMs AUTH_MARGIN_S before expiry.
AUTH_MARGIN_S = 1800         # pre-emptive stop this long before expiry (watchdog period 15 min -> stops >= 15 min early)
WATCHDOG_LAG_S = 900         # the watchdog runs every 15 min
_EXPIRY_CMD = "grep -E '^[[:space:]]*expires_at:' ~/.nebius/credentials.yaml 2>/dev/null\n"   # never reads the token line


def parse_expiry(text: str) -> int | None:
    """Earliest `expires_at:` epoch in credentials.yaml text (conservative if several profiles hold tokens)."""
    vals = []
    for line in text.splitlines():
        k, _, v = line.strip().partition(":")
        if k == "expires_at":
            try:
                vals.append(int(float(v.strip().strip("'\""))))
            except ValueError:
                pass
    return min(vals) if vals else None


def auth_expiry() -> int | None:
    """Epoch at which the WSL Nebius CLI federation token expires, or None if unknown. The token itself never leaves WSL."""
    try:
        r = subprocess.run(WSL, input=_EXPIRY_CMD.encode(), capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    return parse_expiry(r.stdout.decode(errors="replace").replace("\0", ""))


def auth_horizon(expiry: int | None, now: float | None = None) -> float:
    """Latest epoch a VM deadline may have so that the watchdog still holds a valid token when it must act."""
    now = time.time() if now is None else now
    if expiry is None:
        return now                       # unknown lifetime: treat as expired (fail closed)
    return expiry - AUTH_MARGIN_S - WATCHDOG_LAG_S


def auth_clamp_hours(hours: float, expiry: int | None, now: float | None = None) -> float:
    """Hours of deadline that fit inside the auth horizon (<= hours, possibly <= 0)."""
    now = time.time() if now is None else now
    return min(hours, (auth_horizon(expiry, now) - now) / 3600)


def auth_guard(hours: float, *, clamp: bool) -> float:
    """Return the deadline length to use. `clamp` (start) shortens to the horizon; otherwise (extend) refuse beyond it."""
    exp = auth_expiry()
    ok = auth_clamp_hours(hours, exp)
    left = "unknown" if exp is None else f"{(exp - time.time()) / 3600:.2f} h"
    if ok >= hours:
        return hours
    if clamp and ok >= 0.5:
        print(f"WARNING: CLI auth expires in {left}; deadline shortened from {hours} h to {ok:.2f} h so the watchdog can "
              "still stop the VM. Run `forge_cloud.py login` to get a fresh ~12 h window.")
        return ok
    raise SystemExit(f"refusing: a {hours} h deadline outlives the Nebius CLI auth (expires in {left}; need "
                     f"{(AUTH_MARGIN_S + WATCHDOG_LAG_S) / 60:.0f} min margin). Run `python infra/nebius/forge_cloud.py login` first.")


def load() -> dict:
    return json.loads(STATE.read_text("utf-8")) if STATE.exists() else {}


def save(st: dict) -> None:
    STATE.write_text(json.dumps(st, indent=1), "utf-8")


def costs(c: dict | None = None) -> dict:
    c = c or CFG
    vcpu, ram = (int(c["preset"].split("vcpu")[0]), int(c["preset"].split("-")[1].rstrip("gb")))
    compute = vcpu * c["usd_per_vcpu_h"] + ram * c["usd_per_gib_ram_h"]
    disk_h = c["disk_gib"] * c["usd_per_gib_disk_month"] / 730
    return {"compute_usd_per_h": round(compute, 4), "disk_usd_per_h": round(disk_h, 5), "total_usd_per_h": round(compute + disk_h, 4),
            "run_90min_usd": round(1.5 * (compute + disk_h), 2), "deadline_cap_usd": round(c["default_deadline_h"] * (compute + disk_h), 2),
            "disk_usd_per_day_when_stopped": round(disk_h * 24, 3)}


def spend_events(path: Path | None = None) -> list[dict]:
    path = path or SPEND
    return [json.loads(l) for l in path.read_text("utf-8").splitlines() if l.strip()] if path.exists() else []


def spend_record(event: str, **kw) -> None:
    with SPEND.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": event, "epoch": int(time.time()), **kw}) + "\n")


def spend_total(now: float | None = None, profile: str | None = None) -> dict:
    """Conservative spend since the ledger started: every run interval is charged from its start until the next recorded
    API stop (or `now` if none). The deadman timer powers the GUEST off at the deadline, but on 2026-10-15 the instance
    still reported RUNNING 3.75 h later, so a guest poweroff is not assumed to end compute billing. Disk is charged
    continuously from the first event. Rates are the quoted ones in CFG, not a billing statement."""
    now = time.time() if now is None else now
    prof = PROFILES[profile or VM]
    ev = spend_events(HERE / prof["spend"])
    if not ev:
        return {"compute_h": 0.0, "usd": 0.0, "cap_usd": SPEND_CAP_USD}
    c = costs(prof)
    hours, run_start, deadline = 0.0, None, 0.0
    for e in ev:
        if e["event"] == "start":
            if run_start is not None:
                hours += max(0.0, e["epoch"] - run_start) / 3600
            run_start, deadline = e["epoch"], e["deadline"]
        elif e["event"] == "extend" and run_start is not None:
            deadline = e["deadline"]
        elif e["event"] == "stop" and run_start is not None:
            hours += max(0.0, e["epoch"] - run_start) / 3600
            run_start = None
    if run_start is not None:
        hours += max(0.0, now - run_start) / 3600
    end = now
    if any(e["event"] == "deleted" for e in ev):        # a deleted profile's disk stops billing at deletion
        end = max(e["epoch"] for e in ev if e["event"] == "deleted")
    disk_h = max(0.0, end - ev[0]["epoch"]) / 3600
    usd = hours * c["compute_usd_per_h"] + disk_h * c["disk_usd_per_h"]
    return {"compute_h": round(hours, 3), "usd": round(usd, 3), "cap_usd": SPEND_CAP_USD}


def spend_all(now: float | None = None) -> dict:
    per = {name: spend_total(now, name) for name in PROFILES}
    return {"usd": round(sum(v["usd"] for v in per.values()), 3), "cap_usd": SPEND_CAP_USD, "profiles": per}


def spend_guard(extra_hours: float) -> None:
    t = spend_all()
    projected = t["usd"] + extra_hours * costs()["total_usd_per_h"]
    if projected > SPEND_CAP_USD:
        raise SystemExit(f"refusing: projected infra spend ${projected:.2f} exceeds the approved ${SPEND_CAP_USD:.2f} cap "
                         f"(spent ~${t['usd']:.2f}); ask the owner to raise it")


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
    print(f"profile {VM}: " + (f"WITHIN the ${CFG['max_usd_per_h']:.2f}/h ceiling" if ok
                               else f"EXCEEDS the ${CFG['max_usd_per_h']:.2f}/h ceiling - will not create"))
    if not ok:
        raise SystemExit(1)


def cmd_create(a) -> None:
    c = costs()
    if c["total_usd_per_h"] > CFG["max_usd_per_h"]:
        raise SystemExit("quoted rate exceeds ceiling")
    if load().get("instance_id"):
        raise SystemExit(f"an instance is already recorded in {STATE.name}; refusing to create a second one")
    spend_guard(CFG["default_deadline_h"])
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
    spend_record("start", deadline=int(time.time() + CFG["default_deadline_h"] * 3600) + 900, by="create")
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
    exp = auth_expiry()
    print(json.dumps({"id": st["instance_id"], "state": state, "ip": ip, "deadline_in_h": round(left, 2),
                      "auth_expires_in_h": None if exp is None else round((exp - time.time()) / 3600, 2),
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
        r = ssh("pgrep -f '[s]cripts/run_r[0-9a-z_]*.py' >/dev/null && echo busy || echo done", timeout=60, check=False)
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
    ssh("cd ~ && mkdir -p logs creature-forge/experiments/phase2a_r3/results_v2 creature-forge/experiments/phase2a_r1/results creature-forge/experiments/phase2a_r2/results creature-forge/experiments/phase2a_r3/results creature-forge/experiments/phase2a_r3/results_v2 && tar czf /tmp/forge_results.tgz logs creature-forge/experiments/phase2a_r1/results creature-forge/experiments/phase2a_r2/results creature-forge/experiments/phase2a_r3/results creature-forge/experiments/phase2a_r3/results_v2 && sha256sum /tmp/forge_results.tgz > /tmp/forge_results.sha")
    sc = ["scp", "-F", str(Path.home() / ".ssh" / "config")]
    subprocess.check_call(sc + [f"{HOST}:/tmp/forge_results.tgz", f"{HOST}:/tmp/forge_results.sha", str(dest)])
    import hashlib
    got = hashlib.sha256((dest / "forge_results.tgz").read_bytes()).hexdigest()
    want = (dest / "forge_results.sha").read_text().split()[0]
    if got != want:
        raise SystemExit("checksum mismatch on retrieved results")
    with tarfile.open(dest / "forge_results.tgz", "r:gz") as tf:  # the checksum only proves integrity, not safety: filter="data" refuses
        tf.extractall(dest, filter="data")                        # absolute paths, "..", links outside dest and special files
    st = load()
    st["last_sync"] = {"dir": str(dest), "sha256": got, "epoch": int(time.time())}
    save(st)
    print("results verified and extracted to", dest)
    return dest


def cmd_extend(a) -> None:
    left = max(0.0, (load().get("deadline_epoch", 0) - time.time()) / 3600)
    spend_guard(max(0.0, a.hours - left))
    auth_guard(a.hours, clamp=False)
    dl = set_deadline(a.hours)
    spend_record("extend", deadline=dl)
    print(f"deadline now {a.hours} h from now ({dl}), local and VM verified equal (est. cap ${a.hours * costs()['total_usd_per_h']:.2f})")


def cmd_stop(_a=None) -> None:
    nebius("compute", "instance", "stop", "--id", load()["instance_id"])
    spend_record("stop")
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
    spend_guard(CFG["default_deadline_h"])
    hours = auth_guard(CFG["default_deadline_h"], clamp=True)
    nebius("compute", "instance", "start", "--id", load()["instance_id"])
    spend_record("start", deadline=int(time.time() + hours * 3600) + 900)  # +15 min: boot/sync slack
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
    dl = set_deadline(hours)
    spend_record("extend", deadline=dl)
    print(f"started; local and VM-side deadline verified equal ({dl}, {hours:.2f} h from now)")


def cmd_spend(_a=None) -> None:
    print(json.dumps(spend_all()))


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
    spend_record("stop", by="delete")
    spend_record("deleted")


def cmd_watchdog(_a=None) -> None:
    """Run from Task Scheduler every 15 min: stops EVERY profile's VM whose deadline passed (independent of any session),
    and pre-emptively stops running VMs when the CLI auth is about to expire (after expiry it could stop nothing)."""
    log = HERE / "watchdog.log"
    exp = auth_expiry()
    for name, prof in PROFILES.items():
        path = HERE / prof["state"]
        st = json.loads(path.read_text("utf-8")) if path.exists() else {}
        if not st.get("instance_id"):
            continue
        try:
            got = json.loads(nebius("compute", "instance", "get", "--id", st["instance_id"], "--format", "json"))
            state = got.get("status", {}).get("state")
            why = watchdog_reason(time.time(), st.get("deadline_epoch", 0), exp, state)
            if why:
                nebius("compute", "instance", "stop", "--id", st["instance_id"])
                with (HERE / prof["spend"]).open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"event": "stop", "epoch": int(time.time()), "by": "watchdog", "reason": why}) + "\n")
                msg = f"{why}: stop requested"
            else:
                msg = f"ok state={state}" + ("" if exp is None else f" auth_left_h={(exp - time.time()) / 3600:.2f}")
        except SystemExit as e:
            msg = f"error {e}"
        with log.open("a") as f:
            f.write(f"{time.strftime('%FT%T')} [{name}] {msg}\n")


def watchdog_reason(now: float, deadline: float, expiry: int | None, state: str | None) -> str | None:
    """Why the watchdog must stop a VM now, or None. Unknown auth expiry does not trigger a stop by itself (the `get` call
    that produced `state` just succeeded, so the token is valid now)."""
    if state not in ("RUNNING", "STARTING"):
        return None
    if now > deadline:
        return "deadline passed"
    if expiry is not None and now >= expiry - AUTH_MARGIN_S:
        return "CLI auth expiring"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for n in ("plan", "create", "status", "ssh-config", "bootstrap", "check", "monitor", "sync-down", "stop", "start", "watchdog", "verify-deadline", "spend", "login"):
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
     "extend": cmd_extend, "stop": cmd_stop, "start": cmd_start, "verify-deadline": cmd_verify_deadline, "run": cmd_run, "wait": cmd_wait, "delete": cmd_delete, "watchdog": cmd_watchdog, "spend": cmd_spend, "login": cmd_login}[a.cmd](a)


if __name__ == "__main__":
    main()
