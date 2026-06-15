"""CLI: watch-wallet-csv — importa CSVs da inbox e reconcilia."""
from __future__ import annotations

import argparse
import sys
import time

from config import settings
from ingest.user_transactions.wallet_inbox import inbox_root, scan_inbox


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Monitora a pasta inbox de CSV Superbet e importa arquivos novos para bronze. "
            f"Padrão: {settings.lake_root}/{settings.wallet_inbox_dir}/{{user_id}}/"
        )
    )
    parser.add_argument(
        "--user",
        default=settings.superbet_finalize_user_id,
        help="ID do usuário (padrão: SUPERBET_FINALIZE_USER_ID)",
    )
    parser.add_argument(
        "--no-reconcile",
        action="store_true",
        help="Só importa bronze, sem reconciliar",
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SEC",
        help="Repete a cada N segundos (padrão: executa uma vez)",
    )
    args = parser.parse_args()

    if not settings.wallet_inbox_enabled:
        print("Wallet inbox desabilitada (WALLET_INBOX_ENABLED=false)", file=sys.stderr)
        return 1

    user_id = args.user
    reconcile = not args.no_reconcile
    interval = args.loop

    folder = inbox_root(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    print(f"Inbox: {folder}")

    def _run_once() -> int:
        outcome = scan_inbox(user_id, reconcile=reconcile)
        if outcome.n_imported:
            print(f"Importados: {outcome.n_imported}")
            for imp in outcome.imports:
                if imp.imported:
                    print(f"  + {imp.file_path} → upload_id={imp.upload_id} ({imp.n_rows} linhas)")
        else:
            print("Nenhum CSV novo na inbox.")

        if outcome.reconciliation:
            rec = outcome.reconciliation
            if rec.get("error"):
                print(f"Reconcile erro: {rec['error']}", file=sys.stderr)
                return 3
            if rec.get("n_pairs", 0) > 0:
                print(
                    f"Reconcile: {rec['n_pairs']} pares, "
                    f"{rec.get('n_high_confidence', 0)} alta confiança"
                )

        return 0

    if interval <= 0:
        return _run_once()

    print(f"Loop a cada {interval}s (Ctrl+C para parar)")
    while True:
        code = _run_once()
        if code != 0:
            return code
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
