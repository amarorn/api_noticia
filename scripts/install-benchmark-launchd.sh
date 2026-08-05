#!/usr/bin/env bash
# Instala agente launchd para benchmark diário in-play (macOS).
#
# Uso:
#   ./scripts/install-benchmark-launchd.sh          # instala e ativa
#   ./scripts/install-benchmark-launchd.sh --remove # desinstala
#   ./scripts/install-benchmark-launchd.sh --run-now  # executa uma vez agora
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.beanalytic.inplay-benchmark-daily"
TEMPLATE="${ROOT}/scripts/launchd/${LABEL}.plist"
TARGET="${HOME}/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

usage() {
  cat <<EOF
Instala benchmark diário in-play via launchd (06:12 horário local).

  ./scripts/install-benchmark-launchd.sh            instalar / recarregar
  ./scripts/install-benchmark-launchd.sh --remove   desinstalar
  ./scripts/install-benchmark-launchd.sh --status     verificar status
  ./scripts/install-benchmark-launchd.sh --crontab    instalar cron (alternativa)
  ./scripts/install-benchmark-launchd.sh --run-now    rodar pipeline uma vez

Saídas:
  data/lake/reports/inplay_daily_YYYYMMDD.json
  data/lake/metrics_history.parquet
  data/lake/logs/inplay_benchmark_daily.log

Gate de regressão:
  python scripts/check_model_regression.py
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
  chmod +x "${ROOT}/scripts/inplay_benchmark_cron.sh"
  mkdir -p "${ROOT}/data/lake/logs" "${ROOT}/data/lake/reports"
  mkdir -p "${HOME}/Library/LaunchAgents"

  unload_agent

  sed "s|@@REPO_ROOT@@|${ROOT}|g" "${TEMPLATE}" > "${TARGET}"
  echo "Gerado: ${TARGET}"

  launchctl bootstrap "${DOMAIN}" "${TARGET}"
  launchctl enable "${DOMAIN}/${LABEL}"

  echo ""
  echo "Benchmark diário agendado (06:12 horário local)."
  echo "Log: ${ROOT}/data/lake/logs/inplay_benchmark_daily.log"
  echo ""
  show_status
}

install_crontab() {
  chmod +x "${ROOT}/scripts/inplay_benchmark_cron.sh"
  CRON_LINE="12 6 * * * ${ROOT}/scripts/inplay_benchmark_cron.sh"
  (
    crontab -l 2>/dev/null | grep -v "inplay_benchmark_cron.sh" || true
    echo "${CRON_LINE}"
  ) | crontab -
  echo "Crontab instalado:"
  crontab -l | grep inplay_benchmark_cron
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
  chmod +x "${ROOT}/scripts/inplay_benchmark_cron.sh"
  "${ROOT}/scripts/inplay_benchmark_cron.sh"
  echo "Concluído. Verifique data/lake/reports/inplay_daily_*.json"
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
