#!/usr/bin/env bash
# Ambiente dev completo: API + frontend Vite + poll Superbet (futebol WC + beisebol).
#
# Uso:
#   ./scripts/dev-full.sh              # sobe tudo (mata processos nas portas 8000/5173 antes)
#   ./scripts/dev-full.sh stop         # para serviços iniciados por este script
#   ./scripts/dev-full.sh status       # verifica portas e PIDs
#
# Variáveis (opcional, export ou .env):
#   API_PORT=8000
#   FRONTEND_PORT=5173
#   DEV_API_RELOAD=1          # reload só em api/ (padrão: stable, sem reload)
#   SKIP_POLL=1               # não inicia nenhum poll Superbet
#   POLL_BASEBALL=1           # foco beisebol: pula poll futebol/WC (equiv. SKIP_POLL_FOOTBALL=1)
#   SKIP_POLL_FOOTBALL=1      # só poll de beisebol (se poll ativo)
#   SKIP_POLL_BASEBALL=1      # só poll WC/futebol (se poll ativo)
#   SKIP_FRONTEND=1           # só API + poll
#   NO_KILL_PORTS=1           # não mata processos já nas portas
#   SUPERBET_POLL_INTERVAL_SEC=120
#   POLL_EVENT_IDS=11499852   # IDs fixos (futebol); vazio = --wc-copa --auto
#   POLL_BASEBALL_EVENT_IDS=  # IDs fixos beisebol; vazio = --baseball --auto
#   DEV_LOG_DIR=./.dev/logs
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
DEV_LOG_DIR="${DEV_LOG_DIR:-$ROOT/.dev/logs}"
PID_FILE="$ROOT/.dev/dev-full.pids"
POLL_PID_FILE="$ROOT/.dev/dev-full.poll.pid"
POLL_BASEBALL_PID_FILE="$ROOT/.dev/dev-full.poll-baseball.pid"
POLL_INTERVAL="${SUPERBET_POLL_INTERVAL_SEC:-${POLL_INTERVAL_SEC:-120}}"

_red() { printf '\033[0;31m'; }
_grn() { printf '\033[0;32m'; }
_ylw() { printf '\033[0;33m'; }
_cyn() { printf '\033[0;36m'; }
_rst() { printf '\033[0m'; }

load_env() {
  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
}

kill_port() {
  local port=$1
  local attempt
  for attempt in 1 2 3 4 5 6; do
    local pids
    pids="$(lsof -ti:"$port" 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
      return 0
    fi
    if [[ "$attempt" -le 2 ]]; then
      echo "$pids" | xargs kill 2>/dev/null || true
    else
      echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
    sleep 0.4
  done
  if lsof -ti:"$port" >/dev/null 2>&1; then
    _red
    echo "Erro: porta ${port} ainda em uso. Rode: ./scripts/dev-full.sh stop" >&2
    lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    _rst
    return 1
  fi
}

kill_project_uvicorn() {
  pkill -f "uvicorn api.main:app.*--port ${API_PORT}" 2>/dev/null || true
  pkill -f "uvicorn api.main:app --host 127.0.0.1 --port ${API_PORT}" 2>/dev/null || true
  sleep 0.3
}

stop_services() {
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      [[ -n "$pid" ]] || continue
      kill "$pid" 2>/dev/null || true
    done <"$PID_FILE"
    sleep 0.3
    while read -r pid; do
      [[ -n "$pid" ]] || continue
      kill -9 "$pid" 2>/dev/null || true
    done <"$PID_FILE"
  fi
  rm -f "$PID_FILE" "$POLL_PID_FILE" "$POLL_BASEBALL_PID_FILE"
  kill_project_uvicorn
  kill_port "$API_PORT" || true
  kill_port "$FRONTEND_PORT" || true
  _grn
  echo "Serviços dev-full parados."
  _rst
}

status_services() {
  echo "Portas:"
  for port in "$API_PORT" "$FRONTEND_PORT"; do
    if lsof -ti:"$port" >/dev/null 2>&1; then
      _grn
      echo "  :$port — em uso (PID $(lsof -ti:"$port" | tr '\n' ' '))"
      _rst
    else
      _ylw
      echo "  :$port — livre"
      _rst
    fi
  done
  if [[ -f "$PID_FILE" ]]; then
    echo "PIDs registrados ($PID_FILE):"
    cat "$PID_FILE"
  else
    echo "Nenhum PID dev-full registrado."
  fi
  for label_file in \
    "poll futebol:$POLL_PID_FILE" \
    "poll beisebol:$POLL_BASEBALL_PID_FILE"
  do
    local label="${label_file%%:*}"
    local file="${label_file#*:}"
    if [[ -f "$file" ]]; then
      local ppid
      ppid="$(cat "$file" 2>/dev/null || true)"
      if [[ -n "$ppid" ]] && kill -0 "$ppid" 2>/dev/null; then
        _grn
        echo "  ${label}: ativo (PID ${ppid})"
        _rst
      else
        _ylw
        echo "  ${label}: registrado mas morto (${file})"
        _rst
      fi
    else
      echo "  ${label}: não iniciado"
    fi
  done
}

