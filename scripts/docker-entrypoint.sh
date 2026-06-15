#!/bin/sh
set -e

LAKE="${LAKE_ROOT:-/data/lake}"

mkdir -p "$LAKE/bronze" "$LAKE/silver" "$LAKE/gold"
mkdir -p "$LAKE/fixtures" "$LAKE/cache"
mkdir -p "$LAKE/artifacts/wc_predictor"

if [ -z "$(ls -A "$LAKE/fixtures" 2>/dev/null)" ]; then
  echo "wc_fixtures_missing: importe fixtures WC ou inclua data/lake/fixtures no deploy"
fi

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
