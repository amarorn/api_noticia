#!/usr/bin/env bash
# Benchmark consolidado da qualidade dos modelos (WC pré-jogo, in-play, walk-forward).
# Uso rápido:  ./scripts/run-model-benchmark.sh
# Sem walk-forward (~5 min): ./scripts/run-model-benchmark.sh --skip-walkforward
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi
if [[ -f .env ]]; then set -a; source .env; set +a; fi
exec run-model-benchmark "$@"
