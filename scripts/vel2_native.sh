#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/forge/dev/r0-codex
OUT=artifacts/vel2_stage_a
PY=/home/forge/dev/venvs/hdb/bin/python
mkdir -p "$OUT"
DRIVER=
KILLER=
finish() {
 rc=$?
 trap - EXIT TERM INT
 set +e
 [[ -z "$KILLER" ]] || kill -TERM -- "-$KILLER" 2>/dev/null
 [[ -z "$DRIVER" ]] || kill -TERM -- "-$DRIVER" 2>/dev/null
 printf '{"exit_code":%s,"end_epoch":%s}\n' "$rc" "$(date +%s)" > "$OUT/finish.json"
 "$PY" scripts/r0_integrity.py archive --root "$OUT" > "$OUT/archive.log" 2>&1
 date +%s | sudo tee /var/lib/forge/deadline >/dev/null
 sudo /usr/local/sbin/forge-selfstop
 exit "$rc"
}
trap finish EXIT
trap 'exit 124' TERM INT
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
[[ -z $(git status --porcelain --untracked-files=normal) ]]
sudo systemctl is-active --quiet forge-selfstop.timer
sudo test -x /usr/local/sbin/forge-selfstop
DEADLINE=$(cat /var/lib/forge/deadline)
setsid bash -c 'sleep "$1"; kill -TERM "$2"' _ "$((DEADLINE-$(date +%s)-180))" "$$" &
KILLER=$!
git rev-parse HEAD > "$OUT/source_commit.txt"
cp experiments/causal_engineer/dev/vel2/stage_a*.json docs/VEL2_PROTOCOL.md "$OUT/"
"$PY" -B -m unittest discover -s tests -p test_vel2.py -v > "$OUT/guard_tests.txt" 2>&1
setsid "$PY" -B scripts/vel2_repeatability.py run --out "$OUT" > "$OUT/driver.log" 2>&1 &
DRIVER=$!
wait "$DRIVER"
"$PY" -B scripts/vel2_repeatability.py analyze --out "$OUT" --analysis-output "$OUT/analysis_repeat.json" > "$OUT/analysis_repeat_stdout.json"
cmp "$OUT/analysis.json" "$OUT/analysis_repeat.json"
