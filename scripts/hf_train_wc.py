# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "scikit-learn>=1.4.0",
#   "pandas>=2.2.0",
#   "pyarrow>=15.0.0",
#   "pydantic>=2.6.0",
#   "pydantic-settings>=2.2.0",
#   "structlog>=24.1.0",
#   "huggingface_hub>=0.23.0",
#   "httpx>=0.27.0",
#   "pyyaml>=6.0.0",
#   "numpy>=1.26.0",
# ]
# ///
"""Treina o modelo WC (train-wc) em Hugging Face Jobs (CPU).

Assume que o job roda com cwd na raiz do repositório clonado — HF Jobs monta
o repo em /workspace. O script adiciona a raiz ao ``sys.path``, baixa dados
do dataset Hub para ``./data/`` e persiste artefatos no artifact-repo.

Exemplo::

    hf jobs uv run scripts/hf_train_wc.py --flavor cpu-upgrade --timeout 15m \\
      --secrets HF_TOKEN -- \\
      --dataset-repo USER/api-noticia-wc-train-data \\
      --artifact-repo USER/api-noticia-wc-artifacts \\
      --force
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

# LAKE_PRIMARY deve ser definido antes de qualquer import do projeto.
os.environ["LAKE_PRIMARY"] = "local"

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Treina modelo WC no Hugging Face Jobs e publica artefatos no Hub",
    )
    parser.add_argument(
        "--dataset-repo",
        type=str,
        required=True,
        help="Repo HF (dataset) com estrutura data/lake/fixtures, data/wc/, etc.",
    )
    parser.add_argument(
        "--artifact-repo",
        type=str,
        required=True,
        help="Repo HF (model) para upload de predictor.pkl e manifest.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Ignora artefato em cache e força retreino",
    )
    parser.add_argument(
        "--data-prefix",
        type=str,
        default="",
        help="Prefixo opcional no dataset-repo (ex.: v1/ → v1/data/...)",
    )
    return parser.parse_args()


def _resolve_data_root(snapshot_dir: Path, data_prefix: str) -> Path:
    base = snapshot_dir
    prefix = data_prefix.strip("/")
    if prefix:
        base = snapshot_dir / prefix
    data_root = base / "data"
    if not data_root.is_dir():
        raise FileNotFoundError(
            f"Diretório data/ não encontrado em {base}. "
            "Verifique --data-prefix e a estrutura do dataset-repo."
        )
    return data_root


def download_and_sync_dataset(repo_id: str, data_prefix: str) -> None:
    from huggingface_hub import snapshot_download

    print(f"Baixando dataset {repo_id}...")
    snapshot_dir = Path(
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir_use_symlinks=False,
        )
    )
    data_root = _resolve_data_root(snapshot_dir, data_prefix)
    target = Path("data")
    copied = 0
    for src in data_root.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(data_root)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    print(f"Dataset sincronizado: {copied} arquivos em {target.resolve()}")


def upload_artifacts(repo_id: str, artifact_dir: Path) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name in ("predictor.pkl", "manifest.json"):
        path = artifact_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Artefato ausente após treino: {path}")
        print(f"Enviando {name} → {repo_id}...")
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=name,
            repo_id=repo_id,
            repo_type="model",
            commit_message=f"wc train {stamp}",
        )
    print(f"Artefatos publicados em https://huggingface.co/{repo_id}")


def _print_manifest_metrics(manifest: dict) -> None:
    training = manifest.get("training_metrics") or {}
    collab = manifest.get("collab_metrics") or {}
    print("--- Métricas do manifest ---")
    print(f"created_at: {manifest.get('created_at')}")
    print(f"fixture_rows: {manifest.get('fixture_rows')}")
    if "holdout_accuracy" in training:
        print(f"holdout_accuracy: {training['holdout_accuracy']}")
    if "holdout_brier" in training:
        print(f"holdout_brier: {training['holdout_brier']}")
    if "holdout_log_loss" in training:
        print(f"holdout_log_loss: {training['holdout_log_loss']}")
    if "brier_score" in collab:
        print(f"ensemble_brier: {collab['brier_score']}")
    if "log_loss" in collab:
        print(f"ensemble_log_loss: {collab['log_loss']}")
    if "accuracy" in collab:
        print(f"ensemble_accuracy: {collab['accuracy']}")
    print(f"ensemble_weights: {manifest.get('ensemble_weights')}")
    print(f"loaded_from_cache: {manifest.get('loaded_from_cache')}")


def main() -> None:
    args = parse_args()

    download_and_sync_dataset(args.dataset_repo, args.data_prefix)

    import structlog

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    from config import settings
    from models.wc_artifact import load_or_train_wc_predictor
    from models.wc_train_progress import WcTrainProgressReporter

    fixtures = sorted(settings.fixtures_path.glob("world_cup_*.parquet"))
    if not fixtures:
        raise FileNotFoundError(
            f"Nenhum fixture world_cup_*.parquet em {settings.fixtures_path}. "
            "Verifique o conteúdo do dataset-repo."
        )
    print(f"Fixtures encontrados: {len(fixtures)} arquivos")

    reporter = WcTrainProgressReporter(console=True)
    if args.force:
        print("Modo force: retreino completo")

    _predictor, manifest = load_or_train_wc_predictor(
        force=args.force,
        progress=reporter,
        enable_mlflow=False,
    )

    artifact_dir = settings.wc_artifact_dir
    print(f"Artefato local: {artifact_dir.resolve()}")
    _print_manifest_metrics(manifest)
    upload_artifacts(args.artifact_repo, artifact_dir)


if __name__ == "__main__":
    main()
