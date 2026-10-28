#!/usr/bin/env bash
# W2 damaged-plant export on the main VM (recorded Stage 2 Linux environment).
# Owner authorization 2026-10-21: bounded W2 replay export, <= 2 workers, ~296 rollout-eq, <= $0.30 incremental, no inference.
# Order: snapshot tree check -> no-physics tests -> exact smoke test -> (only if it passed) full export -> SHA-256.
set -u
T=35d9360a9414fa53cae7dd8bee3b83f90c9f2b18        # tree of local commit c8816c6
S="$HOME/dev/w2-plant-export"
O="$HOME/dev/runs/w2_plant_export_2026-10-21_r2"
PY="$HOME/dev/venvs/hdb/bin/python"
A="$HOME/dev/hdb/artifacts/hdb"
APPROVAL="owner W2 authorization 2026-10-21 (bounded W2 replay export, commit c8816c6, main VM, <=2 workers, ~296 rollout-eq, <=\$0.30)"
mkdir -p "$O" && cd "$S" || exit 9
fail() { echo "$1" > "$O/EXIT"; date -u +"end %FT%TZ" >> "$O/timing.log"; kill "$MON" 2>/dev/null; exit 1; }
( while true; do echo "$(date -u +%FT%TZ) $(free -m | awk 'NR==2{print "used_mb=" $3, "avail_mb=" $7}')" >> "$O/mem_samples.log"; sleep 15; done ) &
MON=$!
date -u +"start %FT%TZ" > "$O/timing.log"
{ echo "head $(git rev-parse HEAD) tree $(git rev-parse HEAD^{tree})"; echo "status [$(git status --porcelain)]"; "$PY" -c "import sys,platform,numpy,mujoco;print(platform.platform(),sys.version.split()[0],numpy.__version__,mujoco.__version__)"; } > "$O/checkout.log" 2>&1
[ "$(git rev-parse HEAD^{tree})" = "$T" ] || fail "tree is not $T"
[ -z "$(git status --porcelain)" ] || fail "checkout not clean"
timeout 600 "$PY" -m unittest tests.test_frozen_paths tests.test_frozen_records tests.test_evidence_tracked tests.test_w2_damaged_plant_export \
  > "$O/tests.log" 2>&1 || fail "no-physics tests failed ($?)"
date -u +"tests_ok %FT%TZ" >> "$O/timing.log"
timeout 900 "$PY" -u scripts/w2_damaged_plant_export.py --smoke --approved-by "$APPROVAL" --artifacts-root "$A" --workers 2 \
  > "$O/smoke.log" 2>&1 || fail "smoke test failed ($?)"
date -u +"smoke_ok %FT%TZ" >> "$O/timing.log"
timeout 1800 /usr/bin/time -v -o "$O/time_v.log" "$PY" -u scripts/w2_damaged_plant_export.py --execute --approved-by "$APPROVAL" \
  --artifacts-root "$A" --workers 2 --out "$O/plant_replays" > "$O/export.log" 2>&1 || fail "export failed ($?)"
(cd "$O" && find plant_replays -type f | sort | xargs sha256sum -b > vm_sha256.txt && (cd plant_replays && sha256sum -c --quiet SHA256SUMS)) \
  || fail "sha256 step failed"
echo 0 > "$O/EXIT"
date -u +"end %FT%TZ" >> "$O/timing.log"
kill "$MON"
