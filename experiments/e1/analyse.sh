#!/bin/bash
# E-1 analysis (operational wrapper; ON the VM or locally on pulled files). Concatenates shards per arm in shard order,
# runs the registered scripts/e1_analysis.py once, and writes SHA256SUMS over inputs and outputs.
set -euo pipefail
E=${1:-artifacts/e1}
mkdir -p $E/analysis
for a in A0 A1 K0n; do cat $(ls $E/arms/${a}_s*.jsonl | sort -V) > $E/arms/$a.jsonl; done
python scripts/e1_analysis.py --instances $E/build/instances.jsonl --arm A0=$E/arms/A0.jsonl --arm A1=$E/arms/A1.jsonl \
  --arm K0n=$E/arms/K0n.jsonl --out $E/analysis | tee $E/analysis/summary.txt
(cd $E && sha256sum build/instances.jsonl build/summary.json build/sample_log.jsonl arms/A0.jsonl arms/A1.jsonl arms/K0n.jsonl \
  analysis/e1_results.json > analysis/SHA256SUMS)
