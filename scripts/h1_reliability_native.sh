#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/forge/dev/r0-codex
OUT=artifacts/h1_stage_b_v1
A=artifacts/h1_stage_a_v1
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
DEADLINE=$(cat /var/lib/forge/deadline)
(( DEADLINE > $(date +%s) + 600 ))
setsid bash -c 'sleep "$1"; kill -TERM "$2"' _ "$((DEADLINE-$(date +%s)-180))" "$$" &
KILLER=$!
git rev-parse HEAD > "$OUT/source_commit.txt"
"$PY" -B -c 'import sys;sys.path.insert(0,"scripts");import h1_reliability as b;b.source_check(b.STUDY)' > "$OUT/source_validation.txt"
"$PY" -B -m unittest discover -s tests -p test_h1_reliability.py -v > "$OUT/guard_tests.txt" 2>&1
for k in 0 1 2 3 4 5 6 7; do
 setsid "$PY" -B scripts/h1_reliability.py run --stage-a "$A" --out "$OUT" --shard "$k/8" > "$OUT/shard_$k.log" 2>&1 &
 pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid"; done
"$PY" scripts/h1_reliability.py analyze --stage-a "$A" --out "$OUT" --analysis-output "$OUT/analysis.json" > "$OUT/analysis_stdout.txt"
"$PY" scripts/h1_reliability.py analyze --stage-a "$A" --out "$OUT" --analysis-output "$OUT/analysis_repeat.json" > "$OUT/analysis_repeat_stdout.txt"
cmp "$OUT/analysis.json" "$OUT/analysis_repeat.json"
"$PY" scripts/h1_reliability_audit.py --stage-a "$A" --out "$OUT" > "$OUT/independent_audit_stdout.txt"
