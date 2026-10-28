#!/bin/bash
# E-1 arm launcher (operational; runs ON the batch VM in tmux, slot ~/dev/hdb at the registration tree).
# Preconditions checked here: G-R2 PASS, build complete (G-B), registration tree. Every shard uses --resume (registered
# recovery procedure: re-running this script after an interruption resumes every shard with identical inputs).
set -uo pipefail
source ~/dev/hdb/artifacts/e1/env.sh
E=artifacts/e1
REG_TREE=5fcdf4ef98b1a79f7d4115f4444454365c2cbc8b
[ "$(git rev-parse HEAD^{tree})" = "$REG_TREE" ] || { echo "tree is not the registration tree"; exit 2; }
grep -q '"gate_G_R": "PASS"' $E/gate_batch/gate_G_R.json || { echo "G-R2 has not passed"; exit 3; }
grep -q "BUILD_EXIT 0" $E/build/build.log || { echo "build not complete"; exit 4; }
mkdir -p $E/arms
SM=experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json
INST=$E/build/instances.jsonl
launch() {  # arm nshards workers
  for k in $(seq 0 $(( $2 - 1 ))); do
    python scripts/e1_run.py --arm $1 --instances $INST --stop-model $SM --workers $3 --shard $k/$2 --resume \
      --out $E/arms/$1_s$k.jsonl >> $E/arms/$1_s$k.log 2>&1 &
  done
}
launch A1 4 6
launch K0n 4 6
launch A0 2 6
wait
echo "ARMS_DONE $(date -u +%FT%TZ)" >> $E/arms/done.log
