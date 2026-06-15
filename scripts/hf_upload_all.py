# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "huggingface_hub>=0.23.0",
# ]
# ///
"""Publica o repositório inteiro no Hugging Face Hub sem filtros de .gitignore.

Inclui data/lake, .env, credentials, .venv, node_modules, parquet, etc.
A biblioteca HF só exclui `.git/` e `.cache/huggingface/` (limite interno).

Uso::

    python scripts/hf_upload_all.py
    python scripts/hf_upload_all.py --repo-id beAnalytic/api-noticia --public
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload completo para Hugging Face Hub")
    parser.add_argument(
        "--repo-id",
        default="beAnalytic/api-noticia",
        help="Repo destino (padrão: beAnalytic/api-noticia)",
    )
    parser.add_argument(
        "--repo-type",
        default="dataset",
        choices=["dataset", "model", "space"],
        help="Tipo do repo HF (padrão: dataset)",
    )
    parser.add_argument(
        "--private",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Repo privado (recomendado: contém .env e credentials)",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=REPO_ROOT,
        help="Pasta raiz a enviar (padrão: raiz do projeto)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        raise SystemExit(f"Pasta inválida: {folder}")

    from huggingface_hub import HfApi

    api = HfApi()
    user = api.whoami()
    print(f"Conta HF: {user.get('name') or user.get('fullname')}")
    print(f"Origem:   {folder}")
    print(f"Destino:  https://huggingface.co/{args.repo_id} ({args.repo_type})")
    print(f"Privado:  {args.private}")
    print("Enviando todos os arquivos (sem .gitignore; HF exclui apenas .git/)…")

    api.upload_large_folder(
        folder_path=str(folder),
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        private=args.private,
        ignore_patterns=[],
        num_workers=8,
    )
    print(f"Concluído: https://huggingface.co/{args.repo_id}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
