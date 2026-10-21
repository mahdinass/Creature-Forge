#!/usr/bin/env bash
# DO-1 demo export on the main VM: the recorded environment of DO1-L4-r0.
# Owner approval 2026-10-21 (W1a recovery): exporter commit dd5d5ea, <= 2 workers, about 240 rollout-eq plus setup checks.
# Order: clean-checkout and HEAD check -> no-physics tests -> exact smoke test -> (only if the smoke test passed) full
# export -> SHA-256. Every stage has its own hard timeout; any failure stops the script.
set -u
C=dd5d5ea39b20e603f993c4a7b1699e6b4e879ab5
S="$HOME/dev/do1-demo-export"
O="$HOME/dev/runs/do1_demo_export_2026-10-21"
PY="$HOME/dev/venvs/hdb/bin/python"
A="$HOME/dev/hdb/artifacts/hdb"
APPROVAL="owner W1a recovery authorization 2026-10-21 (exporter dd5d5ea, main VM, <=2 workers, ~240 rollout-eq + setup)"
mkdir -p "$O" && cd "$S" || exit 9
fail() { echo "$1" > "$O/EXIT"; date -u +"end %FT%TZ" >> "$O/timing.log"; kill "$MON" 2>/dev/null; exit 1; }
( while true; do echo "$(date -u +%FT%TZ) $(free -m | awk 'NR==2{print "used_mb=" $3, "avail_mb=" $7}')" >> "$O/mem_samples.log"; sleep 15; done ) &
MON=$!
date -u +"start %FT%TZ" > "$O/timing.log"
{ echo "head $(git rev-parse HEAD)"; echo "status [$(git status --porcelain)]"; "$PY" -c "import sys,platform,numpy,mujoco;print(platform.platform(),sys.version.split()[0],numpy.__version__,mujoco.__version__)"; } > "$O/checkout.log" 2>&1
[ "$(git rev-parse HEAD)" = "$C" ] || fail "HEAD is not $C"
[ -z "$(git status --porcelain)" ] || fail "checkout not clean"
timeout 600 "$PY" -m unittest tests.test_frozen_paths tests.test_frozen_records tests.test_redactions tests.test_do1_demo_export \
  > "$O/tests.log" 2>&1 || fail "no-physics tests failed ($?)"
date -u +"tests_ok %FT%TZ" >> "$O/timing.log"
timeout 900 "$PY" -u scripts/do1_demo_export.py --smoke --approved-by "$APPROVAL" --artifacts-root "$A" --workers 2 \
  > "$O/smoke.log" 2>&1 || fail "smoke test failed ($?)"
date -u +"smoke_ok %FT%TZ" >> "$O/timing.log"
timeout 1800 /usr/bin/time -v -o "$O/time_v.log" "$PY" -u scripts/do1_demo_export.py --execute --approved-by "$APPROVAL" \
  --artifacts-root "$A" --workers 2 --out "$O/demo" > "$O/export.log" 2>&1 || fail "export failed ($?)"
(cd "$O" && find demo -type f | sort | xargs sha256sum -b > vm_sha256.txt && (cd demo && sha256sum -c --quiet SHA256SUMS)) \
  || fail "sha256 step failed"
echo 0 > "$O/EXIT"
date -u +"end %FT%TZ" >> "$O/timing.log"
kill "$MON"
