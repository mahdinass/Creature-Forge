#!/bin/sh
# usage: fa1_trace_by.sh <instance_id> <arm>  (looks the raw record up in episode_index.csv)
ref=$(grep -F "$1" episode_index.csv | grep -F ",$2," | head -1 | awk -F, '{print $NF}' | tr -d '\r')
p=${ref%#L*}; n=${ref##*#L}
PYTHONDONTWRITEBYTECODE=1 ../Creature-Forge/.venv/Scripts/python.exe -I scripts/fa1_trace.py "$p" "$n"
