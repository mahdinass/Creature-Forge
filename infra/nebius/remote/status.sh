#!/bin/bash
# Runs ON the VM. One-shot health + progress report.
echo "time: $(date -u +%FT%TZ)  uptime: $(uptime -p)"
echo "deadline: $(date -u -d @$(cat /var/lib/forge/deadline) +%FT%TZ)"
free -m | awk 'NR==2{printf "mem_total_mb=%s avail_mb=%s\n",$2,$7}'
echo "load: $(cut -d' ' -f1-3 /proc/loadavg)  disk: $(df -h / | awk 'NR==2{print $3"/"$2" ("$5")"}')"
echo "experiment processes: $(pgrep -fc '[s]cripts/run_r[0-9a-z_]*.py' || true)"
L=$(ls -t $HOME/creature-forge/experiments/phase2a_r*/results/ledger.jsonl 2>/dev/null | head -1 || true)
if [ -n "$L" ] && [ -f "$L" ]; then echo "ledger lines: $(wc -l < "$L")"; tail -n 2 "$L" | cut -c1-300; else echo "ledger: none yet"; fi
F=$(ls -t $HOME/logs/run_r*.log 2>/dev/null | head -1 || true)
[ -n "$F" ] && { echo "--- $F"; tail -n 8 "$F"; } || true
