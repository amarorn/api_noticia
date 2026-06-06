#!/usr/bin/env bash
set -euo pipefail

cd /workspace

python -m pip install --upgrade pip
pip install -e ".[dev,gcp,sofascore,analytics]"

mkdir -p data/lake/{bronze,silver,gold,fixtures,sofascore,fept,artifacts/wc_predictor,cache}

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Criado .env a partir de .env.example (LAKE_PRIMARY=local)"
fi

if [ -f frontend/package.json ]; then
  if command -v npm >/dev/null 2>&1; then
    (cd frontend && npm install)
  fi
fi

echo "Dev Container pronto. API: uvicorn api.main:app --reload --host 0.0.0.0 --port 8000"
