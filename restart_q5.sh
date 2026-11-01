#!/bin/bash
curl -s -X POST http://127.0.0.1:8090/api/stop -H 'Content-Type: application/json' -d '{"model":"poly-q5"}'
sleep 3
curl -s -m 280 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"poly-q5"}'
