#!/usr/bin/env bash
# Gera data/rounds/current.json a partir das fixtures (OpenFootball).
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m pipelines.sync_current_round "$@"
