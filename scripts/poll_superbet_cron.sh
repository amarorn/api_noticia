#!/usr/bin/env bash
# Captura um tick Superbet (cron / launchd) — uma execução por invocação.
#
# Cron (a cada 2 min, 10h–23h BRT):
#   */2 10-23 * * * /caminho/api_noticia/scripts/poll_superbet_cron.sh
#
# Launchd (recomendado no macOS):
#   ./scripts/install-poll-launchd.sh
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

POLL_ACTIVE_HOUR_START="${POLL_ACTIVE_HOUR_START:-10}"
POLL_ACTIVE_HOUR_END="${POLL_ACTIVE_HOUR_END:-23}"
POLL_TIMEZONE="${POLL_TIMEZONE:-America/Sao_Paulo}"
POLL_MAX_EVENTS="${POLL_MAX_EVENTS:-15}"
POLL_FILTER_INTERNATIONAL="${POLL_FILTER_INTERNATIONAL:-true}"
POLL_PHASE="${POLL_PHASE:-friendly}"

HOUR="$(TZ="${POLL_TIMEZONE}" date +%H)"
if (( 10#${HOUR} < POLL_ACTIVE_HOUR_START || 10#${HOUR} > POLL_ACTIVE_HOUR_END )); then
  exit 0
fi

if [[ ! -d .venv ]]; then
  echo "poll_superbet_cron: .venv ausente em ${ROOT}" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

LOG_DIR="${ROOT}/data/lake/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/poll_superbet.log"

{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) poll tick (TZ=${POLL_TIMEZONE}, hour=${HOUR}) ==="

  ARGS=(--no-train --max-events "${POLL_MAX_EVENTS}" --phase "${POLL_PHASE}")

  if [[ "${POLL_WC_COPA:-false}" == "true" ]]; then
    ARGS+=(--wc-copa)
  fi

  if [[ -n "${POLL_EVENT_IDS:-}" ]]; then
    ARGS+=(--event-ids "${POLL_EVENT_IDS}")
  else
    ARGS+=(--auto)
    if [[ "${POLL_FILTER_INTERNATIONAL}" == "true" ]]; then
      ARGS+=(--filter-international)
    fi
  fi

  poll-superbet-live "${ARGS[@]}"
} >> "${LOG_FILE}" 2>&1
