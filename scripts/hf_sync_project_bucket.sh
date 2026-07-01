#!/usr/bin/env bash
# Sincroniza o projeto inteiro para o bucket HF (rsync-like).
#
# Pré-requisitos:
#   pip install -U 'huggingface_hub[cli]'   # hf sync / hf buckets sync
#   export HF_TOKEN=hf_...                  # conta amarorn
#
# Uso:
#   ./scripts/hf_sync_project_bucket.sh
#   ./scripts/hf_sync_project_bucket.sh --dry-run
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUCKET="${HF_BUCKET:-hf://buckets/amarorn/model_wc_2026}"
DRY_RUN="${1:-}"

cd "$ROOT"

if [[ -z "${HF_TOKEN:-}" && -z "${HUGGING_FACE_HUB_TOKEN:-}" ]]; then
  echo "Defina HF_TOKEN (https://huggingface.co/settings/tokens)" >&2
  exit 1
fi

HF_BIN="${HF_BIN:-hf}"
if ! command -v "$HF_BIN" >/dev/null 2>&1; then
  HF_BIN="$ROOT/.venv/bin/hf"
fi

"$HF_BIN" auth login --token "${HF_TOKEN:-$HUGGING_FACE_HUB_TOKEN}" >/dev/null 2>&1 || true

# Projeto completo: código + data/lake + configs locais.
# Exclui só .git (reconstruível) e caches pesados de dev.
SYNC_CMD=(
  "$HF_BIN" sync "$ROOT" "$BUCKET"
)
if [[ "$DRY_RUN" == "--dry-run" ]]; then
  SYNC_CMD+=(--dry-run)
fi
SYNC_CMD+=(
  --exclude ".git/**"
  --exclude ".venv/**"
  --exclude "node_modules/**"
  --exclude "**/__pycache__/**"
  --exclude ".pytest_cache/**"
  --exclude ".ruff_cache/**"
  --exclude "frontend/dist/**"
  --exclude "mlruns/**"
  --exclude "agent-transcripts/**"
)
"${SYNC_CMD[@]}"

echo "Bucket: $BUCKET"
