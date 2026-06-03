#!/usr/bin/env bash
# API de desenvolvimento: reload só em api/ (evita reinício ao gravar parquet ou editar pipelines)
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

exec uvicorn api.main:app \
  --reload \
  --host 127.0.0.1 \
  --port 8000 \
  --reload-dir api
