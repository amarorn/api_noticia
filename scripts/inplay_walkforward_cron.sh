#!/usr/bin/env bash
# Relatório semanal in-play: tune MLE + walk-forward + retreino GBM (domingo).
#
# Cron (domingo 07:18 BRT ≈ horário local):
#   18 7 * * 0 /caminho/api_noticia/scripts/inplay_walkforward_cron.sh
#
# Launchd (recomendado no macOS):
#   ./scripts/install-walkforward-launchd.sh
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

if [[ ! -x .venv/bin/python ]]; then
  echo "inplay_walkforward_cron: .venv ausente em ${ROOT}" >&2
  exit 1
fi

LOG_DIR="${ROOT}/data/lake/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/inplay_walkforward_weekly.log"

EVAL_SEASON="${INPLAY_WALKFORWARD_EVAL_SEASON:-2022}"
SKIP_TUNE="${INPLAY_WEEKLY_SKIP_TUNE:-0}"
SKIP_GBM="${INPLAY_WEEKLY_SKIP_GBM:-0}"

ARGS=(--eval-season "${EVAL_SEASON}" --quiet)
if [[ "${SKIP_TUNE}" == "1" ]]; then
  ARGS+=(--skip-tune)
fi
if [[ "${SKIP_GBM}" == "1" ]]; then
  ARGS+=(--skip-gbm)
fi

{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) inplay weekly report (eval_season=${EVAL_SEASON}) ==="
  .venv/bin/inplay-weekly-report "${ARGS[@]}"

  if [[ "${SKIP_HF_PUBLISH:-0}" != "1" ]]; then
    if [[ -n "${HF_TOKEN:-${HUGGING_FACE_HUB_TOKEN:-}}" ]]; then
      echo "=== HF publish (reports + artifacts) ==="
      ./scripts/publish-reports-hf.sh || echo "publish-reports-hf falhou (exit $?)"
      ./scripts/publish-artifacts.sh || echo "publish-artifacts falhou (exit $?)"
    else
      echo "HF publish pulado (HF_TOKEN ausente)"
    fi
  fi
} >> "${LOG_FILE}" 2>&1
