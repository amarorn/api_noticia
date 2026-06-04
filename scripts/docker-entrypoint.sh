#!/bin/sh
set -e

mkdir -p /data/lake/bronze /data/lake/silver /data/lake/gold
mkdir -p /data/lake/fixtures /data/lake/cache
mkdir -p /data/lake/artifacts/wc_predictor

if [ -z "$(ls -A /data/lake/fixtures 2>/dev/null)" ]; then
  echo "wc_fixtures_missing: rode 'fly ssh console -C \"import-world-cup --missing-only\"'"
fi

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
