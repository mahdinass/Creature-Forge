---
name: nebius-ops
description: Use whenever Creature Forge work needs the Nebius VM (tests, builds, browser flows, MuJoCo batches, Studio demo, live Nemotron calls) or touches cloud spend - starting/stopping the VM, syncing code, running remote commands, tunnels, deadlines, ledgers, shutdown.
---

# Nebius operations (Creature Forge)

Local Windows PC: edit files, git, ssh only — it has almost no free RAM. Everything heavy runs on the VM.

## Lifecycle (`infra/nebius/forge_cloud.py`, Nebius CLI runs inside WSL)
- `status`, `start` (refuses beyond the infra cap `SPEND_CAP_USD`, $96 since 2026-10-19 (phase-3 Stage 2: +$20 on a $75.48 ledger); sets a verified 6 h deadline), `extend --hours H`
  (cap-guarded), `stop`, `spend` (ledger total). Never `create`/`delete` without owner approval.
- Deadman timer on the VM powers off at the deadline; the Windows task `CreatureForgeNebiusWatchdog` stops it too.
- Stop the VM at the end of every work block or when idle > 30 min. Pull artifacts first.

## Development loop (`infra/nebius/forge_dev.py`)
- `sync --tree <worktree> --slot <name>`: mirrors the worktree incl. uncommitted changes (temp-index snapshot pushed
  to the VM's bare repo; never GitHub). Each slot: `~/dev/<slot>`, own venv, `core.autocrlf=false`.
- `test --tree . --slot s {py,fe,e2e,smoke,all}` (syncs first), `exec --slot s [--heavy] "<cmd>"`.
  Heavy commands share a VM-wide lock; ≤ 3 concurrent agents; MuJoCo pool ≤ 6 workers (`CF_WORKERS`).
- `serve --slot s` runs Studio on VM 127.0.0.1:8000 (tmux `studio`); `tunnel` maps it to local 127.0.0.1:8765.
  Never bind to 0.0.0.0 or open ports; ufw allows only SSH.
- `pull --slot s [path]` copies VM outputs to `artifacts/vm/<slot>/`.

## Secrets and spend
- `.env` lives only on Windows and at `~/dev/.env` (mode 600) on the VM. Never print, log, commit or pass keys as args.
- Inference ledger on the VM: `~/dev/ledger/inference_ledger.jsonl` (`CF_INFERENCE_LEDGER`); caps $40 / 8,000 (2026-10-18, owner-approved amendment)
  requests. Infra ledger: `infra/nebius/spend_ledger.jsonl` (git-ignored), cap `SPEND_CAP_USD` ($96, phase-3 Stage 2, 2026-10-19). Unattended CLI calls never open a browser; an auth failure writes `AUTH_BLOCKED` and stops all further attempts until the owner runs `forge_cloud.py login`.
- On any failure: record state in `docs/PROJECT_STATE.md`, stop the VM if idle, resume from the last commit.
