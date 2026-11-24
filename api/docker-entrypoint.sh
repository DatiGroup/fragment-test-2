#!/bin/sh
set -e

# Optionally load .env if present (useful for local dev); but docker-compose `environment` will take precedence.
if [ -f "./.env" ]; then
  echo "Loading .env file"
  set -o allexport
  . ./.env
  set +o allexport
fi

# Wait for the database to be available (uses DATABASE_URL env var)
wait_for_db() {
  if [ -z "$DATABASE_URL" ]; then
    echo "DATABASE_URL not set; skipping DB wait"
    return 0
  fi

  echo "Waiting for DB to become available..."
  # Try to use pg_isready if available
  if command -v pg_isready >/dev/null 2>&1; then
    # extract host and port
    DB_HOST=$(echo $DATABASE_URL | sed -n 's,.*@\([^:/]*\).*:\([0-9]*\).*,\1,p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's,.*@[^:]*:\([0-9]*\).*\/.*,\1,p')
    if [ -z "$DB_HOST" ]; then
      # fallback: use localhost
      DB_HOST=localhost
    fi
    if [ -z "$DB_PORT" ]; then
      DB_PORT=5432
    fi
    until pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; do
      echo "pg_isready: waiting for $DB_HOST:$DB_PORT..."
      sleep 1
    done
  else
    # Fallback: use Python to attempt a DB connection via SQLAlchemy
    python - <<PY
import os, time
from sqlalchemy import create_engine
url = os.getenv('DATABASE_URL')
if not url:
    print('No DATABASE_URL set')
else:
    engine = create_engine(url)
    while True:
        try:
            conn = engine.connect()
            conn.close()
            print('DB is available')
            break
        except Exception as e:
            print('DB not ready, retrying...', e)
            time.sleep(1)
PY
  fi
}

wait_for_db

# run alembic migrations (best-effort)
if [ -f "./alembic.ini" ]; then
  echo "Running alembic migrations..."
  alembic -c alembic.ini upgrade head || echo "alembic failed; continuing"
fi

# start server
exec uvicorn main:app --host 0.0.0.0 --port 8000
