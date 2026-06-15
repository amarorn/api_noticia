"""Lembrete semanal para exportar CSV Superbet (Fase A+4)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings
from ingest.user_transactions.wallet_inbox import get_wallet_sync_status, scan_inbox

logger = logging.getLogger(__name__)


def run_wallet_reminder(user_id: str, *, import_inbox: bool = True) -> dict[str, Any]:
    """Verifica status da carteira e registra lembrete se CSV estiver desatualizado."""
    status = get_wallet_sync_status(user_id)
    now = datetime.now(UTC).isoformat()

    result: dict[str, Any] = {
        "checked_at": now,
        "user_id": user_id,
        "sync_status": status,
        "action": "none",
        "message": "",
    }

    needs_attention = (
        status.get("stale")
        or status.get("n_pending", 0) > 0
        or status.get("n_uploads", 0) == 0
    )

    if status.get("n_pending", 0) > 0 and import_inbox and settings.wallet_inbox_enabled:
        inbox = scan_inbox(user_id, reconcile=True)
        result["inbox_import"] = inbox.to_dict()
        result["action"] = "imported_inbox"
        result["message"] = f"Importados {inbox.n_imported} CSV(s) da inbox."
        needs_attention = status.get("stale") or status.get("n_uploads", 0) == 0

    if needs_attention:
        days = status.get("days_since_upload")
        if status.get("n_uploads", 0) == 0:
            msg = (
                f"[CARTEIRA] Nenhum CSV importado para {user_id}. "
                f"Exporte na Superbet → {status.get('inbox_dir')}/"
            )
        elif status.get("stale"):
            msg = (
                f"[CARTEIRA] CSV desatualizado ({days} dias) — usuário {user_id}. "
                f"Exporte novo extrato Superbet → {status.get('inbox_dir')}/"
            )
        else:
            msg = f"[CARTEIRA] Verifique carteira do usuário {user_id}."

        if result["action"] == "none":
            result["action"] = "reminder"
            result["message"] = msg

        logger.warning(msg)
        _append_reminder_log(msg, result)
    else:
        result["message"] = f"Carteira OK — último upload há {days} dias."
        logger.info("wallet_reminder_ok", user_id=user_id, days=days)

    return result


def _append_reminder_log(message: str, payload: dict[str, Any]) -> Path:
    log_dir = Path(settings.lake_root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "wallet_reminder.log"
    line = json.dumps({"message": message, **payload}, ensure_ascii=False)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return log_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lembrete semanal: exporte CSV Superbet se carteira estiver desatualizada."
    )
    parser.add_argument(
        "--user",
        default=settings.superbet_finalize_user_id,
        help="ID do usuário",
    )
    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Só lembrar, sem importar inbox",
    )
    args = parser.parse_args()

    outcome = run_wallet_reminder(args.user, import_inbox=not args.no_import)
    print(outcome.get("message", "ok"))
    if outcome.get("action") == "reminder":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
