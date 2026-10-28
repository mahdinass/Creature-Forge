#!/bin/bash
set -uo pipefail
source ~/dev/hdb/artifacts/e1/env.sh
G="python scripts/e1_repro_gate.py --records-dir artifacts/hdb --thresholds artifacts/hdb/thresholds_dev.json --stop-model experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json --n 4 --out artifacts/e1/gate_batch"
for a in A1 A0 K0n; do $G --arm $a --workers 7 > artifacts/e1/gate_batch/$a.log 2>&1 & done
wait
$G --compare > artifacts/e1/gate_batch/compare.log 2>&1
echo GATE_DONE >> artifacts/e1/gate_batch/compare.log
