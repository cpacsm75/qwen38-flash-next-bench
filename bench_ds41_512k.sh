#!/bin/bash
# 딥시크 V4.1 XQ: 512K 컨텍스트에서 arena 110 vs 130 A/B (단독 실행, 450W)
set -u
exec >> /data/bench-results/bench-ds41.log 2>&1
X=/data/Xolotl
echo "=== $(date -Is) ds41 512K arena A/B start (power $(nvidia-smi --query-gpu=power.limit --format=csv,noheader)) ==="

start_engine() {
  cfg="$1"
  systemctl --user stop ds41-512k-bench >/dev/null 2>&1
  fuser -k -n tcp 20084 >/dev/null 2>&1
  sleep 3
  systemd-run --user --unit ds41-512k-bench --collect \
    --property=WorkingDirectory=$X \
    --property=Environment=CUDA_HOME=/data/cuda-13.1/root/usr/local/cuda-13.1 \
    --property=Environment=PATH=/data/cuda-13.1/root/usr/local/cuda-13.1/bin:/usr/local/bin:/usr/bin:/bin \
    --property=StandardOutput=append:$X/ds41-512k-bench.log \
    --property=StandardError=append:$X/ds41-512k-bench.log \
    -- $X/.venv/bin/python $X/tools/v41/serve/serve_ds41.py --engine strata --config "$cfg" --host 0.0.0.0 --port 20084
  for i in $(seq 1 360); do
    curl -s -m 3 http://127.0.0.1:20084/health 2>/dev/null | grep -q '"loaded": true' && break
    sleep 5
  done
  curl -s -m 5 http://127.0.0.1:20084/health; echo
}

for A in 110 130; do
  echo "--- arena $A ---"
  start_engine "/data/Xolotl/ds41-v4-512k-${A}.json"
  M=$(curl -s -m 10 http://127.0.0.1:20084/v1/models | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)
  echo "model id: ${M:-?}"
  echo "--- arena line ---"; grep -iE 'tier:|arena \(|VRAM .* free' $X/ds41-512k-bench.log 2>/dev/null | tail -3
  BENCH_MODEL="${M:-deepseek-v4.1-flash-1017-xq-512k}" BENCH_PROC=ds41_generate \
    python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20084 390000 \
    "/data/bench-results/ds41_512k_arena${A}.json"
  grep -iE 'tier:|arena \(' $X/ds41-512k-bench.log 2>/dev/null | tail -2
done

systemctl --user stop ds41-512k-bench >/dev/null 2>&1
echo "=== $(date -Is) ds41 512K A/B done ==="
