#!/usr/bin/env bash
# Runs the same real verification steps as tests/test_monitoring_stack.py, by hand, so a human can
# watch it happen (and poke at Grafana/Prometheus themselves) instead of trusting pytest's word for it.
#
# Usage: LAB_TARGET=solution scripts/manual_verify.sh   (or LAB_TARGET=starter to see it fail)
set -euo pipefail

LAB_TARGET="${LAB_TARGET:-solution}"
APP_PORT="${APP_PORT:-18000}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-19090}"
GRAFANA_PORT="${GRAFANA_PORT:-13000}"
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_URL="http://127.0.0.1:${APP_PORT}"
PROM_URL="http://127.0.0.1:${PROMETHEUS_PORT}"

cleanup() {
  echo "--- tearing down (docker compose down -v) ---"
  LAB_TARGET="$LAB_TARGET" docker compose -f "$LAB_DIR/docker-compose.yml" down -v
}
trap cleanup EXIT

echo "--- bringing up the real stack (LAB_TARGET=$LAB_TARGET) ---"
LAB_TARGET="$LAB_TARGET" APP_PORT="$APP_PORT" PROMETHEUS_PORT="$PROMETHEUS_PORT" GRAFANA_PORT="$GRAFANA_PORT" \
  docker compose -f "$LAB_DIR/docker-compose.yml" up -d --build

echo "--- waiting for app /health ---"
for _ in $(seq 1 30); do
  if curl -sf "$APP_URL/health" >/dev/null; then break; fi
  sleep 2
done
curl -s "$APP_URL/health"; echo

echo "--- waiting for prometheus target to be up ---"
for _ in $(seq 1 15); do
  if curl -s "$PROM_URL/api/v1/targets" | grep -q '"health":"up"'; then break; fi
  sleep 2
done
curl -s "$PROM_URL/api/v1/targets" | python3 -m json.tool | grep -E "job|health|lastError"

echo "--- sending 25 real /predict requests ---"
for i in $(seq 1 25); do
  curl -s -X POST "$APP_URL/predict" -H 'Content-Type: application/json' \
    -d '{"features": [0.1, -0.05, 0.02]}' >/dev/null
done
sleep 6
echo "http_requests_total{endpoint=\"/predict\"}:"
curl -s -G "$PROM_URL/api/v1/query" --data-urlencode 'query=http_requests_total{endpoint="/predict"}'
echo
echo "http_request_duration_seconds_count{endpoint=\"/predict\"}:"
curl -s -G "$PROM_URL/api/v1/query" --data-urlencode 'query=http_request_duration_seconds_count{endpoint="/predict"}'
echo

echo "--- inducing a real latency spike (sends slow requests until the alert fires or 60s elapse) ---"
deadline=$((SECONDS + 60))
while [ "$SECONDS" -lt "$deadline" ]; do
  curl -s -X POST "$APP_URL/predict" -H 'Content-Type: application/json' \
    -d '{"features":[0.0],"simulate_latency_seconds":1.2}' >/dev/null
  state=$(curl -s "$PROM_URL/api/v1/alerts" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for a in d['data']['alerts']:
    if a['labels']['alertname']=='HighPredictRequestLatency':
        print(a['state']); sys.exit()
print('none')")
  echo "HighPredictRequestLatency state=$state"
  if [ "$state" = "firing" ]; then break; fi
done

echo "--- inducing a real drift spike ---"
curl -s -X POST "$APP_URL/predict" -H 'Content-Type: application/json' -d '{"features":[100.0,100.0,100.0]}'
echo
deadline=$((SECONDS + 30))
while [ "$SECONDS" -lt "$deadline" ]; do
  state=$(curl -s "$PROM_URL/api/v1/alerts" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for a in d['data']['alerts']:
    if a['labels']['alertname']=='HighPredictionDrift':
        print(a['state']); sys.exit()
print('none')")
  echo "HighPredictionDrift state=$state"
  if [ "$state" = "firing" ]; then break; fi
  sleep 2
done

echo "--- final /api/v1/alerts ---"
curl -s "$PROM_URL/api/v1/alerts" | python3 -m json.tool

echo "--- done (teardown runs automatically via the EXIT trap) ---"
