#!/usr/bin/env bash
# Publica relatórios WS1 + métricas no bucket Hugging Face.
#
# Pré-requisitos:
#   pip install -U 'huggingface_hub[cli]'   # ou: hf CLI no PATH
#   export HF_TOKEN=hf_...                  # https://huggingface.co/settings/tokens
#
# Uso:
#   ./scripts/publish-reports-hf.sh
#   ./scripts/publish-reports-hf.sh --dry-run
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORTS_DIR="${REPORTS_DIR:-$ROOT/data/lake/reports}"
METRICS_PATH="${METRICS_PATH:-$ROOT/data/lake/metrics_history.parquet}"
BUCKET="${HF_BUCKET:-hf://buckets/amarorn/model_wc_2026}"
DEST="${BUCKET%/}/lake/reports"
DRY_RUN=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN="--dry-run" ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo "Opção desconhecida: $arg (use --dry-run)" >&2
      exit 1
      ;;
  esac
done

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${HF_TOKEN:-}" && -z "${HUGGING_FACE_HUB_TOKEN:-}" ]]; then
  HF_BIN="${HF_BIN:-hf}"
  if ! command -v "$HF_BIN" >/dev/null 2>&1; then
    HF_BIN="$ROOT/.venv/bin/hf"
  fi
  if command -v "$HF_BIN" >/dev/null 2>&1 && "$HF_BIN" auth whoami >/dev/null 2>&1; then
    echo "Usando login HF em cache ($( "$HF_BIN" auth whoami 2>/dev/null | head -1 ))"
  else
    echo "Defina HF_TOKEN (https://huggingface.co/settings/tokens) ou rode: hf auth login" >&2
    exit 1
  fi
fi

HF_BIN="${HF_BIN:-hf}"
if ! command -v "$HF_BIN" >/dev/null 2>&1; then
  HF_BIN="$ROOT/.venv/bin/hf"
fi
if ! command -v "$HF_BIN" >/dev/null 2>&1; then
  echo "CLI 'hf' não encontrado. Rode: pip install -U 'huggingface_hub[cli]'" >&2
  exit 1
fi

"$HF_BIN" auth login --token "${HF_TOKEN:-$HUGGING_FACE_HUB_TOKEN}" >/dev/null 2>&1 || true

STAGING="$ROOT/data/lake/.hf_publish_reports"
rm -rf "$STAGING"
mkdir -p "$STAGING"

if [[ -d "$REPORTS_DIR" ]]; then
  # Copia JSON/parquet de reports (inplay_daily_*, inplay_weekly_*, baselines, model_benchmark_*)
  cp -R "$REPORTS_DIR"/. "$STAGING/" 2>/dev/null || true
fi

if [[ -f "$METRICS_PATH" ]]; then
  cp "$METRICS_PATH" "$STAGING/metrics_history.parquet"
fi

if [[ ! "$(ls -A "$STAGING" 2>/dev/null)" ]]; then
  echo "Nada para publicar em $REPORTS_DIR / $METRICS_PATH" >&2
  exit 1
fi

SYNC_CMD=("$HF_BIN" sync "$STAGING" "$DEST")
if [[ -n "$DRY_RUN" ]]; then
  SYNC_CMD+=("$DRY_RUN")
fi

echo "Origem (staging): $STAGING"
echo "Destino HF:       $DEST"
file_count="$(find "$STAGING" -type f | wc -l | tr -d ' ')"
echo "Arquivos:         $file_count"

"${SYNC_CMD[@]}"

if [[ -z "$DRY_RUN" ]]; then
  PUBLISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  MANIFEST="$REPORTS_DIR/hf_publish_manifest.json"
  PY="$ROOT/.venv/bin/python"
  [[ -x "$PY" ]] || PY=python3
  "$PY" - "$MANIFEST" "$PUBLISHED_AT" "$DEST" "$STAGING" <<'PY'
import json
import sys
from pathlib import Path

manifest_path, published_at, dest, staging = sys.argv[1:5]
root = Path(staging)
files = [
    {"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size}
    for p in sorted(root.rglob("*"))
    if p.is_file()
]
payload = {
    "published_at": published_at,
    "destination": dest,
    "file_count": len(files),
    "files": files,
}
Path(manifest_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Manifest: {manifest_path}")
PY
fi

echo "Relatórios publicados no HF: $DEST"