ensure_prereqs() {
  if [[ ! -f .venv/bin/activate ]]; then
    _red
    echo "Erro: .venv não encontrado. Rode: python -m venv .venv && pip install -e \".[dev]\"" >&2
    _rst
    exit 1
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate

  if [[ "${SKIP_FRONTEND:-0}" != "1" ]] && [[ ! -d frontend/node_modules ]]; then
    _ylw
    echo "Instalando dependências do frontend (npm install)…"
    _rst
    (cd frontend && npm install)
  fi

  mkdir -p "$DEV_LOG_DIR" "$(dirname "$PID_FILE")"
}

record_pid() {
  echo "$1" >>"$PID_FILE"
}

assert_process_alive() {
  local pid=$1
  local label=$2
  if ! kill -0 "$pid" 2>/dev/null; then
    _red
    echo "Erro: ${label} encerrou logo após iniciar (PID ${pid})." >&2
    echo "  Veja ${DEV_LOG_DIR}/ e rode: ./scripts/dev-full.sh stop" >&2
    _rst
    stop_services
    exit 1
  fi
}

prefix_log() {
  local tag=$1
  while IFS= read -r line; do
    printf '[%s] %s\n' "$tag" "$line"
  done
}

start_api() {
  local api_cmd
  if [[ "${DEV_API_RELOAD:-1}" == "1" ]]; then
    api_cmd=(
      uvicorn api.main:app --reload --host 127.0.0.1 --port "$API_PORT"
      --reload-dir api --reload-dir ingest --reload-dir models --reload-dir schemas --reload-dir pipelines
    )
  else
    api_cmd=(uvicorn api.main:app --host 127.0.0.1 --port "$API_PORT")
  fi
  _cyn
  echo "→ API http://127.0.0.1:${API_PORT} (log: ${DEV_LOG_DIR}/api.log)"
  _rst
  (
    "${api_cmd[@]}" 2>&1 | tee -a "$DEV_LOG_DIR/api.log" | prefix_log "api"
  ) &
  API_WRAPPER_PID=$!
  record_pid "$API_WRAPPER_PID"
  sleep 0.8
  assert_process_alive "$API_WRAPPER_PID" "API"
}

start_poll_football() {
  local poll_args=(--wc-copa --interval "$POLL_INTERVAL" --no-train)
  if [[ -n "${POLL_EVENT_IDS:-}" ]]; then
    poll_args=(--event-ids "$POLL_EVENT_IDS" --interval "$POLL_INTERVAL" --no-train --phase "${POLL_PHASE:-group}")
  fi
  _cyn
  echo "→ Poll Superbet futebol/WC (intervalo ${POLL_INTERVAL}s) — log: ${DEV_LOG_DIR}/poll.log"
  _rst
  (
    poll-superbet-live "${poll_args[@]}" 2>&1 | tee -a "$DEV_LOG_DIR/poll.log" | prefix_log "poll"
  ) &
  record_pid "$!"
  echo "$!" >"$POLL_PID_FILE"
}

start_poll_baseball() {
  local poll_args=(--baseball --interval "$POLL_INTERVAL" --fast)
  if [[ -n "${POLL_BASEBALL_EVENT_IDS:-}" ]]; then
    # Mantém --baseball para usar o motor de beisebol (não o WC).
    poll_args=(
      --baseball
      --event-ids "$POLL_BASEBALL_EVENT_IDS"
      --interval "$POLL_INTERVAL"
      --fast
    )
  fi
  _cyn
  echo "→ Poll Superbet beisebol (intervalo ${POLL_INTERVAL}s) — log: ${DEV_LOG_DIR}/poll-baseball.log"
  _rst
  (
    poll-superbet-live "${poll_args[@]}" 2>&1 | tee -a "$DEV_LOG_DIR/poll-baseball.log" | prefix_log "poll-bb"
  ) &
  record_pid "$!"
  echo "$!" >"$POLL_BASEBALL_PID_FILE"
}

start_poll() {
  if [[ "${POLL_BASEBALL:-0}" == "1" ]]; then
    SKIP_POLL_FOOTBALL=1
    _ylw
    echo "→ POLL_BASEBALL=1: poll futebol/WC desativado (só beisebol)"
    _rst
  fi
  if [[ "${SKIP_POLL_FOOTBALL:-0}" != "1" ]]; then
    start_poll_football
  else
    _ylw
    echo "→ Poll futebol/WC pulado (SKIP_POLL_FOOTBALL=1)"
    _rst
  fi
  if [[ "${SKIP_POLL_BASEBALL:-0}" != "1" ]]; then
    start_poll_baseball
  else
    _ylw
    echo "→ Poll beisebol pulado (SKIP_POLL_BASEBALL=1)"
    _rst
  fi
}

