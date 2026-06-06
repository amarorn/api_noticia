#!/usr/bin/env bash
# Dev padrão: perfil local (sem custo GCP). Cloud só para publicar/testar BI.
#
#   ./scripts/docker-dev.sh up                # API local (padrão)
#   ./scripts/docker-dev.sh run daily-sync
#   ./scripts/docker-dev.sh cloud up          # GCS/BQ quando precisar
#   ./scripts/docker-dev.sh cloud run sync-gcp --layer all
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ "${1:-}" = "local" ] || [ "${1:-}" = "cloud" ]; then
  PROFILE="$1"
  ACTION="${2:-up}"
  shift 2 || true
else
  PROFILE="local"
  ACTION="${1:-up}"
  shift 1 || true
fi

case "$PROFILE" in
  local|cloud) ;;
  *)
    echo "Perfil inválido: $PROFILE (use local ou cloud)" >&2
    exit 1
    ;;
esac

case "$ACTION" in
  up)
    docker compose --profile "$PROFILE" up "api-${PROFILE}" -d --build
    echo "API: http://localhost:${API_PORT:-8000}"
    ;;
  down)
    docker compose --profile "$PROFILE" down
    ;;
  logs)
    docker compose --profile "$PROFILE" logs -f "api-${PROFILE}"
    ;;
  run)
    if [ "$#" -lt 1 ]; then
      echo "Informe o comando CLI (ex.: daily-sync, train-wc --force)" >&2
      exit 1
    fi
    docker compose --profile "$PROFILE" run --rm --build "pipeline-${PROFILE}" "$@"
    ;;
  build)
    docker compose --profile "$PROFILE" build
    ;;
  *)
    echo "Ação inválida: $ACTION (use up, down, logs, run, build)" >&2
    exit 1
    ;;
esac
