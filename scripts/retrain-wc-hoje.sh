#!/usr/bin/env bash
# Retreino WC com dados até hoje (jogos finalizados entram; futuros sem vazamento).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate
if [[ -f .env ]]; then set -a; source .env; set +a; fi
exec retrain-wc-hoje "$@"
