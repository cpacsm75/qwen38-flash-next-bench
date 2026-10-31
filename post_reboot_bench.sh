#!/bin/bash
# 헤드리스 재부팅 후 1회: 재벤치 → 보고서 → GitHub 푸시 → 전원 종료
set -u
MARK=/data/bench-results/.post_reboot_done
[ -f "$MARK" ] && exit 0
exec >> /data/bench-results/post_reboot.log 2>&1
echo "=== $(date -Is) post-reboot bench start ==="

# strata-web 준비 대기
for i in $(seq 1 60); do
  curl -s -m 2 http://127.0.0.1:8090/api/status >/dev/null 2>&1 && break
  sleep 2
done

cd /data/PolyStrata || exit 1

echo "--- poly-q5"
curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"poly-q5"}' >/dev/null
for i in $(seq 1 90); do curl -s -m 2 http://127.0.0.1:20080/health | grep -q '"loaded": true' && break; sleep 2; done
.venv/bin/python polystrata.py benchmark --model qwen3.8-flash-next-unsloth-ud-q5_k_xl --port 20080 --prompt-tokens 200000 --json /data/bench-results/q5_post_256k.json
.venv/bin/python polystrata.py benchmark --model qwen3.8-flash-next-unsloth-ud-q5_k_xl --port 20080 --prompt-tokens 400000 --json /data/bench-results/q5_post_512k.json
curl -s -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"poly-q5"}' >/dev/null
sleep 5

echo "--- inf-fp8"
curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"inf-fp8"}' >/dev/null
for i in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:20082/health | grep -q '"status":"ok"' && break; sleep 2; done
python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20082 8192,200000,390000 /data/bench-results/fp8_post.json
curl -s -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"inf-fp8"}' >/dev/null

echo "--- deepseek v4.1"
systemctl --user start ds41-serve
for i in $(seq 1 300); do curl -s -m 2 http://127.0.0.1:20084/health | grep -q '"loaded": true' && break; sleep 2; done
BENCH_MODEL=deepseek-v4.1-flash-1017-xq BENCH_PROC=ds41_generate python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20084 8192,32768 /data/bench-results/deepseek_post.json
systemctl --user stop ds41-serve

echo "--- report"
python3 /data/bench-results/make_post_report.py

echo "--- git push"
cd /data/bench-results || exit 1
git add -A
git -c user.name=cpacsm75 -c user.email=cjscsm@gmail.com commit -q -m "Headless re-run after reboot: Q5/FP8 benchmarks + POST_REBOOT.md" || true
TOKEN=$(cat "$HOME/.config/gh/token" 2>/dev/null)
if [ -n "${TOKEN:-}" ]; then
  git push -q "https://cpacsm75:${TOKEN}@github.com/cpacsm75/qwen38-flash-next-bench.git" main && echo "push ok"
else
  echo "no token, push skipped"
fi

touch "$MARK"
echo "=== $(date -Is) done, powering off ==="
sync
sudo -n /usr/bin/systemctl poweroff
