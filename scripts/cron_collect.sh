#!/usr/bin/env bash
# Cron: 0 8,14,20 * * * /caminho/api_noticia/scripts/cron_collect.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
daily-sync