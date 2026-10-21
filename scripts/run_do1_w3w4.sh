#!/usr/bin/env bash
# W3 (DO1-L4-rep) then W4 (DO1-X) on the main Nebius VM - owner authorization 2026-10-21 (docs/DO1_REPLICATION_PROTOCOL.md).
# Usage (on the VM, from the clean checkout of the approved commit): bash scripts/run_do1_w3w4.sh <40-hex commit> <out dir>
# W4 starts only if W3 exits 0. The VM is never powered off from here; the operator stops it through the API.
set -u
C="$1"; O="$2"
PY="$HOME/dev/venvs/hdb/bin/python"
ART="$HOME/dev/hdb/artifacts/hdb"; REC="$HOME/dev/runs/do1_w3w4_inputs/records"
APPROVAL="owner W3/W4 authorization 2026-10-21 (DO1-L4-rep cap 39644 + DO1-X cap 14416, main VM, 6 workers, <= \$1.50 incremental)"
mkdir -p "$O"
[ "$(git rev-parse HEAD)" = "$C" ] && [ -z "$(git status --porcelain)" ] || { echo "checkout is not the clean approved commit" > "$O/REFUSED"; exit 9; }
{ echo "head $(git rev-parse HEAD)"; echo "status [$(git status --porcelain)]"; "$PY" -c "import sys,platform,numpy,mujoco;print(platform.platform(),sys.version.split()[0],numpy.__version__,mujoco.__version__)"; } > "$O/checkout.log"
( while true; do echo "$(date -u +%FT%TZ) $(free -m | awk 'NR==2{print "used_mb=" $3, "avail_mb=" $7}')" >> "$O/mem_samples.log"; sleep 15; done ) &
MON=$!
date -u +"start W3 %FT%TZ" > "$O/timing.log"
/usr/bin/time -v -o "$O/time_v_w3.log" "$PY" -u scripts/do1_repair_ablation.py --phase DO1-L4-rep --execute \
  --approved-by "$APPROVAL" --harness-commit "$C" --max-rollouts 39644 --max-wall-s 7200 \
  --artifacts-root "$ART" --records-root "$REC" --workers 6 --out "$O/do1_l4_rep.jsonl" > "$O/do1_l4_rep.log" 2>&1
W3=$?; echo "$W3" > "$O/EXIT_W3"
date -u +"end W3 %FT%TZ rc=$W3" >> "$O/timing.log"
if [ "$W3" = "0" ]; then
  date -u +"start W4 %FT%TZ" >> "$O/timing.log"
  /usr/bin/time -v -o "$O/time_v_w4.log" "$PY" -u scripts/do1_repair_ablation.py --phase DO1-X --execute \
    --approved-by "$APPROVAL" --harness-commit "$C" --max-rollouts 14416 --max-wall-s 3600 \
    --artifacts-root "$ART" --records-root "$REC" --workers 6 --out "$O/do1_x.jsonl" > "$O/do1_x.log" 2>&1
  W4=$?; echo "$W4" > "$O/EXIT_W4"
  date -u +"end W4 %FT%TZ rc=$W4" >> "$O/timing.log"
else
  echo "W4 not started: W3 exited $W3 (protocol section 4)" > "$O/EXIT_W4"
fi
kill "$MON"
( cd "$O" && sha256sum $(ls | grep -v '^vm_sha256.txt$') > vm_sha256.txt )
echo done > "$O/FINISHED"
