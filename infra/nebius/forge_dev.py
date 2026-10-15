"""Remote development loop on the Creature Forge Nebius VM: code is edited on Windows, everything heavy runs on the VM.

    python infra/nebius/forge_dev.py bootstrap                      # one-time: Node 22, Chrome, bare repo (idempotent)
    python infra/nebius/forge_dev.py sync  [--tree PATH] [--slot S]  # mirror the worktree INCLUDING uncommitted changes
    python infra/nebius/forge_dev.py exec  [--slot S] [--heavy] [--timeout T] "<cmd>"
    python infra/nebius/forge_dev.py test  [--slot S] {py,fe,e2e,smoke,all}   # implies sync
    python infra/nebius/forge_dev.py serve [--slot S]               # Studio on the VM at 127.0.0.1:8000 (tmux)
    python infra/nebius/forge_dev.py tunnel [--stop]                # local http://127.0.0.1:8765 -> VM 127.0.0.1:8000
    python infra/nebius/forge_dev.py pull  [--slot S] [PATH]        # copy VM slot files (default artifacts/forge) back

How `sync` works: a throwaway commit of the worktree is built with a temporary GIT_INDEX_FILE (the real index, HEAD and
branch are untouched; .gitignore'd files such as .env are excluded), pushed over SSH to refs/dev/<slot> of the bare repo
~/dev/cf.git on the VM, and checked out detached in ~/dev/<slot> (core.autocrlf=false, like CI) followed by `git clean -fd`
without -x, so ignored VM outputs (artifacts/, node_modules/, dist/) survive. Each slot has its own venv in ~/dev/venvs/<slot>.
The registered research clone ~/creature-forge is never touched. No GitHub credentials are needed on the VM.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shlex
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import forge_cloud as fc  # noqa: E402  (shared HOST, ssh(), state)

SSH_CFG = str(Path.home() / ".ssh" / "config")
TUNNEL_PID = HERE / "tunnel.pid"
LOCAL_PORT = 8765
TESTS = {
    "py": "python -m unittest discover -s tests",
    "fe": "npm --prefix studio test && npm --prefix studio run build",
    "e2e": "test -f studio/dist/index.html || npm --prefix studio run build; python scripts/lab_browser_check.py",
    "smoke": "python scripts/smoke_test.py && python scripts/verify_demo_trials.py",
}


def git(tree: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", "-C", str(tree), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, **(env or {})}).stdout.strip()


def default_slot(tree: Path) -> str:
    name = git(tree, "rev-parse", "--abbrev-ref", "HEAD")
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name.split("/")[-1])[:40] or "default"


def snapshot(tree: Path) -> str:
    """Commit object for the current worktree contents (tracked + untracked, not ignored), parented on HEAD."""
    idx = tree / ".git" / "forge-dev.index" if (tree / ".git").is_dir() else Path(git(tree, "rev-parse", "--git-path", "forge-dev.index"))
    if not idx.is_absolute():
        idx = tree / idx
    env = {"GIT_INDEX_FILE": str(idx)}
    try:
        git(tree, "read-tree", "HEAD", env=env)
        git(tree, "add", "-A", env=env)
        t = git(tree, "write-tree", env=env)
        return git(tree, "commit-tree", t, "-p", "HEAD", "-m", "forge-dev snapshot (never pushed to GitHub)")
    finally:
        idx.unlink(missing_ok=True)


def remote_bash(script: str, timeout: int) -> subprocess.CompletedProcess:
    """Run a bash script on the VM via stdin. Bytes, not text mode: Windows text mode would send CRLF line endings."""
    r = subprocess.run(["ssh", "-F", SSH_CFG, fc.HOST, "bash -s"], input=script.encode(), capture_output=True, timeout=timeout)
    return subprocess.CompletedProcess(r.args, r.returncode, r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"))


def remote_prepare(slot: str) -> str:
    s, v = f"$HOME/dev/{slot}", f"$HOME/dev/venvs/{slot}"
    return f"""set -euo pipefail
