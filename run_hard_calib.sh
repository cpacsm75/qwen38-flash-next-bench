#!/bin/bash
# run_hard_calib.sh — 고난도 문항으로 팩별 정답률 캘리브레이션
# 각 팩마다 active.json 교체 → 서비스 재시작 → 엔진 id 확인 → eval_runner 실행
set -u
L=/data/cuda-13.1/root/usr/local/cuda-13.1/targets/x86_64-linux/lib
export LD_LIBRARY_PATH=$L
SET=/data/bench-results/eval_set_hard_2026-11-12.json
OUTDIR=/data/bench-results/hard
mkdir -p $OUTDIR
BASE=http://127.0.0.1:8080

wait_engine () {
  for i in $(seq 1 90); do
    id=$(curl -s -m 3 $BASE/v1/models | python3 -c "import sys,json
try:
    d=json.load(sys.stdin); print(d['data'][0]['id'])
except Exception: print('')" 2>/dev/null)
    if [ -n "$id" ]; then echo "$id"; return 0; fi
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
  /data/bench-results/eval_runner.py $BASE "$id" $OUTDIR/hard_$tag.json \
      --set $SET --reasoning-budget 1024 --max-tokens 8192
done
echo "===== done $(date +%H:%M:%S)"
