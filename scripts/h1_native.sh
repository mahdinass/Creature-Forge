#!/usr/bin/env bash
# Native H1 supervisor. Existing root SA timer and independent Windows watchdog remain active.
set -Eeuo pipefail
cd /home/forge/dev/r0-codex
OUT=artifacts/h1_stage_a_v1
PY=/home/forge/dev/venvs/hdb/bin/python
pids=()
KILLER=
finish() {
 rc=$?; trap - EXIT TERM INT; set +e
 [[ -z "$KILLER" ]] || kill -TERM -- "-$KILLER" 2>/dev/null
 for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null; done
 printf '{"exit_code":%s,"end_epoch":%s}\n' "$rc" "$(date +%s)" > "$OUT/finish.json"
 "$PY" scripts/r0_integrity.py archive --root "$OUT" > "$OUT/archive.log" 2>&1
 date +%s | sudo tee /var/lib/forge/deadline >/dev/null
 sudo /usr/local/sbin/forge-selfstop
 exit "$rc"
}
mkdir "$OUT"
trap finish EXIT
trap 'exit 124' TERM INT
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
[[ -z $(git status --porcelain --untracked-files=normal) ]]
sudo systemctl is-active --quiet forge-selfstop.timer
sudo test -x /usr/local/sbin/forge-selfstop
[[ $(getconf _NPROCESSORS_ONLN) -ge 48 ]]
DEADLINE=$(cat /var/lib/forge/deadline)
(( DEADLINE > $(date +%s) + 600 ))
setsid bash -c 'sleep "$1"; kill -TERM "$2"' _ "$((DEADLINE-$(date +%s)-180))" "$$" &
KILLER=$!
git rev-parse HEAD > "$OUT/source_commit.txt"
"$PY" -B -c 'import sys;sys.path.insert(0,"scripts");import h1_counterfactual as h;print(h.validate_sources(h.STUDY))' > "$OUT/source_validation.txt"
"$PY" -B -m unittest discover -s tests -p test_h1.py -v > "$OUT/guard_tests.txt" 2>&1
for k in 0 1 2 3 4 5 6 7; do
 setsid "$PY" -B scripts/h1_counterfactual.py run --out "$OUT" --shard "$k/8" > "$OUT/shard_$k.log" 2>&1 &
 pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid"; done
"$PY" scripts/h1_counterfactual.py analyze --out "$OUT" --analysis-output "$OUT/analysis.json" > "$OUT/analysis_stdout.json"
"$PY" scripts/h1_counterfactual.py analyze --out "$OUT" --analysis-output "$OUT/analysis_repeat.json" > "$OUT/analysis_repeat_stdout.json"
cmp "$OUT/analysis.json" "$OUT/analysis_repeat.json"
"$PY" scripts/h1_audit.py --out "$OUT" > "$OUT/independent_audit_stdout.txt"
