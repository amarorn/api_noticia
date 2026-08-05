#!/usr/bin/env bash
# Publica data/lake/artifacts/ no bucket HF (modelos e coeficientes versionados).
#
# Não envia o projeto inteiro — só artefatos de modelo. Por padrão exclui
# snapshots intermediários de feedback GBM e caches reconstruíveis.
#
# Pré-requisitos:
#   pip install -U 'huggingface_hub[cli]'
#   export HF_TOKEN=hf_...
#
# Uso:
#   ./scripts/publish-artifacts.sh
#   ./scripts/publish-artifacts.sh --dry-run
#   ./scripts/publish-artifacts.sh --include-feedback --include-cache
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-$ROOT/data/lake/artifacts}"
BUCKET="${HF_BUCKET:-hf://buckets/amarorn/model_wc_2026}"
DEST="${BUCKET%/}/artifacts"

DRY_RUN=""
INCLUDE_FEEDBACK=false
INCLUDE_CACHE=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN="--dry-run" ;;
    --include-feedback) INCLUDE_FEEDBACK=true ;;
    --include-cache) INCLUDE_CACHE=true ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Opção desconhecida: $arg (use --dry-run, --include-feedback, --include-cache)" >&2
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

if [[ ! -d "$ARTIFACTS_DIR" ]]; then
  echo "Pasta de artefatos não encontrada: $ARTIFACTS_DIR" >&2
  exit 1
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

"$HF_BIN" auth login --token "${HF_TOKEN:-$HUGGING_FACE_HUB_TOKEN}" >/dev/null 2>&1 || true

SYNC_CMD=("$HF_BIN" sync "$ARTIFACTS_DIR" "$DEST")
if [[ -n "$DRY_RUN" ]]; then
  SYNC_CMD+=("$DRY_RUN")
fi

# Snapshots intermediários do loop de feedback (dezenas de .pkl por dia).
if [[ "$INCLUDE_FEEDBACK" != true ]]; then
  SYNC_CMD+=(--exclude "inplay_gbm_feedback_v*/**")
fi

# Caches reconstruíveis no treino; não são necessários em runtime.
if [[ "$INCLUDE_CACHE" != true ]]; then
  SYNC_CMD+=(--exclude "wc_predictor/logistic_features_cache.json")
  SYNC_CMD+=(--exclude "wc_predictor/train_progress.json")
fi

echo "Origem:  $ARTIFACTS_DIR"
echo "Destino: $DEST"
if [[ "$INCLUDE_FEEDBACK" != true ]]; then
  echo "Exclui:  inplay_gbm_feedback_v* (use --include-feedback para enviar)"
fi
if [[ "$INCLUDE_CACHE" != true ]]; then
  echo "Exclui:  logistic_features_cache.json, train_progress.json"
fi

"${SYNC_CMD[@]}"

# Manifest local de publicação (gitignored em data/lake/).
if [[ -z "$DRY_RUN" ]]; then
  PUBLISHED_AT="$(date -u +%Y%m%dT%H%M%SZ)"
  MANIFEST="$ARTIFACTS_DIR/publish_manifest.json"
  python3 - "$MANIFEST" "$PUBLISHED_AT" "$DEST" "$INCLUDE_FEEDBACK" "$INCLUDE_CACHE" <<'PY'
import json
import sys
from pathlib import Path

manifest_path, published_at, dest, inc_fb, inc_cache = sys.argv[1:6]
root = Path(manifest_path).parent
files: list[dict] = []
for path in sorted(root.rglob("*")):
    if not path.is_file():
        continue
    rel = path.relative_to(root).as_posix()
    if rel == "publish_manifest.json":
        continue
    if inc_fb != "true" and rel.startswith("inplay_gbm_feedback_v"):
        continue
    if inc_cache != "true" and rel in {
        "wc_predictor/logistic_features_cache.json",
        "wc_predictor/train_progress.json",
    }:
        continue
    st = path.stat()
    files.append({"path": rel, "bytes": st.st_size, "mtime_ns": st.st_mtime_ns})

payload = {
    "published_at": published_at,
    "destination": dest,
    "include_feedback": inc_fb == "true",
    "include_cache": inc_cache == "true",
    "file_count": len(files),
    "files": files,
}
Path(manifest_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Manifest local: {manifest_path} ({len(files)} arquivos)")
PY
fi

echo "Publicação concluída: $DEST"