_handle_poll_death() {
  local pid_file=$1
  local label=$2
  local log_hint=$3
  local poll_pid=""
  [[ -f "$pid_file" ]] || return 0
  poll_pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$poll_pid" ]] || return 0
  if kill -0 "$poll_pid" 2>/dev/null; then
    return 0
  fi
  _ylw
  echo "${label} encerrou (veja ${log_hint}). API e frontend continuam." >&2
  _rst
  rm -f "$pid_file"
  if [[ -f "$PID_FILE" ]]; then
    grep -vx "$poll_pid" "$PID_FILE" >"${PID_FILE}.tmp" 2>/dev/null && mv "${PID_FILE}.tmp" "$PID_FILE"
  fi
  return 1
}

start_frontend() {
  _cyn
  echo "→ Frontend http://127.0.0.1:${FRONTEND_PORT} (log: ${DEV_LOG_DIR}/frontend.log)"
  _rst
  (
    cd frontend
    npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" 2>&1 \
      | tee -a "$DEV_LOG_DIR/frontend.log" | prefix_log "web"
  ) &
  record_pid "$!"
}

wait_for_api() {
  local i
  for i in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:${API_PORT}/health/live" >/dev/null 2>&1; then
      _grn
      echo "API pronta."
      _rst
      return 0
    fi
    sleep 0.5
  done
  _ylw
  echo "Aviso: API ainda não respondeu em /health/live (pode estar carregando o predictor)…"
  _rst
}

start_all() {
  load_env
  ensure_prereqs

  if [[ "${NO_KILL_PORTS:-0}" != "1" ]]; then
    stop_services
  else
    rm -f "$PID_FILE" "$POLL_PID_FILE" "$POLL_BASEBALL_PID_FILE"
  fi
  : >"$PID_FILE"

  if ! kill_port "$API_PORT"; then
    exit 1
  fi
  if [[ "${SKIP_FRONTEND:-0}" != "1" ]]; then
    kill_port "$FRONTEND_PORT" || exit 1
  fi

  _grn
  echo "══════════════════════════════════════════════════════════"
  echo "  Bolão AI — dev completo (Ctrl+C para parar tudo)"
  echo "══════════════════════════════════════════════════════════"
  _rst

  start_api
  wait_for_api

  if [[ "${SKIP_POLL:-0}" != "1" ]]; then
    start_poll
  fi

  if [[ "${SKIP_FRONTEND:-0}" != "1" ]]; then
    start_frontend
    sleep 0.5
    FRONTEND_PID="$(tail -n 1 "$PID_FILE")"
    assert_process_alive "$FRONTEND_PID" "Frontend"
  fi

  echo ""
  _grn
  echo "URLs:"
  echo "  Frontend:  http://127.0.0.1:${FRONTEND_PORT}"
  echo "  API:       http://127.0.0.1:${API_PORT}/docs"
  echo "  Ao vivo:   http://127.0.0.1:${FRONTEND_PORT}/ao-vivo"
  echo "  Beisebol:  http://127.0.0.1:${FRONTEND_PORT}/ao-vivo  (filtro Beisebol)"
  echo "Logs:        ${DEV_LOG_DIR}/  (poll.log + poll-baseball.log)"
  echo ""
  echo "Parar: Ctrl+C ou ./scripts/dev-full.sh stop"
  _rst

  trap 'stop_services; exit 0' INT TERM

  while true; do
    local dead=0
    local poll_pid=""
    local bb_pid=""

    if [[ -f "$POLL_PID_FILE" ]]; then
      poll_pid="$(cat "$POLL_PID_FILE" 2>/dev/null || true)"
    fi
    if [[ -f "$POLL_BASEBALL_PID_FILE" ]]; then
      bb_pid="$(cat "$POLL_BASEBALL_PID_FILE" 2>/dev/null || true)"
    fi

    while read -r pid; do
      [[ -n "$pid" ]] || continue
      if ! kill -0 "$pid" 2>/dev/null; then
        if [[ -n "$poll_pid" && "$pid" == "$poll_pid" ]]; then
          continue
        fi
        if [[ -n "$bb_pid" && "$pid" == "$bb_pid" ]]; then
          continue
        fi
        dead=1
      fi
    done <"$PID_FILE"

    _handle_poll_death "$POLL_PID_FILE" "Poll Superbet futebol/WC" "${DEV_LOG_DIR}/poll.log" || true
    _handle_poll_death "$POLL_BASEBALL_PID_FILE" "Poll Superbet beisebol" "${DEV_LOG_DIR}/poll-baseball.log" || true

    if [[ "$dead" == "1" ]]; then
      _red
      echo "Um processo essencial terminou. Encerrando o restante…" >&2
      _rst
      stop_services
      exit 1
    fi
    sleep 2
  done
}

case "${1:-start}" in
  start|"")
    start_all
    ;;
  stop)
    stop_services
    ;;
  status)
    status_services
    ;;
  -h|--help)
    sed -n '2,24p' "$0" | sed 's/^# \?//'
    ;;
  *)
    echo "Comando desconhecido: $1 (use start | stop | status | --help)" >&2
    exit 1
    ;;
esac
