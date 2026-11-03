#!/bin/bash
# 코딩 평가 체인: ds41 → inf-fp8 → poly-q8 → poly-q5 (엔진별 로드·평가·정지). 끝나면 ds41-serve 복구.
set -u
exec >> /data/bench-results/code_chain.log 2>&1
echo "=== $(date -Is) code chain start ==="

wait_port() {  # $1=port
  for i in $(seq 1 180); do
    curl -s -m 3 "http://127.0.0.1:$1/health" | grep -qE '"loaded": true|"status":"ok"' && return 0
    sleep 5
  done
  return 1
}

model_id() { curl -s -m 10 "http://127.0.0.1:$1/v1/models" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])'; }

# 1) ds41 (이미 떠 있을 수 있음)
echo "--- ds41 ---"
systemctl --user start ds41-serve >/dev/null 2>&1
wait_port 20084 && python3 /data/bench-results/code_eval.py http://127.0.0.1:20084 "$(model_id 20084)" /data/bench-results/code_ds41.json --max-tokens 2048
systemctl --user stop ds41-serve >/dev/null 2>&1; sleep 5

run_8090() {  # $1=key $2=port $3=tag
  echo "--- $3 ($1) ---"
  curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d "{\"model\":\"$1\"}" >/dev/null
  if wait_port "$2"; then
    python3 /data/bench-results/code_eval.py "http://127.0.0.1:$2" "$(model_id "$2")" "/data/bench-results/code_${3}.json" --max-tokens 2048
  else
    echo "$3 로드 실패"
  fi
  curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d "{\"model\":\"$1\"}" >/dev/null
  sleep 8
}

run_8090 inf-fp8 20082 fp8
run_8090 poly-q8 20081 q8
run_8090 poly-q5 20080 q5

echo "--- ds41-serve 복구 ---"
systemctl --user start ds41-serve
echo "=== $(date -Is) code chain done ==="
