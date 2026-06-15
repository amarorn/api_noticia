"""CLI: upload-user-csv — sobe um CSV de transações Superbet para bronze."""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from ingest.user_transactions.parser import parse_user_csv_file
from ingest.user_transactions.store import save_transactions_bronze


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sobe um CSV de transações Superbet para o bronze do datalake."
    )
    parser.add_argument("--file", required=True, help="Caminho do CSV")
    parser.add_argument("--user", required=True, help="ID do usuário (ex: jamarorn)")
    parser.add_argument("--upload-id", help="UUID do upload (opcional)")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Erro: arquivo não encontrado: {path}", file=sys.stderr)
        return 1

    upload_id = args.upload_id or str(uuid.uuid4())
    rows = parse_user_csv_file(path, args.user, upload_id)

    if not rows:
        print("Erro: nenhuma linha válida no CSV", file=sys.stderr)
        return 2

    out = save_transactions_bronze(rows, args.user, upload_id)
    n_inplay = sum(1 for r in rows if r.is_inplay_bet and r.is_bet_placed)
    n_wins = sum(1 for r in rows if r.is_win)

    print(f"OK — upload_id={upload_id}")
    print(f"   linhas={len(rows)} inplay_placed={n_inplay} wins={n_wins}")
    print(f"   bronze: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
