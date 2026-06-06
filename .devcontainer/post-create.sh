#!/usr/bin/env bash
set -euo pipefail

cd /workspace

python -m pip install --upgrade pip
pip install -e ".[dev,gcp,sofascore,analytics]"

mkdir -p data/lake/{bronze,silver,gold,fixtures,sofascore,fept,artifacts/wc_predictor,cache}

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Criado .env a partir de .env.example"
fi

if [ -f frontend/package.json ] && command -v npm >/dev/null 2>&1; then
  (cd frontend && npm install)
fi

echo "Dev Container pronto (lake local, sem custo GCP)."
