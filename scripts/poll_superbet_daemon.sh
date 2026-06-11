#!/usr/bin/env bash
# Daemon simples no terminal (alternativa se launchd bloquear Documents).
#
# Uso:
#   ./scripts/poll_superbet_daemon.sh
#   POLL_EVENT_IDS=13108472 ./scripts/poll_superbet_daemon.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

POLL_INTERVAL="${POLL_INTERVAL_SEC:-120}"
POLL_MAX_EVENTS="${POLL_MAX_EVENTS:-15}"
POLL_PHASE="${POLL_PHASE:-friendly}"
POLL_FILTER_INTERNATIONAL="${POLL_FILTER_INTERNATIONAL:-true}"

# shellcheck disable=SC1091
source .venv/bin/activate

ARGS=(--interval "${POLL_INTERVAL}" --no-train --max-events "${POLL_MAX_EVENTS}" --phase "${POLL_PHASE}")

if [[ -n "${POLL_EVENT_IDS:-}" ]]; then
  ARGS+=(--event-ids "${POLL_EVENT_IDS}")
else
  ARGS+=(--auto)
  if [[ "${POLL_FILTER_INTERNATIONAL}" == "true" ]]; then
    ARGS+=(--filter-international)
  fi
fi

echo "Daemon poll Superbet — Ctrl+C para parar"
echo "Intervalo: ${POLL_INTERVAL}s | Args: ${ARGS[*]}"
exec poll-superbet-live "${ARGS[@]}"
