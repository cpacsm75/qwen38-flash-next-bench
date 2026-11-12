#!/bin/bash
# run_moj_calib.sh — 변호사시험 기출 80문항으로 팩별 캘리브레이션
set -u
export LD_LIBRARY_PATH=/data/cuda-13.1/root/usr/local/cuda-13.1/targets/x86_64-linux/lib
SET=/data/bench-results/moj/eval_set_moj_2026-11-12.json
OUTDIR=/data/bench-results/moj; mkdir -p $OUTDIR
BASE=http://127.0.0.1:8080
wait_engine () {
  for i in $(seq 1 90); do
    id=$(curl -s -m 3 $BASE/v1/models | python3 -c "import sys,json
try: print(json.load(sys.stdin)['data'][0]['id'])
except Exception: print('')" 2>/dev/null)
    [ -n "$id" ] && { echo "$id"; return 0; }
    sleep 5
  done
  return 1
}
for pair in "q6:basalt_q6.json" "q8:basalt_q8.json" "nvfp4:basalt_nvfp4.json" "unc:basalt_unc.json"; do
  tag=${pair%%:*}; cfg=${pair#*:}
  echo "===== $tag ($cfg) $(date +%H:%M:%S)"
  ln -sfn $cfg /data/basalt/active.json
  systemctl --user restart basalt.service
  id=$(wait_engine) || { echo "  engine failed"; continue; }
  echo "  model: $id"
  sleep 5
  /data/bench-results/eval_runner.py $BASE "$id" $OUTDIR/moj_$tag.json \
      --set $SET --reasoning-budget 1024 --max-tokens 8192
done
echo "===== done $(date +%H:%M:%S)"
