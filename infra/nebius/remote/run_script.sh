#!/bin/bash
# Runs ON the VM. Launch one experiment stage detached with a log; never blocks the SSH session.
#   run_script.sh <script-name> [args...]     e.g.  run_script.sh run_r2.py train --arm S --rep 1
# OS-level timeout of 58 min on top of the registered 60-minute cumulative active-time limit.
set -euo pipefail
cd "$HOME/creature-forge"
S=$1; shift
TS=$(date -u +%Y%m%dT%H%M%SZ)
TAG=$(echo "${S%.py} $*" | tr ' ' '_' | tr -cd 'A-Za-z0-9_.-')
LOG=$HOME/logs/${TAG}_$TS.log
pgrep -f "[s]cripts/run_r[0-9].py" >/dev/null && { echo "an experiment stage is already running"; exit 4; }
nohup setsid timeout 3500 "$HOME/venvs/creature-forge/bin/python" "scripts/$S" "$@" > "$LOG" 2>&1 &
echo "$LOG pid=$!"
