#!/usr/bin/env bash
# Relatório semanal P&L vs Brier (segunda 8h BRT sugerido).
# Crontab: 0 11 * * 1 /path/to/api_noticia/scripts/weekly-pl-report.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

USER_ID="${1:-${SUPERBET_FINALIZE_USER_ID:-jamarorn}}"

# shellcheck disable=SC1091
source .venv/bin/activate

LOG_DIR="${ROOT}/data/lake/logs"
mkdir -p "${LOG_DIR}"

{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) weekly-pl user=${USER_ID} ==="
  weekly-pl-report --user "${USER_ID}"
} >> "${LOG_DIR}/weekly_pl_cron.log" 2>&1
