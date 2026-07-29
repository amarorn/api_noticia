#!/usr/bin/env bash
# Poll contínuo Superbet — beisebol (KBO/MLB/NPB, sport_id=20).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
exec poll-superbet-live --baseball --interval "${SUPERBET_POLL_INTERVAL_SEC:-120}" --fast "$@"
