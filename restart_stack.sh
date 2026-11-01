#!/bin/bash
systemctl --user restart strata-web
sleep 5
curl -s -m 280 -X POST http://127.0.0.1:8090/api/start -H 'Content-Type: application/json' -d '{"model":"poly-q5"}'
