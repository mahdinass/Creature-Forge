#!/bin/bash
set -uo pipefail
cd ~/dev/hdb
export PATH=$HOME/dev/venvs/hdb/bin:$PATH PYTHONUNBUFFERED=1 CF_HDB_WALKERS=artifacts/hdb/walkers_all.jsonl OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
G="python scripts/e1_repro_gate.py --records-dir artifacts/hdb --thresholds artifacts/hdb/thresholds_dev.json --stop-model experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json --n 4 --out artifacts/e1/gate"
$G --arm A1 --workers 3 > artifacts/e1/gate/A1.log 2>&1 &
$G --arm A0 --workers 2 > artifacts/e1/gate/A0.log 2>&1 &
$G --arm K0n --workers 2 > artifacts/e1/gate/K0n.log 2>&1 &
wait
$G --compare > artifacts/e1/gate/compare.log 2>&1
echo GATE_DONE >> artifacts/e1/gate/compare.log