S={s}; V={v}
[ -d "$S/.git" ] || {{ git clone -q "$HOME/dev/cf.git" "$S" 2>/dev/null; git -C "$S" config core.autocrlf false; }}
cd "$S"
git fetch -q origin "+refs/dev/{slot}:refs/dev/{slot}"
git checkout -q -f --detach "refs/dev/{slot}"
git clean -fdq
[ -x "$V/bin/python" ] || python3 -m venv "$V"
h=$(sha256sum pyproject.toml | cut -c1-16)
if [ "$(cat "$V/.pyproject" 2>/dev/null)" != "$h" ]; then "$V/bin/pip" install -q --upgrade pip; "$V/bin/pip" install -q -e '.[studio]'; echo "$h" > "$V/.pyproject"; fi
if [ -f studio/package-lock.json ] && command -v npm >/dev/null; then
  h2=$(sha256sum studio/package-lock.json | cut -c1-16)
  if [ "$(cat studio/node_modules/.lockhash 2>/dev/null)" != "$h2" ]; then npm --prefix studio ci --no-audit --no-fund --loglevel=error; echo "$h2" > studio/node_modules/.lockhash; fi
fi
[ -f "$HOME/dev/.env" ] && ln -sf "$HOME/dev/.env" "$S/.env"
echo "synced {slot} at $(git rev-parse --short HEAD)"
"""


def cmd_sync(a) -> str:
    tree = Path(a.tree).resolve()
    slot = a.slot or default_slot(tree)
    fc.ssh("bash -lc " + shlex.quote("[ -d ~/dev/cf.git ] || git init --bare -q ~/dev/cf.git"), timeout=60)
    sha = snapshot(tree)
    env = {**os.environ, "GIT_SSH_COMMAND": f'ssh -F "{SSH_CFG}"'}
    subprocess.run(["git", "-C", str(tree), "push", "-q", "--force", f"{fc.HOST}:dev/cf.git", f"{sha}:refs/dev/{slot}"],
                   check=True, env=env)
    r = remote_bash(remote_prepare(slot), timeout=1800)
    if r.returncode != 0:
        raise SystemExit(f"remote prepare failed ({r.returncode}):\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    print(r.stdout.strip().splitlines()[-1])
    return slot


def run_remote(slot: str, cmd: str, timeout: int, heavy: bool, tail: int = 60) -> int:
    lock = "flock -w 3600 $HOME/dev/.heavy.lock " if heavy else ""
    script = f"""cd "$HOME/dev/{slot}" || exit 90
