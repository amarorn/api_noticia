#!/usr/bin/env bash
# Backup semanal do lake local → GCS (sync-gcp --layer all).
#
# Requer: pip install -e ".[gcp]", GOOGLE_APPLICATION_CREDENTIALS no .env
# Uso manual: ./scripts/lake-cloud-backup.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT}/data/lake/logs"
LOG_FILE="${LOG_DIR}/lake_cloud_backup.log"

mkdir -p "${LOG_DIR}"
cd "${ROOT}"

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

if [[ "${LAKE_PRIMARY:-local}" == "cloud" ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) LAKE_PRIMARY=cloud — backup ignorado (já cloud-first)" >>"${LOG_FILE}"
  exit 0
fi

if [[ -z "${GCS_BUCKET:-}" || -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) GCS_BUCKET ou credenciais ausentes — backup ignorado" >>"${LOG_FILE}"
  exit 0
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Iniciando sync-gcp --layer all" >>"${LOG_FILE}"
if sync-gcp --layer all >>"${LOG_FILE}" 2>&1; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Backup concluído" >>"${LOG_FILE}"
else
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Backup falhou (ver log)" >>"${LOG_FILE}"
  exit 1
fi
