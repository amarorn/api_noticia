#!/usr/bin/env bash
# Publica lake + artefatos + código no Hugging Face (bucket amarorn).
#
# Camadas (use flags para reduzir escopo):
#   padrão     → artefatos + relatórios/métricas WS1
#   --full     → projeto inteiro (rsync-like, exclui .venv/node_modules)
#   --with-ticks → inclui live_ticks.parquet (pode ser grande)
#
# Pré-requisitos:
#   export HF_TOKEN=hf_...
#   pip install -U 'huggingface_hub[cli]'
#
# Uso:
#   ./scripts/hf_sync_all.sh
#   ./scripts/hf_sync_all.sh --dry-run
#   ./scripts/hf_sync_all.sh --full
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DRY_RUN=""
FULL=false
WITH_TICKS=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN="--dry-run" ;;
    --full) FULL=true ;;
    --with-ticks) WITH_TICKS=true ;;
    -h|--help)
      sed -n '2,22p' "$0"
      exit 0
      ;;
    *)
      echo "Opção desconhecida: $arg" >&2
      exit 1
      ;;
  esac
done

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DRY_ARGS=()
if [[ -n "$DRY_RUN" ]]; then
  DRY_ARGS=("$DRY_RUN")
fi

echo "══════════════════════════════════════════════════════════"
echo "  HF sync — api-noticia"
echo "══════════════════════════════════════════════════════════"

echo ""
echo "→ Artefatos (data/lake/artifacts/)"
# shellcheck disable=SC2086
./scripts/publish-artifacts.sh ${DRY_ARGS[@]+"${DRY_ARGS[@]}"}

echo ""
echo "→ Relatórios WS1 (reports + metrics_history.parquet)"
# shellcheck disable=SC2086
./scripts/publish-reports-hf.sh ${DRY_ARGS[@]+"${DRY_ARGS[@]}"}

if [[ "$WITH_TICKS" == true ]]; then
  echo ""
  echo "→ Live ticks (bronze/superbet/live_ticks.parquet)"
  TICKS="$ROOT/data/lake/bronze/superbet/live_ticks.parquet"
  BUCKET="${HF_BUCKET:-hf://buckets/amarorn/model_wc_2026}"
  DEST="${BUCKET%/}/lake/bronze/superbet"
  HF_BIN="${HF_BIN:-hf}"
  command -v "$HF_BIN" >/dev/null 2>&1 || HF_BIN="$ROOT/.venv/bin/hf"
  if [[ -f "$TICKS" ]]; then
    STAGING="$ROOT/data/lake/.hf_publish_ticks"
    mkdir -p "$STAGING"
    cp "$TICKS" "$STAGING/live_ticks.parquet"
    SYNC=( "$HF_BIN" sync "$STAGING" "$DEST" )
    [[ -n "$DRY_RUN" ]] && SYNC+=("$DRY_RUN")
    "${SYNC[@]}"
    rm -rf "$STAGING"
    echo "Ticks publicados: $DEST/live_ticks.parquet"
  else
    echo "Aviso: $TICKS não encontrado — pulando"
  fi
fi

if [[ "$FULL" == true ]]; then
  echo ""
  echo "→ Projeto completo (código + data/lake local)"
  # shellcheck disable=SC2086
  ./scripts/hf_sync_project_bucket.sh ${DRY_ARGS[@]+"${DRY_ARGS[@]}"}
fi

echo ""
echo "Concluído. Bucket: ${HF_BUCKET:-hf://buckets/amarorn/model_wc_2026}"
