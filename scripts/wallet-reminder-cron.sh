#!/usr/bin/env bash
# Lembrete semanal: exporte CSV Superbet se desatualizado (domingo 9h BRT sugerido).
# Crontab: 0 12 * * 0 /path/to/api_noticia/scripts/wallet-reminder-cron.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

USER_ID="${1:-${SUPERBET_FINALIZE_USER_ID:-jamarorn}}"

# shellcheck disable=SC1091
source .venv/bin/activate

LOG_DIR="${ROOT}/data/lake/logs"
mkdir -p "${LOG_DIR}"

{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) wallet-reminder user=${USER_ID} ==="
  wallet-reminder --user "${USER_ID}" || true
} >> "${LOG_DIR}/wallet_reminder_cron.log" 2>&1
