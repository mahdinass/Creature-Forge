#!/usr/bin/env bash
# W2: rewrite experiments/w2/SHA256SUMS over the served/derived files and pin its hash in creature_forge/studio/nemotron_api.py.
set -euo pipefail
cd "$(dirname "$0")/../experiments/w2"
files="gen0137_one_side_weakness/A1e.jsonl gen0137_one_side_weakness/A3.jsonl gen0137_one_side_weakness/A4.jsonl
gen0137_one_side_weakness/SOURCES.json gen0137_one_side_weakness/case.json gen0137_one_side_weakness/cross_instance.json studies.json"
: > SHA256SUMS
for f in $files; do printf '%s *%s\n' "$(sha256sum "$f" | cut -d' ' -f1)" "$f" >> SHA256SUMS; done
h=$(sha256sum SHA256SUMS | cut -d' ' -f1)
cd ../..
sed -i -E "s/^SUMS_SHA256 = \"[0-9a-f_A-Z]+\"/SUMS_SHA256 = \"$h\"/" creature_forge/studio/nemotron_api.py
grep -n '^SUMS_SHA256' creature_forge/studio/nemotron_api.py
