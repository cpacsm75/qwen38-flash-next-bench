#!/bin/bash
# 딥시크 256K(ctx 262144, arena 130): BF16 KV vs --kv-q8 — VRAM expert 상주가 오르는지
set -u
exec >> /data/bench-results/bench-ds41-kvq8.log 2>&1
X=/data/Xolotl
echo "=== $(date -Is) ds41 256K KV A/B start (power $(nvidia-smi --query-gpu=power.limit --format=csv,noheader)) ==="

run_arm() {  # $1 = tag
  tag="$1"
  systemctl --user stop ds41-kv-bench >/dev/null 2>&1
  fuser -k -n tcp 20084 >/dev/null 2>&1; sleep 4
  systemd-run --user --unit ds41-kv-bench --collect \
    --property=WorkingDirectory=$X \
    --property=Environment=CUDA_HOME=/data/cuda-13.1/root/usr/local/cuda-13.1 \
    --property=Environment=PATH=/data/cuda-13.1/root/usr/local/cuda-13.1/bin:/usr/local/bin:/usr/bin:/bin \
    --property=StandardOutput=append:$X/ds41-256k-${tag}-engine.log \
    --property=StandardError=append:$X/ds41-256k-${tag}-engine.log \
    -- $X/.venv/bin/python $X/tools/v41/serve/serve_ds41.py --engine strata \
       --config $X/ds41-v4-256k-${tag}.json --host 0.0.0.0 --port 20084
  for i in $(seq 1 300); do curl -s -m 3 http://127.0.0.1:20084/health 2>/dev/null | grep -q '"loaded": true' && break; sleep 5; done
  echo "--- arm $tag health ---"; curl -s -m 5 http://127.0.0.1:20084/health; echo
  echo "--- arm $tag tier/VRAM ---"
  grep -E 'tier:|VRAM ready seed|first batch' $X/ds41-256k-${tag}-engine.log | tail -3
  M=$(curl -s -m 10 http://127.0.0.1:20084/v1/models | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')
  echo "model id: $M"
  BENCH_MODEL="$M" BENCH_PROC=ds41_generate python3 /data/bench-results/bench_infernix.py \
    http://127.0.0.1:20084 200000 /data/bench-results/ds41_256k_${tag}.json
  grep -E 'prompt phases' $X/ds41-256k-${tag}-engine.log | tail -1
  systemctl --user stop ds41-kv-bench >/dev/null 2>&1; sleep 5
}

for T in bf16 kvq8; do
  echo "=== arm: $T ==="
  run_arm "$T"
done
echo "=== $(date -Is) ds41 256K KV A/B done ==="
