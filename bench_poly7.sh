#!/bin/bash
# PolyStrata v0.1.45-poly.7 재벤치 (Q5_K_XL, poly.6과 동일 조건: 1M ctx, int8 KV, MTP on)
set -u
exec >> /data/bench-results/bench-poly7.log 2>&1
echo "=== $(date -Is) poly7 bench start ==="
cd /data/PolyStrata || exit 1
M=qwen3.8-flash-next-unsloth-ud-q5_k_xl

curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"poly-q5"}' > /dev/null
for i in $(seq 1 240); do
  curl -s -m 2 http://127.0.0.1:20080/health | grep -q '"loaded": true' && break
  sleep 2
done
echo "--- health ---"; curl -s -m 5 http://127.0.0.1:20080/health; echo
echo "--- vram/ram after load ---"; nvidia-smi --query-gpu=memory.used --format=csv,noheader; free -g | sed -n 2p

for T in 64 200000 400000 750000; do
  case $T in
    64)     TAG=short ;;
    200000) TAG=256k ;;
    400000) TAG=512k ;;
    750000) TAG=1m ;;
  esac
  echo "--- bench $TAG ($T) ---"
  .venv/bin/python polystrata.py benchmark --model "$M" --port 20080 --prompt-tokens "$T" \
    --json "/data/bench-results/poly7_q5_${TAG}.json"
done

echo "--- stop ---"
curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"poly-q5"}'
echo
echo "=== $(date -Is) poly7 bench done ==="
