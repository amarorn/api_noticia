#!/usr/bin/env bash
# API sem reload — use com o frontend para evitar ECONNRESET durante coleta de notícias
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

exec uvicorn api.main:app --host 127.0.0.1 --port 8000
