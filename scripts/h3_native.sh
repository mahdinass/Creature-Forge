#!/usr/bin/env bash
# H3 approved supervisor; existing root API timer and independent laptop watchdog.
set -Eeuo pipefail
cd /home/forge/dev/h3-codex
OUT=artifacts/h3_pilot_v1
PY=/home/forge/dev/venvs/hdb/bin/python
AUTH=/home/forge/h3_authorization.json
PLAN=experiments/causal_engineer/dev/h3/plan.json
pids=(); KILLER=
finish() {
 rc=$?; trap - EXIT TERM INT; set +e
 [[ -z "$KILLER" ]] || kill -TERM -- "-$KILLER" 2>/dev/null
 for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null; done
 printf '{"exit_code":%s,"end_epoch":%s}\n' "$rc" "$(date +%s)" > "$OUT/finish.json"
 [[ ! -f /home/forge/h3_native.log ]] || cp /home/forge/h3_native.log "$OUT/supervisor_snapshot.log"
 "$PY" scripts/r0_integrity.py archive --root "$OUT" > "$OUT/archive.log" 2>&1
 # Bounded retrieval grace; lost clients cannot leave paid compute running.
 for _ in $(seq 1 60); do [[ -f "$OUT/retrieval_ack" ]] && break; sleep 1; done
 date +%s | sudo tee /var/lib/forge/deadline >/dev/null
 sudo /usr/local/sbin/forge-selfstop
 exit "$rc"
}
mkdir -p artifacts
mkdir "$OUT"
trap finish EXIT
trap 'exit 124' TERM INT
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
[[ -x "$PY" && -z $(git status --porcelain --untracked-files=normal) ]]
sudo systemctl is-active --quiet forge-selfstop.timer
sudo test -x /usr/local/sbin/forge-selfstop
DEADLINE=$(cat /var/lib/forge/deadline)
(( DEADLINE > $(date +%s) + 600 ))
setsid bash -c 'sleep "$1"; kill -TERM "$2"' _ "$((DEADLINE-$(date +%s)-180))" "$$" & KILLER=$!
git rev-parse HEAD > "$OUT/source_commit.txt"
"$PY" -B -c 'import sys,json,numpy,mujoco;sys.path.insert(0,"scripts");import h3_run as h;p=json.load(open(h.STUDY/"plan.json"));h.check_plan(p);print(sys.executable,numpy.__version__,mujoco.__version__)' > "$OUT/source_validation.txt"
setsid "$PY" -B scripts/h3_run.py gate --execute --authorization "$AUTH" --plan "$PLAN" --out "$OUT" > "$OUT/gate.log" 2>&1 & pids=("$!"); wait "${pids[0]}"; pids=()
setsid "$PY" -B scripts/h3_run.py qualify --execute --authorization "$AUTH" --plan "$PLAN" --out "$OUT" --gate-receipt "$OUT/gate/result.json" > "$OUT/qualify.log" 2>&1 & pids=("$!"); wait "${pids[0]}"; pids=()
"$PY" - "$OUT" "$DEADLINE" > "$OUT/launch_cases.txt" <<'PY'
import json,sys,time
from pathlib import Path
root=Path(sys.argv[1]);q=json.load(open(root/'qualify/result.json'))
if not q['passed']:
 print('NO-GO: qualification yielded fewer than six eligible lineages per side',file=sys.stderr);sys.exit(20)
rate=max(.118528,q['wall_s']/max(1,q['equivalents_reserved']))
forecast=2*25836*rate*1.25+900
if time.time()+forecast>int(sys.argv[2])-180:
 print('NO-GO: complete study plus uncertainty/retrieval cannot fit remaining window',file=sys.stderr);sys.exit(21)
for key in sorted(sum(q['accepted'].values(),[])):print(key)
PY
mapfile -t cases < "$OUT/launch_cases.txt"
for start in 0 8; do
 pids=()
 for id in "${cases[@]:$start:8}"; do
  setsid "$PY" -B scripts/h3_run.py case --case "$id" --execute --authorization "$AUTH" --plan "$PLAN" --out "$OUT" --gate-receipt "$OUT/gate/result.json" --qualification "$OUT/qualify/result.json" > "$OUT/${id}.log" 2>&1 & pids+=("$!")
 done
 for pid in "${pids[@]}"; do wait "$pid"; done
 pids=()
done
"$PY" -B scripts/h3_analyze.py --plan "$PLAN" --campaign "$OUT" --out "$OUT/analysis.json"
