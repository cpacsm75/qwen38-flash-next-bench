#!/bin/bash
# Dense8 512K(YaRN2) → FP8 512K 1회 반복 (450W, 단독 실행)
set -u
exec >> /data/bench-results/bench-512k2.log 2>&1
echo "=== $(date -Is) dense8-long + fp8 repeat start ==="

# ---------- 1) Dense8 512K (YaRN2 TOML, 직접 기동) ----------
curl -s -m 60 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"inf-fp8"}' >/dev/null 2>&1
systemctl --user stop inf-dense8-bench >/dev/null 2>&1; fuser -k -n tcp 20082 >/dev/null 2>&1; sleep 5
systemd-run --user --unit inf-dense8-bench --collect \
  --property=WorkingDirectory=/data/Infernix \
  --property=StandardOutput=append:/data/Infernix/dense8-long.log \
  --property=StandardError=append:/data/Infernix/dense8-long.log \
  -- /data/Infernix/build/apps/infernix-serve --config /data/strata-web/infernix-dense8-long.toml
for i in $(seq 1 240); do curl -s -m 2 http://127.0.0.1:20082/health | grep -q '"status":"ok"' && break; sleep 3; done
echo "--- dense8-long health ---"; curl -s -m 5 http://127.0.0.1:20082/health; echo
M=$(curl -s -m 10 http://127.0.0.1:20082/v1/models | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')
echo "model id: $M"
BENCH_MODEL="$M" python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20082 390000 /data/bench-results/dense8_512k.json
systemctl --user stop inf-dense8-bench >/dev/null 2>&1
fuser -k -n tcp 20082 >/dev/null 2>&1
sleep 6

# ---------- 2) FP8 512K 1회 반복 ----------
curl -s -m 300 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"inf-fp8"}' >/dev/null
for i in $(seq 1 240); do curl -s -m 2 http://127.0.0.1:20082/health | grep -q '"status":"ok"' && break; sleep 3; done
echo "--- fp8 health ---"; curl -s -m 5 http://127.0.0.1:20082/health; echo
M=$(curl -s -m 10 http://127.0.0.1:20082/v1/models | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')
echo "model id: $M"
BENCH_MODEL="$M" python3 /data/bench-results/bench_infernix.py http://127.0.0.1:20082 390000 /data/bench-results/fp8_512k_rerun.json
curl -s -m 120 -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"inf-fp8"}' >/dev/null
echo "=== $(date -Is) done ==="
