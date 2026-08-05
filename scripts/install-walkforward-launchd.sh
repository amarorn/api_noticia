#!/usr/bin/env bash
# Instala agente launchd para walk-forward semanal in-play (macOS).
#
# Uso:
#   ./scripts/install-walkforward-launchd.sh            # instala (domingo 07:18)
#   ./scripts/install-walkforward-launchd.sh --remove   # desinstala
#   ./scripts/install-walkforward-launchd.sh --run-now  # executa uma vez agora
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.beanalytic.inplay-walkforward-weekly"
TEMPLATE="${ROOT}/scripts/launchd/${LABEL}.plist"
TARGET="${HOME}/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

usage() {
  cat <<EOF
Instala walk-forward semanal in-play via launchd (domingo 07:18 horário local).

Pipeline: tune-inplay → walk-forward → train-inplay-gbm

  ./scripts/install-walkforward-launchd.sh            instalar / recarregar
  ./scripts/install-walkforward-launchd.sh --remove     desinstalar
  ./scripts/install-walkforward-launchd.sh --status     verificar status
  ./scripts/install-walkforward-launchd.sh --crontab    cron alternativo (dom 07:18)
  ./scripts/install-walkforward-launchd.sh --run-now    rodar pipeline uma vez

Variáveis (.env):
  INPLAY_WALKFORWARD_EVAL_SEASON=2022
  INPLAY_WEEKLY_SKIP_TUNE=0       # 1 = pular tune MLE
  INPLAY_WEEKLY_SKIP_GBM=0        # 1 = pular retreino GBM (~10 min)

Saídas:
  data/lake/reports/inplay_weekly_YYYYMMDD.json
  data/lake/metrics_history.parquet (report_kind=weekly)
  data/lake/logs/inplay_walkforward_weekly.log

Relacionado (diário 06:12):
  ./scripts/install-benchmark-launchd.sh
EOF
}

unload_agent() {
  if launchctl print "${DOMAIN}/${LABEL}" &>/dev/null; then
    launchctl bootout "${DOMAIN}" "${TARGET}" 2>/dev/null || true
    echo "Agente ${LABEL} descarregado."
  fi
}

remove_agent() {
  unload_agent
  rm -f "${TARGET}"
  echo "Removido: ${TARGET}"
}

install_agent() {
  chmod +x "${ROOT}/scripts/inplay_walkforward_cron.sh"
  mkdir -p "${ROOT}/data/lake/logs" "${ROOT}/data/lake/reports"
  mkdir -p "${HOME}/Library/LaunchAgents"

  unload_agent

  sed "s|@@REPO_ROOT@@|${ROOT}|g" "${TEMPLATE}" > "${TARGET}"
  echo "Gerado: ${TARGET}"

  launchctl bootstrap "${DOMAIN}" "${TARGET}"
  launchctl enable "${DOMAIN}/${LABEL}"

  echo ""
  echo "Walk-forward semanal agendado (domingo 07:18 horário local)."
  echo "Log: ${ROOT}/data/lake/logs/inplay_walkforward_weekly.log"
  echo ""
  show_status
}

install_crontab() {
  chmod +x "${ROOT}/scripts/inplay_walkforward_cron.sh"
  CRON_LINE="18 7 * * 0 ${ROOT}/scripts/inplay_walkforward_cron.sh"
  (
    crontab -l 2>/dev/null | grep -v "inplay_walkforward_cron.sh" || true
    echo "${CRON_LINE}"
  ) | crontab -
  echo "Crontab instalado:"
  crontab -l | grep inplay_walkforward_cron
}

show_status() {
  if launchctl print "${DOMAIN}/${LABEL}" &>/dev/null; then
    echo "Status: ATIVO (${LABEL})"
    launchctl print "${DOMAIN}/${LABEL}" | head -20
  else
    echo "Status: INATIVO (agente não carregado)"
  fi
}

run_now() {
  chmod +x "${ROOT}/scripts/inplay_walkforward_cron.sh"
  "${ROOT}/scripts/inplay_walkforward_cron.sh"
  echo "Concluído. Verifique data/lake/reports/inplay_weekly_*.json"
}

case "${1:-}" in
  --remove|-r)
    remove_agent
    ;;
  --status|-s)
    show_status
    ;;
  --crontab|-c)
    install_crontab
    ;;
  --run-now|-n)
    run_now
    ;;
  --help|-h)
    usage
    ;;
  "")
    install_agent
    ;;
  *)
    echo "Opção desconhecida: $1" >&2
    usage
    exit 1
    ;;
esac
