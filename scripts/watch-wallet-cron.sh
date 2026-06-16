#!/usr/bin/env bash
# Importa CSVs da inbox Superbet (cron semanal ou pós-rodada).
# Uso: ./scripts/watch-wallet-cron.sh [user_id]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

USER_ID="${1:-${SUPERBET_FINALIZE_USER_ID:-jamarorn}}"

# shellcheck disable=SC1091
source .venv/bin/activate

LOG_DIR="${ROOT}/data/lake/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/watch_wallet.log"

{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) watch-wallet user=${USER_ID} ==="
  watch-wallet-csv --user "${USER_ID}"
} >> "${LOG_FILE}" 2>&1
