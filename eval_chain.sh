#!/bin/bash
# Q8_0 → Q5_K_XL 순차 평가 (FP8 평가가 끝난 뒤 실행). 끝나면 ds41-serve 재기동.
set -u
exec >> /data/bench-results/eval_chain.log 2>&1
LOG1=/data/bench-results/eval_fp8.json

echo "=== $(date -Is) chain start (waiting for FP8 eval) ==="
for i in $(seq 1 120); do [ -f "$LOG1" ] && break; sleep 15; done
[ -f "$LOG1" ] || { echo "FP8 결과 없음 — 중단"; exit 1; }
echo "FP8 결과 확인"

run_engine() {  # $1=8090 model key, $2=tag
  key="$1"; tag="$2"
  echo "--- $tag: start $key ---"
  systemctl --user stop ds41-serve >/dev/null 2>&1
  curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d "{\"model\":\"$key\"}" >/dev/null
  # 포트는 키에 따라 다르다: poly-q8=20081, poly-q5=20080
  port=$(python3 -c "
import json
e=json.load(open('/data/strata-web/engines.json'))['engines']
print(e['$key']['port'])")
  echo "  port=$port"
  for i in $(seq 1 180); do
    curl -s -m 3 "http://127.0.0.1:$port/health" | grep -q '"loaded": true' && break; sleep 5
  done
  curl -s -m 5 "http://127.0.0.1:$port/health"; echo
  M=$(curl -s -m 10 "http://127.0.0.1:$port/v1/models" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')
  echo "  model=$M"
  python3 /data/bench-results/eval_runner.py "http://127.0.0.1:$port" "$M" "/data/bench-results/eval_${tag}.json" --max-tokens 2048
  curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d "{\"model\":\"$key\"}" >/dev/null
  sleep 6
}

run_engine poly-q8 q8
run_engine poly-q5 q5

echo "--- ds41-serve 재기동 ---"
systemctl --user start ds41-serve
echo "=== $(date -Is) chain done ==="
