#!/usr/bin/env bash
cd ~/dev/ta1-phase1b
( while true; do echo "$(date -u +%FT%TZ) used_mb=$(free -m | awk "/Mem:/{print \}") avail_mb=$(free -m | awk "/Mem:/{print \}")" >> /home/forge/dev/runs/fa1c_phase1b_2026-10-20/mem_samples.log; sleep 15; done ) &
MON=$!
date -u +"start %FT%TZ" > /home/forge/dev/runs/fa1c_phase1b_2026-10-20/timing.log
/usr/bin/time -v -o /home/forge/dev/runs/fa1c_phase1b_2026-10-20/time_v.log ~/dev/venvs/hdb/bin/python -u scripts/ta1_tool_access.py --phase 1B --execute --approved-by "owner FA-1C Phase 1B Nebius amendment 2026-10-20" --harness-commit 33a6e6f05aa0a0af968811156b44755f3c7381f9 --max-rollouts 7208 --artifacts-root ~/dev/hdb/artifacts/hdb --records-root ~/dev/runs/fa1c_phase1b_inputs/records --workers 6 --out /home/forge/dev/runs/fa1c_phase1b_2026-10-20/ta1_phase1b.jsonl > /home/forge/dev/runs/fa1c_phase1b_2026-10-20/ta1_phase1b.log 2>&1
echo $? > /home/forge/dev/runs/fa1c_phase1b_2026-10-20/EXIT
date -u +"end %FT%TZ" >> /home/forge/dev/runs/fa1c_phase1b_2026-10-20/timing.log
kill $MON
