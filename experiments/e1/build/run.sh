#!/bin/bash
set -uo pipefail
source ~/dev/hdb/artifacts/e1/env.sh
git rev-parse HEAD^{tree} > artifacts/e1/build/tree.txt
python scripts/e1_build.py --protocol experiments/e1/protocol.json --workers 7 --batch 28 --out-dir artifacts/e1/build > artifacts/e1/build/build.log 2>&1
echo "BUILD_EXIT $?" >> artifacts/e1/build/build.log
