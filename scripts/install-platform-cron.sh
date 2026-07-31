#!/usr/bin/env bash
# Instala crons da plataforma ML (poll futebol clubes + wallet + relatório semanal).
#
# Uso:
#   ./scripts/install-platform-cron.sh          # instala tudo
#   ./scripts/install-platform-cron.sh --remove # remove linhas deste repo
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_ID="${SUPERBET_FINALIZE_USER_ID:-jamarorn}"

usage() {
  cat <<EOF
Instala crons recomendados para a plataforma ML:

  */2 10-23 * * *   poll Superbet (--auto, clubes ao vivo)
  0 */6 * * *       watch-wallet-csv (importa inbox)
  0 12 * * 0        wallet-reminder (domingo)
  0 11 * * 1        weekly-pl-report (segunda)
  0 3 * * 0         lake-cloud-backup (domingo, requer GCP)

Logs: data/lake/logs/
EOF
}

remove_crons() {
  crontab -l 2>/dev/null | grep -v "${ROOT}/scripts/" | crontab - || true
  echo "Crons do repo removidos."
}

install_crons() {
  chmod +x "${ROOT}/scripts/poll_superbet_cron.sh"
  chmod +x "${ROOT}/scripts/watch-wallet-cron.sh"
  chmod +x "${ROOT}/scripts/wallet-reminder-cron.sh"
  chmod +x "${ROOT}/scripts/weekly-pl-report.sh"
  chmod +x "${ROOT}/scripts/lake-cloud-backup.sh"
  mkdir -p "${ROOT}/data/lake/logs"

  POLL_LINE="*/2 10-23 * * * ${ROOT}/scripts/poll_superbet_cron.sh"
  WALLET_LINE="0 */6 * * * ${ROOT}/scripts/watch-wallet-cron.sh ${USER_ID}"
  REMIND_LINE="0 12 * * 0 ${ROOT}/scripts/wallet-reminder-cron.sh ${USER_ID}"
  REPORT_LINE="0 11 * * 1 ${ROOT}/scripts/weekly-pl-report.sh ${USER_ID}"
  BACKUP_LINE="0 3 * * 0 ${ROOT}/scripts/lake-cloud-backup.sh"

  (
    crontab -l 2>/dev/null | grep -v "${ROOT}/scripts/" || true
    echo "${POLL_LINE}"
    echo "${WALLET_LINE}"
    echo "${REMIND_LINE}"
    echo "${REPORT_LINE}"
    echo "${BACKUP_LINE}"
  ) | crontab -

  echo "Crons instalados:"
  crontab -l | grep "${ROOT}/scripts/" || true
  echo ""
  echo "Dica: se launchd falhar (Documents/), use só este cron para poll WC."
}

case "${1:-}" in
  --remove|-r) remove_crons ;;
  --help|-h) usage ;;
  "") install_crons ;;
  *)
    echo "Opção desconhecida: $1" >&2
    usage
    exit 1
    ;;
esac
