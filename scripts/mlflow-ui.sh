#!/usr/bin/env bash
# Sobe MLflow UI apontando para mlflow.db do projeto.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi
if [[ -f .env ]]; then set -a; source .env; set +a; fi
exec mlflow-ui "$@"
