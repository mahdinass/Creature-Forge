#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/forge/dev/r0-codex
OUT=${DI1_OUT:-artifacts/di1_pilot_v1}
PY=/home/forge/dev/venvs/hdb/bin/python
mkdir -p "$OUT"
DEADLINE=$(cat /var/lib/forge/deadline)
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
setsid bash -c 'sleep "$1"; kill -TERM "$2"' _ "$((DEADLINE-$(date +%s)-180))" "$$" &
KILLER=$!
date -u > "$OUT/start.txt"
git rev-parse HEAD > "$OUT/source_commit.txt"
cp experiments/causal_engineer/dev/di1/pilot_config.json experiments/causal_engineer/dev/di1/stopmap_dev_v1.json docs/DI1_PROTOCOL.md "$OUT/"
"$PY" -B -m unittest discover -s tests -p test_di1.py -v > "$OUT/guard_tests.txt" 2>&1
ARGS=()
if [[ ${DI1_MODE:-v1} == stop ]]; then
 ARGS=(--stop-pilot --prior artifacts/di1_pilot_v1)
 cp experiments/causal_engineer/dev/di1/PILOT_AMENDMENT_2.md "$OUT/"
 cp experiments/causal_engineer/dev/di1/pilot_v2_source_hashes.json "$OUT/"
 "$PY" -B scripts/di1_analyze.py --root artifacts/di1_pilot_v1 --out "$OUT/v1_analysis.json" > "$OUT/v1_analysis_stdout.json"
fi
setsid "$PY" -B scripts/di1_pilot_driver.py --out "$OUT" "${ARGS[@]}" > "$OUT/driver.log" 2>&1 &
DRIVER=$!
wait "$DRIVER"
if [[ ${DI1_MODE:-v1} == stop ]]; then
 "$PY" -B scripts/di1_generation_replay.py --root artifacts/di1_pilot_v1 --out "$OUT/generation_replay" > "$OUT/generation_replay.log"
 "$PY" -B scripts/di1_analyze.py --root "$OUT" --out "$OUT/analysis.json" --stop-amendment > "$OUT/analysis_stdout.json"
 "$PY" -B scripts/di1_analyze.py --root "$OUT" --out "$OUT/analysis.json" --stop-amendment > "$OUT/analysis_repeat_stdout.json"
fi
