#!/usr/bin/env bash
set -euo pipefail

max_retries=${DB_CONNECT_RETRIES:-30}
retry_delay=${DB_CONNECT_DELAY:-2}

echo "[entrypoint] Checking database connectivity..."
attempt=1
while true; do
  if python - <<'PY' >/dev/null 2>&1; then
from sqlalchemy import text
from fitness.database import engine
with engine.connect() as connection:
    connection.execute(text("SELECT 1"))
PY
    echo "[entrypoint] Database connection established."
    break
  fi

  if [[ $attempt -ge $max_retries ]]; then
    echo "[entrypoint] Database did not become available after ${max_retries} attempts." >&2
    exit 1
  fi

  echo "[entrypoint] Database unavailable (attempt ${attempt}/${max_retries}); retrying in ${retry_delay}s..."
  attempt=$((attempt + 1))
  sleep "${retry_delay}"
done

if [[ -n "${SKIP_DB_MIGRATIONS:-}" ]]; then
  echo "[entrypoint] SKIP_DB_MIGRATIONS set, skipping Alembic upgrade."
else
  echo "[entrypoint] Running Alembic migrations..."
  alembic upgrade head
fi

echo "[entrypoint] Starting application..."
exec "$@"
