#!/usr/bin/env bash
# Retreina todos os modelos: WC pré-jogo, in-play (Hawkes/GBM/feedback), palpites.
# Uso rápido:  ./scripts/retrain-all-models.sh
# Só in-play:   ./scripts/retrain-all-models.sh --skip-pregame --skip-predictions
# Completo+eval: ./scripts/retrain-all-models.sh --with-benchmark --with-walkforward
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi
if [[ -f .env ]]; then set -a; source .env; set +a; fi
exec retrain-all-models "$@"
