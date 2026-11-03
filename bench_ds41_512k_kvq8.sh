#!/bin/bash
set -u
exec >> /data/bench-results/bench-ds41-512k-kvq8.log 2>&1
X=/data/Xolotl
echo "=== $(date -Is) ds41 512K kv-q8 start ==="
systemctl --user stop ds41-kvq8-bench >/dev/null 2>&1; fuser -k -n tcp 20084 >/dev/null 2>&1; sleep 4
systemd-run --user --unit ds41-kvq8-bench --collect \
  --property=WorkingDirectory=$X \
  --property=Environment=CUDA_HOME=/data/cuda-13.1/root/usr/local/cuda-13.1 \
  --property=Environment=PATH=/data/cuda-13.1/root/usr/local/cuda-13.1/bin:/usr/local/bin:/usr/bin:/bin \
  --property=StandardOutput=append:$X/ds41-512k-kvq8-engine.log \
  --property=StandardError=append:$X/ds41-512k-kvq8-engine.log \
  -- $X/.venv/bin/python $X/tools/v41/serve/serve_ds41.py --engine strata --config $X/ds41-v4-512k-130-kvq8.json --host 0.0.0.0 --port 20084
for i in $(seq 1 300); do curl -s -m 3 http://127.0.0.1:20084/health 2>/dev/null | grep -q '"loaded": true' && break; sleep 5; done
grep -E 'tier:|VRAM ready seed|kv:' $X/ds41-512k-kvq8-engine.log | tail -3
M=$(curl -s -m 10 http://127.0.0.1:20084/v1/models | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')
echo "model id: $M"
BENCH_MODEL="$M" BENCH_PROC=ds41_generate python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20084 390000 /data/bench-results/ds41_512k_arena130_kvq8.json
grep -E 'prompt phases' $X/ds41-512k-kvq8-engine.log | tail -1
systemctl --user stop ds41-kvq8-bench >/dev/null 2>&1
echo "=== $(date -Is) done ==="
