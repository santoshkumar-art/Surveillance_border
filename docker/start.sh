#!/bin/sh
set -eu

: "${PORT:=10000}"
export PORT

# Render provides PORT at runtime; substitute it into nginx's configuration.
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

uvicorn app.main:app --app-dir /app/backend --host 127.0.0.1 --port 8000 &
backend_pid=$!

shutdown() {
  kill "$backend_pid" 2>/dev/null || true
}
trap shutdown INT TERM EXIT

nginx -g 'daemon off;'
