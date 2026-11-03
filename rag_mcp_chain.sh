#!/bin/bash
# RAG + 도구호출(MCP) 벤치 체인: MCQ 체인이 끝난 뒤 실행. 엔진별로 로드→RAG→MCP→정지.
set -u
exec >> /data/bench-results/rag_mcp_chain.log 2>&1
echo "=== $(date -Is) rag/mcp chain start ==="

# MCQ 체인 종료 대기 (eval_q5.json 또는 eval-chain 유닛 종료)
for i in $(seq 1 240); do
  if [ -f /data/bench-results/eval_q5.json ] || ! systemctl --user is-active --quiet eval-chain; then break; fi
  sleep 15
done
echo "MCQ 체인 종료 감지"

wait_port() {
  for i in $(seq 1 180); do
    curl -s -m 3 "http://127.0.0.1:$1/health" | grep -qE '"loaded": true|"status":"ok"' && return 0
    sleep 5
  done
  return 1
}
model_id() { curl -s -m 10 "http://127.0.0.1:$1/v1/models" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])'; }

run_on() {  # $1=port $2=tag
  port="$1"; tag="$2"
  m=$(model_id "$port")
  echo "--- $tag ($m) ---"
  python3 /data/bench-results/rag_eval.py "http://127.0.0.1:$port" "$m" "/data/bench-results/rag_${tag}.json" 2>&1
  python3 /data/bench-results/mcp_eval.py "http://127.0.0.1:$port" "$m" "/data/bench-results/mcp_${tag}.json" 2>&1
}

echo "--- ds41 ---"
systemctl --user start ds41-serve >/dev/null 2>&1
wait_port 20084 && run_on 20084 ds41
systemctl --user stop ds41-serve >/dev/null 2>&1; sleep 5

run_8090() {  # $1=key $2=port $3=tag
  echo "--- $3 ($1) ---"
  curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d "{\"model\":\"$1\"}" >/dev/null
  if wait_port "$2"; then run_on "$2" "$3"; else echo "$3 로드 실패"; fi
  curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d "{\"model\":\"$1\"}" >/dev/null
  sleep 8
}

run_8090 inf-fp8 20082 fp8
run_8090 poly-q8 20081 q8
run_8090 poly-q5 20080 q5

echo "--- ds41-serve 복구 ---"
systemctl --user start ds41-serve
echo "=== $(date -Is) rag/mcp chain done ==="
