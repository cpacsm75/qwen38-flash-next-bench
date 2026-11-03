#!/bin/bash
# Infernix Dense8 512K 단일 지점 (450W) — 모델 id를 엔진에서 직접 읽어 쓴다
set -u
exec >> /data/bench-results/bench-512k.log 2>&1
echo "=== $(date -Is) dense8 512K start ==="
curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"inf-dense8"}' > /dev/null
for i in $(seq 1 240); do
  curl -s -m 2 http://127.0.0.1:20082/health | grep -q '"status":"ok"' && break; sleep 2
done
echo "--- inf-dense8 health ---"; curl -s -m 5 http://127.0.0.1:20082/health; echo
M=$(curl -s -m 10 http://127.0.0.1:20082/v1/models | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')
echo "model id: $M"
BENCH_MODEL="$M" python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20082 390000 /data/bench-results/dense8_512k.json
curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"inf-dense8"}' > /dev/null
echo "=== $(date -Is) dense8 done ==="
