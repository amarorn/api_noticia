#!/usr/bin/env bash
# Relatório diário de benchmark in-play (cron / launchd) — uma execução por invocação.
#
# Cron (06:12 BRT):
#   12 6 * * * /caminho/api_noticia/scripts/inplay_benchmark_cron.sh
#
# Launchd (recomendado no macOS):
#   ./scripts/install-benchmark-launchd.sh
#
# Após o gate, publica relatórios no HF se HF_TOKEN estiver no .env
# (ou login em cache via `hf auth login`). Desligue com SKIP_HF_PUBLISH=1.
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
  echo "inplay_benchmark_cron: .venv ausente em ${ROOT}" >&2
  exit 1
fi

LOG_DIR="${ROOT}/data/lake/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/inplay_benchmark_daily.log"

USER_ID="${INPLAY_BENCHMARK_USER_ID:-jamarorn}"

{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) inplay daily report ==="
  .venv/bin/inplay-daily-report --user-id "${USER_ID}" --quiet
  .venv/bin/python scripts/check_model_regression.py || {
    code=$?
    echo "check_model_regression exit ${code}"
    exit "${code}"
  }

  if [[ "${SKIP_HF_PUBLISH:-0}" != "1" ]]; then
    if [[ -n "${HF_TOKEN:-${HUGGING_FACE_HUB_TOKEN:-}}" ]]; then
      echo "=== HF publish (reports) ==="
      ./scripts/publish-reports-hf.sh || echo "publish-reports-hf falhou (exit $?)"
    else
      echo "HF publish pulado (HF_TOKEN ausente; defina no .env ou export HF_TOKEN=...)"
    fi
  fi
} >> "${LOG_FILE}" 2>&1
