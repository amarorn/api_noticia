# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "huggingface_hub>=0.23.0",
# ]
# ///
"""Publica a API Bolão AI no Hugging Face Space (Docker), sem segredos locais.

Envia só o necessário para build: código, fixtures WC, artefato predictor.
Não inclui .env, credentials/, node_modules, lake bronze/silver, etc.

Uso::

    export HF_TOKEN=hf_...
    python scripts/hf_deploy_space.py --repo-id amarorn/model_wc_2026_espoace
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOW_PATTERNS = [
    "README.md",
    "Dockerfile",
    "pyproject.toml",
    "config.py",
    "api/**",
    "ingest/**",
    "models/**",
    "pipelines/**",
    "schemas/**",
    "data/sources.yaml",
    "data/rounds/**",
    "data/wc/**",
    "data/lake/fixtures/world_cup_*.parquet",
    "data/lake/fixtures/brasileirao_*.parquet",
    "data/lake/fixtures/fifa_matches.parquet",
    "data/lake/artifacts/wc_predictor/predictor.pkl",
    "data/lake/artifacts/wc_predictor/manifest.json",
    "scripts/docker-entrypoint.sh",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy Docker Space no Hugging Face Hub")
    parser.add_argument(
        "--repo-id",
        default="amarorn/model_wc_2026_espoace",
        help="Space HF (usuário/nome)",
    )
    parser.add_argument(
        "--private",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Space privado (padrão: público)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        raise SystemExit(
            "Defina HF_TOKEN (https://huggingface.co/settings/tokens). "
            "Não commite o token no repositório."
        )

    artifact_pkl = REPO_ROOT / "data/lake/artifacts/wc_predictor/predictor.pkl"
    artifact_manifest = REPO_ROOT / "data/lake/artifacts/wc_predictor/manifest.json"
    for path in (artifact_pkl, artifact_manifest):
        if not path.is_file():
            raise SystemExit(f"Artefato WC ausente: {path}. Rode train-wc antes do deploy.")

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    user = api.whoami()
    print(f"Conta HF: {user.get('name') or user.get('fullname')}")
    print(f"Space:    https://huggingface.co/spaces/{args.repo_id}")

    api.create_repo(
        repo_id=args.repo_id,
        repo_type="space",
        space_sdk="docker",
        private=args.private,
        exist_ok=True,
    )

    print("Enviando arquivos do Space (allowlist, sem .env/credentials)…")
    api.upload_folder(
        folder_path=str(REPO_ROOT),
        repo_id=args.repo_id,
        repo_type="space",
        allow_patterns=ALLOW_PATTERNS,
        commit_message="Deploy API WC 2026 — Bolão AI",
    )
    print(f"Concluído. Aguarde o build em https://huggingface.co/spaces/{args.repo_id}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
