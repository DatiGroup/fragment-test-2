#!/bin/sh
set -e

# Load .env if present (compose environment will take precedence)
if [ -f "./.env" ]; then
  echo "Loading .env for worker"
  set -o allexport
  . ./.env
  set +o allexport
fi

# run worker
exec python main.py
