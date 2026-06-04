#!/usr/bin/env bash
# Deploy rápido na Fly.io (requer flyctl e volume já criado — ver docs/deploy-fly.md)
set -euo pipefail

APP="${FLY_APP:-api-noticia}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v fly >/dev/null 2>&1; then
  echo "Instale flyctl: https://fly.io/docs/hands-on/install-flyctl/"
  exit 1
fi

if ! fly apps list 2>/dev/null | grep -q "^${APP}[[:space:]]"; then
  echo "Criando app ${APP}..."
  fly apps create "${APP}"
fi

if ! fly volumes list -a "${APP}" 2>/dev/null | grep -q api_noticia_data; then
  echo "Criando volume api_noticia_data em gru..."
  fly volume create api_noticia_data --region gru --size 3 -a "${APP}" --yes
fi

echo "Deploy ${APP}..."
fly deploy -a "${APP}"

echo ""
echo "Próximos passos (primeira vez):"
echo "  fly ssh console -a ${APP} -C 'import-world-cup --missing-only'"
echo "  fly ssh console -a ${APP} -C 'train-wc --force'"
echo "  curl -s https://${APP}.fly.dev/health"
