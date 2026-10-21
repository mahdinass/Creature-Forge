#!/usr/bin/env bash
# DO-1 exploratory pilot DO1-L4-r0 - single authorized execution (owner approval 2026-10-21, commit e9d2379)
O="$HOME/dev/runs/do1_l4_r0_pilot_2026-10-21"
cd "$HOME/dev/do1-l4-r0" || exit 9
( while true; do echo "$(date -u +%FT%TZ) $(free -m | awk 'NR==2{print "used_mb=" $3, "avail_mb=" $7}')" >> "$O/mem_samples.log"; sleep 15; done ) &
MON=$!
date -u +"start %FT%TZ" > "$O/timing.log"
/usr/bin/time -v -o "$O/time_v.log" "$HOME/dev/venvs/hdb/bin/python" -u scripts/do1_repair_ablation.py --phase DO1-L4-r0 --execute \
  --approved-by "owner DO1-L4-r0 pilot authorization 2026-10-21 (commit e9d2379, main VM, <=7208, 6 workers)" \
  --harness-commit e9d2379def2546cedcc9ce5c3cc2aa22b9746392 --max-rollouts 7208 --max-wall-s 3000 \
  --artifacts-root "$HOME/dev/hdb/artifacts/hdb" --records-root "$HOME/dev/runs/fa1c_a1_inputs/records" --workers 6 \
  --out "$O/do1_l4_r0.jsonl" > "$O/do1_l4_r0.log" 2>&1
echo $? > "$O/EXIT"
date -u +"end %FT%TZ" >> "$O/timing.log"
kill "$MON"
