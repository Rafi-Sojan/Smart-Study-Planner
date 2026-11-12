#!/bin/sh
set -eu

PORT="${PORT:-10000}"
API_PORT="${API_PORT:-8000}"

case "$PORT" in
  ''|*[!0-9]*)
    echo "PORT must be an integer" >&2
    exit 2
    ;;
esac
case "$API_PORT" in
  ''|*[!0-9]*)
    echo "API_PORT must be an integer" >&2
    exit 2
    ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "PORT is outside the supported range" >&2
  exit 2
fi
if [ "$API_PORT" -lt 1 ] || [ "$API_PORT" -gt 65535 ]; then
  echo "API_PORT is outside the supported range" >&2
  exit 2
fi
if [ "$PORT" -eq "$API_PORT" ]; then
  echo "PORT and API_PORT must be different" >&2
  exit 2
fi

export PORT API_PORT
envsubst '${PORT} ${API_PORT}' \
  < /app/deploy/render/nginx.conf.template \
  > /tmp/nginx.conf
nginx -t -c /tmp/nginx.conf

python -m uvicorn src.api.main:app \
  --host 127.0.0.1 \
  --port "$API_PORT" \
  --proxy-headers \
  --forwarded-allow-ips 127.0.0.1 &
api_pid=$!

nginx -c /tmp/nginx.conf -g 'daemon off;' &
nginx_pid=$!

shutdown() {
  trap - INT TERM
  kill -TERM "$nginx_pid" "$api_pid" 2>/dev/null || true
  wait "$nginx_pid" 2>/dev/null || true
  wait "$api_pid" 2>/dev/null || true
  exit 0
}
trap shutdown INT TERM

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
  sleep 1
done

exit_status=1
if ! kill -0 "$api_pid" 2>/dev/null; then
  wait "$api_pid" || exit_status=$?
else
  wait "$nginx_pid" || exit_status=$?
fi

kill -TERM "$nginx_pid" "$api_pid" 2>/dev/null || true
wait "$nginx_pid" 2>/dev/null || true
wait "$api_pid" 2>/dev/null || true
exit "$exit_status"
