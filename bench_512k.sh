#!/bin/bash
# 450W(현행 유지) / 512K 단일 지점 재측정 (다른 컨텍스트 길이는 재지 않는다)
set -u
exec >> /data/bench-results/bench-512k.log 2>&1
echo "=== $(date -Is) 512K-only start (power $(nvidia-smi --query-gpu=power.limit --format=csv,noheader)) ==="

# --- 1) PolyStrata Q5 (poly.7 엔진) ---
cd /data/PolyStrata || exit 1
curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"poly-q5"}' > /dev/null
for i in $(seq 1 240); do
  curl -s -m 2 http://127.0.0.1:20080/health | grep -q '"loaded": true' && break; sleep 2
done
echo "--- poly-q5 health ---"; curl -s -m 5 http://127.0.0.1:20080/health; echo
.venv/bin/python polystrata.py benchmark --model qwen3.8-flash-next-unsloth-ud-q5_k_xl --port 20080 \
  --prompt-tokens 400000 --json /data/bench-results/poly7_q5_512k_500w.json
curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"poly-q5"}' > /dev/null
sleep 6

# --- 2) Infernix FP8 ---
curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"inf-fp8"}' > /dev/null
for i in $(seq 1 240); do
  curl -s -m 2 http://127.0.0.1:20082/health | grep -q '"status":"ok"' && break; sleep 2
done
echo "--- inf-fp8 health ---"; curl -s -m 5 http://127.0.0.1:20082/health; echo
curl -s -m 10 http://127.0.0.1:20082/v1/models | head -c 300; echo
python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20082 390000 /data/bench-results/fp8_512k_500w.json
curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"inf-fp8"}' > /dev/null
sleep 6

# --- 3) Infernix Dense8 ---
curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"inf-dense8"}' > /dev/null
for i in $(seq 1 240); do
  curl -s -m 2 http://127.0.0.1:20082/health | grep -q '"status":"ok"' && break; sleep 2
done
echo "--- inf-dense8 health ---"; curl -s -m 5 http://127.0.0.1:20082/health; echo
curl -s -m 10 http://127.0.0.1:20082/v1/models | head -c 300; echo
python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20082 390000 /data/bench-results/dense8_512k_500w.json
curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"inf-dense8"}' > /dev/null

echo "=== $(date -Is) 512K-only done ==="
