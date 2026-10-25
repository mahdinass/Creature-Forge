#!/usr/bin/env bash
# VM-only, from the committed isolated R0 checkout. Existing SA self-stop only.
# Args: output-dir, absolute deadline epoch. No credentials enter this script.
set -Eeuo pipefail
OUT=${1:-}
DEADLINE=${2:-}
ROOT=$(pwd -P)
PY=${R0_PYTHON:-}
STUDY=experiments/causal_engineer/dev/repair_strategy_r0
pids=()
KILLER=
EVIDENCE_READY=
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

finish() {
  rc=$?
  trap - EXIT TERM INT
  set +e
  [[ -z "$KILLER" ]] || kill -TERM -- "-$KILLER" 2>/dev/null
  for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null; done
  for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null; done
  if [[ -n "$EVIDENCE_READY" ]]; then
    printf '{"exit_code":%s,"end_epoch":%s}\n' "$rc" "$(date +%s)" > "$OUT/finish_$(date +%s)_$$.json"
    # Preserve completed/invalid evidence on every exit, including partial runs.
    "$PY" scripts/r0_integrity.py archive --root "$OUT" > "$OUT/archive.log" 2>&1
  fi
  # API stop is the billing stop. Existing root SA timer remains independent.
  date +%s | sudo tee /var/lib/forge/deadline >/dev/null
  sudo /usr/local/sbin/forge-selfstop
  exit "$rc"
}
trap finish EXIT
trap 'exit 124' TERM INT

[[ -n "$OUT" && $(realpath -m "$OUT") == "$ROOT/artifacts/"* ]] || exit 79
[[ -n "$PY" && -x "$PY" ]] || exit 78
mkdir -p "$OUT"
EVIDENCE_READY=1
[[ "$DEADLINE" =~ ^[0-9]+$ ]] || exit 80
(( DEADLINE > $(date +%s) + 300 )) || exit 81
[[ $(cat /var/lib/forge/deadline) == "$DEADLINE" ]] || exit 82
sudo systemctl is-active --quiet forge-selfstop.timer || exit 83
sudo test -x /usr/local/sbin/forge-selfstop || exit 84
sudo test -s /var/lib/forge/instance_id || exit 85
[[ $(getconf _NPROCESSORS_ONLN) -ge 48 ]] || exit 86
[[ -z $(git status --porcelain --untracked-files=normal) ]] || exit 87

# A deadline killer supplements the independent five-minute API-stop timer.
setsid bash -c 'sleep "$1"; kill -TERM "$2"' _ "$((DEADLINE - $(date +%s) - 180))" "$$" &
KILLER=$!
for k in 0 1 2 3 4 5 6 7; do
  setsid "$PY" scripts/r0_experiment.py run --study "$STUDY" --out "$OUT" \
    --shard "$k/8" --workers 6 > "$OUT/shard_$k.log" 2>&1 &
  pids+=("$!")
done
while (( ${#pids[@]} )); do
  # A remote two-second sweep also handles children that exited before a wait.
  # Any failed shard triggers the EXIT handler, which terminates the others.
  next=()
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then next+=("$pid"); else wait "$pid" || exit 88; fi
  done
  pids=("${next[@]}")
  (( ${#pids[@]} == 0 )) || sleep 2
done
kill -TERM -- "-$KILLER" 2>/dev/null || true
"$PY" scripts/r0_experiment.py analyze --study "$STUDY" --out "$OUT" > "$OUT/analysis_stdout.json"
"$PY" scripts/r0_integrity.py audit --root "$OUT" --study "$STUDY" > "$OUT/integrity.json"
touch "$OUT/COMPLETE"
