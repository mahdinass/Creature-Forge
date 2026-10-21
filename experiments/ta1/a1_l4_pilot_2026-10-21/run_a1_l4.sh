#!/usr/bin/env bash
# FA-1C Amendment A1 paired L4 pilot - single authorized execution (owner approval 2026-10-21)
O="$HOME/dev/runs/fa1c_a1_l4_pilot_2026-10-21"
cd "$HOME/dev/ta1-a1-l4" || exit 9
( while true; do echo "$(date -u +%FT%TZ) $(free -m | awk 'NR==2{print "used_mb=" $3, "avail_mb=" $7}')" >> "$O/mem_samples.log"; sleep 15; done ) &
MON=$!
date -u +"start %FT%TZ" > "$O/timing.log"
/usr/bin/time -v -o "$O/time_v.log" "$HOME/dev/venvs/hdb/bin/python" -u scripts/ta1_tool_access.py --phase 2a-L4-pilot --execute \
  --approved-by "owner Amendment A1 L4 pilot authorization 2026-10-21" \
  --harness-commit 86d0a2bcf8b32f74455739aa040d6e35d32f9e73 --max-rollouts 7208 \
  --artifacts-root "$HOME/dev/hdb/artifacts/hdb" --records-root "$HOME/dev/runs/fa1c_a1_inputs/records" --workers 6 \
  --out "$O/ta1_a1_l4.jsonl" > "$O/ta1_a1_l4.log" 2>&1
echo $? > "$O/EXIT"
date -u +"end %FT%TZ" >> "$O/timing.log"
kill "$MON"
