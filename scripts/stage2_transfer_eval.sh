#!/usr/bin/env bash
# Stage-2 transfer evaluation, LLM arms (phase 3; development evidence, docs/HAS_SCIENTIST.md "Development protocol").
# Run on the batch VM after the inference-ledger handover (main VM ledger copied in; no LLM calls on main meanwhile).
# Non-LLM arms (A1e, A2, A1e on compositions) were run earlier with the same instance selection.
#   bash scripts/stage2_transfer_eval.sh <part>     part: single | comp | lfo | corrupt | all
set -euo pipefail
cd "$(dirname "$0")/.."
export CREATURE_FORGE_ENABLE_LIVE=1 CF_INFERENCE_LEDGER="$HOME/dev/ledger/inference_ledger.jsonl"
export CF_HDB_WALKERS=artifacts/hdb/walkers_all.jsonl
C="python scripts/hdb_agent_run.py --split-file experiments/causal_engineer/dev/hdb/stage2_split.json --thresholds artifacts/hdb/thresholds_dev.json --stop-model experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json --which transfer --sample --sample-seed 20261019"
FAMS="pitch_sensor_bias payload_offset low_ground_friction short_feet feedback_gain_loss actuator_weakness one_side_weakness clock_fault heavy_torso"
MEM=artifacts/hdb/memory_v5.json; LFO=artifacts/hdb/memory_v5_lfo.json; BAD=artifacts/hdb/memory_v5_corrupt.json
LEARNED=artifacts/hdb/amortized_v1.json
mkdir -p artifacts/hdb/logs
part=${1:-all}
W=${W:-2}   # pool workers per session (1 on the 8-vCPU main VM)
launch() { tmux new -d -s "$1" "$2 > artifacts/hdb/logs/$1.log 2>&1"; }
if [[ $part == single || $part == all ]]; then
  for f in $FAMS; do
    launch "T3_$f" "$C --arm A3 --families $f --limit 4 --workers $W --out artifacts/hdb/s2_transfer_A3_$f.jsonl"
    launch "T4_$f" "$C --arm A4 --memory $MEM --learned $LEARNED --families $f --limit 4 --workers $W --out artifacts/hdb/s2_transfer_A4_$f.jsonl"
  done
fi
if [[ $part == comp || $part == all ]]; then
  for k in 0 1 2 3 4 5 6 7; do
    launch "TC3_$k" "$C --arm A3 --devcomp --limit 16 --shard $k/8 --workers $W --out artifacts/hdb/s2_transfer_devcomp_A3_$k.jsonl"
    launch "TC4_$k" "$C --arm A4 --memory $MEM --learned $LEARNED --devcomp --limit 16 --shard $k/8 --workers $W --out artifacts/hdb/s2_transfer_devcomp_A4_$k.jsonl"
  done
fi
if [[ $part == lfo || $part == all ]]; then
  # leave-family-out memory (actuator_weakness and pitch_sensor_bias excluded by a hash rule) on those families' instances
  for f in actuator_weakness pitch_sensor_bias; do
    launch "TL_$f" "$C --arm A4lfo --memory $LFO --learned $LEARNED --families $f --limit 4 --workers $W --out artifacts/hdb/s2_transfer_A4lfo_$f.jsonl"
  done
fi
if [[ $part == corrupt || $part == all ]]; then
  # corrupted-dossier probe on the non-friction families (the probe's false mechanism is low friction)
  python scripts/hdb_memory_corrupt.py --memory $MEM --out $BAD
  for f in payload_offset clock_fault heavy_torso one_side_weakness; do
    launch "TX_$f" "$C --arm A4bad --memory $BAD --learned $LEARNED --families $f --limit 3 --workers $W --out artifacts/hdb/s2_transfer_A4bad_$f.jsonl"
  done
fi
tmux ls
