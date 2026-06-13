#!/usr/bin/env bash
# Poll contínuo Superbet — seleções internacionais (Copa / amistosos).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
exec poll-superbet-live --wc-copa --interval "${SUPERBET_POLL_INTERVAL_SEC:-120}" "$@"
