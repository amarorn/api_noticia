#!/usr/bin/env bash
# API de desenvolvimento: reload só em api/ (evita reinício ao gravar parquet ou editar pipelines)
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_BIN="$ROOT/.venv/bin"

if [[ -f "$VENV_BIN/activate" ]]; then
  # shellcheck source=/dev/null
  source "$VENV_BIN/activate"
fi

for var in SSL_CERT_FILE REQUESTS_CA_BUNDLE CURL_CA_BUNDLE; do
  ca="${!var:-}"
  if [[ -n "$ca" ]] && [[ ! -f "$ca" ]]; then
    unset "$var"
  fi
done

exec "${VENV_BIN}/uvicorn" api.main:app \
  --reload \
  --host 127.0.0.1 \
  --port 8000 \
  --reload-dir api