export VIRTUAL_ENV=$HOME/dev/venvs/{slot} PATH=$HOME/dev/venvs/{slot}/bin:$PATH CF_SLOT={slot} PYTHONUNBUFFERED=1
export CF_INFERENCE_LEDGER=$HOME/dev/ledger/inference_ledger.jsonl; mkdir -p $HOME/dev/ledger
left=$(( $(cat /var/lib/forge/deadline 2>/dev/null || echo 0) - $(date +%s) ))
[ "$left" -lt {timeout} ] && echo "WARNING: VM deadline in $((left/60)) min (< command timeout); extend with forge_cloud.py extend"
log=$HOME/logs/dev/$(date +%Y%m%dT%H%M%S)-{slot}.log
{lock}timeout {timeout} bash -c {shlex.quote(cmd)} > "$log" 2>&1; rc=$?
tail -n {tail} "$log"; echo "[forge-dev] rc=$rc log=$log"; exit $rc
"""
    r = remote_bash(script, timeout=timeout + 120)
    print(r.stdout, end="")
    if r.stderr.strip():
        print(r.stderr[-1500:], file=sys.stderr)
    return r.returncode


def cmd_exec(a) -> None:
    slot = a.slot or default_slot(Path(a.tree).resolve())
    sys.exit(run_remote(slot, a.command, a.timeout, a.heavy, a.tail))


def cmd_test(a) -> None:
    slot = cmd_sync(a)
    kinds = ["py", "fe", "e2e", "smoke"] if a.kind == "all" else [a.kind]
    results = {}
    for k in kinds:
        print(f"=== {k}: {TESTS[k]}")
        results[k] = run_remote(slot, TESTS[k], a.timeout, heavy=True, tail=a.tail)
    print("=== summary", {k: ("PASS" if rc == 0 else f"FAIL rc={rc}") for k, rc in results.items()})
    sys.exit(max(results.values()))


def cmd_serve(a) -> None:
    slot = a.slot or default_slot(Path(a.tree).resolve())
    live = "export CREATURE_FORGE_ENABLE_LIVE=1 && " if a.live else ""   # live Nemotron calls only when explicitly asked
    inner = (f'cd $HOME/dev/{slot} && {live}export PATH=$HOME/dev/venvs/{slot}/bin:$PATH CF_SLOT={slot} '
             f'CF_INFERENCE_LEDGER=$HOME/dev/ledger/inference_ledger.jsonl && mkdir -p $HOME/dev/ledger && '
             f'(test -f studio/dist/index.html || npm --prefix studio run build) && python scripts/run_studio.py '
             f'2>&1 | tee -a $HOME/logs/dev/studio-{slot}.log')
    fc.ssh(f"tmux kill-session -t studio 2>/dev/null; tmux new-session -d -s studio {shlex.quote(inner)}", timeout=60, check=False)
    for _ in range(60):
        if fc.ssh("curl -fsS http://127.0.0.1:8000/api/version", timeout=30, check=False).returncode == 0:
            print(f"Studio ({slot}) is up on the VM at 127.0.0.1:8000 (not public). Run `tunnel` and open http://127.0.0.1:{LOCAL_PORT}")
            return
        time.sleep(3)
    raise SystemExit("Studio did not answer within 3 min; see ~/logs/dev/studio-*.log on the VM")


def cmd_tunnel(a) -> None:
    if TUNNEL_PID.exists():
        pid = int(TUNNEL_PID.read_text())
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        TUNNEL_PID.unlink()
        print("stopped previous tunnel", pid)
    if a.stop:
        return
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    p = subprocess.Popen(["ssh", "-F", SSH_CFG, "-N", "-o", "ExitOnForwardFailure=yes",
                          "-L", f"127.0.0.1:{LOCAL_PORT}:127.0.0.1:8000", fc.HOST],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    TUNNEL_PID.write_text(str(p.pid))
    print(f"tunnel pid {p.pid}: http://127.0.0.1:{LOCAL_PORT} -> VM 127.0.0.1:8000 (private; stop with `tunnel --stop`)")


def cmd_pull(a) -> None:
    slot = a.slot or default_slot(Path(a.tree).resolve())
    rel = a.path.strip("/")
    dest = ROOT / "artifacts" / "vm" / slot
    dest.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ssh", "-F", SSH_CFG, fc.HOST, f"cd $HOME/dev/{slot} && tar czf - {shlex.quote(rel)}"],
                       capture_output=True, timeout=1800)
    if r.returncode != 0:
        raise SystemExit(r.stderr.decode(errors="replace")[-1500:])
    with tarfile.open(fileobj=io.BytesIO(r.stdout), mode="r:gz") as t:
        t.extractall(dest, filter="data")
    print(f"pulled {slot}:{rel} -> {dest / rel}")


def cmd_bootstrap(_a) -> None:
    subprocess.run(["scp", "-F", SSH_CFG, str(HERE / "remote" / "dev_bootstrap.sh"), f"{fc.HOST}:dev_bootstrap.sh"], check=True)
    r = fc.ssh("chmod +x ~/dev_bootstrap.sh && ~/dev_bootstrap.sh", timeout=1800, check=False)
    print(r.stdout[-2000:], r.stderr[-1500:])
    env_local = ROOT / ".env"
    if env_local.exists():   # copied, never printed; readable only by the forge user
        subprocess.run(["scp", "-q", "-F", SSH_CFG, str(env_local), f"{fc.HOST}:dev/.env"], check=True)
        fc.ssh("chmod 600 ~/dev/.env", timeout=60)
        print(".env copied to ~/dev/.env (mode 600)")
    sys.exit(r.returncode)


def main() -> None:
    for s in (sys.stdout, sys.stderr):   # remote output contains UTF-8 (vitest check marks); never crash on cp1252
        getattr(s, "reconfigure")(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--tree", default=str(ROOT))
    common.add_argument("--slot")
    sp.add_parser("bootstrap")
    sp.add_parser("sync", parents=[common])
    e = sp.add_parser("exec", parents=[common]); e.add_argument("command"); e.add_argument("--heavy", action="store_true")
    e.add_argument("--timeout", type=int, default=1800); e.add_argument("--tail", type=int, default=60)
    t = sp.add_parser("test", parents=[common]); t.add_argument("kind", choices=[*TESTS, "all"])
    t.add_argument("--timeout", type=int, default=3000); t.add_argument("--tail", type=int, default=25)
    sv = sp.add_parser("serve", parents=[common]); sv.add_argument("--live", action="store_true")
    tu = sp.add_parser("tunnel"); tu.add_argument("--stop", action="store_true")
    p = sp.add_parser("pull", parents=[common]); p.add_argument("path", nargs="?", default="artifacts/forge")
    a = ap.parse_args()
    {"bootstrap": cmd_bootstrap, "sync": cmd_sync, "exec": cmd_exec, "test": cmd_test, "serve": cmd_serve,
     "tunnel": cmd_tunnel, "pull": cmd_pull}[a.cmd](a)


if __name__ == "__main__":
    main()
