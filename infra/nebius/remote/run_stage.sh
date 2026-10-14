#!/bin/bash
# Runs ON the VM. Launch one R1 stage detached with a log; never blocks the SSH session.
#   run_stage.sh <stage> [--rep N]   (stage: pilot|train|validate|gate|select)
# OS-level timeout of 95 min on top of the registered 90-minute ledger limit.
set -euo pipefail
cd "$HOME/creature-forge"
TS=$(date -u +%Y%m%dT%H%M%SZ); LOG=$HOME/logs/r1_$1_$TS.log
pgrep -f "scripts/run_r1.py" >/dev/null && { echo "an R1 stage is already running"; exit 4; }
nohup setsid timeout 5700 "$HOME/venvs/creature-forge/bin/python" scripts/run_r1.py "$@" > "$LOG" 2>&1 &
echo "$LOG pid=$!"
