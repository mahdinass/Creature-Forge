#!/usr/bin/env bash
# DS-1 launcher (docs/DS1_PROTOCOL.md, amendment 1). Detached tmux sessions with checkpointed outputs (resume = rerun).
#   bash scripts/ds1_launch.sh <part> [stop-map]   part: pilot | stream | eval-llm (main VM) | eval-nonllm (batch VM)
set -euo pipefail
cd "$(dirname "$0")/.."
D=experiments/causal_engineer/dev/hdb/ds1
MAP=${2:-$D/stopmap_dev_v2.json}
OUT=artifacts/hdb/ds1
mkdir -p $OUT artifacts/hdb/logs
ENV="env PATH=$HOME/dev/venvs/${CF_SLOT:-hdb}/bin:$PATH PYTHONUNBUFFERED=1 CF_HDB_WALKERS=artifacts/hdb/walkers_all.jsonl"
LIVE="$ENV CREATURE_FORGE_ENABLE_LIVE=1 CF_INFERENCE_LEDGER=$HOME/dev/ledger/inference_ledger.jsonl"
B="python scripts/hdb_agent_run.py --split-file experiments/causal_engineer/dev/hdb/stage2_split.json --thresholds artifacts/hdb/thresholds_dev.json --mults 1.0,1.3,1.7"
C="$B --stop-model $MAP --v6 $D/engine_v6_settings.json"
C5="$B --stop-model experiments/causal_engineer/dev/hdb/stopmap_dev_v1.json"   # v5 reference: exactly the Stage-2 A1e configuration
X="--cases $D/cases_init.json --memory $D/memory_ds1_init.json"
ids() { python3 -c "import json,sys; d=json.load(open('$1')); print(','.join(d['$2'][int('$3'):int('$4')]))"; }
launch() { tmux new -d -s "$1" "$2 > artifacts/hdb/logs/$1.log 2>&1"; }
part=$1
if [[ $part == pilot || $part == pilot-single ]]; then
  P=$D/ds1_pilot_instances.json
  S3=$(ids $P single 0 3); S2=$(ids $P single 0 2); S1=$(ids $P single 0 1); CP=$(ids $P comp 0 1)
fi
if [[ $part == pilot-single ]]; then
  launch P_A1e6_s "$ENV $C --arm A1e6 --which init --only $S3 --workers 1 --out $OUT/pilot_A1e6.jsonl"
  launch P_A3v5_s "$LIVE $C --arm A3v5 --which init --only $S2 --workers 1 --out $OUT/pilot_A3v5.jsonl"
  launch P_A4x_s "$LIVE $C --arm A4x $X --which init --only $S2 --workers 1 --out $OUT/pilot_A4x.jsonl"
  launch P_eq_s "$ENV $C --arm A4x $X --no-scientist --which init --only $S1 --workers 1 --out $OUT/pilot_A4x_noscientist.jsonl"
fi
if [[ $part == pilot ]]; then
  launch P_A1e6_s "$ENV $C --arm A1e6 --which init --only $S3 --workers 1 --out $OUT/pilot_A1e6.jsonl"
  launch P_A1e6_c "$ENV $C --arm A1e6 --which init --devcomp --only $CP --workers 1 --out $OUT/pilot_A1e6.c.jsonl"
  launch P_A3v5_s "$LIVE $C --arm A3v5 --which init --only $S2 --workers 1 --out $OUT/pilot_A3v5.jsonl"
  launch P_A3v5_c "$LIVE $C --arm A3v5 --which init --devcomp --only $CP --workers 1 --out $OUT/pilot_A3v5.c.jsonl"
  launch P_A4x_s "$LIVE $C --arm A4x $X --which init --only $S2 --workers 1 --out $OUT/pilot_A4x.jsonl"
  launch P_A4x_c "$LIVE $C --arm A4x $X --which init --devcomp --only $CP --workers 1 --out $OUT/pilot_A4x.c.jsonl"
  launch P_eq_s "$ENV $C --arm A4x $X --no-scientist --which init --only $S1 --workers 1 --out $OUT/pilot_A4x_noscientist.jsonl"
fi
if [[ $part == stream ]]; then
  launch STREAM "$LIVE python scripts/ds1_stream.py --instances $D/ds1_stream_instances.json --cases-init $D/cases_init.json --memory $D/memory_ds1_init.json --v6 $D/engine_v6_settings.json --stop-model $MAP --rounds 4 --per-round 5 --out-dir $OUT/stream"
fi
if [[ $part == eval-llm || $part == eval-nonllm ]]; then
  E=$D/ds1_eval_instances.json
  MFINAL=$OUT/stream/cases_upd_r4.json      # M_final (protocol §6): init store + the updating stream's outcomes
  if [[ $part == eval-llm ]]; then ARMS=${LLM_ARMS:-"A3v5 A4x"}; PRE=$LIVE; W=1; else ARMS=${NONLLM_ARMS:-"A1e A1e6"}; PRE=$ENV; W=${W:-6}; fi
  for arm in $ARMS; do
    EXTRA=""
    if [[ $arm == A4x ]]; then
      [[ -s $MFINAL ]] || { echo "A4x dev-eval needs M_final ($MFINAL): finish the stream first"; exit 1; }
      EXTRA="--cases $MFINAL --memory $D/memory_ds1_init.json"
    fi
    CC=$C; [[ $arm == A1e ]] && CC=$C5
    for k in 0 1 2 3 4 5; do
      launch "E_${arm}_s$k" "$PRE $CC --arm $arm $EXTRA --which transfer --only $(ids $E single $((k*5)) $((k*5+5))) --workers $W --out $OUT/eval_${arm}_s$k.jsonl"
    done
    launch "E_${arm}_c" "$PRE $CC --arm $arm $EXTRA --which transfer --devcomp --only $(ids $E comp 0 6) --workers $W --out $OUT/eval_${arm}_c.jsonl"
  done
fi
tmux ls
