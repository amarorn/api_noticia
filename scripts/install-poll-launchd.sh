#!/usr/bin/env bash
# Instala agente launchd para captura automática de ticks Superbet (macOS).
#
# Uso:
#   ./scripts/install-poll-launchd.sh          # instala e ativa
#   ./scripts/install-poll-launchd.sh --remove # desinstala
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.beanalytic.poll-superbet-live"
TEMPLATE="${ROOT}/scripts/launchd/${LABEL}.plist"
TARGET="${HOME}/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

usage() {
  cat <<EOF
Instala captura automática de ticks Superbet via launchd.

  ./scripts/install-poll-launchd.sh          instalar / recarregar
  ./scripts/install-poll-launchd.sh --remove desinstalar
  ./scripts/install-poll-launchd.sh --status   verificar status
  ./scripts/install-poll-launchd.sh --crontab  instalar cron (alternativa)

Configuração opcional no .env:
  POLL_ACTIVE_HOUR_START=10      # hora BRT início (padrão 10)
  POLL_ACTIVE_HOUR_END=23        # hora BRT fim (padrão 23)
  POLL_MAX_EVENTS=15             # máx. jogos por ciclo
  POLL_FILTER_INTERNATIONAL=true # só seleções/amistosos
  POLL_EVENT_IDS=13108472        # IDs fixos (opcional; sem isso usa --auto)

Logs:
  data/lake/logs/poll_superbet.log
  data/lake/logs/poll_superbet_launchd.{out,err}.log
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
  chmod +x "${ROOT}/scripts/poll_superbet_cron.sh"
  mkdir -p "${ROOT}/data/lake/logs"
  mkdir -p "${HOME}/Library/LaunchAgents"

  unload_agent

  sed "s|@@REPO_ROOT@@|${ROOT}|g" "${TEMPLATE}" > "${TARGET}"
  echo "Gerado: ${TARGET}"

  launchctl bootstrap "${DOMAIN}" "${TARGET}"
  launchctl enable "${DOMAIN}/${LABEL}"
  launchctl kickstart -k "${DOMAIN}/${LABEL}" 2>/dev/null || true

  echo ""
  echo "Captura automática ativa (intervalo 120s, janela ${POLL_ACTIVE_HOUR_START:-10}h–${POLL_ACTIVE_HOUR_END:-23}h BRT)."
  echo "Verifique: tail -f ${ROOT}/data/lake/logs/poll_superbet.log"
  echo ""
  verify_agent
}

verify_agent() {
  sleep 3
  ERR_LOG="${ROOT}/data/lake/logs/poll_superbet_launchd.err.log"
  if [[ -f "${ERR_LOG}" ]] && grep -q "Operation not permitted" "${ERR_LOG}" 2>/dev/null; then
    echo "⚠️  macOS bloqueou o launchd (pasta Documents protegida)."
    echo "   Opção A — Ajustes do Sistema → Privacidade → Acesso Total ao Disco → ativar para Terminal (ou /bin/bash)"
    echo "   Opção B — Rodar no terminal: ./scripts/poll_superbet_daemon.sh"
    echo "   Opção C — Cron: ./scripts/install-poll-launchd.sh --crontab"
    return 1
  fi
  if [[ -f "${ROOT}/data/lake/logs/poll_superbet.log" ]]; then
    echo "Última linha do log:"
    tail -1 "${ROOT}/data/lake/logs/poll_superbet.log" || true
  fi
}

install_crontab() {
  chmod +x "${ROOT}/scripts/poll_superbet_cron.sh"
  CRON_LINE="*/2 10-23 * * * ${ROOT}/scripts/poll_superbet_cron.sh"
  (
    crontab -l 2>/dev/null | grep -v "poll_superbet_cron.sh" || true
    echo "${CRON_LINE}"
  ) | crontab -
  echo "Crontab instalado:"
  crontab -l | grep poll_superbet_cron
  echo "Log: ${ROOT}/data/lake/logs/poll_superbet.log"
}

show_status() {
  if launchctl print "${DOMAIN}/${LABEL}" &>/dev/null; then
    echo "Status: ATIVO (${LABEL})"
    launchctl print "${DOMAIN}/${LABEL}" | head -20
  else
    echo "Status: INATIVO (agente não carregado)"
  fi
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
